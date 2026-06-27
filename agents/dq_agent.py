"""
Data Quality Agent — CPG outlet-level DQ checks for the India Master File.
Checks are tailored to flat outlet data (one row per store).
Claude provides a plain-English verdict in FMCG trade language.
"""

import logging
import pandas as pd
import numpy as np
from typing import Tuple
from agents.llm_client import call_llm
from agents.context_loader import ContextLoader

logger = logging.getLogger("perfect_store.dq")

_ctx = ContextLoader()


# ── Core DQ checks ──────────────────────────────────────────────────────────

def check_required_columns(df: pd.DataFrame, required: list) -> dict:
    missing = [c for c in required if c not in df.columns]
    return {
        "check": "required_columns",
        "missing": missing,
        "pass": len(missing) == 0,
        "detail": f"{len(df.columns)} columns present"
    }


def check_nulls(df: pd.DataFrame, threshold_pct: float = 60.0) -> dict:
    """Flag columns where null % exceeds threshold (set high for sparse India data)."""
    null_pct = (df.isnull().sum() / len(df) * 100).round(1)
    issues = null_pct[null_pct > threshold_pct].to_dict()
    return {
        "check": "null_values",
        "threshold_pct": threshold_pct,
        "issues": issues,
        "total_columns": len(df.columns),
        "columns_above_threshold": len(issues),
        "pass": len(issues) == 0
    }


def check_duplicate_outlet_ids(df: pd.DataFrame, id_col: str = "OUTLET_UID_EDITED") -> dict:
    """Each outlet should appear once (flat file — one row per store)."""
    if id_col not in df.columns:
        return {"check": "duplicate_outlet_ids", "issues": {}, "pass": True,
                "note": f"Column '{id_col}' not found"}
    total = len(df)
    unique = df[id_col].nunique()
    dupes = total - unique
    return {
        "check": "duplicate_outlet_ids",
        "total_rows": total,
        "unique_outlets": unique,
        "duplicate_rows": dupes,
        "pass": dupes == 0,
        "issues": {} if dupes == 0 else {"duplicate_count": dupes}
    }


def check_vpo_outliers(df: pd.DataFrame, col: str = "VPO",
                       multiplier: float = 10.0) -> dict:
    """Flag outlets whose monthly revenue (VPO) is Nx the national average."""
    if col not in df.columns:
        return {"check": "vpo_outliers", "issues": {}, "pass": True,
                "note": f"Column '{col}' not found"}
    vals = df[col].dropna()
    if len(vals) == 0:
        return {"check": "vpo_outliers", "issues": {}, "pass": True,
                "note": "No non-null values"}

    avg = vals.mean()
    threshold = avg * multiplier
    n_outliers = (vals > threshold).sum()
    pct_outliers = n_outliers / len(vals) * 100

    return {
        "check": "vpo_outliers",
        "avg_vpo": round(float(avg), 2),
        "threshold": round(float(threshold), 2),
        "n_outliers": int(n_outliers),
        "pct_outliers": round(float(pct_outliers), 2),
        "pass": pct_outliers < 1.0,  # flag if >1% of outlets are outliers
        "issues": {} if n_outliers == 0 else {
            f"outlets_above_{multiplier}x_avg": f"{n_outliers:,} ({pct_outliers:.1f}%)"
        }
    }


def check_negative_revenue(df: pd.DataFrame, sku_column_keywords: list = None) -> dict:
    """Negative SKU revenue values indicate credits/returns — flag if widespread."""
    keywords = sku_column_keywords or []
    sku_cols = [c for c in df.columns if keywords and any(
        kw in c.upper() for kw in keywords
    )]
    issues = {}
    for col in sku_cols:
        neg = (df[col] < 0).sum()
        if neg > 0:
            issues[col] = f"{neg:,} negative values"

    return {
        "check": "negative_sku_revenue",
        "sku_columns_checked": len(sku_cols),
        "issues": issues,
        "pass": len(issues) == 0,
        "note": "Negative values = returns/credits; will be clipped to 0 before clustering"
    }


def check_zero_vpo_outlets(df: pd.DataFrame) -> dict:
    """Flag proportion of outlets with zero monthly revenue."""
    if "VPO" not in df.columns:
        return {"check": "zero_revenue_outlets", "issues": {}, "pass": True,
                "note": "VPO column not found"}
    total = len(df)
    zero = (df["VPO"].fillna(0) == 0).sum()
    pct = zero / total * 100
    return {
        "check": "zero_revenue_outlets",
        "zero_vpo_count": int(zero),
        "pct_zero": round(float(pct), 1),
        "pass": pct < 5.0,
        "issues": {} if pct < 5.0 else {
            "zero_revenue_outlets": f"{zero:,} ({pct:.1f}%) outlets have ₹0 VPO"
        }
    }


