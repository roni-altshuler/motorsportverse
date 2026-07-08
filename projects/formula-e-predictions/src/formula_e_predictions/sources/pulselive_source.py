"""Formula E results from the official Pulselive API — the real live feed.

``api.formula-e.pulselive.com/formula-e/v1`` serves the championship's race
list, per-race sessions, per-session classifications, and standings with no
auth. This module wraps it behind the same source contract as the F3 project's
FIA scraper: honest User-Agent, self-throttled (~1 request/second), optional
disk cache for cheap backfill reruns, and a **wrong-event guard from day one**
(the F1 flagship shipped Austria's classification as the British GP result from
exactly the class of bug this guards against).

API facts (probed live 2026-07-07/08, samples committed as test fixtures):

* ``GET /races?size&page`` — paginated all-time race list (196 entries back to
  Beijing 2014). Test events ("Valencia Testing", rookie tests) live in a
  SEPARATE championship with ``seriesType: "FE_TESTS"`` — the same *name* as
  the points championship, so filtering must key on ``seriesType``, and round
  numbers must be derived from date-ordered points races, never ``sequence``.
* ``GET /races/{id}/sessions`` — sessions incl. "Race", "Combined qualifying",
  group/duel qualifying stages, and free practice.
* ``GET /races/{id}/sessions/{sid}/results`` — rows with ``driverPosition``
  (0 = unclassified), TLA, names, team, ``startingPosition``, ``polePosition``
  / ``fastestLap`` flags, dnf/dns/dsq/exc booleans, and ``points`` (bonuses
  included).
* ``GET /standings/drivers|teams?championshipId=`` — official standings with
  per-race progression.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "pulselive"

# Matches test/rookie events by name — belt to the seriesType suspenders.
_TEST_NAME = re.compile(r"test|rookie|pre-?season", re.IGNORECASE)

# Championship names look like "SEASON 2025-2026"; key = ENDING year.
_SEASON_NAME = re.compile(r"SEASON\s+(\d{4})-(\d{4})")


class WrongEventError(RuntimeError):
    """A fetched race's identity does not match the requested calendar entry.

    The API is fronted by a CDN and (like FastF1's fuzzy event matcher) could
    serve a different race's payload for a requested id, or the calendar could
    drift out of sync with the config. A race whose own metadata (date / city /
    championship) disagrees with what the caller asked for must never be
    ingested as that round's classification. Raising — rather than parsing the
    payload anyway — turns a wrong-event response into a refusal instead of a
    corrupted snapshot.
    """


def season_of_championship(champ: dict) -> int | None:
    """Ending-year season key for a championship dict, or None for tests/other."""
    series = (champ.get("series") or {}).get("seriesType")
    if series is not None and series != "FE_REGULAR":
        return None
    m = _SEASON_NAME.search(champ.get("name") or "")
    return int(m.group(2)) if m else None


class PulseliveClient:
    """Thin throttled/cached JSON GET layer over the Pulselive API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        cache_dir: Path | str | None = None,
        min_interval: float = 1.0,
        timeout: int = 30,
    ):
        self.base_url = (base_url or config.PULSELIVE_BASE_URL).rstrip("/")
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.min_interval = min_interval
        self.timeout = timeout
        self._last_request = 0.0

    # ------------------------------------------------------------------ #
    def _cache_path(self, key: str) -> Path | None:
        if self.cache_dir is None:
            return None
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
        return self.cache_dir / f"{safe}.json"

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get_json(self, path: str, *, cache_key: str | None = None, params: dict | None = None):
        """GET ``path`` (relative), preferring the disk cache when configured.

        Network failures return ``None`` — a failed live fetch is a no-op for
        callers, never bad data.
        """
        cp = self._cache_path(cache_key) if cache_key else None
        if cp is not None and cp.exists():
            try:
                return json.loads(cp.read_text(encoding="utf-8"))
            except Exception:
                pass  # unreadable cache entry → refetch
        try:
            import requests
        except ImportError:
            return None
        try:
            self._throttle()
            resp = requests.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params or {},
                headers={"User-Agent": config.PULSELIVE_USER_AGENT},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
        except Exception:
            return None
        if cp is not None and data is not None:
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return data

    # ------------------------------------------------------------------ #
    def all_races(self) -> list[dict] | None:
        """The full paginated race list (merged), or None when unreachable."""
        cp = self._cache_path("races")
        if cp is not None and cp.exists():
            try:
                return json.loads(cp.read_text(encoding="utf-8"))
            except Exception:
                pass
        races: list[dict] = []
        page = 0
        while True:
            data = self.get_json("/races", params={"size": 100, "page": page})
            if not data or "races" not in data:
                return None
            races.extend(data["races"])
            info = data.get("pageInfo") or {}
            if page >= int(info.get("numPages", 1)) - 1:
                break
            page += 1
        if cp is not None:
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(races, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return races

    def sessions(self, race_id: str) -> list[dict] | None:
        data = self.get_json(f"/races/{race_id}/sessions", cache_key=f"race_{race_id}_sessions")
        return data.get("sessions") if isinstance(data, dict) else None

    def session_results(self, race_id: str, session_id: str) -> list[dict] | None:
        data = self.get_json(
            f"/races/{race_id}/sessions/{session_id}/results",
            cache_key=f"race_{race_id}_session_{session_id}_results",
        )
        return data if isinstance(data, list) else None

    def driver_standings(self, championship_id: str) -> list[dict] | None:
        data = self.get_json(
            "/standings/drivers",
            cache_key=f"standings_drivers_{championship_id}",
            params={"championshipId": championship_id},
        )
        return data if isinstance(data, list) else None

    def team_standings(self, championship_id: str) -> list[dict] | None:
        data = self.get_json(
            "/standings/teams",
            cache_key=f"standings_teams_{championship_id}",
            params={"championshipId": championship_id},
        )
        return data if isinstance(data, list) else None


# --------------------------------------------------------------------------- #
# Race-list interpretation (pure functions — unit-tested offline on fixtures)
# --------------------------------------------------------------------------- #
def points_races(races: list[dict], season: int) -> list[dict]:
    """The season's points races, date-ordered — index+1 IS the round number.

    Filters to the season's FE_REGULAR championship (test events live in a
    separate FE_TESTS championship that shares the season *name*, so the filter
    keys on ``seriesType``; a name-pattern check backstops feeds that omit the
    series block). ``sequence`` is per-championship and counts differently for
    tests, so ordering is strictly by date (then sequence for doubleheaders
    sharing a date-string, which does not happen today but costs nothing).
    """
    picked = [
        r
        for r in races
        if season_of_championship(r.get("championship") or {}) == season
        and not _TEST_NAME.search(r.get("name") or "")
    ]
    picked.sort(key=lambda r: (str(r.get("date") or ""), int(r.get("sequence") or 0)))
    return picked


def verify_race_identity(race: dict, *, round: int, expected: dict) -> None:
    """Assert a race dict matches the round's expected calendar identity.

    ``expected`` carries any of ``date`` / ``city`` / ``season`` (from the
    human-verified config calendar or a snapshot's calendar). A mismatch — or a
    race with no identity at all — raises :class:`WrongEventError` so a wrong
    event can never be ingested as this round's data.
    """
    if not race or not race.get("id"):
        raise WrongEventError(f"round {round}: race payload has no identity")
    exp_date = expected.get("date")
    if exp_date and str(race.get("date") or "")[:10] != str(exp_date)[:10]:
        raise WrongEventError(
            f"round {round}: expected race date {exp_date}, got {race.get('date')!r} "
            f"({race.get('name')!r})"
        )
    exp_city = expected.get("city")
    if exp_city and (race.get("city") or "").strip().lower() != str(exp_city).strip().lower():
        raise WrongEventError(
            f"round {round}: expected city {exp_city!r}, got {race.get('city')!r} "
            f"({race.get('name')!r})"
        )
    exp_season = expected.get("season")
    if exp_season:
        got = season_of_championship(race.get("championship") or {})
        if got != int(exp_season):
            raise WrongEventError(
                f"round {round}: expected season {exp_season}, got {got} "
                f"({race.get('name')!r})"
            )


def _status_of(row: dict) -> str:
    if row.get("dsq"):
        return "DSQ"
    if row.get("dns"):
        return "DNS"
    if row.get("dnq"):
        return "DNQ"
    if row.get("exc"):
        return "EXC"
    if row.get("dnf"):
        return "DNF"
    return "Finished"


def parse_race_rows(rows: list[dict]) -> list[dict]:
    """API result rows → snapshot-shaped rows (classified first, then DNFs).

    ``driverPosition`` 0 marks an unclassified entrant; those rows keep
    ``position: None`` with a status so entry lists and DNF modelling survive.
    Team names are normalised through ``config.TEAM_ALIASES``.
    """
    out: list[dict] = []
    for row in rows:
        team_raw = ((row.get("team") or {}).get("name") or "").strip()
        pos = int(row.get("driverPosition") or 0)
        first = (row.get("driverFirstName") or "").strip()
        last = (row.get("driverLastName") or "").strip()
        out.append(
            {
                "position": pos if pos > 0 else None,
                "code": (row.get("driverTLA") or "").strip().upper(),
                "name": (f"{first} {last}").strip(),
                "team": config.TEAM_ALIASES.get(team_raw, team_raw),
                "grid": int(row["startingPosition"]) if row.get("startingPosition") else None,
                "status": _status_of(row),
                "points": float(row.get("points") or 0.0),
                "pole": bool(row.get("polePosition")),
                "fastestLap": bool(row.get("fastestLap")),
            }
        )
    out.sort(key=lambda r: (r["position"] is None, r["position"] or 0))
    return out


def _find_session(sessions: list[dict], name: str) -> dict | None:
    for s in sessions:
        if (s.get("sessionName") or "").strip().lower() == name.lower():
            return s
    return None


# --------------------------------------------------------------------------- #
# The live source behind the DataSource seam
# --------------------------------------------------------------------------- #
class PulseliveFESource:
    """Live FE results source. Answers ``None`` on any failure (defer to the
    next source in the composite) and ``[]`` for a known round that has not
    been run — never fabricated data."""

    name = SOURCE_NAME

    def __init__(self, *, client: PulseliveClient | None = None, cache_dir: Path | None = None):
        self._client = client or PulseliveClient(cache_dir=cache_dir)
        self._season_races: dict[int, list[dict]] = {}

    # ------------------------------------------------------------------ #
    def season_races(self, year: int) -> list[dict] | None:
        """Date-ordered points races for a season (round = index + 1)."""
        if year not in self._season_races:
            races = self._client.all_races()
            if races is None:
                return None
            picked = points_races(races, year)
            # Wrong-season guard on the pinned anchor: the config's verified
            # championship id must agree with what the list serves.
            pinned = config.CHAMPIONSHIP_IDS.get(year)
            if pinned and picked:
                got = {(r.get("championship") or {}).get("id") for r in picked}
                if got != {pinned}:
                    raise WrongEventError(
                        f"season {year}: championship id mismatch — expected {pinned}, got {got}"
                    )
            self._season_races[year] = picked
        return self._season_races[year]

    def _race_for_round(self, year: int, round: int) -> dict | None:
        races = self.season_races(year)
        if races is None or not (1 <= round <= len(races)):
            return None
        race = races[round - 1]
        # Cross-check against the human-verified config calendar for the active
        # season (independent of the API's own ordering).
        if year == config.SEASON and round in config.CALENDAR_META:
            verify_race_identity(
                race,
                round=round,
                expected={"date": config.CALENDAR_META[round].get("date"), "season": year},
            )
        return race

    # ------------------------------------------------------------------ #
    def results(self, year: int, round: int, race_index: int = 0) -> list[Result] | None:
        """Classified order for a round's race; ``[]`` = not run yet; ``None`` =
        this source cannot answer (network down / unknown round)."""
        race = self._race_for_round(year, round)
        if race is None:
            return None
        if not race.get("hasRaceResults"):
            return []
        rows = self.race_rows(year, round)
        if rows is None:
            return None
        classified = [r for r in rows if r["position"]]
        if not classified:
            return None
        return [
            Result(
                competitor=r["code"],
                position=r["position"],
                grid=r["grid"],
                status=r["status"],
                points=r["points"],
            )
            for r in classified
        ]

    def race_rows(self, year: int, round: int) -> list[dict] | None:
        """Full snapshot-shaped rows (classified + DNFs) for a round's race."""
        race = self._race_for_round(year, round)
        if race is None:
            return None
        sessions = self._client.sessions(race["id"])
        if not sessions:
            return None
        race_session = _find_session(sessions, "Race")
        if race_session is None or not race_session.get("hasResults"):
            return None
        rows = self._client.session_results(race["id"], race_session["id"])
        if not rows:
            return None
        return parse_race_rows(rows)

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """Combined-qualifying classification (P1 first), or None when absent."""
        race = self._race_for_round(year, round)
        if race is None:
            return None
        sessions = self._client.sessions(race["id"])
        if not sessions:
            return None
        quali = _find_session(sessions, "Combined qualifying")
        if quali is None or not quali.get("hasResults"):
            return None
        rows = self._client.session_results(race["id"], quali["id"])
        if not rows:
            return None
        ordered = sorted(
            (r for r in rows if int(r.get("driverPosition") or 0) > 0),
            key=lambda r: int(r["driverPosition"]),
        )
        order = [(r.get("driverTLA") or "").strip().upper() for r in ordered]
        return order or None

    # ------------------------------------------------------------------ #
    def driver_standings(self, year: int) -> list[dict] | None:
        cid = self._championship_id(year)
        return self._client.driver_standings(cid) if cid else None

    def team_standings(self, year: int) -> list[dict] | None:
        cid = self._championship_id(year)
        return self._client.team_standings(cid) if cid else None

    def _championship_id(self, year: int) -> str | None:
        if year in config.CHAMPIONSHIP_IDS:
            return config.CHAMPIONSHIP_IDS[year]
        races = self.season_races(year)
        if races:
            return (races[0].get("championship") or {}).get("id")
        return None
