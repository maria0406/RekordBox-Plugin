# Set Prep Copilot: Design Doc

Sep 30, 2026 · @Maria Cruz

## Overview

Set Prep Copilot turns an unordered list of tracks into a ready-to-play set: it orders the tracks by BPM and key, marks where each transition should happen, and pushes the result back to the DJ's library.

The problem: prepping a set is the most time-consuming part of DJing. A DJ has to figure out which songs mix well together, then decide where in each song to start the blend, when to swap the bass, and when to use a filter. Today that means listening through every track and setting cues by hand.

**The gap in rekordbox today:** the track list sorts by one column at a time, so a DJ can sort by BPM or by key, but not both. Sorting by BPM scatters compatible keys, and sorting by key scatters tempos, so the DJ still has to build the order by hand. Set Prep Copilot orders the whole set by BPM and key together, then adds energy on top.

The product is a companion tool that sits beside rekordbox. It reads a setlist, analyzes the audio itself, and writes back a reordered playlist with labeled, color-coded cue points in rekordbox that tell the DJ what to do at each point in the track. For beginners without a library yet, it ships a practice catalog of openly licensed house tracks graded from easy to hard.

## Goals and non-goals

The MVP ships in 3 weeks and does three things well: order a set, mark transitions, and hand the result back to rekordbox.

**Goals**

- Take a setlist of 10 to 30 tracks and return an ordered set based on BPM and key compatibility
- Analyze each track's audio ourselves to find beats, phrases, and energy changes
- Mark each track with labeled cues for actions: mix in, mix out, bass swap, filter, and loop
- Import the ordered playlist and cues into rekordbox without manual re-entry

**Non-goals for the MVP**

- Genre-specific logic, including Latin to English house bridging
- Live, in-set guidance (moved to the Move Coach and Phrase Countdown Light extensions)
- A true in-app rekordbox plugin: rekordbox has no public plugin API, so this is a companion app that talks to rekordbox through its supported XML import
- Any Spotify integration (removed from scope Oct 4, 2026). It was redundant: Spotify's developer policy forbids analyzing its audio, its audio-features endpoints are gone for new apps, so it could only ever mirror a playlist rekordbox already has, while gating every user behind a login and a 5-tester cap. Streamed tracks of any service stay out of scope for analysis.
- Automatic mixing or AI-generated transitions: the DJ still performs the set

## Users and success metrics

The first users are student DJs at UT who play on rekordbox with a beginner or mid-level controller like the DDJ-FLX4, plus Maria as user zero.

| Metric | How it is measured | MVP target |
| --- | --- | --- |
| Prep time per set | Timed prep of a 15-track set, before vs. after | Cut by at least 50% (baseline measured in week 1) |
| Cue accuracy | Share of generated cues the DJ keeps without moving | 70% or more |
| Active testers | DJs who prep at least one real set with the tool | 5 |
| Would use again | One-question survey after a set | 4 of 5 testers say yes |

The baseline for prep time comes from user interviews in week 1, so every target is measured against real numbers, not guesses.

## End-to-end workflow

The DJ builds a rough setlist in rekordbox, runs it through the tool, and gets back an ordered, cued set in rekordbox.

1. **Build the setlist.** The DJ drags tracks into a rekordbox playlist, in any order.
2. **Run the tool.** The DJ opens the tool, which reads playlists and tracks straight from rekordbox's own local library database (no manual XML export or upload step), picks the playlist to prep, and chooses a set shape (for example, warm up, build, peak, cool down).
3. **Analyze.** For each track, the tool detects BPM, beat grid, musical key, phrase boundaries, and energy over time.
4. **Order.** The tool sequences the tracks so each neighbor pair is BPM-compatible and key-compatible, and the energy follows the chosen set shape.
5. **Tag.** For each transition, the tool places labeled cues: where to start mixing in, where to swap bass, where to apply a filter, and where the outgoing track should be gone.
6. **Review.** The DJ sees the ordered set and every cue in a simple preview screen, and can reorder tracks or nudge a cue before exporting.
7. **Write back to rekordbox.** The tool writes a new XML file with a new playlist and the cue points. The DJ imports it through rekordbox's XML view.

**Key design decision:** the tool can only analyze audio it can open, so the MVP works on local files (purchased or owned music). Streamed tracks (Spotify, Beatport, SoundCloud, TIDAL) play inside rekordbox under DRM, and their audio cannot be read by a third-party tool. DJs without local files start with the bundled practice catalog instead.

## System architecture

The tool is a Python companion app that reads a rekordbox export, runs a five-step pipeline, and writes results back to rekordbox.

