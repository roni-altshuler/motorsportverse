"""Guarded promotion logic for the shadow/A-B model pipeline.

Why this exists
---------------
The user explicitly chose the *heavy* MLOps path: production + candidate
ensembles run in parallel, the candidate ships only when the data says so.
This module encodes the "says so" — given two streams of per-round
accuracy metrics, recommend whether to promote, hold, or demote the
candidate.

The mechanism is intentionally conservative.  Promotion ships a model
that's about to predict real races — we'd rather miss a marginal win
than promote a regression.

Variant tagging convention
--------------------------
Registry entries carry an optional ``metadata["variant"]`` field:

* ``"production"`` — current default; what the website renders.  Absent /
  missing field defaults to production for backwards-compat.
* ``"candidate"`` — proposed replacement; trained in parallel, scored in
  parallel, never shipped without a promotion decision.

The promotion rule reads forward_eval JSONs that have been tagged with
the same variant, computes the mean error over the trailing window, and
applies the configured threshold.

Promotion rule v1
-----------------
A candidate is recommended for promotion when **all** of:
  1. It has been scored on at least ``min_rounds_to_decide`` distinct
     rounds (default 5).
  2. Its mean per-round score (lower-is-better) on the trailing window is
     better than production's by at least ``relative_improvement_threshold``
     (default 2%).
  3. There is no round in the window where the candidate is *worse* than
     production by more than ``max_per_round_regression`` (default 20%).
     This guards against a "won on average, blew up in one race" candidate.

When (1) fails → ``"hold"``.  When (1) passes but (2) or (3) fails →
``"hold"``.  Significant *negative* improvement triggers ``"demote"``
(treated symmetrically with promotion thresholds).

Future extensions (not v1)
--------------------------
* Per-market Brier instead of aggregate score — once the probabilities
  layer persists Brier-by-market into the per-round files.
* Multi-armed bandit style allocation (instead of binary production /
  candidate split) — only worth pursuing when there's enough rounds per
  season to support it.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Sequence

LOGGER = logging.getLogger(__name__)

DEFAULT_MIN_ROUNDS_TO_DECIDE: int = 5
DEFAULT_RELATIVE_IMPROVEMENT_THRESHOLD: float = 0.02   # 2% better than production
DEFAULT_MAX_PER_ROUND_REGRESSION: float = 0.20         # block on any 20%+ blowup
DEFAULT_TRAILING_WINDOW: int = 10                      # rolling window for comparison

VARIANT_PRODUCTION: str = "production"
VARIANT_CANDIDATE: str = "candidate"

DECISION_PROMOTE: str = "promote"
DECISION_DEMOTE: str = "demote"
DECISION_HOLD: str = "hold"


@dataclass
class PromotionDecision:
    """Output of ``evaluate_promotion``.

    ``decision`` is one of ``"promote"`` / ``"hold"`` / ``"demote"``.

    The numeric fields (``mean_production``, ``mean_candidate``,
    ``relative_change``) report what the rule actually saw, so the
    website's accuracy panel can render the comparison side-by-side.
    """

    decision: str
    reason: str
    rounds_compared: int
    mean_production: float | None
    mean_candidate: float | None
    relative_change: float | None        # (candidate - production) / production
    worst_round_regression: float | None  # max per-round (cand - prod) / prod
    blocked_by_per_round_guard: bool


@dataclass
class _AlignedScores:
    """Production + candidate scores aligned to common rounds."""

    rounds: list[int]
    production: list[float]
    candidate: list[float]


def _align_by_round(
    production_scores: Sequence[tuple[int, float]],
    candidate_scores: Sequence[tuple[int, float]],
) -> _AlignedScores:
    """Inner-join the two score streams on round number, drop NaN/None,
    and sort ascending."""
    prod_map: dict[int, float] = {}
    for rnd, score in production_scores:
        if score is None or _isnan(score):
            continue
        prod_map[int(rnd)] = float(score)
    cand_map: dict[int, float] = {}
    for rnd, score in candidate_scores:
        if score is None or _isnan(score):
            continue
        cand_map[int(rnd)] = float(score)
    common = sorted(set(prod_map) & set(cand_map))
    return _AlignedScores(
        rounds=common,
        production=[prod_map[r] for r in common],
        candidate=[cand_map[r] for r in common],
    )


def _isnan(value: object) -> bool:
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def evaluate_promotion(
    production_scores: Sequence[tuple[int, float]],
    candidate_scores: Sequence[tuple[int, float]],
    *,
    min_rounds_to_decide: int = DEFAULT_MIN_ROUNDS_TO_DECIDE,
    relative_improvement_threshold: float = DEFAULT_RELATIVE_IMPROVEMENT_THRESHOLD,
    max_per_round_regression: float = DEFAULT_MAX_PER_ROUND_REGRESSION,
    trailing_window: int = DEFAULT_TRAILING_WINDOW,
) -> PromotionDecision:
    """Apply the v1 promotion rule to two aligned score streams.

    Scores are "lower is better" (e.g. RMSE position error or Brier).

    Parameters
    ----------
    production_scores, candidate_scores
        Per-round score lists as ``(round, score)`` tuples.  We
        inner-join on round, drop NaN, and use only rounds present in
        both streams.
    min_rounds_to_decide
        Minimum overlap before any non-hold decision is allowed.
    relative_improvement_threshold
        How much *better* the candidate must be (as a fraction of
        production's score) to recommend promotion.  Default 2%.
    max_per_round_regression
        If any single round in the window has the candidate worse than
        production by more than this fraction, promotion is blocked even
        if the average improvement passes.  Default 20%.
    trailing_window
        How many of the most-recent common rounds to compare on.
    """
    aligned = _align_by_round(production_scores, candidate_scores)
    if len(aligned.rounds) < min_rounds_to_decide:
        return PromotionDecision(
            decision=DECISION_HOLD,
            reason=(
                f"insufficient overlap ({len(aligned.rounds)} common rounds; "
                f"need >= {min_rounds_to_decide})"
            ),
            rounds_compared=len(aligned.rounds),
            mean_production=None,
            mean_candidate=None,
            relative_change=None,
            worst_round_regression=None,
            blocked_by_per_round_guard=False,
        )

    window_rounds = aligned.rounds[-trailing_window:]
    window_prod = aligned.production[-trailing_window:]
    window_cand = aligned.candidate[-trailing_window:]
    mean_prod = sum(window_prod) / len(window_prod)
    mean_cand = sum(window_cand) / len(window_cand)
    if mean_prod <= 0:
        relative_change = 0.0
    else:
        relative_change = (mean_cand - mean_prod) / mean_prod

    # Per-round guard: find the worst per-round regression of the candidate.
    worst_regression = -math.inf
    for prod, cand in zip(window_prod, window_cand):
        if prod <= 0:
            continue
        worst_regression = max(worst_regression, (cand - prod) / prod)
    blocked = worst_regression > max_per_round_regression

    if blocked:
        return PromotionDecision(
            decision=DECISION_HOLD,
            reason=(
                f"per-round guard tripped (worst regression "
                f"{worst_regression:.1%} > {max_per_round_regression:.0%})"
            ),
            rounds_compared=len(window_rounds),
            mean_production=round(mean_prod, 4),
            mean_candidate=round(mean_cand, 4),
            relative_change=round(relative_change, 4),
            worst_round_regression=round(worst_regression, 4),
            blocked_by_per_round_guard=True,
        )

    if relative_change <= -relative_improvement_threshold:
        decision = DECISION_PROMOTE
        reason = (
            f"candidate {abs(relative_change):.1%} better than production "
            f"(threshold {relative_improvement_threshold:.0%})"
        )
    elif relative_change >= relative_improvement_threshold:
        decision = DECISION_DEMOTE
        reason = (
            f"candidate {relative_change:.1%} *worse* than production "
            f"(threshold {relative_improvement_threshold:.0%})"
        )
    else:
        decision = DECISION_HOLD
        reason = (
            f"candidate within ±{relative_improvement_threshold:.0%} of "
            f"production (mean change {relative_change:+.1%})"
        )

    return PromotionDecision(
        decision=decision,
        reason=reason,
        rounds_compared=len(window_rounds),
        mean_production=round(mean_prod, 4),
        mean_candidate=round(mean_cand, 4),
        relative_change=round(relative_change, 4),
        worst_round_regression=round(worst_regression, 4),
        blocked_by_per_round_guard=False,
    )
