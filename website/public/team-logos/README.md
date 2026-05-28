# Team logos

This directory holds team-logo assets used by `<TeamBadge>`.

## Asset map

The current files in this directory and their team mapping. The mapping lives in [`src/lib/teamLogo.ts`](../../src/lib/teamLogo.ts) — `LOGO_BY_TEAM`. To swap any of these out: drop a new file with the same filename into this directory and the UI picks it up automatically.

| Team             | File                       |
|------------------|----------------------------|
| Mercedes         | `MercedesBenzLogo.png`     |
| Red Bull Racing  | `RedBullLogo.webp`         |
| Ferrari          | `FerrariLogo.avif`         |
| McLaren          | `MclarenLogo.jpg`          |
| Aston Martin     | `AstonMartinLogo.png`      |
| Alpine           | `AlpineLogo.svg`           |
| Williams         | `WilliamsLogo.png`         |
| Racing Bulls     | `RacingBullLogo.png`       |
| Haas             | `HaasLogo.jpg`             |
| Audi             | `AudiLogo.png`             |
| Cadillac         | `CadillacLogo.webp`        |

## Adding a new team

1. Drop the asset file into this directory (any standard web format works — SVG/PNG/JPG/WebP/AVIF).
2. Add the team name → filename pair to `LOGO_BY_TEAM` in [`src/lib/teamLogo.ts`](../../src/lib/teamLogo.ts).

That's it. `<TeamBadge>` resolves the URL via `teamLogoUrl(team)` and renders the asset. A missing or 404 file degrades gracefully to a tinted initials badge.

## Recommended specs

- **Format**: SVG ideal for crispness; PNG with transparency is fine. AVIF / WebP supported.
- **Aspect**: roughly square works best across both badge variants. The `card` variant gives the logo more room to breathe.
- **Background**: transparent. The badge renders on a near-black backdrop framed by the team's accent colour.
