#!/usr/bin/env python3
"""Offline walk-forward comparison; never changes published forecasts or models."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

import numpy as np

from motorsport_core.evidence import paired_bootstrap
from motorsport_core.promotion import evaluate_promotion


def benchmark(series: str) -> dict:
    package = series.replace('-', '_') + '_predictions'
    config = importlib.import_module(f'{package}.config')
    skill = importlib.import_module(f'{package}.ml_skill')
    model = importlib.import_module(f'{package}.model')
    source = getattr(importlib.import_module(f'{package}.datasource'), f'{series.upper()}DataSource')(live=False)
    composite = getattr(importlib.import_module(f'{package}.sources'), f'Composite{series.upper()}Source')
    rounds = [r for r in source.completed_rounds(config.SEASON)
              if all(composite.is_real(source.provenance(config.SEASON, r, race_index=i)) for i in (0, 1))]
    rows = []
    for current in rounds:
        prior = [r for r in rounds if r < current]
        candidate = skill.predict_temporal_candidate(source, config.SEASON, prior, len(config.DRIVERS) / 2)
        if candidate is None:
            continue
        elo, _ = model._elo_skill(source, config.SEASON, current)
        legacy = skill.predict_ml_skill(source, config.SEASON, prior, elo, len(config.DRIVERS) / 2)
        if legacy is None:
            continue
        features = skill._per_driver_features(source, config.SEASON, prior, {}, len(config.DRIVERS) / 2)
        observations = {}
        for race in source.race_results_for_round(config.SEASON, current).values():
            for result in race:
                observations.setdefault(result.competitor, []).append(result.position)
        actual = {code: float(np.mean(values)) for code, values in observations.items()}
        codes = sorted(set(actual) & set(legacy) & set(candidate.predictions))
        if not codes:
            continue
        def mae(prediction):
            return float(np.mean([abs(prediction[c] - actual[c]) for c in codes]))
        rows.append({'round': current, 'n': len(codes), 'legacyMAE': mae(legacy),
                     'candidateMAE': mae(candidate.predictions),
                     'historicalMeanMAE': mae({c: features[c]['roll_mean_finish'] for c in codes}),
                     'learnedWeight': candidate.learned_weight,
                     'validationRound': candidate.validation_round,
                     'trainingRounds': candidate.training_rounds})
    prod = [(r['round'], r['legacyMAE']) for r in rows]
    cand = [(r['round'], r['candidateMAE']) for r in rows]
    improvement = [p[1] - c[1] for p, c in zip(prod, cand)]
    low, high, _ = paired_bootstrap(improvement)
    decision = evaluate_promotion(prod, cand)
    return {'series': series, 'season': config.SEASON,
            'basis': 'retrospective walk-forward skill-signal experiment on real committed rounds; not live accuracy or a full forecast A/B test',
            'target': 'mean finishing position across the next sprint and feature race',
            'rounds': rows, 'nRounds': len(rows),
            'legacyMAE': float(np.mean([p[1] for p in prod])) if prod else None,
            'candidateMAE': float(np.mean([p[1] for p in cand])) if cand else None,
            'improvement95CI': [low, high], 'gateDecision': decision.decision, 'gateReason': decision.reason,
            'productionChanged': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Explicitly force the legacy comparator even in an opted-in shell.
    import os
    for series in ('F2', 'F3'):
        os.environ[f'{series}_USE_TEMPORAL_SKILL'] = '0'
    report = {'experiments': [benchmark(series) for series in ('f2', 'f3')]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    for item in report['experiments']:
        print(item['series'], item['nRounds'], item['legacyMAE'], item['candidateMAE'], item['gateDecision'])


if __name__ == '__main__':
    main()
