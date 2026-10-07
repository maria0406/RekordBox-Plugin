"""Read/write rekordbox collection XML exports.

Schema is from Pioneer's own "XML file format for playlists sharing" spec
(https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf), fetched
and transcribed directly rather than guessed. Chosen as the MVP path over
writing rekordbox's local SQLCipher database directly: XML import is the
only sanctioned, documented mechanism, has production precedent (Mixed In
Key ships the same export-XML / re-import workflow), and a malformed XML
file can't corrupt the live library the way a bad direct DB write could.

IMPORTANT, UNVERIFIED (flag for the design doc's "day 1" test gate):
Pioneer's own spec PDF documents POSITION_MARK with exactly five attributes:
Name, Type, Start, End, Num -- there is NO documented color attribute on
POSITION_MARK. The only color attribute the spec documents anywhere is
TRACK's own "Colour" (whole-track color tag, RGB hex, a fixed 8-value
palette: Rose 0xFF007F, Red 0xFF0000, Orange 0xFFA500, Lemon 0xFFFF00,
Green 0x00FF00, Turquoise 0x25FDE9, Blue 0x0000FF, Violet 0x660099).
Separately, earlier research in this project (a mixxx2rekordbox GitHub
issue) observed real-world rekordbox XML exports carrying Red/Green/Blue
attributes on POSITION_MARK in practice, with values matching this same
palette. Those two sources disagree on whether it's documented, not on the
palette itself -- both point at the same 8 hex values. This module:
  1. Uses that confirmed 8-color palette for CUE_COLORS below, since it is
     Pioneer's own reference implementation's color set either way.
  2. Writes Red/Green/Blue attributes on every POSITION_MARK as a hedge
     (an XML parser ignores attributes it doesn't recognize, so this can't
     break import even if rekordbox's cue import truly ignores them).
  3. Does NOT promise rekordbox will actually render that color on a cue,
     on the desktop app or on CDJ hardware. Confirming that is a day-1
     task, not something this code can verify.
"""
from __future__ import annotations

import datetime
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

CUE_COLORS = {
    "mix_in": "#00FF00",     # Green -- Pioneer palette
    "mix_out": "#FF0000",    # Red
    "bass_swap": "#FFA500",  # Orange
    "filter": "#0000FF",     # Blue
    "drop": "#660099",       # Violet
    "loop_8": "#FFFF00",     # Lemon
    "late_in": "#25FDE9",    # Turquoise
    "early_out": "#FF007F",  # Rose
    # Pioneer's palette has only 8 colors and all are taken; rekordbox ignores
    # memory-cue colors on import anyway, so this one only shows in the app.
    "fake_drop": "#B266FF",  # Light violet
    "out_option": "#FF7A7A",  # Light red, app only: extra ways out (OUT -16, -32, ...)
}

_TYPE_CUE = "0"
_TYPE_LOOP = "4"
_NUM_MEMORY = "-1"


class RekordboxXmlError(Exception):
    pass


# Matches a URI path component that decoded to a leading-slash-plus-drive-
# letter, e.g. "/C:/Music/...\" -- the shape a Windows path takes once run
# through urllib's URL parser. Group 1 is the real Windows path, still with
# forward slashes.
_WINDOWS_URI_PATH_RE = re.compile(r"^/([A-Za-z]:/.*)$")

# Matches a Windows path directly (drive letter + separator), to tell it
# apart from a POSIX absolute path before encoding.
_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _location_to_path(location: str) -> str:
    """file://localhost/... (or file:///...) -> a plain local filesystem
    path, POSIX or Windows.

    NOTE on why this isn't just pyrekordbox's own rbxml.decode_path/
    encode_path: those are correct for the one real-world example this
    project has actually confirmed (a Windows path in Pioneer's own demo
    XML), but pyrekordbox's encode_path unconditionally prepends another
    "/" to the path before the URI prefix -- for a POSIX absolute path
    (which already starts with "/"), that produces a double slash
    ("file://localhost//Users/..."), confirmed by actually running it
    against a real path from this project's own (Mac) rekordbox library.
    Every existing test fixture and every real single-slash path this
    project has actually seen from rekordbox use a single slash, so this
    implementation keeps that for POSIX and only special-cases the
    Windows drive-letter shape, rather than adopting a behavior that
    would regress the primary platform this project runs on.
    """
    parsed = urllib.parse.urlparse(location)
    path = urllib.parse.unquote(parsed.path)
    windows_match = _WINDOWS_URI_PATH_RE.match(path)
    if windows_match:
        return windows_match.group(1).replace("/", "\\")
    return path


