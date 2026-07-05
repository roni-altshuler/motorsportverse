"""Forward-time evaluation metrics for ranked motorsport predictions.

CLI-free, importable distillation of the F1 project's ``forward_eval.py``
scoring core. These functions operate on plain ``{competitor: position}``
maps so they work for any sport whose output is a finishing order.

The F1 project's CLI (file IO, per-round JSON writers, reliability-diagram
plotting) can import these back; only the pure metric algorithms live here.

Public API
----------
- :func:`average_ranks` — tie-aware ranking.
- :func:`spearman_correlation` — rank correlation between two orders.
- :func:`ndcg_at_k` — ranking quality of the predicted top-K.
- :func:`mean_position_error` / :func:`within_n` — positional accuracy.
- :func:`score_round` — bundle the per-round metrics into one dict.
- :func:`last_order_baseline` — the "previous result as prediction" baseline.
"""
from __future__ import annotations

import math
from typing import Mapping

Order = Mapping[str, int]


def average_ranks(values: list[int]) -> list[float]:
    """Convert raw positions to average ranks (ties get the mean rank)."""
    indexed = sorted(enumerate(values), key=lambda iv: iv[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # +1 for 1-indexed rank
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def spearman_correlation(predicted: list[int], actual: list[int]) -> float | None:
    """Spearman rank correlation between two integer rank vectors.

    Average-rank convention for ties; reduces to the standard
    ``1 - 6 Σ d² / (n(n²-1))`` in the no-tie case. Returns ``None`` for n < 3.
    """
    n = len(predicted)
    if n < 3:
        return None
    pred_ranks = average_ranks(predicted)
    act_ranks = average_ranks(actual)
    mean_p = sum(pred_ranks) / n
    mean_a = sum(act_ranks) / n
    cov = sum((p - mean_p) * (a - mean_a) for p, a in zip(pred_ranks, act_ranks))
    var_p = sum((p - mean_p) ** 2 for p in pred_ranks)
    var_a = sum((a - mean_a) ** 2 for a in act_ranks)
    denom = math.sqrt(var_p * var_a)
    if denom <= 0:
        return None
    return cov / denom


def ndcg_at_k(predicted: Order, actual: Order, k: int = 5) -> float | None:
    """Normalised DCG over the predicted top-K.

    Relevance is ``n - actual_position`` (P1 = highest gain). Result ∈ [0, 1];
    1.0 = predicted top-K exactly matches the actual top-K. ``None`` when fewer
    than K competitors are shared between the two maps.
    """
    common = sorted(set(predicted.keys()) & set(actual.keys()))
    if len(common) < k or k < 1:
        return None
    n = len(common)
    relevance = {d: float(n - actual[d]) for d in common}
    pred_topk = sorted(common, key=lambda d: predicted[d])[:k]
    ideal_topk = sorted(common, key=lambda d: actual[d])[:k]

    def dcg(order: list[str]) -> float:
        return sum(relevance[d] / math.log2(rank + 1) for rank, d in enumerate(order, start=1))

    ideal_dcg = dcg(ideal_topk)
    if ideal_dcg <= 0:
        return None
    return dcg(pred_topk) / ideal_dcg


def mean_position_error(predicted: Order, actual: Order) -> float | None:
    """Mean absolute positional error over shared competitors."""
    common = sorted(set(predicted.keys()) & set(actual.keys()))
    if not common:
        return None
    return sum(abs(predicted[d] - actual[d]) for d in common) / len(common)


def within_n(predicted: Order, actual: Order, n: int) -> int:
    """Count of competitors whose predicted position is within ``n`` of actual."""
    common = set(predicted.keys()) & set(actual.keys())
    return sum(1 for d in common if abs(predicted[d] - actual[d]) <= n)


def score_round(predicted: Order, actual: Order) -> dict[str, object]:
    """Per-round metric bundle for a single event.

    Mirrors the headline metrics of the F1 ``RoundEvaluation``: positional
    error, winner/podium hits, within-N counts, Spearman ρ and NDCG@5.
    """
    common = sorted(set(predicted.keys()) & set(actual.keys()))
    if not common:
        return {"n": 0}
    pred_sorted = sorted(predicted.items(), key=lambda kv: kv[1])
    act_sorted = sorted(actual.items(), key=lambda kv: kv[1])
    pred_winner = pred_sorted[0][0]
    act_winner = act_sorted[0][0]
    pred_top3 = {d for d, _ in pred_sorted[:3]}
    act_top3 = {d for d, _ in act_sorted[:3]}
    return {
        "n": len(common),
        "mean_position_error": round(mean_position_error(predicted, actual), 3),
        "winner_hit": pred_winner == act_winner,
        "podium_hits": len(pred_top3 & act_top3),
        "within_3": within_n(predicted, actual, 3),
        "within_5": within_n(predicted, actual, 5),
        "exact_matches": sum(1 for d in common if predicted[d] == actual[d]),
        "spearman_correlation": spearman_correlation(
            [predicted[d] for d in common], [actual[d] for d in common]
        ),
        "ndcg_at_5": ndcg_at_k(predicted, actual, 5),
    }


def last_order_baseline(previous_actual: Order) -> dict[str, int]:
    """The 'previous result becomes the prediction' baseline order."""
    return {d: pos for d, pos in previous_actual.items()}


def brier_score(
    probs: Mapping[str, float], outcomes: Mapping[str, int | float | bool]
) -> float | None:
    """Mean squared error between predicted probabilities and binary outcomes.

    ``probs`` maps a key (competitor, or any event id) to a predicted
    probability in ``[0, 1]``; ``outcomes`` maps the same keys to the realised
    outcome (``1``/``True`` = happened, ``0``/``False`` = did not). Only keys
    present in *both* maps are scored. Lower is better; 0 is perfect.

    Returns ``None`` when there are no shared keys. Probabilities are clamped to
    ``[0, 1]`` defensively.
    """
    common = sorted(set(probs.keys()) & set(outcomes.keys()))
    if not common:
        return None
    total = 0.0
    for k in common:
        p = min(1.0, max(0.0, float(probs[k])))
        y = float(bool(outcomes[k])) if isinstance(outcomes[k], bool) else float(outcomes[k])
        total += (p - y) ** 2
    return total / len(common)


def log_loss(
    probs: Mapping[str, float],
    outcomes: Mapping[str, int | float | bool],
    eps: float = 1e-12,
) -> float | None:
    """Mean binary cross-entropy between predicted probabilities and outcomes.

    Same input contract as :func:`brier_score`. Probabilities are clipped to
    ``[eps, 1 - eps]`` so a confident miss stays finite. Lower is better.
    Returns ``None`` when there are no shared keys.
    """
    common = sorted(set(probs.keys()) & set(outcomes.keys()))
    if not common:
        return None
    total = 0.0
    for k in common:
        p = min(1.0 - eps, max(eps, float(probs[k])))
        y = float(bool(outcomes[k])) if isinstance(outcomes[k], bool) else float(outcomes[k])
        total += -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))
    return total / len(common)


