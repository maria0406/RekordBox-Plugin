"""Turns an ordered set (from scoring.order_tracks) plus each track's
analysis (from audio_analysis.analyze_track) into the cue plan described in
the design doc's "Transition tagging in rekordbox" section, in the shape
rekordbox_xml.write_export expects: {track_id: [cue_dict, ...]}.

Cue placement rules, from the design doc's legend table:
- MIX IN: incoming track, first downbeat of the intro phrase. Hot cue A + memory cue.
- MIX OUT: outgoing track, start of the outro phrase, lined up with the next
  track's MIX IN.
- BASS SWAP: 16 bars into the overlap, on a phrase line, on BOTH tracks.
- FILTER: outgoing track, 8 bars before it should be gone.
- DROP: incoming track, its first drop.
- LOOP 8: outgoing track's outro, an 8-bar safety loop.
"""
from __future__ import annotations

from .rekordbox_xml import CUE_COLORS


def _bar_seconds(bpm: float) -> float:
    return 60.0 / bpm * 4  # 4/4 bar length in seconds


def _outro_phrase(phrases: list[dict]) -> dict | None:
    return phrases[-1] if phrases else None


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
        outro_phrase = _outro_phrase(out_phrases) or {"start_bar": max(0, len(out_downbeats) - 8)}
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

        # LOOP 8: outgoing track's outro, an 8-bar safety loop.
        loop_start = mix_out_time
        loop_end = loop_start + 8 * _bar_seconds(out_bpm)
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