def _path_to_location(path: str) -> str:
    """A plain local filesystem path (POSIX or Windows) -> a
    file://localhost/... URI, per spec.

    Windows encoding confirmed against a real example (Pioneer's own demo
    XML, fetched during this project's pyrekordbox research): a path like
    r"C:\\Music\\PioneerDJ\\Demo Tracks\\Demo Track 1.mp3" encodes to
    "file://localhost/C:/Music/PioneerDJ/Demo%20Tracks/Demo%20Track%201.mp3"
    -- backslashes become forward slashes, and the drive letter sits right
    after the prefix's single trailing slash, with no extra separator.
    """
    path_str = str(path)
    if _WINDOWS_PATH_RE.match(path_str):
        normalized = path_str.replace("\\", "/")
        quoted = urllib.parse.quote(normalized, safe=":/")
        return f"file://localhost/{quoted}"

    quoted = urllib.parse.quote(path_str)
    if not quoted.startswith("/"):
        quoted = "/" + quoted
    return f"file://localhost{quoted}"


def _track_attrs_to_dict(track_el: ET.Element) -> dict:
    attrs = dict(track_el.attrib)
    d = {
        "track_id": attrs.get("TrackID"),
        "name": attrs.get("Name"),
        "artist": attrs.get("Artist"),
        "album": attrs.get("Album"),
        "total_time": attrs.get("TotalTime"),
        "average_bpm": attrs.get("AverageBpm"),
        "tonality": attrs.get("Tonality"),
        "location": _location_to_path(attrs["Location"]) if attrs.get("Location") else None,
        "raw_attrib": attrs,  # preserved verbatim when we re-emit this track
    }
    return d


def parse_collection(path: str | Path) -> list[dict]:
    """Every track in the COLLECTION: TrackID, Name, Artist, Location (local
    filesystem path, decoded from its file:// URI), TotalTime, and any
    AverageBpm/Tonality rekordbox already computed.
    """
    tree = ET.parse(path)
    root = tree.getroot()
    collection = root.find("COLLECTION")
    if collection is None:
        raise RekordboxXmlError(f"No <COLLECTION> element found in {path}")
    return [_track_attrs_to_dict(t) for t in collection.findall("TRACK")]


def _find_playlist_node(root: ET.Element, playlist_name: str) -> ET.Element | None:
    playlists = root.find("PLAYLISTS")
    if playlists is None:
        return None
    # Playlists can be nested in folder NODEs; search the whole tree.
    for node in playlists.iter("NODE"):
        if node.get("Type") == "1" and node.get("Name") == playlist_name:
            return node
    return None


def list_playlist_names(path: str | Path) -> list[str]:
    """Every playlist (Type=1 NODE) name in the file, for a picker UI."""
    tree = ET.parse(path)
    root = tree.getroot()
    playlists_el = root.find("PLAYLISTS")
    if playlists_el is None:
        return []
    return sorted({n.get("Name") for n in playlists_el.iter("NODE") if n.get("Type") == "1"})


