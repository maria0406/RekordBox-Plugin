"""The "learn harder skills as you progress" curriculum: five levels, each a
skill focus plus rules for which pairs of catalog tracks make a good lesson.

A lesson is a pair (track A playing, track B coming in). Difficulty comes
from two places, and the levels raise both together:
- the tracks themselves (`difficulty.rate` level: runway, tempo drift,
  phrasing, ...), and
- the pair: how far apart the tempos are and how the keys relate, using the
  same Camelot scoring as set ordering (scoring.camelot_score: 1.0 same key,
  0.8 compatible, 0.15 clash).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..scoring import camelot_score


@dataclass(frozen=True)
class Level:
    number: int
    title: str
    skills: tuple[str, ...]
    max_track_level: int  # neither track may be harder than this
    min_track_level: int  # at least one track must be at least this hard
    bpm_gap_pct: tuple[float, float]  # allowed tempo difference, percent
    key_scores: tuple[float, ...]  # allowed camelot_score values


LEVELS: tuple[Level, ...] = (
    Level(
        1, "Your first blend",
        ("Cue the incoming track on its first downbeat",
         "Start it on the first beat of a phrase",
         "Swap over with the volume faders"),
        max_track_level=1, min_track_level=1, bpm_gap_pct=(0.0, 1.0), key_scores=(1.0, 0.8),
    ),
    Level(
        2, "Beatmatching with the pitch fader",
        ("Match tempo with the pitch fader",
         "Nudge the jog wheel to keep beats aligned",
         "Swap the bass with the low EQ"),
        max_track_level=2, min_track_level=1, bpm_gap_pct=(1.5, 4.0), key_scores=(1.0, 0.8),
    ),
    Level(
        3, "Harmonic mixing",
        ("Read keys on the Camelot wheel",
         "Mix to a neighbouring or relative key",
         "Hold a longer 32-bar blend"),
        max_track_level=3, min_track_level=2, bpm_gap_pct=(0.0, 3.0), key_scores=(0.8,),
    ),
    Level(
        4, "Phrasing and structure",
        ("Count 32-bar phrases",
         "Bring a track in over a breakdown",
         "Line up one track's drop with the other's outro"),
        max_track_level=4, min_track_level=3, bpm_gap_pct=(0.0, 4.0), key_scores=(1.0, 0.8),
    ),
    Level(
        5, "Hard transitions",
        ("Ride a big tempo change",
         "Hide a key clash with filters and EQ",
         "Mix out of short intros with an echo-out"),
        max_track_level=5, min_track_level=4, bpm_gap_pct=(0.0, 8.0), key_scores=(1.0, 0.8, 0.15),
    ),
)


def bpm_gap_pct(bpm_a: float, bpm_b: float) -> float:
    return abs(bpm_b - bpm_a) / bpm_a * 100.0


def pair_fits(level: Level, a: dict, b: dict) -> bool:
    la, lb = a["difficulty"]["level"], b["difficulty"]["level"]
    if max(la, lb) > level.max_track_level or max(la, lb) < level.min_track_level:
        return False
    low, high = level.bpm_gap_pct
    if not (low <= bpm_gap_pct(a["bpm"], b["bpm"]) <= high):
        return False
    return camelot_score(a["camelot_key"], b["camelot_key"]) in level.key_scores


def build_lessons(tracks: list[dict], lessons_per_level: int = 20, max_uses_per_track: int = 2, seed: int = 0) -> list[dict]:
    """Pick up to `lessons_per_level` track pairs for every level.

    Pairs are drawn in random (seeded, so rebuilds are stable) order, and each
    track appears in at most `max_uses_per_track` lessons per level so a
    learner keeps hearing new music.
    """
    rng = random.Random(seed)
    lessons: list[dict] = []
    for level in LEVELS:
        pairs = [(a, b) for a in tracks for b in tracks if a is not b and pair_fits(level, a, b)]
        rng.shuffle(pairs)
        uses: dict[str, int] = {}
        picked = 0
        for a, b in pairs:
            if picked >= lessons_per_level:
                break
            if uses.get(a["id"], 0) >= max_uses_per_track or uses.get(b["id"], 0) >= max_uses_per_track:
                continue
            uses[a["id"]] = uses.get(a["id"], 0) + 1
            uses[b["id"]] = uses.get(b["id"], 0) + 1
            picked += 1
            lessons.append({
                "level": level.number,
                "title": level.title,
                "skills": list(level.skills),
                "track_a": a["id"],
                "track_b": b["id"],
                "bpm_gap_pct": round(bpm_gap_pct(a["bpm"], b["bpm"]), 2),
                "key_score": camelot_score(a["camelot_key"], b["camelot_key"]),
            })
    return lessons
