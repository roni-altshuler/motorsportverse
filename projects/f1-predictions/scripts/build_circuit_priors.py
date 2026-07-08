#!/usr/bin/env python3
"""Build data-derived per-circuit priors from Jolpica/Ergast history.

Emits ``features/data/circuit_priors.json`` with, per circuitId:
  * ``gridFinishSpearman`` — mean per-race Spearman correlation between grid
    and finishing position among classified finishers. High (→1) = processional
    circuit where the grid decides the race; low = high-overtaking/chaos.
  * ``dnfRate`` — fraction of starters not classified (status-based).
  * ``races`` — sample size (races aggregated).

Data: full season results (grid + position + status per entry) from the
Jolpica Ergast-compatible API for the ground-effect era seasons (2022-2025 by
default) — a regulation-consistent window. These are *historical priors about
circuits*, not about the 2026 season, so there is no round-level leakage:
the candidate model may use them for any 2026 round.

Usage::

    python scripts/build_circuit_priors.py                 # 2022-2025
    python scripts/build_circuit_priors.py --seasons 2023,2024,2025
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(PROJECT_ROOT, "features", "data", "circuit_priors.json")
BASE_URL = "https://api.jolpi.ca/ergast/f1"

# Statuses that count as classified. Jolpica reports lapped finishers as
# "Lapped" (legacy Ergast used "+N Laps" — kept for compatibility).
_CLASSIFIED_PREFIXES = ("Finished", "Lapped", "+")


def _fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def fetch_season_results(season):
    """All (circuitId, round, [(grid, position, classified), ...]) for a season."""
    races = {}
    offset = 0
    while True:
        payload = _fetch_json(f"{BASE_URL}/{season}/results.json?limit=100&offset={offset}")
        table = payload.get("MRData", {}).get("RaceTable", {})
        total = int(payload.get("MRData", {}).get("total", 0))
        for race in table.get("Races", []):
            key = (race["Circuit"]["circuitId"], int(race["round"]))
            rows = races.setdefault(key, [])
            for res in race.get("Results", []):
                try:
                    grid = int(res.get("grid"))
                    pos = int(res.get("position"))
                except (TypeError, ValueError):
                    continue
                status = str(res.get("status", ""))
                classified = status.startswith(_CLASSIFIED_PREFIXES)
                # grid 0 = pit-lane start; place at the back for rank purposes.
                rows.append((grid if grid > 0 else 30, pos, classified))
        offset += 100
        if offset >= total:
            break
    return races


def _spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx <= 0 or vy <= 0:
        return None
    return cov / (vx ** 0.5 * vy ** 0.5)


def build_priors(seasons):
    per_circuit = {}
    for season in seasons:
        print(f"Fetching {season} results from Jolpica…")
        for (circuit_id, _rnd), rows in fetch_season_results(season).items():
            entry = per_circuit.setdefault(circuit_id, {"spearmans": [], "starters": 0, "dnfs": 0})
            classified = [(g, p) for g, p, ok in rows if ok]
            rho = _spearman([g for g, _ in classified], [p for _, p in classified])
            if rho is not None:
                entry["spearmans"].append(rho)
            entry["starters"] += len(rows)
            entry["dnfs"] += sum(1 for _, _, ok in rows if not ok)

    out = {}
    for circuit_id, agg in sorted(per_circuit.items()):
        races = len(agg["spearmans"])
        if races == 0 or agg["starters"] == 0:
            continue
        out[circuit_id] = {
            "gridFinishSpearman": round(sum(agg["spearmans"]) / races, 4),
            "dnfRate": round(agg["dnfs"] / agg["starters"], 4),
            "races": races,
        }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seasons", type=str, default="2022,2023,2024,2025")
    args = parser.parse_args()
    seasons = [int(s) for s in args.seasons.split(",") if s.strip()]

    priors = build_priors(seasons)
    payload = {
        "seasons": seasons,
        "source": "Jolpica Ergast-compatible API (season results incl. grid + status)",
        "definitions": {
            "gridFinishSpearman": "mean per-race Spearman(grid, finish) among classified finishers",
            "dnfRate": "unclassified starters / total starters",
        },
        "circuits": priors,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"Wrote {len(priors)} circuits → {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
