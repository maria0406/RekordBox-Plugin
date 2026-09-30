import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.scoring import bpm_score, camelot_score, order_tracks


class TestCamelotScore(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(camelot_score("8A", "8A"), 1.0)

    def test_relative_major_minor(self):
        self.assertEqual(camelot_score("8A", "8B"), 0.8)

    def test_adjacent_step(self):
        self.assertEqual(camelot_score("8A", "9A"), 0.8)
        self.assertEqual(camelot_score("8A", "7A"), 0.8)

    def test_wraps_12_to_1(self):
        self.assertEqual(camelot_score("12A", "1A"), 0.8)

    def test_incompatible(self):
        self.assertEqual(camelot_score("8A", "3B"), 0.15)


class TestBpmScore(unittest.TestCase):
    def test_same_tempo(self):
        self.assertEqual(bpm_score(124, 125), 1.0)

    def test_double_time(self):
        self.assertEqual(bpm_score(124, 248), 1.0)

    def test_half_time(self):
        self.assertEqual(bpm_score(124, 62), 1.0)

    def test_far_off(self):
        self.assertEqual(bpm_score(124, 90), 0.0)


class TestOrderTracks(unittest.TestCase):
    def test_locked_positions_stay_put(self):
        tracks = [
            {"id": f"t{i}", "bpm": 120 + i, "camelot_key": "8A", "energy": i}
            for i in range(6)
        ]
        ordered = order_tracks(tracks, set_shape="build", locked={0: "t3", 5: "t0"})
        self.assertEqual(ordered[0]["id"], "t3")
        self.assertEqual(ordered[5]["id"], "t0")
        self.assertEqual({t["id"] for t in ordered}, {t["id"] for t in tracks})

    def test_all_tracks_present_no_locks(self):
        tracks = [
            {"id": f"t{i}", "bpm": 120 + (i % 3) * 20, "camelot_key": f"{(i % 12) + 1}A", "energy": i % 4}
            for i in range(10)
        ]
        ordered = order_tracks(tracks, set_shape="peak")
        self.assertEqual({t["id"] for t in ordered}, {t["id"] for t in tracks})
        self.assertEqual(len(ordered), len(tracks))


if __name__ == "__main__":
    unittest.main()
