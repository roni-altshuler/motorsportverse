#!/usr/bin/env python3
"""Naive-baseline accuracy for honest benchmarking of the F1 model.

The forensic audit (2026-07-07) showed the headline model numbers are only
meaningful *against a bar*. The bar is set by three parameter-free strategies:

  * **grid-order** — predict the finishing order == the qualifying grid
    (winner = pole-sitter). This is the strong post-qualifying baseline every
    model must beat; grid order alone won 6 of 9 winners in 2026.
  * **pole-sitter** — a winner-only view of grid-order (does the pole-sitter win).
  * **points-leader** — predict the current championship points leader wins.

These are computed straight from the published JSON (real qualifying grids in
``rounds/round_NN.json::weekendResults``, official finishing order in
``season_results_<year>.json``) with **no leakage**: round N's baseline uses
only round N's qualifying grid and the championship standings *before* round N.
The result is emitted into ``gp_accuracy_report.json`` under ``baselines`` so the
site (and any evaluator) can always show model-vs-baseline side by side.

This module is pure I/O + arithmetic over already-committed data; it never runs
the ML pipeline, so it is safe to call at export time on completed rounds.
"""
from __future__ import annotations

import json
import os

# 2026 points system (top 10 score). Sprint points intentionally ignored — a
# documented approximation matching the audit's standings baseline.
POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}


def _load_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _is_dnf(status_text):
    """A driver is a DNF/DNS/DSQ when their status is not a bare finishing number."""
    return not str(status_text).strip().isdigit()


def _grid_from_round(round_data):
    """{driver: grid_position} from the committed qualifying session, else {}."""
    for session in (round_data.get("weekendResults") or {}).get("sessions", []):
        if session.get("key") == "qualifying":
            return {
                row["driver"]: int(row["position"])
                for row in session.get("rows", [])
                if row.get("driver") and row.get("position")
            }
    return {}


def _set_overlap_pct(pred_order, actual_pos, cutoff):
    """Set-membership overlap of the predicted top-``cutoff`` vs the actual
    top-``cutoff`` (mirrors advanced_models.podium_points_accuracy)."""
    pred_top = set(pred_order[:cutoff])
    actual_top = {d for d, pos in actual_pos.items() if int(pos) <= cutoff}
    if not actual_top:
        return None, 0, 0
    hits = len(pred_top & actual_top)
    return hits, len(actual_top), hits


def _eval_full_order(pred_pos, actual_pos):
    """Metric family for a *full-order* baseline (grid-order)."""
    common = sorted(set(pred_pos) & set(actual_pos))
    if not common:
        return None
    pred_order = sorted(common, key=lambda d: pred_pos[d])
    act_order = sorted(common, key=lambda d: int(actual_pos[d]))
    winner_hit = pred_order[0] == act_order[0]
    diffs = [abs(pred_pos[d] - int(actual_pos[d])) for d in common]

    podium_hits, podium_total, _ = _set_overlap_pct(pred_order, actual_pos, 3)
    points_hits, points_total, _ = _set_overlap_pct(pred_order, actual_pos, 10)
    podium_pct = round(podium_hits / podium_total * 100, 1) if podium_total else 0.0
    points_pct = round(points_hits / points_total * 100, 1) if points_total else 0.0
    blend = round(0.6 * podium_pct + 0.4 * points_pct, 1)

    return {
        "winnerHit": bool(winner_hit),
        "podiumHits": int(podium_hits or 0),
        "podiumTotal": int(podium_total),
        "top10Overlap": int(points_hits or 0),
        "meanError": round(sum(diffs) / len(diffs), 2),
        "podiumAccuracyPct": podium_pct,
        "pointsAccuracyPct": points_pct,
        "blendPct": blend,
    }


def _points_leader_before(cum_points):
    """Driver with the most championship points so far; None if all zero."""
    if not cum_points or max(cum_points.values(), default=0) == 0:
        return None
    return sorted(cum_points, key=lambda d: (-cum_points[d], d))[0]


def baseline_order_streams(data_dir, season_year, rounds_dir=None):
    """Full finishing-order baseline streams for forward_eval.

    Returns ``{"grid_order": {round: {driver: pos}}, "standings_order": {...}}``.
    ``grid_order`` = round N's real qualifying grid (post-quali information —
    the strong baseline). ``standings_order`` = championship order strictly
    BEFORE round N (its P1 is the "pick the points leader" baseline). Both are
    leakage-safe by construction.
    """
    rounds_dir = rounds_dir or os.path.join(data_dir, "rounds")
    season_results = _load_json(os.path.join(data_dir, f"season_results_{season_year}.json")) or {}

    grid_stream, standings_stream = {}, {}
    cum_points = {}
    for rnd in sorted((int(r) for r in season_results), key=int):
        actual_pos = {d: int(p) for d, p in season_results[str(rnd)].items()}
        round_data = _load_json(os.path.join(rounds_dir, f"round_{rnd:02d}.json")) or {}
        status = round_data.get("actualStatus") or {}

        grid = _grid_from_round(round_data)
        if grid:
            grid_stream[rnd] = grid

        if cum_points and max(cum_points.values()) > 0:
            ordered = sorted(actual_pos, key=lambda d: (-cum_points.get(d, 0), d))
            standings_stream[rnd] = {d: i + 1 for i, d in enumerate(ordered)}

        for drv, pos in actual_pos.items():
            if drv in status and _is_dnf(status[drv]):
                continue
            cum_points[drv] = cum_points.get(drv, 0) + POINTS.get(pos, 0)

    return {"grid_order": grid_stream, "standings_order": standings_stream}


