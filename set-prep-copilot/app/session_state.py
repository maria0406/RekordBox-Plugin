"""In-process session state for the current prep session. This is a local,
single-user app (one DJ, one browser, one running server process), so a
module-level store is simpler and safer than pretending this is a
multi-tenant web service -- there's no second user to isolate it from.
Cleared whenever the server restarts.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PrepSession:
    pkce_verifier: str | None = None
    pkce_state: str | None = None

    playlist_name: str | None = None
    source_tracks: list[dict] = field(default_factory=list)  # from rekordbox_db.get_playlist_tracks

    set_shape: str = "build"
    analyses: dict = field(default_factory=dict)  # {track_id: analyze_track(...) output}
    ordered_tracks: list[dict] = field(default_factory=list)
    cue_plan: dict = field(default_factory=dict)  # {track_id: [cue_dict, ...]}
    skipped_tracks: list[dict] = field(default_factory=list)  # [{"name", "artist", "reason"}]

    spotify_matches: dict = field(default_factory=dict)  # {track_id: {"track": spotify_track, "confidence": str}}
    spotify_playlist_url: str | None = None
    rekordbox_export_path: str | None = None


STATE = PrepSession()


def reset() -> None:
    global STATE
    STATE = PrepSession()
