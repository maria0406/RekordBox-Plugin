"""Estimates where each deck is in its track from the FLX4's MIDI messages.

rekordbox has no API for playback position (Pro DJ Link only runs in Export
mode; see the research notes), so the overlay listens to the same MIDI the
controller sends rekordbox -- macOS lets two apps read one input -- and
replays the deck logic itself:

- LOAD   -> position 0, paused, cue point 0
- PLAY   -> toggle play/pause; position advances at the deck's rate
- CUE    -> playing: jump back to the cue point and pause.
            paused: set the cue point here (Pioneer's "back cue" behaviour)
- TEMPO  -> rate = 1 + offset * TEMPO_RANGE

Known blind spots, by design for this first version: jog nudges, scratching,
hot cue pads, loops, beat jump and SYNC all move the real position without
the estimate following. The overlay offers a manual re-sync for that, and a
memory-reading source (e.g. rkbx_link) can replace this clock later without
touching the coach.

Pure logic, no MIDI I/O: `MidiTracker.handle(msg, now)` takes anything with
mido's message attributes, so it is testable without hardware.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MAP = Path(__file__).resolve().parent / "flx4_midi_map.json"
PROBED_MAP = APP_DIR.parent / "spikes" / "flx4_map.json"  # written by spikes/midi_probe.py

TEMPO_RANGE = 0.10  # rekordbox's default tempo slider range is +/-10%
TEMPO_FASTER_AT_BOTTOM = True  # Pioneer sliders: pulled toward you = faster. Unverified on FLX4 MIDI.

# MIDI map key -> the coach's control id (templates/_controller.html)
CONTROL_KEYS = {
    "ch1_fader": "ch1-fader", "ch2_fader": "ch2-fader",
    "ch1_low_eq": "ch1-low", "ch2_low_eq": "ch2-low",
    "ch1_cfx": "ch1-cfx", "ch2_cfx": "ch2-cfx",
    "crossfader": "crossfader",
}
KNOBS = {"ch1-low", "ch2-low", "ch1-cfx", "ch2-cfx"}


def load_map(path: Path | None = None) -> tuple[dict, str]:
    """{(kind, channel, number): key}, plus where it came from. Accepts both
    our default file and spikes/midi_probe.py output (it nests the identity
    under "first")."""
    if path is None:
        path = PROBED_MAP if PROBED_MAP.exists() else DEFAULT_MAP
    raw = json.loads(Path(path).read_text())
    lookup = {}
    for key, ident in raw.items():
        if key.startswith("_"):
            continue
        ident = ident.get("first", ident)
        number = ident.get("note", ident.get("control"))
        lookup[(_kind(ident["type"]), ident["channel"], number)] = key
    return lookup, str(path)


def _kind(msg_type: str) -> str:
    return "note" if msg_type in ("note_on", "note_off") else msg_type


@dataclass
class DeckClock:
    position: float = 0.0  # seconds into the track as of `since`
    since: float = 0.0
    playing: bool = False
    rate: float = 1.0
    cue_point: float = 0.0

    def at(self, now: float) -> float:
        return self.position + ((now - self.since) * self.rate if self.playing else 0.0)

    def _settle(self, now: float) -> None:
        self.position, self.since = self.at(now), now

    def load(self, now: float) -> None:
        self.position, self.since, self.playing, self.cue_point = 0.0, now, False, 0.0

    def toggle_play(self, now: float) -> None:
        self._settle(now)
        self.playing = not self.playing

    def cue(self, now: float) -> None:
        self._settle(now)
        if self.playing:
            self.position, self.playing = self.cue_point, False
        else:
            self.cue_point = self.position

    def set_rate(self, now: float, rate: float) -> None:
        self._settle(now)
        self.rate = rate

    def seek(self, now: float, position: float) -> None:
        self.position, self.since = max(0.0, position), now

    def snapshot(self, now: float) -> dict:
        return {"position": self.at(now), "playing": self.playing, "rate": self.rate}


@dataclass
class MidiTracker:
    lookup: dict
    decks: dict = field(default_factory=lambda: {1: DeckClock(), 2: DeckClock()})
    controls: dict = field(default_factory=dict)  # the DJ's actual control positions, coach ids
    last_message: str | None = None

    def handle(self, msg, now: float) -> None:
        number = getattr(msg, "note", getattr(msg, "control", None))
        key = self.lookup.get((_kind(msg.type), getattr(msg, "channel", None), number))
        if key is None:
            return
        self.last_message = key
        value = getattr(msg, "velocity", getattr(msg, "value", 0))
        pressed = msg.type == "note_on" and value > 0

        deck = 1 if key.startswith("deck1") else 2 if key.startswith("deck2") else None
        if deck and key.endswith("_play") and pressed:
            self.decks[deck].toggle_play(now)
        elif deck and key.endswith("_cue") and pressed:
            self.decks[deck].cue(now)
        elif deck and key.endswith("_load") and pressed:
            self.decks[deck].load(now)
        elif deck and key.endswith("_tempo"):
            offset = (value - 64) / 64  # MSB only: 7-bit is plenty for a rate estimate
            if not TEMPO_FASTER_AT_BOTTOM:
                offset = -offset
            self.decks[deck].set_rate(now, 1 + offset * TEMPO_RANGE)
        elif key in CONTROL_KEYS:
            cid = CONTROL_KEYS[key]
            self.controls[cid] = (value - 64) / 64 if cid in KNOBS else value / 127

    def snapshot(self, now: float) -> dict:
        return {
            "decks": {str(n): d.snapshot(now) for n, d in self.decks.items()},
            "controls": dict(self.controls),
            "last_message": self.last_message,
        }
