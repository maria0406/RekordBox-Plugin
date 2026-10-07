from __future__ import annotations

import statistics
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, cues, rekordbox_db, rekordbox_xml, scoring, session_state
from .audio_analysis import analyze_track

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

app = FastAPI(title="Set Prep Copilot")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

CUE_LEGEND = [
    {"name": "MIX IN", "color": rekordbox_xml.CUE_COLORS["mix_in"], "action": "Start the blend", "where": "Incoming track: hot cue A, first downbeat of the intro phrase"},
    {"name": "MIX OUT", "color": rekordbox_xml.CUE_COLORS["mix_out"], "action": "Begin leaving", "where": "Outgoing track: start of the outro phrase"},
    {"name": "BASS SWAP", "color": rekordbox_xml.CUE_COLORS["bass_swap"], "action": "Swap the bass", "where": "16 bars into the overlap, both tracks"},
    {"name": "FILTER", "color": rekordbox_xml.CUE_COLORS["filter"], "action": "Filter out", "where": "Outgoing track: 1 bar after its BASS SWAP, 8-bar sweep"},
    {"name": "DROP", "color": rekordbox_xml.CUE_COLORS["drop"], "action": "Fully in", "where": "Incoming track: its first drop"},
    {"name": "LOOP 8", "color": rekordbox_xml.CUE_COLORS["loop_8"], "action": "Safety loop", "where": "Outgoing track: last 8 bars of the transition, to stretch the blend"},
    {"name": "LATE IN", "color": rekordbox_xml.CUE_COLORS["late_in"], "action": "Alternate start", "where": "Incoming track: where the full beat arrives, to skip a long intro"},
    {"name": "EARLY OUT", "color": rekordbox_xml.CUE_COLORS["early_out"], "action": "Alternate exit", "where": "Outgoing track: its first breakdown, to leave before the outro"},
    {"name": "FAKE DROP", "color": rekordbox_xml.CUE_COLORS["fake_drop"], "action": "Hold back the drop", "where": "Any track: last bar of a build-up; loop it or cut the bass, then let the drop hit"},
]


def render(request: Request, name: str, **context):
    return templates.TemplateResponse(request, name, {"legend": CUE_LEGEND, **context})


@app.get("/")
def index():
    return RedirectResponse("/setup")


@app.get("/setup")
def setup_get(request: Request):
    playlists: list[dict] = []
    rekordbox_error: str | None = None
    try:
        playlists = sorted(rekordbox_db.list_playlists(), key=lambda p: p["path"])
    except rekordbox_db.RekordboxDbError as exc:
        rekordbox_error = str(exc)

    return render(
        request, "setup.html",
        playlists=playlists, rekordbox_error=rekordbox_error,
    )


@app.get("/setup/tracks")
def setup_tracks(playlist_id: str):
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
    try:
        source_tracks = rekordbox_db.get_playlist_tracks(playlist_id)
    except rekordbox_db.RekordboxDbError as exc:
        return render(request, "setup.html", playlists=[], rekordbox_error=str(exc))

    if not source_tracks:
        return render(
            request, "setup.html",
            playlists=sorted(rekordbox_db.list_playlists(), key=lambda p: p["path"]),
            rekordbox_error=(
                f"{playlist_name!r} has no tracks with a local audio file rekordbox can see "
                "(it may be empty, or every track in it is streamed/missing). Pick a playlist "
                "that has local tracks in it, or add some to this one in rekordbox first."
            ),
        )

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
            # attribute. Send back rekordbox's own value untouched: importing
            # the XML overwrites the library's BPM field, and the DJ's decks
            # run on rekordbox's beat grid, not ours (same for "tonality").
            "average_bpm": track.get("average_bpm"),
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

    if not scoring_input:
        return render(
            request, "setup.html",
            playlists=sorted(rekordbox_db.list_playlists(), key=lambda p: p["path"]),
            rekordbox_error=(
                f"None of the {len(source_tracks)} track(s) in {playlist_name!r} could be "
                f"analyzed — their audio files couldn't be read: "
                + "; ".join(f"{s['name']} ({s['reason']})" for s in skipped)
            ),
        )

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
    if not session_state.STATE.ordered_tracks:
        return RedirectResponse("/setup")

    return render(
        request, "results.html",
        ordered_tracks=session_state.STATE.ordered_tracks,
        cue_plan=session_state.STATE.cue_plan,
        playlist_name=session_state.STATE.playlist_name,
        set_shape=session_state.STATE.set_shape,
        rekordbox_export_ready=bool(session_state.STATE.rekordbox_export_path),
        skipped_tracks=session_state.STATE.skipped_tracks,
    )


@app.post("/results/move")
def results_move(track_id: str = Form(...), direction: str = Form(...)):
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
    track_cues = session_state.STATE.cue_plan.get(track_id)
    if track_cues is not None and 0 <= cue_index < len(track_cues):
        cue = track_cues[cue_index]
        cue["start_s"] = max(0.0, cue["start_s"] + delta_seconds)
        if cue.get("loop_end_s") is not None:
            cue["loop_end_s"] = max(cue["start_s"], cue["loop_end_s"] + delta_seconds)

    return RedirectResponse("/results", status_code=303)


@app.post("/export/rekordbox")
def export_rekordbox():
    out_name = f"{(session_state.STATE.playlist_name or 'set').replace(' ', '_')}_prepped.xml"
    out_path = config.UPLOADS_DIR / out_name
    comments_by_track_id = cues.build_transition_notes(
        session_state.STATE.ordered_tracks, session_state.STATE.analyses, session_state.STATE.cue_plan,
    )
    rekordbox_xml.write_export(
        tracks_in_order=session_state.STATE.ordered_tracks,
        cues_by_track_id={
            track_id: cues.merge_coincident_memory_cues(track_cues)
            for track_id, track_cues in session_state.STATE.cue_plan.items()
        },
        output_path=str(out_path),
        playlist_name=f"{session_state.STATE.playlist_name} (Prepped)",
        comments_by_track_id=comments_by_track_id,
    )
    session_state.STATE.rekordbox_export_path = str(out_path)
    return FileResponse(out_path, filename=out_name, media_type="application/xml")


@app.get("/practice")
def practice(request: Request):
    if not session_state.STATE.ordered_tracks:
        return RedirectResponse("/setup")

    transitions = []
    coach_data = []
    ordered = session_state.STATE.ordered_tracks
    plan = session_state.STATE.cue_plan
    for i in range(len(ordered) - 1):
        out_t, in_t = ordered[i], ordered[i + 1]
        timing = cues.transition_timing(plan.get(out_t["id"], []), plan.get(in_t["id"], []))
        if timing is None:
            continue
        transitions.append({"outgoing": out_t, "incoming": in_t})
        coach_data.append({
            "outId": out_t["id"], "inId": in_t["id"],
            "outName": out_t["name"], "inName": in_t["name"],
            "outBpm": out_t["bpm"], "inBpm": in_t["bpm"],
            **timing,
        })

    return render(request, "practice.html", transitions=transitions, practice_data={"transitions": coach_data})


@app.get("/audio/{track_id}")
def audio(track_id: str):
    """Stream a track in the current set to the practice demo. Only files of
    tracks already in the session's set are served -- never an arbitrary path."""
    track = next((t for t in session_state.STATE.ordered_tracks if t["id"] == track_id), None)
    if track is None or not Path(track["location"]).is_file():
        return JSONResponse({"error": "unknown track"}, status_code=404)
    return FileResponse(track["location"])
