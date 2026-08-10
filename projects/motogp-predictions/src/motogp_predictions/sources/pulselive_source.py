"""MotoGP live results source — the official pulselive results API.

MotoGP is not served by Jolpica/Ergast or the FIA CMS, but it publishes a
public results API on the same Pulselive platform Formula E uses
(``api.motogp.pulselive.com``). This module is the thin client that walks

    seasons → events (calendar) → sessions (per category) → classification

and maps the premier **MotoGP class** onto the canonical
:class:`motorsport_data.schema.Result` shape (rider → competitor, manufacturer →
team/constructor, Grand Prix race → feature, Sprint → sprint, Q2+Q1 → grid).

The client is offline-cacheable: every GET is memoised on disk under
``MOTOGP_HTTP_CACHE`` (default: the project's ``.http_cache``) so the snapshot
builder is re-runnable without hammering the API, and a completed pull is fully
reproducible. Downstream builds/tests never call this — they read the committed
snapshot produced by :mod:`motogp_predictions.build_snapshot`.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://api.motogp.pulselive.com/motogp/v1/results"
PREMIER_CATEGORY = "MotoGP™"

# Session ``type`` codes in the API (verified against 2024 payloads):
#   FP/PR/P  practice · Q  qualifying (number 1|2) · SPR  sprint · WUP  warm-up
#   RAC  the Grand Prix race
_RACE_TYPE = "RAC"
_SPRINT_TYPE = "SPR"
_QUALI_TYPE = "Q"

_UA = {"User-Agent": "MotorsportVerse/1.0 (research; +https://github.com)"}


def _cache_dir() -> Path:
    env = os.environ.get("MOTOGP_HTTP_CACHE")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / ".http_cache"


class MotoGPApi:
    """Disk-cached client for the MotoGP results API."""

    def __init__(self, *, cache_dir: Path | None = None, throttle: float = 0.15):
        self._cache = cache_dir or _cache_dir()
        self._cache.mkdir(parents=True, exist_ok=True)
        self._throttle = throttle
        self._last_net = 0.0

    # -- low-level ------------------------------------------------------- #
    def _get(self, url: str) -> object:
        key = url.replace("https://", "").replace("/", "_").replace("?", "_").replace("&", "_")
        blob = self._cache / f"{key}.json"
        if blob.exists():
            try:
                return json.loads(blob.read_text(encoding="utf-8"))
            except Exception:
                blob.unlink(missing_ok=True)
        # polite throttle between real network hits
        dt = time.monotonic() - self._last_net
        if dt < self._throttle:
            time.sleep(self._throttle - dt)
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers=_UA)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self._last_net = time.monotonic()
                blob.write_text(json.dumps(data), encoding="utf-8")
                return data
            except urllib.error.HTTPError as e:  # noqa: PERF203
                last_err = e
                if e.code in (404, 400):
                    return None
                time.sleep(0.6 * (attempt + 1))
            except Exception as e:
                last_err = e
                time.sleep(0.6 * (attempt + 1))
        raise RuntimeError(f"MotoGP API GET failed after retries: {url} ({last_err})")

    # -- endpoints ------------------------------------------------------- #
    def seasons(self) -> list[dict]:
        return self._get(f"{API_ROOT}/seasons") or []

    def season_uuid(self, year: int) -> str | None:
        for s in self.seasons():
            if s.get("year") == year:
                return s.get("id")
        return None

    def categories(self, season_uuid: str) -> list[dict]:
        return self._get(f"{API_ROOT}/categories?seasonUuid={season_uuid}") or []

    def premier_category_uuid(self, season_uuid: str) -> str | None:
        for c in self.categories(season_uuid):
            if c.get("name") == PREMIER_CATEGORY:
                return c.get("id")
        return None

    def events(self, season_uuid: str, *, finished_only: bool = True) -> list[dict]:
        url = f"{API_ROOT}/events?seasonUuid={season_uuid}"
        if finished_only:
            url += "&isFinished=true"
        events = self._get(url) or []
        # real Grands Prix only (drop pre-season tests), ordered by date
        events = [e for e in events if not e.get("test")]
        events.sort(key=lambda e: e.get("date_start") or e.get("date_end") or "")
        return events

    def sessions(self, event_uuid: str, category_uuid: str) -> list[dict]:
        url = f"{API_ROOT}/sessions?eventUuid={event_uuid}&categoryUuid={category_uuid}"
        return self._get(url) or []

    def classification(self, session_uuid: str) -> list[dict]:
        url = f"{API_ROOT}/session/{session_uuid}/classification?test=false"
        data = self._get(url)
        if isinstance(data, dict):
            return data.get("classification", []) or []
        return data or []


# --------------------------------------------------------------------------- #
# Canonical mapping helpers
# --------------------------------------------------------------------------- #
def _pick_sessions(sessions: list[dict]) -> dict[str, dict]:
    """Reduce a category's session list to the ones we ingest.

    Returns ``{'race': s, 'sprint': s, 'q1': s, 'q2': s}`` (missing keys omitted).
    Qualifying is split across two sessions (``number`` 1 and 2); the sprint and
    race are singletons.
    """
    picked: dict[str, dict] = {}
    for s in sessions:
        typ = s.get("type")
        if typ == _RACE_TYPE:
            picked["race"] = s
        elif typ == _SPRINT_TYPE:
            picked["sprint"] = s
        elif typ == _QUALI_TYPE:
            num = s.get("number")
            picked[f"q{num}"] = s
    return picked


def rider_surname(full_name: str) -> str:
    return (full_name or "").strip().split(" ")[-1] if full_name else ""