def parse_playlist(path: str | Path, playlist_name: str) -> list[dict]:
    """The named playlist's tracks, in order, each resolved to a full track
    dict via the COLLECTION. Raises RekordboxXmlError (listing available
    playlist names) if playlist_name isn't found.
    """
    tree = ET.parse(path)
    root = tree.getroot()

    node = _find_playlist_node(root, playlist_name)
    if node is None:
        playlists_el = root.find("PLAYLISTS")
        available = sorted(
            {n.get("Name") for n in playlists_el.iter("NODE") if n.get("Type") == "1"}
            if playlists_el is not None
            else set()
        )
        raise RekordboxXmlError(
            f"Playlist {playlist_name!r} not found. Available playlists: {available}"
        )

    collection = root.find("COLLECTION")
    by_id = {t.get("TrackID"): _track_attrs_to_dict(t) for t in collection.findall("TRACK")}
    by_location = {t["location"]: t for t in by_id.values() if t["location"]}

    key_type = node.get("KeyType", "0")
    tracks = []
    for track_ref in node.findall("TRACK"):
        key = track_ref.get("Key")
        if key_type == "1":
            resolved = by_location.get(_location_to_path(key))
        else:
            resolved = by_id.get(key)
        if resolved is None:
            raise RekordboxXmlError(
                f"Playlist {playlist_name!r} references track key {key!r} "
                f"(KeyType={key_type}) not found in COLLECTION"
            )
        tracks.append(resolved)
    return tracks


# Attributes a TRACK element needs for rekordbox's XML import to accept it,
# beyond the core fields every track dict carries -- confirmed from Pioneer's
# own real example export (pyrekordbox's XML tutorial). Tracks read via the
# legacy XML-upload path (raw_attrib populated) use their real original
# values for all of these instead; this default set only applies to
# DB-sourced tracks (see rekordbox_db.py), which don't have them.
_TRACK_ATTR_DEFAULTS = {
    "Composer": "", "Grouping": "", "Genre": "", "Kind": "", "Size": "0",
    "DiscNumber": "0", "TrackNumber": "0", "Year": "0", "BitRate": "0",
    "SampleRate": "0", "Comments": "", "PlayCount": "0", "Rating": "0",
    "Remixer": "", "Label": "", "Mix": "",
}


def _track_element_from_dict(track: dict) -> ET.Element:
    """Build a <TRACK> element for the COLLECTION. If `track["raw_attrib"]`
    is populated (the track came from `parse_collection`/`parse_playlist`,
    i.e. a real rekordbox XML export), those original attributes are used
    verbatim -- full fidelity, nothing invented. Otherwise (the track came
    from `rekordbox_db.get_playlist_tracks`, a direct read of rekordbox's
    live database) the element is built fresh from the track's core fields
    plus `_TRACK_ATTR_DEFAULTS` for everything rekordbox's XML import
    expects to see that we don't have a real value for.
    """
    el = ET.Element("TRACK")
    raw = track.get("raw_attrib")
    if raw:
        el.attrib.update(raw)
        return el

    el.set("TrackID", track["track_id"])
    el.set("Name", track.get("name") or "")
    el.set("Artist", track.get("artist") or "")
    el.set("Album", track.get("album") or "")
    total_time = track.get("total_time")
    el.set("TotalTime", str(int(total_time)) if total_time else "0")
    avg_bpm = track.get("average_bpm")
    el.set("AverageBpm", f"{float(avg_bpm):.2f}" if avg_bpm else "0.00")
    el.set("Tonality", track.get("tonality") or "")
    el.set("DateAdded", datetime.date.today().isoformat())
    el.set("Location", _path_to_location(track["location"]))
    for key, default in _TRACK_ATTR_DEFAULTS.items():
        el.set(key, default)
    return el


