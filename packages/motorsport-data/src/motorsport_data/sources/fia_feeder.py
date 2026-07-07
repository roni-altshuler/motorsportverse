"""Shared scraper for FIA feeder-series results sites (fiaformula2/3.com).

FIA Formula 2 and FIA Formula 3 publish results through the same CMS: each
round's results are **server-rendered HTML** at ``/Results?raceid=N``. A single
round page carries:

- the full Feature + Sprint classifications (one ``<table>`` per session, each
  preceded by a ``<span>Feature Race</span>`` / ``<span>Sprint Race</span>`` heading);
- per row, a 3-letter driver code (``<span class="visible-desktop-down">ARO</span>``),
  car number, full name, finishing position, and team name;
- a round **navigator** linking every ``raceid`` in the season, in round order —
  so one fetch resolves the whole calendar from a single anchor raceid.

:class:`FiaFeederSource` turns that into ``motorsport_data.schema.Result`` rows
plus an entry list (code → name/team) and a derived calendar. It uses only the
stdlib + a lazy ``requests`` import (no lxml/bs4), and returns ``None``/``{}`` on
any failure so it slots into a composite-source seam and never breaks a pipeline.

Series-specific knobs (base URL, season anchor raceids, session/qualifying
headings) are injected via the constructor; per-sport packages subclass or
instantiate with their config, e.g. ``f2_predictions.sources.fia_f2_source``.

Parsing HTML with regex is normally a sin; it's tolerable here because the markup
is narrow, regular, and we control failure (any mismatch → defer to the next
source). If the site restructures, the scraper degrades to ``None``, not garbage.
"""
from __future__ import annotations

import html as _html
import re

from ..schema import Result

class WrongEventError(RuntimeError):
    """A fetched round page's event identity does not match the request.

    The FIA CMS is fronted by a cache/proxy and (like FastF1's fuzzy event
    matcher) can silently serve a *different* round's page for a requested
    ``raceid`` when its backend hiccups. A round page whose title says a
    different round — or a different country than the caller's calendar expects
    — must never be ingested as the requested round's classification. Raising
    this (rather than parsing the page anyway) is what turns a wrong-event
    response into a refusal instead of a corrupted snapshot.
    """


DEFAULT_SESSION_HEADINGS: dict[int, str] = {0: "Sprint Race", 1: "Feature Race"}

# Headings the qualifying classification can appear under on a round page. F2/F3
# run a single qualifying session that sets the FEATURE grid (the sprint grid is
# the reverse of its top N), so this is the one session that drives both races.
DEFAULT_QUALI_HEADINGS: tuple[str, ...] = (
    "Qualifying",
    "Qualifying Session",
    "Qualifying Result",
)

# Row-level extractors (matched within a single <tr> block).
_RE_POS = re.compile(r'<div class="pos">\s*(\d+)\s*</div>')
_RE_CARNO = re.compile(r'<div class="car-no">\s*(\d+)\s*</div>')
_RE_CODE = re.compile(r'<span class="visible-desktop-down">\s*([A-Za-z]{2,4})\s*</span>')
_RE_NAME = re.compile(r'<span class="visible-desktop-up">\s*([^<]+?)\s*</span>')
_RE_TEAM = re.compile(r'<span class="team-name">\s*([^<]+?)\s*</span>')
_RE_RACEID = re.compile(r'raceid=(\d+)')
_RE_TITLE_COUNTRY = re.compile(r"Round\s+\d+\s*:\s*([^,<]+)")
# Full title shape: "... Round 2 : USA , Miami 01-03 May 2026". Round number is
# authoritative — raceids are NOT in calendar order (fly-aways added late carry
# higher ids), so never infer the round from raceid sort order.
_RE_TITLE_ROUND = re.compile(
    r"Round\s+(\d+)\s*:\s*([^,<]+?)\s*,\s*([^0-9<]+?)\s*"
    r"(\d{1,2}-\d{1,2}\s+\w+\s+\d{4})"
)


