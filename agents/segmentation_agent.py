"""
Segmentation Agent — clusters outlets directly from flat outlet-level data.

Since each row in the India Master File IS one store (already aggregated),
we skip RFM computation and cluster directly on:
  - Sales performance  : VPO, TOTAL_REVENUE, AVG_SKU, ACTIVE_MONTHS
  - Store attributes   : store_size, cooler_available, store_format, sector, footfall
  - Demographics       : per-capita income, SEC household counts
  - Proximity          : distance to schools, offices, transport, malls
  - SKU mix            : individual SKU revenue columns

Claude then labels each cluster in CPG business terms.
"""

import os
import re
import json
import logging
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from typing import Tuple, List, Optional
from agents.llm_client import call_llm
from agents.context_loader import ContextLoader

logger = logging.getLogger("perfect_store.segmentation")

_ctx = ContextLoader()


# ── Feature engineering ──────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Prepare the feature matrix for clustering.
    - Convert categorical flags to numeric (0/1)
    - Encode ordinal categories
    - Return only columns that have enough non-null values
    """
    seg_cfg = config.get("segmentation", {})
    numeric_features = seg_cfg.get("numeric_features", [])
    categorical_features = seg_cfg.get("categorical_features", [])
    min_features = seg_cfg.get("min_features_required", 3)

    df = df.copy()

    # ── Convert footfall tag to numeric ──────────────────────────────────
    footfall_map = {
        "low (<30)": 15, "low": 15,
        "medium (30-100)": 65, "medium": 65,
        "high (>100)": 150, "high": 150,
    }
    if "estmtd_daily_footfall_tag" in df.columns:
        df["estmtd_daily_footfall_numeric"] = (
            df["estmtd_daily_footfall_tag"]
            .str.lower().str.strip()
            .map(footfall_map)
        )

    # ── Binary Yes/No columns → 1/0 ──────────────────────────────────────
    yes_no_cols = [
        "cooler_available", "chocolates_avlblty", "biscuits_avlblty",
        "noodles_avlblty", "protein_bars_avlblty", "oats_avlblty",
        "premium_category_sold", "premium_snacks_sold", "BI",
    ]
    for col in yes_no_cols:
        if col in df.columns:
            df[col + "_num"] = (
                df[col].str.strip().str.lower()
                .map({"yes": 1, "no": 0})
            )
            # Add numeric version to feature list if not already there
            numeric_features = list(numeric_features) + [col + "_num"]

    # ── Ordinal encoding for store size ──────────────────────────────────
    size_map = {
        "<200 sqft": 1, "200–300 sqft": 2, "300–500 sqft": 3,
        "500–1000 sqft": 4, ">1000 sqft": 5,
        "micro outlet": 1, "small outlet": 2, "medium outlet": 3,
        "large outlet": 4, "very large outlet": 5,
    }
    if "store_size_bracket" in df.columns:
        df["store_size_bracket_num"] = (
            df["store_size_bracket"].str.lower().str.strip().map(size_map)
        )
        numeric_features = list(numeric_features) + ["store_size_bracket_num"]

    # ── Ordinal encoding for price pack lead ─────────────────────────────
    pack_map = {"rs. 5": 5, "rs. 10": 10, "rs. 15": 15, "rs. 20": 20, "rs. 30": 30}
    for col in ["western_salty_lead_pack", "chocolates_lead_pack", "biscuits_lead_pack"]:
        if col in df.columns:
            new_col = col + "_num"
            df[new_col] = df[col].str.lower().str.strip().map(pack_map)
            numeric_features = list(numeric_features) + [new_col]

    # ── Store format one-hot ──────────────────────────────────────────────
    if "store_format" in df.columns:
        df["is_modern_trade"] = (
            df["store_format"].str.upper().str.strip() == "MT"
        ).astype(float)
        numeric_features = list(numeric_features) + ["is_modern_trade"]

    # ── Urban vs periphery ────────────────────────────────────────────────
    if "urban_vs_periphery_tagging" in df.columns:
        df["is_urban"] = (
            df["urban_vs_periphery_tagging"].str.lower().str.strip() == "urban"
        ).astype(float)
        numeric_features = list(numeric_features) + ["is_urban"]

    # ── Sector urban/rural ────────────────────────────────────────────────
    if "sector" in df.columns:
        df["is_urban_sector"] = (
            df["sector"].str.lower().str.strip() == "urban"
        ).astype(float)
        numeric_features = list(numeric_features) + ["is_urban_sector"]

    # ── Auto-detect brand revenue columns not already in numeric_features ──
    # Picks up  "LAYS MEDIUM", "KURKURE SMALL" etc. produced by the SKU
    # transactional aggregation step, matching on sku_column_keywords.
    sku_keywords = seg_cfg.get("sku_column_keywords", [])
    if sku_keywords:
        existing = set(numeric_features)
        auto_brand_cols = [
            c for c in df.columns
            if any(kw in c.upper() for kw in sku_keywords) and c not in existing
        ]
        if auto_brand_cols:
            numeric_features = list(numeric_features) + auto_brand_cols
            logger.info(f"Auto-added {len(auto_brand_cols)} brand revenue columns to features")

    # ── Priority bucket ordinal (only present when prioritization ran first) ─
    # Encodes A/B/C/D as 4/3/2/1 so clusters are commercially anchored to
    # revenue tier without being fully determined by it (VPO is already a feature).
    if "priority_bucket" in df.columns:
        bucket_map = {"A": 4, "B": 3, "C": 2, "D": 1}
        df["priority_bucket_num"] = df["priority_bucket"].map(bucket_map)
        numeric_features = list(numeric_features) + ["priority_bucket_num"]
        logger.info("Priority bucket encoded as numeric feature (A=4, B=3, C=2, D=1)")

    # ── Cap negative SKU values at 0 (returns/credits) ───────────────────
    sku_keywords = seg_cfg.get("sku_column_keywords", [])
    sku_cols = [c for c in df.columns if sku_keywords and any(
        kw in c.upper() for kw in sku_keywords
    )]
    for col in sku_cols:
        if col in df.columns:
            df[col] = df[col].clip(lower=0)

    # ── Filter to features that exist and have sufficient data ───────────
    available = []
    for col in dict.fromkeys(numeric_features):  # deduplicate, preserve order
        if col in df.columns:
            non_null_pct = df[col].notna().mean()
            if non_null_pct >= 0.10:  # at least 10% of rows have data
                available.append(col)
                logger.debug(f"Feature '{col}': {non_null_pct:.1%} coverage")
            else:
                logger.debug(f"Dropping '{col}': only {non_null_pct:.1%} coverage")

    if len(available) < min_features:
        raise ValueError(
            f"Only {len(available)} usable features found (minimum {min_features}). "
            f"Check column names in config."
        )

    logger.info(f"Using {len(available)} features for clustering: {available}")
    return df, available


def _coerce_column_to_numeric(series: pd.Series) -> pd.Series:
    """
    Robustly convert a Series to float.
    Handles:
      - Normal numeric values and strings ('3.14', '42')
      - Hex strings ('0x2a' → 42.0) — sometimes present in exported CPG data
      - Everything else → NaN (picked up by the imputer downstream)
    """
    def _convert(val):
        if pd.isna(val):
            return np.nan
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        # Hex string check
        if s.lower().startswith("0x"):
            try:
                return float(int(s, 16))
            except ValueError:
                return np.nan
        # Normal numeric string
        try:
            return float(s)
        except ValueError:
            return np.nan

    return series.apply(_convert)


def build_feature_matrix(df: pd.DataFrame, feature_cols: list) -> np.ndarray:
    """
    Extract, impute, and scale feature matrix for KMeans.
    Applies robust numeric coercion per column to handle hex strings
    or other non-numeric artefacts in the source data.
    """
    feat_df = df[feature_cols].copy()

    n_coerced = 0
    for col in feat_df.columns:
        original_nulls = feat_df[col].isna().sum()
        feat_df[col] = _coerce_column_to_numeric(feat_df[col])
        new_nulls = feat_df[col].isna().sum()
        coerced = new_nulls - original_nulls
        if coerced > 0:
            logger.warning(
                f"Column '{col}': {coerced:,} values could not be parsed "
                f"(hex/string artefacts) → set to NaN for imputation"
            )
            n_coerced += coerced

    if n_coerced > 0:
        logger.warning(
            f"Total coerced values across all features: {n_coerced:,}. "
            f"Check source data for hex strings (e.g. '0x2a') or unexpected text."
        )

    X = feat_df.values.astype(float)

    # Impute missing values with median (robust to outliers)
    imputer = SimpleImputer(strategy="median")
    X = imputer.fit_transform(X)

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return X_scaled, imputer, scaler


# ── KMeans Clustering ────────────────────────────────────────────────────────

def run_kmeans(df: pd.DataFrame, feature_cols: list, n_clusters: int,
               random_state: int = 42) -> Tuple[pd.DataFrame, object]:
    """
    Run KMeans (MiniBatchKMeans for large datasets > 100k rows).
    Returns df with 'cluster' column added, plus the fitted model.
    """
    X_scaled, imputer, scaler = build_feature_matrix(df, feature_cols)
    n_rows = len(df)

    if n_rows > 100_000:
        logger.info(f"Large dataset ({n_rows:,} rows) — using MiniBatchKMeans")
        model = MiniBatchKMeans(
            n_clusters=n_clusters, random_state=random_state,
            batch_size=10_000, n_init=5, max_iter=300
        )
    else:
        model = KMeans(
            n_clusters=n_clusters, random_state=random_state,
            n_init=10, max_iter=300
        )

    labels = model.fit_predict(X_scaled)
    df = df.copy()
    df["cluster"] = labels

    logger.info(f"Clustering complete. Distribution:")
    for cid in range(n_clusters):
        cnt = (labels == cid).sum()
        logger.info(f"  Cluster {cid}: {cnt:,} outlets ({cnt/n_rows:.1%})")

    return df, model


# ── Cluster Profile Builder ─────────────────────────────────────────────────

def build_cluster_profiles(df: pd.DataFrame, feature_cols: list,
                           config: dict) -> List[dict]:
    """Build a rich profile dict per cluster for Claude to interpret."""
    label_features = config.get("segmentation", {}).get("label_features", [])
    id_col = config.get("segmentation", {}).get("id_col", "OUTLET_UID_EDITED")
    profiles = []

    for cid in sorted(df["cluster"].unique()):
        subset = df[df["cluster"] == cid]
        n = len(subset)

        profile = {
            "cluster_id": int(cid),
            "outlet_count": n,
            "pct_of_total": round(n / len(df) * 100, 1),
        }

        # Sales performance
        for col in ["VPO", "TOTAL_REVENUE", "AVG_SKU", "ACTIVE_MONTHS"]:
            if col in subset.columns:
                vals = pd.to_numeric(subset[col], errors="coerce").dropna()
                if len(vals):
                    profile[f"avg_{col}"] = round(float(vals.mean()), 2)
                    profile[f"median_{col}"] = round(float(vals.median()), 2)

        # Top categorical breakdowns
        for col in label_features:
            if col in subset.columns:
                vc = subset[col].dropna().value_counts(normalize=True).head(3)
                if len(vc):
                    profile[f"top_{col}"] = {
                        k: f"{v:.0%}" for k, v in vc.items()
                    }

        # Numeric feature averages (selected key ones)
        numeric_summary_cols = [
            "store_size", "nbrhd_per_capita_income",
            "distance_to_nearest_large_office_in_km",
            "distance_to_nearest_malls",
            "distance_to_nearest_train_stn_in_km",
            "no_of_schools_in_a_1_km_radius",
            "sec_a_hhs", "sec_b_hhs", "sec_c_hhs", "sec_d_hhs", "sec_e_hhs",
        ]
        numeric_avgs = {}
        for col in numeric_summary_cols:
            if col in subset.columns:
                vals = pd.to_numeric(subset[col], errors="coerce").dropna()
                if len(vals) > 0:
                    numeric_avgs[col] = round(float(vals.mean()), 1)
        if numeric_avgs:
            profile["avg_demographics"] = numeric_avgs

        profiles.append(profile)

    return profiles


# ── Claude-powered segment labeling ─────────────────────────────────────────

def label_segments_with_claude(
    profiles: List[dict],
    api_key: str,
    model: str = "claude-opus-4-6",
    dq_context: Optional[str] = None,
    priority_context: Optional[str] = None,
) -> dict:
    """
    Send cluster profiles to Claude and get CPG business labels.
    Returns {cluster_id: {"label": str, "channel": str, "occasion": str,
                          "description": str, "action": str}}.
    """
    profiles_text = ""
    for p in profiles:
        profiles_text += f"\n### Cluster {p['cluster_id']} — {p['outlet_count']:,} outlets ({p['pct_of_total']}% of total)\n"

        if "avg_VPO" in p:
            profiles_text += f"- Monthly Revenue (VPO): avg ₹{p['avg_VPO']:,.0f}, median ₹{p.get('median_VPO', 0):,.0f}\n"
        if "avg_TOTAL_REVENUE" in p:
            profiles_text += f"- Total Revenue: avg ₹{p['avg_TOTAL_REVENUE']:,.0f}\n"
        if "avg_AVG_SKU" in p:
            profiles_text += f"- Avg SKU Count: {p['avg_AVG_SKU']:.1f}\n"
        if "avg_ACTIVE_MONTHS" in p:
            profiles_text += f"- Avg Active Months: {p['avg_ACTIVE_MONTHS']:.1f}\n"

        for k, v in p.items():
            if k.startswith("top_"):
                col_name = k.replace("top_", "")
                profiles_text += f"- {col_name}: {v}\n"

        if "avg_demographics" in p:
            profiles_text += f"- Demographics: {p['avg_demographics']}\n"

        profiles_text += "\n"

    upstream_context = ""
    if dq_context:
        upstream_context += f"\n## Data Quality Context\n{dq_context}\n"
    if priority_context:
        upstream_context += f"\n## Priority Distribution Context\n{priority_context}\n"

    prompt = f"""Below are cluster profiles from a segmentation of {sum(p['outlet_count'] for p in profiles):,} retail outlets across India.