&#91;embedded content: system architecture · 5 pipeline steps, 2 outputs\]

Place cues is the core of the product; every other step either feeds it or delivers its output. The app runs locally on the DJ's laptop, so music files never leave the machine.

## Audio analysis and set ordering

The analysis turns each audio file into a bar-by-bar map of the track, and the ordering step uses those maps to pick the smoothest sequence.

**Per-track analysis (Python, using librosa or Essentia)**

| Feature | Method | Used for |
| --- | --- | --- |
| BPM and beat grid | Beat tracking, then snap to a constant tempo (house is almost always fixed-tempo 4/4) | Ordering and cue timing |
| Downbeats and bars | Find beat 1 of each bar from low-frequency onsets | Every cue lands on a bar line |
| Phrases | Group bars into 8, 16, and 32 bar blocks, then confirm with structural change detection | Mix points land on phrase starts |
| Energy curve | Loudness (RMS) per bar, plus a separate low-frequency band for bass presence | Finding intro, breakdown, drop, and outro |
| Key | Chroma-based key estimate, converted to Camelot notation (for example 8A) | Harmonic compatibility |

**Section labels.** From the energy curve, each track gets labeled sections: intro (low bass, early), drop (big jump in bass energy), breakdown (bass drops out mid-track), and outro (energy falls off at the end). rekordbox has its own phrase analysis with similar labels, which is a useful benchmark for testing ours.

**Ordering.** Each pair of tracks gets a transition score:

- BPM: within about 6% scores well; half or double time is allowed
- Key: same Camelot number, one step away, or the relative major or minor scores well
- Energy: the score rises when the move matches the chosen set shape (for example, rising energy during the build)

With 10 to 30 tracks, a greedy pass (always pick the best next track) followed by a simple swap-improvement pass is fast and good enough. The DJ can lock a track in place, such as a fixed opener or closer, and the tool orders around it.

## Transition tagging in rekordbox

Every action gets its own cue name and color, so the DJ can read what to do straight off the waveform: green means mix in, orange means swap bass, red means get out.

rekordbox offers two kinds of cues, and the scheme uses both:

- **Memory cues** have no limit, carry a name, and show as markers on the waveform and in the cue list. They hold the instructions.
- **Hot cues** are limited to 8 (A to H) and map to the FLX4's performance pads. They hold the one or two points the DJ jumps to by hand.

**Cue legend**

| Action | Cue name | Color | Cue type | Where it goes |
| --- | --- | --- | --- | --- |
| Start the blend | MIX IN | Green | Hot cue A | Incoming track: first downbeat of the intro phrase |
| Begin leaving | MIX OUT | Red | Memory cue | Outgoing track: start of the outro phrase, lined up with the next track's MIX IN |
| Swap the bass | BASS SWAP | Orange | Memory cue, on both tracks | 16 bars into the overlap, on a phrase line: cut the outgoing low EQ, bring in the incoming |
| Filter out | FILTER | Blue | Memory cue | Outgoing track: 1 bar after its BASS SWAP, start sweeping the filter over 8 bars before the fade-out |
| Fully in | DROP | Violet | Memory cue | Incoming track: its first drop, where the outgoing track should be silent |
| Safety loop | LOOP 8 | Lemon | Memory loop (8 bars) | Outgoing track: the last 8 bars of the transition, to buy time if the blend needs longer |
| Alternate start | LATE IN | Turquoise | Memory cue | Incoming track: the phrase line where the full arrangement arrives, to skip a long intro |
| Alternate exit | EARLY OUT | Rose | Memory cue | Outgoing track: the phrase line where its first breakdown starts, to leave before the outro |
| Earlier way out | OUT -16 / -32 / -48 / ... | (app only) | Memory cue | Outgoing track: every 16 bars before MIX OUT, back to 32 bars after the track's own MIX IN, so a playing track never goes more than 16 bars without a way out |
| Hold back the drop | FAKE DROP | (app only) | Memory cue | Any track: the last bar of the build out of its first breakdown; loop it, cut the bass or echo out, then let the drop hit |

No two cues on a track share a spot (at least one bar apart). When two would collide, the higher-priority cue keeps the spot: actions (bass swap, filter, loop) move later a bar at a time, while markers (drop, alternates, fake drop) are left out rather than moved off the music they mark.

**How the pairs line up.** Cues are always placed in pairs across two tracks. If track 1's MIX OUT is at bar 97, track 2's MIX IN is at its bar 1, and the BASS SWAP sits 16 bars later on both. Because both land on phrase lines, the two tracks' phrases stay in step through the whole transition.

