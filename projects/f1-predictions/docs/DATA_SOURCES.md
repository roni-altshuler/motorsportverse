# Data sources & acknowledgements

This is the canonical place for every external dataset, library, API, and image source used by the platform. User-facing UI strings deliberately do not name implementation details — credits and tech disclosure live here.

## Live race data

### [FastF1](https://docs.fastf1.dev/)
- **Used for:** lap-by-lap telemetry, sector times, sprint qualifying timing, historical race data 2018+.
- **Rate limit:** ~500 requests/hour on the public FastF1 cache.
- **Citation:** Schäfer, M. _FastF1: Access to F1 telemetry data._ MIT License.

### Jolpica / Ergast-compatible API
- **Used for:** official 2026 standings, classified race results, historical 1950+ archive backfill.
- **Endpoint:** `https://api.jolpi.ca/ergast/` (Jolpica is a free, Ergast-API-compatible community mirror after the original Ergast retired).
- **License:** Open data, CC0 / public domain attribution.

## Historical archive

### `data/history.duckdb`
- Local DuckDB populated by [`backfill_history.py`](../backfill_history.py) (FastF1 Tier 1) and [`ergast_backfill.py`](../ergast_backfill.py) (Ergast Tier 2).
- Gitignored (`/data/` is project-root-anchored — does **not** match `website/public/data/`); the backfill workflow force-adds it.

## Weather

### Open-Meteo (planned)
- [`weather_api.py`](../weather_api.py) wraps the Open-Meteo free weather forecast API.
- Currently dormant — see [docs/ROADMAP.md](ROADMAP.md). Race-day rain probability is presently hardcoded per round in the CALENDAR.

## Race photography (Calendar page)

All race-card photography is sourced from **[Wikimedia Commons](https://commons.wikimedia.org/)** — free-licensed, stable URLs, no API key required. Curated in [`website/src/lib/raceArt.ts`](../website/src/lib/raceArt.ts) (every URL `curl`-verified before commit). The "SkySat" satellite aerials (Planet Labs Inc. donations to Commons, 2017-2018) provide overhead circuit photography matching the formula1.com hero strip aesthetic for 15 of the 22 races.

## Frontend libraries

| Library | License | Role |
|---|---|---|
| [Next.js](https://nextjs.org/) 16.x | MIT | React framework + static export |
| [React](https://react.dev/) 19.x | MIT | UI runtime |
| [Tailwind CSS](https://tailwindcss.com/) v4 | MIT | Utility-first styling |
| [Recharts](https://recharts.org/) | MIT | Interactive line + bar charts |
| [@visx/*](https://airbnb.io/visx/) | MIT | Custom heatmap + ordination charts |
| [Framer Motion](https://www.framer.com/motion/) | MIT | Entrance + variant animations |
| [GSAP](https://gsap.com/) | Custom GreenSock no-charge license | Scroll-tied parallax (track-map sweep) |
| [Lenis](https://lenis.darkroom.engineering/) | MIT | Smooth-scroll provider |
| [Magic UI](https://magicui.design/) | MIT | Primitive components (Bento, MagicCard, Spotlight, BorderBeam) |
| [Lucide](https://lucide.dev/) | ISC | Icon set |
| [Satori](https://github.com/vercel/satori) + [@resvg/resvg-js](https://github.com/yisibl/resvg-js) | MIT | OG-image generation (SVG → PNG → WebP) |
| [Sharp](https://sharp.pixelplumbing.com/) | Apache 2.0 | WebP encoding |
| [Playwright](https://playwright.dev/) | Apache 2.0 | End-to-end screenshot testing |

## Backend libraries

| Library | License | Role |
|---|---|---|
| [scikit-learn](https://scikit-learn.org/) | BSD-3 | Gradient Boosting, isotonic regression, logistic regression (DNF model), preprocessing |
| [XGBoost](https://xgboost.readthedocs.io/) | Apache 2.0 | Gradient-boosted trees (ensemble component) |
| [LightGBM](https://lightgbm.readthedocs.io/) | MIT | Reserved for the Phase 2 ensemble experiment |
| [PyTorch](https://pytorch.org/) | BSD | Optional LSTM lap predictor |
| [pandas](https://pandas.pydata.org/) + [NumPy](https://numpy.org/) | BSD | Tabular + numerical primitives |
| [DuckDB](https://duckdb.org/) | MIT | Historical-archive store (`data/history.duckdb`) |
| [Matplotlib](https://matplotlib.org/) | PSF-based | Per-round PNG visualisations (track map, OG fallbacks) |
| [pytest](https://pytest.org/) | MIT | 390+ test suite |
| [ruff](https://docs.astral.sh/ruff/) | MIT | Lint gate on hot paths |

## Spiritual ancestor

- **[mar-antaya/2025_f1_predictions](https://github.com/mar-antaya/2025_f1_predictions)** — the early-2025 starting point that this fork has substantially extended (three-layer pipeline, calibration gating, forward-eval discipline, race simulator, full Next.js dashboard, sprint-weekend handling, model promotion, drift report). Original author retains credit for the initial v1 framework.

## A note on user-facing copy

Per the project's UI tech-stack scrub policy: user-facing pages must not name implementation details like algorithm names ("Plackett-Luce", "Monte Carlo", "isotonic regression", "XGBoost") or library names. The dashboard talks about **what the model says** ("Win probability", "Forecast", "Calibrated"), not **how it's built**.

All such credits belong here in `docs/DATA_SOURCES.md` and in the root [README.md](../README.md) Acknowledgements section.
