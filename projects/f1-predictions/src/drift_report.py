"""CLI that builds the model-health report from round + forward-eval JSON.

Why this exists
---------------
``models/drift.py`` is the pure computational core (PSI, rolling position RMSE).
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
  each carries ``rmse_position_error`` in finishing positions. Only
  calendar-matched, settled, unheld rounds with valid grades are eligible.
* ``website/public/data/season.json`` — season and event identity.
  A hold on the latest elapsed round makes current diagnostics unavailable.

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
import math
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from models.drift import (
    ModelHealthReport,
    build_health_report,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
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
                payload = json.load(fh)
                if isinstance(payload, dict):
                    out[rnd] = payload
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
                payload = json.load(fh)
                if isinstance(payload, dict):
                    out[rnd] = payload
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _build_rmse_series(
    forward_eval_by_round: dict[int, dict],
) -> list[tuple[int, float]]:
    """Extract finite, nonnegative position RMSE, measured in positions."""
    series: list[tuple[int, float]] = []
    for rnd, payload in forward_eval_by_round.items():
        score = payload.get("rmse_position_error")
        if score is None:
            continue
        try:
            value = float(score)
            if not isinstance(score, bool) and math.isfinite(value) and value >= 0:
                series.append((int(rnd), value))
        except (TypeError, ValueError):
            continue
    return sorted(series)


def _valid_event_identity(identity: dict | None, rnd: int) -> bool:
    """Require canonical identity values before comparing calendar and snapshot."""
    return bool(
        isinstance(identity, dict)
        and type(identity.get("round")) is int
        and identity["round"] == rnd
        and rnd > 0
        and all(isinstance(identity.get(field), str) and identity[field].strip()
                for field in ("name", "gpKey", "circuit", "date"))
    )


def _eligible_rounds(rounds: dict[int, dict], forward_eval: dict[int, dict],
                     season_data: dict, season: int, today: date):
    """Fail closed on calendar identity, settlement and publication eligibility.

    Existing forward-eval files alone cannot establish eligibility. Held rounds
    may retain classifications or stale grades; future previews are never graded.
    """
    entries = season_data.get("calendar")
    calendar = {}
    if isinstance(entries, list):
        for event in entries:
            if isinstance(event, dict) and type(event.get("round")) is int:
                if event["round"] in calendar:
                    calendar = {}
                    break
                calendar[event["round"]] = event
    eligible, observed, excluded = {}, {}, []
    for rnd, state in sorted(rounds.items()):
        event = calendar.get(rnd)
        reason = None
        try:
            event_date = date.fromisoformat(event["date"]) if event else None
        except (KeyError, TypeError, ValueError):
            event_date = None
        # A hold still applies when the held snapshot itself has wrong event
        # metadata. Determine the elapsed slot from the calendar independently.
        if event_date is not None and event_date <= today:
            observed[rnd] = state
        if (type(season_data.get("season")) is not int
                or season_data["season"] != season or season <= 0
                or not _valid_event_identity(event, rnd)
                or not _valid_event_identity(state, rnd)
                or any(state.get(k) != event.get(k)
                       for k in ("round", "name", "gpKey", "circuit", "date"))):
            reason = "event_mismatch"
        else:
            if event_date is None or event_date.isoformat() != event["date"]:
                reason = "invalid_date"
            elif event_date > today:
                reason = "future_round"
            else:
                observed[rnd] = state
                grade = forward_eval.get(rnd, {})
                if state.get("publicationHold") is not None:
                    reason = "publication_hold"
                elif not state.get("actualResults"):
                    reason = "unsettled_round"
                elif not state.get("classification"):
                    reason = "no_forecast"
                elif not _grade_matches(state, grade, season, rnd):
                    reason = "no_valid_grade"
        if reason:
            excluded.append({"round": rnd, "reason": reason})
        else:
            eligible[rnd] = state
    return eligible, observed, excluded


def _grade_matches(state: dict, grade: dict, season: int, rnd: int) -> bool:
    """Reject stale grades by checking their RMSE against the unchanged inputs."""
    records, actual = state.get("classification"), state.get("actualResults")
    if (not isinstance(records, list) or not isinstance(actual, dict)
            or grade.get("season") != season or grade.get("round") != rnd
            or type(grade.get("drivers_compared")) is not int
            or not _build_rmse_series({rnd: grade})):
        return False
    predicted = {}
    for row in records:
        if (not isinstance(row, dict) or not isinstance(row.get("driver"), str)
                or row["driver"] in predicted or not _valid_position(row.get("position"))):
            return False
        predicted[row["driver"]] = row["position"]
    if any(not isinstance(driver, str) or not _valid_position(pos)
           for driver, pos in actual.items()):
        return False
    common = predicted.keys() & actual.keys()
    if not common or grade["drivers_compared"] != len(common):
        return False
    rmse = math.sqrt(sum((predicted[d] - actual[d]) ** 2 for d in common) / len(common))
    return math.isclose(float(grade["rmse_position_error"]), rmse, rel_tol=1e-6, abs_tol=1e-6)


def _valid_position(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 1


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
    season_file: Path | None = None,
    today: date | None = None,
) -> ModelHealthReport:
    rounds = _load_round_jsons(rounds_dir)
    forward_eval = _load_forward_eval(forward_eval_dir)
    try:
        season_data = json.loads((season_file or rounds_dir.parent / "season.json").read_text())
    except (OSError, json.JSONDecodeError):
        season_data = {}
    if not isinstance(season_data, dict):
        season_data = {}
    eligible, observed, excluded = _eligible_rounds(
        rounds, forward_eval, season_data, season, today or datetime.now(timezone.utc).date()
    )
    latest_observed = max(observed, default=None)
    if latest_observed is not None and observed[latest_observed].get("publicationHold") is not None:
        return ModelHealthReport(
            season=season, last_evaluated_round=None, diagnostic_status="publication_hold",
            unavailable_reason="The latest elapsed round's model forecast is withheld; current forecast diagnostics are unavailable.",
            last_observed_round=latest_observed, excluded_rounds=excluded,
        )
    if not eligible:
        return ModelHealthReport(
            season=season, last_evaluated_round=None, diagnostic_status="no_eligible_rounds",
            unavailable_reason="No eligible settled model forecasts with valid position grades are available.",
            last_observed_round=latest_observed, excluded_rounds=excluded,
        )
    baseline_records, current_records, last_round = _split_baseline_current(
        eligible, feature_columns, season
    )
    rmse_series = _build_rmse_series({r: forward_eval[r] for r in eligible})
    report = build_health_report(
        season=season,
        last_evaluated_round=last_round,
        baseline_records=baseline_records,
        current_records=current_records,
        feature_columns=feature_columns,
        rmse_by_round=rmse_series,
        rolling_window=rolling_window,
    )
    report.last_observed_round = latest_observed
    report.excluded_rounds = excluded
    return report


def report_to_jsonable(report: ModelHealthReport) -> dict:
    return {
        "season": report.season,
        "lastEvaluatedRound": report.last_evaluated_round,
        "featureDrift": [asdict(fs) for fs in report.feature_drift],
        "outputDrift": asdict(report.output_drift) if report.output_drift else None,
        "warnings": report.warnings,
        "alarms": report.alarms,
        "outputMetric": "rmse_position_error",
        "outputUnit": "positions",
        "rmseByRound": report.rmse_by_round,
        "diagnosticStatus": report.diagnostic_status,
        "unavailableReason": report.unavailable_reason,
        "lastObservedRound": report.last_observed_round,
        "excludedRounds": report.excluded_rounds,
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
        help="Window size for the rolling position-RMSE trend comparison.  Default 5.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit 0 (with a message) if no eligible settled rounds "
             "are present yet.  CI uses this on pre-race phases.",
    )
    parser.add_argument("--season-file", type=Path, help="Season/calendar JSON (default: rounds-dir/../season.json).")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = build_report(
        season=args.season,
        rounds_dir=args.rounds_dir,
        forward_eval_dir=args.forward_eval_dir,
        rolling_window=args.rolling_window,
        season_file=args.season_file,
    )

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
                f"{od.rolling_rmse_recent:.4f}" if od.rolling_rmse_recent is not None else "—"
            )
            baseline = (
                f"{od.rolling_rmse_baseline:.4f}" if od.rolling_rmse_baseline is not None else "—"
            )
            print(
                f"  output drift: recent={recent} "
                f"baseline={baseline} severity={od.severity}"
            )
        if report.unavailable_reason:
            print(f"  unavailable: {report.unavailable_reason}")
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
    if report.diagnostic_status == "no_eligible_rounds" and not args.allow_empty:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
