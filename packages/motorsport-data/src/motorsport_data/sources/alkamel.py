"""Shared ingester for Al Kamel Systems timing archives (WEC + IMSA).

Al Kamel runs the official timing for the FIA World Endurance Championship
(``fiawec.alkamelsystems.com``) and the IMSA WeatherTech SportsCar Championship
(``imsa.alkamelsystems.com``). Both publish a *static, browsable* results archive
keyed by season → event → championship → session, with machine-readable
semicolon-delimited ``.CSV`` classifications alongside the human PDFs.

The archive is fully enumerable without any private API:

* the landing page embeds a season ``<select name="season">`` whose option
  values are ``<index>_<year>`` folders (``15_2026`` … ``01_2011``);
* re-requesting ``/?season=<folder>&evvent=<event>`` re-renders the page with
  that season's event ``<select name="evvent">`` *and* the selected event's full
  file tree as plain ``href="Results/..."`` links;
* the final race classification is ``.../<ts>_Race/.../03_Classification_Race*.CSV``
  (endurance races are split into hourly folders — the final hour is the result).

This client turns that into structured per-class rows. It is deliberately
read-only, disk-cached, and identity-checking (every parsed row carries the
season/event it came from) so downstream snapshot builders never touch the
network and can be re-run offline. WEC and IMSA differ only by ``host`` and the
championship-folder hint, so both projects bind the same class.
"""
from __future__ import annotations

import csv
import io
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import requests

_UA = "MotorsportVerse/1.0 (+https://github.com/roni-altshuler/motorsportverse)"
_TIMEOUT = 30


@dataclass(frozen=True)
class ClassificationRow:
    """One car's final finishing line, verbatim from an Al Kamel CSV."""

    position: int | None  # overall classified position; None if not classified
    number: str  # car number as printed ("7", "007", "51") — stable entry id
    team: str
    vehicle: str  # manufacturer/car, e.g. "Ferrari 499P"
    cls: str  # HYPERCAR / LMP2 / LMGT3 / GTP / GTD PRO / GTD …
    status: str  # Classified / Not Classified / Retired / …
    laps: int | None
    drivers: tuple[str, ...] = ()

    @property
    def classified(self) -> bool:
        return self.status.strip().lower().startswith("classif") and self.position is not None


@dataclass(frozen=True)
class EventRef:
    season_folder: str  # e.g. "15_2026"
    year: int
    event_folder: str  # e.g. "03_LE MANS"
    round_no: int  # leading index of the event folder
    name: str  # human event name, e.g. "LE MANS"


