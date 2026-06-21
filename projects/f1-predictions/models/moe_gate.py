"""Learned mixture-of-experts gating for the regime-routed engine.

Replaces the rule-based regime classifier from Phase 5 with a small
learned softmax gate over K experts. The gate is fit on prior-rounds
expert predictions to minimise per-round winner negative log-likelihood
of the fused probability.

Architecture
------------
::

    z = W · x + b        # linear projection, W in R^(K x d), b in R^K
    w = softmax(z)       # K expert weights summing to 1
    P_final = Σ_e w[e] · P_expert_e

where ``x`` is a per-round feature vector and the experts produce
per-driver probability arrays.

Loss
----
For one training round (features x, expert P_win arrays, winner index):

* ``fused_p[j] = Σ_e w[e] · P_e[j]``
* ``L = -log(fused_p[winner])``

Total objective is the mean over training rounds plus an L2 penalty on
``W`` (not on biases). With only ~48 historical rounds available, the
gate is at serious overfitting risk; the L2 coefficient defaults to
0.5 which empirically suppresses spurious-feature pickups.

Training is done by ``scipy.optimize.minimize`` with method
``L-BFGS-B`` and a hand-coded analytic gradient (no autograd
dependency).

Leak-safety
-----------
The gate is trained on cached prior-round predictions. The cache is
populated round-by-round as the benchmark loop progresses, so every
round used for training was itself produced via leak-safe expert
predictions. The gate at test round (s, r) sees only the cache slice
strictly prior to (s, r).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize


DEFAULT_FEATURE_NAMES: tuple[str, ...] = (
    "round_normalized",
    "mean_maturity",
    "volatility",
    "qualifying_dispersion",
    "archetype_qualifying_importance",
)

DEFAULT_EXPERT_NAMES: tuple[str, ...] = (
    "elite_head",
    "early_fusion",
    "mid_fusion",
    "late_fusion",
    "probabilistic_v_for_elite",
)


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


@dataclass
class TrainingExample:
    """One historical round packaged for gate training."""

    features: np.ndarray            # shape (d,)
    expert_p_win: np.ndarray         # shape (K, n_drivers) — per-expert P(win)
    expert_p_pod: np.ndarray         # shape (K, n_drivers) — per-expert P(podium)
    winner_idx: int                 # index into the n_drivers dim
    drivers: list[str] = field(default_factory=list)


class LearnedGate:
    """Linear softmax MoE gate.

    Parameters
    ----------
    n_experts
        K — number of experts.
    n_features
        d — feature dimension.
    l2
        L2 regularization coefficient on the projection matrix (not on
        biases).
    eps
        Numerical floor on the fused probability inside the log.
    """

    def __init__(
        self,
        n_experts: int,
        n_features: int,
        *,
        l2: float = 0.5,
        eps: float = 1e-9,
    ) -> None:
        self.n_experts = int(n_experts)
        self.n_features = int(n_features)
        self.l2 = float(l2)
        self.eps = float(eps)
        # W shape (K, d), b shape (K,)
        self.W: np.ndarray = np.zeros((self.n_experts, self.n_features))
        self.b: np.ndarray = np.zeros(self.n_experts)
        self.is_fitted: bool = False
        self.train_history: list[dict] = []

    # --------------------------------------------------------------- #
    # Loss + gradient
    # --------------------------------------------------------------- #

    def _unpack(self, theta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        K, d = self.n_experts, self.n_features
        W = theta[: K * d].reshape((K, d))
        b = theta[K * d :]
        return W, b

    def _pack(self, W: np.ndarray, b: np.ndarray) -> np.ndarray:
        return np.concatenate([W.ravel(), b.ravel()])

    def _loss_and_grad(
        self, theta: np.ndarray, examples: list[TrainingExample]
    ) -> tuple[float, np.ndarray]:
        W, b = self._unpack(theta)
        total_loss = 0.0
        dW = np.zeros_like(W)
        db = np.zeros_like(b)
        n = len(examples)
        if n == 0:
            return 0.0, self._pack(dW, db)
        for ex in examples:
            x = ex.features
            z = W @ x + b
            w_gate = _softmax(z)
            p_win_per_expert = ex.expert_p_win[:, ex.winner_idx]  # shape (K,)
            fused_p = float(np.dot(w_gate, p_win_per_expert))
            fused_p = max(fused_p, self.eps)
            total_loss += -np.log(fused_p)
            # dL/dw_e = -p_e / fused_p
            dL_dw = -p_win_per_expert / fused_p
            # softmax gradient: dL/dz_e = w_e · (dL/dw_e - Σ_k w_k · dL/dw_k)
            dot = float(np.dot(w_gate, dL_dw))
            dL_dz = w_gate * (dL_dw - dot)
            # dL/dW[e, j] = dL/dz[e] · x[j]
            dW += np.outer(dL_dz, x)
            db += dL_dz
        # mean reduction
        total_loss /= n
        dW /= n
        db /= n
        # L2 on W
        total_loss += 0.5 * self.l2 * float(np.sum(W * W))
        dW += self.l2 * W
        return float(total_loss), self._pack(dW, db)

    # --------------------------------------------------------------- #
    # Fit / predict
    # --------------------------------------------------------------- #

    def fit(
        self,
        examples: list[TrainingExample],
        *,
        max_iter: int = 200,
    ) -> "LearnedGate":
        """Train the gate by minimising mean per-round winner NLL + L2.

        Resets internal state on each call (so the benchmark loop can
        re-fit per test round on the cache slice strictly prior to that
        round).
        """
        if not examples:
            # Nothing to learn from — leave W, b at zeros so softmax
            # returns uniform weights.
            self.W = np.zeros((self.n_experts, self.n_features))
            self.b = np.zeros(self.n_experts)
            self.is_fitted = False
            return self
        theta0 = self._pack(self.W, self.b)
        result = minimize(
            fun=lambda t: self._loss_and_grad(t, examples),
            x0=theta0,
            jac=True,
            method="L-BFGS-B",
            options={"maxiter": max_iter},
        )
        W, b = self._unpack(result.x)
        self.W = W
        self.b = b
        self.is_fitted = True
        self.train_history.append(
            {
                "n_examples": len(examples),
                "final_loss": float(result.fun),
                "converged": bool(result.success),
            }
        )
        return self

    def predict_weights(self, features: np.ndarray) -> np.ndarray:
        """Return softmax expert weights for a single round's features."""
        x = np.asarray(features, dtype=float)
        if x.shape != (self.n_features,):
            raise ValueError(
                f"feature shape {x.shape} != expected ({self.n_features},)"
            )
        if not self.is_fitted:
            # Uninformed prior: uniform.
            return np.full(self.n_experts, 1.0 / self.n_experts)
        z = self.W @ x + self.b
        return _softmax(z)


