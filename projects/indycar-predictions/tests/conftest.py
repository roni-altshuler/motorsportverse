"""Shared IndyCar test plumbing.

Everything here (and in every test) is OFFLINE: results come from the
committed, human-verified history files (``data/history_<year>.json`` — the
curated files ARE the fixtures) or from wikitext built programmatically from
those same files — never the network.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from indycar_predictions import config

DATA = Path(__file__).resolve().parents[1] / "data"

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]
_TT = {"oval": "O", "road": "R", "street": "S"}


def load_history(year: int) -> dict:
    return json.loads((DATA / f"history_{year}.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Wikitext fixture builders — the scraper contract, built from the committed
# curated data so the fixtures never drift from reality.
# --------------------------------------------------------------------------- #
def _md(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{_MONTHS[d.month - 1]} {d.day}"


def article_title(rnd: int) -> str:
    return f"{config.SEASON} {config.CALENDAR_META[rnd]['raceName']}"


def make_season_page(
    n_articles: int,
    standings: list[tuple[str, float]],
    *,
    venue_override: dict[int, str] | None = None,
    date_override: dict[int, str] | None = None,
) -> str:
    """A season-page wikitext with Schedule + Results + standings grid."""
    sched = ['==Schedule==', '{| class="wikitable"', '! Rd !! Date !! Track/Location !! Race']
    for rnd, meta in sorted(config.CALENDAR_META.items()):
        venue = (venue_override or {}).get(rnd, meta["venue"])
        d = (date_override or {}).get(rnd, meta["date"])
        sched.append("|-")
        sched.append(f"! {rnd}")
        sched.append(
            f"| {_md(d)} || {{{{Color box|silver|{_TT[meta['trackType']]}|border=darker silver}}}} "
            f"[[{venue}]] || [[{article_title(rnd)}|{meta['raceName']}]]"
        )
    sched.append("|}")
    res = ['==Results==', '{| class="wikitable"', '! Rd !! Race !! Report']
    for rnd in range(1, n_articles + 1):
        res.append("|-")
        res.append(f"! {rnd}")
        res.append(
            f"| [[{article_title(rnd)}|{config.CALENDAR_META[rnd]['raceName']}]] "
            f"|| [[{article_title(rnd)}|Report]]"
        )
    res.append("|}")
    st = ['==Points standings==', '===Drivers===', '{| class="wikitable"', "! Pos !! Driver !! Pts"]
    for i, (drv, pts) in enumerate(standings, 1):
        st.append("|-")
        st.append(f"! {i}")
        st.append(f"| [[{drv}]] || {pts:g}")
    st.append("|}")
    return "\n".join(sched + [""] + res + [""] + st) + "\n"


def make_race_article(results: list[dict]) -> str:
    """A per-race article wikitext with one race-classification table."""
    lines = [
        '==Race==', '===Race classification===', '{| class="wikitable"',
        '! {{Tooltip|Pos|Position}} !! No. !! Driver !! Team !! Engine !! Laps '
        '!! Time/Retired !! {{Tooltip|Grid|Start}} !! {{Tooltip|Led|Laps led}} !! Points',
    ]
    for r in results:
        pts = r.get("points")
        pts_s = f"{pts:g}" if pts is not None else ""
        lines.append("|-")
        lines.append(
            f"| {r['position']} || 5 || [[{r['driver']}]] || {r.get('team') or ''} || "
            f"{r.get('engine') or ''} || {r.get('laps') or 100} || "
            f"{r.get('status') or '1:00:00.0'} || {r.get('grid') or ''} || 0 || {pts_s}"
        )
    lines.append("|}")
    return "\n".join(lines) + "\n"


def synthetic_new_round_results(rnd: int) -> list[dict]:
    """A plausible classification for a not-yet-curated round: the 25
    full-season roster drivers, base-table points (+3 winner bonus)."""
    rows = []
    for i, d in enumerate(config.DRIVERS, start=1):
        pts = float(config.POINTS.get(i, 5)) + (3.0 if i == 1 else 0.0)
        rows.append(
            {
                "position": i,
                "driver": d["name"],
                "team": d["team"],
                "engine": d["engine"],
                "grid": ((i + 4) % len(config.DRIVERS)) + 1,
                "laps": 200 if i <= 20 else 150,
                "status": "1:40:00.0" if i == 1 else ("+%d.%03d" % (i, i)) if i <= 20 else "Contact",
                "points": pts,
            }
        )
    return rows


def summed_standings(rounds: list[dict]) -> list[tuple[str, float]]:
    """Official-grid standings recomputed by summing awarded per-race points."""
    totals: dict[str, float] = {}
    for rd in rounds:
        for r in rd["results"]:
            if r.get("points") is not None:
                totals[r["driver"]] = totals.get(r["driver"], 0.0) + float(r["points"])
    return sorted(totals.items(), key=lambda kv: -kv[1])


def build_wiki_pages(
    n_rounds: int,
    *,
    extra_results: dict[int, list[dict]] | None = None,
    venue_override: dict[int, str] | None = None,
    article_override: dict[int, str] | None = None,
) -> dict[str, str]:
    """{page title: wikitext} for a season parsed through round ``n_rounds``.

    Rounds up to the committed count come from the real history file; rounds
    beyond it come from ``extra_results`` (default: the synthetic new-round
    classification). ``article_override`` swaps a round's article wikitext
    wholesale (poisoned-page tests).
    """
    hist = load_history(config.SEASON)
    by_round = {int(rd["round"]): rd["results"] for rd in hist["rounds"]}
    rounds = []
    for rnd in range(1, n_rounds + 1):
        if rnd in by_round:
            results = by_round[rnd]
        else:
            results = (extra_results or {}).get(rnd) or synthetic_new_round_results(rnd)
        rounds.append({"round": rnd, "results": results})
    standings = summed_standings(rounds)
    pages = {
        f"{config.SEASON} IndyCar Series": make_season_page(
            n_rounds, standings, venue_override=venue_override
        )
    }
    for rd in rounds:
        title = article_title(rd["round"])
        pages[title] = (article_override or {}).get(rd["round"]) or make_race_article(
            rd["results"]
        )
    return pages


class FakeWikiClient:
    """Offline stand-in for WikiClient, serving prepared wikitext pages."""

    def __init__(self, pages: dict[str, str] | None = None):
        self._pages = pages or {}
        self.requests: list[str] = []

    def wikitext(self, page: str) -> str | None:
        self.requests.append(page)
        return self._pages.get(page)


# --------------------------------------------------------------------------- #
# Source wrappers
# --------------------------------------------------------------------------- #
class TruncatedSource:
    """Wrap a results source, hiding every round after ``upto`` for ``year``.

    Keeps expensive walk-forward tests fast (fewer rounds → fewer replays)
    and simulates an earlier point in the season.
    """

    name = "snapshot"  # counts as real for the calibration gate

    def __init__(self, inner, year: int, upto: int):
        self._inner = inner
        self._year = year
        self._upto = upto

    def _hidden(self, year, round) -> bool:
        return year == self._year and round > self._upto

    def results(self, year, round, race_index: int = 0):
        if self._hidden(year, round):
            return []
        return self._inner.results(year, round, race_index)

    def race_rows(self, year, round):
        if self._hidden(year, round):
            return None
        rr = getattr(self._inner, "race_rows", None)
        return rr(year, round) if rr else None

    def qualifying(self, year, round):
        if self._hidden(year, round):
            return None
        q = getattr(self._inner, "qualifying", None)
        return q(year, round) if q else None

    def calendar(self, year):
        cal = getattr(self._inner, "calendar", None)
        return cal(year) if cal else []

    def standings(self, year):
        st = getattr(self._inner, "standings", None)
        return st(year) if st else []

    def provenance(self, year, round, race_index: int = 0):
        return "snapshot"


@pytest.fixture()
def snapshot_source():
    from indycar_predictions.sources.snapshot import SnapshotIndycarSource

    return SnapshotIndycarSource()


@pytest.fixture()
def real_source():
    """The production default source stack (committed history + synthetic)."""
    from indycar_predictions.datasource import IndycarDataSource

    return IndycarDataSource()


@pytest.fixture()
def truncated_source():
    """IndycarDataSource seeing only the first 6 rounds of the active season."""
    from indycar_predictions.datasource import IndycarDataSource
    from indycar_predictions.sources.composite import CompositeIndycarSource
    from indycar_predictions.sources.snapshot import SnapshotIndycarSource

    composite = CompositeIndycarSource(
        [TruncatedSource(SnapshotIndycarSource(), config.SEASON, 6)]
    )
    return IndycarDataSource(source=composite)
