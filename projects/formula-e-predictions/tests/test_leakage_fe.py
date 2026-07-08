"""Leakage tests: forecasts for round N must be blind to round >= N results."""
from __future__ import annotations

import pytest

from formula_e_predictions import config, model
from formula_e_predictions.datasource import FEDataSource
from formula_e_predictions.sources.snapshot import SnapshotFESource

SEASON = config.SEASON


class _TamperedSource:
    """Snapshot source whose results AT/AFTER a cutoff round are inverted.

    If the model peeks at the current round (or any later one), the tampering
    changes its output — the twin-source equality test below catches it.
    """

    name = "snapshot"

    def __init__(self, cutoff: int):
        self._inner = SnapshotFESource()
        self._cutoff = cutoff

    def results(self, year, round, race_index: int = 0):
        res = self._inner.results(year, round, race_index)
        if res and year == SEASON and round >= self._cutoff:
            flipped = list(reversed(res))
            return [r.model_copy(update={"position": i}) for i, r in enumerate(flipped, start=1)]
        return res

    def race_rows(self, year, round):
        return self._inner.race_rows(year, round)

    def qualifying(self, year, round):
        return None

    def provenance(self, year, round, race_index: int = 0):
        return "snapshot"

    def calendar(self, year):
        return self._inner.calendar(year)


CUTOFF = 5


def test_skill_blind_to_current_and_future_rounds():
    clean = FEDataSource(source=SnapshotFESource())
    tampered = FEDataSource(source=_TamperedSource(CUTOFF))
    pace_clean = model.estimate_skill(clean, SEASON, CUTOFF)
    pace_tampered = model.estimate_skill(tampered, SEASON, CUTOFF)
    assert pace_clean == pace_tampered


def test_skill_sees_prior_rounds():
    """Sanity check the tampering is real: a forecast for CUTOFF+1 (which may
    see round CUTOFF) must differ between the two sources."""
    clean = FEDataSource(source=SnapshotFESource())
    tampered = FEDataSource(source=_TamperedSource(CUTOFF))
    pace_clean = model.estimate_skill(clean, SEASON, CUTOFF + 1)
    pace_tampered = model.estimate_skill(tampered, SEASON, CUTOFF + 1)
    assert pace_clean != pace_tampered


def test_assert_prior_only_guard():
    from motorsport_core.leakage import LeakageError, assert_prior_only

    with pytest.raises(LeakageError):
        assert_prior_only({5: None}, current_round=5, label="fe.test")
    assert_prior_only({4: None}, current_round=5, label="fe.test")


def test_elo_replay_rejects_future_events(real_source):
    """The Elo builder's cutoff rejects events at/after the boundary."""
    from motorsport_core import elo

    builder = elo.EloFeatureBuilder()
    events = model._season_events(real_source, SEASON)
    with pytest.raises(ValueError):
        builder.replay_history(events, current_season=SEASON, current_round=1)
