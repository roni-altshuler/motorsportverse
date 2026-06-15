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


__all__ = [
    "average_ranks",
    "spearman_correlation",
    "ndcg_at_k",
    "mean_position_error",
    "within_n",
    "score_round",
    "last_order_baseline",
]
