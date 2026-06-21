"""Championship simulator — probabilistic WDC + WCC forecast.

Given current standings, the calendar of remaining races, and the
per-driver win/podium probabilities for the next race, run a Monte
Carlo over the rest of the season:

  For each MC sample:
    For each remaining race:
      Sample a finishing order via Plackett-Luce on driver "skill".
      Convert order to F1 points (25-18-15-12-10-8-6-4-2-1-0…), add
        +1 for fastest lap (assigned to top-10 random driver), +8 for
        sprint winner on sprint weekends.
      Accumulate per-driver + per-constructor points.
  Aggregate:
    P(driver wins WDC)      = fraction of samples where driver is top
    P(constructor wins WCC) = fraction of samples where constructor is top
    Expected final points + mean final position per entity.

Skill vector
------------
We use the most recent published probabilities (``round_NN.json``) as
the per-race ``win_probability`` distribution.  This is an
approximation — it assumes the same form-card across the rest of the
season — but it is the strongest signal available without re-running
the full ML pipeline for every future round.  When per-round forecasts
become available, replace the single skill vector with a per-round
vector and re-run.

Output
------
``website/public/data/championship_forecast.json`` consumed by the
website's "Who Can Still Win?" tab on the standings page.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STANDINGS_PATH = PROJECT_ROOT / "website" / "public" / "data" / "standings.json"
SEASON_PATH = PROJECT_ROOT / "website" / "public" / "data" / "season.json"
PROBABILITIES_DIR = PROJECT_ROOT / "website" / "public" / "data" / "probabilities"
OUTPUT_PATH = PROJECT_ROOT / "website" / "public" / "data" / "championship_forecast.json"

# F1 standard scoring system (top 10 only; everyone else scores 0).
RACE_POINTS = np.array([25, 18, 15, 12, 10, 8, 6, 4, 2, 1])
SPRINT_POINTS = np.array([8, 7, 6, 5, 4, 3, 2, 1])

DEFAULT_N_SAMPLES = 5000
RNG_SEED = 42
# Temperature on the win-probability vector. We use the next race's
# marginal probabilities as a proxy for ALL remaining races, but
# different circuits favour different drivers — softening the
# distribution acknowledges that variance.  Temperature < 1 flattens
# (skill = p ** temperature, re-normalised); 0.65 was chosen empirically
# so the simulator returns sensible spread without collapsing to a
# uniform distribution.
DEFAULT_SKILL_TEMPERATURE = 0.65
# Default per-driver per-race retirement probability when the round
# JSON does not carry a DNF market.  ~1.5 cars DNF per race
# historically × 22 drivers ≈ 0.07.
DEFAULT_DNF_PROBABILITY = 0.08


@dataclass
class SimulationInputs:
    drivers: list[str]
    driver_full_names: dict[str, str]
    driver_teams: dict[str, str]
    driver_team_colors: dict[str, str]
    current_driver_points: dict[str, float]
    current_constructor_points: dict[str, float]
    win_probabilities: dict[str, float]
    dnf_probabilities: dict[str, float]
    remaining_rounds: list[dict]  # [{round, name, sprint, sprint_laps?, ...}]


def _load_standings(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_season(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_latest_probabilities(directory: Path, last_completed_round: int) -> Optional[dict]:
    """Find the most recent round_NN.json with `round > last_completed_round`.

    The "next race" probabilities are the right skill vector — they
    reflect the model's current take on the form-card.
    """
    if not directory.exists():
        return None
    candidates = sorted(directory.glob("round_*.json"))
    next_round_target = last_completed_round + 1
    chosen: Optional[Path] = None
    for path in candidates:
        try:
            rnd = int(path.stem.split("_")[-1])
        except ValueError:
            continue
        if rnd >= next_round_target:
            chosen = path
            break
    if chosen is None and candidates:
        chosen = candidates[-1]  # fall back to the latest
    if chosen is None:
        return None
    try:
        with chosen.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _build_inputs(
    standings: dict,
    season: dict,
    probabilities: Optional[dict],
) -> SimulationInputs:
    drivers_meta = standings.get("drivers", [])
    driver_codes = [d["driver"] for d in drivers_meta]
    driver_teams = {d["driver"]: d["team"] for d in drivers_meta}
    driver_team_colors = {d["driver"]: d.get("teamColor", "#888") for d in drivers_meta}
    driver_full_names = {d["driver"]: d.get("driverFullName", d["driver"]) for d in drivers_meta}
    current_driver_points = {d["driver"]: float(d["points"]) for d in drivers_meta}

    constructors_meta = standings.get("constructors", [])
    current_constructor_points = {
        c["team"]: float(c["points"]) for c in constructors_meta
    }

    win_probabilities: dict[str, float] = {}
    dnf_probabilities: dict[str, float] = {}
    if probabilities and "markets" in probabilities:
        win_market = probabilities["markets"].get("win", [])
        for entry in win_market:
            drv = entry["driver"]
            p = entry.get("probability", entry.get("rawProbability", 0.0))
            win_probabilities[drv] = max(float(p), 1e-6)
        dnf_market = probabilities["markets"].get("dnf", [])
        for entry in dnf_market:
            drv = entry["driver"]
            p = entry.get("probability", entry.get("rawProbability", 0.0))
            dnf_probabilities[drv] = float(p)
    # Defaults: uniform skill vector + base DNF rate when missing.
    for drv in driver_codes:
        win_probabilities.setdefault(drv, 1.0 / len(driver_codes))
        dnf_probabilities.setdefault(drv, DEFAULT_DNF_PROBABILITY)

    # `season.completedRounds` is unreliable (the exporter sometimes
    # writes the full calendar there); the standings file's
    # `lastUpdatedRound` is the authoritative cursor.
    last_completed = int(standings.get("lastUpdatedRound", 0) or 0)
    calendar = season.get("calendar", [])
    remaining_rounds: list[dict] = []
    for rnd in calendar:
        rnd_num = int(rnd.get("round", 0))
        if rnd_num <= last_completed:
            continue
        remaining_rounds.append(
            {
                "round": rnd_num,
                "name": rnd.get("name"),
                "sprint": bool(rnd.get("sprint", False)),
            }
        )

    return SimulationInputs(
        drivers=driver_codes,
        driver_full_names=driver_full_names,
        driver_teams=driver_teams,
        driver_team_colors=driver_team_colors,
        current_driver_points=current_driver_points,
        current_constructor_points=current_constructor_points,
        win_probabilities=win_probabilities,
        dnf_probabilities=dnf_probabilities,
        remaining_rounds=remaining_rounds,
    )


def _plackett_luce_orderings(
    skill: np.ndarray,
    n_samples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw n_samples finishing orderings via the Gumbel-max trick.

    ``skill`` are per-driver positive numbers ∝ relative win odds.
    Returns an (n_samples, n_drivers) array of driver indices in
    finishing order (idx 0 = winner).
    """
    log_skill = np.log(np.maximum(skill, 1e-12))
    # Sample Gumbel noise per (sample, driver) → ordering = argsort desc.
    gumbel = -np.log(-np.log(rng.uniform(size=(n_samples, skill.shape[0]))))
    perturbed = log_skill[None, :] + gumbel
    return np.argsort(-perturbed, axis=1)


