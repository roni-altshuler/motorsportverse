# MotorsportVerse — Project State Audit

**Date:** 2026-06-17
**Auditor:** Claude (takeover of next development phase)
**Repo HEAD at audit:** `de5cc5e` (origin/main) · audit branch `feat/f2-production`
**Scope:** Full repository inspection ahead of bringing **RaceIQ F2** to production. No code was modified to produce this document.

> **Read this first.** The local checkout was 10 commits behind `origin/main` when this engagement began (`8f45493` → `de5cc5e`). All findings below are against the **synced** tree (`de5cc5e`). The remote already contains most of the F2 product + host redesign; the branch `feat/f2-parity-and-host-redesign` is merged into main and obsolete; there are no open PRs; CI on `origin/main` is green. This is a *finish + validate + correct* effort, **not** a from-scratch build.

---

## 0. Executive summary

| Area | State | One-line |
|------|-------|----------|
| Monorepo foundation | ✅ Solid | scverse-style: 2 shared packages + per-sport projects + registry + 2 websites |
| Shared libraries (`motorsport-core`, `motorsport-data`) | ✅ Production-grade | Rich, tested, sport-agnostic; ~75% of F2 reuses them |
| F2 backend pipeline | ✅ Built / ⚠️ wired to synthetic | End-to-end model, two race heads, championship MC, honest calibration gate — but runs on **synthetic** data |
| F2 website | ✅ Built, F1-parity | Home/calendar/standings/predictions/race/accuracy/about, charts, circuit maps |
| Host/ecosystem site | ✅ Redesigned | Linear/Vercel-grade landing, command palette, WebGL hero |
| Branding | ✅ System in place | RaceIQ single-logo + per-series color; 23 generated SVGs + PNG artwork |
| CI / deploy | ✅ Green | ruff + pytest + registry validate + dual static-export deploy to Pages |
| **Data accuracy** | ❌ **Blocking** | Calendar wrong (12 vs official 14), results synthetic, completed-count wrong (6 vs 5) — see `F2_DATA_AUDIT.md` |

**Bottom line:** the *engineering* is largely done and high-quality. The single thing standing between F2 and a credible production launch is **data**: the site presents an invented 12-round calendar with model-generated ("synthetic") results as if they were the 2026 season. The working real feed (fiaformula2.com scraper) exists in the tree but **is not wired into the live path**. Closing that gap is Phase 3.

---

## 1. Current architecture map

```
                       ┌─────────────────────────────────────────┐
                       │  registry/projects/*.json (catalog SoT)  │
                       │  → build_registry(.py/.mjs) → registry.json│
                       └───────────────┬─────────────────────────┘
                                       │ consumed at build
        ┌──────────────────────────────┴───────────────┐
        │                                               │
┌───────▼────────┐                            ┌─────────▼──────────┐
│ website/ (HUB) │  Next.js 16 static export  │ projects/f2-…/website│ Next.js 16 static export
│ ecosystem hub  │                            │ RaceIQ F2 site       │
└────────────────┘                            └─────────▲──────────┘
                                                         │ reads public/data/*.json
                                              ┌──────────┴───────────┐
                                              │ f2_predictions.export │  (single JSON producer)
                                              └──────────┬───────────┘
                                                         │ uses
                  ┌──────────────────────────────────────┴───────────────────────┐
                  │ projects/f2-predictions/src/f2_predictions/                    │
                  │  config(calendar/roster/points) · datasource (seam) ·          │
                  │  model (Elo+history+ML→pace→2 heads) · sources/* (synth+FIA) ·  │
                  │  backfill · forward_eval · drift_report · promotion_decision   │
                  └───────────────┬───────────────────────────┬───────────────────┘
                                  │ supplies DataSource+Predictor; inherits everything else
            ┌─────────────────────▼──────────┐   ┌────────────▼─────────────────┐
            │ packages/motorsport-core        │   │ packages/motorsport-data      │
            │ calibration · championship ·    │   │ schema (pydantic) · store      │
            │ standings · elo · eval · drift ·│   │ (DuckDB HistoryStore) ·        │
            │ promotion · registry · leakage ·│   │ sources/base+jolpica · rollover│
            │ conformal · reliability         │   │                                │
            └─────────────────────────────────┘   └────────────────────────────────┘
```