def write_export(
    tracks_in_order: list[dict],
    cues_by_track_id: dict[str, list[dict]],
    output_path: str | Path,
    playlist_name: str,
    comments_by_track_id: dict[str, str] | None = None,
) -> None:
    """Write a new, self-contained rekordbox XML: a COLLECTION holding only
    `tracks_in_order` (built from each track dict -- see
    `_track_element_from_dict`), our cues as POSITION_MARK children, and one
    PLAYLISTS node named `playlist_name` listing them in order. This file
    doesn't carry the DJ's other playlists or library tracks -- it's meant
    to be imported through rekordbox's "rekordbox xml" sidebar tree, which
    merges by location against the live library rather than replacing it.
    Verified in rekordbox 7 (Oct 4, 2026): "Import Playlist" alone adds no
    cues to tracks already in the library; "Import To Collection" on the
    tracks with overwrite brings in every cue at the exact time, the names,
    the hot cue's color (snapped to rekordbox's palette) and Comments, but
    NOT memory-cue colors, and only one memory cue per position (see
    cues.merge_coincident_memory_cues). It also overwrites the library's
    AverageBpm/Tonality, which is why those carry rekordbox's own values.

    `cues_by_track_id[track_id]` entries: {"name": str, "color_hex":
    "#RRGGBB", "start_s": float, "cue_kind": "hot"|"memory",
    "hot_cue_index": int|None (0-7, hot only), "loop_end_s": float|None}.

    `comments_by_track_id`, if given (see `cues.build_transition_notes`):
    {track_id: comment_string}. Per the design doc's "Transition note in
    the Comments field" -- a track named here gets its Comments attribute
    SET to that string, a real overwrite, not a fallback-if-empty. That
    applies whether the track came from a real rekordbox XML export
    (`raw_attrib` populated, which would otherwise carry through its
    original Comments verbatim) or fresh from the database (which
    otherwise defaults Comments to ""). A track not named here keeps
    whatever `_track_element_from_dict` already gave it.
    """
    comments_by_track_id = comments_by_track_id or {}

    root = ET.Element("DJ_PLAYLISTS", {"Version": "1.0.0"})
    ET.SubElement(root, "PRODUCT", {
        "Name": "Set Prep Copilot", "Version": "0.1", "Company": "Set Prep Copilot",
    })
    collection = ET.SubElement(root, "COLLECTION", {"Entries": str(len(tracks_in_order))})

    track_els_by_id: dict[str, ET.Element] = {}
    for t in tracks_in_order:
        el = _track_element_from_dict(t)
        track_id = t["track_id"]
        if track_id in comments_by_track_id:
            el.set("Comments", comments_by_track_id[track_id])
        collection.append(el)
        track_els_by_id[track_id] = el

    for track_id, cues in cues_by_track_id.items():
        track_el = track_els_by_id.get(track_id)
        if track_el is None:
            raise RekordboxXmlError(
                f"Cue list references TrackID {track_id!r} not present in tracks_in_order"
            )
        for cue in cues:
            is_loop = cue.get("loop_end_s") is not None
            mark = ET.SubElement(track_el, "POSITION_MARK")
            mark.set("Name", cue["name"])
            mark.set("Type", _TYPE_LOOP if is_loop else _TYPE_CUE)
            mark.set("Start", f"{cue['start_s']:.3f}")
            if is_loop:
                mark.set("End", f"{cue['loop_end_s']:.3f}")
            if cue["cue_kind"] == "hot":
                idx = cue["hot_cue_index"]
                if idx is None or not (0 <= idx <= 7):
                    raise RekordboxXmlError(
                        f"Hot cue {cue['name']!r} on track {track_id} needs "
                        f"hot_cue_index in 0-7, got {idx!r}"
                    )
                mark.set("Num", str(idx))
            elif cue["cue_kind"] == "memory":
                mark.set("Num", _NUM_MEMORY)
            else:
                raise RekordboxXmlError(f"Unknown cue_kind {cue['cue_kind']!r}")
            # Hedge: not in Pioneer's documented POSITION_MARK schema, but
            # observed in real-world exports (see module docstring). Ignored
            # by a parser that doesn't recognize it either way.
            hex_color = cue["color_hex"].lstrip("#")
            mark.set("Red", str(int(hex_color[0:2], 16)))
            mark.set("Green", str(int(hex_color[2:4], 16)))
            mark.set("Blue", str(int(hex_color[4:6], 16)))

    playlists = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(playlists, "NODE", {"Type": "0", "Name": "ROOT", "Count": "1"})

    new_playlist = ET.SubElement(root_node, "NODE", {
        "Type": "1", "Name": playlist_name,
        "Entries": str(len(tracks_in_order)), "KeyType": "0",
    })
    for t in tracks_in_order:
        ET.SubElement(new_playlist, "TRACK", {"Key": t["track_id"]})

    out_tree = ET.ElementTree(root)
    ET.indent(out_tree, space="  ")
    out_tree.write(output_path, encoding="UTF-8", xml_declaration=True)