def compute_season_baselines(data_dir, season_year, rounds_dir=None):
    """Compute per-round + season baseline metrics from committed JSON.

    Returns a dict shaped for ``gp_accuracy_report.json`` (see module docstring).
    Only rounds with BOTH an official finishing order and a qualifying grid are
    scored; everything else is skipped so pre-race rounds never pollute the rates.
    """
    rounds_dir = rounds_dir or os.path.join(data_dir, "rounds")
    season_results = _load_json(os.path.join(data_dir, f"season_results_{season_year}.json")) or {}

    grid_perround, pole_perround, leader_perround = {}, {}, {}
    grid_scored, pole_hits, leader_scored, leader_hits = [], 0, 0, 0

    cum_points = {}  # cumulative championship points BEFORE the current round
    for rnd in sorted((int(r) for r in season_results), key=int):
        actual_pos = {d: int(p) for d, p in season_results[str(rnd)].items()}
        round_data = _load_json(os.path.join(rounds_dir, f"round_{rnd:02d}.json")) or {}
        status = round_data.get("actualStatus") or {}
        grid = _grid_from_round(round_data)

        # ── points-leader baseline (uses standings strictly BEFORE this round) ──
        leader = _points_leader_before(cum_points)
        if leader is not None and actual_pos:
            actual_winner = sorted(actual_pos, key=lambda d: actual_pos[d])[0]
            hit = leader == actual_winner
            leader_perround[str(rnd)] = {"winnerHit": bool(hit), "predictedWinner": leader}
            leader_scored += 1
            leader_hits += int(hit)

        # ── grid-order + pole-sitter baselines (use THIS round's real grid) ──
        if grid and actual_pos:
            metrics = _eval_full_order(grid, actual_pos)
            if metrics:
                grid_perround[str(rnd)] = metrics
                grid_scored.append(metrics)
                pole_driver = sorted(grid, key=lambda d: grid[d])[0]
                actual_winner = sorted(actual_pos, key=lambda d: actual_pos[d])[0]
                phit = pole_driver == actual_winner
                pole_perround[str(rnd)] = {"winnerHit": bool(phit), "predictedWinner": pole_driver}
                pole_hits += int(phit)

        # ── advance cumulative points AFTER scoring this round (no leakage) ──
        for drv, pos in actual_pos.items():
            if drv in status and _is_dnf(status[drv]):
                continue  # a positioned-but-retired car does not score
            cum_points[drv] = cum_points.get(drv, 0) + POINTS.get(pos, 0)

    def _season_full(scored):
        if not scored:
            return {"roundsScored": 0}
        n = len(scored)
        return {
            "roundsScored": n,
            "winnerHits": sum(m["winnerHit"] for m in scored),
            "winnerHitRate": round(sum(m["winnerHit"] for m in scored) / n * 100, 1),
            "podiumSetPct": round(sum(m["podiumAccuracyPct"] for m in scored) / n, 1),
            "pointsSetPct": round(sum(m["pointsAccuracyPct"] for m in scored) / n, 1),
            "blendPct": round(sum(m["blendPct"] for m in scored) / n, 1),
            "meanError": round(sum(m["meanError"] for m in scored) / n, 2),
        }

    return {
        "gridOrder": {
            "label": "Qualifying grid order",
            "description": "Predict the finishing order to equal the qualifying grid.",
            "season": _season_full(grid_scored),
            "perRound": grid_perround,
        },
        "poleSitter": {
            "label": "Pole-sitter wins",
            "description": "Predict the pole-sitter to win the race.",
            "season": {
                "roundsScored": len(pole_perround),
                "winnerHits": pole_hits,
                "winnerHitRate": round(pole_hits / len(pole_perround) * 100, 1) if pole_perround else 0.0,
            },
            "perRound": pole_perround,
        },
        "pointsLeader": {
            "label": "Championship points leader wins",
            "description": "Predict the driver leading the championship (before the round) to win.",
            "season": {
                "roundsScored": leader_scored,
                "winnerHits": leader_hits,
                "winnerHitRate": round(leader_hits / leader_scored * 100, 1) if leader_scored else 0.0,
            },
            "perRound": leader_perround,
        },
    }
