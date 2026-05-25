"""Bayesian hierarchical model for driver-within-team partial pooling.

Why this layer exists
---------------------

The Layer 1 ensemble + the learned race-projection head both treat
drivers as independent units. With ~500 quali samples per season,
that's a lot of variance to estimate per driver — and it's wasteful,
because drivers from the same team share a chassis. The right
statistical primitive for "Hadjar at Racing Bulls vs Hadjar at Red
Bull" reasoning is partial pooling: drivers' skill estimates pull
toward their team mean by a learned amount, with more pulling when
the per-driver sample size is small.

This module exposes a PyMC implementation behind a feature flag.
The model is *optional* — full posterior fitting is comparatively
expensive (~1-3 minutes per refresh on the project's CI runner)
and unstable on tiny samples (the first few rounds of a new
season). When the optional dependency isn't installed, or the
caller hasn't opted in, the module imports cleanly but its
:func:`fit_hierarchical_skill_model` raises a clear error.

Generative model
----------------

    μ_team[t]    ~ Normal(0, σ_team)        # team-level offset
    σ_drv[t]     ~ HalfNormal(σ_pool)       # within-team driver spread
    δ_drv[d]     ~ Normal(0, σ_drv[team_of[d]])  # driver-within-team offset
    y[i]         ~ Normal(μ_team[team_of[d_i]] + δ_drv[d_i], σ_obs)

``y[i]`` is the *deviation* of a driver's finishing position from
the field mean for race ``i``. Centering on the field mean removes
the per-race trend so the posterior is identifiable.

What you get back
-----------------

After fitting, :class:`HierarchicalSkillPosterior` exposes per-driver
mean + std-dev for ``δ_drv`` (driver-relative skill within team) and
per-team mean + std-dev for ``μ_team`` (team strength). Both flow
into the ensemble as features (means) and into the conformal
calibrator as stratum metadata (high-variance drivers → wider
intervals).

Limits
------

* Cold rookies have ``δ_drv ~ 0`` because the posterior pulls them
  toward their team mean — exactly the desired behaviour.
* The model uses NUTS by default; for CI we recommend ADVI for
  speed (set ``method="advi"``).
* The implementation is intentionally minimal — it's a working
  scaffold. Production refinements (regression on race features,
  hierarchical priors on σ_drv) are appropriate follow-ups.

Operational note
----------------

Train weekly with the most recent ``max_history_seasons`` of data
(default 3 — matches the regulation-era window). Cache the
:class:`HierarchicalSkillPosterior` in the model registry under
sentinel round 97.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np


try:
    import pymc as pm  # type: ignore
    import arviz as az  # type: ignore

    _HAS_PYMC = True
except ImportError:  # pragma: no cover - exercised in CI without pymc
    pm = None  # type: ignore
    az = None  # type: ignore
    _HAS_PYMC = False


@dataclass(frozen=True)
class _DriverObservation:
    season: int
    round: int
    driver: str
    team: str
    centred_finish: float  # finish_position minus race mean


@dataclass
class HierarchicalSkillPosterior:
    """Posterior summary suitable for downstream feature extraction."""

    driver_mean: dict[str, float] = field(default_factory=dict)
    driver_std: dict[str, float] = field(default_factory=dict)
    team_mean: dict[str, float] = field(default_factory=dict)
    team_std: dict[str, float] = field(default_factory=dict)
    sigma_obs: float = float("nan")
    method: str = "nuts"
    draws: int = 0

    def driver_skill_feature(
        self,
        driver: str,
        *,
        default: float = 0.0,
    ) -> float:
        return float(self.driver_mean.get(driver, default))

    def driver_uncertainty_feature(
        self,
        driver: str,
        *,
        default: float = 1.0,
    ) -> float:
        return float(self.driver_std.get(driver, default))

    def team_strength_feature(
        self,
        team: str,
        *,
        default: float = 0.0,
    ) -> float:
        return float(self.team_mean.get(team, default))


def _ensure_pymc() -> None:
    if not _HAS_PYMC:
        raise RuntimeError(
            "pymc is not installed. Hierarchical skill modelling is optional; "
            "install with `pip install pymc arviz` to enable. The rest of the "
            "stack continues to work without it."
        )


def _build_observations(
    rows: Iterable[Mapping[str, object]],
) -> list[_DriverObservation]:
    """Center finishing positions per race so the posterior is identifiable."""
    by_race: dict[tuple[int, int], list[Mapping[str, object]]] = {}
    for row in rows:
        season = int(row["season"])
        rnd = int(row["round"])
        by_race.setdefault((season, rnd), []).append(row)
    out: list[_DriverObservation] = []
    for (season, rnd), race_rows in by_race.items():
        finishes = [
            int(r["actual_position"])
            for r in race_rows
            if r.get("actual_position") is not None
        ]
        if not finishes:
            continue
        mean_finish = float(np.mean(finishes))
        for row in race_rows:
            if row.get("actual_position") is None:
                continue
            out.append(
                _DriverObservation(
                    season=season,
                    round=rnd,
                    driver=str(row["driver"]),
                    team=str(row["team"]),
                    centred_finish=float(row["actual_position"]) - mean_finish,
                )
            )
    return out


def fit_hierarchical_skill_model(
    rows: Sequence[Mapping[str, object]],
    *,
    method: str = "advi",
    draws: int = 1000,
    tune: int = 1000,
    target_accept: float = 0.9,
    random_seed: int = 42,
    progressbar: bool = False,
) -> HierarchicalSkillPosterior:
    """Fit the partial-pool model and return a posterior summary.

    ``rows`` is an iterable of dicts with keys
    ``season, round, driver, team, actual_position``. Centering is
    applied internally. Use ``method="advi"`` for fast variational
    inference (CI-friendly) or ``method="nuts"`` for the gold-standard
    HMC sampler.
    """
    _ensure_pymc()

    observations = _build_observations(rows)
    if len(observations) < 20:
        raise ValueError(
            f"hierarchical fit needs >= 20 observations; got {len(observations)}"
        )

    drivers = sorted({o.driver for o in observations})
    teams = sorted({o.team for o in observations})
    drv_idx = {d: i for i, d in enumerate(drivers)}
    team_idx = {t: i for i, t in enumerate(teams)}
    driver_team = {o.driver: o.team for o in observations}

    y_obs = np.array([o.centred_finish for o in observations], dtype=np.float64)
    drv_obs = np.array([drv_idx[o.driver] for o in observations], dtype=np.int64)
    team_obs = np.array([team_idx[o.team] for o in observations], dtype=np.int64)
    team_of_driver = np.array(
        [team_idx[driver_team[d]] for d in drivers], dtype=np.int64
    )

    with pm.Model() as model:  # type: ignore[attr-defined]
        sigma_pool = pm.HalfNormal("sigma_pool", sigma=1.5)
        sigma_team = pm.HalfNormal("sigma_team", sigma=3.0)
        sigma_obs = pm.HalfNormal("sigma_obs", sigma=3.0)

        mu_team = pm.Normal("mu_team", mu=0.0, sigma=sigma_team, shape=len(teams))
        sigma_drv = pm.HalfNormal("sigma_drv", sigma=sigma_pool, shape=len(teams))

        delta_drv = pm.Normal(
            "delta_drv",
            mu=0.0,
            sigma=sigma_drv[team_of_driver],
            shape=len(drivers),
        )

        mu_obs = mu_team[team_obs] + delta_drv[drv_obs]
        pm.Normal("y_obs", mu=mu_obs, sigma=sigma_obs, observed=y_obs)

        if method == "advi":
            approx = pm.fit(
                n=draws,
                method="advi",
                random_seed=random_seed,
                progressbar=progressbar,
            )
            trace = approx.sample(draws, random_seed=random_seed)
        elif method == "nuts":
            trace = pm.sample(
                draws=draws,
                tune=tune,
                target_accept=target_accept,
                random_seed=random_seed,
                progressbar=progressbar,
            )
        else:
            raise ValueError(
                f"method must be 'advi' or 'nuts'; got {method!r}"
            )

    summary = az.summary(trace, var_names=["mu_team", "delta_drv", "sigma_obs"])
    sigma_obs_mean = float(
        summary.loc["sigma_obs", "mean"] if "sigma_obs" in summary.index else float("nan")
    )

    posterior = HierarchicalSkillPosterior(
        method=method,
        draws=int(draws),
        sigma_obs=sigma_obs_mean,
    )

    for d, idx in drv_idx.items():
        key = f"delta_drv[{idx}]"
        if key in summary.index:
            posterior.driver_mean[d] = float(summary.loc[key, "mean"])
            posterior.driver_std[d] = float(summary.loc[key, "sd"])

    for t, idx in team_idx.items():
        key = f"mu_team[{idx}]"
        if key in summary.index:
            posterior.team_mean[t] = float(summary.loc[key, "mean"])
            posterior.team_std[t] = float(summary.loc[key, "sd"])

    return posterior


def attach_posterior_features(
    rows: Iterable[dict],
    posterior: HierarchicalSkillPosterior,
    *,
    driver_key: str = "driver",
    team_key: str = "team",
) -> Iterable[dict]:
    """Inject posterior summaries into a Driver dict iterable.

    Mutates each row in place. Use after the posterior is fitted to
    add features ``hier_driver_skill``, ``hier_driver_uncertainty``,
    ``hier_team_strength``.
    """
    for row in rows:
        d = row.get(driver_key)
        t = row.get(team_key)
        if isinstance(d, str):
            row["hier_driver_skill"] = posterior.driver_skill_feature(d)
            row["hier_driver_uncertainty"] = posterior.driver_uncertainty_feature(d)
        if isinstance(t, str):
            row["hier_team_strength"] = posterior.team_strength_feature(t)
    return rows


__all__ = [
    "HierarchicalSkillPosterior",
    "fit_hierarchical_skill_model",
    "attach_posterior_features",
]
