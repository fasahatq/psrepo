"""
Space Allocation Agent — converts segment MSL SKUs into rack-ready facing recommendations.

For each priority bucket (A / B / C / D):
  1. Reads the latest MSL Excel (MSL_Priority_Buckets_*.xlsx from the most recent run)
  2. Joins MSL SKUs with physical pack dimensions (CPG_Pack_Dimensions_cm.xlsx)
  3. Evaluates available rack assets (CPG_Rack_Comparison.xlsx)
  4. Calculates facings required so each SKU holds 7 days of supply
     (once-a-week servicing frequency)
  5. Assigns SKUs to shelves by commercial priority zone
  6. Recommends the optimal number of rack assets per segment
  7. Calls the LLM for a narrative recommendation using space_allocation.md context
  8. Writes a Space_Allocation_<timestamp>.xlsx into the same run folder as the MSL
"""

import os
import re
import glob
import math
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional
from agents.llm_client import call_llm
from agents.context_loader import ContextLoader

logger = logging.getLogger("perfect_store.space_allocation")
_ctx = ContextLoader()

_AGENTS_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_AGENTS_DIR)
OUTPUTS_DIR  = os.path.join(PROJECT_ROOT, "outputs")
INBOX_DIR    = os.path.join(PROJECT_ROOT, "inbox")
RACK_FILE    = os.path.join(INBOX_DIR, "CPG_Rack_Comparison.xlsx")
PACK_FILE    = os.path.join(INBOX_DIR, "CPG_Pack_Dimensions_cm.xlsx")

# ── Service / DoS defaults ────────────────────────────────────────────────────
DOS_TARGET_DAYS           = 7      # once-a-week service → hold 7 days of stock
WEEKLY_UNITS_PER_STORE    = 100    # total category units sold per store per week (proxy)
USABLE_WIDTH_PCT          = 0.95   # fraction of shelf width that is usable
USABLE_HEIGHT_PCT         = 0.95   # fraction of shelf height that is clear (pack vs shelf)
MIN_INNOVATION_PCT        = 0.10   # reserve 10 % of rack for innovation SKUs

# ── Shelf zone maps by shelf count ───────────────────────────────────────────
ZONE_MAP = {
    5: {1: "base", 2: "grab_zone", 3: "eye_level", 4: "eye_level", 5: "upper"},
    4: {1: "base", 2: "grab_zone", 3: "eye_level", 4: "upper"},
    3: {1: "base", 2: "eye_level", 3: "upper"},
    2: {1: "grab_zone", 2: "eye_level"},
}

# ── Brand / PPG normalisation for joining MSL ↔ pack dimensions ──────────────
BRAND_MAP = {
    "lays": "Lay's", "lay's": "Lay's",
    "kurkure": "Kurkure", "uncle chipps": "Uncle Chipps",
    "doritos": "Doritos", "cheetos": "Cheetos",
    "quaker": "Quaker",
}
PPG_NORM = {
    "small": "Small", "medium": "Medium", "large": "Large",
    "extra large": "Extra Large", "insti large": "Large", "insti mids": "Medium",
}


# ══════════════════════════════════════════════════════════════════════════════
# Data loaders
# ══════════════════════════════════════════════════════════════════════════════

