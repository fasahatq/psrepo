# Perfect Store AI Workbench

A React/Vite front-end for the Perfect Store pipeline, wired to a thin FastAPI
backend. Runs entirely on localhost — nothing is deployed. The Streamlit control
panel in [`../gui/`](../gui/) is unaffected; this is a parallel UI.

```
workbench/
  src/App.jsx          the whole UI (one file, faithful to the original mockup)
  server/              FastAPI over pipeline.run_pipeline + agents.llm_client
  run_workbench.sh     starts API (:8020) + Vite (:5173) together
```

## Run

```bash
./workbench/run_workbench.sh        # installs deps on first run, then serves both
# open http://localhost:5173
```

Or start the two processes yourself:

```bash
venv/bin/pip install -r workbench/server/requirements.txt   # first time
venv/bin/python -m uvicorn workbench.server.app:app --port 8020 --reload
cd workbench && npm install && npm run dev
```

Vite proxies `/api/*` to the backend on `:8020`.

Nav is three sections: **Market Workspace**, **Output Studio**, **Agent Hub**.

## What is wired to real data

| Area | Source |
|---|---|
| **Market Workspace — Execute pipeline** | inline source-file picker → `POST /api/runs` → `pipeline.run_pipeline` on a background thread |
| **Market Workspace — horizontal pipeline** | `GET /api/runs/stream` (SSE) — 7 stage nodes light amber→green from step events; live log strip below |
| **Market Workspace — Recent outputs** | `GET /api/runs`; capped to ~2 rows, scrolls |
| **Market Workspace — Output preview** | `GET /api/runs/{id}/deck` → real slide PNGs (`soffice` .pptx→pdf, PyMuPDF rasterise, cached in `outputs/<run>/.deck_cache/`), shown in a scrollable strip |
| **Output Studio — Segmentation agent** | `segment_cards` from `segment_report*.xlsx` "Segment Cards" sheet — label, channel · occasion, growth, headline, Hero SKU chips |
| **Output Studio — MSL agent** | `top_skus` — Hero SKUs ranked by how many segments call them out |
| **Output Studio — Recommended assets** | each segment's "Merch & Space" Top Actions (chiller, POSM, planogram…) + KPI |
| **Output Studio — Charts / Deliverables** | `charts/*.png` and all run files with download links |
| **Agent Hub** | one card per `agents/*.py`; status from the last run, live during a run |
| **Copilot** | `POST /api/copilot` → `agents.llm_client.call_llm`, grounded on the selected run's summary. Uses whatever `LLM_BACKEND` is set in `.env` (currently `vertex` / `gemini-2.5-flash`) |
| **Add data** | `POST /api/inbox` — multipart upload into `inbox/` |

## Requirements

- Python deps: `venv/bin/pip install -r workbench/server/requirements.txt`
- **`soffice`** (LibreOffice, headless) on `PATH` for deck slide rendering:
  `sudo apt-get install -y --no-install-recommends libreoffice-impress libreoffice-core`.
  Without it, everything works except the deck preview (`/api/health` reports `deck_render: false`).

## Known limitations (by design)

- **No "market" field** in the data model — every run shows under *India*; the
  *Mexico* / *Brazil* workspaces are empty states.
- **One** pipeline run at a time (`POST /api/runs` returns `409` if one is active).
- Copilot needs valid Vertex ADC on the host.
- First deck preview for a run takes ~2–4 s (soffice conversion); then it's cached.

## API

`GET /api/health` · `GET|POST /api/inbox` · `GET /api/runs` · `POST /api/runs` ·
`GET /api/runs/active` · `GET /api/runs/stream` · `GET /api/runs/{id}` ·
`GET /api/runs/{id}/file/{name}` · `GET /api/runs/{id}/chart/{name}` ·
`GET /api/runs/{id}/deck` · `GET /api/runs/{id}/deck/{name}` ·
`POST /api/copilot` — full schema at `http://localhost:8020/docs`.
