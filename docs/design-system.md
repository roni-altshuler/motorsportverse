# Design system

> **The full reference is [`DESIGN.md`](../DESIGN.md)** at the repository root —
> tokens, type, spacing, components, motion, the validated chart palette, and
> the honesty rules that are also design rules, in
> [getdesign.md](https://getdesign.md/) format.
>
> This page is the short orientation. When the two disagree, `DESIGN.md` wins.

## There are two surfaces, deliberately different

| | **The hub** (`website/`) | **A series site** (`projects/*/website/`) |
|---|---|---|
| Job | make you want to look | let you read a number |
| Canvas | deep blue-black `#060910` | pure black `#000000` |
| Language | cinematic — mesh gradients, glass, glow | **Bugatti** — hairlines, no gradients, no shadows |
| Accent | one crimson `#e7102f` | the series' own colour |

The hub is a catalog; a series site is an instrument. Most design mistakes here
are one surface's rule applied to the other. See `DESIGN.md` §0.

## Ecosystem tokens

Hub tokens live in `website/src/styles/tokens.css` and are exposed as Tailwind v4
utilities via the `@theme inline` block in `globals.css` (`bg-canvas`, `text-ink`,
`border-hairline`, …). Per-project accent comes from the registry entry's
`accent` field, applied inline as `--team-color` / `--accent`.

## Maturity colours

| Stage | Token |
|---|---|
| production | `--maturity-production` (teal) |
| experimental | `--maturity-experimental` (amber) |
| in-development | `--maturity-in-development` (blueprint blue) |
| concept | `--maturity-concept` (grey) |
| archived | `--maturity-archived` (dim grey) |

Rendered by `components/MaturityBadge.tsx`.

## Chart colour is validated, not chosen

Every site defines `--viz-model`, `--viz-baseline`, `--viz-cat-3`,
`--viz-reference`, `--viz-field` and `--viz-seq-1..5`. These are measured
against all three chart surfaces in the repo, with the numbers recorded in
`DESIGN.md` §1.4 and in a comment block in each `tokens.css`.

Two rules people get wrong:

- **The categorical scale stops at three.** A fourth hue fails CVD separation;
  a fourth contender folds into `--viz-field`.
- **Model and baseline are always direct-labelled.** Their tritan separation is
  ΔE 5.7, below the floor, so colour alone is not legal for that pair.

## The shared component set

`projects/f1-predictions/website/src/components/{ui,magicui}` is canonical.
Every other site — including the hub — carries a byte-identical copy, enforced
by `node scripts/sync_shared_ui.mjs --check` in CI. Edit the canonical copy and
run the sync; editing a target is how drift happens.

Evidence components (`EvidencePanel`, `BaselineLadder`, `StatusBanner`,
`EmptyState`, `Skeleton`, `format.ts`) and the shared test suite under
`src/__tests__/shared/` are synced by the same gate. Per-target exemptions live
in `TARGET_EXEMPTIONS` and each one carries its reason.

Charts under `components/charts/` are deliberately **not** gated — the variants
were genuinely adapted per series. Promote a chart to the shared set only once
its data contract is truly series-agnostic.

## Branding assets

`website/public/brand/`: `logo.svg`, `mark.svg`, `favicon.svg`, per-sport marks
under `brand/sports/`, and `public/og/default.svg`. Replace placeholders with
final artwork without changing any references.

## Deployment

Next.js 16 **static export** (`output: "export"`) to GitHub Pages. No server
components, no runtime fetches — all data is JSON read at build time.
