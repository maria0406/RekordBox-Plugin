import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.cues import build_cue_plan, build_transition_notes, merge_coincident_memory_cues, transition_timing, _format_mmss
from app.rekordbox_xml import CUE_COLORS


def _fake_analysis(bpm=124.0, n_bars=64, phrase_starts=(0, 32)):
    downbeats = [i * (60.0 / bpm * 4) for i in range(n_bars)]
    bounds = list(phrase_starts) + [n_bars]
    return {
        "bpm": bpm,
        "downbeats": downbeats,
        "phrases": [{"start_bar": s, "length": e - s} for s, e in zip(bounds, bounds[1:])],
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

    def test_mix_in_is_a_single_hot_cue(self):
        ordered = [{"id": "t1"}, {"id": "t2"}]
        analyses = {"t1": _fake_analysis(), "t2": _fake_analysis()}
        plan = build_cue_plan(ordered, analyses)
        mix_ins = [c for c in plan["t2"] if c["name"] == "MIX IN"]
        self.assertEqual([(c["cue_kind"], c["hot_cue_index"]) for c in mix_ins], [("hot", 0)])

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

    def test_filter_is_one_bar_after_outgoing_bass_swap(self):
        out = _fake_analysis()  # MIX OUT at bar 32, BASS SWAP at bar 48
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": out, "t2": _fake_analysis()})
        bass_swap = next(c for c in plan["t1"] if c["name"] == "BASS SWAP")
        filter_cue = next(c for c in plan["t1"] if c["name"] == "FILTER")
        self.assertEqual(bass_swap["start_s"], out["downbeats"][48])
        self.assertEqual(filter_cue["start_s"], out["downbeats"][49])

    def test_short_track_never_stacks_cues(self):
        out = _fake_analysis()
        out["downbeats"] = out["downbeats"][:12]  # BASS SWAP and FILTER both clamp to the last bar
        out["phrases"] = [{"start_bar": 0, "length": 12}]
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": out, "t2": _fake_analysis()})
        _assert_no_stacked_cues(self, plan["t1"], bpm=124.0)
        self.assertIn("BASS SWAP", {c["name"] for c in plan["t1"]})  # the higher-priority cue keeps the spot

    def test_loop_8_sits_at_the_end_of_the_transition_not_on_mix_out(self):
        out = _fake_analysis(n_bars=96, phrase_starts=(0, 32, 64))
        out["duration"] = out["downbeats"][-1] + 2.0
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": out, "t2": _fake_analysis()})
        loop = next(c for c in plan["t1"] if c["name"] == "LOOP 8")
        self.assertEqual(loop["start_s"], out["downbeats"][64 + 24])

    def test_drop_on_the_bass_swap_bar_is_left_out(self):
        incoming = _fake_analysis()
        incoming["sections"] = [{"label": "drop", "start": incoming["downbeats"][16], "end": incoming["downbeats"][24]}]
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": _fake_analysis(), "t2": incoming})
        names = [c["name"] for c in plan["t2"]]
        self.assertIn("BASS SWAP", names)
        self.assertNotIn("DROP", names)

    def test_late_in_where_the_full_arrangement_arrives(self):
        incoming = _fake_analysis(n_bars=96, phrase_starts=(0, 32, 64))
        incoming["energy_curve"] = [{"rms": 0.3 if i < 21 else 1.0} for i in range(96)]  # 21 quiet bars
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": _fake_analysis(), "t2": incoming})
        late_in = next(c for c in plan["t2"] if c["name"] == "LATE IN")
        self.assertEqual(late_in["start_s"], incoming["downbeats"][24])  # rounded up to the phrase line

    def test_no_late_in_without_a_long_intro(self):
        incoming = _fake_analysis()
        incoming["energy_curve"] = [{"rms": 1.0}] * 64
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": _fake_analysis(), "t2": incoming})
        self.assertNotIn("LATE IN", {c["name"] for c in plan["t2"]})

    def test_early_out_at_the_first_breakdown(self):
        out = _fake_analysis(n_bars=96, phrase_starts=(0, 32, 64))  # MIX OUT at bar 64
        out["sections"] = [{"label": "breakdown", "start": out["downbeats"][39], "end": out["downbeats"][48]}]
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": out, "t2": _fake_analysis()})
        early_out = next(c for c in plan["t1"] if c["name"] == "EARLY OUT")
        self.assertEqual(early_out["start_s"], out["downbeats"][40])

    def test_fake_drop_on_the_last_bar_before_the_beat_returns(self):
        track = _fake_analysis(n_bars=96, phrase_starts=(0, 32, 64))
        track["sections"] = [{"label": "breakdown", "start": track["downbeats"][40], "end": track["downbeats"][48]}]
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": track, "t2": _fake_analysis()})
        fake = next(c for c in plan["t1"] if c["name"] == "FAKE DROP")
        self.assertEqual(fake["start_s"], track["downbeats"][47])

    def test_no_fake_drop_when_the_breakdown_runs_to_the_end(self):
        track = _fake_analysis()
        track["sections"] = [{"label": "breakdown", "start": track["downbeats"][56], "end": track["downbeats"][63] + 2.0}]
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": _fake_analysis(), "t2": track})
        self.assertNotIn("FAKE DROP", {c["name"] for c in plan["t2"]})

    def test_ways_out_every_sixteen_bars_back_to_the_track_arriving(self):
        out = _fake_analysis(n_bars=160, phrase_starts=(0, 32, 64, 96, 128))  # opener; MIX OUT at bar 128
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": out, "t2": _fake_analysis()})
        outs = {c["name"]: c["start_s"] for c in plan["t1"] if c["name"] == "MIX OUT" or c["name"].startswith("OUT -")}
        self.assertEqual(outs, {
            "OUT -96": out["downbeats"][32], "OUT -80": out["downbeats"][48], "OUT -64": out["downbeats"][64],
            "OUT -48": out["downbeats"][80], "OUT -32": out["downbeats"][96],
            "OUT -16": out["downbeats"][112], "MIX OUT": out["downbeats"][128],
        })

    def test_no_way_out_during_the_tracks_own_mix_in(self):
        tracks = [_fake_analysis(n_bars=96, phrase_starts=(0, 32, 64)) for _ in range(3)]  # MIX OUT at bar 64
        plan = build_cue_plan([{"id": "a"}, {"id": "b"}, {"id": "c"}], dict(zip("abc", tracks)))
        outs = sorted(c["bar"] for c in plan["b"] if c["name"].startswith("OUT -"))
        self.assertEqual(outs, [32, 48])  # mixed in at bar 0: nothing before bar 32

    def test_full_set_has_no_stacked_cues(self):
        ordered = [{"id": f"t{i}"} for i in range(4)]
        analyses = {}
        for i in range(4):
            a = _fake_analysis(n_bars=96, phrase_starts=(0, 32, 64))
            a["energy_curve"] = [{"rms": 0.3 if b < 18 else 1.0} for b in range(96)]
            a["sections"] = [{"label": "drop", "start": a["downbeats"][16], "end": a["downbeats"][24]},
                             {"label": "breakdown", "start": a["downbeats"][48], "end": a["downbeats"][56]}]
            a["duration"] = a["downbeats"][-1] + 2.0
            analyses[f"t{i}"] = a
        plan = build_cue_plan(ordered, analyses)
        for track_cues in plan.values():
            _assert_no_stacked_cues(self, track_cues, bpm=124.0)

    def test_loop_past_track_end_is_skipped(self):
        out = _fake_analysis()
        out["duration"] = out["downbeats"][32] + 2.0  # MIX OUT is bar 32; an 8-bar loop would overrun
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": out, "t2": _fake_analysis()})
        self.assertNotIn("LOOP 8", {c["name"] for c in plan["t1"]})

    def test_single_track_no_crash(self):
        ordered = [{"id": "solo"}]
        plan = build_cue_plan(ordered, {"solo": _fake_analysis()})
        self.assertEqual(plan, {"solo": []})


def _assert_no_stacked_cues(test, track_cues, bpm):
    bar_s = 60.0 / bpm * 4
    starts = sorted(c["start_s"] for c in track_cues)
    for a, b in zip(starts, starts[1:]):
        test.assertGreaterEqual(b - a, bar_s * 0.99, f"cues {a:.2f}s and {b:.2f}s are within a bar")


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


class TestTransitionTiming(unittest.TestCase):
    def test_includes_filter_cue_time(self):
        out, inc = _fake_analysis(), _fake_analysis()
        plan = build_cue_plan([{"id": "t1"}, {"id": "t2"}], {"t1": out, "t2": inc})
        timing = transition_timing(plan["t1"], plan["t2"])
        self.assertEqual(timing, {
            "mixOutS": out["downbeats"][32], "bassSwapS": out["downbeats"][48],
            "filterS": out["downbeats"][49], "mixInS": inc["downbeats"][0], "fakeDropS": None,
        })

    def test_includes_fake_drop_before_mix_out_only(self):
        timing = transition_timing(
            [_cue("FAKE DROP", 40.0), _cue("MIX OUT", 100.0), _cue("FAKE DROP", 120.0)], [_cue("MIX IN", 0.0)],
        )
        self.assertEqual(timing["fakeDropS"], 40.0)

    def test_ignores_filter_before_mix_out_and_missing_filter(self):
        timing = transition_timing([_cue("FILTER", 5.0), _cue("MIX OUT", 10.0)], [_cue("MIX IN", 0.0)])
        self.assertIsNone(timing["filterS"])


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
