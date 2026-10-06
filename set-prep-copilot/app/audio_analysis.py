"""Per-track audio analysis for Set Prep Copilot.

Implements the design doc's "Audio analysis and set ordering" table: BPM and
beat grid, downbeats/bars, phrases, an energy curve (full-band + bass-band),
a Camelot-notation key estimate, and heuristic section labels.

What's solid vs. what's a tunable heuristic
--------------------------------------------
- BPM / beat grid (`bpm`, `beat_times`): librosa's beat tracker is mature and
  reliable for fixed-tempo 4/4 house/techno, which is this product's target
  material. Trust the beat times. `bpm` is fitted to those beat times
  (`bpm_from_beats`), NOT librosa's own tempo estimate: that estimate comes
  from a tempogram whose bins are ~3 BPM apart around 124 (sr 44.1k, hop
  512 -> 60*44100/512/lag = 120.19, 123.05, 126.05, ...). A 300-track
  catalog landed on just 15 distinct values, and a track rekordbox reads as
  124.00 came out as 123.05.
- Downbeats/bars (`downbeats`): a simple "every 4th beat starting at the
  first beat" heuristic, not true downbeat detection. Fine for fixed-tempo
  4/4 material per the design doc; would need real downbeat detection for
  anything with pickup beats, tempo changes, or non-4/4 material.
- Key (`camelot_key`, `key_confidence`): a whole-track-average
  Krumhansl-Schmuckler chroma correlation. This is a classical, well-known
  algorithm, but the design doc's own risk table already commits to
  benchmarking against rekordbox's own key values on 20 tracks before
  trusting it for real ordering decisions -- treat this as a v0 baseline,
  not a finished key detector. It ignores modulation (key changes mid-track)
  and picks one whole-track key.
- Sections (`sections`) and phrases (`phrases`): heuristic thresholds on the
  bass-energy curve (documented inline below). The design doc explicitly
  treats rekordbox's own phrase analysis as "a useful benchmark for testing
  ours" -- i.e. these are expected to be approximations to be tuned against
  real tracks, not a finished structural-analysis system.
"""
from __future__ import annotations

import numpy as np
import librosa
from scipy.signal import butter, sosfiltfilt

# ---------------------------------------------------------------------------
# Camelot wheel mapping
# ---------------------------------------------------------------------------
# Pitch class indices follow librosa's chroma convention: 0 = C, 1 = C#, ...
# 11 = B. Verified against the standard reference points: C major = 8B,
# A minor = 8A, G major = 9B, E minor = 9A (relative major/minor pairs share
# a Camelot number; majors are "B", minors are "A"; each step around the
# wheel is a fifth).
MAJOR_CAMELOT = {
    0: "8B", 1: "3B", 2: "10B", 3: "5B", 4: "12B", 5: "7B",
    6: "2B", 7: "9B", 8: "4B", 9: "11B", 10: "6B", 11: "1B",
}
MINOR_CAMELOT = {
    0: "5A", 1: "12A", 2: "7A", 3: "2A", 4: "9A", 5: "4A",
    6: "11A", 7: "6A", 8: "1A", 9: "8A", 10: "3A", 11: "10A",
}

# Krumhansl-Kessler key profiles (standard, widely published values).
_MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

BASS_BAND_HZ = (30.0, 200.0)  # low-frequency band used for bass-presence RMS


MIN_BEATS_FOR_FIT = 16


def bpm_from_beats(beat_times: list[float], fallback: float) -> float:
    """Least-squares slope of beat time vs. beat index. Each beat time is
    quantized to a ~12 ms frame, but the fit averages that out over the
    whole track, giving sub-0.1 BPM resolution on a steady 4/4 track."""
    if len(beat_times) < MIN_BEATS_FOR_FIT:
        return fallback
    slope = np.polyfit(np.arange(len(beat_times)), np.asarray(beat_times), 1)[0]
    return float(60.0 / slope) if slope > 0 else fallback


