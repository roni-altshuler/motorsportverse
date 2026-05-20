"""Tests for the forward-time evaluation harness."""
from __future__ import annotations

import json
from pathlib import Path

from forward_eval import (
    _ndcg_at_k,
    _spearman_correlation,
    evaluate_season,
    score_round,
    write_per_round_files,
)


class TestScoreRound:
    def test_perfect_prediction(self):
        pred = {"VER": 1, "NOR": 2, "PIA": 3}
        act = {"VER": 1, "NOR": 2, "PIA": 3}
        r = score_round(2025, 1, pred, act)
        assert r.mean_position_error == 0.0
        assert r.exact_matches == 3
        assert r.within_3 == 3
        assert r.winner_hit is True
        assert r.podium_hits == 3
        # New metrics — perfect prediction → ρ = 1, NDCG@5 = None (only 3 drivers)
        assert r.spearman_correlation == 1.0
        assert r.ndcg_at_5 is None  # too few drivers for K=5

    def test_winner_swap(self):
        pred = {"VER": 1, "NOR": 2, "PIA": 3}
        act = {"NOR": 1, "VER": 2, "PIA": 3}
        r = score_round(2025, 1, pred, act)
        assert r.exact_matches == 1
        assert r.winner_hit is False
        # All three drivers were in the predicted-top-3 *and* the actual-top-3.
        assert r.podium_hits == 3

    def test_disjoint_driver_sets_returns_nan_errors(self):
        pred = {"VER": 1}
        act = {"NOR": 1}
        r = score_round(2025, 1, pred, act)
        assert r.drivers_compared == 0
        assert r.exact_matches == 0
        assert r.winner_hit is False

    def test_biggest_misses_sorted(self):
        pred = {"VER": 1, "NOR": 2, "PIA": 20}
        act = {"VER": 1, "NOR": 19, "PIA": 2}
        r = score_round(2025, 1, pred, act)
        # PIA: pred 20 → actual 2, delta 18; NOR: 2 → 19, delta 17.
        assert r.biggest_misses[0]["driver"] == "PIA"
        assert r.biggest_misses[0]["absDelta"] == 18

    def test_log_loss_uniform_baseline_is_ln_n(self):
        import math

        pred = {f"D{i}": i for i in range(1, 23)}
        act = {f"D{i}": i for i in range(1, 23)}
        r = score_round(2025, 1, pred, act)
        assert r.log_loss_uniform_baseline is not None
        assert abs(r.log_loss_uniform_baseline - math.log(22)) < 1e-9


class TestEvaluateSeason:
    def test_empty_intersection_returns_no_rounds(self):
        report = evaluate_season(2025, predicted={1: {"VER": 1}}, actual={})
        assert report.rounds == []
        assert report.summary["rounds_evaluated"] == 0

    def test_round_filter_applied(self):
        pred = {1: {"VER": 1}, 2: {"VER": 1}, 3: {"VER": 1}}
        act = {1: {"VER": 1}, 2: {"VER": 1}, 3: {"VER": 1}}
        report = evaluate_season(2025, pred, act, rounds=[2])
        assert len(report.rounds) == 1
        assert report.rounds[0].round == 2

    def test_summary_winner_hit_rate(self):
        # 2 rounds: round 1 winner hit, round 2 winner missed.
        pred = {1: {"VER": 1, "NOR": 2}, 2: {"VER": 1, "NOR": 2}}
        act = {1: {"VER": 1, "NOR": 2}, 2: {"NOR": 1, "VER": 2}}
        report = evaluate_season(2025, pred, act)
        assert report.summary["winner_hit_rate"] == 0.5


