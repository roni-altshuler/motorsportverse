"""Skill-prior feature replacing the leakage-prone ``PreviousPosition``.

Why this exists
---------------
The legacy pipeline used a ``PreviousPosition`` feature defined as
"finish position in round N-1". Audit findings (see
``/home/ronaltshuler/.claude/plans/you-are-acting-as-declarative-naur.md``)
flag this as a tautological proxy that suppresses learning of structural
features: a driver who was P8 last race but has true pace for P4 keeps
getting predicted as P8 because the model leans on the shortcut.

Replace it with a Bayesian skill prior — a smoothed expectation over
the driver's *body of work*, not a single noisy data point. The
expectation blends three signals strictly drawn from rounds prior to
``current_round`` (leakage assertion at the boundary):

  * **driver_season_mean** — average finish so far this season.
  * **team_strength_index** — average finish across all drivers on the
    team so far this season. Captures "Red Bull is fast right now" even
    for new entrants joining the team.
  * **circuit_specific_history** — the driver's average finish at this
    circuit in prior seasons. Captures "Verstappen at Suzuka" / "Norris
    at Singapore" effects.

The prior is the weighted mean ``(α·driver + β·team + γ·circuit) /
(α+β+γ)``. Default weights are tuned to maximise Spearman ρ on 2024
hold-outs (see ``scripts/tune_ranker.py`` which can also tune these).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

try:
    from ..leakage import assert_prior_only  # type: ignore
except ImportError:  # pragma: no cover — standalone fallback
    def assert_prior_only(rounds_map, current_round, label):  # type: ignore[no-redef]
        max_round = max(rounds_map.keys()) if rounds_map else -1
        if max_round >= current_round:
            raise ValueError(
                f"{label}: saw round {max_round} but current_round={current_round}"
            )


DEFAULT_ALPHA = 0.55  # driver
DEFAULT_BETA = 0.25   # team
DEFAULT_GAMMA = 0.20  # circuit history


@dataclass(frozen=True)
class SkillPriorConfig:
    alpha: float = DEFAULT_ALPHA
    beta: float = DEFAULT_BETA
    gamma: float = DEFAULT_GAMMA
    # Add some shrinkage toward the field mean so a single-data-point sample
    # doesn't dominate. Pseudo-count tunable per blend term.
    driver_pseudo_count: float = 2.0
    team_pseudo_count: float = 3.0
    circuit_pseudo_count: float = 1.5


def attach_skill_priors(
    rows: pd.DataFrame,
    current_round: int,
    *,
    season: int,
    prior_results: dict[int, pd.DataFrame],
    historical_results: pd.DataFrame | None = None,
    circuit_key: str | None = None,
    config: SkillPriorConfig = SkillPriorConfig(),
) -> pd.DataFrame:
    """Add a ``SkillPrior`` column to ``rows`` (one row per driver).

    Parameters
    ----------
    rows :
        DataFrame with at least ``Driver`` and ``Team`` columns; one row per
        driver entering the predicted race.
    current_round :
        Round we are predicting. Used to guard against leakage.
    season :
        Current season year. Used to scope ``prior_results``.
    prior_results :
        Dict of ``{round: DataFrame}`` containing rows for races already run
        in the current season. Each frame must have ``Driver``, ``Team``,
        ``FinishPosition`` columns. Keys must all be < current_round.
    historical_results :
        Optional DataFrame across past seasons with ``Driver``, ``Season``,
        ``Round``, ``CircuitKey``, ``FinishPosition`` columns. Used for the
        per-driver-per-circuit term.
    circuit_key :
        Identifier (e.g. gpKey) for the circuit being predicted. Looked up
        against ``historical_results.CircuitKey``.
    """
    assert_prior_only(prior_results, current_round, "skill_priors")

    field_mean = _field_mean_from_prior(prior_results)

    # ── Per-driver mean across current-season prior rounds ─────────────
    driver_means = _agg_driver_means(prior_results)
    # ── Per-team mean across current-season prior rounds ───────────────
    team_means = _agg_team_means(prior_results)
    # ── Per-driver-per-circuit historical mean across past seasons ─────
    if historical_results is not None and circuit_key is not None:
        circuit_means = _agg_driver_circuit_means(
            historical_results,
            current_season=season,
            current_round=current_round,
            circuit_key=circuit_key,
        )
    else:
        circuit_means = {}

    def _smoothed(value: float | None, pseudo: float) -> float:
        if value is None or not np.isfinite(value):
            return field_mean
        # Bayesian shrinkage toward field_mean with strength `pseudo`
        return (value * 1.0 + field_mean * pseudo) / (1.0 + pseudo)

    out = rows.copy()
    priors = np.empty(len(out), dtype=np.float64)
    components = {"DriverPrior": [], "TeamPrior": [], "CircuitPrior": []}
    for i, row in enumerate(out.itertuples(index=False)):
        driver = getattr(row, "Driver", None)
        team = getattr(row, "Team", None)
        d_prior = _smoothed(driver_means.get(driver), config.driver_pseudo_count)
        t_prior = _smoothed(team_means.get(team), config.team_pseudo_count)
        c_prior = _smoothed(circuit_means.get(driver), config.circuit_pseudo_count)
        components["DriverPrior"].append(d_prior)
        components["TeamPrior"].append(t_prior)
        components["CircuitPrior"].append(c_prior)
        priors[i] = (
            config.alpha * d_prior + config.beta * t_prior + config.gamma * c_prior
        ) / (config.alpha + config.beta + config.gamma)

    out["SkillPrior"] = priors
    out["DriverPrior"] = components["DriverPrior"]
    out["TeamPrior"] = components["TeamPrior"]
    out["CircuitPrior"] = components["CircuitPrior"]
    return out


# ── Aggregation helpers ───────────────────────────────────────────────────
def _field_mean_from_prior(prior_results: dict[int, pd.DataFrame]) -> float:
    parts = [df["FinishPosition"].to_numpy() for df in prior_results.values()
             if "FinishPosition" in df.columns and len(df)]
    if not parts:
        return 10.5  # midfield for a 22-car grid
    arr = np.concatenate(parts)
    arr = arr[np.isfinite(arr)]
    if not len(arr):
        return 10.5
    return float(np.mean(arr))


def _agg_driver_means(prior_results: dict[int, pd.DataFrame]) -> dict[str, float]:
    rows = []
    for df in prior_results.values():
        if {"Driver", "FinishPosition"}.issubset(df.columns):
            rows.append(df[["Driver", "FinishPosition"]])
    if not rows:
        return {}
    cat = pd.concat(rows, ignore_index=True)
    cat = cat.dropna(subset=["FinishPosition"])
    return cat.groupby("Driver")["FinishPosition"].mean().to_dict()


def _agg_team_means(prior_results: dict[int, pd.DataFrame]) -> dict[str, float]:
    rows = []
    for df in prior_results.values():
        if {"Team", "FinishPosition"}.issubset(df.columns):
            rows.append(df[["Team", "FinishPosition"]])
    if not rows:
        return {}
    cat = pd.concat(rows, ignore_index=True)
    cat = cat.dropna(subset=["FinishPosition"])
    return cat.groupby("Team")["FinishPosition"].mean().to_dict()


def _agg_driver_circuit_means(
    historical: pd.DataFrame,
    *,
    current_season: int,
    current_round: int,
    circuit_key: str,
    lookback_seasons: int = 4,
) -> dict[str, float]:
    if historical is None or historical.empty:
        return {}
    needed = {"Driver", "Season", "Round", "CircuitKey", "FinishPosition"}
    if not needed.issubset(historical.columns):
        return {}
    df = historical
    # Strictly prior-only: same circuit, earlier season OR same season earlier round
    same_circuit = df["CircuitKey"] == circuit_key
    earlier_season = df["Season"] < current_season
    same_season_earlier = (df["Season"] == current_season) & (df["Round"] < current_round)
    in_window = df["Season"] >= (current_season - lookback_seasons)
    mask = same_circuit & in_window & (earlier_season | same_season_earlier)
    scoped = df[mask]
    if scoped.empty:
        return {}
    return scoped.groupby("Driver")["FinishPosition"].mean().to_dict()