**The reuse contract:** a sport supplies a `DataSource` (calendar/results) + a `Predictor`; everything numerically heavy (calibration, championship Monte Carlo, standings, Elo, eval, drift, promotion, leakage guards) is inherited from `motorsport-core`. F2's `registry` entry lists `uses_core = [calibration, championship, standings, elo, conformal, eval, drift, promotion, leakage, interfaces]`.

---

## 2. Directory tree summary

```
motorsportverse/
├── CLAUDE.md, README.md, CONTRIBUTING.md, GOVERNANCE.md, LICENSE
├── pyproject.toml            # uv workspace (members: packages/*, projects/*); ruff E/F/W, line 100, py311
├── .github/workflows/
│   ├── ci.yml                # python job (ruff+pytest core/data/f2 + registry validate) + website build
│   └── deploy-website.yml    # regen F2 data → build both sites → Pages (/<repo>/ and /<repo>/projects/f2/)
├── packages/
│   ├── motorsport-core/      # src/motorsport_core/{calibration,championship,standings,elo,eval,
│   │                         #   leakage,drift,promotion,registry,conformal,reliability,era,
│   │                         #   hierarchical_bayes,interfaces,features/*}  + tests/
│   └── motorsport-data/      # src/motorsport_data/{schema,store,rollover,sources/{base,jolpica}} + tests/
├── projects/f2-predictions/
│   ├── pyproject.toml        # deps: motorsport-core/data; optional [ml]=xgboost; NO tool.uv.sources
│   ├── src/f2_predictions/   # config, datasource, model, ml_skill, export, backfill, forward_eval,
│   │                         #   drift_report, promotion_decision, train_race_pace(dormant),
│   │                         #   predict, sources/{synthetic,composite,fia_f2_source,fastf1_source,official_source}
│   ├── tests/                # 13 test files (pipeline, model, sources, scraper, calibration gate, backfill, schema…)
│   └── website/              # Next.js 16 site (mirrors F1 flagship); public/data/* is the export output
├── registry/
│   ├── index.json            # generated catalog (11 projects)
│   ├── projects/*.json        # 11 entries (f1=production, f2=experimental, 9=concept)
│   └── schema/                # project.schema.json, maturity.schema.json
├── website/                  # ecosystem hub (Next.js 16 static export)
├── scripts/                  # build_registry.py, build_registry_node.mjs, new_project.py, generate_brand.py
├── templates/project-template/  # scaffold for `new_project.py`
└── docs/                     # architecture, design-system, core-api, data-schema, BRANDING_SYSTEM,
                              #   REPO_AUDIT, F2_READINESS, IMPLEMENTATION_SUMMARY, adding-a-sport, index
                              #   (+ this file, F2_DATA_AUDIT, F2_DESIGN_REVIEW, BRANDING_RECOMMENDATION)
```

---

## 3. Existing data sources

| Source | File | Status | Notes |
|--------|------|--------|-------|
| **SyntheticF2Source** | `sources/synthetic.py` | ✅ Active (default) | Deterministic seeded finishing orders from `config._TRUTH_PACE`; CI-safe; **this is what the live site currently ships.** |
| **FiaF2Source** (official scrape) | `sources/fia_f2_source.py` | ✅ Works, ⚠️ **not wired into live path** | Regex-parses `fiaformula2.com/Results?raceid=N`. **Verified during this audit: it parsed live 2026 Round 1 sprint+feature classifications correctly.** Not included in `CompositeF2Source.default()`. |
| **FastF1F2Source** | `sources/fastf1_source.py` | ⛔ Stub | `_load()` always returns `None` (FastF1 has no F2 sessions). |
| **OfficialF2Source** | `sources/official_source.py` | ⛔ Stub | Returns `None` unless `OFFICIAL_F2_RESULTS_URL` set + `F2_ENABLE_OFFICIAL_FETCH=1`. URL is empty. |
| **CompositeF2Source** | `sources/composite.py` | ✅ Active in live mode | `default()` = `[FastF1F2Source, OfficialF2Source, SyntheticF2Source]` → **both real members are stubs, so it always falls back to synthetic even with `F2_USE_LIVE_RESULTS=1`.** |
| **JolpicaClient** (shared) | `motorsport_data/sources/jolpica.py` | ⚠️ F1-only | Verified this audit: `api.jolpi.ca/ergast/f2/2026/...` → **404**. Ergast/Jolpica covers F1 only. `JolpicaClient(series="f2")` is effectively dead for F2. |
| **HistoryStore** (DuckDB) | `motorsport_data/store.py` | ✅ Available | Durable predicted-vs-actual record for calibration/eval; `backfill.py` writes to it. |

