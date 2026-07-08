"""Model-health / drift report for NASCAR — thin CLI over motorsport_core.drift.

Reads the per-round JSONs that :mod:`nascar_predictions.export` writes and
produces ``website/public/data/model_health.json``: feature drift (PSI of the
model's output distribution, early rounds vs recent rounds) plus an
output-side rolling Brier trend on the race win market. Same shape as F1's.

Run:  python -m nascar_predictions.drift_report --season 2026
          [--allow-empty] [--data <dir>]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from motorsport_core import drift

from . import config

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "website" / "public" / "data"

# Model-output columns we monitor for distribution drift. ``pDnf`` rides along
# because the hazard head is a first-class model component here.
FEATURE_COLUMNS = ("predictedValue", "pWin", "pPodium", "pDnf", "meanFinish", "finishRangeHigh")
# How many of the earliest / latest completed rounds form the baseline / current window.
DRIFT_WINDOW = 4


def _load_round(data_dir: Path, rnd: int) -> dict | None:
    path = data_dir / "rounds" / f"round_{rnd:02d}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _feature_records(round_json: dict) -> list[dict]:
    return list(round_json.get("race", {}).get("classification", []))


def _round_brier(round_json: dict) -> float | None:
    """Brier of the race win market: mean (p_win - I[finished P1])²."""
    rows = _feature_records(round_json)
    scored = [r for r in rows if r.get("actualPosition") is not None]
    if not scored:
        return None
    return sum(
        (float(r.get("pWin", 0.0)) - (1.0 if r["actualPosition"] == 1 else 0.0)) ** 2
        for r in scored
    ) / len(scored)


def build_report(data_dir: Path, year: int) -> drift.ModelHealthReport:
    completed = []
    for rnd in range(1, len(config.CALENDAR) + 1):
        rj = _load_round(data_dir, rnd)
        if rj is None or not rj.get("completed"):
            continue
        completed.append(rj)
    # Compare the two most recent non-overlapping windows so the early-season
    # cold start doesn't masquerade as drift.
    current = [rec for rj in completed[-DRIFT_WINDOW:] for rec in _feature_records(rj)]
    baseline = [
        rec for rj in completed[-2 * DRIFT_WINDOW: -DRIFT_WINDOW] for rec in _feature_records(rj)
    ]
    brier_by_round = [
        (rj["round"], b) for rj in completed if (b := _round_brier(rj)) is not None
    ]
    last_round = completed[-1]["round"] if completed else None
    return drift.build_health_report(
        season=year,
        last_evaluated_round=last_round,
        baseline_records=baseline,
        current_records=current,
        feature_columns=FEATURE_COLUMNS,
        brier_by_round=brier_by_round,
    )


def _serialize(report: drift.ModelHealthReport) -> dict:
    return {
        "season": report.season,
        "lastEvaluatedRound": report.last_evaluated_round,
        "featureDrift": [
            {"feature": f.feature, "psi": f.psi, "severity": f.severity}
            for f in report.feature_drift
        ],
        "outputDrift": (
            {
                "rollingBrierRecent": report.output_drift.rolling_brier_recent,
                "rollingBrierBaseline": report.output_drift.rolling_brier_baseline,
                "relativeChange": report.output_drift.relative_change,
                "severity": report.output_drift.severity,
                "roundsCompared": report.output_drift.rounds_compared,
            }
            if report.output_drift
            else None
        ),
        "warnings": report.warnings,
        "alarms": report.alarms,
        "brierByRound": report.brier_by_round,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--season", type=int, default=config.SEASON)
    p.add_argument("--data", type=Path, default=DEFAULT_DATA)
    p.add_argument("--allow-empty", action="store_true")
    args = p.parse_args()
    report = build_report(args.data, args.season)
    if report.last_evaluated_round is None and not args.allow_empty:
        print("drift_report: no round data found", flush=True)
        return 1
    out = args.data / "model_health.json"
    out.write_text(json.dumps(_serialize(report), indent=2) + "\n")
    print(f"drift_report: wrote {out} (warnings={len(report.warnings)}, alarms={len(report.alarms)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
