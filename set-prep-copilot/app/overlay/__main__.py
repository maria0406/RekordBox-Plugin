"""Open the Move Coach overlay: a frameless, transparent, always-on-top window
placed over rekordbox's track-browser corner.

    uvicorn app.main:app --host 127.0.0.1 --port 8888   # the app, as usual
    python -m app.overlay                               # then, in a second terminal

The window just loads http://127.0.0.1:8888/overlay; the app process does the
MIDI listening (app/overlay/listener.py). Prep a set in the app first -- the
overlay coaches that set's transitions in order.

Caveat: macOS keeps ordinary floating windows off another app's full-screen
Space, so run rekordbox windowed (maximized is fine), not in full screen.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request

WIDTH, HEIGHT = 560, 470
MARGIN = 24
REKORDBOX_OWNER = "rekordbox"


def rekordbox_bounds() -> dict | None:
    """{X, Y, Width, Height} of rekordbox's largest on-screen window, in
    screen points (top-left origin), or None. Window bounds don't need the
    Screen Recording permission; only window titles would."""
    try:
        import Quartz
    except ImportError:
        return None
    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    ) or []
    candidates = [
        w["kCGWindowBounds"] for w in windows
        if REKORDBOX_OWNER in str(w.get("kCGWindowOwnerName", "")).lower() and w.get("kCGWindowLayer", 1) == 0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda b: b["Width"] * b["Height"])


def placement(bounds: dict | None) -> tuple[int | None, int | None]:
    """Bottom-right of rekordbox's window: that's the track list, which a
    DJ glances at least mid-mix. None lets the OS place the window."""
    if not bounds:
        return None, None
    x = int(bounds["X"] + bounds["Width"] - WIDTH - MARGIN)
    y = int(bounds["Y"] + bounds["Height"] - HEIGHT - MARGIN)
    return max(0, x), max(0, y)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Open the Move Coach overlay over rekordbox.")
    parser.add_argument("--url", default="http://127.0.0.1:8888/overlay")
    args = parser.parse_args(argv)

    try:
        urllib.request.urlopen(args.url, timeout=3).close()
    except OSError:
        sys.exit(f"Can't reach {args.url}. Start the app first: uvicorn app.main:app --host 127.0.0.1 --port 8888")

    try:
        import webview
    except ImportError:
        sys.exit("pywebview isn't installed: pip install -r requirements.txt")

    bounds = rekordbox_bounds()
    if bounds is None:
        print("rekordbox window not found; opening the overlay where macOS puts it (drag it into place).")
    x, y = placement(bounds)
    webview.create_window(
        "Move Coach", args.url, width=WIDTH, height=HEIGHT, x=x, y=y,
        frameless=True, easy_drag=True, on_top=True, transparent=True,
        focus=False,  # don't steal keyboard focus: rekordbox's shortcuts keep working
    )
    webview.start()


if __name__ == "__main__":
    main()
