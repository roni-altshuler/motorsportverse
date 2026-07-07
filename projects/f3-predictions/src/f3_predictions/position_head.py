"""Direct finishing-position head for F3 (opt-in alternative race-order head).

This is the F3 port of the F1 flagship's ``models/position_model.py``
(landed in commit 189db5b, A/B-gated, verdict-driven). The production F3 race
order is a *post-processing* of the latent-skill blend: :mod:`.model` sorts
drivers by simulated mean finish from a pace score that was learned/blended to
rank like pace — it never learns finishing position directly. This module
learns finishing position **directly**, leakage-safe, so it can be A/B'd
against the production path before anyone trusts it.

Gate
----
The head is wired behind the ``F3_USE_POSITION_HEAD`` environment flag
(default **OFF**) via :func:`head_enabled`; ``model.forecast_round`` consults
it and the production path is byte-identical when the flag is absent. The
promotion decision is data-driven: :func:`run_backtest` produces the
walk-forward A/B evidence (``forward_eval --position-model-ab``) and
``promotion_decision.py`` reads its verdict.

Training frame — the pragmatic clean choice
-------------------------------------------
F1 trains on committed round-JSON snapshots because rebuilding prior rounds'
FastF1 feature matrices is slow and rate-limited. F3 has no such constraint:
the whole pipeline replays offline from the committed snapshot, so the
training frame here is built from **leakage-safe re-forecasts of prior
rounds** — for round ``r`` the model is run exactly as it was pre-race (only
rounds ``< r`` visible), and its per-driver signals become the features. Like
F1, the head is therefore a learned **re-ranking on top of the production
signal** — it isolates "does learning position directly beat sorting by
simulated pace?".

Both race types are in scope — deliberately. F1's design re-ranks the (one)
production classification per round; F3's production model routes *two*
structurally different races through the same probability engine, and the
reverse-grid sprint is precisely the regime where a hand-tuned grid penalty
(``config.SPRINT_GRID_PENALTY``) might lose to a learned grid-vs-pace
tradeoff. Excluding sprints would also discard half the training rows of a
9-round season. The ``gridPosition`` + ``isSprint`` features carry the
race-type structure, so one pooled head serves both races.

Every multi-round aggregation asserts prior-only via
``motorsport_core.leakage.assert_prior_only``.

Probability layer
-----------------
Predicted positions (lower = better) feed the **same** Plackett-Luce Monte
Carlo used by the production path (``model._race_forecast`` treats its score
as lower-is-better), so win/podium/top-K markets come from an identical
engine — only the ordering signal changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Mapping

import numpy as np

from motorsport_core.eval import score_round, spearman_correlation, walk_forward_summary
from motorsport_core.leakage import assert_prior_only

from . import config

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .datasource import F3DataSource
    from .model import RaceForecast, RoundForecastF3

SPRINT = "sprint"
FEATURE = "feature"

ENV_FLAG = "F3_USE_POSITION_HEAD"
RANDOM_STATE = 42

# F3 has a 9-round season and ~60 finisher-rows per weekend (30-car grid × two
# races), so two prior rounds already out-train F1's three prior rounds
# (~20 rows each) — the gate opens one round earlier without getting reckless.
DEFAULT_MIN_PRIOR_ROUNDS = 2

# Feature order is load-bearing: it aligns with ``MONOTONIC_CONSTRAINTS``.
FEATURE_NAMES: tuple[str, ...] = (
    "scoreRank",         # within-race rank of the production pace score (1 = fastest)
    "scoreGap",          # pace-score gap to the fastest driver (seconds proxy)
    "winProbability",    # production win prob for this race, [0, 1]
    "gridPosition",      # starting slot (1 = pole) — carries the reverse-grid sprint
    "finishRangeWidth",  # rangeHigh - rangeLow (MC uncertainty span)
    "finishRangeLow",    # optimistic MC finish bound
    "isSprint",          # 1.0 for the reverse-grid sprint, 0.0 for the feature
)

# Monotonic priors for HistGradientBoostingRegressor: +1 = predicted finishing
# position worsens (rises) with the feature, -1 = improves, 0 = unconstrained.
MONOTONIC_CONSTRAINTS: tuple[int, ...] = (1, 1, -1, 1, 0, 1, 0)


# --------------------------------------------------------------------------- #
# Gate
# --------------------------------------------------------------------------- #
def head_enabled(override: bool | None = None) -> bool:
    """A/B gate: explicit override wins, else the ``F3_USE_POSITION_HEAD`` env
    flag (default OFF — production is unchanged unless someone opts in)."""
    if override is not None:
        return bool(override)
    return os.environ.get(ENV_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------- #
# Feature extraction
# --------------------------------------------------------------------------- #
def extract_race_features(race_fc: "RaceForecast") -> dict[str, dict[str, float]]:
    """Build ``{driver: {feature: value}}`` from one race's locked forecast.

    Circuit-agnostic: every feature is a *within-race* quantity (rank,
    gap-to-fastest, probability, grid slot, interval width) so rows are
    comparable across venues without leaking absolute pace levels.
    """
    codes = list(race_fc.score.keys())
    if not codes:
        return {}
    scores = np.array([float(race_fc.score[c]) for c in codes], dtype=float)
    fastest = float(scores.min())
    order = np.argsort(scores, kind="stable")
    rank = np.empty(len(codes), dtype=float)
    rank[order] = np.arange(1, len(codes) + 1, dtype=float)
    grid_pos = {c: i + 1 for i, c in enumerate(race_fc.grid)}
    is_sprint = 1.0 if race_fc.race_type == SPRINT else 0.0

    out: dict[str, dict[str, float]] = {}
    for i, c in enumerate(codes):
        low = int(race_fc.range_low.get(c, 0) or 0)
        high = int(race_fc.range_high.get(c, low) or low)
        out[c] = {
            "scoreRank": float(rank[i]),
            "scoreGap": float(scores[i] - fastest),
            "winProbability": float(min(1.0, max(0.0, race_fc.markets.p_win.get(c, 0.0)))),
            "gridPosition": float(grid_pos.get(c, len(codes))),
            "finishRangeWidth": float(max(0, high - low)),
            "finishRangeLow": float(low),
        }
        out[c]["isSprint"] = is_sprint
    return out


def _feature_vector(feats: Mapping[str, float]) -> list[float]:
    return [float(feats.get(name, 0.0)) for name in FEATURE_NAMES]


# --------------------------------------------------------------------------- #
# Training frame assembly (leakage-safe)
# --------------------------------------------------------------------------- #
def build_training_frame(
    forecasts_by_round: Mapping[int, "RoundForecastF3"],
    actual_by_round: Mapping[int, Mapping[str, Mapping[str, int]]],
    target_round: int,
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Assemble ``(X, y, rounds_used)`` from rounds strictly before ``target_round``.

    ``forecasts_by_round`` maps round → its leakage-safe pre-race forecast;
    ``actual_by_round`` maps round → ``{race_type: {driver: position}}``
    (classified finishers only, so the frame is finishers-only like the
    headline eval). Leakage discipline: the prior map is asserted
    ``assert_prior_only`` before any row is emitted.
    """
    prior_map = {int(r): fc for r, fc in forecasts_by_round.items() if int(r) < int(target_round)}
    assert_prior_only(prior_map, current_round=int(target_round), label="f3.position_head.training_rounds")

    xs: list[list[float]] = []
    ys: list[float] = []
    rounds_used: list[int] = []
    for rnd in sorted(prior_map):
        actual_round = actual_by_round.get(rnd)
        if not actual_round:
            continue
        contributed = False
        fc = prior_map[rnd]
        for race_type in (SPRINT, FEATURE):
            actual_race = actual_round.get(race_type) or {}
            if not actual_race:
                continue
            feats = extract_race_features(getattr(fc, race_type))
            for drv, f in feats.items():
                pos = actual_race.get(drv)
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
class PositionHead:
    """Gradient-boosted regressor on finishing position with monotonic priors.

    Deterministic (``random_state=42``). ``predict_positions`` returns a
    ``{driver: predicted_position}`` map (lower = better) ready to feed the
    Plackett-Luce probability layer.
    """

    estimator: object = None
    trained_rounds: list[int] = field(default_factory=list)
    n_train_rows: int = 0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "PositionHead":
        from sklearn.ensemble import HistGradientBoostingRegressor

        # HistGBR supports true monotonic constraints; shallow trees because
        # the frame is small (a handful of rounds × ~60 rows).
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
            raise RuntimeError("PositionHead is not fitted")
        drivers = list(features_by_driver.keys())
        X = np.asarray([_feature_vector(features_by_driver[d]) for d in drivers], dtype=float)
        preds = np.asarray(self.estimator.predict(X), dtype=float)
        return {d: float(p) for d, p in zip(drivers, preds)}


