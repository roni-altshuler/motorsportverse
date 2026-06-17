"""Composite F2 source — real feeds first, synthetic always last.

Tries each source in priority order and returns the first non-``None`` answer,
recording which source served each race so the calibration gate can count only
*real* rounds. The synthetic source never returns ``None``, so the composite
always resolves to a concrete (possibly empty) classification.
"""
from __future__ import annotations

from motorsport_data.schema import Result

from .synthetic import SOURCE_NAME as SYNTHETIC_NAME
from .synthetic import SyntheticF2Source

# Sources whose data counts as "real" for the honest calibration gate.
REAL_SOURCES = frozenset({"fastf1", "official", "fia", "snapshot"})


class CompositeF2Source:
    name = "composite"

    def __init__(self, sources):
        """``sources`` is an ordered list tried first→last. The last entry should
        be a :class:`SyntheticF2Source` so there is always a fallback."""
        self._sources = list(sources)
        self._provenance: dict[tuple[int, int, int], str] = {}

    def results(self, year: int, round: int, race_index: int = 1) -> list[Result]:
        for source in self._sources:
            res = source.results(year, round, race_index)
            if res is not None:
                self._provenance[(year, round, race_index)] = source.name
                return res
        # Should be unreachable when a synthetic source is present.
        self._provenance[(year, round, race_index)] = SYNTHETIC_NAME
        return []

    def provenance(self, year: int, round: int, race_index: int = 1) -> str:
        key = (year, round, race_index)
        if key not in self._provenance:
            # Resolve lazily so provenance is correct even if results() wasn't called.
            self.results(year, round, race_index)
        return self._provenance.get(key, "unknown")

    @staticmethod
    def default():
        """Offline real data first: the committed snapshot (real, deterministic),
        then synthetic for upcoming rounds. This is the production default and
        needs no network."""
        from .snapshot import SnapshotF2Source

        return CompositeF2Source([SnapshotF2Source(), SyntheticF2Source()])

    @staticmethod
    def live():
        """Live network feed first (fresh FIA scrape), then the committed
        snapshot, then synthetic. Used when ``F2_USE_LIVE_RESULTS=1`` — mainly to
        refresh data; builds normally use :meth:`default` for reproducibility."""
        from .fia_f2_source import FiaF2Source
        from .snapshot import SnapshotF2Source

        return CompositeF2Source([FiaF2Source(), SnapshotF2Source(), SyntheticF2Source()])

    @staticmethod
    def is_real(provenance: str) -> bool:
        return provenance in REAL_SOURCES
