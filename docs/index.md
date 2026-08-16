# MotorsportVerse documentation

MotorsportVerse is a unified, open-source ecosystem of motorsport AI projects —
one central catalog, many sport-specific projects, all built on shared
infrastructure. It is modelled on [scverse](https://scverse.org/): a discoverable
hub plus independent, repo-ready projects.

## The shape of it

```
motorsportverse/
├── website/            ecosystem landing site + project catalog
├── packages/
│   ├── motorsport-core   shared ML & evaluation infrastructure (pip)
│   └── motorsport-data   canonical schema + ingestion + history store (pip)
├── registry/           the project catalog (source of truth)
├── projects/           one folder per sport (f2-predictions, …)
├── docs/               this documentation
├── scripts/            registry builder + new-project scaffolder
└── templates/          project skeleton
```

The **F1 Predictions** project is the flagship and reference implementation, and
lives **in this repo** at `projects/f1-predictions/`. Everything reusable was
extracted from it into `motorsport-core` and `motorsport-data`.

That extraction is never finished, and the cost of leaving it half-done is
concrete: a calibration fix that stayed in the flagship for a month meant five
cloned series published incoherent probabilities the whole time. See
[Known issues](KNOWN_ISSUES.md). **A fix that belongs to every series goes in
`packages/`, not in the project where it was found.**

## Where to go next

- [Architecture](architecture.md) — how the layers fit together.
- [Adding a sport](adding-a-sport.md) — ship a new project.
- [Core API](core-api.md) — `motorsport-core` reference.
- [Data schema](data-schema.md) — the canonical models.
- [Evidence policy](EVIDENCE.md) — **what an accuracy claim has to show.**
- [Design reference](../DESIGN.md) — the full visual system.
- [Design system](design-system.md) — the short orientation.
- [Branding system](BRANDING_SYSTEM.md) — the RaceIQ logo system.
- [Known issues](KNOWN_ISSUES.md) — defects carried on purpose, and their gates.

### Reports

- [Implementation summary](IMPLEMENTATION_SUMMARY.md) — what shipped + diagrams.
- [F2 readiness](F2_READINESS.md) — RaceIQ F2 capabilities + reuse.
- [Repository audit](REPO_AUDIT.md) — hygiene findings + fixes.

## Maturity levels

Projects move through five stages: **concept → in-development → experimental →
production → archived**. See [GOVERNANCE.md](../GOVERNANCE.md).
