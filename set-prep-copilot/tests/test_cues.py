import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.cues import build_cue_plan, build_transition_notes, merge_coincident_memory_cues, _format_mmss
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

    def test_mix_out_leaves_room_for_the_transition(self):
        out = _fake_analysis()  # 64 bars
        out["phrases"] = [{"start_bar": 0, "length": 32}, {"start_bar": 32, "length": 24}, {"start_bar": 56, "length": 8}]
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": out, "t2": _fake_analysis()})
        mix_out = next(c for c in plan["t1"] if c["name"] == "MIX OUT")
        self.assertEqual(mix_out["start_s"], out["downbeats"][32])  # not the 8-bar tail phrase at bar 56

    def test_loop_past_track_end_is_skipped(self):
        out = _fake_analysis()
        out["duration"] = out["downbeats"][32] + 2.0  # MIX OUT is bar 32; an 8-bar loop would overrun
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": out, "t2": _fake_analysis()})
        self.assertNotIn("LOOP 8", {c["name"] for c in plan["t1"]})

    def test_single_track_no_crash(self):
        ordered = [{"id": "solo"}]
        plan = build_cue_plan(ordered, {"solo": _fake_analysis()})
        self.assertEqual(plan, {"solo": []})


def _cue(name, start_s, kind="memory", loop_end_s=None):
    return {"name": name, "color_hex": "#FF0000", "start_s": start_s, "cue_kind": kind,
            "hot_cue_index": 0 if kind == "hot" else None, "loop_end_s": loop_end_s}


class TestMergeCoincidentMemoryCues(unittest.TestCase):
    def test_same_time_memory_cues_merge_into_one(self):
        merged = merge_coincident_memory_cues([
            _cue("FILTER", 350.041), _cue("MIX OUT", 365.540), _cue("BASS SWAP", 365.5401),
        ])
        self.assertEqual([c["name"] for c in merged], ["FILTER", "MIX OUT + BASS SWAP"])

    def test_hot_cues_and_loops_are_not_merged(self):
        cues = [_cue("MIX IN", 1.0, kind="hot"), _cue("MIX IN", 1.0), _cue("LOOP 8", 1.0, loop_end_s=16.0)]
        self.assertEqual(len(merge_coincident_memory_cues(cues)), 3)

    def test_does_not_mutate_input(self):
        cues = [_cue("MIX OUT", 2.0), _cue("BASS SWAP", 2.0)]
        merge_coincident_memory_cues(cues)
        self.assertEqual(cues[0]["name"], "MIX OUT")


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
