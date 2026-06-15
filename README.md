<div align="center">

<img src="website/public/brand/logo.svg" alt="MotorsportVerse" width="420" />

# 🏁 MotorsportVerse

**A unified, open-source motorsport AI ecosystem.**

One central catalog. Many sport-specific projects. Shared ML & data infrastructure.

</div>

---

MotorsportVerse is to motorsport prediction what [scverse](https://scverse.org/)
is to single-cell biology: a discoverable hub of independent, repo-ready projects
that all build on a common foundation. The **F1 Predictions** project is the
flagship and reference implementation; everything reusable was extracted from it
into two shared packages.

## What's here

```
motorsportverse/
├── website/              ecosystem landing site + project catalog (Next.js, static export)
├── packages/
│   ├── motorsport-core   shared ML & evaluation infrastructure (pip)
│   └── motorsport-data   canonical schema + ingestion + history store (pip)
├── registry/             the project catalog (JSON + schema; source of truth)
├── projects/
│   └── f2-predictions    first expansion beyond F1
├── docs/                 unified documentation
├── scripts/              registry builder + new-project scaffolder
└── templates/            project skeleton
```

> The F1 flagship lives in its own repository (`f1_predictions/`) and is
> **untouched** — MotorsportVerse extracts shared infrastructure from it rather
> than modifying it.

## Project catalog

| Project | Sport | Maturity |
|---|---|---|
| [RaceIQ F1](registry/projects/f1-predictions.json) | Formula 1 | **production** |
| [RaceIQ F2](projects/f2-predictions/) | Formula 2 | **experimental** (first operational expansion) |
| F3 · Formula E · IndyCar · NASCAR · WEC · Le Mans · IMSA · WRC · MotoGP | — | concept |

Every project is a **RaceIQ** product on the shared core; the ecosystem hub is
**MotorsportVerse**. See the [branding system](docs/BRANDING_SYSTEM.md).

Browse them all on the [website project directory](website/) (`/projects`).

## Quick start

```bash
# Shared packages (editable installs)
pip install -e "packages/motorsport-core[dev]" "packages/motorsport-data[dev]"
pytest packages/motorsport-core packages/motorsport-data

# Build/validate the catalog
python scripts/build_registry.py

# Run the ecosystem website
cd website && npm install && npm run dev   # → http://localhost:3000

# Scaffold a new sport
python scripts/new_project.py nascar-predictions --sport NASCAR \
  --category stock --summary "NASCAR Cup Series forecasts." --added 2026-06-15
```

## Recommended next sport: **Formula 2**

F2 wins on all four axes — **data availability** (FastF1 supports F2; shares the
Jolpica feed and identical circuits), **modelling potential** (same weekend
structure, reusable track archetypes, feeder-series talent signal), **community
interest** (F1-adjacent audience), and **ease of implementation** (~90% core
reuse). It's the best proof that the shared template works. Ranked runner-ups:
F3 → NASCAR → Formula E.

## Documentation

[Architecture](docs/architecture.md) · [Adding a sport](docs/adding-a-sport.md) ·
[Core API](docs/core-api.md) · [Data schema](docs/data-schema.md) ·
[Design system](docs/design-system.md) · [Governance](GOVERNANCE.md) ·
[Org structure](.github/ORG_STRUCTURE.md)

## License

MIT — see [LICENSE](LICENSE).
