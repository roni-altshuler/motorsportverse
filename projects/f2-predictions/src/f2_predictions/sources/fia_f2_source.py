"""Real F2 results scraped from fiaformula2.com — the working Phase 3 feed.

The official site serves each round's results as **server-rendered HTML** at
``/Results?raceid=N``. A single round page carries:

- the full Feature + Sprint classifications (one ``<table>`` per session, each
  preceded by a ``<span>Feature Race</span>`` / ``<span>Sprint Race</span>`` heading);
- per row, a 3-letter driver code (``<span class="visible-desktop-down">ARO</span>``),
  car number, full name, finishing position, and team name;
- a round **navigator** linking every ``raceid`` in the season, in round order —
  so one fetch resolves the whole calendar from a single anchor raceid.

This module turns that into ``motorsport_data.schema.Result`` rows plus an entry
list (code → name/team) and a derived calendar. It uses only the stdlib + a lazy
``requests`` import (no lxml/bs4), and returns ``None``/``{}`` on any failure so it
slots into the :class:`CompositeF2Source` contract and never breaks the pipeline.

Parsing HTML with regex is normally a sin; it's tolerable here because the markup
is narrow, regular, and we control failure (any mismatch → defer to the next
source). If the site restructures, the scraper degrades to ``None``, not garbage.
"""
from __future__ import annotations

import html as _html
import re

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "fia"

_SESSION_HEADING = {0: "Sprint Race", 1: "Feature Race"}

# Row-level extractors (matched within a single <tr> block).
_RE_POS = re.compile(r'<div class="pos">\s*(\d+)\s*</div>')
_RE_CARNO = re.compile(r'<div class="car-no">\s*(\d+)\s*</div>')
_RE_CODE = re.compile(r'<span class="visible-desktop-down">\s*([A-Za-z]{2,4})\s*</span>')
_RE_NAME = re.compile(r'<span class="visible-desktop-up">\s*([^<]+?)\s*</span>')
_RE_TEAM = re.compile(r'<span class="team-name">\s*([^<]+?)\s*</span>')
_RE_RACEID = re.compile(r'raceid=(\d+)')
_RE_TITLE_COUNTRY = re.compile(r"Round\s+\d+\s*:\s*([^,<]+)")


class FiaF2Source:
    name = SOURCE_NAME

    def __init__(self, *, timeout: int = 20):
        self._timeout = timeout
        self._page_cache: dict[int, str] = {}
        self._raceids_cache: dict[int, list[int]] = {}
        self._entries: dict[int, dict[str, dict[str, str]]] = {}

    # ------------------------------------------------------------------ #
    # Public contract
    # ------------------------------------------------------------------ #
    def results(self, year: int, round: int, race_index: int = 1) -> list[Result] | None:
        """Classified order for one race, or ``None`` if it can't be fetched/parsed."""
        try:
            raceids = self._season_raceids(year)
            if not raceids or not (1 <= round <= len(raceids)):
                return None
            page = self._page(raceids[round - 1])
            if page is None:
                return None
            rows = self._parse_session(page, _SESSION_HEADING[race_index])
            if not rows:
                return None
            self._record_entries(year, rows)
            return [
                Result(
                    competitor=r["code"],
                    position=r["position"],
                    grid=None,  # the race table has no grid column; real grid TBD
                    status="Finished",
                    points=None,  # standings recompute from position
                )
                for r in rows
            ]
        except Exception:
            return None

    def entry_list(self, year: int) -> dict[str, dict[str, str]]:
        """code -> {'name', 'team'} accumulated from every round parsed so far."""
        return dict(self._entries.get(year, {}))

    def calendar(self, year: int) -> list[dict]:
        """Ordered [{round, raceid, country}] derived from the navigator + titles."""
        out: list[dict] = []
        for i, raceid in enumerate(self._season_raceids(year), start=1):
            country = None
            page = self._page(raceid)
            if page:
                m = _RE_TITLE_COUNTRY.search(page)
                if m:
                    country = _html.unescape(m.group(1)).strip()
            out.append({"round": i, "raceid": raceid, "country": country})
        return out

    def num_rounds(self, year: int) -> int:
        return len(self._season_raceids(year))

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _get(self, url: str) -> str | None:
        try:
            import requests
        except ImportError:
            return None
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (motorsportverse/f2 research)"},
                timeout=self._timeout,
            )
            if resp.status_code != 200 or not resp.text:
                return None
            return resp.text
        except Exception:
            return None

    def _page(self, raceid: int) -> str | None:
        if raceid not in self._page_cache:
            page = self._get(f"{config.FIA_F2_BASE_URL}/Results?raceid={raceid}")
            if page is None:
                return None
            self._page_cache[raceid] = page
        return self._page_cache[raceid]

    def _season_raceids(self, year: int) -> list[int]:
        if year in self._raceids_cache:
            return self._raceids_cache[year]
        anchor = config.FIA_F2_SEASON_ANCHORS.get(year)
        if anchor is None:
            return []
        page = self._page(anchor)
        if page is None:
            return []
        # The navigator lists every raceid in the season; sort ascending = round order.
        raceids = sorted({int(x) for x in _RE_RACEID.findall(page)})
        self._raceids_cache[year] = raceids
        return raceids

    @staticmethod
    def _parse_session(page: str, heading: str) -> list[dict]:
        """Extract classified rows from the table following a session heading."""
        h = page.find(f">{heading}</span>")
        if h == -1:
            return []
        body_start = page.find("<tbody", h)
        body_end = page.find("</tbody>", body_start) if body_start != -1 else -1
        if body_start == -1 or body_end == -1:
            return []
        body = page[body_start:body_end]
        rows: list[dict] = []
        for tr in re.split(r"<tr\b", body)[1:]:
            pos = _RE_POS.search(tr)
            code = _RE_CODE.search(tr)
            if not pos or not code:
                continue  # unclassified / DNS rows lack a numeric position
            name = _RE_NAME.search(tr)
            team = _RE_TEAM.search(tr)
            rows.append(
                {
                    "position": int(pos.group(1)),
                    "code": code.group(1).upper(),
                    "name": _html.unescape(name.group(1)) if name else code.group(1),
                    "team": _html.unescape(team.group(1)) if team else "",
                }
            )
        # Dedup by finishing position, keep ascending (defends against stray matches).
        seen: set[int] = set()
        ordered = []
        for r in sorted(rows, key=lambda r: r["position"]):
            if r["position"] in seen:
                continue
            seen.add(r["position"])
            ordered.append(r)
        return ordered

    def _record_entries(self, year: int, rows: list[dict]) -> None:
        book = self._entries.setdefault(year, {})
        for r in rows:
            book[r["code"]] = {"name": r["name"], "team": r["team"]}
