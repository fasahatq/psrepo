"""Perfect Store — pipeline control panel.

    venv/bin/streamlit run gui/app.py        (or ./run_gui.sh)

Runs locally in the browser (http://localhost:8501). Nothing is deployed.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from gui.outputs import list_runs, render_run, run_label          # noqa: E402
from gui.runner import PipelineRunner                             # noqa: E402
from gui.steps import STEP_META, STEP_ORDER                       # noqa: E402
from gui.wheel import build_wheel_svg                             # noqa: E402

st.set_page_config(page_title="Perfect Store Pipeline", page_icon="🎯",
                   layout="wide", initial_sidebar_state="expanded")

REFRESH_SECS = 1.2
_STATUS_ICON = {"pending": "⚪", "running": "🟡", "done": "🟢"}


# ── session state ───────────────────────────────────────────────────────────
def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("runner", None)
    ss.setdefault("run_active", False)
    ss.setdefault("steps", {n: "pending" for n in STEP_ORDER})
    ss.setdefault("details", {n: "" for n in STEP_ORDER})
    ss.setdefault("logs", [])
    ss.setdefault("run_done", False)
    ss.setdefault("last_run_dir", None)
    ss.setdefault("view_run", None)


def _reset_progress() -> None:
    ss = st.session_state
    ss.steps = {n: "pending" for n in STEP_ORDER}
    ss.details = {n: "" for n in STEP_ORDER}
    ss.logs = []
    ss.run_done = False


def _apply_events(events: list[dict]) -> None:
    ss = st.session_state
    for ev in events:
        kind = ev.get("kind")
        if kind == "step":
            step, status = ev["step"], ev["status"]
            if step in ss.steps:
                # starting step N implies every earlier step is finished
                if status == "running":
                    for k in STEP_ORDER:
                        if k < step and ss.steps[k] != "done":
                            ss.steps[k] = "done"
                ss.steps[step] = status
                if ev.get("detail"):
                    ss.details[step] = ev["detail"]
            elif step == 8:                       # "complete"
                for k in STEP_ORDER:
                    ss.steps[k] = "done"
                ss.run_done = True
        elif kind == "log":
            ss.logs.append(f"{ev['ts']}  {ev['level']:<5} {ev['name']:<22} {ev['msg']}")
            ss.logs = ss.logs[-600:]
        elif kind == "end":
            ss.run_active = False
            runner: PipelineRunner = ss.runner
            if runner and runner.error:
                ss.logs.append("── TRACEBACK " + "─" * 40)
                ss.logs.extend(runner.error.splitlines())
            elif runner and not runner.error:
                ss.run_done = True
                for k in STEP_ORDER:
                    ss.steps[k] = "done"
            if runner and runner.output_dir:
                ss.last_run_dir = runner.output_dir
                ss.view_run = runner.output_dir


# ── sidebar: pick input + launch ───────────────────────────────────────────
# Column fingerprints that mark a file as a real pipeline input rather than a
# support/reference sheet (pack dimensions, rack comparison, …).
_OUTLET_COLS = {"OUTLET_UID_EDITED", "VPO", "TOTAL_REVENUE"}
_SKU_COLS = {"CUST_UNIQ_ID_VAL", "NET_SALES", "BRND_NM"}
_PREFERRED = "Market_Master_File.csv"


def _fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.0f} TB"


@st.cache_data(show_spinner=False)
def _scan_inbox(inbox_str: str, _sig: tuple) -> list[dict]:
    """Classify every CSV/Excel in inbox/ as 'dataset' (valid input) or
    'reference'. Cached on the folder's (name, mtime, size) signature."""
    inbox = Path(inbox_str)
    entries: list[dict] = []
    for p in sorted(inbox.glob("*")):
        if p.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            continue
        try:
            if p.suffix.lower() == ".csv":
                cols = set(pd.read_csv(p, nrows=0).columns.str.strip())
            else:
                cols = set(pd.read_excel(p, nrows=0).columns.str.strip())
        except Exception:
            cols = set()
        is_dataset = bool(cols & _OUTLET_COLS) or _SKU_COLS.issubset(cols)
        entries.append({"name": p.name, "size": p.stat().st_size,
                        "kind": "dataset" if is_dataset else "reference"})
    entries.sort(key=lambda d: (d["kind"] != "dataset",
                                d["name"] != _PREFERRED, -d["size"]))
    return entries


