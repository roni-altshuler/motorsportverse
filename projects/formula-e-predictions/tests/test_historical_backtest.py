"""Historical backtest: multi-season replay, aggregation, reliability."""
from __future__ import annotations

from formula_e_predictions import config, historical_backtest as hb
from formula_e_predictions.datasource import FEDataSource
from formula_e_predictions.sources.composite import CompositeFESource
from formula_e_predictions.sources.snapshot import SnapshotFESource

from conftest import TruncatedSource


def _truncated(year: int, upto: int) -> FEDataSource:
    composite = CompositeFESource([TruncatedSource(SnapshotFESource(), year, upto)])
    return FEDataSource(source=composite)


def test_replay_season_scores_real_past_rounds():
    source = _truncated(2023, 3)
    rep = hb.replay_season(source, 2023)
    assert len(rep["rounds"]) == 3
    for block in rep["rounds"]:
        assert block["drivers_compared"] >= 15
        assert block["mean_position_error"] is not None
        assert len(block["biggest_misses"]) == 5
    # Market pairs pooled over every scored race.
    assert len(rep["market_pairs"]["win"]) > 0


def test_replay_skips_missing_seasons():
    source = FEDataSource()
    rep = hb.replay_season(source, 2016)  # pre-window, no committed snapshot
    assert rep["rounds"] == []


def test_backtest_payload_shape():
    payload = hb.backtest([2023])  # full 2023 replay via committed snapshot
    assert payload["seasons"] == [2023]
    per = payload["perSeason"][0]
    assert per["season"] == 2023
    assert per["summary"]["rounds_evaluated"] == 16
    assert payload["roundsEvaluated"] == 16
    assert payload["finishersOnly"] is True
    for m in hb.MARKETS:
        rep = payload["markets"][m]
        assert rep["samples"] > 0 and rep["brier"] is not None
        assert rep["plot"] == f"reliability_plots/reliability_{m}.png"


def test_reliability_bins_edges():
    pairs = [(0.0, 0), (0.05, 0), (0.95, 1), (1.0, 1)]
    bins = hb._reliability_bins(pairs, n_bins=10)
    assert sum(b["count"] for b in bins) == 4  # p=1.0 lands in the last bin
    assert bins[0]["binLo"] == 0.0
    assert bins[-1]["binHi"] == 1.0


def test_market_report_empty():
    rep = hb._market_report([])
    assert rep == {"brier": None, "logLoss": None, "samples": 0, "reliability": []}


def test_season_summary_empty():
    s = hb._season_summary([])
    assert s["rounds_evaluated"] == 0
    assert s["season_mean_error"] is None


def test_write_outputs(tmp_path):
    source = _truncated(2023, 2)
    rep = hb.replay_season(source, 2023)
    payload = {
        "season": 2023,
        "seasons": [2023],
        "generatedAt": "t",
        "source": "test",
        "scoring": "test",
        "finishersOnly": True,
        "roundsEvaluated": len(rep["rounds"]),
        "totalRows": rep["rows"],
        "pooledSummary": hb._season_summary(rep["rounds"]),
        "perSeason": [{"season": 2023, "summary": hb._season_summary(rep["rounds"]), "rounds": rep["rounds"]}],
        "perDriver": hb._per_driver(rep["driver_errors"]),
        "markets": {m: {**hb._market_report(rep["market_pairs"][m]), "plot": f"reliability_plots/reliability_{m}.png"} for m in hb.MARKETS},
    }
    written = hb.write_outputs(payload, tmp_path / "backtest", tmp_path / "plots")
    assert (tmp_path / "backtest" / "summary.json").exists()
    for m in hb.MARKETS:
        assert (tmp_path / "plots" / f"reliability_{m}.png").exists()
    assert len(written) == 1 + len(hb.MARKETS)


def test_default_seasons_are_gen3_window():
    assert list(hb.DEFAULT_SEASONS) == list(range(config.ML_FIRST_SEASON, config.SEASON + 1))
