"""Round-trip tests for app.rekordbox_xml, using stdlib unittest (no pytest
dependency) so this doesn't touch requirements.txt while other install work
may be running against the shared venv."""
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import rekordbox_xml as rbxml  # noqa: E402

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="7.0.0" Company="Pioneer DJ"/>
  <COLLECTION Entries="3">
    <TRACK TrackID="1" Name="Track One" Artist="Artist A" Album="Album A"
           TotalTime="200" AverageBpm="124.00" Tonality="8A"
           Location="file://localhost/Users/dj/Music/track%20one.mp3"/>
    <TRACK TrackID="2" Name="Track Two" Artist="Artist B" Album="Album B"
           TotalTime="180" AverageBpm="126.00" Tonality="9A"
           Location="file://localhost/Users/dj/Music/track_two.mp3"/>
    <TRACK TrackID="3" Name="Track Three" Artist="Artist C" Album="Album C"
           TotalTime="220" AverageBpm="123.00" Tonality="7A"
           Location="file://localhost/Users/dj/Music/track_three.mp3"/>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT" Count="1">
      <NODE Type="1" Name="Rough Setlist" Entries="3" KeyType="0">
        <TRACK Key="1"/>
        <TRACK Key="2"/>
        <TRACK Key="3"/>
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
"""


class TestRekordboxXml(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.source_path = Path(self.tmpdir.name) / "source.xml"
        self.source_path.write_text(SAMPLE_XML)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_parse_collection(self):
        tracks = rbxml.parse_collection(self.source_path)
        self.assertEqual(len(tracks), 3)
        t1 = next(t for t in tracks if t["track_id"] == "1")
        self.assertEqual(t1["name"], "Track One")
        self.assertEqual(t1["artist"], "Artist A")
        self.assertEqual(t1["average_bpm"], "124.00")
        self.assertEqual(t1["tonality"], "8A")
        # URI decoded to a plain path, %20 unescaped
        self.assertEqual(t1["location"], "/Users/dj/Music/track one.mp3")

    def test_parse_playlist_order(self):
        tracks = rbxml.parse_playlist(self.source_path, "Rough Setlist")
        self.assertEqual([t["track_id"] for t in tracks], ["1", "2", "3"])
        self.assertEqual([t["name"] for t in tracks], ["Track One", "Track Two", "Track Three"])

    def test_parse_playlist_missing_raises_with_available_names(self):
        with self.assertRaises(rbxml.RekordboxXmlError) as ctx:
            rbxml.parse_playlist(self.source_path, "Does Not Exist")
        self.assertIn("Rough Setlist", str(ctx.exception))

    def test_write_export_round_trip(self):
        tracks = rbxml.parse_playlist(self.source_path, "Rough Setlist")
        # Reorder: 2, 1, 3
        reordered = [tracks[1], tracks[0], tracks[2]]

        cues_by_track_id = {
            "2": [
                {
                    "name": "MIX IN",
                    "color_hex": rbxml.CUE_COLORS["mix_in"],
                    "start_s": 4.0,
                    "cue_kind": "hot",
                    "hot_cue_index": 0,
                    "loop_end_s": None,
                },
                {
                    "name": "MIX IN",
                    "color_hex": rbxml.CUE_COLORS["mix_in"],
                    "start_s": 4.0,
                    "cue_kind": "memory",
                    "hot_cue_index": None,
                    "loop_end_s": None,
                },
            ],
            "1": [
                {
                    "name": "LOOP 8",
                    "color_hex": rbxml.CUE_COLORS["loop_8"],
                    "start_s": 180.0,
                    "cue_kind": "memory",
                    "hot_cue_index": None,
                    "loop_end_s": 195.5,
                },
            ],
        }

        output_path = Path(self.tmpdir.name) / "output.xml"
        rbxml.write_export(
            tracks_in_order=reordered,
            cues_by_track_id=cues_by_track_id,
            output_path=output_path,
            playlist_name="Set Prep: Sat 10/10",
        )

        # File is well-formed and re-parseable.
        out_root = ET.parse(output_path).getroot()

        # New playlist exists with the reordered TrackID sequence.
        out_tracks = rbxml.parse_playlist(output_path, "Set Prep: Sat 10/10")
        self.assertEqual([t["track_id"] for t in out_tracks], ["2", "1", "3"])

        # Every exported track's original attributes (raw_attrib, carried
        # through from the source file) survived untouched -- the output is
        # self-contained (doesn't clone the whole source document or its
        # other playlists) but doesn't invent or drop track attributes for
        # tracks it DOES include.
        t1 = next(t for t in out_tracks if t["track_id"] == "1")
        self.assertEqual(t1["artist"], "Artist A")

        # POSITION_MARK entries for track 2: hot cue A + memory cue, both green.
        track2_el = next(
            t for t in out_root.find("COLLECTION").findall("TRACK") if t.get("TrackID") == "2"
        )
        marks = track2_el.findall("POSITION_MARK")
        self.assertEqual(len(marks), 2)
        kinds = {(m.get("Num"), m.get("Type")) for m in marks}
        self.assertEqual(kinds, {("0", "0"), ("-1", "0")})
        for m in marks:
            self.assertEqual(m.get("Name"), "MIX IN")
            self.assertEqual((m.get("Red"), m.get("Green"), m.get("Blue")), ("0", "255", "0"))
            self.assertEqual(m.get("Start"), "4.000")

        # POSITION_MARK for track 1: a loop, Type=4, with End set.
        track1_el = next(
            t for t in out_root.find("COLLECTION").findall("TRACK") if t.get("TrackID") == "1"
        )
        loop_marks = track1_el.findall("POSITION_MARK")
        self.assertEqual(len(loop_marks), 1)
        loop_mark = loop_marks[0]
        self.assertEqual(loop_mark.get("Type"), "4")
        self.assertEqual(loop_mark.get("Start"), "180.000")
        self.assertEqual(loop_mark.get("End"), "195.500")
        self.assertEqual(loop_mark.get("Num"), "-1")

        # Track 3 (no cues assigned) is untouched -- zero POSITION_MARK children.
        track3_el = next(
            t for t in out_root.find("COLLECTION").findall("TRACK") if t.get("TrackID") == "3"
        )
        self.assertEqual(track3_el.findall("POSITION_MARK"), [])

    def test_write_export_rejects_unknown_track_id(self):
        tracks = rbxml.parse_playlist(self.source_path, "Rough Setlist")
        output_path = Path(self.tmpdir.name) / "output2.xml"
        with self.assertRaises(rbxml.RekordboxXmlError):
            rbxml.write_export(
                tracks_in_order=tracks,
                cues_by_track_id={"999": [{
                    "name": "MIX IN", "color_hex": "#00FF00", "start_s": 1.0,
                    "cue_kind": "memory", "hot_cue_index": None, "loop_end_s": None,
                }]},
                output_path=output_path,
                playlist_name="X",
            )

    def test_write_export_from_db_sourced_tracks_no_raw_attrib(self):
        """Tracks from rekordbox_db.get_playlist_tracks() have no raw_attrib
        (they're read from the live database, not a parsed XML file) --
        write_export must build a valid TRACK element from core fields
        alone, defaulting the rest."""
        db_sourced_tracks = [
            {
                "track_id": "500", "name": "DB Track", "artist": "DB Artist",
                "album": "DB Album", "total_time": 210, "average_bpm": 128.0,
                "tonality": "5A", "location": "/Users/dj/Music/db track.mp3",
                "isrc": "USDB00000001", "raw_attrib": None,
            },
        ]
        output_path = Path(self.tmpdir.name) / "output_db.xml"
        rbxml.write_export(
            tracks_in_order=db_sourced_tracks,
            cues_by_track_id={},
            output_path=output_path,
            playlist_name="DB Sourced Set",
        )

        out_tracks = rbxml.parse_collection(output_path)
        self.assertEqual(len(out_tracks), 1)
        t = out_tracks[0]
        self.assertEqual(t["name"], "DB Track")
        self.assertEqual(t["artist"], "DB Artist")
        self.assertEqual(t["average_bpm"], "128.00")
        self.assertEqual(t["tonality"], "5A")
        # Space in the path round-trips through the file:// URI encode/decode.
        self.assertEqual(t["location"], "/Users/dj/Music/db track.mp3")

    def test_write_export_applies_comments_override(self):
        """comments_by_track_id overrides Comments on both an XML-sourced
        (raw_attrib populated) track and a DB-sourced (no raw_attrib) one."""
        xml_sourced = rbxml.parse_playlist(self.source_path, "Rough Setlist")[0]  # TrackID "1"
        db_sourced = {
            "track_id": "500", "name": "DB Track", "artist": "DB Artist",
            "album": "DB Album", "total_time": 210, "average_bpm": 128.0,
            "tonality": "5A", "location": "/Users/dj/Music/db track.mp3",
            "isrc": "USDB00000001", "raw_attrib": None,
        }
        output_path = Path(self.tmpdir.name) / "output_comments.xml"
        rbxml.write_export(
            tracks_in_order=[xml_sourced, db_sourced],
            cues_by_track_id={},
            output_path=output_path,
            playlist_name="Commented Set",
            comments_by_track_id={
                "1": "Next: Track Two, 8A to 9A, 124 to 126 BPM, blend at 3:00, bass swap at 3:30.",
                "500": "Next: Someone Else, 5A to 6A, 128 to 130 BPM, blend at 1:00, bass swap at 1:30.",
            },
        )

        out_root = ET.parse(output_path).getroot()
        track_els = {t.get("TrackID"): t for t in out_root.find("COLLECTION").findall("TRACK")}
        self.assertEqual(
            track_els["1"].get("Comments"),
            "Next: Track Two, 8A to 9A, 124 to 126 BPM, blend at 3:00, bass swap at 3:30.",
        )
        self.assertEqual(
            track_els["500"].get("Comments"),
            "Next: Someone Else, 5A to 6A, 128 to 130 BPM, blend at 1:00, bass swap at 1:30.",
        )

    def test_write_export_without_comments_keeps_existing_behavior(self):
        """No comments_by_track_id given (the default) -- unchanged from
        before this feature existed: DB-sourced tracks default to "",
        XML-sourced tracks keep their original Comments verbatim."""
        tracks = rbxml.parse_playlist(self.source_path, "Rough Setlist")
        output_path = Path(self.tmpdir.name) / "output_no_comments.xml"
        rbxml.write_export(
            tracks_in_order=tracks, cues_by_track_id={},
            output_path=output_path, playlist_name="No Comments Set",
        )
        out_root = ET.parse(output_path).getroot()
        track1 = next(t for t in out_root.find("COLLECTION").findall("TRACK") if t.get("TrackID") == "1")
        # SAMPLE_XML's track 1 never had a Comments attribute at all, and
        # raw_attrib is preserved verbatim -- so it stays absent (None),
        # not invented as "".
        self.assertIsNone(track1.get("Comments"))


class TestWindowsPaths(unittest.TestCase):
    """rekordbox also runs on Windows; the earlier POSIX-only implementation
    would have mis-encoded a drive-letter path. Confirmed against a real
    example from Pioneer's own demo XML (fetched during this project's
    pyrekordbox research): a path like
    r"C:\\Music\\PioneerDJ\\Demo Tracks\\Demo Track 1.mp3" encodes to
    "file://localhost/C:/Music/PioneerDJ/Demo%20Tracks/Demo%20Track%201.mp3".
    """

    def test_windows_path_to_location_matches_real_example(self):
        windows_path = r"C:\Music\PioneerDJ\Demo Tracks\Demo Track 1.mp3"
        location = rbxml._path_to_location(windows_path)
        self.assertEqual(
            location,
            "file://localhost/C:/Music/PioneerDJ/Demo%20Tracks/Demo%20Track%201.mp3",
        )

    def test_windows_location_decodes_back_to_native_path(self):
        location = "file://localhost/C:/Music/PioneerDJ/Demo%20Tracks/Demo%20Track%201.mp3"
        path = rbxml._location_to_path(location)
        self.assertEqual(path, r"C:\Music\PioneerDJ\Demo Tracks\Demo Track 1.mp3")

    def test_windows_path_round_trips(self):
        windows_path = r"D:\DJ Music\Warehouse Set\04 Track (Extended Mix).flac"
        location = rbxml._path_to_location(windows_path)
        self.assertEqual(rbxml._location_to_path(location), windows_path)

    def test_posix_path_still_single_slash_not_doubled(self):
        # Regression guard: pyrekordbox's own rbxml.encode_path double-slashes
        # a POSIX absolute path (confirmed by running it directly against a
        # real path during this project's research) -- this project's own
        # encoder must NOT reproduce that for the platform it actually runs on.
        posix_path = "/Users/dj/Music/track one.mp3"
        location = rbxml._path_to_location(posix_path)
        self.assertEqual(location, "file://localhost/Users/dj/Music/track%20one.mp3")
        self.assertNotIn("localhost//", location)

    def test_posix_path_round_trips_unchanged(self):
        posix_path = "/Users/dj/Music/track one.mp3"
        location = rbxml._path_to_location(posix_path)
        self.assertEqual(rbxml._location_to_path(location), posix_path)


if __name__ == "__main__":
    unittest.main()