def _linear_trend(values: list[float]) -> float | None:
    """OLS slope of ``values`` against their index (0, 1, 2, ...).

    Positive slope = the metric is rising across rounds. ``None`` for < 2
    points or a degenerate x-variance.
    """
    n = len(values)
    if n < 2:
        return None
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x <= 0:
        return None
    return cov / var_x


def walk_forward_summary(per_round_metrics: list[Mapping[str, object]]) -> dict[str, object]:
    """Aggregate a list of per-round metric dicts into a walk-forward summary.

    This is the headline validation surface: given the per-round metric bundles
    produced over a season (e.g. one :func:`score_round` output per round, or
    any dicts sharing numeric metric keys), report per-metric ``mean``,
    ``median``, ``min``, ``max``, ``last`` and ``trend`` (OLS slope over rounds,
    positive = improving upward) across all rounds.

    Only numeric (``int``/``float``, excluding ``bool``) metric values are
    aggregated; ``None`` values are skipped per-metric so a metric that is
    undefined in early rounds still summarises over the rounds where it exists.
    Returns ``{"n_rounds": int, "metrics": {name: {...}}}``. Empty input yields
    ``{"n_rounds": 0, "metrics": {}}``.
    """
    rounds = list(per_round_metrics)
    if not rounds:
        return {"n_rounds": 0, "metrics": {}}

    # Collect ordered numeric series per metric key.
    series: dict[str, list[float]] = {}
    for rd in rounds:
        for key, val in rd.items():
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                continue
            if val is None:
                continue
            series.setdefault(key, [])
    # Second pass preserving round order, skipping missing/None per metric.
    for key in series:
        vals: list[float] = []
        for rd in rounds:
            v = rd.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v is None:
                continue
            vals.append(float(v))
        series[key] = vals

    metrics: dict[str, object] = {}
    for key, vals in series.items():
        if not vals:
            continue
        ordered = sorted(vals)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 1:
            median = ordered[mid]
        else:
            median = (ordered[mid - 1] + ordered[mid]) / 2
        metrics[key] = {
            "mean": sum(vals) / len(vals),
            "median": median,
            "min": min(vals),
            "max": max(vals),
            "last": vals[-1],
            "trend": _linear_trend(vals),
            "n": len(vals),
        }

    return {"n_rounds": len(rounds), "metrics": metrics}


__all__ = [
    "average_ranks",
    "spearman_correlation",
    "ndcg_at_k",
    "mean_position_error",
    "within_n",
    "score_round",
    "last_order_baseline",
    "brier_score",
    "log_loss",
    "walk_forward_summary",
]