The data includes store sales performance (VPO = monthly revenue), SKU breadth, outlet attributes (channel, format, sector), and neighbourhood demographics (SEC household classification, proximity to schools/offices/malls).
{upstream_context}
{profiles_text}

## Your task
For each cluster, provide in the CPG/FMCG context:
1. A **label** (6-10 words) — evocative India archetype, e.g. "Schoolzone Youth Impulse GT"
2. A **channel** — one of: GT, MT, AfH, EC
3. An **occasion** — one of: Immediate/GrabGo, FutureConsumption/StockUp, MealAccompaniment, Celebratory, OnTheMove, Youth, Premium, Morning
4. A **description** (2-3 sentences) — what defines this store type, its shoppers, commercial significance
5. An **action** for the Perfect Store / trade team — cooler placement, SKU assortment, activation type, visit frequency

Use Indian CPG trade terminology: GT, MT, kirana, AfH, VPO, SEC, FMCG, Rs. price points.

Return ONLY a valid JSON array — no prose, no markdown fences. Each element must follow this exact schema:
[
  {{
    "cluster_id": <int>,
    "label": "<6-10 word label>",
    "channel": "<GT|MT|AfH|EC>",
    "occasion": "<occasion name>",
    "description": "<2-3 sentences>",
    "action": "<recommended action>"
  }}
]
"""

    text = call_llm(prompt, api_key, model, max_tokens=3000,
                    system_prompt=_ctx.build("segmentation"))
    logger.info("Segment labels received from LLM.")
    labels = _parse_json_labels(text, len(profiles))
    if labels is None:
        logger.warning("JSON label parsing failed — falling back to text parser")
        labels = _parse_segment_labels(text, len(profiles))
    return labels


def _parse_json_labels(text: str, n_clusters: int) -> Optional[dict]:
    """
    Parse a JSON array returned by the LLM into the labels dict.
    Returns None if parsing fails so the caller can fall back to text parsing.
    """
    try:
        clean = text.strip()
        # Strip optional ```json ... ``` fences
        clean = re.sub(r'^```[a-zA-Z]*\s*', '', clean)
        clean = re.sub(r'\s*```$', '', clean.rstrip())
        data = json.loads(clean)
        if not isinstance(data, list):
            return None
        labels = {}
        for item in data:
            cid = int(item["cluster_id"])
            labels[cid] = {
                "label":       item.get("label", f"Segment {cid}"),
                "channel":     item.get("channel", "GT"),
                "occasion":    item.get("occasion", "Immediate/GrabGo"),
                "description": item.get("description", ""),
                "action":      item.get("action", ""),
            }
        # Ensure every cluster has an entry
        for i in range(n_clusters):
            if i not in labels:
                labels[i] = {
                    "label": f"Segment {i}", "channel": "GT",
                    "occasion": "Immediate/GrabGo",
                    "description": "Cluster profile pending review.",
                    "action": "Review cluster details manually."
                }
        return labels
    except Exception:
        return None


def _parse_segment_labels(text: str, n_clusters: int) -> dict:
    """Parse Claude's response into structured labels including channel and occasion."""
    labels = {}
    lines = text.strip().split("\n")
    current_cluster = None

    for line in lines:
        line_stripped = line.strip()
        upper = line_stripped.upper()
        if upper.startswith("CLUSTER") and ":" in line_stripped:
            try:
                cid = int(line_stripped.split(":")[0].replace("CLUSTER", "").strip())
                current_cluster = cid
                labels[cid] = {"label": "", "channel": "", "occasion": "", "description": "", "action": ""}
            except ValueError:
                continue
        elif current_cluster is not None:
            if upper.startswith("LABEL:"):
                labels[current_cluster]["label"] = line_stripped.split(":", 1)[1].strip()
            elif upper.startswith("CHANNEL:"):
                labels[current_cluster]["channel"] = line_stripped.split(":", 1)[1].strip()
            elif upper.startswith("OCCASION:"):
                labels[current_cluster]["occasion"] = line_stripped.split(":", 1)[1].strip()
            elif upper.startswith("DESCRIPTION:"):
                labels[current_cluster]["description"] = line_stripped.split(":", 1)[1].strip()
            elif upper.startswith("ACTION:"):
                labels[current_cluster]["action"] = line_stripped.split(":", 1)[1].strip()

    for i in range(n_clusters):
        if i not in labels:
            labels[i] = {
                "label": f"Segment {i}",
                "channel": "GT",
                "occasion": "Immediate/GrabGo",
                "description": "Cluster profile pending review.",
                "action": "Review cluster details manually."
            }
    return labels


