"""Leakage discipline for the MotoGP model — a round may read only prior data.

Unlike a spec series with a fresh grid each year, MotoGP riders carry form across
seasons, so round 1 is legitimately *not* neutral (it seeds from prior seasons).
The invariant that must hold is stronger and purely temporal: forecasting round R
must never read round R's own — or any later round's — race results. Prior seasons
(whole) and this season's rounds strictly before R are the entire admissible set.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("OMP_NUM_THREADS", "1")

from motorsport_core import elo, leakage

from motogp_predictions import config, model
from motogp_predictions.datasource import MotoGPDataSource
from motogp_predictions.sources.snapshot import SnapshotMotoGPSource


class _NoFutureSource:
    """Wraps the real snapshot source but RAISES if any result at/after ``cutoff``
    (in the current season) is read — a hard tripwire for temporal leakage."""

    def __init__(self, inner, year: int, cutoff: int):
        self._inner = inner
        self._year = year
        self._cutoff = cutoff
        self.name = getattr(inner, "name", "snapshot")

    def results(self, year: int, round: int, race_index: int = 1):
        if year == self._year and round >= self._cutoff:
            raise AssertionError(f"LEAKAGE: read round {round} >= cutoff {self._cutoff}")
        return self._inner.results(year, round, race_index)

    def qualifying(self, year: int, round: int):
        return self._inner.qualifying(year, round)

    def completed_rounds(self, year: int):
        done = self._inner.completed_rounds(year)
        return [r for r in done if not (year == self._year and r >= self._cutoff)]

    def provenance(self, year: int, round: int, race_index: int = 1):
        return self._inner.provenance(year, round, race_index)


def test_prior_only_guard_rejects_current_round():
    with pytest.raises(leakage.LeakageError):
        leakage.assert_prior_only({8: None}, current_round=8, label="motogp.model.skill")


def test_elo_replay_rejects_future_event():
    builder = elo.EloFeatureBuilder()
    event = elo.RaceEvent(
        season=config.SEASON,
        round=17,  # sub-round encoding of round 9
        finish_order={"A": 1, "B": 2},
        grid_order=None,
        team_of={"A": "Ducati", "B": "Ducati"},
    )
    with pytest.raises(ValueError):
        builder.replay_history([event], current_season=config.SEASON, current_round=17)


def test_skill_estimate_is_deterministic():
    src = MotoGPDataSource()
    a = model.estimate_skill(src, config.SEASON, current_round=8)
    b = model.estimate_skill(src, config.SEASON, current_round=8)
    assert a == b


def test_forecast_never_reads_its_own_or_later_rounds():
    # The tripwire fires if round R itself is ever read (proves the guard is real)...
    cutoff = 8
    guard = _NoFutureSource(SnapshotMotoGPSource(), config.SEASON, cutoff)
    with pytest.raises(AssertionError):
        guard.results(config.SEASON, cutoff)

    # ...yet the full round-R forecast (post-quali) completes without tripping it,
    # so it demonstrably reads only rounds < R (and prior seasons).
    src = MotoGPDataSource(source=guard)
    grid = guard.qualifying(config.SEASON, cutoff)
    fc = model.forecast_round(src, config.SEASON, cutoff, n_samples=800, known_grid=grid)
    assert sorted(fc.feature.order) == sorted(d["code"] for d in config.DRIVERS)


def test_forecast_is_invariant_to_hiding_the_future():
    # Skill for round R built from the guarded (future-hidden) source must equal the
    # skill from the full source — the later rounds are never consulted, so removing
    # them changes nothing.
    cutoff = 8
    full = MotoGPDataSource()
    guarded = MotoGPDataSource(source=_NoFutureSource(SnapshotMotoGPSource(), config.SEASON, cutoff))
    assert model.estimate_skill(full, config.SEASON, cutoff) == model.estimate_skill(
        guarded, config.SEASON, cutoff
    )
