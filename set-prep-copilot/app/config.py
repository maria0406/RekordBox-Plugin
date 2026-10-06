from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UPLOADS_DIR = ROOT / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
