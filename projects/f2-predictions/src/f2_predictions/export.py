"""Generate the F2 website's JSON data from the pipeline.

Writes a small, typed set of JSON files the F2 website reads at build time. The
shapes follow the spirit of the F1 contract but are intentionally compact. Run:

    python -m f2_predictions.export
    # or:  python -m f2_predictions.export --out <dir>

Default output dir is ``projects/f2-predictions/website/public/data``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config, pipeline
from .datasource import F2DataSource

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"


def build_payload() -> dict:
    source = F2DataSource()
    year = config.SEASON

    driver_standings = pipeline.driver_standings(source, year)
    teams = pipeline.team_standings(source, year)
    title = pipeline.project_title(source, year, n_samples=4000)

    next_round = config.COMPLETED_ROUNDS + 1
    prediction = None
    if next_round <= len(config.CALENDAR):
        pred = pipeline.predict_round(source, year, next_round)
        prediction = {
            "season": pred.season,
            "round": pred.round,
            "venueKey": pred.venue_key,
            "venueName": pred.venue_name,
            "qualifying": [
                {"position": i, "code": c, "name": config.DRIVER_NAME[c], "team": config.TEAM_OF[c]}
                for i, c in enumerate(pred.qualifying_order, start=1)
            ],
            "race": [
                {
                    "position": i,
                    "code": c,
                    "name": config.DRIVER_NAME[c],
                    "team": config.TEAM_OF[c],
                    "pWin": round(pred.p_win.get(c, 0.0), 4),
                    "pPodium": round(pred.p_podium.get(c, 0.0), 4),
                }
                for i, c in enumerate(pred.race_order, start=1)
            ],
        }

    return {
        "sport": config.SPORT,
        "season": year,
        "completedRounds": config.COMPLETED_ROUNDS,
        "totalRounds": len(config.CALENDAR),
        "calendar": [
            {
                "round": i,
                "key": v.key,
                "name": v.name,
                "country": v.country,
                "completed": i <= config.COMPLETED_ROUNDS,
            }
            for i, v in enumerate(config.CALENDAR, start=1)
        ],
        "driverStandings": [
            {
                "position": i,
                "code": r.key,
                "name": config.DRIVER_NAME.get(r.key, r.key),
                "team": config.TEAM_OF.get(r.key, ""),
                "points": r.points,
                "wins": r.wins,
                "podiums": r.podiums,
            }
            for i, r in enumerate(driver_standings, start=1)
        ],
        "teamStandings": [
            {"position": i, "team": r.key, "points": r.points, "wins": r.wins, "podiums": r.podiums}
            for i, r in enumerate(teams, start=1)
        ],
        "championship": [
            {
                "code": t.key,
                "name": config.DRIVER_NAME.get(t.key, t.key),
                "team": config.TEAM_OF.get(t.key, ""),
                "pTitle": t.p_title,
                "currentPoints": t.current_points,
                "projMean": t.proj_mean,
                "projP10": t.proj_p10,
                "projP90": t.proj_p90,
            }
            for t in title
        ],
        "nextPrediction": prediction,
    }


def write(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    path = out_dir / "f2.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    path = write(args.out)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
