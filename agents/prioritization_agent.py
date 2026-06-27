"""
Prioritization Agent — buckets stores into A/B/C/D and identifies A+/B+/C+/D+.

STEP 1 — BUCKET ASSIGNMENT (what the store IS today)
    Rank all stores by actual VPO (monthly revenue), high → low:
        A  = top 20%      (high performers)
        B  = next 20%     (good performers)
        C  = next 30%     (mid performers)
        D  = bottom 30%   (low performers)

STEP 2 — POTENTIAL MODELLING (what the store COULD earn)
    Fit a Quantile Regression at the 75th percentile.
    Features: neighbourhood demographics (per-capita income, SEC households),
              proximity (distance to offices, malls, schools, transport),
              store attributes (size, cooler, footfall, format, channel).
    Target: VPO

    The 75th-percentile model predicts the UPPER REALISTIC potential
    for a store given its environment — not the average, but what similar
    well-run stores in the same type of neighbourhood actually achieve.

STEP 3 — OPPORTUNITY GAP
    opportunity_gap = predicted_75th_VPO - actual_VPO

    A positive gap means the store is UNDERPERFORMING its environment.
    The bigger the gap, the more headroom there is.

STEP 4 — PLUS TAGGING (within-bucket upgrade)
    Within each bucket, stores with a positive opportunity gap are tagged "+":
        A+ : stores in bucket A that are below their 75th-pct potential
        B+ : stores in bucket B that are below their 75th-pct potential
        C+ : stores in bucket C that are below their 75th-pct potential
        D+ : stores in bucket D that are below their 75th-pct potential

    The final_priority tag carries both dimensions:
        A, A+, B, B+, C, C+, D, D+

Claude then writes a plain-English narrative explaining:
  - what drives the model's potential estimate
  - why certain store types have large gaps
  - recommended interventions per priority tier
"""

import logging
import warnings
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from typing import Tuple, Optional
from agents.llm_client import call_llm
from agents.context_loader import ContextLoader
from agents.segmentation_agent import _coerce_column_to_numeric

logger = logging.getLogger("perfect_store.prioritization")

_ctx = ContextLoader()
warnings.filterwarnings("ignore")


# ── Constants ────────────────────────────────────────────────────────────────

# Bucket thresholds (percentile of VPO, high → low)
BUCKET_THRESHOLDS = {
    "A": (80, 100),   # top 20%
    "B": (60, 80),    # next 20%
    "C": (30, 60),    # next 30%
    "D": (0,  30),    # bottom 30%
}

# Features used in the potential model
POTENTIAL_FEATURES_NUMERIC = [
    # Demographics
    "nbrhd_per_capita_income",
    "sec_a_hhs", "sec_b_hhs", "sec_c_hhs", "sec_d_hhs", "sec_e_hhs",
    # Proximity
    "distance_to_nearest_large_office_in_km",
    "distance_to_nearest_malls",
    "distance_to_nearest_bus_stn_in_km",
    "distance_to_nearest_train_stn_in_km",
    "distance_to_nearest_school_in_km",
    "distance_to_nearest_commercial_place",
    # Catchment activity
    "no_of_schools_in_a_1_km_radius",
    "no_of_colleges_in_a_1_km_radius",
    "estmtd_daily_footfall_numeric",
    # Store
    "store_size",
    "AVG_SKU",
    "ACTIVE_MONTHS",
]

FOOTFALL_MAP = {
    "low (<30)": 15, "low": 15,
    "medium (30-100)": 65, "medium": 65,
    "high (>100)": 150, "high": 150,
}

QUANTILE = 0.75   # predict upper realistic potential


# ── Step 1: Bucket assignment ────────────────────────────────────────────────