**Source of truth for F2 (confirmed):** `fiaformula2.com` (official; scraper works), cross-checked against Wikipedia "2026 Formula 2 Championship". `FIA_F2_SEASON_ANCHORS = {2024: 1064, 2026: 1092}`; the navigator on raceid 1092 exposes **14 raceids** (1092, 1095–1107) = the real 14-round calendar.

---

## 4. Existing APIs

This is a **static-export** product — there is no runtime backend/API. The "API" surface is:

1. **Python module entry points** (run in CI/deploy and locally):
   - `python -m f2_predictions.export` → writes the website JSON contract.
   - `python -m f2_predictions.forward_eval --season 2026 [--allow-empty]`
   - `python -m f2_predictions.drift_report --season 2026 [--allow-empty]`
   - `python -m f2_predictions.promotion_decision --season 2026 [--allow-empty]`
   - `python -m f2_predictions.backfill` → HistoryStore.
   - `scripts/build_registry.py` / `build_registry_node.mjs` → registry.json.
2. **The JSON data contract** (`projects/f2-predictions/website/public/data/`), the real inter-process API between Python and the site: `f2.json`, `rounds/round_NN.json`, `probabilities/round_NN.json`, `calibration_summary.json`, `model_health.json`, `promotion_status.json`, `forward_eval/*`, `circuits.json`. Mirrored in TypeScript (`src/types/f2.ts`) and gated by `tests/test_website_data_schema.py`.
3. **External data APIs consumed:** `fiaformula2.com` (HTML scrape) is the only live one; Jolpica is F1-only and unused for F2.

---

## 5. Existing F2 implementation status (backend)

**Maturity in registry:** `experimental`. **Verdict: feature-complete engine, mis-fed data.**

| Capability | Status | Evidence / location |
|------------|--------|---------------------|
| Season config (calendar, roster, teams, points) | ⚠️ Present but **calendar wrong** | `config.py`: 12 hardcoded rounds, `COMPLETED_ROUNDS=6`. Roster (22 real drivers) & teams (11) & points tables are correct. |
| DataSource seam (synthetic/live) | ✅ / ⚠️ | `datasource.py` `F2_USE_LIVE_RESULTS`; composite excludes the working FIA source. |
| Unique spec-series skill model | ✅ | `model.py` blends Elo (0.55) + finishing history (0.45) + team (0.12) + optional ML (GBR+XGB) + optional Bayesian; rookie pooling. |
| Two race heads (feature merit / reverse-grid sprint) | ✅ | `model.py` `_race_forecast`, `_reverse_grid` (top-10 reversed), `SPRINT_GRID_PENALTY=0.12`. |
| Probabilities (win/podium/top6/top10 + H2H) | ✅ | via `motorsport_core.calibration.plackett_luce_probabilities`. |
| Finishing-range intervals + confidence | ✅ | MC positional quantiles + `conformal.width_to_confidence_label`. |
| Championship Monte Carlo (sprint+feature alternation) | ✅ | `model.project_championship_f2`, `races_per_round=2`. |
| Honest calibration gate | ✅ | `MIN_REAL_ROUNDS_FOR_CALIBRATION=4`; `REAL_SOURCES={fastf1,official}` (note: excludes `fia`). Currently `applied=false` (0 real rounds). |
| Backfill → HistoryStore | ✅ | `backfill.py`, sprint offset `+50`. |
| Forward-eval / drift / promotion | ✅ | reuse `motorsport_core.{eval,drift,promotion}`. |
| Per-lap race simulator | 💤 Dormant | `train_race_pace.py`, `USE_RACE_SIMULATOR=False` (no F2 lap feed). |
| Tests | ✅ | 13 files, 68 tests pass (see §"test suites"). |

