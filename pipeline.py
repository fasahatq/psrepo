"""
Perfect Store Pipeline — orchestrates the full flow for outlet-level data.

Supports:
  data_mode = "flat_outlet"  → each row is one store, cluster directly
  data_mode = "transactional" → aggregate by retailer first (RFM), then cluster

Handles large files (900k+ rows) via chunked loading.
"""

import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from agents.dq_agent import run_dq_checks, get_claude_dq_verdict, get_df_summary
from agents.prioritization_agent import run_prioritization
from agents.segmentation_agent import run_segmentation
from agents.msl_generator import run_msl_from_df
from agents.output_agent import generate_outputs
from agents.space_allocation_agent import run_space_allocation

logger = logging.getLogger("perfect_store.pipeline")


# ── Config & data loading ────────────────────────────────────────────────────

def load_config(project_root: str) -> dict:
    config_path = os.path.join(project_root, ".claude", "config.json")
    with open(config_path) as f:
        return json.load(f)


def load_data(file_path: str, sample_size: int = None) -> pd.DataFrame:
    """
    Load CSV or Excel. For very large files (>500k rows), loads in chunks
    to avoid memory issues. Normalises column names.
    """
    ext = Path(file_path).suffix.lower()
    logger.info(f"Loading {Path(file_path).name} ...")

    if ext == ".csv":
        # Peek at row count first
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            row_count = sum(1 for _ in f) - 1  # subtract header

        logger.info(f"File has ~{row_count:,} rows")

        if sample_size and row_count > sample_size:
            # Sample evenly across the file
            import math
            skip_interval = max(1, math.floor(row_count / sample_size))
            skip_rows = [i for i in range(1, row_count + 1) if i % skip_interval != 0]
            skip_rows = skip_rows[:row_count - sample_size]
            df = pd.read_csv(file_path, skiprows=skip_rows, low_memory=False)
            logger.info(f"Sampled {len(df):,} rows (1 in every {skip_interval})")
        else:
            # Load in chunks and concatenate (memory-safe)
            chunk_size = 100_000
            chunks = []
            for chunk in pd.read_csv(file_path, chunksize=chunk_size, low_memory=False):
                chunks.append(chunk)
                logger.info(f"  Loaded {sum(len(c) for c in chunks):,} rows...")
            df = pd.concat(chunks, ignore_index=True)

    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Preserve original column names — do NOT lowercase (columns have mixed case)
    df.columns = df.columns.str.strip()

    # Replace "null" strings with actual NaN
    df = df.replace("null", pd.NA)

    logger.info(f"Loaded {len(df):,} rows × {len(df.columns)} columns")
    return df


# ── Transactional SKU → flat outlet preprocessing ────────────────────────────

def _is_sku_transactional(df: pd.DataFrame) -> bool:
    """Return True when the file is a store×SKU transactional file, not a flat outlet file."""
    has_sku_cols = {"CUST_UNIQ_ID_VAL", "NET_SALES", "BRND_NM"}.issubset(df.columns)
    missing_outlet = "OUTLET_UID_EDITED" not in df.columns or "VPO" not in df.columns
    return has_sku_cols and missing_outlet


