"""IndyCar results scraper — a REFRESH MECHANISM, never a source of truth.

IndyCar has no public API, so this project is snapshot-primary: the committed
``data/history_<year>.json`` files are canonical and this module exists only
so :mod:`indycar_predictions.refresh` can *append newly completed rounds* to
the active season's file. It re-uses the Wikipedia race-article parsing the
curation pipeline proved out (:mod:`.wikitext_parse`, vendored from
``scripts/parse.py`` — the code that produced and verified all 15 committed
seasons), wrapped in strict validation:

* **requested-event-vs-page identity** — the season page's schedule must match
  the human-verified config calendar round-for-round (venue slug + date), and
  every per-race article title must carry the season year. A mismatch raises
  :class:`WrongEventError` (the F1 flagship once published Austria's result as
  the British GP from exactly this class of bug — never again).
* **clean-parse gate** — a classification is refused (:class:`DirtyParseError`)
  unless the car count sits in the expected band (24-28, 30-35 at the Indy
  500), positions are unique and contiguous from P1, awarded points are
  present, and most drivers are on the config roster whitelist. A truncated
  table, a qualifying/schedule table mis-detected as results, or a page for
  some other series all fail here — refused, never ingested.

Network failures return ``None`` (defer / no-op), a genuinely not-yet-run
round returns ``[]`` — never fabricated data.
"""
from __future__ import annotations

import re
import time
import unicodedata

from motorsport_data.schema import Result

from .. import config
from . import wikitext_parse as wp
from .snapshot import is_dnf_status

SOURCE_NAME = "wikipedia"


class WrongEventError(RuntimeError):
    """The fetched page's identity does not match the requested round."""


class DirtyParseError(RuntimeError):
    """A parsed classification failed validation — refuse, never ingest."""


