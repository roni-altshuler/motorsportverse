# Architecture

MotorsportVerse is layered so that sport-specific projects stay thin and the
hard, reusable parts live once in shared packages.

```
┌─────────────────────────────────────────────────────────────┐
│  projects/<sport>-predictions   (thin: DataSource + Predictor) │
│    f1-predictions (flagship)   f2-predictions   …             │
└───────────────┬───────────────────────────┬──────────────────┘
                │ implements                 │ implements
                ▼                            ▼
   motorsport_core.interfaces.Predictor   motorsport_data.sources.DataSource
                │                            │
┌───────────────▼────────────┐ ┌────────────▼─────────────────┐
│  motorsport-core            │ │  motorsport-data             │
│  calibration, registry,     │ │  schema, store (DuckDB),     │
│  drift, promotion, elo,     │ │  sources (Jolpica/…),        │
│  conformal, eval, leakage,  │ │  rollover                    │
│  standings, championship,   │ │                              │
│  features                   │ │                              │
└─────────────────────────────┘ └──────────────────────────────┘
                │                            │
                └──────────────┬─────────────┘
                               ▼
              registry/ (catalog)  →  website/ (catalog UI)
```

## The two seams

A new sport implements exactly two contracts:

1. **`DataSource`** (`motorsport_data.sources.base`) — where calendar, entry
   list, and results come from. Leakage-safe: `results()` returns data only once
   a round has run.
2. **`Predictor`** (`motorsport_core.interfaces`) — features + a fit procedure
   that turns a grid into a ranked, optionally-probabilistic `RoundForecast`.

Everything else — Plackett-Luce calibration, the model registry, drift
monitoring, the A/B promotion gate, forward-eval metrics — is consumed unchanged.

## Data flow (per round)

```
DataSource.grid() ─▶ Predictor.predict() ─▶ RoundForecast
                                              │  predicted_order
                                              │  probabilities (Plackett-Luce)
                                              ▼
                          motorsport_data.schema (Round/Prediction)
                                              ▼
                       JSON under website/public/data  ─▶  project website
                                              ▼
        HistoryStore (predicted,actual)  ─▶  calibration + forward-eval
```

## Why this split

- **`motorsport-core` is dependency-light** (numpy/pandas/sklearn/scipy). No
  sport constants, no web framework, no plotting in the import path.
- **`motorsport-data` schema imports need only pydantic**; DuckDB and the HTTP
  client are optional extras so projects pull in only what they use.
- **The registry is just JSON + a schema**, so the catalog is editable without
  touching code and validated in CI.

## Monorepo today, org-ready tomorrow

Each `packages/*` and `projects/*` folder is self-contained (its own
`pyproject.toml`/`package.json`), so any folder can be lifted into its own
GitHub-org repo with `git subtree split` when it warrants one. See
[.github/ORG_STRUCTURE.md](../.github/ORG_STRUCTURE.md).
