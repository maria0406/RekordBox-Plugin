"""Transition scoring and set ordering, per the design doc's
"Audio analysis and set ordering" section:

- BPM: within about 6% scores well; half or double time is allowed
- Key: same Camelot number, one step away, or the relative major/minor
  scores well
- Energy: score rises when the move matches the chosen set shape (e.g.
  rising energy during a build)

Approach: a greedy pass (always pick the best next track), followed by a
simple swap-improvement pass, per the design doc -- fast and good enough
for 10-30 tracks.
"""
from __future__ import annotations

SET_SHAPES = ("warm_up", "build", "peak", "cool_down", "custom")

_CAMELOT_LETTERS = ("A", "B")


def _parse_camelot(key: str) -> tuple[int, str] | None:
    key = (key or "").strip().upper()
    if len(key) < 2 or key[-1] not in _CAMELOT_LETTERS:
        return None
    try:
        number = int(key[:-1])
    except ValueError:
        return None
    if not (1 <= number <= 12):
        return None
    return number, key[-1]


def camelot_score(key1: str, key2: str) -> float:
    """1.0 identical, 0.8 relative major/minor or adjacent number
    (same letter), 0.15 otherwise."""
    p1, p2 = _parse_camelot(key1), _parse_camelot(key2)
    if p1 is None or p2 is None:
        return 0.15

    num1, letter1 = p1
    num2, letter2 = p2

    if num1 == num2 and letter1 == letter2:
        return 1.0
    if num1 == num2 and letter1 != letter2:
        return 0.8  # relative major/minor
    if letter1 == letter2 and (abs(num1 - num2) == 1 or abs(num1 - num2) == 11):
        return 0.8  # one Camelot step away (wraps 12 <-> 1)
    return 0.15


def bpm_score(bpm1: float, bpm2: float, tolerance: float = 0.06) -> float:
    """1.0 within `tolerance` of same tempo, half-time, or double-time;
    falls off linearly outside that band."""
    if not bpm1 or not bpm2:
        return 0.0

    ratio = bpm2 / bpm1
    # Relative distance from same-tempo (1.0), double-time (2.0), or half-time (0.5).
    best_delta = min(abs(ratio - target) / target for target in (1.0, 2.0, 0.5))
    if best_delta <= tolerance:
        return 1.0
    if best_delta >= tolerance * 4:
        return 0.0
    return max(0.0, 1.0 - (best_delta - tolerance) / (tolerance * 3))


def _target_energy_fraction(position_fraction: float, set_shape: str) -> float:
    """What energy level (0-1) we want at this point in the set, 0=start, 1=end."""
    if set_shape == "warm_up":
        return 0.15 + 0.25 * position_fraction
    if set_shape == "build":
        return position_fraction
    if set_shape == "peak":
        return 0.7 + 0.3 * (1 - abs(2 * position_fraction - 1))
    if set_shape == "cool_down":
        return 1 - 0.7 * position_fraction
    return 0.5  # custom/unspecified: energy is not scored, treat as neutral


def energy_score(track_energy: float, position_fraction: float, set_shape: str) -> float:
    """track_energy is a 0-1 normalized scalar (e.g. mean RMS, min-max
    normalized across the playlist before calling this)."""
    if set_shape == "custom":
        return 0.5
    target = _target_energy_fraction(position_fraction, set_shape)
    return max(0.0, 1.0 - abs(track_energy - target))


WEIGHTS = {"bpm": 0.4, "key": 0.35, "energy": 0.25}


def transition_score(track_a: dict, track_b: dict, b_position_fraction: float, set_shape: str) -> float:
    bpm = bpm_score(track_a["bpm"], track_b["bpm"])
    key = camelot_score(track_a["camelot_key"], track_b["camelot_key"])
    energy = energy_score(track_b.get("energy_norm", 0.5), b_position_fraction, set_shape)
    return WEIGHTS["bpm"] * bpm + WEIGHTS["key"] * key + WEIGHTS["energy"] * energy


def _normalize_energy(tracks: list[dict]) -> None:
    values = [t.get("energy", 0.0) for t in tracks]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    for t in tracks:
        t["energy_norm"] = (t.get("energy", 0.0) - lo) / span


def order_tracks(
    tracks: list[dict],
    set_shape: str = "build",
    locked: dict[int, str] | None = None,
) -> list[dict]:
    """tracks: each needs 'id', 'bpm', 'camelot_key', 'energy' (a raw scalar,
    e.g. mean RMS over the track -- normalized here).
    locked: {position_index: track_id} for tracks the DJ pinned in place
    (e.g. a fixed opener or closer); other tracks are ordered around them.
    Returns tracks in play order (same dicts, plus 'energy_norm' added)."""
    if not tracks:
        return []

    tracks = list(tracks)
    _normalize_energy(tracks)
    by_id = {t["id"]: t for t in tracks}
    n = len(tracks)
    locked = locked or {}

    remaining = {t["id"] for t in tracks}
    order: list[str | None] = [None] * n
    for pos, track_id in locked.items():
        if 0 <= pos < n and track_id in remaining:
            order[pos] = track_id
            remaining.discard(track_id)

    # Greedy fill: for each open slot in order, extend from whatever's
    # already placed immediately before it, picking the best-scoring
    # remaining track each time.
    for pos in range(n):
        if order[pos] is not None:
            continue
        prev_id = order[pos - 1] if pos > 0 else None
        position_fraction = pos / max(1, n - 1)

        if prev_id is None:
            # No predecessor to score a transition from (e.g. slot 0 is
            # open): pick the remaining track whose energy best matches
            # this position's target, so the set still opens on-shape.
            best_id = min(
                remaining,
                key=lambda tid: abs(by_id[tid]["energy_norm"] - _target_energy_fraction(position_fraction, set_shape)),
            )
        else:
            best_id = max(
                remaining,
                key=lambda tid: transition_score(by_id[prev_id], by_id[tid], position_fraction, set_shape),
            )
        order[pos] = best_id
        remaining.discard(best_id)

    # Swap-improvement pass: try swapping every pair of UNLOCKED positions;
    # keep the swap if it improves the sum of adjacent transition scores.
    def adjacent_score_sum(seq: list[str]) -> float:
        total = 0.0
        for i in range(1, n):
            total += transition_score(by_id[seq[i - 1]], by_id[seq[i]], i / max(1, n - 1), set_shape)
        return total

    locked_positions = set(locked.keys())
    improved = True
    iterations = 0
    while improved and iterations < 20:
        improved = False
        iterations += 1
        current_score = adjacent_score_sum(order)  # type: ignore[arg-type]
        for i in range(n):
            if i in locked_positions:
                continue
            for j in range(i + 1, n):
                if j in locked_positions:
                    continue
                order[i], order[j] = order[j], order[i]
                new_score = adjacent_score_sum(order)  # type: ignore[arg-type]
                if new_score > current_score + 1e-9:
                    current_score = new_score
                    improved = True
                else:
                    order[i], order[j] = order[j], order[i]

    return [by_id[tid] for tid in order]  # type: ignore[index]
