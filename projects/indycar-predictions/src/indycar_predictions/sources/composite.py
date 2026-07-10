"""Composite IndyCar source — committed snapshots first, synthetic always last.

Tries each source in priority order and returns the first non-``None`` answer,
recording which source served each race so the calibration gate can count only
*real* rounds. The synthetic source never returns ``None``, so the composite
always resolves to a concrete (possibly empty) classification.

Snapshot-primary inversion: unlike the API-backed projects, the LIVE scraper
never leads the stack — the committed history files are canonical and the
scraper only feeds :mod:`..refresh`. ``live()`` therefore still puts the
snapshot first and the scraper behind it (a freshness probe, not an override),
so a transient wiki edit can never displace verified data at build time.
"""
from __future__ import annotations

from motorsport_data.schema import Result

from .synthetic import SOURCE_NAME as SYNTHETIC_NAME
from .synthetic import SyntheticIndycarSource

# Sources whose data counts as "real" for the honest calibration gate.
REAL_SOURCES = frozenset({"snapshot", "wikipedia", "official"})


class CompositeIndycarSource:
    name = "composite"

    def __init__(self, sources):
        """``sources`` is an ordered list tried first→last. The last entry
        should be a :class:`SyntheticIndycarSource` so there is always a
        fallback."""
        self._sources = list(sources)
        self._provenance: dict[tuple[int, int], str] = {}

    def results(self, year: int, round: int, race_index: int = 0) -> list[Result]:
        for source in self._sources:
            res = source.results(year, round, race_index)
            if res is not None:
                self._provenance[(year, round)] = source.name
                return res
        # Should be unreachable when a synthetic source is present.
        self._provenance[(year, round)] = SYNTHETIC_NAME
        return []

    def provenance(self, year: int, round: int, race_index: int = 0) -> str:
        key = (year, round)
        if key not in self._provenance:
            # Resolve lazily so provenance is correct even if results() wasn't called.
            self.results(year, round)
        return self._provenance.get(key, "unknown")

    def _first(self, method: str, year: int, round: int):
        """First non-empty answer for an optional accessor across the stack.

        Only real sources implement these accessors; the synthetic fallback
        has none, so a non-``None`` answer is real by construction — the same
        honesty contract as the calibration gate.
        """
        for source in self._sources:
            fn = getattr(source, method, None)
            if fn is None:
                continue
            try:
                out = fn(year, round)
            except Exception:
                out = None
            if out:
                return out
        return None

    def qualifying(self, year: int, round: int) -> list[str] | None:
        out = self._first("qualifying", year, round)
        return list(out) if out else None

    def race_rows(self, year: int, round: int) -> list[dict] | None:
        return self._first("race_rows", year, round)

    def calendar(self, year: int) -> list[dict]:
        for source in self._sources:
            cal = getattr(source, "calendar", None)
            if cal is None:
                continue
            try:
                entries = cal(year)
            except Exception:
                entries = []
            if entries:
                return entries
        return []

    def standings(self, year: int) -> list[dict]:
        for source in self._sources:
            fn = getattr(source, "standings", None)
            if fn is None:
                continue
            try:
                rows = fn(year)
            except Exception:
                rows = []
            if rows:
                return list(rows)
        return []

    @staticmethod
    def default():
        """Offline real data first: the committed history files (canonical,
        deterministic), then synthetic for anything they don't cover. This is
        the production default and needs no network."""
        from .snapshot import SnapshotIndycarSource

        return CompositeIndycarSource([SnapshotIndycarSource(), SyntheticIndycarSource()])

    @staticmethod
    def live():
        """Snapshot still first (it is the source of truth), with the
        Wikipedia scraper behind it as a freshness probe, then synthetic.
        Used when ``INDYCAR_USE_LIVE_RESULTS=1`` — mainly by the race-weekend
        gate; builds normally use :meth:`default` for reproducibility."""
        from .indycar_scraper_source import IndycarScraperSource
        from .snapshot import SnapshotIndycarSource

        return CompositeIndycarSource(
            [SnapshotIndycarSource(), IndycarScraperSource(), SyntheticIndycarSource()]
        )

    @staticmethod
    def is_real(provenance: str) -> bool:
        return provenance in REAL_SOURCES
