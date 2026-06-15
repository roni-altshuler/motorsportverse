"""Shared Jolpica/Ergast client for open-wheel series.

Jolpica (https://api.jolpi.ca/ergast/) is the maintained successor to the
deprecated Ergast API. It primarily serves Formula 1; this client is written
series-parameterised so future open-wheel categories that expose an
Ergast-compatible endpoint can reuse it unchanged. For series without an
Ergast feed (F2/F3 telemetry, NASCAR, etc.), implement a dedicated
:class:`~motorsport_data.sources.base.DataSource` instead.

``requests`` is an optional dependency — construct :class:`JolpicaClient` only
when it's installed (``pip install requests``).
"""
from __future__ import annotations

import time

from ..schema import Result, Round, Season, Venue

BASE_URL = "https://api.jolpi.ca/ergast"

# Jolpica soft limits: ~4 req/sec, 500 req/hour. We self-throttle conservatively.
_MIN_INTERVAL_S = 0.25


class JolpicaClient:
    """Rate-limited Ergast/Jolpica client returning canonical schema objects."""

    def __init__(self, series: str = "f1", sport: str = "Formula 1", base_url: str = BASE_URL):
        try:
            import requests  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError("JolpicaClient requires requests — `pip install requests`") from exc
        import requests

        self.series = series
        self.sport = sport
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._last_request = 0.0

    # ------------------------------------------------------------------ #
    def _get(self, path: str) -> dict:
        elapsed = time.monotonic() - self._last_request
        if elapsed < _MIN_INTERVAL_S:
            time.sleep(_MIN_INTERVAL_S - elapsed)
        url = f"{self.base_url}/{self.series}/{path}"
        resp = self._session.get(url, timeout=30)
        self._last_request = time.monotonic()
        resp.raise_for_status()
        return resp.json()["MRData"]

    # ------------------------------------------------------------------ #
    def season(self, year: int) -> Season:
        data = self._get(f"{year}/races/?limit=100")
        races = data.get("RaceTable", {}).get("Races", [])
        calendar = [
            Venue(
                key=_slug(r["Circuit"]["circuitId"]),
                name=r["raceName"],
                country=r["Circuit"]["Location"].get("country"),
            )
            for r in races
        ]
        return Season(sport=self.sport, year=year, calendar=calendar)

    def results(self, year: int, round: int) -> list[Result]:
        data = self._get(f"{year}/{round}/results/?limit=100")
        races = data.get("RaceTable", {}).get("Races", [])
        if not races:
            return []  # round not yet run / no data published
        out: list[Result] = []
        for res in races[0].get("Results", []):
            out.append(
                Result(
                    competitor=res["Driver"]["code"]
                    if "code" in res["Driver"]
                    else res["Driver"]["driverId"],
                    position=int(res["position"]) if res.get("position") else None,
                    grid=int(res["grid"]) if res.get("grid") else None,
                    status=res.get("status"),
                    points=float(res["points"]) if res.get("points") else None,
                )
            )
        return out

    def round(self, year: int, round: int) -> Round:
        season = self.season(year)
        idx = round - 1
        venue = season.calendar[idx] if 0 <= idx < len(season.calendar) else Venue(
            key=f"round-{round}", name=f"Round {round}"
        )
        results = self.results(year, round)
        return Round(
            season=year,
            round=round,
            venue=venue,
            completed=bool(results),
            results=results,
        )


def _slug(value: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in value).strip("-")


__all__ = ["JolpicaClient", "BASE_URL"]
