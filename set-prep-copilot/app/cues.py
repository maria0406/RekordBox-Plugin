"""Turns an ordered set (from scoring.order_tracks) plus each track's
analysis (from audio_analysis.analyze_track) into the cue plan described in
the design doc's "Transition tagging in rekordbox" section, in the shape
rekordbox_xml.write_export expects: {track_id: [cue_dict, ...]}.

Cue placement rules, from the design doc's legend table:
- MIX IN: incoming track, first downbeat of the intro phrase. Hot cue A + memory cue.
- MIX OUT: outgoing track, start of the last phrase that still leaves
  TRANSITION_BARS of track to mix over, lined up with the next track's MIX IN.
- BASS SWAP: 16 bars into the overlap, on a phrase line, on BOTH tracks.
- FILTER: outgoing track, 8 bars before it should be gone.
- DROP: incoming track, its first drop.
- LOOP 8: outgoing track's outro, an 8-bar safety loop.
"""
from __future__ import annotations

from .rekordbox_xml import CUE_COLORS


def _bar_seconds(bpm: float) -> float:
    return 60.0 / bpm * 4  # 4/4 bar length in seconds


# The full transition -- 16 bars blending in, the bass swap, 8 bars of filter,
# 4 bars of fade (static/js/coach.js) -- needs about 30 bars of outgoing track.
TRANSITION_BARS = 32


def _outro_phrase(phrases: list[dict], n_bars: int) -> dict:
    """The phrase to mix out from: the latest phrase start that still leaves
    TRANSITION_BARS before the track ends. The literal last phrase is often
    only a few bars long, which ran the bass swap off the end of the track."""
    latest_start = max(0, n_bars - TRANSITION_BARS)
    fitting = [p for p in phrases if p["start_bar"] <= latest_start]
    return fitting[-1] if fitting else {"start_bar": latest_start}


def _bar_time(downbeats: list[float], bar_index: int) -> float:
    if not downbeats:
        return 0.0
    bar_index = max(0, min(bar_index, len(downbeats) - 1))
    return downbeats[bar_index]


def _format_mmss(seconds: float) -> str:
    """124.6 -> "2:05" -- minutes unpadded, seconds zero-padded, matching
    the design doc's own example ("blend at 4:05")."""
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


def build_cue_plan(ordered_tracks: list[dict], analyses: dict[str, dict]) -> dict[str, list[dict]]:
    """ordered_tracks: play order, each a dict with 'id'.
    analyses: {track_id: analyze_track(...) output}.
    Returns {track_id: [cue_dict, ...]} in the shape rekordbox_xml expects."""
    cues: dict[str, list[dict]] = {t["id"]: [] for t in ordered_tracks}

    for i in range(len(ordered_tracks) - 1):
        outgoing = ordered_tracks[i]
        incoming = ordered_tracks[i + 1]
        out_id, in_id = outgoing["id"], incoming["id"]
        out_analysis = analyses.get(out_id)
        in_analysis = analyses.get(in_id)
        if not out_analysis or not in_analysis:
            continue

        out_downbeats = out_analysis.get("downbeats") or []
        in_downbeats = in_analysis.get("downbeats") or []
        out_phrases = out_analysis.get("phrases") or []
        in_phrases = in_analysis.get("phrases") or []
        out_bpm = out_analysis.get("bpm", 120.0)

        # MIX IN: incoming track's first downbeat of its intro (first) phrase.
        intro_phrase = in_phrases[0] if in_phrases else {"start_bar": 0}
        mix_in_time = _bar_time(in_downbeats, intro_phrase["start_bar"])
        cues[in_id].append({
            "name": "MIX IN", "color_hex": CUE_COLORS["mix_in"], "start_s": mix_in_time,
            "cue_kind": "hot", "hot_cue_index": 0, "loop_end_s": None,
        })
        cues[in_id].append({
            "name": "MIX IN", "color_hex": CUE_COLORS["mix_in"], "start_s": mix_in_time,
            "cue_kind": "memory", "hot_cue_index": None, "loop_end_s": None,
        })

        # MIX OUT: outgoing track's outro phrase start, lined up with MIX IN.
        outro_phrase = _outro_phrase(out_phrases, len(out_downbeats))
        mix_out_time = _bar_time(out_downbeats, outro_phrase["start_bar"])
        cues[out_id].append({
            "name": "MIX OUT", "color_hex": CUE_COLORS["mix_out"], "start_s": mix_out_time,
            "cue_kind": "memory", "hot_cue_index": None, "loop_end_s": None,
        })

        # BASS SWAP: 16 bars into the overlap, on both tracks.
        bass_swap_out_bar = outro_phrase["start_bar"] + 16
        bass_swap_in_bar = intro_phrase["start_bar"] + 16
        cues[out_id].append({
            "name": "BASS SWAP", "color_hex": CUE_COLORS["bass_swap"], "start_s": _bar_time(out_downbeats, bass_swap_out_bar),
            "cue_kind": "memory", "hot_cue_index": None, "loop_end_s": None,
        })
        cues[in_id].append({
            "name": "BASS SWAP", "color_hex": CUE_COLORS["bass_swap"], "start_s": _bar_time(in_downbeats, bass_swap_in_bar),
            "cue_kind": "memory", "hot_cue_index": None, "loop_end_s": None,
        })

        # FILTER: outgoing track, 8 bars before MIX OUT's phrase line.
        filter_bar = max(0, outro_phrase["start_bar"] - 8)
        cues[out_id].append({
            "name": "FILTER", "color_hex": CUE_COLORS["filter"], "start_s": _bar_time(out_downbeats, filter_bar),
            "cue_kind": "memory", "hot_cue_index": None, "loop_end_s": None,
        })

        # DROP: incoming track's first drop section, if one was detected.
        drop_section = next((s for s in (in_analysis.get("sections") or []) if s["label"] == "drop"), None)
        if drop_section:
            cues[in_id].append({
                "name": "DROP", "color_hex": CUE_COLORS["drop"], "start_s": drop_section["start"],
                "cue_kind": "memory", "hot_cue_index": None, "loop_end_s": None,
            })

        # LOOP 8: outgoing track's outro, an 8-bar safety loop. rekordbox
        # silently drops a loop that runs past the end of the track (seen on
        # a real import), so skip it rather than export one that vanishes.
        loop_start = mix_out_time
        loop_end = loop_start + 8 * _bar_seconds(out_bpm)
        duration = out_analysis.get("duration")
        if duration is None or loop_end <= duration:
            cues[out_id].append({
                "name": "LOOP 8", "color_hex": CUE_COLORS["loop_8"], "start_s": loop_start,
                "cue_kind": "memory", "hot_cue_index": None, "loop_end_s": loop_end,
            })

    return cues


