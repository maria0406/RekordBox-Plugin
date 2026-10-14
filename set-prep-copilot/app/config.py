from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UPLOADS_DIR = ROOT / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Hosted demo (render.yaml sets this): no rekordbox on the server, so the
# app serves app/demo.py's CC-licensed demo set and keeps one prep session
# per browser instead of one for the whole process.
DEMO_MODE = os.environ.get("DEMO_MODE") == "1"
