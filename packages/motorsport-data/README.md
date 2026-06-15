# motorsport-data

The data-layer half of [MotorsportVerse](../../README.md)'s shared
infrastructure: a **sport-agnostic** schema, a history store, and ingestion
adapters. Generalised from the F1 Predictions project's Python→JSON→TypeScript
data contract.

## What's inside

| Module | Role |
|---|---|
| `schema` | Pydantic models — `Season`, `Round`, `Competitor`, `Team`, `Venue`, `Result`, `Prediction`. Neutral field names (`competitor`, `venue`) so any category maps on |
| `store` | `HistoryStore` — DuckDB table of `(predicted, actual)` pairs that calibration + forward-eval consume |
| `sources.base` | `DataSource` ABC — the upstream contract each sport implements |
| `sources.jolpica` | Shared, rate-limited Jolpica/Ergast client for open-wheel series |
| `rollover` | Config-driven multi-season archival (`archive_season`, `auto_rollover`) |

## Install

```bash
pip install -e packages/motorsport-data            # core (pydantic only)
pip install -e "packages/motorsport-data[store]"   # + duckdb history store
pip install -e "packages/motorsport-data[ingest]"  # + requests (Jolpica client)
pytest packages/motorsport-data
```

The `store` and `ingest` extras are optional so the schema imports stay
dependency-light. The Jolpica client primarily serves F1; F2/F3 telemetry and
non-open-wheel series implement their own `DataSource`.
