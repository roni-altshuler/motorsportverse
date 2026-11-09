# MotoGP 2026 publication hold

The raw `official_2026.json` is preserved. Its completed-event calendar identifies
Malaysia on 1 November as round 18 and Qatar on 8 November as round 19. The full
calendar identifies Australia on 25 October as round 18, Malaysia as round 19,
and Qatar as round 20. The previous ingester numbered classified Grands Prix
independently from the full calendar, shifting events after the missing race.

The official [2026 calendar](https://www.motogp.com/en/calendar/2026) and
[Australian GP cancellation statement](https://www.motogp.com/en/news/2026/10/25/farewell-phillip-island-from-motogp-ceo-carmelo-ezpeleta/1180981)
confirm the schedule and cancellation. The results API could not be accessed
from the coding executor: its HTTPS tunnel was denied with 403. No retry or
alternate route was used. No missing Australian GP or Sprint result is invented.

`publication_quarantine_2026.json` records the source commit and SHA-256 hashes of
all former public artifacts. Their bytes remain recoverable from that immutable
Git commit. They are removed from current public serving, rather than relabeled
or left available behind a warning. Forecasts, standings, championship odds,
calibration, accuracy and health all depend on the affected input mapping.
The site and every existing deep link show the hold and exact event mismatch.

The ingester now joins completed events to full-calendar event UUIDs and checks
venue/date identity. A missing GP leaves a real gap; it cannot compress later
round numbers. Publication also refuses sparse completed IDs because the current
model, export and evaluation consumers still use completed counts as round
bounds. Supporting legitimate cancellation gaps needs a separate verified change;
this hold does not weaken the shared continuity or baseline guards.
The cross-series circuit inventory reports this source-bound hold as unavailable,
not verified geometry. Unexplained missing data, malformed evidence, a source-hash
mismatch, or surviving numerical artifacts still fail. Strict verified-coverage
mode continues to fail for held and unverified entries.

Both export and evaluation enforce the hold before running numerical work and
remove stale current-season artifacts. The hold is deterministic and a repeated
run produces no new timestamps or scores. Raw/private snapshots and archives
are not deleted. A healthy contiguous snapshot can rebuild normally; a prior
hold clears only after export and evaluation both complete successfully.
An export-completion record binds all generated files to the current snapshot
hash; standalone evaluation cannot clear a hold when that record or any file
is missing or stale. This record is not evidence of pre-event publication.
Normal-output contract tests retain their numerical assertions on the verified
pre-mismatch prefix. Separate tests assert that the actual production corpus is
held, source bytes are unchanged, and no stale numerical artifacts are public.

Recovery requires verified event-matched session inputs and explicit support for
noncontiguous completed-round coverage. This change does not recover providers,
retrain historical models, modify F1 holds, or claim original pre-event forecasts.