# --------------------------------------------------------------------------- #
# Thin throttled wikitext client (MediaWiki action API)
# --------------------------------------------------------------------------- #
class WikiClient:
    def __init__(self, *, api_url: str | None = None, min_interval: float = 1.0,
                 timeout: int = 30):
        self.api_url = api_url or config.WIKIPEDIA_API
        self.min_interval = min_interval
        self.timeout = timeout
        self._last_request = 0.0

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def wikitext(self, page: str) -> str | None:
        """Raw wikitext of ``page``; ``None`` on any failure (a failed live
        fetch is a no-op for callers, never bad data)."""
        try:
            import requests
        except ImportError:
            return None
        try:
            self._throttle()
            resp = requests.get(
                self.api_url,
                headers={"User-Agent": config.INDYCAR_USER_AGENT},
                params={
                    "action": "parse",
                    "page": page,
                    "prop": "wikitext",
                    "format": "json",
                    "redirects": 1,
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return None
            payload = resp.json()
            if "error" in payload:
                return None
            return payload["parse"]["wikitext"]["*"]
        except Exception:
            return None


# --------------------------------------------------------------------------- #
# Pure validation (offline-testable)
# --------------------------------------------------------------------------- #
def _slug(name: str | None) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def verify_round_identity(sched_entry: dict, *, year: int, round: int) -> None:
    """Assert a parsed schedule row matches the config calendar's round.

    Only meaningful for the ACTIVE season (config carries its verified
    calendar); compares the venue slug and the ISO date. A mismatch means the
    page's round numbering has drifted from the committed calendar — a human
    must re-verify before anything is ingested.
    """
    if year != config.SEASON:
        return
    meta = config.CALENDAR_META.get(round)
    if meta is None:
        raise WrongEventError(f"round {round}: not on the {year} config calendar")
    got_venue = _slug(sched_entry.get("venue"))
    exp_venue = _slug(meta.get("venue")) or str(meta.get("key"))
    if got_venue and exp_venue and got_venue != exp_venue and got_venue != _slug(meta.get("key")):
        raise WrongEventError(
            f"round {round}: schedule venue {sched_entry.get('venue')!r} does not match the "
            f"config calendar venue {meta.get('venue')!r}"
        )
    got_date = sched_entry.get("date") or ""
    exp_date = str(meta.get("date") or "")
    if got_date and exp_date and got_date[:10] != exp_date[:10]:
        raise WrongEventError(
            f"round {round}: schedule date {got_date!r} does not match the config "
            f"calendar date {exp_date!r}"
        )


def verify_article_title(title: str, *, year: int, round: int) -> None:
    """The per-race article for a round must belong to the requested season."""
    if str(year) not in (title or ""):
        raise WrongEventError(
            f"round {round}: race article {title!r} does not name the {year} season "
            "— refusing to ingest a different event's classification"
        )


def known_roster_fraction(rows: list[dict]) -> float:
    """Fraction of a classification's driver codes known to config."""
    if not rows:
        return 0.0
    known = set(config.TEAM_OF) | set(config.INDY500_ONLY_DRIVERS)
    codes = [config.driver_code(r.get("driver") or "") for r in rows]
    return sum(1 for c in codes if c in known) / len(codes)


def validate_classification(
    rows: list[dict], *, year: int, round: int, is_indy500: bool | None = None
) -> None:
    """Clean-parse gate for one parsed race classification.

    Raises :class:`DirtyParseError` on ANY problem — partial/garbage parses
    are refused wholesale (``refresh --require-clean-parse`` semantics).
    """
    problems: list[str] = []
    if is_indy500 is None:
        is_indy500 = config.is_indy500_round(round) if year == config.SEASON else False
    lo, hi = config.INDY500_CAR_COUNT if is_indy500 else config.EXPECTED_CAR_COUNT
    n = len(rows)
    if not (lo <= n <= hi):
        problems.append(f"car count {n} outside the expected band [{lo}, {hi}]")

    positions = [r["position"] for r in rows if r.get("position") is not None]
    unclassified = n - len(positions)
    if unclassified > 2:
        problems.append(f"{unclassified} rows without a finishing position")
    if len(positions) != len(set(positions)):
        problems.append("duplicate finishing positions")
    if positions and (min(positions) != 1 or max(positions) != len(positions)):
        problems.append(
            f"positions not contiguous from P1 (min={min(positions)}, "
            f"max={max(positions)}, classified={len(positions)}) — truncated table?"
        )
    missing_points = sum(
        1 for r in rows if r.get("position") is not None and r.get("points") is None
    )
    if missing_points:
        problems.append(f"{missing_points} classified rows without awarded points")
    missing_status = sum(1 for r in rows if not (r.get("status") or "").strip())
    if missing_status > 2:
        problems.append(f"{missing_status} rows without a time/retired status")

    if year == config.SEASON:
        frac = known_roster_fraction(rows)
        if frac < config.ROSTER_WHITELIST_MIN_FRACTION:
            problems.append(
                f"only {frac:.0%} of drivers are on the config roster whitelist "
                f"(need ≥ {config.ROSTER_WHITELIST_MIN_FRACTION:.0%}) — wrong series/page?"
            )

    if problems:
        raise DirtyParseError(
            f"round {round} ({year}): refusing unclean parse — " + "; ".join(problems)
        )


# --------------------------------------------------------------------------- #
# The live source behind the DataSource seam
# --------------------------------------------------------------------------- #
class IndycarScraperSource:
    """Live Wikipedia-backed source. Answers ``None`` on any fetch failure
    (defer to the next source in the composite), ``[]`` for a known round that
    has not been run, and RAISES on identity/validation failures — a wrong or
    dirty page must abort, not silently degrade."""

    name = SOURCE_NAME

    def __init__(self, *, client: WikiClient | None = None, today: str | None = None):
        self._client = client or WikiClient()
        self._season_cache: dict[int, dict | None] = {}
        self._today = today  # ISO date override (tests); None = wall clock

    # ------------------------------------------------------------------ #
    def _today_iso(self) -> str:
        if self._today:
            return self._today
        from datetime import date

        return date.today().isoformat()

    def _iso_date(self, md: str | None, year: int) -> str | None:
        months = {
            m: i
            for i, m in enumerate(
                ["January", "February", "March", "April", "May", "June", "July",
                 "August", "September", "October", "November", "December"], 1)
        }
        if not md:
            return None
        m = re.match(r"([A-Za-z]+)\s+(\d+)", md)
        if not m or m.group(1) not in months:
            return None
        return f"{year:04d}-{months[m.group(1)]:02d}-{int(m.group(2)):02d}"

    def season_state(self, year: int) -> dict | None:
        """Parse the season page + per-race articles once per season.

        Returns ``{"schedule": [...], "races": {round: rows}, "standings":
        [...], "clean": bool, "notes": [...]}`` or ``None`` when the season
        page cannot be fetched/parsed. Raises :class:`WrongEventError` /
        :class:`DirtyParseError` per the guards above.
        """
        if year in self._season_cache:
            return self._season_cache[year]

        page = f"{year} IndyCar Series"
        w = self._client.wikitext(page)
        if w is None:
            self._season_cache[year] = None
            return None
        try:
            schedule = wp.parse_schedule(w)
            articles = wp.parse_results_articles(w, year)
            standings = wp.parse_standings(w, wp.load_aliases())
        except ValueError:
            self._season_cache[year] = None
            return None

        for entry in schedule:
            entry["date"] = self._iso_date(entry.get("date_md"), year)
        # Identity guard: the whole parsed schedule must agree with the
        # human-verified config calendar (active season only).
        if year == config.SEASON and len(schedule) != len(config.CALENDAR_META):
            raise WrongEventError(
                f"season {year}: page schedule has {len(schedule)} championship rounds "
                f"but the config calendar has {len(config.CALENDAR_META)} — a "
                "cancelled/added event needs human re-verification before refreshing"
            )
        for entry in schedule:
            verify_round_identity(entry, year=year, round=int(entry["round"]))

        # Per-race articles, expanded in order (a double-header article
        # carries two classification tables = two rounds).
        aliases = wp.load_aliases()
        races: dict[int, list[dict]] = {}
        notes: list[str] = []
        clean = True
        rnd = 0
        for title in articles:
            aw = self._client.wikitext(title)
            if aw is None:
                clean = False
                notes.append(f"article fetch failed: {title!r}")
                break
            parsed = wp.parse_race_classifications(aw, aliases)
            if not parsed:
                clean = False
                notes.append(f"article parsed no race classification: {title!r}")
                break
            for rows in parsed:
                rnd += 1
                verify_article_title(title, year=year, round=rnd)
                races[rnd] = rows
        if rnd > len(schedule):
            raise WrongEventError(
                f"season {year}: parsed {rnd} race classifications for a "
                f"{len(schedule)}-round schedule"
            )
        # An uncovered tail is only acceptable when it is genuinely
        # future-dated (an in-progress season) or freshly run within the
        # publication grace window (the page lags the chequered flag by hours,
        # sometimes a day or two — that is a defer, not a dirty parse). An
        # OLDER gap means the results table mis-parsed — dirty.
        if clean and rnd < len(schedule):
            nxt = schedule[rnd].get("date")
            if nxt:
                from datetime import date as _date, timedelta as _timedelta

                grace_floor = (
                    _date.fromisoformat(self._today_iso())
                    - _timedelta(days=config.RESULT_PUBLICATION_GRACE_DAYS)
                ).isoformat()
            if not (nxt and nxt >= grace_floor):
                clean = False
                notes.append(
                    f"rounds {rnd + 1}..{len(schedule)} have no parsed classification "
                    "but are not future-dated (beyond the "
                    f"{config.RESULT_PUBLICATION_GRACE_DAYS}-day publication grace) "
                    "— parse gap"
                )
            elif nxt <= self._today_iso():
                notes.append(
                    f"round {rnd + 1} ran on {nxt} but its classification is not on "
                    "the page yet — deferring within the publication grace window"
                )

        state = {
            "schedule": schedule,
            "races": races,
            "standings": standings,
            "clean": clean,
            "notes": notes,
        }
        self._season_cache[year] = state
        return state

    # ------------------------------------------------------------------ #
    def _validated_rows(self, year: int, round: int) -> list[dict] | None:
        state = self.season_state(year)
        if state is None:
            return None
        if round < 1 or round > len(state["schedule"]):
            return None
        rows = state["races"].get(round)
        if rows is None:
            # Not parsed: genuinely future round → "not run yet"; otherwise
            # the season parse is dirty and must not answer.
            if state["clean"]:
                return []
            raise DirtyParseError(
                f"round {round} ({year}): season parse is not clean — " +
                "; ".join(state["notes"])
            )
        validate_classification(rows, year=year, round=round)
        return rows

    def results(self, year: int, round: int, race_index: int = 0) -> list[Result] | None:
        rows = self._validated_rows(year, round)
        if rows is None:
            return None
        if rows == []:
            return []
        classified = sorted(
            (r for r in rows if r.get("position")), key=lambda r: r["position"]
        )
        return [
            Result(
                competitor=config.driver_code(r.get("driver") or ""),
                position=int(r["position"]),
                grid=r.get("grid"),
                status=r.get("status"),
                points=r.get("points"),
            )
            for r in classified
        ]

    def race_rows(self, year: int, round: int) -> list[dict] | None:
        """Snapshot-shaped rows for a COMPLETED round, or None."""
        rows = self._validated_rows(year, round)
        if not rows:
            return None
        out = []
        for r in rows:
            status = r.get("status")
            out.append(
                {
                    "position": r.get("position"),
                    "code": config.driver_code(r.get("driver") or ""),
                    "name": r.get("driver") or "",
                    "team": r.get("team") or "",
                    "engine": r.get("engine") or "",
                    "grid": r.get("grid"),
                    "laps": r.get("laps"),
                    "status": status,
                    "dnf": is_dnf_status(status),
                    "points": r.get("points"),
                }
            )
        out.sort(key=lambda r: (r["position"] is None, r["position"] or 0))
        return out

    def raw_results(self, year: int, round: int) -> list[dict] | None:
        """The validated curation-schema rows (driver/team/engine/... keys) —
        what :mod:`..refresh` appends to the history file."""
        rows = self._validated_rows(year, round)
        if not rows:
            return None
        out = [
            {
                "position": r.get("position"),
                "driver": r.get("driver"),
                "team": r.get("team"),
                "engine": (r.get("engine") or "").replace("Chevrolet Indy V6", "Chevrolet")
                or None,
                "grid": r.get("grid"),
                "laps": r.get("laps"),
                "status": r.get("status"),
                "points": r.get("points"),
            }
            for r in rows
        ]
        out.sort(key=lambda r: (r["position"] is None, r["position"] or 999))
        return out

    def standings(self, year: int) -> list[dict] | None:
        state = self.season_state(year)
        return list(state["standings"]) if state else None
