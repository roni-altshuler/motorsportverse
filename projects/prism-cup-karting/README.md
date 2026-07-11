# Prism Cup Karting

A just-for-fun MotorsportVerse project: a fictional kart-racing league in the
great arcade tradition — twelve original mascot racers across three weight
classes, eight fantasy circuits, four cups, homing orbs, boost-pad chains and
midfield-shuffling storms. The whole season is produced by a seeded simulator;
the website bakes those results and also runs the same engine live in the
browser ("Race Night" on the home page).

> A fan-made fictional league. All characters, items, tracks and results are
> simulated and original. Not affiliated with any video game company.

## Layout

```
src/prism_cup/
  config.py     roster (stats, weight classes, item-luck), items table,
                8 tracks (hazard / laps / boost-pad density), 4 cups, points
  simulate.py   seeded race + season simulator with the item mechanics
  export.py     CLI — writes website/public/data/*.json
tests/          determinism, classification integrity, measured mechanics,
                export schema (mirrors website/src/lib/types.ts)
website/        Next.js 16 + Tailwind v4 static export (sibling of the
                RaceIQ family, prism-violet accent, bespoke lean components)
```

## Simulator mechanics (the genre, with original names)

- **Rubber-banding**: item draws are position-weighted — the back of the
  field pulls the strong equalisers (Seeker Orb, Tempest, Comet Boost), the
  front mostly defensive tools.
- **Seeker Orb** always hunts the current leader; a **Static Shield** blocks
  one hit; knock-back scales inversely with `knock_resistance`, so heavies
  lose fewer places per hit.
- Pace is accel-weighted early in a race and top-speed-weighted late; track
  `hazard` scales lap-to-lap variance and `boost_pad_density` feeds
  boost-chain moves.

All of this is asserted statistically in `tests/test_simulate.py`.

## Regenerating the data

From this directory (stdlib only — no extra installs needed):

```bash
PYTHONPATH=src ../../.venv/bin/python -m prism_cup.export            # default seed
PYTHONPATH=src ../../.venv/bin/python -m prism_cup.export --seed 42  # a different season
PYTHONPATH=src ../../.venv/bin/python -m pytest -q                   # tests
```

The exporter is deterministic for a given seed and writes
`website/public/data/{prism-cup,roster,tracks}.json` and `cups/cup_[1-4].json`.

## Website

```bash
cd website
npm install
PAGES_BASE_PATH= npm run build      # static export to out/
node scripts/shoot.mjs              # Playwright screenshots (port 4342)
```
