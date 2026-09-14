"""Shared UI building blocks for the Perfect Store control panel.

Keeps all raw HTML/CSS in one place so app.py and outputs.py stay readable.
"""

from __future__ import annotations

import html as _html

import streamlit as st
import streamlit.components.v1 as components

_CSS = """
<style>
/* ── hide Streamlit chrome ─────────────────────────────────────────── */
#MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], footer {visibility:hidden; height:0; position:fixed;}

/* ── layout rhythm ────────────────────────────────────────────────── */
.block-container {max-width:1180px; padding-top:1.1rem; padding-bottom:3rem;}
[data-testid="stVerticalBlock"] {gap:0.9rem;}
h1,h2,h3,h4 {letter-spacing:-0.01em;}

:root {
  --ps-border:#e2e8f0; --ps-ink:#0f2942; --ps-mut:#64748b; --ps-card:#ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {--ps-border:#334155; --ps-ink:#e2e8f0; --ps-mut:#94a3b8; --ps-card:#0f172a;}
}

/* ── header ───────────────────────────────────────────────────────── */
.ps-header {display:flex; align-items:center; justify-content:space-between;
  gap:16px; border-bottom:1px solid var(--ps-border); padding-bottom:14px; margin-bottom:18px;}
.ps-brand {display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;}
.ps-brand .mark {font-size:21px; font-weight:800; color:var(--ps-ink);}
.ps-brand .sub {font-size:12.5px; color:var(--ps-mut);}
.ps-pill {font-size:11.5px; font-weight:700; letter-spacing:.02em; text-transform:uppercase;
  padding:5px 12px; border-radius:999px; white-space:nowrap;}
.ps-pill.idle {background:#f1f5f9; color:#475569;}
.ps-pill.running {background:#fef3c7; color:#92400e;}
.ps-pill.done {background:#dcfce7; color:#166534;}
.ps-pill.failed {background:#fee2e2; color:#991b1b;}
.ps-pill.aborted {background:#ffedd5; color:#9a3412;}

/* ── vertical stepper ─────────────────────────────────────────────── */
.ps-stepper {display:flex; flex-direction:column;}
.ps-step {display:grid; grid-template-columns:34px 1fr auto; gap:12px;
  padding:8px 0; position:relative;}
.ps-step:not(:last-child)::before {content:""; position:absolute; left:16px;
  top:34px; bottom:-4px; width:2px; background:var(--ps-border);}
.ps-step .node {width:32px; height:32px; border-radius:50%; display:flex;
  align-items:center; justify-content:center; font-size:13px; font-weight:700;
  border:2px solid var(--ps-border); background:var(--ps-card); color:#94a3b8; z-index:1;}
.ps-step.running .node {border-color:#f59e0b; color:#b45309;
  box-shadow:0 0 0 4px rgba(245,158,11,.18);}
.ps-step.done .node {border-color:#22c55e; background:#22c55e; color:#fff;}
.ps-step .name {font-weight:600; font-size:13.5px; color:var(--ps-ink);}
.ps-step.pending .name {color:#94a3b8;}
.ps-step .detail {font-size:11.5px; color:var(--ps-mut);
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; margin-top:2px;}
.ps-step .time {font-size:12px; color:#94a3b8; align-self:center;
  font-variant-numeric:tabular-nums;}

/* ── callouts ─────────────────────────────────────────────────────── */
.ps-callout {border:1px solid var(--ps-border); border-left:4px solid #64748b;
  border-radius:8px; padding:11px 14px; margin:4px 0; background:var(--ps-card);}
.ps-callout .t {font-weight:600; font-size:13px; color:var(--ps-ink);}
.ps-callout .b {font-size:12.5px; color:var(--ps-mut); margin-top:2px;}
.ps-callout.info {border-left-color:#0ea5e9;}
.ps-callout.warn {border-left-color:#f59e0b;}
.ps-callout.error {border-left-color:#ef4444;}
.ps-callout.empty {border-left-color:#cbd5e1;}

/* ── artifact card header ─────────────────────────────────────────── */
.ps-art {border:1px solid var(--ps-border); border-radius:10px 10px 0 0;
  border-bottom:none; padding:12px 14px 8px; background:var(--ps-card);}
.ps-art .ico {font-size:20px;}
.ps-art .nm {font-weight:600; font-size:12.5px; color:var(--ps-ink);
  margin:5px 0 1px; word-break:break-all; line-height:1.3;}
.ps-art .mt {font-size:11px; color:var(--ps-mut);}
.ps-art .badge {display:inline-block; font-size:10.5px; font-weight:700;
  background:#eef2ff; color:#4338ca; padding:1px 7px; border-radius:999px; margin-left:6px;}
div[data-testid="column"] .stDownloadButton button {border-radius:0 0 10px 10px;
  border:1px solid var(--ps-border); border-top:none; width:100%;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def header(status: str = "idle") -> None:
    """status ∈ idle | running | done | failed | aborted"""
    labels = {"idle": "Idle", "running": "Running", "done": "Complete",
              "failed": "Failed", "aborted": "Aborted"}
    st.markdown(
        f"""<div class="ps-header">
          <div class="ps-brand">
            <span class="mark">Perfect Store</span>
            <span class="sub">Segmentation &amp; Activation Pipeline</span>
          </div>
          <span class="ps-pill {status}">{labels.get(status, "Idle")}</span>
        </div>""",
        unsafe_allow_html=True,
    )


def stepper(steps: list[dict]) -> None:
    """steps: [{n, name, state (pending|running|done), detail, time}]"""
    rows = []
    for s in steps:
        node = "✓" if s["state"] == "done" else str(s["n"])
        detail = f'<div class="detail">{_html.escape(s["detail"])}</div>' if s.get("detail") else ""
        tm = f'<div class="time">{_html.escape(s["time"])}</div>' if s.get("time") else '<div class="time"></div>'
        rows.append(
            f'<div class="ps-step {s["state"]}"><div class="node">{node}</div>'
            f'<div class="body"><div class="name">{_html.escape(s["name"])}</div>{detail}</div>{tm}</div>'
        )
    st.markdown(f'<div class="ps-stepper">{"".join(rows)}</div>', unsafe_allow_html=True)


def callout(kind: str, title: str, body: str = "") -> None:
    """kind ∈ info | warn | error | empty"""
    b = f'<div class="b">{_html.escape(body)}</div>' if body else ""
    st.markdown(
        f'<div class="ps-callout {kind}"><div class="t">{_html.escape(title)}</div>{b}</div>',
        unsafe_allow_html=True,
    )


def art_card_header(icon: str, name: str, meta: str, badge: str = "") -> None:
    b = f'<span class="badge">{_html.escape(badge)}</span>' if badge else ""
    st.markdown(
        f'<div class="ps-art"><div class="ico">{icon}</div>'
        f'<div class="nm">{_html.escape(name)}{b}</div>'
        f'<div class="mt">{_html.escape(meta)}</div></div>',
        unsafe_allow_html=True,
    )


_LEVEL_COLOUR = {"ERROR": "#f87171", "WARN": "#fbbf24", "WARNING": "#fbbf24",
                 "INFO": "#93c5fd", "DEBUG": "#64748b"}


def console(lines: list[str], height: int = 320) -> None:
    """Dark, monospace, auto-scrolled log panel with level colouring + copy."""
    def _colour(ln: str) -> str:
        for lvl, col in _LEVEL_COLOUR.items():
            if f" {lvl} " in f" {ln} " or ln.strip().startswith(lvl):
                return col
        if ln.startswith("──"):
            return "#f87171"
        return "#cbd5e1"

    body = "".join(
        f'<div class="ln" style="color:{_colour(l)}">{_html.escape(l) or "&nbsp;"}</div>'
        for l in lines
    ) or '<div class="ln" style="color:#64748b">— no log output yet —</div>'
    raw = _html.escape("\n".join(lines)).replace("`", "\\`")

    doc = f"""<div style="position:relative;font-family:ui-monospace,SFMono-Regular,Menlo,monospace">
  <button onclick="navigator.clipboard.writeText(`{raw}`);this.textContent='Copied';
    setTimeout(()=>this.textContent='Copy',1200)"
    style="position:absolute;top:8px;right:10px;z-index:2;font:600 11px system-ui;
    padding:3px 10px;border-radius:6px;border:1px solid #334155;background:#1e293b;
    color:#cbd5e1;cursor:pointer">Copy</button>
  <div id="ps-log" style="background:#0b1220;border:1px solid #1e293b;border-radius:8px;
    padding:12px 14px;height:{height - 24}px;overflow:auto;font-size:12px;line-height:1.55;
    white-space:pre-wrap;word-break:break-word">{body}</div>
  <script>var e=document.getElementById('ps-log');e.scrollTop=e.scrollHeight;</script>
</div>"""
    try:
        components.html(doc, height=height, scrolling=False)
    except Exception:  # pragma: no cover - defensive if components.html is removed
        st.code("\n".join(lines) or "— no log output yet —", language="log",
                height=height)