---

## 6. Existing F2 website status

**Stack:** Next.js 16.1.6, React 19, Tailwind v4, static export (`output:"export"`), framer-motion + GSAP + Lenis, Recharts + `@visx/*` (`.npmrc` pins `legacy-peer-deps`). Mirrors the F1 flagship design, themed F2 electric-blue (`--accent: #1E9BD7`).

**Routes:** `/` (HomePage: hero parallax, race-card carousel, championship bento, podium stage, marketing sections), `/calendar/`, `/standings/` (driver+team, progression charts, who-can-win lanes), `/predictions/` (next round), `/race/[round]/` (sprint+feature, circuit map, heatmaps, H2H), `/accuracy/` (calibration, forward-eval, model health), `/about/`.

**Data layer:** `lib/f2data.ts` (fs-based, build-time), `lib/f2client.ts` (client fetch + round lifecycle), `lib/teams.ts` (fs-free color map), `lib/raceArt.ts` (Wikimedia aerial photography). Driver portraits via `DriverPortrait`/`DriverHeadshot` with conic-gradient fallback. Circuit SVGs from `circuits.json`.

**Status:** ✅ Visually complete and on-par with F1. It faithfully renders whatever `export.py` produces — so today it faithfully renders **synthetic** data. No website bug blocks launch; the blocker is upstream data. (Design-parity nuances are in `F2_DESIGN_REVIEW.md`.)

---

## 7. Existing F2 prediction pipeline status

End-to-end and correct *as a pipeline*; the inputs are synthetic. Flow:

`config.CALENDAR/roster` → `F2DataSource` (synthetic) → `model.estimate_skill` (leakage-guarded, prior rounds only) → pace → **feature** (merit grid) + **sprint** (reverse grid + penalty) heads → `calibration.plackett_luce_probabilities` / `sample_finishing_orders` → per-round payloads + `championship.project_championship` → `export.py` writes JSON. Calibration stays **off** until ≥4 real rounds.

Two honesty caveats worth noting now (detailed in the data audit):
- `dataSource` is **hardcoded** to `"synthetic"` in `export.py` rather than read from `source.provenance(...)`.
- `seasonAccuracy` is computed against **synthetic "actuals"** (model vs its own generator), so it is not a real accuracy measurement (currently `meanPositionError=4.667`, `winnerHitRate=0.333`).

---

## 8. Existing branding assets

A coherent system already exists (decision detailed in `BRANDING_RECOMMENDATION.md`):

- **Generator:** `scripts/generate_brand.py` emits 23 SVGs.
- **Series lockups:** `website/public/brand/series/raceiq-{f1,f2,f3,formula-e,indycar,nascar,wec,wrc}.svg` — shared condensed wordmark + forward-chevron + telemetry-tick baseline; **only the color changes per series** (F1 `#E10600`, F2 `#1E9BD7`, …).
- **Sport marks:** `website/public/brand/sports/*.svg` (11) — catalog icons / favicon source.
- **Ecosystem artwork (PNG):** `website/public/brand/motorsportverse-{logo,mark}.png` + `source/…collage.png`; `favicon.svg`; `og/default.svg`.
- **F2 site brand:** `projects/f2-predictions/website/public/brand/{logo,mark}.svg`.
- **Docs:** `docs/BRANDING_SYSTEM.md` documents the single-logo + per-series-color decision.

Assets are explicitly "clean placeholders, replaceable without changing paths."

---

## 9. Existing technical debt

