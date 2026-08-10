"""Smoke tests — the package imports and the real backend produces a forecast."""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")


def test_imports():
    from motogp_predictions.datasource import MotoGPDataSource  # noqa: F401
    from motogp_predictions.predict import MotoGPPredictor  # noqa: F401


def test_snapshot_is_real_and_loaded():
    from motogp_predictions import config

    assert config.SPORT == "MotoGP"
    assert config.COMPLETED_ROUNDS >= 1, "no completed rounds in the committed snapshot"
    assert len(config.DRIVERS) >= 15, "roster not derived from the snapshot"
    assert set(config.MANUFACTURERS) & {"Ducati", "Aprilia", "KTM"}, "manufacturers missing"


def test_predictor_produces_ranked_probabilistic_forecast():
    from motogp_predictions import config
    from motogp_predictions.datasource import MotoGPDataSource
    from motogp_predictions.predict import MotoGPPredictor

    src = MotoGPDataSource()
    rnd = min(config.COMPLETED_ROUNDS, 6) or 1
    fc = MotoGPPredictor().predict(src, config.SEASON, rnd)

    # a complete permutation over the field
    assert len(fc.predicted_order) == len(config.DRIVERS)
    assert sorted(fc.predicted_order.values()) == list(range(1, len(config.DRIVERS) + 1))
    # non-degenerate markets (the suite-wide anti-collapse contract). Raw
    # Monte-Carlo win probability legitimately rounds to 0 for backmarkers in a
    # ~29-rider field, so we assert the market is *spread* (many live contenders,
    # no over-confident favourite, normalised) rather than strictly all-positive.
    pw = dict(fc.probabilities.p_win)
    assert abs(sum(pw.values()) - 1.0) < 0.05, "win market not normalised"
    assert max(pw.values()) < 0.85, "degenerate over-confident favourite"
    assert sum(1 for p in pw.values() if p > 0) >= 8, "market collapsed onto too few riders"
