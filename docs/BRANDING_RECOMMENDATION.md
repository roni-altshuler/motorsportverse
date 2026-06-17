# MotorsportVerse / RaceIQ — Branding Recommendation

**Date:** 2026-06-17 · **Branch:** `feat/f2-production`
**Question:** As the ecosystem expands beyond F1 and F2, should RaceIQ use **(A)** a single RaceIQ logo adapted across all series, or **(B)** series-specific logos that share a common RaceIQ visual language?

**Recommendation: Option B — series-specific marks sharing one RaceIQ visual language.** The owner has commissioned a professional brand board that realises exactly this (see *Delivered artwork* below), and it is the right call now that the artwork exists: it preserves ecosystem recognition (shared wordmark, typography, tagline, master mark) while giving each series a distinct, category-appropriate identity. The repo's generated colour-only SVGs (Option A) remain a useful **fallback** for not-yet-designed concept series. The A↔B analysis below records why.

> **Update (2026-06-17):** this recommendation was revised after the owner added a finished brand board — [`brand/source/raceiq-combined-logos.png`](../website/public/brand/source/raceiq-combined-logos.png) (preview: [`docs/assets/f2-review/branding-board.png`](assets/f2-review/branding-board.png)). It supersedes the placeholder system as the design source of truth.

---

## Current state (what's built)

- **Names:** ecosystem = **MotorsportVerse** (the hub/catalog); product family = **RaceIQ** (the engine); per series = **RaceIQ `<Series>`** (RaceIQ F1, RaceIQ F2, …).
- **One generator:** [`scripts/generate_brand.py`](../scripts/generate_brand.py) holds a single `SERIES` table `(key, label, accent)` and emits 23 SVGs — per-series **marks** (`brand/sports/<key>.svg`) and **lockups** (`brand/series/raceiq-<key>.svg`), plus the ecosystem mark/OG.
- **One design language:** every series logo shares the condensed **Saira** wordmark, the forward **speed-chevron** mark, and the **telemetry-tick** baseline. The *only* per-series variable is the accent colour (F1 `#E10600`, F2 `#1E9BD7`, F3 steel, Formula E teal, IndyCar blue, NASCAR gold, WEC magenta, WRC orange, Le Mans green, IMSA indigo, MotoGP crimson). The ecosystem itself uses a neutral teal `#38e1c6` so no single series dominates the hub.
- **Verified:** `raceiq-f1.svg` and `raceiq-f2.svg` are byte-identical apart from the colour and the series label — i.e. the system already behaves as "one logo, recoloured per series."

So in the question's terms, the repo's *generated* assets implement **Option A**, while structurally delivering Option B's promise (a coherent shared language with a recognisable per-series identity).

## Delivered artwork (the chosen direction)

The owner added a finished brand board — `website/public/brand/source/raceiq-combined-logos.png` — that defines the production system:

- **Master brand:** a **MOTORSPORTVERSE** wordmark + race-car mark, tagline *"AI · PREDICTION · ANALYTICS"*; ecosystem tagline *"ONE UNIVERSE · EVERY MOTORSPORT"*.
- **Typography:** **Orbitron** (a wide, technical display face) — replaces the placeholder Saira Condensed.
- **Per-series lockups:** *RaceIQ F1, F2, F3, Formula E, Indy, NASCAR, WEC, Rally* — each a **category-appropriate car silhouette** (open-wheeler, stock car, LMP, rally car, …) in the series accent colour, with the shared *RaceIQ `<Series>`* wordmark + per-series tagline.
- **Variants per logo:** icon mark · monochrome · dark-mode · light-mode.
- **Palette:** the full per-series colour set + neutral black/white, consistent with the registry `accent` values.

This is **Option B done well**: strong per-series identity (distinct silhouettes) bound by one visual language (shared wordmark, Orbitron, tagline, master mark, colour system). It keeps "this is RaceIQ" and "this is the series" both instantly legible.

**Integration status:** the board is a single reference image (1639×959, no transparency) — not yet per-series web-ready assets. Wiring it onto the live sites needs individual exports (SVG preferred, or transparent/high-res PNG) for the master mark and each series lockup, to replace the placeholder `brand/logo.svg` / `brand/series/raceiq-*.svg`. Tracked as a launch follow-up (does not block the F2 *data* launch).

