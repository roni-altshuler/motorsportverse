#!/usr/bin/env python3
"""Benchmark the Priority-3 volatility model against actual 2026 race chaos.

Validates two things on rounds 1-5:
  1. volatility_score vs actual position shuffle (mean |pred-actual| per round)
     — does the score rank clean vs chaotic races correctly?
  2. predicted safety_car_probability vs actual SC/VSC occurrence.

Empirical SC/VSC/red rates are aggregated from FastF1 track_status across
cached seasons for the 2026 circuits. Reads only.
"""
import os
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("F1_REGISTRY_ENABLED", "0")
logging.getLogger("fastf1").setLevel(logging.ERROR)

import numpy as np  # noqa: E402
import fastf1  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from models.race_volatility import (circuit_volatility,  # noqa: E402
                                    compute_circuit_status_rates,
                                    SC_CODE, VSC_CODES)

fastf1.Cache.enable_cache("f1_cache")
GP = {1: "Australia", 2: "China", 3: "Japan", 4: "Miami", 5: "Canada"}
# Actual position shuffle per round (mean |pred-actual|) from the audit.
ACTUAL_SHUFFLE = {1: 6.36, 2: 4.64, 3: 2.00, 4: 4.18, 5: 5.36}


def track_status_loader(year, gp_key):
    s = fastf1.get_session(year, gp_key, "R")
    s.load(laps=True, telemetry=False, weather=False, messages=False)
    ts = getattr(s, "track_status", None)
    if ts is None or len(ts) == 0:
        return None
    return list(ts["Status"].astype(str))


def actual_sc(year, gp_key):
    codes = track_status_loader(year, gp_key) or []
    s = set(codes)
    return {"sc": int(SC_CODE in s),
            "vsc_or_sc": int(SC_CODE in s or any(c in s for c in VSC_CODES))}


def main():
    # Empirical rates across cached seasons for the 2026 circuits.
    seasons = [2023, 2024, 2025, 2026]
    pairs = [(yr, GP[r]) for yr in seasons for r in GP]
    empirical = compute_circuit_status_rates(track_status_loader, pairs)

    rows = []
    for r in range(1, 6):
        gp = GP[r]
        v = circuit_volatility(gp, empirical=empirical)
        act = actual_sc(2026, gp)
        rows.append({
            "round": r, "gp": gp,
            "volatility_score": round(v.volatility_score, 3),
            "pred_sc_prob": round(v.safety_car_probability, 3),
            "n_empirical": v.n_empirical,
            "actual_shuffle": ACTUAL_SHUFFLE[r],
            "actual_sc": act["sc"],
            "actual_sc_or_vsc": act["vsc_or_sc"],
        })

    vol = [x["volatility_score"] for x in rows]
    shuffle = [x["actual_shuffle"] for x in rows]
    rho, p = spearmanr(vol, shuffle)

    # SC probability vs actual SC/VSC occurrence (Brier).
    sc_pred = np.array([x["pred_sc_prob"] for x in rows])
    sc_act = np.array([x["actual_sc_or_vsc"] for x in rows])
    sc_brier = float(np.mean((sc_pred - sc_act) ** 2))

    result = {
        "per_round": rows,
        "volatility_vs_shuffle_spearman": {"rho": round(float(rho), 3),
                                           "p_value": round(float(p), 3)},
        "safety_car_brier": round(sc_brier, 4),
        "note": "5 rounds only — correlations are indicative, not significant.",
    }
    Path("diagnostics/rebuild_2026/volatility_benchmark.json").write_text(
        json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
