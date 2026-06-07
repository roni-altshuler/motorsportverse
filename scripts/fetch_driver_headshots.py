#!/usr/bin/env python3
"""
fetch_driver_headshots.py
=========================
Fetch the current season's driver headshots from openf1.org, convert each one
to a 192x192 WebP, and stash them under
``website/public/headshots/<NAME_ACRONYM>.webp``.  Also writes a manifest at
``data/driver_headshots.json`` mapping the 3-letter code to a website-relative
path (e.g. ``{"VER": "/headshots/VER.webp"}``).  The website's data writers
(``export_website_data.py``) load this manifest to populate ``headshotUrl`` on
``DriverInfo``, ``DriverStanding`` and ``ClassificationEntry`` JSON payloads.

Usage:
    python scripts/fetch_driver_headshots.py            # idempotent
    python scripts/fetch_driver_headshots.py --force    # re-download everything

Behaviour:
- Pulls https://api.openf1.org/v1/drivers?session_key=latest first.  If that
  returns nothing, falls back to the latest meeting_key for the current season.
- Skips any driver whose target file already exists unless ``--force`` is set.
- If openf1.org is unavailable, the script logs the error, leaves the existing
  manifest untouched, and exits non-zero (so CI can flag the issue) — the
  website continues to serve whatever headshots were committed previously.
"""
from __future__ import annotations

import argparse
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


# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_PUBLIC = PROJECT_ROOT / "website" / "public"
HEADSHOTS_DIR = WEBSITE_PUBLIC / "headshots"
DATA_DIR = PROJECT_ROOT / "data"
MANIFEST_PATH = DATA_DIR / "driver_headshots.json"

OPENF1_BASE = "https://api.openf1.org/v1"
USER_AGENT = "f1_predictions-headshot-fetcher/1.0 (+https://github.com/roni-altshuler/f1_predictions)"
HTTP_TIMEOUT = 20  # seconds
TARGET_SIZE = (192, 192)  # max W,H — preserves aspect ratio via thumbnail()
WEBP_QUALITY = 88


def _http_json(url: str) -> list | dict:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read()


def _fetch_drivers_for_session(session_key: str | int) -> list[dict]:
    """Return raw driver dicts from openf1 for a given session_key."""
    url = f"{OPENF1_BASE}/drivers?session_key={session_key}"
    data = _http_json(url)
    if not isinstance(data, list):
        return []
    return data


def _fetch_latest_meeting_drivers(season_year: int) -> list[dict]:
    """Fallback path: look up the most recent meeting in the season and grab
    its drivers (any session_key from that meeting will do)."""
    meetings = _http_json(f"{OPENF1_BASE}/meetings?year={season_year}")
    if not isinstance(meetings, list) or not meetings:
        return []
    # Pick the highest meeting_key (chronologically latest).
    meetings.sort(key=lambda m: m.get("meeting_key", 0), reverse=True)
    for meeting in meetings:
        meeting_key = meeting.get("meeting_key")
        if not meeting_key:
            continue
        sessions = _http_json(f"{OPENF1_BASE}/sessions?meeting_key={meeting_key}")
        if not isinstance(sessions, list) or not sessions:
            continue
        sessions.sort(key=lambda s: s.get("session_key", 0), reverse=True)
        for session in sessions:
            session_key = session.get("session_key")
            if not session_key:
                continue
            drivers = _fetch_drivers_for_session(session_key)
            if drivers:
                return drivers
    return []


def _dedupe_by_acronym(drivers: Iterable[dict]) -> dict[str, dict]:
    """Reduce multiple session entries per driver to one (the latest by
    session_key) keyed by ``name_acronym``."""
    by_code: dict[str, dict] = {}
    for drv in drivers:
        code = (drv.get("name_acronym") or "").strip().upper()
        if not code or len(code) != 3:
            continue
        existing = by_code.get(code)
        if existing is None:
            by_code[code] = drv
            continue
        # Prefer the entry with the higher session_key (latest session).
        if (drv.get("session_key") or 0) >= (existing.get("session_key") or 0):
            by_code[code] = drv
    return by_code


def _is_fallback_silhouette(url: str) -> bool:
    """True when an openf1 headshot_url is F1.com's generic silhouette.

    Cloudinary serves the placeholder via the ``d_driver_fallback_image.png``
    delivery directive when no real profile photo exists for a driver.
    """
    return "d_driver_fallback_image" in url or "driver_fallback_image" in url


