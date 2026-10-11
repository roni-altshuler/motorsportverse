# Verified final-grid shadow contract

The champion's grid prior uses `QualifyingRank`. Its qualifying override's
`grid` map seats no-time drivers; it does not apply a timed driver's penalty.
The simulator bridge uses `GridPosition`, then qualifying rank, then row order.
Singapore's final grid moved Russell from qualifying P6 to grid P21 while the
champion feature frame stayed identical. [The original probe](../grid-baseline/champion-input-contract.json)
records that defect.

This change adds `StartingGridPosition` as an independent, validated observation
for **explicit shadow calls**. Production calls retain their behavior. No exporter
or workflow supplies the new arguments. No published forecast, registry entry,
Singapore hold, baseline seal, receipt or source timestamp changes. There are
no website changes.

## Data and time boundaries

`models/starting_grid.py` binds a frozen event to the trusted calendar and an
independently pinned Formula1.com starting-grid URL and exact race start. The
published season/round, GP key, name, circuit and date must agree. Any recorded
provider identity must also agree. Provider race IDs are never guessed; an
echoed round number is insufficient identity.

The final-grid session must be official, unique and complete for the caller's
expected field. Driver codes and integer positions must be unique; positions
must form 1 through N. Partial fields, conflicting columns, fractional/boolean
positions and pit-lane zero positions are unavailable. Pit-lane starts need a
separate explicit representation before support; no slot is invented here.

An aware `verifiedAt` timestamp is required, at or before the input cutoff and
within a one-hour freshness ceiling; callers may only tighten that policy.
Any fetched timestamp must precede
verification, and any published-source generation timestamp must precede cutoff.
The cutoff must be strictly before race start. Consumers require that same
requested cutoff; reusing an earlier snapshot for a later request fails.

Provenance carries canonical event identity, source URL, verification and optional
fetch/generation times, cutoff, race start, freshness policy and SHA-256 of the
canonical session JSON. That digest is separate from raw provider responses or
the published baseline seal. The recorded identity basis is the published event
plus independently pinned official URL. Rejections raise `StartingGridUnavailable`
with explicit reasons.

## Consumers and training compatibility

`apply_race_postprocessing` accepts validated `shadow_starting_grid`, matching
`shadow_event` and `shadow_input_cutoff`. It applies the final slot to the existing
circuit-conditioned grid prior. Qualifying times/ranks and pace-derived
`GridAdvantage` stay unchanged. `DEFAULT_FEATURE_COLS` and the learned-head schema
stay unchanged; no coefficient is fitted or replaced.

The learned-head route is refused for this shadow contract because it has no
final-grid evaluation. Game-theory neighbor/battle features keep their existing
qualifying-derived meanings as learned inputs. Replacing those with starting
positions needs historical coverage and a reviewed training/evaluation contract.

The simulator's explicit shadow route initializes `GridEntry.grid_position` and
the existing grid-based retirement prior from `StartingGridPosition`. Pace offset
and the race-pace feature schema are retained. Its result includes the same
event/cutoff/source provenance and `mode: starting-grid-shadow`. Invalid grids
raise before the no-model/disabled-registry fallback. No environment switch or
automatic production activation is added.

## Read-only evidence and temporal coverage

[The audit](contract-audit.json) uses the committed Singapore grid/qualifying
snapshot verified at **05:15:33 UTC**, generated at **05:31:42 UTC**. Its
**06:00 UTC cutoff is a retrospective contract-test cutoff**, separate from
forecast generation or the baseline seal. The report's later `generatedAt` is
the actual audit execution time. A new 09:00 UTC cutoff correctly rejects the
older source under the one-hour policy.

Flat synthetic lap-time outputs isolate grid coupling. Russell retains qualifying
rank 6 and qualifying time 91.747 seconds; the grid prior and simulator receive
starting slot 21. Hadjar retains existing no-time handling and grid slot 22.
No champion inference, forward forecast, win-probability claim or accuracy claim
is produced by this controlled diagnostic.

The cheap temporal coverage audit inspects **16 completed 2026 rounds**.
**None contains a distinct final-grid session in the committed snapshots**, so
there are **zero eligible historical contexts** for the comparison. This is a
repository coverage limit, not a claim that providers lack official grids/results.
Qualifying order is never relabelled as final grid; missing historical grids are
never reconstructed. Accuracy improvements or regressions cannot be measured on
this cohort. Production wiring needs complete event-bound, pre-race final-grid
snapshots and a temporal comparison. Changes to learned grid-dependent features
also need reviewed training compatibility.

Reproduce from the F1 project directory using existing dependencies:

```sh
F1_REGISTRY_ENABLED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  python src/audit_starting_grid_contract.py \
  --round 17 \
  --source-url https://www.formula1.com/en/results/2026/races/1296/singapore/starting-grid \
  --race-start-utc 2026-10-11T12:00:00Z \
  --input-cutoff 2026-10-11T06:00:00Z \
  --output /tmp/starting-grid-contract-audit.json
```

The CLI permits only an explicit external diagnostic path or `docs/qa`; it refuses
published/model paths, including the immutable receipt. It makes no provider
request and never runs regeneration, training, promotion or publication.

[Validation](validation.json) records focused/full regressions, Ruff, scoped mypy
and byte compilation. [Preservation](preservation.json) records unchanged data,
artifacts and all eleven saved worktree heads. The website tree is identical to
main, so no visual change or new browser-QA claim is made.
