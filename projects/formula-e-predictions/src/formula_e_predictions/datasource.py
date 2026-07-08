"""FE data source — calendar/roster from config + snapshots, results from a
selectable feed.

Implements the shared ``motorsport_data.sources.base.DataSource`` contract.
The active season's calendar and roster come from :mod:`config`; archived
seasons resolve their calendar/roster from the per-season snapshots written by
:mod:`backfill` (``data/seasons/<year>.json``) so the historical backtest can
replay real past seasons with the real grids of the time. The *results* come
from a source selected at construction:

- default (``FE_USE_LIVE_RESULTS`` unset/``"0"``): the **real** committed
  snapshots for completed rounds, with the deterministic synthetic generator
  behind them — offline and reproducible, so CI/tests stay deterministic while
  shipping real data;
- live (``FE_USE_LIVE_RESULTS="1"``): a :class:`CompositeFESource` that hits
  the Pulselive API first, then the snapshot, then synthetic.

The set of *completed* rounds is **derived from the feed** (the leading run of
rounds that actually return results), not a hardcoded constant. Tests can
inject a source directly via ``FEDataSource(source=...)``.
"""
from __future__ import annotations

import os

from motorsport_data.schema import Competitor, Result, Round, Season, Venue
from motorsport_data.sources.base import DataSource

from . import config
from .sources import CompositeFESource


def _live_enabled() -> bool:
    return os.getenv("FE_USE_LIVE_RESULTS", "0") == "1"