def _convert_to_webp(raw: bytes, dest: Path) -> None:
    img = Image.open(io.BytesIO(raw))
    if img.mode not in {"RGB", "RGBA"}:
        img = img.convert("RGBA" if "A" in img.mode else "RGB")
    img.thumbnail(TARGET_SIZE, Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="WEBP", quality=WEBP_QUALITY, method=6)


def _season_year() -> int:
    raw = os.getenv("F1_SEASON_YEAR")
    if raw and raw.isdigit():
        return int(raw)
    # Cheap fallback — the season is well-known and stable.
    return 2026


def fetch_and_cache(force: bool = False) -> dict:
    """Main entry point.  Returns the manifest dict written to disk.

    Raises ``RuntimeError`` if openf1.org is unreachable so the caller (and
    CI) can decide what to do; in that case the existing manifest is left
    untouched.
    """
    HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Hit openf1.org for the driver list ──
    drivers: list[dict] = []
    try:
        drivers = _fetch_drivers_for_session("latest")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"  openf1 /drivers?session_key=latest failed: {exc}")

    if not drivers:
        season = _season_year()
        print(f"  Falling back to latest meeting for season {season}…")
        try:
            drivers = _fetch_latest_meeting_drivers(season)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"openf1.org unreachable: {exc}") from exc

    if not drivers:
        raise RuntimeError("openf1.org returned no drivers for any session")

    by_code = _dedupe_by_acronym(drivers)
    print(f"  Resolved {len(by_code)} unique drivers from openf1.")

    # ── 2. Load existing manifest (so partial runs still produce a complete map) ──
    manifest: dict[str, str] = {}
    if MANIFEST_PATH.exists():
        try:
            with MANIFEST_PATH.open() as f:
                manifest = json.load(f)
                if not isinstance(manifest, dict):
                    manifest = {}
        except (OSError, json.JSONDecodeError):
            manifest = {}

    downloaded = 0
    skipped = 0
    errors = 0

    # ── 3. Download / convert / cache each headshot ──
    for code, drv in sorted(by_code.items()):
        url = (drv.get("headshot_url") or "").strip()
        if not url:
            print(f"  [skip] {code}: no headshot_url")
            continue

        dest = HEADSHOTS_DIR / f"{code}.webp"

        # Some drivers (typically rookies whose profile photo hasn't been shot
        # yet, e.g. Lindblad) only have F1.com's generic silhouette, which
        # openf1 serves via Cloudinary's ``d_driver_fallback_image.png``
        # directive. Never let that clobber a curated headshot we've committed
        # by hand — skip it even under ``--force``.
        if _is_fallback_silhouette(url):
            if dest.exists():
                manifest[code] = f"/headshots/{code}.webp"
                skipped += 1
                print(f"  [keep] {code}: openf1 has only a fallback silhouette "
                      "— keeping existing curated headshot")
            else:
                print(f"  [skip] {code}: openf1 has only a fallback silhouette, "
                      "no curated headshot yet")
            continue

        if dest.exists() and not force:
            manifest[code] = f"/headshots/{code}.webp"
            skipped += 1
            continue

        try:
            raw = _http_bytes(url)
            _convert_to_webp(raw, dest)
            manifest[code] = f"/headshots/{code}.webp"
            downloaded += 1
            print(f"  [ok]   {code} -> {dest.name} ({len(raw) // 1024} KB src)")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            errors += 1
            print(f"  [err]  {code}: {exc}")

    # ── 4. Persist manifest (kept committed so the website builds without re-fetching) ──
    with MANIFEST_PATH.open("w") as f:
        json.dump(dict(sorted(manifest.items())), f, indent=2, sort_keys=True)
        f.write("\n")

    print(
        f"\nSummary: downloaded={downloaded}  skipped={skipped}  errors={errors}  "
        f"total_in_manifest={len(manifest)}  -> {MANIFEST_PATH.relative_to(PROJECT_ROOT)}"
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download every headshot even when a .webp already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        fetch_and_cache(force=args.force)
    except RuntimeError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        sys.stderr.write(
            "  Existing manifest at "
            f"{MANIFEST_PATH.relative_to(PROJECT_ROOT)} (if any) left untouched.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
