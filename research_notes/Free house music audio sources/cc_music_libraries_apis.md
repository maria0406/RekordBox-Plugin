# CC / Royalty-Free Music Libraries and APIs for House/EDM (status as of Oct 2026)

Scope: sources of downloadable, openly licensed house / deep house / tech house / techno / EDM audio for a DJ "set prep" learning tool that analyzes audio (BPM, key, beat grid, phrase, energy) and lets users practice mixing.

Method note: Research done 2026-10-02 with web search/fetch plus live API probes (Internet Archive advancedsearch, Openverse API, Audius API, Jamendo API). Uppbeat FAQ returned HTTP 429 and Mixkit's license page did not render its text, so those two are unverified. Some services on the candidate list (Incompetech, Chosic, YouTube Audio Library, Bandcamp, Freesound limits) were not fetched before the tool-call budget ran out. They are listed under Gaps with what I know from training data, marked unverified.

---

## Q1: Volume of house/techno/EDM tracks, and are they full-length and DJ-friendly?

### Takeaway
The deepest pools of full-length, 4/4, club-style tracks with redistributable licenses are the **Internet Archive netlabels collection**: about 77k audio releases, of which about 2.9k are tagged house, about 6.2k techno and about 3.9k minimal. Next comes **Jamendo**, with about 645k tracks overall and a "deephouse" genre tag. Audius has plenty of DJ-style house, with BPM and key metadata, but most of it is "All rights reserved". Pixabay, Mixkit, Uppbeat and NCS lean toward background music or EDM-pop, not DJ tools.

