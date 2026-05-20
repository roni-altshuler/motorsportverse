"""CLI that builds the model-health report from round + forward-eval JSON.

Why this exists
---------------
``models/drift.py`` is the pure computational core (PSI, rolling Brier).
This CLI is the glue that pulls per-round inputs from disk and writes
``website/public/data/model_health.json`` for the website's accuracy
panel to render.  Mirrors the ``forward_eval.py`` CLI pattern so CI
wiring is uniform.

Inputs
------
* ``website/public/data/rounds/round_NN.json`` — feature-side: each
  classification entry carries ``predictedTime``, ``winProbability``,
  ``finishRangeLow/High`` etc.  We treat the trailing N-1 rounds as the
  *baseline distribution* and the latest round as *current*.
* ``website/public/data/forward_eval/round_NN.json`` — output-side:
  each carries ``rmse_position_error`` and (optionally) Brier proxies.
  In v1 we use ``rmse_position_error`` as the per-round "lower-is-better"
  score; a future enhancement will switch to per-market Brier from the
  probabilities layer once those are persisted per round.

Output
------
``website/public/data/model_health.json`` (gitignored only via the
implicit /data/ rule — ``website/public/data/`` is force-added by
``update_predictions.yml``).

Usage
-----
::

    python drift_report.py --season 2026
    python drift_report.py --season 2026 --output reports/drift_2026.json
    python drift_report.py --season 2026 --allow-empty  # exit 0 if no rounds
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from models.drift import (
    ModelHealthReport,
    build_health_report,
)

PROJECT_ROOT = Path(__file__).resolve().parent
WEBSITE_ROUNDS = PROJECT_ROOT / "website" / "public" / "data" / "rounds"
WEBSITE_FORWARD_EVAL = PROJECT_ROOT / "website" / "public" / "data" / "forward_eval"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "website" / "public" / "data" / "model_health.json"
)

# Features pulled from each classification entry for PSI.  Each feature is
# a numeric prediction-side metric we'd expect to be stable across rounds
# in a healthy model.  When the distribution shifts the model's environment
# has changed in a way worth surfacing.
DEFAULT_FEATURE_COLUMNS: tuple[str, ...] = (
    "predictedTime",
    "winProbability",
    "finishRangeLow",
    "finishRangeHigh",
)


def _load_round_jsons(rounds_dir: Path) -> dict[int, dict]:
    """Read every ``round_NN.json`` under ``rounds_dir`` keyed by round."""
    out: dict[int, dict] = {}
    if not rounds_dir.exists():
        return out
    for path in sorted(rounds_dir.glob("round_*.json")):
        try:
            stem = path.stem.split("_")[-1]
            rnd = int(stem)
        except ValueError:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                out[rnd] = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _classification_records(round_data: dict) -> list[dict]:
    return list(round_data.get("classification") or [])


def _load_forward_eval(forward_eval_dir: Path) -> dict[int, dict]:
    """Read forward_eval/round_NN.json files keyed by round."""
    out: dict[int, dict] = {}
    if not forward_eval_dir.exists():
        return out
    for path in sorted(forward_eval_dir.glob("round_*.json")):
        try:
            stem = path.stem.split("_")[-1]
            rnd = int(stem)
        except ValueError:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                out[rnd] = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _build_brier_series(
    forward_eval_by_round: dict[int, dict],
) -> list[tuple[int, float]]:
    """Extract (round, score) pairs from forward-eval files.

    For v1 we use ``rmse_position_error`` as the "lower-is-better" per-
    round score — it's already populated by ``forward_eval.py``.  Once the
    probabilities layer persists per-round Brier into the same files,
    switch this to a market-Brier key (e.g. ``win_market_brier``).
    """
    series: list[tuple[int, float]] = []
    for rnd, payload in forward_eval_by_round.items():
        score = payload.get("rmse_position_error")
        if score is None:
            continue
        try:
            series.append((int(rnd), float(score)))
        except (TypeError, ValueError):
            continue
    return series


def _split_baseline_current(
    rounds: dict[int, dict],
    feature_columns: Iterable[str],
    season: int,
) -> tuple[list[dict], list[dict], int | None]:
    """Trailing-vs-latest split for feature drift.

    Returns ``(baseline_records, current_records, last_round)``.  The
    baseline pools every classification entry from rounds prior to the
    most recent one; current = the most recent round's classification.
    """
    if not rounds:
        return [], [], None
    sorted_rounds = sorted(rounds.keys())
    last_round = sorted_rounds[-1]
    baseline_records: list[dict] = []
    for rnd in sorted_rounds[:-1]:
        baseline_records.extend(_classification_records(rounds[rnd]))
    current_records = _classification_records(rounds[last_round])
    # We don't actually use feature_columns / season here; signature kept
    # symmetric for caller composition.
    _ = (feature_columns, season)
    return baseline_records, current_records, last_round


def build_report(
    season: int,
    rounds_dir: Path = WEBSITE_ROUNDS,
    forward_eval_dir: Path = WEBSITE_FORWARD_EVAL,
    feature_columns: Iterable[str] = DEFAULT_FEATURE_COLUMNS,
    rolling_window: int = 5,
) -> ModelHealthReport:
    rounds = _load_round_jsons(rounds_dir)
    forward_eval = _load_forward_eval(forward_eval_dir)
    baseline_records, current_records, last_round = _split_baseline_current(
        rounds, feature_columns, season
    )
    brier_series = _build_brier_series(forward_eval)
    return build_health_report(
        season=season,
        last_evaluated_round=last_round,
        baseline_records=baseline_records,
        current_records=current_records,
        feature_columns=feature_columns,
        brier_by_round=brier_series,
        rolling_window=rolling_window,
    )


def report_to_jsonable(report: ModelHealthReport) -> dict:
    return {
        "season": report.season,
        "lastEvaluatedRound": report.last_evaluated_round,
        "featureDrift": [asdict(fs) for fs in report.feature_drift],
        "outputDrift": asdict(report.output_drift) if report.output_drift else None,
        "warnings": report.warnings,
        "alarms": report.alarms,
        "brierByRound": report.brier_by_round,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the model-health drift report and write to JSON."
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument(
        "--rounds-dir",
        type=Path,
        default=WEBSITE_ROUNDS,
        help="Directory of per-round JSON files (default: website/public/data/rounds).",
    )
    parser.add_argument(
        "--forward-eval-dir",
        type=Path,
        default=WEBSITE_FORWARD_EVAL,
        help="Directory of forward-eval per-round JSONs (default: "
             "website/public/data/forward_eval).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write model_health.json.",
    )
    parser.add_argument(
        "--rolling-window",
        type=int,
        default=5,
        help="Window size for the rolling-Brier trend comparison.  Default 5.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit 0 (with a message) if no rounds / no forward-eval files "
             "are present yet.  CI uses this on pre-race phases.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = build_report(
        season=args.season,
        rounds_dir=args.rounds_dir,
        forward_eval_dir=args.forward_eval_dir,
        rolling_window=args.rolling_window,
    )

    if report.last_evaluated_round is None and not report.brier_by_round:
        msg = (
            f"⚠️  Drift report: no round JSONs in {args.rounds_dir} and no "
            f"forward-eval files in {args.forward_eval_dir}; nothing to report."
        )
        print(msg)
        return 0 if args.allow_empty else 1

    output_path = (
        args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fh:
        json.dump(report_to_jsonable(report), fh, indent=2)

    if not args.quiet:
        print(f"📊 Drift report for season {args.season}")
        if report.last_evaluated_round is not None:
            print(f"  last evaluated round: R{report.last_evaluated_round:02d}")
        if report.output_drift:
            od = report.output_drift
            recent = (
                f"{od.rolling_brier_recent:.4f}" if od.rolling_brier_recent is not None else "—"
            )
            baseline = (
                f"{od.rolling_brier_baseline:.4f}" if od.rolling_brier_baseline is not None else "—"
            )
            print(
                f"  output drift: recent={recent} "
                f"baseline={baseline} severity={od.severity}"
            )
        print(f"  features tracked: {len(report.feature_drift)}")
        if report.warnings:
            print(f"  ⚠️  warnings: {len(report.warnings)}")
            for w in report.warnings:
                print(f"     - {w}")
        if report.alarms:
            print(f"  🚨 ALARMS: {len(report.alarms)}")
            for a in report.alarms:
                print(f"     - {a}")
        try:
            display_path = output_path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = output_path
        print(f"📝 Written {display_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