# ── Rich per-segment multi-dimensional summaries ────────────────────────────

RICH_SECTIONS = [
    "identity_card",
    "shopper_profile",
    "demographic_catchment",
    "store_characteristics",
    "dimensions_radar",
    "comparative_snapshot",
    "commercial_action_plan",
]


def _empty_rich_summary() -> dict:
    return {k: "" for k in RICH_SECTIONS}


def _profile_to_prompt_block(profile: dict) -> str:
    """Flatten a cluster profile dict into a compact prompt snippet."""
    lines = [
        f"Cluster {profile['cluster_id']}: {profile['outlet_count']:,} outlets "
        f"({profile['pct_of_total']}% of total)"
    ]
    if "avg_VPO" in profile:
        lines.append(
            f"- Avg Monthly Revenue (VPO): ₹{profile['avg_VPO']:,.0f}  "
            f"(median ₹{profile.get('median_VPO', 0):,.0f})"
        )
    if "avg_TOTAL_REVENUE" in profile:
        lines.append(f"- Avg Total Revenue: ₹{profile['avg_TOTAL_REVENUE']:,.0f}")
    if "avg_AVG_SKU" in profile:
        lines.append(f"- Avg SKU Count: {profile['avg_AVG_SKU']}")
    if "avg_ACTIVE_MONTHS" in profile:
        lines.append(f"- Avg Active Months: {profile['avg_ACTIVE_MONTHS']}")
    for k, v in profile.items():
        if k.startswith("top_"):
            lines.append(f"- {k.replace('top_', '')}: {v}")
    if "avg_demographics" in profile:
        lines.append(f"- Neighbourhood demographics: {profile['avg_demographics']}")
    return "\n".join(lines)


