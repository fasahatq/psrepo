"""Run ``pipeline.run_pipeline`` on a background thread and expose its progress
(step events + log lines) through a thread-safe queue.

Adapted almost verbatim from ``gui/runner.py`` — that class is already
framework-agnostic. The only additions here are a module-level singleton
(``current_run`` / ``start_run``) and an ``events()`` generator the SSE endpoint
can iterate.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import traceback
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _QueueLogHandler(logging.Handler):
    """Push every ``perfect_store.*`` log record onto the shared queue."""

    def __init__(self, q: "queue.Queue") -> None:
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.q.put({
                "kind": "log",
                "level": record.levelname,
                "name": record.name.replace("perfect_store.", ""),
                "msg": record.getMessage(),
                "ts": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
            })
        except Exception:
            pass


class PipelineRunner:
    """One pipeline execution. Create, ``start(...)``, then poll ``drain()`` or
    iterate ``events()`` until ``finished`` is set."""

    def __init__(self) -> None:
        self.q: "queue.Queue[dict]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self.finished = threading.Event()
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.result: dict | None = None
        self.error: str | None = None
        self.run_id: str | None = None
        self.output_dir: str | None = None
        self.source_file: str | None = None
        self.sample_size: int | None = None
        self.meta: dict = {}
        self._cancel = threading.Event()
        self.aborted = False
        # replayable history so a client that connects mid-run still gets the
        # full picture.
        self._history: list[dict] = []
        self._history_lock = threading.Lock()

    # -- callback handed to run_pipeline -------------------------------------
    def _on_step(self, step: int, name: str, status: str, detail: str = "") -> None:
        if step == 0 and status == "start":
            try:
                meta = json.loads(detail or "{}")
                self.run_id = meta.get("run_id")
                self.output_dir = meta.get("output_dir")
                self.meta = meta
                self._emit({"kind": "init", "meta": meta})
            except Exception:
                pass
            return
        self._emit({"kind": "step", "step": step, "name": name,
                    "status": status, "detail": detail})

    def _emit(self, ev: dict) -> None:
        with self._history_lock:
            self._history.append(ev)
        self.q.put(ev)

    # -- lifecycle -----------------------------------------------------------
    def start(self, file_path: str, sample_size: int | None) -> None:
        from pipeline import run_pipeline, PipelineAborted

        self.source_file = os.path.basename(file_path)
        self.sample_size = sample_size
        self.started_at = datetime.now()
        handler = _QueueLogHandler(self.q)
        handler.setLevel(logging.INFO)
        ps_logger = logging.getLogger("perfect_store")

        # Mirror perfect_store.* logs into _history too (via a second tiny handler).
        hist_handler = logging.Handler()
        hist_handler.setLevel(logging.INFO)

        def _hist_emit(record: logging.LogRecord) -> None:
            try:
                with self._history_lock:
                    self._history.append({
                        "kind": "log",
                        "level": record.levelname,
                        "name": record.name.replace("perfect_store.", ""),
                        "msg": record.getMessage(),
                        "ts": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                    })
            except Exception:
                pass

        hist_handler.emit = _hist_emit  # type: ignore[method-assign]

        def _target() -> None:
            ps_logger.addHandler(handler)
            ps_logger.addHandler(hist_handler)
            try:
                self.result = run_pipeline(
                    file_path, PROJECT_ROOT,
                    sample_size=sample_size,
                    progress_callback=self._on_step,
                    cancel_check=self._cancel.is_set,
                )
            except PipelineAborted as exc:
                self.aborted = True
                self._emit({"kind": "log", "level": "WARNING", "name": "pipeline",
                            "msg": str(exc),
                            "ts": datetime.now().strftime("%H:%M:%S")})
            except Exception:
                self.error = traceback.format_exc()
                self._emit({"kind": "log", "level": "ERROR", "name": "pipeline",
                            "msg": "Pipeline crashed — see traceback below",
                            "ts": datetime.now().strftime("%H:%M:%S")})
            finally:
                ps_logger.removeHandler(handler)
                ps_logger.removeHandler(hist_handler)
                self.ended_at = datetime.now()
                if self.result:
                    self.output_dir = self.result.get("output_dir", self.output_dir)
                self.finished.set()
                self._emit({"kind": "end", "error": bool(self.error),
                            "aborted": self.aborted,
                            "traceback": self.error or "",
                            "output_dir": os.path.basename(self.output_dir)
                            if self.output_dir else None})

        self._thread = threading.Thread(target=_target, name="perfect-store-run",
                                        daemon=True)
        self._thread.start()

    def drain(self) -> list[dict]:
        events: list[dict] = []
        while True:
            try:
                events.append(self.q.get_nowait())
            except queue.Empty:
                break
        return events

    def history(self) -> list[dict]:
        with self._history_lock:
            return list(self._history)

    def events(self, poll: float = 0.4):
        """Yield every event: the replayed history first, then live events until
        an ``end`` event is seen. Safe to call from an SSE handler."""
        seen = 0
        hist = self.history()
        for ev in hist:
            seen += 1
            yield ev
            if ev.get("kind") == "end":
                return
        while True:
            hist = self.history()
            for ev in hist[seen:]:
                seen += 1
                yield ev
                if ev.get("kind") == "end":
                    return
            if self.finished.is_set():
                # flush anything appended between the slice and the flag
                hist = self.history()
                for ev in hist[seen:]:
                    seen += 1
                    yield ev
                return
            time.sleep(poll)

    def cancel(self) -> None:
        """Request a cooperative abort. The pipeline stops at its next step
        boundary and raises PipelineAborted, which _target catches."""
        self._cancel.set()

    @property
    def cancelling(self) -> bool:
        return self._cancel.is_set() and not self.finished.is_set()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def status(self) -> str:
        if self.is_running:
            return "running"
        if self.aborted:
            return "aborted"
        if self.error:
            return "failed"
        if self.finished.is_set():
            return "done"
        return "idle"

    @property
    def elapsed_secs(self) -> int:
        if not self.started_at:
            return 0
        end = self.ended_at or datetime.now()
        return int((end - self.started_at).total_seconds())

    def snapshot(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "source_file": self.source_file,
            "sample_size": self.sample_size,
            "output_dir": os.path.basename(self.output_dir) if self.output_dir else None,
            "elapsed_secs": self.elapsed_secs,
            "meta": self.meta,
            "error": self.error,
            "aborted": self.aborted,
        }


# ── module-level singleton ────────────────────────────────────────────────────
_current: PipelineRunner | None = None
_lock = threading.Lock()


def current_run() -> PipelineRunner | None:
    return _current


def start_run(file_path: str, sample_size: int | None) -> PipelineRunner:
    """Start a run. Raises RuntimeError if one is already in flight."""
    global _current
    with _lock:
        if _current is not None and _current.is_running:
            raise RuntimeError("a pipeline run is already in progress")
        runner = PipelineRunner()
        _current = runner
    runner.start(file_path, sample_size)
    return runner
