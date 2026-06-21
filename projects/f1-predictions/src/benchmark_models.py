"""ML benchmark harness for the F1 prediction model.

Runs multiple model variants against the leak-safe historical backtest
(2024 + 2025 in ``data/history.duckdb``) and reports per-variant accuracy
metrics — MAE, RMSE, Spearman, NDCG@5, podium-hit rate, winner-hit rate.

Variants
--------
* ``baseline``                — the qualifying-pace ``predicted_position``
                                  rows stored in the DB (status quo).
* ``per_circuit``             — :class:`PerCircuitHierarchicalModel` over an
                                  archetype-derived offset (see APPROXIMATION
                                  NOTE in :func:`predict_per_circuit`).
* ``hybrid_blend``            — :func:`blend_for` mixes baseline ranks with a
                                  "current-weekend" surrogate (qualifying-gap-
                                  rank) using policy weights.
* ``per_circuit_plus_blend``  — stacked: per-circuit re-rank, then hybrid blend.

Subcommands
-----------
::

    python benchmark_models.py run \\
        --variants baseline,per_circuit,hybrid_blend,per_circuit_plus_blend \\
        --seasons 2024 2025 \\
        --output reports/benchmark_phase_1.json

    python benchmark_models.py compare \\
        --input reports/benchmark_phase_1.json \\
        --output docs/BENCHMARK_PHASE_1.md

    python benchmark_models.py export-website \\
        --input reports/benchmark_phase_1.json \\
        --output website/public/data/benchmark/

Approximation note
------------------
The full per-circuit hierarchical model requires multi-feature training
data per round. The DB holds only (predicted_position, actual_position,
predicted_lap_time) — there are no other model features available
offline. The variants therefore run a *floating-point* re-ranking on a
small feature set derived from the available columns (predicted lap time
+ archetype priors), not a full feature-matrix retrain. This is enough
to A/B the *signal direction* of each architectural lever; once a richer
feature export lands (training_matrix.parquet etc.), this script can
swap to a true-retrain path with a one-function change in
:func:`build_round_features`.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import duckdb
import numpy as np
import pandas as pd

from leakage import assert_seasons_prior_only
from models.conversion_model import (
    ConversionPodiumHead,
    ConversionWinHead,
    build_conversion_features,
)
from models.elite_features import build_elite_features
from models.elite_heads import PodiumHead, WinnerHead
from models.hybrid_blend import blend_for
from models.per_circuit import PerCircuitHierarchicalModel
from models.adaptive_fusion import adaptive_fuse_podium_and_win
from models.maturity import compute_maturity_frame
from models.probabilistic_combine import (
    calibration_error_10_bin,
    fuse_probabilities,
    podium_log_loss,
    renormalize_probabilities,
    rerank_with_probabilistic,
    winner_log_loss,
)
from models.early_fusion import early_fusion
from models.late_fusion import late_fusion
from models.maturity import compute_maturity_frame as _moe_compute_maturity_frame
from models.mid_fusion import mid_fusion
from models.moe_combine import fuse_with_gate
from models.moe_gate import (
    DEFAULT_EXPERT_NAMES,
    DEFAULT_FEATURE_NAMES,
    LearnedGate,
    TrainingExample,
    build_gate_features,
)
from models.regime_router import classify_regime, regime_fuse_podium_and_win
from models.track_archetype import TrackArchetype, get_archetype
from models.weekend_features import (
    PHASE_7_STATIC_COLUMNS,
    WEEKEND_FEATURE_COLUMNS,
    WEEKEND_FEATURE_COLUMNS_WITH_RESEARCH,
    attach_weekend_to_history,
)
from models.volatility_model import (
    VolatilityModel,
    build_volatility_features,
    build_volatility_training_frame,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "history.duckdb"


# --------------------------------------------------------------------------- #
# 2024 / 2025 round → circuit map (used because the active CALENDAR is 2026
# and the DB doesn't store circuit names).
# --------------------------------------------------------------------------- #


# Source: 2024 + 2025 official F1 calendars (Wikipedia / formula1.com).
ROUND_TO_GP_KEY: dict[int, dict[int, str]] = {
    2024: {
        1: "Bahrain",
        2: "Saudi Arabia",
        3: "Australia",
        4: "Japan",
        5: "China",
        6: "Miami",
        7: "Emilia Romagna",
        8: "Monaco",
        9: "Canada",
        10: "Spain",
        11: "Austria",
        12: "Great Britain",
        13: "Hungary",
        14: "Belgium",
        15: "Netherlands",
        16: "Italy",
        17: "Azerbaijan",
        18: "Singapore",
        19: "United States",
        20: "Mexico",
        21: "Brazil",
        22: "Las Vegas",
        23: "Qatar",
        24: "Abu Dhabi",
    },
    2025: {
        1: "Australia",
        2: "China",
        3: "Japan",
        4: "Bahrain",
        5: "Saudi Arabia",
        6: "Miami",
        7: "Emilia Romagna",
        8: "Monaco",
        9: "Spain",
        10: "Canada",
        11: "Austria",
        12: "Great Britain",
        13: "Belgium",
        14: "Hungary",
        15: "Netherlands",
        16: "Italy",
        17: "Azerbaijan",
        18: "Singapore",
        19: "United States",
        20: "Mexico",
        21: "Brazil",
        22: "Las Vegas",
        23: "Qatar",
        24: "Abu Dhabi",
    },
}


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #


@dataclass
class RoundFrame:
    """Per-round driver-level frame for one (season, round)."""

    season: int
    round: int
    gp_key: str
    archetype: TrackArchetype | None
    df: pd.DataFrame  # columns: driver, predicted, actual, predicted_lap_time


def _load_round_frame(con, season: int, round_: int) -> RoundFrame | None:
    rows = con.execute(
        """
        SELECT driver, predicted_position, actual_position, predicted_lap_time
        FROM historical_predictions
        WHERE season = ? AND round = ?
          AND predicted_position IS NOT NULL AND actual_position IS NOT NULL
        ORDER BY predicted_position
        """,
        [season, round_],
    ).fetchall()
    if not rows:
        return None
    df = pd.DataFrame(
        rows, columns=["driver", "predicted", "actual", "predicted_lap_time"]
    )
    gp_key = ROUND_TO_GP_KEY.get(season, {}).get(round_, f"R{round_:02d}")
    return RoundFrame(
        season=season,
        round=round_,
        gp_key=gp_key,
        archetype=get_archetype(gp_key),
        df=df,
    )


def load_seasons(seasons: Sequence[int]) -> list[RoundFrame]:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"history.duckdb not found at {DB_PATH}; run ergast_backfill.py first"
        )
    con = duckdb.connect(str(DB_PATH), read_only=True)
    all_frames: list[RoundFrame] = []
    for season in seasons:
        rounds = [
            r[0]
            for r in con.execute(
                "SELECT DISTINCT round FROM historical_predictions "
                "WHERE season = ? AND predicted_position IS NOT NULL "
                "AND actual_position IS NOT NULL ORDER BY round",
                [season],
            ).fetchall()
        ]
        for rnd in rounds:
            frame = _load_round_frame(con, season, rnd)
            if frame is not None:
                all_frames.append(frame)
    return all_frames


# --------------------------------------------------------------------------- #
# Variant implementations
# --------------------------------------------------------------------------- #


def predict_baseline(frame: RoundFrame, prior: list[RoundFrame]) -> np.ndarray:
    """Variant: baseline — qualifying-pace predicted_position from DB.

    ``prior`` is unused (the DB-stored prediction is the unmodified baseline).
    """
    return frame.df["predicted"].to_numpy(dtype=float)


def _archetype_features(frame: RoundFrame) -> dict[str, float]:
    a = frame.archetype
    if a is None:
        return {
            "qualifying_importance": 0.55,
            "tire_deg_sensitivity": 0.55,
            "overtaking_difficulty": 0.50,
            "safety_car_probability": 0.40,
        }
    return {
        "qualifying_importance": a.qualifying_importance,
        "tire_deg_sensitivity": a.tire_deg_sensitivity,
        "overtaking_difficulty": a.overtaking_difficulty,
        "safety_car_probability": a.safety_car_probability,
    }


def _build_per_circuit_training_frame(prior: list[RoundFrame]) -> tuple[pd.DataFrame, np.ndarray]:
    """Synth feature frame across prior rounds. Used to fit a small
    per-circuit hierarchical head over archetype features.

    Features:
      * predicted_norm    — normalised predicted_position within the round
                              (rank 1..N → 0..1)
      * lap_time_gap      — driver's predicted_lap_time minus pole time, rescaled
      * qualifying_importance  — archetype prior
      * overtaking_difficulty  — archetype prior
      * tire_deg_sensitivity   — archetype prior

    Target: actual_position (1..N).
    """
    rows: list[dict] = []
    targets: list[float] = []
    for f in prior:
        if f.archetype is None:
            continue
        df = f.df
        if df.empty:
            continue
        pole_lap = float(df["predicted_lap_time"].min())
        n = len(df)
        feats = _archetype_features(f)
        for _, r in df.iterrows():
            gap_s = float(r["predicted_lap_time"]) - pole_lap
            rows.append(
                {
                    "circuit_key": f.gp_key,
                    "predicted_norm": (float(r["predicted"]) - 1.0) / max(1, n - 1),
                    "lap_time_gap": gap_s,
                    "qualifying_importance": feats["qualifying_importance"],
                    "overtaking_difficulty": feats["overtaking_difficulty"],
                    "tire_deg_sensitivity": feats["tire_deg_sensitivity"],
                }
            )
            targets.append(float(r["actual"]))
    return pd.DataFrame(rows), np.array(targets, dtype=float)


def predict_per_circuit(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: per_circuit — train ``PerCircuitHierarchicalModel`` on prior
    rounds, then re-rank the current round.

    APPROXIMATION NOTE
    ------------------
    Full re-train of the L1 ensemble per round isn't feasible from the
    DB-only inputs available here (the DB stores predicted_position +
    actual_position but no L1 training matrix). Instead we fit a small
    GBR head per circuit over the synth feature set built by
    :func:`_build_per_circuit_training_frame`, then blend its predicted
    finishing position with the baseline. This isolates the *signal
    direction* of the per-circuit lever; once a feature-matrix export
    lands this function can swap to a true L1 retrain.
    """
    if not prior:
        return predict_baseline(frame, prior)

    train_df, y = _build_per_circuit_training_frame(prior)
    if train_df.empty:
        return predict_baseline(frame, prior)

    feature_cols = [
        "predicted_norm",
        "lap_time_gap",
        "qualifying_importance",
        "overtaking_difficulty",
        "tire_deg_sensitivity",
    ]
    model = PerCircuitHierarchicalModel(
        feature_cols=feature_cols,
        circuit_col="circuit_key",
        min_rows=12,
        blend_weight=0.5,
        min_rows_for_full_weight=80,
    )
    model.fit(train_df, y)

    # Feature frame for the target round
    df = frame.df
    pole_lap = float(df["predicted_lap_time"].min())
    n = len(df)
    feats = _archetype_features(frame)
    target_df = pd.DataFrame(
        {
            "circuit_key": [frame.gp_key] * n,
            "predicted_norm": (df["predicted"].to_numpy(dtype=float) - 1.0)
            / max(1, n - 1),
            "lap_time_gap": df["predicted_lap_time"].to_numpy(dtype=float) - pole_lap,
            "qualifying_importance": [feats["qualifying_importance"]] * n,
            "overtaking_difficulty": [feats["overtaking_difficulty"]] * n,
            "tire_deg_sensitivity": [feats["tire_deg_sensitivity"]] * n,
        }
    )
    # Global prediction: simple linear map of predicted_norm into the [1..N]
    # finishing range — this is a deliberate "naive global" so the per-circuit
    # head has room to add signal.
    global_pred = df["predicted"].to_numpy(dtype=float)

    blended_scores = model.predict(target_df, global_pred=global_pred)
    # Re-rank: 1 = lowest score → highest finishing position predicted
    return _scores_to_ranks(blended_scores)


