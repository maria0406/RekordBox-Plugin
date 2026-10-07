"""Overlay endpoints, mounted on the main app:

- GET  /overlay        the compact coach page the overlay window loads
- GET  /overlay/state  MIDI-estimated deck positions (polled ~10x/second)
- POST /overlay/sync   manual re-sync: "deck N is at P seconds"

The overlay coaches the current prepped set (session_state, from /analyze).
Transition i plays out of deck 1 into deck 2 when i is even and back again
when odd, the way a DJ alternates decks through a set.
"""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from .. import cues, session_state
from . import listener

router = APIRouter()


def overlay_transitions() -> list[dict]:
    ordered = session_state.STATE.ordered_tracks
    plan = session_state.STATE.cue_plan
    out = []
    for i in range(len(ordered) - 1):
        out_t, in_t = ordered[i], ordered[i + 1]
        timing = cues.transition_timing(plan.get(out_t["id"], []), plan.get(in_t["id"], []))
        if timing is None:
            continue
        out.append({
            "index": i,
            "outDeck": 1 if i % 2 == 0 else 2,
            "outName": out_t["name"], "inName": in_t["name"],
            "outBpm": out_t["bpm"], "inBpm": in_t["bpm"],
            **timing,
        })
    return out


@router.get("/overlay")
def overlay_page(request: Request):
    from ..main import render  # late import: main includes this router

    listener.start()
    return render(request, "overlay.html", overlay_data={"transitions": overlay_transitions()})


@router.get("/overlay/state")
def overlay_state():
    listener.start()
    return JSONResponse(listener.snapshot())


@router.post("/overlay/sync")
def overlay_sync(deck: int = Form(...), position: float = Form(...)):
    if deck not in (1, 2):
        return JSONResponse({"error": "deck must be 1 or 2"}, status_code=400)
    listener.start()
    listener.seek(deck, position)
    return JSONResponse(listener.snapshot())
