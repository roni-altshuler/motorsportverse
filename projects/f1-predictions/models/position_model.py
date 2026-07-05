"""Direct finishing-position model (opt-in alternative race-order head).

Motivation
----------
The production race order is a *post-processing* of the qualifying-time
regression: ``predicted_classification`` sorts drivers by
``RaceProjectionTime`` (a 13-term ``RaceProjectionScore`` layered on top of the
lap-time ensemble).  That head never learns finishing position directly — it
learns *pace* and hopes pace ranks like the race result.

This module learns finishing position **directly**, leakage-safe, so it can be
A/B'd against the production path before anyone trusts it.  It is wired behind
``--use-position-model`` in ``export_website_data.py`` and defaults **OFF**; the
production path is unchanged when the flag is absent.

Training frame — the pragmatic clean choice
--------------------------------------------
``build_training_dataset`` in ``f1_prediction_utils.py`` builds a rich per-round
feature matrix, but rebuilding *prior* rounds' matrices at export time would
require re-fetching FastF1 sessions per round (rate-limited, slow, and the
qualifying/telemetry inputs for a past round are not cheaply reproducible).  The
committed ``website/public/data/rounds/round_NN.json`` files, on the other hand,
already carry a locked, leakage-safe snapshot of the model's per-driver signals
for every completed round: predicted lap-time (→ within-round rank + gap),
win probability, DNF probability, and the finish-range interval.

So the training frame here is a **light feature set derived from the committed
round JSONs** (current-season rounds only).  Tradeoff: we train on the
production model's *own signals* rather than raw telemetry, so the position head
is a learned **re-ranking** on top of the production pace signal — not an
independent-from-scratch model.  That is exactly what we want for an A/B lever:
it isolates "does learning position directly beat sorting by pace?".  Because
only current-season committed rounds expose these signals cleanly, training is
restricted to rounds ``< N`` of the current season (prior-season JSONs are not
in this tree), and the A/B honestly reports that.

Every multi-round aggregation asserts prior-only via
``motorsport_core.leakage.assert_prior_only``.

Probability layer
-----------------
Predicted positions (lower = better) feed the **same** Plackett-Luce probability
layer used by the production path (``motorsport_core.calibration`` treats the
input as a score where lower is better), so win/podium/top-K probabilities are
produced by an identical engine — only the ordering signal changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

try:  # pragma: no cover - import guard
    from motorsport_core.calibration import plackett_luce_probabilities
    from motorsport_core.leakage import assert_prior_only
except Exception:  # pragma: no cover
    plackett_luce_probabilities = None  # type: ignore[assignment]

    def assert_prior_only(rounds_map, current_round, label="rounds_map"):  # type: ignore[misc]
        return None


# --------------------------------------------------------------------------- #
# Feature catalogue
# --------------------------------------------------------------------------- #

# Feature order is load-bearing: it aligns with ``MONOTONIC_CONSTRAINTS`` below.
FEATURE_NAMES: tuple[str, ...] = (
    "predTimeRank",       # within-round rank of predicted lap time (1 = fastest)
    "predTimeGap",        # seconds behind the fastest predicted lap time
    "winProbability",     # production win prob, [0, 1]
    "dnfProbability",     # per-driver DNF prob, [0, 1]
    "finishRangeWidth",   # finishRangeHigh - finishRangeLow (uncertainty span)
    "finishRangeLow",     # optimistic finish bound (1 = predicted podium edge)
)

# Monotonic priors for HistGradientBoostingRegressor: +1 = predicted finishing
# position increases with the feature, -1 = decreases, 0 = unconstrained.
#   predTimeRank↑  → worse position (+1)
#   predTimeGap↑   → worse position (+1)
#   winProb↑       → better position (-1)
#   dnfProb↑       → worse position (+1)
#   rangeWidth     → unconstrained (0)
#   finishRangeLow↑→ worse position (+1)
MONOTONIC_CONSTRAINTS: tuple[int, ...] = (1, 1, -1, 1, 0, 1)

RANDOM_STATE = 42


# --------------------------------------------------------------------------- #
# Feature extraction
# --------------------------------------------------------------------------- #


def _to_prob(value: object) -> float:
    """Coerce a win-probability field to [0, 1] (committed JSON stores 0-100)."""
    try:
        p = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if p > 1.0:
        p = p / 100.0
    return float(min(1.0, max(0.0, p)))


def extract_round_features(
    classification: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, float]]:
    """Build ``{driver: {feature: value}}`` from a round's classification rows.

    Works for both a committed ``round_NN.json``'s ``classification`` list and a
    freshly-synthesised list of dicts (live export path).  Circuit-agnostic:
    every feature is a *within-round* quantity (rank, gap-to-fastest, prob,
    interval width) so rows are comparable across circuits without leaking
    absolute lap times.
    """
    rows: list[dict[str, object]] = [dict(r) for r in classification if r.get("driver")]
    if not rows:
        return {}

    times = np.array([float(r.get("predictedTime", 0.0) or 0.0) for r in rows], dtype=float)
    fastest = float(np.min(times)) if len(times) else 0.0
    # Dense min-rank of predicted time (1 = fastest).
    order = np.argsort(times, kind="stable")
    rank = np.empty(len(times), dtype=float)
    rank[order] = np.arange(1, len(times) + 1, dtype=float)

    out: dict[str, dict[str, float]] = {}
    for i, r in enumerate(rows):
        drv = str(r["driver"])
        pos = int(r.get("position", i + 1) or (i + 1))
        low = int(r.get("finishRangeLow", pos) or pos)
        high = int(r.get("finishRangeHigh", pos) or pos)
        out[drv] = {
            "predTimeRank": float(rank[i]),
            "predTimeGap": float(times[i] - fastest),
            "winProbability": _to_prob(r.get("winProbability", 0.0)),
            "dnfProbability": _to_prob(r.get("dnfProbability", 0.0)),
            "finishRangeWidth": float(max(0, high - low)),
            "finishRangeLow": float(low),
        }
    return out


def _feature_vector(feats: Mapping[str, float]) -> list[float]:
    return [float(feats.get(name, 0.0)) for name in FEATURE_NAMES]


# --------------------------------------------------------------------------- #
# Training frame assembly (leakage-safe)
# --------------------------------------------------------------------------- #


def build_training_frame(
    rounds_by_round: Mapping[int, Sequence[Mapping[str, object]]],
    actual: Mapping[int, Mapping[str, int]],
    target_round: int,
    *,
    season: int | None = None,
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Assemble ``(X, y, rounds_used)`` from rounds strictly before ``target_round``.

    ``rounds_by_round`` maps round number → that round's classification rows
    (committed JSON snapshots).  ``actual`` maps round number → the observed
    ``{driver: finishing_position}``.  Only rounds ``< target_round`` that have
    *both* features and actuals contribute rows.

    Leakage discipline: the prior-round map is asserted ``assert_prior_only``
    before any row is emitted, so a caller that forgets to filter fails loudly
    instead of training on the target round or later.
    """
    prior_map = {int(r): rows for r, rows in rounds_by_round.items() if int(r) < int(target_round)}
    assert_prior_only(prior_map, current_round=int(target_round), label="position_model_training_rounds")

    xs: list[list[float]] = []
    ys: list[float] = []
    rounds_used: list[int] = []
    for rnd in sorted(prior_map):
        actual_round = actual.get(rnd) or actual.get(str(rnd))  # type: ignore[arg-type]
        if not actual_round:
            continue
        feats = extract_round_features(prior_map[rnd])
        if not feats:
            continue
        contributed = False
        for drv, f in feats.items():
            pos = actual_round.get(drv)
            if pos is None:
                continue
            xs.append(_feature_vector(f))
            ys.append(float(int(pos)))
            contributed = True
        if contributed:
            rounds_used.append(rnd)

    if not xs:
        return np.empty((0, len(FEATURE_NAMES))), np.empty((0,)), []
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float), rounds_used


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #


