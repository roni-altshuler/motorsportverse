"""Bootstrap prediction intervals for the quali-time ensemble.

A-P2.3: every published predictedTime is a point estimate today.  Even a
small bootstrap (20-30 replicas) gives a per-driver 90% credible band
that ``classification[*].predictionIntervalLow / High`` can render as
error bars on the website's main chart.

Approach
--------
For each replica:
  1. Bootstrap-sample the training rows (with replacement).
  2. Fit a *single* GBR (smaller than the production pair — speed matters).
  3. Score every row in the inference set.

The matrix of (n_replicas, n_drivers) predictions is then reduced to
(low, high) per driver via the 5th and 95th percentiles.

Performance budget
------------------
Production train_ensemble uses GBR n_estimators=200 + XGB n_estimators=250.
For the bootstrap we use n_estimators=80 to fit in roughly 1/3 of one
ensemble's wall-clock per replica.  Default n_replicas=20 → adds roughly
10s per round on the current CI runner; well under budget.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor


def bootstrap_prediction_intervals(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_inference: np.ndarray,
    *,
    n_replicas: int = 20,
    n_estimators: int = 80,
    max_depth: int = 3,
    random_state: int = 42,
    low_percentile: float = 5.0,
    high_percentile: float = 95.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(low, high)`` arrays of shape ``(n_inference,)``.

    Both arrays carry per-driver 90% (default) credible band endpoints.

    The bootstrap is reproducible: same ``random_state`` → same intervals.
    Replica fits are deterministic given their sampled indices.
    """
    if n_replicas < 2:
        raise ValueError(f"n_replicas must be >= 2, got {n_replicas}")
    if len(X_train) < 4:
        raise ValueError(
            f"need >= 4 training rows for bootstrap, got {len(X_train)}"
        )
    if len(X_inference) == 0:
        return np.array([]), np.array([])

    rng = np.random.default_rng(seed=random_state)
    n_train = len(X_train)
    n_inference = len(X_inference)
    predictions = np.zeros((n_replicas, n_inference), dtype=np.float64)

    for r in range(n_replicas):
        idx = rng.integers(low=0, high=n_train, size=n_train)
        replica_seed = int(rng.integers(0, 2**31 - 1))
        model = GradientBoostingRegressor(
            n_estimators=n_estimators,
            learning_rate=0.05,
            max_depth=max_depth,
            random_state=replica_seed,
        )
        model.fit(X_train[idx], y_train[idx])
        predictions[r] = model.predict(X_inference)

    low = np.percentile(predictions, low_percentile, axis=0)
    high = np.percentile(predictions, high_percentile, axis=0)
    return low, high
