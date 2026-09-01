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


# ── Cluster Diagnosis extras (differentiators, stability, anomaly flags) ─────
# These are deterministic — no LLM calls — and feed the Interpretation and
# Challenge stages with concrete evidence instead of free-text impressions.

def _add_top_differentiators(profiles: List[dict], n: int = 8) -> List[dict]:
    """
    Rank each cluster's numeric features by deviation from the outlet-count-
    weighted universe average, attaching the top N as `top_differentiators`.
    Lets the Interpretation stage cite concrete evidence ("why this segment
    exists") instead of prose alone, and gives the Challenge stage something
    concrete to check a label against.
    """
    scalar_keys = list(dict.fromkeys(
        k for p in profiles for k in p
        if k.startswith("avg_") and isinstance(p[k], (int, float))
    ))
    demo_keys = list(dict.fromkeys(
        k for p in profiles for k in p.get("avg_demographics", {})
    ))

    def _weighted_avg(key: str, getter) -> Optional[float]:
        vals_weights = [(getter(p), p["outlet_count"]) for p in profiles
                        if getter(p) is not None]
        total_w = sum(w for _, w in vals_weights)
        if not total_w:
            return None
        return sum(v * w for v, w in vals_weights) / total_w

    universe_avg = {}
    for k in scalar_keys:
        universe_avg[k] = _weighted_avg(k, lambda p, k=k: p.get(k))
    for k in demo_keys:
        universe_avg[k] = _weighted_avg(
            k, lambda p, k=k: p.get("avg_demographics", {}).get(k))

    for p in profiles:
        deviations = []
        for k in scalar_keys:
            uavg = universe_avg.get(k)
            if k in p and uavg:
                dev_pct = (p[k] - uavg) / abs(uavg)
                deviations.append({
                    "feature": k.replace("avg_", ""),
                    "cluster_value": p[k],
                    "universe_avg": round(uavg, 2),
                    "pct_deviation": round(dev_pct * 100, 1),
                })
        for k in demo_keys:
            v = p.get("avg_demographics", {}).get(k)
            uavg = universe_avg.get(k)
            if v is not None and uavg:
                dev_pct = (v - uavg) / abs(uavg)
                deviations.append({
                    "feature": k,
                    "cluster_value": v,
                    "universe_avg": round(uavg, 2),
                    "pct_deviation": round(dev_pct * 100, 1),
                })
        deviations.sort(key=lambda d: abs(d["pct_deviation"]), reverse=True)
        p["top_differentiators"] = deviations[:n]

    return profiles


def compute_cluster_diagnostics(df: pd.DataFrame, feature_cols: list,
                                model_obj, config: dict,
                                sample_size: int = 10_000) -> dict:
    """
    Deterministic Cluster-Diagnosis extras beyond raw stats: nearest-neighbour
    cluster (from fitted centroids), a sampled silhouette score per cluster,
    and a size-anomaly flag. No LLM calls.

    Silhouette/stability figures are computed on a random sample (default
    10k rows) rather than the full dataset — silhouette is O(n^2) and this
    pipeline routinely sees 900k-row files. The sample is refit through
    build_feature_matrix independently, so its scaling is a close but not
    bit-identical approximation of the production fit — acceptable for a
    diagnostic signal, not used for the cluster assignments themselves.
    """
    seg_cfg = config.get("segmentation", {})
    n_clusters = seg_cfg.get("n_clusters", 6)
    diag_cfg = seg_cfg.get("diagnostics", {})
    tiny_pct = diag_cfg.get("tiny_cluster_pct", 2.0)
    dominant_pct = diag_cfg.get("dominant_cluster_pct", 60.0)
    random_state = seg_cfg.get("random_state", 42)

    # Nearest-cluster centroid distance — cheap, uses the already-fitted model.
    nearest = {}
    centers = getattr(model_obj, "cluster_centers_", None)
    if centers is not None and len(centers) > 1:
        from scipy.spatial.distance import cdist
        dist = cdist(centers, centers)
        np.fill_diagonal(dist, np.inf)
        for cid in range(len(centers)):
            nn = int(np.argmin(dist[cid]))
            nearest[cid] = {
                "nearest_cluster_id": nn,
                "nearest_cluster_distance": round(float(dist[cid][nn]), 3),
            }

    # Sampled silhouette score per cluster.
    silhouette_by_cluster = {}
    try:
        from sklearn.metrics import silhouette_samples
        n = len(df)
        sample_n = min(sample_size, n)
        rng = np.random.RandomState(random_state)
        idx = rng.choice(n, size=sample_n, replace=False) if n > sample_n else np.arange(n)
        sample_df = df.iloc[idx]
        X_sample, _, _ = build_feature_matrix(sample_df, feature_cols)
        sample_labels = sample_df["cluster"].values
        if len(set(sample_labels)) > 1:
            scores = silhouette_samples(X_sample, sample_labels)
            for cid in range(n_clusters):
                mask = sample_labels == cid
                if mask.any():
                    silhouette_by_cluster[cid] = round(float(scores[mask].mean()), 3)
    except Exception as e:
        logger.warning(f"Silhouette diagnostics skipped ({type(e).__name__}: {e})")

    results = {}
    for cid in sorted(df["cluster"].unique()):
        pct = (df["cluster"] == cid).mean() * 100
        anomaly = None
        if pct < tiny_pct:
            anomaly = "tiny"
        elif pct > dominant_pct:
            anomaly = "dominant"
        results[cid] = {
            **nearest.get(cid, {}),
            "silhouette_avg": silhouette_by_cluster.get(cid),
            "size_anomaly_flag": anomaly,
        }
    return results


