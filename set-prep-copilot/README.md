# Set Prep Copilot

A companion tool for rekordbox: it reads a playlist from your local rekordbox
library, analyzes each track's audio (BPM, key, energy, phrases), orders the
set for smooth transitions, places transition cues, and hands the result
back to rekordbox (as an importable XML) and Spotify (as a preview
playlist). See `../RekordBox-Plugin Design Doc.md` for the full picture —
this file is just setup.

## Prerequisites

- Python 3.9 or newer.
- rekordbox installed and opened **at least once** on your machine (so its
  local database and config exist for the tool to read).
- A Spotify **Premium** account.
- **You do not need to create your own Spotify developer app.** This tool
  runs under one developer app (the project owner's). Spotify's Development
  Mode caps that app at 5 allowlisted testers — the owner adds your Spotify
  account to that allowlist, and you use the *same* Client ID everyone else
  does. It's not a secret (no client secret is ever used — this is the
  Authorization Code with PKCE flow), so just ask the owner for it.

## Setup

```bash
cd set-prep-copilot
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in `set-prep-copilot/` (same folder as this README):

```
SPOTIFY_CLIENT_ID=<paste the Client ID the project owner gives you>
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
SESSION_SECRET=<your own random value>
```

Generate a `SESSION_SECRET` with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Running it

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8888
```

Then open `http://127.0.0.1:8888` in your browser.

## Using it

1. **Connect** — log in with Spotify and approve the permissions.
2. **Setup** — pick a playlist. This reads straight from your local
   rekordbox library (no manual XML export or upload needed), and lets you
   choose a set shape (warm up / build / peak / cool down).
3. **Results** — see the reordered tracklist and the cues placed on each
   transition.
4. **Export** — download a rekordbox XML with the new playlist and cues
   (you still import it yourself in rekordbox, via
   `File > Import > rekordbox xml` — that step can't be automated), and/or
   create a preview playlist in your Spotify library in the same order.
5. **Practice** — walk through each transition and see which control to
   move, when.

## Known limitations

- Analysis only works on **local audio files**. Spotify-streamed tracks
  inside rekordbox can't be analyzed — Spotify's Web API doesn't expose raw
  audio or audio-analysis endpoints, and DRM means the tool can't read
  streamed audio either.
- Analyzing a full 15–30 track set runs real audio processing per track and
  can take a while — this isn't instant.