**Transition note in the Comments field.** The tool also writes a one-line summary into each track's Comments field, which shows as a column in rekordbox. Example: *Next: track 2, 8A to 9A, 124 to 125 BPM, blend at 4:05, bass swap at 4:36.*

**How it is encoded.** In the rekordbox XML, each cue is a POSITION\_MARK element with a Name, a Type (0 for a cue, 4 for a loop), a Start time in seconds, an End time (loops only), and a Num (-1 for a memory cue, 0 to 7 for hot cues A to H). Tracks live in COLLECTION (keyed by TrackID, with the tempo attribute named AverageBpm, not Tempo) and playlists live under PLAYLISTS/NODE (Type 0 = folder, 1 = playlist), each referencing its tracks by a Key that's either a TrackID or a file path depending on the node's KeyType.

**Verified against Pioneer's own XML format spec, Sept 30, 2026** (implementation in `set-prep-copilot/app/rekordbox_xml.py`, tests in `set-prep-copilot/tests/test_rekordbox_xml.py`):

- Pioneer's spec documents exactly five POSITION\_MARK attributes — Name, Type, Start, End, Num — and **no color attribute at all**. The only color the spec documents anywhere is TRACK's own whole-track Colour tag, using a fixed 8-value palette (Rose, Red, Orange, Lemon, Green, Turquoise, Blue, Violet). Separately, real-world rekordbox XML exports have been observed carrying Red/Green/Blue attributes on POSITION\_MARK in practice, using that same palette. The two sources agree on the palette, not on whether it's documented. Given that, the tool writes Red/Green/Blue on every cue (a parser ignores attributes it doesn't recognize, so this can't break import even if cue color truly isn't read) but makes no promise it renders on the desktop app or on CDJ hardware — that split (does color show at all, and does it survive to hardware) replaces the single open question below.
- Re-importing never touches a track's existing cues: the tool only appends new POSITION\_MARK elements from its own cue plan and otherwise copies every COLLECTION attribute through untouched. What's still unverified is rekordbox's own import-merge behavior on a track that already exists in the live library — whether it merges the new cues in cleanly or does something else. That's the day-1 test for the "XML import could overwrite a DJ's hand-set cues" risk below, not something achievable from the writer side alone.
- One more data point on the color question, from the live database rather than the XML side: `pyrekordbox`'s own `DjmdCue` table (rekordbox's internal cue model, separate from the XML import format) has both a `Color` column ("-1 if no color", per pyrekordbox's own docstring) and a separate `ColorTableIndex` column — confirming rekordbox's internal data model genuinely supports per-cue color as two distinct concepts. Checked all 35 real `DjmdCue` rows in this machine's own rekordbox library: every one has `Color = -1` and `ColorTableIndex = None` (none of Pioneer's bundled demo content has a manually-colored cue), so this doesn't show what a colored cue's values actually look like — it only confirms the fields exist and are live. Still doesn't answer whether the XML import's Red/Green/Blue attributes map onto either of these fields at all; that's a separate, still-open question from a different pathway (XML import vs. direct DB model), and still needs the same day-1 hardware test.

**Verified against pyrekordbox's real schema and a live rekordbox library, Sept 30, 2026** (implementation in `set-prep-copilot/app/rekordbox_db.py`; schema confirmed from pyrekordbox 0.4.4's installed source, then validated end-to-end against real data on this machine, not just unit tests):

- The manual "File > Export Collection in xml format" + upload step is gone. The tool now reads the DJ's playlists and tracks straight from rekordbox's own local database (pyrekordbox's `Rekordbox6Database`), read-only — it never calls `.add()`/`.commit()` on the database session, so it can't touch or corrupt the live library. This is a different, much lower-risk use of pyrekordbox than the direct-DB cue-*write* path this doc already researched and rejected for the MVP: reading is pyrekordbox's core, well-trodden use case, writing cues is the risky edge case that stays out of scope.
- Confirmed, not assumed: rekordbox stores BPM as an integer times 100. Verified against a known real track in this machine's own rekordbox library (rekordbox's own bundled "Demo Track 1"): the database's raw value `12800` converts to `128.0`, exactly matching that track's real, documented BPM.
- The database's FolderPath field is already a plain local filesystem path — unlike the XML format's Location attribute, no file:// URI decoding needed.
- Real upgrade over the old XML-export path: the database carries each track's ISRC directly (rekordbox extracts it from the file's own tags during its own analysis), which the XML export never did.
- pyrekordbox's own database handler only warns, never blocks, when rekordbox is running at the same time. Whether reading actually works smoothly against a real *running* rekordbox instance, not just what the source code says, is a new day-1 verification item, below.
- Consequence for the write side: `write_export` no longer clones a source XML document to build its output — there's no longer an uploaded file to clone. It now builds a minimal, self-contained XML from just the tracks being exported, with no record of the DJ's other existing playlists. Getting that new playlist and its cues folded correctly into the live library now depends entirely on rekordbox's own XML-import merge behavior. That was already the day-1 risk item above ("XML import could overwrite a DJ's hand-set cues") — this change makes it more load-bearing, not a new risk.
- End-to-end validation: the full pipeline (database read, then real librosa audio analysis, then BPM/key/energy scoring and ordering, then cue placement, then XML export) ran against real data — the two actual Demo Track MP3s in this machine's real rekordbox library, not synthetic test fixtures — and produced a valid, re-parseable XML with 8 correctly-encoded POSITION\_MARK cues.

