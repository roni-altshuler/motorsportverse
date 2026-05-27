"""Full-pipeline leakage integration test.

`tests/test_leakage.py` covers `assert_prior_only` and `filter_prior_only`
as pure unit tests.  This file exercises the aggregator boundaries in
`f1_prediction_utils` end-to-end: every feature builder that consumes
multi-round history must either filter to ``round < current_round`` or
raise ``LeakageError`` when given future-round data.

If a future refactor adds a new aggregator that forgets to plumb
``current_round`` through, the test added here is the safety net that
catches it.
"""
from __future__ import annotations

import pandas as pd
import pytest

from leakage import LeakageError
from f1_prediction_utils import (
    _add_prediction_bias_features,
    _load_season_position_maps,
)


def _make_merged(drivers: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Driver": drivers,
            "Team": [
                {
                    "VER": "Red Bull Racing",
                    "HAM": "Ferrari",
                    "NOR": "McLaren",
                    "RUS": "Mercedes",
                }.get(d, "McLaren")
                for d in drivers
            ],
        }
    )


class TestPredictionBiasLeakageBoundary:
    """`_add_prediction_bias_features` MUST refuse future-round inputs
    when `current_round` is passed.  Tested at the boundary because that
    is where the bug would actually surface in production."""

    def test_future_predicted_results_rejected(self):
        merged = _make_merged(["VER", "HAM"])
        # Round 6 data passed while predicting round 5 -> leakage.
        with pytest.raises(LeakageError):
            _add_prediction_bias_features(
                merged,
                predicted_results={"6": {"VER": 1, "HAM": 2}},
                actual_results={},
                current_round=5,
            )

    def test_future_actual_results_rejected(self):
        merged = _make_merged(["VER", "HAM"])
        with pytest.raises(LeakageError):
            _add_prediction_bias_features(
                merged,
                predicted_results={},
                actual_results={"6": {"VER": 1, "HAM": 2}},
                current_round=5,
            )

    def test_target_round_itself_rejected(self):
        """current_round == 5 means round 5 IS what we're predicting; data
        for round 5 leaking into the training features is the most common
        bug, so it MUST raise."""
        merged = _make_merged(["VER", "HAM"])
        with pytest.raises(LeakageError):
            _add_prediction_bias_features(
                merged,
                predicted_results={"5": {"VER": 1, "HAM": 2}},
                actual_results={},
                current_round=5,
            )

    def test_prior_rounds_pass_cleanly(self):
        merged = _make_merged(["VER", "HAM"])
        out = _add_prediction_bias_features(
            merged,
            predicted_results={"1": {"VER": 1, "HAM": 2}, "2": {"VER": 1, "HAM": 2}},
            actual_results={"1": {"VER": 1, "HAM": 2}, "2": {"VER": 2, "HAM": 1}},
            current_round=5,
        )
        # Bias columns must exist and have finite values for every driver.
        assert "DriverPredictionBias" in out.columns
        assert "TeamPredictionBias" in out.columns
        assert out["DriverPredictionBias"].notna().all()

    def test_current_round_none_skips_assertion(self):
        """Backward-compatibility path: when `current_round` is omitted,
        the unit-test surface still works (no leakage check).  We do not
        want to break the small handful of existing unit tests that build
        bias features directly."""
        merged = _make_merged(["VER", "HAM"])
        # Even with future-round data, no `current_round` means no check.
        out = _add_prediction_bias_features(
            merged,
            predicted_results={"99": {"VER": 1, "HAM": 2}},
            actual_results={"99": {"VER": 1, "HAM": 2}},
        )
        assert "DriverPredictionBias" in out.columns


class TestSeasonPositionMapsLeakageBoundary:
    """`_load_season_position_maps(current_round=N)` must return only
    rounds < N.  This is the upstream contract that the feature
    aggregators rely on."""

    def test_round_filter_strips_future_rounds(self, tmp_path, monkeypatch):
        # Write synthetic predicted/actual files that include round 6 data
        # while we ask for round 5.  The filter must remove round 6.
        import json
        import f1_prediction_utils as fpu

        pred_path = tmp_path / "predicted_results_2026.json"
        act_path = tmp_path / "season_results_2026.json"
        pred_path.write_text(
            json.dumps(
                {
                    "2": {"VER": 1, "HAM": 2},
                    "6": {"VER": 1, "HAM": 2},
                }
            )
        )
        act_path.write_text(
            json.dumps(
                {
                    "2": {"VER": 1, "HAM": 2},
                    "6": {"VER": 2, "HAM": 1},
                }
            )
        )
        monkeypatch.setattr(fpu, "PREDICTED_RESULTS_FILE", str(pred_path))
        monkeypatch.setattr(fpu, "PREDICTED_RESULTS_WEBSITE_FILE", str(pred_path))
        monkeypatch.setattr(fpu, "SEASON_RESULTS_FILE", str(act_path))
        monkeypatch.setattr(fpu, "SEASON_RESULTS_WEBSITE_FILE", str(act_path))
        monkeypatch.chdir(tmp_path)

        predicted, actual, combined = _load_season_position_maps(current_round=5)
        # Round 6 must be gone from all three maps.
        assert "6" not in predicted
        assert "6" not in actual
        assert "6" not in combined
        # Round 2 (prior) must survive.
        assert "2" in predicted
        assert "2" in actual
        assert "2" in combined
