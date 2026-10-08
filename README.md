<div align="center">

<img src="website/public/brand/motorsportverse-logo.png" alt="MotorsportVerse" width="560" />

**A unified, open-source motorsport AI ecosystem.**

One repository. One catalog. Many sport-specific prediction projects on shared ML & data infrastructure.

[Live site](https://roni-altshuler.github.io/motorsportverse/) ·
[Project catalog](https://roni-altshuler.github.io/motorsportverse/#projects) ·
[Architecture](docs/architecture.md) ·
[Adding a sport](docs/adding-a-sport.md) ·
[Governance](GOVERNANCE.md)

</div>

---

## Vision

The [October quality roadmap](docs/QUALITY_ROADMAP_2026-10.md) records the next
model-evaluation and race-weekend product priorities.

MotorsportVerse is a single home for predicting motorsport outcomes with AI and
machine learning. The goal is one coherent "universe" of projects — Formula 1,
Formula 2, and every series after them — that all forecast race results, then
grade themselves against reality, instead of a scatter of disconnected
repositories.

It is to motorsport prediction what [scverse](https://scverse.org/) is to
single-cell biology: a discoverable hub of independent, repo-ready projects that
all build on a common foundation. Every series gets its own project and its own
dashboard, but they share the numerically heavy parts — calibration, championship
simulation, evaluation, drift detection, model promotion, and a canonical data
schema — so a new sport is a thin layer on a proven core, not a rewrite.

**Principles**

- **One repository, one catalog.** Every project lives here and is listed in a
  machine-readable [registry](registry/). The catalog is the source of truth for
  which sports exist and how mature each one is.
- **Shared core, thin projects.** Reusable ML & data infrastructure lives in two
  pip packages; each sport supplies only a data source and a predictor.
- **Honest by construction.** Probabilities are calibrated and gated — a project
  never claims more confidence than its data supports — and every prediction is
  scored against the real result.
- **Each series is first-class.** Open-wheel, stock car, endurance, rally, and
  formula-electric all belong; none is an afterthought.

## F1 prediction context

The F1 race page reports the ranking and probability export timestamps separately,
with recorded qualifying and weather assumptions. Missing, invalid or conflicting
metadata stays explicit. Export times do not establish a forecast input cutoff;
the current artifacts do not publish one. Factor availability describes the
stored export without promising a future model run. See the
[verification and screenshots](docs/qa/prediction-freshness/README.md).

## Circuit map availability

The [local FastF1 exporter](docs/FASTF1_LOCAL_CAPTURE.md) bridges an existing trusted
offline cache to the F1 circuit workspace. It preserves bounded native samples,
labels units and accuracy, and rejects F1-only input under other series. Synthetic
tests validate the adapter; no new real telemetry, map or data rights are supplied.
The [hydration audit](docs/qa/local-fastf1/HYDRATION_INVESTIGATION.md) records a
controlled root-layout replay repair and keeps the earlier browser failure's
unresolved attribution explicit.

The [shared explorer shell](docs/reviews/2026-10-06-zandvoort-explorer/README.md)
has no registered event or production consumer. The independent
[F1 local workspace](docs/UPSTREAM_CIRCUIT_WORKSPACE.md) previews user-supplied
captures and an explicitly fictional demo; it does not approve the image shell.
The shell binds reviewed image hashes to downloaded, decoded bytes and hides checked
claims and controls on image failure, with retry and cleanup regressions. The
Zandvoort pilot still needs source-byte inspection, hashing and real-map browser QA.
Selected markers, list borders and keyboard focus now use the supported ink/canvas
pair, with computed contrast checks across all 11 palettes and fixture screenshots.

F2/F3 race disclosures distinguish existing outlines awaiting layout review from
the unavailable interactive explorer, which requires a reviewed layout.

The shared **Explore circuit** feature remains unfinished. The
[circuit evidence audit](docs/CIRCUIT_GEOMETRY.md) records 43 stored paths across
168 published calendar rounds, **37 eligible for continued legacy display** and
**zero reviewed for a new explorer**. These are separate states: absent review
records do not establish that existing display is forbidden or incorrect.

Existing nonconflicting outlines and the decorative F1 hero sweep are preserved
without a verification claim. Confirmed Austria/Silverstone conflicts are
quarantined. Ambiguous corner numbers are suppressed while their outline and
unambiguous markers remain. F1's invented generic fallback is removed. No empty
explorer panels are added to other sites.

As of 6 October 2026, counts refer to **committed calendar rounds**, including
double headers, rather than independently verified official calendar coverage.

| Series | Stored paths / published rounds | Legacy outlines retained | Explorer-reviewed layouts |
| --- | ---: | ---: | ---: |
| F1 | 22 / 22 | 20 | 0 |
| F2 | 12 / 14 | 10 | 0 |
| F3 | 9 / 9 | 7 | 0 |
| Formula E | 0 / 17 | 0 | 0 |
| IndyCar | 0 / 18 | 0 | 0 |
| NASCAR | 0 / 36 | 0 | 0 |
| MotoGP | 0 / 22 | 0 | 0 |
| WRC | 0 / 13 | 0 | 0 |
| WEC | 0 / 6 | 0 | 0 |
| IMSA | 0 / 11 | 0 | 0 |
| Le Mans | No site or published calendar | 0 | 0 |

A new explorer requires an explicit configuration, source-appropriate provenance
and documented reuse basis. Geographic maps need a pinned map revision, not a
fictional timed session. Telemetry sources need their resolved session/year.
Rally stages, ovals and road configurations stay distinct; no sectors, DRS
locations or live telemetry are inferred. [The Monaco pilot prerequisites](docs/CIRCUIT_GEOMETRY.md#bounded-pilot-prerequisite)
are recorded without claiming a verified or delivered interactive feature.

## What's here

The [theme and navigation audit](docs/THEME_JOURNEYS.md) covers the hub and all
ten published series sites. Their intentional dark palettes and individual
series accents remain distinct; recovery pages and project launch labels use
readable, consistent controls. The shared motion preference now hydrates from
the same initial state as the static export. This changes presentation, not
published result coverage or model performance.
Browser journeys check each destination's content and completed loading before
measurement, including the available F1 driver and MotoGP rider profiles.

The F1 [circuit workspace](docs/UPSTREAM_CIRCUIT_WORKSPACE.md) lets users explore
browser-local captures in Tom Shaw's replay output format, or try a clearly
fictional demo. Upstream code vendoring and real Zandvoort artwork remain blocked
by their respective license/source dependencies; no new historical telemetry is
published. The shared adapter is available to all series without map approval.

The F1 [archived lap comparison](docs/ARCHIVED_LAP_COMPARISON.md) is a bounded
2025 Monaco timing pilot merged through PR #13. It uses existing committed
lap records, keeps sectors from the same stored lap, and explains the absent lap
context. It does not add live timing, reviewed geometry or a current-season
comparison to F1 or the other series.

[The locked-install audit](docs/LOCKFILE_INSTALL_AUDIT.md) records the repaired
test dependency omissions in eight site locks. All 11 sites pass clean Node 20 /
npm 10 installs, ESLint, frontend tests, types and static builds; website CI now
enforces the locked install, lint and type checks. [The lint repair](docs/LINT_TOOLING_REPAIR.md)
records the exact errors, fixes and remaining warnings without rule suppression.
[Matched MotoGP mobile browser evidence](docs/MOTOGP_MOBILE_VISIBILITY.md) verifies
painted podium, probability and classification content after real scrolling.

```
motorsportverse/
├── website/                 ecosystem landing site + project catalog (Next.js, static export)
├── packages/
│   ├── motorsport-core      shared ML & evaluation infrastructure (pip)
│   └── motorsport-data      canonical schema + ingestion + history store (pip)
├── projects/
│   ├── f1-predictions       RaceIQ F1 — the flagship & reference implementation
│   ├── f2-predictions       RaceIQ F2 — first sport on the shared core
│   ├── f3-predictions       RaceIQ F3 — the golden-template new-series clone
│   ├── formula-e-predictions RaceIQ Formula E — live product (pulselive API)
│   ├── nascar-predictions   RaceIQ NASCAR — live product (DNF hazard, Chase title MC)
│   ├── indycar-predictions  RaceIQ Indy — live product (curated history, dual-surface form)
│   └── <5 more>             scaffolded series (WEC, MotoGP, WRC, IMSA, Le Mans)
│                            — DataSource+Predictor seams ready to implement
├── registry/                the project catalog (JSON + schema; source of truth)
├── docs/                    unified documentation
├── scripts/                 registry builder + new-project scaffolder
└── templates/               project skeleton
```

> The **F1 flagship** previously lived in its own repository and has been merged
> in here, with full git history, under [`projects/f1-predictions/`](projects/f1-predictions/).
> Its prediction pipeline, race-weekend automation, and dashboard now run from
> this monorepo.

## Project catalog

Every project is a **RaceIQ** product built on the shared core; the ecosystem hub
is **MotorsportVerse**.

| Project | Sport | Maturity |
|---|---|---|
| [RaceIQ F1](projects/f1-predictions/) | Formula 1 | **production** |
| [RaceIQ F2](projects/f2-predictions/) | Formula 2 | **production** |
| [RaceIQ F3](projects/f3-predictions/) | Formula 3 | **production** |
| [RaceIQ Formula E](projects/formula-e-predictions/) | Formula E | **production** |
| [RaceIQ NASCAR](projects/nascar-predictions/) | NASCAR Cup | **production** |
| [RaceIQ Indy](projects/indycar-predictions/) | IndyCar | **production** |
| [WEC](projects/wec-predictions/) · [MotoGP](projects/motogp-predictions/) · [WRC](projects/wrc-predictions/) · [IMSA](projects/imsa-predictions/) · [Le Mans](projects/lemans-predictions/) | — | in-development (scaffolded) |

Browse them all on the [live catalog](https://roni-altshuler.github.io/motorsportverse/#projects)
or under the website's `/projects` directory. See the
[branding system](docs/BRANDING_SYSTEM.md) for the per-series identity.

## Deployment

GitHub Pages serves one site per repository, so the whole ecosystem ships as a
single artifact:

| Site | URL |
|---|---|
| Ecosystem hub | https://roni-altshuler.github.io/motorsportverse/ |
| RaceIQ F1 dashboard | https://roni-altshuler.github.io/motorsportverse/projects/f1/ |
| RaceIQ F2 dashboard | https://roni-altshuler.github.io/motorsportverse/projects/f2/ |
| RaceIQ F3 dashboard | https://roni-altshuler.github.io/motorsportverse/projects/f3/ |
| RaceIQ Formula E dashboard | https://roni-altshuler.github.io/motorsportverse/projects/formula-e/ |
| RaceIQ NASCAR dashboard | https://roni-altshuler.github.io/motorsportverse/projects/nascar/ |
| RaceIQ Indy dashboard | https://roni-altshuler.github.io/motorsportverse/projects/indycar/ |

## Quick start

```bash
# Shared packages (editable installs)
pip install -e "packages/motorsport-core[dev]" "packages/motorsport-data[dev]"
pytest packages/motorsport-core packages/motorsport-data

# Build/validate the catalog
python scripts/build_registry.py

# Run the ecosystem website
cd website && npm install && npm run dev   # → http://localhost:3000

# Run a project (the F1 flagship)
cd projects/f1-predictions/website && npm install && npm run dev

# Scaffold a new sport (use --skip-registry if the catalog entry already exists)
python scripts/new_project.py <slug>-predictions --sport "<Sport>" \
  --category <category> --summary "<one-line blurb>" --added <ISO date>
```

## Published result coverage

The F2, F3 and IndyCar dashboards distinguish imported results from scheduled
race dates and show past-due coverage beside the snapshot forecast. A dataset
export time or a successful no-work poll does not establish source freshness.
As of 6 October 2026, published coverage remains **6/14**, **5/9** and **11/18**
rounds respectively; official free calendars show results for the uncovered
past weekends. Ingestion is still pending separate source/session verification.

Run `python scripts/check_result_coverage.py f2` (or `f3`, `indycar`) for an
offline coverage audit. The polling workflows run it even after a no-work gate;
past-due gaps fail a separate coverage job without blocking valid updates.
Homepage coverage, forecast badges and carousel labels recheck at hydration
and hourly. A passed schedule date remains a snapshot forecast during the
grace period, then becomes past due; time never marks a result as imported.
Forecast status and calendar actions use the displayed prediction's own round,
so an earlier coverage gap cannot mark a later forecast as past due.
See the [verified findings and browser QA](docs/reviews/2026-10-06-result-coverage/README.md).

## How a series gets promoted

Every sport moves through the same honest ladder: **scaffolded** (project tree +
core seams) → **experimental** (runs end-to-end on real data, accuracy accruing)
→ **production** (forward accuracy validated over real rounds). F2 proved the
template; F3 followed it in a fraction of the time — the FIA feeder-series
scraper, the spec-series skill model, and the entire probability/championship
stack were reused outright. Formula E, NASCAR and IndyCar each cloned that
recipe onto a very different data reality (a live API, an unofficial JSON
feed, and a hand-verified committed archive). The five scaffolded series are
ready for the same path the moment a data feed is wired.

## Documentation

[Platform improvement audit](docs/PLATFORM_IMPROVEMENT_AUDIT.md) ·
- [Continued model and fan-experience improvements](docs/CONTINUED_IMPROVEMENTS.md) — coherent probabilities, uncertainty fixes and driver exploration.
[Architecture](docs/architecture.md) · [Adding a sport](docs/adding-a-sport.md) ·
[Core API](docs/core-api.md) · [Data schema](docs/data-schema.md) ·
[Design system](docs/design-system.md) · [Branding system](docs/BRANDING_SYSTEM.md) ·
[Governance](GOVERNANCE.md) · [Org structure](.github/ORG_STRUCTURE.md)

## License

MIT — see [LICENSE](LICENSE).