# ── Context Enrichment (deterministic taxonomy + POI/GTM packaging) ─────────

CHANNEL_TAXONOMY = ["GT", "MT", "AfH", "EC"]
OCCASION_TAXONOMY = [
    "Immediate/GrabGo", "FutureConsumption/StockUp", "MealAccompaniment",
    "Celebratory", "OnTheMove", "Youth", "Premium", "Morning",
]


def build_cluster_context_pack(profile: dict) -> dict:
    """
    Context Agent: structures the channel/occasion taxonomy plus the
    POI/demographic rollups already present in the profile into an explicit
    block for the Interpretation stage — instead of those facts being
    scattered loosely across ad-hoc prompt text.
    """
    poi_keys = [
        "distance_to_nearest_school_in_km", "distance_to_nearest_large_office_in_km",
        "distance_to_nearest_malls", "distance_to_nearest_train_stn_in_km",
        "no_of_schools_in_a_1_km_radius",
    ]
    demo = profile.get("avg_demographics", {})
    poi_summary = {k: demo[k] for k in poi_keys if k in demo}
    sec_summary = {k: v for k, v in demo.items() if k.startswith("sec_")}

    dominant_geo = {}
    for key in ("top_DB State", "top_Top City", "top_sector",
                "top_channel", "top_store_format"):
        if key in profile:
            dominant_geo[key.replace("top_", "")] = profile[key]

    return {
        "channel_taxonomy": CHANNEL_TAXONOMY,
        "occasion_taxonomy": OCCASION_TAXONOMY,
        "poi_summary": poi_summary,
        "sec_summary": sec_summary,
        "dominant_geography": dominant_geo,
    }


def _context_pack_to_prompt_block(pack: dict) -> str:
    lines = []
    if pack.get("dominant_geography"):
        lines.append(f"- Dominant geography: {pack['dominant_geography']}")
    if pack.get("poi_summary"):
        lines.append(f"- POI proximity (avg km / count): {pack['poi_summary']}")
    if pack.get("sec_summary"):
        lines.append(f"- SEC household mix: {pack['sec_summary']}")
    return "\n".join(lines)


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

        # Context Enrichment pack — channel/occasion taxonomy, POI/GTM rollup
        context_pack = build_cluster_context_pack(p)
        pack_block = _context_pack_to_prompt_block(context_pack)
        if pack_block:
            profiles_text += pack_block + "\n"

        # Cluster Diagnosis extras — evidence for "why this segment exists"
        if p.get("top_differentiators"):
            top3 = p["top_differentiators"][:3]
            profiles_text += "- Top differentiators vs. universe: " + "; ".join(
                f"{d['feature']} {d['pct_deviation']:+.0f}% vs avg" for d in top3
            ) + "\n"
        if p.get("size_anomaly_flag"):
            profiles_text += f"- Size anomaly: {p['size_anomaly_flag']} cluster\n"
        if p.get("silhouette_avg") is not None:
            profiles_text += f"- Cluster separation (silhouette): {p['silhouette_avg']}\n"

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
6. A **confidence** rating (High/Medium/Low) — how well-separated and commercially distinct this cluster actually is, based on its top differentiators, size anomaly flag, and silhouette score above. Be honest — a tiny or poorly-separated cluster should not get High confidence.
7. A **why_this_segment_exists** sentence — must cite at least one concrete top differentiator or POI/demographic fact from the data above, not a generic restatement of the label.

Use Indian CPG trade terminology: GT, MT, kirana, AfH, VPO, SEC, FMCG, Rs. price points.

