"""Smoke tests — the package imports and the backend forecasts the next round."""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")


def test_imports():
    import wec_predictions  # noqa: F401
    from wec_predictions import config, export, forward_eval, model, refresh  # noqa: F401
    from wec_predictions.datasource import WecDataSource  # noqa: F401
    from wec_predictions.predict import main  # noqa: F401


def test_predict_next_round_runs():
    from wec_predictions import config, model
    from wec_predictions.datasource import WecDataSource

    src = WecDataSource()
    rnd = config.next_round()
    fc = model.forecast_round(src, config.SEASON, rnd, n_samples=1500)

    assert fc.round == rnd
    assert fc.classes, "next-round forecast produced no classes"
    for cf in fc.classes:
        # a complete, non-degenerate per-class market
        assert len(cf.order) == len(cf.field) >= 2
        assert abs(sum(cf.markets.p_win.values()) - 1.0) < 0.05