def generate_segment_summary(
    profile: dict,
    all_profiles: List[dict],
    api_key: str,
    model: str = "claude-opus-4-6",
    max_tokens: int = 2500,
    label_info: Optional[dict] = None,
    dq_context: Optional[str] = None,
    priority_context: Optional[str] = None,
) -> dict:
    """
    Generate a rich, 7-section summary for ONE cluster profile.
    Returns a dict with keys from RICH_SECTIONS.
    """
    profile_block = _profile_to_prompt_block(profile)

    universe_lines = []
    for col in ["avg_VPO", "avg_TOTAL_REVENUE", "avg_AVG_SKU", "avg_ACTIVE_MONTHS"]:
        vals = [p[col] for p in all_profiles if col in p]
        if vals:
            universe_lines.append(f"- Universe avg {col.replace('avg_', '')}: {np.mean(vals):,.1f}")
    universe_block = "\n".join(universe_lines) or "Not available"

    all_cluster_lines = []
    for p in all_profiles:
        row = f"Cluster {p['cluster_id']}: {p['outlet_count']:,} outlets"
        if "avg_VPO" in p:
            row += f", avg VPO ₹{p['avg_VPO']:,.0f}"
        all_cluster_lines.append(row)
    all_clusters_block = "\n".join(all_cluster_lines)

    channel = (label_info or {}).get("channel", "GT")
    occasion = (label_info or {}).get("occasion", "Immediate/GrabGo")
    cluster_name = (label_info or {}).get("label", f"Cluster {profile['cluster_id']}")

    context_block = ""
    if dq_context:
        context_block += f"\nDATA QUALITY CONTEXT:\n{dq_context}\n"
    if priority_context:
        context_block += f"\nPRIORITY DISTRIBUTION CONTEXT:\n{priority_context}\n"

    prompt = f"""You are generating a cluster summary for an internal Perfect Store segmentation report.

CLUSTER DATA:
{profile_block}
Pre-classified Channel: {channel}
Pre-classified Occasion: {occasion}
Cluster Name: {cluster_name}

UNIVERSE AVERAGES:
{universe_block}

ALL CLUSTERS (for comparative snapshot):
{all_clusters_block}{context_block}

{'=' * 60}
TASK: Produce ALL 7 sections below. Follow the exact format. Use Indian CPG trade language
(GT, MT, kirana, AfH, VPO, SEC, Rs. price points, festival seasons). Be data-grounded — cite
feature values. Verify all 8 quality checks: channel assigned, occasion mapped, SEC stated,
all 8 dimensions scored, ≥3 Hero SKUs named, 6-8 actions, all 8 levers covered, data-grounded.
{'=' * 60}

IDENTITY CARD:
CLUSTER {profile['cluster_id']} — {cluster_name}
Primary Channel   : {channel}
Primary Occasion  : {occasion}
Outlet Count      : {profile['outlet_count']:,} stores ({profile['pct_of_total']}% of universe)
Avg Monthly VPO   : ₹{profile.get('avg_VPO', 0):,.0f}
Growth Potential  : (High / Medium / Low — your assessment)
SEC Profile       : (dominant SEC band)

SHOPPER PROFILE:
(3-5 sentences: who shops here — age, SEC, life-stage; what and why they buy; when; how. Use India archetypes: kirana loyalty, festival stocking, office-goer, etc.)

DEMOGRAPHIC CATCHMENT:
(3-5 sentences: dominant SEC band and income sensitivity; urbanicity/tier; POI mix; seasonal/event demand; neighbourhood archetype e.g. "college corridor", "suburban residential", "highway dhaba cluster")

STORE CHARACTERISTICS:
(3-5 sentences: store type, size, VPO tier, SKU depth vs universe, chiller presence, execution quality)

DIMENSIONS RADAR:
Provide the 8-dimension scoring table then the radar chart spec:

| Dimension | Score (1-5) | Rationale |
|---|---|---|
| Beverage Category Depth | X | (reason) |
| Immediate Consumption Mix | X | (reason) |
| Seasonal Demand Spike | X | (reason) |
| Premium Mix | X | (reason) |
| Low Price-Pack Dependency | X | (reason) |
| Footfall Intensity | X | (reason) |
| Loyalty / Repeat Purchase | X | (reason) |
| Execution Quality | X | (reason) |

[RADAR CHART]
Scores: [list of 8 scores in dimension order above]
Cluster colour: (pick from #004B87 #009CDE #E4002B #FFB81C #41B6E6 #6CC24A #FF6900 #7B2D8B based on cluster id {profile['cluster_id']})
Universe avg overlay: grey dashed

COMPARATIVE SNAPSHOT:
(Markdown table comparing all clusters on 5 metrics: Count, Avg VPO, IC Mix, Premium Mix, Growth Potential. Bold THIS cluster's row.)

COMMERCIAL ACTION PLAN:
(6-8 actions in this format:

ACTION 1: [LEVER TYPE]
Initiative : ...
Objective  : ...
Hero SKUs  : (≥3 specific SKUs)
Channel    : ...
Timeline   : Immediate (0-4 wks) / Short (1-3 mo) / Medium (3-6 mo)
KPI        : ...

Cover all 8 levers across the 6-8 actions: Portfolio, Merch & Space, Hero SKU Distribution, Picture of Success, Pricing & Promo, Occasion Activation, Demographic Targeting, Channel Partnership)
"""
    text = call_llm(prompt, api_key, model, max_tokens=max_tokens,
                    system_prompt=_ctx.build("segmentation"))
    return _parse_rich_summary(text)


