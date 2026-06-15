# Data schema reference

`motorsport-data` provides the canonical, sport-agnostic models. Neutral field
names (`competitor`, `venue`) so any category maps on. All are Pydantic v2 with
`extra="ignore"` (forward-compatible additions, strict required fields).

`pip install -e packages/motorsport-data` (schema needs only pydantic).

## Models (`motorsport_data.schema`)

| Model | Key fields |
|---|---|
| `Competitor` | `code`, `name`, `team`, `number?`, `nationality?` |
| `Team` | `name`, `color?`, `nationality?` |
| `Venue` | `key`, `name`, `country?`, `kind` (`VenueKind`: circuit/oval/street/stage) |
| `Result` | `competitor`, `position?`, `grid?`, `status?`, `points?` |
| `Prediction` | `competitor`, `predicted_position`, `predicted_value?`, `p_win?`, `p_podium?`, `low?`, `high?` |
| `Round` | `season`, `round`, `venue`, `completed`, `predictions[]`, `results[]` |
| `Season` | `sport`, `year`, `competitors[]`, `teams[]`, `calendar[]`, `completed_rounds[]` |

`position` / `predicted_position` are 1-indexed; `position = None` means DNF/DNS.

## History store (`motorsport_data.store`)

`HistoryStore(path)` wraps a DuckDB table keyed on
`(sport, season, round, competitor)` holding `predicted_position`,
`actual_position`, `predicted_value`. This is what `motorsport_core.calibration`
and `eval` consume.

- `upsert(rows: list[HistoryRow]) -> int` — idempotent insert-or-replace.
- `completed_rounds(sport, season) -> list[int]`
- `pairs(sport) -> list[(predicted, actual)]`

Requires the `store` extra: `pip install -e "packages/motorsport-data[store]"`.

## Ingestion (`motorsport_data.sources`)

- `base.DataSource` — the ABC every sport implements.
- `jolpica.JolpicaClient(series="f1", sport="Formula 1")` — shared, rate-limited
  Ergast/Jolpica client returning schema objects. Requires the `ingest` extra.

## Rollover (`motorsport_data.rollover`)

Config-driven multi-season archival: `archive_season`, `start_season`,
`auto_rollover`. Sport-agnostic — supply the data root and the artefact lists.
