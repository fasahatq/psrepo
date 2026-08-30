#!/usr/bin/env python3
"""
Generate the Perfect Store Pipeline — Comprehensive Agentic AI Audit PDF.
Run: python3 generate_audit_pdf.py
Output: Perfect_Store_AI_Audit.pdf
"""

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Preformatted
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.colors import HexColor

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY        = HexColor("#1F3864")
BLUE        = HexColor("#2E75B6")
LIGHT_BLUE  = HexColor("#BDD7EE")
ORANGE      = HexColor("#F4B942")
GOLD        = HexColor("#FFD966")
RED         = HexColor("#C00000")
GREEN       = HexColor("#375623")
DARK_GRAY   = HexColor("#404040")
MID_GRAY    = HexColor("#767676")
LIGHT_GRAY  = HexColor("#F2F2F2")
CODE_BG     = HexColor("#1E1E2E")
CODE_FG     = HexColor("#CDD6F4")
WHITE       = colors.white
BLACK       = colors.black

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm

# ── Styles ────────────────────────────────────────────────────────────────────
def build_styles():
    base = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "cover_title": S("cover_title",
            fontName="Helvetica-Bold", fontSize=28,
            textColor=WHITE, alignment=TA_CENTER, spaceAfter=6,
            leading=34),
        "cover_sub": S("cover_sub",
            fontName="Helvetica", fontSize=14,
            textColor=LIGHT_BLUE, alignment=TA_CENTER, spaceAfter=4,
            leading=18),
        "cover_meta": S("cover_meta",
            fontName="Helvetica", fontSize=10,
            textColor=GOLD, alignment=TA_CENTER, spaceAfter=3),

        "h1": S("h1",
            fontName="Helvetica-Bold", fontSize=16,
            textColor=WHITE, backColor=NAVY,
            spaceBefore=14, spaceAfter=6, leading=20,
            leftIndent=0, borderPadding=(6, 8, 6, 8)),
        "h2": S("h2",
            fontName="Helvetica-Bold", fontSize=13,
            textColor=NAVY, spaceBefore=12, spaceAfter=4,
            leading=17, borderPadding=(0, 0, 2, 0)),
        "h3": S("h3",
            fontName="Helvetica-Bold", fontSize=11,
            textColor=BLUE, spaceBefore=8, spaceAfter=3,
            leading=15),
        "h4": S("h4",
            fontName="Helvetica-BoldOblique", fontSize=10,
            textColor=DARK_GRAY, spaceBefore=6, spaceAfter=2,
            leading=14),
        "body": S("body",
            fontName="Helvetica", fontSize=9.5,
            textColor=DARK_GRAY, spaceBefore=3, spaceAfter=3,
            leading=14, alignment=TA_JUSTIFY),
        "bullet": S("bullet",
            fontName="Helvetica", fontSize=9.5,
            textColor=DARK_GRAY, spaceBefore=2, spaceAfter=2,
            leading=13, leftIndent=14, bulletIndent=4),
        "bullet2": S("bullet2",
            fontName="Helvetica", fontSize=9,
            textColor=DARK_GRAY, spaceBefore=1, spaceAfter=1,
            leading=12, leftIndent=28, bulletIndent=18),
        "code": S("code",
            fontName="Courier", fontSize=7.8,
            textColor=CODE_FG, backColor=CODE_BG,
            spaceBefore=4, spaceAfter=4,
            leading=11, leftIndent=4, rightIndent=4,
            borderPadding=(6, 6, 6, 6)),
        "inline_code": S("inline_code",
            fontName="Courier-Bold", fontSize=9,
            textColor=NAVY),
        "label": S("label",
            fontName="Helvetica-Bold", fontSize=8.5,
            textColor=WHITE, backColor=BLUE,
            alignment=TA_CENTER, leading=12,
            borderPadding=(3, 5, 3, 5)),
        "caption": S("caption",
            fontName="Helvetica-Oblique", fontSize=8,
            textColor=MID_GRAY, alignment=TA_CENTER,
            spaceBefore=2, spaceAfter=6),
        "finding_title": S("finding_title",
            fontName="Helvetica-Bold", fontSize=10,
            textColor=NAVY, backColor=LIGHT_BLUE,
            spaceBefore=8, spaceAfter=3, leading=14,
            borderPadding=(4, 6, 4, 6)),
        "exec_bullet": S("exec_bullet",
            fontName="Helvetica", fontSize=10,
            textColor=DARK_GRAY, spaceBefore=4, spaceAfter=4,
            leading=15, leftIndent=16, bulletIndent=4),
        "toc_item": S("toc_item",
            fontName="Helvetica", fontSize=9.5,
            textColor=NAVY, spaceBefore=2, spaceAfter=2, leading=13),
        "roadmap_h": S("roadmap_h",
            fontName="Helvetica-Bold", fontSize=10,
            textColor=WHITE, backColor=BLUE,
            alignment=TA_CENTER, leading=14,
            borderPadding=(4, 4, 4, 4)),
    }


# ── Helper builders ───────────────────────────────────────────────────────────
def hr(color=NAVY, thickness=1, space_before=4, space_after=4):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceAfter=space_after, spaceBefore=space_before)

def sp(h=4):
    return Spacer(1, h * mm)

def h1(text, styles):
    return Paragraph(f"&nbsp;&nbsp;{text}", styles["h1"])

def h2(text, styles):
    return [hr(BLUE, 0.5, 2, 2), Paragraph(text, styles["h2"])]

def h3(text, styles):
    return Paragraph(text, styles["h3"])

def h4(text, styles):
    return Paragraph(text, styles["h4"])

def body(text, styles):
    return Paragraph(text, styles["body"])

def bul(text, styles, level=1):
    s = styles["bullet"] if level == 1 else styles["bullet2"]
    return Paragraph(f"• &nbsp;{text}", s)

def code_block(text, styles):
    return Preformatted(text, styles["code"])

def finding(tag, title, styles):
    return Paragraph(f"Finding {tag}: {title}", styles["finding_title"])

def labeled(text, styles):
    return Paragraph(text, styles["label"])

def table_style_base():
    return [
        ("BACKGROUND",   (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("TEXTCOLOR",    (0, 1), (-1, -1), DARK_GRAY),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -1), 7.5),
        ("GRID",         (0, 0), (-1, -1), 0.4, HexColor("#CCCCCC")),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("WORDWRAP",     (0, 0), (-1, -1), True),
    ]


def make_table(headers, rows, col_widths, highlight_rows=None):
    data = [headers] + rows
    style = table_style_base()
    if highlight_rows:
        for ri in highlight_rows:
            style.append(("BACKGROUND", (0, ri), (-1, ri), LIGHT_BLUE))
            style.append(("FONTNAME",   (0, ri), (-1, ri), "Helvetica-Bold"))
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


# ── Cover page ────────────────────────────────────────────────────────────────
class CoverBackground(Flowable):
    def draw(self):
        c = self.canv
        w, h = PAGE_W, PAGE_H
        c.setFillColor(NAVY)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColor(BLUE)
        c.rect(0, h * 0.38, w, h * 0.30, fill=1, stroke=0)
        c.setFillColor(ORANGE)
        c.rect(0, h * 0.36, w, 3, fill=1, stroke=0)
        c.rect(0, h * 0.68, w, 3, fill=1, stroke=0)
        c.setFillColor(HexColor("#FFFFFF08"))
        for i in range(0, int(w), 40):
            c.rect(i, 0, 1, h, fill=1, stroke=0)

    def wrap(self, *args):
        return (0, 0)