### Cited Findings
- **Internet Archive netlabels (live query, 2026-10-02):** `collection:netlabels AND mediatype:audio` gives **77,019 items**. The subject tags give these counts: `house` 2,872; `techno` 6,216; `minimal` 3,862; `"deep house" OR "tech house"` 745. NOTE: each item is a *release* (EP/album), not a single track, so the track counts are several times higher. Subject tags are free text, so these counts are approximate and miss untagged releases. — [IA advancedsearch API](https://archive.org/advancedsearch.php)
- The IA netlabels collection holds "complete, freely downloadable and streamable catalogs of virtual record labels", described as non-profit, community-built and dedicated to "non-commercial, freely distributable music". Its RSS shows deep minimal techno, acid house and psychedelic techno releases. — [IA netlabels RSS](https://archive.org/services/collection-rss.php?mediatype=audio&collection=netlabels); [audio-file.org overview](https://audio-file.org/2021/12/31/netlabels-internet-archive-virtual-record-labels/)
- A list of active and inactive netlabels exists in JSON form, which helps when seeding curated label lists. — [timpulver/netlabel-list](https://github.com/timpulver/netlabel-list)
- **Jamendo:** Openverse indexes **644,709 Jamendo items**, all genres. — [Openverse sources](https://openverse.org/sources). A live Openverse query for "deep house" returned a Jamendo track (275 s long) tagged `genres: ['dance','deephouse']`, and a "techno" query returned a 313 s Jamendo track. Jamendo electronic tracks are typically full-length (4–6 min), but I could not get an exact house count. — [Openverse API](https://api.openverse.org/v1/audio/)
- **Audius:** a search for "deep house" returned DJ sets (64–84 min) and full tracks tagged with genres such as "Progressive House" and "Deep House". The first results were long mixes, not single tracks. — [Audius API](https://api.audius.co/v1)
- **Openverse** indexes audio from Jamendo, Freesound and Wikimedia Commons. The 3,958,146 count for Wikimedia Commons on the sources page appears to cover all media, not only audio; that reading is unverified. — [Openverse sources](https://openverse.org/sources). Openverse passed 1M audio records in Nov 2022. — [Make WordPress Openverse](https://make.wordpress.org/openverse/2022/11/16/openverse-now-includes-over-1-million-audio-records/)
- **Freesound:** 591,448 items are indexed in Openverse. — [Openverse sources](https://openverse.org/sources). A live "tech house" query returned a 7.6 s Freesound clip, which shows that Freesound is loops and one-shots, not full tracks. — [Openverse API](https://api.openverse.org/v1/audio/)
- **Pixabay** has "thousands of royalty-free songs" plus 70,000+ sound effects. — [Pixabay FAQ](https://pixabay.com/service/faq/) (via search snippet)
- **NCS** is mainly EDM / future bass / dubstep / pop-EDM aimed at creators on YouTube and Twitch. — [NCS usage policy](https://ncs.io/usage-policy)

### Inferences
- For phrase/structure teaching, IA netlabels and Jamendo are the best match. They hold real club tracks with DJ intros and outros, from labels that explicitly release minimal, deep and tech house.
- Audius has the most "modern" DJ-oriented catalog, but you must filter by license and downloadability, and very few tracks pass both filters (see Q2).
- Pixabay, Mixkit and Uppbeat tracks are mostly produced as video background beds of 1–3 min, often without 16/32-bar DJ intros. That makes them weaker for teaching beatmatching across long blends. This is my assessment and was not measured.

### Gaps
- Exact Jamendo counts per tag (house / deephouse / techhouse / techno). The Jamendo API needs a registered client_id, and the public demo id I tried returned "Application Suspended". With your own key, use `tracks/?tags=deephouse&fullcount=true`.
- Exact Pixabay house/EDM track count and typical durations. I did not query them.
- An Audius count of CC-licensed and downloadable house tracks. I did not page through results.
- FMA electronic/house counts after the rebuild. The FMA research dataset (mdeff/fma, 106k tracks, 2017 snapshot) exists, but its current relevance and licensing are not verified. — [mdeff/fma](https://github.com/mdeff/fma)
- I did not research ccMixter's house content. My training knowledge says it is mostly downtempo, hip-hop and remix stems, with little club house (unverified).

---

## Q2: Licenses — commercial use, in-app streaming/redistribution, caching, derivatives (mixing), automated analysis, attribution

### Takeaway
CC-BY and CC-BY-SA content, which comes from IA netlabels, Jamendo, some ccMixter and Openverse, is the only category that clearly allows in-app redistribution, derivatives and commercial use. Most netlabel content is CC BY-NC, so it is fine if the app is non-commercial. Platform terms add restrictions on top of the CC licenses: the Jamendo API is non-commercial unless licensed and bans offline caching apps; the SoundCloud API forbids storing files and any AI/ML use; NCS, Pixabay, Mixkit and Uppbeat licenses target video creators, not redistribution in apps.

### Cited Findings
- **IA netlabels licenses (live query):** 49,881 of the 77,019 netlabel items have a `licenseurl` containing `by-nc`, which is about 65% non-commercial. The sample release `yarn014` is CC BY 4.0. — [IA advancedsearch](https://archive.org/advancedsearch.php); [archive.org/metadata/yarn014](https://archive.org/metadata/yarn014)
- **Jamendo** tracks are under CC licenses chosen per track. The API offers filters `ccnc`, `ccnd` and `ccsa` to restrict results by NC, ND and SA. — [Jamendo API tracks docs](https://developer.jamendo.com/v3.0/tracks). Openverse samples showed Jamendo tracks under `by-nc-nd 3.0`, `by-sa 3.0` and `by 3.0`. — [Openverse API](https://api.openverse.org/v1/audio/)
- **Jamendo API terms:** "may be used freely for non-commercial uses". Commercial use is defined as "any use that is intended for or directed toward commercial advantage or any monetary compensation, including any revenue arising from affiliation programs or advertising", and needs a quote from licensing@jamendo.com. — [Jamendo API Terms of Use](https://devportal.jamendo.com/api_terms_of_use)
- **Jamendo caching:** "Applications must not be specifically designed to cache the content nor offering an offline access to the content. Caching system may only be used to the extent reasonably necessary for the operation of the Application." — [Jamendo API ToU](https://devportal.jamendo.com/api_terms_of_use)
- **Jamendo attribution:** apps must credit the members as creators, credit JAMENDO as the provider, and "provide a direct backlink from each Content in the Application to the relevant Content's page". The terms do not mention AI/ML. — [Jamendo API ToU](https://devportal.jamendo.com/api_terms_of_use)
- **SoundCloud API terms:** apps cannot include a file-save function. Only session caching "reasonably necessary" is allowed, and offline access is prohibited. It is forbidden to "Copy or reproduce any User Content for the purposes of informing, training, developing (or as input to) artificial intelligence or machine intelligence technologies", including digital fingerprints. Modification is allowed only where the uploader consents, for example through a CC license that permits derivatives. Attribution must include the creator, SoundCloud and a visible backlink. — [SoundCloud API Terms of Use](https://developers.soundcloud.com/docs/api/terms-of-use)
- SoundCloud public API policy: "downloading or storing of any content on SoundCloud is not allowed". — [SoundCloud help: Public APIs](https://help.soundcloud.com/hc/en-us/articles/115003446727-SoundCloud-Public-APIs) (via search snippet)
- **Audius:** tracks are API-accessible by default unless the artist opts out ("Disallow Streaming via the API"). Since a July 8, 2025 ToS update, third-party use through the API is governed by the custom **Open Music License (OML)** plus separate API Terms. The blog post does not spell out what the OML permits, such as caching, derivatives or commercial use. — [Audius blog, ToS update](https://blog.audius.co/posts/audius-terms-of-service-update); [Audius ToU PDF, Oct 5 2025](https://audius.co/documents/TermsOfUse.pdf)
- Live Audius results showed `license: 'All rights reserved'` and `is_downloadable: False` on house tracks. — [Audius API](https://api.audius.co/v1)
- **Pixabay Content License:** free use without attribution, and modification is allowed. It prohibits selling or distributing content "on a Standalone basis" where no creative work has been applied. — [Pixabay license summary](https://pixabay.com/service/license-summary/)
- **NCS:** free for independent creators' UGC on YouTube and Twitch if the artist and song are credited. Commercial content needs a paid Commercial License Agreement. Claims are not guaranteed against on TikTok, Instagram and Facebook. — [NCS usage policy](https://ncs.io/usage-policy) (via search snippet)
- **ccMixter** is still operating. It made a "Minor Update to Terms of Use" (dated Aug 28, 2025 per search snippet). — [ccMixter thread 4494](https://ccmixter.org/thread/4494)
- **FMA** is owned by Tribe of Noise (acquired 2019, after KitSplit in Dec 2018). It is still CC-based, and Tribe of Noise PRO now offers paid licensing alongside it. — [Wikipedia: FMA](https://en.wikipedia.org/wiki/Free_Music_Archive); [FMA About](https://freemusicarchive.org/about/)

### Inferences
- **Is mixing a derivative work?** Live or recorded DJ mixes generally count as adaptations or performances. Under CC, playing two tracks over each other in a private practice session inside the app is low risk for any license. Recording or sharing a mix needs licenses without ND, so you should **exclude ND tracks** if users can export or share mixes. SA would then require the mix to be shared under the same license. This is a legal interpretation; confirm it with counsel.
- **Automated analysis** (BPM, key, beat grid) is not restricted by any CC license. Among platform terms, the SoundCloud AI clause ("input to ... machine intelligence") could arguably cover ML-based beat or key detectors, which is a risk. Jamendo and IA terms say nothing about it.
- **The best legal fit is IA netlabels filtered to CC BY / BY-SA.** It has no platform-level API terms beyond IA's general ToU, it allows files to be downloaded and cached, and it permits commercial use when the license is not NC.
- If the app will be free and non-commercial, BY-NC content opens up about 65% more of the IA netlabel catalog and the Jamendo API's free tier.
- Pixabay, NCS, Mixkit and Uppbeat licenses are written for embedding music in videos. Redistributing raw tracks to app users so they can download and mix them is close to "standalone distribution" and is probably not allowed (inference).

### Gaps
- I did not read the full text of the Audius Open Music License, so it is unknown whether it allows caching, derivatives or commercial apps.
- Pixabay full Content License: the summary page did not address use in apps or streaming, AI training, or Content ID for music. Training knowledge, unverified: Pixabay music can carry Content ID claims and the license bans using content to train AI.
- Mixkit license: the text was not retrieved. Training knowledge, unverified: the "Mixkit Stock Music Free License" allows use in projects but bans redistribution as standalone files or in competing libraries.
- Uppbeat: the FAQ returned HTTP 429. Training knowledge, unverified: there is a free tier with monthly download caps and a credit required in video descriptions, a Premium paid plan, and the license is tied to YouTube/social video use. Uppbeat has no public API.
- Incompetech / Kevin MacLeod: not fetched. Training knowledge, unverified: tracks are CC BY 4.0 (CC BY 3.0 historically), with a paid "no attribution" license available. There are few house tracks; it is mostly cinematic and library music.
- YouTube Audio Library: not fetched. Training knowledge, unverified: it is available only inside YouTube Studio, licensed for use in YouTube videos (some tracks need attribution), and not licensed for redistribution in third-party apps. It has no API.
- Chosic: not fetched. Training knowledge, unverified: it aggregates CC-BY and custom-licensed tracks from other artists; it has no API, and per-track licenses vary.
- Bandcamp: not researched. Training knowledge, unverified: it has no public API for catalogs or downloads, and "free / name-your-price" does not grant a CC license unless the artist marks one. It works only for manual, artist-by-artist curation.

---

## Q3: API availability, endpoints, auth, rate limits, audio URLs

### Takeaway
**IA (no key, JSON search and metadata, direct file URLs)**, **Jamendo API v3 (client_id; stream and download URLs including FLAC)**, **Openverse (an aggregator with direct file URLs)** and **Audius (open REST, streaming)** are the usable APIs. The FMA API is shut down. Pixabay's API covers only images and video. SoundCloud's API exists but forbids storing files and is moving to HLS AAC only.

### Cited Findings
- **Internet Archive:** `archive.org/advancedsearch.php` (Lucene query, JSON output) plus `archive.org/metadata/{identifier}`, which lists every file with its format. No key is needed for reads. — [audio-file.org](https://audio-file.org/2021/12/31/netlabels-internet-archive-virtual-record-labels/); a live probe of [archive.org/metadata/yarn014](https://archive.org/metadata/yarn014) returned file formats including **Flac, WAVE, VBR MP3, Ogg Vorbis, plus "Essentia Low GZ" and "Essentia High GZ"**, which are precomputed Essentia audio-analysis descriptor files, and "Columbia Peaks".
- **Jamendo API v3** `tracks` endpoint: `audioformat` sets the stream URL format (mp31 = 96 kbps, mp32 = VBR "good quality", ogg, flac). `audiodlformat` sets the download URL format. `audiodownload` is an empty string when `audiodownload_allowed` is false. Filters include `tags` (AND), `fuzzytags` (OR), `speed` (verylow…veryhigh), `ccnc`/`ccnd`/`ccsa`, and `include=musicinfo` (genres, instruments, vocal/instrumental, acoustic/electric). — [Jamendo tracks docs](https://developer.jamendo.com/v3.0/tracks)
- Jamendo free non-commercial quota: **35,000 requests per month** (search snippet). Jamendo also reserves the right to impose other limits. — [Jamendo API ToU](https://devportal.jamendo.com/api_terms_of_use); [Jamendo Licensing help: API](https://help-licensing.jamendo.com/hc/en-us/articles/20699346005661-Jamendo-API)
- A live test with Jamendo's public documentation client_id returned "Jamendo Api Suspended Application", so each developer must register their own client_id. — Jamendo API, probed 2026-10-02
- **Openverse** `GET https://api.openverse.org/v1/audio/?q=...` works anonymously. It returned `source`, `license`, `license_version`, `duration`, `filetype`, `bit_rate`, a direct `url` (for example `prod-1.storage.jamendo.com/?trackid=...&format=mp32`) and `genres`. The anonymous `result_count` was capped at 240 for each query, which suggests unauthenticated pagination limits. — [Openverse API](https://api.openverse.org/v1/audio/) (probe)
- **Audius** `GET https://api.audius.co/v1/tracks/search?query=...&app_name=...` works without a key and returns `genre`, `duration`, `is_downloadable`, `is_streamable`, `bpm`, `musical_key` and `license`. — [Audius API](https://api.audius.co/v1) (probe); [Audius dev docs](https://docs.audius.org/developers/introduction/overview/)
- Audius artists control downloads per track (Public, Followers or Premium). They can offer a "Full Track Download" as a lossless copy, plus stems and source files (FLAC, WAV, ALAC, AIFF). — [Audius help (search snippet)](https://help.audius.co/product/editing-your-release)
- **FMA API:** FMA "had to shut down the API" because of server load. It says it still welcomes app developers who do not put excessive stress on its servers. — [FMA app developers page](https://freemusicarchive.org/app-developers)
- **Pixabay API:** only `GET /api/` (images) and `/api/videos/` are documented; there is **no music endpoint**. Limits are 100 requests per 60 s, and responses must be cached for 24 h. — [Pixabay API docs](https://pixabay.com/api/docs/)
- **SoundCloud API:** MP3 and Opus transcodings were removed on **Dec 31, 2025**. Streams are now HLS AAC only (`hls_aac_160_url` preferred, `hls_aac_96_url`). Tracks have `access` set to playable, preview or blocked. The `/tracks` endpoint can filter by license. — [SoundCloud dev blog](https://developers.soundcloud.com/blog/api-streaming-urls/); [soundcloud/api issue #441](https://github.com/soundcloud/api/issues/441)
- **Freesound APIv2:** supports token auth and OAuth2. APIv1 has reached end of life. It offers content-based similarity search and audio descriptors. — [Freesound API docs](https://freesound.org/docs/api/)

### Inferences
- IA is the only major source where bulk, programmatic download of lossless files is clearly fine technically and contractually, subject to general IA ToU and polite rate limits. The Essentia descriptor files could cut down your own analysis or serve to cross-check it.
- Openverse is a good discovery layer across Jamendo and Freesound, but the Jamendo API terms still apply to the Jamendo files it points to (inference).

### Gaps
- Exact Audius API rate limits and the API Terms text were not fetched.
- Freesound rate limits (training knowledge, unverified: about 60 requests/min and 2,000 per day for standard keys) and the OAuth2 requirement for downloading originals were not confirmed in this session.
- I found no IA-specific published rate limit.

---

## Q4: Audio format and quality

### Takeaway
IA netlabels often carry **FLAC/WAV plus VBR MP3/OGG**, and Jamendo exposes **FLAC** through `audioformat`/`audiodlformat=flac`. Both work for analysis and practice. Openverse's Jamendo URLs default to mp32 (VBR). SoundCloud is AAC HLS at 96 or 160 kbps only. Audius lossless downloads exist only where the artist enables them.

### Cited Findings
- IA `yarn014` files include Flac, WAVE, VBR MP3 and Ogg Vorbis. — [archive.org/metadata/yarn014](https://archive.org/metadata/yarn014)
- Jamendo formats: mp31 (96 kbps), mp32 (VBR), ogg, flac. — [Jamendo tracks docs](https://developer.jamendo.com/v3.0/tracks)
- SoundCloud API streams: AAC HLS at 160 or 96 kbps only after Dec 31, 2025. — [SoundCloud dev blog](https://developers.soundcloud.com/blog/api-streaming-urls/)
- Freesound previews via Openverse: 128 kbps MP3 (`-hq.mp3`). — [Openverse API probe](https://api.openverse.org/v1/audio/)
- Audius: optional lossless full-track download and stems (FLAC/WAV/ALAC/AIFF). — [Audius help](https://help.audius.co/product/editing-your-release)

### Inferences
- Older netlabel releases (2000s) may be 128–192 kbps MP3 only; check formats per item through the metadata endpoint.

### Gaps
- Pixabay, Mixkit, Uppbeat and NCS formats were not verified. Training knowledge, unverified: Pixabay and Mixkit offer MP3 (Mixkit sometimes WAV), Uppbeat offers MP3 (WAV on Premium), and NCS offers MP3 with WAV on some releases.

---

## Q5: Genre/tag metadata quality; BPM/key metadata

### Takeaway
**Audius** is the only source tested that returns **BPM and musical key** fields. **Jamendo** has curated genre tags (for example `deephouse`) and a coarse `speed` bucket, but no BPM or key. IA tags are free text set by uploaders; there is no BPM or key in metadata, although Essentia descriptor files are attached to many items. Expect to run your own analysis anyway.

### Cited Findings
- Audius search results include `bpm: 122`, `musical_key: 'G minor'` and genre "Deep House". — [Audius API probe](https://api.audius.co/v1)
- Jamendo offers `include=musicinfo` (genres, instruments, vocal/instrumental) and `speed` buckets. — [Jamendo tracks docs](https://developer.jamendo.com/v3.0/tracks)
- Jamendo genre tags seen through Openverse include `['dance','deephouse']`. A "house" text query also matched a track tagged filmscore/singersongwriter, so text search is noisy. — [Openverse API probe](https://api.openverse.org/v1/audio/)
- An IA subject example is a freeform semicolon-separated list ("Electronic;Netaudio;Netlabel;...;Footwork;Juke;Drum and Bass"). — [archive.org/metadata/yarn014](https://archive.org/metadata/yarn014)
- Freesound offers audio descriptors through its API (rhythm and tonal analysis). — [Freesound API docs](https://freesound.org/docs/api/)

### Inferences
- Use the source tags only to pre-filter candidates, then confirm a track is in the house tempo range (about 118–130 BPM) with your own analyzer. Audius BPM and key values are likely auto-detected and may contain octave errors (unverified).

### Gaps
- Whether Pixabay or Uppbeat expose BPM. Training knowledge, unverified: Uppbeat shows BPM on its site, and Pixabay shows duration and mood/genre only.

---

## Q6: Cost

### Takeaway
IA, Openverse, ccMixter, Freesound, the Audius API and the Pixabay site are free. The Jamendo API is free only for non-commercial use, and commercial use needs a quoted license. NCS commercial use needs a paid agreement. Uppbeat and Tribe of Noise PRO (FMA) are freemium or paid licensing.

### Cited Findings
- Jamendo: the API is free for non-commercial use (35k requests per month); commercial pricing is on request from licensing@jamendo.com. — [Jamendo API ToU](https://devportal.jamendo.com/api_terms_of_use)
- NCS: commercial use requires a Commercial License Agreement and a fee. — [NCS usage policy](https://ncs.io/usage-policy)
- Pixabay API: free, including for commercial projects (search snippet). — [publicapis.io Pixabay](https://publicapis.io/pixabay-api)
- FMA plus Tribe of Noise PRO: paid licensing "for every creator and every budget". — [FMA About](https://freemusicarchive.org/about/)
- Audius: costs and fees page exists (not read). — [Audius help: costs and fees](https://help.audius.co/product/costs-and-fees)

### Inferences
- **Recommended stack for an MVP:** (1) IA netlabels, filtered to `licenseurl` BY/BY-SA (or BY-NC if the app stays non-commercial) and to house/techno/minimal subjects, preferring FLAC. (2) The Jamendo API v3 with your own client_id, `tags=deephouse|techhouse|house|techno`, `audiodlformat=flac`, and `audiodownload_allowed=true`, used non-commercially, with attribution plus backlinks and without offline caching features. (3) Optionally, Openverse for discovery. Avoid SoundCloud (no storage, AI clause, HLS only), NCS, Pixabay, Mixkit, Uppbeat and the YouTube Audio Library as in-app sources, because their licenses target video creators.

### Gaps
- Jamendo Licensing commercial price quotes are not public.
- Uppbeat and Mixkit pricing were not verified in this session.
