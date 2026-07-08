"""Shared NASCAR test plumbing.

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

    def stage_results(self, year, round):
        if self._hidden(year, round):
            return None
        sr = getattr(self._inner, "stage_results", None)
        return sr(year, round) if sr else None

    def qualifying(self, year, round):
        if self._hidden(year, round):
            return None
        q = getattr(self._inner, "qualifying", None)
        return q(year, round) if q else None

    def entry_list(self, year, round):
        return None

    def calendar(self, year):
        cal = getattr(self._inner, "calendar", None)
        return cal(year) if cal else []

    def provenance(self, year, round, race_index: int = 0):
        return "snapshot"


class FakeCacherClient:
    """Offline stand-in for NascarCacherClient, serving fixture payloads."""

    def __init__(self, race_lists: dict | None = None, weekends: dict | None = None):
        self._race_lists = race_lists or {}
        self._weekends = weekends or {}
        self.requests: list[tuple] = []

    def race_list(self, year: int):
        self.requests.append(("race_list", year))
        return self._race_lists.get(year)

    def weekend_feed(self, year: int, race_id: int, series: int | None = None):
        self.requests.append(("weekend", year, race_id))
        return self._weekends.get((year, race_id))


@pytest.fixture()
def snapshot_source():
    from nascar_predictions.sources.snapshot import SnapshotNascarSource

    return SnapshotNascarSource()


@pytest.fixture()
def real_source():
    """The production default source stack (committed snapshots + synthetic)."""
    from nascar_predictions.datasource import NascarDataSource

    return NascarDataSource()


@pytest.fixture()
def truncated_source():
    """NascarDataSource seeing only the first 6 rounds of the active season."""
    from nascar_predictions import config
    from nascar_predictions.datasource import NascarDataSource
    from nascar_predictions.sources.composite import CompositeNascarSource
    from nascar_predictions.sources.snapshot import SnapshotNascarSource

    composite = CompositeNascarSource([TruncatedSource(SnapshotNascarSource(), config.SEASON, 6)])
    return NascarDataSource(source=composite)
