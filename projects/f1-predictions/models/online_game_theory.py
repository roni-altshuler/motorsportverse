"""Online-learning hook for the game-theory coefficients (A-P2.1).

Why this exists
---------------
The audit flagged ``RaceProjectionScore`` 's game-theory terms (undercut,
overcut, teammate_conflict, DRS overtake, field-volatility, …) as
*hand-tuned* — fit on three rounds via
``optimize_game_theory_postprocessing.py`` and never updated again.  This
module replaces the static fit with a tiny online learner that:

  1. Reads the last round's actual finishing order.
  2. Computes per-driver residuals (actual − pure-pace prediction).
  3. Regresses the residual against each game-theory term using ridge
     regression.
  4. Exponentially blends the new coefficients with the prior so the
     learner has memory but doesn't lock onto early-season anomalies.
  5. Persists the updated coefficients to the model registry.

At apply time, ``apply_race_postprocessing`` reads the latest registered
coefficient set and multiplies term-wise.  When no learned set exists
(fresh repo, registry disabled), the legacy hard-coded coefficients
stay in force.

Term catalogue
--------------
Mirrors the seven terms in [f1_prediction_utils.py:1100-1145].  Adding
a new term means: (a) compute it on the prediction side, (b) add a
column to ``TERM_NAMES`` here, (c) the learner picks it up
automatically.

Constraints
-----------
* Tiny in scope — pure linear blend + ridge, no scikit pipeline gymnastics.
* Deterministic given a seed; reproducible across CI runs.
* Registry-backed via the existing ``models/registry.py`` (round=98
  sentinel keeps the entry out of per-weekend slots).
"""
from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Iterable, Sequence

import numpy as np

LOGGER = logging.getLogger(__name__)

GAME_THEORY_REGISTRY_ROUND: int = 98
GAME_THEORY_METADATA_KIND: str = "game-theory-coefficients"

# Term names tracked by the learner.  Each one maps to a column on the
# per-driver feature DataFrame ``merged`` that f1_prediction_utils
# produces at race-projection time.  Adding a new term: add it here and
# ensure the column exists upstream.
TERM_NAMES: tuple[str, ...] = (
    "UndercutEdgeAhead",
    "OvercutEdgeBehind",
    "TeamOrderPressure",
    "TeammateConflictRisk",
    "FieldPositionVolatility",
    "LocalBattleIntensity",
    "DRSOvertakeProbAhead",
)

# Legacy coefficients (matching the hand-tuned values in
# f1_prediction_utils::apply_race_postprocessing).  Used as the prior and
# as the production fallback when no learned coefficients exist yet.
LEGACY_COEFFICIENTS: dict[str, float] = {
    "UndercutEdgeAhead": -0.30,
    "OvercutEdgeBehind": -0.20,
    "TeamOrderPressure": -0.15,
    "TeammateConflictRisk": -0.18,
    "FieldPositionVolatility": 0.028,
    "LocalBattleIntensity": 0.10,
    "DRSOvertakeProbAhead": -0.12,
}

# Ridge regularisation strength.  We have at most ~22 driver-rows per
# round; without ridge the fit will overfit early-season noise.
DEFAULT_RIDGE_ALPHA: float = 1.0

# Exponential blend weight for new coefficients.  At α=0.30, the
# coefficient half-life is ~2 rounds.  Higher α = more reactive to the
# latest race; lower α = closer to the LEGACY anchor.
DEFAULT_BLEND_ALPHA: float = 0.30


@dataclass
class GameTheoryCoefficients:
    """A frozen snapshot of the learner's current coefficients."""

    coefficients: dict[str, float] = field(default_factory=lambda: dict(LEGACY_COEFFICIENTS))
    rounds_seen: int = 0
    last_residual_rmse: float | None = None
    last_updated_season: int | None = None
    last_updated_round: int | None = None

    @classmethod
    def from_legacy(cls) -> "GameTheoryCoefficients":
        return cls(coefficients=dict(LEGACY_COEFFICIENTS), rounds_seen=0)

    def to_jsonable(self) -> dict:
        return asdict(self)