---

## Option A — single RaceIQ logo, per-series colour

**Pros**
- **Instant ecosystem recognition.** The chevron + wordmark + ticks are constant, so any RaceIQ property is recognisably RaceIQ at a glance — the explicit goal ("this is RaceIQ" / "this is Formula 2").
- **Trivial scalability.** Adding a sport = one row in the `SERIES` table (key, label, colour) → regenerate. No new design work, no per-series artwork commissioning.
- **Lowest maintenance.** One generator is the single source of truth; a tweak to the wordmark/chevron propagates to all series in one commit. No drift between 11+ logo sets.
- **Consistent quality floor.** Every series ships at the same visual quality automatically; a new/low-maturity sport never looks worse than the flagship.
- **Colour does the differentiation work** — the fastest visual cue humans parse, and series already own strong colour identities.

**Cons**
- **Colour-only distinction** can be subtle for colour-blind users or in monochrome contexts (mitigated by the always-present series label text).
- **Less bespoke personality** per series — a logo can't lean into a series' heritage iconography (e.g. an oval for NASCAR).
- Two series with nearby hues could be confusable at thumbnail size (the current palette is chosen for separation, so this is latent, not active).

## Option B — series-specific logos sharing a visual language

**Pros**
- **Stronger individual identity** per series; room for heritage cues and series-specific motifs.
- Useful if a series becomes an **independent product/partnership** that must stand alone off-platform.

**Cons**
- **Design + maintenance cost scales linearly** with the catalog (11 entries today, more later) — every series needs bespoke artwork and upkeep.
- **Drift risk:** keeping N hand-made logos "in the same language" is exactly the consistency problem Option A eliminates by construction.
- **Slower expansion:** a new sport can't launch until its logo is designed — friction against the "add a sport in minutes" ethos (`scripts/new_project.py`).
- **Diluted ecosystem recognition** if per-series personality is pushed too far.

---

## Decision matrix

| Criterion | Option A (single, recoloured) | Option B (series-specific) |
|-----------|-------------------------------|----------------------------|
| Ecosystem recognition | ★★★★★ | ★★★ |
| Per-series distinction | ★★★★ (colour + label) | ★★★★★ |
| Scalability (add a sport) | ★★★★★ (one table row) | ★★ (design each) |
| Maintenance burden | ★★★★★ (one generator) | ★★ (N logo sets) |
| Consistency guarantee | ★★★★★ (by construction) | ★★★ (manual discipline) |
| Bespoke personality | ★★★ | ★★★★★ |

In the **abstract** (no artwork yet), Option A wins on recognition, scalability, maintenance, and guaranteed consistency — which is why the placeholder generator was built that way, and why it stays the **fallback** for undesigned concept series. But the trade-off flips once a **cohesive, professionally-designed** Option-B set exists: the delivered board pays down B's only real costs (design effort + drift) up front and as a single coherent system, so B's stronger per-series identity becomes a clear net win **without** sacrificing ecosystem recognition (the shared wordmark/typography/tagline/master mark carry it).

---

## Recommendation & guardrails

**Adopt Option B — the delivered RaceIQ brand board — as the standing system**, with the generated SVGs as the fallback for not-yet-designed series. Guardrails:

- Treat the **brand board** (`brand/source/raceiq-combined-logos.png`) as the design source of truth; produce per-series web exports from it.
- Preserve the **shared language** on every series mark: the *RaceIQ* wordmark in **Orbitron**, the per-series tagline, the master **MOTORSPORTVERSE** mark, and the registry-aligned colour per series — so ecosystem recognition never depends on the silhouette alone.
- Keep the **series label text** in every lockup (distinction never relies on colour or silhouette alone — accessibility).
- For a **new concept series** with no bespoke art yet, fall back to the colour-only generated lockup so it can still launch immediately (`scripts/new_project.py`), then upgrade to a designed silhouette when promoted.
- Swap assets **without changing file paths** (`brand/logo.svg`, `brand/series/raceiq-<key>.svg`, `brand/sports/<key>.svg`) so integration needs no code changes.

**Integration follow-up (post-data-launch):** export the master mark + each series lockup (SVG preferred) from the board and drop them onto the existing paths; update the sites' display font to Orbitron for the wordmark. This is a visual-polish pass independent of the F2 data launch.
