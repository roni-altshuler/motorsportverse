"""Tests for the F3 historical backtest module.

Covers the pure aggregation helpers on small fixtures and an end-to-end run
over the committed real snapshot (deterministic, offline), asserting the JSON
payload shape and that the reliability PNGs are written.
"""
from __future__ import annotations

import json

import pytest

# The backtest renders reliability PNGs; matplotlib is not a core dependency
# (CI installs core+data+xgboost only), so skip honestly instead of failing
# collection where it is absent.
pytest.importorskip("matplotlib")

from f3_predictions import config, historical_backtest as hb  # noqa: E402


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def test_reliability_bins_partitions_and_counts():
    pairs = [(0.05, 0), (0.05, 0), (0.15, 1), (0.95, 1), (1.0, 1)]
    bins = hb._reliability_bins(pairs, n_bins=10)
    # Three occupied bins: [0.0,0.1), [0.1,0.2), and the closed top bin.
    assert len(bins) == 3
    total = sum(b["count"] for b in bins)
    assert total == len(pairs)
    first = bins[0]
    assert first["binLo"] == 0.0 and first["count"] == 2
    assert first["empirical"] == 0.0
    # p == 1.0 lands in the last bin thanks to the closed-right special case.
    assert bins[-1]["count"] == 2


def test_reliability_bins_empty():
    assert hb._reliability_bins([]) == []


def test_market_report_brier_logloss():
    # Perfectly confident, perfectly correct → Brier 0, tiny log-loss.
    pairs = [(1.0, 1), (0.0, 0), (1.0, 1)]
    rep = hb._market_report(pairs)
    assert rep["samples"] == 3
    assert rep["brier"] == 0.0
    assert rep["logLoss"] >= 0.0
    assert isinstance(rep["reliability"], list)


def test_market_report_empty():
    rep = hb._market_report([])
    assert rep == {"brier": None, "logLoss": None, "samples": 0, "reliability": []}


def test_market_pairs_win_has_single_positive():
    actual = {"A": 1, "B": 2, "C": 3}
    probs = {"A": 0.5, "B": 0.3, "C": 0.2}
    pairs = hb._market_pairs(probs, actual, hb.MARKET_THRESHOLD["win"])
    assert sum(y for _, y in pairs) == 1  # exactly one winner
    # The positive pair is the actual winner (A, P1), carrying its predicted prob.
    positive = [p for p, y in pairs if y]
    assert positive == [0.5]


def test_market_pairs_podium_threshold():
    actual = {"A": 1, "B": 2, "C": 3, "D": 4}
    probs = {c: 0.25 for c in actual}
    pairs = hb._market_pairs(probs, actual, hb.MARKET_THRESHOLD["podium"])
    assert sum(y for _, y in pairs) == 3  # top-3 positive


def test_round_block_shape():
    predicted = {"A": 1, "B": 2, "C": 3, "D": 4}
    actual = {"A": 1, "B": 3, "C": 2, "D": 4}
    block = hb._round_block(2, "Monaco", predicted, actual)
    assert block["round"] == 2
    assert block["venueName"] == "Monaco"
    assert block["drivers_compared"] == 4
    assert block["winner_hit"] is True  # A predicted + actual P1
    assert block["exact_matches"] == 2  # A and D exact
    assert 0 <= block["podium_hits"] <= 3
    assert isinstance(block["biggest_misses"], list)
    assert block["mean_position_error"] is not None


def test_season_summary_rates():
    rounds = [
        hb._round_block(1, "R1", {"A": 1, "B": 2, "C": 3}, {"A": 1, "B": 2, "C": 3}),
        hb._round_block(2, "R2", {"A": 1, "B": 2, "C": 3}, {"A": 3, "B": 2, "C": 1}),
    ]
    s = hb._season_summary(rounds)
    assert s["rounds_evaluated"] == 2
    assert 0 <= s["within_3_rate"] <= 1
    assert 0 <= s["podium_hit_rate"] <= 1
    assert s["season_mean_error"] is not None


def test_season_summary_empty():
    s = hb._season_summary([])
    assert s["rounds_evaluated"] == 0
    assert s["season_mean_error"] is None


def test_per_driver_sorted_by_mae():
    errors = {"A": [0, 1], "B": [5, 6], "C": [2]}
    rows = hb._per_driver(errors)
    assert [r["driver"] for r in rows] == ["A", "C", "B"]
    assert rows[0]["mae"] == 0.5
    assert all(0 <= r["within_3_rate"] <= 1 for r in rows)


# --------------------------------------------------------------------------- #
# End-to-end (offline, deterministic real snapshot)
# --------------------------------------------------------------------------- #
def test_backtest_end_to_end(tmp_path):
    payload = hb.backtest(config.SEASON)

    # Season block shape (F1 parity).
    assert payload["season"] == config.SEASON
    assert payload["seasons"] == [config.SEASON]
    assert payload["finishersOnly"] is True
    block = payload["perSeason"][0]
    assert block["season"] == config.SEASON
    assert block["summary"]["rounds_evaluated"] == config.COMPLETED_ROUNDS
    assert len(block["rounds"]) == config.COMPLETED_ROUNDS
    for r in block["rounds"]:
        assert r["drivers_compared"] > 0
        assert r["mean_position_error"] is not None

    # Per-driver aggregation is non-empty and sorted ascending by MAE.
    assert payload["perDriver"]
    maes = [d["mae"] for d in payload["perDriver"]]
    assert maes == sorted(maes)

    # Every market has a report with reliability bins + a plot path.
    for m in hb.MARKETS:
        rep = payload["markets"][m]
        assert rep["samples"] > 0
        assert rep["brier"] is not None
        assert rep["plot"] == f"reliability_plots/reliability_{m}.png"
        assert isinstance(rep["reliability"], list)

    # Writing produces valid JSON + one PNG per market.
    out_dir = tmp_path / "historical_backtest"
    plots_dir = tmp_path / "reliability_plots"
    written = hb.write_outputs(payload, out_dir, plots_dir)
    assert (out_dir / "summary.json").exists()
    reloaded = json.loads((out_dir / "summary.json").read_text())
    assert reloaded["season"] == config.SEASON
    for m in hb.MARKETS:
        png = plots_dir / f"reliability_{m}.png"
        assert png.exists() and png.stat().st_size > 0
    assert len(written) == 1 + len(hb.MARKETS)
