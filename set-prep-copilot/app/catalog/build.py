"""Builds the practice catalog: harvest -> download -> analyze -> rate ->
lessons + credits.

    python -m app.catalog.build --target 300
    python -m app.catalog.build --rescore   # re-derive BPM/difficulty/lessons from saved analyses

Output (in --out, default set-prep-copilot/catalog/, which is gitignored):
- catalog.json   every accepted track: identity, full license record, BPM,
                 key, difficulty score and level. Rewritten after each
                 track, so an interrupted run resumes where it stopped.
- rejected.json  track ids already tried and rejected, with the reason.
- analysis/      full analyze_track output per track (beat grid, phrases,
                 energy curve) for the practice UI.
- audio/         the downloaded MP3s.
- lessons.json   the level-by-level lesson pairs (curriculum.build_lessons).
- CREDITS.md     Title / Author / Source / License for every track, as
                 every CC BY* license requires.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..audio_analysis import analyze_track, bpm_from_beats
from . import curriculum, difficulty, internet_archive

DEFAULT_OUT = Path(__file__).resolve().parent.parent.parent / "catalog"

# House lives at roughly 118-130 BPM. The window is wider so the hard levels
# have some tempo spread, but tracks outside it are mis-tagged (or the beat
# tracker halved/doubled them) and don't belong in a house practice crate.
MIN_BPM = 112.0
MAX_BPM = 136.0

def _load(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default

def _save(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def _safe_filename(track_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in track_id)

def catalog_entry(cand: internet_archive.CandidateTrack, analysis: dict, audio_path: Path, analysis_path: Path) -> dict:
    return {
        "id": cand.track_id,
        "title": cand.title,
        "artist": cand.artist,
        "release": cand.release_title,
        "source": "Internet Archive netlabels",
        "source_url": cand.source_url,
        "download_url": cand.download_url,
        "license": {
            "name": cand.license.name,
            "url": cand.license.url,
            "attribution_required": cand.license.attribution_required,
            "commercial_ok": cand.license.commercial_ok,
            "adaptations_ok": cand.license.adaptations_ok,
            "share_alike": cand.license.share_alike,
        },
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "audio_path": str(audio_path),
        "analysis_path": str(analysis_path),
        "duration": round(analysis["duration"], 2),
        "bpm": round(analysis["bpm"], 2),
        "camelot_key": analysis["camelot_key"],
        "key_confidence": round(analysis["key_confidence"], 3),
        "difficulty": difficulty.rate(analysis),
    }

def rejection_reason(analysis: dict) -> str | None:
    if analysis["duration"] < internet_archive.MIN_TRACK_SECONDS:
        return f"too short ({analysis['duration']:.0f}s)"
    if not (MIN_BPM <= analysis["bpm"] <= MAX_BPM):
        return f"tempo {analysis['bpm']:.1f} BPM outside house range"
    return None

def write_credits(tracks: list[dict], path: Path) -> None:
    lines = [
        "# Practice track credits",
        "",
        "Every practice track is used under the Creative Commons license listed next to it.",
        "",
    ]
    for t in sorted(tracks, key=lambda t: (t["artist"].lower(), t["title"].lower())):
        lic = t["license"]
        lines.append(
            f'- "{t["title"]}" by {t["artist"]}, from [{t["release"]}]({t["source_url"]}), '
            f'licensed under [{lic["name"]}]({lic["url"]})'
        )
    path.write_text("\n".join(lines) + "\n")

def build(target: int, out_dir: Path, max_releases: int, tracks_per_release: int) -> list[dict]:
    audio_dir = out_dir / "audio"
    analysis_dir = out_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = out_dir / "catalog.json"
    rejected_path = out_dir / "rejected.json"

    tracks: list[dict] = _load(catalog_path, [])
    rejected: dict[str, str] = _load(rejected_path, {})
    done = {t["id"] for t in tracks} | set(rejected)

    try:
        _harvest(target, max_releases, tracks_per_release, tracks, rejected, done, audio_dir, analysis_dir, catalog_path, rejected_path)
    finally:
        # Always leave a usable catalog behind, even if the harvest died
        # part-way (network loss, Ctrl-C): levels, lessons and credits cover
        # whatever was accepted so far, and the next run resumes from there.
        if tracks:
            difficulty.assign_levels(tracks)
            _save(catalog_path, tracks)
        _save(out_dir / "lessons.json", curriculum.build_lessons(tracks))
        write_credits(tracks, out_dir / "CREDITS.md")
    return tracks

def _harvest(target, max_releases, tracks_per_release, tracks, rejected, done, audio_dir, analysis_dir, catalog_path, rejected_path) -> None:
    for cand in internet_archive.iter_candidates(max_releases, tracks_per_release):
        if len(tracks) >= target:
            break
        if cand.track_id in done:
            continue
        done.add(cand.track_id)
        try:
            audio_path = internet_archive.download(cand, audio_dir)
        except internet_archive.InternetArchiveError as exc:
            # Usually transient (IA 5xx, dropped connection): skip for this
            # run but don't record it, so the next run tries again.
            print(f"  skip {cand.track_id}: {exc}", file=sys.stderr)
            continue
        try:
            analysis = analyze_track(str(audio_path))
        except Exception as exc:  # one undecodable file must not stop a multi-hour run
            rejected[cand.track_id] = f"failed: {exc}"
            _save(rejected_path, rejected)
            print(f"  skip {cand.track_id}: {exc}", file=sys.stderr)
            continue

        reason = rejection_reason(analysis)
        if reason:
            rejected[cand.track_id] = reason
            _save(rejected_path, rejected)
            audio_path.unlink(missing_ok=True)
            print(f"  reject {cand.title}: {reason}")
            continue

        analysis_path = analysis_dir / f"{_safe_filename(cand.track_id)}.json"
        _save(analysis_path, analysis)
        entry = catalog_entry(cand, analysis, audio_path, analysis_path)
        tracks.append(entry)
        _save(catalog_path, tracks)
        print(
            f"[{len(tracks)}/{target}] difficulty {entry['difficulty']['score']:.2f} "
            f"{entry['bpm']:.1f} BPM {entry['camelot_key']}  {cand.artist} - {cand.title}"
        )

def rescore(out_dir: Path) -> list[dict]:
    """Re-run everything after analysis -- BPM fit, house-tempo filter,
    difficulty, levels, lessons, credits -- from the saved per-track
    analysis files. No downloads, no audio decoding: use it after changing
    BPM fitting or difficulty weights."""
    catalog_path = out_dir / "catalog.json"
    rejected_path = out_dir / "rejected.json"
    tracks: list[dict] = _load(catalog_path, [])
    rejected: dict[str, str] = _load(rejected_path, {})

    kept: list[dict] = []
    for track in tracks:
        analysis = json.loads(Path(track["analysis_path"]).read_text())
        analysis["bpm"] = bpm_from_beats(analysis["beat_times"], fallback=analysis["bpm"])
        _save(Path(track["analysis_path"]), analysis)
        reason = rejection_reason(analysis)
        if reason:
            rejected[track["id"]] = reason
            Path(track["audio_path"]).unlink(missing_ok=True)
            print(f"  reject {track['title']}: {reason}")
            continue
        track["bpm"] = round(analysis["bpm"], 2)
        track["difficulty"] = difficulty.rate(analysis)
        kept.append(track)

    if kept:
        difficulty.assign_levels(kept)
    _save(catalog_path, kept)
    _save(rejected_path, rejected)
    _save(out_dir / "lessons.json", curriculum.build_lessons(kept))
    write_credits(kept, out_dir / "CREDITS.md")
    return kept


def _print_summary(tracks: list[dict], out_dir: Path) -> None:
    by_level: dict[int, int] = {}
    for t in tracks:
        lvl = t["difficulty"]["level"]
        by_level[lvl] = by_level.get(lvl, 0) + 1
    lessons = _load(out_dir / "lessons.json", [])
    print(f"\n{len(tracks)} tracks in {out_dir}")
    for level in curriculum.LEVELS:
        n_lessons = sum(1 for lesson in lessons if lesson["level"] == level.number)
        print(f"  Level {level.number} ({level.title}): {by_level.get(level.number, 0)} tracks, {n_lessons} lessons")

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the practice-track catalog from Internet Archive netlabels.")
    parser.add_argument("--target", type=int, default=300, help="stop after this many accepted tracks")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-releases", type=int, default=600, help="search at most this many releases")
    parser.add_argument("--tracks-per-release", type=int, default=3)
    parser.add_argument("--rescore", action="store_true", help="recompute from saved analyses; no downloads")
    args = parser.parse_args(argv)

    if args.rescore:
        tracks = rescore(args.out)
    else:
        tracks = build(args.target, args.out, args.max_releases, args.tracks_per_release)
    _print_summary(tracks, args.out)

if __name__ == "__main__":
    main()
