"""Export the simulated Prism Cup season to the website's data directory.

Usage (from the project root):

    PYTHONPATH=src python -m prism_cup.export [--out DIR] [--seed N]

Writes, under `website/public/data/` by default:

    prism-cup.json    roster summary + season standings + cup winners + items
    roster.json       character cards (stats + bios)
    tracks.json       circuit cards
    cups/cup_N.json   one file per cup: 4 race classifications + highlights

Output is fully deterministic for a given seed (no timestamps), so re-running
the exporter never dirties the tree.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prism_cup import config
from prism_cup.simulate import select_highlights, simulate_season

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = PROJECT_ROOT / "website" / "public" / "data"


def _racer_card(racer: dict) -> dict:
    return {
        "id": racer["id"],
        "name": racer["name"],
        "vibe": racer["vibe"],
        "weightClass": racer["weight_class"],
        "color": racer["color"],
        "bio": racer["bio"],
        "stats": {
            "accel": racer["accel"],
            "topSpeed": racer["top_speed"],
            "knockResistance": racer["knock_resistance"],
            "itemLuck": racer["item_luck"],
        },
    }


def _track_card(track: dict) -> dict:
    return {
        "id": track["id"],
        "name": track["name"],
        "laps": track["laps"],
        "hazard": track["hazard"],
        "boostPadDensity": track["boost_pad_density"],
        "color": track["color"],
        "character": track["character"],
    }


def _race_report(race: dict) -> dict:
    return {
        "trackId": race["trackId"],
        "trackName": race["trackName"],
        "laps": race["laps"],
        "classification": race["classification"],
        "highlights": select_highlights(race["events"]),
    }


def build_payloads(seed: int = config.SEASON_SEED) -> dict[str, dict]:
    """Simulate the season and shape every JSON payload, keyed by file path."""
    season = simulate_season(seed)
    payloads: dict[str, dict] = {}

    payloads["roster.json"] = {
        "weightClasses": config.WEIGHT_CLASSES,
        "racers": [_racer_card(r) for r in config.ROSTER],
    }
    payloads["tracks.json"] = {"tracks": [_track_card(t) for t in config.TRACKS]}

    for cup in season["cups"]:
        payloads[f"cups/cup_{cup['number']}.json"] = {
            "number": cup["number"],
            "id": cup["id"],
            "name": cup["name"],
            "trackIds": cup["trackIds"],
            "standings": cup["standings"],
            "races": [_race_report(r) for r in cup["races"]],
        }

    total_races = sum(len(c["races"]) for c in season["cups"])
    payloads["prism-cup.json"] = {
        "league": "Prism Cup Karting",
        "season": 1,
        "seed": season["seed"],
        "disclaimer": config.DISCLAIMER,
        "champion": season["champion"],
        "standings": season["standings"],
        "cupWinners": season["cupWinners"],
        "cups": [
            {"number": c["number"], "id": c["id"], "name": c["name"], "trackIds": c["trackIds"]}
            for c in season["cups"]
        ],
        "items": config.ITEMS,
        "summary": {
            "totalRaces": total_races,
            "totalCups": len(season["cups"]),
            "fieldSize": config.FIELD_SIZE,
            "uniqueWinners": len({c["winner"] for c in season["cupWinners"]}),
        },
    }
    return payloads


def export_all(out_dir: Path | str = DEFAULT_OUT, seed: int = config.SEASON_SEED) -> list[Path]:
    out = Path(out_dir)
    written = []
    for rel, payload in build_payloads(seed).items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the simulated Prism Cup season data.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    parser.add_argument("--seed", type=int, default=config.SEASON_SEED, help="season seed")
    args = parser.parse_args()
    for path in export_all(args.out, args.seed):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
