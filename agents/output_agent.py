"""
Output Agent — generates deliverables:
  1. Labelled segment CSVs (one per segment + combined)
  2. Excel workbook with a chart per segment
  3. PDF narrative using Claude's summary
All outputs go to outputs/.
"""

import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image as RLImage
)
from reportlab.lib import colors

logger = logging.getLogger("perfect_store.output")

# Cluster colour palette (one per cluster index 0–7)
_CLUSTER_COLOURS = [
    "#004B87", "#009CDE", "#E4002B", "#FFB81C",
    "#41B6E6", "#6CC24A", "#FF6900", "#7B2D8B"
]

_RADAR_DIMENSIONS = [
    "Beverage\nDepth", "IC Mix", "Seasonal\nSpike",
    "Premium\nMix", "Low Price-\nPack", "Footfall",
    "Loyalty", "Execution"
]


def _charts_dir(output_dir: str) -> str:
    d = os.path.join(output_dir, "charts")
    os.makedirs(d, exist_ok=True)
    return d


def _parse_radar_scores(dimensions_radar_text: str) -> list:
    """Extract 8 numeric scores from the [RADAR CHART] Scores: [...] line."""
    import re
    m = re.search(r"Scores\s*:\s*\[([^\]]+)\]", dimensions_radar_text or "")
    if not m:
        return [3] * 8
    try:
        scores = [float(x.strip()) for x in m.group(1).split(",")]
        return (scores + [3] * 8)[:8]
    except ValueError:
        return [3] * 8


def plot_radar_chart(cluster_id: int, cluster_name: str,
                     scores: list, universe_avg: list,
                     output_dir: str) -> str:
    """Render a radar/spider chart and save as PNG. Returns file path."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed — skipping radar chart")
        return ""

    colour = _CLUSTER_COLOURS[cluster_id % len(_CLUSTER_COLOURS)]
    N = len(_RADAR_DIMENSIONS)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    scores_plot = list(scores) + [scores[0]]
    avg_plot = list(universe_avg) + [universe_avg[0]]
    angles_plot = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
    ax.plot(angles_plot, scores_plot, color=colour, linewidth=2, label=cluster_name)
    ax.fill(angles_plot, scores_plot, color=colour, alpha=0.25)
    ax.plot(angles_plot, avg_plot, color="#888888", linewidth=1.5,
            linestyle="--", label="Universe Avg")
    ax.set_xticks(angles)
    ax.set_xticklabels(_RADAR_DIMENSIONS, size=8)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.yaxis.set_tick_params(labelsize=7)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=8)
    ax.set_title(cluster_name, size=11, fontweight="bold", pad=18)
    fig.tight_layout()

    path = os.path.join(_charts_dir(output_dir), f"radar_cluster_{cluster_id}.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_cluster_bar_chart(cluster_names: list, vpo_values: list,
                           outlet_counts: list, output_dir: str) -> str:
    """Grouped bar chart: VPO (left axis) + outlet count (right axis) by cluster."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ""

    x = np.arange(len(cluster_names))
    width = 0.35
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()
    ax1.bar(x - width / 2, vpo_values, width, color="#004B87", label="Avg VPO (₹)")
    ax2.bar(x + width / 2, outlet_counts, width, color="#009CDE", label="Outlet Count")
    ax1.set_xlabel("Cluster")
    ax1.set_ylabel("Avg Monthly VPO (₹)", color="#004B87")
    ax2.set_ylabel("Outlet Count", color="#009CDE")
    ax1.set_xticks(x)
    ax1.set_xticklabels(cluster_names, rotation=30, ha="right", fontsize=9)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
    fig.tight_layout()

    path = os.path.join(_charts_dir(output_dir), "cluster_bar_overview.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_value_potential_bubble(cluster_names: list, vpo_values: list,
                                 outlet_counts: list, output_dir: str) -> str:
    """Bubble chart: VPO (y) vs cluster index (x), sized by outlet count."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ""

    n = len(cluster_names)
    colours = [_CLUSTER_COLOURS[i % len(_CLUSTER_COLOURS)] for i in range(n)]
    growth_proxy = np.arange(n)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(growth_proxy, vpo_values,
               s=[max(c * 0.3, 30) for c in outlet_counts],
               c=colours, alpha=0.75, edgecolors="white", linewidth=1.5)
    for i, name in enumerate(cluster_names):
        ax.annotate(name, (growth_proxy[i], vpo_values[i]),
                    textcoords="offset points", xytext=(8, 4), fontsize=8)
    mean_vpo = np.mean(vpo_values)
    ax.axhline(y=mean_vpo, color="grey", linestyle="--", alpha=0.5, label=f"Avg VPO ₹{mean_vpo:,.0f}")
    ax.set_xlabel("Cluster")
    ax.set_xticks(growth_proxy)
    ax.set_xticklabels(cluster_names, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Avg Monthly VPO (₹)")
    ax.set_title("Cluster Value × Outlet Count Matrix")
    ax.legend(fontsize=8)
    fig.tight_layout()

    path = os.path.join(_charts_dir(output_dir), "value_potential_bubble.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_feature_heatmap(cluster_names: list, feature_names: list,
                         feature_matrix: np.ndarray, output_dir: str) -> str:
    """Z-scored feature heatmap (clusters × features)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        return ""

    fig_h = max(4, len(cluster_names) * 0.7 + 2)
    fig, ax = plt.subplots(figsize=(min(20, len(feature_names) * 1.1 + 2), fig_h))
    sns.heatmap(feature_matrix, annot=False,
                xticklabels=feature_names, yticklabels=cluster_names,
                cmap="RdBu_r", center=0, ax=ax, linewidths=0.4,
                cbar_kws={"shrink": 0.8})
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right", fontsize=7)
    ax.set_yticklabels(ax.get_yticklabels(), fontsize=9)
    ax.set_title("Cluster Feature Index Heatmap (z-scored)")
    fig.tight_layout()

    path = os.path.join(_charts_dir(output_dir), "feature_heatmap.png")
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── CSV outputs ──────────────────────────────────────────────────────────────

