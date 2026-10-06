# Testing guide

Two layers: the automated suite (fast, no real rekordbox needed) and a
manual walkthrough (needs a real rekordbox library).
Do the automated suite first — if it's not green, the manual walkthrough
isn't worth your time yet.

## 1. Automated tests

```bash
cd set-prep-copilot
source .venv/bin/activate
python3 -m unittest discover -s tests -v
```

Expect **75 tests, all passing**. What each file actually covers:

| File | Covers |
| --- | --- |
| `test_scoring.py` | Camelot key scoring, BPM scoring (incl. half/double-time), greedy+swap ordering, locked opener/closer |
| `test_cues.py` | Cue placement (MIX IN/OUT, BASS SWAP, FILTER, DROP, LOOP 8), Comments-field transition notes |
| `test_rekordbox_xml.py` | XML parse/write round-trip, DB-sourced (no `raw_attrib`) export, Windows vs. POSIX path handling, Comments override |
| `test_audio_analysis.py` | BPM recovery on a synthetic click track, output shape/types |
| `test_main_routes.py` | `/setup/tracks`, `/results/move`, `/results/nudge-cue`, missing-file skip handling — via FastAPI's `TestClient` with `rekordbox_db` mocked out |
| `test_catalog.py` | Practice catalog: CC license parsing and policy, Internet Archive harvesting (mocked HTTP), difficulty features and levels, lesson pairing rules |

If a test fails after you've changed code, **read the failure before re-running** —
several of these encode real facts about external systems (confirmed BPM
scaling, confirmed XML attribute names) that aren't safe to "fix" by changing
the assertion.

Things the automated suite deliberately does **not** cover, because they need
real external systems:
- Whether the Internet Archive's live API still returns what `app/catalog/internet_archive.py` expects.
- Whether rekordbox actually imports the exported XML cleanly.
- Whether cue colors render on the rekordbox desktop app or CDJ hardware.

## 2. Manual walkthrough

### Prerequisites
- rekordbox installed and opened at least once (so its local database exists).
- At least one playlist in your rekordbox library with a few tracks whose audio files are actually present on disk.

### Start the server

```bash
cd set-prep-copilot
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8888
```

Open `http://127.0.0.1:8888`.

### Walkthrough steps

1. **Setup** — `/` should redirect straight here. — confirm the playlist dropdown lists your *actual* rekordbox playlists (not folders — folders shouldn't appear). Pick one, and confirm the "Lock as opener"/"Lock as closer" dropdowns populate with that playlist's actual tracks (this is a live `fetch` to `/setup/tracks` — check the browser console if they stay empty). Try both with and without locking a track, and try each of the four set shapes at least once across your test runs.
2. **Analyze** — submit the form. This is the slow step (real audio analysis per track) — expect it to take roughly proportional to track count × track length, not instant. If you have a playlist with a track whose file has been moved/deleted, confirm it shows up in the "N tracks were skipped" notice on Results instead of crashing the request.
3. **Results** — check:
   - If you locked an opener/closer, confirm it's actually first/last in the list.
   - Cue dots appear per track, colors match the legend (top nav → "Cue legend").
   - Click an up/down arrow on a track — confirm the order actually swaps and the cue dots update (cues are rebuilt on reorder, so a track's cues should change based on its new neighbors).
   - Click a cue's +/- button — confirm nothing visually breaks (the change is only visible in the exported XML/comments, not on this page — see step 4).
4. **Export to rekordbox** — click "Download rekordbox XML," then import it in rekordbox: point `Preferences > Advanced > Database > rekordbox xml` at the file, then in the sidebar's **rekordbox xml** tree select all of **All Tracks** > right-click > **Import To Collection** (allow the overwrite), then right-click the playlist > **Import Playlist**. Importing only the playlist brings in no cues for tracks already in the library (confirmed Oct 4, 2026). This is the step the automated suite *cannot* verify. Check specifically:
   - Does the new playlist appear with the right tracks in the right order?
   - Do the cues appear on the waveform/cue list at all?
   - Do the cue **colors** match what the legend says, or come in some other color, or no color? (This is a known open question — see the design doc's open questions list. Whatever you observe is genuinely new information, write it down.)
   - Does the **Comments** column show the "Next: track X, ..." summary?
   - If you re-import onto a track that already had hand-set cues, do your old cues survive, or get wiped? (Also an open design-doc question.)
5. **Practice** — walk through a transition, click each cue button, confirm the corresponding control on the deck diagram animates (fader slides, knob turns, button pulses). This is cosmetic/preview only — there's no real MIDI listening yet, so don't expect it to react to an actual controller.

### Edge cases worth deliberately trying
- A playlist with only 1 track (ordering/cue code should not crash on a set with no transitions).
- A playlist where every track has the exact same BPM and key (scoring should still produce *some* valid order, not error).
- Running `/analyze` twice in a row on different playlists in the same server session (session state should fully reset, not merge the two runs).
- Killing the server mid-analysis and restarting it (in-memory session state is lost by design — confirm you land back at `/setup`, not a broken state).

## 3. What "passing" doesn't tell you

The automated suite and the manual walkthrough together still don't answer
the questions in the design doc's **Open questions** section — those need
real DJ usage over time (cue-accuracy
rate, actual prep-time reduction). Don't treat "75/75 green + one clean
walkthrough" as "done" — treat it as "ready for a real tester."
