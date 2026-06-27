"""
Watcher Agent — monitors the inbox/ folder for new files using watchdog.
When a file lands, moves it to processing/ and triggers the pipeline.
"""

import os
import shutil
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("perfect_store.watcher")


class InboxHandler(FileSystemEventHandler):
    """Handles new files arriving in inbox/."""

    def __init__(self, inbox_dir: str, processing_dir: str, pipeline_callback):
        super().__init__()
        self.inbox_dir = Path(inbox_dir)
        self.processing_dir = Path(processing_dir)
        self.pipeline_callback = pipeline_callback
        self._seen = set()

    def on_created(self, event):
        if event.is_directory:
            return
        src = Path(event.src_path)
        # Skip hidden/temp files
        if src.name.startswith(".") or src.name.startswith("~"):
            return
        # Only process CSV and Excel files
        if src.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            logger.info(f"Skipping non-data file: {src.name}")
            return
        if src.name in self._seen:
            return
        self._seen.add(src.name)
        logger.info(f"New file detected: {src.name}")
        self._process_file(src)

    def _process_file(self, src: Path):
        """Move file to processing/ and kick off pipeline."""
        # Wait briefly for file writes to finish
        time.sleep(1)
        dest = self.processing_dir / src.name
        try:
            shutil.move(str(src), str(dest))
            logger.info(f"Moved {src.name} → processing/")
        except Exception as e:
            logger.error(f"Failed to move {src.name}: {e}")
            return

        # Trigger the pipeline
        try:
            self.pipeline_callback(str(dest))
        except Exception as e:
            logger.error(f"Pipeline failed for {src.name}: {e}", exc_info=True)


def start_watcher(inbox_dir: str, processing_dir: str, pipeline_callback):
    """Start the file watcher. Blocks until interrupted."""
    os.makedirs(inbox_dir, exist_ok=True)
    os.makedirs(processing_dir, exist_ok=True)

    handler = InboxHandler(inbox_dir, processing_dir, pipeline_callback)
    observer = Observer()
    observer.schedule(handler, inbox_dir, recursive=False)
    observer.start()
    logger.info(f"Watching {inbox_dir} for new files... (Ctrl+C to stop)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Watcher stopped.")
    observer.join()


def process_existing_files(inbox_dir: str, processing_dir: str, pipeline_callback):
    """Process any files already sitting in inbox/ (useful on startup)."""
    inbox = Path(inbox_dir)
    for f in sorted(inbox.iterdir()):
        if f.is_file() and f.suffix.lower() in (".csv", ".xlsx", ".xls"):
            dest = Path(processing_dir) / f.name
            shutil.move(str(f), str(dest))
            logger.info(f"Processing existing file: {f.name}")
            try:
                pipeline_callback(str(dest))
            except Exception as e:
                logger.error(f"Pipeline failed for {f.name}: {e}", exc_info=True)
