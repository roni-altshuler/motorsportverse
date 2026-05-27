"""Tests for the per-circuit hierarchical wrapper."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models.per_circuit import (
    DEFAULT_BLEND_WEIGHT,
    PerCircuitHierarchicalModel,
)


def _synth_df(n_per_circuit: int = 20, n_circuits: int = 3) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(0)
    rows = []
    for c_idx in range(n_circuits):
        for _ in range(n_per_circuit):
            rows.append(
                {
                    "circuit_key": f"C{c_idx}",
                    "f0": rng.normal(0, 1),
                    "f1": rng.normal(0, 1),
                }
            )
    df = pd.DataFrame(rows)
    # Circuit-specific signal: each circuit has its own lap-time bias.
    bias_by_circuit = {f"C{i}": 80 + i * 5 for i in range(n_circuits)}
    y = np.array(
        [
            bias_by_circuit[r.circuit_key] + 1.2 * r.f0 + rng.normal(0, 0.3)
            for r in df.itertuples()
        ]
    )
    return df, y


def test_per_circuit_fit_creates_heads():
    df, y = _synth_df()
    model = PerCircuitHierarchicalModel(
        feature_cols=["f0", "f1"],
        min_rows=8,
    )
    model.fit(df, y)
    assert sorted(model.heads.keys()) == ["C0", "C1", "C2"]


def test_predict_blends_with_global():
    df, y = _synth_df()
    model = PerCircuitHierarchicalModel(
        feature_cols=["f0", "f1"],
        min_rows=8,
    )
    model.fit(df, y)
    # A naive global prediction = grand mean.
    global_pred = np.full(len(df), float(y.mean()))
    blended = model.predict(df, global_pred=global_pred)
    # Blended prediction should be CLOSER to y than the flat global mean
    # because the per-circuit head captures the circuit bias.
    mae_global = float(np.mean(np.abs(global_pred - y)))
    mae_blended = float(np.mean(np.abs(blended - y)))
    assert mae_blended < mae_global, (
        f"per-circuit blend should improve MAE: global {mae_global:.3f} vs blended {mae_blended:.3f}"
    )


def test_unknown_circuit_falls_back_to_global():
    df_train, y_train = _synth_df()
    model = PerCircuitHierarchicalModel(feature_cols=["f0", "f1"], min_rows=8)
    model.fit(df_train, y_train)
    # Predict frame contains a circuit we never trained on.
    df_test = pd.DataFrame(
        {"circuit_key": ["NEW_CIRCUIT"] * 3, "f0": [0.0, 0.5, -0.5], "f1": [0.0, 0.0, 0.0]}
    )
    global_pred = np.array([90.0, 91.0, 89.0])
    blended = model.predict(df_test, global_pred=global_pred)
    # No head → output equals global exactly.
    np.testing.assert_array_equal(blended, global_pred)


def test_thin_history_dampens_blend_weight():
    rng = np.random.default_rng(1)
    # 9 rows for C0, 9 for C1 — above min_rows (8) but well below
    # MIN_ROWS_FOR_FULL_WEIGHT (30).  Blend weight should be capped.
    rows = []
    for c in ["C0", "C1"]:
        for _ in range(9):
            rows.append({"circuit_key": c, "f0": rng.normal(0, 1), "f1": rng.normal(0, 1)})
    df = pd.DataFrame(rows)
    y = np.array([85.0] * len(df))
    model = PerCircuitHierarchicalModel(
        feature_cols=["f0", "f1"],
        min_rows=8,
        blend_weight=DEFAULT_BLEND_WEIGHT,
        min_rows_for_full_weight=30,
    )
    model.fit(df, y)
    # Per-circuit head should be present but its effective weight is
    # heavily dampened by row-count confidence (9/30 ≈ 0.3 → effective
    # blend ≈ 0.4 * 0.3 = 0.12).  We verify this by ensuring the
    # predicted output stays mostly anchored to the global prediction.
    global_pred = np.array([100.0] * len(df))  # far from y to make the test sharp
    blended = model.predict(df, global_pred=global_pred)
    # Effective weight ~0.12 → blended ~ 100 - 0.12*(100-85) = ~98.2
    # Assert blended is closer to 100 than to 85.
    assert all(abs(b - 100.0) < abs(b - 85.0) for b in blended)


def test_fit_requires_feature_cols():
    df, y = _synth_df()
    model = PerCircuitHierarchicalModel(feature_cols=[])
    with pytest.raises(ValueError, match="feature_cols"):
        model.fit(df, y)


def test_predict_requires_aligned_global_pred():
    df, y = _synth_df()
    model = PerCircuitHierarchicalModel(feature_cols=["f0", "f1"], min_rows=8).fit(df, y)
    with pytest.raises(ValueError, match="length"):
        model.predict(df, global_pred=np.zeros(len(df) + 5))
