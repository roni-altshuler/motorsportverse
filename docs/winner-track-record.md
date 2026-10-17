# Winner track record

`/track-record` is the consumer view for **original pre-race winner picks**.
The hub links to the ten series views. `/accuracy` remains the historical
evaluation, explicitly qualified as such. RMSE and podium/points overlap never
enter winner scoring.

The shared, read-only build adapter is `src/lib/trackRecordData.ts` in F1's
website; the shared UI gate copies it and the pure scoring module/component to
the other sites. The series bridge respects the existing season selector.
No prediction, result, seal, lock, model, or historical artifact is rewritten.

## Current source and missing evidence

The reader uses the committed `public/data/rounds/round_NN.json` plus the series
calendar (`season.json`, `f2.json`, `f3.json`, `fe.json`, etc.). Result positions
come from `actualResults`, never `accuracy`, `forward_eval`, or embedded RMSE.
The fixed winner pick is the unique original classification position **1**.
It is never the minimum after intersecting driver sets. Every saved position and
its actual counterpart can be inspected, including entries present on only one
side. Missing/duplicate P1s, invalid identities and unknown event dates cannot
score. Stage/class scopes and seasons remain separate.

The current corpus has no audited immutable model-publication receipts. F1's
R17 receipt is explicitly an **official grid baseline**, not a model forecast;
it is never counted. Many F1 snapshots were generated after their event and
other series omit original publication timestamps. F2's walk-forward evaluation
is a retrospective replay. None of these establish original public pre-race
model performance. A genuine empty denominator renders **Not yet scored**,
with saved picks, results, pending/missing/held/unverified coverage visible.
WEC/IMSA dates missing from calendars remain missing; MotoGP sprint dates are
not inferred from Sunday dates. Event-only classes are not expanded across
unrelated rounds.

## Trusted original-publication input

The adapter can consume an **audited** `forecast_receipts.json` archive index,
schema version 1, with a `forecasts` array. This task creates **no receipt or
original-forecast artifact**, and does not backfill historical publication.
This contract is an explicit trust boundary: a hash and a self-declared timestamp
do not prove that bytes were public before a race. Before a receipt enters the
trusted committed index, its publication event and immutable artifact must be
independently checked against the actual public record. Do not fabricate or
backdate receipts for existing snapshots. Adding that producer/audit process is
outside this view change.

Each trusted entry identifies `season`, `round`, `scope`,
`forecastKind: "model_forecast"`, `artifactFile`, `artifactSha256`, `sealedAt`,
and a full `sourceCommit`. `artifactFile` must be a single JSON file under
`forecasts/`, carrying the original round contract, with no actual results,
completion, synthetic/replay markers or publication holds. It is distinct from
the mutable result snapshot. `verification` must contain:

- `kind: "audited_publication_event"`;
- the actual `publishedAt` time with UTC/offset;
- `eventUrl`, an audited public workflow-run record in this repository;
- `artifactUrl`, the exact raw GitHub URL pinned to `sourceCommit` and the
  original series `public/data/forecasts/<file>.json` path.

Offline checks enforce one receipt per season/round/scope, artifact SHA256,
identity, original generation ≤ seal ≤ audited publication < event start,
and the expected immutable URL. Missing/contradictory evidence is unverified.
If race start time is absent, publication must be before 00:00 UTC on the known
event date (a conservative cutoff); a same-day time is not guessed. Current
result snapshots must match identity and be complete/official, contain unique
P1, and be free of holds or synthetic results. Non-F1 completion must be marked
in both snapshot and calendar; F1 requires the official Grand Prix session.
Explicit provisional results stay pending. Positive receipt examples exist
only in temporary unit/browser fixtures, clearly marked as test data.

## Timeline and reconciliation

Headline, chart, accessible date table and history all derive from one ledger.
For the selected season and race/class, cumulative accuracy is pooled correct
picks / eligible settled races. A point is a UTC calendar event date; all tied
events enter together. The horizontal axis uses actual elapsed time and the
vertical axis is always 0–100%. Straight segments join observed values: no
smoothing, forced improvement or claims that a version caused a change.

Recent form is the preceding **28 calendar days**, inclusive of the selected
date (start = date minus 27 days). Each point discloses both correct/settled
counts and that exact window. Denominators vary; weekly helpers aggregate
counts, including partial weeks, and never average percentages. Unknown dates
are excluded. Model versions appear only from actual saved metadata.

The date slider supports native keyboard/touch input and announces date,
counts and window. The full date table and full pick/result ledger provide the
nonvisual alternative. No public demo data are substituted for an empty record.
