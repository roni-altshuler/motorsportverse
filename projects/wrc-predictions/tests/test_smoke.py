"""Smoke tests — the package imports and the real backend produces a forecast."""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")


def test_imports():
    from wrc_predictions.datasource import WrcDataSource  # noqa: F401
    from wrc_predictions.predict import WrcPredictor  # noqa: F401


def test_snapshot_is_real_and_loaded():
    from wrc_predictions import config

    assert config.SPORT == "WRC"
    assert config.COMPLETED_ROUNDS >= 1
    assert len(config.DRIVERS) >= 15
    # every round carries a surface (the defining rally variable)
    assert set(config.SURFACE_OF.values()) <= {"gravel", "tarmac", "snow"}
    assert all(config.surface_for_round(r) for r in config.SURFACE_OF)


def test_predictor_produces_ranked_probabilistic_forecast():
    from wrc_predictions import config
    from wrc_predictions.datasource import WrcDataSource
    from wrc_predictions.predict import WrcPredictor

    src = WrcDataSource()
    rnd = min(config.COMPLETED_ROUNDS, 6) or 1
    fc = WrcPredictor().predict(src, config.SEASON, rnd)

    assert len(fc.predicted_order) == len(config.DRIVERS)
    assert sorted(fc.predicted_order.values()) == list(range(1, len(config.DRIVERS) + 1))
    pw = dict(fc.probabilities.p_win)
    assert abs(sum(pw.values()) - 1.0) < 0.05, "win market not normalised"
    assert max(pw.values()) < 0.85, "degenerate over-confident favourite"
    assert sum(1 for p in pw.values() if p > 0) >= 8, "market collapsed onto too few crews"
