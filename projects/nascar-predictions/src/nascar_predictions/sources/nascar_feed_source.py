"""NASCAR Cup results from the official cf.nascar.com cacher feeds.

``https://cf.nascar.com/cacher`` serves season race lists and per-race weekend
feeds with no auth. This module wraps them behind the same source contract as
the FE project's Pulselive client: honest User-Agent, self-throttled (~1
request/second), optional disk cache for cheap backfill reruns, and a
**wrong-event guard from day one** (the F1 flagship shipped Austria's
classification as the British GP result from exactly the class of bug this
guards against).

API facts (probed live 2026-07-07/08, samples committed as test fixtures):

* ``GET {CACHER}/{year}/race_list_basic.json`` — dict of ``series_1`` (Cup),
  ``series_2``, ``series_3``. Per race: ``race_id``, ``race_type_id``
  (**1 = points race** — everything else is the Clash / Duels / All-Star and
  must be filtered), ``race_name``, ``track_name``, ``race_date``,
  ``stage_N_laps``, plus post-race stats. Round number = date order of the
  points races. History available from ~2013.
* ``GET {CACHER}/{year}/{series}/{race_id}/weekend-feed.json`` —
  ``weekend_race[0]`` metadata + ``results[]`` (finishing/starting position,
  driver/team/make, points_earned, playoff_points_earned, laps_led,
  finishing_status), ``stage_results[]`` (per-stage top-10 with stage points),
  and ``weekend_runs[]`` (practice ``run_type`` 1 / qualifying ``run_type`` 2).
* **A future race's weekend feed returns a fully pre-seeded entry list**
  (positions filled, ``finishing_status`` empty, points 0) — completion must
  key on non-empty ``finishing_status``, never on ``results`` being non-empty.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "nascar-feed"

#: race_type_id of a points race in the race list (Clash/Duels/All-Star are 2+).
POINTS_RACE_TYPE = 1


class WrongEventError(RuntimeError):
    """A fetched race's identity does not match the requested calendar entry.

    The cacher is a CDN-fronted JSON store; a stale edge, a race_id typo, or a
    calendar drifting out of sync with the config could serve a different
    race's payload for a requested round. A race whose own metadata (race_id /
    date / track) disagrees with what the caller asked for must never be
    ingested as that round's classification. Raising — rather than parsing the
    payload anyway — turns a wrong-event response into a refusal instead of a
    corrupted snapshot.
    """


class NascarCacherClient:
    """Thin throttled/cached JSON GET layer over the cf.nascar.com cacher."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        cache_dir: Path | str | None = None,
        min_interval: float = 1.0,
        timeout: int = 30,
    ):
        self.base_url = (base_url or config.CACHER_BASE_URL).rstrip("/")
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

    def get_json(self, path: str, *, cache_key: str | None = None):
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
                headers={"User-Agent": config.NASCAR_USER_AGENT},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
        except Exception:
            return None
        if cp is not None and data is not None:
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
        return data

    # ------------------------------------------------------------------ #
    def race_list(self, year: int) -> dict | None:
        data = self.get_json(f"/{year}/race_list_basic.json", cache_key=f"race_list_{year}")
        return data if isinstance(data, dict) else None

    def weekend_feed(self, year: int, race_id: int, series: int | None = None) -> dict | None:
        series = series or config.CUP_SERIES_ID
        data = self.get_json(
            f"/{year}/{series}/{race_id}/weekend-feed.json",
            cache_key=f"weekend_{year}_{race_id}",
        )
        return data if isinstance(data, dict) else None


# --------------------------------------------------------------------------- #
# Race-list / weekend-feed interpretation (pure functions — unit-tested
# offline on fixtures)
# --------------------------------------------------------------------------- #
def points_races(race_list: dict, series: int | None = None) -> list[dict]:
    """The season's Cup points races, date-ordered — index+1 IS the round number.

    Filters ``race_type_id == 1`` (the Clash, the Duels and the All-Star race
    live in the same list with other type ids and must never count as rounds).
    """
    series = series or config.CUP_SERIES_ID
    races = list((race_list or {}).get(f"series_{series}") or [])
    picked = [r for r in races if int(r.get("race_type_id") or 0) == POINTS_RACE_TYPE]
    picked.sort(key=lambda r: (str(r.get("race_date") or ""), int(r.get("race_id") or 0)))
    return picked