def load_rack_specs() -> Dict[str, dict]:
    """
    Parse CPG_Rack_Comparison.xlsx.
    Returns {rack_name: {height_mm, width_mm, depth_mm, n_shelves, ...}}.
    """
    xl = pd.ExcelFile(RACK_FILE)
    raw = xl.parse(xl.sheet_names[0], header=None)

    # Find the row that acts as the column header ("Parameter", "Wire Rack", …)
    hdr_row = None
    for i, row in raw.iterrows():
        vals = [str(v).strip().lower() for v in row if pd.notna(v)]
        if "parameter" in vals:
            hdr_row = i
            break
    if hdr_row is None:
        raise ValueError("Could not locate 'Parameter' header row in rack file")

    raw.columns = [str(v).strip() if pd.notna(v) else f"col_{c}"
                   for c, v in enumerate(raw.iloc[hdr_row])]
    data = raw.iloc[hdr_row + 1:].dropna(how="all").reset_index(drop=True)
    data = data[data[data.columns[0]].notna()]

    param_col = data.columns[0]
    rack_names = [c for c in data.columns[1:] if not c.startswith("col_")]

    def _mm(val_str: str) -> Optional[float]:
        """Extract first numeric mm value from a string like '1,600 mm (63")'."""
        m = re.search(r"([\d,]+(?:\.\d+)?)\s*mm", str(val_str), re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))
        # fallback: first integer
        m = re.search(r"[\d,]+", str(val_str))
        return float(m.group().replace(",", "")) if m else None

    def _shelves(val_str: str) -> int:
        nums = re.findall(r"\d+", str(val_str))
        return int(round(sum(int(n) for n in nums) / len(nums))) if nums else 3

    racks: Dict[str, dict] = {}
    for rack in rack_names:
        spec: dict = {}
        for _, row in data.iterrows():
            param = str(row[param_col]).strip().lower()
            val   = str(row[rack]).strip() if pd.notna(row[rack]) else ""
            if "height" in param:
                v = _mm(val); spec["height_mm"] = v if v else 0
            elif "width" in param:
                v = _mm(val); spec["width_mm"]  = v if v else 0
            elif "depth" in param:
                v = _mm(val); spec["depth_mm"]  = v if v else 0
            elif "shelf" in param or "tier" in param:
                spec["n_shelves"] = _shelves(val)

        spec.setdefault("n_shelves", 5)
        spec["usable_width_mm"]  = spec.get("width_mm",  0) * USABLE_WIDTH_PCT
        # per-shelf clearance height
        n = spec["n_shelves"]
        spec["shelf_height_mm"] = (spec.get("height_mm", 0) / n) * USABLE_HEIGHT_PCT
        racks[rack.strip()] = spec

    logger.info(f"Racks loaded: {list(racks.keys())}")
    return racks


