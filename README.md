# FotPredict — Formula 1 Race Prediction Platform

A self-evaluating Formula 1 analytics platform that predicts every 2026 Grand Prix outcome, scores itself against the actual results round-over-round, and ships a polished interactive dashboard.

**[Live demo](https://roni-altshuler.github.io/f1_predictions/)**

---

## What it does

- **Predicts every weekend** of the 22-round 2026 season — qualifying pace, finishing positions, win/podium probabilities, with confidence bands.
- **Calibrated probabilities** — the model is honestly gated; raw probabilities ship until enough multi-season history is available for isotonic calibration to fit, at which point the dashboard flips to calibrated output and surfaces a green "Calibrated" badge.
- **Forward-time accuracy** — every prediction is scored after the race against a `last-race-winner` baseline. Round-by-round metrics (MAE, Brier, Spearman, NDCG) live at [`/accuracy`](https://roni-altshuler.github.io/f1_predictions/accuracy/) and feed a drift report.
- **Sprint weekends are first-class** — Sprint Qualifying + Sprint Race sit alongside standard Qualifying and the Grand Prix on the race detail page.
- **WDC math** — "Who can still win the championship" lanes with mathematical-elimination logic, animated beams to the champion zone.
- **Living points-progression chart** — solid lines for actual standings, dashed projection lines extending through the season, refreshing each round.

## Screenshots

> _Placeholders — capture and add: `/`, `/race/N`, `/standings`, `/standings?tab=wdc`, `/calendar`, `/accuracy`._

## Quick start

```bash
# Website only (uses the JSON snapshot already in the repo)
cd website
npm install
npm run dev
# → http://localhost:3000
```

To regenerate predictions yourself you also need the Python pipeline — see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## How it works (high level)

We ingest official timing and historical race archives, train a per-race regression model on qualifying pace + circuit characteristics + driver/team form, then run a probabilistic sampler to convert pace into calibrated finishing-position probabilities. A separate per-lap race simulator models pit windows, safety cars, and tyre degradation for an alternative-method probability stream.

Every prediction is published to a static JSON contract that the Next.js dashboard consumes at build time; the same JSON is replayed against actual results by an automated forward-evaluation pipeline that gates model promotion.

## Deeper reading

- **[Architecture](docs/ARCHITECTURE.md)** — the three-layer prediction pipeline, data flow, file layout.
- **[ML pipeline](docs/ML_PIPELINE.md)** — training methodology, calibration gating, leakage discipline, race simulator.
- **[Model evaluation](docs/MODEL_EVALUATION.md)** — forward-eval methodology, per-round scoring, ablations.
- **[Data sources & acknowledgements](docs/DATA_SOURCES.md)** — every external dataset and library credited.
- **[Development guide](docs/DEVELOPMENT.md)** — setup, build, prebuild gotchas, deploy.
- **[Roadmap](docs/ROADMAP.md)** — what's next.
- **[Phase 1 benchmark](docs/BENCHMARK_PHASE_1.md)** — quantitative before/after of the ML overhaul Phase 1.

## Project layout

```
f1_predictions/
├── README.md                       ← this file
├── docs/                           ← detailed engineering documentation
├── website/                        ← Next.js static site (the dashboard)
│   ├── src/                        ← React + TypeScript components
│   └── public/data/                ← JSON snapshots consumed by the UI
├── f1_prediction_utils.py          ← core training, feature engineering
├── advanced_models.py              ← pit strategy + tyre deg + sequence model
├── export_website_data.py          ← Python → JSON contract bridge
├── forward_eval.py                 ← round-over-round model scoring
├── drift_report.py                 ← feature PSI + rolling Brier
├── promotion_decision.py           ← shadow / A-B model promotion gate
├── models/                         ← calibration, race simulator, intervals, DNF
└── tests/                          ← pytest suite (390+ tests)
```

## License

MIT — see [LICENSE](LICENSE) (TBA — see [docs/ROADMAP.md](docs/ROADMAP.md)).

## Acknowledgements

Full credits are in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md). Highlights:

- **[FastF1](https://docs.fastf1.dev/)** — historical telemetry + lap-time archives.
- **Jolpica / Ergast-compatible API** — official 2026 standings + classified race results.
- **[Wikimedia Commons](https://commons.wikimedia.org/)** — aerial circuit photography for the calendar surface.
- **[Next.js](https://nextjs.org/)**, **[Recharts](https://recharts.org/)**, **[Framer Motion](https://www.framer.com/motion/)**, **[Magic UI](https://magicui.design/)** — frontend stack.
- **[scikit-learn](https://scikit-learn.org/)**, **[XGBoost](https://xgboost.readthedocs.io/)**, **[DuckDB](https://duckdb.org/)** — backbone of the prediction + evaluation pipeline.
- Original spiritual ancestor: [`mar-antaya/2025_f1_predictions`](https://github.com/mar-antaya/2025_f1_predictions).
