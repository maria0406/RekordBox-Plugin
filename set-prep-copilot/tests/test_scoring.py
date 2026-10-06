import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.scoring import bpm_score, camelot_score, energy_score, order_tracks, _energy_level, _normalize_energy


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


class TestEnergyLevel(unittest.TestCase):
    def test_buckets_into_1_to_10(self):
        self.assertEqual(_energy_level(0.0), 1)
        self.assertEqual(_energy_level(1.0), 10)
        self.assertEqual(_energy_level(0.05), 1)
        self.assertEqual(_energy_level(0.55), 6)

    def test_normalize_energy_sets_both_norm_and_level(self):
        tracks = [{"energy": 0.0}, {"energy": 5.0}, {"energy": 10.0}]
        _normalize_energy(tracks)
        self.assertEqual(tracks[0]["energy_level"], 1)
        self.assertEqual(tracks[2]["energy_level"], 10)
        self.assertIn("energy_norm", tracks[1])


class TestEnergyScore(unittest.TestCase):
    def test_no_predecessor_scores_fit_only(self):
        # Level 5 with no predecessor, mid-set during a build (target ~ mid):
        # should just reflect fit, no smoothness term to apply.
        score = energy_score(None, current_level=5, position_fraction=0.5, set_shape="build")
        self.assertGreater(score, 0.0)

    def test_one_level_jump_is_fully_smooth(self):
        a = energy_score(5, 6, position_fraction=0.5, set_shape="build")
        b = energy_score(5, 5, position_fraction=0.5, set_shape="build")
        # Both are within the "smooth" band (jump <= 1); scores should be close,
        # not penalized relative to each other for smoothness.
        self.assertAlmostEqual(a, b, delta=0.21)  # differ only by the "fit" term

    def test_large_jump_is_penalized_vs_small_jump(self):
        small_jump = energy_score(5, 6, position_fraction=0.5, set_shape="build")
        big_jump = energy_score(5, 10, position_fraction=0.5, set_shape="build")
        self.assertGreater(small_jump, big_jump)

    def test_custom_shape_is_neutral(self):
        self.assertEqual(energy_score(1, 10, position_fraction=0.5, set_shape="custom"), 0.5)


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