def predicted_order(predicted_positions: Mapping[str, float]) -> list[str]:
    """Drivers sorted best (lowest predicted position) first — deterministic."""
    return [d for d, _ in sorted(predicted_positions.items(), key=lambda kv: (kv[1], kv[0]))]


def monotonic_sanity(
    predicted_positions: Mapping[str, float],
    features_by_driver: Mapping[str, Mapping[str, float]],
) -> float | None:
    """Rank-correlation between the base pace signal and the predicted order.

    A healthy head stays *positively* correlated with ``scoreRank`` (it
    re-ranks around the pace signal, it does not invert it). Returns the
    Spearman correlation in ``[-1, 1]`` (``None`` if < 3 drivers).
    """
    common = [d for d in predicted_positions if d in features_by_driver]
    if len(common) < 3:
        return None
    pace_rank = [int(round(features_by_driver[d]["scoreRank"])) for d in common]
    order = predicted_order({d: predicted_positions[d] for d in common})
    pred_rank_map = {d: i + 1 for i, d in enumerate(order)}
    pred_rank = [pred_rank_map[d] for d in common]
    return spearman_correlation(pred_rank, pace_rank)


# --------------------------------------------------------------------------- #
# Wiring against the F3 data/model layer
# --------------------------------------------------------------------------- #
def _actuals_for_round(source: "F3DataSource", year: int, rnd: int) -> dict[str, dict[str, int]]:
    races = source.race_results_for_round(year, rnd)
    return {
        race_type: {r.competitor: r.position for r in races[race_type] if r.position is not None}
        for race_type in (SPRINT, FEATURE)
    }


