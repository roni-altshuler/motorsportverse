# Team logos

This directory holds team-logo assets used by `<TeamBadge>`.

## Quick start — adding your own logos

To swap in a licensed team logo (your own asset, or one you have rights
to use): drop an SVG (or PNG) into this directory using the filename
convention below. `<TeamBadge>` picks the new file up automatically on
the next build — no code change needed.

```
website/public/team-logos/<team-slug>.svg
```

That's it. The slug derivation is below; the fallback chain handles
the rest.

## Filename convention

`<team-slug>.svg` — where `<team-slug>` is the team name lower-cased
and hyphenated. Example mapping:

| Team name        | Filename                |
|------------------|-------------------------|
| Mercedes         | `mercedes.svg`          |
| Red Bull Racing  | `red-bull-racing.svg`   |
| Ferrari          | `ferrari.svg`           |
| McLaren          | `mclaren.svg`           |
| Aston Martin     | `aston-martin.svg`      |
| Alpine           | `alpine.svg`            |
| Williams         | `williams.svg`          |
| Racing Bulls     | `racing-bulls.svg`      |
| Haas             | `haas.svg`              |
| Audi             | `audi.svg`              |
| Cadillac         | `cadillac.svg`          |

The slug derivation lives in
[`src/lib/teamLogo.ts`](../../src/lib/teamLogo.ts) — `teamSlug(name)`.

## Recommended asset specs

For best results across both badge variants:

- **Format**: SVG preferred (scales cleanly); transparent PNG also OK
- **Aspect ratio**: roughly square (256×256 viewBox is what's
  shipped); the badge crops at the centre when rendered in the
  circular "badge" variant
- **Colour**: should read on both dark and light surfaces; the badge
  background sits on a near-black backdrop with the team's accent
  colour as a frame
- **Layout** (for the rectangular "card" variant): emblem on top,
  team wordmark, optional small subtitle — matches the broadcast
  graphics pattern used in motorsport coverage

## What ships in this repo

The 11 SVGs currently committed here are **abstract geometric
placeholders** — three-letter abbreviation inside a ringed disc with
the team wordmark beneath, in each team's official colour. They are
**not** reproductions of the trademarked team logos and are
intentionally neutral so the repo can ship them safely. Replace any
of them with your licensed assets by overwriting the same filename.

## Fallback behaviour

`<TeamBadge>` handles a missing file gracefully:
1. Try the explicit `logoUrl` prop (if passed)
2. Try the conventional `/team-logos/<slug>.svg` path
3. On `onError` (file 404s), fall back to a tinted initials badge

The UI never shows a broken-image icon. You can ship logos for some
teams and leave others on the initials fallback — they'll mix cleanly.
