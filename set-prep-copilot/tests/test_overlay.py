import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402

from app import session_state  # noqa: E402
from app.main import app  # noqa: E402
from app.overlay import __main__ as launcher, listener, midi_clock  # noqa: E402
from app.overlay.midi_clock import DeckClock, MidiTracker  # noqa: E402

client = TestClient(app)
LOOKUP, _ = midi_clock.load_map(midi_clock.DEFAULT_MAP)


def note(channel, number, velocity=127):
    return SimpleNamespace(type="note_on", channel=channel, note=number, velocity=velocity)


def cc(channel, number, value):
    return SimpleNamespace(type="control_change", channel=channel, control=number, value=value)


class TestDeckClock(unittest.TestCase):
    def test_play_pause_accumulates_position(self):
        d = DeckClock()
        d.toggle_play(10.0)
        self.assertAlmostEqual(d.at(15.0), 5.0)
        d.toggle_play(15.0)
        self.assertAlmostEqual(d.at(100.0), 5.0)

    def test_cue_while_playing_returns_to_cue_point(self):
        d = DeckClock()
        d.toggle_play(0.0)
        d.toggle_play(4.0)
        d.cue(4.0)  # paused: sets the cue point at 4s
        d.toggle_play(4.0)
        d.cue(10.0)  # playing: back to 4s, paused
        self.assertFalse(d.playing)
        self.assertAlmostEqual(d.at(20.0), 4.0)

    def test_rate_scales_position(self):
        d = DeckClock()
        d.toggle_play(0.0)
        d.set_rate(10.0, 1.05)
        self.assertAlmostEqual(d.at(20.0), 10.0 + 10.5)


class TestMidiTracker(unittest.TestCase):
    def test_play_load_and_controls_from_default_map(self):
        t = MidiTracker(LOOKUP)
        t.handle(note(1, 11), 0.0)  # deck 2 PLAY
        self.assertTrue(t.decks[2].playing)
        t.handle(note(1, 11, velocity=0), 1.0)  # release is ignored
        self.assertTrue(t.decks[2].playing)
        t.handle(cc(0, 19, 127), 1.0)  # channel 1 fader all the way up
        t.handle(cc(0, 15, 0), 1.0)  # channel 1 LOW fully left
        self.assertEqual(t.controls["ch1-fader"], 1.0)
        self.assertEqual(t.controls["ch1-low"], -1.0)
        t.handle(note(6, 71), 2.0)  # deck 2 LOAD resets its clock
        self.assertFalse(t.decks[2].playing)
        self.assertEqual(t.decks[2].at(5.0), 0.0)

    def test_tempo_slider_changes_rate(self):
        t = MidiTracker(LOOKUP)
        t.handle(cc(0, 0, 64), 0.0)
        self.assertAlmostEqual(t.decks[1].rate, 1.0)
        t.handle(cc(0, 0, 127), 0.0)
        self.assertAlmostEqual(t.decks[1].rate, 1 + 63 / 64 * midi_clock.TEMPO_RANGE)

    def test_unknown_messages_are_ignored(self):
        t = MidiTracker(LOOKUP)
        t.handle(SimpleNamespace(type="clock"), 0.0)
        t.handle(note(9, 99), 0.0)
        self.assertIsNone(t.last_message)

    def test_probe_output_format_is_accepted(self):
        probe = {"deck1_play": {"first": {"type": "note_on", "channel": 3, "note": 42}, "message_count": 2}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(probe, f)
        try:
            lookup, _ = midi_clock.load_map(f.name)
        finally:
            os.unlink(f.name)
        self.assertEqual(lookup, {("note", 3, 42): "deck1_play"})


def _seed_set():
    def cue(name, s):
        return {"name": name, "start_s": s, "cue_kind": "memory", "color_hex": "#FFFFFF", "hot_cue_index": None, "loop_end_s": None}
    session_state.STATE.ordered_tracks = [
        {"id": str(i), "name": f"T{i}", "bpm": 124.0, "location": "/x.mp3"} for i in range(3)
    ]
    session_state.STATE.cue_plan = {
        "0": [cue("MIX OUT", 300.0), cue("BASS SWAP", 331.0)],
        "1": [cue("MIX IN", 2.0), cue("MIX OUT", 280.0), cue("BASS SWAP", 311.0)],
        "2": [cue("MIX IN", 1.0)],
    }


class TestOverlayRoutes(unittest.TestCase):
    def setUp(self):
        session_state.reset()
        listener.reset_for_tests(MidiTracker(LOOKUP))  # never opens a real MIDI port

    def tearDown(self):
        session_state.reset()
        listener.reset_for_tests()

    def test_transitions_alternate_decks(self):
        from app.overlay.routes import overlay_transitions
        _seed_set()
        trs = overlay_transitions()
        self.assertEqual([t["outDeck"] for t in trs], [1, 2])
        self.assertEqual(trs[0]["mixOutS"], 300.0)
        self.assertEqual(trs[1]["mixInS"], 1.0)

    def test_page_renders(self):
        _seed_set()
        resp = client.get("/overlay")
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="overlay-data"', resp.text)
        self.assertIn("svg", resp.text)

    def test_sync_sets_deck_position(self):
        resp = client.post("/overlay/sync", data={"deck": 2, "position": 42.5})
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.json()["decks"]["2"]["position"], 42.5)
        self.assertEqual(client.post("/overlay/sync", data={"deck": 3, "position": 0}).status_code, 400)

    def test_state_reports_midi_status(self):
        body = client.get("/overlay/state").json()
        self.assertIn("midi", body)
        self.assertIn("1", body["decks"])


class TestLauncherPlacement(unittest.TestCase):
    def test_bottom_right_of_rekordbox(self):
        x, y = launcher.placement({"X": 0, "Y": 25, "Width": 1440, "Height": 875})
        self.assertEqual((x, y), (1440 - launcher.WIDTH - launcher.MARGIN, 25 + 875 - launcher.HEIGHT - launcher.MARGIN))
        self.assertEqual(launcher.placement(None), (None, None))

    def test_exits_cleanly_when_app_is_not_running(self):
        with mock.patch.object(launcher.urllib.request, "urlopen", side_effect=OSError("refused")):
            with self.assertRaises(SystemExit):
                launcher.main(["--url", "http://127.0.0.1:1/overlay"])


if __name__ == "__main__":
    unittest.main()