def build_transition_notes(
    ordered_tracks: list[dict], analyses: dict[str, dict], cue_plan: dict[str, list[dict]]
) -> dict[str, str]:
    """The design doc's "Transition note in the Comments field": a one-line
    summary per track, e.g. "Next: track 2, 8A to 9A, 124 to 125 BPM, blend
    at 4:05, bass swap at 4:36." Reuses build_cue_plan's own MIX OUT/BASS
    SWAP timings for that track rather than recomputing them, so the note
    can never drift from the cues actually placed.

    Returns {track_id: note}. The last track in the set has no next track,
    so it gets no entry (not an empty string) -- callers should treat a
    missing key as "no note for this track," not an error.
    """
    notes: dict[str, str] = {}

    for i in range(len(ordered_tracks) - 1):
        outgoing = ordered_tracks[i]
        incoming = ordered_tracks[i + 1]
        out_id, in_id = outgoing["id"], incoming["id"]
        out_analysis = analyses.get(out_id)
        in_analysis = analyses.get(in_id)
        if not out_analysis or not in_analysis:
            continue

        out_cues = cue_plan.get(out_id, [])
        mix_out = next((c for c in out_cues if c["name"] == "MIX OUT"), None)
        bass_swap = next((c for c in out_cues if c["name"] == "BASS SWAP"), None)
        if mix_out is None or bass_swap is None:
            continue

        notes[out_id] = (
            f"Next: {incoming.get('name', '')}, "
            f"{out_analysis.get('camelot_key', '?')} to {in_analysis.get('camelot_key', '?')}, "
            f"{out_analysis.get('bpm', 0.0):.0f} to {in_analysis.get('bpm', 0.0):.0f} BPM, "
            f"blend at {_format_mmss(mix_out['start_s'])}, "
            f"bass swap at {_format_mmss(bass_swap['start_s'])}."
        )

    return notes


def merge_coincident_memory_cues(track_cues: list[dict]) -> list[dict]:
    """rekordbox keeps only one plain memory cue per position: importing
    MIX OUT and BASS SWAP at the same millisecond silently dropped one
    (seen in a real rekordbox 7 import, Oct 2026). Merge them into a single
    cue named "MIX OUT + BASS SWAP" so the DJ still sees both instructions.
    Hot cues and loops are left alone -- rekordbox kept those alongside a
    memory cue at the same spot. Only for export: practice mode keys its
    animations off the individual cue names."""
    merged: list[dict] = []
    by_position: dict[int, dict] = {}
    for cue in track_cues:
        if cue["cue_kind"] != "memory" or cue.get("loop_end_s") is not None:
            merged.append(cue)
            continue
        position_ms = round(cue["start_s"] * 1000)
        existing = by_position.get(position_ms)
        if existing is None:
            existing = dict(cue)
            by_position[position_ms] = existing
            merged.append(existing)
        elif cue["name"] not in existing["name"].split(" + "):
            existing["name"] = f"{existing['name']} + {cue['name']}"
    return merged


def transition_timing(out_cues: list[dict], in_cues: list[dict]) -> dict | None:
    """The cue times the Move Coach conductor (static/js/coach.js) needs for
    one transition: {"mixOutS", "bassSwapS", "mixInS"}, or None if the plan
    has no MIX OUT/MIX IN for it. The outgoing track can carry two BASS
    SWAPs (one from mixing it in, one for mixing it out); the one at or after
    MIX OUT is this transition's."""
    mix_out = next((c["start_s"] for c in out_cues if c["name"] == "MIX OUT"), None)
    mix_in = next((c["start_s"] for c in in_cues if c["name"] == "MIX IN"), None)
    if mix_out is None or mix_in is None:
        return None
    bass_swap = min(
        (c["start_s"] for c in out_cues if c["name"] == "BASS SWAP" and c["start_s"] >= mix_out),
        default=None,
    )
    return {"mixOutS": mix_out, "bassSwapS": bass_swap, "mixInS": mix_in}

