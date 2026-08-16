"""Tests for the paired model-vs-baseline evidence artifact."""
from __future__ import annotations

import json

import pytest

from motorsport_core import evidence


def _write_round(directory, rnd, *, model, baseline, race_type="race", baseline_key="lastRace"):
    payload = {
        "round": rnd,
        "venueName": f"Venue {rnd}",
        race_type: {"n": 20, "mean_position_error": model, "ndcg_at_5": 0.6},
        "baselines": {
            baseline_key: {"n": 20, "mean_position_error": baseline, "ndcg_at_5": 0.5}
        },
    }
    (directory / f"round_{rnd:02d}.json").write_text(json.dumps(payload))


def _write_feeder_round(directory, rnd, *, model, baseline):
    payload = {
        "round": rnd,
        "sprint": {"n": 24, "mean_position_error": model, "ndcg_at_5": 0.6},
        "feature": {"n": 26, "mean_position_error": model, "ndcg_at_5": 0.6},
        "baselines": {
            "sprint": {"n": 24, "mean_position_error": baseline, "ndcg_at_5": 0.5},
            "feature": {"n": 26, "mean_position_error": baseline, "ndcg_at_5": 0.5},
        },
    }
    (directory / f"round_{rnd:02d}.json").write_text(json.dumps(payload))


# --------------------------------------------------------------------------- #
# paired_bootstrap
# --------------------------------------------------------------------------- #


def test_bootstrap_is_deterministic():
    """A published artifact that changes when nothing changed is a daily diff."""
    diffs = [-0.4, -0.2, -0.9, 0.1, -0.5, -0.3]
    assert evidence.paired_bootstrap(diffs) == evidence.paired_bootstrap(diffs)


def test_bootstrap_interval_brackets_the_mean():
    diffs = [-0.4, -0.2, -0.9, 0.1, -0.5, -0.3]
    low, high, p_negative = evidence.paired_bootstrap(diffs)
    mean = sum(diffs) / len(diffs)
    assert low is not None and high is not None
    assert low <= mean <= high
    assert 0.0 <= p_negative <= 1.0


def test_bootstrap_needs_two_points():
    assert evidence.paired_bootstrap([0.5]) == (None, None, None)


# --------------------------------------------------------------------------- #
# compare_paired
# --------------------------------------------------------------------------- #


def test_lower_is_better_metric_flips_the_improvement_sign():
    """A smaller position error is a BETTER model, and `improvement` says so."""
    paired = [(r, 5.0, 7.0) for r in range(1, 9)]
    result = evidence.compare_paired(
        "mean_position_error", paired, baseline="lastRace", race_type="race"
    )
    assert result.delta == pytest.approx(-2.0)
    assert result.improvement == pytest.approx(2.0)
    assert result.verdict == "better"


def test_higher_is_better_metric_keeps_the_sign():
    paired = [(r, 0.8, 0.5) for r in range(1, 9)]
    result = evidence.compare_paired("ndcg_at_5", paired, baseline="lastRace", race_type="race")
    assert result.improvement == pytest.approx(0.3)
    assert result.verdict == "better"


def test_a_losing_model_is_reported_as_worse_not_hidden():
    """docs/EVIDENCE.md rule 2: not beating the baseline is a publishable result."""
    paired = [(r, 9.0, 6.0) for r in range(1, 9)]
    result = evidence.compare_paired(
        "mean_position_error", paired, baseline="gridOrder", race_type="race"
    )
    assert result.verdict == "worse"
    assert "does NOT beat" in result.note
    assert result.improvement < 0


def test_small_sample_earns_no_claim_however_good_it_looks():
    paired = [(r, 1.0, 20.0) for r in range(1, evidence.MIN_ROUNDS_FOR_CLAIM)]
    result = evidence.compare_paired(
        "mean_position_error", paired, baseline="lastRace", race_type="race"
    )
    assert result.verdict == "insufficient"
    assert result.improvement > 0  # the delta is enormous and still earns nothing


def test_a_straddling_interval_is_inconclusive_not_a_win():
    """The sign of a point estimate is not evidence when the CI covers zero."""
    paired = [
        (1, 6.0, 6.4), (2, 7.0, 6.1), (3, 5.0, 5.6), (4, 8.0, 7.2),
        (5, 6.5, 6.3), (6, 7.5, 7.9), (7, 5.5, 5.2), (8, 6.2, 6.6),
    ]
    result = evidence.compare_paired(
        "mean_position_error", paired, baseline="lastRace", race_type="race"
    )
    assert result.verdict == "inconclusive"
    assert result.ci_low <= 0 <= result.ci_high


def test_no_paired_rounds_is_insufficient_not_a_crash():
    result = evidence.compare_paired(
        "mean_position_error", [], baseline="lastRace", race_type="race"
    )
    assert result.verdict == "insufficient"
    assert result.model_mean is None


# --------------------------------------------------------------------------- #
# build_evidence
# --------------------------------------------------------------------------- #


