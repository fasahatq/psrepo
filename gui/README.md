# Perfect Store — Pipeline GUI

A local **Streamlit** control panel for `pipeline.run_pipeline`. Runs in your
browser at `http://localhost:8501`; nothing is deployed or hosted.

## Run

```bash
pip install -r requirements.txt        # first time (adds streamlit)
./run_gui.sh                           # or: venv/bin/streamlit run gui/app.py
```

## What it does

| Panel | |
|---|---|
| **Sidebar** | Pick a source file from `inbox/`, set an optional row sample, hit **Run pipeline**. Files are auto-classified: a **dataset** has outlet columns (`OUTLET_UID_EDITED`, `VPO`, …) or SKU-transactional columns (`CUST_UNIQ_ID_VAL`, `NET_SALES`, …); anything else (pack dimensions, rack comparison) is flagged **reference** and the run is blocked unless you tick *Run anyway*. Default selection is `Market_Master_File.csv`. |
| **Run & progress** | The Perfect Store wheel — 5 wedges that go grey → amber (running) → green (done) as the 7 steps execute — a **vertical stepper** with per-step state, detail and elapsed time, and a **console-style log panel** (auto-scroll, level colouring, level filter, copy). Live panels refresh via `st.fragment` — no full-page reload. |
| **Outputs** | Browse every run in `outputs/<timestamp>/`: a **download strip** of artifact cards (deck/Excel/CSV with sizes; deck shows slide count), a segment summary with formatted tables + charts, the deck slide list, Excel workbooks (sheet-by-sheet), segment CSVs and PNG charts. |

The app has a branded header with a live status pill (Idle / Running / Complete /
Failed), Streamlit's default chrome hidden, and remembers the selected file,
sample size and active view across reruns (via URL query params).

## Step → wheel mapping (`gui/steps.py`)

| Wheel wedge | Pipeline steps |
|---|---|
| Segmentation & Prioritization | 1 Load · 2 DQ · 3 Prioritization · 4 Segmentation |
| Shopper Value Offer | 5 MSL generation |
| Retail Value Offer | 7 Space allocation |
| Picture of Success | 6 Generate outputs |
| Execution & Tracking | whole-run completion + artifacts |

## How progress is wired

`run_pipeline(..., progress_callback=fn)` calls `fn(step, name, status, detail)`
as each step starts/finishes (`status` ∈ `start | running | done`).
`gui/runner.py` runs the pipeline on a background thread and forwards those
events plus `perfect_store.*` log records through a queue; `gui/app.py` drains
the queue on a ~1.2 s refresh while a run is active. The callback is optional —
CLI (`python main.py run …`) and the watcher are unaffected.

## Files

```
gui/app.py       Streamlit entry point
gui/ui.py        shared CSS + components (header, stepper, console, callouts, cards)
gui/wheel.py     the live SVG wheel
gui/runner.py    background pipeline runner + log capture
gui/outputs.py   artifact discovery + viewers
gui/steps.py     step ↔ wedge mapping and labels
```
