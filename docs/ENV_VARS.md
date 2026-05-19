# Environment Variables

Single reference for every environment variable the project reads. Vars are
loaded via either `python-dotenv` (if installed — see `requirements-dev.txt`)
or plain `os.environ`. Local development typically uses a `.env` file at the
project root; see `.env.example` for the template and the [Local development
setup section in the README](../README.md#local-development-setup).

## Quick reference

| Variable | Required | Default | Read by |
|----------|----------|---------|---------|
| `ODDS_API_KEY` | Yes (for value-finder) | — | `odds_ingest.py`, `export_value_data.py` |
| `F1_SEASON_YEAR` | No | `DEFAULT_SEASON_YEAR` in `f1_prediction_utils.py`; CI falls back to `date +%Y` | `f1_prediction_utils.py`, `.github/workflows/update_predictions.yml` |
| `F1_USE_LIVE_STANDINGS` | No | `1` (enabled) | `export_website_data.py::export_standings` |
| `F1_USE_LIVE_ROUND_RESULTS` | No | `1` (enabled) | `export_website_data.py::export_round` |
| `ENABLE_GAME_THEORY_ENHANCEMENTS` | No | `1` (enabled) | `export_website_data.py::export_round` |
| `F1_GAME_THEORY_POSTPROCESS_SCALE` | No | `1.2` (clamped to `[0.0, 2.5]`) | `f1_prediction_utils.py::apply_race_postprocessing`, `benchmark_game_theory_upgrades.py` |
| `F1_GAME_THEORY_UNCERTAINTY_SCALE` | No | inherits `F1_GAME_THEORY_POSTPROCESS_SCALE` (clamped to `[0.0, 2.5]`) | `f1_prediction_utils.py::apply_race_postprocessing`, `benchmark_game_theory_upgrades.py` |
| `F1_WEEKEND_TODAY` | No (test only) | `date.today()` | `gp_weekend.py::_utc_today` |
| `F1_WEEKEND_NOW_UTC` | No (test only) | `datetime.utcnow()` | `gp_weekend.py::_utc_now` |

---

## `ODDS_API_KEY`

- **Read by**: `odds_ingest.py` (`fetch_winner_odds`), `export_value_data.py`
  (via the dotenv load at module import).
- **Default**: none. The CLI in `odds_ingest.py` exits with code 2 if missing.
- **Required**: yes, for the live `/value` page data flow. Without it the
  `/value` page renders its empty state but the rest of the site (predictions,
  standings, race detail) is unaffected.
- **Example**:

  ```bash
  export ODDS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  ```

  In CI this is wired as a GitHub Actions repository secret and injected into
  the workflow with `env: ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}`.

- **The Odds API F1 gap (verified 2026-05)**: The Odds API's public catalog
  covers 160+ sports across 16 groups (American Football, Baseball, Basketball,
  Boxing, Cricket, Golf, MMA, Soccer, Tennis, etc.) but does **not** include
  any motorsport — F1 is unavailable on any tier. The key itself is valid and
  the project's tests exercise the client against a fixture, but
  `python odds_ingest.py --round N --season YYYY` will hit a 404 on the
  `motorsport_f1` sport key and exit with a clear error message listing
  alternative sources. **No quota is charged for the 404**, so a misconfigured
  run does not eat into the free-tier 500/month allowance.
  Alternative odds sources tracked in the Tier 2 roadmap:
  - Pinnacle direct API (funded account required)
  - Betfair Exchange API (KYC required; UK/AU/EU only)
  - Manual CSV import from Oddschecker / similar aggregator

---

## `F1_SEASON_YEAR`

- **Read by**: `f1_prediction_utils.py` (sets the module-level `SEASON_YEAR`
  constant at import time, which then drives every race file's calendar and
  driver-list lookup). Also referenced explicitly in
  `.github/workflows/update_predictions.yml` lines 38, 131, 151.
- **Default**: `DEFAULT_SEASON_YEAR` (compile-time constant inside
  `f1_prediction_utils.py`). The CI workflow falls back to `date -u +%Y` if the
  GitHub Actions repository variable is unset.
- **Required**: no.
- **Example**:

  ```bash
  export F1_SEASON_YEAR=2026
  ```

---

## `F1_USE_LIVE_STANDINGS`

- **Read by**: `export_website_data.py::export_standings` (~line 2012).
- **Default**: `1` (enabled). Disable with `0`, `false`, `no`, or `off`.
- **Required**: no.
- **Behaviour**: when truthy, `export_standings` fetches live driver +
  constructor standings from the Jolpica/Ergast-compatible API and writes them
  to `website/public/data/standings.json`, with local fallback if the API call
  fails. When falsy, the exporter uses the locally computed standings derived
  from cached race classifications.
- **Example**:

  ```bash
  export F1_USE_LIVE_STANDINGS=1   # default — official feed
  export F1_USE_LIVE_STANDINGS=0   # disable — use local computation
  ```

---

## `F1_USE_LIVE_ROUND_RESULTS`

- **Read by**: `export_website_data.py::export_round` (~line 872).
- **Default**: `1` (enabled). Disable with `0`, `false`, `no`, or `off`.
- **Required**: no.
- **Behaviour**: when truthy, completed-round files refresh their
  `actualResults` block from Jolpica/Ergast-compatible classified race results.
  When falsy, results stay sourced from FastF1 + local artifacts. Practical
  impact: keep this enabled for production pipelines and disable it when
  reproducing historical predictions.
- **Example**:

  ```bash
  export F1_USE_LIVE_ROUND_RESULTS=1
  ```

---

## `ENABLE_GAME_THEORY_ENHANCEMENTS`

- **Read by**: `export_website_data.py::export_round` (~line 649).
- **Default**: `1` (enabled). Disable with `0`, `false`, `no`, or `off`.
- **Required**: no.
- **Behaviour**: when truthy, the round export calls
  `advanced_models.apply_game_theory_enhancements` to inject undercut /
  overcut / DRS / battle / teammate-conflict terms into the postprocessed
  predictions. When falsy, the pipeline emits baseline regression output
  unchanged. The CLI flag `--disable-game-theory` on `export_website_data.py`
  has the same effect as setting this to `0`.
- **Example**:

  ```bash
  export ENABLE_GAME_THEORY_ENHANCEMENTS=0   # baseline ablation run
  ```

---

## `F1_GAME_THEORY_POSTPROCESS_SCALE`

- **Read by**: `f1_prediction_utils.py::apply_race_postprocessing` (line 1062)
  via the `_env_float` helper, plus `benchmark_game_theory_upgrades.py` which
  saves/restores the value while sweeping.
- **Default**: `1.2`. Clamped to `[0.0, 2.5]` regardless of input.
- **Required**: no.
- **Behaviour**: master gain on the game-theory postprocessing terms (undercut,
  overcut, team-order, DRS, battle, teammate conflict, field volatility). The
  default was calibrated by running
  `optimize_game_theory_postprocessing.py` over completed rounds 1–3 — see the
  saved tuning report under `reports/`. Setting it to `0.0` zeroes out the
  postprocess additively even when
  `ENABLE_GAME_THEORY_ENHANCEMENTS=1`.
- **Example**:

  ```bash
  export F1_GAME_THEORY_POSTPROCESS_SCALE=1.2
  ```

---

## `F1_GAME_THEORY_UNCERTAINTY_SCALE`

- **Read by**: `f1_prediction_utils.py::apply_race_postprocessing` (line 1064).
- **Default**: inherits the value of `F1_GAME_THEORY_POSTPROCESS_SCALE` (so
  `1.2` unless that one is overridden). Clamped to `[0.0, 2.5]`.
- **Required**: no.
- **Behaviour**: independent knob on the *uncertainty* portion of the
  postprocessing (versus the directional terms governed by
  `F1_GAME_THEORY_POSTPROCESS_SCALE`). Override it when sweeping the two
  dimensions separately during tuning.
- **Example**:

  ```bash
  export F1_GAME_THEORY_UNCERTAINTY_SCALE=1.0
  ```

---

## `F1_WEEKEND_TODAY` (test-only override)

- **Read by**: `gp_weekend.py::_utc_today`.
- **Default**: `date.today()`.
- **Required**: no.
- **Behaviour**: lets tests pin the apparent calendar date so `is_race_weekend`
  and friends are deterministic. Format is ISO `YYYY-MM-DD`. Production code
  should never set this.

---

## `F1_WEEKEND_NOW_UTC` (test-only override)

- **Read by**: `gp_weekend.py::_utc_now`.
- **Default**: `datetime.utcnow()`.
- **Required**: no.
- **Behaviour**: ISO datetime override for the current UTC instant. Same
  rationale as `F1_WEEKEND_TODAY` but for sub-day comparisons.

---

## Calibration gate (not an env var, but referenced from configuration)

The exporter `export_probabilities.py` reads no env vars — but it does take a
`--min-completed-rounds` flag (default `3`) that governs whether isotonic
calibration is actually applied to published probabilities. While only Round 4
of 2026 has actual results, calibration training is effectively empty: the
script honestly emits `calibration.applied = false` in each round JSON and the
`/value` page surfaces this disclaimer. Once the multi-season historical
backfill lands (audit §2.2, Tier 1), `applied` flips to `true` automatically
once the gate is satisfied — no code change needed.
