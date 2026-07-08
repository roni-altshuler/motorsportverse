"""Playoff backtest: champion identification, field ground truth, checkpoints."""
from __future__ import annotations

from nascar_predictions import playoff_backtest as pb
from nascar_predictions.datasource import NascarDataSource


def test_actual_champion_from_ground_truth(real_source):
    # Real-world alignment of the archive (final points_position == 1).
    assert pb.actual_champion(real_source, 2022) == "JOLOGANO"
    assert pb.actual_champion(real_source, 2021) == "KYLARSON"
    assert pb.actual_champion(real_source, 2020) == "CHELLIOTT"


def test_actual_champion_none_for_incomplete_season(real_source):
    # 2025's finale never published in the feed; 2026 is in progress.
    assert pb.actual_champion(real_source, 2025) is None
    assert pb.actual_champion(real_source, 2026) is None


def test_real_playoff_field_is_sixteen(real_source):
    field = pb.real_playoff_field(real_source, 2022)
    assert len(field) == 16
    assert "JOLOGANO" in field


def test_evaluate_checkpoint_shape(real_source):
    entry = pb.evaluate_checkpoint(
        real_source, 2022, "pre_playoffs", 26, "JOLOGANO", n_sims=300
    )
    assert entry is not None
    assert entry["throughRound"] == 26
    assert 0.0 <= entry["championPTitle"] <= 1.0
    assert 0.0 <= entry["championPercentile"] <= 1.0
    assert entry["uniformBaseline"] == round(1 / 16, 4)
    assert len(entry["top5"]) == 5
    # The eventual champion must at least be simulated INTO the playoffs.
    assert entry["championPMakePlayoffs"] > 0.5


def test_backtest_payload_gate_shape():
    """One-season mini-backtest exercises the aggregation + gate plumbing."""
    source = NascarDataSource()
    payload = pb.backtest([2022], n_sims=300)
    assert payload["seasons"] == [2022]
    season = payload["perSeason"][0]
    assert season["champion"] == "JOLOGANO"
    assert {c["checkpoint"] for c in season["checkpoints"]} == set(pb.CHECKPOINTS)
    fr = season["fieldReconstruction"]
    assert fr["actualFieldSize"] == 16
    assert fr["overlap"] >= 15
    gate = payload["gate"]
    assert set(gate) >= {
        "pass", "basis", "minMeanChampionPercentile", "minMeanUniformRatio",
        "observedMeanChampionPercentile", "observedMeanUniformRatio",
    }
    assert payload["caveats"]
    # The datasource fixture isn't reused here on purpose: the backtest builds
    # its own source (documenting the CLI behaviour).
    assert source is not None