def _parse_rich_summary(text: str) -> dict:
    """
    Parse the LLM's 7-section response into a dict.
    Lenient: tolerates bold/markdown markers and missing colons.
    """
    sections = _empty_rich_summary()
    # Ordered longest-first so "COMMERCIAL ACTION PLAN" matches before "COMMERCIAL"
    markers = [
        ("COMMERCIAL ACTION PLAN", "commercial_action_plan"),
        ("COMMERCIAL ACTION", "commercial_action_plan"),
        ("COMMERCIAL NEXT STEPS", "commercial_action_plan"),
        ("COMMERCIAL", "commercial_action_plan"),
        ("IDENTITY CARD", "identity_card"),
        ("IDENTITY", "identity_card"),
        ("SHOPPER PROFILE", "shopper_profile"),
        ("SHOPPER", "shopper_profile"),
        ("DEMOGRAPHIC CATCHMENT", "demographic_catchment"),
        ("DEMOGRAPHIC", "demographic_catchment"),
        ("DEMOGRAPHICS", "demographic_catchment"),
        ("STORE CHARACTERISTICS", "store_characteristics"),
        ("CHARACTERISTICS", "store_characteristics"),
        ("DIMENSIONS RADAR", "dimensions_radar"),
        ("DIMENSIONS", "dimensions_radar"),
        ("COMPARATIVE SNAPSHOT", "comparative_snapshot"),
        ("COMPARATIVE", "comparative_snapshot"),
    ]

    current = None
    buffer: list = []

    def _flush():
        nonlocal buffer
        if current is not None and buffer:
            sections[current] = "\n".join(buffer).strip()
        buffer = []

    for raw in text.strip().split("\n"):
        line = raw.strip().lstrip("*# ").rstrip("*").strip()
        # Strip "Section N: " or "N. " prefixes the LLM sometimes adds
        line = re.sub(r'^(?:section\s+\d+\s*[:.]\s*|\d+\s*[.]\s*)', '', line,
                      flags=re.IGNORECASE).strip()
        if not line:
            if current is not None:
                buffer.append("")
            continue
        upper = line.upper()
        matched_key = None
        remainder = ""
        for marker, key in markers:
            if upper.startswith(marker):
                matched_key = key
                if ":" in line:
                    remainder = line.split(":", 1)[1].strip()
                break
        if matched_key:
            _flush()
            current = matched_key
            if remainder:
                buffer.append(remainder)
        elif current is not None:
            buffer.append(line)
    _flush()
    return sections