def assign_abcd_buckets(df: pd.DataFrame, vpo_col: str = "VPO") -> pd.DataFrame:
    """
    Assign A/B/C/D buckets based on VPO percentile rank.
    Higher VPO = higher bucket.
    """
    df = df.copy()
    vpo = df[vpo_col].fillna(0)
    pct_rank = vpo.rank(pct=True) * 100   # 0–100 percentile

    def _bucket(p):
        if p > 80:   return "A"
        elif p > 60: return "B"
        elif p > 30: return "C"
        else:        return "D"

    df["vpo_percentile"] = pct_rank.round(2)
    df["priority_bucket"] = pct_rank.map(_bucket)

    counts = df["priority_bucket"].value_counts().sort_index()
    logger.info("Bucket distribution:")
    for b, n in counts.items():
        pct = n / len(df) * 100
        logger.info(f"  Bucket {b}: {n:,} outlets ({pct:.1f}%)")

    return df


# ── Step 2: Feature preparation for potential model ──────────────────────────

def _prep_footfall(df: pd.DataFrame) -> pd.DataFrame:
    """Convert footfall tag to numeric midpoint."""
    if "estmtd_daily_footfall_tag" in df.columns:
        df["estmtd_daily_footfall_numeric"] = (
            df["estmtd_daily_footfall_tag"]
            .str.lower().str.strip()
            .map(FOOTFALL_MAP)
        )
    return df


def _prep_binary(df: pd.DataFrame) -> pd.DataFrame:
    """Convert Yes/No columns to 1/0."""
    for col in ["cooler_available", "BI"]:
        if col in df.columns:
            new = col + "_bin"
            df[new] = df[col].str.strip().str.lower().map({"yes": 1, "no": 0})
    return df


def _prep_store_format(df: pd.DataFrame) -> pd.DataFrame:
    """1 if Modern Trade, 0 if General Trade."""
    if "store_format" in df.columns:
        df["is_modern_trade"] = (
            df["store_format"].str.upper().str.strip() == "MT"
        ).astype(float)
    return df


def _prep_sector(df: pd.DataFrame) -> pd.DataFrame:
    """1 if Urban sector."""
    if "sector" in df.columns:
        df["is_urban"] = (
            df["sector"].str.lower().str.strip() == "urban"
        ).astype(float)
    return df


def build_potential_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    """
    Prepare features for the potential model.
    Returns (df_with_engineered_cols, list_of_feature_cols_used).
    """
    df = df.copy()
    df = _prep_footfall(df)
    df = _prep_binary(df)
    df = _prep_store_format(df)
    df = _prep_sector(df)

    # Collect all candidate numeric feature columns
    candidates = POTENTIAL_FEATURES_NUMERIC + [
        "cooler_available_bin", "BI_bin", "is_modern_trade", "is_urban"
    ]

    # Keep only columns that exist and have ≥10% coverage
    usable = []
    for col in dict.fromkeys(candidates):   # deduplicate
        if col in df.columns:
            coverage = df[col].notna().mean()
            if coverage >= 0.10:
                usable.append(col)
                logger.debug(f"  Potential feature '{col}': {coverage:.1%} coverage")
            else:
                logger.debug(f"  Skipping '{col}': {coverage:.1%} coverage too low")

    if len(usable) < 2:
        raise ValueError(
            f"Not enough features for potential model (found {len(usable)}). "
            "Check column names in config."
        )

    logger.info(f"Potential model using {len(usable)} features: {usable}")
    return df, usable


# ── Step 3: Quantile regression (75th percentile) ───────────────────────────

def _fit_quantile_regression(X: np.ndarray, y: np.ndarray,
                             quantile: float = 0.75) -> "fitted model":
    """
    Fit a quantile regression model.
    Tries sklearn QuantileRegressor first (memory-efficient HiGHS LP solver),
    then statsmodels QuantReg, then falls back to OLS.
    """
    try:
        from sklearn.linear_model import QuantileRegressor
        model = QuantileRegressor(quantile=quantile, alpha=0.01, solver="highs")
        model.fit(X, y)
        logger.info(f"Fitted sklearn QuantileRegressor (q={quantile})")
        return ("sklearn", model)
    except Exception:
        pass

    try:
        import statsmodels.api as sm
        X_const = sm.add_constant(X)
        model = sm.QuantReg(y, X_const)
        result = model.fit(q=quantile, max_iter=2000)
        logger.info(f"Fitted statsmodels QuantReg (q={quantile})")
        return ("statsmodels", result)
    except ImportError:
        pass

    # Final fallback: plain linear regression (predicts mean, not upper bound)
    from sklearn.linear_model import LinearRegression
    model = LinearRegression()
    model.fit(X, y)
    logger.warning(
        "Neither sklearn QuantileRegressor nor statsmodels available — "
        "using OLS linear regression as fallback."
    )
    return ("ols", model)


