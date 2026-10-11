"""Offline, event-grouped Ridge shadow. Never writes serving or feature state.

Historical qualifying/grid tables are reconstructed inputs, not immutable
pre-race publications. Weather and sprint-result features are deliberately
omitted because their historical availability times are not recorded.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from event_identity import published_matches
from export_circuit_history import SEASON_CALENDARS
from leakage import assert_seasons_prior_only

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
ALPHA = 10.0  # fixed before evaluation; no tuning on the scored events
GRID_FEATURES = ["grid_fraction"]
WEEKEND_FEATURES = ["grid_fraction", "quali_fraction", "quali_gap", "penalty_delta"]
HISTORY_FEATURES = WEEKEND_FEATURES + [
    "driver_recent_mean", "driver_recent_n", "driver_track_mean", "driver_track_n",
    "team_recent_mean", "team_recent_n",
]
VARIANTS = {"ridge_grid": GRID_FEATURES, "ridge_quali_grid": WEEKEND_FEATURES,
            "ridge_history": HISTORY_FEATURES}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def lap_seconds(value: object) -> float | None:
    try:
        parts = [float(p) for p in str(value).split(":")]
        if len(parts) not in (2, 3):
            return None
        seconds = sum(v * 60 ** (len(parts) - i - 1) for i, v in enumerate(parts))
        return seconds if math.isfinite(seconds) and seconds > 0 else None
    except (TypeError, ValueError):
        return None


def _venue(gp_key: str, season: int, rnd: int) -> str:
    # Relocation must never borrow Bahrain/Sakhir history for Sepang.
    return "Sepang" if season == 2026 and rnd == 16 else gp_key


def load_inputs(root: Path = PROJECT_ROOT) -> tuple[list[dict], pd.DataFrame, dict]:
    """Read committed facts only; exclude predicted DB rows from actual history."""
    data = root / "website/public/data"
    season_bytes = (data / "season.json").read_bytes()
    season = json.loads(season_bytes)
    year = int(season["season"])
    calendar = {int(e["round"]): {"name": e["name"], "gp_key": e["gpKey"],
                "date": e["date"], "circuit": e["circuit"], "raceStartUtc": e.get("raceStartUtc")} for e in season["calendar"]}
    db_path = root / "data/history.duckdb"
    db_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()
    sources = [{"path": "website/public/data/season.json", "sha256": hashlib.sha256(season_bytes).hexdigest()},
               {"path": "data/history.duckdb", "sha256": db_sha}]
    with duckdb.connect(str(root / "data/history.duckdb"), read_only=True) as db:
        historical = db.execute(
            "SELECT season, round, driver, actual_position, source FROM historical_predictions "
            "WHERE season BETWEEN 2022 AND ? AND actual_position > 0 ORDER BY season, round, driver",
            [year - 1],
        ).fetchdf()
    if hashlib.sha256(db_path.read_bytes()).hexdigest() != db_sha:
        raise ValueError("historical database changed during the read-only snapshot")
    history = []
    for (s, r), group in historical.groupby(["season", "round"], sort=True):
        venue = SEASON_CALENDARS.get(int(s), {}).get(int(r))
        if venue is None:
            raise ValueError(f"unmapped historical event {s}/{r}")
        if group["actual_position"].duplicated().any():
            raise ValueError(f"duplicate actual position in historical event {s}/{r}")
        classification_size = int(group["actual_position"].max())
        for row in group.to_dict("records"):
            history.append({"season": int(s), "round": int(r), "driver": row["driver"],
                            "venue": venue, "team": None,
                            "finish_fraction": row["actual_position"] / classification_size})
    events, coverage = [], []
    for rnd, info in sorted(calendar.items()):
        path = data / f"rounds/round_{rnd:02d}.json"
        if not path.exists():
            coverage.append({"round": rnd, "eligible": False, "reason": "no snapshot"})
            continue
        raw = path.read_bytes()
        sources.append({"path": str(path.relative_to(root)), "sha256": hashlib.sha256(raw).hexdigest()})
        state = json.loads(raw)
        if not published_matches(state, rnd, calendar):
            coverage.append({"round": rnd, "eligible": False, "reason": "event identity mismatch"})
            continue
        sessions = {s["key"]: s for s in state.get("weekendResults", {}).get("sessions", [])}
        q_session = sessions.get("qualifying", {})
        q_rows = q_session.get("rows", []) if q_session.get("status") == "official" else []
        race_rows = sessions.get("grandPrix", {}).get("rows", [])
        actuals = state.get("actualResults") or {}
        venue = _venue(info["gp_key"], year, rnd)
        if actuals:
            n = max(int(v) for v in actuals.values())
            teams = {row["driver"]: row.get("team") for row in race_rows}
            for driver, position in actuals.items():
                history.append({"season": year, "round": rnd, "driver": driver,
                                "venue": venue, "team": teams.get(driver),
                                "finish_fraction": int(position) / n})
        grid_session = sessions.get("startingGrid", {})
        if grid_session.get("status") == "official":
            grid_rows, grid_key, origin = grid_session.get("rows", []), "position", "official starting-grid table"
        else:
            grid_rows, grid_key, origin = race_rows, "grid", "reconstructed from race-result grid field"
        grid = {row["driver"]: row.get(grid_key) for row in grid_rows if row.get(grid_key) is not None}
        q = {row["driver"]: row for row in q_rows}
        eligible = bool(q and len(q) == len(q_rows) == len(grid_rows) == len(grid)
                        and set(q) == set(grid)
                        and sorted(grid.values()) == list(range(1, len(grid) + 1)))
        record = {"round": rnd, "qualifyingRows": len(q_rows), "knownGridRows": len(grid),
                  "actualRows": len(actuals), "eligible": eligible,
                  "gridOrigin": origin, "immutableHistoricalCutoffEstablished": False,
                  "storedForecastGeneratedAt": state.get("generatedAt"),
                  "qualifyingSourceCheckedAt": q_session.get("verifiedAt") or q_session.get("fetchedAt"),
                  "gridSourceCheckedAt": grid_session.get("verifiedAt") or grid_session.get("fetchedAt"),
                  "qualifyingSourceUrl": q_session.get("sourceUrl"), "gridSourceUrl": grid_session.get("sourceUrl")}
        coverage.append(record)
        if not eligible:
            record["reason"] = "incomplete qualifying field or final grid; no grid inferred from qualifying"
            continue
        best = {}
        for driver, row in q.items():
            values = [lap_seconds(row.get(k)) for k in ("q3", "q2", "q1")]
            values = [v for v in values if v is not None]
            best[driver] = min(values) if values else lap_seconds(row.get("time"))
        timed = [v for v in best.values() if v is not None]
        if not timed:
            record.update(eligible=False, reason="no qualifying times")
            continue
        n = len(q)
        stored = {row["driver"]: row["position"] for row in state.get("classification", [])}
        rows = [{"season": year, "round": rnd, "driver": driver, "team": row.get("team"),
                 "venue": venue, "field_size": n, "grid_fraction": grid[driver] / n,
                 "quali_fraction": row["position"] / n,
                 "quali_gap": (best[driver] / min(timed) - 1) if best[driver] is not None else np.nan,
                 "penalty_delta": (grid[driver] - row["position"]) / n,
                 "actual_position": actuals.get(driver), "stored_position": stored.get(driver)}
                for driver, row in sorted(q.items())]
        labelled = bool(set(actuals) == set(q) and sorted(actuals.values()) == list(range(1, n + 1)))
        events.append({"season": year, "round": rnd, "name": info["name"], "date": info["date"],
                       "raceStartUtc": info["raceStartUtc"], "rows": rows, "labelled": labelled, "coverage": record})
    audit = {
        "season": year, "historicalActualRows": len(historical),
        "sourceCommit": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
        "historicalEvents": int(historical.groupby(["season", "round"]).ngroups),
        "historicalDbColumns": ["season", "round", "driver", "actual_position", "source"],
        "historyPolicy": "actual rows only; known-classification normalization; historical team unknown and unused",
        "rounds": coverage,
        "trainingEligibleRounds": [e["round"] for e in events if e["labelled"]],
        "omitted": {"weather": "no historical forecast issue/availability timestamps; no observed race weather used",
                    "sprintResults": "no historical source availability timestamps; today's sprint is not a trained feature",
                    "dnf": "historical DB has no status; finishing last is not inferred to be a DNF",
                    "historicalTeam": "DB has no team; no current team is assigned backwards",
                    "historicalQualifyingOrGrid": "DB predicted positions/lap times are neither qualifying nor final grid"},
        "sources": sources,
    }
    return events, pd.DataFrame(history), audit


def features_for_event(event: dict, history: pd.DataFrame) -> pd.DataFrame:
    target = (event["season"], event["round"])
    prior = history[(history.season < target[0]) | ((history.season == target[0]) & (history["round"] < target[1]))]
    prior = prior.sort_values(["season", "round", "driver"])
    assert_seasons_prior_only(prior.to_dict("records"), *target, label="ridge feature history")
    rows = []
    for raw in event["rows"]:
        row = dict(raw)
        driver = prior[prior.driver == row["driver"]]
        recent = driver.tail(5)
        track = driver[driver.venue == row["venue"]].tail(3)
        team = prior[prior.team.notna() & (prior.team == row["team"])]
        team_races = team.groupby(["season", "round"])["finish_fraction"].mean().tail(3)
        row.update(driver_recent_mean=float(recent.finish_fraction.mean()), driver_recent_n=len(recent),
                   driver_track_mean=float(track.finish_fraction.mean()), driver_track_n=len(track),
                   team_recent_mean=float(team_races.mean()), team_recent_n=len(team_races))
        rows.append(row)
    return pd.DataFrame(rows)


def fit_fold(train: pd.DataFrame, columns: list[str]) -> Pipeline:
    """All missing-value encoding and scaling are fitted on training events only."""
    model = make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                          StandardScaler(), Ridge(alpha=ALPHA, solver="svd"))
    model.fit(train[columns], train.actual_position / train.field_size)
    return model


def rank_scores(drivers: list[str], scores: list[float] | np.ndarray) -> dict[str, int]:
    return {driver: i for i, (driver, _) in enumerate(sorted(zip(drivers, scores), key=lambda p: (p[1], p[0])), 1)}


def score(actual: dict[str, int], predicted: dict[str, int]) -> dict:
    if set(actual) != set(predicted):
        return {"available": False, "reason": "not the same complete driver field"}
    drivers = sorted(actual)
    a, p = np.array([actual[d] for d in drivers]), np.array([predicted[d] for d in drivers])
    return {"available": True, "drivers": len(drivers), "mae": float(np.abs(a - p).mean()),
            "rmse": float(np.sqrt(np.mean((a - p) ** 2))), "spearman": float(spearmanr(a, p).statistic),
            "winnerHit": int(any(actual[d] == predicted[d] == 1 for d in drivers)),
            "podiumHits": sum(actual[d] <= 3 and predicted[d] <= 3 for d in drivers)}


def evaluate(events: list[dict], history: pd.DataFrame, min_train_events: int = 5) -> dict:
    labelled = sorted((e for e in events if e["labelled"]), key=lambda e: (e["season"], e["round"]))
    frames = {(e["season"], e["round"]): features_for_event(e, history) for e in labelled}
    results = []
    for event in labelled:
        key = (event["season"], event["round"])
        train_keys = sorted(k for k in frames if k < key)
        if len(train_keys) < min_train_events:
            continue
        train = pd.concat([frames[k] for k in train_keys], ignore_index=True)
        assert_seasons_prior_only(train.to_dict("records"), *key, label="ridge training events")
        target = frames[key]
        actual = dict(zip(target.driver, target.actual_position.astype(int)))
        metrics = {}
        for name, columns in VARIANTS.items():
            model = fit_fold(train, columns)
            predicted = rank_scores(list(target.driver), model.predict(target[columns]))
            metrics[name] = score(actual, predicted)
        for name, column in (("final_grid", "grid_fraction"), ("qualifying_order", "quali_fraction"), ("stored_model", "stored_position")):
            metrics[name] = score(actual, rank_scores(list(target.driver), target[column].to_numpy())) if target[column].notna().all() else {"available": False}
        results.append({"season": key[0], "round": key[1], "name": event["name"],
                        "trainEvents": [list(k) for k in train_keys], "trainRows": len(train), "metrics": metrics})
    summary = {}
    for name in [*VARIANTS, "final_grid", "qualifying_order", "stored_model"]:
        available = [r["metrics"][name] for r in results if r["metrics"][name].get("available")]
        summary[name] = {"events": len(available), "drivers": sum(m["drivers"] for m in available),
                         **({metric: float(np.mean([m[metric] for m in available])) for metric in ("mae", "rmse", "spearman", "podiumHits")} if available else {}),
                         "winnerHits": sum(m["winnerHit"] for m in available)}
    return {"label": "retrospective chronological shadow backtest", "alpha": ALPHA,
            "minTrainEvents": min_train_events, "foldPolicy": "expanding earlier events only; all drivers of an event held out together",
            "featureMissingness": "training-fold median encoding with explicit missingness indicators; no factual field is filled",
            "variants": VARIANTS, "rounds": results, "summary": summary,
            "storedModelLimitation": "stored forecasts include retrospective regenerations; immutable pre-race input cutoffs are not established",
            "promotion": {"promote": False,
                          "historyDeltaMAEVsGrid": summary["ridge_history"].get("mae", 0) - summary["final_grid"].get("mae", 0),
                          "historyDeltaMAEVsStored": summary["ridge_history"].get("mae", 0) - summary["stored_model"].get("mae", 0),
                          "reasons": ["shadow only", "small reconstructed-input event cohort", "no immutable historical input-availability record",
                                      "history challenger must not be promoted when its shared-cohort MAE regresses"]}}


def candidate(event: dict, events: list[dict], history: pd.DataFrame, audit: dict, *, now: datetime) -> dict:
    """An immutable shadow candidate, without probabilities or publication side effects."""
    key = (event["season"], event["round"])
    if event["coverage"]["actualRows"] or any(row.get("actual_position") is not None for row in event["rows"]):
        raise ValueError("candidate event has an outcome; refuse hindsight forecast")
    start = datetime.fromisoformat(str(event.get("raceStartUtc")).replace("Z", "+00:00"))
    if now.tzinfo is None or now >= start:
        raise ValueError("candidate must be generated before verified race start")
    for field in ("qualifyingSourceCheckedAt", "gridSourceCheckedAt"):
        checked = datetime.fromisoformat(str(event["coverage"][field]).replace("Z", "+00:00"))
        if checked.tzinfo is None or checked > now:
            raise ValueError("candidate requires verified source timestamps before its cutoff")
    q_url, g_url = event["coverage"]["qualifyingSourceUrl"], event["coverage"]["gridSourceUrl"]
    prefix = f"https://www.formula1.com/en/results/{key[0]}/races/"
    if (not q_url.startswith(prefix) or not q_url.endswith("/qualifying")
            or not g_url.endswith("/starting-grid")
            or q_url.removesuffix("/qualifying") != g_url.removesuffix("/starting-grid")):
        raise ValueError("candidate requires matching verified official qualifying and post-penalty grid sources")
    earlier = [e for e in events if e["labelled"] and (e["season"], e["round"]) < key]
    train = pd.concat([features_for_event(e, history) for e in earlier], ignore_index=True)
    assert_seasons_prior_only(train.to_dict("records"), *key, label="candidate training")
    target = features_for_event(event, history)
    model = fit_fold(train, HISTORY_FEATURES)
    scores = model.predict(target[HISTORY_FEATURES])
    finished = datetime.now(timezone.utc)
    if finished >= start or finished < now:
        raise ValueError("candidate generation finished outside the pre-race input window")
    ranks = rank_scores(list(target.driver), scores)
    imputer, scaler, ridge = model.steps[0][1], model.steps[1][1], model.steps[2][1]
    model_state = {"alpha": ALPHA, "features": HISTORY_FEATURES,
                   "imputerStatistics": imputer.statistics_.tolist(), "missingIndicators": imputer.indicator_.features_.tolist(),
                   "scalerMean": scaler.mean_.tolist(), "scalerScale": scaler.scale_.tolist(),
                   "coefficients": ridge.coef_.tolist(), "intercept": float(ridge.intercept_),
                   "trainedEvents": [[e["season"], e["round"]] for e in earlier]}
    range_warnings = []
    for column in HISTORY_FEATURES:
        low, high = train[column].min(), train[column].max()
        for driver, value in zip(target.driver, target[column]):
            if pd.notna(value) and pd.notna(low) and (value < low or value > high):
                range_warnings.append({"driver": driver, "feature": column, "value": float(value),
                                       "trainMin": float(low), "trainMax": float(high)})
    return {"status": "shadow_only", "season": key[0], "round": key[1], "name": event["name"],
            "generatedAt": finished.isoformat().replace("+00:00", "Z"), "inputCutoff": now.isoformat().replace("+00:00", "Z"),
            "sourceCommit": audit["sourceCommit"],
            "sourceObservedAt": event["coverage"], "sourceSnapshotSha256": digest(audit["sources"]),
            "codeSha256": CODE_SHA256,
            "modelSha256": digest(model_state), "modelState": model_state,
            "classification": [{"driver": d, "position": ranks[d], "score": float(s),
                                "officialGridPosition": int(round(g * len(target))),
                                "qualifyingPosition": int(round(q * len(target)))}
                               for d, s, g, q in zip(target.driver, scores, target.grid_fraction, target.quali_fraction)],
            "inputRangeWarnings": range_warnings, "scoreKind": "unbounded regressed finishing fraction; ranking score, not probability",
            "probabilities": None, "publicationHoldReleased": False,
            "limitation": "experimental shadow; historical weather/sprint availability absent; no accuracy or live publication claim"}


def write_artifact(path: Path, value: dict, root: Path = PROJECT_ROOT) -> None:
    if not path.resolve().is_relative_to((root / "reports/ridge-shadow").resolve()):
        raise ValueError("shadow artifacts must stay in reports/ridge-shadow; serving/feature state is forbidden")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != CODE_SHA256:
        raise ValueError("model implementation changed during generation")
    encoded = json.dumps(value, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(encoded)
            file.flush()
            os.fsync(file.fileno())
        os.link(temporary, path)  # complete content, atomic create, never overwrite
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports/ridge-shadow")
    parser.add_argument("--candidate-round", type=int)
    args = parser.parse_args()
    start = time.perf_counter()
    events, history, audit = load_inputs()
    report = evaluate(events, history)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    report.update(runtimeSeconds=time.perf_counter() - start, coverage=audit,
                  codeSha256=CODE_SHA256)
    write_artifact(args.output_dir / f"evaluation_{stamp}.json", report)
    if args.candidate_round:
        event = next(e for e in events if e["round"] == args.candidate_round)
        if event["labelled"]:
            raise ValueError("candidate event already has an outcome; refuse hindsight forecast")
        value = candidate(event, events, history, audit, now=now)
        write_artifact(args.output_dir / f"candidate_{stamp}_{value['modelSha256'][:12]}.json", value)
    print(json.dumps({"eligibleRounds": audit["trainingEligibleRounds"], "summary": report["summary"],
                      "runtimeSeconds": report["runtimeSeconds"], "outputDir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
