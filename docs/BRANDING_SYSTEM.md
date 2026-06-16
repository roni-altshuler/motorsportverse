# MotorsportVerse branding system

One ecosystem, one design language, many series. Every project in
MotorsportVerse is a **RaceIQ** product (RaceIQ is the flagship F1 engine's
name); the ecosystem that houses them is **MotorsportVerse**.

All assets are generated from a single source — [`scripts/generate_brand.py`](../scripts/generate_brand.py) —
so the system can never drift. Re-run it to regenerate every SVG:

```bash
python scripts/generate_brand.py
```

## Naming

| Layer | Name | Example |
|---|---|---|
| Ecosystem | **MotorsportVerse** | the hub, the catalog, the shared packages |
| Product family | **RaceIQ** | the prediction engine brand |
| Per-series product | **RaceIQ &lt;Series&gt;** | RaceIQ F1, RaceIQ F2, RaceIQ NASCAR |

## Primary ecosystem logo (authoritative)

The MotorsportVerse ecosystem identity is the supplied artwork, sliced from the
master collage (`website/public/brand/source/motorsportverse-logo-collage.png`)
into purpose-specific assets:

| Asset | File | Used for |
|---|---|---|
| **Hero lockup** (car + wordmark + "AI · PREDICTION · ANALYTICS") | `website/public/brand/motorsportverse-logo.png` | README hero, website home hero, OG/Twitter card |
| **Hex MV badge** (square) | `website/public/brand/motorsportverse-mark.png` | navbar mark, favicon source (`website/src/app/icon.png`) |
| **Master collage** (all 6 variants) | `website/public/brand/source/…collage.png` | source of truth; re-slice for new placements |

The collage also contains alternate lockups ("Intelligence in Motion",
"Predict. Simulate. Win.", "Data. Intelligence. Victory.", an MV monogram with
circuit traces). Re-crop from the master collage as needed — keep that file as
the single source.

> The generated SVGs below (`scripts/generate_brand.py`) remain the system for
> **per-series RaceIQ marks** (F1/F2/F3/…), which the ecosystem collage does not
> cover. The ecosystem-level `logo.svg`/`mark.svg` produced by the generator are
> now superseded by the PNG artwork above for the hero/mark/favicon placements.

## What every (series) logo shares

1. **Common typography** — a condensed geometric uppercase wordmark
   (`Saira Condensed`, weight 700, positive letter-tracking). "Race" in ink,
   "IQ" in the series accent. The series tag below is tracked +4.
2. **Common technology aesthetic** — a *telemetry tick baseline*: a row of
   measurement ticks (every third tick taller/brighter) evoking timing screens.
3. **Common motorsport DNA** — a *forward speed chevron*: a double, forward-leaning
   chevron mark. Identical geometry across all series; only the color changes.
4. **A unique color palette per series** — the single variable that
   distinguishes one RaceIQ product from another.

## Series palette

| Series | Product | Accent | Mark |
|---|---|---|---|
| Formula 1 | RaceIQ F1 | `#E10600` red | `brand/sports/f1.svg` |
| Formula 2 | RaceIQ F2 | `#1E9BD7` azure | `brand/sports/f2.svg` |
| Formula 3 | RaceIQ F3 | `#9AA7B4` steel | `brand/sports/f3.svg` |
| Formula E | RaceIQ Formula E | `#18C8B6` teal | `brand/sports/formula-e.svg` |
| IndyCar | RaceIQ Indy | `#2E6BE6` blue | `brand/sports/indycar.svg` |
| NASCAR | RaceIQ NASCAR | `#F2B705` gold | `brand/sports/nascar.svg` |
| WEC | RaceIQ WEC | `#B5179E` magenta | `brand/sports/wec.svg` |
| Rally (WRC) | RaceIQ Rally | `#E2571E` orange | `brand/sports/wrc.svg` |
| *Le Mans* | RaceIQ Le Mans | `#1A8F4C` green | `brand/sports/lemans.svg` |
| *IMSA* | RaceIQ IMSA | `#3457D5` indigo | `brand/sports/imsa.svg` |
| *MotoGP* | RaceIQ MotoGP | `#CC0033` crimson | `brand/sports/motogp.svg` |

Colors are deliberately distinct in hue so two series are never confusable. The
per-series accent is also the `accent` field in each `registry/projects/*.json`
entry, so the catalog UI and the logo always agree.

The ecosystem itself uses a neutral electric-teal accent `#38e1c6` (not any one
series' color) so the hub never appears to favor a single championship.

## Asset inventory

```
website/public/brand/
├── logo.svg            MotorsportVerse horizontal lockup
├── mark.svg            MotorsportVerse square mark
├── favicon.svg         (= mark)
├── sports/<key>.svg    per-series square marks  → registry catalog icons
└── series/raceiq-<key>.svg  per-series horizontal lockups (the 8 named series)
website/public/og/default.svg   social-share card
```

Two sizes per series:

- **Mark** (`sports/<key>.svg`, 64×64) — the chevron in a rounded tile. Used as
  the catalog icon and as a favicon source.
- **Lockup** (`series/raceiq-<key>.svg`, 340×80) — chevron + "RaceIQ &lt;Series&gt;"
  wordmark + tick baseline. Used in project headers and READMEs.

## Usage rules

- **Don't recolor a series with another series' accent.** The accent *is* the
  identity. Change `SERIES` in the generator instead.
- **Don't restyle the wordmark per series.** Typography is shared on purpose.
- **Mark on dark only** by default (canvas `#0a0b0d`). For light contexts, wrap
  the mark tile (it carries its own dark background).
- **Placeholders today.** These are clean, coherent SVGs intended to be replaced
  by final artwork later *without changing any file paths* — every reference
  (registry icons, README, website) points at these stable names.

## Typography & tokens

The web design system (tokens, components) is documented separately in
[design-system.md](design-system.md). The logo wordmark font (`Saira Condensed`)
matches the F1 flagship's display face, keeping the family visually unified from
logo to live UI.
