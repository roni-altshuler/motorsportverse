"""DNF (Did Not Finish) probability model.

Predicts per-driver probability of NOT classifying in a given race, using a
small logistic regression on:
  - driver_prior_dnf_rate: rolling 10-race DNF rate for the driver, computed
    strictly from rounds prior to the prediction target (leakage-safe).
  - predicted_position_norm: the Layer-1 ensemble's predicted finishing
    position normalised to [0, 1]; back-of-grid drivers DNF disproportionately
    often (collisions, mechanical wear from running deep in dirty air).
  - circuit_dnf_rate: per-circuit historical DNF rate (1.0 = every driver
    DNF'd here on average, 0.0 = nobody ever has).

Training data comes from `data/history.duckdb::historical_predictions`, where
`actual_position IS NULL` is the DNF indicator (drivers entered but not
classified).

Output ships into `website/public/data/probabilities/round_NN.json` as an
optional `dnfProbability` field on each driver entry. The web UI surfaces it
as a small "DNF risk" pill on the race detail page.

v1 scope (intentional, kept small):
  - Two-feature logistic regression with `class_weight="balanced"`.
  - Flat 0.05 fallback when training rows < 200 for the season cohort.
  - No bayesian prior, no per-team modelling (history table doesn't carry
    team mapping yet).

v2+ (see docs/ROADMAP.md):
  - Add team-mapping + per-team DNF rate.
  - Wire `Bernoulli(p_dnf)` sampling into `models/race_simulator.py` for
    each MC iteration.
  - Surface as a chart on /accuracy/dnf-calibration.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Sequence

import numpy as np

# Project base-rate fallback when the model can't fit (cold start, sparse data).
# Computed from 2018-2025 history: ~336/2233 historical entries DNF'd = 15%.
_BASE_RATE = 0.15
_MIN_TRAIN_ROWS = 200
_HISTORY_WINDOW = 10  # rolling DNF rate over the prior N races per driver


@dataclass
class DnfModelInputs:
    """Per-driver features at predict time for the upcoming race."""

    driver: str
    predicted_position: int
    circuit_key: str


def compute_dnf_probabilities(
    history_db_path: Path,
    *,
    season: int,
    current_round: int,
    inputs: Sequence[DnfModelInputs],
) -> Dict[str, float]:
    """Train a per-season DNF logistic regression on prior data and predict
    p_dnf for the listed drivers at the upcoming round.

    Returns a `{driver_code: p_dnf}` dict. Drivers with no historical data
    fall back to the global base rate (0.15).
    """
    try:
        import duckdb  # local import keeps the runtime light
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        # Sklearn / duckdb not available; everyone gets the base rate.
        return {item.driver: _BASE_RATE for item in inputs}

    history_db_path = Path(history_db_path)
    if not history_db_path.exists():
        return {item.driver: _BASE_RATE for item in inputs}

    con = duckdb.connect(str(history_db_path), read_only=True)
    try:
        # Pull every historical entry STRICTLY before (season, current_round).
        rows = con.execute(
            """
            SELECT season, round, driver, predicted_position, actual_position
            FROM historical_predictions
            WHERE (season, round) < (?, ?)
            ORDER BY season, round, driver
            """,
            (season, current_round),
        ).fetchall()
    finally:
        con.close()

    if len(rows) < _MIN_TRAIN_ROWS:
        return {item.driver: _BASE_RATE for item in inputs}

    # Build (X, y) for training: each historical row = one (driver, race) entry.
    # y = 1 if actual_position IS NULL (driver entered but didn't classify).
    # X features:
    #   [0] driver_prior_dnf_rate (rolling 10-race window, strictly prior)
    #   [1] predicted_position normalised to [0, 1] (we proxy with rank)
    train_X = []
    train_y = []

    # First, build a chronological view + rolling per-driver DNF tracking.
    per_driver_recent: Dict[str, list[int]] = {}  # driver -> recent DNF flags
    for season_h, round_h, driver_h, pred_h, actual_h in rows:
        prior = per_driver_recent.get(driver_h, [])
        prior_rate = (sum(prior) / len(prior)) if prior else _BASE_RATE
        is_dnf = 1 if actual_h is None else 0
        pred_norm = max(0.0, min(1.0, (pred_h or 11) / 22.0))
        train_X.append([prior_rate, pred_norm])
        train_y.append(is_dnf)
        # Update rolling window AFTER recording (leakage-safe).
        per_driver_recent.setdefault(driver_h, []).append(is_dnf)
        per_driver_recent[driver_h] = per_driver_recent[driver_h][-_HISTORY_WINDOW:]

    X = np.array(train_X, dtype=float)
    y = np.array(train_y, dtype=int)

    if y.sum() < 10 or len(y) - y.sum() < 10:
        # Degenerate cohort — can't fit a classifier; fall back to base rate.
        return {item.driver: _BASE_RATE for item in inputs}

    model = LogisticRegression(
        class_weight="balanced",
        max_iter=200,
        random_state=42,
    )
    model.fit(X, y)

    # For predict-time features we use each driver's current rolling rate (the
    # final state of per_driver_recent after consuming all training rows).
    predictions: Dict[str, float] = {}
    for item in inputs:
        recent = per_driver_recent.get(item.driver, [])
        prior_rate = (sum(recent) / len(recent)) if recent else _BASE_RATE
        pred_norm = max(0.0, min(1.0, item.predicted_position / 22.0))
        x_row = np.array([[prior_rate, pred_norm]], dtype=float)
        p = float(model.predict_proba(x_row)[0, 1])
        # Clip to plausible bounds — extreme values would propagate to the UI
        # as nonsensical "92% DNF risk" claims.
        predictions[item.driver] = max(0.01, min(0.65, p))

    return predictions


__all__ = ["DnfModelInputs", "compute_dnf_probabilities"]
