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

from gui import ui                                                # noqa: E402
from gui.outputs import list_runs, render_run, run_label          # noqa: E402
from gui.runner import PipelineRunner                             # noqa: E402
from gui.steps import STEP_META, STEP_ORDER                       # noqa: E402
from gui.wheel import build_wheel_svg                             # noqa: E402

st.set_page_config(page_title="Perfect Store", page_icon="🎯",
                   layout="wide", initial_sidebar_state="expanded")

REFRESH_SECS = 1.2
_VIEWS = ["Run & progress", "Outputs"]


# ── helpers ────────────────────────────────────────────────────────────────
def _fmt_dur(secs: float) -> str:
    secs = int(secs)
    return f"{secs // 60}m {secs % 60:02d}s" if secs >= 60 else f"{secs}s"


def _qp_get(key: str, default: str = "") -> str:
    try:
        return st.query_params.get(key, default)
    except Exception:
        return default


def _qp_set(**kw) -> None:
    try:
        for k, v in kw.items():
            if v is None:
                st.query_params.pop(k, None)
            else:
                st.query_params[k] = str(v)
    except Exception:
        pass


# ── session state ─────────────────────────────────────────────────────────
def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("runner", None)
    ss.setdefault("run_active", False)
    ss.setdefault("run_done", False)
    ss.setdefault("prev_active", False)
    ss.setdefault("steps", {n: "pending" for n in STEP_ORDER})
    ss.setdefault("details", {n: "" for n in STEP_ORDER})
    ss.setdefault("step_started", {})
    ss.setdefault("step_elapsed", {})
    ss.setdefault("logs", [])
    ss.setdefault("last_run_dir", None)
    ss.setdefault("view_run", None)


def _reset_progress() -> None:
    ss = st.session_state
    ss.steps = {n: "pending" for n in STEP_ORDER}
    ss.details = {n: "" for n in STEP_ORDER}
    ss.step_started = {}
    ss.step_elapsed = {}
    ss.logs = []
    ss.run_done = False


def _close_step_timer(n: int) -> None:
    ss = st.session_state
    if n in ss.step_started and n not in ss.step_elapsed:
        ss.step_elapsed[n] = time.time() - ss.step_started[n]


def _apply_events(events: list[dict]) -> None:
    ss = st.session_state
    for ev in events:
        kind = ev.get("kind")
        if kind == "step":
            step, status = ev["step"], ev["status"]
            if step in ss.steps:
                if status == "running":
                    for k in STEP_ORDER:
                        if k < step and ss.steps[k] != "done":
                            ss.steps[k] = "done"
                            _close_step_timer(k)
                    ss.step_started.setdefault(step, time.time())
                ss.steps[step] = status
                if status == "done":
                    _close_step_timer(step)
                if ev.get("detail"):
                    ss.details[step] = ev["detail"]
            elif step == 8:
                for k in STEP_ORDER:
                    ss.steps[k] = "done"
                    _close_step_timer(k)
                ss.run_done = True
        elif kind == "log":
            ss.logs.append(f"{ev['ts']}  {ev['level']:<5} {ev['name']:<22} {ev['msg']}")
            ss.logs = ss.logs[-800:]
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
                    _close_step_timer(k)
            if runner and runner.output_dir:
                ss.last_run_dir = runner.output_dir
                ss.view_run = runner.output_dir


def _status() -> str:
    ss = st.session_state
    if ss.run_active:
        return "running"
    if ss.runner and getattr(ss.runner, "error", None):
        return "failed"
    if ss.run_done:
        return "done"
    return "idle"


# ── sidebar: pick input + launch ─────────────────────────────────────────
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
        with st.sidebar:
            ui.callout("error", "No data files in inbox/",
                       "Add your outlet data CSV/Excel to the inbox/ folder.")
        return

    names = [e["name"] for e in entries]
    remembered = _qp_get("f")
    idx = names.index(remembered) if remembered in names else 0

    def _label(e: dict) -> str:
        tail = "" if e["kind"] == "dataset" else "  —  reference, not a pipeline input"
        return f"{e['name']}  ({_fmt_size(e['size'])}){tail}"

    sel = st.sidebar.selectbox("Source file (from inbox/)", entries, index=idx,
                               format_func=_label, disabled=ss.run_active)
    _qp_set(f=sel["name"])

    run_anyway = False
    if sel["kind"] == "dataset":
        st.sidebar.caption(f"✅ `{sel['name']}` — valid pipeline input")
    else:
        with st.sidebar:
            ui.callout("warn", "Not a pipeline input",
                       f"{sel['name']} has no outlet/SKU columns — the run will "
                       f"fail at prioritization. Pick your outlet data file "
                       f"(e.g. {_PREFERRED}).")
        run_anyway = st.sidebar.checkbox("Run anyway", value=False,
                                         disabled=ss.run_active)

    use_sample = st.sidebar.checkbox(
        "Sample rows (faster test run)",
        value=_qp_get("s", "1") != "0", disabled=ss.run_active)
    sample_size = None
    if use_sample:
        sample_size = st.sidebar.number_input(
            "Sample size", min_value=500, max_value=1_000_000,
            value=int(_qp_get("n", "5000") or 5000), step=500,
            disabled=ss.run_active)
        _qp_set(s="1", n=int(sample_size))
    else:
        _qp_set(s="0", n=None)

    blocked = sel["kind"] == "reference" and not run_anyway
    start = st.sidebar.button("▶  Run pipeline", type="primary",
                              disabled=ss.run_active or blocked, width="stretch")

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
        ss.prev_active = True
        _qp_set(v="Run & progress")
        st.rerun()


