"""Next-event skill candidate, with event-level validation and recency weights.

Feature callbacks receive ONLY the rounds preceding the target event. Labels
are the subsequent event's observed finishes. The last completed event is held
out as a whole when choosing the blend with the historical-mean baseline.
This is a research candidate, not evidence of improved live forecast accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

from .leakage import assert_prior_only

Features = Mapping[str, Mapping[str, float]]


@dataclass
class TemporalSkillPrediction:
    predictions: dict[str, float]
    learned_weight: float
    validation_round: int
    validation_model_mae: float
    validation_baseline_mae: float
    training_rounds: list[int]


def predict_temporal_skill(
    prior_rounds: Sequence[int],
    feature_columns: Sequence[str],
    features_before: Callable[[list[int]], Features],
    actual_for: Callable[[int], Mapping[str, float]],
    *,
    half_life_rounds: float = 6.0,
    min_training_rows: int = 8,
) -> TemporalSkillPrediction | None:
    """Fit next-race labels; choose blend weight using the last prior event.

    No historical feature may contain an Elo value computed at today's cutoff;
    adapters must replay Elo at each cutoff or omit that column. ``_target`` is
    never used. The mandatory roll_mean_finish column supplies a real baseline.
    """
    if not np.isfinite(half_life_rounds) or half_life_rounds <= 0:
        raise ValueError('half_life_rounds must be finite and positive')
    if min_training_rows < 1:
        raise ValueError('min_training_rows must be positive')
    if 'roll_mean_finish' not in feature_columns or any(c.startswith('_') for c in feature_columns):
        raise ValueError('Use observable features including roll_mean_finish, never target metadata')
    rounds = sorted(set(prior_rounds))
    if len(rounds) < 3:
        return None
    x_rows, targets, groups = [], [], []
    for index, target_round in enumerate(rounds[1:], start=1):
        history = rounds[:index]
        assert_prior_only(dict.fromkeys(history), target_round, "temporal_skill features")
        features = features_before(history)
        actual = actual_for(target_round)
        for code, observed in actual.items():
            row = features.get(code)
            if row is None:
                continue
            vector = [row[c] for c in feature_columns]
            if not np.all(np.isfinite(vector)) or not np.isfinite(observed) or observed < 1:
                continue
            x_rows.append(vector)
            targets.append(observed)
            groups.append(target_round)
    if not x_rows:
        return None
    x, y, group = np.asarray(x_rows), np.asarray(targets), np.asarray(groups)
    validation_round = rounds[-1]
    train, valid = group < validation_round, group == validation_round
    if int(train.sum()) < min_training_rows or not valid.any():
        return None
    baseline_column = list(feature_columns).index('roll_mean_finish')

    def learner() -> GradientBoostingRegressor:
        return GradientBoostingRegressor(n_estimators=100, learning_rate=0.04,
                                         max_depth=2, min_samples_leaf=4,
                                         loss='huber', random_state=42)

    weights = np.exp2(-(validation_round - group) / half_life_rounds)
    model = learner().fit(x[train], y[train], sample_weight=weights[train])
    model_valid = model.predict(x[valid])
    baseline_valid = x[valid, baseline_column]
    # Prefer the simpler baseline on ties. No validation driver leaks into fit.
    candidates = (0.0, 0.25, 0.5, 0.75, 1.0)
    weight = min(candidates, key=lambda w: float(np.mean(np.abs(
        w * model_valid + (1 - w) * baseline_valid - y[valid]))))
    current = features_before(rounds)
    codes = list(current)
    if not codes:
        return None
    current_x = np.asarray([[current[c][f] for f in feature_columns] for c in codes])
    if not np.all(np.isfinite(current_x)):
        raise ValueError('Current features must be finite')
    model.fit(x, y, sample_weight=weights)
    prediction = weight * model.predict(current_x) + (1 - weight) * current_x[:, baseline_column]
    return TemporalSkillPrediction(
        predictions={c: float(max(1.0, prediction[i])) for i, c in enumerate(codes)},
        learned_weight=weight, validation_round=validation_round,
        validation_model_mae=float(np.mean(np.abs(model_valid - y[valid]))),
        validation_baseline_mae=float(np.mean(np.abs(baseline_valid - y[valid]))),
        training_rounds=sorted(set(group[train].tolist())),
    )
