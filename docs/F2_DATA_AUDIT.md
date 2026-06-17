# RaceIQ F2 — Data Accuracy Audit

**Date:** 2026-06-17 · **Repo HEAD:** `de5cc5e` · **Branch:** `feat/f2-production`
**Goal:** Trace every discrepancy between what RaceIQ F2 displays and the official 2026 FIA Formula 2 season **to its exact code path**, and define the fix. No code was patched to produce this document.

---

## Methodology & sources of truth

| Source | Use | Verified this audit |
|--------|-----|---------------------|
| **fiaformula2.com** | Primary source of truth (calendar, results, qualifying, classifications) | ✅ Reachable (HTTP 200). In-repo `FiaF2Source._parse_session` **successfully parsed live 2026 Round 1** sprint + feature classifications. |
| **Wikipedia — 2026 Formula 2 Championship** | Cross-check (calendar, standings) | ✅ Fetched; standings & calendar below. |
| **Jolpica / Ergast** | Considered for results | ❌ **F2 not supported** — `api.jolpi.ca/ergast/f2/2026/...` returns 404. F1-only. Not usable. |
| Shipped site data | "Current displayed value" | ✅ Read from `projects/f2-predictions/website/public/data/f2.json` (generated from `SyntheticF2Source`). |

**Feasibility verdict:** the **real-actuals path is achievable via the FIA scraper** (`sources/fia_f2_source.py`), which already works on the live 2026 pages. The scraper is simply **not wired into the live pipeline**, and the calendar/completed-count are hardcoded. Fixing data accuracy is integration + content correction, not new modeling.

**Reference data captured (the "expected values" used throughout):**

*Official 2026 F2 calendar — 14 rounds (5 completed by 2026-06-17):*

| R | Venue (key) | Country | Sprint / Feature | Completed? |
|---|-------------|---------|------------------|-----------|
| 1 | Albert Park (melbourne) | Australia | 7 / 8 Mar | ✅ |
| 2 | Miami Int'l Autodrome (miami) | USA | 2 / 3 May | ✅ |
| 3 | Gilles Villeneuve (montreal) | Canada | 23 / 24 May | ✅ |
| 4 | Monaco (monaco) | Monaco | 6 / 7 Jun | ✅ |
| 5 | Barcelona-Catalunya (catalunya) | Spain | 13 / 14 Jun | ✅ |
| 6 | Red Bull Ring (spielberg) | Austria | 27 / 28 Jun | ⬜ |
| 7 | Silverstone (silverstone) | UK | 4 / 5 Jul | ⬜ |
| 8 | Spa-Francorchamps (spa) | Belgium | 18 / 19 Jul | ⬜ |
| 9 | Hungaroring (hungaroring) | Hungary | 25 / 26 Jul | ⬜ |
| 10 | Monza (monza) | Italy | 5 / 6 Sep | ⬜ |
| 11 | Madring (madrid) | Spain | 12 / 13 Sep | ⬜ |
| 12 | Baku City (baku) | Azerbaijan | 25 / 26 Sep | ⬜ |
| 13 | Lusail (losail) | Qatar | 28 / 29 Nov | ⬜ |
| 14 | Yas Marina (yas-marina) | UAE | 5 / 6 Dec | ⬜ |

*Official drivers' championship (top 10, after R5):* Minì 86 · Tsolov 80 · Câmara 69 · Dunne 67 · León 54 · Beganovic 53 · Stenshorne 48 · van Hoepen 43 · Maini 41 · Miyata 30.

*Official teams' championship:* Campos 134 · Rodin 115 · MP 98 · Invicta 90 · DAMS 65 · ART 54 · Trident 50 · Hitech 50 · Prema 30 · AIX 20 · VAR 13.

---

## D-1 — Calendar schedule  🔴 Blocking

| Field | Detail |
|-------|--------|
| **Source of truth** | fiaformula2.com / Wikipedia: 14 rounds in the order Australia, Miami, Montréal, Monaco, Barcelona, Austria, Silverstone, Spa, Hungary, Monza, Madrid, Baku, Lusail, Yas Marina. |
| **Current displayed value** | 12 rounds: Australia, **Monaco(R2)**, **Austria(R3)**, **Spain(R4)**, GB(R5), Belgium(R6), Hungary(R7), Italy(R8), Madrid(R9), Baku(R10), Qatar(R11), Abu Dhabi(R12). **Miami and Montréal are entirely absent.** |
| **Expected value** | The 14-round table above, with correct order and Sprint/Feature dates. |
| **Root cause** | `config.CALENDAR` is a **hardcoded** 12-entry list (`config.py` ~L18–37); it was hand-curated to F1-shared European circuits and never reconciled with the official F2 schedule. `totalRounds` derives from `len(config.CALENDAR)`. The live feed is never consulted for the calendar. |
| **Proposed fix** | Source the calendar from the FIA navigator (`FiaF2Source` exposes 14 raceids on anchor 1092) or replace `config.CALENDAR` with the verified 14-round table incl. dates. Add the two missing venue keys (`miami`, `montreal`) with circuit geometry + race-art. Derive `totalRounds` from the corrected list. |
| **Code path** | `config.py:CALENDAR` → `datasource.F2DataSource.season()` → `export.build_payload()` `"calendar"` (L~390) & `"totalRounds"` → `f2.json` → site `calendar/page.tsx`, `SeasonRibbon`, race-card grid. |