class FEDataSource(DataSource):
    sport = config.SPORT

    def __init__(self, *, live: bool | None = None, source=None):
        if source is not None:
            self._source = source
        elif _live_enabled() if live is None else live:
            self._source = CompositeFESource.live()
        else:
            self._source = CompositeFESource.default()
        self._completed_cache: dict[int, list[int]] = {}
        self._roster_cache: dict[int, list[dict]] = {}

    # ------------------------------------------------------------------ #
    def total_rounds(self, year: int = config.SEASON) -> int:
        """Rounds in the season's calendar (config for the active season,
        snapshot for archived ones; falls back to the completed count)."""
        if year == config.SEASON:
            return len(config.CALENDAR)
        cal = self._snapshot_calendar(year)
        if cal:
            return len(cal)
        return len(self.completed_rounds(year))

    def completed_rounds(self, year: int = config.SEASON) -> list[int]:
        """Rounds with published results — the leading run of scored rounds.

        Derived from the feed: a round counts as completed once its race
        returns a non-empty classification. FE rounds complete in date order,
        so we stop at the first round with no results.
        """
        if year not in self._completed_cache:
            limit = len(config.CALENDAR) if year == config.SEASON else 30
            done: list[int] = []
            for rnd in range(1, limit + 1):
                res = self._source.results(year, rnd)
                if res:
                    done.append(rnd)
                else:
                    break
            self._completed_cache[year] = done
        return self._completed_cache[year]

    # ------------------------------------------------------------------ #
    # Roster / teams — season-aware so past seasons replay their real grids.
    # ------------------------------------------------------------------ #
    def roster(self, year: int = config.SEASON) -> list[dict]:
        """[{code, name, team}] — config for the active season, else derived
        from the season snapshot's entry rows (the real grid of that season)."""
        if year == config.SEASON:
            return list(config.DRIVERS)
        if year not in self._roster_cache:
            seen: dict[str, dict] = {}
            for rnd in self.completed_rounds(year):
                rows = self.race_rows(year, rnd) or []
                for r in rows:
                    # Last round wins, so the roster reflects late-season seats.
                    seen[r["code"]] = {"code": r["code"], "name": r["name"], "team": r["team"]}
            self._roster_cache[year] = list(seen.values())
        return self._roster_cache[year]

    def team_of(self, year: int = config.SEASON) -> dict[str, str]:
        if year == config.SEASON:
            return dict(config.TEAM_OF)
        return {d["code"]: d["team"] for d in self.roster(year)}

    def driver_name(self, year: int = config.SEASON) -> dict[str, str]:
        if year == config.SEASON:
            return dict(config.DRIVER_NAME)
        return {d["code"]: d["name"] for d in self.roster(year)}

    def entrants(self, year: int, round: int) -> list[str]:
        """Codes entered at a round (pre-race public info: the entry list).

        For a round with recorded rows (incl. DNFs) that IS the entry list;
        otherwise the season roster.
        """
        rows = self.race_rows(year, round)
        if rows:
            return [r["code"] for r in rows]
        return [d["code"] for d in self.roster(year)]

    # ------------------------------------------------------------------ #
    def season(self, year: int = config.SEASON) -> Season:
        return Season(
            sport=config.SPORT,
            year=year,
            competitors=[
                Competitor(code=d["code"], name=d["name"], team=d["team"])
                for d in self.roster(year)
            ],
            teams=config.TEAMS if year == config.SEASON else [],
            calendar=config.CALENDAR if year == config.SEASON else [],
            completed_rounds=self.completed_rounds(year),
        )

    def round(self, year: int, round: int) -> Round:
        venue = self._venue(round, year)
        completed = round in self.completed_rounds(year)
        results = self.results(year, round) if completed else []
        return Round(season=year, round=round, venue=venue, completed=completed, results=results)

    def results(self, year: int, round: int) -> list[Result]:
        """Classified order for a scored race. Returns ``[]`` for rounds not
        yet run (leakage-safe)."""
        if round < 1:
            return []
        if year == config.SEASON and round > len(config.CALENDAR):
            return []
        res = self._source.results(year, round)
        return res if res is not None else []

    def race_results_for_round(self, year: int, round: int) -> dict[str, list[Result]]:
        """The round's scored race keyed by race type: {'race': [...]}.

        FE runs one race per round; the dict shape keeps parity with the
        multi-race feeder-series projects so shared tooling reads one contract.
        """
        return {"race": self.results(year, round)}

    def race_rows(self, year: int, round: int) -> list[dict] | None:
        """Full entry rows (classified + DNFs with grid/points/flags) when a
        real source carries them; None in synthetic-only mode."""
        rr = getattr(self._source, "race_rows", None)
        return rr(year, round) if rr else None

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """Real qualifying order (P1 first) for a round, or ``None`` if not run.

        Drives the post-quali forecast: once the combined-qualifying session is
        published the grid is locked, so the model conditions on the *actual*
        grid instead of its predicted merit order. ``None`` (pre-quali / no
        real feed) keeps the predicted-grid behaviour — leakage-safe.
        """
        if round < 1:
            return None
        if year == config.SEASON and round > len(config.CALENDAR):
            return None
        q = getattr(self._source, "qualifying", None)
        if q is None:
            return None
        order = q(year, round)
        return list(order) if order else None

    def provenance(self, year: int, round: int) -> str:
        """Which source served this race's results — 'snapshot' | 'pulselive' |
        'synthetic'. Used by the honest calibration gate to count only *real*
        rounds."""
        src = self._source
        if hasattr(src, "provenance"):
            return src.provenance(year, round)
        return getattr(src, "name", "synthetic")

    # ------------------------------------------------------------------ #
    def _snapshot_calendar(self, year: int) -> list[dict]:
        for src in getattr(self._source, "_sources", [self._source]):
            cal = getattr(src, "calendar", None)
            if cal is None:
                continue
            try:
                entries = cal(year)
            except Exception:
                entries = []
            if entries:
                return entries
        return []

    def _venue(self, round: int, year: int = config.SEASON) -> Venue:
        if year == config.SEASON:
            idx = round - 1
            return config.CALENDAR[idx] if 0 <= idx < len(config.CALENDAR) else config.CALENDAR[0]
        for c in self._snapshot_calendar(year):
            if int(c.get("round", 0)) == round:
                return Venue(
                    key=c.get("key", f"round-{round}"),
                    name=c.get("name", f"Round {round}"),
                    country=c.get("country"),
                    kind=c.get("kind", "street"),
                )
        return Venue(key=f"round-{round}", name=f"Round {round}", kind="street")

    def venue_for(self, year: int, round: int) -> Venue:
        """Public venue accessor (season-aware)."""
        return self._venue(round, year)


# Back-compat alias for the scaffolded template name.
SportDataSource = FEDataSource
