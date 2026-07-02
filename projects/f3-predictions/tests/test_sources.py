"""Phase 2 source seam: real-feed selection, graceful fallback, provenance."""

import pytest

from f3_predictions import config
from f3_predictions.datasource import F3DataSource
from f3_predictions.sources import (
    CompositeF3Source,
    FastF1F3Source,
    OfficialF3Source,
    SyntheticF3Source,
)


def test_synthetic_source_is_deterministic_and_complete():
    s = SyntheticF3Source()
    a = [r.competitor for r in s.results(config.SEASON, 2, race_index=1)]
    b = [r.competitor for r in s.results(config.SEASON, 2, race_index=1)]
    assert a == b
    assert len(a) == len(config.DRIVERS)
    assert s.results(config.SEASON, config.COMPLETED_ROUNDS + 1) == []  # unrun → []


def test_real_sources_defer_when_unavailable():
    # FastF1 has no F3 results API and the official feed is disabled by default,
    # so both return None (defer) rather than guessing.
    assert FastF1F3Source().results(config.SEASON, 1, 1) is None
    assert OfficialF3Source().results(config.SEASON, 1, 1) is None


def test_composite_default_serves_real_snapshot():
    # The default composite is snapshot-first: completed rounds resolve to the
    # committed real data (classified finishers only — retirements excluded).
    comp = CompositeF3Source.default()
    res = comp.results(config.SEASON, 1, race_index=1)
    assert 12 <= len(res) <= len(config.DRIVERS)
    assert comp.provenance(config.SEASON, 1, 1) == "snapshot"
    assert CompositeF3Source.is_real("snapshot")
    assert not CompositeF3Source.is_real("synthetic")


def test_composite_falls_back_to_synthetic_without_real_sources():
    comp = CompositeF3Source([SyntheticF3Source()])
    res = comp.results(config.SEASON, 1, race_index=1)
    assert len(res) == len(config.DRIVERS)
    assert comp.provenance(config.SEASON, 1, 1) == "synthetic"


def test_composite_prefers_a_real_source():
    class FakeReal:
        name = "fastf1"

        def __init__(self):
            self._syn = SyntheticF3Source()

        def results(self, year, round, race_index=1):
            res = self._syn.results(year, round, race_index)
            return res if res else None  # real only for rounds that have run

    comp = CompositeF3Source([FakeReal(), SyntheticF3Source()])
    assert len(comp.results(config.SEASON, 1, 1)) == len(config.DRIVERS)
    assert comp.provenance(config.SEASON, 1, 1) == "fastf1"
    assert CompositeF3Source.is_real(comp.provenance(config.SEASON, 1, 1))
    # An unrun round has no real data → falls back to synthetic.
    assert comp.provenance(config.SEASON, config.COMPLETED_ROUNDS + 1, 1) == "synthetic"


def test_datasource_serves_real_data_by_default():
    s = F3DataSource()  # default = snapshot (real) + synthetic fallback
    assert 12 <= len(s.results(config.SEASON, 1)) <= len(config.DRIVERS)
    assert s.results(config.SEASON, len(config.CALENDAR)) == []  # finale not yet run
    assert s.provenance(config.SEASON, 1, 1) == "snapshot"
    races = s.race_results_for_round(config.SEASON, 1)
    assert races["sprint"] and races["feature"]


def test_live_composite_priority_order():
    # Live mode tries the network FIA scrape first, then the offline snapshot,
    # then synthetic — verified structurally so the test stays offline.
    comp = CompositeF3Source.live()
    assert [src.name for src in comp._sources] == ["fia", "snapshot", "synthetic"]


@pytest.mark.parametrize("race_index", [0, 1])
def test_sprint_and_feature_indices_resolve(race_index):
    s = F3DataSource()
    assert 12 <= len(s.results(config.SEASON, 1, race_index=race_index)) <= len(config.DRIVERS)
