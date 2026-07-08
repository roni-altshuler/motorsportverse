"""Candidate post-quali re-ranker (A/B-gated model-upgrade stream).

Activated by ``F1_CANDIDATE_MODEL=1`` (never on by default). Applies, in the
research-priority order established by the 2026-07-07 audit + research
synthesis, up to three compositional upgrades on top of the production
``RaceProjectionScore``:

  1. ``quali_gap``      — qualifying gap in *seconds* (pct-of-pole,
     session-normalized) as an explicit signal. The production score only sees
     the z-scored quali time; pct-of-pole distinguishes a dominant pole lap
     from a coin-flip front row, so grid trust scales with the actual margin.
  2. ``circuit_priors`` — data-derived grid stickiness from our own warehouse
     build (``features/data/circuit_priors.json``: per-circuit grid→finish
     Spearman + attrition over 2022-2025, Jolpica). Replaces part of the
     hand-coded overtaking guess with measured history, shrunk toward the
     hand value by sample size.
  3. ``dnf``            — per-driver P(DNF) composed via Monte Carlo:
     sample DNFs FIRST (Bernoulli per driver), rank survivors by the pace
     score, send retirees to the back; the mean finishing position over the
     samples is the candidate order. This is the composition pattern
     (Peng et al. 2020) — NOT the previously-benchmarked-negative approach of
     bolting a reliability adjustment onto the point estimate.

Ablation control: ``F1_CANDIDATE_ABLATION`` = comma list of enabled
components. Used by the walk-forward ablation harness to add techniques one
at a time and stop when one hurts.

Walk-forward ablation verdict (2026 R1-9, honest post-quali replay):

  ============================  ======  =======  =====  ======
  stream                        winner  pod/3    MAE    blend
  ============================  ======  =======  =====  ======
  production (regenerated)      5/9     1.56     3.91   60.4
  grid-order baseline           6/9     1.78     3.67   64.4
  A1 quali_gap                  6/9     1.56     3.88   60.4
  A2 + circuit_priors           7/9     1.56     3.87   60.9
  A3 + dnf (full spread)        6/9     1.67     3.93   63.1
  A4 + dnf (damp 0.5)           6/9     1.56     3.92   60.9
  ============================  ======  =======  =====  ======

The DEFAULT is therefore ``quali_gap,circuit_priors`` (the A2 config): it is
the only stream that beats the grid-order baseline on winner-hit. The DNF
composition (``dnf``) stays available opt-in — it trades a winner call for
podium/blend gains (it demotes fragile front-runners whose pace-gap is tiny)
and was REJECTED for the point prediction per the stop-when-it-hurts rule;
its natural home is the probability layer (future work).

Leakage: all season-2026 inputs (driver/team DNF rates, season attrition base
rate) are computed from committed rounds **strictly before** ``round_num``;
circuit priors are 2022-2025 history (a prior about circuits, not about any
2026 round). Enforced with ``leakage.assert_prior_only`` at the boundary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PRIORS_PATH = _PROJECT_ROOT / "features" / "data" / "circuit_priors.json"
_ROUNDS_DIR = _PROJECT_ROOT / "website" / "public" / "data" / "rounds"

# 2026 calendar gp_key → Jolpica circuitId (new venues absent → hand fallback).
GP_KEY_TO_CIRCUIT_ID = {
    "Australia": "albert_park",
    "China": "shanghai",
    "Japan": "suzuka",
    "Miami": "miami",
    "Monaco": "monaco",
    "Canada": "villeneuve",
    "Spain": "catalunya",
    "Austria": "red_bull_ring",
    "Great Britain": "silverstone",
    "Belgium": "spa",
    "Hungary": "hungaroring",
    "Netherlands": "zandvoort",
    "Italy": "monza",
    "Azerbaijan": "baku",
    "Singapore": "marina_bay",
    "United States": "americas",
    "Mexico": "rodriguez",
    "Brazil": "interlagos",
    "Las Vegas": "vegas",
    "Qatar": "losail",
    "Abu Dhabi": "yas_marina",
}

# 2026 is an all-new-PU regulation year: pundit + season-to-date evidence says
# elevated attrition. Season base rate is *learned* from prior rounds and
# shrunk toward this prior.
DNF_BASE_RATE_PRIOR = 0.15
DNF_MC_SAMPLES = 4000
_RNG_SEED = 42

_ALL_COMPONENTS = ("quali_gap", "circuit_priors", "dnf")
# The promoted-candidate configuration (A2): dnf is opt-in only — see the
# ablation table in the module docstring.
_DEFAULT_COMPONENTS = ("quali_gap", "circuit_priors")


def candidate_enabled() -> bool:
    return str(os.getenv("F1_CANDIDATE_MODEL", "0")).strip().lower() in {"1", "true", "yes", "on"}


def candidate_ablation() -> tuple[str, ...]:
    raw = os.getenv("F1_CANDIDATE_ABLATION")
    if raw is None or not str(raw).strip():
        return _DEFAULT_COMPONENTS
    chosen = tuple(p.strip() for p in str(raw).split(",") if p.strip() in _ALL_COMPONENTS)
    return chosen or _DEFAULT_COMPONENTS


def _zscore(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    std = values.std()
    if std == 0 or np.isnan(std):
        return np.zeros_like(values)
    return (values - values.mean()) / std


def load_circuit_prior(gp_key: str, priors_path: Path | None = None) -> dict | None:
    """The 2022-2025 measured prior for a circuit, or None (e.g. Madrid)."""
    path = Path(priors_path) if priors_path else _PRIORS_PATH
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    circuit_id = GP_KEY_TO_CIRCUIT_ID.get(gp_key)
    if not circuit_id:
        return None
    return (payload.get("circuits") or {}).get(circuit_id)


def _is_dnf_status(status) -> bool:
    return not str(status).strip().isdigit()


def collect_season_reliability(round_num: int, rounds_dir: Path | None = None) -> dict:
    """Per-driver / per-team DNF counts from committed rounds STRICTLY < round_num.

    Reads ``round_NN.json::actualStatus`` (+ classification team mapping) —
    historical facts available before round ``round_num``'s race.
    """
    from leakage import assert_prior_only

    rounds_dir = Path(rounds_dir) if rounds_dir else _ROUNDS_DIR
    per_round: dict[int, dict] = {}
    for path in sorted(rounds_dir.glob("round_*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        rnd = int(payload.get("round", 0) or 0)
        if rnd <= 0 or rnd >= int(round_num):
            continue
        status = payload.get("actualStatus") or {}
        if not status:
            continue
        teams = {
            str(e.get("driver")): str(e.get("team"))
            for e in payload.get("classification", [])
            if isinstance(e, dict) and e.get("driver")
        }
        per_round[rnd] = {"status": status, "teams": teams}

    assert_prior_only(per_round, int(round_num), "candidate_reliability_rounds")

    driver_starts: dict[str, int] = {}
    driver_dnfs: dict[str, int] = {}
    team_starts: dict[str, int] = {}
    team_dnfs: dict[str, int] = {}
    total_starts = 0
    total_dnfs = 0
    for rnd, data in per_round.items():
        for drv, status in data["status"].items():
            dnf = _is_dnf_status(status)
            driver_starts[drv] = driver_starts.get(drv, 0) + 1
            driver_dnfs[drv] = driver_dnfs.get(drv, 0) + int(dnf)
            team = data["teams"].get(drv)
            if team:
                team_starts[team] = team_starts.get(team, 0) + 1
                team_dnfs[team] = team_dnfs.get(team, 0) + int(dnf)
            total_starts += 1
            total_dnfs += int(dnf)

    return {
        "rounds_seen": len(per_round),
        "driver_starts": driver_starts,
        "driver_dnfs": driver_dnfs,
        "team_starts": team_starts,
        "team_dnfs": team_dnfs,
        "total_starts": total_starts,
        "total_dnfs": total_dnfs,
    }


def compute_dnf_probabilities(drivers, teams_by_driver, reliability, circuit_prior) -> dict:
    """Blend season base rate, team reliability, driver incident rate and the
    historical circuit attrition into per-driver P(DNF). All rates shrink
    toward the base by sample size (cold-start safe)."""
    total_starts = reliability.get("total_starts", 0)
    # Season-learned base rate, shrunk toward the regulation-era prior.
    base = (
        (reliability.get("total_dnfs", 0) + DNF_BASE_RATE_PRIOR * 40.0)
        / (total_starts + 40.0)
        if total_starts
        else DNF_BASE_RATE_PRIOR
    )
    circuit_rate = None
    if circuit_prior and circuit_prior.get("dnfRate") is not None:
        circuit_rate = float(circuit_prior["dnfRate"])
    # Circuit-adjusted base: half season pattern, half circuit history.
    circuit_base = 0.5 * base + 0.5 * circuit_rate if circuit_rate is not None else base

    out = {}
    k_drv, k_team = 4.0, 6.0
    for drv in drivers:
        d_starts = reliability["driver_starts"].get(drv, 0)
        d_rate = (
            (reliability["driver_dnfs"].get(drv, 0) + base * k_drv) / (d_starts + k_drv)
        )
        team = teams_by_driver.get(drv)
        t_starts = reliability["team_starts"].get(team, 0)
        t_rate = (
            (reliability["team_dnfs"].get(team, 0) + base * k_team) / (t_starts + k_team)
        )
        p = 0.45 * circuit_base + 0.30 * t_rate + 0.25 * d_rate
        out[drv] = float(np.clip(p, 0.04, 0.40))
    return out


def dnf_composed_mean_finish(strength: np.ndarray, p_dnf: np.ndarray,
                             n_samples: int = DNF_MC_SAMPLES,
                             seed: int = _RNG_SEED) -> np.ndarray:
    """Monte Carlo composition: sample DNFs first, rank survivors by strength.

    ``strength``: higher = faster. Retirees fill the last positions (random
    order among themselves — lap counts at retirement are unknowable pre-race).
    Returns the mean finishing position per driver.
    """
    n = len(strength)
    rng = np.random.default_rng(seed)
    order_by_strength = np.argsort(-strength, kind="stable")
    finish_sum = np.zeros(n)
    for _ in range(n_samples):
        dnf_mask = rng.random(n) < p_dnf
        pos = np.empty(n, dtype=float)
        survivors = [i for i in order_by_strength if not dnf_mask[i]]
        retirees = np.flatnonzero(dnf_mask)
        rng.shuffle(retirees)
        for rank, idx in enumerate(survivors, start=1):
            pos[idx] = rank
        for rank, idx in enumerate(retirees, start=len(survivors) + 1):
            pos[idx] = rank
        finish_sum += pos
    return finish_sum / n_samples


def apply_candidate_reranking(merged, *, round_num, gp_key, rain_probability=0.0,
                              hand_pole_lock=None, rounds_dir=None,
                              priors_path=None):
    """Re-rank ``merged`` with the enabled candidate components.

    Modifies ``RaceProjectionScore``/``RaceProjectionTime`` in place-copy and
    returns ``(merged, config)`` where ``config`` documents what was applied
    (recorded in ``modelConfig.candidate`` — additive schema).
    """
    components = candidate_ablation()
    config = {"applied": True, "components": list(components)}
    merged = merged.copy()

    score = merged["RaceProjectionScore"].to_numpy(dtype=float)

    # ── 1. Qualifying gap in seconds (pct of pole) ──────────────────────────
    if "quali_gap" in components and "AdjustedQualiTime" in merged.columns:
        quali = merged["AdjustedQualiTime"].to_numpy(dtype=float)
        pole = np.nanmin(quali)
        gap_pct = np.clip((quali - pole) / pole, 0.0, 0.06)
        w_gap = 0.15
        score = score + _zscore(gap_pct) * w_gap
        config["qualiGap"] = {"weight": w_gap, "maxGapPct": round(float(gap_pct.max()), 4)}

    # ── 2. Data-derived circuit grid-trust prior ────────────────────────────
    if "circuit_priors" in components and hand_pole_lock is not None \
            and "QualifyingRank" in merged.columns:
        prior = load_circuit_prior(gp_key, priors_path)
        if prior:
            n_races = float(prior.get("races", 0))
            stick_hand = float(hand_pole_lock) / 0.95 if hand_pole_lock else 0.5
            stick_data = float(np.clip(prior["gridFinishSpearman"], 0.0, 1.0))
            k = 4.0
            stick_blend = (n_races * stick_data + k * stick_hand) / (n_races + k)
            pole_lock_data = 0.95 * stick_blend * (1.0 - 0.25 * float(rain_probability))
            delta = float(np.clip(pole_lock_data - float(hand_pole_lock), -0.35, 0.35))
            grid_rank = merged["QualifyingRank"].fillna(merged["QualifyingRank"].max())
            score = score + _zscore(grid_rank.to_numpy(dtype=float)) * delta
            config["circuitPriors"] = {
                "gridFinishSpearman": stick_data,
                "handPoleLock": round(float(hand_pole_lock), 4),
                "dataPoleLock": round(pole_lock_data, 4),
                "deltaApplied": round(delta, 4),
            }
        else:
            config["circuitPriors"] = {"applied": False, "reason": "no prior for circuit"}

    merged["RaceProjectionScore"] = score

    # ── 3. DNF composition (sample DNFs first, rank survivors by pace) ──────
    if "dnf" in components:
        drivers = merged["Driver"].tolist()
        teams = (
            dict(zip(merged["Driver"], merged["Team"]))
            if "Team" in merged.columns else {}
        )
        reliability = collect_season_reliability(round_num, rounds_dir)
        circuit_prior = load_circuit_prior(gp_key, priors_path)
        p_dnf_map = compute_dnf_probabilities(drivers, teams, reliability, circuit_prior)
        p_dnf = np.array([p_dnf_map[d] for d in drivers], dtype=float)
        # Spread dampening: 1.0 = use the full per-driver differences; smaller
        # values shrink everyone toward the field mean so DNF risk re-ranks
        # only materially fragile cars (walk-forward showed the full spread
        # can dethrone a rightful winner pick on tiny front-row pace gaps).
        damp = float(np.clip(float(os.getenv("F1_CANDIDATE_DNF_DAMP", "1.0") or 1.0), 0.0, 1.0))
        if damp < 1.0:
            p_dnf = np.clip(p_dnf.mean() + damp * (p_dnf - p_dnf.mean()), 0.02, 0.45)
        strength = -_zscore(score)  # lower score = faster
        mean_finish = dnf_composed_mean_finish(strength, p_dnf)
        merged["CandidateMeanFinish"] = mean_finish
        merged["CandidateDnfProbability"] = p_dnf
        # Mean finish is the candidate ORDER; keep score spacing for downstream
        # consumers by re-anchoring the score to the mean-finish ranking.
        score = _zscore(mean_finish)
        merged["RaceProjectionScore"] = score
        config["dnf"] = {
            "dampening": damp,
            "roundsSeen": reliability["rounds_seen"],
            "seasonBaseRate": round(
                reliability["total_dnfs"] / reliability["total_starts"], 4
            ) if reliability["total_starts"] else None,
            "meanPDnf": round(float(p_dnf.mean()), 4),
            "mcSamples": DNF_MC_SAMPLES,
        }

    # Re-derive RaceProjectionTime from the (possibly re-ranked) score so the
    # classification sort + gaps follow the candidate order.
    if "PredictedLapTime" in merged.columns:
        merged["RaceProjectionTime"] = (
            float(merged["PredictedLapTime"].min()) + 1.15 + _zscore(score) * 0.85
        )
    return merged, config