def _aggregate_sku_to_outlet(df: pd.DataFrame, project_root: str = None) -> pd.DataFrame:
    """
    Aggregate a transactional SKU file (India_Synthetic_SKU_Data.csv) into a
    flat outlet file the pipeline can consume.

    VPO / TOTAL_REVENUE = sum of NET_SALES per store.
    AVG_SKU             = number of distinct SKU rows per store.
    Outlet metadata (DB State, COHORT, channel, etc.) is enriched by joining
    with Market_Master_File.csv so the pipeline sees real field values.
    """
    grp = df.groupby("CUST_UNIQ_ID_VAL", sort=False)

    flat = pd.DataFrame({
        "OUTLET_UID_EDITED": grp["CUST_UNIQ_ID_VAL"].first(),
        "VPO":               grp["NET_SALES"].sum().round(2),
        "TOTAL_REVENUE":     grp["NET_SALES"].sum().round(2),
        "AVG_SKU":           grp.size(),
        "ACTIVE_MONTHS":     1,
    }).reset_index(drop=True)

    flat["OUTLET_UID_EDITED"] = flat["OUTLET_UID_EDITED"].astype(str).str.strip()

    # Brand × PPG revenue pivot → columns like "LAYS MEDIUM", "KURKURE SMALL"
    df = df.copy()
    df["_sku_col"] = (df["BRND_NM"].str.upper().str.strip()
                      + " " + df["PPG_DESC"].str.upper().str.strip())
    pivot = (
        df.pivot_table(
            index="CUST_UNIQ_ID_VAL",
            columns="_sku_col",
            values="NET_SALES",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename(columns={"CUST_UNIQ_ID_VAL": "OUTLET_UID_EDITED"})
    )
    pivot["OUTLET_UID_EDITED"] = pivot["OUTLET_UID_EDITED"].astype(str).str.strip()
    flat = flat.merge(pivot, on="OUTLET_UID_EDITED", how="left")

    # ── Enrich with Market_Master_File.csv ────────────────────────────────────
    # Preferred over hard-coded defaults: brings in real outlet metadata and
    # all segmentation features already present in the master file.
    MMF_ENRICH_COLS = [
        # Identity & geography
        "OUTLET_UID_EDITED", "DB State", "Top City", "pepsi_top_city_name",
        "COHORT", "channel", "sub_channel_name", "store_format", "sector",
        "BI", "state", "district",
        # Revenue / activity (prefer MMF values when available)
        "VPO", "TOTAL_REVENUE", "AVG_SKU", "ACTIVE_MONTHS",
        # Store attributes
        "store_size", "store_size_bracket", "store size tagging",
        "cooler_available", "urban_vs_periphery_tagging",
        "nbrhd_per_capita_income", "estmtd_daily_footfall_tag",
        # Demographics
        "sec_a_hhs", "sec_b_hhs", "sec_c_hhs", "sec_d_hhs", "sec_e_hhs",
        # Proximity features
        "no_of_schools_in_a_1_km_radius", "no_of_colleges_in_a_1_km_radius",
        "distance_to_nearest_school_in_km", "distance_to_nearest_large_office_in_km",
        "distance_to_nearest_bus_stn_in_km", "distance_to_nearest_train_stn_in_km",
        "distance_to_nearest_malls", "nearest_pepsi_distributer_distance_in_km",
        "nearest_pepsi_distributor_name",
        # Availability flags
        "chocolates_avlblty", "biscuits_avlblty", "noodles_avlblty",
        "premium_category_sold", "premium_snacks_sold",
        "western_salty_lead_pack",
        # SKU revenue columns already in Market_Master_File
        "LAYS LARGE 20", "LAYS MEDIUM 10", "LAYS SMALL 5",
        "KURKURE LARGE 20", "KURKURE MEDIUM 10", "KURKURE SMALL 5",
        "UNCLE CHIPPS LARGE 20", "UNCLE CHIPPS MEDIUM 10",
        "DORITOS LARGE 20", "DORITOS MEDIUM 10", "DORITOS SMALL 5",
        "CHEETOS MEDIUM 10", "CHEETOS SMALL 5",
        "KKNMK MEDIUM 10", "KKNMK SMALL 5",
    ]

    mmf_path = None
    if project_root:
        mmf_path = os.path.join(project_root, "inbox", "Market_Master_File.csv")

    if mmf_path and os.path.exists(mmf_path):
        mmf = pd.read_csv(mmf_path, low_memory=False)
        mmf.columns = mmf.columns.str.strip()
        mmf["OUTLET_UID_EDITED"] = mmf["OUTLET_UID_EDITED"].astype(str).str.strip()

        avail_cols = [c for c in MMF_ENRICH_COLS if c in mmf.columns]
        mmf_slim = mmf[avail_cols].drop_duplicates("OUTLET_UID_EDITED")

        # Merge; suffix _mmf for overlapping revenue columns so we can pick best
        flat = flat.merge(mmf_slim, on="OUTLET_UID_EDITED", how="left",
                          suffixes=("", "_mmf"))

        # For VPO / TOTAL_REVENUE / AVG_SKU / ACTIVE_MONTHS: prefer MMF values
        # when they are non-null (MMF has real historical data).
        for col in ["VPO", "TOTAL_REVENUE", "AVG_SKU", "ACTIVE_MONTHS"]:
            mmf_col = col + "_mmf"
            if mmf_col in flat.columns:
                flat[col] = flat[mmf_col].combine_first(flat[col])
                flat.drop(columns=[mmf_col], inplace=True)

        logger.info(f"Enriched {len(flat):,} outlets from Market_Master_File.csv "
                    f"({len(avail_cols)} columns merged)")
    else:
        logger.warning("Market_Master_File.csv not found — using fallback defaults "
                       "for outlet metadata")

    # ── Fallback defaults for any still-missing mandatory columns ─────────────
    defaults = {
        "BI": "yes", "COHORT": "SKU Data", "DB State": "Unknown",
        "Top City": "Unknown", "channel": "GT", "store_format": "GT",
        "sector": "Urban", "sub_channel_name": "Retail",
    }
    for col, val in defaults.items():
        if col not in flat.columns:
            flat[col] = val
        else:
            flat[col] = flat[col].fillna(val)

    logger.info(
        f"Aggregated {len(df):,} SKU rows → {len(flat):,} outlet rows | "
        f"sample brand×PPG cols: "
        f"{[c for c in flat.columns if c not in set(MMF_ENRICH_COLS) | {'OUTLET_UID_EDITED','VPO','TOTAL_REVENUE','AVG_SKU','ACTIVE_MONTHS'}][:5]}..."
    )
    return flat


# ── Pipeline ─────────────────────────────────────────────────────────────────

def run_pipeline(file_path: str, project_root: str = None,
                 sample_size: int = None):
    """
    Run the full pipeline for a single file.
    Args:
        file_path   : path to the data file (in processing/)
        project_root: root folder of the project
        sample_size : if set, only use this many rows (useful for testing)
    """
    if project_root is None:
        project_root = os.path.dirname(os.path.abspath(__file__))

    load_dotenv(os.path.join(project_root, ".env"))
    config = load_config(project_root)
    llm_backend = os.getenv("LLM_BACKEND", "anthropic").strip().lower()
    local_model = os.getenv("LOCAL_LLM_MODEL", "gemma3:12b")

    if llm_backend == "azure":
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    elif llm_backend == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    elif llm_backend == "vertex":
        api_key = None
        model = os.getenv("VERTEX_MODEL", "gemini-1.5-pro")
    elif llm_backend == "local":
        api_key = None
        model = local_model
    else:  # anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")

    base_output_dir = os.path.join(project_root, config.get("outputs_dir", "outputs"))
    log_dir = os.path.join(project_root, config.get("logs_dir", "logs"))
    data_mode = config.get("data_mode", "flat_outlet")

    use_llm = bool(api_key) or (llm_backend in ("local", "gemini", "vertex", "azure"))

    filename = Path(file_path).stem
    start_time = datetime.now()
    run_ts = start_time.strftime("%Y%m%d_%H%M%S")
    run_id = f"{filename}_{run_ts}"
    output_dir = os.path.join(base_output_dir, run_ts)

    display_model = model

    logger.info("=" * 65)
    logger.info(f"Perfect Store Pipeline | run_id: {run_id}")
    logger.info(f"File      : {file_path}")
    logger.info(f"Data mode : {data_mode}")
    logger.info(f"LLM backend : {llm_backend}  |  model: {display_model}")
    logger.info("=" * 65)

    # ── Step 1: Load ─────────────────────────────────────────────────────
    logger.info("Step 1/7 — Loading data")
    df = load_data(file_path, sample_size=sample_size)

    if _is_sku_transactional(df):
        logger.info("Transactional SKU file detected — aggregating to flat outlet format "
                    "and enriching from Market_Master_File.csv")
        df = _aggregate_sku_to_outlet(df, project_root=project_root)

    # ── Step 2: Data Quality ─────────────────────────────────────────────
    logger.info("Step 2/7 — Running DQ checks")
    dq_results = run_dq_checks(df, config)
    passed = sum(1 for r in dq_results if r.get("pass"))
    logger.info(f"DQ: {passed}/{len(dq_results)} checks passed")

    if use_llm:
        df_summary = get_df_summary(df)
        try:
            dq_passed, dq_report = get_claude_dq_verdict(
                dq_results, df_summary, api_key, model)
            logger.info(f"LLM DQ verdict: {'PASS' if dq_passed else 'FAIL'}")
        except Exception as e:
            logger.warning(
                f"LLM DQ call failed ({type(e).__name__}: {e}) — "
                f"falling back to rule-based DQ report"
            )
            dq_passed = all(r.get("pass") for r in dq_results)
            dq_report = _fallback_dq_report(dq_results)
    else:
        logger.warning("No LLM configured — using fallback DQ report")
        dq_passed = all(r.get("pass") for r in dq_results)
        dq_report = _fallback_dq_report(dq_results)

    os.makedirs(log_dir, exist_ok=True)
    dq_log = os.path.join(log_dir, f"dq_report_{run_id}.txt")
    with open(dq_log, "w", encoding="utf-8") as f:
        f.write(dq_report)
    logger.info(f"DQ report saved: {dq_log}")

    # Build a compact DQ context string — passed to every downstream LLM call
    # so agents can reference data-quality caveats in their narratives.
    dq_context = _build_dq_context(dq_results, df)

    # ── Step 3: Prioritization ────────────────────────────────────────────
    # Runs before segmentation so priority_bucket is available as a
    # clustering feature, producing commercially-aligned segments.
    logger.info("Step 3/7 — Prioritization (A/B/C/D + opportunity gap)")
    df_out, priority_narrative = run_prioritization(
        df, config, api_key, model, dq_context=dq_context)

    priority_counts = df_out["priority"].value_counts().sort_index()
    logger.info("Priority distribution:")
    for tag, cnt in priority_counts.items():
        avg_gap = df_out.loc[df_out["priority"] == tag, "opportunity_gap"].mean()
        logger.info(f"  {tag:3s}: {cnt:,} outlets | avg gap ₹{avg_gap:,.0f}/month")

    priority_log = os.path.join(log_dir, f"priority_narrative_{run_id}.txt")
    with open(priority_log, "w", encoding="utf-8") as f:
        f.write(priority_narrative)
    logger.info(f"Priority narrative saved: {priority_log}")

    # Build a compact priority context string for segmentation to consume.
    priority_context = _build_priority_context(df_out)

    # ── Step 4: Segmentation ──────────────────────────────────────────────
    # Receives df_out which already carries priority_bucket / priority columns,
    # allowing segmentation to use priority tier as a clustering signal.
    logger.info("Step 4/7 — Segmentation")
    df_out, labels = run_segmentation(
        df_out, config, api_key, model,
        dq_context=dq_context, priority_context=priority_context,
    )

    n_segments = df_out["cluster"].nunique()
    logger.info(f"Segmentation complete: {n_segments} segments across {len(df_out):,} outlets")
    for cid, info in labels.items():
        cnt = (df_out["cluster"] == cid).sum()
        logger.info(f"  Cluster {cid} ({cnt:,} outlets): {info.get('label', '?')}")

    # ── Step 5: MSL Generation ────────────────────────────────────────────
    logger.info("Step 5/7 — MSL Generation")
    sku_file = config.get("sku_file", "India_Synthetic_SKU_Data.csv")
    sku_csv  = os.path.join(project_root, config.get("inbox_dir", "inbox"), sku_file)
    msl_path = run_msl_from_df(df_out, sku_csv, output_dir,
                               api_key=api_key, model=model, labels=labels)
    if msl_path:
        logger.info(f"MSL workbook saved: {msl_path}")
    else:
        logger.warning("MSL generation skipped (SKU file missing or no matching outlets)")

    # ── Step 6: Outputs ───────────────────────────────────────────────────
    logger.info("Step 6/7 — Generating outputs")
    outputs = generate_outputs(df_out, labels, dq_report, output_dir,
                               priority_narrative=priority_narrative)
    outputs["msl"] = msl_path

    # ── Step 7: Space Allocation ──────────────────────────────────────────
    logger.info("Step 7/7 — Space Allocation")
    space_alloc_path = None
    if msl_path:
        try:
            space_alloc_path = run_space_allocation(
                api_key=api_key,
                model=model,
                msl_path=msl_path,
                output_dir=output_dir,
            )
            logger.info(f"Space allocation workbook: {space_alloc_path}")
        except Exception as exc:
            logger.warning(f"Space allocation failed ({type(exc).__name__}: {exc}) — skipped")
    else:
        logger.warning("Space allocation skipped — no MSL file available")
    outputs["space_allocation"] = space_alloc_path

    logger.info("=" * 65)
    logger.info("Pipeline complete!")
    logger.info(f"  Segment CSVs      : {len(outputs['csv_files'])} files")
    logger.info(f"  Excel report      : {outputs['excel']}")
    logger.info(f"  Priority Excel    : {outputs.get('priority_excel', 'N/A')}")
    logger.info(f"  MSL workbook      : {outputs['msl'] or 'skipped'}")
    logger.info(f"  Space allocation  : {outputs['space_allocation'] or 'skipped'}")
    logger.info(f"  PDF report        : {outputs['pdf']}")
    logger.info("=" * 65)

    return outputs


def _build_dq_context(dq_results: list, df: pd.DataFrame) -> str:
    """
    Compact DQ summary injected into downstream prompts so Claude can reference
    data-quality caveats when writing prioritization and segmentation narratives.
    """
    passed = sum(1 for r in dq_results if r.get("pass"))
    lines = [f"DQ: {passed}/{len(dq_results)} checks passed."]
    for r in dq_results:
        if not r.get("pass") and r.get("issues"):
            issues_str = ", ".join(f"{k}: {v}" for k, v in r["issues"].items())
            lines.append(f"  - {r['check']}: {issues_str}")
    if "VPO" in df.columns:
        zero_vpo = int((df["VPO"].fillna(0) == 0).sum())
        pct = zero_vpo / max(len(df), 1) * 100
        if pct > 0:
            lines.append(f"  - Zero-VPO outlets: {zero_vpo:,} ({pct:.1f}%)")
    return "\n".join(lines)


def _build_priority_context(df: pd.DataFrame) -> str:
    """
    Compact priority distribution summary injected into segmentation prompts so
    Claude knows the commercial tier breakdown when labelling segments.
    """
    if "priority" not in df.columns:
        return ""
    lines = ["Priority distribution (A=top 20%, D=bottom 30% by VPO):"]
    for tag in ["A+", "A", "B+", "B", "C+", "C", "D+", "D"]:
        n = int((df["priority"] == tag).sum())
        if n:
            avg_gap = (
                df.loc[df["priority"] == tag, "opportunity_gap"].mean()
                if "opportunity_gap" in df.columns else 0
            )
            lines.append(f"  {tag}: {n:,} outlets, avg gap ₹{avg_gap:,.0f}/mo")
    return "\n".join(lines)


def _fallback_dq_report(dq_results: list) -> str:
    verdict = "PASS" if all(r.get("pass") for r in dq_results) else "FAIL"
    lines = [f"VERDICT: {verdict}", "", "REPORT:"]
    for r in dq_results:
        status = "PASS" if r.get("pass") else "FAIL"
        lines.append(f"• [{status}] {r['check']}")
        if r.get("issues") and isinstance(r["issues"], dict):
            for k, v in r["issues"].items():
                lines.append(f"    - {k}: {v}")
        if r.get("missing"):
            lines.append(f"    - Missing: {', '.join(str(m) for m in r['missing'])}")
    return "\n".join(lines)
