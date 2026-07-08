# RaceIQ Formula E website

Next.js static-export site for the MotorsportVerse Formula E project — the same
RaceIQ design system as the F1/F2/F3 sites, re-themed to the Formula E electric
blue accent (`#1E1AF0`, registry palette).

## What's different from the F3 golden template

- **Single-race weekends** — Formula E scores ONE race per round, so the race
  detail page has no sprint/feature tabs and `SprintGridFlip` is gone.
- **Doubleheaders** — two rounds share a venue key (`"Jeddah"`/`"Jeddah II"`);
  the calendar pairs them into one weekend card group and the race page's
  header + narrative carry "race N of 2" context.
- **Venue kind** — every round is `street` or `circuit`; badged on the
  calendar, the race header, and threaded through the narrative rules.
- **Split-year season** — the championship label is "2025-26" (`seasons.json`
  labels); `season` in the data is the END year.

## Data

All pages read `public/data/fe.json` (+ `rounds/`, `probabilities/`,
`forward_eval/`, `historical_backtest/`, `model_health.json`,
`promotion_status.json`, `calibration_summary.json`, `seasons.json`), generated
by the Python pipeline:

```bash
# from the project root, after installing the FE package + core/data:
python -m formula_e_predictions.export   # writes website/public/data/fe.json + fan-out
```

The TypeScript contract is `src/types/fe.ts`; its pydantic mirror lives in
`../tests/test_website_data_schema.py` — change both together.

## Develop / build / verify

```bash
npm install
PAGES_BASE_PATH= npm run build          # static export → out/
node scripts/shoot.mjs [/tmp/fe-shots]  # Playwright screenshot harness (after build)
```

`next.config.ts` reads `PAGES_BASE_PATH`; the unified Pages deploy sets it to
`/motorsportverse/projects/formula-e`.

Race art (`src/lib/raceArt.ts`) must stay aerial venue photography — every URL
curl-verified; venues with no verified aerial fall back to the gradient card.
`src/components/{ui,magicui}` are byte-identical mirrors of the F1 canonical
set (`scripts/sync_shared_ui.mjs --check` at the repo root).
