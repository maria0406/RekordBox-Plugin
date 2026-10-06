"""Spike: can we hear the DDJ-FLX4 while rekordbox is using it?

macOS CoreMIDI lets several apps read the same input port, so this script
should see every button/knob/fader message even with rekordbox open and in
control of the FLX4. That's the foundation for the Move Coach / Phrase
Countdown timing engine (see the design doc). Pioneer doesn't publish the
FLX4's MIDI map in a form we can rely on, so the wizard also records it.

    python spikes/midi_probe.py            # mapping wizard -> spikes/flx4_map.json
    python spikes/midi_probe.py --monitor  # print every message live (Ctrl-C to stop)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import mido

PORT_HINT = "FLX4"
MAP_PATH = Path(__file__).resolve().parent / "flx4_map.json"
SETTLE_SECONDS = 1.0  # after the first message, swallow the rest of that gesture

# The controls Move Coach needs (design doc "Cue to move mapping"), plus the
# ones the timing engine needs to follow playback.
CONTROLS = [
    ("deck1_play", "Press Deck 1 PLAY/PAUSE"),
    ("deck1_cue", "Press Deck 1 CUE"),
    ("deck2_play", "Press Deck 2 PLAY/PAUSE"),
    ("deck2_cue", "Press Deck 2 CUE"),
    ("deck1_load", "Press LOAD for Deck 1 (left load button by the browse knob)"),
    ("deck2_load", "Press LOAD for Deck 2"),
    ("ch1_fader", "Move the channel 1 volume fader"),
    ("ch2_fader", "Move the channel 2 volume fader"),
    ("crossfader", "Move the crossfader"),
    ("ch1_low_eq", "Turn the channel 1 LOW EQ knob"),
    ("ch2_low_eq", "Turn the channel 2 LOW EQ knob"),
    ("ch1_cfx", "Turn the channel 1 CFX (filter) knob"),
    ("ch2_cfx", "Turn the channel 2 CFX (filter) knob"),
    ("deck1_tempo", "Move the Deck 1 TEMPO slider"),
    ("deck2_tempo", "Move the Deck 2 TEMPO slider"),
    ("deck1_jog", "Spin the Deck 1 jog wheel (edge, not the top)"),
    ("deck1_loop", "Press Deck 1 4 BEAT/EXIT loop button"),
]


def open_port() -> mido.ports.BaseInput:
    names = mido.get_input_names()
    matches = [n for n in names if PORT_HINT.lower() in n.lower()]
    if not matches:
        sys.exit(f"No MIDI input matching {PORT_HINT!r}. Inputs seen: {names or 'none'}. Is the FLX4 plugged in?")
    print(f"Listening on: {matches[0]}")
    return mido.open_input(matches[0])


def identity(msg: mido.Message) -> dict:
    """What identifies a control: message type, channel, and note/CC number."""
    ident = {"type": msg.type, "channel": msg.channel}
    if hasattr(msg, "note"):
        ident["note"] = msg.note
    if hasattr(msg, "control"):
        ident["control"] = msg.control
    return ident


def drain(port, seconds: float) -> list[mido.Message]:
    msgs = []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for msg in port.iter_pending():
            msgs.append(msg)
        time.sleep(0.005)
    return msgs


def monitor(port) -> None:
    print("Move anything on the FLX4. Ctrl-C to stop.\n")
    start = time.monotonic()
    try:
        for msg in port:
            print(f"{time.monotonic() - start:9.3f}s  {msg}")
    except KeyboardInterrupt:
        pass


def wizard(port) -> None:
    print("For each prompt, do the move once, then let go.\n")
    mapping: dict[str, dict] = {}
    for key, prompt in CONTROLS:
        drain(port, 0.3)  # flush anything left over from the last control
        print(f"-> {prompt} ... ", end="", flush=True)
        first = None
        while first is None:
            for msg in port.iter_pending():
                if msg.type not in ("clock", "active_sensing"):
                    first = msg
                    break
            time.sleep(0.005)
        rest = drain(port, SETTLE_SECONDS)
        gesture = [first] + rest
        ids = {json.dumps(identity(m), sort_keys=True) for m in gesture}
        mapping[key] = {
            "first": identity(first),
            "all_identities": [json.loads(i) for i in sorted(ids)],
            "sample": [str(m) for m in gesture[:6]],
            "message_count": len(gesture),
        }
        print(f"got {first}  ({len(gesture)} msgs, {len(ids)} distinct ids)")

    MAP_PATH.write_text(json.dumps(mapping, indent=2))
    print(f"\nSaved {len(mapping)} controls to {MAP_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitor", action="store_true", help="print every message instead of running the wizard")
    args = parser.parse_args()
    with open_port() as port:
        monitor(port) if args.monitor else wizard(port)


if __name__ == "__main__":
    main()