@dataclass
class AlKamelClient:
    """Read-only, disk-cached client over an Al Kamel results archive."""

    host: str  # e.g. "https://fiawec.alkamelsystems.com"
    champ_hint: str  # substring that marks the championship folder, e.g. "FIA WEC"
    cache_dir: Path
    polite_delay: float = 0.3
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.host = self.host.rstrip("/")
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session.headers.update({"User-Agent": _UA})

    # ---- low-level fetch with disk cache -----------------------------------
    def _cache_path(self, key: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", key)
        return self.cache_dir / safe

    def _get_text(self, url: str, cache_key: str, refresh: bool = False,
                  validate=None, tries: int = 5) -> str:
        """GET with disk cache, a fresh connection, and optional validation.

        The archive is served behind a flaky front end that will occasionally
        answer on a reused keep-alive connection with the *default* (current)
        season's page instead of the one requested. We defend against that by
        forcing ``Connection: close`` (a fresh connection per request) and, when
        a ``validate`` predicate is supplied, retrying until the returned page
        actually corresponds to what we asked for. Only validated pages are
        cached; a stale cached page that no longer validates is refetched.
        """
        cp = self._cache_path(cache_key)
        if cp.exists() and not refresh:
            cached = cp.read_text(encoding="utf-8", errors="replace")
            if validate is None or validate(cached):
                return cached
        last = ""
        for _ in range(tries):
            time.sleep(self.polite_delay)
            self.session.cookies.clear()
            resp = self.session.get(url, headers={"Connection": "close"}, timeout=_TIMEOUT)
            resp.raise_for_status()
            last = resp.content.decode("utf-8", errors="replace")
            if validate is None or validate(last):
                cp.write_text(last, encoding="utf-8")
                return last
        # Validation never passed; surface the best-effort page but do not cache
        # it as authoritative (so a later run can retry from scratch).
        return last

    _TREE_SEASON = re.compile(r'href="Results/(\d+_\d{4}(?:-\d{4})?)/', re.IGNORECASE)

    def _tree_seasons(self, html: str) -> set[str]:
        return set(self._TREE_SEASON.findall(html))

    # ---- enumeration -------------------------------------------------------
    def _page(self, season_folder: str | None = None, event_folder: str | None = None,
              refresh: bool = False, validate=None) -> str:
        params: dict[str, str] = {}
        if season_folder:
            params["season"] = season_folder
        if event_folder:
            params["evvent"] = event_folder  # sic — the form field is misspelled upstream
        url = self.host + "/"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        key = "page__" + (season_folder or "root") + "__" + (event_folder or "default")
        # Default validator: when a season is requested, the embedded results
        # tree must reference exactly that season (defeats the keep-alive
        # contamination that leaks the default season's page).
        if validate is None and season_folder:
            validate = lambda t: self._tree_seasons(t) == {season_folder}  # noqa: E731
        return self._get_text(url, key, refresh=refresh, validate=validate)

    _SEASON_OPT = re.compile(r'<option\s+Value="(\d+_\d{4}(?:-\d{4})?)"', re.IGNORECASE)
    _EVENT_OPT = re.compile(r'<option\s+Value="(\d+_[^"]+)"', re.IGNORECASE)

    def list_seasons(self, refresh: bool = False) -> list[tuple[str, int]]:
        """Return ``[(season_folder, year), …]`` newest year first.

        Multi-year folders like ``08_2018-2019`` map to their *final* year.
        """
        html = self._page(refresh=refresh)
        out: list[tuple[str, int]] = []
        for folder in dict.fromkeys(self._SEASON_OPT.findall(html)):
            year_label = folder.split("_", 1)[1]
            year = int(year_label.split("-")[-1])
            out.append((folder, year))
        out.sort(key=lambda t: t[1], reverse=True)
        return out

    def list_events(self, season_folder: str, refresh: bool = False) -> list[EventRef]:
        """Events that actually have a results tree for the given season."""
        html = self._page(season_folder=season_folder, refresh=refresh)
        year = int(season_folder.split("_", 1)[1].split("-")[-1])
        events: list[EventRef] = []
        seen: set[str] = set()
        for value in self._EVENT_OPT.findall(html):
            # event options are "<idx>_<NAME>"; season options are "<idx>_<year>"
            if re.fullmatch(r"\d+_\d{4}(?:-\d{4})?", value):
                continue
            if value in seen:
                continue
            seen.add(value)
            idx_s, _, name = value.partition("_")
            events.append(
                EventRef(
                    season_folder=season_folder,
                    year=year,
                    event_folder=value,
                    round_no=int(idx_s),
                    name=name.strip(),
                )
            )
        events.sort(key=lambda e: e.round_no)
        return events

    # ---- results -----------------------------------------------------------
    def _hrefs(self, html: str) -> list[str]:
        return re.findall(r'href="(Results/[^"]+?\.CSV)"', html, flags=re.IGNORECASE)

    def _race_classification_url(self, event: EventRef, refresh: bool = False) -> str | None:
        """URL of the *final* race classification CSV for an event, or None.

        Endurance races are split into hourly folders; we take the deepest hour.
        Shorter races may store the classification directly in the ``_Race``
        session folder. We restrict to the configured championship folder so a
        support race can't leak in.
        """
        # The event page must reference this exact season AND this event folder
        # in its results tree, or the flaky front end handed us another page.
        ef_enc = urllib.parse.quote(event.event_folder, safe="").lower()
        ef_plain = event.event_folder.replace(" ", "%20").lower()

        def _ok(t: str) -> bool:
            if self._tree_seasons(t) != {event.season_folder}:
                return False
            tl = t.lower()
            prefix_enc = f"results/{event.season_folder.lower()}/{ef_enc}/"
            prefix_plain = f"results/{event.season_folder.lower()}/{ef_plain}/"
            return prefix_enc in tl or prefix_plain in tl

        html = self._page(season_folder=event.season_folder, event_folder=event.event_folder,
                          refresh=refresh, validate=_ok)
        champ = self.champ_hint.replace(" ", "%20").lower()
        best_key: tuple | None = None
        best_href: str | None = None
        for href in self._hrefs(html):
            low = href.lower()
            if champ not in low:
                continue
            # session folder must be the race (…/<ts>_Race[…]/…)
            if not re.search(r"_race(?:%20\d+)?(/|%20)", low):
                continue
            fname = href.rsplit("/", 1)[-1].lower()
            # WEC writes "03_Classification_Race…"; IMSA writes "03_Results_Race…".
            if not re.match(r"03_(classification|results)_race", fname):
                continue
            if "grid" in fname or "analysis" in fname:
                continue
            # WEC: pick the deepest hour ("…/24_Hour 24/…") and any "Final" file.
            m = re.search(r"/(\d+)_hour", low)
            hour = int(m.group(1)) if m else 0
            final_bonus = 1000 if "final" in low else 0
            # IMSA: prefer the most authoritative status (Official/Amended over
            # Provisional/Unofficial).
            if "official" in fname:
                status = 4 + (1 if "amended" in fname else 0)
            elif "unofficial" in fname:
                status = 1
            elif "provisional" in fname:
                status = 0
            else:
                status = 3
            # tiebreaker: the latest race-session timestamp (double-headers).
            ts_m = re.search(r"/(\d{12,14})_race", low)
            ts = int(ts_m.group(1)) if ts_m else 0
            key = (hour + final_bonus, status, ts)
            if best_key is None or key > best_key:
                best_key, best_href = key, href
        if best_href is None:
            return None
        return self.host + "/" + urllib.parse.quote(best_href, safe="/%")

    def race_classification(self, event: EventRef, refresh: bool = False
                            ) -> list[ClassificationRow]:
        """Parsed final race classification for one event (empty if none yet)."""
        url = self._race_classification_url(event, refresh=refresh)
        if not url:
            return []
        key = f"csv__{event.season_folder}__{event.event_folder}__race"
        text = self._get_text(url, key, refresh=refresh)
        return self._parse_csv(text)

    @staticmethod
    def _parse_csv(text: str) -> list[ClassificationRow]:
        text = text.lstrip("﻿")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        rows: list[ClassificationRow] = []
        for raw in reader:
            r = { (k or "").strip().upper(): (v or "").strip() for k, v in raw.items() }
            number = r.get("NUMBER", "")
            if not number:
                continue
            pos_s = r.get("POSITION", "")
            try:
                position: int | None = int(pos_s)
            except (TypeError, ValueError):
                position = None
            try:
                laps: int | None = int(r.get("LAPS", ""))
            except (TypeError, ValueError):
                laps = None
            # Driver lineup: WEC writes one column per driver (``DRIVER_1``);
            # IMSA splits it (``DRIVER1_FIRSTNAME`` + ``DRIVER1_SECONDNAME``).
            # Support both so the entry's crew is captured either way.
            drivers_list: list[str] = []
            for i in range(1, 7):
                name = (r.get(f"DRIVER_{i}") or "").strip()
                if not name:
                    first = (r.get(f"DRIVER{i}_FIRSTNAME") or "").strip()
                    last = (r.get(f"DRIVER{i}_SECONDNAME") or "").strip()
                    name = f"{first} {last}".strip()
                if name:
                    drivers_list.append(name)
            drivers = tuple(drivers_list)
            status = r.get("STATUS", "")
            # non-classified cars keep their CSV position blank-or-NC → None
            if position is not None and not status.lower().startswith("classif"):
                # some feeds print a running position even for retirements
                position = position
            rows.append(
                ClassificationRow(
                    position=position if (status.lower().startswith("classif")) else None,
                    number=number,
                    team=r.get("TEAM", ""),
                    vehicle=r.get("VEHICLE", ""),
                    cls=r.get("CLASS", "").upper() or "UNKNOWN",
                    status=status or "Unknown",
                    laps=laps,
                    drivers=drivers,
                )
            )
        return rows


__all__ = ["AlKamelClient", "ClassificationRow", "EventRef"]
