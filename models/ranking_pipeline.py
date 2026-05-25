"""Shadow-stream orchestrator for the LambdaRank candidate pipeline.

Why this exists
---------------
The plan keeps the legacy ``train_ensemble`` lap-time regressor running as
production while the new ranking pipeline trains in parallel and writes
its predictions to a candidate JSON. The promotion gate in
``promotion_decision.py`` decides when the candidate beats production.
This module is the glue:

    historical (driver, season, round) rows
        → RaceGroupedTimeSeriesSplit
        → LambdaRanker (objective="lambdarank")
        → PlackettLuceHead (calibrated probabilities)
        → predicted finishing positions for the next race
        → candidate JSON (probabilities/round_NN_candidate.json)

The function ``train_and_predict_next_round`` is the single public entry
point. It produces both the ranking output and the calibrated probability
output, ready to be written by the export layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .cv import RaceGroupedTimeSeriesSplit
from .plackett_luce_head import PlackettLuceHead
from .ranking import LambdaRanker, LambdaRankerConfig, build_groups


@dataclass
class RankingPipelineResult:
    predictions: pd.DataFrame  # one row per driver: Driver, predictedPosition, rankerScore
    win_probabilities: dict[str, float]
    podium_probabilities: dict[str, float]
    top6_probabilities: dict[str, float]
    top10_probabilities: dict[str, float]
    metadata: dict = field(default_factory=dict)


def train_and_predict_next_round(
    training_rows: pd.DataFrame,
    next_round_rows: pd.DataFrame,
    *,
    feature_cols: list[str],
    target_col: str = "FinishPosition",
    cv_config: RaceGroupedTimeSeriesSplit | None = None,
    ranker_config: LambdaRankerConfig | None = None,
    head: PlackettLuceHead | None = None,
) -> RankingPipelineResult:
    """Fit the ranker on history, predict next-round positions + probabilities.

    Parameters
    ----------
    training_rows :
        DataFrame with one row per (driver, race) and columns
        ``Season``, ``Round``, ``Driver``, ``Team`` plus ``target_col`` and
        every name in ``feature_cols``. Sprint rows (if any) must include
        an ``IsSprint`` boolean — the ranker treats sprint vs main as
        separate ranking groups.
    next_round_rows :
        DataFrame with one row per driver in the upcoming race; same
        columns minus the target.
    feature_cols :
        Subset of column names to use as model inputs. Categorical / string
        columns should be encoded by the caller (the legacy pipeline does
        this in ``f1_prediction_utils.py``).
    """
    if cv_config is None:
        cv_config = RaceGroupedTimeSeriesSplit(
            n_splits=4, min_train_races=20, test_size_races=4
        )
    if ranker_config is None:
        ranker_config = LambdaRankerConfig()
    if head is None:
        head = PlackettLuceHead()

    # ── Sort training rows to make CV + LightGBM groups contiguous ─────
    sort_cols = ["Season", "Round"]
    if "IsSprint" in training_rows.columns:
        sort_cols.append("IsSprint")
    sort_cols.append("Driver")
    training_rows = training_rows.sort_values(sort_cols).reset_index(drop=True)

    X = training_rows[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = training_rows[target_col].astype(float).clip(1, 22).values
    groups_per_row = training_rows[["Season", "Round"]]

    # ── Race-grouped CV: collect held-out fold scores for calibration ──
    score_history: list[np.ndarray] = []
    outcome_history: list[np.ndarray] = []
    for train_idx, test_idx in cv_config.split(X, y, groups=groups_per_row):
        train_rows = training_rows.iloc[train_idx]
        test_rows = training_rows.iloc[test_idx]
        train_groups = build_groups(train_rows)
        test_groups = build_groups(test_rows)

        ranker = LambdaRanker(config=ranker_config)
        ranker.fit(
            X.iloc[train_idx],
            y[train_idx],
            train_groups,
        )
        scores = ranker.predict(X.iloc[test_idx])

        start = 0
        for size in test_groups.astype(int):
            end = start + size
            score_history.append(scores[start:end])
            outcome_history.append(y[test_idx][start:end])
            start = end

    if score_history:
        head.fit_temperature(score_history, outcome_history)

    # ── Refit on the full history, predict the next round ─────────────
    final_ranker = LambdaRanker(config=ranker_config)
    full_groups = build_groups(training_rows)
    final_ranker.fit(X, y, full_groups)

    next_X = (
        next_round_rows[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    )
    next_scores = final_ranker.predict(next_X)

    # Single-group prediction (one race)
    next_group = np.array([len(next_round_rows)], dtype=np.int64)
    positions = final_ranker.rank_predictions(next_X, next_group)

    marg = head.marginal_probabilities(next_scores, top_k=(1, 3, 6, 10))
    drivers = list(next_round_rows["Driver"].astype(str))
    predictions = pd.DataFrame(
        {
            "Driver": drivers,
            "rankerScore": next_scores,
            "predictedPosition": positions,
        }
    ).sort_values("predictedPosition", kind="stable").reset_index(drop=True)

    win = {d: float(p) for d, p in zip(drivers, marg[1])}
    podium = {d: float(p) for d, p in zip(drivers, marg[3])}
    top6 = {d: float(p) for d, p in zip(drivers, marg[6])}
    top10 = {d: float(p) for d, p in zip(drivers, marg[10])}

    metadata = {
        "ranker": ranker_config.__dict__,
        "temperature": head.temperature,
        "cv_folds": cv_config.n_splits,
        "training_rows": int(len(training_rows)),
        "training_races": int(training_rows[["Season", "Round"]].drop_duplicates().shape[0]),
        "features": list(feature_cols),
    }
    return RankingPipelineResult(
        predictions=predictions,
        win_probabilities=win,
        podium_probabilities=podium,
        top6_probabilities=top6,
        top10_probabilities=top10,
        metadata=metadata,
    )
