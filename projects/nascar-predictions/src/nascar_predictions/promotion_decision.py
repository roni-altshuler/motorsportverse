"""Promotion gate for NASCAR — thin CLI over motorsport_core.promotion.

Compares the production model's per-round error stream against a candidate's
and recommends promote / hold / demote via
:func:`motorsport_core.promotion.evaluate_promotion`.

The candidate is the **direct finishing-position head**
(:mod:`.position_head`, A/B-gated by ``NASCAR_USE_POSITION_HEAD`` and OFF by
default). Its walk-forward evidence is the
``forward_eval/position_model_ab.json`` artifact written by
``python -m nascar_predictions.forward_eval --position-model-ab``: per
completed round N the head retrains on rounds ``< N`` and is scored against
the same actuals as the production replay. This module aligns the two
per-round error streams, applies the shared conservative promotion rule, and
folds the A/B's own data-driven verdict into
``website/public/data/promotion_status.json``.

Without the A/B artifact this honestly reports ``hold`` for want of a
candidate.

Run:  python -m nascar_predictions.promotion_decision --season 2026
          [--allow-empty]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from motorsport_core import promotion

from . import config

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "website" / "public" / "data"

CANDIDATE_NAME = "position-head"


def _load_production_scores(data_dir: Path) -> list[tuple[int, float]]:
    """Production per-round score = race mean position error (lower better)."""
    fe_dir = data_dir / "forward_eval"
    scores: list[tuple[int, float]] = []
    if not fe_dir.exists():
        return scores
    for path in sorted(fe_dir.glob("round_*.json")):
        rj = json.loads(path.read_text())
        mpe = rj.get("race", {}).get("mean_position_error")
        if mpe is not None:
            scores.append((int(rj["round"]), float(mpe)))
    return scores


def _load_candidate_scores(data_dir: Path) -> tuple[list[tuple[int, float]], dict | None]:
    """Candidate per-round scores + A/B verdict from ``position_model_ab.json``.

    The candidate score mirrors the production stream's definition — the race
    mean position error of the walk-forward position head — so
    :func:`evaluate_promotion` compares like with like. Rounds where the head
    could not train (``applied: false``) are excluded; the promotion rule's
    minimum-overlap guard then does the honest thing.
    """
    ab_path = data_dir / "forward_eval" / "position_model_ab.json"
    if not ab_path.exists():
        return [], None
    try:
        ab = json.loads(ab_path.read_text())
    except (OSError, json.JSONDecodeError):
        return [], None
    scores: list[tuple[int, float]] = []
    for entry in ab.get("rounds", []):
        head = entry.get("positionHead") or {}
        if not head.get("applied"):
            continue
        mpe = (head.get("race") or {}).get("mean_position_error")
        if mpe is not None:
            scores.append((int(entry["round"]), float(mpe)))
    return scores, ab.get("verdict")


def build_status(data_dir: Path) -> dict:
    production = _load_production_scores(data_dir)
    candidate, ab_verdict = _load_candidate_scores(data_dir)
    decision = promotion.evaluate_promotion(production, candidate)
    return {
        # Original shape — the website reads these keys; never rename/remove.
        "decision": decision.decision,
        "reason": decision.reason,
        "roundsCompared": decision.rounds_compared,
        "meanProduction": decision.mean_production,
        "meanCandidate": decision.mean_candidate,
        "relativeChange": decision.relative_change,
        "hasCandidate": bool(candidate),
        # Additive: which candidate was compared and what its walk-forward A/B
        # concluded (the env flag stays OFF unless this says the head wins AND
        # the gate above agrees).
        "candidate": CANDIDATE_NAME if candidate else None,
        "candidateFlag": "NASCAR_USE_POSITION_HEAD",
        "abVerdict": ab_verdict,
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
    if status["abVerdict"]:
        v = status["abVerdict"]
        print(
            f"promotion_decision: A/B verdict — {v.get('recommendation')} "
            f"(head meanErr={v.get('positionHeadMeanError')} vs "
            f"prod meanErr={v.get('productionMeanError')})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