def verify_race_identity(
    race_meta: dict, *, round: int, expected: dict, date_tolerance_days: int = 0
) -> None:
    """Assert a weekend-feed race block matches the round's expected identity.

    ``expected`` carries any of ``raceId`` / ``date`` (YYYY-MM-DD) / ``track``
    (from the human-verified config calendar or the race list). A mismatch —
    or a race with no identity at all — raises :class:`WrongEventError` so a
    wrong event can never be ingested as this round's data.

    ``date_tolerance_days`` allows a bounded date drift: rain-delayed races
    carry the RESCHEDULED date in the race list but the original date in the
    weekend feed (verified on the 2020 Daytona 500, Sunday → Monday), so the
    race-list ↔ weekend-feed cross-check needs slack while the config-calendar
    check stays exact.
    """
    if not race_meta or not race_meta.get("race_id"):
        raise WrongEventError(f"round {round}: race payload has no identity")
    exp_id = expected.get("raceId")
    if exp_id and int(race_meta.get("race_id") or 0) != int(exp_id):
        raise WrongEventError(
            f"round {round}: expected race_id {exp_id}, got {race_meta.get('race_id')!r} "
            f"({race_meta.get('race_name')!r})"
        )
    exp_date = expected.get("date")
    got_date = str(race_meta.get("race_date") or "")[:10]
    if exp_date and got_date != str(exp_date)[:10]:
        drift = None
        try:
            from datetime import date

            a = date.fromisoformat(str(exp_date)[:10])
            b = date.fromisoformat(got_date)
            drift = abs((a - b).days)
        except ValueError:
            pass
        if drift is None or drift > date_tolerance_days:
            raise WrongEventError(
                f"round {round}: expected race date {exp_date}, got "
                f"{race_meta.get('race_date')!r} ({race_meta.get('race_name')!r})"
            )
    exp_track = expected.get("track")
    if exp_track:
        got = (race_meta.get("track_name") or "").strip().lower()
        if got != str(exp_track).strip().lower():
            raise WrongEventError(
                f"round {round}: expected track {exp_track!r}, got "
                f"{race_meta.get('track_name')!r} ({race_meta.get('race_name')!r})"
            )


def race_is_complete(rows: list[dict]) -> bool:
    """True when the results rows carry a real classification.

    A FUTURE race's weekend feed returns a fully pre-seeded entry list with
    positions filled but every ``finishing_status`` empty and 0 points — so
    completion keys on the status field, never on ``results`` being non-empty.
    """
    return any((r.get("finishing_status") or "").strip() for r in rows or [])


def _status_of(row: dict) -> str:
    if row.get("disqualified"):
        return "Disqualified"
    return (row.get("finishing_status") or "").strip() or "Unknown"


def is_dnf_status(status: str | None) -> bool:
    """NASCAR classifies every car; a non-'Running' status is a retirement."""
    return (status or "").strip().lower() not in {"running", ""}


def parse_result_rows(rows: list[dict]) -> list[dict]:
    """Weekend-feed result rows → snapshot-shaped rows (classified order).

    Every car is classified in NASCAR (retirees keep a finishing position),
    so ``position`` is always set; ``status`` + ``dnf`` carry the attrition
    signal the model's hazard head consumes.
    """
    out: list[dict] = []
    for row in rows or []:
        status = _status_of(row)
        out.append(
            {
                "position": int(row.get("finishing_position") or 0) or None,
                "code": config.driver_code(row.get("driver_fullname") or ""),
                "name": (row.get("driver_fullname") or "").strip(),
                "team": (row.get("team_name") or "").strip(),
                "make": (row.get("car_make") or "").strip(),
                "grid": int(row["starting_position"]) if row.get("starting_position") else None,
                "status": status,
                "dnf": is_dnf_status(status),
                "points": float(row.get("points_earned") or 0.0),
                "playoffPoints": float(row.get("playoff_points_earned") or 0.0),
                "lapsLed": int(row.get("laps_led") or 0),
                "lapsCompleted": int(row.get("laps_completed") or 0),
                # Official points-standings position AFTER this race — the
                # ground truth the playoff backtest validates its
                # reconstruction (field, champion) against.
                "pointsPosition": int(row.get("points_position") or 0),
            }
        )
    out.sort(key=lambda r: (r["position"] is None, r["position"] or 0))
    return out


def parse_stage_results(weekend_race: dict) -> dict[str, list[dict]]:
    """``stage_results`` → {"1": [{code, name, position, points}], "2": ...}.

    The weekend feed carries the per-stage top-10 with stage points directly —
    no approximation needed. Empty dict when the feed has no stage data
    (pre-2017 shapes / road-course exceptions).
    """
    out: dict[str, list[dict]] = {}
    for stage in weekend_race.get("stage_results") or []:
        num = stage.get("stage_number")
        rows = []
        for r in stage.get("results") or []:
            rows.append(
                {
                    "code": config.driver_code(r.get("driver_fullname") or ""),
                    "name": (r.get("driver_fullname") or "").strip(),
                    "position": int(r.get("finishing_position") or 0),
                    "points": float(r.get("stage_points") or 0.0),
                }
            )
        if num is not None and rows:
            out[str(int(num))] = sorted(rows, key=lambda r: r["position"])
    return out


def parse_qualifying(weekend_feed: dict) -> list[str] | None:
    """Qualifying order (P1 first) from ``weekend_runs`` (run_type 2), or None."""
    runs = [r for r in weekend_feed.get("weekend_runs") or [] if int(r.get("run_type") or 0) == 2]
    if not runs:
        return None
    rows = sorted(
        (r for r in runs[-1].get("results") or [] if r.get("finishing_position")),
        key=lambda r: int(r["finishing_position"]),
    )
    order = [config.driver_code(r.get("driver_name") or "") for r in rows]
    return order or None


