# Perfect Store — Agentic AI Pipeline

An end-to-end, LLM-assisted pipeline that turns raw store-level CPG data into
**Perfect Store** execution deliverables: store segments, A/B/C/D prioritization,
Must-Stock Lists, planogram space allocation, and executive PDF/Excel reports.

Perfect Store is a CPG commercial-execution framework that answers three questions:

1. **Which stores matter most?** → segmentation + prioritization
2. **What should happen in those stores?** → MSL, shopper value offer, space
3. **Are we executing well?** → scorecards and reports

See [`context/project.md`](context/project.md) for the full framework, glossary,
and metric definitions.

---

## Pipeline stages

`pipeline.run_pipeline()` runs seven sequential steps (each emits a `Step N/7`
log line and a progress event):

| # | Step | Agent | Output |
|---|------|-------|--------|
| 1 | Load data | `pipeline.load_data` | normalised DataFrame (chunked for 900k+ rows; transactional SKU files are auto-aggregated to one row per outlet) |
| 2 | Data-quality checks | `agents/dq_agent.py` | pass/fail checks + LLM verdict → `logs/dq_report_*.txt` |
| 3 | Prioritization | `agents/prioritization_agent.py` | A/B/C/D tiers by VPO percentile, 75th-percentile quantile-regression potential, opportunity gap → `logs/priority_narrative_*.txt` |
| 4 | Segmentation | `agents/segmentation_agent.py` | K-means clusters on sales / attributes / demographics / proximity / SKU mix, LLM-labelled in trade terms |
| 5 | MSL generation | `agents/msl_generator.py` | `MSL_Priority_Buckets_*.xlsx` — one Must-Stock sheet per priority bucket |
| 6 | Outputs | `agents/output_agent.py` | segment CSVs, `segment_report_*.xlsx`, `priority_report_*.xlsx`, `perfect_store_report_*.pdf`, charts |
| 7 | Space allocation | `agents/space_allocation_agent.py` | `Space_Allocation_*.xlsx` — rack facings + asset recommendations per bucket |

LLM calls go through `agents/llm_client.py`, which supports several backends
(see [LLM backends](#llm-backends)). Prompt grounding comes from
`context/project.md` plus per-agent files in `context/agents/`.

---

## Repository layout

```
main.py                 CLI entry point (watch / run / process-inbox / generate-sample)
pipeline.py             the 7-step orchestrator
agents/                 one module per stage + llm_client, context_loader, watcher
context/
  project.md            Perfect Store framework + glossary (always loaded into prompts)
  agents/*.md           per-agent prompt context
gui/                    Streamlit control panel — see gui/README.md
config/config.json      column mapping, DQ thresholds, segmentation features
scripts/                standalone helpers (sample data, synthetic SKU, audit/week-1 PDFs, trim)
docs/                   architecture & solution decks (.pptx)
inbox/                  input data files  (tracked)
processing/             transient copies of files being processed  (git-ignored)
outputs/<timestamp>/    all generated deliverables per run  (git-ignored)
logs/                   DQ reports, priority narratives, pipeline.log  (git-ignored)
.env                    LLM backend + credentials  (git-ignored; copy from .env.template)
```

> `outputs/`, `logs/`, and `processing/` are **not** version-controlled — every
> run recreates them locally.

---

## Quick start

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.template .env        # then edit — pick an LLM backend (see below)
```

Put a data file in `inbox/` (e.g. `Market_Master_File.csv`), then either:

### Command line

```bash
python main.py run inbox/Market_Master_File.csv   # process one file
python main.py process-inbox                       # process everything in inbox/
python main.py watch                               # watch inbox/ and process new arrivals
python main.py generate-sample                     # write inbox/sample_cpg_data.csv for testing
```

### GUI (Streamlit)

```bash
./run_gui.sh            # or: venv/bin/streamlit run gui/app.py
```

Opens a local dashboard at `http://localhost:8501` with a live Perfect Store
wheel, per-step progress, streaming logs, and a browser for every run's outputs.
Details in [`gui/README.md`](gui/README.md).

---

## Inputs

| File (in `inbox/`) | Role |
|---|---|
| `Market_Master_File.csv` | **Primary input** — flat outlet data, one row per store (`OUTLET_UID_EDITED`, `VPO`, `TOTAL_REVENUE`, `AVG_SKU`, …) |
| `India_Synthetic_SKU_Data.csv` | Alternative input — store × SKU transactional file; auto-aggregated to outlet level and enriched from the master file |
| `CPG_Pack_Dimensions_cm.xlsx` | Pack dimensions, used by step 7 (space allocation) |
| `CPG_Rack_Comparison.xlsx` | Rack/asset catalogue, used by step 7 |

A run needs one primary/alternative input; the two `CPG_*` files are reference
data consumed internally.

## Outputs

Each run writes to `outputs/<YYYYMMDD_HHMMSS>/`:

- `all_segments_*.csv` and `segment_<n>_<label>_*.csv` — labelled outlets
- `segment_report_*.xlsx` — segment workbook with a chart per segment
- `priority_report_*.xlsx` — A/B/C/D distribution and potential vs. actual
- `MSL_Priority_Buckets_*.xlsx` — Must-Stock List per bucket
- `Space_Allocation_*.xlsx` — rack facings and asset counts
- `perfect_store_report_*.pdf` — executive narrative
- `charts/` — radar, bar, bubble and heatmap PNGs

DQ reports and priority narratives land in `logs/`.

---

## Configuration

`config/config.json`:

| Key | Purpose |
|---|---|
| `data_mode` | `flat_outlet` (default) or `transactional` |
| `sku_file` | SKU file joined during MSL generation |
| `columns` | maps logical fields (`monthly_revenue`, `state`, …) to actual column names |
| `dq_checks` | required columns, null threshold, outlier multiplier |
| `segmentation` | `n_clusters`, numeric/categorical/label feature lists, chunk size |

Behaviour flags via `.env`:

- `DQ_HALT_ON_FAIL=1` — abort the run when the DQ verdict is FAIL (default: warn and continue)

---

## LLM backends

Set `LLM_BACKEND` in `.env` (see `.env.template` for the full settings per backend):

| Value | Uses | Auth |
|---|---|---|
| `anthropic` | Claude via Anthropic API | `ANTHROPIC_API_KEY` |
| `azure` | Azure OpenAI Service | `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_DEPLOYMENT` |
| `gemini` | Gemini via Google AI API | `GEMINI_API_KEY` |
| `vertex` | Gemini/Claude via Vertex AI | Application Default Credentials (`gcloud auth application-default login`) |
| `local` | Ollama on localhost | none — `ollama pull gemma3:12b` |

If no backend is configured the pipeline still runs, falling back to rule-based
DQ and narrative text.

---

## Requirements

Python 3.10+ and the packages in [`requirements.txt`](requirements.txt)
(pandas, scikit-learn, statsmodels, openpyxl/xlsxwriter, reportlab, matplotlib,
watchdog, the LLM SDKs, and streamlit for the GUI).
