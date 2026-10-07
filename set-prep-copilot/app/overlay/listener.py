"""Background MIDI listener: opens the FLX4 input (shared with rekordbox) and
feeds every message into one MidiTracker. Started on first use by the
overlay routes; a missing controller is reported, not fatal, so the overlay
still renders (and can be re-synced by hand)."""
from __future__ import annotations

import threading
import time

from .midi_clock import MidiTracker, load_map

PORT_HINT = "FLX4"

_lock = threading.Lock()
_tracker: MidiTracker | None = None
_status = {"connected": False, "port": None, "error": None, "map": None}
_port = None


def now() -> float:
    return time.monotonic()


def _on_message(msg) -> None:
    with _lock:
        _tracker.handle(msg, now())


def start() -> None:
    """Idempotent: open the port once per process."""
    global _tracker, _port
    with _lock:
        if _tracker is not None:
            return
        lookup, source = load_map()
        _tracker = MidiTracker(lookup)
        _status["map"] = source
    try:
        import mido

        names = [n for n in mido.get_input_names() if PORT_HINT.lower() in n.lower()]
        if not names:
            _status["error"] = f"No MIDI input matching {PORT_HINT!r}. Is the controller plugged in?"
            return
        _port = mido.open_input(names[0], callback=_on_message)
        _status.update(connected=True, port=names[0], error=None)
    except Exception as exc:  # no backend, port busy, ... -- overlay still works with manual sync
        _status["error"] = f"MIDI unavailable: {exc}"


def snapshot() -> dict:
    with _lock:
        state = _tracker.snapshot(now()) if _tracker else {"decks": {}, "controls": {}, "last_message": None}
    return {**state, "midi": dict(_status)}


def seek(deck: int, position: float) -> None:
    with _lock:
        if _tracker:
            _tracker.decks[deck].seek(now(), position)


def reset_for_tests(tracker: MidiTracker | None = None) -> None:
    global _tracker, _port
    with _lock:
        _tracker, _port = tracker, None
        _status.update(connected=False, port=None, error=None, map=None)
