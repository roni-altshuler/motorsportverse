"""Export the simulated season as the website's JSON data contract.

    python -m chrome_valley.export [--out DIR] [--seed N]

Writes into ``website/public/data/`` by default:

* ``chrome-valley.json`` — league info, venues, calendar, standings, summary
* ``roster.json``        — character cards (traits + bios) for the garage
* ``rounds/round_NN.json`` — full classification + events + 3 story bullets

The output is deterministic for a given seed (no timestamps), so rebuilding
the site never churns the data files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from chrome_valley import config, simulate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = PROJECT_ROOT / "website" / "public" / "data"


def _character_card(char: config.Character) -> dict:
    return {
        "slug": char.slug,
        "name": char.name,
        "number": char.number,
        "car": char.car,
        "hometown": char.hometown,
        "role": char.role,
        "bio": char.bio,
        "color": char.color,
        "basePace": char.base_pace,
        "traits": {
            "grit": char.grit,
            "showboat": char.showboat,
            "consistency": char.consistency,
            "heart": char.heart,
        },
        "affinity": dict(char.affinity),
    }


def _venue_card(venue: config.Venue) -> dict:
    return {
        "slug": venue.slug,
        "name": venue.name,
        "kind": venue.kind,
        "tags": list(venue.tags),
        "laps": venue.laps,
        "chaos": venue.chaos,
        "pitDrama": venue.pit_drama,
        "night": venue.night,
        "blurb": venue.blurb,
    }


def build_roster() -> dict:
    return {
        "league": config.LEAGUE_NAME,
        "disclaimer": config.DISCLAIMER,
        "characters": [_character_card(c) for c in config.CHARACTERS],
    }


def build_round(race: simulate.Race) -> dict:
    venue = config.venue_by_slug(race.venue_slug)
    return {
        "round": race.round,
        "venue": {
            "slug": venue.slug,
            "name": venue.name,
            "kind": venue.kind,
            "laps": venue.laps,
        },
        "story": list(race.story),
        "results": [
            {
                "position": r.position,
                "slug": r.slug,
                "name": config.character_by_slug(r.slug).name,
                "number": config.character_by_slug(r.slug).number,
                "points": r.points,
                "lapsCompleted": r.laps_completed,
                "dnf": r.dnf,
                "dnfReason": r.dnf_reason,
                "lapsLed": r.laps_led,
                "gapSeconds": r.gap_seconds,
            }
            for r in race.results
        ],
        "events": [
            {"lap": e.lap, "kind": e.kind, "slug": e.slug, "detail": e.detail}
            for e in race.events
        ],
    }


def build_league(season: simulate.Season) -> dict:
    winners = {race.round: race.results[0].slug for race in season.races}
    champion = season.champion
    return {
        "league": {
            "name": config.LEAGUE_NAME,
            "tagline": config.TAGLINE,
            "trophy": config.TROPHY_NAME,
            "disclaimer": config.DISCLAIMER,
        },
        "seed": season.seed,
        "season": {
            "name": config.SEASON_NAME,
            "rounds": len(season.races),
            "champion": {
                "slug": champion.slug,
                "name": config.character_by_slug(champion.slug).name,
                "points": champion.points,
            },
            "summary": simulate.season_summary(season),
        },
        "venues": [_venue_card(v) for v in config.VENUES],
        "calendar": [
            {
                "round": race.round,
                "venueSlug": race.venue_slug,
                "venueName": config.venue_by_slug(race.venue_slug).name,
                "kind": config.venue_by_slug(race.venue_slug).kind,
                "winnerSlug": winners[race.round],
                "winnerName": config.character_by_slug(winners[race.round]).name,
            }
            for race in season.races
        ],
        "standings": [
            {
                "position": row.position,
                "slug": row.slug,
                "name": config.character_by_slug(row.slug).name,
                "number": config.character_by_slug(row.slug).number,
                "color": config.character_by_slug(row.slug).color,
                "points": row.points,
                "wins": row.wins,
                "podiums": row.podiums,
                "dnfs": row.dnfs,
            }
            for row in season.standings
        ],
    }


def export(out_dir: Path, seed: int = config.DEFAULT_SEED) -> list[Path]:
    season = simulate.simulate_season(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "rounds").mkdir(exist_ok=True)

    written: list[Path] = []

    def write(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        written.append(path)

    write(out_dir / "chrome-valley.json", build_league(season))
    write(out_dir / "roster.json", build_roster())
    for race in season.races:
        write(out_dir / "rounds" / f"round_{race.round:02d}.json", build_round(race))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the Chrome Valley simulated season.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output data directory")
    parser.add_argument("--seed", type=int, default=config.DEFAULT_SEED, help="season seed")
    args = parser.parse_args(argv)
    written = export(args.out, args.seed)
    for path in written:
        print(f"wrote {path}")
    print(f"exported season (seed={args.seed}) → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
