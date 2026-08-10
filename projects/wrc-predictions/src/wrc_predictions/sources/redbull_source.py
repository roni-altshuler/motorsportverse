"""WRC live results source — the official wrc.com data API.

wrc.com itself is Cloudflare-gated, but its React app reads a clean, public JSON
API hosted on Red Bull's platform (``p-p.redbull.com/rb-wrccom-lintegration-yv-prod``)
which serves without a challenge. This module is the thin client over it:

    seasons -> season-detail (calendar + championships) -> championship results

The premier **FIA World Rally Championship for Drivers** (championshipId 333) and
**for Manufacturers** (335) give, per driver/manufacturer, an ``overallPosition``
and a ``roundResults`` list carrying that entrant's finishing position and points
at every rally (``eventId``). Pivoting ``roundResults`` by ``eventId`` reconstructs
each rally's full classification — the "race result" the model consumes.

Rally has ONE scored classification per round (no sprint/qualifying), so a WRC
round is simpler than a circuit weekend: one venue, one result, driven by pace on
that rally's surface. Every GET is memoised on disk under ``WRC_HTTP_CACHE``.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://p-p.redbull.com/rb-wrccom-lintegration-yv-prod/api"
DRIVERS_CHAMP = "FIA World Rally Championship for Drivers"
MANUFACTURERS_CHAMP = "FIA World Rally Championship for Manufacturers"

_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def _cache_dir() -> Path:
    env = os.environ.get("WRC_HTTP_CACHE")
    return Path(env) if env else Path(__file__).resolve().parents[3] / ".http_cache"


class WrcApi:
    """Disk-cached client for the wrc.com (Red Bull-hosted) results API."""

    def __init__(self, *, cache_dir: Path | None = None, throttle: float = 0.15):
        self._cache = cache_dir or _cache_dir()
        self._cache.mkdir(parents=True, exist_ok=True)
        self._throttle = throttle
        self._last_net = 0.0

    def _get(self, path: str) -> object:
        url = f"{API_ROOT}{path}"
        key = path.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-")
        blob = self._cache / f"{key}.json"
        if blob.exists():
            try:
                return json.loads(blob.read_text(encoding="utf-8"))
            except Exception:
                blob.unlink(missing_ok=True)
        dt = time.monotonic() - self._last_net
        if dt < self._throttle:
            time.sleep(self._throttle - dt)
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=30) as r:
                    data = json.loads(r.read().decode("utf-8"))
                self._last_net = time.monotonic()
                blob.write_text(json.dumps(data), encoding="utf-8")
                return data
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (400, 404):
                    return None
                time.sleep(0.6 * (attempt + 1))
            except Exception as e:
                last_err = e
                time.sleep(0.6 * (attempt + 1))
        raise RuntimeError(f"WRC API GET failed after retries: {url} ({last_err})")

    # -- endpoints ------------------------------------------------------- #
    def seasons(self) -> list[dict]:
        return self._get("/seasons.json") or []

    def wrc_season_id(self, year: int) -> int | None:
        for s in self.seasons():
            if s.get("year") == year and s.get("name") == "World Rally Championship":
                return s.get("seasonId")
        return None

    def season_detail(self, season_id: int) -> dict:
        return self._get(f"/season-detail.json?seasonId={season_id}") or {}

    def championship_id(self, season_id: int, name: str) -> int | None:
        for c in self.season_detail(season_id).get("championships", []):
            if c.get("name") == name:
                return c.get("championshipId")
        return None

    def championship_detail(self, champ_id: int, season_id: int) -> dict:
        return self._get(
            f"/championship-detail.json?championshipId={champ_id}&seasonId={season_id}"
        ) or {}

    def championship_results(self, champ_id: int, season_id: int) -> dict:
        return self._get(
            f"/championship-overall-results.json?championshipId={champ_id}&seasonId={season_id}"
        ) or {}
