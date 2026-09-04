"""Perfect Store AI Workbench — FastAPI backend.

    venv/bin/uvicorn workbench.server.app:app --port 8020 --reload

A thin API over the existing pipeline. Nothing here is deployed; it runs on
localhost alongside the Vite dev server (which proxies /api to :8020).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from workbench.server import artifacts, copilot, deck  # noqa: E402
from workbench.server.runner import current_run, start_run  # noqa: E402

app = FastAPI(title="Perfect Store AI Workbench API", version="1.0.0")

# Vite dev server origin — harmless on localhost, convenient if the proxy is off.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INBOX_DIR = Path(PROJECT_ROOT) / "inbox"


# ── models ───────────────────────────────────────────────────────────────────
class StartRunBody(BaseModel):
    file: str
    sample_size: int | None = 5000


class CopilotBody(BaseModel):
    messages: list[dict]
    run_id: str | None = None


# ── meta ─────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict:
    backend, _, model = copilot._resolve_model()
    return {"status": "ok", "llm_backend": backend, "model": model,
            "deck_render": deck.has_soffice(), "project_root": PROJECT_ROOT}


# ── inbox ────────────────────────────────────────────────────────────────────
@app.get("/api/inbox")
def get_inbox() -> list[dict]:
    return artifacts.scan_inbox()


@app.post("/api/inbox")
async def upload_inbox(file: UploadFile = File(...)) -> dict:
    name = os.path.basename(file.filename or "upload.csv")
    if Path(name).suffix.lower() not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(400, "only .csv / .xlsx / .xls files are accepted")
    INBOX_DIR.mkdir(exist_ok=True)
    dest = INBOX_DIR / name
    dest.write_bytes(await file.read())
    return {"name": name, "size": dest.stat().st_size}


# ── runs ─────────────────────────────────────────────────────────────────────
@app.get("/api/runs")
def get_runs() -> list[dict]:
    return [artifacts.run_brief(d) for d in artifacts.list_runs()]


@app.get("/api/runs/active")
def get_active_run() -> dict:
    r = current_run()
    if r is None:
        return {"status": "idle"}
    return r.snapshot()


@app.get("/api/runs/stream")
def stream_run() -> StreamingResponse:
    r = current_run()

    def gen():
        if r is None:
            yield _sse({"kind": "idle"})
            return
        try:
            for ev in r.events():
                yield _sse(ev)
        except GeneratorExit:  # client disconnected
            return

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.post("/api/runs", status_code=202)
def post_run(body: StartRunBody) -> dict:
    entries = {e["name"] for e in artifacts.scan_inbox()}
    if body.file not in entries:
        raise HTTPException(404, f"{body.file} is not in inbox/")

    processing = Path(PROJECT_ROOT) / "processing"
    processing.mkdir(exist_ok=True)
    src = processing / body.file
    src.write_bytes((INBOX_DIR / body.file).read_bytes())

    try:
        runner = start_run(str(src), body.sample_size or None)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return runner.snapshot()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    try:
        return artifacts.run_detail(run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"run {run_id} not found")


@app.get("/api/runs/{run_id}/file/{name}")
def get_run_file(run_id: str, name: str) -> FileResponse:
    try:
        p = artifacts.artifact_path(run_id, name)
    except FileNotFoundError:
        raise HTTPException(404, "artifact not found")
    return FileResponse(p, media_type=artifacts.mime_for(name), filename=p.name)


@app.get("/api/runs/{run_id}/chart/{name}")
def get_run_chart(run_id: str, name: str) -> FileResponse:
    try:
        p = artifacts.chart_path(run_id, name)
    except FileNotFoundError:
        raise HTTPException(404, "chart not found")
    return FileResponse(p, media_type="image/png")


@app.get("/api/runs/{run_id}/deck")
def get_run_deck(run_id: str) -> dict:
    try:
        artifacts._run_dir(run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"run {run_id} not found")
    try:
        return deck.render(run_id)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@app.get("/api/runs/{run_id}/deck/{name}")
def get_run_slide(run_id: str, name: str) -> FileResponse:
    try:
        p = deck.slide_path(run_id, name)
    except FileNotFoundError:
        raise HTTPException(404, "slide not found")
    return FileResponse(p, media_type="image/png")


# ── copilot ──────────────────────────────────────────────────────────────────
@app.post("/api/copilot")
def post_copilot(body: CopilotBody) -> dict:
    if not body.messages:
        raise HTTPException(400, "messages is empty")
    return copilot.answer(body.messages, body.run_id)


# ── helpers ──────────────────────────────────────────────────────────────────
def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"
