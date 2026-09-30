"""Calls a fixed set of Spotify Web API endpoints with my own account,
saves the raw JSON responses, and writes API_SHAPES.md describing the
shape of each response.

Read-only: never creates, edits, or deletes anything in the account.
Uses requests directly (not spotipy) so it's immune to spotipy helpers that
still call endpoints Spotify retired in the February 2026 migration
(e.g. POST /playlists/{id}/tracks -> POST /playlists/{id}/items).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

from auth import SpotifyAuth

HERE = Path(__file__).resolve().parent
SAMPLES_DIR = HERE / "samples"
API_BASE = "https://api.spotify.com/v1"

SAMPLES_DIR.mkdir(exist_ok=True)

# Each captured call: (endpoint_name, method, url, params, notes)
CALL_LOG: list[dict] = []


def log(msg: str) -> None:
    print(msg)


def request_json(auth: SpotifyAuth, method: str, url: str, *, params: dict | None = None,
                  allow_statuses: tuple[int, ...] = ()) -> tuple[int, object, dict]:
    """Make one API call, handling 401 (refresh once) and 429 (wait Retry-After).

    Returns (status_code, parsed_body_or_None, response_headers).
    `allow_statuses` marks status codes as expected-and-fine to record rather
    than retry against (used for the audio-features/audio-analysis calls,
    which are expected to fail for a new app).
    """
    refreshed_once = False
    rate_limit_retries = 0
    max_rate_limit_retries = 5

    while True:
        resp = requests.request(method, url, headers=auth.auth_header(), params=params, timeout=15)
        log(f"{method} {resp.url} -> {resp.status_code}")

        if resp.status_code == 401 and not refreshed_once:
            log("  got 401, refreshing access token once and retrying...")
            auth.refresh()
            refreshed_once = True
            continue

        if resp.status_code == 429 and rate_limit_retries < max_rate_limit_retries:
            retry_after = int(resp.headers.get("Retry-After", "1"))
            rate_limit_retries += 1
            log(f"  rate-limited, waiting {retry_after}s per Retry-After header "
                f"(attempt {rate_limit_retries}/{max_rate_limit_retries})...")
            time.sleep(retry_after)
            continue

        break

    body: object = None
    if resp.status_code == 204 or not resp.content:
        body = None
    else:
        try:
            body = resp.json()
        except ValueError:
            body = {"_non_json_body": resp.text[:2000]}

    if resp.status_code >= 400 and resp.status_code not in allow_statuses:
        log(f"  WARNING: {resp.status_code} response body: {json.dumps(body)[:500]}")

    return resp.status_code, body, dict(resp.headers)


def save_sample(name: str, status: int, body: object) -> None:
    path = SAMPLES_DIR / f"{name}.json"
    payload = {"status_code": status, "body": body}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    log(f"  saved samples/{name}.json")


def call(auth: SpotifyAuth, name: str, method: str, url: str, *, params: dict | None = None,
          note: str, allow_statuses: tuple[int, ...] = ()) -> tuple[int, object]:
    status, body, headers = request_json(auth, method, url, params=params, allow_statuses=allow_statuses)
    save_sample(name, status, body)
    CALL_LOG.append(
        {
            "name": name,
            "method": method,
            "url": url,
            "params": params or {},
            "status": status,
            "body": body,
            "note": note,
        }
    )
    return status, body


def main() -> None:
    log("Authenticating with Spotify (Authorization Code with PKCE)...")
    auth = SpotifyAuth()
    log("Authenticated.\n")

    # 1. GET /v1/me
    status, me = call(
        auth, "me", "GET", f"{API_BASE}/me",
        note="The authenticated user's profile.",
    )
    if status != 200 or not isinstance(me, dict):
        sys.exit("Could not fetch /v1/me; aborting (check your Client ID and that you completed login).")
    my_id = me.get("id")

    # 2. GET /v1/me/playlists?limit=10
    status, playlists = call(
        auth, "me_playlists", "GET", f"{API_BASE}/me/playlists",
        params={"limit": 10},
        note="The authenticated user's playlists (owned and followed).",
    )

    # Find the first playlist owned by me, since playlist items are only
    # returned for playlists I own or collaborate on.
    owned_playlist = None
    if isinstance(playlists, dict):
        for item in playlists.get("items", []) or []:
            owner = (item or {}).get("owner") or {}
            if owner.get("id") == my_id:
                owned_playlist = item
                break

    if owned_playlist is None:
        log("\nNo owned playlist found in the first 10 results; skipping playlist items, "
            "track, and search calls that depend on it.")
        playlist_id = None
    else:
        playlist_id = owned_playlist["id"]
        log(f"\nUsing owned playlist: {owned_playlist.get('name')!r} ({playlist_id})")

    first_track = None
    if playlist_id:
        # 3. GET /v1/playlists/{id}/items?limit=10
        status, items = call(
            auth, "playlist_items", "GET", f"{API_BASE}/playlists/{playlist_id}/items",
            params={"limit": 10},
            note="Tracks in a playlist I own (post-Feb-2026 endpoint; replaces /tracks). "
                 "NOTE: the per-item payload key is now 'item', not the pre-migration 'track'.",
        )
        if isinstance(items, dict):
            for entry in items.get("items", []) or []:
                entry = entry or {}
                # Feb 2026 migration renamed this key from "track" to "item"; check both
                # so this keeps working if it ever reverts or a mixed response shows up.
                track = entry.get("item") or entry.get("track")
                if track and track.get("id") and track.get("type") == "track":
                    first_track = track
                    break

    track_id = first_track["id"] if first_track else None

    if track_id:
        # 4. GET /v1/tracks/{id}
        status, track = call(
            auth, "track", "GET", f"{API_BASE}/tracks/{track_id}",
            note="Full track object, including external_ids (ISRC).",
        )
    else:
        track = None
        log("\nNo track found in the owned playlist; skipping track, search, "
            "audio-features, and audio-analysis calls.")

    if track and isinstance(track, dict):
        isrc = (track.get("external_ids") or {}).get("isrc")
        track_name = track.get("name", "")
        artist_name = ((track.get("artists") or [{}])[0]).get("name", "")

        # 5. GET /v1/search?type=track&limit=5&q=isrc:XXXX
        if isrc:
            call(
                auth, "search_isrc", "GET", f"{API_BASE}/search",
                params={"type": "track", "limit": 5, "q": f"isrc:{isrc}"},
                note="Search by ISRC, to test exact ISRC-based track matching.",
            )
        else:
            log("\nTrack has no ISRC in external_ids; skipping ISRC search.")

        # 6. GET /v1/search?type=track&limit=5&q=track:{name} artist:{artist}
        call(
            auth, "search_query", "GET", f"{API_BASE}/search",
            params={"type": "track", "limit": 5, "q": f"track:{track_name} artist:{artist_name}"},
            note="Search by track/artist text, to compare against ISRC matching.",
        )

    # 7. GET /v1/me/player/currently-playing
    if sys.stdin.isatty():
        log("\nMake sure something is playing on Spotify right now for an accurate "
            "currently-playing sample, then press Enter.")
        input()
    else:
        log("\nNot running in an interactive terminal -- assuming you were told to "
            "start playback before this run started. Pausing 5s, then calling "
            "currently-playing as-is (a 204 here just means nothing was playing).")
        time.sleep(5)
    call(
        auth, "currently_playing", "GET", f"{API_BASE}/me/player/currently-playing",
        note="The user's currently playing track. Returns 204 with an empty body "
             "when nothing is playing.",
    )

    if track_id:
        # 8. audio-features / audio-analysis -- expected to fail for a new app
        call(
            auth, "audio_features", "GET", f"{API_BASE}/audio-features/{track_id}",
            note="Tempo/energy/danceability etc. Expected to fail (403) for apps "
                 "created after the Nov 2024 access change.",
            allow_statuses=(401, 403, 404),
        )
        call(
            auth, "audio_analysis", "GET", f"{API_BASE}/audio-analysis/{track_id}",
            note="Bar/beat/section-level audio analysis. Expected to fail (403) for "
                 "apps created after the Nov 2024 access change.",
            allow_statuses=(401, 403, 404),
        )

    log("\nAll calls complete. Writing API_SHAPES.md...")
    write_shapes_doc(me_id=my_id, track=track if isinstance(track, dict) else None)
    log("Done. See API_SHAPES.md and samples/.")


# ---------------------------------------------------------------------------
# API_SHAPES.md generation
# ---------------------------------------------------------------------------

MAX_STR_LEN = 80


def _truncate(value):
    if isinstance(value, str) and len(value) > MAX_STR_LEN:
        return value[:MAX_STR_LEN] + "..."
    return value


def _type_name(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _outline(value, indent: int = 0, key_label: str | None = None) -> list[str]:
    lines: list[str] = []
    pad = "  " * indent
    t = _type_name(value)

    if isinstance(value, dict):
        header = f"{pad}- **{key_label}** (object)" if key_label else f"{pad}- (object)"
        lines.append(header)
        if not value:
            lines.append(f"{pad}  - _(empty object)_")
        for k, v in value.items():
            lines.extend(_outline(v, indent + 1, key_label=k))
        return lines

    if isinstance(value, list):
        header = f"{pad}- **{key_label}** (array, {len(value)} item(s))" if key_label else f"{pad}- (array, {len(value)} item(s))"
        lines.append(header)
        if not value:
            lines.append(f"{pad}  - _(empty array)_")
        else:
            lines.extend(_outline(value[0], indent + 1, key_label="[0]"))
        return lines

    example = _truncate(value)
    example_str = json.dumps(example, ensure_ascii=False)
    label = f"**{key_label}**" if key_label else "value"
    lines.append(f"{pad}- {label} ({t}) = `{example_str}`")
    return lines


def _find(name: str) -> dict | None:
    for entry in CALL_LOG:
        if entry["name"] == name:
            return entry
    return None


def _render_call_section(entry: dict) -> str:
    out = [f"## {entry['name']}", ""]
    url = entry["url"]
    if entry["params"]:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(entry['params'])}"
    out.append(f"**Request:** `{entry['method']} {url}`")
    out.append("")
    out.append(f"**Status code:** {entry['status']}")
    out.append("")
    out.append(f"**Useful for:** {entry['note']}")
    out.append("")
    out.append("**Shape:**")
    out.append("")
    if entry["body"] is None:
        out.append("_(no response body)_")
    else:
        out.extend(_outline(entry["body"]))
    out.append("")
    return "\n".join(out)


def write_shapes_doc(me_id: str | None, track: dict | None) -> None:
    sections = []
    endpoint_order = [
        "me",
        "me_playlists",
        "playlist_items",
        "track",
        "search_isrc",
        "search_query",
        "currently_playing",
        "audio_features",
        "audio_analysis",
    ]

    doc = ["# Spotify Web API — Data Shapes", "", ]
    doc.append(
        "Generated by `explore.py` against my own Spotify account, using the raw "
        "Web API (requests, not spotipy) as of the February 2026 endpoint migration. "
        "Each section below is one endpoint call: its request, HTTP status, and a "
        "nested outline of every field the response actually contained, with the "
        "field's type and a truncated example value (long strings cut to "
        f"{MAX_STR_LEN} chars, arrays shown as their first item only)."
    )
    doc.append("")

    for name in endpoint_order:
        entry = _find(name)
        if entry is None:
            doc.append(f"## {name}")
            doc.append("")
            doc.append("_(skipped — no upstream data to call this with; see terminal log)_")
            doc.append("")
            continue
        doc.append(_render_call_section(entry))

    # --- Fields that matter for the set-prep tool ---------------------------
    doc.append("## Fields that matter for the set-prep tool")
    doc.append("")

    track_entry = _find("track")
    t = track if track is not None else (track_entry["body"] if track_entry else None)

    def field(path, label):
        cur = t
        for p in path:
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                cur = None
                break
        present = cur is not None
        doc.append(f"- **{label}**: {'present' if present else 'MISSING/null'}"
                    + (f" — example: `{json.dumps(_truncate(cur), ensure_ascii=False)}`" if present else ""))

    if t is None:
        doc.append("_(No track object was retrieved — the owned-playlist lookup did not find a playable track, "
                    "so ID/URI/name/ISRC/etc. below could not be checked. See the `track` and `playlist_items` "
                    "sections above for what happened.)_")
    else:
        field(["id"], "Track ID")
        field(["uri"], "Track URI")
        field(["name"], "Name")
        field(["artists"], "Artists")
        field(["duration_ms"], "Duration (ms)")
        field(["external_ids", "isrc"], "ISRC (external_ids.isrc)")
        field(["explicit"], "Explicit flag")
        field(["album", "images"], "Album art (album.images)")

    doc.append("")
    af_entry = _find("audio_features")
    aa_entry = _find("audio_analysis")
    af_ok = af_entry is not None and af_entry["status"] == 200
    aa_ok = aa_entry is not None and aa_entry["status"] == 200
    if af_entry is None and aa_entry is None:
        doc.append("- **Tempo / key / loudness / energy / section data**: not tested this run "
                    "(no track ID was available to call audio-features/audio-analysis with).")
    else:
        af_status = af_entry["status"] if af_entry else "n/a"
        aa_status = aa_entry["status"] if aa_entry else "n/a"
        doc.append(f"- **Audio features** (`/v1/audio-features/{{id}}`, tempo, key, energy, danceability, "
                    f"loudness): status **{af_status}** — {'ACCESSIBLE' if af_ok else 'NOT accessible to this app'}.")
        doc.append(f"- **Audio analysis** (`/v1/audio-analysis/{{id}}`, bar/beat/section-level tempo, key, "
                    f"loudness, energy): status **{aa_status}** — {'ACCESSIBLE' if aa_ok else 'NOT accessible to this app'}.")
        doc.append("")
        doc.append(
            "**Bottom line:** " + (
                "Audio features and audio analysis ARE accessible to this app, so tempo/key/loudness/energy/"
                "section data can come from the Spotify API directly."
                if (af_ok and aa_ok) else
                "Audio features and/or audio analysis are NOT accessible to this app (consistent with Spotify's "
                "November 2024 change restricting these endpoints for apps created after that date — see the "
                "design doc's 'Spotify playlist output' section). No tempo, key, loudness, energy, or section "
                "data is available from the Web API for this app. Set Prep Copilot's own librosa/Essentia "
                "analysis pipeline is the only source for these values."
            )
        )

    doc.append("")
    doc.append("### Fields missing or null compared with the older API")
    doc.append("")
    if t is None:
        doc.append("_(Could not check — no track object retrieved this run.)_")
    else:
        older_fields = {
            "popularity": t.get("popularity", "__absent__"),
            "available_markets": t.get("available_markets", "__absent__"),
            "linked_from": t.get("linked_from", "__absent__"),
            "album.available_markets": (t.get("album") or {}).get("available_markets", "__absent__"),
            "preview_url": t.get("preview_url", "__absent__"),
        }
        any_missing = False
        for k, v in older_fields.items():
            if v == "__absent__":
                doc.append(f"- `{k}`: **missing** (key not present in the response at all)")
                any_missing = True
            elif v is None:
                doc.append(f"- `{k}`: **present but null**")
                any_missing = True
            else:
                doc.append(f"- `{k}`: present — example `{json.dumps(_truncate(v), ensure_ascii=False)}`")
        if not any_missing:
            doc.append("_(All of popularity / available_markets / linked_from / preview_url came back populated.)_")

    (HERE / "API_SHAPES.md").write_text("\n".join(doc) + "\n")


if __name__ == "__main__":
    main()
