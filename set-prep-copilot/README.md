# Set Prep Copilot

A companion tool for rekordbox: it reads a playlist from your local rekordbox
library, analyzes each track's audio (BPM, key, energy, phrases), orders the
set for smooth transitions, places transition cues, and hands the result
back to rekordbox as an importable XML. It also ships a practice library of
openly licensed house tracks, graded by difficulty (see "Practice catalog"
below). See `../RekordBox-Plugin Design Doc.md` for the full picture —
this file is just setup.

## Prerequisites

- Python 3.9 or newer.
- rekordbox installed and opened **at least once** on your machine (so its
  local database and config exist for the tool to read).

## Setup

```bash
cd set-prep-copilot
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running it

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8888
```

Then open `http://127.0.0.1:8888` in your browser.

## Using it

1. **Setup** — pick a playlist. This reads straight from your local
   rekordbox library (no manual XML export or upload needed), and lets you
   choose a set shape (warm up / build / peak / cool down).
2. **Results** — see the reordered tracklist and the cues placed on each
   transition.
3. **Export** — download a rekordbox XML with the new playlist and cues
   (you still import it yourself in rekordbox — the Results page has the
   exact steps; import the tracks, not just the playlist, or the cues
   won't come in).
4. **Practice** — walk through each transition and see which control to
   move, when.

## Known limitations

- Analysis only works on **local audio files**. Streamed tracks inside
  rekordbox (Spotify, Beatport, SoundCloud, TIDAL) can't be analyzed: DRM
  blocks reading the audio, and the services' terms forbid analyzing it.
- Analyzing a full 15–30 track set runs real audio processing per track and
  can take a while — this isn't instant.

## Practice catalog

`python -m app.catalog.build --target 300` builds a graded practice library
of Creative Commons house tracks from Internet Archive netlabels into
`catalog/` (gitignored, about 3.5 GB for 300 tracks). It downloads, analyzes
and rates each track, splits the catalog into five difficulty levels, pairs
tracks into lessons per level, and writes `CREDITS.md`, which the CC BY
licenses require the app to show. Interrupted runs resume where they stopped.
License policy (non-commercial allowed, no-derivatives excluded) lives in
`app/catalog/licenses.py`; see `../reports/Free house music audio sources.md`
for why.