def _ridge_fit(
    X: np.ndarray, y: np.ndarray, alpha: float = DEFAULT_RIDGE_ALPHA
) -> np.ndarray:
    """Closed-form ridge regression — no scikit needed for a tiny problem.

    β = (XᵀX + αI)⁻¹ Xᵀ y
    """
    if X.size == 0:
        return np.zeros(X.shape[1] if X.ndim == 2 else 0)
    n_features = X.shape[1]
    gram = X.T @ X + alpha * np.eye(n_features)
    try:
        return np.linalg.solve(gram, X.T @ y)
    except np.linalg.LinAlgError:
        return np.zeros(n_features)


def update_from_round(
    prior: GameTheoryCoefficients,
    terms: dict[str, Sequence[float]],
    residuals: Sequence[float],
    *,
    blend_alpha: float = DEFAULT_BLEND_ALPHA,
    ridge_alpha: float = DEFAULT_RIDGE_ALPHA,
    season: int | None = None,
    round_num: int | None = None,
) -> GameTheoryCoefficients:
    """Blend new ridge-fitted coefficients into the running estimate.

    Parameters
    ----------
    prior
        Coefficient state before this round.
    terms
        Per-driver values for each term name (keyed by TERM_NAMES).
        Missing terms inherit the legacy coefficient at blend time —
        we don't penalise omission.
    residuals
        ``actual_finish - predicted_finish`` per driver, in the same
        order as the term arrays.  This is what the regression tries to
        explain via the game-theory terms.
    blend_alpha
        How heavily to weight the new fit.  ``0`` = no learning; ``1`` =
        the new fit replaces the prior outright.
    ridge_alpha
        L2 strength for the per-round fit.
    """
    residual_arr = np.asarray(list(residuals), dtype=np.float64)
    n_rows = len(residual_arr)
    if n_rows < 4:
        # Too few rows to fit anything meaningful — keep the prior.
        return GameTheoryCoefficients(
            coefficients=dict(prior.coefficients),
            rounds_seen=prior.rounds_seen,
            last_residual_rmse=None,
            last_updated_season=season,
            last_updated_round=round_num,
        )

    cols = [t for t in TERM_NAMES if t in terms and len(list(terms[t])) == n_rows]
    if not cols:
        return GameTheoryCoefficients(
            coefficients=dict(prior.coefficients),
            rounds_seen=prior.rounds_seen,
            last_residual_rmse=None,
            last_updated_season=season,
            last_updated_round=round_num,
        )
    X = np.column_stack([np.asarray(terms[c], dtype=np.float64) for c in cols])
    # Centre the design matrix so the bias falls out of the fit.
    X_centred = X - X.mean(axis=0, keepdims=True)
    y_centred = residual_arr - residual_arr.mean()

    beta = _ridge_fit(X_centred, y_centred, alpha=ridge_alpha)
    fit_residual = y_centred - X_centred @ beta
    rmse = float(math.sqrt(float(np.mean(fit_residual**2))))

    new_coeffs = dict(prior.coefficients)
    for col, b in zip(cols, beta):
        prior_value = prior.coefficients.get(col, LEGACY_COEFFICIENTS.get(col, 0.0))
        new_coeffs[col] = (1 - blend_alpha) * prior_value + blend_alpha * float(b)

    return GameTheoryCoefficients(
        coefficients=new_coeffs,
        rounds_seen=prior.rounds_seen + 1,
        last_residual_rmse=rmse,
        last_updated_season=season,
        last_updated_round=round_num,
    )


def walk_history(
    initial: GameTheoryCoefficients | None,
    round_inputs: Iterable[dict],
    *,
    blend_alpha: float = DEFAULT_BLEND_ALPHA,
    ridge_alpha: float = DEFAULT_RIDGE_ALPHA,
) -> GameTheoryCoefficients:
    """Apply ``update_from_round`` over a sequence of historical rounds.

    Each ``round_inputs`` element is a dict with keys ``season``,
    ``round``, ``terms``, ``residuals``.  The learner runs forward in
    time so each round's coefficients see only prior data — leakage
    discipline holds at the level of the coefficient set.
    """
    state = initial or GameTheoryCoefficients.from_legacy()
    for entry in round_inputs:
        state = update_from_round(
            state,
            entry.get("terms", {}),
            entry.get("residuals", []),
            blend_alpha=blend_alpha,
            ridge_alpha=ridge_alpha,
            season=entry.get("season"),
            round_num=entry.get("round"),
        )
    return state
