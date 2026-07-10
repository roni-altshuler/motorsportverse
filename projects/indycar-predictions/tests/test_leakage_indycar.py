"""Leakage tests: forecasts for round N must be blind to round >= N results."""
from __future__ import annotations

import pytest

from indycar_predictions import config, model
from indycar_predictions.datasource import IndycarDataSource
from indycar_predictions.sources.snapshot import SnapshotIndycarSource

SEASON = config.SEASON


class _TamperedSource:
    """Snapshot source whose results AT/AFTER a cutoff round are inverted.

    If the model peeks at the current round (or any later one), the tampering
    changes its output — the twin-source equality test below catches it.
    """

    name = "snapshot"

    def __init__(self, cutoff: int):
        self._inner = SnapshotIndycarSource()
        self._cutoff = cutoff

    def results(self, year, round, race_index: int = 0):
        res = self._inner.results(year, round, race_index)
        if res and year == SEASON and round >= self._cutoff:
            flipped = list(reversed(res))
            return [r.model_copy(update={"position": i}) for i, r in enumerate(flipped, start=1)]
        return res

    def race_rows(self, year, round):
        rows = self._inner.race_rows(year, round)
        if rows and year == SEASON and round >= self._cutoff:
            flipped = list(reversed(rows))
            return [
                {**r, "position": i, "dnf": not r.get("dnf", False)}
                for i, r in enumerate(flipped, start=1)
            ]
        return rows

    def qualifying(self, year, round):
        return None

    def calendar(self, year):
        return self._inner.calendar(year)

    def standings(self, year):
        return self._inner.standings(year)

    def provenance(self, year, round, race_index: int = 0):
        return "snapshot"


CUTOFF = 5


def test_skill_and_hazard_blind_to_current_and_future_rounds():
    clean = IndycarDataSource(source=SnapshotIndycarSource())
    tampered = IndycarDataSource(source=_TamperedSource(CUTOFF))
    assert model.estimate_skill(clean, SEASON, CUTOFF) == model.estimate_skill(
        tampered, SEASON, CUTOFF
    )
    assert model.estimate_dnf_risk(clean, SEASON, CUTOFF) == model.estimate_dnf_risk(
        tampered, SEASON, CUTOFF
    )


def test_skill_sees_prior_rounds():
    """Sanity check the tampering is real: a forecast for CUTOFF+1 (which may
    see round CUTOFF) must differ between the two sources."""
    clean = IndycarDataSource(source=SnapshotIndycarSource())
    tampered = IndycarDataSource(source=_TamperedSource(CUTOFF))
    assert model.estimate_skill(clean, SEASON, CUTOFF + 1) != model.estimate_skill(
        tampered, SEASON, CUTOFF + 1
    )


def test_assert_prior_only_guard():
    from motorsport_core.leakage import LeakageError, assert_prior_only

    with pytest.raises(LeakageError):
        assert_prior_only({5: None}, current_round=5, label="indycar.test")
    assert_prior_only({4: None}, current_round=5, label="indycar.test")