## Risks and open questions

The biggest risk is that most student DJs play from streaming services, whose audio the tool cannot read; the bundled practice catalog gives them something to learn on until they own files.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| XML import could overwrite a DJ's hand-set cues | Lost work, lost trust — higher stakes now that exports are minimal, self-contained files (just the new playlist and its tracks) rather than a full clone of the DJ's library, so a clean merge on import depends entirely on rekordbox's own behavior | Always write to a new playlist, back up the rekordbox library first, and test on a spare library. |
| Our key or BPM detection is wrong | Bad ordering and misplaced cues | Benchmark against rekordbox's own values on 20 tracks before testing with users. |
| 3 weeks alongside classes | Scope slips | Hold the cue scheme and ordering as must-haves; the review screen can be a simple list. |

**Open questions**

- [ ] Does rekordbox 7 render POSITION_MARK's (undocumented) RGB attributes at all, and does that color survive onto CDJ hardware?
- [ ] Does re-importing XML for a track already in the library cleanly merge in new cues, or conflict with hand-set ones?
- [x] Does reading the rekordbox database work reliably while rekordbox itself is open and running? **Answered, Sept 30, 2026:** yes, confirmed empirically — launched the real rekordbox 7 app on this machine, then ran `rekordbox_db.list_playlists()`/`get_playlist_tracks()` against it three times in a row while it stayed open. Every read succeeded in well under half a second, no hang, no error, only pyrekordbox's own advisory log line ("Rekordbox is running!"). No longer a risk.
- [x] Desktop app or command-line tool for the MVP? **Answered:** neither — a local web app (FastAPI backend, browser UI), run on the DJ's own laptop. Chosen so other testers can run the same codebase themselves without a packaged installer, while still keeping audio analysis local (see `set-prep-copilot/`).
- [ ] How long does a 15-track set take to prep today (baseline from interviews)?

## 3-week milestones

Week 1 retires the biggest technical risks before any real building starts, so weeks 2 and 3 go to shipping and testing.

&#91;embedded content: 3-week plan · 3 phases, 3 gates\]

If the week 1 gate fails (cues do not import cleanly), the fallback is to write cues as a printed prep sheet per set.

## Future extension: Phrase Countdown Light

The light takes the set plan off the laptop screen and onto the booth: a small LED ring on the controller counts down to each cue the tool placed.

- **Hardware:** an ESP32 board and a ring of addressable LEDs, powered over USB
- **Input:** a small script on the laptop listens to the FLX4's MIDI messages (play and cue buttons) alongside rekordbox, and knows each track's BPM and cue times from the set plan
- **Output:** amber at 8 bars before a cue, cue color (green, orange, red) at the cue itself
- **Main risk:** the count drifts from the audio if the DJ nudges the tempo or jumps around a track, so the script needs to resync on every play or cue press

This extension adds a physical product to the story for hardware program management roles. It starts only after the MVP has real users.

## Extension: Move Coach animations

Move Coach teaches the transition, not just where it goes: at each cue, a popup shows a diagram of the FLX4 with an animated arrow on the exact control to move and which way.

**Why it matters:** the cue says *when* to swap bass, but a newer DJ may not know *how*. Showing the knob and the direction turns every prepped set into a lesson, which widens the audience from DJs who already know how to mix to people learning.

**User story**

*As a new DJ learning on my FLX4, I want to be shown which control to move, which way, and when, while I play my own set, so that I build the muscle memory for clean transitions without hiring a private coach.*

