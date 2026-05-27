"""Tests for the two-stage classifier+regressor scaffold."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models.two_stage import (
    TwoStageRanker,
    _bucket_to_centre,
    _position_to_bucket,
)


def _synth_dataset(n_rows: int = 80, n_features: int = 4, seed: int = 0) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(
        rng.normal(0, 1, size=(n_rows, n_features)),
        columns=[f"f{i}" for i in range(n_features)],
    )
    # Position is correlated with the first feature so the model has
    # something real to learn.  Clip to [1, 22] and round to ints.
    raw = 11 + 4.0 * X["f0"] + rng.normal(0, 1.5, size=n_rows)
    positions = np.clip(np.round(raw).astype(int), 1, 22)
    return X, positions


def test_bucket_mapping_covers_all_positions():
    for pos in range(1, 23):
        bucket = _position_to_bucket(pos)
        assert 0 <= bucket <= 3


def test_bucket_centre_is_within_bucket_range():
    assert 1.0 <= _bucket_to_centre(0) <= 5.0
    assert 6.0 <= _bucket_to_centre(1) <= 10.0
    assert 11.0 <= _bucket_to_centre(2) <= 15.0
    assert 16.0 <= _bucket_to_centre(3) <= 22.0


def test_fit_predict_roundtrip():
    X, y = _synth_dataset()
    ranker = TwoStageRanker().fit(X, y)
    preds = ranker.predict(X)
    assert preds.shape == y.shape
    # Predictions must be within the [1, 22] position range.
    assert np.all(preds >= 1.0)
    assert np.all(preds <= 22.0)


def test_predict_before_fit_raises():
    X, _ = _synth_dataset()
    with pytest.raises(RuntimeError):
        TwoStageRanker().predict(X)


def test_fit_row_alignment_validation():
    X, y = _synth_dataset(n_rows=50)
    with pytest.raises(ValueError, match="row-aligned"):
        TwoStageRanker().fit(X, y[:40])
