"""The hosted demo (DEMO_MODE=1): app/demo.py's committed demo set, and
per-browser sessions in session_state. Neither needs the demo audio
downloaded."""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import cues, demo, scoring, session_state  # noqa: E402


def _request(session_id):
    return SimpleNamespace(state=SimpleNamespace(session_id=session_id))


class TestDemoSet(unittest.TestCase):
    def test_every_demo_track_has_a_precomputed_analysis(self):
        for playlist in demo.list_playlists():
            for track in demo.get_playlist_tracks(playlist["id"]):
                analysis = demo.analyze_track(track["location"])
                self.assertGreater(analysis["bpm"], 0)
                self.assertTrue(analysis["downbeats"])

    def test_unknown_playlist_raises(self):
        with self.assertRaises(demo.RekordboxDbError):
            demo.get_playlist_tracks("nope")

    def test_unknown_file_raises_like_a_missing_track(self):
        with self.assertRaises(FileNotFoundError):
            demo.analyze_track("/nowhere/else.mp3")

    def test_demo_set_produces_a_cue_plan(self):
        playlist_id = demo.list_playlists()[0]["id"]
        tracks = demo.get_playlist_tracks(playlist_id)
        analyses = {t["track_id"]: demo.analyze_track(t["location"]) for t in tracks}
        scoring_input = [
            {"id": t["track_id"], "bpm": analyses[t["track_id"]]["bpm"],
             "camelot_key": analyses[t["track_id"]]["camelot_key"], "energy": 0.1}
            for t in tracks
        ]
        ordered = scoring.order_tracks(scoring_input, set_shape="build")
        plan = cues.build_cue_plan(ordered, analyses)
        self.assertEqual(set(plan), {t["track_id"] for t in tracks})

    def test_every_demo_track_is_credited(self):
        credits = demo.credits()
        self.assertEqual(len(credits), sum(len(demo.get_playlist_tracks(p["id"])) for p in demo.list_playlists()))
        for credit in credits:
            self.assertTrue(credit["license"]["name"] and credit["license"]["url"] and credit["source_url"])


class TestDemoSessions(unittest.TestCase):
    def setUp(self):
        session_state.reset()

    def tearDown(self):
        session_state.reset()

    def test_local_app_shares_one_session(self):
        with mock.patch("app.config.DEMO_MODE", False):
            self.assertIs(session_state.current(_request("a")), session_state.STATE)
            self.assertIs(session_state.current(_request("b")), session_state.STATE)

    def test_demo_keeps_one_session_per_browser(self):
        with mock.patch("app.config.DEMO_MODE", True):
            a = session_state.current(_request("a"))
            a.playlist_name = "A's set"
            self.assertIs(session_state.current(_request("a")), a)
            self.assertIsNone(session_state.current(_request("b")).playlist_name)

    def test_demo_drops_least_recently_used_session_past_the_cap(self):
        with mock.patch("app.config.DEMO_MODE", True), mock.patch("app.session_state.MAX_DEMO_SESSIONS", 2):
            first = session_state.current(_request("first"))
            session_state.current(_request("second"))
            session_state.current(_request("first"))  # now "second" is the oldest
            session_state.current(_request("third"))
            self.assertIs(session_state.current(_request("first")), first)
            self.assertNotIn("second", session_state._demo_sessions)


if __name__ == "__main__":
    unittest.main()