def _prior_replays(
    source: "F3DataSource", year: int, target_round: int
) -> tuple[dict[int, "RoundForecastF3"], dict[int, dict[str, dict[str, int]]]]:
    """Leakage-safe re-forecasts + actuals for completed rounds ``< target_round``.

    Each prior round is re-forecast with the head explicitly disabled
    (``use_position_head=False``) so training features are always the
    *production* signal — never the head's own output (no feedback loop).
    """
    from . import model as _model

    forecasts: dict[int, "RoundForecastF3"] = {}
    actuals: dict[int, dict[str, dict[str, int]]] = {}
    last = min(int(target_round) - 1, config.COMPLETED_ROUNDS)
    for rnd in range(1, last + 1):
        actual = _actuals_for_round(source, year, rnd)
        if not actual.get(FEATURE):
            continue
        forecasts[rnd] = _model.forecast_round(source, year, rnd, use_position_head=False)
        actuals[rnd] = actual
    return forecasts, actuals


def train_for_round(
    source: "F3DataSource",
    year: int,
    target_round: int,
    *,
    min_prior_rounds: int = DEFAULT_MIN_PRIOR_ROUNDS,
    forecasts_by_round: Mapping[int, "RoundForecastF3"] | None = None,
    actual_by_round: Mapping[int, Mapping[str, Mapping[str, int]]] | None = None,
) -> PositionHead | None:
    """Train a :class:`PositionHead` for ``target_round`` on prior rounds only.

    Graceful degradation: returns ``None`` when fewer than ``min_prior_rounds``
    prior rounds have both features and actuals — the caller then falls back to
    the production path. Precomputed forecasts/actuals may be passed to avoid
    re-replaying (the backtest shares one replay across all target rounds).
    """
    if forecasts_by_round is None or actual_by_round is None:
        forecasts_by_round, actual_by_round = _prior_replays(source, year, target_round)
    X, y, rounds_used = build_training_frame(forecasts_by_round, actual_by_round, target_round)
    if len(rounds_used) < int(min_prior_rounds) or len(y) == 0:
        return None
    return PositionHead(trained_rounds=rounds_used).fit(X, y)


def rerank_race(head: PositionHead, race_fc: "RaceForecast", *, n_samples: int) -> "RaceForecast":
    """Re-run one race's Monte Carlo with the head's predicted positions as the score.

    Uses the **same** ``model._race_forecast`` machinery as production (grid
    unchanged, Plackett-Luce markets, MC finish ranges, confidence bands) —
    only the ordering signal is swapped.
    """
    from . import model as _model

    feats = extract_race_features(race_fc)
    pred = head.predict_positions(feats)
    return _model._race_forecast(race_fc.race_type, race_fc.grid, pred, n_samples=n_samples)