def check_state_coverage(df: pd.DataFrame) -> dict:
    """Summarise state/cohort distribution for Claude to comment on."""
    info = {}
    if "DB State" in df.columns:
        info["states"] = df["DB State"].value_counts().head(5).to_dict()
    if "COHORT" in df.columns:
        info["cohorts"] = df["COHORT"].value_counts().head(5).to_dict()
    if "Top City" in df.columns:
        info["city_tiers"] = df["Top City"].value_counts().head(5).to_dict()
    if "channel" in df.columns:
        info["channels"] = df["channel"].value_counts().head(5).to_dict()
    return {
        "check": "geographic_channel_coverage",
        "issues": {},
        "pass": True,
        "summary": info
    }


# ── Run all checks ──────────────────────────────────────────────────────────

def run_dq_checks(df: pd.DataFrame, config: dict) -> list:
    dq_cfg = config.get("dq_checks", {})
    results = []
    results.append(check_required_columns(
        df, dq_cfg.get("required_columns", [])))
    results.append(check_nulls(
        df, dq_cfg.get("null_threshold_pct", 60.0)))
    results.append(check_duplicate_outlet_ids(
        df, dq_cfg.get("id_col", "OUTLET_UID_EDITED")))
    results.append(check_vpo_outliers(
        df, dq_cfg.get("volume_outlier_col", "VPO"),
        dq_cfg.get("volume_outlier_multiplier", 10.0)))
    results.append(check_negative_revenue(df, sku_column_keywords=dq_cfg.get("sku_column_keywords", [])))
    results.append(check_zero_vpo_outlets(df))
    results.append(check_state_coverage(df))
    return results


# ── Claude DQ verdict ────────────────────────────────────────────────────────

def get_claude_dq_verdict(dq_results: list, df_summary: dict,
                          api_key: str, model: str = "claude-opus-4-6"
                          ) -> Tuple[bool, str]:
    """
    Ask Claude to interpret DQ results and write a plain-English
    report in Indian CPG/FMCG trade terms.
    """
    prompt = f"""A new outlet master file has been ingested. Below are the automated DQ check results.

## File Summary
- Total outlets: {df_summary['rows']:,}
- Total columns: {df_summary['columns']}
- Key columns present: {df_summary['key_columns']}

## DQ Check Results
{_format_dq_results(dq_results)}

## Your task
1. Issue an overall **PASS** or **FAIL** verdict.
   - PASS = data is usable for outlet segmentation (minor issues are acceptable)
   - FAIL = blocking issues that must be resolved before clustering

2. Write a concise DQ report (4-8 bullet points) in FMCG / Perfect Store trade language. For example:
   - Flag if outlet IDs are duplicated (would inflate cluster sizes)
   - Flag if VPO (monthly revenue) has suspicious outliers or excessive zeros
   - Note which demographic columns have partial coverage and how that will affect segmentation
   - Flag negative SKU revenue values (returns/credits) and how they'll be handled
   - Note the geographic spread (states, cohorts, channels) and any imbalances

3. If FAIL, list the specific blockers that must be fixed.

Format your response as:
VERDICT: PASS or FAIL

REPORT:
• (bullet points here)
"""

    text = call_llm(prompt, api_key, model, max_tokens=1024,
                    system_prompt=_ctx.build("dq"))
    passed = "VERDICT: PASS" in text.upper()
    return passed, text


def _format_dq_results(results: list) -> str:
    lines = []
    for r in results:
        status = "PASS" if r.get("pass") else "FAIL"
        lines.append(f"[{status}] {r['check']}")
        for k, v in r.items():
            if k not in ("check", "pass") and v and v != {}:
                if isinstance(v, dict) and len(v) > 0:
                    for dk, dv in v.items():
                        lines.append(f"      {dk}: {dv}")
                elif not isinstance(v, dict):
                    lines.append(f"      {k}: {v}")
    return "\n".join(lines)


def get_df_summary(df: pd.DataFrame) -> dict:
    key_cols = ["OUTLET_UID_EDITED", "VPO", "TOTAL_REVENUE", "AVG_SKU",
                "ACTIVE_MONTHS", "DB State", "COHORT", "channel"]
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "key_columns": [c for c in key_cols if c in df.columns],
    }
