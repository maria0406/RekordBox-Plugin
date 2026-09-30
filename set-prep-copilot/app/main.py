from __future__ import annotations

import secrets
import statistics
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, config, cues, rekordbox_db, rekordbox_xml, scoring, session_state, spotify_client
from .audio_analysis import analyze_track

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

app = FastAPI(title="Set Prep Copilot")
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

CUE_LEGEND = [
    {"name": "MIX IN", "color": rekordbox_xml.CUE_COLORS["mix_in"], "action": "Start the blend", "where": "Incoming track: first downbeat of the intro phrase"},
    {"name": "MIX OUT", "color": rekordbox_xml.CUE_COLORS["mix_out"], "action": "Begin leaving", "where": "Outgoing track: start of the outro phrase"},
    {"name": "BASS SWAP", "color": rekordbox_xml.CUE_COLORS["bass_swap"], "action": "Swap the bass", "where": "16 bars into the overlap, both tracks"},
    {"name": "FILTER", "color": rekordbox_xml.CUE_COLORS["filter"], "action": "Filter out", "where": "Outgoing track: 8 bars before it should be gone"},
    {"name": "DROP", "color": rekordbox_xml.CUE_COLORS["drop"], "action": "Fully in", "where": "Incoming track: its first drop"},
    {"name": "LOOP 8", "color": rekordbox_xml.CUE_COLORS["loop_8"], "action": "Safety loop", "where": "Outgoing track's outro, 8-bar loop"},
]


def render(request: Request, name: str, **context):
    return templates.TemplateResponse(request, name, {"legend": CUE_LEGEND, **context})


@app.get("/")
def index():
    if auth.is_authenticated():
        return RedirectResponse("/setup")
    return RedirectResponse("/connect")


@app.get("/connect")
def connect(request: Request):
    return render(request, "connect.html")


@app.get("/login")
def login(request: Request):
    verifier, challenge = auth.make_pkce_pair()
    state = secrets.token_urlsafe(16)
    request.session["pkce_verifier"] = verifier
    request.session["pkce_state"] = state
    return RedirectResponse(auth.build_authorize_url(challenge, state))


@app.get("/callback")
def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return render(request, "connect.html", error=f"Spotify sign-in was not completed: {error}")

    expected_state = request.session.pop("pkce_state", None)
    verifier = request.session.pop("pkce_verifier", None)
    if not verifier or not state or state != expected_state:
        return render(request, "connect.html", error="Login could not be verified (state mismatch). Please try again.")

    tokens = auth.exchange_code_for_tokens(code, verifier)
    auth.save_cached_tokens(tokens)
    return RedirectResponse("/setup")


@app.get("/logout")
def logout():
    auth.clear_cached_tokens()
    session_state.reset()
    return RedirectResponse("/connect")


def _require_auth():
    return None if auth.is_authenticated() else RedirectResponse("/connect")


@app.get("/setup")
def setup_get(request: Request):
    redirect = _require_auth()
    if redirect:
        return redirect

    me = spotify_client.get_me()
    playlists: list[dict] = []
    rekordbox_error: str | None = None
    try:
        playlists = sorted(rekordbox_db.list_playlists(), key=lambda p: p["path"])
    except rekordbox_db.RekordboxDbError as exc:
        rekordbox_error = str(exc)

    return render(
        request, "setup.html", me=me,
        playlists=playlists, rekordbox_error=rekordbox_error,
    )


@app.get("/setup/tracks")
def setup_tracks(playlist_id: str):
    redirect = _require_auth()
    if redirect:
        return redirect

    try:
        tracks = rekordbox_db.get_playlist_tracks(playlist_id)
    except rekordbox_db.RekordboxDbError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    return JSONResponse({
        "tracks": [{"id": t["track_id"], "name": t["name"], "artist": t["artist"]} for t in tracks],
    })


