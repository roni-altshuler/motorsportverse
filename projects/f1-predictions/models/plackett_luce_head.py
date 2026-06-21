"""Convert ranker scores to calibrated win / podium / top-K probabilities
via a temperature-scaled Plackett-Luce factorisation.

Why this exists
---------------
The legacy probability layer derives win probability as an exponential
of the gap-to-leader in predicted lap time
(``f1_prediction_utils.py:1406``). That's a model-free heuristic — it
ignores the rest of the field, can't express "two drivers are within a
tenth and either could win", and has no temperature parameter to tune.

A Plackett-Luce model is the right shape: given a score per driver,
``p(driver finishes first) = exp(score / τ) / Σ exp(score_i / τ)``, and
``p(finishes second | first removed)`` extends the same softmax over
the remaining field. Temperature τ controls how sharp the distribution
is — calibration learns τ from historical (predicted, observed) pairs
so the published probabilities mean what they claim to mean.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class PlackettLuceHead:
    """Score-array → marginal {win, podium, top6, top10} probabilities."""

    temperature: float = 1.0
    rng_seed: int = 42
    n_mc_samples: int = 5000

    def fit_temperature(
        self,
        score_history: list[np.ndarray],
        outcome_history: list[np.ndarray],
        *,
        grid: Iterable[float] = (0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0),
    ) -> float:
        """Pick τ by grid search to minimise log-loss on win prob.

        ``score_history[i]`` and ``outcome_history[i]`` are the scores and
        the finishing positions for race ``i``. We minimise the negative
        log probability of the actual winner under the model.
        """
        best_tau = self.temperature
        best_nll = float("inf")
        for tau in grid:
            nll = 0.0
            n = 0
            for scores, outcomes in zip(score_history, outcome_history):
                if len(scores) == 0:
                    continue
                p_win = self._softmax(scores, tau)
                winner_idx = int(np.argmin(outcomes))  # finish = 1 is winner
                p = max(float(p_win[winner_idx]), 1e-12)
                nll -= np.log(p)
                n += 1
            if n == 0:
                continue
            nll /= n
            if nll < best_nll:
                best_nll = nll
                best_tau = float(tau)
        self.temperature = best_tau
        return best_tau

    @staticmethod
    def _softmax(scores: np.ndarray, tau: float) -> np.ndarray:
        s = np.asarray(scores, dtype=np.float64)
        if tau <= 0:
            raise ValueError("temperature must be > 0")
        z = s / tau
        z -= z.max()  # numerical stability
        ez = np.exp(z)
        return ez / ez.sum()

    def win_probabilities(self, scores: np.ndarray) -> np.ndarray:
        return self._softmax(scores, self.temperature)

    def marginal_probabilities(
        self,
        scores: np.ndarray,
        top_k: tuple[int, ...] = (1, 3, 6, 10),
    ) -> dict[int, np.ndarray]:
        """Marginal Pr(driver finishes in top-K) for each K via Monte Carlo.

        The Plackett-Luce sample is generated efficiently with the Gumbel-max
        trick: ``finishing_order = argsort(scores/τ + Gumbel(0,1))`` per
        sample. This is the same approach the legacy ``export_probabilities.py``
        uses for h2h sampling, kept here to stay consistent.
        """
        scores = np.asarray(scores, dtype=np.float64)
        n = len(scores)
        if n == 0:
            return {k: np.zeros(0) for k in top_k}

        rng = np.random.default_rng(self.rng_seed)
        z = scores / self.temperature
        # (n_mc, n) matrix of perturbed scores
        gumbel = -np.log(-np.log(rng.uniform(size=(self.n_mc_samples, n)) + 1e-12) + 1e-12)
        perturbed = z[None, :] + gumbel
        # argsort descending → predicted finishing order per sample
        orders = np.argsort(-perturbed, axis=1)
        # rank of each driver per sample
        ranks = np.empty_like(orders)
        rows = np.arange(self.n_mc_samples)[:, None]
        ranks[rows, orders] = np.arange(n)[None, :]
        ranks = ranks + 1  # 1-indexed

        return {k: (ranks <= k).mean(axis=0) for k in top_k}