@dataclass
class PositionModel:
    """A gradient-boosted regressor on finishing position with monotonic priors.

    Deterministic (``random_state=42``).  ``predict_positions`` returns a
    ``{driver: predicted_position}`` map (lower = better) ready to feed the
    Plackett-Luce probability layer.
    """

    estimator: object = None
    trained_rounds: list[int] = field(default_factory=list)
    n_train_rows: int = 0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "PositionModel":
        from sklearn.ensemble import HistGradientBoostingRegressor

        # HistGBR supports true monotonic constraints; keep the trees shallow
        # because the training frame is small (a handful of rounds × ~22 rows).
        try:
            est = HistGradientBoostingRegressor(
                loss="squared_error",
                max_depth=3,
                max_iter=200,
                learning_rate=0.05,
                min_samples_leaf=5,
                monotonic_cst=list(MONOTONIC_CONSTRAINTS),
                random_state=RANDOM_STATE,
            )
            est.fit(X, y)
        except Exception:  # pragma: no cover - defensive fallback
            from sklearn.ensemble import GradientBoostingRegressor

            est = GradientBoostingRegressor(
                n_estimators=120,
                max_depth=2,
                learning_rate=0.05,
                subsample=0.9,
                random_state=RANDOM_STATE,
            )
            est.fit(X, y)
        self.estimator = est
        self.n_train_rows = int(len(y))
        return self

    def predict_positions(
        self, features_by_driver: Mapping[str, Mapping[str, float]]
    ) -> dict[str, float]:
        """Return ``{driver: predicted_position}`` (continuous, lower = better)."""
        if self.estimator is None:
            raise RuntimeError("PositionModel is not fitted")
        drivers = list(features_by_driver.keys())
        X = np.asarray([_feature_vector(features_by_driver[d]) for d in drivers], dtype=float)
        preds = np.asarray(self.estimator.predict(X), dtype=float)
        return {d: float(p) for d, p in zip(drivers, preds)}


