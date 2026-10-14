"""In-process session state for the current prep session. Run locally this
is a single-user app (one DJ, one browser, one running server process), so
a module-level store is simpler and safer than pretending this is a
multi-tenant web service -- there's no second user to isolate it from.
The Move Coach overlay window relies on that too: it's a separate webview
with its own cookies, yet must see the set prepped in the browser.

The hosted demo (config.DEMO_MODE) is the exception: every visitor would
otherwise overwrite everyone else's set, so there each browser gets its
own PrepSession, keyed by a cookie that main.py's middleware sets.

Cleared whenever the server restarts.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field

from fastapi import Request

from . import config


@dataclass
class PrepSession:
    playlist_name: str | None = None
    source_tracks: list[dict] = field(default_factory=list)  # from rekordbox_db.get_playlist_tracks

    set_shape: str = "build"
    analyses: dict = field(default_factory=dict)  # {track_id: analyze_track(...) output}
    ordered_tracks: list[dict] = field(default_factory=list)
    cue_plan: dict = field(default_factory=dict)  # {track_id: [cue_dict, ...]}
    skipped_tracks: list[dict] = field(default_factory=list)  # [{"name", "artist", "reason"}]

    rekordbox_export_path: str | None = None


STATE = PrepSession()

SESSION_COOKIE = "prep_session"
MAX_DEMO_SESSIONS = 200  # oldest-used sessions are dropped past this, to bound memory
_demo_sessions: OrderedDict[str, PrepSession] = OrderedDict()
_demo_sessions_lock = threading.Lock()  # sync routes run on a thread pool


def current(request: Request) -> PrepSession:
    if not config.DEMO_MODE:
        return STATE
    sid = request.state.session_id
    with _demo_sessions_lock:
        session = _demo_sessions.get(sid)
        if session is None:
            session = _demo_sessions[sid] = PrepSession()
            if len(_demo_sessions) > MAX_DEMO_SESSIONS:
                _demo_sessions.popitem(last=False)
        else:
            _demo_sessions.move_to_end(sid)  # most recently used
        return session


def reset() -> None:
    global STATE
    STATE = PrepSession()
    _demo_sessions.clear()