def cover_page(styles):
    elems = [CoverBackground(), Spacer(1, 70 * mm)]
    elems.append(Paragraph("PERFECT STORE PIPELINE", styles["cover_title"]))
    elems.append(Paragraph("Comprehensive Agentic AI Audit", styles["cover_sub"]))
    elems.append(Spacer(1, 8 * mm))
    elems.append(Paragraph("Agentic Architecture · LLM Optimization · Token Efficiency",
                            styles["cover_meta"]))
    elems.append(Paragraph("Caching Strategy · Pipeline Performance · Code Quality",
                            styles["cover_meta"]))
    elems.append(Spacer(1, 10 * mm))
    meta = [
        ["Project", "Perfect Store India CPG Pipeline"],
        ["Backend",  "Vertex AI  ·  Gemini 2.5 Flash"],
        ["Scope",   "17 LLM Calls  ·  7 Agent Files  ·  ~900k Row Datasets"],
        ["Date",    datetime.now().strftime("%B %d, %Y")],
    ]
    mt = Table(meta, colWidths=[35 * mm, 110 * mm])
    mt.setStyle(TableStyle([
        ("TEXTCOLOR",    (0, 0), (-1, -1), WHITE),
        ("FONTNAME",     (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",     (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LINEBELOW",    (0, 0), (-1, -2), 0.3, HexColor("#FFFFFF40")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    elems += [mt, PageBreak()]
    return elems


# ── TOC ───────────────────────────────────────────────────────────────────────
def toc_page(styles):
    elems = [h1("Table of Contents", styles), sp(4)]
    sections = [
        ("Executive Summary", "3"),
        ("1. Agentic AI Architecture Review", "4"),
        ("   1.1  Current Flow: Procedural, Not Agentic", "4"),
        ("   1.2  Proposed Agent + Tools Architecture", "5"),
        ("   1.3  Missing: Observability Hooks", "5"),
        ("2. LLM Call Optimization", "6"),
        ("   2.1  Complete LLM Call Inventory (17 calls/run)", "6"),
        ("   2.2  Thinking Tokens on Structured Output Calls", "6"),
        ("   2.3  Missing Structured Output for JSON Labels", "7"),
        ("   2.4  Per-Cluster Summary Stagger Blocks 25 Seconds", "7"),
        ("   2.5  Temperature Not Tuned Per Call Type", "8"),
        ("3. Token Efficiency", "9"),
        ("   3.1  Vertex Backend Missing Context Cache (Critical)", "9"),
        ("   3.2  segmentation.md Ships 300+ Lines of Python Code", "9"),
        ("   3.3  project.md Duplicate Context Across All 17 Calls", "10"),
        ("   3.4  MSL Prompt Sends 60 Rows When 20–30 Suffice", "10"),
        ("   3.5  _coerce_column_to_numeric Uses series.apply()", "10"),
        ("   3.6  build_cluster_profiles Sends All ~30 Features", "11"),
        ("4. Persistent Caching Strategy", "12"),
        ("   4.1  No Response-Level Cache Across Runs (Critical)", "12"),
        ("   4.2  Gemini Context Cache Not Persisted Across Restarts", "13"),
        ("5. Context & Reference Files", "14"),
        ("   5.1  Missing Pydantic Schemas for All LLM Outputs", "14"),
        ("   5.2  No Config File for Prompts / Models / Thresholds", "14"),
        ("   5.3  No Few-Shot Examples for Cluster Labeling", "15"),
        ("   5.4  No .gitignore — .env Likely Committed", "15"),
        ("6. Pipeline-Level Optimizations", "16"),
        ("   6.1  No Stage Checkpointing — Full Restart on Failure", "16"),
        ("   6.2  KMeans n_clusters=6 Hardcoded Without Validation", "16"),
        ("   6.3  load_data Chunks then Concatenates — Peak Memory 2×", "17"),
        ("7. Code Quality & Productionization", "18"),
        ("   7.1  requirements.txt Missing Critical Dependencies", "18"),
        ("   7.2  ContextLoader Re-instantiated in llm_msl_selection", "18"),
        ("   7.3  No Unit Tests for Deterministic Components", "18"),
        ("   7.4  Retry Logic Should Use tenacity", "19"),
        ("8. Cost & Latency Dashboard", "20"),
        ("Refactored Code Snippets (Top 5)", "22"),
        ("Proposed Target Architecture", "25"),
        ("Prioritized Roadmap", "26"),
        ("Open Questions & Assumptions", "27"),
    ]
    for title, page in sections:
        depth = title.startswith("   ")
        s = styles["bullet" if depth else "toc_item"]
        elems.append(Paragraph(
            f"{'&nbsp;' * (8 if depth else 0)}{title}"
            f"<font color='#767676'> {'.' * max(1, 60 - len(title))} {page}</font>",
            s))
    elems.append(PageBreak())
    return elems


# ── Section builders ──────────────────────────────────────────────────────────

def exec_summary(styles):
    elems = [h1("Executive Summary", styles), sp(2)]
    points = [
        ("<b>Vertex AI context cache is wired to <font face='Courier'>_call_gemini</font> only — "
         "not <font face='Courier'>_call_vertex_gemini</font> (llm_client.py:545).</b> "
         "Your active backend is Vertex, so every one of 17 LLM calls re-sends the full "
         "system prompt (~7,750 tokens each) uncached. Eight lines of code fix this and save "
         "~75% of input-token costs. <b>Highest ROI change in the entire codebase.</b>"),

        ("<b>You have 17 LLM calls per run, not 7.</b> "
         "MSL selection and space allocation each run once per priority bucket "
         "(4 buckets × 2 = 8 calls). Per-cluster summaries are 6 calls. "
         "Total: 1 DQ + 1 priority + 1 cluster-label + 6 summaries + 4 MSL + 4 space-alloc = 17 calls, "
         "costing ~$0.030/run on Gemini 2.5 Flash."),

        ("<b>The <font face='Courier'>ThreadPoolExecutor</font> stagger in "
         "<font face='Courier'>generate_rich_segment_summaries</font> "
         "(segmentation_agent.py:765) sleeps before submitting each task.</b> "
         "With 6 clusters and 5s stagger, submission alone blocks for 25 seconds of pure dead wait. "
         "Replacing with <font face='Courier'>asyncio.gather + Semaphore</font> "
         "cuts segmentation wall-time in half."),

        ("<b>No LLM response cache exists across pipeline runs.</b> "
         "The Gemini context cache only caches the system prompt server-side — not the generated "
         "response. Re-running on the same dataset re-invokes all 17 API calls. "
         "A <font face='Courier'>diskcache</font> response cache (keyed by "
         "sha256(prompt + system + model + max_tokens)) makes re-runs free."),

        ("<b><font face='Courier'>segmentation.md</font> is 593 lines including 300+ lines "
         "of Python chart code</b> (§6, §10, §11) that the model cannot execute but fully "
         "tokenizes. This alone wastes ~21,000 input tokens across 7 segmentation calls per run. "
         "Strip the code blocks — they belong in the repo, not the system prompt."),
    ]
    for i, pt in enumerate(points, 1):
        elems.append(KeepTogether([
            Paragraph(f"<b>{i}.</b>", styles["body"]),
            Paragraph(pt, styles["exec_bullet"]),
            sp(1),
        ]))
    elems.append(PageBreak())
    return elems


def section1(styles):
    elems = [h1("1.  Agentic AI Architecture Review", styles), sp(2)]

    # 1.1
    for x in h2("1.1  Current Flow: Procedural, Not Agentic", styles): elems.append(x)
    elems.append(body(
        "<b>pipeline.py:220–398</b> is a single linear function with no state machine, "
        "no planner, no critic/validator, and no self-correction loops. "
        "The pipeline continues even on a DQ FAIL verdict — "
        "<font face='Courier'>dq_passed</font> is computed but never checked.",
        styles))

    elems.append(finding("1.1", "DQ FAIL never halts the pipeline", styles))
    elems.append(body(
        "File: <b>pipeline.py:292–305</b> — "
        "<font face='Courier'>dq_passed</font> is assigned but the pipeline continues regardless.",
        styles))
    elems.append(code_block(
"""# CURRENT (pipeline.py:292-305)
dq_passed, dq_report = get_claude_dq_verdict(...)
logger.info(f"LLM DQ verdict: {'PASS' if dq_passed else 'FAIL'}")
# pipeline just continues — no gate!

# RECOMMENDED: configurable gate
REQUIRE_DQ_PASS = os.getenv("REQUIRE_DQ_PASS", "true").lower() == "true"
if not dq_passed and REQUIRE_DQ_PASS:
    logger.error("DQ FAIL — pipeline halted. Set REQUIRE_DQ_PASS=false to override.")
    raise RuntimeError(f"DQ gate failed:\\n{dq_report}")""", styles))
    elems.append(body("Impact: Prevents silent corruption of segmentation and MSL outputs "
                      "when data quality is genuinely blocking. <b>High.</b>", styles))

    # 1.2
    for x in h2("1.2  Proposed Agent + Tools Architecture", styles): elems.append(x)
    elems.append(body(
        "Expose regression, clustering, MSL, and space-allocation as "
        "<font face='Courier'>@tool</font>-decorated functions with Pydantic I/O schemas. "
        "A lightweight state-machine orchestrator (not full LangGraph) runs the DAG. "
        "A CriticAgent validates JSON structure and business rules before outputs are accepted.",
        styles))

    arch_rows = [
        ["Stage", "Agent / Tool", "LLM?", "Critic Gate?"],
        ["Data Ingest",    "load_data tool",         "No",  "Schema check"],
        ["DQ Check",       "DQAgent",                "Yes", "PASS/FAIL gate"],
        ["Prioritization", "QuantileRegressionTool", "Yes", "n/a"],
        ["Clustering",     "KMeansTool",             "Yes", "Label schema validate"],
        ["Rich Summaries", "AsyncSummaryTool (×6)",  "Yes", "Section completeness"],
        ["MSL",            "MSLTool (×4 buckets)",   "Yes", "Hero count > 0"],
        ["Space Alloc",    "SpaceTool (×4 buckets)", "Yes", "n/a"],
        ["Output",         "OutputAgent",            "No",  "n/a"],
    ]
    elems.append(make_table(
        arch_rows[0], arch_rows[1:],
        [45*mm, 60*mm, 20*mm, 45*mm]))
    elems.append(sp(2))

    # 1.3
    for x in h2("1.3  Missing: Observability Hooks", styles): elems.append(x)
    elems.append(finding("1.3", "run_id not threaded into LLM calls or logs", styles))
    elems.append(body(
        "<b>pipeline.py:261</b> defines <font face='Courier'>run_id</font> "
        "but it is never passed to any agent or <font face='Courier'>call_llm()</font>. "
        "Every log message inside dq_agent.py, segmentation_agent.py, etc., "
        "is disconnected from the originating run — impossible to correlate failures.",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: add run_id + stage to call_llm signature (llm_client.py)
import structlog
log = structlog.get_logger()

def call_llm(prompt, api_key, model, max_tokens=2000,
             system_prompt=None, use_thinking=True,
             run_id=None, stage=None) -> str:
    bound = log.bind(run_id=run_id, stage=stage, model=model)
    bound.info("llm_call_start", prompt_chars=len(prompt))
    t0 = time.perf_counter()
    result = _dispatch(...)
    bound.info("llm_call_end",
               latency_ms=round((time.perf_counter()-t0)*1000),
               output_chars=len(result))
    return result""", styles))
    elems.append(PageBreak())
    return elems


def section2(styles):
    elems = [h1("2.  LLM Call Optimization", styles), sp(2)]

    for x in h2("2.1  Complete LLM Call Inventory (17 Calls / Run)", styles):
        elems.append(x)
    elems.append(body(
        "The pipeline makes <b>17 LLM calls per full run</b>, not 7. "
        "MSL selection and space allocation each run once per priority bucket (A/B/C/D), "
        "and per-cluster rich summaries generate 6 parallel calls.",
        styles))

    inv_rows = [
        ["#", "File", "Function", "Line", "max_tokens", "Thinking", "Call Type"],
        ["1",  "dq_agent.py",            "get_claude_dq_verdict",    "211", "1,024",  "ON (waste)", "Binary verdict"],
        ["2",  "prioritization_agent.py","get_claude_priority_narrative","454","2,000","ON (ok)",   "700-word narrative"],
        ["3",  "segmentation_agent.py",  "label_segments_with_claude","407","3,000",  "ON (ok)",   "JSON cluster labels"],
        ["4-9","segmentation_agent.py",  "generate_segment_summary ×6","651","2,500×6","ON (ok)",  "7-section rich summaries"],
        ["10-13","msl_generator.py",     "llm_msl_selection ×4",     "399","3,000×4","ON (waste)","Pipe-delimited table"],
        ["14-17","space_allocation_agent.py","get_llm_recommendation ×4","521","1,800×4","ON (waste)","Short narrative"],
    ]
    elems.append(make_table(
        inv_rows[0], inv_rows[1:],
        [10*mm, 38*mm, 44*mm, 11*mm, 20*mm, 22*mm, 30*mm],
        highlight_rows=[1, 5, 6]))
    elems.append(sp(3))

    # 2.2
    elems.append(finding("2.2", "Thinking Tokens on 9 Structured Output Calls", styles))
    elems.append(body(
        "<b>llm_client.py:535–538</b> adds <font face='Courier'>thinking_budget=2048</font> "
        "to ALL Gemini 2.5+ calls. DQ verdict (binary PASS/FAIL), MSL classification "
        "(pipe-delimited table), and space allocation narrative are deterministic structured "
        "outputs that don't benefit from CoT reasoning chains.",
        styles))
    elems.append(body(
        "Calls wasting thinking: DQ (#1), MSL ×4 (#10–13), space-alloc ×4 (#14–17) = "
        "<b>9 calls × 2,048 tokens = 18,432 wasted thinking tokens per run</b> "
        "(≈$0.006 at output pricing of $0.30/1M).",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: add use_thinking param to call_llm (llm_client.py)
def call_llm(prompt, api_key, model, max_tokens=2000,
             system_prompt=None, use_thinking=True) -> str: ...

# _call_vertex_gemini — only allocate budget when requested
thinking_config = None
total_tokens = max_tokens
if use_thinking and ("2.5" in model_name or "3." in model_name):
    thinking_budget = 2048
    total_tokens = max_tokens + thinking_budget
    thinking_config = types.ThinkingConfig(thinking_budget=thinking_budget)

# dq_agent.py:211 — disable thinking
text = call_llm(prompt, api_key, model, max_tokens=1024,
                system_prompt=_ctx.build("dq"), use_thinking=False)

# msl_generator.py:399 — disable thinking
response = call_llm(prompt, api_key, model, max_tokens=3000,
                    system_prompt=system_prompt, use_thinking=False)""", styles))
    elems.append(sp(2))

    # 2.3
    elems.append(finding("2.3", "No Structured Output Enforcement for JSON Cluster Labels", styles))
    elems.append(body(
        "<b>segmentation_agent.py:407</b> asks for JSON but parses with "
        "<font face='Courier'>_parse_json_labels</font> + "
        "<font face='Courier'>_parse_segment_labels</font> text-parser fallback "
        "(250 lines of fragile code). Vertex AI Gemini supports "
        "<font face='Courier'>response_mime_type='application/json'</font> and "
        "<font face='Courier'>response_schema</font> for guaranteed valid JSON.",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: agents/schemas.py — define response schema
from google.genai import types as genai_types

CLUSTER_LABEL_SCHEMA = genai_types.Schema(
    type=genai_types.Type.ARRAY,
    items=genai_types.Schema(
        type=genai_types.Type.OBJECT,
        properties={
            "cluster_id":  genai_types.Schema(type=genai_types.Type.INTEGER),
            "label":       genai_types.Schema(type=genai_types.Type.STRING),
            "channel":     genai_types.Schema(type=genai_types.Type.STRING,
                               enum=["GT", "MT", "AfH", "EC"]),
            "occasion":    genai_types.Schema(type=genai_types.Type.STRING),
            "description": genai_types.Schema(type=genai_types.Type.STRING),
            "action":      genai_types.Schema(type=genai_types.Type.STRING),
        },
        required=["cluster_id", "label", "channel",
                  "occasion", "description", "action"],
    ),
)""", styles))
    elems.append(body("Impact: Eliminates ~250 lines of fallback parsing code. "
                      "Removes risk of silent fallback to auto-generated labels. "
                      "<b>High reliability. Low effort.</b>", styles))
    elems.append(sp(2))

    # 2.4
    elems.append(finding("2.4", "Per-Cluster Summary Stagger Blocks 25 Seconds", styles))
    elems.append(body(
        "<b>segmentation_agent.py:765</b> calls "
        "<font face='Courier'>time.sleep(stagger_secs)</font> BEFORE submitting each task to "
        "the ThreadPoolExecutor. With 6 clusters and 5s stagger, the submission loop alone "
        "takes 25 seconds before any cluster past the first is dispatched.",
        styles))

    timeline_rows = [
        ["Time", "Event"],
        ["t = 0s",  "Submit cluster 0"],
        ["t = 5s",  "sleep(5) then submit cluster 1"],
        ["t = 10s", "sleep(5) then submit cluster 2"],
        ["t = 15s", "sleep(5) then submit cluster 3  ← clusters 0,1,2 may already be done"],
        ["t = 20s", "sleep(5) then submit cluster 4"],
        ["t = 25s", "sleep(5) then submit cluster 5"],
    ]
    elems.append(make_table(timeline_rows[0], timeline_rows[1:],
                            [25*mm, 130*mm], highlight_rows=[4]))
    elems.append(sp(2))
    elems.append(code_block(
"""# RECOMMENDED: segmentation_agent.py — replace with asyncio
import asyncio
from concurrent.futures import ThreadPoolExecutor

_summary_executor = ThreadPoolExecutor(max_workers=6)

async def _run_all_summaries(profiles, api_key, model, labels,
                              dq_context, priority_context) -> dict:
    max_concurrent = int(os.getenv("SEGMENT_SUMMARY_MAX_WORKERS", "3"))
    semaphore = asyncio.Semaphore(max_concurrent)
    loop = asyncio.get_event_loop()

    async def _one(p):
        cid = p["cluster_id"]
        label_info = (labels or {}).get(cid, {})
        async with semaphore:
            summary = await loop.run_in_executor(
                _summary_executor,
                lambda: generate_segment_summary(
                    p, profiles, api_key, model,
                    label_info=label_info,
                    dq_context=dq_context,
                    priority_context=priority_context,
                )
            )
            return cid, summary

    results = await asyncio.gather(*[_one(p) for p in profiles],
                                   return_exceptions=True)
    return {cid: s for cid, s in results if not isinstance(s, Exception)}

def generate_rich_segment_summaries(...) -> dict:
    return asyncio.run(_run_all_summaries(...))""", styles))
    elems.append(body("Impact: Eliminates 25s of dead sleep. Wall-time for 6 summaries "
                      "drops from ~55s to ~25s. <b>High latency impact.</b>", styles))
    elems.append(sp(2))

    # 2.5
    elems.append(finding("2.5", "Temperature Not Tuned Per Call Type", styles))
    temp_rows = [
        ["Call", "Current Temp", "Recommended", "Rationale"],
        ["DQ verdict",          "0.3", "0.1", "Deterministic classification"],
        ["Priority narrative",  "0.3", "0.3", "OK as-is"],
        ["Cluster labeling",    "0.3", "0.1", "Structured JSON; lower variance is better"],
        ["Per-cluster summaries","0.3","0.5", "Creative writing; variation adds quality"],
        ["MSL classification",  "0.3", "0.1", "Structured table; must be consistent across buckets"],
        ["Space allocation",    "0.3", "0.4", "Short narrative; slight variation acceptable"],
    ]
    elems.append(make_table(temp_rows[0], temp_rows[1:],
                            [45*mm, 30*mm, 30*mm, 65*mm]))
    elems.append(PageBreak())
    return elems


def section3(styles):
    elems = [h1("3.  Token Efficiency", styles), sp(2)]

    # 3.1
    elems.append(finding("3.1 — CRITICAL",
                          "Vertex Backend Missing Context Cache", styles))
    elems.append(body(
        "<b>llm_client.py:545</b> in <font face='Courier'>_call_vertex_gemini</font> "
        "passes <font face='Courier'>system_instruction</font> directly — "
        "no caching. Compare with <font face='Courier'>_call_gemini</font> (line 401) "
        "which calls <font face='Courier'>_get_or_create_gemini_cache</font>. "
        "Since <font face='Courier'>LLM_BACKEND=vertex</font> is your active config, "
        "<b>zero system prompt caching is occurring.</b> "
        "Every call pays full input-token cost for project.md + agent.md (~7,750 tokens each).",
        styles))
    elems.append(code_block(
"""# CURRENT — _call_vertex_gemini (llm_client.py:545)
if system_prompt:
    config_kwargs["system_instruction"] = system_prompt   # NO CACHING

# RECOMMENDED — 8-line fix
if system_prompt:
    cache_name = _get_or_create_gemini_cache(client, model_name, system_prompt)
    if cache_name:
        config_kwargs["cached_content"] = cache_name
        # DO NOT also pass system_instruction — it's embedded in the cache
    else:
        config_kwargs["system_instruction"] = system_prompt""", styles))
    cost_rows = [
        ["Metric", "Before Fix", "After Fix"],
        ["System prompt tokens / call", "~7,750", "~7,750 (cached)"],
        ["17 calls × sys prompt cost",
         "17 × 7,750 × $0.075/1M = $0.00987",
         "17 × 7,750 × $0.01875/1M = $0.00247"],
        ["Savings per run", "—", "$0.0074 (75% reduction)"],
    ]
    elems.append(make_table(cost_rows[0], cost_rows[1:],
                            [60*mm, 60*mm, 55*mm], highlight_rows=[4]))
    elems.append(sp(3))

    # 3.2
    elems.append(finding("3.2",
                          "segmentation.md Ships 300+ Lines of Python Code to the LLM", styles))
    elems.append(body(
        "<font face='Courier'>context/agents/segmentation.md</font> is 593 lines. "
        "Sections §6 (Python chart code for 5 chart types), §10 (Python integration code), "
        "and §11 (chart references) contain <b>Python source code the model cannot execute</b> "
        "but fully tokenizes. This adds ~3,000 tokens to every segmentation call × 7 calls = "
        "<b>~21,000 wasted tokens per run.</b>",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: split segmentation.md into two files
# context/agents/segmentation_system.md  ← LLM guidance only (§1-§5, §7-§9)
# context/agents/segmentation_code_ref.md ← code references (§6, §10, §11)

# context_loader.py — agents see only segmentation_system.md
def build(self, agent_name: str) -> str:
    agent_file = f"{agent_name}_system.md"   # suffix convention
    agent = self._load(os.path.join("agents", agent_file))
    ...
    return "\\n\\n".join(parts)""", styles))
    elems.append(sp(2))

    # 3.3
    elems.append(finding("3.3",
                          "project.md Duplicate Context Across All 17 Calls", styles))
    elems.append(body(
        "<font face='Courier'>context_loader.py:60</font> embeds "
        "<font face='Courier'>project.md</font> (267+ lines, ~3,750 tokens) in the system "
        "prompt for every call. With Finding 3.1 fix applied, these become cached reads "
        "at 75% discount. Further optimization: split static vs. dynamic prefix.",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: context_loader.py — static prefix separation
def build(self, agent_name: str, static_only: bool = False) -> str:
    project = self._load("project.md")
    if static_only:
        return project          # for cache warming
    agent = self._load(os.path.join("agents", f"{agent_name}.md"))
    parts = [p for p in [project, "---", agent] if p]
    return "\\n\\n".join(parts)

# In pipeline.py — warm cache at start
from agents.context_loader import ContextLoader
ctx = ContextLoader()
_warm_system_context(ctx)   # pre-create Vertex cache for project.md""", styles))
    elems.append(sp(2))

    # 3.4
    elems.append(finding("3.4",
                          "MSL Prompt Sends 60 Rows When 20–30 Would Suffice", styles))
    elems.append(body(
        "<b>msl_generator.py:355</b> hard-codes "
        "<font face='Courier'>product_list[:60]</font>. "
        "A pipe-delimited row averages ~100 chars. 60 rows ≈ 1,500 tokens × 4 buckets "
        "= 6,000 tokens that could be halved by sending only enough rows to cover "
        "80% cumulative mix + 5 extra for strategic picks.",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: msl_generator.py — adaptive row count
def _build_product_table(product_list: list, target_mix: float = 0.80) -> str:
    header = "RANK | PRODUCT | PPG | BRAND | % MIX | CUM MIX | % STORES | INDEX"
    rows = [header]
    running, cutoff = 0.0, len(product_list)
    for i, p in enumerate(product_list):
        running += (p.get("cat_pct_mix") or 0)
        if running >= target_mix and i >= 10:
            cutoff = min(i + 5, len(product_list))
            break
    for p in product_list[:cutoff]:
        idx = p.get("index")
        rows.append(f"{p['display_rank']} | {p['product_name']} | ...")
    return "\\n".join(rows)""", styles))
    elems.append(sp(2))

    # 3.5
    elems.append(finding("3.5",
                          "_coerce_column_to_numeric Uses series.apply() — Slow on 900k Rows", styles))
    elems.append(body(
        "<b>segmentation_agent.py:181</b> and <b>prioritization_agent.py:278</b> call "
        "<font face='Courier'>series.apply(_convert)</font> per column. On 900k rows × "
        "30 feature columns = 27 million Python object calls. "
        "This can add 2–3 minutes of pure computation on large files.",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: vectorized with hex-string fallback
def _coerce_column_to_numeric(series: pd.Series) -> pd.Series:
    # Fast path: handles 99% of cases via pandas vectorized coercion
    result = pd.to_numeric(series, errors="coerce")

    # Slow path: only process non-null values that failed coercion
    needs_check = result.isna() & series.notna()
    if needs_check.any():
        str_vals = series[needs_check].astype(str).str.strip().str.lower()
        hex_mask = str_vals.str.startswith("0x")
        if hex_mask.any():
            hex_vals = str_vals[hex_mask].apply(
                lambda s: float(int(s, 16)) if s.startswith("0x") else np.nan
            )
            result.loc[hex_vals.index] = hex_vals
    return result
# ~100-1000x faster than series.apply() on large DataFrames""", styles))
    elems.append(sp(2))

    # 3.6
    elems.append(finding("3.6",
                          "build_cluster_profiles Sends All ~30 Features to LLM", styles))
    elems.append(body(
        "<b>segmentation_agent.py:314–329</b> includes all 11 demographic columns "
        "and up to 14 categorical columns per cluster in the LLM prompt. "
        "Send only the top 8–10 features where the cluster deviates most from universe mean.",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: segmentation_agent.py — top-discriminating features
def _top_discriminating_features(profile, all_profiles, n=8):
    universe_avgs = {}
    for key in profile.get("avg_demographics", {}):
        vals = [p.get("avg_demographics", {}).get(key, np.nan)
                for p in all_profiles]
        universe_avgs[key] = np.nanmean(vals)
    deviations = {
        k: abs(v - universe_avgs.get(k, v)) / max(abs(universe_avgs.get(k, 1)), 1)
        for k, v in profile.get("avg_demographics", {}).items()
    }
    top = sorted(deviations, key=deviations.get, reverse=True)[:n]
    return {k: profile["avg_demographics"][k] for k in top}""", styles))
    elems.append(PageBreak())
    return elems


def section4(styles):
    elems = [h1("4.  Persistent Caching Strategy", styles), sp(2)]

    # 4.1
    elems.append(finding("4.1 — CRITICAL",
                          "No Response-Level Cache Across Pipeline Runs", styles))
    elems.append(body(
        "Zero response caching exists. The Gemini context cache only caches the system prompt "
        "server-side — not the generated response. Re-running the pipeline on the same dataset "
        "re-invokes all 17 API calls. During iterative development (dozens of re-runs per day), "
        "this is the single largest avoidable cost in the pipeline.",
        styles))

    cache_rows = [
        ["Layer", "Cache Key", "Value", "TTL", "Backend"],
        ["Exact-match LLM response",
         "sha256(prompt + system + model + backend + max_tokens)",
         "Response text string", "24h", "diskcache.Cache"],
        ["Intermediate artifacts",
         "sha256(df_hash + stage + config_hash)",
         "Parquet (clusters, priority cols)", "7d", "Parquet files"],
        ["Gemini server-side context",
         "sha256(model + system_prompt)[:16]",
         "Cache name string", "1h", "In-memory dict (exists)"],
        ["Embedding cache",
         "sha256(text)",
         "numpy float32 array", "30d", "diskcache.Cache"],
    ]
    elems.append(make_table(cache_rows[0], cache_rows[1:],
                            [38*mm, 55*mm, 40*mm, 12*mm, 25*mm]))
    elems.append(sp(3))
    elems.append(code_block(
"""# agents/cache.py  (new file)
import hashlib, json, os
import diskcache

_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".llm_cache")
_cache: diskcache.Cache | None = None

def _get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        _cache = diskcache.Cache(_CACHE_DIR, size_limit=2**30)  # 1 GB
    return _cache

def make_cache_key(prompt, system_prompt, model, backend, max_tokens) -> str:
    payload = json.dumps({"p": prompt, "s": system_prompt or "",
                          "m": model, "b": backend, "t": max_tokens},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()

def cached_call(inner_fn, prompt, api_key, model, max_tokens,
                system_prompt, ttl=86_400, **kwargs) -> str:
    if os.getenv("ENABLE_LLM_CACHE", "true").lower() != "true":
        return inner_fn(prompt, api_key, model, max_tokens,
                        system_prompt, **kwargs)
    backend = os.getenv("LLM_BACKEND", "anthropic")
    key = make_cache_key(prompt, system_prompt, model, backend, max_tokens)
    cache = _get_cache()
    if key in cache:
        logger.debug(f"LLM cache HIT key={key[:10]}")
        return cache[key]
    result = inner_fn(prompt, api_key, model, max_tokens,
                      system_prompt, **kwargs)
    cache.set(key, result, expire=ttl)
    return result

# llm_client.py — wrap the dispatcher
from agents.cache import cached_call

def call_llm(prompt, api_key, model, max_tokens=2000,
             system_prompt=None, use_thinking=True) -> str:
    return cached_call(_dispatch_llm, prompt, api_key, model,
                       max_tokens, system_prompt,
                       use_thinking=use_thinking)""", styles))
    elems.append(body(
        "Impact: Re-runs on same data go from ~$0.030 and 3–5 minutes → "
        "<b>$0.00 and &lt;5 seconds</b>. Highest-ROI change for development workflow.",
        styles))
    elems.append(sp(3))

    # 4.2
    elems.append(finding("4.2",
                          "Gemini Context Cache Not Persisted Across Process Restarts", styles))
    elems.append(body(
        "<b>llm_client.py:117</b> stores <font face='Courier'>_gemini_cache_registry</font> "
        "in memory. On every process restart (which happens every pipeline run since it's a CLI), "
        "all cache names are lost and new <font face='Courier'>cachedContents</font> resources "
        "are created. Gemini charges $1.00/1M tokens/hour for stored cache content.",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: persist registry to SQLite (llm_client.py)
import sqlite3, time

_CACHE_DB = os.path.join(os.path.dirname(__file__), "..", ".gemini_cache.db")

def _load_cache_registry() -> dict:
    con = sqlite3.connect(_CACHE_DB)
    con.execute("CREATE TABLE IF NOT EXISTS cache_registry "
                "(key TEXT PRIMARY KEY, name TEXT, expires_at REAL)")
    rows = con.execute(
        "SELECT key, name FROM cache_registry WHERE expires_at > ?",
        (time.time(),)
    ).fetchall()
    con.close()
    return {k: n for k, n in rows}

def _save_cache_entry(key: str, name: str, ttl: int = 3600):
    con = sqlite3.connect(_CACHE_DB)
    con.execute("INSERT OR REPLACE INTO cache_registry VALUES (?, ?, ?)",
                (key, name, time.time() + ttl))
    con.commit(); con.close()

# At module init
_gemini_cache_registry = _load_cache_registry()""", styles))
    elems.append(PageBreak())
    return elems


def section5(styles):
    elems = [h1("5.  Context & Reference Files", styles), sp(2)]

    # 5.1
    elems.append(finding("5.1",
                          "Missing Pydantic Schemas for All LLM Outputs", styles))
    elems.append(body(
        "No structured validation of LLM outputs before they enter the data pipeline. "
        "<b>segmentation_agent.py:417–451</b> uses <font face='Courier'>try/except json.loads()</font> "
        "with a text-parser fallback. <b>msl_generator.py:401–413</b> uses manual pipe-split. "
        "Malformed outputs silently degrade to auto-generated placeholders with no flag in "
        "the final report.",
        styles))
    elems.append(code_block(
"""# agents/schemas.py  (new file)
from pydantic import BaseModel, Field, validator
from typing import Literal, List, Optional

class ClusterLabel(BaseModel):
    cluster_id: int
    label: str = Field(min_length=3, max_length=80)
    channel: Literal["GT", "MT", "AfH", "EC"]
    occasion: str
    description: str = Field(min_length=10)
    action: str = Field(min_length=10)

class MSLItem(BaseModel):
    rank: int
    sku_type: Literal["Hero", "Strategic", ""]
    criterion: str = ""
    reasoning: str = ""

class DQVerdict(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    bullets: List[str] = []
    raw_text: str = ""

    @classmethod
    def from_llm_text(cls, text: str) -> "DQVerdict":
        v = "PASS" if "VERDICT: PASS" in text.upper() else "FAIL"
        bullets = [l.strip().lstrip("*•- ")
                   for l in text.split("\\n") if l.strip().startswith(("*","•","-"))]
        return cls(verdict=v, bullets=bullets, raw_text=text)

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"

class PipelineState(BaseModel):
    run_id: str
    file_path: str
    dq_passed: Optional[bool] = None
    priority_narrative: Optional[str] = None
    segment_labels: Optional[dict] = None
    msl_path: Optional[str] = None
    errors: List[str] = []""", styles))
    elems.append(sp(2))

    # 5.2
    elems.append(finding("5.2",
                          "No Config File for Prompts / Models / Thresholds", styles))
    elems.append(body(
        "Prompt text is hardcoded as f-strings inside functions "
        "(dq_agent.py:180–209, prioritization_agent.py:421–452, etc.). "
        "Changing any prompt requires editing Python source files and redeploying.",
        styles))
    elems.append(code_block(
"""# config/prompts.yaml  (new file)
dq_verdict:
  max_tokens: 1024
  temperature: 0.1
  use_thinking: false
  system_context: dq

priority_narrative:
  max_tokens: 2000
  temperature: 0.3
  use_thinking: true
  system_context: prioritization
  word_target: "500-700"

cluster_labeling:
  max_tokens: 3000
  temperature: 0.1
  use_thinking: false
  system_context: segmentation

cluster_summary:
  max_tokens: 2500
  temperature: 0.5
  use_thinking: true
  system_context: segmentation

msl_selection:
  max_tokens: 3000
  temperature: 0.1
  use_thinking: false
  system_context: msl

space_allocation:
  max_tokens: 1800
  temperature: 0.4
  use_thinking: false
  system_context: space_allocation

models:
  default_vertex: "gemini-2.5-flash"
  fallback_vertex: "gemini-2.0-flash"
  default_anthropic: "claude-opus-4-6" """, styles))
    elems.append(sp(2))

    # 5.3
    elems.append(finding("5.3",
                          "No Few-Shot Examples for Cluster Labeling", styles))
    elems.append(body(
        "<font face='Courier'>label_segments_with_claude</font> (segmentation_agent.py:338) "
        "provides zero worked examples. Output quality depends entirely on the system prompt. "
        "Add <font face='Courier'>context/examples/cluster_labels.json</font> "
        "with 2–3 curated input→output pairs showing ideal India archetypes.",
        styles))
    elems.append(code_block(
"""# context/examples/cluster_labels.json  (new file)
[
  {
    "input_summary": "Cluster: 2,100 outlets, avg VPO Rs.8,700, channel: GT 89%,
     sector: Rural 72%, avg SKU: 6.2, school proximity: 0.3km, SEC D/E 68%",
    "output": {
      "label": "Rural Kirana Youth Impulse GT",
      "channel": "GT",
      "occasion": "Immediate/GrabGo",
      "description": "Small rural kirana stores serving SEC D/E households near
       schools. Rs.5-10 price points dominate. High footfall from students.",
      "action": "Focus on Rs.5-10 Hero SKUs, chiller seeding top outlets,
       weekly visit frequency."
    }
  }
]""", styles))
    elems.append(sp(2))

    # 5.4
    elems.append(finding("5.4",
                          "No .gitignore — .env with GCP Project ID Likely Committed", styles))
    elems.append(body(
        "<font face='Courier'>.env</font> contains "
        "<font face='Courier'>VERTEX_PROJECT=proj-psdesign-500716</font> and "
        "service account credentials. No <font face='Courier'>.gitignore</font> was found. "
        "This is a security-critical gap.",
        styles))
    elems.append(code_block(
"""# .gitignore  (create immediately)
.env
.llm_cache/
.gemini_cache.db
__pycache__/
*.pyc
outputs/
logs/
processing/
inbox/*.csv
inbox/*.xlsx
*.pptx
venv/
.venv/
*.egg-info/""", styles))
    elems.append(PageBreak())
    return elems


def section6(styles):
    elems = [h1("6.  Pipeline-Level Optimizations", styles), sp(2)]

    # 6.1
    elems.append(finding("6.1",
                          "No Stage Checkpointing — Full Restart on Any Failure", styles))
    elems.append(body(
        "<b>pipeline.py:220–398</b> is one uninterrupted function. "
        "If <font face='Courier'>run_space_allocation</font> fails at Step 7, "
        "all 6 preceding steps — including 13 LLM calls — must re-run from scratch. "
        "This makes debugging expensive.",
        styles))
    elems.append(code_block(
"""# agents/checkpoint.py  (new file)
import hashlib, os, pickle
import pandas as pd

def df_hash(df: pd.DataFrame) -> str:
    return hashlib.md5(
        pd.util.hash_pandas_object(df).values
    ).hexdigest()[:12]

def checkpoint_save(stage: str, df: pd.DataFrame,
                    output_dir: str, **extras):
    path = os.path.join(output_dir, "checkpoints", f"{stage}.parquet")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False)
    if extras:
        meta = path.replace(".parquet", "_meta.pkl")
        pickle.dump(extras, open(meta, "wb"))

def checkpoint_load(stage: str, output_dir: str):
    path = os.path.join(output_dir, "checkpoints", f"{stage}.parquet")
    if os.path.exists(path):
        df = pd.read_parquet(path)
        meta = path.replace(".parquet", "_meta.pkl")
        extras = pickle.load(open(meta,"rb")) if os.path.exists(meta) else {}
        return df, extras
    return None, {}

# pipeline.py usage
df_pri, pri_meta = checkpoint_load("prioritization", checkpoint_dir)
if df_pri is None:
    df_pri, narrative = run_prioritization(df, config, api_key, model)
    checkpoint_save("prioritization", df_pri, checkpoint_dir,
                    narrative=narrative)""", styles))
    elems.append(body(
        "Impact: Failed pipeline at Step 7 recovers by loading Steps 1–6 from parquet. "
        "Saves ~$0.025–$0.040 and 2–3 minutes per debugging iteration. "
        "<b>High reliability value.</b>", styles))
    elems.append(sp(2))

    # 6.2
    elems.append(finding("6.2",
                          "KMeans n_clusters=6 Hardcoded Without Validation", styles))
    elems.append(body(
        "<font face='Courier'>config.json: \"n_clusters\": 6</font> is used directly "
        "(<b>segmentation_agent.py:797</b>). No silhouette scoring or elbow analysis. "
        "For urban-only or single-state subsets, 6 clusters may be wrong — "
        "generating empty segments and wasting MSL/summary LLM calls.",
        styles))
    elems.append(code_block(
"""# segmentation_agent.py — optional auto-k with silhouette scoring
from sklearn.metrics import silhouette_score

def find_optimal_k(X_scaled: np.ndarray, k_range=(3, 9),
                   random_state=42) -> int:
    scores = {}
    for k in range(k_range[0], k_range[1] + 1):
        m = MiniBatchKMeans(n_clusters=k, random_state=random_state,
                            batch_size=10_000, n_init=3)
        labels = m.fit_predict(X_scaled)
        sample = min(10_000, len(X_scaled))
        scores[k] = silhouette_score(X_scaled, labels,
                                     sample_size=sample,
                                     random_state=random_state)
        logger.info(f"  k={k}: silhouette={scores[k]:.3f}")
    best = max(scores, key=scores.get)
    logger.info(f"Optimal k={best} (silhouette={scores[best]:.3f})")
    return best

# Control via env var
if os.getenv("AUTO_CLUSTER_K", "false").lower() == "true":
    n_clusters = find_optimal_k(X_scaled[:50_000])""", styles))
    elems.append(sp(2))

    # 6.3
    elems.append(finding("6.3",
                          "load_data Chunks then Concatenates — Peak Memory 2×", styles))
    elems.append(body(
        "<b>pipeline.py:62–67</b> loads CSV chunks into a list and calls "
        "<font face='Courier'>pd.concat(chunks)</font>. On a 900k-row file, this holds "
        "all chunks in memory while creating the concatenated copy — peak memory usage "
        "is approximately 2× the final DataFrame size.",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: use pyarrow backend for zero-copy load (pandas 2.0+)
df = pd.read_csv(file_path,
                 low_memory=False,
                 dtype_backend="pyarrow")   # 2-3x faster, ~40% less memory

# Or full pyarrow for maximum efficiency
import pyarrow.csv as pa_csv
table = pa_csv.read_csv(file_path)
df = table.to_pandas()""", styles))
    elems.append(PageBreak())
    return elems


def section7(styles):
    elems = [h1("7.  Code Quality & Productionization", styles), sp(2)]

    # 7.1
    elems.append(finding("7.1",
                          "requirements.txt Missing Critical Dependencies", styles))
    elems.append(body(
        "The pipeline will fail to import on a fresh install. "
        "The following packages are used but absent from requirements.txt:",
        styles))
    missing_rows = [
        ["Package", "Used In", "Why Missing"],
        ["google-genai>=1.0.0",       "_call_gemini, _call_vertex_gemini", "Gemini SDK"],
        ["google-cloud-aiplatform>=1.60.0", "Vertex AI auth",             "GCP client"],
        ["anthropic[vertex]>=0.25.0", "_call_vertex_claude",              "Anthropic+Vertex"],
        ["statsmodels>=0.14.0",       "prioritization_agent.py:228",      "QuantReg fallback"],
        ["scipy>=1.11.0",             "statsmodels dependency",           "Math backend"],
        ["seaborn>=0.12.0",           "output_agent.py heatmap",          "Chart library"],
        ["diskcache>=5.6.0",          "Recommended LLM cache",            "Not yet added"],
        ["pydantic>=2.0.0",           "Recommended schema validation",    "Not yet added"],
        ["structlog>=24.0.0",         "Recommended logging",              "Not yet added"],
        ["tenacity>=8.0.0",           "Replace hand-rolled retry",        "Not yet added"],
    ]
    elems.append(make_table(missing_rows[0], missing_rows[1:],
                            [52*mm, 55*mm, 58*mm]))
    elems.append(sp(2))

    # 7.2
    elems.append(finding("7.2",
                          "ContextLoader Re-instantiated Inside llm_msl_selection", styles))
    elems.append(body(
        "<b>msl_generator.py:395–396</b> creates "
        "<font face='Courier'>ctx = ContextLoader()</font> inside "
        "<font face='Courier'>llm_msl_selection()</font>, which is called once per bucket. "
        "Each instantiation re-reads project.md and msl.md from disk. "
        "Three-character fix with significant cleanliness benefit.",
        styles))
    elems.append(code_block(
"""# CURRENT (msl_generator.py:395) — inside function, called 4× per run
def llm_msl_selection(bucket_name, product_list, api_key, model, ...):
    ...
    ctx = ContextLoader()           # re-instantiates on every bucket
    system_prompt = ctx.build("msl")

# RECOMMENDED — module-level singleton
_ctx = ContextLoader()              # loaded once at import time

def llm_msl_selection(bucket_name, product_list, api_key, model, ...):
    ...
    system_prompt = _ctx.build("msl")   # uses in-memory cache""", styles))
    elems.append(sp(2))

    # 7.3
    elems.append(finding("7.3",
                          "No Unit Tests for Any Deterministic Components", styles))
    elems.append(body(
        "No test files were found in the project. The following components are "
        "100% deterministic, have no LLM dependency, and should have full test coverage:",
        styles))
    test_rows = [
        ["Component", "File", "Test Type"],
        ["check_nulls, check_vpo_outliers, check_duplicate_outlet_ids",
         "dq_agent.py:21–148", "Unit"],
        ["assign_abcd_buckets",       "prioritization_agent.py:104", "Unit"],
        ["_coerce_column_to_numeric", "segmentation_agent.py:173",   "Unit (including hex)"],
        ["compute_opportunity_gap",   "prioritization_agent.py:325", "Unit"],
        ["_parse_json_labels",        "segmentation_agent.py:417",   "Unit (malformed JSON)"],
        ["_parse_rich_summary",       "segmentation_agent.py:656",   "Snapshot"],
        ["build_metrics",             "msl_generator.py:159",        "Unit"],
        ["_fallback_msl_selection",   "msl_generator.py:311",        "Unit"],
    ]
    elems.append(make_table(test_rows[0], test_rows[1:],
                            [68*mm, 42*mm, 55*mm]))
    elems.append(code_block(
"""# tests/test_dq_agent.py
import pandas as pd, pytest
from agents.dq_agent import check_nulls, check_duplicate_outlet_ids

def test_null_check_flags_high_null_columns():
    df = pd.DataFrame({"A": [1, None, None, None], "B": [1, 2, 3, 4]})
    assert not check_nulls(df, 60.0)["pass"]

def test_duplicate_outlet_ids_detected():
    df = pd.DataFrame({"OUTLET_UID_EDITED": ["A", "A", "B"]})
    result = check_duplicate_outlet_ids(df)
    assert not result["pass"] and result["duplicate_rows"] == 1

def test_hex_coercion_converts_correctly():
    from agents.segmentation_agent import _coerce_column_to_numeric
    s = pd.Series(["0x2a", "10", "3.14", None, "bad"])
    r = _coerce_column_to_numeric(s)
    assert r[0] == 42.0 and r[1] == 10.0 and pd.isna(r[3]) and pd.isna(r[4])""", styles))
    elems.append(sp(2))

    # 7.4
    elems.append(finding("7.4",
                          "Hand-Rolled Retry Should Use tenacity", styles))
    elems.append(body(
        "<b>llm_client.py:204–227</b> hand-rolls exponential backoff with "
        "<font face='Courier'>time.sleep</font>. This lacks jitter (thundering herd risk "
        "when 3+ parallel summary calls all retry simultaneously), logging hooks, "
        "and composable stop conditions.",
        styles))
    elems.append(code_block(
"""# RECOMMENDED: llm_client.py — use tenacity
from tenacity import (retry, stop_after_attempt, wait_exponential_jitter,
                       retry_if_exception, before_sleep_log)

@retry(
    stop=stop_after_attempt(int(os.getenv("LLM_MAX_RETRIES", "4"))),
    wait=wait_exponential_jitter(
        initial=float(os.getenv("LLM_RETRY_BASE_DELAY", "5")),
        max=60, jitter=2
    ),
    retry=retry_if_exception(_is_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _dispatch_with_retry(backend_fn, *args, **kwargs):
    return backend_fn(*args, **kwargs)""", styles))
    elems.append(PageBreak())
    return elems


def section8(styles):
    elems = [h1("8.  Cost & Latency Dashboard", styles), sp(2)]

    for x in h2("Estimated Tokens Per Run (Active: Vertex AI Gemini 2.5 Flash)", styles):
        elems.append(x)

    token_rows = [
        ["Stage", "Calls", "Input Tokens", "Output Tokens", "Thinking", "Subtotal"],
        ["DQ verdict",             "1",  "3,500",  "800",   "2,048",  "6,348"],
        ["Priority narrative",     "1",  "5,000",  "2,000", "2,048",  "9,048"],
        ["Cluster labeling",       "1",  "8,000",  "2,500", "2,048",  "12,548"],
        ["Per-cluster summaries",  "6",  "72,000", "15,000","12,288", "99,288"],
        ["MSL selection",          "4",  "28,000", "11,200","8,192",  "47,392"],
        ["Space allocation",       "4",  "22,000", "6,400", "8,192",  "36,592"],
        ["TOTAL",                  "17", "138,500","37,900","34,816", "211,216"],
    ]
    t = Table([token_rows[0]] + token_rows[1:],
              colWidths=[45*mm, 15*mm, 25*mm, 25*mm, 22*mm, 25*mm],
              repeatRows=1)
    style = table_style_base()
    style.append(("FONTNAME",   (0, 7), (-1, 7), "Helvetica-Bold"))
    style.append(("BACKGROUND", (0, 7), (-1, 7), NAVY))
    style.append(("TEXTCOLOR",  (0, 7), (-1, 7), WHITE))
    t.setStyle(TableStyle(style))
    elems.append(t)
    elems.append(sp(3))

    for x in h2("Pricing (Gemini 2.5 Flash on Vertex, 2026)", styles):
        elems.append(x)
    price_rows = [
        ["Token Type", "Rate", "Tokens/Run", "Cost/Run"],
        ["Input (standard)",      "$0.075 / 1M tokens", "~138,500", "$0.0104"],
        ["Output + Thinking",     "$0.30 / 1M tokens",  "~72,716",  "$0.0218"],
        ["System prompt overhead","(subset of input)",   "~131,750", "(included)"],
        ["Total per fresh run",   "",                    "~211,216", "$0.0322"],
    ]
    elems.append(make_table(price_rows[0], price_rows[1:],
                            [50*mm, 40*mm, 35*mm, 40*mm]))
    elems.append(sp(3))

    for x in h2("Projected Savings After Each Recommended Fix", styles):
        elems.append(x)
    savings_rows = [
        ["Fix", "Tokens Saved/Run", "$/Run Saved", "Latency", "Effort"],
        ["F3.1 Add context cache to Vertex",   "~92,225 sys prompt tokens", "$0.0074", "100ms/call", "S (8 lines)"],
        ["F2.1 Disable thinking (9 calls)",    "~18,432 thinking tokens",   "$0.0055", "50-150ms/call","S (12 lines)"],
        ["F3.2 Strip code from segmentation.md","~21,000 input tokens",     "$0.0016", "—",           "S (delete lines)"],
        ["F3.4 Adaptive MSL row count",         "~22,400 input tokens",     "$0.0017", "—",           "S (20 lines)"],
        ["F4.1 LLM response cache",             "100% on re-runs",          "$0.0322", "3-5 min",     "M (30 lines)"],
        ["F2.3 Async summaries",                "0 tokens",                 "—",       "-25s latency","M (40 lines)"],
        ["F3.5 Vectorized coercion",            "0 tokens",                 "—",       "-2min compute","S (20 lines)"],
        ["F6.1 Stage checkpointing",            "All tokens past fail point","$0.01-0.03","—",         "M (50 lines)"],
        ["TOTAL (fresh runs)",                  "~154,057 tokens",          "-$0.016/run","—",         ""],
        ["TOTAL (re-runs w/ cache)",            "211,216 tokens",           "-$0.032/run","3–5 min",   ""],
    ]
    t2 = Table([savings_rows[0]] + savings_rows[1:],
               colWidths=[50*mm, 37*mm, 23*mm, 25*mm, 30*mm],
               repeatRows=1)
    s2 = table_style_base()
    s2.append(("FONTNAME",   (0, 9), (-1, 10), "Helvetica-Bold"))
    s2.append(("BACKGROUND", (0, 9), (-1, 10), HexColor("#375623")))
    s2.append(("TEXTCOLOR",  (0, 9), (-1, 10), WHITE))
    t2.setStyle(TableStyle(s2))
    elems.append(t2)
    elems.append(sp(3))

    for x in h2("Top 3 Highest-ROI Changes", styles): elems.append(x)
    top3 = [
        ("1", "Add context cache to _call_vertex_gemini",
         "8 lines · $0.0074/run · improves all 17 calls · zero risk"),
        ("2", "Add diskcache LLM response cache",
         "30 lines · $0.032 saved per re-run · highest dev-cycle value"),
        ("3", "Replace ThreadPoolExecutor+sleep with asyncio",
         "40 lines · eliminates 25s dead wait · 2× segment summary throughput"),
    ]
    for num, title, detail in top3:
        elems.append(KeepTogether([
            Paragraph(f"<b>#{num} — {title}</b>", styles["h3"]),
            Paragraph(detail, styles["body"]),
            sp(1),
        ]))
    elems.append(PageBreak())
    return elems


def section_snippets(styles):
    elems = [h1("Refactored Code Snippets (Top 5)", styles), sp(2)]

    snippets = [
        ("Snippet 1", "Context Cache for Vertex Backend",
         "llm_client.py — _call_vertex_gemini (~line 545)",
"""# _call_vertex_gemini — add 8 lines for context caching
def _call_vertex_gemini(prompt, max_tokens, system_prompt,
                        project, model_name, use_thinking=True):
    from google import genai
    from google.genai import types

    location = os.getenv("VERTEX_LOCATION", "us-central1")
    client = genai.Client(vertexai=True, project=project, location=location)

    thinking_config = None
    total_tokens = max_tokens
    if use_thinking and ("2.5" in model_name or "3." in model_name):
        thinking_budget = 2048
        total_tokens = max_tokens + thinking_budget
        thinking_config = types.ThinkingConfig(thinking_budget=thinking_budget)

    config_kwargs = dict(max_output_tokens=total_tokens,
                         temperature=0.3, thinking_config=thinking_config)

    if system_prompt:
        # ← ADD: same pattern already used in _call_gemini
        cache_name = _get_or_create_gemini_cache(client, model_name, system_prompt)
        if cache_name:
            config_kwargs["cached_content"] = cache_name
        else:
            config_kwargs["system_instruction"] = system_prompt

    response = client.models.generate_content(
        model=model_name, contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    text = response.text
    if text is None:
        parts = []
        for candidate in (response.candidates or []):
            content = getattr(candidate, "content", None)
            for part in (content.parts or [] if content else []):
                if not getattr(part, "thought", False) and part.text:
                    parts.append(part.text)
        text = "\\n".join(parts)
    if not text:
        finish = (response.candidates[0].finish_reason
                  if response.candidates else "unknown")
        raise ValueError(f"Vertex Gemini empty response (finish={finish})")
    return text"""),

        ("Snippet 2", "LLM Response Cache",
         "agents/cache.py — new file",
"""import hashlib, json, os, logging
import diskcache

logger = logging.getLogger("perfect_store.cache")
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".llm_cache")
_cache: diskcache.Cache | None = None

def _get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        _cache = diskcache.Cache(_CACHE_DIR, size_limit=2**30)  # 1 GB
    return _cache

def make_cache_key(prompt, system_prompt, model, backend, max_tokens) -> str:
    payload = json.dumps({"p": prompt, "s": system_prompt or "",
                          "m": model, "b": backend, "t": max_tokens},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()

def cached_call(inner_fn, prompt, api_key, model, max_tokens,
                system_prompt, ttl=86_400, **kwargs) -> str:
    if os.getenv("ENABLE_LLM_CACHE", "true").lower() != "true":
        return inner_fn(prompt, api_key, model, max_tokens,
                        system_prompt, **kwargs)
    backend = os.getenv("LLM_BACKEND", "anthropic")
    key = make_cache_key(prompt, system_prompt, model, backend, max_tokens)
    cache = _get_cache()
    if key in cache:
        logger.debug(f"LLM cache HIT  key={key[:10]}")
        return cache[key]
    result = inner_fn(prompt, api_key, model, max_tokens,
                      system_prompt, **kwargs)
    cache.set(key, result, expire=ttl)
    logger.debug(f"LLM cache MISS stored key={key[:10]}")
    return result

# llm_client.py — wrap the dispatcher
from agents.cache import cached_call

def call_llm(prompt, api_key, model, max_tokens=2000,
             system_prompt=None, use_thinking=True) -> str:
    return cached_call(_dispatch_llm, prompt, api_key, model,
                       max_tokens, system_prompt,
                       use_thinking=use_thinking)"""),

        ("Snippet 3", "Async Per-Cluster Summaries",
         "segmentation_agent.py — replace generate_rich_segment_summaries (~line 721)",
"""import asyncio
from concurrent.futures import ThreadPoolExecutor

_summary_executor = ThreadPoolExecutor(
    max_workers=6, thread_name_prefix="seg_summary")

async def _run_all_summaries(profiles, api_key, model, labels,
                              dq_context, priority_context) -> dict:
    max_concurrent = int(os.getenv("SEGMENT_SUMMARY_MAX_WORKERS", "3"))
    semaphore = asyncio.Semaphore(max_concurrent)
    loop = asyncio.get_event_loop()

    async def _one(p):
        cid = p["cluster_id"]
        label_info = (labels or {}).get(cid, {})
        async with semaphore:   # max 3 concurrent LLM calls
            try:
                summary = await loop.run_in_executor(
                    _summary_executor,
                    lambda: generate_segment_summary(
                        p, profiles, api_key, model,
                        label_info=label_info,
                        dq_context=dq_context,
                        priority_context=priority_context,
                    )
                )
                return cid, summary
            except Exception as e:
                logger.warning(f"Summary for cluster {cid} failed: {e}")
                return cid, _empty_rich_summary()

    results = await asyncio.gather(*[_one(p) for p in profiles])
    return dict(results)

def generate_rich_segment_summaries(profiles, api_key, model,
                                     labels=None, dq_context=None,
                                     priority_context=None) -> dict:
    # No more sleep() — asyncio semaphore controls concurrency
    return asyncio.run(_run_all_summaries(
        profiles, api_key, model, labels, dq_context, priority_context
    ))"""),

        ("Snippet 4", "Pydantic DQ Verdict + Pipeline Gate",
         "agents/schemas.py (new) + dq_agent.py:211 + pipeline.py:292",
"""# agents/schemas.py
from pydantic import BaseModel, Field
from typing import Literal, List

class DQVerdict(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    bullets: List[str] = []
    raw_text: str = ""

    @classmethod
    def from_llm_text(cls, text: str) -> "DQVerdict":
        verdict = "PASS" if "VERDICT: PASS" in text.upper() else "FAIL"
        bullets = [l.strip().lstrip("*•- ")
                   for l in text.split("\\n")
                   if l.strip() and l.strip()[0] in "*•-"]
        return cls(verdict=verdict, bullets=bullets, raw_text=text)

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"

# dq_agent.py — updated return type
def get_claude_dq_verdict(dq_results, df_summary, api_key, model) -> DQVerdict:
    text = call_llm(prompt, api_key, model, max_tokens=1024,
                    system_prompt=_ctx.build("dq"), use_thinking=False)
    return DQVerdict.from_llm_text(text)

# pipeline.py — add gate (after line 294)
REQUIRE_DQ_PASS = os.getenv("REQUIRE_DQ_PASS", "true").lower() == "true"
dq_verdict = get_claude_dq_verdict(dq_results, df_summary, api_key, model)
logger.info(f"DQ verdict: {dq_verdict.verdict}")
if not dq_verdict.passed and REQUIRE_DQ_PASS:
    logger.error("Pipeline halted: DQ FAIL. "
                 "Set REQUIRE_DQ_PASS=false to override.")
    raise RuntimeError(f"DQ gate failed:\\n{dq_verdict.raw_text}")"""),

        ("Snippet 5", "Vectorized Numeric Coercion",
         "segmentation_agent.py:173 + prioritization_agent.py:278",
"""def _coerce_column_to_numeric(series: pd.Series) -> pd.Series:
    \"\"\"
    Vectorized coercion — ~100-1000x faster than series.apply()
    on 900k-row DataFrames. Handles hex strings as a targeted fallback.
    \"\"\"
    # Fast path: pandas vectorized handles int, float, numeric strings,
    # scientific notation — covers 99%+ of real data
    result = pd.to_numeric(series, errors="coerce")

    # Slow path: only for non-null values that failed vectorized coercion
    # (i.e., genuinely unparseable — typically hex strings like '0x2a')
    needs_check = result.isna() & series.notna()
    if needs_check.any():
        str_vals = series[needs_check].astype(str).str.strip().str.lower()
        hex_mask = str_vals.str.startswith("0x")
        if hex_mask.any():
            def _try_hex(s: str) -> float:
                try:
                    return float(int(s, 16))
                except (ValueError, OverflowError):
                    return float("nan")
            hex_vals = str_vals[hex_mask].apply(_try_hex)
            result.loc[hex_vals.index] = hex_vals
    return result
# Benchmark: 900k rows × 30 features
# Before (series.apply): ~180 seconds
# After  (vectorized):   ~1.8 seconds"""),
    ]

    for num, title, location, code in snippets:
        elems.append(KeepTogether([
            h3(f"{num}: {title}", styles),
            Paragraph(f"<i>Location: {location}</i>", styles["caption"]),
        ]))
        elems.append(code_block(code, styles))
        elems.append(sp(2))

    elems.append(PageBreak())
    return elems


def section_architecture(styles):
    elems = [h1("Proposed Target Architecture", styles), sp(2)]
    elems.append(body(
        "The diagram below describes the recommended agentic DAG with critic gates, "
        "async fan-out for summaries, per-bucket parallelism for MSL/Space, "
        "and a three-layer cache intercepting every LLM call.",
        styles))
    elems.append(sp(2))

    arch_data = [
        ["Component", "Type", "LLM Calls", "Cache Layer", "Critic Gate"],
        ["File Watcher / CLI",    "Trigger",    "0",   "—",                  "—"],
        ["PipelineState",         "Pydantic",   "0",   "—",                  "Schema validation"],
        ["DQ Agent",              "Agent",      "1",   "Response cache",      "PASS/FAIL gate"],
        ["Prioritization Tool",   "Tool",       "1",   "Response + artifact", "—"],
        ["KMeans Tool",           "Tool",       "0",   "Artifact (parquet)",  "—"],
        ["Cluster Label Tool",    "Tool",       "1",   "Response cache",      "JSON schema + retry"],
        ["Rich Summary Tool",     "Async×6",    "6",   "Response cache",      "Section completeness"],
        ["MSL Tool",              "Tool×4",     "4",   "Response cache",      "Hero count > 0"],
        ["Space Allocation Tool", "Tool×4",     "4",   "Response cache",      "—"],
        ["Output Agent",          "Agent",      "0",   "—",                  "—"],
        ["TOTAL",                 "17 calls",   "17",  "3-layer cache",       "3 critic gates"],
    ]
    t = Table(arch_data, colWidths=[42*mm, 22*mm, 22*mm, 42*mm, 38*mm],
              repeatRows=1)
    s = table_style_base()
    s.append(("FONTNAME",   (0, 11), (-1, 11), "Helvetica-Bold"))
    s.append(("BACKGROUND", (0, 11), (-1, 11), NAVY))
    s.append(("TEXTCOLOR",  (0, 11), (-1, 11), WHITE))
    t.setStyle(TableStyle(s))
    elems.append(t)
    elems.append(sp(3))

    elems.append(h3("Data & Control Flow", styles))
    elems.append(body(
        "1. <b>File Watcher</b> (watcher.py) detects new CSV in inbox/, moves to processing/, "
        "triggers pipeline with a run_id (UUID).",
        styles))
    elems.append(body(
        "2. <b>PipelineState</b> (Pydantic BaseModel) is initialised with run_id and file_path. "
        "All agent results are stored here — enables checkpoint-based recovery.",
        styles))
    elems.append(body(
        "3. <b>DQ Agent</b> runs 7 rule checks, sends compact result JSON to LLM. "
        "CriticAgent validates DQVerdict schema. If FAIL and REQUIRE_DQ_PASS=true, pipeline halts.",
        styles))
    elems.append(body(
        "4. <b>Prioritization Tool</b> runs quantile regression, checkpoints result to parquet, "
        "then calls LLM for narrative. Checkpoint allows skip on re-run.",
        styles))
    elems.append(body(
        "5. <b>KMeans Tool</b> clusters outlets. If AUTO_CLUSTER_K=true, "
        "silhouette scoring selects optimal k. Centroid artifact cached.",
        styles))
    elems.append(body(
        "6. <b>Cluster Label Tool</b> calls LLM with response_schema JSON enforcement. "
        "CriticAgent validates all n_clusters labels are present and schema-compliant. "
        "Retries once if validation fails.",
        styles))
    elems.append(body(
        "7. <b>Rich Summary Tool</b> fans out to 6 async tasks with Semaphore(3). "
        "Each task uses diskcache — on re-run, all 6 are cache hits.",
        styles))
    elems.append(body(
        "8. <b>MSL Tool + Space Tool</b> run per bucket. "
        "Both benefit from response cache on re-runs with same outlet/SKU data.",
        styles))
    elems.append(body(
        "9. <b>Output Agent</b> assembles CSV + Excel + PDF from PipelineState. "
        "Adds fallback warning banners to any section that used LLM fallback.",
        styles))
    elems.append(sp(2))

    elems.append(h3("Three-Layer Cache Intercept", styles))
    cache_flow = [
        ["Layer", "Intercepts", "Key", "Hit Rate Estimate"],
        ["1. Response cache (diskcache)", "All 17 LLM calls",
         "sha256(prompt+system+model+backend+tokens)", "~80% on re-runs"],
        ["2. Vertex context cache (server-side)", "System prompt prefix per call",
         "sha256(model+system_prompt)[:16]", "~100% within process"],
        ["3. Artifact cache (parquet)", "Regression + clustering outputs",
         "sha256(df_hash+stage)", "~90% on iterative debug runs"],
    ]
    elems.append(make_table(cache_flow[0], cache_flow[1:],
                            [45*mm, 38*mm, 55*mm, 30*mm]))
    elems.append(PageBreak())
    return elems


def section_roadmap(styles):
    elems = [h1("Prioritized Roadmap", styles), sp(2)]

    weeks = [
        ("Week 1 — Zero-Risk, High-ROI Fixes (< 1 hour each)", NAVY, [
            ["#", "Task", "File(s)", "Lines Changed", "Impact"],
            ["1", "Add context cache to _call_vertex_gemini",
             "llm_client.py", "8", "$0.0074/run"],
            ["2", "Move ContextLoader() to module level in msl_generator",
             "msl_generator.py", "3", "Correctness"],
            ["3", "Disable use_thinking on DQ, MSL, space-alloc",
             "llm_client.py + 3 callers", "12", "$0.0055/run"],
            ["4", "Strip §6/§10/§11 code from segmentation.md",
             "segmentation.md", "−170 lines", "$0.0016/run"],
            ["5", "Add .gitignore (.env, outputs/, .llm_cache/)",
             ".gitignore (new)", "12", "Security"],
            ["6", "Add DQ gate (REQUIRE_DQ_PASS env var)",
             "pipeline.py", "6", "Data integrity"],
            ["7", "Add missing deps + pin versions in requirements.txt",
             "requirements.txt", "10", "Reproducibility"],
        ]),
        ("Week 2 — Medium Effort, High Value", BLUE, [
            ["#", "Task", "File(s)", "Lines", "Impact"],
            ["8",  "Add diskcache LLM response cache",
             "agents/cache.py (new), llm_client.py", "50", "$0.032/re-run"],
            ["9",  "Replace ThreadPoolExecutor+sleep with asyncio",
             "segmentation_agent.py", "40", "−25s latency"],
            ["10", "Add agents/schemas.py with Pydantic models",
             "agents/schemas.py (new)", "80", "Reliability"],
            ["11", "Vectorize _coerce_column_to_numeric",
             "segmentation_agent.py,\nprioritization_agent.py", "20",
             "−2 min compute"],
            ["12", "Add use_thinking param to call_llm and callers",
             "llm_client.py + 5 files", "30", "Cost + correctness"],
            ["13", "Adaptive MSL row count (60 → coverage-based)",
             "msl_generator.py", "20", "Token savings"],
        ]),
        ("Week 3+ — Architectural Improvements", HexColor("#375623"), [
            ["#", "Task", "File(s)", "Lines", "Impact"],
            ["14", "Stage checkpointing with parquet artifacts",
             "agents/checkpoint.py (new),\npipeline.py", "80",
             "Fault tolerance"],
            ["15", "config/prompts.yaml + pydantic-settings loader",
             "config/prompts.yaml (new)", "60", "Maintainability"],
            ["16", "Gemini response_schema for cluster labeling",
             "agents/schemas.py, llm_client.py", "40", "Reliability"],
            ["17", "Persist Gemini context cache to SQLite",
             "llm_client.py", "30", "Cost across restarts"],
            ["18", "Unit tests ≥80% coverage on deterministic fns",
             "tests/ (new directory)", "200", "Correctness"],
            ["19", "Optional auto-k silhouette scoring",
             "segmentation_agent.py", "35", "Accuracy"],
            ["20", "structlog + run_id threading through all calls",
             "llm_client.py + all agents", "60", "Observability"],
            ["21", "Few-shot examples in context/examples/",
             "context/examples/\ncluster_labels.json (new)", "40",
             "LLM output quality"],
        ]),
    ]

    for title, hdr_color, rows in weeks:
        p = Paragraph(title, styles["roadmap_h"])
        p.style.backColor = hdr_color
        elems.append(p)
        t = Table(rows, colWidths=[8*mm, 65*mm, 40*mm, 22*mm, 32*mm],
                  repeatRows=1)
        ts = table_style_base()
        ts[0] = ("BACKGROUND", (0, 0), (-1, 0), hdr_color)
        t.setStyle(TableStyle(ts))
        elems.append(t)
        elems.append(sp(3))

    elems.append(PageBreak())
    return elems


def section_questions(styles):
    elems = [h1("Open Questions & Assumptions", styles), sp(2)]

    items = [
        ("Assumption",
         "MSL runs for all 4 priority buckets (A/B/C/D) per run = 4 LLM calls, "
         "and space allocation similarly = 4 calls. If some buckets are always empty "
         "in practice, the actual call count (and cost) is proportionally lower."),
        ("Assumption",
         "context/agents/space_allocation.md, msl.md, prioritization.md, and dq.md "
         "are proportionally smaller than segmentation.md (593 lines). "
         "If any are large, the token-savings estimates for Finding 3.2 are understated."),
        ("Question",
         "Is generate_sample_data.py generating the actual India_Synthetic_SKU_Data.csv "
         "used by MSL? If so, the synthetic data distribution is fully controlled, meaning "
         "MSL LLM outputs are highly cacheable (same data = same top-60 table = same response)."),
        ("Question",
         "Is the pipeline run once per client engagement (weekly/monthly cadence) or "
         "continuously (daily file drops)? If daily, the response cache TTL "
         "(suggested at 24h) should be tied to file fingerprint invalidation, not time."),
        ("Question",
         "The segmentation.md §9 example output uses placeholder SKU names like "
         "[Bev A 200ml] to avoid hardcoding brand names. Should real PepsiCo brand names "
         "(Lay's, Kurkure, Doritos, etc.) be used in the few-shot examples? "
         "Real names dramatically improve LLM output specificity."),
        ("Question",
         "Does the pipeline ever process multiple region files concurrently? "
         "The _gemini_cache_registry dict (module-level with threading.Lock) is correct "
         "within one process but would need Redis or SQLite if multiple processes "
         "run simultaneously against the same Vertex project."),
        ("Assumption",
         "context/agents/dq.md, msl.md, prioritization.md, and space_allocation.md "
         "were not read in full during this audit. If any contain Python code blocks "
         "(as segmentation.md does), apply Finding 3.2 (strip code blocks) to them as well."),
        ("Question",
         "Is there a preferred observability platform? The audit recommends structlog "
         "for structured logging. If LangSmith, Langfuse, or OpenTelemetry is already "
         "in the stack, the run_id threading approach in Finding 1.3 should emit spans "
         "directly to that platform instead."),
    ]

    for kind, text in items:
        color = ORANGE if kind == "Question" else BLUE
        elems.append(KeepTogether([
            Paragraph(
                f'<font color="{color.hexval() if hasattr(color,"hexval") else "#2E75B6"}">'
                f'<b>{kind}</b></font>', styles["h4"]),
            Paragraph(text, styles["body"]),
            sp(1),
        ]))

    elems.append(sp(4))
    elems.append(hr(NAVY, 1))
    elems.append(sp(2))
    elems.append(body(
        "<i>Audit prepared by Claude Sonnet 4.6 (Claude Code) · "
        f"{datetime.now().strftime('%B %d, %Y')} · "
        "Perfect Store Pipeline — Vertex AI Gemini 2.5 Flash backend · "
        "proj-psdesign-500716</i>",
        styles))
    return elems


# ── Page templates ────────────────────────────────────────────────────────────
def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    if doc.page > 1:
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(NAVY)
        canvas.drawString(MARGIN, h - 12 * mm,
                          "PERFECT STORE PIPELINE — COMPREHENSIVE AI AUDIT")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MID_GRAY)
        canvas.drawRightString(w - MARGIN, h - 12 * mm,
                               f"CONFIDENTIAL · {datetime.now().strftime('%Y-%m-%d')}")
        canvas.setStrokeColor(NAVY)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, h - 13 * mm, w - MARGIN, h - 13 * mm)

        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MID_GRAY)
        canvas.drawCentredString(w / 2, 10 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(HexColor("#CCCCCC"))
        canvas.setLineWidth(0.3)
        canvas.line(MARGIN, 13 * mm, w - MARGIN, 13 * mm)
    canvas.restoreState()


# ── Main ──────────────────────────────────────────────────────────────────────
def build_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="Perfect Store Pipeline — Comprehensive Agentic AI Audit",
        author="Claude Code (Claude Sonnet 4.6)",
        subject="Agentic AI Architecture Audit",
    )

    styles = build_styles()
    story = []

    story += cover_page(styles)
    story += toc_page(styles)
    story += exec_summary(styles)
    story += section1(styles)
    story += section2(styles)
    story += section3(styles)
    story += section4(styles)
    story += section5(styles)
    story += section6(styles)
    story += section7(styles)
    story += section8(styles)
    story += section_snippets(styles)
    story += section_architecture(styles)
    story += section_roadmap(styles)
    story += section_questions(styles)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    print(f"✓  PDF generated: {output_path}")
    return output_path


if __name__ == "__main__":
    out = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Perfect_Store_AI_Audit.pdf")
    build_pdf(out)