def write_segment_csvs(df: pd.DataFrame, labels: dict, output_dir: str) -> list:
    """Write one CSV per segment plus a combined file."""
    ts = _timestamp()
    os.makedirs(output_dir, exist_ok=True)
    files = []

    # Combined
    combined_path = os.path.join(output_dir, f"all_segments_{ts}.csv")
    df.to_csv(combined_path, index=False)
    files.append(combined_path)
    logger.info(f"Wrote combined CSV: {combined_path}")

    # Per-segment
    for cid in sorted(df["cluster"].unique()):
        label = labels.get(cid, {}).get("label", f"Segment_{cid}")
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in label)[:50]
        seg_path = os.path.join(output_dir, f"segment_{cid}_{safe_name}_{ts}.csv")
        df[df["cluster"] == cid].to_csv(seg_path, index=False)
        files.append(seg_path)

    logger.info(f"Wrote {len(df['cluster'].unique())} segment CSVs")
    return files


# ── Excel workbook with charts ──────────────────────────────────────────────

def write_excel_workbook(df: pd.DataFrame, labels: dict, output_dir: str) -> str:
    """Create an Excel workbook with summary + chart per segment."""
    ts = _timestamp()
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"segment_report_{ts}.xlsx")

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({
            "bold": True, "bg_color": "#004B87", "font_color": "#FFFFFF",
            "border": 1, "text_wrap": True
        })
        rupee_fmt = workbook.add_format({"num_format": "₹#,##0"})

        # ── Summary sheet ────────────────────────────────────────────────
        summary_data = []
        for cid in sorted(df["cluster"].unique()):
            subset = df[df["cluster"] == cid]
            label_info = labels.get(cid, {})
            row = {
                "Cluster": cid,
                "Label": label_info.get("label", f"Segment {cid}"),
                "Outlet Count": len(subset),
                "% of Total": round(len(subset) / len(df) * 100, 1),
            }
            for col, alias in [("VPO", "Avg Monthly Rev (VPO)"),
                                ("TOTAL_REVENUE", "Avg Total Revenue"),
                                ("AVG_SKU", "Avg SKU Count"),
                                ("ACTIVE_MONTHS", "Avg Active Months")]:
                if col in subset.columns:
                    row[alias] = round(subset[col].mean(), 1)
            row["Recommended Action"] = label_info.get("action", "")
            summary_data.append(row)

        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        summary_ws = writer.sheets["Summary"]
        for col_num, col_name in enumerate(summary_df.columns):
            summary_ws.write(0, col_num, col_name, header_fmt)
            summary_ws.set_column(col_num, col_num, max(15, len(col_name) + 4))

        # ── VPO bar chart ─────────────────────────────────────────────────
        n_rows = len(summary_data)
        chart = workbook.add_chart({"type": "column"})
        chart.add_series({
            "name": "Avg Monthly Revenue (VPO) by Segment",
            "categories": ["Summary", 1, 1, n_rows, 1],  # Label
            "values": ["Summary", 1, 4, n_rows, 4],       # Avg Monthly Rev
            "fill": {"color": "#004B87"},
        })
        chart.set_title({"name": "Avg Monthly Revenue (VPO) per Segment"})
        chart.set_x_axis({"name": "Segment"})
        chart.set_y_axis({"name": "Avg VPO (₹)", "num_format": "₹#,##0"})
        chart.set_size({"width": 720, "height": 380})
        summary_ws.insert_chart("A" + str(n_rows + 3), chart)

        # ── Outlet count pie chart ────────────────────────────────────────
        pie = workbook.add_chart({"type": "pie"})
        pie.add_series({
            "name": "Outlet Distribution",
            "categories": ["Summary", 1, 1, n_rows, 1],
            "values": ["Summary", 1, 2, n_rows, 2],
            "data_labels": {"percentage": True, "category": True},
        })
        pie.set_title({"name": "Outlet Count by Segment"})
        pie.set_size({"width": 500, "height": 350})
        summary_ws.insert_chart("A" + str(n_rows + 24), pie)

        # ── Rich Summaries sheet (LLM-generated 7-section, one row per cluster) ─
        rich_cols = [
            ("identity_card", "Identity Card"),
            ("shopper_profile", "Shopper Profile"),
            ("demographic_catchment", "Demographic & Catchment"),
            ("store_characteristics", "Store Characteristics"),
            ("dimensions_radar", "Dimensions & Radar"),
            ("comparative_snapshot", "Comparative Snapshot"),
            ("commercial_action_plan", "Commercial Action Plan"),
        ]
        rich_rows = []
        for cid in sorted(df["cluster"].unique()):
            info = labels.get(cid, {})
            row = {
                "Cluster": cid,
                "Label": info.get("label", f"Segment {cid}"),
                "Channel": info.get("channel", ""),
                "Occasion": info.get("occasion", ""),
            }
            for key, title in rich_cols:
                row[title] = info.get(key, "")
            rich_rows.append(row)

        if rich_rows:
            rich_df = pd.DataFrame(rich_rows)
            rich_df.to_excel(writer, sheet_name="Rich Summaries", index=False)
            rich_ws = writer.sheets["Rich Summaries"]
            wrap_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})
            for col_num, col_name in enumerate(rich_df.columns):
                rich_ws.write(0, col_num, col_name, header_fmt)
                if col_name == "Cluster":
                    width = 10
                elif col_name in ("Label", "Channel", "Occasion"):
                    width = 28
                else:
                    width = 60
                rich_ws.set_column(col_num, col_num, width, wrap_fmt)
            rich_ws.set_default_row(180)

        # ── Cluster Overview chart sheet ──────────────────────────────────
        cnames = [labels.get(cid, {}).get("label", f"Seg {cid}")[:20]
                  for cid in sorted(df["cluster"].unique())]
        vpo_vals, count_vals = [], []
        for cid in sorted(df["cluster"].unique()):
            subset = df[df["cluster"] == cid]
            vpo_vals.append(float(pd.to_numeric(subset.get("VPO", pd.Series(dtype=float)),
                                                errors="coerce").mean() or 0))
            count_vals.append(len(subset))

        bar_path = plot_cluster_bar_chart(cnames, vpo_vals, count_vals, output_dir)
        bubble_path = plot_value_potential_bubble(cnames, vpo_vals, count_vals, output_dir)

        overview_ws = workbook.add_worksheet("Cluster Overview")
        if bar_path and os.path.exists(bar_path):
            overview_ws.insert_image("B2", bar_path, {"x_scale": 0.9, "y_scale": 0.9})
        if bubble_path and os.path.exists(bubble_path):
            overview_ws.insert_image("B32", bubble_path, {"x_scale": 0.9, "y_scale": 0.9})

        # ── Radar charts sheet ────────────────────────────────────────────
        universe_avg_scores = [3.0] * 8
        radar_ws = workbook.add_worksheet("Radar Charts")
        row_offset, col_offset = 1, 1
        for idx, cid in enumerate(sorted(df["cluster"].unique())):
            info = labels.get(cid, {})
            scores = _parse_radar_scores(info.get("dimensions_radar", ""))
            radar_path = plot_radar_chart(
                cid, info.get("label", f"Cluster {cid}")[:25],
                scores, universe_avg_scores, output_dir
            )
            if radar_path and os.path.exists(radar_path):
                r = row_offset + (idx // 3) * 30
                c = col_offset + (idx % 3) * 12
                radar_ws.insert_image(r, c, radar_path, {"x_scale": 0.75, "y_scale": 0.75})

        # ── Feature Heatmap sheet ─────────────────────────────────────────
        numeric_feature_cols = [c for c in df.select_dtypes(include=[np.number]).columns
                                 if c not in ("cluster",) and df[c].notna().mean() > 0.3][:25]
        if numeric_feature_cols and len(df["cluster"].unique()) > 1:
            from sklearn.preprocessing import StandardScaler
            feat_matrix = np.zeros((len(df["cluster"].unique()), len(numeric_feature_cols)))
            for i, cid in enumerate(sorted(df["cluster"].unique())):
                subset = df[df["cluster"] == cid][numeric_feature_cols]
                feat_matrix[i] = pd.to_numeric(
                    subset.stack(), errors="coerce"
                ).unstack().mean().values
            scaler = StandardScaler()
            feat_z = scaler.fit_transform(feat_matrix.T).T
            heatmap_path = plot_feature_heatmap(
                [labels.get(cid, {}).get("label", f"Seg {cid}")[:18]
                 for cid in sorted(df["cluster"].unique())],
                [c[:18] for c in numeric_feature_cols],
                feat_z, output_dir
            )
            heatmap_ws = workbook.add_worksheet("Feature Heatmap")
            if heatmap_path and os.path.exists(heatmap_path):
                heatmap_ws.insert_image("B2", heatmap_path, {"x_scale": 0.85, "y_scale": 0.85})

        # ── Per-segment detail sheets (first 50k rows max per sheet) ─────
        for cid in sorted(df["cluster"].unique()):
            sheet_name = f"Seg {cid}"[:31]
            subset = df[df["cluster"] == cid].copy().head(50_000)
            subset.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            for col_num, col_name in enumerate(subset.columns):
                ws.write(0, col_num, col_name, header_fmt)
                ws.set_column(col_num, col_num, max(12, len(str(col_name)) + 3))

    logger.info(f"Wrote Excel workbook: {path}")
    return path


# ── PDF narrative ────────────────────────────────────────────────────────────

def write_pdf_report(rfm: pd.DataFrame, labels: dict, dq_report: str,
                     output_dir: str, priority_narrative: str = "") -> str:
    """Generate a PDF narrative report with DQ summary and segment insights."""
    ts = _timestamp()
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"perfect_store_report_{ts}.pdf")

    doc = SimpleDocTemplate(path, pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=22, textColor=HexColor("#004B87"),
        spaceAfter=20
    )
    heading_style = ParagraphStyle(
        "CustomHeading", parent=styles["Heading2"],
        fontSize=14, textColor=HexColor("#004B87"),
        spaceBefore=16, spaceAfter=8
    )
    body_style = ParagraphStyle(
        "CustomBody", parent=styles["Normal"],
        fontSize=10, leading=14, spaceAfter=6
    )
    label_style = ParagraphStyle(
        "SegLabel", parent=styles["Heading3"],
        fontSize=12, textColor=HexColor("#E31837"),
        spaceBefore=12, spaceAfter=4
    )

    story = []

    # Title
    story.append(Paragraph("Perfect Store — Segmentation Report", title_style))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}",
        body_style))
    story.append(HRFlowable(width="100%", thickness=2,
                             color=HexColor("#004B87")))
    story.append(Spacer(1, 12))

    # DQ Section
    story.append(Paragraph("Data Quality Assessment", heading_style))
    for line in dq_report.split("\n"):
        line = line.strip()
        if line:
            # Escape XML chars for reportlab
            safe_line = (line.replace("&", "&amp;").replace("<", "&lt;")
                         .replace(">", "&gt;"))
            story.append(Paragraph(safe_line, body_style))
    story.append(Spacer(1, 12))

    # Segmentation overview
    story.append(Paragraph("Segmentation Overview", heading_style))
    n_segments = rfm["cluster"].nunique()
    n_outlets = len(rfm)
    vpo_col = "VPO" if "VPO" in rfm.columns else None
    rev_col = "TOTAL_REVENUE" if "TOTAL_REVENUE" in rfm.columns else None
    total_vpo = rfm[vpo_col].sum() if vpo_col else 0
    overview = (
        f"The analysis identified <b>{n_segments} distinct outlet segments</b> across "
        f"<b>{n_outlets:,} retail outlets</b>"
    )
    if vpo_col:
        overview += f", representing a combined monthly VPO of <b>₹{total_vpo:,.0f}</b>."
    else:
        overview += "."
    story.append(Paragraph(overview, body_style))
    story.append(Spacer(1, 8))

    # Summary table
    cols = ["Segment", "Label", "Outlets", "% Total"]
    if vpo_col:
        cols += ["Avg VPO (₹)", "Avg SKUs"]
    table_data = [cols]
    for cid in sorted(rfm["cluster"].unique()):
        subset = rfm[rfm["cluster"] == cid]
        label_info = labels.get(cid, {})
        row = [
            str(cid),
            label_info.get("label", f"Segment {cid}")[:38],
            f"{len(subset):,}",
            f"{len(subset)/n_outlets*100:.1f}%",
        ]
        if vpo_col:
            row.append(f"₹{subset[vpo_col].mean():,.0f}")
        if "AVG_SKU" in subset.columns:
            row.append(f"{subset['AVG_SKU'].mean():.1f}")
        table_data.append(row)

    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#004B87")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F0F4F8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    # ── Priority Section ──────────────────────────────────────────────────
    if "priority" in rfm.columns:
        story.append(PageBreak())
        story.append(Paragraph("Store Prioritization — A/B/C/D & Upside Tagging", heading_style))

        tier_order = ["A+", "A", "B+", "B", "C+", "C", "D+", "D"]
        tier_desc = {
            "A":  "Top 20% by VPO — performing at potential",
            "A+": "Top 20% by VPO — BELOW 75th-pct potential (highest intervention ROI)",
            "B":  "Next 20% by VPO — performing at potential",
            "B+": "Next 20% by VPO — BELOW 75th-pct potential",
            "C":  "Next 30% by VPO — performing at potential",
            "C+": "Next 30% by VPO — BELOW 75th-pct potential (emerging opportunity)",
            "D":  "Bottom 30% by VPO — performing at potential",
            "D+": "Bottom 30% by VPO — BELOW 75th-pct potential (underserved catchment)",
        }

        # Priority summary table
        priority_table_data = [["Tier", "Description", "Outlets", "% Total",
                                 "Avg Actual VPO", "Avg Potential VPO", "Avg Gap"]]
        for tier in tier_order:
            sub = rfm[rfm["priority"] == tier]
            if len(sub) == 0:
                continue
            priority_table_data.append([
                tier,
                tier_desc.get(tier, ""),
                f"{len(sub):,}",
                f"{len(sub)/n_outlets*100:.1f}%",
                f"₹{sub['VPO'].mean():,.0f}" if "VPO" in sub else "-",
                f"₹{sub['predicted_potential_vpo'].mean():,.0f}" if "predicted_potential_vpo" in sub else "-",
                f"₹{sub['opportunity_gap'].mean():,.0f}" if "opportunity_gap" in sub else "-",
            ])

        p_table = Table(priority_table_data, repeatRows=1,
                        colWidths=[40, 200, 55, 45, 75, 80, 60])
        p_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1A1A2E")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F5F5F5")]),
            ("ALIGN", (2, 1), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            # Highlight "+" rows
            ("BACKGROUND", (0, 1), (-1, 1), HexColor("#D6EAF8")),  # A+
            ("BACKGROUND", (0, 3), (-1, 3), HexColor("#D5F5E3")),  # B+
            ("BACKGROUND", (0, 5), (-1, 5), HexColor("#FEF9E7")),  # C+
            ("BACKGROUND", (0, 7), (-1, 7), HexColor("#FDEDEC")),  # D+
        ]))
        story.append(p_table)
        story.append(Spacer(1, 16))

        # Claude narrative
        if priority_narrative:
            story.append(Paragraph("Strategic Prioritization Narrative", heading_style))
            for line in priority_narrative.split("\n"):
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 4))
                    continue
                safe = (line.replace("&", "&amp;").replace("<", "&lt;")
                        .replace(">", "&gt;"))
                if line.startswith("**") and line.endswith("**"):
                    story.append(Paragraph(f"<b>{safe[2:-2]}</b>", body_style))
                else:
                    story.append(Paragraph(safe, body_style))

    # Segment detail pages
    story.append(PageBreak())
    story.append(Paragraph("Segment Deep Dives", heading_style))

    for cid in sorted(rfm["cluster"].unique()):
        label_info = labels.get(cid, {})
        subset = rfm[rfm["cluster"] == cid]

        story.append(Paragraph(
            f"Segment {cid}: {label_info.get('label', 'Unnamed')}", label_style))
        story.append(Paragraph(label_info.get("description", ""), body_style))

        pct = len(subset) / n_outlets * 100
        details_parts = [f"<b>Outlets:</b> {len(subset):,} ({pct:.1f}% of total)"]
        if "VPO" in subset.columns:
            details_parts.append(f"<b>Avg VPO:</b> ₹{subset['VPO'].mean():,.0f}/month")
        if "TOTAL_REVENUE" in subset.columns:
            details_parts.append(f"<b>Avg Total Rev:</b> ₹{subset['TOTAL_REVENUE'].mean():,.0f}")
        if "AVG_SKU" in subset.columns:
            details_parts.append(f"<b>Avg SKUs:</b> {subset['AVG_SKU'].mean():.1f}")
        if "ACTIVE_MONTHS" in subset.columns:
            details_parts.append(f"<b>Avg Active Months:</b> {subset['ACTIVE_MONTHS'].mean():.1f}")
        story.append(Paragraph(" &nbsp;|&nbsp; ".join(details_parts), body_style))

        if label_info.get("action"):
            story.append(Paragraph(
                f"<b>Recommended Action:</b> {label_info['action']}", body_style))

        # LLM-generated 7-section rich summary
        rich_order = [
            ("identity_card", "Identity Card"),
            ("shopper_profile", "Shopper Profile"),
            ("demographic_catchment", "Demographic & Catchment Profile"),
            ("store_characteristics", "Store Characteristics"),
            ("dimensions_radar", "Sales Behaviour Dimensions"),
            ("comparative_snapshot", "Comparative Cluster Snapshot"),
            ("commercial_action_plan", "Commercial Action Plan"),
        ]

        # Embed radar chart image if available
        radar_img = os.path.join(output_dir, "charts", f"radar_cluster_{cid}.png")
        if os.path.exists(radar_img):
            story.append(RLImage(radar_img, width=3.2*inch, height=3.2*inch))
            story.append(Spacer(1, 6))

        for key, title in rich_order:
            content = (label_info.get(key) or "").strip()
            if not content:
                continue
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>{title}</b>", body_style))
            for raw in content.split("\n"):
                line = raw.strip()
                if not line:
                    continue
                # Skip raw [RADAR CHART] directive blocks — chart already embedded above
                if line.startswith("[RADAR CHART]"):
                    continue
                safe = (line.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;"))
                story.append(Paragraph(safe, body_style))
        story.append(Spacer(1, 10))

    doc.build(story)
    logger.info(f"Wrote PDF report: {path}")
    return path


# ── Main entry point ─────────────────────────────────────────────────────────

def write_priority_excel(df: pd.DataFrame, output_dir: str) -> str:
    """
    Dedicated priority workbook:
      - Summary sheet: count / avg VPO / avg gap per priority tier
      - One sheet per tier (A+, A, B+, B, C+, C, D+, D)
      - Bar charts: VPO actual vs predicted by tier, outlet counts
    """
    ts = _timestamp()
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"priority_report_{ts}.xlsx")

    if "priority" not in df.columns:
        return None

    # Tier order for display
    tier_order = ["A+", "A", "B+", "B", "C+", "C", "D+", "D"]
    tier_colors = {
        "A+": "#004B87", "A": "#0074CC",
        "B+": "#00843D", "B": "#4CAF50",
        "C+": "#E5A000", "C": "#FFC72C",
        "D+": "#C8102E", "D": "#E57373",
    }

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({
            "bold": True, "bg_color": "#1A1A2E", "font_color": "#FFFFFF",
            "border": 1, "text_wrap": True, "align": "center"
        })
        rupee_fmt = workbook.add_format({"num_format": "₹#,##0"})
        pct_fmt   = workbook.add_format({"num_format": "0.0%"})

        # ── Summary sheet ─────────────────────────────────────────────────
        summary_rows = []
        for tier in tier_order:
            sub = df[df["priority"] == tier]
            if len(sub) == 0:
                continue
            summary_rows.append({
                "Priority Tier": tier,
                "Is Upside Store": "Yes" if "+" in tier else "No",
                "Outlet Count": len(sub),
                "% of Total": round(len(sub) / len(df) * 100, 1),
                "Avg Actual VPO (₹)": round(sub["VPO"].mean(), 0) if "VPO" in sub else 0,
                "Avg Predicted Potential (₹)": round(sub["predicted_potential_vpo"].mean(), 0) if "predicted_potential_vpo" in sub else 0,
                "Avg Opportunity Gap (₹)": round(sub["opportunity_gap"].mean(), 0) if "opportunity_gap" in sub else 0,
                "Total Opportunity (₹/month)": round(sub["opportunity_gap"].clip(lower=0).sum(), 0) if "opportunity_gap" in sub else 0,
                "Avg SKUs": round(sub["AVG_SKU"].mean(), 1) if "AVG_SKU" in sub else "",
                "Avg Active Months": round(sub["ACTIVE_MONTHS"].mean(), 1) if "ACTIVE_MONTHS" in sub else "",
            })
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_excel(writer, sheet_name="Priority Summary", index=False)
        ws = writer.sheets["Priority Summary"]
        for ci, col in enumerate(summary_df.columns):
            ws.write(0, ci, col, header_fmt)
            ws.set_column(ci, ci, max(16, len(col) + 4))

        n_tiers = len(summary_rows)

        # Actual vs Predicted VPO grouped bar chart
        chart1 = workbook.add_chart({"type": "column"})
        chart1.add_series({
            "name": "Avg Actual VPO",
            "categories": ["Priority Summary", 1, 0, n_tiers, 0],
            "values":     ["Priority Summary", 1, 4, n_tiers, 4],
            "fill":       {"color": "#004B87"},
            "gap": 80,
        })
        chart1.add_series({
            "name": "Avg Predicted Potential VPO",
            "categories": ["Priority Summary", 1, 0, n_tiers, 0],
            "values":     ["Priority Summary", 1, 5, n_tiers, 5],
            "fill":       {"color": "#E31837"},
        })
        chart1.set_title({"name": "Actual VPO vs Predicted Potential by Priority Tier"})
        chart1.set_x_axis({"name": "Priority Tier"})
        chart1.set_y_axis({"name": "Avg VPO (₹)", "num_format": "₹#,##0"})
        chart1.set_size({"width": 750, "height": 400})
        ws.insert_chart("A" + str(n_tiers + 3), chart1)

        # Opportunity gap bar chart (upside tiers only)
        chart2 = workbook.add_chart({"type": "column"})
        chart2.add_series({
            "name": "Avg Opportunity Gap (₹/month)",
            "categories": ["Priority Summary", 1, 0, n_tiers, 0],
            "values":     ["Priority Summary", 1, 6, n_tiers, 6],
            "fill":       {"color": "#00843D"},
        })
        chart2.set_title({"name": "Avg Opportunity Gap per Tier (₹/month)"})
        chart2.set_x_axis({"name": "Priority Tier"})
        chart2.set_y_axis({"name": "Gap (₹)", "num_format": "₹#,##0"})
        chart2.set_size({"width": 600, "height": 350})
        ws.insert_chart("A" + str(n_tiers + 24), chart2)

        # ── Per-tier detail sheets ─────────────────────────────────────────
        detail_cols = [
            "OUTLET_UID_EDITED", "DB State", "Top City", "COHORT",
            "channel", "store_format", "sector",
            "VPO", "TOTAL_REVENUE", "AVG_SKU", "ACTIVE_MONTHS",
            "priority_bucket", "priority", "vpo_percentile",
            "predicted_potential_vpo", "opportunity_gap",
            "gap_pct_of_potential", "gap_rank_within_bucket",
            "segment_label",
        ]
        available_cols = [c for c in detail_cols if c in df.columns]

        for tier in tier_order:
            sub = df[df["priority"] == tier][available_cols].copy()
            if len(sub) == 0:
                continue
            sub = sub.sort_values("opportunity_gap", ascending=False).reset_index(drop=True)
            sheet_name = f"Tier {tier}"[:31]
            sub.head(50_000).to_excel(writer, sheet_name=sheet_name, index=False)
            tw = writer.sheets[sheet_name]
            # Colour-coded header per tier
            tier_hdr = workbook.add_format({
                "bold": True,
                "bg_color": tier_colors.get(tier, "#333333"),
                "font_color": "#FFFFFF",
                "border": 1, "text_wrap": True
            })
            for ci, col in enumerate(sub.columns):
                tw.write(0, ci, col, tier_hdr)
                tw.set_column(ci, ci, max(14, len(str(col)) + 3))

    logger.info(f"Wrote priority workbook: {path}")
    return path


def generate_outputs(df: pd.DataFrame, labels: dict, dq_report: str,
                     output_dir: str, priority_narrative: str = "") -> dict:
    """Generate all output files. Returns dict of output paths."""
    csv_files = write_segment_csvs(df, labels, output_dir)
    excel_path = write_excel_workbook(df, labels, output_dir)
    priority_excel = write_priority_excel(df, output_dir)
    pdf_path = write_pdf_report(df, labels, dq_report, output_dir,
                                priority_narrative=priority_narrative)

    return {
        "csv_files": csv_files,
        "excel": excel_path,
        "priority_excel": priority_excel,
        "pdf": pdf_path,
    }
