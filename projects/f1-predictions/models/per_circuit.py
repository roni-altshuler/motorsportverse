"""Per-circuit hierarchical model.

The global Layer 1 regressor is a single GBR+XGB ensemble trained on
all circuits' qualifying-time history.  Some circuits (Monaco, Baku,
Singapore) have characteristics so different from the rest that a
single model cannot capture them — the qualifying pace ranking is more
about narrow-window single-lap performance than season-long form.

A per-circuit model is a thin specialisation on top of the global
model: train one small regressor per circuit on that circuit's
historical rows only, then blend the per-circuit prediction with the
global prediction by a configurable weight.

The blend keeps the model robust on circuits with little history
(Las Vegas, Madrid, returning venues) — full per-circuit weight only
kicks in once we've seen the circuit at least ``min_rows_for_full_weight``
times.

Designed to live alongside the existing ensemble, not replace it.  Wire
it into ``export_website_data.py`` after running the A/B benchmark in
``benchmark_per_circuit.py``.

Wiring status (2026-07)
-----------------------
``export_website_data.py`` exposes a ``--use-per-circuit`` flag that threads
through ``export_round_data(use_per_circuit=...)`` and records the outcome in
``round_NN.json::modelConfig.perCircuit``.  The flag is currently recorded as
``applied: false`` in the single-round export path: ``fit`` needs a
CROSS-circuit training frame (many circuits' historical rows, each ≥
``min_rows``), but the per-round ``merged`` frame holds only the current
circuit's 22 drivers.  The tested A/B path that DOES build prior-round frames
is ``src/benchmark_models.py::predict_per_circuit``.  Full single-round wiring
is deferred until a per-round L1 feature-matrix export lands (so the head can
be fit on prior rounds without leaking the current one).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor


DEFAULT_BLEND_WEIGHT = 0.4  # weight on the per-circuit head; rest is global
MIN_ROWS_FOR_FULL_WEIGHT = 30


@dataclass
class CircuitHead:
    """A single per-circuit regressor with row-count metadata."""

    model: GradientBoostingRegressor
    n_rows: int
    circuit_key: str


@dataclass
class PerCircuitHierarchicalModel:
    """Wrap a global model + a per-circuit head.

    At training time we fit one circuit-specific GBR per circuit_key
    present in the training frame; circuits with too few rows are
    skipped (the global model handles them).  At predict time we look
    up the head for the current circuit; if absent, we fall back to
    the global prediction.
    """

    global_predictions_col: str = "PredictedLapTime_Global"
    circuit_col: str = "circuit_key"
    feature_cols: list[str] = field(default_factory=list)
    blend_weight: float = DEFAULT_BLEND_WEIGHT
    min_rows: int = 8
    min_rows_for_full_weight: int = MIN_ROWS_FOR_FULL_WEIGHT
    heads: dict[str, CircuitHead] = field(default_factory=dict)

    def fit(self, df: pd.DataFrame, y: np.ndarray) -> "PerCircuitHierarchicalModel":
        if self.circuit_col not in df.columns:
            raise ValueError(f"missing '{self.circuit_col}' column in training frame")
        if not self.feature_cols:
            raise ValueError("feature_cols must be set before fitting")
        for circuit, rows in df.groupby(self.circuit_col):
            mask = rows.index
            if len(mask) < self.min_rows:
                continue
            X_c = df.loc[mask, self.feature_cols].fillna(0.0)
            y_c = y[mask] if isinstance(y, pd.Series) else y[np.asarray(mask)]
            head = GradientBoostingRegressor(
                n_estimators=80,
                learning_rate=0.05,
                max_depth=2,
                random_state=42,
            )
            head.fit(X_c, y_c)
            self.heads[str(circuit)] = CircuitHead(
                model=head, n_rows=len(mask), circuit_key=str(circuit)
            )
        return self

    def predict(self, df: pd.DataFrame, *, global_pred: np.ndarray) -> np.ndarray:
        """Blend per-circuit head's prediction with the global prediction.

        ``global_pred`` is the output of the existing ensemble — passed
        in explicitly so this class stays decoupled from
        ``f1_prediction_utils.train_ensemble``.
        """
        if len(global_pred) != len(df):
            raise ValueError(
                f"global_pred length {len(global_pred)} != df length {len(df)}"
            )
        out = np.array(global_pred, dtype=float)
        for circuit, group in df.groupby(self.circuit_col):
            head = self.heads.get(str(circuit))
            if head is None:
                continue
            idx = group.index
            X_c = df.loc[idx, self.feature_cols].fillna(0.0)
            head_pred = head.model.predict(X_c)
            # Adaptive blend: full per-circuit weight only once we've
            # seen enough rows at this circuit; partial weight while the
            # archive is shallow.
            confidence = min(1.0, head.n_rows / self.min_rows_for_full_weight)
            local_weight = self.blend_weight * confidence
            arr_idx = df.index.get_indexer(idx)
            out[arr_idx] = (1.0 - local_weight) * out[arr_idx] + local_weight * head_pred
        return out

    def covered_circuits(self) -> list[str]:
        return sorted(self.heads.keys())
