"""Tests for the leakage guard module and pipeline-level wiring.

These tests pin down the assertion contract: any data containing rounds at or
beyond the prediction target must raise LeakageError before features are built.
"""
from __future__ import annotations

import pytest

from leakage import (
    LeakageError,
    assert_prior_only,
    assert_seasons_prior_only,
    filter_prior_only,
)


class TestAssertPriorOnly:
    def test_empty_input_is_safe(self):
        assert_prior_only({}, current_round=5)
        assert_prior_only(None, current_round=5)

    def test_prior_rounds_pass(self):
        assert_prior_only({"1": {"VER": 1}, "2": {"VER": 1}}, current_round=5)

    def test_round_equal_to_current_is_leakage(self):
        with pytest.raises(LeakageError, match=r"\[5\]"):
            assert_prior_only({"5": {"VER": 1}}, current_round=5)

    def test_round_greater_than_current_is_leakage(self):
        with pytest.raises(LeakageError, match=r"\[7, 9\]"):
            assert_prior_only(
                {"1": {}, "7": {"VER": 1}, "9": {"VER": 1}},
                current_round=5,
            )

    def test_mixed_int_and_str_keys(self):
        with pytest.raises(LeakageError):
            assert_prior_only({1: {}, 6: {"VER": 1}}, current_round=5)

    def test_non_int_keys_are_skipped(self):
        assert_prior_only({"meta": "ignored", "3": {}}, current_round=5)

    def test_zero_current_round_rejected(self):
        with pytest.raises(LeakageError, match="positive int"):
            assert_prior_only({"1": {}}, current_round=0)

    def test_error_message_names_the_label(self):
        with pytest.raises(LeakageError, match="combined_results"):
            assert_prior_only(
                {"6": {"VER": 1}}, current_round=5, label="combined_results"
            )


class TestFilterPriorOnly:
    def test_filters_future_rounds(self):
        out = filter_prior_only(
            {"1": "a", "5": "b", "7": "c"}, current_round=5
        )
        assert out == {"1": "a"}

    def test_empty_input(self):
        assert filter_prior_only({}, current_round=5) == {}
        assert filter_prior_only(None, current_round=5) == {}


class TestSeasonsPriorOnly:
    def test_older_season_passes(self):
        rows = [{"season": 2024, "round": 22}, {"season": 2025, "round": 1}]
        assert_seasons_prior_only(rows, current_season=2026, current_round=3)

    def test_same_season_prior_round_passes(self):
        rows = [{"season": 2026, "round": 1}, {"season": 2026, "round": 2}]
        assert_seasons_prior_only(rows, current_season=2026, current_round=3)

    def test_same_season_target_round_fails(self):
        rows = [{"season": 2026, "round": 3}]
        with pytest.raises(LeakageError):
            assert_seasons_prior_only(rows, current_season=2026, current_round=3)

    def test_future_season_fails(self):
        rows = [{"season": 2027, "round": 1}]
        with pytest.raises(LeakageError):
            assert_seasons_prior_only(rows, current_season=2026, current_round=3)


class TestPipelineWiring:
    """End-to-end: confirm the pipeline's public API rejects bad input."""

    def test_build_training_dataset_rejects_zero_round(self):
        import pandas as pd

        from f1_prediction_utils import build_training_dataset

        grid = pd.DataFrame({"Driver": ["VER"], "Team": ["Red Bull Racing"]})
        stats = pd.DataFrame({"Driver": ["VER"], "AvgLapTime": [80.0]})
        with pytest.raises(LeakageError, match="current_round"):
            build_training_dataset(grid, stats, current_round=0)

    def test_build_training_dataset_rejects_non_int_round(self):
        import pandas as pd

        from f1_prediction_utils import build_training_dataset

        grid = pd.DataFrame({"Driver": ["VER"], "Team": ["Red Bull Racing"]})
        stats = pd.DataFrame({"Driver": ["VER"], "AvgLapTime": [80.0]})
        with pytest.raises(LeakageError, match="current_round"):
            build_training_dataset(grid, stats, current_round="5")  # type: ignore[arg-type]
