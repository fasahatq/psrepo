"""Copilot chat — grounds a question in a selected run's summary and routes it
through the pipeline's own LLM client (``agents.llm_client.call_llm``).

Backend/model are resolved from the environment exactly the way
``pipeline.run_pipeline`` does, so the workbench Copilot uses whatever
``LLM_BACKEND`` is configured (``vertex`` / ``gemini-2.5-flash`` here).
"""

from __future__ import annotations

import json
import logging
import os

from .artifacts import _run_dir, run_summary

logger = logging.getLogger("perfect_store.workbench.copilot")

_SYSTEM = (
    "You are the Perfect Store Copilot, an analyst embedded in a CPG retail-execution "
    "workbench. You help commercial teams read the pipeline's outputs: outlet segments, "
    "A/B/C/D prioritization, opportunity gaps (actual vs potential VPO), Must-Stock Lists "
    "and the leadership deck. Answer in a concise, executive tone. Ground every claim in "
    "the run data provided below; if the data does not cover the question, say so plainly "
    "rather than guessing. Refer to segments by their label and cite slide numbers when "
    "the deck titles make that possible."
)


def _resolve_model() -> tuple[str, str | None, str]:
    backend = os.getenv("LLM_BACKEND", "anthropic").strip().lower()
    if backend == "azure":
        return backend, os.getenv("AZURE_OPENAI_API_KEY"), os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    if backend == "gemini":
        return backend, os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    if backend == "vertex":
        return backend, None, os.getenv("VERTEX_MODEL", "gemini-2.5-flash")
    if backend == "local":
        return backend, None, os.getenv("LOCAL_LLM_MODEL", "gemma3:12b")
    return backend, os.getenv("ANTHROPIC_API_KEY"), os.getenv("CLAUDE_MODEL", "claude-opus-4-6")


def _grounding(run_id: str | None) -> str:
    if not run_id:
        return "No run is selected. Ask the user to open a run in Output Studio first."
    try:
        summ = run_summary(_run_dir(run_id))
    except Exception:
        return f"Run {run_id} could not be loaded."
    if not summ:
        return f"Run {run_id} has no segment summary (all_segments*.csv missing)."

    lines = [f"RUN {run_id} — {summ.get('outlets', '?')} outlets, "
             f"{summ.get('segment_count', '?')} segments, "
             f"{summ.get('priority_tiers', '?')} priority tiers."]
    if summ.get("total_vpo"):
        lines.append(f"Total monthly VPO across the base: {summ['total_vpo']:,.0f}.")
    lines.append("\nSEGMENTS (largest first):")
    for s in summ.get("segments", []):
        lines.append(
            f"- [{s['id']}] {s['label']}: {s['outlets']} outlets ({s['pct_universe']}% of universe), "
            f"avg VPO {_num(s['avg_vpo'])}, avg SKUs {_num(s['avg_skus'])}, "
            f"avg opportunity gap {_num(s['avg_gap'])}."
            + (f" Action: {s['action']}" if s.get("action") else "")
        )
    if summ.get("priority_tiers_table"):
        lines.append("\nPRIORITY TIERS:")
        for t in summ["priority_tiers_table"]:
            lines.append(
                f"- {t['tier']}: {t['outlets']} outlets ({t['pct_universe']}%), "
                f"avg actual VPO {_num(t['avg_actual_vpo'])}, "
                f"avg potential VPO {_num(t['avg_potential_vpo'])}, "
                f"avg gap {_num(t['avg_gap'])}."
            )
    return "\n".join(lines)


def _num(v) -> str:
    return "n/a" if v is None else f"{v:,.0f}"


def answer(messages: list[dict], run_id: str | None) -> dict:
    """`messages` is a list of {role: 'user'|'ai', text: str}. Returns {text, model, backend}."""
    backend, api_key, model = _resolve_model()
    grounding = _grounding(run_id)

    convo = "\n".join(
        f"{'User' if m.get('role') == 'user' else 'Copilot'}: {m.get('text', '')}"
        for m in messages[-8:]
    )
    prompt = (
        f"RUN DATA\n========\n{grounding}\n\n"
        f"CONVERSATION SO FAR\n===================\n{convo}\n\n"
        f"Reply as the Copilot to the user's last message."
    )

    try:
        from agents.llm_client import call_llm
        text = call_llm(prompt, api_key, model, max_tokens=900, system_prompt=_SYSTEM)
        text = (text or "").strip() or "(no response)"
    except Exception as exc:  # noqa: BLE001
        logger.warning("copilot call_llm failed: %s", exc)
        text = ("The Copilot LLM backend is unavailable right now "
                f"({backend}). The run summary is still loaded — try again shortly.")
    return {"text": text, "model": model, "backend": backend}