| # | Debt | Severity | Location |
|---|------|----------|----------|
| D1 | **Working FIA scraper not wired** into `CompositeF2Source.default()` | High | `sources/composite.py` |
| D2 | `REAL_SOURCES` excludes `"fia"` → scraper data wouldn't count toward calibration even if wired | High | `sources/composite.py:16` |
| D3 | `dataSource` hardcoded `"synthetic"` instead of reading provenance | High | `export.py` (~L133, L398) |
| D4 | Calendar + `COMPLETED_ROUNDS` hardcoded, never derived from feed/dates | High | `config.py` |
| D5 | `seasonAccuracy` scored vs synthetic actuals (misleading metric) | Med | `export.py` `_season_accuracy` |
| D6 | `JolpicaClient(series="f2")` is dead (Ergast = F1-only) but present as if usable | Med | `motorsport_data/sources/jolpica.py` |
| D7 | F2 project lacks `tool.uv.sources` → won't `uv pip install` cleanly via workspace | Low | `projects/f2-predictions/pyproject.toml` (per CLAUDE.md) |
| D8 | Base UI components (Card/Button/Badge/Stat…) duplicated across host + F2 sites | Low | both `website/src/components/ui/*` |
| D9 | `test_smoke.py` asserts maturity ∈ {in-development, experimental} — will block a production flip until relaxed | Low (expected) | `tests/test_smoke.py` |
| D10 | FIA scraper returned 21/19 rows for Round 1 (vs 22) on live page — minor robustness (DNS/code-less rows) to harden | Med | `sources/fia_f2_source.py` |
| D11 | F1 still keeps private copies of core (intentional, deferred); not in scope | Info | per `REPO_AUDIT.md` |

---

## 10. Blocking issues preventing F2 launch

Ordered by how hard they block a *credible* launch (full root-cause + fix in `F2_DATA_AUDIT.md`):

1. **B1 — Calendar is wrong.** Site shows **12** invented rounds in the wrong order (Australia→Monaco→Austria→Spain→GB→Belgium→…); the official 2026 season has **14** (Australia→Miami→Montréal→Monaco→Barcelona→Austria→Silverstone→Spa→Hungary→Monza→Madrid→Baku→Lusail→Yas Marina). Missing Miami & Montréal entirely.
2. **B2 — Results are synthetic, presented as real.** Every completed round is model-generated; standings/points/wins are fictional (e.g. shipped MIN 135 / 6 wins vs real Minì 86; shipped team Campos 162 vs real 134).
3. **B3 — Completed-round count wrong.** Shows 6 completed; only **5** are done as of 2026-06-17 (Barcelona R5 on Jun 14; Austria R6 is Jun 27–28).
4. **B4 — Real feed not wired** (D1–D3): the one working source (FIA scraper) is excluded from the live path, and provenance is hardcoded.
5. **B5 — Calibration & accuracy cannot be honest** until real rounds flow (B2/B4); `applied=false` and `seasonAccuracy` is vs synthetic.

**None of these are website or modeling defects** — they are data-wiring + content-accuracy issues. The remediation plan (repoint to the real FIA feed, correct the calendar, emit real actuals + forecasts, flip calibration honestly) is Phase 3, contingent on checkpoint approval.

---

## Appendix — build pipelines, test suites, deployment

**CI (`.github/workflows/ci.yml`):** `python` job (Python 3.11): editable-install core+data+f2, `pip install xgboost`, `ruff check packages/motorsport-core packages/motorsport-data projects scripts`, `pytest` core / data / f2, `python scripts/build_registry.py`. `website` job (Node 20): `npm install && npm run build`. No matrix.

**Deploy (`.github/workflows/deploy-website.yml`):** on push to `main` (path-filtered) or manual. Regenerates F2 data (`export` + forward_eval + drift + promotion with `--allow-empty`), builds hub (`PAGES_BASE_PATH=/<repo>`) and F2 site (`/<repo>/projects/f2`), assembles `website/out/projects/f2`, deploys to Pages. **Note: deploy does not set `F2_USE_LIVE_RESULTS`, so it ships synthetic data today.**

**Test suites (baseline, this audit):** `motorsport-core` + `motorsport-data` = **92 passed**; `f2-predictions` = **68 passed** (~2m46s; ML tests dominate). `ruff check packages projects scripts` = **clean**. Total **160 passing, 0 failing**.

**Registry:** 11 projects — `f1-predictions` (production), `f2-predictions` (experimental), 9 concepts. Schema enforces slug/name/sport/category/maturity/summary; validated in CI by both the Python and Node builders (byte-identical output).
