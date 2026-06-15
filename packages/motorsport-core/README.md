# motorsport-core

Shared, **sport-agnostic** ML and evaluation infrastructure for the
[MotorsportVerse](../../README.md) ecosystem. Extracted from the F1 Predictions
(RaceIQ) flagship as the reusable foundation every motorsport project builds on.

## What's inside

| Module | Role |
|---|---|
| `interfaces` | `DataSource` / `Predictor` ABCs + `Competitor`/`Venue`/`GridEntry`/`RoundForecast` dataclasses — the seam each sport implements |
| `calibration` | Plackett-Luce ranking sampler + isotonic & stratified probability calibration |
| `registry` | File-backed model registry (joblib/torch artefacts + committed metadata, atomic writes) |
| `drift` | Population-Stability-Index + rolling-Brier health monitoring |
| `promotion` | Guarded production/candidate A/B promotion gate |
| `eval` | Forward-time ranking metrics (Spearman ρ, NDCG@K, within-N, podium hits) |
| `elo` (+ `era`) | Pairwise competitor/team Elo with optional regulation-era awareness |
| `conformal` | Conformal prediction intervals |
| `reliability` | Reliability diagrams + ECE/MCE calibration assessment |
| `hierarchical_bayes` | Bayesian skill priors |
| `leakage` | `assert_prior_only` temporal-leakage guards |
| `features.skill_priors`, `features.competitor_history` | Reusable feature builders |

## Install (editable, for development)

```bash
pip install -e packages/motorsport-core
pytest packages/motorsport-core
```

## Usage sketch

```python
from motorsport_core import calibration, eval, registry
from motorsport_core.interfaces import DataSource, Predictor, Competitor

probs = calibration.plackett_luce_probabilities(strengths, competitors)
metrics = eval.score_round(predicted_order, actual_order)
```

A new sport implements `DataSource` + `Predictor` and reuses everything else
unchanged. See [`docs/adding-a-sport.md`](../../docs/adding-a-sport.md).
