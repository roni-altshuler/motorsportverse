"""Monte Carlo championship projection — sport-agnostic.

Given current points and a strength estimate per competitor, simulate the
remaining rounds many times and report each competitor's probability of winning
the title plus a projected final-points distribution.

Reuses :func:`motorsport_core.calibration.sample_finishing_orders` for the
per-round race sampling (the same Plackett-Luce engine that powers the
single-race probability layer) — no duplicated sampling logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .calibration import DEFAULT_TEMPERATURE, sample_finishing_orders
from .standings import points_for


@dataclass
class TitleProjection:
    """Projected championship outcome for one competitor."""

    key: str
    p_title: float
    current_points: float
    proj_mean: float
    proj_p10: float
    proj_p90: float

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "p_title": round(self.p_title, 4),
            "current_points": self.current_points,
            "proj_mean": round(self.proj_mean, 1),
            "proj_p10": round(self.proj_p10, 1),
            "proj_p90": round(self.proj_p90, 1),
        }


def project_championship(
    current_points: Mapping[str, float],
    strengths: Mapping[str, float],
    remaining_rounds: int,
    points: Mapping[int, float],
    *,
    n_samples: int = 5000,
    temperature: float = DEFAULT_TEMPERATURE,
    seed: int = 42,
    races_per_round: int = 1,
) -> list[TitleProjection]:
    """Monte Carlo the rest of the season.

    Parameters
    ----------
    current_points
        competitor -> points scored so far.
    strengths
        competitor -> score where *lower is better* (e.g. predicted pace /
        rating proxy). Drives the per-race finishing-order sampler.
    remaining_rounds
        How many rounds are left on the calendar.
    points
        Position -> points table.
    races_per_round
        Scored races per round (F2 = 2: sprint + feature).
    n_samples
        Number of full-season simulations.

    Returns one :class:`TitleProjection` per competitor, sorted by ``p_title``.
    """
    competitors = list(strengths.keys())
    base = np.array([float(current_points.get(c, 0.0)) for c in competitors], dtype=float)
    idx = {c: i for i, c in enumerate(competitors)}

    if remaining_rounds <= 0:
        # Season already decided — title goes to the current leader.
        totals = base.copy()
        return _summarize(competitors, current_points, totals[None, :], base)

    total_races = remaining_rounds * max(races_per_round, 1)
    # One big batch of sampled race orders; reshape into (n_samples, races).
    orders = sample_finishing_orders(
        strengths, n_samples=n_samples * total_races, temperature=temperature, seed=seed
    )

    sim_points = np.tile(base, (n_samples, 1))
    cursor = 0
    for _ in range(total_races):
        for s in range(n_samples):
            order = orders[cursor]
            cursor += 1
            for pos, competitor in enumerate(order, start=1):
                sim_points[s, idx[competitor]] += points_for(pos, points)

    return _summarize(competitors, current_points, sim_points, base)


def _summarize(
    competitors: list[str],
    current_points: Mapping[str, float],
    sim_points: np.ndarray,
    base: np.ndarray,
) -> list[TitleProjection]:
    n_samples = sim_points.shape[0]
    winners = np.argmax(sim_points, axis=1)
    win_counts = np.bincount(winners, minlength=len(competitors))
    out: list[TitleProjection] = []
    for i, c in enumerate(competitors):
        col = sim_points[:, i]
        out.append(
            TitleProjection(
                key=c,
                p_title=float(win_counts[i] / n_samples),
                current_points=float(current_points.get(c, 0.0)),
                proj_mean=float(col.mean()),
                proj_p10=float(np.percentile(col, 10)),
                proj_p90=float(np.percentile(col, 90)),
            )
        )
    out.sort(key=lambda t: -t.p_title)
    return out


__all__ = ["TitleProjection", "project_championship"]