Return ONLY a valid JSON array — no prose, no markdown fences. Each element must follow this exact schema:
[
  {{
    "cluster_id": <int>,
    "label": "<6-10 word label>",
    "channel": "<GT|MT|AfH|EC>",
    "occasion": "<occasion name>",
    "description": "<2-3 sentences>",
    "action": "<recommended action>",
    "confidence": "<High|Medium|Low>",
    "why_this_segment_exists": "<one evidence-citing sentence>"
  }}
]
"""

    text = call_llm(prompt, api_key, model, max_tokens=3000,
                    system_prompt=_ctx.build("segmentation"),
                    response_schema=_build_cluster_label_schema())
    logger.info("Segment labels received from LLM.")
    labels = _parse_json_labels(text, len(profiles))
    if labels is None:
        logger.warning("JSON label parsing failed — falling back to text parser")
        labels = _parse_segment_labels(text, len(profiles))
    return labels


def _build_cluster_label_schema():
    """
    Gemini/Vertex structured-output schema for cluster labels. Returns None
    if google-genai isn't installed (e.g. anthropic-only environments) so
    callers fall back to plain prompt-instructed JSON — no behaviour change
    on backends where structured output isn't available.
    """
    try:
        from google.genai import types as genai_types
    except ImportError:
        return None
    return genai_types.Schema(
        type=genai_types.Type.ARRAY,
        items=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "cluster_id":  genai_types.Schema(type=genai_types.Type.INTEGER),
                "label":       genai_types.Schema(type=genai_types.Type.STRING),
                "channel":     genai_types.Schema(type=genai_types.Type.STRING,
                                                  enum=CHANNEL_TAXONOMY),
                "occasion":    genai_types.Schema(type=genai_types.Type.STRING),
                "description": genai_types.Schema(type=genai_types.Type.STRING),
                "action":      genai_types.Schema(type=genai_types.Type.STRING),
                "confidence":  genai_types.Schema(type=genai_types.Type.STRING,
                                                  enum=["High", "Medium", "Low"]),
                "why_this_segment_exists": genai_types.Schema(type=genai_types.Type.STRING),
            },
            required=["cluster_id", "label", "channel", "occasion", "description",
                      "action", "confidence", "why_this_segment_exists"],
        ),
    )


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
                "confidence":  item.get("confidence", "Medium"),
                "why_this_segment_exists": item.get("why_this_segment_exists", ""),
            }
        # Ensure every cluster has an entry
        for i in range(n_clusters):
            if i not in labels:
                labels[i] = {
                    "label": f"Segment {i}", "channel": "GT",
                    "occasion": "Immediate/GrabGo",
                    "description": "Cluster profile pending review.",
                    "action": "Review cluster details manually.",
                    "confidence": "Low",
                    "why_this_segment_exists": "",
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
                labels[cid] = {"label": "", "channel": "", "occasion": "", "description": "",
                               "action": "", "confidence": "Medium", "why_this_segment_exists": ""}
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
            elif upper.startswith("CONFIDENCE:"):
                labels[current_cluster]["confidence"] = line_stripped.split(":", 1)[1].strip()
            elif upper.startswith("WHY_THIS_SEGMENT_EXISTS:") or upper.startswith("WHY THIS SEGMENT EXISTS:"):
                labels[current_cluster]["why_this_segment_exists"] = line_stripped.split(":", 1)[1].strip()

    for i in range(n_clusters):
        if i not in labels:
            labels[i] = {
                "label": f"Segment {i}",
                "channel": "GT",
                "occasion": "Immediate/GrabGo",
                "description": "Cluster profile pending review.",
                "action": "Review cluster details manually.",
                "confidence": "Low",
                "why_this_segment_exists": "",
            }
    return labels


# ── Challenge & Validation Agent ─────────────────────────────────────────────
# Deterministic stability + priority-overlap checks, plus an LLM plausibility
# critique of each proposed label. Produces a soft governance signal
# (`validation_flags`) that output_agent renders as a review banner — it never
# blocks the pipeline.

def run_stability_check(df: pd.DataFrame, feature_cols: list, config: dict,
                        n_runs: int = 5, sample_size: int = 20_000) -> dict:
    """
    Re-clusters a sample of the data with different random seeds and measures
    how consistently each production cluster's members get reassigned
    together (aligned via Hungarian max-overlap matching, not raw label ids,
    since KMeans cluster ids are arbitrary across refits).

    Returns {cluster_id: {"stability_score": float 0-1 or None, "stable": bool or None}}.
    Deterministic — no LLM calls. Runs on a sample (default 20k rows) since
    this pipeline sees files up to ~900k rows and re-clustering repeatedly at
    full scale would be far too slow for a diagnostic check.
    """
    from sklearn.metrics import adjusted_rand_score
    from scipy.optimize import linear_sum_assignment

    seg_cfg = config.get("segmentation", {})
    n_clusters = seg_cfg.get("n_clusters", 6)
    base_seed = seg_cfg.get("random_state", 42)
    threshold = seg_cfg.get("diagnostics", {}).get("stability_threshold", 0.6)

    n = len(df)
    sample_n = min(sample_size, n)
    rng = np.random.RandomState(base_seed)
    sample_idx = rng.choice(n, size=sample_n, replace=False) if n > sample_n else np.arange(n)

    sample_df = df.iloc[sample_idx]
    try:
        X_sample, _, _ = build_feature_matrix(sample_df, feature_cols)
    except Exception as e:
        logger.warning(f"Stability check skipped — feature matrix build failed ({e})")
        return {cid: {"stability_score": None, "stable": None}
                for cid in sorted(df["cluster"].unique())}

    orig_labels = sample_df["cluster"].values
    match_counts = np.zeros(sample_n, dtype=float)
    ari_scores = []

    for run in range(n_runs):
        seed = base_seed + 1000 + run
        model = KMeans(n_clusters=n_clusters, random_state=seed, n_init=5, max_iter=200)
        run_labels = model.fit_predict(X_sample)
        ari_scores.append(adjusted_rand_score(orig_labels, run_labels))

        # Align run_labels to orig_labels via max-overlap (Hungarian on -overlap)
        cost = np.zeros((n_clusters, n_clusters))
        for i in range(n_clusters):
            in_i = orig_labels == i
            for j in range(n_clusters):
                cost[i, j] = -np.sum(in_i & (run_labels == j))
        row_ind, col_ind = linear_sum_assignment(cost)
        mapping = {j: i for i, j in zip(row_ind, col_ind)}
        aligned = np.array([mapping.get(l, -1) for l in run_labels])
        match_counts += (aligned == orig_labels).astype(float)

    per_point_stability = match_counts / n_runs

    results = {}
    for cid in range(n_clusters):
        mask = orig_labels == cid
        if not mask.any():
            results[cid] = {"stability_score": None, "stable": None}
            continue
        score = float(per_point_stability[mask].mean())
        results[cid] = {"stability_score": round(score, 3), "stable": score >= threshold}

    logger.info(f"Stability check ({n_runs} bootstrap runs, sample={sample_n:,}): "
                f"mean ARI={np.mean(ari_scores):.3f}")
    return results


def check_priority_overlap(df: pd.DataFrame, threshold: float = 0.9) -> dict:
    """
    Flags a cluster if it's dominated by a single priority tier — a sign the
    segment may just be re-deriving the priority bucket rather than adding
    new commercial insight. Deterministic — no LLM call.
    """
    cluster_ids = sorted(df["cluster"].unique())
    priority_col = "priority" if "priority" in df.columns else (
        "priority_bucket" if "priority_bucket" in df.columns else None)
    if priority_col is None:
        return {cid: {"dominant_priority": None, "dominant_priority_share": None,
                      "priority_overlap_flag": False} for cid in cluster_ids}

    results = {}
    for cid in cluster_ids:
        subset = df.loc[df["cluster"] == cid, priority_col].dropna()
        if len(subset) == 0:
            results[cid] = {"dominant_priority": None, "dominant_priority_share": None,
                            "priority_overlap_flag": False}
            continue
        vc = subset.value_counts(normalize=True)
        top_share = float(vc.iloc[0])
        results[cid] = {
            "dominant_priority": vc.index[0],
            "dominant_priority_share": round(top_share, 3),
            "priority_overlap_flag": top_share >= threshold,
        }
    return results


def critique_label_plausibility(profile: dict, label_info: dict, api_key: str,
                                model: str = "claude-opus-4-6") -> dict:
    """
    Challenge Agent plausibility critique: one LLM call where the model checks
    its own proposed label against the cluster's actual stats and flags
    mismatches (e.g. a "Premium" label on a below-universe-VPO cluster).
    Instructed not to be agreeable by default.
    """
    profile_block = _profile_to_prompt_block(profile)
    prompt = f"""You proposed this label for a retail outlet segment. Check it against the data