class FiaFeederSource:
    """Results/qualifying/calendar scraper for one FIA feeder-series site."""

    name = "fia"

    def __init__(
        self,
        *,
        base_url: str,
        season_anchors: dict[int, int],
        session_headings: dict[int, str] | None = None,
        quali_headings: tuple[str, ...] | None = None,
        user_agent: str = "Mozilla/5.0 (motorsportverse research)",
        timeout: int = 20,
    ):
        self._base_url = base_url.rstrip("/")
        self._season_anchors = dict(season_anchors)
        self._session_headings = dict(session_headings or DEFAULT_SESSION_HEADINGS)
        self._quali_headings = tuple(quali_headings or DEFAULT_QUALI_HEADINGS)
        self._user_agent = user_agent
        self._timeout = timeout
        self._page_cache: dict[int, str] = {}
        self._raceids_cache: dict[int, list[int]] = {}
        self._round_map_cache: dict[int, dict[int, int]] = {}
        self._calendar_cache: dict[int, list[dict]] = {}
        self._entries: dict[int, dict[str, dict[str, str]]] = {}

    # ------------------------------------------------------------------ #
    # Event-identity guards
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalise_country(value: str) -> str:
        """Fold a country label for comparison: lowercase, drop any
        parenthetical qualifier (``"Spain (Madrid)"`` → ``"spain"``), collapse
        whitespace. Lets a caller's calendar name match the FIA title even when
        one side disambiguates a repeated country."""
        value = _html.unescape(value or "")
        value = re.sub(r"\(.*?\)", " ", value)  # strip "(Madrid)" etc.
        value = re.sub(r"[^0-9a-z]+", " ", value.lower())
        return value.strip()

    @classmethod
    def parse_event_identity(cls, page: str | None) -> dict | None:
        """``{round, country, city, dates}`` from a round page's title, or ``None``.

        Returns ``None`` when the page is falsy or carries no parseable round
        title — the shape of a truncated/garbage response whose identity cannot
        be confirmed.
        """
        if not page:
            return None
        m = _RE_TITLE_ROUND.search(page)
        if not m:
            return None
        return {
            "round": int(m.group(1)),
            "country": _html.unescape(m.group(2)).strip(),
            "city": _html.unescape(m.group(3)).strip(),
            "dates": m.group(4).strip(),
        }

    @classmethod
    def verify_page_identity(
        cls,
        page: str | None,
        *,
        expected_round: int,
        expected_country: str | None = None,
    ) -> dict:
        """Assert ``page`` is the requested round (and, if given, country).

        Returns the parsed identity on success; raises :class:`WrongEventError`
        when the page has no recognisable round title (garbage/truncated), when
        its round differs from ``expected_round``, or when ``expected_country``
        is supplied and does not match the page's title country. This is the one
        gate that stands between a wrong-event response and a snapshot write.
        """
        identity = cls.parse_event_identity(page)
        if identity is None:
            raise WrongEventError(
                f"round page carries no parseable round title — refusing to trust "
                f"it as round {expected_round} (truncated/garbage response?)"
            )
        if identity["round"] != int(expected_round):
            raise WrongEventError(
                f"requested round {expected_round} but the page is round "
                f"{identity['round']} ({identity['country']}) — refusing to ingest "
                f"another round's classification"
            )
        if expected_country is not None:
            want = cls._normalise_country(expected_country)
            got = cls._normalise_country(identity["country"])
            if want and got and want != got:
                raise WrongEventError(
                    f"round {expected_round} expected country '{expected_country}' "
                    f"but the page's title says '{identity['country']}' — refusing "
                    f"to ingest a different event"
                )
        return identity

    # ------------------------------------------------------------------ #
    # Public contract
    # ------------------------------------------------------------------ #
    def results(self, year: int, round: int, race_index: int = 1) -> list[Result] | None:
        """Classified order for one race, or ``None`` if it can't be fetched/parsed."""
        try:
            raceid = self._round_map(year).get(round)
            if raceid is None:
                return None
            page = self._page(raceid)
            if page is None:
                return None
            # A round-scoped fetch must come back as the requested round; a cache/
            # proxy serving a different race's page would otherwise be ingested
            # under this round. A mismatch (or an identity-less page) → defer.
            try:
                self.verify_page_identity(page, expected_round=round)
            except WrongEventError as exc:
                print(f"  ⚠️  {exc}")
                return None
            rows = self._parse_session(page, self._session_headings[race_index])
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

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """Driver codes in qualifying order (P1 first) for a round, or ``None``.

        Qualifying sets the feature-race grid; we expose just the order (the grid)
        since the race tables carry no grid column. Returns ``None`` when the
        session can't be fetched or parsed yet (pre-quali, site down, markup
        changed) so the composite seam falls through and the model uses its
        predicted merit grid instead — never breaking a forecast.
        """
        try:
            raceid = self._round_map(year).get(round)
            if raceid is None:
                return None
            page = self._page(raceid)
            if page is None:
                return None
            try:
                self.verify_page_identity(page, expected_round=round)
            except WrongEventError as exc:
                print(f"  ⚠️  {exc}")
                return None
            for heading in self._quali_headings:
                rows = self._parse_session(page, heading)
                if rows:
                    self._record_entries(year, rows)
                    return [r["code"] for r in rows]  # already position-sorted
            return None
        except Exception:
            return None

    def entry_list(self, year: int) -> dict[str, dict[str, str]]:
        """code -> {'name', 'team'} accumulated from every round parsed so far."""
        return dict(self._entries.get(year, {}))

    def calendar(self, year: int) -> list[dict]:
        """Ordered [{round, raceid, country, city, dates}] from each page's title.

        Round order comes from the *title* (``Round N``), not the raceid sort
        order, because the FIA assigns raceids out of calendar order.
        """
        if year in self._calendar_cache:
            return self._calendar_cache[year]
        out: list[dict] = []
        for raceid in self._season_raceids(year):
            page = self._page(raceid)
            identity = self.parse_event_identity(page)
            if identity is None:
                continue
            out.append({**identity, "raceid": raceid})
        out.sort(key=lambda r: r["round"])
        self._calendar_cache[year] = out
        return out

    def num_rounds(self, year: int) -> int:
        return len(self._season_raceids(year))

    def _round_map(self, year: int) -> dict[int, int]:
        """{round_number: raceid} resolved from page titles (authoritative)."""
        if year not in self._round_map_cache:
            self._round_map_cache[year] = {
                c["round"]: c["raceid"] for c in self.calendar(year)
            }
        return self._round_map_cache[year]

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
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout,
            )
            if resp.status_code != 200 or not resp.text:
                return None
            return resp.text
        except Exception:
            return None

    def _page(self, raceid: int) -> str | None:
        if raceid not in self._page_cache:
            page = self._get(f"{self._base_url}/Results?raceid={raceid}")
            if page is None:
                return None
            self._page_cache[raceid] = page
        return self._page_cache[raceid]

    def _season_raceids(self, year: int) -> list[int]:
        if year in self._raceids_cache:
            return self._raceids_cache[year]
        anchor = self._season_anchors.get(year)
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
    def _parse_session(page: str, heading: str, *, include_unclassified: bool = False) -> list[dict]:
        """Extract rows from the table following a session heading.

        By default returns only **classified** finishers (numeric position),
        sorted/deduped by position — the contract the composite seam + standings
        rely on. With ``include_unclassified=True`` it also returns retirements
        (DNF/DNS/DSQ/NC) with ``position=None`` and a ``status`` string, appended
        after the classified rows, so race pages can show the full field.
        """
        h = page.find(f">{heading}</span>")
        if h == -1:
            return []
        body_start = page.find("<tbody", h)
        body_end = page.find("</tbody>", body_start) if body_start != -1 else -1
        if body_start == -1 or body_end == -1:
            return []
        body = page[body_start:body_end]
        rows: list[dict] = []
        unclassified: list[dict] = []
        for tr in re.split(r"<tr\b", body)[1:]:
            code = _RE_CODE.search(tr)
            if not code:
                continue
            name = _RE_NAME.search(tr)
            team = _RE_TEAM.search(tr)
            base = {
                "code": code.group(1).upper(),
                "name": _html.unescape(name.group(1)) if name else code.group(1),
                "team": _html.unescape(team.group(1)) if team else "",
            }
            pos = _RE_POS.search(tr)
            if pos:
                rows.append({**base, "position": int(pos.group(1)), "status": "Finished"})
            elif include_unclassified:
                # Non-numeric position cell (DNF/DNS/DSQ/NC) — capture the status.
                raw = re.search(r'class="pos">\s*([^<\s][^<]*?)\s*</', tr)
                unclassified.append(
                    {**base, "position": None, "status": (raw.group(1).strip() if raw else "DNF")}
                )
        # Dedup by finishing position, keep ascending (defends against stray matches).
        seen: set[int] = set()
        ordered = []
        for r in sorted(rows, key=lambda r: r["position"]):
            if r["position"] in seen:
                continue
            seen.add(r["position"])
            ordered.append(r)
        if include_unclassified:
            seen_codes = {r["code"] for r in ordered}
            ordered.extend(u for u in unclassified if u["code"] not in seen_codes)
        return ordered

    def _record_entries(self, year: int, rows: list[dict]) -> None:
        book = self._entries.setdefault(year, {})
        for r in rows:
            book[r["code"]] = {"name": r["name"], "team": r["team"]}