@app.post("/analyze")
def analyze(
    request: Request, playlist_id: str = Form(...), playlist_name: str = Form(...),
    set_shape: str = Form("build"), locked_opener_id: str = Form(""), locked_closer_id: str = Form(""),
):
    redirect = _require_auth()
    if redirect:
        return redirect

    try:
        source_tracks = rekordbox_db.get_playlist_tracks(playlist_id)
    except rekordbox_db.RekordboxDbError as exc:
        return render(request, "setup.html", me=spotify_client.get_me(), playlists=[], rekordbox_error=str(exc))

    session_state.STATE.playlist_name = playlist_name
    session_state.STATE.source_tracks = source_tracks
    session_state.STATE.set_shape = set_shape

    analyses: dict[str, dict] = {}
    scoring_input: list[dict] = []
    skipped: list[dict] = []
    for track in source_tracks:
        track_id = track["track_id"]
        try:
            result = analyze_track(track["location"])
        except (FileNotFoundError, RuntimeError, OSError) as exc:
            # Common in a real library: a file that's been moved, renamed, or
            # deleted since rekordbox last saw it. Skip it and tell the DJ,
            # rather than failing the whole analysis run.
            skipped.append({"name": track["name"], "artist": track["artist"], "reason": str(exc)})
            continue
        analyses[track_id] = result
        mean_rms = statistics.fmean(pt["rms"] for pt in result["energy_curve"]) if result["energy_curve"] else 0.0
        scoring_input.append({
            # Both keys carry the same value: scoring.py reads "id",
            # rekordbox_xml.write_export reads "track_id". Everything past
            # "isrc" isn't used for scoring -- it rides along so
            # rekordbox_xml.write_export (called later, on ordered_tracks)
            # has what it needs to build a valid TRACK element.
            "id": track_id,
            "track_id": track_id,
            "bpm": result["bpm"],
            # write_export reads "average_bpm" for the exported AverageBpm
            # attribute; our own measured tempo is more accurate than
            # whatever rekordbox's own analysis said, so that's what goes out.
            "average_bpm": result["bpm"],
            "camelot_key": result["camelot_key"],
            "energy": mean_rms,
            "name": track["name"],
            "artist": track["artist"],
            "isrc": track.get("isrc"),
            "album": track.get("album"),
            "total_time": track.get("total_time"),
            "tonality": track.get("tonality"),
            "location": track["location"],
            "raw_attrib": track.get("raw_attrib"),
        })

    locked: dict[int, str] = {}
    scoring_ids = {t["id"] for t in scoring_input}
    if locked_opener_id and locked_opener_id in scoring_ids:
        locked[0] = locked_opener_id
    if locked_closer_id and locked_closer_id in scoring_ids and locked_closer_id != locked_opener_id:
        locked[len(scoring_input) - 1] = locked_closer_id

    ordered = scoring.order_tracks(scoring_input, set_shape=set_shape, locked=locked)
    plan = cues.build_cue_plan(ordered, analyses)

    session_state.STATE.analyses = analyses
    session_state.STATE.ordered_tracks = ordered
    session_state.STATE.cue_plan = plan
    session_state.STATE.skipped_tracks = skipped
    return RedirectResponse("/results", status_code=303)


@app.get("/results")
def results(request: Request):
    redirect = _require_auth()
    if redirect:
        return redirect
    if not session_state.STATE.ordered_tracks:
        return RedirectResponse("/setup")

    return render(
        request, "results.html",
        ordered_tracks=session_state.STATE.ordered_tracks,
        cue_plan=session_state.STATE.cue_plan,
        playlist_name=session_state.STATE.playlist_name,
        set_shape=session_state.STATE.set_shape,
        spotify_playlist_url=session_state.STATE.spotify_playlist_url,
        rekordbox_export_ready=bool(session_state.STATE.rekordbox_export_path),
        skipped_tracks=session_state.STATE.skipped_tracks,
    )


@app.post("/results/move")
def results_move(track_id: str = Form(...), direction: str = Form(...)):
    redirect = _require_auth()
    if redirect:
        return redirect

    ordered = session_state.STATE.ordered_tracks
    index = next((i for i, t in enumerate(ordered) if t["id"] == track_id), None)
    if index is not None:
        target = index - 1 if direction == "up" else index + 1
        if 0 <= target < len(ordered):
            ordered[index], ordered[target] = ordered[target], ordered[index]
            # Cue placement depends on track order, so it must be rebuilt --
            # left stale it would still describe the pre-swap transitions.
            session_state.STATE.cue_plan = cues.build_cue_plan(ordered, session_state.STATE.analyses)

    return RedirectResponse("/results", status_code=303)


