"""Composite FE source — real feeds first, synthetic always last.

Tries each source in priority order and returns the first non-``None`` answer,
recording which source served each race so the calibration gate can count only
*real* rounds. The synthetic source never returns ``None``, so the composite
always resolves to a concrete (possibly empty) classification.
"""
from __future__ import annotations

from motorsport_data.schema import Result

from .synthetic import SOURCE_NAME as SYNTHETIC_NAME
from .synthetic import SyntheticFESource

# Sources whose data counts as "real" for the honest calibration gate.
REAL_SOURCES = frozenset({"pulselive", "snapshot", "official"})


class CompositeFESource:
    name = "composite"

    def __init__(self, sources):
        """``sources`` is an ordered list tried first→last. The last entry should
        be a :class:`SyntheticFESource` so there is always a fallback."""
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

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """First real qualifying order across the source stack, or ``None``.

        Only real sources (pulselive / snapshot) implement ``qualifying``; the
        synthetic fallback has none, so a non-``None`` answer here is real by
        construction — the same honesty contract as the calibration gate.
        """
        for source in self._sources:
            q = getattr(source, "qualifying", None)
            if q is None:
                continue
            try:
                order = q(year, round)
            except Exception:
                order = None
            if order:
                return list(order)
        return None

    def race_rows(self, year: int, round: int) -> list[dict] | None:
        """Full entry rows (classified + DNFs, with grid/points/flags) from the
        first real source that carries them; None when only synthetic answers."""
        for source in self._sources:
            rr = getattr(source, "race_rows", None)
            if rr is None:
                continue
            try:
                rows = rr(year, round)
            except Exception:
                rows = None
            if rows:
                return rows
        return None

    @staticmethod
    def default():
        """Offline real data first: the committed snapshots (real,
        deterministic), then synthetic for upcoming rounds. This is the
        production default and needs no network."""
        from .snapshot import SnapshotFESource

        return CompositeFESource([SnapshotFESource(), SyntheticFESource()])

    @staticmethod
    def live():
        """Live network feed first (fresh Pulselive fetch), then the committed
        snapshot, then synthetic. Used when ``FE_USE_LIVE_RESULTS=1`` — mainly
        to refresh data; builds normally use :meth:`default` for
        reproducibility."""
        from .pulselive_source import PulseliveFESource
        from .snapshot import SnapshotFESource

        return CompositeFESource(
            [PulseliveFESource(), SnapshotFESource(), SyntheticFESource()]
        )

    @staticmethod
    def is_real(provenance: str) -> bool:
        return provenance in REAL_SOURCES
