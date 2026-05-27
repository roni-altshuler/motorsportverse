"""Export per-round market probabilities to `website/public/data/probabilities/`.

Reads each `website/public/data/rounds/round_*.json` for predicted lap times,
runs the Plackett-Luce → Monte Carlo pipeline from `models.calibration`, fits
the isotonic `ProbabilityCalibrator` on whatever historical (predicted,
observed) pairs are recoverable from `season_results_2026.json`, and writes
both the per-round market JSON and a `calibration_summary.json`.

Data limitation (May 2026): only Round 4 has actual results, and we have no
multi-season historical predictions in-repo, so calibration training is
effectively empty.  The exporter writes `calibration.applied = false` in that
case — the honest answer.  Once a multi-season backfill lands (Tier 1 of the
audit), this script picks it up with no code changes.

CLI::

    python export_probabilities.py                  # all rounds
    python export_probabilities.py --rounds 1,2,3   # subset
    python export_probabilities.py --dry-run        # don't write files
    python export_probabilities.py --history-db data/history.duckdb
                                                    # use backfilled DB

When ``data/history.duckdb`` exists (built by ``backfill_history.py``), its
historical (predicted_position, actual_position) records are appended to the
calibrator's training set.  Each row contributes 4 records (one per market),
and distinct (season, round) tuples count toward ``--min-completed-rounds``
so a 30-round 2023+2024+2025 backfill trivially trips the default gate of 3.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
from pathlib import Path
from typing import Iterable

from models.calibration import (
    DEFAULT_N_SAMPLES,
    DEFAULT_TEMPERATURE,
    MARKETS,
    MarketProbabilities,
    ProbabilityCalibrator,
    brier_score,
    calibrate_market_probabilities,
    collect_history_from_rounds,
    log_loss,
    plackett_luce_probabilities,
    reliability_diagram,
)
from models.registry import ModelRegistry, registry_enabled

PROJECT_ROOT = Path(__file__).resolve().parent
ROUNDS_DIR = PROJECT_ROOT / "website" / "public" / "data" / "rounds"
PROBS_DIR = PROJECT_ROOT / "website" / "public" / "data" / "probabilities"
SEASON_RESULTS_PATH = PROJECT_ROOT / "season_results_2026.json"
DEFAULT_HISTORY_DB = PROJECT_ROOT / "data" / "history.duckdb"

ROUND_FILE_RE = re.compile(r"round_(\d+)\.json$")

# Hand-set "training seasons" — when proper multi-season history exists this
# list will be the seasons actually used.  Currently empty because we have no
# cross-season calibration data.
TRAINING_SEASONS: list[int] = []

DATA_LIMITATION_NOTE = (
    "Only Round 4 of 2026 has actual results; no multi-season historical "
    "(predicted, observed) pairs are available in-repo. Isotonic calibration "
    "requires materially more data (target: 2023+2024+2025 backfilled) before "
    "calibration.applied can be set to true. Until then, exported probabilities "
    "are raw Plackett-Luce Monte Carlo outputs."
)


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #


def _list_round_files(rounds: Iterable[int] | None = None) -> list[Path]:
    if not ROUNDS_DIR.exists():
        return []
    files: list[Path] = []
    for p in sorted(ROUNDS_DIR.glob("round_*.json")):
        m = ROUND_FILE_RE.search(p.name)
        if not m:
            continue
        rnd = int(m.group(1))
        if rounds is not None and rnd not in rounds:
            continue
        files.append(p)
    return files


def _round_number(path: Path) -> int:
    m = ROUND_FILE_RE.search(path.name)
    if not m:
        raise ValueError(f"Path {path} doesn't match round_NN.json")
    return int(m.group(1))


def _load_lap_times(round_path: Path) -> tuple[dict, dict[str, float]]:
    with round_path.open() as f:
        data = json.load(f)
    lap_times: dict[str, float] = {}
    for entry in data.get("classification", []):
        driver = entry.get("driver")
        pred = entry.get("predictedTime")
        if not driver or pred is None:
            continue
        try:
            lap_times[str(driver)] = float(pred)
        except (TypeError, ValueError):
            continue
    return data, lap_times


def _load_history_from_db(db_path: Path) -> tuple[list[dict], int]:
    """Read calibration training records from the historical-backfill DB.

    Returns
    -------
    (records, n_distinct_rounds)
        ``records`` is the flat list expected by
        ``ProbabilityCalibrator.fit_from_history`` — each dict carries
        ``market``, ``predicted`` (in [0, 1]), ``observed`` (0/1).
        ``n_distinct_rounds`` is the number of distinct (season, round) tuples
        the records came from; we surface it so the run-level gate
        (``min_completed_rounds``) honours the multi-season backfill as well
        as the in-repo 2026 results.

    Silently returns ``([], 0)`` if the DB doesn't exist.  The import is
    lazy because duckdb is in `requirements-dev.txt`, not `requirements.txt` —
    we don't want website-only consumers of this module to pay the import cost
    when there's no DB present.
    """
    if not db_path.exists():
        return [], 0
    try:
        from backfill_history import count_distinct_rounds, load_history_records
    except ImportError:
        return [], 0
    records = load_history_records(db_path)
    n_rounds = count_distinct_rounds(db_path)
    return records, n_rounds


def _load_actuals() -> dict[int, dict[str, int]]:
    if not SEASON_RESULTS_PATH.exists():
        return {}
    with SEASON_RESULTS_PATH.open() as f:
        raw = json.load(f)
    out: dict[int, dict[str, int]] = {}
    for k, v in raw.items():
        try:
            rnd = int(k)
        except (TypeError, ValueError):
            continue
        if not isinstance(v, dict):
            continue
        cleaned: dict[str, int] = {}
        for drv, pos in v.items():
            value = pos.get("position") if isinstance(pos, dict) else pos
            try:
                cleaned[str(drv)] = int(value)
            except (TypeError, ValueError):
                continue
        if cleaned:
            out[rnd] = cleaned
    return out


# --------------------------------------------------------------------------- #
# Round export
# --------------------------------------------------------------------------- #


def _sort_market_entries(market_struct: dict[str, dict[str, float]]) -> list[dict]:
    """Sort driver→probs dict into list of {driver, probability, rawProbability}
    descending by calibrated probability."""
    rows = [
        {"driver": d, "probability": vals["probability"], "rawProbability": vals["rawProbability"]}
        for d, vals in market_struct.items()
    ]
    rows.sort(key=lambda r: r["probability"], reverse=True)
    return rows


def build_round_payload(
    round_file: Path,
    calibrator: ProbabilityCalibrator,
    n_samples: int = DEFAULT_N_SAMPLES,
    temperature: float = DEFAULT_TEMPERATURE,
    now: _dt.datetime | None = None,
    history_db_path: Path | None = None,
) -> tuple[dict, MarketProbabilities]:
    """Compute the FROZEN-schema payload for one round.  Pure (no file write)."""
    rnd = _round_number(round_file)
    round_data, lap_times = _load_lap_times(round_file)
    if not lap_times:
        raise ValueError(f"No predictedTime values found in {round_file}")
    mp = plackett_luce_probabilities(
        lap_times=lap_times,
        n_samples=n_samples,
        temperature=temperature,
        seed=42,
    )
    market_struct = calibrate_market_probabilities(mp, calibrator)
    markets_payload = {m: _sort_market_entries(market_struct[m]) for m in MARKETS}

    season = int(round_data.get("season", 2026))
    generated_at = (now or _dt.datetime.now(_dt.timezone.utc)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # DNF probabilities (optional market). Splices into markets["dnf"] as a
    # sorted-descending list of {driver, probability} entries, matching the
    # shape of win/podium/top6/top10 so the website can render it identically.
    dnf_payload = _build_dnf_market(
        round_data=round_data,
        season=season,
        current_round=rnd,
        history_db_path=history_db_path,
    )
    if dnf_payload:
        markets_payload["dnf"] = dnf_payload

    payload = {
        "round": rnd,
        "season": season,
        "generatedAt": generated_at,
        "method": "plackett-luce-from-laptime",
        "monteCarloSamples": n_samples,
        "temperature": temperature,
        "calibration": {
            "method": "isotonic",
            "trainingSeasons": TRAINING_SEASONS,
            "applied": calibrator.is_fitted(),
        },
        "markets": markets_payload,
        "h2h": mp.h2h,
    }
    return payload, mp


def _build_dnf_market(
    round_data: dict,
    season: int,
    current_round: int,
    history_db_path: Path | None,
) -> list[dict] | None:
    """Compute per-driver DNF probabilities via models.dnf and return a market
    payload sorted descending by probability. Returns None when no
    classification entries are available or the historical DB is missing."""
    classification = round_data.get("classification") or []
    if not classification:
        return None
    try:
        from models.dnf import compute_dnf_probabilities, DnfModelInputs
    except ImportError:
        return None
    db_path = Path(history_db_path) if history_db_path else Path("data/history.duckdb")
    inputs = [
        DnfModelInputs(
            driver=str(entry.get("driver", "")),
            predicted_position=int(entry.get("position", 11) or 11),
            circuit_key=str(round_data.get("gpKey", "")),
        )
        for entry in classification
        if entry.get("driver")
    ]
    if not inputs:
        return None
    probs = compute_dnf_probabilities(
        history_db_path=db_path,
        season=season,
        current_round=current_round,
        inputs=inputs,
    )
    rows = [
        {"driver": driver, "probability": prob, "rawProbability": prob}
        for driver, prob in probs.items()
    ]
    rows.sort(key=lambda r: r["probability"], reverse=True)
    return rows


# --------------------------------------------------------------------------- #
# Calibration summary
# --------------------------------------------------------------------------- #


def build_calibration_summary(
    history: list[dict],
    now: _dt.datetime | None = None,
) -> dict:
    """Build `calibration_summary.json` payload.

    Computes Brier + log-loss per market over the available (predicted,
    observed) pairs, plus reliability diagrams.  When there's insufficient
    data the per-market entry has null metrics and an empty reliability list —
    we never lie about a metric we couldn't compute.
    """
    per_market: dict[str, dict] = {}
    for market in MARKETS:
        records = [r for r in history if r["market"] == market]
        if not records:
            per_market[market] = {
                "brierScore": None,
                "logLoss": None,
                "reliability": [],
                "sampleCount": 0,
            }
            continue
        preds = [r["predicted"] for r in records]
        obs = [r["observed"] for r in records]
        per_market[market] = {
            "brierScore": round(brier_score(preds, obs), 6),
            "logLoss": round(log_loss(preds, obs), 6),
            "reliability": reliability_diagram(preds, obs, n_bins=10),
            "sampleCount": len(records),
        }

    return {
        "generatedAt": (now or _dt.datetime.now(_dt.timezone.utc)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "trainingSeasons": TRAINING_SEASONS,
        "dataLimitation": DATA_LIMITATION_NOTE,
        "perMarket": per_market,
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def run(
    rounds: Iterable[int] | None = None,
    n_samples: int = DEFAULT_N_SAMPLES,
    temperature: float = DEFAULT_TEMPERATURE,
    dry_run: bool = False,
    quiet: bool = False,
    min_completed_rounds: int = 3,
    history_db: Path | None = None,
) -> dict:
    """Compute probabilities for every round, write JSON outputs.

    Returns a dict with the orchestration metadata (counts written, summary
    statistics) so callers can use this as a library.
    """
    files = _list_round_files(rounds)
    if not files:
        if not quiet:
            print(f"No round_*.json found under {ROUNDS_DIR}; nothing to do.")
        return {"rounds_written": 0}

    # First pass: compute raw probabilities for every round; this is what we
    # need to (a) build training history against actuals and (b) write the
    # eventual per-round files.  We pass an unfitted calibrator on the first
    # pass — the raw probabilities are the calibrator's *input*, so they must
    # be uncalibrated when matched against historical truth.
    actuals = _load_actuals()
    unfit_calibrator = ProbabilityCalibrator()
    raw_round_payloads: dict[int, tuple[dict, MarketProbabilities]] = {}
    for f in files:
        rnd = _round_number(f)
        try:
            payload, mp = build_round_payload(
                f,
                calibrator=unfit_calibrator,
                n_samples=n_samples,
                temperature=temperature,
            )
        except ValueError as e:
            if not quiet:
                print(f"  Round {rnd}: skipped ({e})")
            continue
        raw_round_payloads[rnd] = (payload, mp)

    # Fit the calibrator against actuals (will be empty / sparse today).
    history = collect_history_from_rounds(
        round_predictions={rnd: mp for rnd, (_, mp) in raw_round_payloads.items()},
        round_actuals=actuals,
    )

    # Multi-season backfill: if the DB exists, append its (predicted, observed)
    # records so isotonic has real training data.  See backfill_history.py for
    # how those records were generated.  The DB-derived rounds count toward
    # the `min_completed_rounds` gate alongside the in-repo 2026 actuals.
    db_path = Path(history_db) if history_db is not None else DEFAULT_HISTORY_DB
    db_history, db_rounds_count = _load_history_from_db(db_path)
    if db_history:
        history = list(history) + db_history

    calibrator = ProbabilityCalibrator()
    calibrator.fit_from_history(history)

    # Persist the fitted calibrator to the registry (A-P0.3).  Keyed by the
    # season + latest completed round so `registry.latest(season)` recovers
    # the most-recent calibrator without callers having to know which round.
    # Non-fatal: registry failures never block the export.
    if registry_enabled():
        try:
            latest_round = max(
                (int(r) for r in actuals if int(r) in {int(rnd) for rnd in raw_round_payloads}),
                default=None,
            )
            if latest_round is not None:
                ModelRegistry().save(
                    season=2026,
                    round_num=latest_round,
                    models={"calibrator": calibrator},
                    metadata={
                        "fittedMarkets": [m for m in MARKETS if calibrator.is_fitted(m)],
                        "sampleCounts": calibrator.sample_counts(),
                        "historyRecords": len(history),
                        "dbHistoryRounds": db_rounds_count,
                        "kind": "probability-calibrator",
                    },
                )
        except Exception as e:
            print(f"  ⚠️  Could not persist calibrator to model registry: {e}")

    # Honest gate: a single completed round trivially satisfies the calibrator's
    # in-class `_min_samples`, but isotonic on ~22 binary observations per
    # market degenerates to a step function (we observed `applied=true` flattening
    # everything to 0 or 0.25).  Per audit §1.6 we keep `applied=false` until at
    # least `min_completed_rounds` historical races are in the training set —
    # the proper fix is the multi-season backfill in audit §2.2.
    completed_rounds_in_history = (
        len({int(r) for r in actuals if int(r) in {int(rnd) for rnd in raw_round_payloads}})
        + db_rounds_count
    )
    calibration_applied = (
        calibrator.is_fitted()
        and completed_rounds_in_history >= min_completed_rounds
    )

    # Second pass: re-emit per-round files, this time with calibration applied
    # if it actually fit.  If nothing fitted, this is a no-op overwrite — but
    # the second pass is cheap (no MC re-sampling, we already have the
    # MarketProbabilities) and keeps the code path uniform.
    PROBS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    # Honest pass: only push through the fitted calibrator when we've decided to
    # apply it.  Otherwise feed an unfitted calibrator (transform = identity)
    # so the published numbers match what `calibration.applied=false` claims.
    effective_calibrator = calibrator if calibration_applied else ProbabilityCalibrator()
    for rnd, (raw_payload, mp) in raw_round_payloads.items():
        market_struct = calibrate_market_probabilities(mp, effective_calibrator)
        markets_payload = {m: _sort_market_entries(market_struct[m]) for m in MARKETS}
        # Preserve any non-MARKETS extras the first pass injected (notably
        # `dnf` from _build_dnf_market) — those don't get re-calibrated, they
        # just pass through unchanged.
        for extra_key, extra_val in (raw_payload.get("markets") or {}).items():
            if extra_key not in MARKETS:
                markets_payload[extra_key] = extra_val
        final_payload = dict(raw_payload)
        final_payload["markets"] = markets_payload
        final_payload["calibration"] = {
            "method": "isotonic",
            "trainingSeasons": TRAINING_SEASONS,
            "applied": calibration_applied,
        }
        target = PROBS_DIR / f"round_{rnd:02d}.json"
        if not dry_run:
            with target.open("w") as fh:
                json.dump(final_payload, fh, indent=2)
        written += 1
        if not quiet:
            top = markets_payload["win"][0]
            print(
                f"  Round {rnd:02d}: wrote {target.name}  "
                f"top P(win): {top['driver']} {top['probability']:.3f}"
            )

    summary = build_calibration_summary(history)
    summary_path = PROBS_DIR / "calibration_summary.json"
    if not dry_run:
        with summary_path.open("w") as fh:
            json.dump(summary, fh, indent=2)
    if not quiet:
        applied = "yes" if calibration_applied else "NO (insufficient data)"
        print(f"Calibration applied: {applied}")
        print(f"History samples: {len(history)}")
        print(f"Wrote {written} round files + calibration_summary.json")

    return {
        "rounds_written": written,
        "calibration_applied": calibration_applied,
        "history_samples": len(history),
        "summary": summary,
    }


def _parse_rounds(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        elif chunk:
            out.add(int(chunk))
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=str, default=None,
                        help="Round filter (e.g. '1-10' or '1,3,5'). Default: all.")
    parser.add_argument("--samples", type=int, default=DEFAULT_N_SAMPLES)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--min-completed-rounds",
        type=int,
        default=3,
        help="Minimum historical races required before applying isotonic "
             "calibration. Below this we publish raw probabilities and flag "
             "calibration.applied=false. Default 3.",
    )
    parser.add_argument(
        "--history-db",
        type=Path,
        default=DEFAULT_HISTORY_DB,
        help=f"Path to the backfilled history DuckDB (default "
             f"{DEFAULT_HISTORY_DB.relative_to(PROJECT_ROOT)}). "
             "When present, its (predicted_position, actual_position) records "
             "feed the isotonic calibrator. Generate it with backfill_history.py.",
    )
    args = parser.parse_args()

    run(
        rounds=_parse_rounds(args.rounds),
        n_samples=args.samples,
        temperature=args.temperature,
        dry_run=args.dry_run,
        quiet=args.quiet,
        min_completed_rounds=args.min_completed_rounds,
        history_db=args.history_db,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
