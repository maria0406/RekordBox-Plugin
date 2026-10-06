import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.catalog import build, curriculum, difficulty, internet_archive as ia, licenses  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None):
        self.status_code = status_code
        self._json_body = json_body

    def json(self):
        if self._json_body is None:
            raise ValueError("no json")
        return self._json_body


class TestLicenses(unittest.TestCase):
    def test_parses_cc_variants(self):
        lic = licenses.parse_license("http://creativecommons.org/licenses/by-nc-sa/3.0/")
        self.assertEqual(lic.name, "CC BY-NC-SA 3.0")
        self.assertFalse(lic.commercial_ok)
        self.assertTrue(lic.adaptations_ok)
        self.assertTrue(lic.share_alike)

    def test_public_domain(self):
        lic = licenses.parse_license("https://creativecommons.org/publicdomain/zero/1.0/")
        self.assertFalse(lic.attribution_required)
        self.assertTrue(licenses.is_allowed(lic))

    def test_unknown_or_missing_is_rejected(self):
        self.assertIsNone(licenses.parse_license(None))
        self.assertIsNone(licenses.parse_license("http://example.com/my-license"))
        self.assertFalse(licenses.is_allowed(None))

    def test_policy_allows_nc_but_not_nd(self):
        self.assertTrue(licenses.is_allowed(licenses.parse_license("http://creativecommons.org/licenses/by-nc/4.0/")))
        self.assertFalse(licenses.is_allowed(licenses.parse_license("http://creativecommons.org/licenses/by-nc-nd/3.0/")))

    def test_monetizing_would_drop_nc(self):
        with mock.patch.object(licenses, "ALLOW_NONCOMMERCIAL", False):
            self.assertFalse(licenses.is_allowed(licenses.parse_license("http://creativecommons.org/licenses/by-nc/4.0/")))
            self.assertTrue(licenses.is_allowed(licenses.parse_license("http://creativecommons.org/licenses/by/4.0/")))


