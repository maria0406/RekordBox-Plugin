"""Turns an ordered set (from scoring.order_tracks) plus each track's
analysis (from audio_analysis.analyze_track) into the cue plan described in
the design doc's "Transition tagging in rekordbox" section, in the shape
rekordbox_xml.write_export expects: {track_id: [cue_dict, ...]}.

Cue placement rules, from the design doc's legend table:
- MIX IN: incoming track, first downbeat of the intro phrase. Hot cue A.
- MIX OUT: outgoing track, start of the last phrase that still leaves
  TRANSITION_BARS of track to mix over, lined up with the next track's MIX IN.
- BASS SWAP: 16 bars into the overlap, on a phrase line, on BOTH tracks.
- FILTER: outgoing track, 1 bar after its BASS SWAP (once the swap is done),
  where the 8-bar filter sweep starts -- the timing Move Coach teaches.
- DROP: incoming track, its first drop.
- LOOP 8: outgoing track, the last 8 bars of the transition, a safety loop
  to stretch the blend.

Alternate mix points, so a DJ isn't limited to one way in and one way out:
- LATE IN: incoming track, the phrase line where its full arrangement first
  arrives -- start here to skip a long intro.
- EARLY OUT: outgoing track, the phrase line where its first breakdown
  starts -- leave here instead of waiting for the outro.

Performance opportunity:
- FAKE DROP: any track, the last bar of the build-up out of its first
  breakdown -- where the crowd expects the beat back. Hold it back (loop
  that bar, cut the bass or echo out), then let the real drop hit.

No two cues on a track share a spot (see _resolve_collisions): rekordbox
drops one of two memory cues at the same position, and stacked cues are
unreadable on the waveform anyway.
"""
from __future__ import annotations

from .rekordbox_xml import CUE_COLORS


def _bar_seconds(bpm: float) -> float:
    return 60.0 / bpm * 4  # 4/4 bar length in seconds


# The full transition -- 16 bars blending in, the bass swap, 8 bars of filter,
# 4 bars of fade (static/js/coach.js) -- needs about 30 bars of outgoing track.
TRANSITION_BARS = 32
PHRASE_BARS = 8
LOOP_BARS = 8

# "Full arrangement" = a bar at least this loud, relative to the track's 90th
# percentile bar energy (same measure as catalog/difficulty.py's runway).
FULL_ARRANGEMENT_FRACTION = 0.85
# Alternates are only worth a cue when they're a real alternative: at least
# this far from the main MIX IN / MIX OUT.
MIN_ALTERNATE_GAP_BARS = 16

# Lower number wins a contested spot. Action cues (things to do) move later
# by a bar until they fit; marker cues (things that are there in the music)
# are left out instead -- a DROP moved off the drop would be wrong.
_PRIORITY = {"MIX IN": 0, "MIX OUT": 0, "BASS SWAP": 1, "FILTER": 2, "LOOP 8": 3,
             "DROP": 4, "LATE IN": 5, "EARLY OUT": 5, "FAKE DROP": 6}
_MARKERS = {"DROP", "LATE IN", "EARLY OUT", "FAKE DROP"}
MAX_SHIFT_BARS = 4


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


def _cue(name: str, color_key: str, start_s: float, bar: int | None, kind: str = "memory",
         hot_index: int | None = None, loop_end_s: float | None = None) -> dict:
    return {
        "name": name, "color_hex": CUE_COLORS[color_key], "start_s": start_s, "bar": bar,
        "cue_kind": kind, "hot_cue_index": hot_index, "loop_end_s": loop_end_s,
    }


def _bar_at(downbeats: list[float], seconds: float) -> int:
    """Index of the downbeat nearest `seconds`."""
    if not downbeats:
        return 0
    return min(range(len(downbeats)), key=lambda i: abs(downbeats[i] - seconds))


def _full_arrangement_bar(analysis: dict) -> int | None:
    rms = [bar["rms"] for bar in analysis.get("energy_curve") or []]
    if not rms:
        return None
    loud = sorted(rms)[int(0.9 * (len(rms) - 1))]
    if loud <= 0:
        return None
    return next((i for i, v in enumerate(rms) if v >= FULL_ARRANGEMENT_FRACTION * loud), None)


