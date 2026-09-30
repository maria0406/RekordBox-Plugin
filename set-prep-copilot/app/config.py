from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback").strip()
SESSION_SECRET = os.environ.get("SESSION_SECRET", "").strip()

TOKEN_CACHE_PATH = ROOT / ".token_cache.json"
UPLOADS_DIR = ROOT / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

SPOTIFY_SCOPES = [
    "user-read-private",
    "playlist-read-private",
    "playlist-modify-private",
]

if not SESSION_SECRET:
    raise RuntimeError(
        "SESSION_SECRET is not set in .env. Generate one (e.g. `python3 -c "
        "'import secrets; print(secrets.token_hex(32))'`) and add it to .env."
    )
