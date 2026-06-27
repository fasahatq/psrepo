#!/usr/bin/env python3
"""
Perfect Store Agent — Main entry point.

Usage:
  # Start the file watcher (monitors inbox/ for new files):
  python main.py watch

  # Process a single file directly:
  python main.py run path/to/data.csv

  # Process any files already in inbox/:
  python main.py process-inbox

  # Generate sample test data:
  python main.py generate-sample
"""

import os
import sys
import logging
from pathlib import Path

# Project root is wherever this script lives
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def setup_logging():
    """Configure logging to console and file."""
    log_dir = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-30s | %(levelname)-5s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(log_dir, "pipeline.log")),
        ]
    )


def cmd_watch():
    """Start the file watcher."""
    from agents.watcher import start_watcher, process_existing_files
    from pipeline import run_pipeline

    inbox = os.path.join(PROJECT_ROOT, "inbox")
    processing = os.path.join(PROJECT_ROOT, "processing")

    def callback(file_path):
        run_pipeline(file_path, PROJECT_ROOT)

    # Process any existing files first
    process_existing_files(inbox, processing, callback)

    # Then watch for new ones
    start_watcher(inbox, processing, callback)


def cmd_run(file_path: str):
    """Process a single file."""
    from pipeline import run_pipeline
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    run_pipeline(file_path, PROJECT_ROOT)


def cmd_process_inbox():
    """Process all files currently in inbox/."""
    from agents.watcher import process_existing_files
    from pipeline import run_pipeline

    inbox = os.path.join(PROJECT_ROOT, "inbox")
    processing = os.path.join(PROJECT_ROOT, "processing")

    def callback(file_path):
        run_pipeline(file_path, PROJECT_ROOT)

    process_existing_files(inbox, processing, callback)


def cmd_generate_sample():
    """Generate sample CPG data for testing."""
    from generate_sample_data import generate_sample_data
    output_path = os.path.join(PROJECT_ROOT, "inbox", "sample_cpg_data.csv")
    generate_sample_data(output_path)
    print(f"Sample data written to: {output_path}")


def main():
    setup_logging()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "watch":
        cmd_watch()
    elif command == "run":
        if len(sys.argv) < 3:
            print("Usage: python main.py run <file_path>")
            sys.exit(1)
        cmd_run(sys.argv[2])
    elif command == "process-inbox":
        cmd_process_inbox()
    elif command == "generate-sample":
        cmd_generate_sample()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
