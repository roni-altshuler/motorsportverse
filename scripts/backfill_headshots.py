#!/usr/bin/env python3
"""
backfill_headshots.py
=====================
Season-wide backfill for the driver headshot manifest.

``fetch_driver_headshots.py`` grabs the current roster from openf1.org's
``?session_key=latest`` view, which is fast but misses drivers who left
the grid earlier in the season (mid-season swaps, one-off replacements,
test-driver appearances).  This script walks every meeting in the season,
collects every distinct ``name_acronym`` that appeared in any session,
and fills in the gaps in ``website/public/headshots/``.

Usage:
    python scripts/backfill_headshots.py                  # current season
    python scripts/backfill_headshots.py --season 2025    # specific season
    python scripts/backfill_headshots.py --force          # re-download all

Designed to be wired into the website's ``prebuild`` step so headshot
coverage stays current across the whole season.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover — Pillow is in requirements.txt
    sys.stderr.write(
        "Pillow is required for headshot conversion. Install with:\n"
        "  pip install Pillow\n"
    )
    raise SystemExit(1) from exc


# ── Reuse the helpers from fetch_driver_headshots.py rather than copy them ──
SCRIPTS_DIR = Path(__file__).resolve().parent
_FETCHER_PATH = SCRIPTS_DIR / "fetch_driver_headshots.py"
_spec = importlib.util.spec_from_file_location("_fetcher", _FETCHER_PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover
    raise RuntimeError(f"cannot load helpers from {_FETCHER_PATH}")
_fetcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fetcher)

OPENF1_BASE = _fetcher.OPENF1_BASE
USER_AGENT = _fetcher.USER_AGENT
HTTP_TIMEOUT = _fetcher.HTTP_TIMEOUT
TARGET_SIZE = _fetcher.TARGET_SIZE
WEBP_QUALITY = _fetcher.WEBP_QUALITY
HEADSHOTS_DIR: Path = _fetcher.HEADSHOTS_DIR
DATA_DIR: Path = _fetcher.DATA_DIR
MANIFEST_PATH: Path = _fetcher.MANIFEST_PATH


def _http_json(url: str) -> list | dict:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read()


def _season_year() -> int:
    raw = os.getenv("F1_SEASON_YEAR")
    if raw and raw.isdigit():
        return int(raw)
    return 2026


def _iter_season_sessions(season_year: int) -> Iterable[int]:
    """Yield every session_key from every meeting in the season."""
    meetings = _http_json(f"{OPENF1_BASE}/meetings?year={season_year}")
    if not isinstance(meetings, list):
        return
    for meeting in meetings:
        meeting_key = meeting.get("meeting_key")
        if not meeting_key:
            continue
        try:
            sessions = _http_json(f"{OPENF1_BASE}/sessions?meeting_key={meeting_key}")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"  [warn] meeting {meeting_key}: {exc}")
            continue
        if not isinstance(sessions, list):
            continue
        for session in sessions:
            key = session.get("session_key")
            if key:
                yield int(key)


def _collect_season_drivers(season_year: int) -> dict[str, dict]:
    """Union driver dicts across every session in the season, keyed by acronym."""
    union: dict[str, dict] = {}
    seen_sessions: set[int] = set()
    for session_key in _iter_season_sessions(season_year):
        if session_key in seen_sessions:
            continue
        seen_sessions.add(session_key)
        try:
            drivers = _fetcher._fetch_drivers_for_session(session_key)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"  [warn] session {session_key}: {exc}")
            continue
        for drv in drivers:
            code = (drv.get("name_acronym") or "").strip().upper()
            if not code or len(code) != 3:
                continue
            existing = union.get(code)
            if existing is None or (drv.get("session_key") or 0) >= (existing.get("session_key") or 0):
                union[code] = drv
    print(f"  Saw {len(union)} distinct drivers across {len(seen_sessions)} sessions.")
    return union


def _convert_to_webp(raw: bytes, dest: Path) -> None:
    img = Image.open(io.BytesIO(raw))
    if img.mode not in {"RGB", "RGBA"}:
        img = img.convert("RGBA" if "A" in img.mode else "RGB")
    img.thumbnail(TARGET_SIZE, Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="WEBP", quality=WEBP_QUALITY, method=6)


def backfill(season_year: int, force: bool) -> dict[str, str]:
    HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    drivers = _collect_season_drivers(season_year)
    if not drivers:
        raise RuntimeError(f"no drivers found for season {season_year}")

    manifest: dict[str, str] = {}
    if MANIFEST_PATH.exists():
        try:
            with MANIFEST_PATH.open() as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    manifest = loaded
        except (OSError, json.JSONDecodeError):
            manifest = {}

    downloaded = skipped = errors = 0
    for code, drv in sorted(drivers.items()):
        dest = HEADSHOTS_DIR / f"{code}.webp"
        rel = f"/headshots/{code}.webp"
        if dest.exists() and not force:
            manifest[code] = rel
            skipped += 1
            continue
        url = (drv.get("headshot_url") or "").strip()
        if not url:
            print(f"  [skip] {code}: no headshot_url")
            continue
        try:
            raw = _http_bytes(url)
            _convert_to_webp(raw, dest)
            manifest[code] = rel
            downloaded += 1
            print(f"  [ok]   {code}: {dest.name}")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            errors += 1
            print(f"  [err]  {code}: {exc}")

    with MANIFEST_PATH.open("w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")

    print(
        f"  Done.  downloaded={downloaded}  cached={skipped}  errors={errors}  "
        f"manifest_size={len(manifest)}"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=_season_year(),
                        help="Season year to backfill (default: current)")
    parser.add_argument("--force", action="store_true",
                        help="Re-download every headshot even if already cached")
    args = parser.parse_args(argv)
    try:
        backfill(args.season, args.force)
    except RuntimeError as exc:
        print(f"backfill failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