def maybe_rerank_round(
    source: "F3DataSource",
    year: int,
    round: int,
    fc: "RoundForecastF3",
    *,
    n_samples: int,
    min_prior_rounds: int = DEFAULT_MIN_PRIOR_ROUNDS,
) -> "RoundForecastF3":
    """Apply the position head to a round forecast when trainable, else pass through.

    Returns the forecast unchanged (``position_head`` metadata records
    ``applied: false`` + reason) when there is too little prior data — the same
    graceful degradation contract as the other optional F3 signals.
    """
    head = train_for_round(source, year, round, min_prior_rounds=min_prior_rounds)
    if head is None:
        return replace(
            fc,
            position_head={
                "applied": False,
                "reason": f"fewer than {min_prior_rounds} prior completed rounds",
            },
        )
    sprint = rerank_race(head, fc.sprint, n_samples=n_samples)
    feature = rerank_race(head, fc.feature, n_samples=n_samples)
    return replace(
        fc,
        sprint=sprint,
        feature=feature,
        position_head={
            "applied": True,
            "trainedRounds": head.trained_rounds,
            "trainRows": head.n_train_rows,
        },
    )


# --------------------------------------------------------------------------- #
# Walk-forward A/B backtest — the acceptance evidence
# --------------------------------------------------------------------------- #
def _numeric_metrics(score: Mapping[str, object]) -> dict[str, float]:
    """Numeric-only view of a ``score_round`` bundle for ``walk_forward_summary``.

    Converts the ``winner_hit`` boolean into ``winnerHit`` (0/1) so it survives
    the summary (which skips bools), and drops ``n``.
    """
    out: dict[str, float] = {}
    for key, val in score.items():
        if key == "n":
            continue
        if key == "winner_hit":
            out["winnerHit"] = 1.0 if val else 0.0
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        out[key] = float(val)
    return out


def _pooled_metrics(sprint: Mapping[str, float], feature: Mapping[str, float]) -> dict[str, float]:
    """Per-key mean of the sprint and feature numeric bundles (the weekend view)."""
    keys = set(sprint) | set(feature)
    out: dict[str, float] = {}
    for k in keys:
        vals = [m[k] for m in (sprint, feature) if isinstance(m.get(k), (int, float))]
        if vals:
            out[k] = float(sum(vals) / len(vals))
    return out


def _score_order(order: list[str], actual: Mapping[str, int]) -> dict:
    predicted = {code: i for i, code in enumerate(order, start=1)}
    return score_round(predicted, actual)


