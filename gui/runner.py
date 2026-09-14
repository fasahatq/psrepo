"""Run pipeline.run_pipeline on a background thread and expose its progress
(step events + log lines) to the Streamlit UI through a thread-safe queue.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import traceback
from datetime import datetime


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
    """One pipeline execution. Create, ``start(...)``, then poll ``drain()`` each
    Streamlit rerun until ``finished`` is set."""

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
        self._cancel = threading.Event()
        self.aborted = False

    # -- callback handed to run_pipeline -------------------------------------
    def _on_step(self, step: int, name: str, status: str, detail: str = "") -> None:
        if step == 0 and status == "start":
            try:
                meta = json.loads(detail or "{}")
                self.run_id = meta.get("run_id")
                self.output_dir = meta.get("output_dir")
                self.q.put({"kind": "init", "meta": meta})
            except Exception:
                pass
            return
        self.q.put({"kind": "step", "step": step, "name": name,
                    "status": status, "detail": detail})

    # -- lifecycle --------------------------------------------------------------
    def start(self, file_path: str, project_root: str,
              sample_size: int | None) -> None:
        from pipeline import run_pipeline, PipelineAborted

        self.started_at = datetime.now()
        handler = _QueueLogHandler(self.q)
        handler.setLevel(logging.INFO)
        ps_logger = logging.getLogger("perfect_store")
        # Streamlit never calls logging.basicConfig (only main.py's CLI path does),
        # so the logger's effective level defaults to WARNING and every
        # logger.info(...) call was silently dropped before reaching the live log
        # panel below. Same gap as workbench/server/runner.py — fixed there too.
        ps_logger.setLevel(logging.INFO)

        def _target() -> None:
            ps_logger.addHandler(handler)
            try:
                self.result = run_pipeline(
                    file_path, project_root,
                    sample_size=sample_size,
                    progress_callback=self._on_step,
                    cancel_check=self._cancel.is_set,
                )
            except PipelineAborted as exc:
                self.aborted = True
                self.q.put({"kind": "log", "level": "WARNING", "name": "pipeline",
                            "msg": str(exc),
                            "ts": datetime.now().strftime("%H:%M:%S")})
            except Exception:
                self.error = traceback.format_exc()
                self.q.put({"kind": "log", "level": "ERROR", "name": "pipeline",
                            "msg": "Pipeline crashed — see traceback below",
                            "ts": datetime.now().strftime("%H:%M:%S")})
            finally:
                ps_logger.removeHandler(handler)
                self.ended_at = datetime.now()
                if self.result:
                    self.output_dir = self.result.get("output_dir", self.output_dir)
                self.finished.set()
                self.q.put({"kind": "end"})

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

    def cancel(self) -> None:
        """Request a cooperative abort. The pipeline stops at its next step
        boundary and raises PipelineAborted, which _target catches."""
        self._cancel.set()

    @property
    def cancelling(self) -> bool:
        """True once an abort was requested but the run hasn't ended yet."""
        return self._cancel.is_set() and not self.finished.is_set()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def elapsed(self) -> str:
        if not self.started_at:
            return "0s"
        end = self.ended_at or datetime.now()
        secs = int((end - self.started_at).total_seconds())
        return f"{secs // 60}m {secs % 60}s" if secs >= 60 else f"{secs}s"
