"""The unique IMSA model behaviours: valid per-class markets, leakage-safety, and
the never-ship-worse gate against the season-form baseline.

IMSA is multi-class, so a round is one race *per class* and every market is keyed
by class. Kept fast (OMP_NUM_THREADS=1, small n_samples).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("OMP_NUM_THREADS", "1")

from imsa_predictions import config, forward_eval, model
from imsa_predictions.datasource import ImsaDataSource


@pytest.fixture
def source():
    return ImsaDataSource()


@pytest.fixture
def completed_round(source):
    """A completed round + the classes that ran it (falls back to the last one)."""
    rnd = max(source.completed_rounds(config.SEASON))
    classes = source.classes_for_round(config.SEASON, rnd)
    return rnd, classes


# --------------------------------------------------------------------------- #
# Valid per-class markets
# --------------------------------------------------------------------------- #
def test_each_class_is_a_valid_market(source, completed_round):
    rnd, classes = completed_round
    scored = 0
    for cls in classes:
        fc = model.forecast_class(source, config.SEASON, rnd, cls, n_samples=2000)
        if fc is None:
            continue
        scored += 1
        field = fc.field
        # order is a full permutation of the class field
        assert sorted(fc.order) == sorted(field)
        # the win market is mutually exclusive → sums to ~1.0
        assert abs(sum(fc.markets.p_win.values()) - 1.0) < 0.05, f"{cls} win market not normalised"
        # p_podium is P(top-3) per entry → expected #podium finishers ≈ 3
        assert abs(sum(fc.markets.p_podium.values()) - 3.0) < 0.2, f"{cls} podium mass off"
        # a strong entry (the model's favourite) gets a non-trivial win probability,
        # clearly above the uniform 1/field baseline.
        top_pwin = max(fc.markets.p_win.values())
        assert top_pwin > 1.5 / len(field), f"{cls} favourite not distinguished from uniform"
    assert scored >= 1, "no classes forecast for the completed round"


def test_cumulative_markets_are_monotonic(source, completed_round):
    rnd, classes = completed_round
    for cls in classes:
        fc = model.forecast_class(source, config.SEASON, rnd, cls, n_samples=2000)
        if fc is None:
            continue
        m = fc.markets
        for code in fc.order:
            assert m.p_top10[code] >= m.p_top6[code] >= m.p_podium[code] >= m.p_win[code] - 1e-9


# --------------------------------------------------------------------------- #
# Leakage-safety: a forecast never sees its own round's results
# --------------------------------------------------------------------------- #
def test_forecast_is_deterministic_and_not_an_oracle(source):
    """The season opener has no in-season prior rounds, so it forecasts purely from
    cross-season history. If the model leaked round 1's own result it would be a
    perfect predictor; instead it produces a deterministic, non-perfect order."""
    year = config.SEASON
    opener = min(source.completed_rounds(year))
    cls = source.classes_for_round(year, opener)[0]
    fc_a = model.forecast_class(source, year, opener, cls, n_samples=2000)
    fc_b = model.forecast_class(source, year, opener, cls, n_samples=2000)
    assert fc_a is not None
    # deterministic (shared seed) → identical order run-to-run
    assert fc_a.order == fc_b.order
    # leakage-safe: the predicted order does NOT reproduce the actual result
    actual = {r.competitor: r.position for r in source.class_results(year, opener, cls)}
    predicted = {code: i for i, code in enumerate(fc_a.order, start=1)}
    from motorsport_core import eval as core_eval

    mpe = core_eval.mean_position_error(predicted, actual)
    assert mpe is not None and mpe > 0.5, "opener forecast suspiciously reproduces the label"


# --------------------------------------------------------------------------- #
# Never-ship-worse gate (recomputed inline, small n_samples for speed)
# --------------------------------------------------------------------------- #
def test_model_not_worse_than_season_form_baseline(source, monkeypatch):
    """Aggregate win+podium Brier over the modern GTP era (2024-2026) must not be
    worse than the season-form baseline by more than a tiny Monte-Carlo tolerance —
    the honest never-ship-worse property the model was tuned for.

    Reuses the production forward-eval scoring path with a reduced sample count."""
    monkeypatch.setattr(forward_eval, "NS", 2000)

    all_blocks: list[dict] = []
    for year in (2024, 2025, 2026):
        for rnd in forward_eval.evaluate_season(source, year):
            all_blocks.extend(rnd["classes"])
    assert all_blocks, "no class-rounds scored across 2024-2026"

    summary = forward_eval._summarise(all_blocks)
    model_agg = summary["model"]["winBrier"] + summary["model"]["podiumBrier"]
    form_agg = summary["seasonForm"]["winBrier"] + summary["seasonForm"]["podiumBrier"]
    assert model_agg <= form_agg + 0.02, (
        f"model win+podium Brier {model_agg:.4f} worse than season-form {form_agg:.4f}"
    )
