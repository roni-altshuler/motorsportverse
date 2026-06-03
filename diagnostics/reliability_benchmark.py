#!/usr/bin/env python3
"""Benchmark the Priority-2 reliability model vs the production baseline.

Ground truth: 2026 rounds 1-5 actual DNFs derived from FastF1 race `Status`
(Retired / Did not start = DNF; Finished / Lapped = classified).

Compares three DNF estimators by Brier score + calibration:
  * base_rate   — flat 0.15 (what the pace-only production model implies)
  * dnf_v1      — existing models/dnf.py (2-feature logistic)
  * reliability — new models/reliability_model.py (expanded features)

Writes docs/diagnostics/06_reliability_benchmark.md and a JSON sidecar.
Reads only; no production writes.
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
import duckdb  # noqa: E402

import f1_prediction_utils as fpu  # noqa: E402
from models.reliability_model import (ReliabilityModel, ReliabilityInputs,  # noqa: E402
                                      classify_retirement)
from models.dnf import compute_dnf_probabilities, DnfModelInputs  # noqa: E402

fastf1.Cache.enable_cache("f1_cache")
GP = {1: "Australia", 2: "China", 3: "Japan", 4: "Miami", 5: "Canada"}
DB = Path("data/history.duckdb")
TEAM_MAP = dict(getattr(fpu, "DRIVER_TEAM_2026", {}))


def actual_dnf_labels(rnd):
    """{driver: (is_dnf, status_class)} from FastF1 race Status."""
    s = fastf1.get_session(2026, GP[rnd], "R")
    s.load(laps=False, telemetry=False, weather=False, messages=False)
    out = {}
    for _, row in s.results.iterrows():
        drv = str(row["Abbreviation"])
        status = str(row["Status"])
        cls = classify_retirement(status)
        out[drv] = (1 if cls != "finished" else 0, cls)
    return out


def predicted_positions(rnd):
    rd = json.load(open(f"website/public/data/rounds/round_{rnd:02d}.json"))
    return {c["driver"]: int(c["position"]) for c in rd["classification"]}


def brier(probs, labels):
    keys = [k for k in probs if k in labels]
    return float(np.mean([(probs[k] - labels[k]) ** 2 for k in keys])), len(keys)


def main():
    # Fit reliability model once on pre-2026 history.
    con = duckdb.connect(str(DB), read_only=True)
    rows = con.execute(
        "SELECT season,round,driver,predicted_position,actual_position "
        "FROM historical_predictions WHERE season<2026 ORDER BY season,round"
    ).fetchall()
    con.close()
    rel = ReliabilityModel().fit(rows, team_map=TEAM_MAP)

    per_round = {}
    agg = {"base_rate": [], "dnf_v1": [], "reliability": [], "labels": []}
    dnf_total = 0
    for rnd in range(1, 6):
        labels_full = actual_dnf_labels(rnd)
        labels = {d: v[0] for d, v in labels_full.items()}
        preds_pos = predicted_positions(rnd)
        drivers = [d for d in preds_pos if d in labels]

        base = {d: 0.15 for d in drivers}
        v1 = compute_dnf_probabilities(
            DB, season=2026, current_round=rnd,
            inputs=[DnfModelInputs(d, preds_pos[d], GP[rnd]) for d in drivers])
        rel_inputs = [ReliabilityInputs(d, preds_pos[d], GP[rnd],
                                        team=TEAM_MAP.get(d), rain_probability=0.1)
                      for d in drivers]
        rel_pred = rel.predict(rel_inputs, team_map=TEAM_MAP)
        relp = {d: rel_pred[d].p_dnf for d in drivers}

        b_base, n = brier(base, labels)
        b_v1, _ = brier(v1, labels)
        b_rel, _ = brier(relp, labels)
        n_dnf = sum(labels.values())
        dnf_total += n_dnf
        per_round[rnd] = {"gp": GP[rnd], "drivers": n, "actual_dnfs": n_dnf,
                          "brier_base_rate": round(b_base, 4),
                          "brier_dnf_v1": round(b_v1, 4),
                          "brier_reliability": round(b_rel, 4)}
        for d in drivers:
            agg["base_rate"].append(base[d]); agg["dnf_v1"].append(v1[d])
            agg["reliability"].append(relp[d]); agg["labels"].append(labels[d])

    lab = np.array(agg["labels"])
    def agg_brier(key):
        return float(np.mean((np.array(agg[key]) - lab) ** 2))
    overall = {k: round(agg_brier(k), 4) for k in ("base_rate", "dnf_v1", "reliability")}

    # Rank drivers by predicted DNF risk vs whether they actually DNF'd (precision@k).
    order = np.argsort(-np.array(agg["reliability"]))
    topk = {k: int(lab[order[:k]].sum()) for k in (5, 10, 15)}

    coefs = rel.coefficients()
    result = {
        "overall_brier": overall,
        "per_round": per_round,
        "total_actual_dnfs": dnf_total,
        "total_observations": int(len(lab)),
        "reliability_precision_at_k": topk,
        "feature_importance": {k: round(v, 4) for k, v in coefs.items()},
    }
    out_json = Path("diagnostics/rebuild_2026/reliability_benchmark.json")
    out_json.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
