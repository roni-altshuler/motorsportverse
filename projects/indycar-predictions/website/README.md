# RaceIQ Indy website

Next.js static-export site for the MotorsportVerse IndyCar project — the same
RaceIQ design system as the F1/F2/F3/Formula E/NASCAR sites, re-themed to the
IndyCar racing-red accent (`#D31217`, registry palette). A DEEP accent on the
black canvas (the same problem family as FE's blue): hovers and small-text
renditions lift the base, and every text-on-accent foreground (`--accent-ink`)
is white.

## What's different from the NASCAR parent clone

- **No playoffs** — the championship is season-long points to the finale; the
  Chase panel, playoff gate and cut-line UI are gone. The standings "Title
  Race" tab shows the straight simulation to the last round.
- **Track types** — every round is `oval` / `road` / `street`; badged on the
  calendar and race header, threaded through the narrative rules, and used as
  the three calibration strata on /accuracy. A coarser `trackGroup`
  (oval vs road_street) names which of the model's two surface ratings drove
  a round.
- **No stage racing** — one classification per round; the stage panels are gone.
- **The Indy 500 is first-class** — `isIndy500` flags the crown jewel (33-car
  field, one-off entries); badged on the calendar, ribbon and race header.
- **Engine suppliers, not manufacturers** — `engineStandings` (Chevrolet /
  Honda) replaces NASCAR's three-make manufacturer panel.
- **DNF hazard is first-class** — every prediction row carries `pDnf`; the
  race tables surface it as a subtle risk indicator and the narrative card
  flags high-hazard favourites.

## Commands

```bash
npm install
PAGES_BASE_PATH= npm run build      # static export into ./out
node scripts/shoot.mjs [outdir]     # Playwright screenshot harness (after build)
```

The data under `public/data/` is produced by `python -m indycar_predictions.export`
(plus the forward_eval / drift_report / promotion_decision CLIs) from the
project root — the site never fetches at runtime.