def _predict(model_tuple, X: np.ndarray) -> np.ndarray:
    kind, model = model_tuple
    if kind == "statsmodels":
        import statsmodels.api as sm
        X_const = sm.add_constant(X, has_constant="add")
        return model.predict(X_const)
    else:
        return model.predict(X)


def fit_potential_model(df: pd.DataFrame, feature_cols: list,
                        vpo_col: str = "VPO",
                        quantile: float = QUANTILE,
                        sample_cap: int = 50_000
                        ) -> Tuple[np.ndarray, object, object, object]:
    """
    Fit quantile regression and return predicted potential VPO for every outlet.

    Returns:
        predicted_vpo  : np.ndarray of predicted upper-potential VPO
        model          : fitted model tuple
        imputer        : fitted SimpleImputer
        scaler         : fitted StandardScaler
    """
    # Robustly coerce each feature column to numeric — handles hex strings
    # (e.g. '0x2a') and other non-numeric artefacts sometimes present in
    # exported CPG data. Unparseable values → NaN (picked up by the imputer).
    feat_df = df[feature_cols].copy()
    n_coerced = 0
    for col in feat_df.columns:
        before = feat_df[col].isna().sum()
        feat_df[col] = _coerce_column_to_numeric(feat_df[col])
        coerced = feat_df[col].isna().sum() - before
        if coerced > 0:
            logger.warning(
                f"Column '{col}': {coerced:,} values could not be parsed "
                f"(hex/string artefacts) → set to NaN for imputation"
            )
            n_coerced += coerced
    if n_coerced > 0:
        logger.warning(
            f"Total coerced values across all potential features: {n_coerced:,}"
        )

    X_raw = feat_df.values.astype(float)
    y = _coerce_column_to_numeric(df[vpo_col]).fillna(0).values.astype(float)

    # Impute + scale
    imputer = SimpleImputer(strategy="median")
    X_imp = imputer.fit_transform(X_raw)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imp)

    # Subsample for fitting (for speed with 900k rows)
    n = len(X_scaled)
    if n > sample_cap:
        idx = np.random.default_rng(42).choice(n, sample_cap, replace=False)
        X_fit, y_fit = X_scaled[idx], y[idx]
        logger.info(f"Fitting on {sample_cap:,}-row sample (full dataset: {n:,} rows)")
    else:
        X_fit, y_fit = X_scaled, y

    model = _fit_quantile_regression(X_fit, y_fit, quantile)

    # Predict on ALL rows
    predicted = _predict(model, X_scaled)
    predicted = np.maximum(predicted, 0)   # floor at 0

    logger.info(
        f"Potential model — predicted VPO: "
        f"min={predicted.min():,.0f}  mean={predicted.mean():,.0f}  "
        f"max={predicted.max():,.0f}  (q={quantile})"
    )
    return predicted, model, imputer, scaler


# ── Step 4: Opportunity gap & plus tagging ───────────────────────────────────