---

## D-2 — Completed-round count  🔴 Blocking

| Field | Detail |
|-------|--------|
| **Source of truth** | 5 rounds completed by 2026-06-17 (R5 Barcelona finished 14 Jun; R6 Austria is 27–28 Jun). |
| **Current displayed value** | `completedRounds: 6`, `lastUpdatedRound: 6`; rounds 1–6 marked `completed:true`; "next" = round 7 (Hungary, also mislabeled per D-1). |
| **Expected value** | `completedRounds: 5`; next round = round 6 (Austria). |
| **Root cause** | `COMPLETED_ROUNDS = 6` is a **hardcoded constant** (`config.py:40`); never derived from race dates or feed availability. |
| **Proposed fix** | Derive completed count from the feed (count rounds whose feature result exists) or from race dates vs. "today". Remove the hardcoded constant in favor of `len([r for r in calendar if has_result(r)])`. |
| **Code path** | `config.py:40 COMPLETED_ROUNDS` → `export.py` (`completed = rnd <= config.COMPLETED_ROUNDS`, L~474; calendar `dataSource` ternary L~398; `_points_history` L~313; `_season_accuracy` L~283) → `f2.json`. |

---

## D-3 — Race results are synthetic, presented as real  🔴 Blocking

| Field | Detail |
|-------|--------|
| **Source of truth** | Official classifications per round (e.g. **R1 Feature:** 1 Tsolov, 2 Câmara, 3 van Hoepen, 4 Goethe, 5 Miyata…; **R1 Sprint:** 1 Dürksen, 2 León, 3 Dunne, 4 Inthraphuvasak, 5 Miyata, 6 Minì…). |
| **Current displayed value** | Deterministic synthetic orders from `config._TRUTH_PACE` + Gaussian noise (seed = `year*1000+round*10+race_index`). All 22 classified, no DNF/DSQ/penalties. Marked `dataSource:"synthetic"`. |
| **Expected value** | The official classification for each completed round's sprint and feature. |
| **Root cause** | (a) `F2DataSource` defaults to `SyntheticF2Source`; (b) even in live mode, `CompositeF2Source.default()` = `[FastF1F2Source, OfficialF2Source, SyntheticF2Source]` — **the only working real source, `FiaF2Source`, is not in the stack**, and the other two are stubs returning `None`; (c) `export.py` **hardcodes** `dataSource:"synthetic"` instead of reading `source.provenance()`. |
| **Proposed fix** | Insert `FiaF2Source` at the front of `CompositeF2Source.default()`; have `export.py` read `source.provenance(year, round, race_index)` for the `dataSource` tag; run the deploy with `F2_USE_LIVE_RESULTS=1`. Forecasts remain for upcoming rounds. |
| **Code path** | `datasource.py:28–37` → `sources/composite.py:46–51 default()` & `:16 REAL_SOURCES` → `export.py` round payload `"dataSource"` (L~133) & calendar (L~398) → `rounds/round_NN.json` `classification/actualResults` → site `RaceDetail`. |

---

## D-4 — Driver standings & points  🔴 Blocking