def _analysis(bpm=124.0, n_bars=96, intro_bars=32, outro_bars=32, quiet=0.5, loud=1.0, beat_jitter=None):
    period = 60.0 / bpm
    n_beats = n_bars * 4
    beat_times = [i * period for i in range(n_beats)]
    if beat_jitter is not None:
        beat_times = [t * (1 + beat_jitter * (i // 64)) for i, t in enumerate(beat_times)]
    curve = []
    for i in range(n_bars):
        in_body = intro_bars <= i < n_bars - outro_bars
        curve.append({"bar_start": i * 4 * period, "rms": loud if in_body else quiet, "bass_rms": 0.5})
    return {"bpm": bpm, "beat_times": beat_times, "energy_curve": curve, "phrases": [], "duration": n_beats * period}


class TestDifficulty(unittest.TestCase):
    def test_runway_bars(self):
        self.assertEqual(difficulty.runway_bars([0.2, 0.2, 1.0, 1.0, 0.3]), (2, 1))
        self.assertEqual(difficulty.runway_bars([]), (0, 0))

    def test_long_intros_at_house_tempo_are_easier(self):
        easy = difficulty.rate(_analysis(bpm=124, intro_bars=32, outro_bars=32))
        hard = difficulty.rate(_analysis(bpm=134, intro_bars=2, outro_bars=1))
        self.assertEqual(easy["features"]["intro_bars"], 32)
        self.assertLess(easy["score"], hard["score"])

    def test_tempo_drift_raises_score(self):
        steady = difficulty.rate(_analysis())
        drifting = difficulty.rate(_analysis(beat_jitter=0.01))
        self.assertEqual(steady["features"]["tempo_drift"], 0.0)
        self.assertGreater(drifting["features"]["tempo_drift"], 0.0)

    def test_assign_levels_spreads_catalog_evenly(self):
        tracks = [{"id": str(i), "difficulty": {"score": i / 10}} for i in range(10)]
        difficulty.assign_levels(tracks)
        self.assertEqual([t["difficulty"]["level"] for t in tracks], [1, 1, 2, 2, 3, 3, 4, 4, 5, 5])


def _track(track_id, bpm, key, level):
    return {"id": track_id, "bpm": bpm, "camelot_key": key, "difficulty": {"level": level}}


class TestCurriculum(unittest.TestCase):
    def test_level_one_needs_easy_tracks_same_tempo_compatible_key(self):
        lvl1 = curriculum.LEVELS[0]
        self.assertTrue(curriculum.pair_fits(lvl1, _track("a", 124, "8A", 1), _track("b", 124.5, "9A", 1)))
        self.assertFalse(curriculum.pair_fits(lvl1, _track("a", 124, "8A", 1), _track("b", 124, "8A", 2)))
        self.assertFalse(curriculum.pair_fits(lvl1, _track("a", 124, "8A", 1), _track("b", 128, "8A", 1)))
        self.assertFalse(curriculum.pair_fits(lvl1, _track("a", 124, "8A", 1), _track("b", 124, "2B", 1)))

    def test_level_two_requires_a_tempo_gap(self):
        lvl2 = curriculum.LEVELS[1]
        self.assertFalse(curriculum.pair_fits(lvl2, _track("a", 124, "8A", 1), _track("b", 124, "8A", 1)))
        self.assertTrue(curriculum.pair_fits(lvl2, _track("a", 122, "8A", 1), _track("b", 125, "8A", 2)))

    def test_only_hardest_level_allows_key_clash(self):
        clash = (_track("a", 124, "8A", 4), _track("b", 124, "2B", 5))
        self.assertTrue(curriculum.pair_fits(curriculum.LEVELS[4], *clash))
        self.assertFalse(curriculum.pair_fits(curriculum.LEVELS[3], *clash))

    def test_build_lessons_caps_track_reuse(self):
        tracks = [_track(str(i), 124, "8A", 1) for i in range(6)]
        lessons = curriculum.build_lessons(tracks, lessons_per_level=50, max_uses_per_track=1)
        level1 = [lesson for lesson in lessons if lesson["level"] == 1]
        self.assertEqual(len(level1), 3)  # 6 tracks, each used once -> 3 pairs
        used = [lesson["track_a"] for lesson in level1] + [lesson["track_b"] for lesson in level1]
        self.assertEqual(len(used), len(set(used)))


class TestInternetArchive(unittest.TestCase):
    METADATA = {
        "metadata": {"title": "Deep EP", "creator": "Some Label", "licenseurl": "http://creativecommons.org/licenses/by-nc-sa/3.0/"},
        "files": [
            {"name": "01 Song.mp3", "format": "VBR MP3", "source": "original", "length": "392.5", "title": "Song", "creator": "Artist"},
            {"name": "01 Song.ogg", "format": "Ogg Vorbis", "source": "derivative", "length": "392.5"},
            {"name": "02 Intro.mp3", "format": "VBR MP3", "source": "original", "length": "45.0"},
            {"name": "03 Untitled.mp3", "format": "VBR MP3", "source": "original", "length": "300"},
        ],
    }

    def test_release_tracks_keeps_full_length_mp3s(self):
        with mock.patch.object(ia.requests, "get", return_value=_FakeResponse(200, self.METADATA)):
            tracks = ia.release_tracks("deep-ep")
        self.assertEqual([t.file_name for t in tracks], ["01 Song.mp3", "03 Untitled.mp3"])
        self.assertEqual(tracks[0].artist, "Artist")
        self.assertEqual(tracks[1].artist, "Some Label")  # falls back to the release creator
        self.assertEqual(tracks[0].track_id, "ia:deep-ep/01 Song.mp3")
        self.assertEqual(tracks[0].download_url, "https://archive.org/download/deep-ep/01%20Song.mp3")

    def test_release_with_nd_license_yields_nothing(self):
        body = {**self.METADATA, "metadata": {**self.METADATA["metadata"], "licenseurl": "http://creativecommons.org/licenses/by-nc-nd/3.0/"}}
        with mock.patch.object(ia.requests, "get", return_value=_FakeResponse(200, body)):
            self.assertEqual(ia.release_tracks("x"), [])

    def test_harvest_continues_past_a_page_with_no_allowed_releases(self):
        nd_page = [{"identifier": "nd", "licenseurl": "http://creativecommons.org/licenses/by-nd/3.0/"}]
        ok_page = [{"identifier": "ok", "licenseurl": "http://creativecommons.org/licenses/by/3.0/"}]
        pages = {1: nd_page, 2: ok_page, 3: []}
        sentinel = object()
        with mock.patch.object(ia, "search_releases", side_effect=lambda page, rows: pages[page]), \
                mock.patch.object(ia, "release_tracks", return_value=[sentinel]), \
                mock.patch.object(ia.time, "sleep"):
            self.assertEqual(list(ia.iter_candidates(max_releases=5)), [sentinel])

    def test_http_error_raises(self):
        with mock.patch.object(ia.requests, "get", return_value=_FakeResponse(503)):
            with self.assertRaises(ia.InternetArchiveError):
                ia.release_tracks("x")


class TestBuild(unittest.TestCase):
    def test_rejects_non_house_tempo_and_short_tracks(self):
        self.assertIsNone(build.rejection_reason({"duration": 300, "bpm": 124}))
        self.assertIn("tempo", build.rejection_reason({"duration": 300, "bpm": 95}))
        self.assertIn("short", build.rejection_reason({"duration": 100, "bpm": 124}))

    def test_build_writes_catalog_lessons_and_credits(self):
        cand = ia.CandidateTrack(
            "rel", "a.mp3", "Song", "Artist", "EP", 300.0,
            licenses.parse_license("http://creativecommons.org/licenses/by/4.0/"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            fake_audio = out / "a.mp3"
            fake_audio.write_bytes(b"x")
            with mock.patch.object(ia, "iter_candidates", return_value=iter([cand])), \
                    mock.patch.object(ia, "download", return_value=fake_audio), \
                    mock.patch.object(build, "analyze_track", return_value={**_analysis(), "camelot_key": "8A", "key_confidence": 0.7}):
                tracks = build.build(target=10, out_dir=out, max_releases=1, tracks_per_release=1)
            self.assertEqual(len(tracks), 1)
            self.assertEqual(tracks[0]["difficulty"]["level"], 1)
            self.assertEqual(tracks[0]["license"]["name"], "CC BY 4.0")
            self.assertTrue((out / "lessons.json").exists())
            self.assertIn('"Song" by Artist', (out / "CREDITS.md").read_text())


if __name__ == "__main__":
    unittest.main()
