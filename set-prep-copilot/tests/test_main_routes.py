"""Route-level tests for app.main's new review/control-flow endpoints, using
FastAPI's TestClient with rekordbox_db monkeypatched so these never need a
real rekordbox install."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402

from app import cues, session_state  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _fake_analysis(bpm=124.0):
    downbeats = [i * (60.0 / bpm * 4) for i in range(64)]
    return {
        "bpm": bpm, "downbeats": downbeats,
        "phrases": [{"start_bar": 0, "length": 32}, {"start_bar": 32, "length": 32}],
        "sections": [], "energy_curve": [{"rms": 0.1, "bass_rms": 0.1}],
        "camelot_key": "8A",
    }


class TestMainRoutesBase(unittest.TestCase):
    def setUp(self):
        session_state.reset()

    def tearDown(self):
        session_state.reset()


class TestSetupTracks(TestMainRoutesBase):
    def test_returns_tracks_for_playlist(self):
        fake_tracks = [
            {"track_id": "1", "name": "Track One", "artist": "Artist A", "location": "/x/1.mp3",
             "album": None, "total_time": 200, "average_bpm": 124.0, "tonality": "8A",
             "isrc": None, "raw_attrib": None},
        ]
        with mock.patch("app.rekordbox_db.get_playlist_tracks", return_value=fake_tracks):
            resp = client.get("/setup/tracks", params={"playlist_id": "42"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["tracks"], [{"id": "1", "name": "Track One", "artist": "Artist A"}])

    def test_db_error_returns_400(self):
        from app.rekordbox_db import RekordboxDbError
        with mock.patch("app.rekordbox_db.get_playlist_tracks", side_effect=RekordboxDbError("nope")):
            resp = client.get("/setup/tracks", params={"playlist_id": "42"})
        self.assertEqual(resp.status_code, 400)


class TestResultsMove(TestMainRoutesBase):
    def _seed(self):
        t1 = {"id": "1", "name": "One", "artist": "A", "bpm": 124.0, "camelot_key": "8A"}
        t2 = {"id": "2", "name": "Two", "artist": "B", "bpm": 126.0, "camelot_key": "9A"}
        session_state.STATE.ordered_tracks = [t1, t2]
        session_state.STATE.analyses = {"1": _fake_analysis(124.0), "2": _fake_analysis(126.0)}
        session_state.STATE.cue_plan = cues.build_cue_plan(session_state.STATE.ordered_tracks, session_state.STATE.analyses)

    def test_move_down_swaps_order_and_rebuilds_cues(self):
        self._seed()
        stale_plan_id = id(session_state.STATE.cue_plan)
        resp = client.post("/results/move", data={"track_id": "1", "direction": "down"}, follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual([t["id"] for t in session_state.STATE.ordered_tracks], ["2", "1"])
        # Cue plan was rebuilt (new dict), not left stale.
        self.assertNotEqual(id(session_state.STATE.cue_plan), stale_plan_id)

    def test_move_up_at_top_is_a_no_op(self):
        self._seed()
        resp = client.post("/results/move", data={"track_id": "1", "direction": "up"}, follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual([t["id"] for t in session_state.STATE.ordered_tracks], ["1", "2"])


class TestNudgeCue(TestMainRoutesBase):
    def test_nudge_shifts_start_and_loop_end(self):
        session_state.STATE.cue_plan = {
            "1": [{"name": "LOOP 8", "start_s": 100.0, "loop_end_s": 116.0, "color_hex": "#FFFF00",
                   "cue_kind": "memory", "hot_cue_index": None}],
        }
        resp = client.post(
            "/results/nudge-cue",
            data={"track_id": "1", "cue_index": "0", "delta_seconds": "2.0"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 303)
        cue = session_state.STATE.cue_plan["1"][0]
        self.assertEqual(cue["start_s"], 102.0)
        self.assertEqual(cue["loop_end_s"], 118.0)

    def test_nudge_does_not_go_negative(self):
        session_state.STATE.cue_plan = {
            "1": [{"name": "MIX OUT", "start_s": 1.0, "loop_end_s": None, "color_hex": "#FF0000",
                   "cue_kind": "memory", "hot_cue_index": None}],
        }
        client.post(
            "/results/nudge-cue",
            data={"track_id": "1", "cue_index": "0", "delta_seconds": "-5.0"},
            follow_redirects=False,
        )
        self.assertEqual(session_state.STATE.cue_plan["1"][0]["start_s"], 0.0)


class TestAnalyzeSkipsMissingFiles(TestMainRoutesBase):
    def test_missing_file_is_skipped_not_fatal(self):
        fake_tracks = [
            {"track_id": "1", "name": "Good", "artist": "A", "location": "/ok.mp3",
             "album": None, "total_time": 200, "average_bpm": 124.0, "tonality": "8A",
             "isrc": None, "raw_attrib": None},
            {"track_id": "2", "name": "Missing", "artist": "B", "location": "/missing.mp3",
             "album": None, "total_time": 200, "average_bpm": 124.0, "tonality": "8A",
             "isrc": None, "raw_attrib": None},
        ]

        def fake_analyze(path):
            if path == "/missing.mp3":
                raise FileNotFoundError("[Errno 2] No such file or directory: '/missing.mp3'")
            return _fake_analysis(124.0)

        with mock.patch("app.main.rekordbox_db.get_playlist_tracks", return_value=fake_tracks), \
             mock.patch("app.main.analyze_track", side_effect=fake_analyze):
            resp = client.post(
                "/analyze",
                data={"playlist_id": "42", "playlist_name": "My Set", "set_shape": "build"},
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 303)
        self.assertEqual(len(session_state.STATE.ordered_tracks), 1)
        self.assertEqual(session_state.STATE.ordered_tracks[0]["id"], "1")
        self.assertEqual(len(session_state.STATE.skipped_tracks), 1)
        self.assertEqual(session_state.STATE.skipped_tracks[0]["name"], "Missing")

    def test_export_keeps_rekordbox_bpm_and_key(self):
        """Importing the XML overwrites the library's BPM/key fields, so they
        must be rekordbox's own values, not ours."""
        fake_tracks = [
            {"track_id": str(i), "name": f"T{i}", "artist": "A", "location": f"/{i}.mp3",
             "album": None, "total_time": 200, "average_bpm": 124.0, "tonality": "Dm",
             "isrc": None, "raw_attrib": None}
            for i in (1, 2)
        ]
        with mock.patch("app.main.rekordbox_db.get_playlist_tracks", return_value=fake_tracks), \
             mock.patch("app.main.analyze_track", side_effect=lambda p: _fake_analysis(123.05)):
            client.post("/analyze", data={"playlist_id": "42", "playlist_name": "My Set"}, follow_redirects=False)

        for track in session_state.STATE.ordered_tracks:
            self.assertEqual(track["average_bpm"], 124.0)
            self.assertEqual(track["tonality"], "Dm")
            self.assertEqual(track["bpm"], 123.05)  # ours, still used for ordering

    def test_locked_opener_and_closer_are_respected(self):
        fake_tracks = [
            {"track_id": str(i), "name": f"T{i}", "artist": "A", "location": f"/{i}.mp3",
             "album": None, "total_time": 200, "average_bpm": 120.0 + i, "tonality": "8A",
             "isrc": None, "raw_attrib": None}
            for i in range(1, 5)
        ]
        with mock.patch("app.main.rekordbox_db.get_playlist_tracks", return_value=fake_tracks), \
             mock.patch("app.main.analyze_track", side_effect=lambda p: _fake_analysis(120.0)):
            resp = client.post(
                "/analyze",
                data={
                    "playlist_id": "42", "playlist_name": "My Set", "set_shape": "build",
                    "locked_opener_id": "3", "locked_closer_id": "2",
                },
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 303)
        ordered_ids = [t["id"] for t in session_state.STATE.ordered_tracks]
        self.assertEqual(ordered_ids[0], "3")
        self.assertEqual(ordered_ids[-1], "2")

    def test_empty_playlist_shows_error_instead_of_silent_bounce(self):
        """A playlist with zero tracks (e.g. rekordbox's own auto-created
        'CUE Analysis Playlist') must not silently redirect to /results and
        bounce back to /setup with no explanation -- it should explain why,
        on the page, in the same request."""
        with mock.patch("app.main.rekordbox_db.get_playlist_tracks", return_value=[]), \
             mock.patch("app.main.rekordbox_db.list_playlists", return_value=[]):
            resp = client.post(
                "/analyze",
                data={"playlist_id": "200000", "playlist_name": "CUE Analysis Playlist", "set_shape": "build"},
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 200)  # re-rendered setup.html, not a redirect
        self.assertIn("no tracks", resp.text)
        self.assertEqual(session_state.STATE.ordered_tracks, [])

    def test_all_tracks_unreadable_shows_error_instead_of_silent_bounce(self):
        fake_tracks = [
            {"track_id": "1", "name": "Ghost", "artist": "A", "location": "/missing.mp3",
             "album": None, "total_time": 200, "average_bpm": 124.0, "tonality": "8A",
             "isrc": None, "raw_attrib": None},
        ]
        with mock.patch("app.main.rekordbox_db.get_playlist_tracks", return_value=fake_tracks), \
             mock.patch("app.main.rekordbox_db.list_playlists", return_value=[]), \
             mock.patch("app.main.analyze_track", side_effect=FileNotFoundError("no such file")):
            resp = client.post(
                "/analyze",
                data={"playlist_id": "42", "playlist_name": "My Set", "set_shape": "build"},
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 200)
        self.assertIn("could be analyzed", resp.text)
        self.assertEqual(session_state.STATE.ordered_tracks, [])