def generate_rich_segment_summaries(
    profiles: List[dict],
    api_key: str,
    model: str = "claude-opus-4-6",
    labels: Optional[dict] = None,
    dq_context: Optional[str] = None,
    priority_context: Optional[str] = None,
) -> dict:
    """
    One rich 7-section summary per cluster. Returns {cluster_id: {sections...}}.

    Calls are parallelised but submissions are staggered to avoid bursting the
    LLM provider's per-minute token quota (a common cause of 429 errors when
    all 6 prompts fire simultaneously).

    Tuneable via env vars:
      SEGMENT_SUMMARY_MAX_WORKERS  — concurrent threads (default: 3)
      SEGMENT_SUMMARY_STAGGER_SECS — seconds between each submission (default: 5)

    Failures per cluster degrade gracefully to an empty summary.
    """
    import time as _time

    max_workers  = int(os.getenv("SEGMENT_SUMMARY_MAX_WORKERS", "3"))
    stagger_secs = float(os.getenv("SEGMENT_SUMMARY_STAGGER_SECS", "5"))
    max_workers  = min(max_workers, len(profiles))

    results: dict = {}

    def _gen_one(p: dict):
        cid = p["cluster_id"]
        label_info = (labels or {}).get(cid, {})
        logger.info(f"Generating rich summary for Cluster {cid}...")
        summary = generate_segment_summary(
            p, profiles, api_key, model,
            label_info=label_info,
            dq_context=dq_context,
            priority_context=priority_context,
        )
        return cid, summary

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, p in enumerate(profiles):
            if i > 0 and stagger_secs > 0:
                _time.sleep(stagger_secs)   # spread token usage over time
            future = executor.submit(_gen_one, p)
            futures[future] = p["cluster_id"]

        for future in as_completed(futures):
            cid = futures[future]
            try:
                cid_result, summary = future.result()
                results[cid_result] = summary
            except Exception as e:
                logger.warning(
                    f"Rich summary for cluster {cid} failed "
                    f"({type(e).__name__}: {e}) — using empty placeholder"
                )
                results[cid] = _empty_rich_summary()

    return results


