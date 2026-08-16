# DESIGN.md — MotorsportVerse

A reusable design reference for this monorepo: the tokens, the type, the spacing,
the components, and **the reasoning behind them**. Written in the
[getdesign.md](https://getdesign.md/) format so an agent picking up a new page —
on the hub, on a series site, or on a site that does not exist yet — produces
something that belongs here rather than a generic layout.

It is the design half of the contract. The evidence half is
[docs/EVIDENCE.md](docs/EVIDENCE.md), and the two overlap: several rules in §8
below are honesty rules that happen to change what a component renders.

---

## 0. There are two surfaces, and they are deliberately different

This is the first thing to get right, because most design mistakes here are a
rule applied to the wrong one.

| | **The hub** (`website/`) | **A series site** (`projects/*/website/`) |
|---|---|---|
| Job | make you want to look | let you read a number |
| Canvas | deep blue-black `#060910` | pure black `#000000` |
| Language | cinematic — mesh gradients, glass, glow | **Bugatti** — hairlines, no gradients, no shadows |
| Accent | one crimson `#e7102f` | the series' own colour |
| Motion | scroll reveals, marquees, tilt | hover transitions, essentially nothing else |
| Type | Inter-family sans | condensed display + serif body + mono numerics |

The hub is a **catalog**. Its job is to make an ecosystem of twelve projects feel
like one product and get you to the right series. Cinematic treatment is correct
there and is not permission to bring gradients onto an accuracy page.

A series site is an **instrument**. Once you are inside a series you came for a
probability, and every pixel that is not helping you read one is in the way.

> **The one-sentence brief for a series site:** a precision instrument, not a
> scoreboard — black, quiet, hairline-ruled, where every number is monospaced and
> every colour means something.
>
> If a change makes a series page louder without making a number clearer, it is
> wrong.

The shared component set in §5 is written to work under **both** token sets. That
is why every shared component styles through CSS custom properties and never
hardcodes a colour.

---

## 1. Colour

### 1.1 The series palette (Bugatti)

Canvas and surfaces — defined in each site's `src/styles/tokens.css`:

| Token | Value | Used for |
|---|---|---|
| `--canvas` | `#000000` | the page |
| `--surface-soft` | `#0d0d0d` | the chart surface, quiet panels |
| `--surface-card` | `#141414` | every card and table surface |
| `--surface-elevated` | `#1f1f1f` | bar tracks, inert fills |
| `--hairline` | `#262626` | **the hairline — this carries all structure** |
| `--hairline-strong` | `#3a3a3a` | hover only |

**Depth comes from hairlines, never from shadow.** `--shadow-*` are all `none` on
the series sites and that is deliberate. The glow stack is selectively re-armed
for exactly three things — a live session, a podium, and a team-coloured surface —
and nothing else may claim it.

Ink:

| Token | Value | Used for |
|---|---|---|
| `--ink` | `#ffffff` | headings, the number that matters |
| `--body` | `#cccccc` | body copy |
| `--muted` | `#999999` | captions, labels, absent values |

Signals — four, and nothing else:

| Token | Value | Means |
|---|---|---|
| `--success` | `#5fa657` | positive, gained places, a hit |
| `--warning` | `#d4a017` | uncertainty, **and every backtest label** |
| `--accent-negative` | the series accent | negative, retired, a miss |
| `--link` | `#c3d9f3` | links and informational text **only** |

**Colour carries meaning only, never decoration.** A hue that is not one of these
four, not the series accent and not a team colour is not saying anything and
should be a shade of grey.

### 1.2 The series accent is one variable, changed in one place

Theming a site happens **only** through the accent block in its `tokens.css`. The
`--accent-f1-red` family names are kept on every site — that is not an oversight,
it is what lets a component ported from the flagship resolve without edits:

| Series | Accent | `--accent-ink` | Hover direction |
|---|---|---|---|
| F1 | `#E10600` | `#ffffff` | darken |
| F2 | `#1E9BD7` | `#04222e` | darken |
| F3 | `#D9A441` | `#04222e` | darken |
| Formula E | `#1E1AF0` | `#ffffff` | **brighten** |
| NASCAR | `#FFD659` | `#141000` | **darken** |
| IndyCar | `#D31217` | `#ffffff` | **brighten** |

Two rules fall out of that table and they are the ones people get wrong:

1. **A light accent needs near-black ink on it.** White text on NASCAR yellow is
   unreadable. `--accent-ink` exists so a shared component never has to know.
2. **A deep accent brightens on hover; a light accent darkens.** Darkening
   Formula E's `#1E1AF0` makes it vanish into the canvas; lifting NASCAR's yellow
   washes it out. The hover token is per-site for this reason alone.

### 1.3 Team colours are the chromatic exception

Constructor and team colours are real-world identity, resolved via
`data-team="…"` or an inline `--team-color`. They are allowed to be any hue
because they are not the design system talking — they are the sport. They appear
on `TeamColorBar`, chart series that represent a team, and nowhere else.

### 1.4 Chart colour is VALIDATED, not chosen

Chart series get their own tokens because a chart mark is a different job from a
link or a caption, and because the site accent is already spoken for by the site's
identity — a chart with two series cannot use it for one of them.

| Token | Value | Slot |
|---|---|---|
| `--viz-model` | `#5fa657` | categorical 1 — **this model** |
| `--viz-baseline` | `#3987e5` | categorical 2 — **the baseline it must beat** |
| `--viz-cat-3` | `#c25ba6` | categorical 3 — a third named series |
| `--viz-reference` | `#4d4d4d` | de-emphasis: the ideal diagonal, gridlines |
| `--viz-field` | `#57575a` | the aggregated tail, deliberately recessive |
| `--viz-seq-1..5` | `#63461e` → `#e79d3b` | sequential, one hue, low→high |

These are measured, not asserted. Run against the dataviz validator on **all
three** chart surfaces in this repo — `#0d0d0d` (series panels), `#141414`
(series cards) and `#0c1119` (the hub) — with `--pairs all`, because on a
championship chart every line is visible at once and checking only adjacent pairs
misses the pair a reader actually confuses:

- Categorical trio: lightness band **PASS** (all three inside L 0.48–0.67),
  chroma floor **PASS**, CVD separation **PASS** at worst ΔE **10.6** (protan,
  magenta↔blue), normal-vision floor **PASS** at worst ΔE **21.4**, contrast
  ≥ 3:1 **PASS**. Identical result on all three surfaces.
- Model↔baseline alone: CVD ΔE **24.2**, normal-vision ΔE **24.9**.
- Sequential ramp: monotone lightness **PASS**, adjacent ΔL **PASS**,
  light-end contrast **PASS** (2.13:1 at worst, on `#141414`), single hue
  **PASS** (3° spread). Passes the stricter *ordinal* gate too, so it is legal
  for discrete ordered marks as well as continuous magnitude.

**Tritan separation for the model/baseline pair is ΔE 5.7**, which is below the
floor and therefore legal **only with secondary encoding**. Both series are
consequently *always* direct-labelled. That is a requirement, not styling.

**The categorical scale stops at three, and that is a measurement.** Every
four-hue set tried failed:

| Fourth hue | Result |
|---|---|
| orange `#d95926` | **FAIL** — orange↔green ΔE 4.8–5.3 deutan, the classic confusion |
| grey `#c8c8c8` | **FAIL** — L 0.833 outside the band, chroma 0 reads as "no series" |

So a fourth contender is never given a fourth hue. It folds into an explicit
**field** line — and because championship-win probabilities sum to one, three
named contenders plus the field is the *entire distribution* rather than a
truncation.

Rules that do not bend:

- Sequential = one hue, low→high. Diverging = two hues plus a neutral grey
  midpoint. **Never a rainbow.**
- **One axis. Never a dual-axis chart.**
- Colour follows the entity, never its rank. A filter that drops a driver must
  not repaint the survivors.
- Past three series, fold the tail into `--viz-field` rather than generating hues.
- A single-series chart uses the **site accent** and needs no legend — the title
  names it. Two or more series use the `--viz-*` slots and always carry both a
  legend and direct labels.
- The finish-probability heatmap's `color-mix(in srgb, var(--accent) N%, …)` ramp
  **is** the one-hue sequential rule, expressed per-site. Leave it site-themed.

---

## 2. Type

Series sites run three families and the split is functional, not decorative:

| Family | Variable | Used for |
|---|---|---|
| Saira Condensed | `--font-display` | headings, wordmarks, nav — uppercase, tracked |
| EB Garamond | `--font-serif` | body prose only |
| JetBrains Mono | `--font-mono` | **every number**, buttons, captions, table headers |

- `.display-xl` … `.title-sm`: uppercase, `letter-spacing: 0.05–0.09em`, weight
  400, `--ink`. **Positive tracking is what makes the restraint elsewhere read as
  deliberate rather than unfinished.**
- `.eyebrow` / `.hud-kicker`: monospace, uppercase, wide tracking, `--muted`. The
  label above every stat.
- `.font-tabular`: `font-variant-numeric: tabular-nums`. **Every number in a
  table gets it** — a points column that jitters as digits change reads as a
  broken table, not a live one.

The hub uses a single sans family with `.display` / `.lead` / `.eyebrow`. It has
no serif because it has no prose worth setting in one.

---

## 3. Spacing and layout

- Series sites: `--space-xxs` 4 → `--space-section` 120px. Sections are separated
  by `--space-xl` (40px), a heading from its content by `--space-sm` (12px),
  cards padded `--space-md` (16px).
- Hub: `--space-xs` 8 → `--space-xxl` 96, plus
  `--section-pad: clamp(72px, 11vw, 140px)` for the long-scroll landing rhythm.
- Radius: series cards `--radius-card: 4px` and **everything else is `0`** —
  the pill is reserved for badges. Hub cards use `--radius-lg: 18px`.
- Tables are full-bleed inside a card with `overflow-x: auto`. **Never let the
  page body scroll horizontally** — the table scrolls inside its own container.

---

## 4. The shared component set, and how it stays shared

`projects/f1-predictions/website/src/components/{ui,magicui}` is the **canonical**
copy. Every other site carries a byte-identical duplicate, enforced in CI by:

```bash
node scripts/sync_shared_ui.mjs --check    # exits 1 on drift
node scripts/sync_shared_ui.mjs            # copy canonical → targets
```

Committed copies plus a drift gate, rather than an npm workspace package, because
each site is an independent static-export build and a real package would touch
every install and the deploy assembler — highest risk, lowest payoff.

Three consequences you must respect:

1. **Edit the canonical copy, then run the sync.** Editing a target is how drift
   happens, and CI will catch it.
2. **A shared component may never hardcode a colour.** It resolves
   `var(--accent)`, `var(--accent-ink)`, `var(--viz-model)` and so on, so one
   source renders correctly under six accents.
3. **Adding a site means adding it to `TARGETS` in the same change** that copies
   the components in.

Charts under `components/charts/` are deliberately **not** drift-gated: the
variants were genuinely adapted per series (different type modules, headshot
resolvers, props). Only promote a chart to the shared set once its data contract
is truly series-agnostic.

---

## 5. Components

| Component | Rule |
|---|---|
| `EvidencePanel` | **Not a tab.** Every probability on the site is unfalsifiable without it. It renders below the numbers it justifies, on every page showing a forecast, and a test asserts it is present. |
| `BaselineLadder` | The model and its baselines, in one table, ranked. A model that does not beat its baseline is **printed as such**, not hidden. |
| `StatusBanner` | Says which state the page is in — stale data, a closed calibration gate, an archived season. Never silently degrades. |
| `EmptyState` | "No rounds scored yet" is a fact worth rendering. An empty page that looks broken gets reported as broken. |
| `Skeleton` | Reserves the real layout's box. A skeleton of the wrong shape is a layout shift with extra steps. |
| `ProbabilityBars` | The number is **always** text beside the bar. A reader cannot read 63% off a bar, and a colour-blind reader cannot read it off a hue. |
| `TeamColorBar` | The only place a raw team hue touches chrome. |
| `SeasonSwitcher` | An archived season is labelled archived everywhere it is shown, not just in the switcher. |
| `CalibrationPanel` | Dot area = sample size. Ships a table view under `<details>`. |
| `DriverHeadshot` | Site-specific by design (excluded from the sync). A missing headshot falls back to initials, never to a broken image. |
| `ErrorBoundary` | Wraps anything client-side and animated. A failed canvas must not take the standings table with it. |
| `LoadingTire` | The only decorative motion permitted on a series site, and only while waiting. |

---

## 6. Motion

Series sites: almost none. Hover transitions on border colour at `--dur-snap`
(180ms). No entrance animation on a data page, no parallax over a table, no
scroll-jacking anywhere.

The reason is the product: a page of probabilities that animates on arrival looks
like it is performing rather than reporting.

The hub is allowed reveals, marquees and card tilt, subject to two hard rules:

1. **`prefers-reduced-motion: reduce` collapses every duration globally.** There
   is a block in each `globals.css` doing this; do not opt a component out.
2. **Scroll-reveal must never leave content permanently invisible.** Use the
   failsafe `useReveal` pattern — if the observer never fires, the content is
   visible anyway. A reveal that fails closed is a blank page in the wild.

---

## 7. Imagery

- **Race art is aerial circuit photography.** `lib/raceArt.ts` maps a round to an
  image, every URL curl-verified. Never an SVG track diagram, never a series or
  sponsor logo, never a country landscape. If no verified image exists, fall back
  to the gradient card — a wrong image is worse than no image.
- **Brand marks live in `public/brand/`** and are referenced, never inlined.
- **A missing image never renders as a broken image.** Every consumer has a
  typographic fallback.

---

## 8. The honesty rules that are also design rules

These are not editorial preferences — they change what components render. The
reasoning is in [docs/EVIDENCE.md](docs/EVIDENCE.md); the rendering consequences
are here.

1. **Absent data renders as absent.** `—`, never `0`. "No prediction published"
   and "predicted last" are different facts, and a UI that draws them identically
   is lying about one of them. `pct(null)` returns `—` and there is a test.
2. **Every probability is text.** Colour and bar length are aids; the text is the
   claim.
3. **A backtest is labelled a backtest**, in `--warning`, every place it appears.
   A reconstructed forecast must never blur into "published in advance".
4. **A result that does not beat its baseline is printed as such.** The accuracy
   page states the comparison in words, not just in a table a reader has to
   diff themselves.
5. **The caveat prints on a hit as well as a miss.** A hit read as proof is the
   same error in the flattering direction.
6. **A closed calibration gate is visible.** While
   `calibration_summary.json.applied` is false, the UI says the probabilities are
   uncalibrated. It does not quietly show them anyway.
7. **Fantasy is labelled fantasy.** Chrome Valley and Prism Cup carry a fan-made,
   simulated disclaimer on every page. They are not predictions of anything real
   and must never be mistakable for one.

---

## 9. What NOT to add

- **Gradients, shadows, glass or glow on a series site.** All four are explicitly
  out. They are the hub's language, not the instrument's.
- **A light theme.** Every site is dark-only; `:root` is the single source of
  truth.
- **Tailwind palette colours.** `text-gray-400` bypasses the token layer and will
  be wrong on at least one of the six accents. Always `text-[var(--muted)]`.
- **Implementation details in user-facing copy.** No "Plackett-Luce", "Elo",
  "XGBoost", "Monte Carlo", "PSI". Describe what the model says, not how. The
  `/about` page is the one place mechanism is explained, in plain language.
- **A chart whose inputs the series does not publish.** Do not port a telemetry
  chart to a series with no telemetry. Fabricating the input to reuse a component
  is the single worst thing available in this codebase.
- **A second place a probability is computed.** Every site renders published JSON.
  A component that recomputes something is a model nobody benchmarked.
- **A client-side import of an fs-based loader.** `lib/<slug>data.ts` and
  `lib/registry.ts` read the filesystem at build time; importing them from a
  `"use client"` component breaks the static export.
