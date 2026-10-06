# Legal/Licensing Considerations for Openly Licensed Music in a DJ Learning App (as of Oct 2026)

*Not legal advice. Focus: US and EU (UK noted). Research conducted 2026-10-02.*

App functions assessed: (a) download/stream free house/EDM tracks to users; (b) automated audio analysis (BPM, key, beatgrid, phrase, energy) with stored derived data; (c) users mix two tracks and possibly record/export/share practice mixes.

---

## 1. What each CC license permits for hosting/streaming, mixing, and sharing recorded mixes

### Takeaway
Hosting/streaming unmodified tracks is permitted under every CC license (with attribution, and non-commercial-only for NC variants); the critical splits are (i) NC — a free app with a paid tier is plausibly "commercial" in purpose, and platform ToS (Jamendo) define commercial even more broadly, and (ii) ND — users may privately make a mix of ND tracks, but a recorded mix that time-stretches/overlaps ND tracks is very likely an "Adapted Material" that cannot be shared. CC0 and CC-BY are the only clean choices for a monetized app that lets users export/share mixes.

### Cited Findings
- CC 4.0 license grant (all licenses): right to "reproduce and Share the Licensed Material, in whole or in part"; ND licenses add "produce and reproduce, but not Share, Adapted Material." — [CC BY-ND 4.0 legal code](https://creativecommons.org/licenses/by-nd/4.0/legalcode.en)
- "Adapted Material" = material "derived from or based upon the Licensed Material and in which the Licensed Material is translated, altered, arranged, transformed, or otherwise modified in a manner requiring permission"; the legal code also specifies that a musical work/sound recording synced in timed relation with a moving image is always Adapted Material. — [CC BY-ND 4.0 legal code](https://creativecommons.org/licenses/by-nd/4.0/legalcode.en)
- Since 4.0, "all CC licenses, even the NoDerivatives licenses, allow anyone to make an adaptation ... but if an adaptation of an ND-licensed work has been created, it cannot be shared." — [CC Certificate course, 4.4 Remixing CC-Licensed Work](https://creativecommons.org/course/cc-cert-edu/unit-4-using-cc-licenses-and-cc-licensed-works/4-4-remixing-cc-licensed-work/) (via search summary)
- Collections (separate, independent works assembled, each retaining its own license) are not derivatives; "all Creative Commons licences permit works to be incorporated into collections," including BY-ND and BY-NC-ND. — [CSU Open Licences text](https://opentext.csu.edu.au/oalicences/chapter/derivatives-adaptations-remixes-and-collections/); [CCGA libguide](https://libguides.ccga.edu/CC/adaptations)
- CC attribution guidance: using music as background in audio/video "constitutes an adaptation — so licenses with ND ... cannot be used this way." — [CC wiki, Recommended practices for attribution](https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution)
- NonCommercial (4.0) = "not primarily intended for or directed towards commercial advantage or monetary compensation." The word "primarily" means only the primary purpose matters. NC turns on *how* a work is used, not *who* uses it — "a reuser need not be in education, in government, an individual, or a recognized charity/nonprofit." CC intentionally avoids an exhaustive list of permitted/prohibited activities. — [CC wiki, NonCommercial interpretation](https://wiki.creativecommons.org/wiki/NonCommercial_interpretation)
- CC's "Defining Noncommercial" study found real-world licensor/licensee disputes over NC interpretation relatively rare. — [CC wiki, NonCommercial interpretation](https://wiki.creativecommons.org/wiki/NonCommercial_interpretation)
- NC-licensed content cannot be remixed with BY-SA works; NC licenses are not "open" under the Open Definition. — [CC wiki, NonCommercial interpretation](https://wiki.creativecommons.org/wiki/NonCommercial_interpretation)
- Licensees may not apply "Effective Technological Measures" (DRM) to the Licensed Material if doing so restricts exercise of the licensed rights, nor impose additional terms (Sec. 2(a)(5)(C)). — [CC BY-ND 4.0 legal code](https://creativecommons.org/licenses/by-nd/4.0/legalcode.en); [CC FAQ](https://creativecommons.org/faq/)
- Industry practice example: Toucan Music's CC/royalty-free license allows tracks in public DJ sets (even paid audiences) "provided recorded DJ mixes are not sold for commercial gain." — [Toucan Music licensing](https://www.toucanmusic.com/licensing/) (via search summary)

### Inferences
- **Hosting/streaming (a):** Allowed under CC0, BY, BY-SA, BY-NC, BY-ND, BY-NC-ND as verbatim "Sharing," subject to attribution (all except CC0) and NC purpose (NC variants). DRM-like streaming protections (encrypted, non-downloadable streams) could arguably conflict with Sec. 2(a)(5)(C) if they prevent users from exercising licensed rights; safest is to also link to the original downloadable source.
- **Freemium = commercial?** CC gives no bright-line rule. A paid tier whose value includes access to the NC music (or ad-supported playback of it) is likely "directed towards ... monetary compensation"; a strictly free tier that is a funnel for paid features is a grey zone. Conservative approach: exclude NC tracks entirely from any paid/ad-supported surface, or use only CC0/BY/BY-SA in a monetized product.
- **Is a DJ mix an adaptation?** No CC source was found addressing audio-only DJ mixes directly. A pure sequence of unaltered tracks would be a collection. But a beatmatched mix time-stretches tracks (tempo/pitch change), overlaps them, and applies EQ/filters — that is "altered ... transformed, or otherwise modified," so a recorded DJ mix is very likely Adapted Material. Consequences: ND/NC-ND tracks — users can mix privately in-app (allowed), but **must not share/export** recorded mixes; BY-SA — a shared mix must be licensed BY-SA (or compatible), which is awkward when mixed with a BY-NC track (incompatible); BY-NC-SA + BY-SA in one mix is incompatible.
- **User-recorded mixes shared publicly:** fine for CC0/BY (with attribution of each track in the description), BY-SA (mix must carry BY-SA), BY-NC (only on non-monetized uploads — YouTube monetization would breach NC). Not fine for any ND track.
- Practical design: tag every track with license flags (`can_share_adaptation`, `commercial_ok`), and disable "export/share mix" when any ND track is in the mix; auto-generate a tracklist with TASL attribution for exported mixes.

### Gaps
- No official CC FAQ or court decision found specifically classifying an audio-only DJ mix (crossfade/beatmatch) as adaptation vs. collection; the analysis above is inference from the legal-code definition.
- CC's NC guidance does not specifically address freemium/subscription apps; I found no authoritative example on point.

---

## 2. Legality of computing/storing audio features (BPM, key, beatgrid) and analyzing users' own tracks

### Takeaway
Extracting factual, non-expressive features (tempo, key, beat positions) is low-risk: the outputs are facts not protected by copyright, and the transient copying needed is strongly supported by US fair use precedent (HathiTrust, Google Books, and 2025 AI-training rulings) and by EU DSM Art. 4 (commercial TDM, subject to opt-out). The UK is narrower (s.29A non-commercial research only, and the March 2026 government report abandoned a commercial TDM exception). Analyzing files the user lawfully owns locally on their device is very low-risk; analyzing Spotify audio is contractually prohibited.

### Cited Findings
- *Authors Guild v. HathiTrust*, 755 F.3d 87 (2d Cir. 2014): full-text searchable database was "quintessentially transformative" because a search result "is different in purpose, character, expression, meaning, and message" from the source; a transformative use "serves a new and different function from the original work and is not a substitute for it." — [Wikipedia summary](https://en.wikipedia.org/wiki/Authors_Guild_v._HathiTrust); [US Copyright Office fair use summary](https://www.copyright.gov/fair-use/summaries/authorsguild-hathitrust-2dcir2014.pdf)
- *Authors Guild v. Google* (2d Cir., Oct 16, 2015): copying books and displaying snippets held transformative and fair use. — [ARL](https://www.arl.org/blog/second-circuit-affirms-fair-use-in-google-books-case/)
- *Bartz v. Anthropic* (N.D. Cal., June 23, 2025): training on lawfully purchased/scanned books was "exceedingly transformative" fair use; but retaining pirated library copies was not ("[e]very factor points against fair use"). The case later settled. — [Jones Day](https://www.jonesday.com/en/insights/2025/06/two-us-courts-address-fair-use-in-genai-training-cases); [AFS Law](https://www.afslaw.com/perspectives/alerts/landmark-ruling-ai-copyright-fair-use-vs-infringement-bartz-v-anthropic); [Wolters Kluwer on settlement](https://legalblogs.wolterskluwer.com/copyright-blog/the-bartz-v-anthropic-settlement-understanding-americas-largest-copyright-settlement/)
- *Kadrey v. Meta* (N.D. Cal., June 25, 2025, Chhabria J.) also found fair use for LLM training; summaries characterize it as less concerned with the source of copies than Bartz. — [White & Case](https://www.whitecase.com/insight-alert/two-california-district-judges-rule-using-books-train-ai-fair-use); [Jackson Walker](https://www.jw.com/news/insights-kadrey-meta-bartz-anthropic-ai-copyright/) (note: commentators describe Chhabria's ruling as narrow/record-specific; treat the "regardless of source" characterization cautiously)
- EU DSM Directive (2019/790) Art. 4 permits reproductions/extractions of *lawfully accessed* works for TDM unless rights are "expressly reserved ... in an appropriate manner, such as machine-readable means in the case of content made publicly available online" (including metadata and website/service T&Cs). Art. 3 covers research organisations/cultural heritage institutions (no opt-out). — [Kluwer Copyright Blog](https://legalblogs.wolterskluwer.com/copyright-blog/the-new-copyright-directive-text-and-data-mining-articles-3-and-4/); [CC statement on Art. 4](https://creativecommons.org/wp-content/uploads/2021/12/CC-Statement-on-the-TDM-Exception-Art-4-DSM-Final.pdf)
- A Dutch court (2025) held that a TDM opt-out under Art. 4 must be made by machine-readable means. — [IPKat, Feb 2025](https://ipkitten.blogspot.com/2025/02/dutch-court-holds-that-tdm-opt-out-must.html)
- UK CDPA s.29A permits copies for "computational analysis" only for non-commercial research. — [Reed Smith](https://www.reedsmith.com/articles/entertainment-and-media-guide-to-ai/text-and-data-mining-in-uk/)
- UK government (18 March 2026 report) abandoned the proposed broad TDM exception with opt-out: "the government no longer has a preferred option"; licences are required unless an existing exception (e.g., s.29A) applies. — [Bratby Law](https://bratby.law/copyright-and-ai-training-exception-2026/); [UK Gov Report on Copyright and AI (PDF)](https://assets.publishing.service.gov.uk/media/69ba692226909a14239612e4/CP2602959_-_Report_on_Copyright_and_Artificial_Intelligence_web.pdf)
- Spotify Developer Policy (effective 15 May 2025): "Do not analyze the Spotify Content or the Spotify Service for any purpose..."; "Do not use the Spotify Platform or any Spotify Content to train a machine learning or AI model or otherwise ingest Spotify Content into a machine learning or AI model." — [Spotify Developer Policy](https://developer.spotify.com/policy)

### Inferences
- BPM, key, beat timestamps, phrase boundaries and energy curves are facts/measurements, not expression; storing and displaying them does not reproduce the work. The only copyright-relevant act is the (temporary) copy used for analysis. For CC/CC0 tracks this copy is licensed anyway (all CC licenses permit reproduction), so feature extraction on CC tracks is essentially risk-free; ND does not bar it because derived numeric metadata is not "Adapted Material" (not a modified version of the work).
- For users' purchased/owned files, running analysis **locally on the user's device** (as Rekordbox/Serato/Mixed In Key do) is the safest architecture: the user lawfully possesses the copy, nothing is redistributed, and only non-expressive data is produced. Uploading users' commercial files to a server for analysis adds storage/copy risk (Bartz shows retention of copies matters) — if done, delete audio immediately after analysis and keep only features.
- Spotify: the existing app must not obtain or analyze Spotify audio streams for BPM/key, must not mix Spotify content with other audio, and must not feed Spotify content into ML. Using Spotify only for metadata/identity (search, track IDs, playlists) and getting features elsewhere (local analysis of user-owned files, or a third-party feature DB such as GetSongBPM, subject to its own terms) is the compliant pattern.
- EU: if the app crawls/pulls tracks from sites, honor machine-readable TDM reservations (robots.txt/TDMRep/ToS). Platform ToS (e.g., Jamendo API terms) can function as an Art. 4 reservation for commercial mining.

### Gaps
- No US case squarely on audio feature extraction (MIR) found; analogy to HathiTrust/Google Books is inference.
- Did not verify whether EU private-copy exceptions (Art. 5(2)(b) InfoSoc) would separately cover local user-side analysis.

---

## 3. Attribution requirements in-app (TASL) and best practices

### Takeaway
All CC licenses except CC0 require attribution that identifies creator, copyright notice, license notice/link, disclaimer notice, a URI to the source "where reasonably practicable," and an indication of modifications — satisfiable "in any reasonable manner based on the medium, means, and context." In practice: show Title/Artist/Source link/License link on the player and track pages, keep a credits page, and auto-insert TASL tracklists in exported mixes.

### Cited Findings
- Sec. 3(a): when Sharing, retain creator identification, copyright notice, license notice, warranty-disclaimer notice, URI/hyperlink where practicable; indicate modifications; include the license text or URI/link. These may be satisfied "in any reasonable manner based on the medium, means, and context." Licensor may request removal of attribution "to the extent reasonably practicable." — [CC BY-ND 4.0 legal code](https://creativecommons.org/licenses/by-nd/4.0/legalcode.en)
- Sec. 6(b): terminated rights reinstate automatically if violation is cured "within 30 days of Your discovery." — [CC BY-ND 4.0 legal code](https://creativecommons.org/licenses/by-nd/4.0/legalcode.en)
- TASL: Title, Author ("who allows you to use the work"), Source (original URL preferred), License (named, with link e.g. creativecommons.org/licenses/by/4.0/). For audio/video, attribute within the recording and in description boxes when reasonable; for apps, publish attribution on dedicated web pages with clickable author/source/license links; consider including the warranty disclaimer. — [CC wiki, Recommended practices for attribution](https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution)
- "CC licenses allow for flexibility in the way credit is provided depending on the medium, means, and context." — [CC FAQ](https://creativecommons.org/faq/)
- Jamendo API terms add platform-specific attribution: credit Jamendo members as creators, credit Jamendo as provider, and "provide a direct backlink from each Content"; do not use Jamendo marks in the app name or imply endorsement. — [Jamendo API Terms of Use](https://devportal.jamendo.com/api_terms_of_use)
- Pixabay content requires no attribution (credit appreciated). — [Pixabay license summary](https://pixabay.com/service/license-summary/)

### Inferences
- Store, per track: title, artist (as licensor wants credited), source URL, license name + URL + version, retrieval date, platform, and a snapshot of the license page at ingestion (for laundering/revocation disputes).
- Mark modifications for shared mixes ("tempo-adjusted and mixed by <user>").
- CC0 needs no attribution, but crediting is still good practice and helps provenance.

### Gaps
- None material.

---

## 4. Risks: license laundering, Content ID, PROs, revocability

### Takeaway
The biggest practical risks are not the CC licenses themselves but (1) mislabeled/laundered uploads (CC gives no warranty), (2) Content ID / automated claims hitting users' mix uploads even when properly licensed (Jamendo itself registers some CC BY-NC-ND tracks in Content ID), and (3) PRO-affiliated artists (e.g., SACEM members on Jamendo) whose collecting society may still claim performance royalties. CC licenses are irrevocable, but that only protects you if the licensor actually had the rights.

### Cited Findings
- "CC licenses are not revocable." Licensees may continue using under the license terms for the duration of copyright; licensors can only stop distributing going forward. — [CC FAQ](https://creativecommons.org/faq/)
- CC licenses include a disclaimer: the author "makes no representations or warranties about the non-infringement" of the work. — [CC wiki, attribution practices](https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution)
- Royalties (Sec. 2(b)(3)): licensor waives royalties "to the extent possible," except where collected via voluntary/compulsory licensing schemes that cannot be waived; for NC licenses, royalties may be collected for commercial uses. — [CC BY-ND 4.0 legal code](https://creativecommons.org/licenses/by-nd/4.0/legalcode.en)
- CC FAQ: creators "may wish to check with their collecting society before applying a CC license"; some societies take assignment of rights, preventing members from using CC licenses. — [CC FAQ](https://creativecommons.org/faq/)
- Jamendo: SACEM members can publish works under CC on Jamendo ("totally fine with SACEM in France"); artists must confirm their PRO permits CC. — [Jamendo artist support, Creative Commons explained](https://support-artist.jamendo.com/creative-commons-explained); [Jamendo collecting societies by country](https://help-artists.jamendo.com/hc/en-us/articles/360007562217-Collecting-Societies-by-country)
- Jamendo became an Independent Management Entity (IME) in Feb 2019, allowing it to act like a collective management organization. — [Wikipedia: Jamendo](https://en.wikipedia.org/wiki/Jamendo)
- Jamendo registers tracks in YouTube Content ID if All Rights Reserved or CC BY-NC-ND 4.0. — [Jamendo support: YouTube Content ID](https://support-artist.jamendo.com/youtube-content-id); [Jamendo: suitability for Content ID](https://help-artists.jamendo.com/hc/en-us/articles/360004303238-How-do-you-define-if-a-track-is-suited-for-YouTube-Content-ID)
- Even licensed Jamendo Licensing customers "may occasionally receive a Content ID claim," which does not invalidate their license. — [Jamendo Licensing: YouTube claims](https://help-licensing.jamendo.com/hc/en-us/articles/211301009-Why-have-I-received-a-Copyright-Infringement-Notification-on-YouTube-)
- Giving credit does not equal permission on YouTube; CC licensing does not prevent Content ID claims; non-exclusively licensed tracks can be claimed by multiple parties. — [Foxi Blog Content ID guide](https://www.foximusic.com/blog/youtube-content-id-for-music-guide-monetization/) (secondary/vendor source)
- Mixcloud holds blanket licenses (US: SoundExchange, ASCAP, BMI, SESAC; UK: PRS, PPL/direct label deals) covering tracks in DJ sets, with restrictions (no rewind, max 3 tracks per artist, no single uploads). — [Hypebot](https://www.hypebot.com/mixcloud-pacts-with-eu-licensor-ice-for-12m-dj-sets/); [Mixcloud help: allowed content](https://help.mixcloud.com/hc/en-us/articles/360004030860-What-type-of-content-can-I-upload-to-Mixcloud) (via search summary)
- SoundCloud mixes face takedowns/copyright strikes via automated detection. — [Digital DJ Tips](https://www.digitaldjtips.com/why-you-shouldnt-post-your-mixes-on-soundcloud/); [DJ TechTools](https://djtechtools.com/2017/06/15/drake-hate-dj-mixes-soundcloud-copyright-strikes-vs-dj-mixes/)

### Inferences
- **License laundering mitigation:** prefer curated sources with artist verification (Jamendo, FMA curated catalog, ccMixter, artist-direct Bandcamp CC releases) over open uploads (SoundCloud/YouTube/Archive.org); run fingerprint checks (e.g., AcoustID/Chromaprint) against known commercial catalogs; record provenance snapshots; have a takedown path and a kill-switch to delist a track app-wide. Irrevocability does not help if the uploader never held rights — then the app is distributing infringing content (US DMCA §512 safe harbor applies only to user uploads, not to an operator-curated catalog).
- **Content ID for user mixes:** recommend Mixcloud for sharing mixes (blanket-licensed); warn users that YouTube/SoundCloud may claim mixes even with valid CC tracks; ship an auto-generated tracklist + license list users can paste in disputes. Avoid Jamendo tracks flagged for Content ID if exporting is a feature.
- **PROs:** for in-app streaming in a commercial context, PRO-affiliated NC tracks may trigger performance-royalty claims; CC0/BY tracks from non-PRO artists minimize this. For public DJ performance by users, venue PRO licenses (ASCAP/BMI/GEMA/SACEM) remain relevant regardless of CC.

### Gaps
- No quantitative data found on prevalence of laundered/mislabeled CC music on Jamendo/FMA/SoundCloud.
- Did not confirm whether SACEM's CC-NC pilot terms still apply in 2026 or whether SACEM claims royalties for commercial streaming of members' CC-NC works.

---

## 5. Platform ToS layered on top of CC licenses

### Takeaway
Platform terms can be stricter than the CC license on each track: Jamendo's API forbids any commercial use (including ads/affiliate revenue) without a Jamendo Licensing deal and forbids apps designed for caching/offline access; Pixabay's license (not CC) forbids standalone redistribution of unaltered content; FMA's site content default is CC BY-NC-SA and each track's license controls.

### Cited Findings
- Jamendo API: "may be used freely for non-commercial uses. For any other type of use including but not limited to commercial uses please contact our sales team at licensing@jamendo.com." Commercial = "any use that is intended for or directed toward commercial advantage or any monetary compensation, including any revenue arising from affiliation programs or advertising." — [Jamendo API Terms of Use](https://devportal.jamendo.com/api_terms_of_use)
- Jamendo API: "Applications must not be specifically designed to cache the content nor offering an offline access to the content. Caching system may only be used to the extent reasonably necessary for the operation of the Application." Jamendo may limit request volume/frequency. — [Jamendo API Terms of Use](https://devportal.jamendo.com/api_terms_of_use)
- Pixabay Content License: free use, no attribution required, may modify/adapt; but may not "sell or distribute Content (either in digital or physical form) on a Standalone basis" where "no creative effort has been applied"; no deceptive use; no use as trademark. — [Pixabay license summary](https://pixabay.com/service/license-summary/)
- FMA: each song/album page states its license; users are responsible for complying; "Unless otherwise noted, all Site Content is licensed under the Creative Commons Attribution-Noncommercial-Share Alike 4.0 license"; FMA also has its own "FMA License." — [FMA Terms of Use](https://freemusicarchive.org/terms_of_use); [FMA License legal code](https://freemusicarchive.org/FMA_Licenselegalcode); [FMA License Guide](https://freemusicarchive.org/License_Guide) (terms page returned HTTP 500 on direct fetch; text from search snippets)
- Spotify Developer Policy: "Do not permit any device or system to segue, mix, re-mix, or overlap any Spotify Content with any other audio content"; no syncing recordings with visual media; streaming SDAs cannot be sold or generate ad revenue. — [Spotify Developer Policy](https://developer.spotify.com/policy)

### Inferences
- **Jamendo:** downloading tracks via API for offline mixing practice in-app conflicts with the caching/offline clause; any paid tier or ads means a commercial deal is needed. Download tracks via Jamendo's own download links per license only for a non-commercial app, or negotiate Jamendo Licensing.
- **Pixabay:** an app that lets users browse and download Pixabay tracks as-is looks like standalone redistribution; streaming them for in-app mixing (creative effort applied) is more defensible, but serving raw files for download is risky. Pixabay content is not CC0 despite common belief.
- **FMA:** check per-track license; check ToS on automated/bulk downloading before scraping (not verified).
- **Spotify:** the existing app's Spotify integration must not play Spotify audio inside a mixing workflow.

### Gaps
- Could not retrieve full FMA Terms of Use (HTTP 500); clauses on scraping/automated access and API use not verified.
- Did not retrieve Pixabay's full license for any music-specific or AI/Content ID clauses, nor SoundCloud/ccMixter ToS.

---

## 6. Spotify Developer Terms and the audio-features deprecation

### Takeaway
Spotify both removed the data (audio-features/audio-analysis endpoints cut for new apps on Nov 27, 2024, still with no replacement in 2026) and contractually forbids the alternative (analyzing Spotify content, ML ingestion, mixing Spotify audio). A DJ prep tool can use Spotify only for metadata/library context; BPM/key must come from local analysis of user-owned files or third-party databases.

### Cited Findings
- Nov 27, 2024: Spotify cut new/non-extended developer access to audio features, audio analysis, recommendations, related artists, and featured playlists, citing "security challenges." — [TechCrunch](https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/); [spotipy issue #1172](https://github.com/spotipy-dev/spotipy/issues/1172)
- Endpoint returns 403 for apps without a (pending) quota extension prior to Nov 27, 2024. — [Spotify Community thread](https://community.spotify.com/t5/Spotify-for-Developers/Web-API-Get-Track-s-Audio-Features-403-error/td-p/6654507)
- As of 2026 there is "still no official replacement." — [DEV Community](https://dev.to/birrings/spotifys-audiofeatures-api-died-in-2024-heres-what-i-built-to-replace-it-3dn3) (secondary, developer blog)
- Spotify Developer Policy (eff. 15 May 2025): no analysis of Spotify Content for any purpose; no ML/AI training or ingestion; no segue/mix/remix/overlap of Spotify Content with other audio. — [Spotify Developer Policy](https://developer.spotify.com/policy)

### Inferences
- The current app's Spotify client (set-prep-copilot/app/spotify_client.py) should be limited to auth, search, playlists and track metadata; feature data should come from GetSongBPM (already being added) or local analysis. Do not pass Spotify preview clips or streams into the analysis pipeline.

### Gaps
- Did not review Spotify's separate Developer Terms (vs. Policy) text for additional download/caching clauses; the fetched Policy summary did not mention caching explicitly.

---

## Summary matrix (inference, based on the above)

| License | Host/stream in free app | In app with paid tier/ads | Analyze & store features | Users mix privately | Users share recorded mix |
|---|---|---|---|---|---|
| CC0 | Yes | Yes | Yes | Yes | Yes (credit optional) |
| CC BY | Yes + TASL | Yes + TASL | Yes | Yes | Yes + TASL, note modifications |
| CC BY-SA | Yes + TASL | Yes + TASL | Yes | Yes | Yes, mix must be BY-SA; incompatible with NC tracks |
| CC BY-NC | Yes + TASL | Risky/likely no | Yes | Yes | Only non-monetized uploads |
| CC BY-ND | Yes + TASL | Yes + TASL | Yes | Yes (4.0 allows private adaptation) | No (likely Adapted Material) |
| CC BY-NC-ND | Yes + TASL | Risky/likely no | Yes | Yes | No |
| Platform overlays | Jamendo API: non-commercial only, no offline caching; Pixabay: no standalone redistribution; Spotify: no analysis/mixing at all |
