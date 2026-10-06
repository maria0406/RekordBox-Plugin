"""Harvests candidate practice tracks from the Internet Archive's netlabels
collection (https://archive.org/details/netlabels).

Why this source: it holds complete catalogs of Creative Commons netlabels
(deep/tech house, minimal, techno), needs no API key, and serves the
original audio files directly. See reports/Free house music audio sources.md.

API shape, confirmed against live responses (2026-10):
- GET https://archive.org/advancedsearch.php?q=...&fl[]=...&rows=&page=&output=json
  -> {"response": {"numFound": N, "docs": [{identifier, title, creator,
  licenseurl, subject}, ...]}}. One doc is a *release* (EP/album), not a track.
- GET https://archive.org/metadata/{identifier}
  -> {"metadata": {title, creator, licenseurl, ...}, "files": [{name, format
  ("VBR MP3", "Flac", "Ogg Vorbis", ...), source ("original"/"derivative"),
  length (seconds, string), title, creator, size}, ...]}
- Files download from https://archive.org/download/{identifier}/{name}.

Subject tags are free text supplied by uploaders, so a "house" tag is only a
candidate filter -- the catalog builder re-checks tempo after analysis.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests

from .licenses import License, is_allowed, parse_license

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{name}"
DETAILS_URL = "https://archive.org/details/{identifier}"

USER_AGENT = "SetPrepCopilot-catalog-builder/0.1 (practice-track curation)"
REQUEST_TIMEOUT = 30
POLITE_DELAY_SECONDS = 1.0  # between metadata calls; IA asks clients not to hammer it

HOUSE_SUBJECTS = (
    "house", "deep house", "deep-house", "tech house", "tech-house",
    "progressive house", "minimal house", "electro house",
)

_MP3_FORMATS = {"vbr mp3", "320kbps mp3", "256kbps mp3", "192kbps mp3", "mp3"}

MIN_TRACK_SECONDS = 180  # shorter than 3 minutes leaves no room to practice a blend
MAX_TRACK_SECONDS = 900  # longer than 15 minutes is almost always a DJ mix, not a track


class InternetArchiveError(Exception):
    pass


@dataclass
class CandidateTrack:
    identifier: str
    file_name: str
    title: str
    artist: str
    release_title: str
    duration: float
    license: License

    @property
    def track_id(self) -> str:
        return f"ia:{self.identifier}/{self.file_name}"

    @property
    def download_url(self) -> str:
        return DOWNLOAD_URL.format(identifier=self.identifier, name=quote(self.file_name))

    @property
    def source_url(self) -> str:
        return DETAILS_URL.format(identifier=self.identifier)


RETRIES = 4
RETRY_BACKOFF_SECONDS = 5.0  # doubles each attempt; rides out DNS blips and 429/5xx


def _get_json(url: str, params: dict | None = None) -> dict:
    for attempt in range(RETRIES):
        try:
            resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            if attempt == RETRIES - 1:
                raise InternetArchiveError(f"Request to {url} failed: {exc}") from exc
        else:
            if resp.status_code != 429 and resp.status_code < 500:
                break
            if attempt == RETRIES - 1:
                break
        time.sleep(RETRY_BACKOFF_SECONDS * 2 ** attempt)
    if resp.status_code != 200:
        raise InternetArchiveError(f"{url} returned HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise InternetArchiveError(f"{url} returned non-JSON") from exc


def build_query(subjects: tuple[str, ...] = HOUSE_SUBJECTS) -> str:
    subject_clause = " OR ".join(f'"{s}"' for s in subjects)
    return f"collection:netlabels AND mediatype:audio AND subject:({subject_clause}) AND licenseurl:*"


def search_releases(page: int = 1, rows: int = 100, subjects: tuple[str, ...] = HOUSE_SUBJECTS) -> list[dict]:
    """One page of search results, unfiltered. License filtering happens
    client-side (via `licenses.is_allowed`) so the policy lives in one place."""
    params = {
        "q": build_query(subjects),
        "fl[]": ["identifier", "title", "creator", "licenseurl", "subject"],
        "sort[]": "downloads desc",  # popular releases first: likelier to be well-produced
        "rows": rows,
        "page": page,
        "output": "json",
    }
    body = _get_json(SEARCH_URL, params)
    return body.get("response", {}).get("docs", [])


def _first(value) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _pick_audio_files(files: list[dict]) -> list[dict]:
    """MP3s only (one per track): IA's originals when they are MP3, else the
    MP3 IA derived from a FLAC/WAV original. Lossy is fine for both practice
    playback and BPM/key/phrase analysis, and keeps the catalog a few GB."""
    mp3s = [f for f in files if _first(f.get("format")).lower() in _MP3_FORMATS]
    originals = [f for f in mp3s if f.get("source") == "original"]
    return originals or mp3s


def release_tracks(identifier: str) -> list[CandidateTrack]:
    body = _get_json(METADATA_URL.format(identifier=identifier))
    meta = body.get("metadata", {})
    lic = parse_license(_first(meta.get("licenseurl")))
    if not is_allowed(lic):
        return []

    release_title = _first(meta.get("title")) or identifier
    release_artist = _first(meta.get("creator"))

    tracks: list[CandidateTrack] = []
    for f in _pick_audio_files(body.get("files", [])):
        try:
            duration = float(f.get("length") or 0)
        except ValueError:
            duration = 0.0  # IA sometimes writes "mm:ss"; unknown length is checked after analysis
        if duration and not (MIN_TRACK_SECONDS <= duration <= MAX_TRACK_SECONDS):
            continue
        name = f["name"]
        tracks.append(
            CandidateTrack(
                identifier=identifier,
                file_name=name,
                title=_first(f.get("title")) or Path(name).stem,
                artist=_first(f.get("creator")) or release_artist,
                release_title=release_title,
                duration=duration,
                license=lic,
            )
        )
    return tracks


def iter_candidates(max_releases: int, tracks_per_release: int = 3, rows: int = 100):
    """Yield candidate tracks across up to `max_releases` releases, capping
    each release so one prolific label/EP doesn't dominate the catalog."""
    seen = 0
    page = 1
    while seen < max_releases:
        docs = search_releases(page=page, rows=rows)
        if not docs:
            return
        for doc in docs:
            if not is_allowed(parse_license(doc.get("licenseurl"))):
                continue
            if seen >= max_releases:
                return
            seen += 1
            try:
                tracks = release_tracks(doc["identifier"])
            except InternetArchiveError:
                continue
            yield from tracks[:tracks_per_release]
            time.sleep(POLITE_DELAY_SECONDS)
        page += 1


def download(track: CandidateTrack, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{track.identifier}__{Path(track.file_name).name}".replace("/", "_")
    dest = dest_dir / safe_name
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        with requests.get(
            track.download_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT, stream=True
        ) as resp:
            if resp.status_code != 200:
                raise InternetArchiveError(f"Download of {track.download_url} returned HTTP {resp.status_code}")
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
            tmp.rename(dest)
    except requests.RequestException as exc:
        raise InternetArchiveError(f"Download of {track.download_url} failed: {exc}") from exc
    return dest
