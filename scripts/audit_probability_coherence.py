#!/usr/bin/env python3
"""Replay shared probability repairs in memory; never rewrite published history."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from motorsport_core.calibration import MARKET_TARGET_SUM, renormalize_market_struct


def blocks(value):
    if isinstance(value, dict):
        markets = value.get('markets')
        if isinstance(markets, dict) and isinstance(markets.get('win'), dict):
            yield markets
        for key, item in value.items():
            if key != 'markets':
                yield from blocks(item)
    elif isinstance(value, list):
        for item in value:
            yield from blocks(item)


def contradictions(markets):
    ordered = [m for m in ('win', 'podium', 'top6', 'top10') if m in markets]
    return sum(markets[a][c]['probability'] > markets[b][c]['probability'] + 1e-8
               for a, b in zip(ordered, ordered[1:])
               for c in set(markets[a]) & set(markets[b]))


def audit(root: Path) -> dict:
    rows = []
    for project in sorted((root / 'projects').glob('*-predictions')):
        if project.name == 'f1-predictions':
            continue  # The flagship uses its own calibrator and array schema.
        count = before = after = changed = 0
        max_adjustment = max_mass_error = 0.0
        for file in sorted((project / 'website/public/data/probabilities').glob('*.json')):
            for original in blocks(json.loads(file.read_text())):
                repaired = renormalize_market_struct(original)
                count += 1
                before += contradictions(original)
                after += contradictions(repaired)
                delta = max((abs(v['probability'] - original[m][c]['probability'])
                             for m, entries in repaired.items() for c, v in entries.items()), default=0)
                changed += delta > 1e-8
                max_adjustment = max(max_adjustment, delta)
                for market, entries in repaired.items():
                    if market in MARKET_TARGET_SUM and entries:
                        max_mass_error = max(max_mass_error, abs(sum(v['probability'] for v in entries.values())
                                                               - min(MARKET_TARGET_SUM[market], len(entries))))
        if count:
            rows.append({'series': project.name, 'marketBlocks': count, 'contradictionsBefore': before,
                         'contradictionsAfter': after, 'changedBlocks': changed,
                         'maximumProbabilityAdjustment': max_adjustment, 'maximumMassErrorAfter': max_mass_error})
    return {'basis': 'in-memory consistency replay of committed exports, not a predictive accuracy benchmark',
            'historicalArtifactsModified': False, 'series': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(Path(__file__).resolve().parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
