"""Cross-season backtest.

Phase 6 roadmap item.  After a season completes, re-run the prediction
pipeline retrospectively on prior seasons and report MAE per season so
we can see whether the model's effectiveness is drifting over time.

This is the scaffold — it reads pre-existing per-round forward-eval
JSONs from prior seasons (or from the same season's archive directory)
and computes the season-level summary.  Re-running the FULL prediction
pipeline against prior seasons is intentionally NOT in scope here: that
needs the FastF1 archive + multi-day backfill time and is best done as
a one-shot offline batch.

Usage::

    # After populating reports/forward_eval_2024.json etc.
    python cross_season_backtest.py --seasons 2024 2025 2026

The script does not require prior-season files to exist; missing
seasons are reported as such rather than crashing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_OUTPUT = REPORTS_DIR / "cross_season_backtest.json"


def _load_season_report(season: int) -> Optional[dict]:
    path = REPORTS_DIR / f"forward_eval_{season}.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _summary_from_rounds(rounds: list[dict]) -> dict:
    if not rounds:
        return {
            "rounds_evaluated": 0,
            "mae": None,
            "podium_hit_rate": None,
            "winner_hit_rate": None,
            "spearman": None,
        }
    maes = [float(r["mean_position_error"]) for r in rounds if "mean_position_error" in r]
    podium_hits = [int(r.get("podium_hits", 0)) for r in rounds]
    winner_hits = [bool(r.get("winner_hit", False)) for r in rounds]
    spearmans = [
        float(r["spearman_correlation"])
        for r in rounds
        if isinstance(r.get("spearman_correlation"), (int, float))
    ]
    return {
        "rounds_evaluated": len(rounds),
        "mae": round(mean(maes), 3) if maes else None,
        "podium_hit_rate": round(sum(podium_hits) / (3 * len(rounds)), 3) if rounds else None,
        "winner_hit_rate": round(sum(winner_hits) / len(rounds), 3) if rounds else None,
        "spearman": round(mean(spearmans), 3) if spearmans else None,
    }


def run(seasons: list[int], output: Path) -> int:
    per_season: dict[str, dict] = {}
    for season in seasons:
        report = _load_season_report(season)
        if report is None:
            per_season[str(season)] = {"status": "no_report"}
            continue
        rounds = report.get("rounds", []) or []
        per_season[str(season)] = {"status": "ok", **_summary_from_rounds(rounds)}

    payload = {
        "seasons_requested": seasons,
        "per_season": per_season,
        "drift": _drift_summary(per_season),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as fh:
        json.dump(payload, fh, indent=2)

    print()
    print(f"Cross-season backtest summary — {len(seasons)} seasons")
    print("─" * 60)
    for season in sorted(per_season, key=int):
        s = per_season[season]
        if s.get("status") != "ok":
            print(f"{season}: no report (run forward_eval.py for that season first)")
            continue
        mae = s.get("mae")
        spr = s.get("spearman")
        print(
            f"{season}: n={s['rounds_evaluated']:>2}  "
            f"MAE={mae if mae is not None else '—'}  "
            f"Spearman={spr if spr is not None else '—'}  "
            f"podium-hit-rate={s.get('podium_hit_rate')}"
        )
    print(f"\n📝 Written {output.relative_to(PROJECT_ROOT)}")
    return 0


def _drift_summary(per_season: dict[str, dict]) -> dict:
    """Compute deltas vs. the earliest available season so a reader can
    see whether MAE / Spearman are drifting up or down over time."""
    keys_with_data = sorted(
        [k for k, v in per_season.items() if v.get("status") == "ok" and v.get("mae") is not None],
        key=int,
    )
    if len(keys_with_data) < 2:
        return {"available": False, "reason": "need at least 2 seasons with completed forward-eval"}
    baseline = per_season[keys_with_data[0]]
    deltas: dict[str, dict] = {}
    for k in keys_with_data[1:]:
        s = per_season[k]
        deltas[k] = {
            "mae_delta": (
                round(s["mae"] - baseline["mae"], 3)
                if baseline.get("mae") is not None
                else None
            ),
            "spearman_delta": (
                round(s["spearman"] - baseline["spearman"], 3)
                if s.get("spearman") is not None and baseline.get("spearman") is not None
                else None
            ),
        }
    return {"available": True, "baseline_season": keys_with_data[0], "deltas": deltas}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seasons", nargs="+", type=int, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    return run(args.seasons, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
