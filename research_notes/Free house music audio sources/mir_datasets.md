# MIR / Academic Datasets with House & EDM Audio (for Set Prep Copilot catalog + analysis ground truth)

Research date: 2026-10-02. Method: primary sources (GitHub READMEs, Zenodo records, TISMIR/ISMIR/arXiv papers), plus **original counts computed this session** from the published metadata files of MTG-Jamendo (`data/raw_30s_cleantags_50artists.tsv`, `audio_licenses.txt`) and FMA (`fma_metadata/tracks.csv`, `genres.csv`). Computed numbers are labelled "(computed)".

Summary table (details and sources below):

| Dataset | House/EDM tracks with audio | Full vs clip | Audio license | Annotations | Best use |
|---|---|---|---|---|---|
| MTG-Jamendo | 16,480 "electronic"; 2,169 house; 427 deephouse; 2,179 techno (4,215 house/deephouse/techno union) (computed) | Full tracks, 320 kbps MP3 | Per-track CC (mostly NC); dataset "solely for non-commercial research" | Tags only (no BPM/key/beats) | Catalog candidate (filter to CC BY / BY-SA) + unlabeled test audio |
| FMA full | 34,413 Electronic; 1,482 House; 2,140 Techno (computed/official) | fma_full untrimmed (879 GiB); fma_large 30 s clips | Per-track artist license; ~88% of Electronic is NC (computed) | Genre, metadata; no BPM/key/beats | Catalog candidate (filter to CC BY/BY-SA/CC0) |
| GiantSteps Tempo | 664 | 2-min Beatport previews (fetched via script) | Beatport previews; no clear redistribution license | Tempo (v2 corrected), genre | Internal BPM benchmark |
| Beatport EDM Key (GiantSteps MTG Key) | 1,486 | 2-min excerpts, included on Zenodo | Zenodo record says CC BY-SA 4.0 (questionable for commercial preview audio) | Global key + confidence | Internal key benchmark |
| UnmixDB | Synthetic mixes from 10 Mixotic CC mixes | ~20 s excerpts | Dataset CC BY-NC-ND 4.0 (Zenodo) | Cue points, BPM, speed factors, beats, mix GT | Internal DJ-mix/transition benchmark |
| Raveform (2026) | 1,423 annotated tracks (56,873 tracks referenced, 4,902 mixes) | No audio (links) | Annotations CC BY 4.0 | Tempo, beats, downbeats, EDM functional segments | Best EDM beat/downbeat/structure GT if you can source audio |
| EDM-CUE / CUE-DETR | ~4,710 tracks, 21k cue points | No audio | CC BY 4.0 (paper) vs MIT (repo) — conflict | Cue points | Cue-point GT (DnB-heavy) |
| EDM-98 (2026) | 98 | No audio stated | CC BY-NC-ND 4.0 | Intro/Build-up/Drop/Breakdown/Outro | Small structure/drop GT |
| djmix (Kim et al.) | 1,557 mixes / 13,728 tracks (2020 paper) | YouTube download via `pip install djmix` | Not stated | Mix-track alignment, boundaries, cue points | Internal research only |
| Harmonix Set | Pop-focused, 912 tracks | No audio (YouTube URLs + mel specs) | Repo MIT | Beats, downbeats, segments | Beat/downbeat algorithm sanity check (not EDM) |

---

## Q1: How many house/EDM tracks with audio, and full-length vs 30 s clips?

### Takeaway
Only two datasets give you thousands of *full-length*, redistributable house/techno audio files: MTG-Jamendo (~2.2k house, ~2.2k techno, 16.5k electronic, all full tracks) and FMA full (~1.5k house, ~2.1k techno, 34k electronic, untrimmed). The EDM-specific annotated benchmarks are small (hundreds to ~1.5k) and either 2-minute previews (GiantSteps/Beatport) or ship no audio at all (Raveform, EDM-CUE, Harmonix, djmix).

