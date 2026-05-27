# Team logos

This directory holds team logo assets used by `<TeamBadge>`.

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

## What's shipped here

Typographic placeholder marks (three-letter abbreviation inside a
ringed disc in the official team colour). They are intentionally
neutral so the repo can ship them safely. Replace any of these with
the official transparent SVG by overwriting the same filename —
`<TeamBadge>` will pick up the new asset automatically.

## Fallback behaviour

`<TeamBadge>` handles a missing file gracefully: on 404 it falls back
to a tinted initials badge. The UI never shows a broken-image icon.
