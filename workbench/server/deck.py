"""Render a run's PPTX deck to per-slide PNGs.

soffice (LibreOffice, headless) converts .pptx -> .pdf; PyMuPDF rasterises each
page. Results are cached in ``outputs/<run_id>/.deck_cache/`` and only rebuilt
when the deck is newer than the cache.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import tempfile
import threading

import pymupdf

from .artifacts import _run_dir

logger = logging.getLogger("perfect_store.workbench.deck")

_DPI = 140
_LOCK = threading.Lock()  # one soffice conversion at a time


def _deck_file(run_dir) -> str | None:
    hits = sorted(glob.glob(os.path.join(str(run_dir), "*.pptx")))
    return hits[0] if hits else None


def _cache_dir(run_dir) -> str:
    d = os.path.join(str(run_dir), ".deck_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _is_fresh(cache_dir: str, deck: str) -> bool:
    slides = sorted(glob.glob(os.path.join(cache_dir, "slide_*.png")))
    if not slides:
        return False
    return min(os.path.getmtime(s) for s in slides) >= os.path.getmtime(deck)


def _build(deck: str, cache_dir: str) -> None:
    with _LOCK:
        if _is_fresh(cache_dir, deck):  # another thread just did it
            return
        for old in glob.glob(os.path.join(cache_dir, "slide_*.png")):
            os.remove(old)
        with tempfile.TemporaryDirectory(prefix="ps_deck_") as tmp:
            profile = os.path.join(tmp, "lo_profile")
            cmd = [
                "soffice", "--headless", "--nologo", "--nofirststartwizard",
                f"-env:UserInstallation=file://{profile}",
                "--convert-to", "pdf", "--outdir", tmp, deck,
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                logger.warning("soffice conversion failed: %s", exc)
                raise RuntimeError("deck conversion failed") from exc
            pdfs = glob.glob(os.path.join(tmp, "*.pdf"))
            if not pdfs:
                raise RuntimeError("soffice produced no pdf")
            doc = pymupdf.open(pdfs[0])
            for i, page in enumerate(doc, 1):
                pix = page.get_pixmap(dpi=_DPI)
                pix.save(os.path.join(cache_dir, f"slide_{i:02d}.png"))
            doc.close()


def render(run_id: str) -> dict:
    run_dir = _run_dir(run_id)
    deck = _deck_file(run_dir)
    if not deck:
        return {"count": 0, "slides": [], "deck_name": None}
    cache_dir = _cache_dir(run_dir)
    if not _is_fresh(cache_dir, deck):
        _build(deck, cache_dir)
    slides = [os.path.basename(p)
              for p in sorted(glob.glob(os.path.join(cache_dir, "slide_*.png")))]
    return {"count": len(slides), "slides": slides, "deck_name": os.path.basename(deck)}


def slide_path(run_id: str, name: str) -> str:
    run_dir = _run_dir(run_id)
    safe = os.path.basename(name)
    p = os.path.join(str(run_dir), ".deck_cache", safe)
    if not os.path.isfile(p):
        raise FileNotFoundError(name)
    return p


def has_soffice() -> bool:
    return shutil.which("soffice") is not None