# ── Main entry point ─────────────────────────────────────────────────────────

def run_segmentation(df: pd.DataFrame, config: dict, api_key: str,
                     model: str = "claude-opus-4-6",
                     dq_context: Optional[str] = None,
                     priority_context: Optional[str] = None,
                     ) -> Tuple[pd.DataFrame, dict]:
    """
    Full segmentation for flat outlet-level data.
    Returns (df_with_cluster_labels, segment_labels_dict).
    """
    seg_cfg = config.get("segmentation", {})
    n_clusters = seg_cfg.get("n_clusters", 6)
    random_state = seg_cfg.get("random_state", 42)

    # Step 1: Feature engineering
    logger.info("Engineering features...")
    df, feature_cols = engineer_features(df, config)

    # Step 2: KMeans clustering
    logger.info(f"Running KMeans with {n_clusters} clusters on {len(df):,} outlets...")
    df, model_obj = run_kmeans(df, feature_cols, n_clusters, random_state)

    # Step 3: Build cluster profiles
    logger.info("Building cluster profiles...")
    profiles = build_cluster_profiles(df, feature_cols, config)

    # Step 4: LLM labeling + rich multi-dimensional summaries
    fallback_labels = {
        i: {"label": f"Segment {i}", "description": "Auto-generated",
            "action": "Review manually", **_empty_rich_summary()}
        for i in range(n_clusters)
    }

    # LLM is usable if Anthropic key is set OR local/vertex backend is configured
    llm_backend = os.getenv("LLM_BACKEND", "anthropic").strip().lower()
    use_llm = bool(api_key) or llm_backend in ("local", "gemini", "vertex", "azure")

    if use_llm:
        logger.info("Requesting LLM segment labels...")
        try:
            labels = label_segments_with_claude(
                profiles, api_key, model,
                dq_context=dq_context,
                priority_context=priority_context,
            )
        except Exception as e:
            logger.warning(
                f"LLM segment labeling failed ({type(e).__name__}: {e}) — "
                f"using auto-generated labels"
            )
            labels = {cid: {k: v for k, v in info.items()
                            if k in ("label", "description", "action")}
                      for cid, info in fallback_labels.items()}

        logger.info("Requesting LLM rich per-segment summaries (parallel)...")
        rich = generate_rich_segment_summaries(
            profiles, api_key, model, labels=labels,
            dq_context=dq_context, priority_context=priority_context,
        )
    else:
        logger.warning(
            "LLM not configured (no API key and LLM_BACKEND!=local) — "
            "skipping segment labeling and rich summaries"
        )
        labels = {cid: {"label": info["label"],
                        "description": info["description"],
                        "action": info["action"]}
                  for cid, info in fallback_labels.items()}
        rich = {cid: _empty_rich_summary() for cid in range(n_clusters)}

    # Merge rich summaries into the labels dict so downstream writers
    # (PDF, Excel) can read shopper/demographics/etc. per cluster.
    for cid, sections in rich.items():
        if cid not in labels:
            labels[cid] = {}
        labels[cid].update(sections)

    # Attach labels to DataFrame (short fields only — avoid CSV bloat from
    # repeating the rich prose on every row; it lives in the labels dict
    # and is rendered in the PDF/Excel).
    df["segment_label"] = df["cluster"].map(
        lambda c: labels.get(c, {}).get("label", f"Segment {c}"))
    df["segment_description"] = df["cluster"].map(
        lambda c: labels.get(c, {}).get("description", ""))
    df["segment_action"] = df["cluster"].map(
        lambda c: labels.get(c, {}).get("action", ""))

    return df, labels