def _pearson_corr(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _estimate_key(y: np.ndarray, sr: int) -> tuple[str, float]:
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)

    best_corr = -2.0
    best_pc = 0
    best_is_major = True
    for pc in range(12):
        major_corr = _pearson_corr(chroma_mean, np.roll(_MAJOR_PROFILE, pc))
        minor_corr = _pearson_corr(chroma_mean, np.roll(_MINOR_PROFILE, pc))
        if major_corr > best_corr:
            best_corr, best_pc, best_is_major = major_corr, pc, True
        if minor_corr > best_corr:
            best_corr, best_pc, best_is_major = minor_corr, pc, False

    camelot = (MAJOR_CAMELOT if best_is_major else MINOR_CAMELOT)[best_pc]
    return camelot, best_corr


def _bass_filter(y: np.ndarray, sr: int) -> np.ndarray:
    nyquist = sr / 2.0
    low, high = BASS_BAND_HZ
    high = min(high, nyquist * 0.99)
    sos = butter(4, [low / nyquist, high / nyquist], btype="band", output="sos")
    return sosfiltfilt(sos, y)


def _bars_from_downbeats(downbeats: list[float], track_duration: float) -> list[tuple[float, float]]:
    """Return (start, end) pairs for every bar, using downbeats as bar starts."""
    if not downbeats:
        return []
    bounds = list(downbeats) + [track_duration]
    return list(zip(bounds[:-1], bounds[1:]))


def _bar_average(times: np.ndarray, values: np.ndarray, bar_start: float, bar_end: float) -> float:
    mask = (times >= bar_start) & (times < bar_end)
    if not np.any(mask):
        return 0.0
    return float(values[mask].mean())


def _label_sections(bars: list[tuple[float, float]], bass_rms: list[float], full_rms: list[float]) -> list[dict]:
    """Heuristic section labeling from the bass-energy curve.

    Thresholds (documented, tunable):
    - "high" bass bar: bass_rms >= 0.3 * max(bass_rms) over the track.
    - intro: the leading run of bars before the first "high" bass bar.
    - drop: the first bar where bass_rms jumps by >= 0.25 * max(bass_rms)
      versus the previous bar (a sudden bass entrance), plus the following
      8 bars.
    - breakdown: the first contiguous run of >= 8 "low" bass bars (bass_rms
      < 0.3 * max) that starts after the drop.
    - outro: the trailing run of bars (at least 8, or fewer if the track is
      short) where full-band RMS is monotonically non-increasing into the
      final bar.
    """
    n = len(bars)
    if n == 0:
        return []

    bass = np.array(bass_rms)
    full = np.array(full_rms)
    bass_max = bass.max() if bass.max() > 0 else 1.0
    high_thresh = 0.3 * bass_max
    jump_thresh = 0.25 * bass_max

    sections: list[dict] = []

    # Intro: leading bars before bass energy first crosses high_thresh.
    first_high = next((i for i in range(n) if bass[i] >= high_thresh), n)
    if first_high > 0:
        sections.append({"label": "intro", "start": bars[0][0], "end": bars[first_high - 1][1]})

    # Drop: first sudden bass jump after the intro.
    drop_bar = None
    for i in range(max(1, first_high), n):
        if bass[i] - bass[i - 1] >= jump_thresh:
            drop_bar = i
            break
    if drop_bar is not None:
        drop_end = min(drop_bar + 8, n) - 1
        sections.append({"label": "drop", "start": bars[drop_bar][0], "end": bars[drop_end][1]})

    # Breakdown: first run of >=8 low-bass bars after the drop (or after the intro).
    scan_from = (drop_bar + 1) if drop_bar is not None else first_high
    run_start = None
    breakdown = None
    for i in range(scan_from, n):
        if bass[i] < high_thresh:
            if run_start is None:
                run_start = i
            if i - run_start + 1 >= 8:
                breakdown = (run_start, i)
        else:
            run_start = None
    if breakdown is not None:
        sections.append({"label": "breakdown", "start": bars[breakdown[0]][0], "end": bars[breakdown[1]][1]})

    # Outro: trailing bars where full-band RMS is non-increasing into the end.
    outro_window = min(16, n)
    start_idx = n - outro_window
    tail = full[start_idx:]
    outro_start = start_idx
    for i in range(len(tail) - 1, 0, -1):
        if tail[i] > tail[i - 1] * 1.05:  # energy rose again; outro starts after this
            outro_start = start_idx + i
            break
    sections.append({"label": "outro", "start": bars[outro_start][0], "end": bars[-1][1]})

    return sections