# --------------------------------------------------------------------------- #
# The live source behind the DataSource seam
# --------------------------------------------------------------------------- #
class NascarFeedSource:
    """Live NASCAR results source. Answers ``None`` on any failure (defer to
    the next source in the composite) and ``[]`` for a known round that has
    not been run — never fabricated data."""

    name = SOURCE_NAME

    def __init__(self, *, client: NascarCacherClient | None = None, cache_dir: Path | None = None):
        self._client = client or NascarCacherClient(cache_dir=cache_dir)
        self._season_races: dict[int, list[dict] | None] = {}
        self._weekend: dict[tuple[int, int], dict | None] = {}

    # ------------------------------------------------------------------ #
    def season_races(self, year: int) -> list[dict] | None:
        """Date-ordered Cup points races for a season (round = index + 1).

        Wrong-season guard: the cacher answers ``/{year}/race_list_basic.json``
        for years before its archive floor with the EARLIEST season it has
        (verified live: ``/2017/`` serves the 2018 list), so every race's own
        ``race_season`` must equal the requested year or the season is treated
        as unavailable — 2018's results must never be ingested twice as 2017.
        """
        if year not in self._season_races:
            race_list = self._client.race_list(year)
            picked = points_races(race_list) if race_list is not None else None
            if picked and any(int(r.get("race_season") or 0) != year for r in picked):
                picked = None
            self._season_races[year] = picked or None
        return self._season_races[year]

    def _race_for_round(self, year: int, round: int) -> dict | None:
        races = self.season_races(year)
        if races is None or not (1 <= round <= len(races)):
            return None
        race = races[round - 1]
        # Cross-check against the human-verified config calendar for the
        # active season (independent of the API's own ordering).
        if year == config.SEASON and round in config.CALENDAR_META:
            meta = config.CALENDAR_META[round]
            verify_race_identity(
                race,
                round=round,
                expected={
                    "raceId": meta.get("raceId"),
                    "date": meta.get("date"),
                    "track": meta.get("track"),
                },
            )
        return race

    def _weekend_feed(self, year: int, round: int) -> dict | None:
        """The round's verified weekend feed, or None."""
        key = (year, round)
        if key in self._weekend:
            return self._weekend[key]
        race = self._race_for_round(year, round)
        if race is None:
            self._weekend[key] = None
            return None
        feed = self._client.weekend_feed(year, int(race["race_id"]))
        wr = (feed or {}).get("weekend_race") or []
        if not feed or not wr:
            # transient failure — do NOT cache, a retry may succeed
            return None
        # Wrong-event guard: the weekend feed's own race block must agree with
        # the race-list entry we resolved the round to. Date tolerance covers
        # rain delays (list carries the rescheduled date, feed the original).
        verify_race_identity(
            wr[0],
            round=round,
            expected={
                "raceId": race.get("race_id"),
                "date": race.get("race_date"),
                "track": race.get("track_name"),
            },
            date_tolerance_days=5,
        )
        self._weekend[key] = feed
        return feed

    # ------------------------------------------------------------------ #
    def results(self, year: int, round: int, race_index: int = 0) -> list[Result] | None:
        """Classified order for a round's race; ``[]`` = not run yet; ``None``
        = this source cannot answer (network down / unknown round)."""
        rows = self.race_rows(year, round)
        if rows is None:
            feed = self._weekend_feed(year, round)
            if feed is None:
                return None
            return []
        return [
            Result(
                competitor=r["code"],
                position=r["position"],
                grid=r["grid"],
                status=r["status"],
                points=r["points"],
            )
            for r in rows
            if r["position"]
        ]

    def race_rows(self, year: int, round: int) -> list[dict] | None:
        """Full snapshot-shaped rows for a COMPLETED round's race, or None.

        ``None`` covers both "cannot answer" and "not complete yet" — the
        caller distinguishes via :meth:`results` returning ``[]``.
        """
        feed = self._weekend_feed(year, round)
        if feed is None:
            return None
        wr = feed["weekend_race"][0]
        raw = wr.get("results") or []
        if not race_is_complete(raw):
            return None
        return parse_result_rows(raw)

    def stage_results(self, year: int, round: int) -> dict[str, list[dict]] | None:
        feed = self._weekend_feed(year, round)
        if feed is None:
            return None
        wr = feed["weekend_race"][0]
        if not race_is_complete(wr.get("results") or []):
            return None
        return parse_stage_results(wr)

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """Qualifying order (P1 first) for a round, or ``None`` if not run.

        Works pre-race too (the upcoming round's weekend feed carries the
        qualifying run once it happens) — drives the post-quali forecast.
        """
        feed = self._weekend_feed(year, round)
        if feed is None:
            return None
        return parse_qualifying(feed)

    def entry_list(self, year: int, round: int) -> list[str] | None:
        """Pre-race entry list for an UPCOMING round, or None.

        A future race's weekend feed serves a pre-seeded results array
        (statuses empty) — that IS the entry list.
        """
        feed = self._weekend_feed(year, round)
        if feed is None:
            return None
        raw = feed["weekend_race"][0].get("results") or []
        if not raw or race_is_complete(raw):
            return None
        return [config.driver_code(r.get("driver_fullname") or "") for r in raw]