def compute_opportunity_gap(df: pd.DataFrame, predicted_vpo: np.ndarray,
                            vpo_col: str = "VPO") -> pd.DataFrame:
    """
    Compute opportunity gap and assign plus tags.

    opportunity_gap = predicted_75th_VPO - actual_VPO
    Positive gap → store is below its environmental potential → tagged '+'
    """
    df = df.copy()
    actual = df[vpo_col].fillna(0).values

    df["predicted_potential_vpo"] = predicted_vpo.round(2)
    df["opportunity_gap"] = (predicted_vpo - actual).round(2)
    df["gap_pct_of_potential"] = (
        df["opportunity_gap"] / df["predicted_potential_vpo"].replace(0, np.nan) * 100
    ).round(1)

    # "+" = store is below 75th-pct potential (positive gap)
    df["has_upside"] = df["opportunity_gap"] > 0

    # Final priority: bucket + "+" suffix if upside exists
    df["priority"] = df.apply(
        lambda r: r["priority_bucket"] + "+" if r["has_upside"] else r["priority_bucket"],
        axis=1
    )

    # Within each bucket, rank stores by gap size (largest gap = rank 1)
    for bucket in ["A", "B", "C", "D"]:
        mask = df["priority_bucket"] == bucket
        df.loc[mask, "gap_rank_within_bucket"] = (
            df.loc[mask, "opportunity_gap"]
            .rank(ascending=False, method="min")
            .astype(int)
        )

    # Summary
    logger.info("Priority distribution:")
    for tag in ["A+", "A", "B+", "B", "C+", "C", "D+", "D"]:
        n = (df["priority"] == tag).sum()
        if n > 0:
            avg_gap = df.loc[df["priority"] == tag, "opportunity_gap"].mean()
            logger.info(f"  {tag:3s}: {n:,} outlets | avg opportunity gap ₹{avg_gap:,.0f}/month")

    return df


# ── Step 5: Claude narrative ─────────────────────────────────────────────────

def get_claude_priority_narrative(df: pd.DataFrame, feature_cols: list,
                                  api_key: str,
                                  model: str = "claude-opus-4-6",
                                  dq_context: Optional[str] = None) -> str:
    """
    Ask Claude to write a business narrative explaining the prioritization:
    what drives potential, why certain stores underperform, and what to do.
    """
    # Build summary stats per priority tier
    summary = []
    for tag in ["A+", "A", "B+", "B", "C+", "C", "D+", "D"]:
        subset = df[df["priority"] == tag]
        if len(subset) == 0:
            continue
        row = {
            "priority": tag,
            "count": len(subset),
            "pct_total": round(len(subset) / len(df) * 100, 1),
            "avg_actual_vpo": round(subset["VPO"].mean(), 0) if "VPO" in subset else 0,
            "avg_predicted_vpo": round(subset["predicted_potential_vpo"].mean(), 0),
            "avg_opportunity_gap": round(subset["opportunity_gap"].mean(), 0),
        }
        # Top channel/format/sector for context
        for col in ["channel", "store_format", "sector", "Top City"]:
            if col in subset.columns:
                top_val = subset[col].dropna().value_counts().index
                if len(top_val):
                    row[f"top_{col}"] = str(top_val[0])
        summary.append(row)

    summary_text = "\n".join(
        f"  {r['priority']:3s} | {r['count']:,} outlets ({r['pct_total']}%) | "
        f"Actual VPO ₹{r['avg_actual_vpo']:,.0f} | "
        f"Predicted potential ₹{r['avg_predicted_vpo']:,.0f} | "
        f"Gap ₹{r['avg_opportunity_gap']:,.0f}"
        for r in summary
    )

    # Feature importance proxy: correlation of each feature with VPO
    try:
        numeric_df = df[feature_cols + ["VPO"]].dropna()
        corr = numeric_df.corr()["VPO"].drop("VPO").abs().sort_values(ascending=False).head(5)
        top_drivers = ", ".join(f"{c} (r={v:.2f})" for c, v in corr.items())
    except Exception:
        top_drivers = "demographics, store size, proximity to commercial hubs"

    dq_note = f"\n## Data Quality Context\n{dq_context}\n" if dq_context else ""

    prompt = f"""We have segmented {len(df):,} retail outlets into priority tiers A/B/C/D (based on actual monthly revenue VPO) and identified "+" outlets within each tier that have untapped potential — stores whose actual VPO is below what a quantile regression model (75th percentile) predicts they should earn given their neighbourhood demographics and proximity to footfall generators.
{dq_note}
## Priority Tier Summary
{summary_text}

## Top drivers of predicted potential (by correlation with VPO)
{top_drivers}

## Quantile regression model
- Target variable: VPO (monthly revenue per outlet, in ₹)
- Quantile: 75th percentile (upper realistic potential given the store's environment)
- Features: neighbourhood per-capita income, SEC household counts (A through E), proximity to offices/malls/transport/schools, store size, daily footfall estimate, cooler availability, store format (GT/MT)
- Opportunity gap = Predicted 75th-pct VPO − Actual VPO (positive = underperforming)

## Your task
Write a business narrative (500–700 words) for the Perfect Store leadership team covering:

1. **What the model reveals** — which environmental factors most strongly predict outlet revenue potential in the Indian FMCG context, and what this means for territory planning.

2. **A+ and B+ stores** — why these outlets are the highest-priority intervention targets. What does it mean that a store is in the top 40% by revenue yet still below its neighbourhood potential? What interventions typically close this gap (e.g. cooler placement, SKU assortment upgrade, visit frequency, planogram compliance)?

3. **C+ and D+ stores** — are these high-potential stores in underserved catchments, or structural low performers? How should the field team approach them differently from A+/B+?

4. **Recommended field actions** — a concrete, prioritised action matrix for the sales team:
   - A+: [action]
   - B+: [action]
   - C+: [action]
   - D+: [action]
   - A/B/C/D (non-plus): [action]

Use Indian CPG trade language: GT, MT, kirana, VPO, SEC, Perfect Store, FMCG. Be specific and actionable — this will be printed in the executive PDF report.
"""

    return call_llm(prompt, api_key, model, max_tokens=2000,
                    system_prompt=_ctx.build("prioritization"))