def run_backtest(
    source: "F3DataSource",
    year: int,
    *,
    min_prior_rounds: int = DEFAULT_MIN_PRIOR_ROUNDS,
    generated_at: str | None = None,
) -> dict[str, object]:
    """Walk-forward A/B: for each completed round N, train on ``< N``, predict N,
    and score the position head against the production path — per race type and
    pooled per weekend.

    Both arms replay the leakage-safe pre-race forecast (production = the order
    the site would have shown; head = the re-ranked order), scored against the
    actual classified finishers via :func:`motorsport_core.eval.score_round`
    and aggregated via :func:`motorsport_core.eval.walk_forward_summary`.
    Rounds with fewer than ``min_prior_rounds`` priors are recorded with
    ``applied: false`` and excluded from the head-to-head summary.
    """
    from . import model as _model

    # One shared replay of every completed round (deterministic, head OFF).
    forecasts: dict[int, "RoundForecastF3"] = {}
    actuals: dict[int, dict[str, dict[str, int]]] = {}
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        actual = _actuals_for_round(source, year, rnd)
        if not actual.get(FEATURE):
            continue
        forecasts[rnd] = _model.forecast_round(source, year, rnd, use_position_head=False)
        actuals[rnd] = actual

    per_round: list[dict[str, object]] = []
    head_pooled: list[dict[str, float]] = []
    prod_pooled: list[dict[str, float]] = []
    head_by_type: dict[str, list[dict[str, float]]] = {SPRINT: [], FEATURE: []}
    prod_by_type: dict[str, list[dict[str, float]]] = {SPRINT: [], FEATURE: []}

    for n in sorted(forecasts):
        fc = forecasts[n]
        prod_scores = {
            race_type: _score_order(getattr(fc, race_type).order, actuals[n][race_type])
            for race_type in (SPRINT, FEATURE)
        }
        entry: dict[str, object] = {"round": n, "production": prod_scores}

        head = train_for_round(
            source, year, n,
            min_prior_rounds=min_prior_rounds,
            forecasts_by_round=forecasts,
            actual_by_round=actuals,
        )
        if head is None:
            entry["positionHead"] = {
                "applied": False,
                "reason": f"fewer than {min_prior_rounds} prior completed rounds",
            }
        else:
            head_scores: dict[str, dict] = {}
            sanity: dict[str, float | None] = {}
            for race_type in (SPRINT, FEATURE):
                feats = extract_race_features(getattr(fc, race_type))
                pred = head.predict_positions(feats)
                head_scores[race_type] = _score_order(predicted_order(pred), actuals[n][race_type])
                sanity[race_type] = monotonic_sanity(pred, feats)
            entry["positionHead"] = {
                "applied": True,
                "trainedRounds": head.trained_rounds,
                "monotonicSanity": sanity,
                **head_scores,
            }
            h_num = {rt: _numeric_metrics(head_scores[rt]) for rt in (SPRINT, FEATURE)}
            p_num = {rt: _numeric_metrics(prod_scores[rt]) for rt in (SPRINT, FEATURE)}
            for rt in (SPRINT, FEATURE):
                head_by_type[rt].append(h_num[rt])
                prod_by_type[rt].append(p_num[rt])
            head_pooled.append(_pooled_metrics(h_num[SPRINT], h_num[FEATURE]))
            prod_pooled.append(_pooled_metrics(p_num[SPRINT], p_num[FEATURE]))
        per_round.append(entry)

    return {
        "season": int(year),
        "generatedAt": generated_at,
        "minPriorRounds": int(min_prior_rounds),
        "roundsScored": len(per_round),
        "roundsCompared": len(head_pooled),
        "rounds": per_round,
        "walkForward": {
            "positionHead": {
                "sprint": walk_forward_summary(head_by_type[SPRINT]),
                "feature": walk_forward_summary(head_by_type[FEATURE]),
                "pooled": walk_forward_summary(head_pooled),
            },
            "production": {
                "sprint": walk_forward_summary(prod_by_type[SPRINT]),
                "feature": walk_forward_summary(prod_by_type[FEATURE]),
                "pooled": walk_forward_summary(prod_pooled),
            },
        },
        "verdict": _verdict(head_pooled, prod_pooled),
    }


def _mean(values: list[float | None]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else None


def _verdict(
    head_metrics: list[Mapping[str, float]],
    prod_metrics: list[Mapping[str, float]],
) -> dict[str, object]:
    """Data-driven promotion verdict from pooled mean position error over the overlap."""
    if not head_metrics or not prod_metrics:
        return {"recommendation": "inconclusive", "reason": "no overlapping rounds"}
    head_err = _mean([m.get("mean_position_error") for m in head_metrics])
    prod_err = _mean([m.get("mean_position_error") for m in prod_metrics])
    head_win = _mean([m.get("winnerHit", 0.0) for m in head_metrics])
    prod_win = _mean([m.get("winnerHit", 0.0) for m in prod_metrics])
    delta = None
    recommendation = "inconclusive"
    if head_err is not None and prod_err is not None:
        delta = round(head_err - prod_err, 4)  # negative = position head better
        if delta < -0.01:
            recommendation = "position-head-better"
        elif delta > 0.01:
            recommendation = "production-better"
    return {
        "recommendation": recommendation,
        "basis": "pooled (sprint+feature) mean_position_error",
        "positionHeadMeanError": round(head_err, 4) if head_err is not None else None,
        "productionMeanError": round(prod_err, 4) if prod_err is not None else None,
        "meanErrorDelta": delta,
        "positionHeadWinnerHitRate": round(head_win, 4) if head_win is not None else None,
        "productionWinnerHitRate": round(prod_win, 4) if prod_win is not None else None,
    }


__all__ = [
    "ENV_FLAG",
    "FEATURE_NAMES",
    "MONOTONIC_CONSTRAINTS",
    "DEFAULT_MIN_PRIOR_ROUNDS",
    "PositionHead",
    "head_enabled",
    "extract_race_features",
    "build_training_frame",
    "train_for_round",
    "predicted_order",
    "monotonic_sanity",
    "rerank_race",
    "maybe_rerank_round",
    "run_backtest",
]