@app.post("/results/nudge-cue")
def results_nudge_cue(track_id: str = Form(...), cue_index: int = Form(...), delta_seconds: float = Form(...)):
    redirect = _require_auth()
    if redirect:
        return redirect

    track_cues = session_state.STATE.cue_plan.get(track_id)
    if track_cues is not None and 0 <= cue_index < len(track_cues):
        cue = track_cues[cue_index]
        cue["start_s"] = max(0.0, cue["start_s"] + delta_seconds)
        if cue.get("loop_end_s") is not None:
            cue["loop_end_s"] = max(cue["start_s"], cue["loop_end_s"] + delta_seconds)

    return RedirectResponse("/results", status_code=303)


@app.post("/export/rekordbox")
def export_rekordbox():
    redirect = _require_auth()
    if redirect:
        return redirect

    out_name = f"{(session_state.STATE.playlist_name or 'set').replace(' ', '_')}_prepped.xml"
    out_path = config.UPLOADS_DIR / out_name
    comments_by_track_id = cues.build_transition_notes(
        session_state.STATE.ordered_tracks, session_state.STATE.analyses, session_state.STATE.cue_plan,
    )
    rekordbox_xml.write_export(
        tracks_in_order=session_state.STATE.ordered_tracks,
        cues_by_track_id=session_state.STATE.cue_plan,
        output_path=str(out_path),
        playlist_name=f"{session_state.STATE.playlist_name} (Prepped)",
        comments_by_track_id=comments_by_track_id,
    )
    session_state.STATE.rekordbox_export_path = str(out_path)
    return FileResponse(out_path, filename=out_name, media_type="application/xml")


@app.get("/export/spotify/preview")
def export_spotify_preview(request: Request):
    redirect = _require_auth()
    if redirect:
        return redirect
    if not session_state.STATE.ordered_tracks:
        return RedirectResponse("/setup")

    matches = {}
    for track in session_state.STATE.ordered_tracks:
        matched, confidence = spotify_client.match_track_by_isrc_then_text(
            track.get("isrc"), track.get("name", ""), track.get("artist", ""),
        )
        matches[track["id"]] = {"track": matched, "confidence": confidence}

    session_state.STATE.spotify_matches = matches

    rows = [
        {"track": track, "match": matches[track["id"]]["track"], "confidence": matches[track["id"]]["confidence"]}
        for track in session_state.STATE.ordered_tracks
    ]
    return render(request, "results_spotify_preview.html", rows=rows, playlist_name=session_state.STATE.playlist_name)


@app.post("/export/spotify/confirm")
async def export_spotify_confirm(request: Request):
    redirect = _require_auth()
    if redirect:
        return redirect

    form = await request.form()
    uris: list[str] = []
    for track in session_state.STATE.ordered_tracks:
        if form.get(f"include_{track['id']}"):
            matched = (session_state.STATE.spotify_matches.get(track["id"]) or {}).get("track")
            if matched:
                uris.append(matched["uri"])

    playlist = spotify_client.create_playlist(
        name=f"Set Prep: {session_state.STATE.playlist_name}",
        description="Ordered by Set Prep Copilot.",
    )
    if uris:
        spotify_client.add_items_to_playlist(playlist["id"], uris)

    session_state.STATE.spotify_playlist_url = playlist.get("external_urls", {}).get("spotify")
    return RedirectResponse("/results", status_code=303)


@app.get("/practice")
def practice(request: Request):
    redirect = _require_auth()
    if redirect:
        return redirect
    if not session_state.STATE.ordered_tracks:
        return RedirectResponse("/setup")

    transitions = []
    ordered = session_state.STATE.ordered_tracks
    plan = session_state.STATE.cue_plan
    for i in range(len(ordered) - 1):
        out_t, in_t = ordered[i], ordered[i + 1]
        transitions.append({
            "outgoing": out_t, "incoming": in_t,
            "outgoing_cues": plan.get(out_t["id"], []),
            "incoming_cues": plan.get(in_t["id"], []),
        })

    return render(request, "practice.html", transitions=transitions)
