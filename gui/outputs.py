"""Discover and render the deliverables a pipeline run drops in
``outputs/<timestamp>/`` — PDF, Excel workbooks, segment CSVs and PNG charts.
"""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st


def list_runs(project_root: str) -> list[Path]:
    """Newest-first list of run folders under outputs/."""
    out = Path(project_root) / "outputs"
    if not out.is_dir():
        return []
    runs = [p for p in out.iterdir() if p.is_dir() and p.name[0].isdigit()]
    return sorted(runs, reverse=True)


def _arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Cast ragged object columns to a nullable string dtype so Streamlit's
    Arrow serialisation doesn't choke on mixed float/str cells."""
    obj_cols = df.select_dtypes(include="object").columns
    if len(obj_cols):
        df = df.astype({c: "string" for c in obj_cols})
    return df


def run_label(run_dir: Path) -> str:
    name = run_dir.name
    try:
        dt = datetime.strptime(name, "%Y%m%d_%H%M%S")
        return dt.strftime("%d %b %Y  %H:%M:%S")
    except ValueError:
        return name


def scan_artifacts(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    pdfs = sorted(run_dir.glob("*.pdf"))
    xlsx = sorted(run_dir.glob("*.xlsx"))
    csvs = sorted(run_dir.glob("*.csv"))
    charts = sorted((run_dir / "charts").glob("*.png")) if (run_dir / "charts").is_dir() else []
    return {"pdf": pdfs, "excel": xlsx, "csv": csvs, "charts": charts}


# ── individual renderers ─────────────────────────────────────────────────────

def _render_pdf(path: Path) -> None:
    data = path.read_bytes()
    st.download_button("⬇ Download PDF", data, file_name=path.name,
                       mime="application/pdf", key=f"dl_{path}")
    b64 = base64.b64encode(data).decode()
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}" width="100%" '
        f'height="820" style="border:1px solid #d7dde2;border-radius:6px"></iframe>',
        unsafe_allow_html=True,
    )
    st.caption("If the preview is blank, use the download button above "
               "(some browsers block inline PDFs).")


def _render_excel(path: Path) -> None:
    try:
        xl = pd.ExcelFile(path)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not open {path.name}: {exc}")
        return
    st.download_button("⬇ Download workbook", path.read_bytes(), file_name=path.name,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key=f"dl_{path}")
    sheet = st.selectbox("Sheet", xl.sheet_names, key=f"sheet_{path}")
    try:
        df = xl.parse(sheet)
        st.dataframe(_arrow_safe(df), width="stretch", height=460)
        st.caption(f"{len(df):,} rows × {len(df.columns)} columns "
                   "— embedded charts are visible in the downloaded file.")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not read sheet '{sheet}': {exc}")


def _render_csv(path: Path) -> None:
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not read {path.name}: {exc}")
        return
    st.download_button("⬇ Download CSV", path.read_bytes(), file_name=path.name,
                       mime="text/csv", key=f"dl_{path}")
    st.dataframe(_arrow_safe(df), width="stretch", height=420)
    st.caption(f"{len(df):,} rows × {len(df.columns)} columns")


# ── top-level viewer ────────────────────────────────────────────────────────

def render_run(run_dir: Path) -> None:
    run_dir = Path(run_dir)
    art = scan_artifacts(run_dir)
    total = sum(len(v) for v in art.values())
    if not total:
        st.info("No output files found in this run folder yet.")
        return

    st.caption(f"📁 `{run_dir}`  —  {len(art['pdf'])} PDF · "
               f"{len(art['excel'])} Excel · {len(art['csv'])} CSV · "
               f"{len(art['charts'])} charts")

    tabs = st.tabs(["📊 Segment summary", "📄 PDF report", "📗 Excel reports",
                    "📑 Segment data", "🖼 Charts"])

    with tabs[0]:
        _render_summary(run_dir, art)

    with tabs[1]:
        if not art["pdf"]:
            st.info("No PDF in this run.")
        for p in art["pdf"]:
            st.subheader(p.name)
            _render_pdf(p)

    with tabs[2]:
        if not art["excel"]:
            st.info("No Excel workbooks in this run.")
        for p in art["excel"]:
            with st.expander(p.name, expanded=len(art["excel"]) == 1):
                _render_excel(p)

    with tabs[3]:
        if not art["csv"]:
            st.info("No CSV files in this run.")
        for p in art["csv"]:
            with st.expander(p.name, expanded=False):
                _render_csv(p)

    with tabs[4]:
        if not art["charts"]:
            st.info("No charts in this run.")
        cols = st.columns(2)
        for k, img in enumerate(art["charts"]):
            with cols[k % 2]:
                st.image(str(img), caption=img.name, width="stretch")


def _render_summary(run_dir: Path, art: dict) -> None:
    """Per-segment counts + priority mix, derived from the combined CSV."""
    combined = next((p for p in art["csv"] if p.name.startswith("all_segments")), None)
    if combined is None:
        st.info("No `all_segments_*.csv` to summarise.")
        return
    try:
        df = pd.read_csv(combined)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not read {combined.name}: {exc}")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Outlets", f"{len(df):,}")
    if "cluster" in df.columns:
        c2.metric("Segments", df["cluster"].nunique())
    if "priority" in df.columns:
        c3.metric("Priority tiers", df["priority"].nunique())

    label_col = next((c for c in ("segment_label", "cluster_label", "label")
                      if c in df.columns), None)

    if "cluster" in df.columns:
        st.markdown("**Outlets per segment**")
        grp_col = label_col or "cluster"
        counts = df.groupby(grp_col).size().sort_values(ascending=False)
        counts.name = "outlets"
        st.bar_chart(counts)

    if "priority" in df.columns:
        st.markdown("**Priority distribution**")
        order = ["A+", "A", "B+", "B", "C+", "C", "D+", "D"]
        pc = df["priority"].value_counts()
        pc = pc.reindex([o for o in order if o in pc.index]).dropna()
        pc.name = "outlets"
        st.bar_chart(pc)
        if "opportunity_gap" in df.columns:
            gap = df.groupby("priority")["opportunity_gap"].mean()
            gap = gap.reindex([o for o in order if o in gap.index]).dropna().round(0)
            gap.name = "avg opportunity gap"
            st.bar_chart(gap)

    with st.expander("Preview combined outlet table"):
        st.dataframe(_arrow_safe(df.head(2000)), width="stretch", height=420)
