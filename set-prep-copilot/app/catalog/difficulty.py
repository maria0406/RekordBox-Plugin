"""How hard is a track to mix? Turns `audio_analysis.analyze_track` output
into a 0-1 difficulty score, and ranks a whole catalog into 1-5 levels.

What makes a house track beginner-friendly, and the feature for each:
- A long, steady run-in and run-out to blend over (`intro_runway`,
  `outro_runway`). The classic "DJ intro" is 16-32 bars of drums before the
  full arrangement arrives.
- A tempo near the house sweet spot of ~124 BPM (`tempo_offcenter`), so a
  beginner's tracks sit close together and need small pitch moves.
- A rock-steady grid (`tempo_drift`): live-played or swung material makes
  beatmatching drift.
- A flat energy arrangement (`energy_busyness`): frequent breakdowns and
  drops give more ways to land a transition badly.

All thresholds below are heuristics to tune once we have hand-labelled
tracks (the research report recommends annotating 50-100 catalog tracks).
The runway measure is deliberately energy-based, not built on
audio_analysis's "intro" section: that section ends at the first loud bass
bar, and in house the kick drum is loud bass from bar 1, so a classic
drums-only DJ intro would read as zero bars long.
"""
from __future__ import annotations

import numpy as np

HOUSE_CENTER_BPM = 124.0
BPM_OFFCENTER_HARD = 8.0  # >= 8 BPM from center scores as fully hard (116 / 132)

RUNWAY_EASY_BARS = 32  # >= 32 bars of run-in/out scores as fully easy
FULL_ARRANGEMENT_FRACTION = 0.85  # "full arrangement" = bar RMS >= 85% of the track's loud level
LOUD_PERCENTILE = 90

# Tempo drift compares the median beat interval of successive 32-beat
# windows. Raw beat-to-beat spacing is useless here: librosa snaps beats to
# ~12 ms frames, which alone is ~2.4% jitter at 124 BPM, even on a drum machine.
# librosa's tracker also assumes one global tempo, so this only catches gross
# drift (live-played sections, tempo changes) -- subtle swing goes unnoticed.
DRIFT_WINDOW_BEATS = 32
DRIFT_EASY_CV = 0.002  # window-tempo coefficient of variation; <= 0.2% is machine-tight
DRIFT_HARD_CV = 0.015

BUSY_EASY_CV = 0.15  # bar-RMS coefficient of variation
BUSY_HARD_CV = 0.50

WEIGHTS = {
    "intro_runway": 0.30,
    "outro_runway": 0.25,
    "tempo_offcenter": 0.15,
    "tempo_drift": 0.15,
    "energy_busyness": 0.15,
}

N_LEVELS = 5


def _clamp01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _ramp(value: float, easy: float, hard: float) -> float:
    """0 at `easy`, 1 at `hard`, linear in between."""
    return _clamp01((value - easy) / (hard - easy))


def runway_bars(bar_rms: list[float]) -> tuple[int, int]:
    """Bars before the full arrangement first arrives, and bars after it last
    plays."""
    if not bar_rms:
        return 0, 0
    rms = np.asarray(bar_rms, dtype=float)
    loud = np.percentile(rms, LOUD_PERCENTILE)
    if loud <= 0:
        return 0, 0
    full = np.nonzero(rms >= FULL_ARRANGEMENT_FRACTION * loud)[0]
    return int(full[0]), int(len(rms) - 1 - full[-1])


def features(analysis: dict) -> dict:
    bpm = float(analysis.get("bpm") or 0)
    beats = np.asarray(analysis.get("beat_times") or [], dtype=float)
    bar_rms = [bar["rms"] for bar in analysis.get("energy_curve") or []]

    intro_bars, outro_bars = runway_bars(bar_rms)

    intervals = np.diff(beats)
    windows = [
        np.median(intervals[i:i + DRIFT_WINDOW_BEATS])
        for i in range(0, len(intervals) - DRIFT_WINDOW_BEATS + 1, DRIFT_WINDOW_BEATS)
    ]
    if len(windows) >= 2:
        window_tempo = np.asarray(windows)
        drift_cv = float(window_tempo.std() / window_tempo.mean())
    else:
        drift_cv = 1.0  # too few beats to judge: treat as hard

    rms = np.asarray(bar_rms, dtype=float)
    busy_cv = float(rms.std() / rms.mean()) if rms.size and rms.mean() > 0 else 1.0

    return {
        "intro_bars": intro_bars,
        "outro_bars": outro_bars,
        "tempo_window_cv": drift_cv,
        "bar_rms_cv": busy_cv,
        "intro_runway": 1.0 - _clamp01(intro_bars / RUNWAY_EASY_BARS),
        "outro_runway": 1.0 - _clamp01(outro_bars / RUNWAY_EASY_BARS),
        "tempo_offcenter": _clamp01(abs(bpm - HOUSE_CENTER_BPM) / BPM_OFFCENTER_HARD) if bpm else 1.0,
        "tempo_drift": _ramp(drift_cv, DRIFT_EASY_CV, DRIFT_HARD_CV),
        "energy_busyness": _ramp(busy_cv, BUSY_EASY_CV, BUSY_HARD_CV),
    }


def rate(analysis: dict) -> dict:
    """{"score": 0-1, "features": {...}} for one analyzed track."""
    feats = features(analysis)
    score = sum(weight * feats[name] for name, weight in WEIGHTS.items())
    return {"score": round(score, 3), "features": feats}


def assign_levels(tracks: list[dict]) -> None:
    """Set track["difficulty"]["level"] (1-5) by rank within the catalog.

    Levels are relative (the easiest fifth is level 1, and so on) rather than
    fixed score cutoffs, so every level has music to practice on whatever the
    harvest happened to find. The scores stay absolute, which keeps the
    ranking meaningful as the catalog grows.
    """
    ranked = sorted(tracks, key=lambda t: (t["difficulty"]["score"], t["id"]))
    for i, track in enumerate(ranked):
        track["difficulty"]["level"] = 1 + i * N_LEVELS // len(ranked)
