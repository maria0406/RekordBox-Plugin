"""Thin wrapper around the Spotify Web API calls this app needs, using
requests directly (not spotipy — some spotipy methods still call endpoints
Spotify removed in the February 2026 migration). Read/write only through
documented endpoints: GET /me, GET /me/playlists, POST /me/playlists,
POST /playlists/{id}/items, GET /search.

Lessons carried over from spotify-api-explorer's live run against this same
account:
- An ISRC search response can report `tracks.total: 0` even when
  `tracks.items` holds the actual match -- always check `len(items)`, not
  `total`.
- Title/artist text search is not reliable as an equality check even when
  the string looks exact (a differently-credited remix can share a
  near-identical title and a different ISRC) -- ISRC is the primary match,
  text search is a flagged-for-review fallback only.
"""
from __future__ import annotations

import time

import requests

from . import auth

API_BASE = "https://api.spotify.com/v1"


class SpotifyAPIError(RuntimeError):
    def __init__(self, status: int, body: object):
        self.status = status
        self.body = body
        super().__init__(f"Spotify API error {status}: {body}")


def _request(method: str, path: str, *, params: dict | None = None, json_body: dict | None = None) -> object:
    url = f"{API_BASE}{path}"
    refreshed_once = False
    rate_limit_retries = 0

    while True:
        token = auth.get_access_token()
        resp = requests.request(
            method, url, headers={"Authorization": f"Bearer {token}"},
            params=params, json=json_body, timeout=15,
        )

        if resp.status_code == 401 and not refreshed_once:
            auth.force_refresh()
            refreshed_once = True
            continue

        if resp.status_code == 429 and rate_limit_retries < 5:
            retry_after = int(resp.headers.get("Retry-After", "1"))
            rate_limit_retries += 1
            time.sleep(retry_after)
            continue

        break

    if resp.status_code == 204 or not resp.content:
        body = None
    else:
        try:
            body = resp.json()
        except ValueError:
            body = {"_non_json_body": resp.text[:500]}

    if resp.status_code >= 400:
        raise SpotifyAPIError(resp.status_code, body)

    return body


def get_me() -> dict:
    return _request("GET", "/me")


def get_my_playlists(limit: int = 50) -> list[dict]:
    """All playlists owned or followed by the user, paginated."""
    me = get_me()
    my_id = me["id"]
    playlists: list[dict] = []
    params = {"limit": limit, "offset": 0}
    while True:
        page = _request("GET", "/me/playlists", params=params)
        playlists.extend(page.get("items", []) or [])
        if not page.get("next"):
            break
        params["offset"] += limit
    return [p for p in playlists if (p.get("owner") or {}).get("id") == my_id]


def search_by_isrc(isrc: str, limit: int = 5) -> list[dict]:
    body = _request("GET", "/search", params={"type": "track", "limit": limit, "q": f"isrc:{isrc}"})
    return ((body or {}).get("tracks") or {}).get("items", []) or []


def search_by_text(track_name: str, artist_name: str, limit: int = 5) -> list[dict]:
    q = f"track:{track_name} artist:{artist_name}"
    body = _request("GET", "/search", params={"type": "track", "limit": limit, "q": q})
    return ((body or {}).get("tracks") or {}).get("items", []) or []


def match_track_by_isrc_then_text(isrc: str | None, track_name: str, artist_name: str) -> tuple[dict | None, str]:
    """Returns (matched_track_or_None, confidence) where confidence is
    'isrc' (exact), 'text' (flag for DJ review), or 'none'."""
    if isrc:
        hits = search_by_isrc(isrc)
        if hits:
            return hits[0], "isrc"

    hits = search_by_text(track_name, artist_name)
    if hits:
        return hits[0], "text"

    return None, "none"


def create_playlist(name: str, description: str = "") -> dict:
    return _request(
        "POST", "/me/playlists",
        json_body={"name": name, "description": description, "public": False},
    )


def add_items_to_playlist(playlist_id: str, track_uris: list[str]) -> None:
    """POST /playlists/{id}/items -- the post-Feb-2026 endpoint (replaces
    the retired /playlists/{id}/tracks)."""
    # Spotify accepts at most 100 URIs per call.
    for i in range(0, len(track_uris), 100):
        chunk = track_uris[i : i + 100]
        _request("POST", f"/playlists/{playlist_id}/items", json_body={"uris": chunk})