# ── progress view ────────────────────────────────────────────────────────
def _build_steps_model() -> list[dict]:
    ss = st.session_state
    now = time.time()
    model = []
    for n in STEP_ORDER:
        state = ss.steps[n]
        if n in ss.step_elapsed:
            tm = _fmt_dur(ss.step_elapsed[n])
        elif state == "running" and n in ss.step_started:
            tm = _fmt_dur(now - ss.step_started[n])
        else:
            tm = ""
        model.append({"n": n, "name": STEP_META[n], "state": state,
                      "detail": ss.details[n], "time": tm})
    return model


def _progress_view() -> None:
    ss = st.session_state
    if ss.run_active and ss.runner is not None:
        _apply_events(ss.runner.drain())

    runner: PipelineRunner | None = ss.runner
    status = _status()
    c1, c2 = st.columns([1, 1], gap="small")
    with c1:
        if status == "running":
            ui.callout("info", "Pipeline running",
                       f"Elapsed {runner.elapsed if runner else '0s'}")
        elif status == "done":
            ui.callout("info", "Run complete",
                       f"Finished in {runner.elapsed if runner else '—'}")
        elif status == "failed":
            last = runner.error.strip().splitlines()[-1][:280] if runner else ""
            ui.callout("error", "Run failed", last)
        else:
            ui.callout("empty", "Idle", "Configure a run in the sidebar and press Run.")
    with c2:
        done = sum(1 for s in ss.steps.values() if s == "done")
        st.progress(done / len(STEP_ORDER), text=f"{done} / {len(STEP_ORDER)} steps complete")

    left, right = st.columns([5, 4], gap="large")
    with left:
        st.markdown("###### Perfect Store execution")
        st.markdown(build_wheel_svg(ss.steps, run_active=ss.run_active,
                                    run_done=ss.run_done),
                    unsafe_allow_html=True)
    with right:
        st.markdown("###### Steps")
        ui.stepper(_build_steps_model())

    st.markdown("###### Live log")
    levels = ["All", "INFO", "WARN", "ERROR"]
    lvl = st.segmented_control("Log level", levels, default="All",
                               label_visibility="collapsed", key="log_lvl")
    lines = ss.logs
    if lvl and lvl != "All":
        tok = "WARN" if lvl == "WARN" else lvl
        lines = [l for l in ss.logs
                 if f" {tok}" in f" {l}" or l.startswith("──")]
    ui.console(lines[-500:])

    # one full rerun when a run transitions active → finished, so the sidebar
    # re-enables and the Outputs view picks up the new run.
    if ss.prev_active and not ss.run_active:
        ss.prev_active = False
        st.rerun(scope="app")
    ss.prev_active = ss.run_active


# ── outputs view ─────────────────────────────────────────────────────────
def _outputs_view() -> None:
    ss = st.session_state
    runs = list_runs(PROJECT_ROOT)
    if not runs:
        ui.callout("empty", "No runs yet", "Launch a pipeline from the sidebar.")
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


# ── entry ────────────────────────────────────────────────────────────────
def main() -> None:
    _init_state()
    ss = st.session_state
    ui.inject_css()
    ui.header(_status())

    _sidebar()

    view = st.radio("View", _VIEWS, horizontal=True, label_visibility="collapsed",
                    index=_VIEWS.index(_qp_get("v", _VIEWS[0]))
                    if _qp_get("v", _VIEWS[0]) in _VIEWS else 0)
    _qp_set(v=view)
    st.divider()

    if view == "Run & progress":
        refresh = f"{REFRESH_SECS}s" if ss.run_active else None

        @st.fragment(run_every=refresh)
        def _frag() -> None:
            _progress_view()

        _frag()
    else:
        _outputs_view()


if __name__ == "__main__":
    main()
