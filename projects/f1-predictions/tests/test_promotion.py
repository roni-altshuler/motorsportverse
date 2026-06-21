"""Tests for the shadow/A-B promotion logic + CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import promotion_decision
from models.promotion import (
    DECISION_DEMOTE,
    DECISION_HOLD,
    DECISION_PROMOTE,
    evaluate_promotion,
)


# --------------------------------------------------------------------------- #
# evaluate_promotion — core rule
# --------------------------------------------------------------------------- #


class TestEvaluatePromotion:
    def test_insufficient_overlap_holds(self):
        prod = [(i, 0.5) for i in range(1, 4)]
        cand = [(i, 0.4) for i in range(1, 4)]  # only 3 common rounds
        d = evaluate_promotion(prod, cand, min_rounds_to_decide=5)
        assert d.decision == DECISION_HOLD
        assert "insufficient overlap" in d.reason
        assert d.rounds_compared == 3

    def test_candidate_significantly_better_promotes(self):
        prod = [(i, 0.50) for i in range(1, 11)]
        cand = [(i, 0.40) for i in range(1, 11)]  # 20% better
        d = evaluate_promotion(
            prod, cand, min_rounds_to_decide=5, relative_improvement_threshold=0.02
        )
        assert d.decision == DECISION_PROMOTE
        assert d.relative_change == pytest.approx(-0.20)
        assert d.mean_production == 0.50
        assert d.mean_candidate == 0.40

    def test_candidate_within_threshold_holds(self):
        prod = [(i, 0.50) for i in range(1, 11)]
        cand = [(i, 0.495) for i in range(1, 11)]  # 1% better — under 2% threshold
        d = evaluate_promotion(
            prod, cand, min_rounds_to_decide=5, relative_improvement_threshold=0.02
        )
        assert d.decision == DECISION_HOLD

    def test_candidate_significantly_worse_demotes(self):
        prod = [(i, 0.50) for i in range(1, 11)]
        cand = [(i, 0.60) for i in range(1, 11)]  # 20% worse
        d = evaluate_promotion(prod, cand, min_rounds_to_decide=5)
        assert d.decision == DECISION_DEMOTE

    def test_per_round_blowup_blocks_promotion(self):
        # Mean is better but one round is a 30% disaster — guard blocks.
        prod = [(i, 0.50) for i in range(1, 11)]
        cand = [(i, 0.40) for i in range(1, 11)]
        cand[3] = (4, 0.70)  # +40% blow-up on round 4
        d = evaluate_promotion(
            prod, cand, min_rounds_to_decide=5,
            relative_improvement_threshold=0.02,
            max_per_round_regression=0.20,
        )
        assert d.decision == DECISION_HOLD
        assert d.blocked_by_per_round_guard is True
        assert "per-round guard" in d.reason

    def test_inner_join_drops_unaligned_rounds(self):
        prod = [(i, 0.50) for i in range(1, 11)]   # rounds 1-10
        cand = [(i, 0.40) for i in range(6, 16)]   # rounds 6-15
        # Overlap = rounds 6-10 = 5 rounds → meets min_rounds_to_decide
        d = evaluate_promotion(prod, cand, min_rounds_to_decide=5)
        assert d.rounds_compared == 5

    def test_trailing_window_caps_comparison(self):
        # 30 rounds; only the last 10 should drive the mean
        prod = [(i, 0.50) for i in range(1, 31)]
        cand = (
            [(i, 0.60) for i in range(1, 21)]   # candidate slow on early rounds
            + [(i, 0.40) for i in range(21, 31)] # but fast on later
        )
        d = evaluate_promotion(prod, cand, min_rounds_to_decide=5, trailing_window=10)
        # Decision driven by last 10 rounds (candidate fast)
        assert d.decision == DECISION_PROMOTE
        assert d.rounds_compared == 10

    def test_filters_nan_scores(self):
        prod = [(i, 0.50) for i in range(1, 11)] + [(11, float("nan"))]
        cand = [(i, 0.45) for i in range(1, 11)] + [(11, float("nan"))]
        d = evaluate_promotion(prod, cand, min_rounds_to_decide=5)
        # NaN rounds dropped before alignment; result based on 10 valid rounds
        assert d.rounds_compared == 10


# --------------------------------------------------------------------------- #
# promotion_decision.py CLI
# --------------------------------------------------------------------------- #


class TestPromotionDecisionCLI:
    def _write_fe(self, directory: Path, scores: dict[int, float]) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for rnd, score in scores.items():
            (directory / f"round_{rnd:02d}.json").write_text(
                json.dumps({"round": rnd, "rmse_position_error": score})
            )

    def test_writes_decision_json_when_both_streams_present(self, tmp_path: Path):
        prod_dir = tmp_path / "prod"
        cand_dir = tmp_path / "cand"
        self._write_fe(prod_dir, {i: 0.50 for i in range(1, 11)})
        self._write_fe(cand_dir, {i: 0.40 for i in range(1, 11)})
        out = tmp_path / "promotion_status.json"
        rc = promotion_decision.main(
            [
                "--season", "2026",
                "--production-dir", str(prod_dir),
                "--candidate-dir", str(cand_dir),
                "--output", str(out),
                "--quiet",
            ]
        )
        assert rc == 0
        assert out.exists()
        payload = json.loads(out.read_text())
        assert payload["decision"] == DECISION_PROMOTE
        assert payload["season"] == 2026
        assert payload["scoreKey"] == "rmse_position_error"

    def test_no_candidate_dir_returns_exit_1_by_default(self, tmp_path: Path):
        prod_dir = tmp_path / "prod"
        self._write_fe(prod_dir, {i: 0.50 for i in range(1, 11)})
        # Candidate dir doesn't exist
        rc = promotion_decision.main(
            [
                "--season", "2026",
                "--production-dir", str(prod_dir),
                "--candidate-dir", str(tmp_path / "missing"),
                "--output", str(tmp_path / "out.json"),
                "--quiet",
            ]
        )
        assert rc == 1

    def test_no_candidate_dir_returns_exit_0_with_allow_empty(self, tmp_path: Path):
        rc = promotion_decision.main(
            [
                "--season", "2026",
                "--production-dir", str(tmp_path / "prod-missing"),
                "--candidate-dir", str(tmp_path / "cand-missing"),
                "--output", str(tmp_path / "out.json"),
                "--allow-empty",
                "--quiet",
            ]
        )
        assert rc == 0