def load_pack_dimensions() -> pd.DataFrame:
    """
    Parse CPG_Pack_Dimensions_cm.xlsx.
    Returns a clean DataFrame with brand_norm, ppg_norm, height/width/depth in cm and mm.
    """
    xl = pd.ExcelFile(PACK_FILE)
    raw = xl.parse(xl.sheet_names[0], header=None)

    # Find the header row — look for "Brand" and "Height" in the same row
    hdr_row = None
    for i, row in raw.iterrows():
        vals_lower = [str(v).lower() for v in row if pd.notna(v)]
        if any("brand" in v for v in vals_lower) and any("height" in v for v in vals_lower):
            hdr_row = i
            break
    if hdr_row is None:
        raise ValueError("Could not locate header row in pack dimensions file")

    # Clean multi-line headers (e.g. "Height\n(cm)") → "Height (cm)"
    raw.columns = [re.sub(r"\s+", " ", str(v)).strip()
                   if pd.notna(v) else f"col_{c}"
                   for c, v in enumerate(raw.iloc[hdr_row])]
    df = raw.iloc[hdr_row + 1:].reset_index(drop=True)

    # Forward-fill brand column
    brand_col  = df.columns[0]
    ppg_col    = df.columns[1]
    df[brand_col] = df[brand_col].ffill()

    # Identify numeric dimension columns
    height_col = next((c for c in df.columns if "Height" in c), None)
    width_col  = next((c for c in df.columns if "Width"  in c), None)
    depth_col  = next((c for c in df.columns if "Depth"  in c or "Gusset" in c), None)

    if not all([height_col, width_col, depth_col]):
        raise ValueError("Could not identify Height/Width/Depth columns in pack file")

    # Keep only rows with numeric height
    df["h"] = pd.to_numeric(df[height_col], errors="coerce")
    df = df.dropna(subset=["h"]).copy()

    df = df.rename(columns={
        brand_col:  "brand",
        ppg_col:    "ppg_raw",
        height_col: "height_cm",
        width_col:  "width_cm",
        depth_col:  "depth_cm",
    })
    for col in ["height_cm", "width_cm", "depth_cm"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Remove note / legend rows
    df = df.dropna(subset=["height_cm", "width_cm", "depth_cm"]).copy()

    # Normalise brand name for joining
    df["brand_norm"] = df["brand"].astype(str).str.strip().str.lower().apply(
        lambda x: BRAND_MAP.get(x, x.title())
    )
    # Normalise PPG label (strip newlines, "(Party Pack)" annotation)
    df["ppg_norm"] = (df["ppg_raw"].astype(str)
                       .str.replace(r"\s+", " ", regex=True)
                       .str.split("(").str[0].str.strip())

    # Convert cm → mm
    for dim in ["height", "width", "depth"]:
        df[f"{dim}_mm"] = df[f"{dim}_cm"] * 10

    keep = ["brand", "brand_norm", "ppg_raw", "ppg_norm",
            "height_cm", "width_cm", "depth_cm",
            "height_mm", "width_mm", "depth_mm"]
    logger.info(f"Pack dimension rows loaded: {len(df)}")
    return df[keep].drop_duplicates(subset=["brand_norm", "ppg_norm"]).reset_index(drop=True)


def find_latest_msl_file() -> str:
    """Auto-detect the most recent MSL_Priority_Buckets_*.xlsx in outputs/."""
    pattern = os.path.join(OUTPUTS_DIR, "**", "MSL_Priority_Buckets_*.xlsx")
    files = glob.glob(pattern, recursive=True)
    if not files:
        raise FileNotFoundError(f"No MSL_Priority_Buckets_*.xlsx found under {OUTPUTS_DIR}")
    return max(files, key=os.path.getmtime)


def load_msl_bucket(xl: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    """
    Parse one bucket sheet from the MSL workbook.
    Returns a clean DataFrame of SKU rows with normalised fields.
    """
    raw = xl.parse(sheet, header=None)

    # Locate the PRODUCT DESCRIPTION header row
    hdr_row = None
    for i, row in raw.iterrows():
        if "PRODUCT DESCRIPTION" in row.astype(str).values:
            hdr_row = i
            break
    if hdr_row is None:
        logger.warning(f"No SKU table found in {sheet}")
        return pd.DataFrame()

    raw.columns = [str(v).strip() if pd.notna(v) else f"col_{c}"
                   for c, v in enumerate(raw.iloc[hdr_row])]
    df = raw.iloc[hdr_row + 1:].reset_index(drop=True)
    df = df[df["PRODUCT DESCRIPTION"].notna()].copy()
    df = df[df["PRODUCT DESCRIPTION"].astype(str).str.strip() != ""].copy()

    # Core fields
    df["PPG"]     = df["PPG"].astype(str).str.strip()
    df["BRAND"]   = df["BRAND"].astype(str).str.strip()
    df["SKU_TYPE"]= df.get("SKU TYPE", pd.Series(dtype=str)).astype(str).str.strip()
    df["CONTRIBUTION"]     = pd.to_numeric(df.get("% MIX OF BUCKET (SHARE)"), errors="coerce").fillna(0)
    df["STORE_SELLING_PCT"]= pd.to_numeric(df.get("% No of Store Selling"),   errors="coerce").fillna(0)
    df["RANKING"]          = pd.to_numeric(df.get("RANKING"), errors="coerce")
    df["INDEX"]            = pd.to_numeric(df.get("INDEX"),   errors="coerce")
    df["SELECTED"]         = df.get("MSL SELECTION", pd.Series(dtype=str)).astype(str).str.strip() == "✓"

    # Join keys
    df["brand_norm"] = df["BRAND"].str.lower().apply(lambda x: BRAND_MAP.get(x, x.title()))
    df["ppg_norm"]   = df["PPG"].str.lower().apply(lambda x: PPG_NORM.get(x, x.title()))

    return df.reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# Facing calculations
# ══════════════════════════════════════════════════════════════════════════════

def calculate_facings(skus: pd.DataFrame, pack_dims: pd.DataFrame,
                      rack: dict, weekly_units_total: float) -> pd.DataFrame:
    """
    Join SKUs with pack dimensions and calculate facing requirements.

    DoS logic (once-a-week service = 7-day target):
        depth_units        = floor(rack_depth / pack_depth)
        vertical_stacks    = floor(shelf_height / pack_height)  [if pack fits]
        capacity_per_facing= depth_units × vertical_stacks
        weekly_units_sku   = weekly_units_total × contribution_pct
        facings_needed     = ceil(weekly_units_sku / capacity_per_facing)
    """
    df = skus.merge(
        pack_dims[["brand_norm", "ppg_norm",
                   "height_cm", "width_cm", "depth_cm",
                   "height_mm", "width_mm", "depth_mm"]],
        on=["brand_norm", "ppg_norm"],
        how="left",
    )

    shelf_h   = rack["shelf_height_mm"]
    rack_d    = rack["depth_mm"]
    rack_uw   = rack["usable_width_mm"]

    rows = []
    for _, r in df.iterrows():
        if pd.isna(r.get("height_mm")):
            rows.append({
                "depth_units": None, "vertical_stacks": None,
                "capacity_per_facing": None,
                "weekly_units_est": None, "facings_needed": None,
                "facing_width_mm": None, "dos_days": None,
                "warning": "Pack dimensions not found — skipped"
            })
            continue

        h, w, d = r["height_mm"], r["width_mm"], r["depth_mm"]

        if h > shelf_h:
            rows.append({
                "depth_units": None, "vertical_stacks": None,
                "capacity_per_facing": None,
                "weekly_units_est": None, "facings_needed": 0,
                "facing_width_mm": 0, "dos_days": None,
                "warning": f"Pack height {h:.0f}mm > shelf height {shelf_h:.0f}mm — does not fit"
            })
            continue

        depth_units     = max(1, math.floor(rack_d / d))
        vertical_stacks = max(1, math.floor(shelf_h / h))
        capacity        = depth_units * vertical_stacks

        weekly_units = weekly_units_total * float(r["CONTRIBUTION"])
        facings      = max(1, math.ceil(weekly_units / capacity)) if capacity > 0 else 1
        facing_w     = facings * w
        dos          = (capacity * facings) / max(weekly_units / DOS_TARGET_DAYS, 0.01)

        warn = ""
        if facing_w > rack_uw:
            warn = f"Facings ({facings}) exceed shelf width — capped"
            facings  = max(1, math.floor(rack_uw / w))
            facing_w = facings * w

        rows.append({
            "depth_units":       int(depth_units),
            "vertical_stacks":   int(vertical_stacks),
            "capacity_per_facing": int(capacity),
            "weekly_units_est":  round(weekly_units, 2),
            "facings_needed":    int(facings),
            "facing_width_mm":   round(facing_w, 1),
            "dos_days":          round(dos, 1),
            "warning":           warn,
        })

    calc = pd.DataFrame(rows, index=df.index)
    return pd.concat([df, calc], axis=1)


# ══════════════════════════════════════════════════════════════════════════════
# Shelf assignment
# ══════════════════════════════════════════════════════════════════════════════

def assign_shelves(df: pd.DataFrame, rack: dict) -> pd.DataFrame:
    """
    Assign each SKU to a shelf number and zone.

    Zone preference:
      Hero SKUs           → eye_level
      Large / XL packs    → base (heavy; bottom shelf)
      Strategic SKUs      → grab_zone
      Innovation / tail   → upper

    Fills shelves left-to-right by width, then spills to next preferred zone.
    """
    n = rack["n_shelves"]
    zone_map = ZONE_MAP.get(n, ZONE_MAP[5])

    shelf_remaining = {s: rack["usable_width_mm"] for s in range(1, n + 1)}

    def _preferred_zones(row) -> list:
        ppg      = str(row.get("ppg_norm", "")).lower()
        sku_type = str(row.get("SKU_TYPE", "")).lower()
        if ppg in ("extra large", "large"):
            base_zone = "base"
        elif sku_type == "hero":
            base_zone = "eye_level"
        elif sku_type == "strategic":
            base_zone = "grab_zone"
        else:
            base_zone = "upper"
        all_zones = ["eye_level", "grab_zone", "base", "upper"]
        return [base_zone] + [z for z in all_zones if z != base_zone]

    # Sort: Hero first by ranking, then Strategic, then rest
    df = df.copy()
    df["_sort"] = df.apply(lambda r: (
        0 if str(r.get("SKU_TYPE", "")).lower() == "hero" else
        1 if str(r.get("SKU_TYPE", "")).lower() == "strategic" else 2
    ), axis=1)
    df = df.sort_values(["_sort", "RANKING"]).reset_index(drop=True)

    shelves_out, zones_out = [], []

    for _, row in df.iterrows():
        facings = row.get("facings_needed")
        if pd.isna(facings) or int(facings) == 0 or str(row.get("warning", "")).startswith("Pack height"):
            shelves_out.append(0)
            zones_out.append("not_placed")
            continue

        w_needed = float(row.get("facing_width_mm", 0))
        placed   = False

        for pref_zone in _preferred_zones(row):
            for shelf_no, zone_label in zone_map.items():
                if zone_label == pref_zone and shelf_remaining[shelf_no] >= w_needed:
                    shelf_remaining[shelf_no] -= w_needed
                    shelves_out.append(shelf_no)
                    zones_out.append(zone_label)
                    placed = True
                    break
            if placed:
                break

        if not placed:
            # No shelf has enough room — mark overflow
            shelves_out.append(0)
            zones_out.append("overflow")

    df["assigned_shelf"] = shelves_out
    df["assigned_zone"]  = zones_out
    return df.drop(columns=["_sort"])


# ══════════════════════════════════════════════════════════════════════════════
# Asset count & coverage
# ══════════════════════════════════════════════════════════════════════════════

def calculate_assets_needed(df: pd.DataFrame, rack: dict) -> dict:
    """
    Estimate number of rack units required for a segment.

    Total space needed = sum of all SKU facing widths.
    Available space per rack = usable_width × n_shelves.
    Assets needed = ceil(total_space / space_per_rack).
    """
    placed   = df[df["assigned_zone"].isin(["eye_level", "grab_zone", "base", "upper"])]
    overflow = df[df["assigned_zone"] == "overflow"]
    no_dims  = df[df["warning"].astype(str).str.contains("not found")]

    total_w_needed   = placed["facing_width_mm"].sum()
    space_per_rack   = rack["usable_width_mm"] * rack["n_shelves"]
    assets_needed    = max(1, math.ceil(total_w_needed / space_per_rack)) if space_per_rack > 0 else 1
    revenue_coverage = float(placed["CONTRIBUTION"].sum()) * 100

    return {
        "assets_needed":          assets_needed,
        "total_width_needed_mm":  round(float(total_w_needed), 1),
        "space_per_rack_mm":      round(float(space_per_rack), 1),
        "revenue_coverage_pct":   round(revenue_coverage, 1),
        "skus_placed":            int(len(placed)),
        "skus_overflow":          int(len(overflow)),
        "skus_no_dims":           int(len(no_dims)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# LLM recommendation
# ══════════════════════════════════════════════════════════════════════════════

def build_llm_prompt(bucket: str, df: pd.DataFrame,
                     rack_name: str, rack: dict, summary: dict) -> str:
    """Build the structured prompt for the LLM space allocation narrative."""

    hero     = df[df["SKU_TYPE"] == "Hero"].sort_values("RANKING").head(8)
    strategic= df[df["SKU_TYPE"] == "Strategic"].sort_values("RANKING").head(8)
    warnings = df[df["warning"].astype(str).str.len() > 0][["PRODUCT DESCRIPTION", "warning"]]

    def _tbl(sub):
        cols = ["PRODUCT DESCRIPTION", "PPG", "facings_needed", "assigned_shelf",
                "assigned_zone", "dos_days"]
        cols = [c for c in cols if c in sub.columns]
        return sub[cols].to_string(index=False) if len(sub) else "None"

    zone_legend = "\n".join(
        f"  Shelf {s} → {z}" for s, z in sorted(
            ZONE_MAP.get(rack["n_shelves"], ZONE_MAP[5]).items()
        )
    )

    return f"""
You are producing the final space allocation recommendation for Priority Bucket {bucket} stores.

## Rack Asset: {rack_name}
- Size          : {rack['height_mm']:.0f} mm H × {rack['width_mm']:.0f} mm W × {rack['depth_mm']:.0f} mm D
- Shelves       : {rack['n_shelves']}  (usable shelf height: {rack['shelf_height_mm']:.0f} mm each)
- Usable width  : {rack['usable_width_mm']:.0f} mm per shelf
{zone_legend}

## Allocation Summary
| Metric | Value |
|--------|-------|
| Assets recommended | {summary['assets_needed']} × {rack_name} |
| Total facing width needed | {summary['total_width_needed_mm']} mm |
| Space per rack (all shelves) | {summary['space_per_rack_mm']} mm |
| Revenue coverage | {summary['revenue_coverage_pct']}% |
| SKUs placed | {summary['skus_placed']} |
| SKUs overflow (need extra asset) | {summary['skus_overflow']} |
| SKUs missing pack dimensions | {summary['skus_no_dims']} |

## Service Frequency Assumption
Weekly servicing: 1 visit per week → Days-of-Supply target = {DOS_TARGET_DAYS} days
Weekly units proxy: {WEEKLY_UNITS_PER_STORE} total units / store / week

## Hero SKU Placements (top 8 by ranking)
{_tbl(hero)}

## Strategic SKU Placements (top 8)
{_tbl(strategic)}

## Warnings / Issues
{warnings.to_string(index=False) if len(warnings) else "None"}

## Your Task
Write a concise, actionable space allocation recommendation covering:
1. **Optimal asset configuration** — confirm asset count and type; explain why
2. **Shelf layout plan** — which shelf holds which brand block / PPG tier and why
   (follow shopper decision hierarchy: mission → price point → pack size → brand → flavour)
3. **Hero SKU eye-level priority** — call out which top Hero SKUs must be at eye-level / grab zone
4. **DoS adequacy** — flag any SKU at risk of stocking out before the next weekly service
5. **Innovation space** — confirm {int(MIN_INNOVATION_PCT*100)}% of facings are reserved for innovation SKUs
6. **Execution guidance** — 3–4 bullet points for the field team setting up the rack
7. **Open issues** — SKUs with missing dimensions or overflow; what to do

Use CPG trade language. Be data-specific. Flag every constraint and assumption clearly.
""".strip()


def get_llm_recommendation(prompt: str, api_key: str, model: str) -> str:
    return call_llm(prompt, api_key, model, max_tokens=1800,
                    system_prompt=_ctx.build("space_allocation"))


# ══════════════════════════════════════════════════════════════════════════════
# Output writer
# ══════════════════════════════════════════════════════════════════════════════

def write_output(results: dict, msl_path: str, output_dir: str) -> str:
    """Write Space_Allocation_<timestamp>.xlsx with one sheet per bucket + Summary."""
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"Space_Allocation_{ts}.xlsx")

    # Column rename for readability
    COL_RENAME = {
        "PRODUCT DESCRIPTION": "Product",
        "PPG": "PPG",
        "BRAND": "Brand",
        "SKU_TYPE": "Type",
        "CONTRIBUTION": "Rev Mix %",
        "STORE_SELLING_PCT": "Store Sell %",
        "RANKING": "Rank",
        "INDEX": "Index",
        "height_cm": "H (cm)",
        "width_cm":  "W (cm)",
        "depth_cm":  "D (cm)",
        "depth_units":        "Depth Units",
        "vertical_stacks":    "V. Stacks",
        "capacity_per_facing":"Cap/Facing",
        "weekly_units_est":   "Wkly Units (est)",
        "facings_needed":     "Facings",
        "facing_width_mm":    "Width (mm)",
        "dos_days":           "DoS (days)",
        "assigned_shelf":     "Shelf",
        "assigned_zone":      "Zone",
        "warning":            "Warnings",
    }
    DISPLAY_COLS = list(COL_RENAME.keys())

    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        wb = writer.book

        hdr_fmt  = wb.add_format({"bold": True, "bg_color": "#1A1A2E",
                                   "font_color": "#FFFFFF", "border": 1, "text_wrap": True})
        meta_fmt = wb.add_format({"italic": True, "font_color": "#555555"})
        hero_fmt = wb.add_format({"bg_color": "#D6EAF8"})
        warn_fmt = wb.add_format({"bg_color": "#FDEDEC", "font_color": "#C0392B"})
        llm_fmt  = wb.add_format({"text_wrap": True, "valign": "top", "font_size": 10,
                                   "bg_color": "#F8F9FA"})
        title_fmt= wb.add_format({"bold": True, "font_size": 13})

        summary_rows = []

        for bucket, res in results.items():
            df        = res["df"]
            rack_name = res["rack_name"]
            rack      = res["rack"]
            asset_sum = res["asset_summary"]
            llm_text  = res["llm_recommendation"]
            sheet     = f"Bucket {bucket}"

            # ── Prepare display DataFrame ────────────────────────────────────
            existing = [c for c in DISPLAY_COLS if c in df.columns]
            out_df   = df[existing].copy()
            out_df["CONTRIBUTION"]      = (out_df["CONTRIBUTION"] * 100).round(2)
            out_df["STORE_SELLING_PCT"] = (out_df["STORE_SELLING_PCT"] * 100).round(1)
            out_df = out_df.rename(columns={k: v for k, v in COL_RENAME.items() if k in out_df.columns})

            DATA_START_ROW = 5  # rows 0-4 = metadata + blank

            out_df.to_excel(writer, sheet_name=sheet, index=False, startrow=DATA_START_ROW)
            ws = writer.sheets[sheet]

            # ── Metadata block ───────────────────────────────────────────────
            ws.write(0, 0, f"Space Allocation — Priority Bucket {bucket}",  title_fmt)
            ws.write(1, 0,
                f"Rack: {rack_name}  |  "
                f"Assets recommended: {asset_sum['assets_needed']}  |  "
                f"Revenue coverage: {asset_sum['revenue_coverage_pct']}%  |  "
                f"DoS target: {DOS_TARGET_DAYS} days (weekly service)",
                meta_fmt)
            ws.write(2, 0, f"MSL source: {os.path.basename(msl_path)}", meta_fmt)

            # ── Column headers ───────────────────────────────────────────────
            for ci, col in enumerate(out_df.columns):
                ws.write(DATA_START_ROW, ci, col, hdr_fmt)
                ws.set_column(ci, ci, max(12, len(col) + 3))

            # ── Row colouring: Hero = blue, warning = red ────────────────────
            for ri, (_, row) in enumerate(out_df.iterrows(), start=DATA_START_ROW + 1):
                type_val = str(row.get("Type", ""))
                warn_val = str(row.get("Warnings", ""))
                fmt = hero_fmt if type_val == "Hero" else (warn_fmt if warn_val else None)
                if fmt:
                    ws.set_row(ri, None, fmt)

            # ── LLM recommendation block ─────────────────────────────────────
            llm_row = DATA_START_ROW + len(out_df) + 2
            ws.write(llm_row, 0, "LLM Space Allocation Recommendation",
                     wb.add_format({"bold": True, "font_size": 12, "bg_color": "#EAF4FB"}))
            ws.set_row(llm_row + 1, 380)
            last_col = max(len(out_df.columns) - 1, 0)
            ws.merge_range(llm_row + 1, 0, llm_row + 1, last_col, llm_text, llm_fmt)
            ws.set_column(0, 0, max(80, ws.dim_colmax + 1))

            summary_rows.append({
                "Bucket":             bucket,
                "Rack Type":          rack_name,
                "Assets Recommended": asset_sum["assets_needed"],
                "SKUs Placed":        asset_sum["skus_placed"],
                "SKUs Overflow":      asset_sum["skus_overflow"],
                "SKUs Missing Dims":  asset_sum["skus_no_dims"],
                "Revenue Coverage %": asset_sum["revenue_coverage_pct"],
                "Total Width Needed (mm)": asset_sum["total_width_needed_mm"],
                "Space Per Rack (mm)":asset_sum["space_per_rack_mm"],
            })

        # ── Summary sheet ────────────────────────────────────────────────────
        sum_df = pd.DataFrame(summary_rows)
        sum_df.to_excel(writer, sheet_name="Summary", index=False)
        ws_sum = writer.sheets["Summary"]
        for ci, col in enumerate(sum_df.columns):
            ws_sum.write(0, ci, col, hdr_fmt)
            ws_sum.set_column(ci, ci, max(18, len(col) + 4))

    logger.info(f"Space allocation output written: {out_path}")
    return out_path


# ══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def run_space_allocation(
    api_key: str,
    model:   str   = "claude-sonnet-4-20250514",
    msl_path: str  = None,
    output_dir: str = None,
    weekly_units_per_store: float = WEEKLY_UNITS_PER_STORE,
) -> str:
    """
    Full space allocation pipeline for all priority buckets.

    Args:
        api_key               : Anthropic API key (or empty for local/Gemini/Vertex)
        model                 : LLM model name
        msl_path              : explicit path to MSL Excel; auto-detected if None
        output_dir            : where to write output; defaults to MSL file's folder
        weekly_units_per_store: total category units sold per store per week (proxy velocity)

    Returns:
        Path to the Space_Allocation_*.xlsx file.
    """
    logger.info("=== Space Allocation Agent starting ===")

    racks     = load_rack_specs()
    pack_dims = load_pack_dimensions()

    msl_path   = msl_path or find_latest_msl_file()
    output_dir = output_dir or os.path.dirname(msl_path)
    logger.info(f"MSL file : {msl_path}")

    xl      = pd.ExcelFile(msl_path)
    buckets = [s for s in xl.sheet_names if s.lower().startswith("bucket")]

    # Pick the primary rack (first = Wire Rack based on file ordering)
    primary_rack_name = list(racks.keys())[0]
    primary_rack      = racks[primary_rack_name]
    logger.info(f"Primary rack : {primary_rack_name}  "
                f"({primary_rack['height_mm']:.0f} H × "
                f"{primary_rack['width_mm']:.0f} W × "
                f"{primary_rack['depth_mm']:.0f} D mm, "
                f"{primary_rack['n_shelves']} shelves)")

    results = {}
    llm_backend = os.getenv("LLM_BACKEND", "anthropic").strip().lower()
    use_llm     = bool(api_key) or llm_backend in ("local", "gemini", "vertex", "azure")

    for sheet in buckets:
        bucket = sheet.replace("Bucket ", "").replace("bucket ", "").strip()
        logger.info(f"\n── Bucket {bucket} ──────────────────────────────────")

        skus = load_msl_bucket(xl, sheet)
        if skus.empty:
            continue

        # Use only MSL-selected SKUs (tick-marked); fall back to all if none selected
        selected = skus[skus["SELECTED"]] if skus["SELECTED"].any() else skus
        logger.info(f"  SKUs to allocate : {len(selected)}")

        df_dims   = calculate_facings(selected, pack_dims, primary_rack, weekly_units_per_store)
        df_placed = assign_shelves(df_dims, primary_rack)
        asset_sum = calculate_assets_needed(df_placed, primary_rack)

        logger.info(f"  Assets needed    : {asset_sum['assets_needed']} × {primary_rack_name}")
        logger.info(f"  Revenue coverage : {asset_sum['revenue_coverage_pct']}%")
        logger.info(f"  Placed / overflow: {asset_sum['skus_placed']} / {asset_sum['skus_overflow']}")

        if use_llm:
            logger.info("  Requesting LLM recommendation...")
            prompt = build_llm_prompt(bucket, df_placed, primary_rack_name, primary_rack, asset_sum)
            try:
                llm_text = get_llm_recommendation(prompt, api_key, model)
            except Exception as exc:
                logger.warning(f"  LLM call failed ({exc}) — using summary fallback")
                llm_text = (
                    f"LLM unavailable. Summary: {asset_sum['assets_needed']} × {primary_rack_name} "
                    f"recommended, {asset_sum['revenue_coverage_pct']}% revenue coverage."
                )
        else:
            llm_text = "LLM not configured. Review allocation table above."

        results[bucket] = {
            "df":                 df_placed,
            "rack_name":          primary_rack_name,
            "rack":               primary_rack,
            "asset_summary":      asset_sum,
            "llm_recommendation": llm_text,
        }

    out_path = write_output(results, msl_path, output_dir)
    logger.info(f"\n=== Space allocation complete → {out_path} ===")
    return out_path


# ── Standalone execution ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model   = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    msl     = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        out = run_space_allocation(api_key=api_key, model=model, msl_path=msl)
        print(f"\nOutput: {out}")
    except Exception as exc:
        logger.error(f"Space allocation failed: {exc}")
        raise