class TestSpearmanCorrelation:
    def test_perfect_agreement_is_one(self):
        assert _spearman_correlation([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0

    def test_perfect_inverse_is_minus_one(self):
        assert _spearman_correlation([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0

    def test_n_below_three_returns_none(self):
        assert _spearman_correlation([1, 2], [1, 2]) is None

    def test_handles_ties_via_average_ranks(self):
        # Two predicted ties at position 1; actual unique.  Average-rank
        # convention assigns rank 1.5 to the tied pair.
        rho = _spearman_correlation([1, 1, 3, 4], [1, 2, 3, 4])
        assert rho is not None
        assert 0.9 < rho <= 1.0


class TestNDCGAtK:
    def test_perfect_top_k_match_is_one(self):
        pred = {f"D{i}": i for i in range(1, 11)}
        act = {f"D{i}": i for i in range(1, 11)}
        assert _ndcg_at_k(pred, act, k=5) == 1.0

    def test_completely_reversed_is_less_than_one(self):
        n = 10
        pred = {f"D{i}": i for i in range(1, n + 1)}
        # Actual reverses the order entirely.
        act = {f"D{i}": (n + 1 - i) for i in range(1, n + 1)}
        ndcg = _ndcg_at_k(pred, act, k=5)
        assert ndcg is not None
        assert ndcg < 0.5

    def test_too_few_drivers_returns_none(self):
        pred = {"VER": 1, "NOR": 2, "PIA": 3}
        act = {"VER": 1, "NOR": 2, "PIA": 3}
        assert _ndcg_at_k(pred, act, k=5) is None


class TestBaselines:
    def test_last_race_winner_recorded_when_prior_round_provided(self):
        pred = {f"D{i}": i for i in range(1, 6)}
        actual_r2 = {f"D{i}": i for i in range(1, 6)}
        # "Last race" actual exactly matched this round → baseline is perfect.
        prior_actual = {f"D{i}": i for i in range(1, 6)}
        r = score_round(2025, 2, pred, actual_r2, prior_round_actual=prior_actual)
        assert "last_race_winner" in r.baselines
        assert r.baselines["last_race_winner"]["winner_hit"] is True
        assert r.baselines["last_race_winner"]["mean_position_error"] == 0.0

    def test_evaluate_season_wires_prior_round_automatically(self):
        pred = {1: {"VER": 1, "NOR": 2}, 2: {"VER": 1, "NOR": 2}}
        act = {1: {"VER": 1, "NOR": 2}, 2: {"NOR": 1, "VER": 2}}
        report = evaluate_season(2025, pred, act)
        # Round 1 has no prior round; baseline should NOT be in baselines.
        # Round 2 has round 1 as prior; baseline should be present.
        round_1 = next(r for r in report.rounds if r.round == 1)
        round_2 = next(r for r in report.rounds if r.round == 2)
        assert "last_race_winner" not in round_1.baselines
        assert "last_race_winner" in round_2.baselines

    def test_season_summary_aggregates_baselines(self):
        pred = {1: {"VER": 1, "NOR": 2}, 2: {"VER": 1, "NOR": 2}}
        act = {1: {"VER": 1, "NOR": 2}, 2: {"NOR": 1, "VER": 2}}
        report = evaluate_season(2025, pred, act)
        assert "last_race_winner" in report.summary["baselines"]
        baseline_summary = report.summary["baselines"]["last_race_winner"]
        assert baseline_summary["rounds_compared"] == 1


class TestPerRoundOutput:
    def test_write_per_round_files_creates_one_file_per_round(self, tmp_path: Path):
        pred = {1: {"VER": 1, "NOR": 2}, 3: {"VER": 1, "NOR": 2}}
        act = {1: {"VER": 1, "NOR": 2}, 3: {"NOR": 1, "VER": 2}}
        report = evaluate_season(2025, pred, act)
        out_dir = tmp_path / "forward_eval"
        written = write_per_round_files(report, out_dir)
        assert len(written) == 2
        assert (out_dir / "round_01.json").exists()
        assert (out_dir / "round_03.json").exists()
        with (out_dir / "round_03.json").open() as fh:
            data = json.load(fh)
        assert data["round"] == 3
        assert data["winner_hit"] is False
        # Baseline metrics survive the dataclass→dict round-trip
        assert "baselines" in data