def simulate_championships(
    inputs: SimulationInputs,
    *,
    n_samples: int = DEFAULT_N_SAMPLES,
    seed: int = RNG_SEED,
    skill_temperature: float = DEFAULT_SKILL_TEMPERATURE,
) -> dict:
    rng = np.random.default_rng(seed)
    drivers = inputs.drivers
    n_drivers = len(drivers)
    raw_skill = np.array([inputs.win_probabilities[d] for d in drivers])
    # Temperature softening: skill = p ** temperature, renormalised.
    # Temperature < 1 flattens the distribution (closer to uniform),
    # acknowledging that next-race probabilities don't extrapolate
    # cleanly to all remaining circuits.
    skill = np.power(raw_skill, max(0.05, skill_temperature))
    skill = skill / skill.sum()
    dnf_p = np.array([inputs.dnf_probabilities[d] for d in drivers])

    # Convert constructor list (no duplicates, preserving standings order)
    constructors = list(dict.fromkeys(inputs.driver_teams[d] for d in drivers))
    constructor_index = {c: i for i, c in enumerate(constructors)}
    driver_to_constructor_idx = np.array(
        [constructor_index[inputs.driver_teams[d]] for d in drivers]
    )

    # Per-sample running totals
    driver_points = np.tile(
        np.array([inputs.current_driver_points[d] for d in drivers], dtype=float),
        (n_samples, 1),
    )
    constructor_points = np.zeros((n_samples, len(constructors)), dtype=float)
    for c_idx, c in enumerate(constructors):
        constructor_points[:, c_idx] = inputs.current_constructor_points.get(c, 0.0)

    for race in inputs.remaining_rounds:
        # Per-driver per-sample DNF mask. A DNF'd driver is moved to
        # the back of the order (no points). We compute mask first so
        # the same drivers are excluded from BOTH the race and the
        # sprint within a given sample / race.
        dnf_mask = rng.uniform(size=(n_samples, n_drivers)) < dnf_p[None, :]
        # Build effective skill per sample: DNF drivers get tiny skill
        # so the Gumbel-max sampler pushes them to the rear.
        log_skill_per_sample = np.log(np.maximum(skill, 1e-12))[None, :].repeat(
            n_samples, axis=0
        )
        log_skill_per_sample[dnf_mask] -= 50.0  # heavy negative shift
        gumbel = -np.log(-np.log(rng.uniform(size=(n_samples, n_drivers))))
        orderings = np.argsort(-(log_skill_per_sample + gumbel), axis=1)
        # Allocate race points: positions 0..9 get RACE_POINTS, rest 0.
        race_pts_matrix = np.zeros_like(driver_points)
        for pos in range(min(len(RACE_POINTS), n_drivers)):
            driver_idx_at_pos = orderings[:, pos]
            np.add.at(
                race_pts_matrix,
                (np.arange(n_samples), driver_idx_at_pos),
                RACE_POINTS[pos],
            )
        # Fastest-lap bonus: +1 to a random top-10 driver per sample
        top_ten = orderings[:, : min(10, n_drivers)]
        choose_idx = rng.integers(0, top_ten.shape[1], size=n_samples)
        fl_driver = top_ten[np.arange(n_samples), choose_idx]
        np.add.at(
            race_pts_matrix,
            (np.arange(n_samples), fl_driver),
            1.0,
        )
        if race.get("sprint", False):
            # Independent sprint ordering using the same skill vector
            # but with the SAME DNF mask — a mechanically-DNF car can't
            # come back for the sprint either.
            log_skill_sprint = np.log(np.maximum(skill, 1e-12))[None, :].repeat(
                n_samples, axis=0
            )
            log_skill_sprint[dnf_mask] -= 50.0
            sprint_gumbel = -np.log(-np.log(rng.uniform(size=(n_samples, n_drivers))))
            sprint_orderings = np.argsort(-(log_skill_sprint + sprint_gumbel), axis=1)
            for pos in range(min(len(SPRINT_POINTS), n_drivers)):
                driver_idx_at_pos = sprint_orderings[:, pos]
                np.add.at(
                    race_pts_matrix,
                    (np.arange(n_samples), driver_idx_at_pos),
                    SPRINT_POINTS[pos],
                )
        driver_points += race_pts_matrix
        # Roll constructor points: each driver's race points contribute
        # to their constructor's total.
        constructor_race_pts = np.zeros_like(constructor_points)
        for d_idx in range(n_drivers):
            c_idx = driver_to_constructor_idx[d_idx]
            constructor_race_pts[:, c_idx] += race_pts_matrix[:, d_idx]
        constructor_points += constructor_race_pts

    # Aggregate
    wdc_winners = np.argmax(driver_points, axis=1)
    wcc_winners = np.argmax(constructor_points, axis=1)
    wdc_prob = np.bincount(wdc_winners, minlength=n_drivers) / n_samples
    wcc_prob = np.bincount(wcc_winners, minlength=len(constructors)) / n_samples
    expected_driver_points = driver_points.mean(axis=0)
    expected_constructor_points = constructor_points.mean(axis=0)

    # Final-position rank from each sample (1 = leader)
    driver_final_positions = np.argsort(-driver_points, axis=1).argsort(axis=1) + 1
    expected_driver_position = driver_final_positions.mean(axis=0)

    wdc_forecast = []
    for d_idx, drv in enumerate(drivers):
        wdc_forecast.append(
            {
                "driver": drv,
                "driverFullName": inputs.driver_full_names[drv],
                "team": inputs.driver_teams[drv],
                "teamColor": inputs.driver_team_colors[drv],
                "currentPoints": float(inputs.current_driver_points[drv]),
                "championshipWinProbability": float(wdc_prob[d_idx]),
                "expectedFinalPoints": float(round(expected_driver_points[d_idx], 1)),
                "expectedFinalPosition": float(round(expected_driver_position[d_idx], 2)),
                "p5thPercentilePoints": float(
                    np.percentile(driver_points[:, d_idx], 5)
                ),
                "p95thPercentilePoints": float(
                    np.percentile(driver_points[:, d_idx], 95)
                ),
            }
        )
    wdc_forecast.sort(
        key=lambda r: r["championshipWinProbability"],
        reverse=True,
    )

    wcc_forecast = []
    for c_idx, team in enumerate(constructors):
        # Resolve team color via the first driver on that team.
        first_driver = next(
            (d for d in drivers if inputs.driver_teams[d] == team),
            None,
        )
        team_color = (
            inputs.driver_team_colors.get(first_driver, "#888") if first_driver else "#888"
        )
        wcc_forecast.append(
            {
                "team": team,
                "teamColor": team_color,
                "currentPoints": float(inputs.current_constructor_points.get(team, 0.0)),
                "championshipWinProbability": float(wcc_prob[c_idx]),
                "expectedFinalPoints": float(round(expected_constructor_points[c_idx], 1)),
                "p5thPercentilePoints": float(
                    np.percentile(constructor_points[:, c_idx], 5)
                ),
                "p95thPercentilePoints": float(
                    np.percentile(constructor_points[:, c_idx], 95)
                ),
            }
        )
    wcc_forecast.sort(
        key=lambda r: r["championshipWinProbability"],
        reverse=True,
    )

    return {
        "wdcForecast": wdc_forecast,
        "wccForecast": wcc_forecast,
        "remainingRounds": len(inputs.remaining_rounds),
        "remainingRoundList": inputs.remaining_rounds,
        "monteCarloSamples": n_samples,
        "skillSourceRound": None,  # populated by caller
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--samples", type=int, default=DEFAULT_N_SAMPLES)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--seed", type=int, default=RNG_SEED)
    args = parser.parse_args(argv)

    standings = _load_standings(STANDINGS_PATH)
    season = _load_season(SEASON_PATH)
    last_completed = int(standings.get("lastUpdatedRound", 0) or 0)
    probabilities = _load_latest_probabilities(PROBABILITIES_DIR, last_completed)
    inputs = _build_inputs(standings, season, probabilities)

    if not inputs.remaining_rounds:
        payload = {
            "wdcForecast": [],
            "wccForecast": [],
            "remainingRounds": 0,
            "remainingRoundList": [],
            "monteCarloSamples": 0,
            "skillSourceRound": None,
            "status": "season_complete",
        }
    else:
        payload = simulate_championships(
            inputs, n_samples=args.samples, seed=args.seed
        )
        payload["skillSourceRound"] = (
            probabilities.get("round") if probabilities else None
        )
        payload["status"] = "ok"

    payload["generatedAt"] = (
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    )
    payload["lastCompletedRound"] = last_completed
    payload["note"] = (
        "Monte Carlo simulation of the remaining season. Skill vector "
        "uses the next race's published win probabilities as a proxy "
        "for all remaining rounds; refresh after each GP weekend."
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        json.dump(payload, fh, indent=2)
    print(
        f"✅ championship_forecast.json — "
        f"{payload['remainingRounds']} remaining rounds, "
        f"{payload['monteCarloSamples']} MC samples"
    )
    if payload.get("wdcForecast"):
        top3 = payload["wdcForecast"][:3]
        for row in top3:
            print(
                f"   {row['driver']:>4}  "
                f"P(WDC)={row['championshipWinProbability']:.1%}  "
                f"E[final pts]={row['expectedFinalPoints']:.1f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