and flag any mismatch — do not be agreeable by default; a real mismatch should lower confidence.

PROPOSED LABEL: {label_info.get('label', '')}
CHANNEL: {label_info.get('channel', '')}
OCCASION: {label_info.get('occasion', '')}
DESCRIPTION: {label_info.get('description', '')}
STATED CONFIDENCE: {label_info.get('confidence', 'Medium')}
STATED RATIONALE: {label_info.get('why_this_segment_exists', '')}

CLUSTER DATA:
{profile_block}
TOP DIFFERENTIATORS: {profile.get('top_differentiators', [])}
SIZE ANOMALY: {profile.get('size_anomaly_flag')}

Return ONLY a JSON object, no prose, no markdown fences:
{{
  "plausible": true|false,
  "issue": "<one sentence describing the mismatch, or empty string if none>",
  "revised_confidence": "High"|"Medium"|"Low"
}}
"""
    try:
        text = call_llm(prompt, api_key, model, max_tokens=400,
                        system_prompt=_ctx.build("segmentation"))
        clean = re.sub(r'^```[a-zA-Z]*\s*', '', text.strip())
        clean = re.sub(r'\s*```$', '', clean.rstrip())
        data = json.loads(clean)
        return {
            "plausible": bool(data.get("plausible", True)),
            "issue": str(data.get("issue", "") or ""),
            "revised_confidence": data.get("revised_confidence", label_info.get("confidence", "Medium")),
        }
    except Exception as e:
        logger.warning(f"Plausibility critique failed for cluster "
                       f"{profile.get('cluster_id')}: {type(e).__name__}: {e}")
        return {"plausible": True, "issue": "",
                "revised_confidence": label_info.get("confidence", "Medium")}


def _empty_validation_flags() -> dict:
    return {
        "stability_score": None, "stable": None,
        "dominant_priority": None, "dominant_priority_share": None,
        "priority_overlap_flag": False,
        "plausible": True, "plausibility_issue": "",
        "revised_confidence": None,
        "weak_or_non_actionable": False, "weak_reasons": [],
    }


def run_challenge_validation(
    df: pd.DataFrame, feature_cols: list, config: dict,
    profiles: List[dict], labels: dict,
    api_key: str, model: str = "claude-opus-4-6",
    use_llm: bool = True,
) -> dict:
    """
    Runs all three Challenge Agent checks and combines them into one
    `validation_flags` dict per cluster. Deterministic checks (stability,
    priority overlap) always run; the LLM plausibility critique runs when
    use_llm is True. Never raises — any failure degrades to an "unvalidated"
    flag set rather than blocking the pipeline (soft-gate governance model).
    """
    profile_by_id = {p["cluster_id"]: p for p in profiles}

    try:
        stability = run_stability_check(df, feature_cols, config)
    except Exception as e:
        logger.warning(f"Stability check failed ({type(e).__name__}: {e}) — skipping")
        stability = {cid: {"stability_score": None, "stable": None} for cid in profile_by_id}

    try:
        priority_overlap = check_priority_overlap(df)
    except Exception as e:
        logger.warning(f"Priority overlap check failed ({type(e).__name__}: {e}) — skipping")
        priority_overlap = {cid: {"dominant_priority": None, "dominant_priority_share": None,
                                   "priority_overlap_flag": False} for cid in profile_by_id}

    plausibility = {}
    if use_llm:
        max_workers = min(int(os.getenv("SEGMENT_SUMMARY_MAX_WORKERS", "3")), len(profile_by_id))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(critique_label_plausibility, profile_by_id[cid],
                                labels.get(cid, {}), api_key, model): cid
                for cid in profile_by_id
            }
            for future in as_completed(futures):
                cid = futures[future]
                try:
                    plausibility[cid] = future.result()
                except Exception as e:
                    logger.warning(f"Plausibility critique task failed for cluster {cid}: {e}")
                    plausibility[cid] = {"plausible": True, "issue": "",
                                         "revised_confidence": labels.get(cid, {}).get("confidence", "Medium")}
    else:
        plausibility = {cid: {"plausible": True, "issue": "",
                              "revised_confidence": labels.get(cid, {}).get("confidence", "Medium")}
                        for cid in profile_by_id}

    flags = {}
    for cid in sorted(df["cluster"].unique()):
        stab = stability.get(cid, {})
        prio = priority_overlap.get(cid, {})
        plaus = plausibility.get(cid, {})

        weak_reasons = []
        if stab.get("stable") is False:
            weak_reasons.append(f"low cluster stability ({stab.get('stability_score')})")
        if prio.get("priority_overlap_flag"):
            share = prio.get("dominant_priority_share") or 0
            weak_reasons.append(
                f"{share:.0%} single priority tier ({prio.get('dominant_priority')})")
        if plaus.get("plausible") is False:
            weak_reasons.append(plaus.get("issue") or "label plausibility issue")

        flags[cid] = {
            "stability_score": stab.get("stability_score"),
            "stable": stab.get("stable"),
            "dominant_priority": prio.get("dominant_priority"),
            "dominant_priority_share": prio.get("dominant_priority_share"),
            "priority_overlap_flag": prio.get("priority_overlap_flag", False),
            "plausible": plaus.get("plausible", True),
            "plausibility_issue": plaus.get("issue", ""),
            "revised_confidence": plaus.get("revised_confidence"),
            "weak_or_non_actionable": bool(weak_reasons),
            "weak_reasons": weak_reasons,
        }
    return flags


# ── Activation hook — execution hypothesis ───────────────────────────────────
# A lightweight stand-in for a dedicated Activation Agent: converts the
# label + action into one testable, KPI-bearing hypothesis. MSL and Space
# Allocation consume the segment label/action directly (see msl_generator.py,
# space_allocation_agent.py); no outcome data exists yet to make this
# adaptive, so it stays a deterministic template for now (see run-history log
# in pipeline.py for where that feedback loop would attach later).

def build_execution_hypothesis(label_info: dict, profile: dict) -> str:
    action = (label_info.get("action") or "").strip()
    if not action:
        return "Insufficient action data to form a hypothesis — review manually."
    diffs = profile.get("top_differentiators") or []
    basis = f"driven by {diffs[0]['feature']} ({diffs[0]['pct_deviation']:+.0f}% vs. universe)" \
        if diffs else "based on the segment profile"
    return (
        f"If we execute '{action}' across this segment ({basis}), "
        f"expect measurable VPO/NSV uplift within one quarter vs. control stores."
    )


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
    # Default stagger is 0 — ThreadPoolExecutor max_workers already caps
    # concurrency, so pre-submission sleeping only wastes wall time.
    # Set SEGMENT_SUMMARY_STAGGER_SECS > 0 to re-enable if rate-limit errors appear.
    stagger_secs = float(os.getenv("SEGMENT_SUMMARY_STAGGER_SECS", "0"))
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
            future = executor.submit(_gen_one, p)   # submit first — task starts immediately
            futures[future] = p["cluster_id"]
            if i < len(profiles) - 1 and stagger_secs > 0:
                _time.sleep(stagger_secs)   # post-submit stagger for rate-limit safety

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


# ── Concise segment cards (for the PPTX deck) ────────────────────────────────

CARD_KEYS = ["headline", "shopper_snapshot", "mission", "growth_potential",
             "dominant_sec", "actions", "hero_skus"]


def _clip_words(text: str, n: int) -> str:
    words = str(text or "").split()
    return " ".join(words[:n]) + ("…" if len(words) > n else "")


def _empty_card(label_info: Optional[dict] = None) -> dict:
    li = label_info or {}
    return {
        "headline": li.get("label", ""),
        "shopper_snapshot": _clip_words(li.get("description", ""), 32),
        "mission": li.get("occasion", ""),
        "growth_potential": "Medium",
        "dominant_sec": "",
        "actions": ([{"lever": "Execution",
                      "text": _clip_words(li.get("action", "Review priorities"), 16),
                      "kpi": ""}]),
        "hero_skus": [],
    }


def _coerce_card(raw: dict, label_info: Optional[dict]) -> dict:
    """Enforce the schema + hard length caps on one LLM card object."""
    base = _empty_card(label_info)
    if not isinstance(raw, dict):
        return base
    out = dict(base)
    out["headline"] = _clip_words(raw.get("headline") or base["headline"], 12)
    out["shopper_snapshot"] = _clip_words(
        raw.get("shopper_snapshot") or base["shopper_snapshot"], 34)
    out["mission"] = _clip_words(raw.get("mission") or base["mission"], 6)
    gp = str(raw.get("growth_potential") or "").strip().capitalize()
    out["growth_potential"] = gp if gp in ("High", "Medium", "Low") else base["growth_potential"]
    out["dominant_sec"] = str(raw.get("dominant_sec") or "").strip()[:6]
    acts = []
    for a in (raw.get("actions") or [])[:3]:
        if isinstance(a, dict):
            acts.append({
                "lever": _clip_words(a.get("lever", ""), 4),
                "text": _clip_words(a.get("text", ""), 16),
                "kpi": _clip_words(a.get("kpi", ""), 6),
            })
        elif isinstance(a, str):
            acts.append({"lever": "", "text": _clip_words(a, 16), "kpi": ""})
    out["actions"] = acts or base["actions"]
    skus = [str(s).strip() for s in (raw.get("hero_skus") or []) if str(s).strip()]
    out["hero_skus"] = skus[:5]
    return out


def _parse_cards(text: str, cluster_ids: List[int],
                 labels: Optional[dict]) -> dict:
    """Parse the LLM's JSON array into {cluster_id: card}. Tolerant of fences."""
    labels = labels or {}
    clean = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(),
                   flags=re.MULTILINE).strip()
    parsed = None
    try:
        parsed = json.loads(clean)
    except Exception:
        m = re.search(r"\[.*\]", clean, flags=re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None

    by_id = {}
    if isinstance(parsed, list):
        for i, item in enumerate(parsed):
            cid = item.get("cluster_id", cluster_ids[i]) if isinstance(item, dict) else cluster_ids[i]
            try:
                cid = int(cid)
            except (TypeError, ValueError):
                cid = cluster_ids[i] if i < len(cluster_ids) else i
            by_id[cid] = item

    out = {}
    for cid in cluster_ids:
        out[cid] = _coerce_card(by_id.get(cid, {}), labels.get(cid, {}))
    return out


def generate_concise_segment_cards(
    profiles: List[dict],
    api_key: str,
    model: str = "claude-opus-4-6",
    labels: Optional[dict] = None,
    dq_context: Optional[str] = None,
    priority_context: Optional[str] = None,
) -> dict:
    """One LLM call → a crisp, slide-ready card per cluster (strict JSON)."""
    labels = labels or {}
    cluster_ids = [p["cluster_id"] for p in profiles]

    profile_block = "\n\n".join(
        f"CLUSTER {p['cluster_id']} "
        f"(pre-label: {labels.get(p['cluster_id'], {}).get('label', '—')}, "
        f"channel: {labels.get(p['cluster_id'], {}).get('channel', '—')}, "
        f"occasion: {labels.get(p['cluster_id'], {}).get('occasion', '—')})\n"
        + _profile_to_prompt_block(p)
        for p in profiles
    )
    universe_lines = []
    for col in ["avg_VPO", "avg_TOTAL_REVENUE", "avg_AVG_SKU", "avg_ACTIVE_MONTHS"]:
        vals = [p[col] for p in profiles if col in p]
        if vals:
            universe_lines.append(f"- Universe avg {col.replace('avg_', '')}: {np.mean(vals):,.1f}")
    universe_block = "\n".join(universe_lines) or "Not available"

    context_block = ""
    if dq_context:
        context_block += f"\nDATA QUALITY CONTEXT:\n{dq_context}\n"
    if priority_context:
        context_block += f"\nPRIORITY DISTRIBUTION CONTEXT:\n{priority_context}\n"

    prompt = f"""Return ONLY a JSON array — one object per cluster, in ascending cluster_id order.
No prose, no markdown, no code fence. Each object exactly:

{{
  "cluster_id": <int>,
  "headline": "<=12 words — the segment's commercial essence>",
  "shopper_snapshot": "<=32 words — who shops here and why they buy>",
  "mission": "<=6 words — primary shopper mission>",
  "growth_potential": "High" | "Medium" | "Low",
  "dominant_sec": "<single letter A-E, or e.g. 'B/C'>",
  "actions": [
    {{"lever": "<1-3 words, e.g. Merch & Space>", "text": "<=16 words, imperative>", "kpi": "<=6 words>"}},
    {{...}}, {{...}}
  ],
  "hero_skus": ["<specific SKU>", "<specific SKU>", "<specific SKU>"]
}}

Rules: exactly 3 actions; 3-5 hero_skus; Indian CPG trade language
(GT/MT/kirana/AfH, VPO, SEC, Rs. price points); every claim grounded in the
cluster data below; be terse — this goes straight onto a slide.

CLUSTERS:
{profile_block}

UNIVERSE AVERAGES:
{universe_block}
{context_block}"""

    text = call_llm(prompt, api_key, model, max_tokens=3200,
                    system_prompt=_ctx.build("segmentation"))
    return _parse_cards(text, cluster_ids, labels)


# ── Main entry point ─────────────────────────────────────────────────────────

def run_segmentation(df: pd.DataFrame, config: dict, api_key: str,
                     model: str = "claude-opus-4-6",
                     dq_context: Optional[str] = None,
                     priority_context: Optional[str] = None,
                     run_id: Optional[str] = None,
                     ) -> Tuple[pd.DataFrame, dict]:
    """
    Full segmentation for flat outlet-level data.
    Returns (df_with_cluster_labels, segment_labels_dict).

    labels[cid] additionally carries (soft-governance framework):
      confidence, why_this_segment_exists  — Interpretation stage (Meaning & Labels)
      validation                           — Challenge & Validation stage flags
      execution_hypothesis                 — Activation stage hook
    """
    seg_cfg = config.get("segmentation", {})
    n_clusters = seg_cfg.get("n_clusters", 6)
    random_state = seg_cfg.get("random_state", 42)

    if run_id:
        logger.info(f"[run_id={run_id}] Starting segmentation")

    # Step 1: Feature engineering
    logger.info("Engineering features...")
    df, feature_cols = engineer_features(df, config)

    # Step 2: KMeans clustering (deterministic core — stays in control)
    logger.info(f"Running KMeans with {n_clusters} clusters on {len(df):,} outlets...")
    df, model_obj = run_kmeans(df, feature_cols, n_clusters, random_state)

    # Step 3: Build cluster profiles + Cluster-Diagnosis extras
    # (differentiators, nearest-cluster/silhouette, size-anomaly flags — all
    # deterministic, no LLM calls)
    logger.info("Building cluster profiles...")
    profiles = build_cluster_profiles(df, feature_cols, config)
    profiles = _add_top_differentiators(profiles)
    try:
        diagnostics = compute_cluster_diagnostics(df, feature_cols, model_obj, config)
        for p in profiles:
            p.update(diagnostics.get(p["cluster_id"], {}))
    except Exception as e:
        logger.warning(f"Cluster diagnostics skipped ({type(e).__name__}: {e})")

    # Step 4: LLM labeling (Context Enrichment + Meaning & Labels) + rich summaries
    fallback_labels = {
        i: {"label": f"Segment {i}", "description": "Auto-generated",
            "action": "Review manually", "confidence": "Low",
            "why_this_segment_exists": "", **_empty_rich_summary()}
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
                            if k in ("label", "description", "action",
                                    "confidence", "why_this_segment_exists")}
                      for cid, info in fallback_labels.items()}

        logger.info("Requesting concise per-segment cards (single call)...")
        try:
            cards = generate_concise_segment_cards(
                profiles, api_key, model, labels=labels,
                dq_context=dq_context, priority_context=priority_context,
            )
        except Exception as e:
            logger.warning(
                f"Concise card generation failed ({type(e).__name__}: {e}) — "
                f"deriving cards from segment labels"
            )
            cards = {p["cluster_id"]: _empty_card(labels.get(p["cluster_id"], {}))
                     for p in profiles}

        # Step 5: Challenge & Validation — deterministic stability/priority-overlap
        # checks + an LLM plausibility critique. Soft gate: flags are attached to
        # `labels` for output_agent to render as a review banner; never blocks.
        logger.info("Running Challenge & Validation checks...")
        try:
            validation_flags = run_challenge_validation(
                df, feature_cols, config, profiles, labels,
                api_key, model, use_llm=True,
            )
        except Exception as e:
            logger.warning(
                f"Challenge & Validation failed ({type(e).__name__}: {e}) — "
                f"segments left unvalidated"
            )
            validation_flags = {p["cluster_id"]: _empty_validation_flags() for p in profiles}

        for cid, flags in validation_flags.items():
            if cid not in labels:
                continue
            labels[cid]["validation"] = flags
            # A plausibility critique can downgrade (never silently upgrade) confidence.
            revised = flags.get("revised_confidence")
            if revised and revised != labels[cid].get("confidence"):
                logger.info(
                    f"Cluster {cid}: confidence revised "
                    f"{labels[cid].get('confidence')} → {revised} by plausibility critique"
                )
                labels[cid]["confidence"] = revised

        # Step 6: Activation hook — one execution hypothesis per segment
        profile_by_id = {p["cluster_id"]: p for p in profiles}
        for cid, info in labels.items():
            if cid in profile_by_id:
                info["execution_hypothesis"] = build_execution_hypothesis(info, profile_by_id[cid])
    else:
        logger.warning(
            "LLM not configured (no API key and LLM_BACKEND!=local) — "
            "skipping segment labeling, cards, and Challenge & Validation"
        )
        labels = {cid: {"label": info["label"],
                        "description": info["description"],
                        "action": info["action"],
                        "confidence": info["confidence"],
                        "why_this_segment_exists": info["why_this_segment_exists"],
                        "validation": _empty_validation_flags()}
                  for cid, info in fallback_labels.items()}
        cards = {cid: _empty_card(labels.get(cid, {})) for cid in range(n_clusters)}

    # Attach the concise card to each label so the PPTX / Excel writers can use it.
    for cid, card in cards.items():
        if cid not in labels:
            labels[cid] = {}
        labels[cid]["card"] = card

    # Attach labels to DataFrame (short fields only — avoid CSV bloat from
    # repeating the rich prose on every row; it lives in the labels dict
    # and is rendered in the PDF/Excel).
    df["segment_label"] = df["cluster"].map(
        lambda c: labels.get(c, {}).get("label", f"Segment {c}"))
    df["segment_description"] = df["cluster"].map(
        lambda c: labels.get(c, {}).get("description", ""))
    df["segment_action"] = df["cluster"].map(
        lambda c: labels.get(c, {}).get("action", ""))
    df["segment_confidence"] = df["cluster"].map(
        lambda c: labels.get(c, {}).get("confidence", ""))
    df["segment_review_flag"] = df["cluster"].map(
        lambda c: bool(labels.get(c, {}).get("validation", {}).get("weak_or_non_actionable")))

    return df, labels
