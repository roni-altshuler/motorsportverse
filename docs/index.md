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

The **F1 Predictions** project (in its own repo, `f1_predictions/`) is the
flagship and reference implementation. Everything reusable was extracted from it
into `motorsport-core` and `motorsport-data`.

## Where to go next

- [Architecture](architecture.md) — how the layers fit together.
- [Adding a sport](adding-a-sport.md) — ship a new project.
- [Core API](core-api.md) — `motorsport-core` reference.
- [Data schema](data-schema.md) — the canonical models.
- [Design system](design-system.md) — tokens, components, identity.
- [Branding system](BRANDING_SYSTEM.md) — the RaceIQ logo system.

### Reports

- [Implementation summary](IMPLEMENTATION_SUMMARY.md) — what shipped + diagrams.
- [F2 readiness](F2_READINESS.md) — RaceIQ F2 capabilities + reuse.
- [Repository audit](REPO_AUDIT.md) — hygiene findings + fixes.

## Maturity levels

Projects move through five stages: **concept → in-development → experimental →
production → archived**. See [GOVERNANCE.md](../GOVERNANCE.md).