def test_missing_directory_is_unavailable_with_a_reason(tmp_path):
    block = evidence.build_evidence(tmp_path / "nope")
    assert block.available is False
    assert block.reason
    assert block.to_json()["available"] is False


def test_empty_directory_is_unavailable(tmp_path):
    directory = tmp_path / "forward_eval"
    directory.mkdir()
    block = evidence.build_evidence(directory)
    assert block.available is False
    assert "scored" in block.reason


def test_rounds_without_baselines_are_not_evidence(tmp_path):
    """A metric with no baseline is a number about the calendar."""
    directory = tmp_path / "forward_eval"
    directory.mkdir()
    (directory / "round_01.json").write_text(
        json.dumps({"round": 1, "race": {"mean_position_error": 4.0}})
    )
    block = evidence.build_evidence(directory)
    assert block.available is False
    assert "baseline" in block.reason


def test_single_race_shape_builds_a_comparison(tmp_path):
    directory = tmp_path / "forward_eval"
    directory.mkdir()
    for rnd in range(1, 9):
        _write_round(directory, rnd, model=5.0, baseline=7.0)
    block = evidence.build_evidence(directory)
    assert block.available is True
    assert block.rounds_scored == 8
    assert block.headline["verdict"] == "better"
    assert block.headline["baseline"] == "lastRace"


def test_feeder_shape_keeps_race_types_separate(tmp_path):
    """F2/F3 key baselines by race type; sprint and feature must not be pooled."""
    directory = tmp_path / "forward_eval"
    directory.mkdir()
    for rnd in range(1, 9):
        _write_feeder_round(directory, rnd, model=5.0, baseline=7.0)
    block = evidence.build_evidence(directory)
    race_types = {c["raceType"] for c in block.comparisons}
    assert race_types == {"sprint", "feature"}
    assert all(c["baseline"] == "lastRace" for c in block.comparisons)


def test_name_keyed_baselines_attach_to_the_pre_quali_block(tmp_path):
    """NASCAR/IndyCar publish two model blocks and ONE set of baselines.

    Those baselines score the pre-qualifying forecast. Attaching them to
    whichever block a set happened to yield first would compare the post-quali
    model against the pre-quali baseline on some runs and not others — a
    difference that would look like model drift.
    """
    directory = tmp_path / "forward_eval"
    directory.mkdir()
    for rnd in range(1, 9):
        payload = {
            "round": rnd,
            "race": {"mean_position_error": 6.0},
            "racePostQuali": {"mean_position_error": 4.0},
            "baselines": {"gridOrder": {"mean_position_error": 5.0}},
        }
        (directory / f"round_{rnd:02d}.json").write_text(json.dumps(payload))

    block = evidence.build_evidence(directory)
    race_types = {c["raceType"] for c in block.comparisons}
    assert race_types == {"race"}
    # 6.0 vs a 5.0 baseline: the pre-quali model loses, and that is the honest
    # comparison. Against the post-quali block it would have "won" at 4.0.
    assert block.headline["verdict"] == "worse"


def test_headline_prefers_the_harder_baseline(tmp_path):
    """Grid order is a stronger yardstick than last-race, so it leads."""
    directory = tmp_path / "forward_eval"
    directory.mkdir()
    for rnd in range(1, 9):
        payload = {
            "round": rnd,
            "race": {"mean_position_error": 5.0},
            "baselines": {
                "lastRace": {"mean_position_error": 9.0},
                "gridOrder": {"mean_position_error": 5.2},
            },
        }
        (directory / f"round_{rnd:02d}.json").write_text(json.dumps(payload))
    block = evidence.build_evidence(directory)
    assert block.headline["baseline"] == "gridOrder"


def test_a_closed_calibration_gate_becomes_a_caveat(tmp_path):
    directory = tmp_path / "forward_eval"
    directory.mkdir()
    for rnd in range(1, 9):
        _write_round(directory, rnd, model=5.0, baseline=7.0)
    summary = tmp_path / "calibration_summary.json"
    summary.write_text(json.dumps({"applied": False, "trainingRounds": 0}))

    block = evidence.build_evidence(directory, calibration_summary=summary)
    assert block.calibration["applied"] is False
    assert any("calibration gate is closed" in c for c in block.caveats)


def test_the_cross_series_caveat_always_prints(tmp_path):
    """Even on a clean win: a hit read as proof is the same error, flatteringly."""
    directory = tmp_path / "forward_eval"
    directory.mkdir()
    for rnd in range(1, 12):
        _write_round(directory, rnd, model=3.0, baseline=9.0)
    block = evidence.build_evidence(directory)
    assert block.headline["verdict"] == "better"
    assert any("only comparable within this series" in c for c in block.caveats)


def test_write_evidence_round_trips(tmp_path):
    directory = tmp_path / "forward_eval"
    directory.mkdir()
    for rnd in range(1, 9):
        _write_round(directory, rnd, model=5.0, baseline=7.0)
    block = evidence.build_evidence(directory, sport="test")
    out = evidence.write_evidence(block, tmp_path / "evidence.json")
    assert json.loads(out.read_text())["sport"] == "test"