# ── Main entry point ─────────────────────────────────────────────────────────

def run_prioritization(df: pd.DataFrame, config: dict, api_key: str,
                       model: str = "claude-opus-4-6",
                       dq_context: Optional[str] = None,
                       ) -> Tuple[pd.DataFrame, str]:
    """
    Full prioritization pipeline.
    Returns (df_with_priority_tags, claude_narrative_text).
    """
    vpo_col = config.get("columns", {}).get("monthly_revenue", "VPO")

    if vpo_col not in df.columns:
        raise ValueError(f"VPO column '{vpo_col}' not found. Check config columns.monthly_revenue.")

    logger.info("=" * 55)
    logger.info("Prioritization Agent starting")
    logger.info(f"  Outlets: {len(df):,} | VPO column: {vpo_col}")
    logger.info("=" * 55)

    # Step 1: A/B/C/D buckets
    logger.info("Step 1/4 — Assigning A/B/C/D buckets")
    df = assign_abcd_buckets(df, vpo_col)

    # Step 2: Feature engineering for potential model
    logger.info("Step 2/4 — Building potential features")
    df, feature_cols = build_potential_features(df)

    # Step 3: Quantile regression
    logger.info(f"Step 3/4 — Fitting quantile regression (q={QUANTILE})")
    np.random.seed(42)
    predicted_vpo, fitted_model, imputer, scaler = fit_potential_model(
        df, feature_cols, vpo_col, QUANTILE
    )

    # Step 4: Opportunity gap + plus tags
    logger.info("Step 4/4 — Computing opportunity gaps and plus tags")
    df = compute_opportunity_gap(df, predicted_vpo, vpo_col)

    # Step 5: LLM narrative
    import os
    llm_backend = os.getenv("LLM_BACKEND", "anthropic").strip().lower()
    use_llm = bool(api_key) or llm_backend in ("local", "gemini", "vertex", "azure")
    if use_llm:
        logger.info("Requesting LLM priority narrative...")
        try:
            narrative = get_claude_priority_narrative(
                df, feature_cols, api_key, model, dq_context=dq_context)
        except Exception as e:
            logger.warning(
                f"LLM priority narrative failed ({type(e).__name__}: {e}) — "
                f"using fallback summary"
            )
            narrative = _fallback_narrative(df)
    else:
        narrative = _fallback_narrative(df)

    return df, narrative


def _fallback_narrative(df: pd.DataFrame) -> str:
    """Plain-text summary when no API key is available."""
    lines = ["PRIORITIZATION SUMMARY", "=" * 40]
    for tag in ["A+", "A", "B+", "B", "C+", "C", "D+", "D"]:
        n = (df["priority"] == tag).sum()
        if n > 0:
            avg_gap = df.loc[df["priority"] == tag, "opportunity_gap"].mean()
            lines.append(f"{tag:3s}: {n:,} outlets | avg opportunity gap ₹{avg_gap:,.0f}/month")
    return "\n".join(lines)
