import os
import re
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.audio_analysis import analyze_track  # noqa: E402


def _make_click_track(bpm: float, duration_s: float, sr: int = 22050) -> np.ndarray:
    """A synthetic 'kick drum' click track: a decaying 60 Hz burst on every beat."""
    n_samples = int(duration_s * sr)
    y = np.zeros(n_samples, dtype=np.float32)
    beat_interval = 60.0 / bpm
    t_burst = np.arange(int(0.08 * sr)) / sr  # 80ms burst
    burst = np.sin(2 * np.pi * 60.0 * t_burst) * np.exp(-t_burst * 40.0)

    beat_time = 0.0
    while beat_time < duration_s:
        start = int(beat_time * sr)
        end = min(start + len(burst), n_samples)
        y[start:end] += burst[: end - start]
        beat_time += beat_interval

    return y


class TestAudioAnalysis(unittest.TestCase):
    def setUp(self):
        self.true_bpm = 128.0
        y = _make_click_track(self.true_bpm, duration_s=30.0)
        self.tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(self.tmp.name, y, 22050)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_bpm_recovered_within_tolerance(self):
        result = analyze_track(self.tmp.name)
        bpm = result["bpm"]
        # Beat trackers commonly lock onto a tempo octave (2x or 0.5x) on a
        # sparse click track; accept the true tempo or a clean octave of it.
        candidates = [self.true_bpm, self.true_bpm * 2, self.true_bpm / 2]
        closest = min(candidates, key=lambda c: abs(c - bpm))
        self.assertLess(
            abs(bpm - closest), 4.0,
            f"BPM {bpm} not within tolerance of any of {candidates}",
        )

    def test_shapes_and_types(self):
        result = analyze_track(self.tmp.name)

        self.assertIsInstance(result["bpm"], float)
        self.assertIsInstance(result["beat_times"], list)
        self.assertTrue(all(isinstance(t, float) for t in result["beat_times"]))

        self.assertIsInstance(result["downbeats"], list)

        self.assertRegex(result["camelot_key"], r"^\d{1,2}[AB]$")
        self.assertIsInstance(result["key_confidence"], float)

        self.assertIsInstance(result["energy_curve"], list)
        for bar in result["energy_curve"]:
            self.assertIn("bar_start", bar)
            self.assertIn("rms", bar)
            self.assertIn("bass_rms", bar)
            self.assertIsInstance(bar["rms"], float)
            self.assertIsInstance(bar["bass_rms"], float)

        self.assertIsInstance(result["sections"], list)
        allowed_labels = {"intro", "drop", "breakdown", "outro"}
        for section in result["sections"]:
            self.assertIn(section["label"], allowed_labels)
            self.assertLessEqual(section["start"], section["end"])

        self.assertIsInstance(result["phrases"], list)
        for phrase in result["phrases"]:
            self.assertIsInstance(phrase["start_bar"], int)
            self.assertIsInstance(phrase["length"], int)
            self.assertGreater(phrase["length"], 0)

        self.assertIsInstance(result["duration"], float)
        self.assertGreater(result["duration"], 0)

    def test_short_audio_does_not_crash(self):
        # 3 seconds -- fewer than 4 beats at 128 BPM, exercises the
        # downbeats/bars edge case where there may be 0 or 1 bar.
        y = _make_click_track(self.true_bpm, duration_s=3.0)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            sf.write(tmp.name, y, 22050)
            result = analyze_track(tmp.name)
            self.assertIsInstance(result["bpm"], float)
        finally:
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
