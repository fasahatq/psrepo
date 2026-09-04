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

## What is wired to real data

| Area | Source |
|---|---|
| **Command Center** metrics, Recent outputs | `GET /api/runs` — the folders in `outputs/<timestamp>/` |
| **Output Studio** | `GET /api/runs/{id}` — real artifacts, sizes, deck slide titles, `all_segments*.csv` summary, PNG charts, downloads |
| **New analysis** | `POST /api/runs` → `pipeline.run_pipeline` on a background thread |
| **Live Run** view | `GET /api/runs/stream` (SSE) — step events + `perfect_store.*` logs |
| **Agent Hub** | one card per `agents/*.py`; status from the last run, live during a run |
| **Copilot** | `POST /api/copilot` → `agents.llm_client.call_llm`, grounded on the selected run's summary. Uses whatever `LLM_BACKEND` is set in `.env` (currently `vertex` / `gemini-2.5-flash`) |
| **Add data** | `POST /api/inbox` — multipart upload into `inbox/` |

## Known limitations (by design, see the plan)

- **No "market" field** in the data model — every run shows under *India*; the
  *Mexico* / *Brazil* workspaces are empty states.
- **Approvals** are stored in `localStorage` only (no server-side approval store).
- **Monitoring Hub** shows real run history; the adoption % / in-market impact
  tiles have no feedback source and are labelled as not wired.
- **One** pipeline run at a time (`POST /api/runs` returns `409` if one is active).
- Copilot needs valid Vertex ADC on the host.

## API

`GET /api/health` · `GET|POST /api/inbox` · `GET /api/runs` · `POST /api/runs` ·
`GET /api/runs/active` · `GET /api/runs/stream` · `GET /api/runs/{id}` ·
`GET /api/runs/{id}/file/{name}` · `GET /api/runs/{id}/chart/{name}` ·
`POST /api/copilot` — full schema at `http://localhost:8020/docs`.
