"""Bench test for the Phrase Countdown Light: drive the ring with fake cues
at a steady tempo, no rekordbox or controller needed.

    pip install pyserial
    python bench_countdown.py                  # finds the board by its HELLO
    python bench_countdown.py --bpm 124 --port /dev/cu.usbmodem1101
    python bench_countdown.py --silent-after 20  # stop sending: ring should go idle after 2 s

Each cue is scheduled 10 bars ahead, so the ring sits idle for 2 bars, then
counts down 8. Cues cycle through the app's MIX IN, BASS SWAP and MIX OUT
colors. A tick is printed on every beat so the LEDs can be checked against a
metronome: one LED should go out every 2 beats.
"""
from __future__ import annotations

import argparse
import sys
import time

import serial
from serial.tools import list_ports

HELLO = "HELLO pcl"
SEND_HZ = 10
LEAD_BARS = 10
GAP_BARS = 2  # after a cue, before the next one is scheduled
CUES = [("MIX IN", "00FF00"), ("BASS SWAP", "FFA500"), ("MIX OUT", "FF0000")]


def find_board() -> str | None:
    for port in list_ports.comports():
        try:
            with serial.Serial(port.device, 115200, timeout=0.5) as s:
                s.reset_input_buffer()
                s.write(b"?\n")
                deadline = time.monotonic() + 1.0
                while time.monotonic() < deadline:
                    if s.readline().decode(errors="replace").startswith(HELLO):
                        return port.device
        except (OSError, serial.SerialException):
            continue
    return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", help="serial port (default: probe every port for HELLO)")
    p.add_argument("--bpm", type=float, default=128.0)
    p.add_argument("--silent-after", type=float, default=None,
                   help="stop sending after this many seconds (link-loss test)")
    args = p.parse_args()

    port = args.port or find_board()
    if not port:
        sys.exit("No board answered '?' with HELLO. Is it plugged in and flashed?")
    ms_per_beat = 60000.0 / args.bpm
    bar_ms = 4 * ms_per_beat
    print(f"{port}: {args.bpm:g} BPM, {ms_per_beat:.1f} ms/beat, cue every {LEAD_BARS + GAP_BARS} bars")

    with serial.Serial(port, 115200, timeout=0) as s:
        start = time.monotonic()
        cue_index = 0
        cue_at = start + LEAD_BARS * bar_ms / 1000
        next_send = start
        next_beat = start
        beat = 0
        pending = ""
        while True:
            now = time.monotonic()
            if args.silent_after is not None and now - start > args.silent_after:
                print(f"Stopped sending at {args.silent_after:g} s: ring should breathe within 2 s.")
                time.sleep(5)
                return
            if now - cue_at > GAP_BARS * bar_ms / 1000:
                cue_index += 1
                cue_at += (LEAD_BARS + GAP_BARS) * bar_ms / 1000
            name, color = CUES[cue_index % len(CUES)]
            if now >= next_send:
                ms_to_cue = round((cue_at - now) * 1000)
                s.write(f"C {ms_to_cue} {round(ms_per_beat)} {color}\n".encode())
                next_send += 1 / SEND_HZ
            if now >= next_beat:
                beats_left = round((cue_at - now) * 1000 / ms_per_beat)
                print(f"beat {beat:4d}  {name:<9}  {beats_left:+4d} beats to cue")
                beat += 1
                next_beat += ms_per_beat / 1000
            pending += s.read(256).decode(errors="replace")
            *lines, pending = pending.split("\n")
            for line in lines:
                if line.strip():
                    print(f"  board: {line.strip()}")
            time.sleep(0.002)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