### Cited Findings
**MTG-Jamendo**
- 55,000+ full audio tracks (55,525 in final splits), 320 kbps MP3 plus low-bitrate mono option; 195 tags (87 genre); full audio ~508 GB — [MTG-Jamendo GitHub](https://github.com/MTG/mtg-jamendo-dataset)
- (computed) Tag counts from the repo's `stats/raw_30s_cleantags_50artists/genre.tsv`: electronic 16,480 tracks (1,546 artists); house 2,169 (327 artists); techno 2,179; deephouse 427; trance 1,528; dance 2,827; minimal 629; club 579; drumnbass 501; dubstep 547; breakbeat 382; edm 281; idm 287; downtempo 1,431; chillout 3,678 — [stats file](https://github.com/MTG/mtg-jamendo-dataset/blob/master/stats/raw_30s_cleantags_50artists/genre.tsv)
- (computed) Mean duration: house tracks 4.55 min, deephouse 5.24 min, techno 4.85 min, electronic 4.48 min — i.e., full-length tracks, from `DURATION` column in [raw_30s_cleantags_50artists.tsv](https://github.com/MTG/mtg-jamendo-dataset/blob/master/data/raw_30s_cleantags_50artists.tsv)
- (computed) Union of house/deephouse/techno = 4,215 tracks — same file.

**FMA (Free Music Archive dataset)**
- Subsets: small 8,000 tracks/30 s/7.2 GiB; medium 25,000/30 s/22 GiB; large 106,574/30 s/93 GiB; full 106,574/untrimmed/879 GiB; hosted at os.unil.cloud.switch.ch/fma/ — [FMA GitHub](https://github.com/mdeff/fma)
- 161 genres (16 roots); Electronic = 34,413 tracks; whole dataset 917 GiB / 343 days of CC audio from 106,574 tracks, 16,341 artists — [FMA ISMIR 2017 paper](https://archives.ismir.net/ismir2017/paper/000075.pdf)
- (computed from `genres.csv`) Electronic 34,413; Ambient Electronic 5,723; Techno 2,140; House 1,482; Dance 1,414; Dubstep 1,144; Minimal Electronic 1,013; Drum & Bass 500 — [fma_metadata.zip](https://os.unil.cloud.switch.ch/fma/fma_metadata.zip)
- (computed) Median duration: House 4.19 min, Techno 4.72 min, Electronic 3.92 min (fma_full is untrimmed; fma_large is 30 s clips of the same tracks) — same file.

**GiantSteps Tempo**
- 664 Beatport audio previews, most 120 s long (six are 62–119 s); downloaded via bash script from `geo-samples.beatport.com/lofi/` URLs; MP3 — [GiantSteps Tempo GitHub](https://github.com/GiantSteps/giantsteps-tempo-dataset)

**Beatport EDM Key Dataset (a.k.a. GiantSteps MTG Key)**
- 1,486 two-minute audio excerpts, audio included (audio.zip ~2.1 GB) — [Zenodo 1101082](https://zenodo.org/records/1101082)

**UnmixDB**
- Built from CC tracks of 10 free Mixotic mixes; ~20 s excerpts from track starts/ends; each 3-track playlist mixed 12 times (4 effect variants x 3 time-scaling variants via sox); ~4.2 GB in six archives — [Zenodo 1422385](https://zenodo.org/records/1422385)
- Source track curation by Sonnleitner et al. (ISMIR 2016): 10 DJ mixes, 118 tracks — cited in [Raveform, TISMIR](https://transactions.ismir.net/articles/10.5334/tismir.288)

**Raveform (Kim, Kim, Kim, Nam, TISMIR 2026)**
- 4,902 DJ mixes, 56,873 unique tracks, 1,423 tracks with structural annotations; genres: techno (dominant), trance, DnB, house, tech house, progressive house; audio NOT included (MixesDB/YouTube links) — [TISMIR article](https://transactions.ismir.net/articles/10.5334/tismir.288); site [mir-aidj.github.io/raveform](https://mir-aidj.github.io/raveform/)

**djmix dataset (Kim et al.)**
- ISMIR 2020 study: 1,557 real-world DJ mixes with 13,728 tracks from 1001Tracklists — [ISMIR 2020 paper](https://archives.ismir.net/ismir2020/paper/000352.pdf)
- Released package downloads audio from YouTube IDs (`pip install djmix`; `dj.tracks[...].download()`); introduced with DAFx 2022 fader/EQ estimation paper — [djmix-dataset GitHub](https://github.com/mir-aidj/djmix-dataset)
- Raveform describes Kim et al. (2020) as "1.5k DJ mixes, 15k tracks (not publicly available)" — [TISMIR](https://transactions.ismir.net/articles/10.5334/tismir.288) (note: partial conflict with the public djmix package, which exposes metadata + YouTube links but not audio files)

**EDM-CUE / CUE-DETR (Argüello et al., ISMIR 2024)**
- 4,710 tracks, ~21k cue points (avg 4.6/track) from 4 professional DJs — [arXiv 2407.06823](https://arxiv.org/pdf/2407.06823)
- "No audio provided, only references"; tracks identified by title/artist/duration; hosted on Hugging Face `disco-eth/edm-cue` — [cue-detr GitHub](https://github.com/ETH-DISCO/cue-detr)
- EDM-CUE is heavily skewed to Drum & Bass/Jungle (90.5% of tracks) — [EDMFormer arXiv 2603.08759](https://arxiv.org/html/2603.08759)

**EDM-98 (EDMFormer, 2026)**
- 98 professionally annotated EDM tracks sampled from EDM-CUE; tempo mean 137.3 BPM (100–175) — [EDMFormer arXiv](https://arxiv.org/html/2603.08759)

**Harmonix Set**
- 912 Western pop tracks; audio not distributed — mel spectrograms (~1.2 GB) + YouTube URLs with DTW alignment scores — [Harmonix GitHub](https://github.com/urinieto/harmonixset)

### Inferences
- For a beginner house-mixing catalog, MTG-Jamendo is the richest *full-length* source (house + deephouse + techno ≈ 4.2k tracks, avg 4.5–5 min, typical DJ-friendly lengths). FMA adds ~3.4k house/techno tracks.
- 30 s clips (fma_large, MusicCaps) and 2-min previews (GiantSteps/Beatport) are too short to teach intros/outros/phrase mixing; use them only for BPM/key validation.
- Genre tags on Jamendo/FMA are artist-supplied; expect some "house" tracks that aren't 4/4 club house — a BPM (118–130) + beat-strength filter will be needed.

### Gaps
- Exact house/techno counts in the *full* MTG-Jamendo `raw.meta` (vs the cleaned 50-artist split used above) were not computed.
- I did not verify current reachability of Beatport `geo-samples` preview URLs (GiantSteps Tempo/Key audio scripts); historically some links have broken.
- Not verified this session (from prior knowledge only — confirm before relying): GiantSteps Key = 604 two-minute Beatport previews; Ballroom = 698 ~30 s ballroom-dance clips; SMC = 217 ~40 s excerpts (both non-EDM); MedleyDB = ~196 multitracks with few electronic tracks; Song Describer = ~1.1k captions over ~706 MTG-Jamendo recordings; MusicCaps = ~5.5k 10 s YouTube clips (IDs only).

---

## Q2: License of the audio — commercial product / streaming to users / research-only?

### Takeaway
Dataset-level terms and per-track audio licenses differ and must be checked separately. MTG-Jamendo's dataset is explicitly non-commercial research only (commercial use needs Jamendo permission), even though ~25% of its house/techno tracks carry commercial-friendly CC BY/BY-SA licenses individually. FMA audio carries each artist's license; only ~13% of its house/techno tracks permit commercial use. Beatport-derived audio is commercial preview audio of uncertain redistribution status. Annotation-only datasets (Raveform CC BY 4.0, EDM-CUE) are commercially usable as metadata but bring no audio.

### Cited Findings
- MTG-Jamendo metadata license: CC BY-NC-SA 4.0; audio under per-track CC licenses listed in `audio_licenses.txt`; dataset "made available solely for non-commercial research and academic use"; commercial use requires authorization from Jamendo S.A. (hello@jamendo.com) — [MTG-Jamendo GitHub](https://github.com/MTG/mtg-jamendo-dataset)
- (computed) MTG-Jamendo whole `audio_licenses.txt` license-URL counts: BY-NC-SA 21,399; BY-NC-ND 15,584; BY-SA 9,933; BY-ND 3,303; BY 3,122; BY-NC 2,274 — [audio_licenses.txt](https://github.com/MTG/mtg-jamendo-dataset/blob/master/audio_licenses.txt)
- (computed) MTG-Jamendo **house** (2,169): BY-NC-SA 593, BY-NC-ND 582, BY-SA 359, BY-ND 225, BY-NC 232, BY 177 → 536 tracks (BY + BY-SA) allow commercial use and derivatives (mixing) — same files
- (computed) MTG-Jamendo **deephouse** (427): BY-NC-ND 241, BY-NC-SA 51, BY-SA 45, BY 44, BY-ND 43, BY-NC 3 → 89 BY/BY-SA
- (computed) MTG-Jamendo **techno** (2,179): BY-NC-SA 739, BY-NC-ND 577, BY-SA 494, BY 188, BY-ND 134, BY-NC 46 → 682 BY/BY-SA
- (computed) house ∪ deephouse ∪ techno (4,215): BY-SA 824 + BY 318 = 1,142 commercial + derivative-friendly; BY-NC-SA 1,253; BY-NC-ND 1,198; BY-ND 358; BY-NC 262
- (computed) MTG-Jamendo electronic (16,480): BY-NC-SA 6,933; BY-NC-ND 4,382; BY-SA 3,032; BY 880; BY-ND 692; BY-NC 493
- FMA: code MIT; metadata CC BY 4.0; audio "distributed under the license chosen by the artist" — [FMA GitHub](https://github.com/mdeff/fma)
- (computed from `tracks.csv` `license` field) FMA all 106,574: NC 51,825; NC+ND 41,869; commercial-OK 9,762; PD/CC0 1,820; commercial-OK+ND 962 — [fma_metadata.zip](https://os.unil.cloud.switch.ch/fma/fma_metadata.zip)
- (computed) FMA Electronic 34,413: NC 18,103; NC+ND 11,952; commercial-OK (BY/BY-SA) 3,644; BY-ND 494; PD/CC0 141
- (computed) FMA House ∪ Techno 3,366: NC 1,875; NC+ND 1,030; commercial-OK 435; BY-ND 20; 0 CC0
- Beatport EDM Key Dataset Zenodo record lists the audio & dataset as CC BY-SA 4.0 — [Zenodo 1101082](https://zenodo.org/records/1101082)
- UnmixDB dataset license on Zenodo: CC BY-NC-ND 4.0 (source tracks described as CC-licensed and freely redistributable) — [Zenodo 1422385](https://zenodo.org/records/1422385); a search snippet / secondary listing described it as CC BY 4.0 — conflict, Zenodo record is authoritative.
- Raveform annotations: CC BY 4.0; no audio — [TISMIR](https://transactions.ismir.net/articles/10.5334/tismir.288)
- EDM-CUE: paper states CC BY 4.0 — [arXiv 2407.06823](https://arxiv.org/pdf/2407.06823); GitHub repo indicates MIT — [cue-detr GitHub](https://github.com/ETH-DISCO/cue-detr) (conflict; either is permissive, but no audio)
- EDM-98: CC BY-NC-ND 4.0 — [EDMFormer arXiv](https://arxiv.org/html/2603.08759)
- Harmonix Set repo: MIT (annotations); audio via third-party YouTube URLs — [Harmonix GitHub](https://github.com/urinieto/harmonixset)
- Spotify killed audio_features, audio_analysis, recommendations etc. for new apps on 2024-11-27 (403 errors); only apps with prior extended quota retain access — [TechCrunch](https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/); [Spotify Community thread](https://community.spotify.com/t5/Spotify-for-Developers/Web-API-Get-Track-s-Audio-Features-403-error/td-p/6654507)

### Inferences
- **Commercial product, streaming to users:** the safest path is to go back to the *original platform* (Jamendo / FMA track pages) for the subset of tracks licensed CC BY or CC BY-SA (and CC0), with attribution, rather than redistributing "the MTG-Jamendo dataset" (whose wrapper is NC research-only). Roughly 1,142 house/deephouse/techno tracks on Jamendo and ~435 house/techno on FMA fit this. Jamendo also sells commercial licensing (Jamendo Licensing), which is the route for NC tracks.
- **Non-commercial / free educational tool:** NC and NC-SA tracks become usable (with attribution); still avoid ND tracks if the app produces/records mixes (a DJ mix is arguably a derivative/adaptation — ND forbids sharing it). This is a legal judgment, not settled by sources here.
- CC BY-SA on mixes means user-exported mixes would need to be shared under BY-SA.
- The CC BY-SA label on Beatport EDM Key audio is doubtful: the excerpts are Beatport commercial previews of label-owned tracks; a CC license from researchers likely cannot grant rights they don't hold. Treat as research-only internal test data.
- Spotify deprecation means BPM/key ground truth must come from the tool's own analysis (Essentia/librosa/madmom) validated against these datasets, or from GetSongBPM-style APIs.

### Gaps
- Did not verify whether all FMA track pages / Jamendo pages still serve downloads in 2026, nor current Jamendo Licensing pricing.
- Did not find any legal opinion on whether CC-ND prohibits use in a DJ-practice app that mixes but does not export.
- MusicCaps (CC BY-SA 4.0 captions, YouTube audio) and Song Describer licenses not verified this session.

---

## Q3: What annotations exist (BPM, key, beats, downbeats, segments, cue points, transitions)?

### Takeaway
No single dataset has full-length CC house audio *and* dense annotations. Annotation coverage for EDM: tempo (GiantSteps Tempo), key (Beatport EDM Key, GiantSteps Key), beats/downbeats/functional structure (Raveform — best, 2026), cue points (EDM-CUE, UnmixDB), transitions/mix alignment (UnmixDB synthetic, djmix real), drops/build-ups (Raveform, EDM-98). MTG-Jamendo and FMA have only genre/mood tags.

### Cited Findings
- GiantSteps Tempo: tempo + genre, in GiantSteps, JAMS and MIREX formats; v2 annotations corrected by Schreiber & Müller (2018); 3 files with no tempo (0.0) — [GiantSteps Tempo GitHub](https://github.com/GiantSteps/giantsteps-tempo-dataset)
- Beatport EDM Key: single global key per excerpt with comments and confidence, annotated by Eduard Mas Marín, revised by Ángel Faraldo; purpose: key estimation in EDM subgenres — [Zenodo 1101082](https://zenodo.org/records/1101082)
- UnmixDB: ground-truth labels (start, end, label), BPM, speed factors, cue points, beat-tracking .beat.xml — [Zenodo 1422385](https://zenodo.org/records/1422385)
- Raveform: tempo, beats, downbeats, and functional segments with EDM vocabulary (Intro, Buildup, Drop, Breakdown, Cooldown, Outro, Bridge, Ambient-Intro, Ambient-Outro) for 1,423 tracks — [TISMIR](https://transactions.ismir.net/articles/10.5334/tismir.288)
- EDM-CUE: ~21k cue points (seconds) for ~4.7k tracks — [arXiv 2407.06823](https://arxiv.org/pdf/2407.06823), [cue-detr GitHub](https://github.com/ETH-DISCO/cue-detr)
- EDM-98: Intro, Build-up, Drop, Breakdown, Outro, Silence, End; ±0.5 s precision — [EDMFormer arXiv](https://arxiv.org/html/2603.08759)
- djmix (2020 study): track lists, boundary timestamps, genre per mix; DTW mix-to-track alignment to derive cue points and effects usage — [ISMIR 2020 paper](https://archives.ismir.net/ismir2020/paper/000352.pdf)
- Harmonix Set: beats (with bar position, bar number), downbeats, functional segments, BPM, time signature, MusicBrainz IDs — [Harmonix GitHub](https://github.com/urinieto/harmonixset)
- SALAMI has "minimal EDM representation" and pop-centric taxonomies — [EDMFormer arXiv](https://arxiv.org/html/2603.08759)

### Inferences
- For validating the app's BPM detector: GiantSteps Tempo v2 (EDM, 664) is the standard benchmark. Key detector: Beatport EDM Key (1,486) + GiantSteps Key. Beat grid/downbeat/phrase (8/16/32-bar) and drop detection: Raveform is the closest match to house/techno phrasing, but audio must be sourced by the user from links.
- A practical internal benchmark: hand-annotate ~50–100 CC BY/BY-SA Jamendo house tracks (BPM, key, downbeat, phrase boundaries) — this is redistributable and matches the catalog domain; no existing dataset does this.

### Gaps
- Didn't confirm whether Raveform track links include any CC-licensed (e.g., Jamendo/Bandcamp-free) tracks.
- Drop-detection datasets from SoundCloud (Yadati et al., ~2014) not researched/verified this session.

---

## Q4: How to download (Zenodo, GitHub, size), audio format

### Takeaway
MTG-Jamendo (~508 GB full, MP3 320k, Python download script) and FMA (zip archives, 93 GiB for 30 s clips, 879 GiB full, MP3) are large; subset by tag/license via metadata first. Benchmark sets are small (Beatport Key audio.zip ~2.1 GB on Zenodo; UnmixDB ~4.2 GB on Zenodo; GiantSteps Tempo via script). Several key datasets have mirdata loaders.

### Cited Findings
- MTG-Jamendo: `scripts/download/download.py` with options for audio quality, mel-spectrograms, or features; ~508 GB full audio; MP3 320 kbps or low-bitrate mono — [MTG-Jamendo GitHub](https://github.com/MTG/mtg-jamendo-dataset)
- FMA: archives at `os.unil.cloud.switch.ch/fma/` (fma_metadata.zip ~342 MB — downloaded successfully this session, 358,412,441 bytes; use Python `zipfile` as macOS `unzip` failed to extract members) — [FMA GitHub](https://github.com/mdeff/fma)
- GiantSteps Tempo: bash download script from Beatport preview URLs; MP3, optional WAV conversion with SoX — [GiantSteps Tempo GitHub](https://github.com/GiantSteps/giantsteps-tempo-dataset)
- Beatport EDM Key: Zenodo with audio.zip (~2.1 GB), keys.zip, xlsx metadata; the record also listed a "4.1 TB" total, which conflicts with the 2.1 GB audio file and is likely a page/extraction error — [Zenodo 1101082](https://zenodo.org/records/1101082)
- UnmixDB: Zenodo, six archives ~4.2 GB total; generation scripts at [Ircam-RnD/unmixdb-creation](https://github.com/Ircam-RnD/unmixdb-creation) — [Zenodo 1422385](https://zenodo.org/records/1422385)
- djmix: `pip install djmix` (needs FFmpeg), YouTube-based audio download, `djmix-dataset.json` metadata — [djmix-dataset GitHub](https://github.com/mir-aidj/djmix-dataset)
- EDM-CUE: Hugging Face `disco-eth/edm-cue` — [cue-detr GitHub](https://github.com/ETH-DISCO/cue-detr)
- Raveform: [mir-aidj.github.io/raveform](https://mir-aidj.github.io/raveform/)
- Harmonix: mel spectrograms ~1.2 GB from Dropbox; YouTube URLs — [Harmonix GitHub](https://github.com/urinieto/harmonixset)

### Inferences
- Don't download fma_full or all of MTG-Jamendo; filter `raw_30s_cleantags_50artists.tsv` (Jamendo) or `tracks.csv` (FMA) by genre + license, then fetch individual files (Jamendo track IDs map to jamendo.com/track/{id}).
- mirdata likely offers loaders for giantsteps_tempo, giantsteps_key, beatport_key, harmonix, mtg_jamendo_autotagging_moodtheme, fma? — not verified.

### Gaps
- mirdata loader list not fetched this session.
- AcousticBrainz (features only, project ended ~2022, data dumps) and Million Song Dataset (features/metadata only, no audio) not re-verified this session; both lack audio and are irrelevant as a catalog.

---

## Q5: Suitability — (a) user-facing practice catalog vs (b) internal test/benchmark set

### Takeaway
(a) Catalog: only MTG-Jamendo and FMA qualify, and only via the CC BY / BY-SA (/CC0) subset sourced from the original platforms with attribution (~1.1k Jamendo + ~0.4k FMA house/techno tracks) for a commercial product; NC tracks are fine only if the tool is non-commercial (and avoid ND if mixes are exported). (b) Benchmarks: GiantSteps Tempo (BPM), Beatport EDM Key + GiantSteps Key (key), Raveform (beats/downbeats/structure/drops), EDM-CUE (cue points, DnB-biased), UnmixDB (transitions); Harmonix/Ballroom/SMC only as generic, non-EDM beat-tracking sanity checks.

### Cited Findings
- MTG-Jamendo is full-length, CC-licensed but wrapper is non-commercial research only — [MTG-Jamendo GitHub](https://github.com/MTG/mtg-jamendo-dataset)
- FMA audio carries artist-chosen licenses — [FMA GitHub](https://github.com/mdeff/fma)
- Raveform has no audio; users obtain via links — [TISMIR](https://transactions.ismir.net/articles/10.5334/tismir.288)
- EDM-CUE 90.5% DnB/Jungle — [EDMFormer arXiv](https://arxiv.org/html/2603.08759)
- Harmonix is pop-focused, audio via YouTube — [Harmonix GitHub](https://github.com/urinieto/harmonixset)
- Spotify audio features unavailable to new apps since 2024-11-27 — [TechCrunch](https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/)

### Inferences
- Ranking for catalog: 1) Jamendo CC BY/BY-SA house+deephouse+techno (full-length, 320 kbps, ~1.1k tracks); 2) FMA BY/BY-SA/CC0 house+techno (~435); 3) everything else unsuitable (clips, previews, no audio, or NC-ND dataset licenses).
- Ranking for benchmarking: BPM → GiantSteps Tempo v2; key → Beatport EDM Key; downbeat/phrase/drop → Raveform (+EDM-98); cue points → EDM-CUE; transitions → UnmixDB. All internal-only (research/NC or no-audio), never shipped to users.
- UnmixDB's NC-ND license and 20 s excerpts make it test-only.
- Mixotic.net CC DJ mixes (source for UnmixDB/Sonnleitner set, 10 mixes/118 tracks) could serve as "example mixes" for teaching if the individual mix licenses permit — not verified.

### Gaps
- No source found for a ready-made, CC-BY-licensed, full-length house dataset with BPM/key/downbeat annotations — appears not to exist (absence of evidence from this search, not proof).
- Mixotic.net current availability and per-mix license terms not checked.
- Song Describer / MusicCaps / MedleyDB / Ballroom / SMC details not verified this session (see Q1 Gaps); all are low relevance (non-EDM, short clips, or no audio).
