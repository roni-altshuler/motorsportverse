"""Shared FE test plumbing.

Everything here (and in every test) is OFFLINE: results come from the
committed snapshots (``data/official_2026.json`` + ``data/seasons/<year>.json``)
or fixtures — never the network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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

    def results(self, year, round, race_index: int = 0):
        if year == self._year and round > self._upto:
            return []
        return self._inner.results(year, round, race_index)

    def race_rows(self, year, round):
        if year == self._year and round > self._upto:
            return None
        rr = getattr(self._inner, "race_rows", None)
        return rr(year, round) if rr else None

    def qualifying(self, year, round):
        if year == self._year and round > self._upto:
            return None
        q = getattr(self._inner, "qualifying", None)
        return q(year, round) if q else None

    def calendar(self, year):
        cal = getattr(self._inner, "calendar", None)
        return cal(year) if cal else []

    def provenance(self, year, round, race_index: int = 0):
        return "snapshot"


@pytest.fixture()
def snapshot_source():
    from formula_e_predictions.sources.snapshot import SnapshotFESource

    return SnapshotFESource()


@pytest.fixture()
def real_source():
    """The production default source stack (committed snapshots + synthetic)."""
    from formula_e_predictions.datasource import FEDataSource

    return FEDataSource()


@pytest.fixture()
def truncated_source():
    """FEDataSource seeing only the first 5 rounds of the active season."""
    from formula_e_predictions import config
    from formula_e_predictions.datasource import FEDataSource
    from formula_e_predictions.sources.composite import CompositeFESource
    from formula_e_predictions.sources.snapshot import SnapshotFESource

    composite = CompositeFESource([TruncatedSource(SnapshotFESource(), config.SEASON, 5)])
    return FEDataSource(source=composite)
