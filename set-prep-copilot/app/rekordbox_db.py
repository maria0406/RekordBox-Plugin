"""Reads the DJ's live rekordbox library (playlists + tracks) directly from
rekordbox's own local database, via pyrekordbox, instead of requiring a
manual "File > Export Collection in xml format" + upload every session.

Read-only: every function here only queries (never .add()s or .commit()s to)
the database session, so this can't touch or corrupt the live library --
unlike the direct-DB cue-*write* path the design doc's rekordbox research
already ruled out for the MVP as too risky, reading is pyrekordbox's core,
well-trodden use case. pyrekordbox's own constructor only *warns* (does not
block or raise) when rekordbox is running at the same time, per its source:
`if pid: logger.warning("Rekordbox is running!")`. Whether that holds up in
practice on a real running rekordbox instance is still a day-1 check, like
the other rekordbox-integration risk items already in the design doc.

Schema confirmed directly from pyrekordbox's installed source (0.4.4,
db6/tables.py and db6/database.py) rather than guessed:
- DjmdContent.BPM is an integer, stored as BPM * 100 -- confirmed from
  pyrekordbox's own test suite (`track2.BPM = 12900` for a 129.00 BPM
  track), not assumed.
- DjmdContent.FolderPath is already a plain local filesystem path --
  confirmed from pyrekordbox's own test suite (`assert content.FolderPath
  == path` where `path` is a plain `os.path.join` result) -- unlike the XML
  format's Location attribute, no file:// URI decoding needed.
- DjmdContent.ISRC exists directly on the content row (rekordbox extracts it
  from the file's tags during its own analysis). This is a real upgrade
  over the XML-export path, which carries no ISRC at all -- tracks read
  this way get real ISRC-based Spotify matching instead of always falling
  back to the text-search path.
- get_playlist_contents() works for both regular and smart playlists, but
  raises ValueError on a folder -- folders are filtered out of the picker.
- Track order within get_playlist_contents() is NOT preserved (no ORDER BY
  in pyrekordbox's own implementation). That's fine here: Set Prep Copilot
  reorders the whole set by its own BPM/key/energy scoring regardless of
  what order the tracks were in inside rekordbox.
"""
from __future__ import annotations

from pyrekordbox import Rekordbox6Database


class RekordboxDbError(Exception):
    pass


def _open_db() -> Rekordbox6Database:
    try:
        return Rekordbox6Database()
    except FileNotFoundError as exc:
        raise RekordboxDbError(
            "Couldn't find a rekordbox library on this machine. Open rekordbox "
            "at least once (so it creates its database), then try again."
        ) from exc
    except ImportError as exc:
        raise RekordboxDbError(
            "Couldn't unlock the rekordbox database: the 'sqlcipher3' package "
            "isn't available in this environment. Re-run `pip install -r "
            "requirements.txt`."
        ) from exc


def _playlist_path(playlist, by_id: dict) -> str:
    """Breadcrumb path (e.g. 'Techno / Peak Time / Friday Set') by walking
    ParentID up to the root, so playlists with the same name in different
    folders are still distinguishable in the picker."""
    parts = [playlist.Name]
    parent_id = playlist.ParentID
    seen = {playlist.ID}
    while parent_id and parent_id in by_id and parent_id not in seen:
        parent = by_id[parent_id]
        if parent.Name and parent.ParentID is not None:  # skip the synthetic root node
            parts.append(parent.Name)
        seen.add(parent_id)
        parent_id = parent.ParentID
    return " / ".join(reversed(parts))


def list_playlists() -> list[dict]:
    """Every non-folder playlist (regular or smart) in the live library, as
    {"id": str, "name": str, "path": str} for a picker UI."""
    db = _open_db()
    try:
        all_playlists = list(db.get_playlist())
        by_id = {p.ID: p for p in all_playlists}
        return [
            {"id": p.ID, "name": p.Name, "path": _playlist_path(p, by_id)}
            for p in all_playlists
            if not p.is_folder
        ]
    finally:
        db.close()


def get_playlist_tracks(playlist_id: str) -> list[dict]:
    """The named playlist's tracks, in the same shape
    rekordbox_xml.parse_playlist() returns (minus `raw_attrib`, which stays
    empty here -- see rekordbox_xml._track_element_from_dict for how that's
    handled on export), so the rest of the pipeline (audio_analysis,
    scoring, cues, rekordbox_xml.write_export) doesn't care which source a
    track dict came from."""
    db = _open_db()
    try:
        playlist = db.get_playlist(ID=playlist_id)
        if playlist is None:
            raise RekordboxDbError(f"Playlist ID {playlist_id!r} not found.")
        if playlist.is_folder:
            raise RekordboxDbError(f"{playlist.Name!r} is a folder, not a playlist.")

        tracks = []
        for content in db.get_playlist_contents(playlist):
            if not content.FolderPath:
                continue  # no local file location -- can't be analyzed
            tracks.append({
                "track_id": content.ID,
                "name": content.Title,
                "artist": content.ArtistName,
                "album": content.AlbumName,
                "total_time": content.Length,
                "average_bpm": (content.BPM / 100.0) if content.BPM else None,
                "tonality": content.KeyName,
                "location": content.FolderPath,
                "isrc": content.ISRC,
                "raw_attrib": None,
            })
        return tracks
    finally:
        db.close()