# --------------------------------------------------------------------------- #
# Feature extraction
# --------------------------------------------------------------------------- #


def build_gate_features(
    *,
    round_index: int,
    volatility: float,
    mean_maturity: float,
    qualifying_dispersion: float,
    archetype_qualifying_importance: float,
    max_round: int = 24,
) -> np.ndarray:
    """Pack the per-round feature vector in :data:`DEFAULT_FEATURE_NAMES` order.

    All inputs are scalars known at prediction time without leaking
    future data:

    * ``round_index`` comes from the calendar
    * ``volatility`` is the leak-safe Layer-2 model output
    * ``mean_maturity`` is computed from the prior driver-history slice
    * ``qualifying_dispersion`` is std(predicted_lap_time) /
      mean(predicted_lap_time) within the round frame (current-round,
      not historical)
    * ``archetype_qualifying_importance`` is a static circuit prior
    """
    return np.array(
        [
            float(round_index) / float(max(1, max_round)),
            float(mean_maturity),
            float(np.clip(volatility, 0.0, 1.0)),
            float(qualifying_dispersion),
            float(archetype_qualifying_importance),
        ],
        dtype=float,
    )


__all__ = [
    "DEFAULT_FEATURE_NAMES",
    "DEFAULT_EXPERT_NAMES",
    "TrainingExample",
    "LearnedGate",
    "build_gate_features",
]
