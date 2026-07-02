"""Promotion gate for F3 — thin CLI over motorsport_core.promotion.

Compares a production model's per-round error stream against a candidate's and
recommends promote / hold / demote via :func:`motorsport_core.promotion.evaluate_promotion`.

In Phase 1 there is a single (production) variant and a synthetic data source, so
this honestly reports ``hold`` for want of a candidate / enough real rounds. The
machinery is wired now so Phase 2 only has to supply candidate scores — it writes
``website/public/data/promotion_status.json`` either way.

Run:  python -m f3_predictions.promotion_decision --season 2026 [--allow-empty]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from motorsport_core import promotion

from . import config

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "website" / "public" / "data"


def _load_production_scores(data_dir: Path) -> list[tuple[int, float]]:
    """Production per-round score = feature-race mean position error (lower better)."""
    fe_dir = data_dir / "forward_eval"
    scores: list[tuple[int, float]] = []
    if not fe_dir.exists():
        return scores
    for path in sorted(fe_dir.glob("round_*.json")):
        rj = json.loads(path.read_text())
        mpe = rj.get("feature", {}).get("mean_position_error")
        if mpe is not None:
            scores.append((int(rj["round"]), float(mpe)))
    return scores


def build_status(data_dir: Path) -> dict:
    production = _load_production_scores(data_dir)
    # Phase 1: no candidate stream yet → empty, which the gate reports as "hold".
    candidate: list[tuple[int, float]] = []
    decision = promotion.evaluate_promotion(production, candidate)
    return {
        "decision": decision.decision,
        "reason": decision.reason,
        "roundsCompared": decision.rounds_compared,
        "meanProduction": decision.mean_production,
        "meanCandidate": decision.mean_candidate,
        "relativeChange": decision.relative_change,
        "hasCandidate": bool(candidate),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--season", type=int, default=config.SEASON)
    p.add_argument("--data", type=Path, default=DEFAULT_DATA)
    p.add_argument("--allow-empty", action="store_true")
    args = p.parse_args()
    status = build_status(args.data)
    out = args.data / "promotion_status.json"
    out.write_text(json.dumps(status, indent=2) + "\n")
    print(f"promotion_decision: {status['decision']} — {status['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
