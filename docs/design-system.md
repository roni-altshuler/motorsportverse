# Design system

The ecosystem site and every project website share one visual language,
extracted from the F1 flagship's design system.

## Identity

A neutral, sport-agnostic shell so no single livery dominates the ecosystem:

- **Canvas** graphite `#0a0b0d`; **surfaces** `#141619`–`#23272c`; **hairlines**
  `#2a2e34`.
- **Ink** off-white `#f4f5f7` with muted/dim greys.
- **Ecosystem accent** electric teal `#38e1c6` (deliberately *not* F1 red).
- **Per-project accent** comes from the registry entry's `accent` field, applied
  inline as `--team-color` / `--accent` on cards and detail pages.

Tokens live in `website/src/styles/tokens.css` and are exposed as Tailwind v4
utilities via the `@theme inline` block in `globals.css` (`bg-canvas`,
`text-ink`, `border-hairline`, …).

## Maturity colors

| Stage | Color |
|---|---|
| production | `--maturity-production` (teal) |
| experimental | `--maturity-experimental` (blue) |
| in-development | `--maturity-in-development` (amber) |
| concept | `--maturity-concept` (grey) |
| archived | `--maturity-archived` (dim grey) |

Rendered by `components/MaturityBadge.tsx`.

## Components

Copied verbatim from F1 (dependency-light: framer-motion, clsx, tailwind-merge,
class-variance-authority):

- `components/ui/` — `Card`, `Button`, `Badge`, `Stat`, `AnimatedNumber`,
  `HUDPanel`, `TeamColorBar`, `cn()` helper, …
- `components/magicui/` — animation primitives (`marquee`, `border-beam`,
  `spotlight`, `number-ticker`, `bento-grid`, …).
- `lib/motion.ts`, `lib/useReducedMotion.ts` — motion tokens + reduced-motion
  guard. Every effect must have a reduced-motion fallback (there is a global
  `prefers-reduced-motion` block in `globals.css`).

Ecosystem-specific: `ProjectCard`, `ProjectExplorer` (client-side maturity +
category filter), `MaturityBadge`, `Navbar`, `Footer`.

## Branding placeholders

`website/public/brand/`: `logo.svg`, `mark.svg`, `favicon.svg`, per-sport marks
under `brand/sports/`, and `public/og/default.svg`. These are placeholders —
replace with final artwork without changing any references.

## Deployment

Next.js 16 **static export** (`output: "export"`) to GitHub Pages, matching the
F1 project. No server components, no runtime fetches — all data is JSON read at
build time (the catalog from `public/data/registry.json`).
