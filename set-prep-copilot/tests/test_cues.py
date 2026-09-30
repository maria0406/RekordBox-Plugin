import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.cues import build_cue_plan, build_transition_notes, _format_mmss
from app.rekordbox_xml import CUE_COLORS


def _fake_analysis(bpm=124.0):
    downbeats = [i * (60.0 / bpm * 4) for i in range(64)]
    return {
        "bpm": bpm,
        "downbeats": downbeats,
        "phrases": [{"start_bar": 0, "length": 32}, {"start_bar": 32, "length": 32}],
        "sections": [{"label": "drop", "start": downbeats[8], "end": downbeats[16]}],
    }


class TestBuildCuePlan(unittest.TestCase):
    def test_two_track_transition_gets_all_cue_types(self):
        ordered = [{"id": "t1"}, {"id": "t2"}]
        analyses = {"t1": _fake_analysis(), "t2": _fake_analysis()}
        plan = build_cue_plan(ordered, analyses)

        names_t1 = {c["name"] for c in plan["t1"]}
        names_t2 = {c["name"] for c in plan["t2"]}

        self.assertIn("MIX OUT", names_t1)
        self.assertIn("BASS SWAP", names_t1)
        self.assertIn("FILTER", names_t1)
        self.assertIn("LOOP 8", names_t1)
        self.assertIn("MIX IN", names_t2)
        self.assertIn("BASS SWAP", names_t2)
        self.assertIn("DROP", names_t2)

    def test_mix_in_has_both_hot_and_memory_cue(self):
        ordered = [{"id": "t1"}, {"id": "t2"}]
        analyses = {"t1": _fake_analysis(), "t2": _fake_analysis()}
        plan = build_cue_plan(ordered, analyses)
        mix_ins = [c for c in plan["t2"] if c["name"] == "MIX IN"]
        kinds = {c["cue_kind"] for c in mix_ins}
        self.assertEqual(kinds, {"hot", "memory"})

    def test_colors_match_confirmed_palette(self):
        ordered = [{"id": "t1"}, {"id": "t2"}]
        analyses = {"t1": _fake_analysis(), "t2": _fake_analysis()}
        plan = build_cue_plan(ordered, analyses)
        mix_out = next(c for c in plan["t1"] if c["name"] == "MIX OUT")
        self.assertEqual(mix_out["color_hex"], CUE_COLORS["mix_out"])

    def test_single_track_no_crash(self):
        ordered = [{"id": "solo"}]
        plan = build_cue_plan(ordered, {"solo": _fake_analysis()})
        self.assertEqual(plan, {"solo": []})


class TestFormatMmSs(unittest.TestCase):
    def test_pads_seconds_not_minutes(self):
        self.assertEqual(_format_mmss(245.0), "4:05")
        self.assertEqual(_format_mmss(276.4), "4:36")
        self.assertEqual(_format_mmss(5.0), "0:05")


class TestBuildTransitionNotes(unittest.TestCase):
    def test_note_format_and_content(self):
        ordered = [
            {"id": "t1", "name": "track 1"},
            {"id": "t2", "name": "track 2"},
        ]
        analyses = {
            "t1": _fake_analysis(bpm=124.0),
            "t2": _fake_analysis(bpm=125.0),
        }
        # Distinct keys so the note's "X to Y" is checkable.
        analyses["t1"]["camelot_key"] = "8A"
        analyses["t2"]["camelot_key"] = "9A"

        plan = build_cue_plan(ordered, analyses)
        notes = build_transition_notes(ordered, analyses, plan)

        mix_out = next(c for c in plan["t1"] if c["name"] == "MIX OUT")
        bass_swap = next(c for c in plan["t1"] if c["name"] == "BASS SWAP")
        expected = (
            f"Next: track 2, 8A to 9A, 124 to 125 BPM, "
            f"blend at {_format_mmss(mix_out['start_s'])}, "
            f"bass swap at {_format_mmss(bass_swap['start_s'])}."
        )
        self.assertEqual(notes["t1"], expected)

    def test_last_track_has_no_note(self):
        ordered = [{"id": "t1", "name": "track 1"}, {"id": "t2", "name": "track 2"}]
        analyses = {"t1": _fake_analysis(), "t2": _fake_analysis()}
        plan = build_cue_plan(ordered, analyses)
        notes = build_transition_notes(ordered, analyses, plan)
        self.assertNotIn("t2", notes)

    def test_single_track_no_notes(self):
        ordered = [{"id": "solo", "name": "Solo"}]
        analyses = {"solo": _fake_analysis()}
        plan = build_cue_plan(ordered, analyses)
        notes = build_transition_notes(ordered, analyses, plan)
        self.assertEqual(notes, {})


if __name__ == "__main__":
    unittest.main()