**Today:** Sofia, a sophomore, bought an FLX4 and wants to play her org's next party. She learns by watching tutorial videos, pausing, and trying to copy what she saw on her own controller. The video uses different songs, so the timing never matches her tracks. When a transition sounds off, she can't tell if she moved the wrong knob, turned it the wrong way, or moved it too late. The only way to get feedback in the moment is a paid private lesson.

**With Move Coach:** Sofia preps her real setlist, then practices it. Eight bars before each cue, the popup shows her controller with an arrow on the exact knob or fader and the direction to move it. When she makes the move, the tool confirms it through MIDI and moves on. Learning and practicing happen at the same time, on her own music.

**What changes for the user**

|  | Learning today | With Move Coach |
| --- | --- | --- |
| Material | Someone else's songs in a video | Her own setlist |
| Timing | Guessed from the video | Tied to the phrase in her track |
| Feedback | None, unless she pays for a lesson | Confirmed on every move |
| Cost | Free videos, or paid private coaching | Built into her prep tool |

The positioning: personal, real-time coaching that today mostly comes from a private instructor. No tool found so far watches the DJ's own controller and tells them which control to move, which way, timed to the phrases in their own tracks.

**Competitive landscape**

| Tool | What it does | Where Move Coach differs |
| --- | --- | --- |
| rekordbox tutorials | Explains what each control does and prompts the user to move it | Generic lessons, not tied to the user's own tracks or timing |
| Video lessons and apps like [DJ Transitions Academy](https://play.google.com/store/apps/details?id=com.dj.guide) | Structured courses, simulations, and quizzes | Learning is separate from playing a real set |
| [DJ.Studio](https://dj.studio/blog/self-paced-dj-learning-guide) | Timeline mix editor with EQ and filter automation per transition | Built for editing a mix offline, not coaching live on a controller |
| [Coach DJ Pro](https://coachdj.net/en/) | Set prep, a paid Live Assistant while mixing, and scoring of transitions after the mix, for rekordbox and Serato | Closest competitor, but its core is scoring the audio of a set after it's played. Move Coach coaches during the set, on the controller. Open question: what its Live Assistant add-on shows. |

The defensible claim is specific: animated, controller-level move prompts, timed to the user's own tracks and confirmed through MIDI. Checking Coach DJ Pro's free tier is a week 1 task.

**Cue to move mapping (Deck 1 outgoing, Deck 2 incoming)**

| Cue | Control on the FLX4 | Animation |
| --- | --- | --- |
| MIX IN | Deck 2 PLAY, then Deck 2 channel fader | Pulse on PLAY, then arrow sliding the fader up |
| BASS SWAP | LOW EQ knob on both channels | Deck 1 LOW turns left, Deck 2 LOW turns right, at the same time |
| FILTER | Deck 1 CFX knob | Slow turn to the right over 8 bars |
| MIX OUT | Deck 1 channel fader | Arrow sliding the fader down |
| LOOP 8 | Deck 1 loop control | Pulse on the button to tap |

&#91;embedded content: Move Coach popup sketch · bass swap\]

In the product, the two arrows animate in a loop until the DJ turns the knobs, and the popup clears once the MIDI messages confirm both moves.

**Two modes, built in order**

1. **Practice mode (first):** in the review screen, the DJ clicks any cue and watches its animation. No live timing needed, so it is low risk.
2. **Live mode (later):** the popup appears on the laptop 8 bars before each cue during a real set. This needs the same MIDI listener as the Phrase Countdown Light, so the two extensions share one timing engine.

**Bonus signal:** the FLX4 sends a MIDI message whenever a knob or fader moves, so the tool can confirm the DJ made the move and mark it done. That gives a learning metric: the share of cued moves completed on time.

**Design note:** the popup uses a simplified, generic drawing of a two-deck controller with the FLX4's control names, not a copy of Pioneer's hardware design or logos. A generic layout also makes it easy to support other controllers later.

**Scope:** this starts after the 3-week MVP. Practice mode is about one week of work: the diagram, five animations, and the cue click handler.

## Sources

- [Spotify: February 2026 Web API Dev Mode changes](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)
- [Spotify: Premium integrates with DJ software, including rekordbox](https://newsroom.spotify.com/2025-09-24/dj-software-integration-premium/)
- [Lexicon: Spotify in rekordbox, what works and what breaks](https://www.lexicondj.com/blog/spotify-in-rekordbox-what-works-what-breaks-and-what-to-do-before-your-gig)
- [pyrekordbox: rekordbox XML format (TRACK, TEMPO, POSITION\_MARK)](https://pyrekordbox.readthedocs.io/en/latest/formats/xml.html)