def train_position_model(
    rounds_by_round: Mapping[int, Sequence[Mapping[str, object]]],
    actual: Mapping[int, Mapping[str, int]],
    target_round: int,
    *,
    season: int | None = None,
    min_prior_rounds: int = 3,
) -> PositionModel | None:
    """Train a :class:`PositionModel` for ``target_round`` on prior rounds.

    Graceful degradation: returns ``None`` when fewer than ``min_prior_rounds``
    prior rounds have both features and actuals — the caller then falls back to
    the production path and records ``applied: false``.
    """
    X, y, rounds_used = build_training_frame(
        rounds_by_round, actual, target_round, season=season
    )
    if len(rounds_used) < int(min_prior_rounds) or len(y) == 0:
        return None
    model = PositionModel(trained_rounds=rounds_used).fit(X, y)
    return model


def predicted_order(predicted_positions: Mapping[str, float]) -> list[str]:
    """Drivers sorted best (lowest predicted position) first — deterministic."""
    return [d for d, _ in sorted(predicted_positions.items(), key=lambda kv: (kv[1], kv[0]))]


def monotonic_sanity(
    predicted_positions: Mapping[str, float],
    features_by_driver: Mapping[str, Mapping[str, float]],
) -> float | None:
    """Rank-correlation between the base pace signal and the predicted order.

    A healthy position head stays *positively* correlated with ``predTimeRank``
    (it re-ranks around the pace signal, it does not invert it).  Returns the
    Spearman-style correlation in ``[-1, 1]`` (``None`` if < 3 drivers).  The
    caller can warn/flag when this drops below 0.
    """
    from motorsport_core.eval import spearman_correlation

    common = [d for d in predicted_positions if d in features_by_driver]
    if len(common) < 3:
        return None
    pace_rank = [int(round(features_by_driver[d]["predTimeRank"])) for d in common]
    order = predicted_order({d: predicted_positions[d] for d in common})
    pred_rank_map = {d: i + 1 for i, d in enumerate(order)}
    pred_rank = [pred_rank_map[d] for d in common]
    return spearman_correlation(pred_rank, pace_rank)


def position_probabilities(
    predicted_positions: Mapping[str, float],
    *,
    n_samples: int = 5000,
    temperature: float = 0.5,
    seed: int = RANDOM_STATE,
):
    """Feed predicted positions (lower = better) into the Plackett-Luce layer.

    Returns the same ``MarketProbabilities`` object the production probability
    path produces, so downstream win/podium/top-K consumers are unchanged.
    """
    if plackett_luce_probabilities is None:  # pragma: no cover
        raise RuntimeError("motorsport_core.calibration is unavailable")
    return plackett_luce_probabilities(
        dict(predicted_positions), n_samples=n_samples, temperature=temperature, seed=seed
    )


# --------------------------------------------------------------------------- #
# A/B backtest — the acceptance evidence
# --------------------------------------------------------------------------- #


def _numeric_metrics(score: Mapping[str, object]) -> dict[str, float]:
    """Numeric-only view of a ``score_round`` bundle for walk-forward summary.

    Converts the ``winner_hit`` boolean into ``winnerHit`` (0/1) so it survives
    ``walk_forward_summary`` (which skips bools), and drops ``n``.
    """
    out: dict[str, float] = {}
    for key, val in score.items():
        if key in ("n", "applied", "reason", "trainedRounds"):
            continue
        if key == "winner_hit":
            out["winnerHit"] = 1.0 if val else 0.0
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        out[key] = float(val)
    return out


