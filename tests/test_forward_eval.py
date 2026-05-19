"""Tests for the forward-time evaluation harness."""
from __future__ import annotations

from forward_eval import evaluate_season, score_round


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
