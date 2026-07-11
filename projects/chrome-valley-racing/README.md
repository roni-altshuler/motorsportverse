# Chrome Valley Racing League

A just-for-fun MotorsportVerse project: a fully simulated racing league in the
"anthropomorphic race cars in small-town Americana" genre, with an interactive
website. Twelve original characters, ten invented venues, one seeded season.

> **A fan-made fictional league. All characters, venues and results are
> simulated and original. Not affiliated with any film studio.**

## What's here

```
src/chrome_valley/
├── config.py     the roster (12 characters with grit/showboat/consistency/
│                 heart traits), 10 venues, mentorships, rivalries
├── simulate.py   seeded season simulator — personality IS the physics:
│                 showboats crash while leading late, high-heart racers surge
│                 in the final laps, the mentor's rookie gains pace round by
│                 round, pit drama, rivalry momentum
└── export.py     CLI that bakes the season into website/public/data/
website/          Next.js 16 + Tailwind v4 static-export site: home page with
                  a live client-side race simulator ("Race Day"), /garage
                  character cards, /season calendar + standings + stories
```

Unlike the prediction projects, this one has **no motorsport-core dependency
and no real-world data** — it is stdlib-only Python plus a lean bespoke
frontend (deliberately outside the shared-UI drift gate).

## Regenerate the data

```bash
cd projects/chrome-valley-racing
PYTHONPATH=src ../../.venv/bin/python -m chrome_valley.export            # default seed 7
PYTHONPATH=src ../../.venv/bin/python -m chrome_valley.export --seed 21  # a different season
```

The export is deterministic per seed (no timestamps) and writes
`website/public/data/{chrome-valley.json, roster.json, rounds/round_NN.json}`.

## Tests & site

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q          # simulator + export contracts
cd website && npm install && PAGES_BASE_PATH= npm run build  # static export → out/
node scripts/shoot.mjs                                       # screenshot harness (port 4341)
```

The website's Race Day section ports the simulator to TypeScript
(`website/src/lib/sim.ts`) and runs it entirely in the browser — pick a venue,
watch the lap-by-lap event feed, or Monte Carlo 100 races into win-probability
bars.