def _late_in(analysis: dict, mix_in_bar: int) -> dict | None:
    """Phrase line where the full arrangement arrives, if that skips a real
    intro (>= MIN_ALTERNATE_GAP_BARS) and is still in the first half."""
    downbeats = analysis.get("downbeats") or []
    full = _full_arrangement_bar(analysis)
    if full is None:
        return None
    bar = -(-full // PHRASE_BARS) * PHRASE_BARS  # round up to the phrase line
    if bar - mix_in_bar < MIN_ALTERNATE_GAP_BARS or bar > len(downbeats) // 2:
        return None
    return _cue("LATE IN", "late_in", _bar_time(downbeats, bar), bar)


def _early_out(analysis: dict, mix_out_bar: int) -> dict | None:
    """Phrase line where the first breakdown starts, if that's a real
    alternative to the outro: past the first 32 bars, and at least
    MIN_ALTERNATE_GAP_BARS before MIX OUT."""
    downbeats = analysis.get("downbeats") or []
    breakdown = next((s for s in (analysis.get("sections") or []) if s["label"] == "breakdown"), None)
    if breakdown is None:
        return None
    bar = round(_bar_at(downbeats, breakdown["start"]) / PHRASE_BARS) * PHRASE_BARS
    if bar < 32 or mix_out_bar - bar < MIN_ALTERNATE_GAP_BARS:
        return None
    return _cue("EARLY OUT", "early_out", _bar_time(downbeats, bar), bar)


def _fake_drop(analysis: dict) -> dict | None:
    """Last bar of the build out of the first breakdown, i.e. the bar right
    before the beat comes back -- only if the beat really does come back
    (the breakdown isn't the end of the track)."""
    downbeats = analysis.get("downbeats") or []
    breakdown = next((s for s in (analysis.get("sections") or []) if s["label"] == "breakdown"), None)
    if breakdown is None:
        return None
    return_bar = _bar_at(downbeats, breakdown["end"])
    if return_bar >= len(downbeats) - 1 or downbeats[return_bar] < breakdown["end"] - 0.5:
        return None
    bar = return_bar - 1
    return _cue("FAKE DROP", "fake_drop", _bar_time(downbeats, bar), bar)


def _resolve_collisions(track_cues: list[dict], downbeats: list[float], bar_s: float) -> list[dict]:
    """Guarantee no two cues sit within one bar of each other. Higher-
    priority cues keep their spot; a colliding action cue moves later a bar
    at a time (up to MAX_SHIFT_BARS), a colliding marker cue is dropped."""
    kept: list[dict] = []

    def clashes(start: float) -> bool:
        return any(abs(start - k["start_s"]) < bar_s * 0.99 for k in kept)

    for cue in sorted(track_cues, key=lambda c: (_PRIORITY.get(c["name"], 9), c["start_s"])):
        if not clashes(cue["start_s"]):
            kept.append(cue)
            continue
        if cue["name"] in _MARKERS or cue.get("bar") is None:
            continue
        for shift in range(1, MAX_SHIFT_BARS + 1):
            bar = cue["bar"] + shift
            if bar >= len(downbeats):
                break
            start = downbeats[bar]
            if not clashes(start):
                moved = dict(cue, bar=bar, start_s=start)
                if moved.get("loop_end_s") is not None:
                    moved["loop_end_s"] += start - cue["start_s"]
                kept.append(moved)
                break
    return sorted(kept, key=lambda c: c["start_s"])


def _format_mmss(seconds: float) -> str:
    """124.6 -> "2:05" -- minutes unpadded, seconds zero-padded, matching
    the design doc's own example ("blend at 4:05")."""
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


def build_cue_plan(ordered_tracks: list[dict], analyses: dict[str, dict]) -> dict[str, list[dict]]:
    """ordered_tracks: play order, each a dict with 'id'.
    analyses: {track_id: analyze_track(...) output}.
    Returns {track_id: [cue_dict, ...]} in the shape rekordbox_xml expects,
    sorted by time, with no two cues on a track within a bar of each other."""
    cues: dict[str, list[dict]] = {t["id"]: [] for t in ordered_tracks}
    mix_in_bars: dict[str, int] = {}
    mix_out_bars: dict[str, int] = {}

    for i in range(len(ordered_tracks) - 1):
        out_id, in_id = ordered_tracks[i]["id"], ordered_tracks[i + 1]["id"]
        out_analysis = analyses.get(out_id)
        in_analysis = analyses.get(in_id)
        if not out_analysis or not in_analysis:
            continue

        out_downbeats = out_analysis.get("downbeats") or []
        in_downbeats = in_analysis.get("downbeats") or []
        out_bpm = out_analysis.get("bpm", 120.0)

        # MIX IN: incoming track's first downbeat of its intro (first) phrase.
        in_phrases = in_analysis.get("phrases") or []
        mix_in_bar = in_phrases[0]["start_bar"] if in_phrases else 0
        mix_in_bars[in_id] = mix_in_bar
        cues[in_id].append(_cue("MIX IN", "mix_in", _bar_time(in_downbeats, mix_in_bar), mix_in_bar,
                                kind="hot", hot_index=0))

        # MIX OUT: outgoing track's outro phrase start, lined up with MIX IN.
        mix_out_bar = _outro_phrase(out_analysis.get("phrases") or [], len(out_downbeats))["start_bar"]
        mix_out_bars[out_id] = mix_out_bar
        cues[out_id].append(_cue("MIX OUT", "mix_out", _bar_time(out_downbeats, mix_out_bar), mix_out_bar))

        # BASS SWAP: 16 bars into the overlap, on both tracks.
        swap_out_bar, swap_in_bar = mix_out_bar + 16, mix_in_bar + 16
        cues[out_id].append(_cue("BASS SWAP", "bass_swap", _bar_time(out_downbeats, swap_out_bar), swap_out_bar))
        cues[in_id].append(_cue("BASS SWAP", "bass_swap", _bar_time(in_downbeats, swap_in_bar), swap_in_bar))

        # FILTER: outgoing track, 1 bar after its BASS SWAP -- the swap takes
        # one bar, then the 8-bar filter sweep thins the outgoing track out.
        cues[out_id].append(_cue("FILTER", "filter", _bar_time(out_downbeats, swap_out_bar + 1), swap_out_bar + 1))

        # DROP: incoming track's first drop section, if one was detected.
        drop = next((s for s in (in_analysis.get("sections") or []) if s["label"] == "drop"), None)
        if drop:
            cues[in_id].append(_cue("DROP", "drop", drop["start"], _bar_at(in_downbeats, drop["start"])))

        # LOOP 8: the last 8 bars of the transition, to stretch the blend if
        # it needs longer. rekordbox silently drops a loop that runs past the
        # end of the track (seen on a real import), so skip it rather than
        # export one that vanishes.
        loop_bar = mix_out_bar + TRANSITION_BARS - LOOP_BARS
        loop_start = _bar_time(out_downbeats, loop_bar)
        loop_end = loop_start + LOOP_BARS * _bar_seconds(out_bpm)
        duration = out_analysis.get("duration")
        if duration is None or loop_end <= duration:
            cues[out_id].append(_cue("LOOP 8", "loop_8", loop_start, loop_bar, loop_end_s=loop_end))

    for track in ordered_tracks:
        track_id = track["id"]
        analysis = analyses.get(track_id)
        if not analysis:
            continue
        if track_id in mix_in_bars:
            late_in = _late_in(analysis, mix_in_bars[track_id])
            if late_in:
                cues[track_id].append(late_in)
        if track_id in mix_out_bars:
            early_out = _early_out(analysis, mix_out_bars[track_id])
            if early_out:
                cues[track_id].append(early_out)
        fake_drop = _fake_drop(analysis)
        if fake_drop:
            cues[track_id].append(fake_drop)
        cues[track_id] = _resolve_collisions(
            cues[track_id], analysis.get("downbeats") or [], _bar_seconds(analysis.get("bpm", 120.0)),
        )

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
    one transition: {"mixOutS", "bassSwapS", "filterS", "mixInS", "fakeDropS"}, or None if
    the plan has no MIX OUT/MIX IN for it. The outgoing track can carry two
    BASS SWAPs (one from mixing it in, one for mixing it out); the one at or
    after MIX OUT is this transition's. Same for FILTER."""
    mix_out = next((c["start_s"] for c in out_cues if c["name"] == "MIX OUT"), None)
    mix_in = next((c["start_s"] for c in in_cues if c["name"] == "MIX IN"), None)
    if mix_out is None or mix_in is None:
        return None
    bass_swap = min(
        (c["start_s"] for c in out_cues if c["name"] == "BASS SWAP" and c["start_s"] >= mix_out),
        default=None,
    )
    filter_s = min(
        (c["start_s"] for c in out_cues if c["name"] == "FILTER" and c["start_s"] >= mix_out),
        default=None,
    )
    # The outgoing track's fake drop, if it comes before this transition: the
    # coach teaches it on the way to the mix.
    fake_drop = max(
        (c["start_s"] for c in out_cues if c["name"] == "FAKE DROP" and c["start_s"] < mix_out),
        default=None,
    )
    return {"mixOutS": mix_out, "bassSwapS": bass_swap, "filterS": filter_s, "mixInS": mix_in,
            "fakeDropS": fake_drop}