def run_backtest(
    season: int,
    rounds_by_round: Mapping[int, Sequence[Mapping[str, object]]],
    actual: Mapping[int, Mapping[str, int]],
    *,
    min_prior_rounds: int = 3,
    generated_at: str | None = None,
) -> dict[str, object]:
    """Walk-forward A/B: for each completed round N, train on ``<N``, predict N,
    and score the position head against the production path.

    The production head for round N is that round's committed classification
    order (``round_NN.json``); the position head retrains from prior rounds
    only.  Both are scored against the actual finishing order and aggregated via
    :func:`motorsport_core.eval.walk_forward_summary`.  Rounds with fewer than
    ``min_prior_rounds`` priors are recorded with ``applied: false`` and excluded
    from the head-to-head summary.
    """
    from motorsport_core.eval import score_round, walk_forward_summary

    completed = sorted(
        r for r in rounds_by_round
        if (actual.get(r) or actual.get(str(r)))  # type: ignore[arg-type]
    )

    per_round: list[dict[str, object]] = []
    pm_metrics: list[dict[str, float]] = []
    prod_metrics: list[dict[str, float]] = []

    for n in completed:
        actual_n = {str(d): int(p) for d, p in (actual.get(n) or actual.get(str(n))).items()}  # type: ignore[union-attr]
        prod_order = {
            str(r["driver"]): int(r.get("position", 0) or 0)
            for r in rounds_by_round[n]
            if r.get("driver")
        }
        prod_score = score_round(prod_order, actual_n)
        entry: dict[str, object] = {"round": n, "production": prod_score}

        model = train_position_model(
            rounds_by_round, actual, n, season=season, min_prior_rounds=min_prior_rounds
        )
        if model is None:
            entry["positionModel"] = {
                "applied": False,
                "reason": f"fewer than {min_prior_rounds} prior completed rounds",
            }
        else:
            feats = extract_round_features(rounds_by_round[n])
            pred_pos = model.predict_positions(feats)
            order = predicted_order(pred_pos)
            pm_order = {d: i + 1 for i, d in enumerate(order)}
            pm_score = score_round(pm_order, actual_n)
            entry["positionModel"] = {
                "applied": True,
                "trainedRounds": model.trained_rounds,
                "monotonicSanity": monotonic_sanity(pred_pos, feats),
                **pm_score,
            }
            pm_metrics.append(_numeric_metrics(pm_score))
            prod_metrics.append(_numeric_metrics(prod_score))
        per_round.append(entry)

    return {
        "season": int(season),
        "generatedAt": generated_at,
        "minPriorRounds": int(min_prior_rounds),
        "roundsScored": len(per_round),
        "roundsCompared": len(pm_metrics),
        "rounds": per_round,
        "walkForward": {
            "positionModel": walk_forward_summary(pm_metrics),
            "production": walk_forward_summary(prod_metrics),
        },
        "verdict": _verdict(pm_metrics, prod_metrics),
    }


def _mean(values: list[float]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else None


def _verdict(
    pm_metrics: list[Mapping[str, float]],
    prod_metrics: list[Mapping[str, float]],
) -> dict[str, object]:
    """Data-driven promotion verdict from mean position error over the overlap."""
    if not pm_metrics or not prod_metrics:
        return {"recommendation": "inconclusive", "reason": "no overlapping rounds"}
    pm_err = _mean([m.get("mean_position_error") for m in pm_metrics])  # type: ignore[list-item]
    prod_err = _mean([m.get("mean_position_error") for m in prod_metrics])  # type: ignore[list-item]
    pm_win = _mean([m.get("winnerHit", 0.0) for m in pm_metrics])
    prod_win = _mean([m.get("winnerHit", 0.0) for m in prod_metrics])
    delta = None
    recommendation = "inconclusive"
    if pm_err is not None and prod_err is not None:
        delta = round(pm_err - prod_err, 4)  # negative = position model better
        if delta < -0.01:
            recommendation = "position-model-better"
        elif delta > 0.01:
            recommendation = "production-better"
        else:
            recommendation = "inconclusive"
    return {
        "recommendation": recommendation,
        "positionModelMeanError": round(pm_err, 4) if pm_err is not None else None,
        "productionMeanError": round(prod_err, 4) if prod_err is not None else None,
        "meanErrorDelta": delta,
        "positionModelWinnerHitRate": round(pm_win, 4) if pm_win is not None else None,
        "productionWinnerHitRate": round(prod_win, 4) if prod_win is not None else None,
    }


__all__ = [
    "FEATURE_NAMES",
    "MONOTONIC_CONSTRAINTS",
    "PositionModel",
    "extract_round_features",
    "build_training_frame",
    "train_position_model",
    "predicted_order",
    "monotonic_sanity",
    "position_probabilities",
    "run_backtest",
]