| Field | Detail |
|-------|--------|
| **Source of truth** | Minì 86 · Tsolov 80 · **Câmara 69** · Dunne 67 · León 54 · Beganovic 53 · Stenshorne 48 · van Hoepen 43 · Maini 41 · Miyata 30. |
| **Current displayed value** | MIN **135** (6 wins, 6 podiums) · TSO 90 · **STE 85** · DUN 72 · LEO 72 · BEG 70 … (**Câmara absent from top 6**; MIN's 6-from-6 wins is a synthetic artifact). |
| **Expected value** | The official table above (recomputed from real sprint+feature classifications, with bonuses). |
| **Root cause** | Standings are computed by `motorsport_core.standings.compute_driver_standings` over **synthetic** results (D-3). **The points logic is correct** — the *inputs* are fictional. Count error (6 vs 5 rounds, D-2) inflates totals further. |
| **Proposed fix** | Once real results flow (D-3) and the round count is correct (D-2), standings recompute correctly with no formula change. Validate the regenerated top-10 against the official table above (a Phase-3 acceptance test). |
| **Code path** | real results → `standings.compute_driver_standings(results, FEATURE_POINTS/SPRINT_POINTS, bonus)` → `export.py` `driverStandings` (+ `_points_history` L~313) → `f2.json` → `StandingsPage`. |

---

## D-5 — Team standings & points  🔴 Blocking

| Field | Detail |
|-------|--------|
| **Source of truth** | Campos 134 · Rodin 115 · MP 98 · Invicta 90 · DAMS 65 · ART 54 · Trident 50 · Hitech 50 · Prema 30 · AIX 20 · VAR 13. |
| **Current displayed value** | Campos **162** · **MP 157** · **Rodin 157** · DAMS 88 · ART 86 · Invicta 60. Ordering & totals differ (Rodin should be 2nd, Invicta should be 4th not 6th). |
| **Expected value** | The official team table above. |
| **Root cause** | Same as D-4: `compute_team_standings` over synthetic results via `team_of` mapping. Logic correct; inputs synthetic. |
| **Proposed fix** | Inherited from the D-3 fix; validate regenerated team table against official. |
| **Code path** | `standings.compute_team_standings(results, points, team_of=config.TEAM_OF, bonus)` → `export.py` `teamStandings` → `f2.json` → `StandingsPage`. |

---

## D-6 — Penalties, DNFs, classifications  🟠 Important

| Field | Detail |
|-------|--------|
| **Source of truth** | Official classifications already incorporate post-race penalties, DNF/DNS/DSQ, and not-classified status. |
| **Current displayed value** | Synthetic generator always classifies **all 22** finishers in pace order; **no penalties, no DNFs, no DSQ** exist in the model. |
| **Expected value** | Real classifications with retirements and penalty-adjusted finishing order; points awarded on the *classified* result. |
| **Root cause** | `SyntheticF2Source._sample_order` returns a full 22-driver permutation with no status field; the canonical `Result.status`/DNF (`position=None`) is unused on the synthetic path. |
| **Proposed fix** | Use the FIA classification (which is already penalty-adjusted). Map non-classified drivers to `position=None`/status in the `Result` schema; ensure standings skip them (already supported by `motorsport_core.standings`). Harden the scraper so retired drivers are represented (see D-9). |
| **Code path** | `sources/fia_f2_source.py:_parse_session` → `Result` rows → `standings.*` / `export` classification. |

---

## D-7 — Qualifying results  🟠 Important

| Field | Detail |
|-------|--------|
| **Source of truth** | Each round has an official **qualifying** classification that sets the feature-race grid (and, reversed top-10, the sprint grid). |
| **Current displayed value** | The site shows a **predicted** "qualifying" = the model's merit order (`nextPrediction.qualifying`, and each round's `grid` is the predicted merit grid). No real qualifying/grid is shown for completed rounds. |
| **Expected value** | For **completed** rounds: the **actual** qualifying order / starting grid. For **upcoming** rounds: the predicted merit grid (as now). |
| **Root cause** | The FIA scraper currently parses only the **Sprint Race** and **Feature Race** session tables (`_SESSION_HEADING = {0:"Sprint Race", 1:"Feature Race"}`); it does not fetch the Qualifying session. The export has no concept of a real starting grid. |
| **Proposed fix** | Extend `FiaF2Source` to also parse the Qualifying classification and (optionally) the feature starting grid; in `export.py`, populate completed rounds' `grid`/qualifying from the real session, keep predicted quali for upcoming rounds. Keep the predicted-vs-actual quali available for accuracy. |
| **Code path** | `sources/fia_f2_source.py` session map → new `qualifying()` → `export.py` round `grid` + `nextPrediction.qualifying` → `RaceDetail` / `predictions/page.tsx`. |

---

## D-8 — Sprint vs feature handling  🟢 Mostly correct (validate)

| Field | Detail |
|-------|--------|
| **Source of truth** | F2 weekend = Qualifying → Sprint (grid = reverse of top-10 of quali) → Feature (grid = quali order). Sprint points top 8 (10-8-6-5-4-3-2-1); Feature points top 10 (25-18-15-12-10-8-6-4-2-1); pole (feature) +2; fastest lap +1 (top-10 + classified). |
| **Current displayed value** | Model: feature = merit grid; sprint = reverse top-10 of merit + `SPRINT_GRID_PENALTY=0.12`. Points tables in `config.py` **match official exactly**. Championship MC alternates sprint+feature (`races_per_round=2`). |
| **Expected value** | Same structure — confirmed correct. The only gap: the model derives the sprint grid from *predicted merit*, whereas reality derives it from *qualifying*. For completed rounds the actual grids should come from the feed (ties to D-7). |
| **Root cause** | By design for forecasting; not a defect. Points tables and weekend structure are accurate. |
| **Proposed fix** | No change to points/structure. For completed rounds, use real sprint/feature classifications (D-3) and real grids (D-7). Add an acceptance test asserting `FEATURE_POINTS`/`SPRINT_POINTS`/bonuses equal the official tables (guards against future drift). |
| **Code path** | `config.py:100–103` (points/bonus), `:129–130` (reverse grid), `model._reverse_grid` / `project_championship_f2`. |

