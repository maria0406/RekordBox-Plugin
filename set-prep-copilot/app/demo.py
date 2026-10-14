"""Demo library for the hosted site (DEMO_MODE=1), where there's no
rekordbox install to read from. Stands in for rekordbox_db and
audio_analysis with the same function shapes, so main.py's pipeline
(scoring, cues, export, practice) runs unchanged:

- list_playlists / get_playlist_tracks serve the playlists in
  demo/demo_set.json -- a handful of Creative Commons tracks picked from
  the practice catalog.
- analyze_track returns the analysis the catalog build already computed
  (demo/analysis/), so the server never loads librosa or decodes audio.
- The audio itself isn't committed: `python -m app.demo` downloads it from
  the Internet Archive into demo/audio/ (Render runs this at build time),
  and /audio serves it same-origin so the practice player's Web Audio
  chain can read it.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

from .config import ROOT

DEMO_DIR = ROOT / "demo"
AUDIO_DIR = DEMO_DIR / "audio"
ANALYSIS_DIR = DEMO_DIR / "analysis"


class RekordboxDbError(Exception):
    pass


@lru_cache(maxsize=1)
def _demo_set() -> dict:
    return json.loads((DEMO_DIR / "demo_set.json").read_text(encoding="utf-8"))


def _all_tracks() -> list[dict]:
    return [t for pl in _demo_set()["playlists"] for t in pl["tracks"]]


def list_playlists() -> list[dict]:
    return [{"id": pl["id"], "name": pl["name"], "path": pl["name"]} for pl in _demo_set()["playlists"]]


def get_playlist_tracks(playlist_id: str) -> list[dict]:
    playlist = next((pl for pl in _demo_set()["playlists"] if pl["id"] == playlist_id), None)
    if playlist is None:
        raise RekordboxDbError(f"Playlist ID {playlist_id!r} not found.")
    return [
        {
            "track_id": t["track_id"],
            "name": t["name"],
            "artist": t["artist"],
            "album": t["album"],
            "total_time": t["total_time"],
            "average_bpm": t["average_bpm"],
            "tonality": None,
            "location": str(AUDIO_DIR / t["audio_file"]),
            "isrc": None,
            "raw_attrib": None,
        }
        for t in playlist["tracks"]
    ]


@lru_cache(maxsize=None)
def _analysis_by_audio_file() -> dict[str, dict]:
    return {
        t["audio_file"]: json.loads((ANALYSIS_DIR / t["analysis_file"]).read_text(encoding="utf-8"))
        for t in _all_tracks()
    }


def analyze_track(file_path: str) -> dict:
    """Precomputed analyze_track() output for a demo track. Every session
    shares the same dict, so callers must treat it as read-only (main.py
    and cues.py only read analyses)."""
    analysis = _analysis_by_audio_file().get(Path(file_path).name)
    if analysis is None:
        raise FileNotFoundError(f"No precomputed analysis for {file_path}")
    return analysis


def credits() -> list[dict]:
    """CC BY attribution for every demo track; base.html shows it on every page."""
    return [
        {
            "name": t["name"], "artist": t["artist"], "album": t["album"],
            "source_url": t["source_url"], "license": t["license"],
        }
        for t in _all_tracks()
    ]


def _download(url: str, dest: Path, attempts: int = 4) -> None:
    """archive.org downloads time out now and then; retry rather than fail
    the whole deploy over one slow handshake."""
    partial = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp, open(partial, "wb") as out:
                while chunk := resp.read(1 << 16):
                    out.write(chunk)
            partial.rename(dest)
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == attempts:
                raise
            print(f"  attempt {attempt} failed ({exc}); retrying", flush=True)
            time.sleep(5 * attempt)


def fetch_audio() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for t in _all_tracks():
        dest = AUDIO_DIR / t["audio_file"]
        if dest.is_file():
            continue
        print(f"Downloading {t['artist']} - {t['name']}", flush=True)
        _download(t["download_url"], dest)


if __name__ == "__main__":
    fetch_audio()