def _group_phrases(bars: list[tuple[float, float]], bass_rms: list[float]) -> list[dict]:
    """Group bars into 8-bar blocks, merging adjacent blocks toward 16/32 when
    their average bass energy is close (a light stand-in for "confirm with
    structural change detection" -- not real segmentation).
    """
    n = len(bars)
    if n == 0:
        return []

    block_size = 8
    blocks: list[dict] = []
    for start in range(0, n, block_size):
        end = min(start + block_size, n)
        avg = float(np.mean(bass_rms[start:end])) if end > start else 0.0
        blocks.append({"start_bar": start, "length": end - start, "avg_bass": avg})

    merged: list[dict] = []
    i = 0
    while i < len(blocks):
        cur = blocks[i]
        # Try to merge with the next block(s) if energy is close and we stay <= 32 bars.
        while (
            i + 1 < len(blocks)
            and cur["length"] + blocks[i + 1]["length"] <= 32
            and cur["avg_bass"] > 0
            and abs(cur["avg_bass"] - blocks[i + 1]["avg_bass"]) <= 0.15 * cur["avg_bass"]
        ):
            nxt = blocks[i + 1]
            total = cur["length"] + nxt["length"]
            cur = {
                "start_bar": cur["start_bar"],
                "length": total,
                "avg_bass": (cur["avg_bass"] * cur["length"] + nxt["avg_bass"] * nxt["length"]) / total,
            }
            i += 1
        merged.append({"start_bar": cur["start_bar"], "length": cur["length"]})
        i += 1

    return merged


def analyze_track(file_path: str) -> dict:
    y, sr = librosa.load(file_path, sr=None, mono=True)
    duration = float(len(y) / sr)

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    bpm = bpm_from_beats(beat_times, fallback=float(np.atleast_1d(tempo)[0]))

    downbeats = beat_times[0::4]
    bars = _bars_from_downbeats(downbeats, duration)

    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)

    bass_y = _bass_filter(y, sr)
    bass_rms = librosa.feature.rms(y=bass_y)[0]
    bass_rms_times = librosa.frames_to_time(np.arange(len(bass_rms)), sr=sr, hop_length=512)

    energy_curve = []
    bass_rms_per_bar: list[float] = []
    full_rms_per_bar: list[float] = []
    for bar_start, bar_end in bars:
        bar_rms = _bar_average(rms_times, rms, bar_start, bar_end)
        bar_bass = _bar_average(bass_rms_times, bass_rms, bar_start, bar_end)
        energy_curve.append({"bar_start": bar_start, "rms": bar_rms, "bass_rms": bar_bass})
        full_rms_per_bar.append(bar_rms)
        bass_rms_per_bar.append(bar_bass)

    camelot_key, key_confidence = _estimate_key(y, sr)
    sections = _label_sections(bars, bass_rms_per_bar, full_rms_per_bar)
    phrases = _group_phrases(bars, bass_rms_per_bar)

    return {
        "bpm": bpm,
        "beat_times": beat_times,
        "downbeats": downbeats,
        "camelot_key": camelot_key,
        "key_confidence": key_confidence,
        "energy_curve": energy_curve,
        "sections": sections,
        "phrases": phrases,
        "duration": duration,
    }
