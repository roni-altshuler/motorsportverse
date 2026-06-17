"""Forward-time evaluation for F2 — scores leakage-safe predictions vs actuals.

For every completed round we re-run the model with *only* prior-round data (the
same leakage-safe forecast the website shows pre-race) and score it against the
actual classification, per race-type and pooled. The metrics are the shared
:func:`motorsport_core.eval.score_round` bundle, so F2's accuracy page renders
with the same components as F1's.

Outputs (under ``website/public/data/forward_eval/``):
    round_NN.json   per-round sprint + feature + pooled metrics
    season.json     season roll-up (means over scored rounds)

Run:  python -m f2_predictions.forward_eval --season 2026 [--allow-empty] [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from motorsport_core import eval as core_eval

from . import config, model, pipeline
from .datasource import F2DataSource

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data" / "forward_eval"


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _score_race(fc_race, actual: dict[str, int]) -> dict:
    predicted = {code: i for i, code in enumerate(fc_race.order, start=1)}
    return core_eval.score_round(predicted, actual)


def evaluate_season(year: int) -> list[dict]:
    source = F2DataSource()
    rounds: list[dict] = []
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        fc = pipeline.forecast_round(source, year, rnd)
        races = source.race_results_for_round(year, rnd)
        sprint_actual = {r.competitor: r.position for r in races[model.SPRINT]}
        feature_actual = {r.competitor: r.position for r in races[model.FEATURE]}
        if not feature_actual:
            continue
        rounds.append(
            {
                "round": rnd,
                "venueName": fc.venue_name,
                "sprint": _score_race(fc.sprint, sprint_actual),
                "feature": _score_race(fc.feature, feature_actual),
            }
        )
    return rounds


def _season_summary(year: int, rounds: list[dict]) -> dict:
    def _mean(key: str) -> float | None:
        vals = [
            r["feature"][key]
            for r in rounds
            if r["feature"].get(key) is not None and r["feature"].get("n", 0) > 0
        ]
        return round(sum(vals) / len(vals), 4) if vals else None

    winner_hits = sum(1 for r in rounds if r["feature"].get("winner_hit"))
    podium_hits = sum(r["feature"].get("podium_hits", 0) for r in rounds)
    scored = len(rounds)
    return {
        "season": year,
        "roundsScored": scored,
        "meanPositionError": _mean("mean_position_error"),
        "meanNdcgAt5": _mean("ndcg_at_5"),
        "winnerHitRate": round(winner_hits / scored, 4) if scored else None,
        "podiumHitRate": round(podium_hits / (scored * 3), 4) if scored else None,
    }


def write(out_dir: Path, year: int) -> int:
    rounds = evaluate_season(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in rounds:
        (out_dir / f"round_{_pad2(r['round'])}.json").write_text(json.dumps(r, indent=2) + "\n")
    (out_dir / "season.json").write_text(json.dumps(_season_summary(year, rounds), indent=2) + "\n")
    return len(rounds)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--season", type=int, default=config.SEASON)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--allow-empty", action="store_true", help="exit 0 even if no rounds are scorable")
    args = p.parse_args()
    n = write(args.out, args.season)
    if n == 0 and not args.allow_empty:
        print("forward_eval: no completed rounds to score", flush=True)
        return 1
    print(f"forward_eval: scored {n} round(s) → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
