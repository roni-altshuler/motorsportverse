"""Phase 2 source seam: real-feed selection, graceful fallback, provenance."""

import pytest

from f2_predictions import config
from f2_predictions.datasource import F2DataSource
from f2_predictions.sources import (
    CompositeF2Source,
    FastF1F2Source,
    OfficialF2Source,
    SyntheticF2Source,
)


def test_synthetic_source_is_deterministic_and_complete():
    s = SyntheticF2Source()
    a = [r.competitor for r in s.results(config.SEASON, 2, race_index=1)]
    b = [r.competitor for r in s.results(config.SEASON, 2, race_index=1)]
    assert a == b
    assert len(a) == 22
    assert s.results(config.SEASON, config.COMPLETED_ROUNDS + 1) == []  # unrun → []


def test_real_sources_defer_when_unavailable():
    # FastF1 has no F2 results API and the official feed is disabled by default,
    # so both return None (defer) rather than guessing.
    assert FastF1F2Source().results(config.SEASON, 1, 1) is None
    assert OfficialF2Source().results(config.SEASON, 1, 1) is None


def test_composite_falls_back_to_synthetic():
    comp = CompositeF2Source.default()
    res = comp.results(config.SEASON, 1, race_index=1)
    assert len(res) == 22
    assert comp.provenance(config.SEASON, 1, 1) == "synthetic"
    assert not CompositeF2Source.is_real("synthetic")


def test_composite_prefers_a_real_source():
    class FakeReal:
        name = "fastf1"

        def __init__(self):
            self._syn = SyntheticF2Source()

        def results(self, year, round, race_index=1):
            res = self._syn.results(year, round, race_index)
            return res if res else None  # real only for rounds that have run

    comp = CompositeF2Source([FakeReal(), SyntheticF2Source()])
    assert len(comp.results(config.SEASON, 1, 1)) == 22
    assert comp.provenance(config.SEASON, 1, 1) == "fastf1"
    assert CompositeF2Source.is_real(comp.provenance(config.SEASON, 1, 1))
    # An unrun round has no real data → falls back to synthetic.
    assert comp.provenance(config.SEASON, config.COMPLETED_ROUNDS + 1, 1) == "synthetic"


def test_datasource_public_api_unchanged_by_default():
    s = F2DataSource()  # live off by default
    assert len(s.results(config.SEASON, 1)) == 22
    assert s.results(config.SEASON, config.COMPLETED_ROUNDS + 1) == []
    assert s.provenance(config.SEASON, 1, 1) == "synthetic"
    races = s.race_results_for_round(config.SEASON, 1)
    assert len(races["sprint"]) == 22 and len(races["feature"]) == 22


def test_live_mode_still_falls_back_safely():
    # With no real feed wired, live mode resolves to synthetic — never breaks.
    s = F2DataSource(live=True)
    assert len(s.results(config.SEASON, 1)) == 22
    assert s.provenance(config.SEASON, 1, 1) == "synthetic"


@pytest.mark.parametrize("race_index", [0, 1])
def test_sprint_and_feature_indices_resolve(race_index):
    s = F2DataSource()
    assert len(s.results(config.SEASON, 1, race_index=race_index)) == 22
