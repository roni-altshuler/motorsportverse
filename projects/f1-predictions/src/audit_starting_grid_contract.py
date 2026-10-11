"""Offline final-grid contract/coverage audit, never a prediction exporter.

Uses flat, synthetic lap-time outputs to isolate the grid prior on committed
qualifying data. Reports no accuracy, probability or forward forecast claim.
No provider request, model fitting, registry access or forecast write occurs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["F1_REGISTRY_ENABLED"] = "0"

import pandas as pd

from f1_prediction_utils import _parse_laptime_to_seconds, apply_qualifying_data, apply_race_postprocessing
from models.race_simulator_runner import _build_grid_and_initials
from models.starting_grid import StartingGridEvent, StartingGridSnapshot, StartingGridUnavailable


def _read(path: Path):
    return json.loads(path.read_text())


def completed_grid_coverage(data_dir: Path, season: int) -> list[dict]:
    """Inspect completed rounds in temporal order; never invent a missing grid.

    The outcome file supplies only completed round IDs, not model inputs.
    Existing snapshots lack independently pinned historical final-grid contexts.
    """
    completed = _read(data_dir / f"season_results_{season}.json")
    rows = []
    for round_num in sorted(map(int, completed)):
        path = data_dir / "rounds" / f"round_{round_num:02d}.json"
        payload = _read(path) if path.exists() else {}
        grids = [s for s in (payload.get("weekendResults") or {}).get("sessions", [])
                 if s.get("key") == "startingGrid"]
        rows.append({"round": round_num, "date": payload.get("date"),
                     "finalGridSessionPresent": bool(grids),
                     "temporalEvaluationEligible": False,
                     "reason": "missing-published-round" if not path.exists() else "missing-final-grid" if not grids
                     else "historical-pre-race-context-not-supplied"})
    return rows


def _controlled_frame(payload: dict, event: StartingGridEvent) -> pd.DataFrame:
    sessions = (payload.get("weekendResults") or {}).get("sessions", [])
    qualifying = [s for s in sessions if s.get("key") == "qualifying"]
    expected_url = event.source_url.rsplit("/", 1)[0] + "/qualifying"
    if len(qualifying) != 1 or qualifying[0].get("status") != "official" or qualifying[0].get("sourceUrl") != expected_url:
        raise StartingGridUnavailable("unverified-qualifying-source")
    rows = qualifying[0]["rows"]
    base = pd.DataFrame({"Driver": [r["driver"] for r in rows], "Team": [r["team"] for r in rows],
                         "CleanAirPace": 99.0, "WetPerformance": 1.0})
    times = {r["driver"]: _parse_laptime_to_seconds(r.get("time")) for r in rows}
    frame = apply_qualifying_data(base, times, grid_positions={r["driver"]: r["position"] for r in rows})
    # Controlled constants, deliberately not fitted/champion model predictions.
    for col, value in {"PredictedLapTime": 95.0, "PredictedLapTime_GB": 95.0,
                       "PredictedLapTime_XGB": 95.0, "CurrentForm": 0.0, "SkillPrior": 10.0,
                       "PositionTrend": 0.0, "ConsistencyScore": 0.1, "PitTimeLoss": 22.0,
                       "TyreDegFactor": 0.5, "SeasonMomentum": 0.0}.items():
        frame[col] = value
    return frame


def build_report(data_dir: Path, *, season: int, round_num: int, source_url: str,
                 race_start_utc: str, input_cutoff: str) -> dict:
    season_data = _read(data_dir / "season.json")
    if season_data["season"] != season:
        raise StartingGridUnavailable("published-season-mismatch")
    calendar = {r["round"]: {"gp_key": r["gpKey"], "name": r["name"], "circuit": r["circuit"],
                            "date": r["date"], "circuit_id": r.get("circuitId"),
                            "race_start_utc": r.get("raceStartUtc")} for r in season_data["calendar"]}
    event = StartingGridEvent.from_calendar(season, round_num, calendar,
                                           source_url=source_url, race_start_utc=race_start_utc)
    path = data_dir / "rounds" / f"round_{round_num:02d}.json"
    source = path.read_bytes(); payload = json.loads(source)
    frame = _controlled_frame(payload, event)
    grid = StartingGridSnapshot.from_published(payload, event=event, expected_drivers=frame["Driver"],
                                               input_cutoff=input_cutoff)
    legacy = apply_race_postprocessing(frame, circuit_key=event.gp_key)
    shadow = apply_race_postprocessing(frame, circuit_key=event.gp_key, shadow_starting_grid=grid,
                                       shadow_event=event, shadow_input_cutoff=input_cutoff)
    pd.testing.assert_frame_equal(legacy[frame.columns], shadow[frame.columns])
    sim_grid, _ = _build_grid_and_initials(shadow, shadow_starting_grid=grid)
    final_positions = {r.driver: r.grid_position for r in sim_grid}
    diagnostics = []
    for driver, final in grid.positions:
        old = legacy.set_index("Driver").loc[driver]; new = shadow.set_index("Driver").loc[driver]
        if int(old["QualifyingRank"]) != final:
            diagnostics.append({"driver": driver, "qualifyingRank": int(old["QualifyingRank"]),
                                "startingGridPosition": final, "simulatorInitialPosition": final_positions[driver],
                                "gridPriorScoreDelta": float(new["RaceProjectionScore"] - old["RaceProjectionScore"])})
    coverage = completed_grid_coverage(data_dir, season)
    return {"generatedAt": datetime.now(timezone.utc).isoformat(),
            "mode": "offline-shadow-contract-diagnostic", "newForecastGenerated": False,
            "controlledModelOutputs": "flat synthetic lap times; not champion inference",
            "sourceRoundSha256": hashlib.sha256(source).hexdigest(), "provenance": grid.provenance(),
            "qualifyingAndExistingFeatureColumnsUnchanged": True,
            "penaltyInputDiagnostics": diagnostics,
            "completedRoundCount": len(coverage),
            "completedRoundsWithFinalGridSession": sum(r["finalGridSessionPresent"] for r in coverage),
            "eligibleTemporalEvaluationRounds": sum(r["temporalEvaluationEligible"] for r in coverage),
            "temporalCoverage": coverage,
            "predictionAccuracyEvaluated": False,
            "regressionAssessment": "Unavailable: no eligible historical final-grid contexts; no promotion claim.",
            "servingWrites": False, "trainingRan": False, "modelPromotion": False, "publicationHoldReleased": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--round", dest="round_num", type=int, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--race-start-utc", required=True)
    parser.add_argument("--input-cutoff", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(PROJECT_ROOT) and not output.is_relative_to(PROJECT_ROOT / "docs" / "qa"):
        parser.error("output must be an external diagnostic file or under docs/qa; never published/model state")
    try:
        report = build_report(PROJECT_ROOT / "website/public/data", season=args.season,
                              round_num=args.round_num, source_url=args.source_url,
                              race_start_utc=args.race_start_utc, input_cutoff=args.input_cutoff)
    except StartingGridUnavailable as exc:
        parser.error(f"official-grid shadow unavailable: {exc.reason}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Contract diagnostic saved to {output}; no forecast or model state written.")


if __name__ == "__main__":
    main()