def _sidebar() -> None:
    ss = st.session_state
    st.sidebar.header("Run a pipeline")

    inbox = Path(PROJECT_ROOT) / "inbox"
    sig = tuple(sorted(
        (p.name, p.stat().st_mtime, p.stat().st_size)
        for p in inbox.glob("*") if p.suffix.lower() in (".csv", ".xlsx", ".xls")
    )) if inbox.is_dir() else ()
    entries = _scan_inbox(str(inbox), sig)

    if not entries:
        st.sidebar.error("No CSV/Excel files in inbox/ — add your outlet data file there.")
        return

    def _label(e: dict) -> str:
        tail = "" if e["kind"] == "dataset" else "  —  reference, not a pipeline input"
        return f"{e['name']}  ({_fmt_size(e['size'])}){tail}"

    sel = st.sidebar.selectbox(
        "Source file (from inbox/)", entries, index=0, format_func=_label,
        disabled=ss.run_active,
    )

    run_anyway = False
    if sel["kind"] == "dataset":
        st.sidebar.caption(f"✅ `{sel['name']}` looks like valid pipeline input.")
    else:
        st.sidebar.warning(
            f"`{sel['name']}` has no outlet/SKU columns — the pipeline will fail "
            f"at prioritization. Pick your outlet data file "
            f"(e.g. `{_PREFERRED}`)."
        )
        run_anyway = st.sidebar.checkbox("Run anyway", value=False,
                                         disabled=ss.run_active)

    use_sample = st.sidebar.checkbox("Sample rows (faster test run)", value=True,
                                     disabled=ss.run_active)
    sample_size = None
    if use_sample:
        sample_size = st.sidebar.number_input(
            "Sample size", min_value=500, max_value=1_000_000, value=5000, step=500,
            disabled=ss.run_active,
        )

    blocked = sel["kind"] == "reference" and not run_anyway
    start = st.sidebar.button("▶  Run pipeline", type="primary",
                              disabled=ss.run_active or blocked, width="stretch")

    st.sidebar.divider()
    st.sidebar.caption(
        f"Backend: `{os.getenv('LLM_BACKEND', 'anthropic')}`  ·  "
        f"root: `{PROJECT_ROOT}`"
    )

    if start:
        processing = Path(PROJECT_ROOT) / "processing"
        processing.mkdir(exist_ok=True)
        src_path = processing / sel["name"]
        src_path.write_bytes((inbox / sel["name"]).read_bytes())

        _reset_progress()
        runner = PipelineRunner()
        runner.start(str(src_path), PROJECT_ROOT,
                     int(sample_size) if sample_size else None)
        ss.runner = runner
        ss.run_active = True
        st.rerun()


# ── main panels ────────────────────────────────────────────────────────────
def _progress_panel() -> None:
    ss = st.session_state
    left, right = st.columns([5, 4], gap="large")

    with left:
        st.markdown("#### Perfect Store execution")
        st.markdown(
            build_wheel_svg(ss.steps, run_active=ss.run_active, run_done=ss.run_done),
            unsafe_allow_html=True,
        )

    with right:
        runner: PipelineRunner | None = ss.runner
        if ss.run_active:
            st.info(f"⏳ Running…  ({runner.elapsed if runner else '0s'})")
        elif ss.run_done:
            st.success(f"✅ Completed in {runner.elapsed if runner else '—'}")
        elif runner and runner.error:
            last = runner.error.strip().splitlines()[-1][:300]
            st.error(f"❌ Run failed — {last}")
            st.caption("Full traceback at the bottom of the log below.")
        else:
            st.caption("Idle — configure a run in the sidebar.")

        done = sum(1 for s in ss.steps.values() if s == "done")
        st.progress(done / len(STEP_ORDER), text=f"{done}/{len(STEP_ORDER)} steps")

        for n in STEP_ORDER:
            status = ss.steps[n]
            line = f"{_STATUS_ICON[status]}  **{n}. {STEP_META[n]}**"
            if ss.details[n]:
                line += f"  \n&nbsp;&nbsp;&nbsp;&nbsp;`{ss.details[n]}`"
            st.markdown(line, unsafe_allow_html=True)

    st.markdown("#### Live log")
    st.text_area("pipeline log", value="\n".join(ss.logs[-400:]) or "—",
                 height=280, label_visibility="collapsed")


def _outputs_panel() -> None:
    ss = st.session_state
    st.markdown("#### Generated outputs")
    runs = list_runs(PROJECT_ROOT)
    if not runs:
        st.info("No runs yet. Launch one from the sidebar.")
        return

    labels = [run_label(r) for r in runs]
    default_idx = 0
    if ss.view_run:
        for i, r in enumerate(runs):
            if str(r) == str(ss.view_run):
                default_idx = i
                break
    pick = st.selectbox("Run", range(len(runs)), index=default_idx,
                        format_func=lambda i: labels[i])
    render_run(runs[pick])


def main() -> None:
    _init_state()
    ss = st.session_state

    st.title("🎯 Perfect Store Pipeline")

    if ss.run_active and ss.runner is not None:
        _apply_events(ss.runner.drain())

    _sidebar()

    tab_run, tab_out = st.tabs(["▶ Run & progress", "📦 Outputs"])
    with tab_run:
        _progress_panel()
    with tab_out:
        _outputs_panel()

    # keep refreshing while a run is in flight
    if ss.run_active:
        time.sleep(REFRESH_SECS)
        st.rerun()


if __name__ == "__main__":
    main()
