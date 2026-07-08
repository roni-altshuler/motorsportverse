"""Composite NASCAR source — real feeds first, synthetic always last.

Tries each source in priority order and returns the first non-``None`` answer,
recording which source served each race so the calibration gate can count only
*real* rounds. The synthetic source never returns ``None``, so the composite
always resolves to a concrete (possibly empty) classification.
"""
from __future__ import annotations

from motorsport_data.schema import Result

from .synthetic import SOURCE_NAME as SYNTHETIC_NAME
from .synthetic import SyntheticNascarSource

# Sources whose data counts as "real" for the honest calibration gate.
REAL_SOURCES = frozenset({"nascar-feed", "snapshot", "official"})


class CompositeNascarSource:
    name = "composite"

    def __init__(self, sources):
        """``sources`` is an ordered list tried first→last. The last entry
        should be a :class:`SyntheticNascarSource` so there is always a
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

    def stage_results(self, year: int, round: int) -> dict[str, list[dict]] | None:
        return self._first("stage_results", year, round)

    def entry_list(self, year: int, round: int) -> list[str] | None:
        out = self._first("entry_list", year, round)
        return list(out) if out else None

    @staticmethod
    def default():
        """Offline real data first: the committed snapshots (real,
        deterministic), then synthetic for upcoming rounds. This is the
        production default and needs no network."""
        from .snapshot import SnapshotNascarSource

        return CompositeNascarSource([SnapshotNascarSource(), SyntheticNascarSource()])

    @staticmethod
    def live():
        """Live network feed first (fresh cf.nascar.com fetch), then the
        committed snapshot, then synthetic. Used when
        ``NASCAR_USE_LIVE_RESULTS=1`` — mainly to refresh data; builds
        normally use :meth:`default` for reproducibility."""
        from .nascar_feed_source import NascarFeedSource
        from .snapshot import SnapshotNascarSource

        return CompositeNascarSource(
            [NascarFeedSource(), SnapshotNascarSource(), SyntheticNascarSource()]
        )

    @staticmethod
    def is_real(provenance: str) -> bool:
        return provenance in REAL_SOURCES