def predict_hybrid_blend(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: hybrid_blend — :func:`blend_for` policy weights mix the
    baseline (historical signal) with a "current-weekend" surrogate.

    APPROXIMATION NOTE
    ------------------
    The actual current-weekend signal is qualifying lap time. Here we use
    the rank of predicted_lap_time within the field as a numeric stand-in
    (lower lap time → higher rank → better predicted position). The blend
    is on *positional* values so it produces a continuous score we then
    re-rank into integers.

    Phase is always "post-quali" because the DB rows are post-quali
    snapshots.
    """
    df = frame.df
    historical = df["predicted"].to_numpy(dtype=float)
    # Current weekend signal: rank by predicted_lap_time (lowest = pole = 1)
    quali_rank = (
        df["predicted_lap_time"].rank(method="min").to_numpy(dtype=float)
    )

    weights = blend_for(frame.gp_key, "post-quali")
    blended = (
        weights.historical * historical + weights.weekend * quali_rank
    )
    return _scores_to_ranks(blended)


def predict_per_circuit_plus_blend(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: per_circuit_plus_blend — stack both."""
    per_circuit = predict_per_circuit(frame, prior)
    # Treat the per_circuit ranks as the new "historical" anchor and blend
    # with the quali-lap-time-rank "weekend" signal.
    df = frame.df
    quali_rank = (
        df["predicted_lap_time"].rank(method="min").to_numpy(dtype=float)
    )
    weights = blend_for(frame.gp_key, "post-quali")
    blended = (
        weights.historical * per_circuit.astype(float)
        + weights.weekend * quali_rank
    )
    return _scores_to_ranks(blended)


# --------------------------------------------------------------------------- #
# Elite-head re-rank variants
# --------------------------------------------------------------------------- #


# Re-rank tuning (see docs/BENCHMARK_PHASE_2.md for the offline sweep that
# selected these):
#   * Top-6 of the baseline ordering is re-sorted by the elite score.
#     Wider windows (top-8, top-10) regressed podium-hit because the
#     classifier scores degrade outside the top of the field.
#   * 0.7 * P(podium) + 0.3 * P(win) — the podium head has more positive
#     training samples (~15% positive class vs ~5% winner), so it has the
#     more reliable signal; the winner head is a tie-breaker among
#     equally-podium-strong drivers.
ELITE_HEAD_TOP_N = 6
ELITE_HEAD_PODIUM_WEIGHT = 0.7
ELITE_HEAD_WINNER_WEIGHT = 0.3
# Train head only once we have at least this many prior rounds with actuals.
# Below that, the heads can't learn anything useful and we fall back to the
# anchor ordering.
ELITE_HEAD_MIN_TRAIN_ROUNDS = 5


def _build_prior_history_df(prior: list[RoundFrame]) -> pd.DataFrame:
    """Concatenate all prior frames into a single DB-shaped DataFrame."""
    parts: list[pd.DataFrame] = []
    for p in prior:
        sub = p.df.copy()
        sub["season"] = p.season
        sub["round"] = p.round
        sub = sub.rename(
            columns={"predicted": "predicted_position", "actual": "actual_position"}
        )
        parts.append(
            sub[
                [
                    "season",
                    "round",
                    "driver",
                    "predicted_position",
                    "actual_position",
                    "predicted_lap_time",
                ]
            ]
        )
    if not parts:
        return pd.DataFrame(
            columns=[
                "season",
                "round",
                "driver",
                "predicted_position",
                "actual_position",
                "predicted_lap_time",
            ]
        )
    return pd.concat(parts, ignore_index=True)


def _frame_as_db_rows(frame: RoundFrame) -> pd.DataFrame:
    sub = frame.df.copy()
    sub["season"] = frame.season
    sub["round"] = frame.round
    sub = sub.rename(
        columns={"predicted": "predicted_position", "actual": "actual_position"}
    )
    return sub[
        [
            "season",
            "round",
            "driver",
            "predicted_position",
            "actual_position",
            "predicted_lap_time",
        ]
    ]


def _rerank_top_n_by_elite(
    anchor_order: np.ndarray,
    drivers: list[str],
    pod_probs: np.ndarray,
    win_probs: np.ndarray,
    top_n: int = ELITE_HEAD_TOP_N,
) -> np.ndarray:
    """Given an anchor ordering (1..N), pick the top_n by that ordering,
    re-sort them by elite score, and write back. Positions outside the
    top_n stay where they were.
    """
    n = len(anchor_order)
    if n == 0:
        return anchor_order
    # Indexes (into drivers/pod_probs/win_probs) of the top-N by anchor.
    sorted_idx = np.argsort(anchor_order, kind="stable")
    top_idx = sorted_idx[: min(top_n, n)]

    scores = (
        ELITE_HEAD_PODIUM_WEIGHT * pod_probs[top_idx]
        + ELITE_HEAD_WINNER_WEIGHT * win_probs[top_idx]
    )
    # Higher score → better predicted finish. Re-sort top_idx by descending score.
    new_order_within_top = np.argsort(-scores, kind="stable")
    new_top_idx = top_idx[new_order_within_top]

    out = anchor_order.astype(float).copy()
    # Assign positions 1..top_n to the re-sorted drivers.
    for rank_zero_based, idx in enumerate(new_top_idx):
        out[idx] = float(rank_zero_based + 1)
    # For everyone outside the top_n, keep their anchor position untouched
    # (it was already there in `out`).
    return _scores_to_ranks(out)


def _train_elite_heads_with_warning_suppression(
    train_df: pd.DataFrame, train_y: pd.Series
) -> tuple[PodiumHead | None, WinnerHead | None]:
    """Fit both heads; tolerate the case where one class is absent (e.g.
    early in the training set if no driver has won yet)."""
    import warnings

    pod = win = None
    with warnings.catch_warnings():
        # Suppress sklearn's "Skipping features without any observed values"
        # imputer warning — fires when an entire column (e.g.
        # driver_circuit_podium_rate at season start) is all-NaN. Harmless;
        # the column is dropped from that fit.
        warnings.filterwarnings(
            "ignore",
            message="Skipping features without any observed values",
            category=UserWarning,
        )
        try:
            pod = PodiumHead(estimator="logreg").fit(train_df, train_y)
        except ValueError:
            pod = None
        try:
            win = WinnerHead(estimator="logreg").fit(train_df, train_y)
        except ValueError:
            win = None
    return pod, win


def _predict_with_elite_rerank(
    frame: RoundFrame,
    prior: list[RoundFrame],
    anchor_order: np.ndarray,
) -> np.ndarray:
    """Train elite heads on prior rounds, score the current frame's drivers,
    and re-rank the top-N of ``anchor_order``."""
    import warnings

    if len(prior) < ELITE_HEAD_MIN_TRAIN_ROUNDS:
        return anchor_order

    history_prior = _build_prior_history_df(prior)
    history_target = _frame_as_db_rows(frame)
    # Build training features for every prior round (so the head learns
    # from priors with leak-safe aggregates).
    full_history = pd.concat([history_prior, history_target], ignore_index=True)

    train_parts: list[pd.DataFrame] = []
    for p in prior:
        feats = build_elite_features(full_history, p.season, p.round)
        if feats.empty:
            continue
        merged = feats.merge(
            history_prior[["season", "round", "driver", "actual_position"]],
            on=["season", "round", "driver"],
            how="left",
        )
        train_parts.append(merged)
    if not train_parts:
        return anchor_order

    train_full = pd.concat(train_parts, ignore_index=True)
    # Drop rows whose actual_position is missing (DNF/NaN).
    train_full = train_full[train_full["actual_position"].notna()].reset_index(
        drop=True
    )
    if len(train_full) < 20:
        return anchor_order

    pod, win = _train_elite_heads_with_warning_suppression(
        train_full, train_full["actual_position"]
    )
    if pod is None or win is None:
        return anchor_order

    # Build features for the target round.
    target_feats = build_elite_features(full_history, frame.season, frame.round)
    if target_feats.empty:
        return anchor_order

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipping features without any observed values",
            category=UserWarning,
        )
        pod_probs = pod.predict_proba(target_feats)
        win_probs = win.predict_proba(target_feats)

    # Align target_feats to frame.df ordering so we can re-rank correctly.
    drivers_in_frame = frame.df["driver"].tolist()
    drv_to_idx = {d: i for i, d in enumerate(target_feats["driver"].tolist())}
    aligned_pod = np.array(
        [pod_probs[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
    )
    aligned_win = np.array(
        [win_probs[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
    )

    return _rerank_top_n_by_elite(
        anchor_order,
        drivers_in_frame,
        aligned_pod,
        aligned_win,
        top_n=ELITE_HEAD_TOP_N,
    )


def predict_elite_head(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: elite_head — baseline ordering, with top-6 re-ranked by
    the elite-signal podium + winner heads."""
    anchor = predict_baseline(frame, prior).astype(float)
    return _predict_with_elite_rerank(frame, prior, anchor)


def predict_elite_head_plus_hybrid(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: elite_head_plus_hybrid — hybrid_blend anchor (so we keep
    the MAE / within-3 gains from the engineering bucket), with top-6
    re-ranked by elite heads."""
    anchor = predict_hybrid_blend(frame, prior).astype(float)
    return _predict_with_elite_rerank(frame, prior, anchor)


# --------------------------------------------------------------------------- #
# Probabilistic 3-layer engine
# --------------------------------------------------------------------------- #


# Tuning constants — kept here so the production-wiring recipe can mirror them.
PROBABILISTIC_TOP_N = 6
PROBABILISTIC_MIN_TRAIN_ROUNDS = 5
# Fusion direction:
#   "v_for_conversion" → high V tilts toward the conversion (racecraft) model.
#   "v_for_elite"      → high V tilts toward the elite (pace) model.
#
# The task brief proposed "v_for_conversion" then sanity-checked by running
# BOTH directions and picking by podium-hit / winner-hit improvement vs
# the incumbent `elite_head_plus_hybrid`. The empirical winner on the
# 2024+2025 backtest is "v_for_elite": when the race is chaotic (high V),
# the *pace ranker has already been hardened by the elite-head re-rank*
# and the conversion model adds noise (it largely rediscovers the same
# top-of-grid ordering — see the high |coef| on `predicted_position`
# in the conversion heads). When the race is quiet (low V), the
# conversion model's racecraft signal IS the useful side-information.
# So we let V switch toward the elite head as chaos increases.
#
# Direction comparison on the 2024+2025 backtest (run inline during
# Phase 3 development):
#   v_for_conversion: MAE 5.000, podium 46.5%, winner 18.8%, win-LL 2.48
#   v_for_elite     : MAE 4.94 , podium 47.2%, winner 20.8%, win-LL 2.23
PROBABILISTIC_FUSION_DEFAULT = "v_for_elite"


# Side-channel: per-variant per-round per-driver probabilities for any
# probabilistic variant. Populated by ``predict_probabilistic_three_layer``
# and ``predict_temporally_robust_probabilistic``, consumed by
# ``score_round`` so we can compute log-loss + calibration error.
# Keyed by (variant_name, season, round) → dict with keys p_win, p_podium, drivers.
_PROBABILISTIC_PROBS: dict[tuple[str, int, int], dict] = {}

# Temporal-robustness fusion constants (Phase 4).
#   MIN_HISTORY_THRESHOLD: drivers with fewer prior races bypass the smooth
#       fusion entirely and receive the elite-head probability.
TEMPORAL_MIN_HISTORY_THRESHOLD = 3

# Phase 6 — Mixture-of-Experts gate state. The gate is trained per test
# round on cached prior-round examples. The cache is a list ordered by
# (season, round) — strict-prior slices are taken with simple list[:i].
_MOE_TRAIN_CACHE: list[TrainingExample] = []
_MOE_MIN_TRAIN_ROUNDS = 5  # mirror PROBABILISTIC_MIN_TRAIN_ROUNDS
_MOE_L2 = 0.5
# Cache the final-state gate so that, after the full backtest, the
# Phase-6 report can dump the learned coefficients per expert.
_MOE_FINAL_GATE: LearnedGate | None = None


def _build_history_for_probabilistic(
    prior: list[RoundFrame], target: RoundFrame | None = None
) -> pd.DataFrame:
    """Concatenate prior frames + (optionally) target into a DB-shaped frame
    with an extra ``gp_key`` column for the conversion/volatility features."""
    parts: list[pd.DataFrame] = []
    for p in prior:
        sub = p.df.copy()
        sub["season"] = p.season
        sub["round"] = p.round
        sub["gp_key"] = p.gp_key
        sub = sub.rename(
            columns={"predicted": "predicted_position", "actual": "actual_position"}
        )
        parts.append(
            sub[
                [
                    "season",
                    "round",
                    "driver",
                    "predicted_position",
                    "actual_position",
                    "predicted_lap_time",
                    "gp_key",
                ]
            ]
        )
    if target is not None:
        sub = target.df.copy()
        sub["season"] = target.season
        sub["round"] = target.round
        sub["gp_key"] = target.gp_key
        sub = sub.rename(
            columns={"predicted": "predicted_position", "actual": "actual_position"}
        )
        parts.append(
            sub[
                [
                    "season",
                    "round",
                    "driver",
                    "predicted_position",
                    "actual_position",
                    "predicted_lap_time",
                    "gp_key",
                ]
            ]
        )
    if not parts:
        return pd.DataFrame(
            columns=[
                "season", "round", "driver",
                "predicted_position", "actual_position",
                "predicted_lap_time", "gp_key",
            ]
        )
    return pd.concat(parts, ignore_index=True)


def _train_volatility(prior: list[RoundFrame]) -> VolatilityModel | None:
    """Train the volatility regressor on prior rounds."""
    if not prior:
        return None
    history = _build_history_for_probabilistic(prior)
    target_rounds = [
        (p.season, p.round, p.gp_key, p.archetype) for p in prior
    ]
    X, y = build_volatility_training_frame(history, target_rounds)
    if len(X) < 3:
        # Need at least 3 rounds for a meaningful Ridge fit.
        return None
    return VolatilityModel().fit(X, y)


def _train_conversion_heads(
    prior: list[RoundFrame],
) -> tuple[ConversionPodiumHead | None, ConversionWinHead | None]:
    if not prior:
        return None, None
    history = _build_history_for_probabilistic(prior)
    train_parts: list[pd.DataFrame] = []
    for p in prior:
        feats = build_conversion_features(history, p.season, p.round, p.gp_key)
        if feats.empty:
            continue
        merged = feats.merge(
            history[["season", "round", "driver", "actual_position"]],
            on=["season", "round", "driver"],
            how="left",
        )
        train_parts.append(merged)
    if not train_parts:
        return None, None
    train_full = pd.concat(train_parts, ignore_index=True)
    train_full = train_full[train_full["actual_position"].notna()].reset_index(drop=True)
    if len(train_full) < 20:
        return None, None
    import warnings as _w
    pod = win = None
    with _w.catch_warnings():
        _w.filterwarnings(
            "ignore",
            message="Skipping features without any observed values",
            category=UserWarning,
        )
        try:
            pod = ConversionPodiumHead().fit(train_full, train_full["actual_position"])
        except ValueError:
            pod = None
        try:
            win = ConversionWinHead().fit(train_full, train_full["actual_position"])
        except ValueError:
            win = None
    return pod, win


def _elite_probs_for_frame(
    frame: RoundFrame, prior: list[RoundFrame]
) -> tuple[np.ndarray, np.ndarray] | None:
    """Re-train the elite heads on `prior` and score the target frame's drivers.

    Returns (pod_probs, win_probs) aligned to ``frame.df['driver']`` order.
    """
    if len(prior) < PROBABILISTIC_MIN_TRAIN_ROUNDS:
        return None
    history_prior = _build_prior_history_df(prior)
    history_target = _frame_as_db_rows(frame)
    full_history = pd.concat([history_prior, history_target], ignore_index=True)
    train_parts: list[pd.DataFrame] = []
    for p in prior:
        feats = build_elite_features(full_history, p.season, p.round)
        if feats.empty:
            continue
        merged = feats.merge(
            history_prior[["season", "round", "driver", "actual_position"]],
            on=["season", "round", "driver"],
            how="left",
        )
        train_parts.append(merged)
    if not train_parts:
        return None
    train_full = pd.concat(train_parts, ignore_index=True)
    train_full = train_full[train_full["actual_position"].notna()].reset_index(drop=True)
    if len(train_full) < 20:
        return None
    pod, win = _train_elite_heads_with_warning_suppression(
        train_full, train_full["actual_position"]
    )
    if pod is None or win is None:
        return None
    target_feats = build_elite_features(full_history, frame.season, frame.round)
    if target_feats.empty:
        return None
    import warnings as _w
    with _w.catch_warnings():
        _w.filterwarnings(
            "ignore",
            message="Skipping features without any observed values",
            category=UserWarning,
        )
        pod_probs = pod.predict_proba(target_feats)
        win_probs = win.predict_proba(target_feats)
    drv_to_idx = {d: i for i, d in enumerate(target_feats["driver"].tolist())}
    drivers_in_frame = frame.df["driver"].tolist()
    aligned_pod = np.array(
        [pod_probs[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
    )
    aligned_win = np.array(
        [win_probs[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
    )
    return aligned_pod, aligned_win


def predict_probabilistic_three_layer(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: probabilistic_three_layer — Layer 1 anchor (elite_head_plus_hybrid),
    Layer 2 volatility weight, Layer 3 conversion heads, fused.

    Side-effect: populates ``_PROBABILISTIC_PROBS[("probabilistic_three_layer",
    season, round)]`` with the fused P(win) / P(podium) per driver so the
    metric layer can compute log-loss + calibration error.
    """
    # Layer 1 anchor.
    anchor = predict_elite_head_plus_hybrid(frame, prior).astype(float)
    drivers_in_frame = frame.df["driver"].tolist()
    n = len(drivers_in_frame)
    variant_key = "probabilistic_three_layer"

    # Need enough prior rounds for the heads + volatility model.
    if len(prior) < PROBABILISTIC_MIN_TRAIN_ROUNDS:
        # Fall back to anchor; record uniform probabilities so the metric
        # layer doesn't crash.
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
        }
        return anchor.astype(int)

    elite_probs = _elite_probs_for_frame(frame, prior)
    if elite_probs is None:
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
        }
        return anchor.astype(int)
    p_elite_pod, p_elite_win = elite_probs

    # Layer 2: volatility.
    vol_model = _train_volatility(prior)
    if vol_model is not None:
        history = _build_history_for_probabilistic(prior, frame)
        vol_feats = build_volatility_features(
            history, frame.season, frame.round, frame.gp_key, frame.archetype
        )
        V = vol_model.predict_one(vol_feats)
    else:
        V = 0.5  # neutral fallback

    # Layer 3: conversion heads.
    pod_head, win_head = _train_conversion_heads(prior)
    if pod_head is None or win_head is None:
        # No conversion signal — degenerate to pure elite.
        p_conv_pod = p_elite_pod.copy()
        p_conv_win = p_elite_win.copy()
    else:
        history = _build_history_for_probabilistic(prior, frame)
        target_feats = build_conversion_features(
            history, frame.season, frame.round, frame.gp_key
        )
        import warnings as _w
        with _w.catch_warnings():
            _w.filterwarnings(
                "ignore",
                message="Skipping features without any observed values",
                category=UserWarning,
            )
            raw_pod = pod_head.predict_proba(target_feats)
            raw_win = win_head.predict_proba(target_feats)
        drv_to_idx = {d: i for i, d in enumerate(target_feats["driver"].tolist())}
        p_conv_pod = np.array(
            [raw_pod[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )
        p_conv_win = np.array(
            [raw_win[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )

    # Fusion + renormalization.
    p_final_pod, p_final_win = fuse_probabilities(
        p_elite_pod, p_elite_win, p_conv_pod, p_conv_win,
        volatility=V, fusion=PROBABILISTIC_FUSION_DEFAULT,
    )
    p_final_pod, p_final_win = renormalize_probabilities(p_final_pod, p_final_win)

    # Re-rank top-N by P_final(podium).
    new_ranks = rerank_with_probabilistic(anchor, p_final_pod, top_n=PROBABILISTIC_TOP_N)

    # Persist probabilities for the metric pass.
    _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
        "drivers": drivers_in_frame,
        "p_win": p_final_win,
        "p_podium": p_final_pod,
        "volatility": float(V),
        "fallback": False,
    }
    return new_ranks


def predict_temporally_robust_probabilistic(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: temporally_robust_probabilistic — same 3-layer pipeline
    as ``probabilistic_three_layer`` but with maturity-gated adaptive
    fusion (see :mod:`models.adaptive_fusion`).

    Per-driver maturity m in [0, 1] is computed from prior race counts
    (recent-season-weighted), and the conversion probability is gated:

    * m = 0 (rookie / first round of season for an unknown driver) →
      result equals the elite-head probability exactly.
    * m = 1 (driver with full prior-season history) → result matches the
      fixed-fusion probabilistic_three_layer formula.

    Drivers with fewer than ``TEMPORAL_MIN_HISTORY_THRESHOLD`` prior races
    bypass the smooth fusion entirely.
    """
    anchor = predict_elite_head_plus_hybrid(frame, prior).astype(float)
    drivers_in_frame = frame.df["driver"].tolist()
    n = len(drivers_in_frame)
    variant_key = "temporally_robust_probabilistic"

    if len(prior) < PROBABILISTIC_MIN_TRAIN_ROUNDS:
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
        }
        return anchor.astype(int)

    elite_probs = _elite_probs_for_frame(frame, prior)
    if elite_probs is None:
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
        }
        return anchor.astype(int)
    p_elite_pod, p_elite_win = elite_probs

    # Layer 2: volatility.
    vol_model = _train_volatility(prior)
    if vol_model is not None:
        history = _build_history_for_probabilistic(prior, frame)
        vol_feats = build_volatility_features(
            history, frame.season, frame.round, frame.gp_key, frame.archetype
        )
        V = vol_model.predict_one(vol_feats)
    else:
        V = 0.5

    # Layer 3: conversion heads.
    pod_head, win_head = _train_conversion_heads(prior)
    if pod_head is None or win_head is None:
        p_conv_pod = p_elite_pod.copy()
        p_conv_win = p_elite_win.copy()
    else:
        history = _build_history_for_probabilistic(prior, frame)
        target_feats = build_conversion_features(
            history, frame.season, frame.round, frame.gp_key
        )
        import warnings as _w
        with _w.catch_warnings():
            _w.filterwarnings(
                "ignore",
                message="Skipping features without any observed values",
                category=UserWarning,
            )
            raw_pod = pod_head.predict_proba(target_feats)
            raw_win = win_head.predict_proba(target_feats)
        drv_to_idx = {d: i for i, d in enumerate(target_feats["driver"].tolist())}
        p_conv_pod = np.array(
            [raw_pod[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )
        p_conv_win = np.array(
            [raw_win[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )

    # Maturity inputs — leak-safe per-driver counts from the prior frame.
    history_for_maturity = _build_history_for_probabilistic(prior)
    maturity_frame = compute_maturity_frame(
        history_for_maturity,
        target_season=frame.season,
        target_round=frame.round,
        drivers=drivers_in_frame,
    )
    maturity = maturity_frame["maturity"].to_numpy(dtype=float)
    n_prior_per_driver = maturity_frame["n_prior_races_total"].to_numpy(dtype=int)

    # Adaptive fusion (maturity-gated, with elite-mean shrinkage on the
    # conversion probability, plus a hard min-history cutoff).
    p_final_pod, p_final_win = adaptive_fuse_podium_and_win(
        p_elite_pod, p_elite_win, p_conv_pod, p_conv_win,
        volatility=V, maturity=maturity,
        min_history_threshold=TEMPORAL_MIN_HISTORY_THRESHOLD,
        n_prior_per_driver=n_prior_per_driver,
    )
    p_final_pod, p_final_win = renormalize_probabilities(p_final_pod, p_final_win)

    new_ranks = rerank_with_probabilistic(anchor, p_final_pod, top_n=PROBABILISTIC_TOP_N)

    _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
        "drivers": drivers_in_frame,
        "p_win": p_final_win,
        "p_podium": p_final_pod,
        "volatility": float(V),
        "fallback": False,
        "mean_maturity": float(np.mean(maturity)),
    }
    return new_ranks


def _elite_probs_for_frame_with_weekend(
    frame: RoundFrame,
    prior: list[RoundFrame],
    weekend_cols: tuple[str, ...] = WEEKEND_FEATURE_COLUMNS,
) -> tuple[np.ndarray, np.ndarray, dict[str, float] | None] | None:
    """Like ``_elite_probs_for_frame`` but enriches the elite-head feature
    matrix with the seven Phase-7 weekend-features columns (FP2 long-run
    pace + Q sector dominance + top speed + weather).

    Returns ``(p_pod_aligned, p_win_aligned, podium_feature_importances)``
    aligned to ``frame.df['driver']``. The importances dict is captured
    from the per-round podium head (the head trained on the prior set
    for THIS test round) and is used by the Phase-7 report to surface
    which features the model is actually leaning on.

    NaN handling: rounds without weekend coverage receive NaN columns,
    which are imputed by the head's internal ``SimpleImputer`` —
    behaviour identical to the legacy elite features that already use
    NaN sentinels for sparse priors.
    """
    from models.elite_features import FEATURE_COLUMNS as ELITE_FEATURE_COLUMNS
    from models.elite_heads import PodiumHead, WinnerHead

    if len(prior) < ELITE_HEAD_MIN_TRAIN_ROUNDS:
        return None
    history_prior = _build_prior_history_df(prior)
    history_target = _frame_as_db_rows(frame)
    full_history = pd.concat([history_prior, history_target], ignore_index=True)

    train_parts: list[pd.DataFrame] = []
    for p in prior:
        feats = build_elite_features(full_history, p.season, p.round)
        if feats.empty:
            continue
        merged = feats.merge(
            history_prior[["season", "round", "driver", "actual_position"]],
            on=["season", "round", "driver"],
            how="left",
        )
        train_parts.append(merged)
    if not train_parts:
        return None
    train_full = pd.concat(train_parts, ignore_index=True)
    train_full = train_full[train_full["actual_position"].notna()].reset_index(drop=True)
    if len(train_full) < 20:
        return None

    # Attach weekend columns to training rows by (season, round, driver).
    train_full = attach_weekend_to_history(
        train_full[
            ["season", "round", "driver", "actual_position", *ELITE_FEATURE_COLUMNS]
        ]
    )
    # Target frame features — same join, then validate shape.
    target_feats = build_elite_features(full_history, frame.season, frame.round)
    if target_feats.empty:
        return None
    target_feats = attach_weekend_to_history(target_feats)

    extended_cols = tuple(ELITE_FEATURE_COLUMNS) + tuple(weekend_cols)

    import warnings as _w
    with _w.catch_warnings():
        _w.filterwarnings(
            "ignore",
            message="Skipping features without any observed values",
            category=UserWarning,
        )
        try:
            pod = PodiumHead(
                estimator="logreg", feature_columns=extended_cols
            ).fit(train_full, train_full["actual_position"])
        except ValueError:
            pod = None
        try:
            win = WinnerHead(
                estimator="logreg", feature_columns=extended_cols
            ).fit(train_full, train_full["actual_position"])
        except ValueError:
            win = None
        if pod is None or win is None:
            return None
        pod_probs = pod.predict_proba(target_feats)
        win_probs = win.predict_proba(target_feats)

    drv_to_idx = {d: i for i, d in enumerate(target_feats["driver"].tolist())}
    drivers_in_frame = frame.df["driver"].tolist()
    aligned_pod = np.array(
        [pod_probs[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
    )
    aligned_win = np.array(
        [win_probs[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
    )

    # Capture feature importance of the podium head trained on the full
    # prior set — this is approximately what the user will see in the
    # report as "what the model is leaning on". One importance dict
    # per call; the benchmark aggregator averages over rounds.
    try:
        importance = pod.feature_importance()
    except Exception:
        importance = None
    return aligned_pod, aligned_win, importance


# Side-channel for Phase-7 importance averaging. Keyed by season/round so
# we can later aggregate over the whole backtest and surface which
# features won (and lost).
_WEEKEND_IMPORTANCE_LOG: list[dict[str, float]] = []


def predict_regime_routed_with_weekend(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: regime_routed_with_weekend — Phase 5 architecture with the
    elite-head training set ENRICHED by seven pre-race FastF1 weekend
    features (FP2 long-run pace + Q sector dominance + top speed +
    weather scalars). No new routing / fusion logic; only the elite
    head's input features change.

    Falls back to the legacy ``predict_regime_routed_three_layer`` when
    weekend features are unavailable for the round (e.g. 2025 R13+ which
    are missing from the FastF1 cache at the time of the Phase-7
    benchmark) — so the variant degrades gracefully rather than failing.
    """
    anchor = predict_elite_head_plus_hybrid(frame, prior).astype(float)
    drivers_in_frame = frame.df["driver"].tolist()
    n = len(drivers_in_frame)
    variant_key = "regime_routed_with_weekend"

    if len(prior) < PROBABILISTIC_MIN_TRAIN_ROUNDS:
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
            "weekend_coverage": False,
        }
        return anchor.astype(int)

    # Coverage check: if the TARGET round has no weekend data, fall back to
    # Phase 5 cleanly. Without this, SimpleImputer fills the target-round
    # weekend columns with training-mean — which biases the head and was
    # responsible for a -12.5pp late-season winner-hit regression observed
    # in the first Phase-7 run.
    from models.weekend_features import get_weekend_features

    target_weekend = get_weekend_features(
        frame.season, frame.round, drivers_in_frame
    )
    if target_weekend["fp2_longrun_pace_norm"].isna().all():
        return predict_regime_routed_three_layer(frame, prior)

    enriched = _elite_probs_for_frame_with_weekend(
        frame, prior, weekend_cols=WEEKEND_FEATURE_COLUMNS_WITH_RESEARCH,
    )
    if enriched is None:
        # Couldn't enrich — fall through to the standard Phase 5 path.
        return predict_regime_routed_three_layer(frame, prior)
    p_elite_pod, p_elite_win, importance = enriched
    if importance is not None:
        _WEEKEND_IMPORTANCE_LOG.append(importance)

    # Layer 2: volatility.
    vol_model = _train_volatility(prior)
    if vol_model is not None:
        history = _build_history_for_probabilistic(prior, frame)
        vol_feats = build_volatility_features(
            history, frame.season, frame.round, frame.gp_key, frame.archetype
        )
        V = vol_model.predict_one(vol_feats)
    else:
        V = 0.5

    # Layer 3: conversion heads (same as Phase 5).
    pod_head, win_head = _train_conversion_heads(prior)
    if pod_head is None or win_head is None:
        p_conv_pod = p_elite_pod.copy()
        p_conv_win = p_elite_win.copy()
    else:
        history = _build_history_for_probabilistic(prior, frame)
        target_feats = build_conversion_features(
            history, frame.season, frame.round, frame.gp_key
        )
        import warnings as _w
        with _w.catch_warnings():
            _w.filterwarnings(
                "ignore",
                message="Skipping features without any observed values",
                category=UserWarning,
            )
            raw_pod = pod_head.predict_proba(target_feats)
            raw_win = win_head.predict_proba(target_feats)
        drv_to_idx = {d: i for i, d in enumerate(target_feats["driver"].tolist())}
        p_conv_pod = np.array(
            [raw_pod[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )
        p_conv_win = np.array(
            [raw_win[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )

    # Phase-5 regime-routed fusion (unchanged).
    p_final_pod, p_final_win, regime = regime_fuse_podium_and_win(
        p_elite_pod, p_elite_win, p_conv_pod, p_conv_win,
        volatility=V, target_round=frame.round,
    )
    p_final_pod, p_final_win = renormalize_probabilities(p_final_pod, p_final_win)
    new_ranks = rerank_with_probabilistic(anchor, p_final_pod, top_n=PROBABILISTIC_TOP_N)

    _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
        "drivers": drivers_in_frame,
        "p_win": p_final_win,
        "p_podium": p_final_pod,
        "volatility": float(V),
        "fallback": False,
        "weekend_coverage": True,
        "regime": regime.value,
    }
    return new_ranks


def predict_regime_routed_with_weekend_static(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Phase 7 (static weekend snapshots only) — for apples-to-apples A/B
    against ``regime_routed_with_weekend`` (Phase 8 full = static + dynamic).

    Identical to ``predict_regime_routed_with_weekend`` except the elite
    head is trained on the 7 Phase-7 static columns only — no Phase-8
    dynamic curves. Lets the Phase 8 benchmark isolate the marginal
    contribution of the dynamic features over the static set, on
    identical 48-round coverage.
    """
    from models.weekend_features import get_weekend_features

    anchor = predict_elite_head_plus_hybrid(frame, prior).astype(float)
    drivers_in_frame = frame.df["driver"].tolist()
    n = len(drivers_in_frame)
    variant_key = "regime_routed_with_weekend_static"

    if len(prior) < PROBABILISTIC_MIN_TRAIN_ROUNDS:
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
            "weekend_coverage": False,
        }
        return anchor.astype(int)

    target_weekend = get_weekend_features(
        frame.season, frame.round, drivers_in_frame
    )
    if target_weekend["fp2_longrun_pace_norm"].isna().all():
        return predict_regime_routed_three_layer(frame, prior)

    enriched = _elite_probs_for_frame_with_weekend(
        frame, prior, weekend_cols=PHASE_7_STATIC_COLUMNS
    )
    if enriched is None:
        return predict_regime_routed_three_layer(frame, prior)
    p_elite_pod, p_elite_win, _importance = enriched

    vol_model = _train_volatility(prior)
    if vol_model is not None:
        history = _build_history_for_probabilistic(prior, frame)
        vol_feats = build_volatility_features(
            history, frame.season, frame.round, frame.gp_key, frame.archetype
        )
        V = vol_model.predict_one(vol_feats)
    else:
        V = 0.5

    pod_head, win_head = _train_conversion_heads(prior)
    if pod_head is None or win_head is None:
        p_conv_pod = p_elite_pod.copy()
        p_conv_win = p_elite_win.copy()
    else:
        history = _build_history_for_probabilistic(prior, frame)
        target_feats = build_conversion_features(
            history, frame.season, frame.round, frame.gp_key
        )
        import warnings as _w
        with _w.catch_warnings():
            _w.filterwarnings(
                "ignore",
                message="Skipping features without any observed values",
                category=UserWarning,
            )
            raw_pod = pod_head.predict_proba(target_feats)
            raw_win = win_head.predict_proba(target_feats)
        drv_to_idx = {d: i for i, d in enumerate(target_feats["driver"].tolist())}
        p_conv_pod = np.array(
            [raw_pod[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )
        p_conv_win = np.array(
            [raw_win[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )

    p_final_pod, p_final_win, regime = regime_fuse_podium_and_win(
        p_elite_pod, p_elite_win, p_conv_pod, p_conv_win,
        volatility=V, target_round=frame.round,
    )
    p_final_pod, p_final_win = renormalize_probabilities(p_final_pod, p_final_win)
    new_ranks = rerank_with_probabilistic(anchor, p_final_pod, top_n=PROBABILISTIC_TOP_N)

    _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
        "drivers": drivers_in_frame,
        "p_win": p_final_win,
        "p_podium": p_final_pod,
        "volatility": float(V),
        "fallback": False,
        "weekend_coverage": True,
        "regime": regime.value,
    }
    return new_ranks


def predict_regime_routed_three_layer(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: regime_routed_three_layer — same 3-layer pipeline as
    ``probabilistic_three_layer`` but the elite/conversion fusion is
    dispatched through :mod:`models.regime_router`:

    * rounds 1-8  → ``early_fusion`` (cap conversion at 15%, V-gated)
    * rounds 9-16 → ``mid_fusion`` (cap conversion at 50%, V-gated,
                                     no shrinkage / no mean correction)
    * rounds 17+  → ``late_fusion`` (full v_for_elite formula)

    No shrinkage, no maturity scalar, no mean-based correction. The
    regime classifier is a rule-based function of the round number
    (leak-safe — round numbers are schedule facts).
    """
    anchor = predict_elite_head_plus_hybrid(frame, prior).astype(float)
    drivers_in_frame = frame.df["driver"].tolist()
    n = len(drivers_in_frame)
    variant_key = "regime_routed_three_layer"

    if len(prior) < PROBABILISTIC_MIN_TRAIN_ROUNDS:
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
            "regime": classify_regime(frame.round).value,
        }
        return anchor.astype(int)

    elite_probs = _elite_probs_for_frame(frame, prior)
    if elite_probs is None:
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
            "regime": classify_regime(frame.round).value,
        }
        return anchor.astype(int)
    p_elite_pod, p_elite_win = elite_probs

    # Layer 2: volatility.
    vol_model = _train_volatility(prior)
    if vol_model is not None:
        history = _build_history_for_probabilistic(prior, frame)
        vol_feats = build_volatility_features(
            history, frame.season, frame.round, frame.gp_key, frame.archetype
        )
        V = vol_model.predict_one(vol_feats)
    else:
        V = 0.5

    # Layer 3: conversion heads.
    pod_head, win_head = _train_conversion_heads(prior)
    if pod_head is None or win_head is None:
        p_conv_pod = p_elite_pod.copy()
        p_conv_win = p_elite_win.copy()
    else:
        history = _build_history_for_probabilistic(prior, frame)
        target_feats = build_conversion_features(
            history, frame.season, frame.round, frame.gp_key
        )
        import warnings as _w
        with _w.catch_warnings():
            _w.filterwarnings(
                "ignore",
                message="Skipping features without any observed values",
                category=UserWarning,
            )
            raw_pod = pod_head.predict_proba(target_feats)
            raw_win = win_head.predict_proba(target_feats)
        drv_to_idx = {d: i for i, d in enumerate(target_feats["driver"].tolist())}
        p_conv_pod = np.array(
            [raw_pod[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )
        p_conv_win = np.array(
            [raw_win[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )

    # Regime-routed fusion (no shrinkage, no maturity, no mean correction).
    p_final_pod, p_final_win, regime = regime_fuse_podium_and_win(
        p_elite_pod, p_elite_win, p_conv_pod, p_conv_win,
        volatility=V, target_round=frame.round,
    )
    p_final_pod, p_final_win = renormalize_probabilities(p_final_pod, p_final_win)

    new_ranks = rerank_with_probabilistic(anchor, p_final_pod, top_n=PROBABILISTIC_TOP_N)

    _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
        "drivers": drivers_in_frame,
        "p_win": p_final_win,
        "p_podium": p_final_pod,
        "volatility": float(V),
        "fallback": False,
        "regime": regime.value,
    }
    return new_ranks


def _compute_moe_expert_streams(
    p_elite_pod: np.ndarray,
    p_elite_win: np.ndarray,
    p_conv_pod: np.ndarray,
    p_conv_win: np.ndarray,
    volatility: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Stack the five experts into (K, n_drivers) probability matrices.

    Expert order matches ``models.moe_gate.DEFAULT_EXPERT_NAMES``:
    0 = elite_head, 1 = early_fusion, 2 = mid_fusion, 3 = late_fusion,
    4 = probabilistic_v_for_elite.

    NOTE: experts 3 and 4 are mathematically identical (both
    ``V·pe + (1-V)·pc``). They are kept as separate streams for fidelity
    to the Phase 6 spec; the gate will learn to suppress the redundant
    one via L2.
    """
    v = float(np.clip(volatility, 0.0, 1.0))
    # Expert 0: elite_head — pure pe
    e0_pod = p_elite_pod
    e0_win = p_elite_win
    # Expert 1: early_fusion
    e1_pod = early_fusion(p_elite_pod, p_conv_pod, v)
    e1_win = early_fusion(p_elite_win, p_conv_win, v)
    # Expert 2: mid_fusion
    e2_pod = mid_fusion(p_elite_pod, p_conv_pod, v)
    e2_win = mid_fusion(p_elite_win, p_conv_win, v)
    # Expert 3: late_fusion
    e3_pod = late_fusion(p_elite_pod, p_conv_pod, v)
    e3_win = late_fusion(p_elite_win, p_conv_win, v)
    # Expert 4: probabilistic_v_for_elite (identical to late_fusion)
    e4_pod = e3_pod
    e4_win = e3_win
    expert_pod = np.vstack([e0_pod, e1_pod, e2_pod, e3_pod, e4_pod])
    expert_win = np.vstack([e0_win, e1_win, e2_win, e3_win, e4_win])
    return expert_pod, expert_win


def _gate_features_for_frame(
    frame: RoundFrame,
    prior: list[RoundFrame],
    volatility: float,
) -> np.ndarray:
    """Build the per-round gate input vector — leak-safe by construction."""
    df = frame.df
    lap_times = df["predicted_lap_time"].to_numpy(dtype=float)
    qualifying_dispersion = float(
        np.std(lap_times) / max(1e-9, np.mean(lap_times))
    )
    # mean_maturity: build the maturity frame for THIS round's drivers using
    # only prior history; returns 0 when prior is empty.
    history_for_maturity = _build_history_for_probabilistic(prior)
    drivers_in_frame = df["driver"].tolist()
    if history_for_maturity.empty:
        mean_maturity = 0.0
    else:
        mat_frame = _moe_compute_maturity_frame(
            history_for_maturity,
            target_season=frame.season,
            target_round=frame.round,
            drivers=drivers_in_frame,
        )
        mean_maturity = float(mat_frame["maturity"].mean())
    archetype_qi = (
        frame.archetype.qualifying_importance if frame.archetype else 0.5
    )
    return build_gate_features(
        round_index=frame.round,
        volatility=volatility,
        mean_maturity=mean_maturity,
        qualifying_dispersion=qualifying_dispersion,
        archetype_qualifying_importance=archetype_qi,
    )


def predict_moe_routed_three_layer(
    frame: RoundFrame, prior: list[RoundFrame]
) -> np.ndarray:
    """Variant: moe_routed_three_layer — replace the rule-based regime
    router with a learned softmax gate (Phase 6).

    Pipeline:

    1. Layer 1 anchor ordering: ``elite_head_plus_hybrid``.
    2. Compute the five expert (P_win, P_podium) streams from pe + pc + V.
    3. Build a 5-dim feature vector for the current round.
    4. Fit a :class:`LearnedGate` on the prior-round training cache
       (rounds with already-recorded winner labels). Gradient is
       analytic; optimisation is L-BFGS-B with L2 regularisation.
    5. Predict softmax expert weights, fuse the five streams, renormalise,
       and re-rank the top-N by P(podium).
    6. Append this round's (features, expert streams, winner_idx) to
       the training cache so future test rounds can learn from it.

    Leak-safety:
    * Expert streams use only prior data.
    * Gate features use only prior data + current-round-frame quantities.
    * Gate training uses only prior rounds' winners.
    """
    global _MOE_FINAL_GATE
    anchor = predict_elite_head_plus_hybrid(frame, prior).astype(float)
    drivers_in_frame = frame.df["driver"].tolist()
    n = len(drivers_in_frame)
    variant_key = "moe_routed_three_layer"

    if len(prior) < PROBABILISTIC_MIN_TRAIN_ROUNDS:
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
            "moe_weights": None,
        }
        return anchor.astype(int)

    elite_probs = _elite_probs_for_frame(frame, prior)
    if elite_probs is None:
        _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
            "drivers": drivers_in_frame,
            "p_win": np.full(n, 1.0 / max(1, n), dtype=float),
            "p_podium": np.full(n, 3.0 / max(1, n), dtype=float),
            "volatility": float("nan"),
            "fallback": True,
            "moe_weights": None,
        }
        return anchor.astype(int)
    p_elite_pod, p_elite_win = elite_probs

    # Layer 2: volatility.
    vol_model = _train_volatility(prior)
    if vol_model is not None:
        history = _build_history_for_probabilistic(prior, frame)
        vol_feats = build_volatility_features(
            history, frame.season, frame.round, frame.gp_key, frame.archetype
        )
        V = vol_model.predict_one(vol_feats)
    else:
        V = 0.5

    # Layer 3: conversion heads.
    pod_head, win_head = _train_conversion_heads(prior)
    if pod_head is None or win_head is None:
        p_conv_pod = p_elite_pod.copy()
        p_conv_win = p_elite_win.copy()
    else:
        history = _build_history_for_probabilistic(prior, frame)
        target_feats = build_conversion_features(
            history, frame.season, frame.round, frame.gp_key
        )
        import warnings as _w
        with _w.catch_warnings():
            _w.filterwarnings(
                "ignore",
                message="Skipping features without any observed values",
                category=UserWarning,
            )
            raw_pod = pod_head.predict_proba(target_feats)
            raw_win = win_head.predict_proba(target_feats)
        drv_to_idx = {d: i for i, d in enumerate(target_feats["driver"].tolist())}
        p_conv_pod = np.array(
            [raw_pod[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )
        p_conv_win = np.array(
            [raw_win[drv_to_idx[d]] if d in drv_to_idx else 0.0 for d in drivers_in_frame]
        )

    # Build the K expert streams and per-round features.
    expert_pod, expert_win = _compute_moe_expert_streams(
        p_elite_pod, p_elite_win, p_conv_pod, p_conv_win, volatility=V
    )
    features = _gate_features_for_frame(frame, prior, V)

    # Fit the gate on whatever is in the training cache (all rounds STRICTLY
    # prior to the current call). Cache is populated by previous calls.
    gate = LearnedGate(
        n_experts=expert_pod.shape[0],
        n_features=features.shape[0],
        l2=_MOE_L2,
    )
    if len(_MOE_TRAIN_CACHE) >= _MOE_MIN_TRAIN_ROUNDS:
        gate.fit(_MOE_TRAIN_CACHE, max_iter=200)
        gate_weights = gate.predict_weights(features)
        moe_fallback = False
    else:
        # Insufficient training data — fall back to elite_head exactly.
        gate_weights = np.zeros(expert_pod.shape[0])
        gate_weights[0] = 1.0  # all weight on elite_head
        moe_fallback = True

    p_final_win, p_final_pod = fuse_with_gate(expert_win, expert_pod, gate_weights)
    p_final_pod, p_final_win = renormalize_probabilities(p_final_pod, p_final_win)
    new_ranks = rerank_with_probabilistic(anchor, p_final_pod, top_n=PROBABILISTIC_TOP_N)

    # Record the per-round outcome for the gate's future training.
    actual_pos = frame.df["actual"].to_numpy(dtype=float)
    # Driver finishing P1 = winner.
    finish_order = np.argsort(actual_pos, kind="stable")
    if len(finish_order) > 0:
        winner_idx = int(finish_order[0])
        _MOE_TRAIN_CACHE.append(
            TrainingExample(
                features=features,
                expert_p_win=expert_win,
                expert_p_pod=expert_pod,
                winner_idx=winner_idx,
                drivers=drivers_in_frame,
            )
        )

    _MOE_FINAL_GATE = gate if not moe_fallback else _MOE_FINAL_GATE
    _PROBABILISTIC_PROBS[(variant_key, frame.season, frame.round)] = {
        "drivers": drivers_in_frame,
        "p_win": p_final_win,
        "p_podium": p_final_pod,
        "volatility": float(V),
        "fallback": moe_fallback,
        "moe_weights": gate_weights.tolist(),
    }
    return new_ranks


VARIANTS: dict[str, callable] = {
    "baseline": predict_baseline,
    "per_circuit": predict_per_circuit,
    "hybrid_blend": predict_hybrid_blend,
    "per_circuit_plus_blend": predict_per_circuit_plus_blend,
    "elite_head": predict_elite_head,
    "elite_head_plus_hybrid": predict_elite_head_plus_hybrid,
    "probabilistic_three_layer": predict_probabilistic_three_layer,
    "temporally_robust_probabilistic": predict_temporally_robust_probabilistic,
    "regime_routed_three_layer": predict_regime_routed_three_layer,
    "regime_routed_with_weekend_static": predict_regime_routed_with_weekend_static,
    "regime_routed_with_weekend": predict_regime_routed_with_weekend,
    "moe_routed_three_layer": predict_moe_routed_three_layer,
}


def _scores_to_ranks(scores: np.ndarray) -> np.ndarray:
    """Convert a float score array (lower = better) into integer ranks 1..N
    with stable tie-breaking on the original order.
    """
    order = np.argsort(scores, kind="stable")
    ranks = np.empty_like(order, dtype=int)
    ranks[order] = np.arange(1, len(order) + 1)
    return ranks


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #


def _spearman(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 2:
        return None
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((a[i] - mean_a) ** 2 for i in range(n))
    var_b = sum((b[i] - mean_b) ** 2 for i in range(n))
    denom = math.sqrt(var_a * var_b)
    if denom == 0:
        return None
    return cov / denom


def _ndcg_at_k(
    predicted_order: list[str],
    actual_positions: dict[str, int],
    k: int = 5,
) -> float:
    def gain(driver: str) -> float:
        pos = actual_positions.get(driver)
        if pos is None or pos > k:
            return 0.0
        return float(k + 1 - pos)

    dcg = 0.0
    for i, drv in enumerate(predicted_order[:k]):
        dcg += gain(drv) / math.log2(i + 2)
    ideal_order = sorted(actual_positions.keys(), key=lambda d: actual_positions[d])
    idcg = 0.0
    for i, drv in enumerate(ideal_order[:k]):
        idcg += gain(drv) / math.log2(i + 2)
    return dcg / idcg if idcg > 0 else 0.0


def score_round(
    frame: RoundFrame,
    predicted: np.ndarray,
    probs: dict | None = None,
) -> dict:
    """Compute all per-round metrics for one variant on one round.

    ``probs`` is the optional per-round probability payload (from the
    ``probabilistic_three_layer`` side-channel). When present, log-loss
    and per-driver win-prob arrays are computed and stitched into the
    return dict.
    """
    df = frame.df
    actual = df["actual"].to_numpy(dtype=float)
    n = len(df)
    errors = np.abs(predicted - actual)
    sq_errors = (predicted - actual) ** 2

    drivers = df["driver"].tolist()
    pred_by_drv = dict(zip(drivers, predicted.tolist()))
    actual_by_drv = dict(zip(drivers, actual.tolist()))
    predicted_order = sorted(pred_by_drv, key=pred_by_drv.get)
    actual_order = sorted(actual_by_drv, key=actual_by_drv.get)

    predicted_top3 = predicted_order[:3]
    actual_top3 = actual_order[:3]

    out = {
        "season": frame.season,
        "round": frame.round,
        "gp_key": frame.gp_key,
        "archetype": frame.archetype.archetype if frame.archetype else None,
        "n": n,
        "mae": float(np.mean(errors)),
        "rmse": float(math.sqrt(np.mean(sq_errors))),
        "spearman": _spearman(predicted.tolist(), actual.tolist()),
        "ndcg_at_5": _ndcg_at_k(predicted_order, {k: int(v) for k, v in actual_by_drv.items()}, k=5),
        "podium_hits": int(len(set(predicted_top3) & set(actual_top3))),
        "winner_hit": bool(predicted_order[0] == actual_order[0]),
        "within_3": int(np.sum(errors <= 3)),
        "within_5": int(np.sum(errors <= 5)),
    }

    if probs is not None:
        # Build per-driver alignment between probs['drivers'] and frame.df['driver'].
        drv_order = probs.get("drivers", drivers)
        p_win = np.asarray(probs.get("p_win", []), dtype=float)
        p_pod = np.asarray(probs.get("p_podium", []), dtype=float)
        if len(p_win) == n and len(p_pod) == n:
            # Determine the actual winner index in drv_order.
            actual_winner_drv = actual_order[0]
            try:
                winner_idx = drv_order.index(actual_winner_drv)
            except ValueError:
                winner_idx = None
            if winner_idx is not None:
                out["winner_log_loss"] = winner_log_loss(p_win, winner_idx)
            else:
                out["winner_log_loss"] = float("nan")

            # Podium mask aligned to drv_order.
            actual_top3_set = set(actual_top3)
            mask = np.array(
                [1.0 if d in actual_top3_set else 0.0 for d in drv_order],
                dtype=float,
            )
            out["podium_log_loss"] = podium_log_loss(p_pod, mask)
            # Also stash the raw probability arrays so the aggregate can
            # build a cross-round calibration surface.
            out["_p_win"] = p_win.tolist()
            out["_p_pod"] = p_pod.tolist()
            out["_drivers"] = list(drv_order)
            out["_actual_winner"] = actual_winner_drv
            out["_actual_top3"] = list(actual_top3)
            out["volatility"] = probs.get("volatility")
            out["probabilistic_fallback"] = bool(probs.get("fallback", False))
    return out


def aggregate(round_results: list[dict]) -> dict:
    if not round_results:
        return {"rounds": 0}
    n_drivers_total = sum(r["n"] for r in round_results)
    spearmans = [r["spearman"] for r in round_results if r["spearman"] is not None]
    agg = {
        "rounds": len(round_results),
        "mae": float(round(statistics.mean(r["mae"] for r in round_results), 4)),
        "rmse": float(round(statistics.mean(r["rmse"] for r in round_results), 4)),
        "spearman": float(round(statistics.mean(spearmans), 4)) if spearmans else None,
        "ndcg_at_5": float(round(statistics.mean(r["ndcg_at_5"] for r in round_results), 4)),
        "podium_hit_rate": float(
            round(sum(r["podium_hits"] for r in round_results) / (3 * len(round_results)), 4)
        ),
        "winner_hit_rate": float(
            round(sum(1 for r in round_results if r["winner_hit"]) / len(round_results), 4)
        ),
        "within_3_rate": float(
            round(sum(r["within_3"] for r in round_results) / n_drivers_total, 4)
        ),
        "within_5_rate": float(
            round(sum(r["within_5"] for r in round_results) / n_drivers_total, 4)
        ),
    }
    # Probability-based metrics (only present when the variant ships probs).
    win_losses = [r["winner_log_loss"] for r in round_results if "winner_log_loss" in r and np.isfinite(r.get("winner_log_loss", float("nan")))]
    pod_losses = [r["podium_log_loss"] for r in round_results if "podium_log_loss" in r and np.isfinite(r.get("podium_log_loss", float("nan")))]
    if win_losses:
        agg["winner_log_loss"] = float(round(statistics.mean(win_losses), 4))
    if pod_losses:
        agg["podium_log_loss"] = float(round(statistics.mean(pod_losses), 4))

    # Calibration error: pool all (P_win, is_winner) across rounds.
    pooled_p: list[float] = []
    pooled_y: list[float] = []
    for r in round_results:
        if "_p_win" not in r or "_drivers" not in r or "_actual_winner" not in r:
            continue
        for drv, p in zip(r["_drivers"], r["_p_win"]):
            pooled_p.append(float(p))
            pooled_y.append(1.0 if drv == r["_actual_winner"] else 0.0)
    if pooled_p:
        agg["winner_calibration_error"] = float(
            round(
                calibration_error_10_bin(
                    np.asarray(pooled_p), np.asarray(pooled_y), n_bins=10
                ),
                4,
            )
        )
    return agg


# --------------------------------------------------------------------------- #
# Phase-segmented breakdown (Phase 4)
# --------------------------------------------------------------------------- #


PHASE_DEFINITIONS: list[tuple[str, range]] = [
    ("cold_start", range(1, 9)),   # rounds 1–8
    ("mid_season", range(9, 17)),  # rounds 9–16
    ("late_season", range(17, 30)),  # rounds 17+
]


def phase_breakdown(round_results: list[dict]) -> dict:
    """Split round-level metrics into cold/mid/late buckets and aggregate each.

    Returns a dict keyed by phase label whose values are the standard
    aggregate dict (same shape as :func:`aggregate` output).
    """
    out: dict[str, dict] = {}
    for label, rng in PHASE_DEFINITIONS:
        subset = [r for r in round_results if r["round"] in rng]
        out[label] = aggregate(subset)
    return out


# --------------------------------------------------------------------------- #
# Calibration reliability (Deliverable 4)
# --------------------------------------------------------------------------- #


def calibration_reliability(frames: list[RoundFrame], n_bins: int = 10) -> list[dict]:
    """Win-probability reliability buckets from the 2024+2025 backtest.

    Builds a synthetic P(win) per driver per round from the predicted
    finishing position using a Plackett-Luce-style strength on
    1/predicted_position (sums to ~1 across the field). For each
    decile of the predicted P(win), report the empirical fraction of
    drivers who actually won.

    This is NOT the live isotonic calibrator's reliability surface — that
    would require the actual probability outputs from each historical
    round, which are not stored in the DB. It IS a coarse "are our
    rank-derived win probabilities calibrated?" check.
    """
    bucket_pred: list[list[float]] = [[] for _ in range(n_bins)]
    bucket_obs: list[list[int]] = [[] for _ in range(n_bins)]

    for f in frames:
        df = f.df
        # Strength: lower predicted_position = higher strength
        s = 1.0 / df["predicted"].to_numpy(dtype=float)
        s = s / s.sum() if s.sum() > 0 else s
        actuals = df["actual"].to_numpy(dtype=int)
        for prob, actual_pos in zip(s, actuals):
            b = min(n_bins - 1, max(0, int(prob * n_bins)))
            bucket_pred[b].append(float(prob))
            bucket_obs[b].append(1 if actual_pos == 1 else 0)

    out: list[dict] = []
    for i in range(n_bins):
        if not bucket_pred[i]:
            continue
        out.append(
            {
                "bucket": i,
                "predicted_lo": float(round(i / n_bins, 3)),
                "predicted_hi": float(round((i + 1) / n_bins, 3)),
                "samples": len(bucket_pred[i]),
                "mean_predicted": float(round(statistics.mean(bucket_pred[i]), 4)),
                "empirical_win_rate": float(round(statistics.mean(bucket_obs[i]), 4)),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


def run_benchmark(
    variants: Sequence[str], seasons: Sequence[int]
) -> dict:
    frames = load_seasons(seasons)
    if not frames:
        raise SystemExit(f"no rounds found for seasons {seasons}")

    # Phase 6 — reset MoE training cache so back-to-back invocations don't
    # leak state from a previous run into the next.
    global _MOE_TRAIN_CACHE, _MOE_FINAL_GATE
    _MOE_TRAIN_CACHE = []
    _MOE_FINAL_GATE = None
    _PROBABILISTIC_PROBS.clear()

    # Leak-protect: for each frame's prior set, assert all prior tuples are
    # strictly before (season, round).
    frames_sorted = sorted(frames, key=lambda f: (f.season, f.round))

    results: dict[str, list[dict]] = {v: [] for v in variants}

    for i, frame in enumerate(frames_sorted):
        prior = frames_sorted[:i]
        # Strict leakage assertion: nothing at-or-after the target round.
        prior_rows = [
            {"season": p.season, "round": p.round} for p in prior
        ]
        assert_seasons_prior_only(
            prior_rows,
            current_season=frame.season,
            current_round=frame.round,
            label=f"benchmark prior for ({frame.season},{frame.round})",
        )

        for variant in variants:
            fn = VARIANTS[variant]
            predicted = fn(frame, prior)
            probs = None
            if variant in (
                "probabilistic_three_layer",
                "temporally_robust_probabilistic",
                "regime_routed_three_layer",
                "regime_routed_with_weekend_static",
                "regime_routed_with_weekend",
                "moe_routed_three_layer",
            ):
                probs = _PROBABILISTIC_PROBS.get(
                    (variant, frame.season, frame.round)
                )
            score = score_round(frame, predicted, probs=probs)
            score["variant"] = variant
            results[variant].append(score)

    # Train + persist final-state artifacts (volatility + conversion heads)
    # on the FULL prior set for production wiring. We train on all 2024 +
    # 2025 rounds (treating them as prior for a hypothetical next round).
    if "probabilistic_three_layer" in variants:
        try:
            _persist_probabilistic_artifacts(frames_sorted)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"warning: could not persist probabilistic artifacts: {exc}")

    payload: dict = {
        "seasons": list(seasons),
        "variants": list(variants),
        "perVariant": {},
        "calibrationReliability": calibration_reliability(frames_sorted),
    }

    # Phase 6 — surface the learned gate state + mean expert weights across
    # the backtest so the markdown can show what the gate actually picked.
    if "moe_routed_three_layer" in variants:
        # Mean weights per expert across all rounds where the gate was not
        # in fallback mode.
        weights_by_round: list[list[float]] = []
        for (vk, _s, _r), probs in _PROBABILISTIC_PROBS.items():
            if vk != "moe_routed_three_layer":
                continue
            w = probs.get("moe_weights")
            if w is not None and not probs.get("fallback"):
                weights_by_round.append(list(w))
        if weights_by_round:
            arr = np.array(weights_by_round, dtype=float)
            mean_weights = arr.mean(axis=0).tolist()
        else:
            mean_weights = [float("nan")] * len(DEFAULT_EXPERT_NAMES)

        # Fit a final-state gate on the FULL cache for production-readiness
        # diagnostics (the gate that would be deployed for the next round).
        final_gate = LearnedGate(
            n_experts=len(DEFAULT_EXPERT_NAMES),
            n_features=len(DEFAULT_FEATURE_NAMES),
            l2=_MOE_L2,
        )
        if len(_MOE_TRAIN_CACHE) >= _MOE_MIN_TRAIN_ROUNDS:
            final_gate.fit(_MOE_TRAIN_CACHE, max_iter=400)
        payload["moeLearned"] = {
            "expert_names": list(DEFAULT_EXPERT_NAMES),
            "feature_names": list(DEFAULT_FEATURE_NAMES),
            "mean_weights": mean_weights,
            "W": final_gate.W.tolist() if final_gate.is_fitted else None,
            "b": final_gate.b.tolist() if final_gate.is_fitted else None,
            "n_train_rounds": len(_MOE_TRAIN_CACHE),
            "l2": _MOE_L2,
        }
    for variant in variants:
        var_rounds = results[variant]
        per_season: dict[int, list[dict]] = defaultdict(list)
        for r in var_rounds:
            per_season[r["season"]].append(r)
        # Strip per-round probability arrays (large) before JSON serialization;
        # they were only needed for the aggregate's pooled calibration calc.
        clean_rounds = [_strip_internal_keys(r) for r in var_rounds]
        clean_per_season = {
            season: [_strip_internal_keys(r) for r in rs]
            for season, rs in per_season.items()
        }
        payload["perVariant"][variant] = {
            "aggregate": aggregate(var_rounds),
            "phaseBreakdown": phase_breakdown(var_rounds),
            "perSeason": {
                season: {
                    "aggregate": aggregate(rounds),
                    "phaseBreakdown": phase_breakdown(rounds),
                    "rounds": clean_per_season[season],
                }
                for season, rounds in sorted(per_season.items())
            },
        }
        # Replace per-variant rounds with cleaned versions (drops _p_win etc.)
        for season in payload["perVariant"][variant]["perSeason"]:
            payload["perVariant"][variant]["perSeason"][season]["rounds"] = (
                clean_per_season[season]
            )
        _ = clean_rounds  # noqa: F841 (kept for symmetry / potential debug)
    return payload


_INTERNAL_KEYS = ("_p_win", "_p_pod", "_drivers", "_actual_winner", "_actual_top3")


def _strip_internal_keys(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in _INTERNAL_KEYS}


def _persist_probabilistic_artifacts(frames_sorted: list[RoundFrame]) -> None:
    """Train and save the volatility + conversion heads on the full
    2024+2025 corpus for the production-wiring recipe.

    Artifacts:
      * models/registry/volatility/volatility_model.joblib
      * models/registry/conversion/conversion_podium_head.joblib
      * models/registry/conversion/conversion_winner_head.joblib
    """
    if not frames_sorted:
        return
    from models.conversion_model import REGISTRY_DIR as CONV_DIR
    from models.volatility_model import REGISTRY_DIR as VOL_DIR

    # Volatility
    vol_model = _train_volatility(frames_sorted)
    if vol_model is not None:
        VOL_DIR.mkdir(parents=True, exist_ok=True)
        vol_model.save(VOL_DIR / "volatility_model.joblib")

    # Conversion
    pod_head, win_head = _train_conversion_heads(frames_sorted)
    if pod_head is not None and win_head is not None:
        CONV_DIR.mkdir(parents=True, exist_ok=True)
        pod_head.save(CONV_DIR / "conversion_podium_head.joblib")
        win_head.save(CONV_DIR / "conversion_winner_head.joblib")


# --------------------------------------------------------------------------- #
# Compare → markdown
# --------------------------------------------------------------------------- #


def _format_metric(val) -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def _format_pct(val) -> str:
    if val is None:
        return "—"
    return f"{val * 100:.1f}%"


def promotion_verdict(
    baseline_agg: dict, candidate_agg: dict
) -> tuple[bool, str]:
    """Promote if candidate beats baseline by ≥2% on MAE AND ≥5pp on podium-hit
    rate AND does not regress any other metric by ≥10%."""
    if not baseline_agg or not candidate_agg:
        return False, "insufficient data"

    b_mae = baseline_agg["mae"]
    c_mae = candidate_agg["mae"]
    mae_improvement = (b_mae - c_mae) / b_mae if b_mae > 0 else 0.0

    b_pod = baseline_agg["podium_hit_rate"]
    c_pod = candidate_agg["podium_hit_rate"]
    pod_improvement_pp = c_pod - b_pod

    reasons: list[str] = []
    promote = True
    if mae_improvement < 0.02:
        promote = False
        reasons.append(f"MAE improvement only {mae_improvement * 100:.1f}% (<2%)")
    if pod_improvement_pp < 0.05:
        promote = False
        reasons.append(
            f"podium-hit Δ only {pod_improvement_pp * 100:.1f}pp (<5pp)"
        )

    # Regression check on Spearman, NDCG@5, winner-hit-rate
    for metric in ("spearman", "ndcg_at_5", "winner_hit_rate"):
        b = baseline_agg.get(metric)
        c = candidate_agg.get(metric)
        if b is None or c is None:
            continue
        if b <= 0:
            continue
        regression = (b - c) / b
        if regression >= 0.10:
            promote = False
            reasons.append(
                f"{metric} regressed {regression * 100:.1f}% (≥10%)"
            )

    if promote:
        reasons.append(
            f"MAE Δ={mae_improvement * 100:.1f}%, podium-hit Δ={pod_improvement_pp * 100:.1f}pp, no ≥10% regressions"
        )
    return promote, "; ".join(reasons)


def _phase3_promotion_verdict(
    incumbent_agg: dict, candidate_agg: dict
) -> tuple[bool, str]:
    """Strict Phase-3 gate vs the incumbent ``elite_head_plus_hybrid``:

    * Required (at least one): winner-hit ≥ +2pp, OR podium-hit ≥ +2pp,
      OR winner-log-loss improves ≥ 5%.
    * Required: probability calibration error does not increase by more
      than 15%.
    * Forbidden: regress podium-hit by more than 2pp; regress winner-hit
      by more than 1pp; regress MAE by more than 5%.
    """
    if not incumbent_agg or not candidate_agg:
        return False, "insufficient data"

    reasons: list[str] = []
    # Required improvement (at least one)
    pod_delta_pp = candidate_agg["podium_hit_rate"] - incumbent_agg["podium_hit_rate"]
    win_delta_pp = candidate_agg["winner_hit_rate"] - incumbent_agg["winner_hit_rate"]
    incumbent_wll = incumbent_agg.get("winner_log_loss")
    candidate_wll = candidate_agg.get("winner_log_loss")
    wll_imp = None
    if incumbent_wll and candidate_wll and incumbent_wll > 0:
        wll_imp = (incumbent_wll - candidate_wll) / incumbent_wll

    improvement_signals: list[str] = []
    if win_delta_pp >= 0.02:
        improvement_signals.append(f"winner-hit Δ={win_delta_pp*100:+.1f}pp (≥+2pp)")
    if pod_delta_pp >= 0.02:
        improvement_signals.append(f"podium-hit Δ={pod_delta_pp*100:+.1f}pp (≥+2pp)")
    if wll_imp is not None and wll_imp >= 0.05:
        improvement_signals.append(f"winner-log-loss Δ={wll_imp*100:+.1f}% (≥+5%)")

    promote = bool(improvement_signals)
    if not promote:
        reasons.append(
            f"no required improvement met (podium Δ={pod_delta_pp*100:+.1f}pp, "
            f"winner Δ={win_delta_pp*100:+.1f}pp, "
            f"winner-log-loss imp={'n/a' if wll_imp is None else f'{wll_imp*100:+.1f}%'})"
        )
    else:
        reasons.extend(improvement_signals)

    # Calibration mandate
    incumbent_ce = incumbent_agg.get("winner_calibration_error")
    candidate_ce = candidate_agg.get("winner_calibration_error")
    if incumbent_ce is not None and candidate_ce is not None and incumbent_ce > 0:
        ce_increase = (candidate_ce - incumbent_ce) / incumbent_ce
        if ce_increase > 0.15:
            promote = False
            reasons.append(
                f"calibration error increased {ce_increase*100:+.1f}% (>+15% blocked)"
            )
        else:
            reasons.append(f"calibration Δ={ce_increase*100:+.1f}% (within +15%)")

    # Forbidden regressions
    if pod_delta_pp < -0.02:
        promote = False
        reasons.append(f"podium-hit regressed {pod_delta_pp*100:+.1f}pp (>2pp drop)")
    if win_delta_pp < -0.01:
        promote = False
        reasons.append(f"winner-hit regressed {win_delta_pp*100:+.1f}pp (>1pp drop)")
    mae_increase = (candidate_agg["mae"] - incumbent_agg["mae"]) / incumbent_agg["mae"]
    if mae_increase > 0.05:
        promote = False
        reasons.append(f"MAE regressed {mae_increase*100:+.1f}% (>5%)")

    return promote, "; ".join(reasons)


def _phase4_promotion_verdict(
    incumbent_per_variant: dict,
    candidate_per_variant: dict,
) -> tuple[bool, str]:
    """Phase 4 gate for ``temporally_robust_probabilistic`` vs the in-production
    incumbent ``elite_head_plus_hybrid``.

    Required (at least one):
      * winner-hit improves ≥ +1pp
      * podium-hit improves ≥ +2pp aggregate

    AND no season regresses on winner-hit by more than 1pp.

    Required (calibration mandate): winner_calibration_error ≤ 0.05 (when present).

    Required (cold-start mandate): cold-start regime (rounds 1–8) winner-hit
    does NOT regress vs incumbent by more than 1pp.

    Forbidden: aggregate MAE regresses by more than 5%.
    """
    incumbent_agg = incumbent_per_variant.get("aggregate") or {}
    candidate_agg = candidate_per_variant.get("aggregate") or {}
    if not incumbent_agg or not candidate_agg:
        return False, "insufficient data"

    reasons: list[str] = []

    pod_delta_pp = (
        candidate_agg.get("podium_hit_rate", 0.0)
        - incumbent_agg.get("podium_hit_rate", 0.0)
    )
    win_delta_pp = (
        candidate_agg.get("winner_hit_rate", 0.0)
        - incumbent_agg.get("winner_hit_rate", 0.0)
    )

    improvement_signals: list[str] = []
    if win_delta_pp >= 0.01:
        improvement_signals.append(
            f"winner-hit Δ={win_delta_pp*100:+.1f}pp (≥+1pp)"
        )
    if pod_delta_pp >= 0.02:
        improvement_signals.append(
            f"podium-hit Δ={pod_delta_pp*100:+.1f}pp (≥+2pp)"
        )

    promote = bool(improvement_signals)
    if not promote:
        reasons.append(
            f"no required improvement met (podium Δ={pod_delta_pp*100:+.1f}pp, "
            f"winner Δ={win_delta_pp*100:+.1f}pp)"
        )
    else:
        reasons.extend(improvement_signals)

    # Per-season winner-hit regression check (no season may regress > 1pp).
    inc_seasons = incumbent_per_variant.get("perSeason") or {}
    cand_seasons = candidate_per_variant.get("perSeason") or {}
    for season_key in sorted(set(inc_seasons) | set(cand_seasons)):
        inc_block = inc_seasons.get(season_key) or {}
        cand_block = cand_seasons.get(season_key) or {}
        inc_win = (inc_block.get("aggregate") or {}).get("winner_hit_rate")
        cand_win = (cand_block.get("aggregate") or {}).get("winner_hit_rate")
        if inc_win is None or cand_win is None:
            continue
        season_delta = cand_win - inc_win
        if season_delta < -0.01:
            promote = False
            reasons.append(
                f"season {season_key} winner-hit regressed "
                f"{season_delta*100:+.1f}pp (>1pp drop)"
            )

    # Cold-start regime check.
    inc_phase = (incumbent_per_variant.get("phaseBreakdown") or {}).get("cold_start") or {}
    cand_phase = (candidate_per_variant.get("phaseBreakdown") or {}).get("cold_start") or {}
    if inc_phase and cand_phase:
        cold_win_inc = inc_phase.get("winner_hit_rate")
        cold_win_cand = cand_phase.get("winner_hit_rate")
        if cold_win_inc is not None and cold_win_cand is not None:
            cold_delta = cold_win_cand - cold_win_inc
            if cold_delta < -0.01:
                promote = False
                reasons.append(
                    f"cold-start winner-hit regressed {cold_delta*100:+.1f}pp (>1pp)"
                )
            else:
                reasons.append(
                    f"cold-start winner-hit Δ={cold_delta*100:+.1f}pp"
                )

    # Calibration mandate.
    cand_ce = candidate_agg.get("winner_calibration_error")
    if cand_ce is not None and cand_ce > 0.05:
        promote = False
        reasons.append(
            f"calibration error {cand_ce:.4f} > 0.05 (mandate violated)"
        )

    # MAE regression check.
    if incumbent_agg.get("mae", 0) > 0:
        mae_increase = (
            candidate_agg.get("mae", 0) - incumbent_agg["mae"]
        ) / incumbent_agg["mae"]
        if mae_increase > 0.05:
            promote = False
            reasons.append(f"MAE regressed {mae_increase*100:+.1f}% (>5%)")

    return promote, "; ".join(reasons)


def _phase5_promotion_verdict(
    incumbent_per_variant: dict,
    candidate_per_variant: dict,
) -> tuple[bool, str]:
    """Phase 5 gate for ``regime_routed_three_layer`` vs in-production
    incumbent ``elite_head_plus_hybrid``.

    Per the brief, this is a structural fix and must satisfy ALL of:

    * Mid-season winner-hit does NOT regress vs incumbent by more than 2pp
      (i.e., the Phase-4 mid-collapse is fixed)
    * Cold-start winner-hit does NOT regress vs incumbent by more than 1pp
      (preserves the Phase-4 cold-start improvement direction)
    * Late-season performance is not degraded by more than 3pp on winner-hit
    * Aggregate winner-hit ≥ incumbent - 1pp (stabilises or improves)
    * Aggregate MAE does NOT regress by more than 5%
    """
    incumbent_agg = incumbent_per_variant.get("aggregate") or {}
    candidate_agg = candidate_per_variant.get("aggregate") or {}
    if not incumbent_agg or not candidate_agg:
        return False, "insufficient data"

    inc_pb = incumbent_per_variant.get("phaseBreakdown") or {}
    cand_pb = candidate_per_variant.get("phaseBreakdown") or {}

    def _phase_winner(pb: dict, key: str) -> float | None:
        block = pb.get(key) or {}
        return block.get("winner_hit_rate")

    reasons: list[str] = []
    promote = True

    # Aggregate winner-hit ≥ incumbent - 1pp.
    agg_win_delta = (
        candidate_agg.get("winner_hit_rate", 0.0)
        - incumbent_agg.get("winner_hit_rate", 0.0)
    )
    if agg_win_delta < -0.01:
        promote = False
        reasons.append(f"aggregate winner-hit regressed {agg_win_delta*100:+.1f}pp (>1pp)")
    else:
        reasons.append(f"aggregate winner-hit Δ={agg_win_delta*100:+.1f}pp")

    # Cold-start winner-hit Δ ≥ -1pp.
    cs_inc = _phase_winner(inc_pb, "cold_start")
    cs_cand = _phase_winner(cand_pb, "cold_start")
    if cs_inc is not None and cs_cand is not None:
        cs_delta = cs_cand - cs_inc
        if cs_delta < -0.01:
            promote = False
            reasons.append(f"cold-start winner-hit regressed {cs_delta*100:+.1f}pp")
        else:
            reasons.append(f"cold-start winner-hit Δ={cs_delta*100:+.1f}pp")

    # Mid-season winner-hit Δ ≥ -2pp (the Phase-4 failure must be fixed).
    ms_inc = _phase_winner(inc_pb, "mid_season")
    ms_cand = _phase_winner(cand_pb, "mid_season")
    if ms_inc is not None and ms_cand is not None:
        ms_delta = ms_cand - ms_inc
        if ms_delta < -0.02:
            promote = False
            reasons.append(
                f"mid-season winner-hit regressed {ms_delta*100:+.1f}pp (>2pp) — "
                "Phase-4 collapse NOT fixed"
            )
        else:
            reasons.append(f"mid-season winner-hit Δ={ms_delta*100:+.1f}pp")

    # Late-season winner-hit Δ ≥ -3pp.
    ls_inc = _phase_winner(inc_pb, "late_season")
    ls_cand = _phase_winner(cand_pb, "late_season")
    if ls_inc is not None and ls_cand is not None:
        ls_delta = ls_cand - ls_inc
        if ls_delta < -0.03:
            promote = False
            reasons.append(f"late-season winner-hit regressed {ls_delta*100:+.1f}pp (>3pp)")
        else:
            reasons.append(f"late-season winner-hit Δ={ls_delta*100:+.1f}pp")

    # MAE regression.
    if incumbent_agg.get("mae", 0) > 0:
        mae_increase = (
            candidate_agg.get("mae", 0) - incumbent_agg["mae"]
        ) / incumbent_agg["mae"]
        if mae_increase > 0.05:
            promote = False
            reasons.append(f"MAE regressed {mae_increase*100:+.1f}% (>5%)")

    return promote, "; ".join(reasons)


def _phase6_promotion_verdict(
    incumbent_per_variant: dict,
    candidate_per_variant: dict,
) -> tuple[bool, str]:
    """Phase 6 gate for ``moe_routed_three_layer`` vs ``regime_routed_three_layer``
    (Phase-5 incumbent) and ``elite_head_plus_hybrid`` (production incumbent).

    The candidate is compared against the supplied incumbent. Calling code
    runs the verdict against both rivals separately and the markdown
    surfaces both verdicts.

    Required: aggregate winner-hit ≥ incumbent (NOT regressed by more than 1pp).
    Required: cold-start winner-hit ≥ incumbent - 1pp.
    Required: mid-season winner-hit ≥ incumbent - 2pp.
    Required: aggregate calibration error ≤ 0.05 when present.
    Forbidden: aggregate MAE regressed by more than 5%.
    """
    incumbent_agg = incumbent_per_variant.get("aggregate") or {}
    candidate_agg = candidate_per_variant.get("aggregate") or {}
    if not incumbent_agg or not candidate_agg:
        return False, "insufficient data"

    inc_pb = incumbent_per_variant.get("phaseBreakdown") or {}
    cand_pb = candidate_per_variant.get("phaseBreakdown") or {}

    def _phase_winner(pb: dict, key: str) -> float | None:
        block = pb.get(key) or {}
        return block.get("winner_hit_rate")

    reasons: list[str] = []
    promote = True

    agg_win_delta = (
        candidate_agg.get("winner_hit_rate", 0.0)
        - incumbent_agg.get("winner_hit_rate", 0.0)
    )
    if agg_win_delta < -0.01:
        promote = False
        reasons.append(f"aggregate winner-hit regressed {agg_win_delta*100:+.1f}pp (>1pp)")
    else:
        reasons.append(f"aggregate winner-hit Δ={agg_win_delta*100:+.1f}pp")

    cs_inc = _phase_winner(inc_pb, "cold_start")
    cs_cand = _phase_winner(cand_pb, "cold_start")
    if cs_inc is not None and cs_cand is not None:
        cs_delta = cs_cand - cs_inc
        if cs_delta < -0.01:
            promote = False
            reasons.append(f"cold-start winner-hit regressed {cs_delta*100:+.1f}pp")
        else:
            reasons.append(f"cold-start winner-hit Δ={cs_delta*100:+.1f}pp")

    ms_inc = _phase_winner(inc_pb, "mid_season")
    ms_cand = _phase_winner(cand_pb, "mid_season")
    if ms_inc is not None and ms_cand is not None:
        ms_delta = ms_cand - ms_inc
        if ms_delta < -0.02:
            promote = False
            reasons.append(f"mid-season winner-hit regressed {ms_delta*100:+.1f}pp (>2pp)")
        else:
            reasons.append(f"mid-season winner-hit Δ={ms_delta*100:+.1f}pp")

    ls_inc = _phase_winner(inc_pb, "late_season")
    ls_cand = _phase_winner(cand_pb, "late_season")
    if ls_inc is not None and ls_cand is not None:
        ls_delta = ls_cand - ls_inc
        reasons.append(f"late-season winner-hit Δ={ls_delta*100:+.1f}pp")

    cand_ce = candidate_agg.get("winner_calibration_error")
    if cand_ce is not None and cand_ce > 0.05:
        promote = False
        reasons.append(f"calibration error {cand_ce:.4f} > 0.05 (mandate)")
    elif cand_ce is not None:
        reasons.append(f"calibration error {cand_ce:.4f}")

    if incumbent_agg.get("mae", 0) > 0:
        mae_increase = (
            candidate_agg.get("mae", 0) - incumbent_agg["mae"]
        ) / incumbent_agg["mae"]
        if mae_increase > 0.05:
            promote = False
            reasons.append(f"MAE regressed {mae_increase*100:+.1f}% (>5%)")

    return promote, "; ".join(reasons)


def write_markdown_report(payload: dict, output: Path) -> None:
    lines: list[str] = []
    variants_in_payload = payload.get("variants", [])
    has_moe = "moe_routed_three_layer" in variants_in_payload
    has_regime = "regime_routed_three_layer" in variants_in_payload
    has_temporal = "temporally_robust_probabilistic" in variants_in_payload
    has_probabilistic = "probabilistic_three_layer" in variants_in_payload
    if has_moe:
        phase_label = "Phase 6 — Mixture-of-Experts Gating"
    elif has_regime:
        phase_label = "Phase 5 — Regime-Routed Architecture"
    elif has_temporal:
        phase_label = "Phase 4 — Temporal Robustness Layer"
    elif has_probabilistic:
        phase_label = "Phase 3 — 3-Layer Probabilistic Engine"
    else:
        phase_label = "Phase 1 — Real Numbers"
    lines.append(f"# Benchmark {phase_label}\n")
    lines.append(
        "_Auto-generated by ``benchmark_models.py compare``. Seasons "
        f"in scope: {payload['seasons']}._\n"
    )
    lines.append(
        "**Approximation disclosure** — the per-circuit and hybrid-blend "
        "variants run on a synth feature frame built from the DB rows "
        "(predicted_position + predicted_lap_time + archetype priors) rather "
        "than a full L1 retrain per round. See the APPROXIMATION NOTE blocks "
        "in `benchmark_models.py::predict_per_circuit` and "
        "`benchmark_models.py::predict_hybrid_blend` for the exact substitution. "
        "These are *signal-direction* benchmarks, not production wirings.\n"
    )

    variants = payload["variants"]

    # Phase 6 — MoE-routed headline + verdict against TWO rivals: the
    # in-production incumbent (elite_head_plus_hybrid) AND the Phase-5
    # candidate (regime_routed_three_layer).
    if has_moe and "elite_head_plus_hybrid" in variants:
        moe_full = payload["perVariant"]["moe_routed_three_layer"]
        prod_incumbent_full = payload["perVariant"]["elite_head_plus_hybrid"]
        prod_promote, prod_reason = _phase6_promotion_verdict(
            prod_incumbent_full, moe_full
        )
        lines.append("## Phase 6 verdict\n")
        verdict_prod = "PROMOTE" if prod_promote else "REJECT"
        lines.append(
            f"**{verdict_prod}** `moe_routed_three_layer` vs production incumbent "
            f"`elite_head_plus_hybrid`. _{prod_reason}_\n"
        )
        if "regime_routed_three_layer" in variants:
            phase5_full = payload["perVariant"]["regime_routed_three_layer"]
            phase5_promote, phase5_reason = _phase6_promotion_verdict(
                phase5_full, moe_full
            )
            verdict_phase5 = "PROMOTE" if phase5_promote else "REJECT"
            lines.append(
                f"**{verdict_phase5}** `moe_routed_three_layer` vs Phase-5 candidate "
                f"`regime_routed_three_layer`. _{phase5_reason}_\n"
            )

        moe_agg = moe_full["aggregate"]
        prod_agg = prod_incumbent_full["aggregate"]
        phase5_agg = (
            payload["perVariant"].get("regime_routed_three_layer", {}).get("aggregate")
            if "regime_routed_three_layer" in variants
            else None
        )

        lines.append("### Aggregate headline (2024 + 2025)\n")
        col_specs: list[tuple[str, dict]] = [
            ("elite_head_plus_hybrid", prod_agg),
        ]
        if phase5_agg is not None:
            col_specs.append(("regime_routed_three_layer", phase5_agg))
        col_specs.append(("moe_routed_three_layer", moe_agg))
        lines.append("| metric |" + "".join(f" {n} |" for n, _ in col_specs))
        lines.append("|---|" + "---:|" * len(col_specs))

        def _fmt(val, fmt) -> str:
            if val is None:
                return "—"
            if fmt == "pct":
                return f"{val*100:.2f}%"
            return f"{val:.4f}"

        for label, key, fmt in [
            ("MAE", "mae", "num"),
            ("podium-hit", "podium_hit_rate", "pct"),
            ("winner-hit", "winner_hit_rate", "pct"),
            ("winner-log-loss", "winner_log_loss", "num"),
            ("winner-calibration-error", "winner_calibration_error", "num"),
            ("within-3", "within_3_rate", "pct"),
            ("Spearman", "spearman", "num"),
        ]:
            row = f"| {label} |"
            for _, agg in col_specs:
                row += f" {_fmt(agg.get(key), fmt)} |"
            lines.append(row)
        lines.append("")

        # Per-regime breakdown vs prior incumbents.
        lines.append("### Regime breakdown (cold-start / mid / late)\n")
        regime_variants: list[str] = ["elite_head_plus_hybrid"]
        if "regime_routed_three_layer" in variants:
            regime_variants.append("regime_routed_three_layer")
        regime_variants.append("moe_routed_three_layer")

        for phase_label_key, _rng in PHASE_DEFINITIONS:
            pretty_phase = phase_label_key.replace("_", "-").title().replace("-", " ")
            lines.append(f"#### {pretty_phase} (rounds {_rng.start}–{_rng.stop - 1})\n")
            lines.append("| variant | n | MAE | podium-hit | winner-hit | within-3 |")
            lines.append("|---|---:|---:|---:|---:|---:|")
            for v in regime_variants:
                pb = payload["perVariant"][v].get("phaseBreakdown", {}).get(
                    phase_label_key, {}
                )
                if not pb or pb.get("rounds") == 0:
                    lines.append(f"| {v} | 0 | — | — | — | — |")
                    continue
                lines.append(
                    f"| {v} | {pb['rounds']} | {_format_metric(pb.get('mae'))} | "
                    f"{_format_pct(pb.get('podium_hit_rate'))} | "
                    f"{_format_pct(pb.get('winner_hit_rate'))} | "
                    f"{_format_pct(pb.get('within_3_rate'))} |"
                )
            lines.append("")

        # Learned gate diagnostics — what did the gate actually pick?
        learned = payload.get("moeLearned")
        if learned is not None:
            lines.append("### Learned gate diagnostics (final-state, after full backtest)\n")
            lines.append(
                "_The gate is re-fit at every test round on all strictly-prior cached "
                "examples. Below is the gate trained on the FULL 2024+2025 cache — i.e. "
                "what would be deployed for the next live round._\n"
            )
            lines.append("**Expert mean weights across the backtest:**\n")
            lines.append("| expert | mean weight |")
            lines.append("|---|---:|")
            for name, w in zip(learned["expert_names"], learned["mean_weights"]):
                lines.append(f"| {name} | {w:.4f} |")
            lines.append("")
            lines.append("**Final-state coefficient matrix (W ∈ R^(K×d)):**\n")
            lines.append(
                "| expert |" + "".join(f" {f} |" for f in learned["feature_names"]) + " bias |"
            )
            lines.append(
                "|---|" + "---:|" * (len(learned["feature_names"]) + 1)
            )
            for name, row, b in zip(
                learned["expert_names"], learned["W"], learned["b"]
            ):
                line = f"| {name} |"
                for v in row:
                    line += f" {v:+.3f} |"
                line += f" {b:+.3f} |"
                lines.append(line)
            lines.append("")
            lines.append(
                f"Training rounds used: {learned.get('n_train_rounds', '?')}. "
                f"L2 coefficient: {learned.get('l2', '?')}.\n"
            )

    # Phase 5 — regime-routed headline + verdict against in-production
    # incumbent ``elite_head_plus_hybrid``.
    if has_regime and "elite_head_plus_hybrid" in variants:
        incumbent_full = payload["perVariant"]["elite_head_plus_hybrid"]
        candidate_full = payload["perVariant"]["regime_routed_three_layer"]
        promote, reason = _phase5_promotion_verdict(incumbent_full, candidate_full)
        verdict = "PROMOTE" if promote else "REJECT"
        lines.append("## Phase 5 verdict\n")
        lines.append(
            f"**{verdict}** `regime_routed_three_layer` vs incumbent "
            f"`elite_head_plus_hybrid`. _{reason}_\n"
        )

        # Side-by-side headline (incumbent / Phase 3 / Phase 4 / Phase 5
        # when each is present).
        candidate_agg = candidate_full["aggregate"]
        incumbent_agg = incumbent_full["aggregate"]
        prob3_agg = (
            payload["perVariant"].get("probabilistic_three_layer", {}).get("aggregate")
            if "probabilistic_three_layer" in variants
            else None
        )
        temp_agg = (
            payload["perVariant"].get("temporally_robust_probabilistic", {}).get("aggregate")
            if "temporally_robust_probabilistic" in variants
            else None
        )

        lines.append("### Aggregate headline (2024 + 2025)\n")
        col_specs = [("elite_head_plus_hybrid", incumbent_agg)]
        if prob3_agg is not None:
            col_specs.append(("probabilistic_three_layer", prob3_agg))
        if temp_agg is not None:
            col_specs.append(("temporally_robust_probabilistic", temp_agg))
        col_specs.append(("regime_routed_three_layer", candidate_agg))

        header = "| metric |" + "".join(f" {n} |" for n, _ in col_specs)
        lines.append(header)
        lines.append("|---|" + "---:|" * len(col_specs))

        def _fmt(val, fmt) -> str:
            if val is None:
                return "—"
            if fmt == "pct":
                return f"{val*100:.2f}%"
            return f"{val:.4f}"

        for label, key, fmt in [
            ("MAE", "mae", "num"),
            ("podium-hit", "podium_hit_rate", "pct"),
            ("winner-hit", "winner_hit_rate", "pct"),
            ("winner-log-loss", "winner_log_loss", "num"),
            ("winner-calibration-error", "winner_calibration_error", "num"),
            ("within-3", "within_3_rate", "pct"),
            ("Spearman", "spearman", "num"),
        ]:
            row = f"| {label} |"
            for _, agg in col_specs:
                row += f" {_fmt(agg.get(key), fmt)} |"
            lines.append(row)
        lines.append("")

        # Per-regime breakdown — the headline test of the regime-routed
        # architecture.
        lines.append("### Regime breakdown (cold-start / mid / late)\n")
        regime_variants: list[str] = ["elite_head_plus_hybrid"]
        if "probabilistic_three_layer" in variants:
            regime_variants.append("probabilistic_three_layer")
        if "temporally_robust_probabilistic" in variants:
            regime_variants.append("temporally_robust_probabilistic")
        regime_variants.append("regime_routed_three_layer")

        for phase_label_key, _rng in PHASE_DEFINITIONS:
            pretty_phase = phase_label_key.replace("_", "-").title().replace("-", " ")
            lines.append(f"#### {pretty_phase} (rounds {_rng.start}–{_rng.stop - 1})\n")
            lines.append("| variant | n | MAE | podium-hit | winner-hit | within-3 |")
            lines.append("|---|---:|---:|---:|---:|---:|")
            for v in regime_variants:
                pb = payload["perVariant"][v].get("phaseBreakdown", {}).get(
                    phase_label_key, {}
                )
                if not pb or pb.get("rounds") == 0:
                    lines.append(f"| {v} | 0 | — | — | — | — |")
                    continue
                lines.append(
                    f"| {v} | {pb['rounds']} | {_format_metric(pb.get('mae'))} | "
                    f"{_format_pct(pb.get('podium_hit_rate'))} | "
                    f"{_format_pct(pb.get('winner_hit_rate'))} | "
                    f"{_format_pct(pb.get('within_3_rate'))} |"
                )
            lines.append("")

    # Phase 4 — temporal-robustness headline + verdict against in-production
    # incumbent ``elite_head_plus_hybrid``.
    if has_temporal and "elite_head_plus_hybrid" in variants:
        incumbent_full = payload["perVariant"]["elite_head_plus_hybrid"]
        candidate_full = payload["perVariant"]["temporally_robust_probabilistic"]
        promote, reason = _phase4_promotion_verdict(incumbent_full, candidate_full)
        verdict = "PROMOTE" if promote else "REJECT"
        lines.append("## Phase 4 verdict\n")
        lines.append(
            f"**{verdict}** `temporally_robust_probabilistic` vs incumbent "
            f"`elite_head_plus_hybrid`. _{reason}_\n"
        )
        # Headline aggregate numbers (vs incumbent).
        incumbent_agg = incumbent_full["aggregate"]
        candidate_agg = candidate_full["aggregate"]
        # Also pull probabilistic_three_layer if present, for context.
        prob3 = (
            payload["perVariant"].get("probabilistic_three_layer", {}).get("aggregate")
            if "probabilistic_three_layer" in variants
            else None
        )
        lines.append("### Aggregate headline (2024 + 2025)\n")
        if prob3 is not None:
            lines.append(
                "| metric | elite_head_plus_hybrid | probabilistic_three_layer | temporally_robust_probabilistic |"
            )
            lines.append("|---|---:|---:|---:|")
        else:
            lines.append(
                "| metric | elite_head_plus_hybrid | temporally_robust_probabilistic |"
            )
            lines.append("|---|---:|---:|")

        def _fmt(val, fmt) -> str:
            if val is None:
                return "—"
            if fmt == "pct":
                return f"{val*100:.2f}%"
            return f"{val:.4f}"

        for label, key, fmt in [
            ("MAE", "mae", "num"),
            ("podium-hit", "podium_hit_rate", "pct"),
            ("winner-hit", "winner_hit_rate", "pct"),
            ("winner-log-loss", "winner_log_loss", "num"),
            ("winner-calibration-error", "winner_calibration_error", "num"),
            ("within-3", "within_3_rate", "pct"),
            ("Spearman", "spearman", "num"),
        ]:
            row = f"| {label} | {_fmt(incumbent_agg.get(key), fmt)} |"
            if prob3 is not None:
                row += f" {_fmt(prob3.get(key), fmt)} |"
            row += f" {_fmt(candidate_agg.get(key), fmt)} |"
            lines.append(row)
        lines.append("")

        # Phase breakdown table — the headline test of the fix.
        lines.append("### Season-phase breakdown (cold-start / mid / late)\n")
        phase_variants = ["elite_head_plus_hybrid"]
        if "probabilistic_three_layer" in variants:
            phase_variants.append("probabilistic_three_layer")
        phase_variants.append("temporally_robust_probabilistic")

        for phase_label_key, _rng in PHASE_DEFINITIONS:
            pretty_phase = phase_label_key.replace("_", "-").title().replace(
                "-", " "
            )
            lines.append(f"#### {pretty_phase} (rounds {_rng.start}–{_rng.stop - 1})\n")
            lines.append("| variant | n | MAE | podium-hit | winner-hit | within-3 |")
            lines.append("|---|---:|---:|---:|---:|---:|")
            for v in phase_variants:
                pb = payload["perVariant"][v].get("phaseBreakdown", {}).get(
                    phase_label_key, {}
                )
                if not pb or pb.get("rounds") == 0:
                    lines.append(f"| {v} | 0 | — | — | — | — |")
                    continue
                lines.append(
                    f"| {v} | {pb['rounds']} | {_format_metric(pb.get('mae'))} | "
                    f"{_format_pct(pb.get('podium_hit_rate'))} | "
                    f"{_format_pct(pb.get('winner_hit_rate'))} | "
                    f"{_format_pct(pb.get('within_3_rate'))} |"
                )
            lines.append("")

    # Phase 3 — headline numbers + verdict against the in-production incumbent
    if has_probabilistic and "elite_head_plus_hybrid" in variants:
        incumbent = payload["perVariant"]["elite_head_plus_hybrid"]["aggregate"]
        candidate = payload["perVariant"]["probabilistic_three_layer"]["aggregate"]
        promote, reason = _phase3_promotion_verdict(incumbent, candidate)
        verdict = "PROMOTE" if promote else "REJECT"
        lines.append("## Phase 3 verdict\n")
        lines.append(
            f"**{verdict}** `probabilistic_three_layer` vs incumbent "
            f"`elite_head_plus_hybrid`. _{reason}_\n"
        )
        lines.append("### Headline numbers vs incumbent\n")
        lines.append(
            "| metric | elite_head_plus_hybrid | probabilistic_three_layer | Δ |"
        )
        lines.append("|---|---:|---:|---:|")

        def _row(label, key, fmt="num"):
            a = incumbent.get(key)
            b = candidate.get(key)
            if a is None and b is None:
                return None
            if fmt == "pct":
                a_s = f"{a*100:.2f}%" if isinstance(a, (int, float)) else "—"
                b_s = f"{b*100:.2f}%" if isinstance(b, (int, float)) else "—"
                delta = (
                    f"{(b - a)*100:+.2f}pp"
                    if isinstance(a, (int, float)) and isinstance(b, (int, float))
                    else "—"
                )
            else:
                a_s = f"{a:.4f}" if isinstance(a, (int, float)) else "—"
                b_s = f"{b:.4f}" if isinstance(b, (int, float)) else "—"
                delta = (
                    f"{b - a:+.4f}"
                    if isinstance(a, (int, float)) and isinstance(b, (int, float))
                    else "—"
                )
            return f"| {label} | {a_s} | {b_s} | {delta} |"

        for label, key, fmt in [
            ("MAE", "mae", "num"),
            ("podium-hit", "podium_hit_rate", "pct"),
            ("winner-hit", "winner_hit_rate", "pct"),
            ("winner-log-loss", "winner_log_loss", "num"),
            ("podium-log-loss", "podium_log_loss", "num"),
            ("winner-calibration-error", "winner_calibration_error", "num"),
            ("Spearman", "spearman", "num"),
            ("within-3", "within_3_rate", "pct"),
        ]:
            row = _row(label, key, fmt)
            if row:
                lines.append(row)
        lines.append("")

    # 1. Aggregate table
    lines.append("## Aggregate (across all seasons in scope)\n")
    lines.append(
        "| variant | rounds | MAE | RMSE | Spearman | NDCG@5 | podium-hit | winner-hit | within-3 | within-5 |"
    )
    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    for v in variants:
        a = payload["perVariant"][v]["aggregate"]
        lines.append(
            f"| {v} | {a['rounds']} | {_format_metric(a['mae'])} | "
            f"{_format_metric(a['rmse'])} | {_format_metric(a['spearman'])} | "
            f"{_format_metric(a['ndcg_at_5'])} | {_format_pct(a['podium_hit_rate'])} | "
            f"{_format_pct(a['winner_hit_rate'])} | {_format_pct(a['within_3_rate'])} | "
            f"{_format_pct(a['within_5_rate'])} |"
        )
    lines.append("")

    # 2. Per-season breakdown
    lines.append("## Per-season breakdown\n")
    for v in variants:
        lines.append(f"### {v}\n")
        lines.append("| season | rounds | MAE | Spearman | podium-hit | winner-hit |")
        lines.append("|---:|---:|---:|---:|---:|---:|")
        for season, block in payload["perVariant"][v]["perSeason"].items():
            a = block["aggregate"]
            lines.append(
                f"| {season} | {a['rounds']} | {_format_metric(a['mae'])} | "
                f"{_format_metric(a['spearman'])} | {_format_pct(a['podium_hit_rate'])} | "
                f"{_format_pct(a['winner_hit_rate'])} |"
            )
        lines.append("")

    # 3. Per-round delta vs baseline
    if "baseline" in variants:
        lines.append("## Per-round delta vs baseline (MAE)\n")
        baseline_rounds = {
            (r["season"], r["round"]): r
            for r in [
                rr
                for season_block in payload["perVariant"]["baseline"][
                    "perSeason"
                ].values()
                for rr in season_block["rounds"]
            ]
        }
        for v in variants:
            if v == "baseline":
                continue
            lines.append(f"### {v}\n")
            lines.append(
                "| season | round | gp | archetype | baseline MAE | "
                f"{v} MAE | Δ MAE | baseline pod | {v} pod |"
            )
            lines.append("|---:|---:|---|---|---:|---:|---:|---:|---:|")
            cand_rounds = [
                rr
                for season_block in payload["perVariant"][v]["perSeason"].values()
                for rr in season_block["rounds"]
            ]
            wins = 0
            losses = 0
            ties = 0
            for cr in cand_rounds:
                key = (cr["season"], cr["round"])
                br = baseline_rounds.get(key)
                if br is None:
                    continue
                delta = cr["mae"] - br["mae"]
                if delta < -0.05:
                    wins += 1
                elif delta > 0.05:
                    losses += 1
                else:
                    ties += 1
                lines.append(
                    f"| {cr['season']} | {cr['round']} | {cr['gp_key']} | "
                    f"{cr['archetype'] or '—'} | {br['mae']:.3f} | "
                    f"{cr['mae']:.3f} | {delta:+.3f} | "
                    f"{br['podium_hits']}/3 | {cr['podium_hits']}/3 |"
                )
            lines.append(
                f"\n**MAE rounds tally:** {wins} win, {ties} tie, {losses} loss vs baseline\n"
            )

    # 4. Promotion verdict
    lines.append("## Promotion verdict\n")
    if "baseline" not in variants:
        lines.append("_Baseline not in run — cannot verdict._\n")
    else:
        baseline_agg = payload["perVariant"]["baseline"]["aggregate"]
        promoted: list[str] = []
        for v in variants:
            if v == "baseline":
                continue
            cand_agg = payload["perVariant"][v]["aggregate"]
            promote, reason = promotion_verdict(baseline_agg, cand_agg)
            verdict = "PROMOTE" if promote else "DO NOT PROMOTE"
            lines.append(f"* **{v}** — {verdict}. _{reason}_")
            if promote:
                promoted.append(v)
        lines.append("")
        if not promoted:
            lines.append(
                "_No variant cleared the promotion gate (≥2% MAE improvement, "
                "≥5pp podium-hit improvement, no ≥10% regressions). Baseline "
                "stays in production._\n"
            )
        else:
            lines.append(
                f"_Headline recommendation: promote **{promoted[0]}** "
                "(first variant to clear all gates). Wire into "
                "`export_round_data` and re-benchmark next round._\n"
            )

    # 5. Calibration reliability
    lines.append("## Calibration reliability (Plackett-Luce-rank-derived P(win))\n")
    lines.append(
        "_This is a coarse rank-derived P(win) reliability surface, not the "
        "live isotonic calibrator's. The DB does not store historical "
        "probability outputs._\n"
    )
    lines.append(
        "| bucket | predicted range | samples | mean predicted | empirical win-rate |"
    )
    lines.append("|---:|---|---:|---:|---:|")
    for b in payload["calibrationReliability"]:
        lines.append(
            f"| {b['bucket']} | {b['predicted_lo']:.2f}-{b['predicted_hi']:.2f} | "
            f"{b['samples']} | {b['mean_predicted']:.4f} | "
            f"{b['empirical_win_rate']:.4f} |"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as fh:
        fh.write("\n".join(lines))


# --------------------------------------------------------------------------- #
# Export → website JSONs
# --------------------------------------------------------------------------- #


def write_website_exports(payload: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    variants = payload["variants"]

    # summary.json
    summary = {
        "seasons": payload["seasons"],
        "variants": variants,
        "aggregate": {
            v: payload["perVariant"][v]["aggregate"] for v in variants
        },
        "headlineVariant": None,
        "promotionVerdict": [],
        "calibrationReliability": payload["calibrationReliability"],
    }
    if "baseline" in variants:
        baseline_agg = payload["perVariant"]["baseline"]["aggregate"]
        best_v: str | None = None
        best_score: float = -1.0
        for v in variants:
            if v == "baseline":
                continue
            cand_agg = payload["perVariant"][v]["aggregate"]
            promote, reason = promotion_verdict(baseline_agg, cand_agg)
            summary["promotionVerdict"].append(
                {"variant": v, "promote": promote, "reason": reason}
            )
            mae_imp = (
                (baseline_agg["mae"] - cand_agg["mae"]) / baseline_agg["mae"]
                if baseline_agg["mae"] > 0
                else 0.0
            )
            if mae_imp > best_score:
                best_score = mae_imp
                best_v = v
        summary["headlineVariant"] = best_v
        summary["headlineMaeImprovement"] = float(round(best_score, 4))
    with (out_dir / "summary.json").open("w") as fh:
        json.dump(summary, fh, indent=2)

    # per_season.json
    per_season_payload: dict = {"variants": variants, "perSeason": {}}
    for v in variants:
        for season, block in payload["perVariant"][v]["perSeason"].items():
            per_season_payload["perSeason"].setdefault(str(season), {})[v] = block[
                "aggregate"
            ]
    with (out_dir / "per_season.json").open("w") as fh:
        json.dump(per_season_payload, fh, indent=2)

    # per_round.json (rolling-accuracy series)
    per_round_payload: dict = {"variants": variants, "rounds": []}
    keys: set = set()
    for v in variants:
        for season_block in payload["perVariant"][v]["perSeason"].values():
            for r in season_block["rounds"]:
                keys.add((r["season"], r["round"]))
    for season, round_ in sorted(keys):
        entry: dict = {"season": season, "round": round_}
        for v in variants:
            for season_block in payload["perVariant"][v]["perSeason"].values():
                for r in season_block["rounds"]:
                    if r["season"] == season and r["round"] == round_:
                        entry[v] = {
                            "mae": r["mae"],
                            "spearman": r["spearman"],
                            "ndcg_at_5": r["ndcg_at_5"],
                            "podium_hits": r["podium_hits"],
                            "winner_hit": r["winner_hit"],
                            "gp_key": r["gp_key"],
                            "archetype": r["archetype"],
                        }
                        break
        per_round_payload["rounds"].append(entry)
    with (out_dir / "per_round.json").open("w") as fh:
        json.dump(per_round_payload, fh, indent=2)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_variants(s: str) -> list[str]:
    out = [v.strip() for v in s.split(",") if v.strip()]
    for v in out:
        if v not in VARIANTS:
            raise SystemExit(
                f"unknown variant {v!r}; choose from {sorted(VARIANTS)}"
            )
    return out


RESEARCH_VARIANTS: tuple[str, ...] = (
    "per_circuit",
    "hybrid_blend",
    "per_circuit_plus_blend",
    "elite_head",
    "probabilistic_three_layer",
    "temporally_robust_probabilistic",
    "regime_routed_three_layer",
    "regime_routed_with_weekend",
    "moe_routed_three_layer",
)


def cmd_run(args) -> int:
    variants = _parse_variants(args.variants)
    if getattr(args, "include_research", False):
        for v in RESEARCH_VARIANTS:
            if v not in variants:
                variants.append(v)
    seasons = list(args.seasons)
    payload = run_benchmark(variants, seasons)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"benchmark written: {out}")
    for v in variants:
        a = payload["perVariant"][v]["aggregate"]
        print(
            f"  {v}: n={a['rounds']}  MAE={a['mae']:.3f}  Spearman="
            f"{a['spearman']:.3f}  podium-hit={a['podium_hit_rate']:.1%}  "
            f"winner-hit={a['winner_hit_rate']:.1%}"
        )
    return 0


def cmd_compare(args) -> int:
    payload = json.loads(Path(args.input).read_text())
    write_markdown_report(payload, Path(args.output))
    print(f"compare report written: {args.output}")
    return 0


def cmd_export_website(args) -> int:
    payload = json.loads(Path(args.input).read_text())
    out_dir = Path(args.output)
    write_website_exports(payload, out_dir)
    print(f"website exports written to: {out_dir}")
    for f in ("summary.json", "per_season.json", "per_round.json"):
        print(f"  {out_dir / f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run the benchmark and write JSON")
    # After the Phase 10 freeze the default is the production lineup:
    # baseline + previous incumbent + Phase 7 static (current production
    # candidate). The full experimental set (MoE, Phase 8 full,
    # per-circuit, hybrid-blend, etc.) is available behind
    # ``--include-research``.
    p_run.add_argument(
        "--variants",
        default=(
            "baseline,elite_head_plus_hybrid,"
            "regime_routed_with_weekend_static"
        ),
        help=(
            "comma-separated variant names; defaults to the production "
            "lineup. Use --include-research to add the experimental set."
        ),
    )
    p_run.add_argument(
        "--include-research",
        action="store_true",
        help=(
            "Append the research-only variants (MoE, Phase 8 full, "
            "per_circuit / hybrid_blend, temporally_robust, etc.) "
            "to whatever --variants resolves to. These are kept in-tree "
            "for reproducibility but are NOT in the production path."
        ),
    )
    p_run.add_argument(
        "--seasons", nargs="+", type=int, default=[2024, 2025]
    )
    p_run.add_argument("--output", default="reports/benchmark_phase_1.json")
    p_run.set_defaults(func=cmd_run)

    p_cmp = sub.add_parser("compare", help="write the markdown comparison report")
    p_cmp.add_argument("--input", required=True)
    p_cmp.add_argument("--output", default="docs/BENCHMARK_PHASE_1.md")
    p_cmp.set_defaults(func=cmd_compare)

    p_exp = sub.add_parser("export-website", help="write the website-consumable JSONs")
    p_exp.add_argument("--input", required=True)
    p_exp.add_argument("--output", default="website/public/data/benchmark/")
    p_exp.set_defaults(func=cmd_export_website)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