---

## D-9 — Real-feed robustness  🟠 Important (enabler for all of the above)

| Field | Detail |
|-------|--------|
| **Observation** | On the live 2026 Round 1 page the in-repo parser returned **21 sprint / 19 feature** rows (expected 22). Likely causes: rows without a 3-letter code, retired/penalised entries, or mobile/desktop duplicate-row handling. Team alignment per row should also be validated against the known roster. |
| **Root cause** | `_parse_session` is regex/positional and tolerant; some rows (DNF, code-less) drop out, and the dedup-by-position step can shorten the list. |
| **Proposed fix** | Harden `_parse_session`: align by car number against `config.DRIVERS`, represent retirements as `position=None`, and add a count/identity assertion (warn if classified count ≠ entry list). Add a fixture test from a *current* 2026 page. Wire `"fia"` into `REAL_SOURCES` so its rounds count toward the calibration gate. |
| **Code path** | `sources/fia_f2_source.py:_parse_session`, `sources/composite.py:16 REAL_SOURCES`, `tests/test_fia_scraper.py`. |

---

## D-10 — Season-accuracy & calibration honesty  🟠 Important

| Field | Detail |
|-------|--------|
| **Source of truth** | Accuracy must compare model predictions to **official** results; calibration may only claim to be applied when trained on real rounds. |
| **Current displayed value** | `seasonAccuracy` = model scored vs **synthetic** "actuals" (`meanPositionError 4.667`, `winnerHitRate 0.333`) — not a real metric. `calibration.applied = false` (correct, but for the wrong reason: 0 real rounds because feed unwired). |
| **Expected value** | `seasonAccuracy` computed vs real results; `calibration.applied` flips true once ≥4 real rounds are backfilled. |
| **Root cause** | D-3 (synthetic inputs). `REAL_SOURCES` excludes `"fia"`, so even a wired scraper wouldn't open the gate. The calibration *gate logic itself is correct and honest.* |
| **Proposed fix** | After D-3/D-9, `seasonAccuracy` becomes meaningful automatically; add `"fia"` to `REAL_SOURCES`; once 4 real rounds exist, the gate opens honestly and the site banner updates. |
| **Code path** | `export.py:_season_accuracy` (L~283), `build_calibrator` (L~214–240), `config.py:177 MIN_REAL_ROUNDS_FOR_CALIBRATION`, `sources/composite.py:16`. |

---

## Summary & Phase-3 remediation order

| ID | Discrepancy | Severity | Fix locus |
|----|-------------|----------|-----------|
| D-1 | Calendar wrong (12 vs 14, order, missing Miami/Montréal) | 🔴 | `config.py` calendar (from feed) |
| D-2 | Completed count 6 vs 5 | 🔴 | derive from feed/dates |
| D-3 | Synthetic results shown as real | 🔴 | wire `FiaF2Source`, read provenance, `F2_USE_LIVE_RESULTS=1` |
| D-4 | Driver standings/points fictional | 🔴 | inherited from D-3 (validate vs official) |
| D-5 | Team standings/points fictional | 🔴 | inherited from D-3 (validate vs official) |
| D-6 | No penalties/DNF/DSQ | 🟠 | use real classification |
| D-7 | No real qualifying/grid | 🟠 | extend scraper to qualifying |
| D-8 | Sprint/feature structure | 🟢 | correct; add guard test |
| D-9 | Scraper robustness (21/19 vs 22) | 🟠 | harden parser; `"fia"`∈REAL_SOURCES |
| D-10 | Accuracy/calibration honesty | 🟠 | inherited from D-3/D-9 |

**Recommended Phase-3 sequence:** (1) harden + wire `FiaF2Source` (D-3, D-9); (2) replace the calendar + completed-count from the feed (D-1, D-2); (3) read provenance & emit real actuals + forecasts (D-3); (4) extend qualifying (D-7); (5) backfill HistoryStore, open calibration gate, real `seasonAccuracy` (D-10); (6) **acceptance test**: regenerated `f2.json` top-10 drivers/teams match the official tables in this document within rounding; calendar = 14 rounds; `completedRounds = 5`. Then re-evaluate the `experimental → production` maturity flip.

> The points tables, weekend structure, model, championship Monte Carlo, calibration gate, and website are **correct and reusable as-is**. This is a data-wiring + content-accuracy remediation, exactly as scoped.
