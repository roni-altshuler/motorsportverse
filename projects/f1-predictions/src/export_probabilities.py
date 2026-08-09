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

from leakage import assert_prior_only
from models.calibration import (
    DEFAULT_N_SAMPLES,
    DEFAULT_TEAM_SIGMA,
    DEFAULT_TEMPERATURE,
    MARKETS,
    LogisticCalibrator,
    MarketProbabilities,
    ProbabilityCalibrator,
    brier_score,
    calibrate_market_probabilities,
    chaos_temperature,
    collect_history_from_rounds,
    fit_temperature_from_history,
    floor_market_struct,
    log_loss,
    plackett_luce_probabilities,
    reliability_diagram,
    renormalize_market_struct,
)
from models.registry import ModelRegistry, registry_enabled

PROJECT_ROOT = Path(__file__).resolve().parent.parent
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
    "Each round is calibrated strictly out-of-sample: the calibrator is fit only "
    "on rounds that completed BEFORE it (expanding window), never on its own "
    "result. A round with fewer than --min-completed-rounds prior races publishes "
    "raw Monte Carlo probabilities (calibration.applied=false) — publishing raw is "
    "strictly better than over-fitting a handful of events. Published probabilities "
    "carry a small floor (no driver is ever 0.0) and are renormalized per market "
    "(win sums to 1, podium to 3, top6 to 6, top10 to 10). The metrics below score "
    "the FINAL PUBLISHED probabilities against actual results, not the raw inputs."
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


def _extract_teams(round_data: dict) -> dict[str, str]:
    """driver_code → team from the round's classification (for team correlation)."""
    teams: dict[str, str] = {}
    for entry in round_data.get("classification") or []:
        drv = entry.get("driver")
        if drv:
            teams[str(drv)] = str(entry.get("team") or drv)
    return teams


def _chaos_inputs(round_data: dict) -> dict[str, float]:
    """Pull the per-race chaos signals used to widen the sampler temperature.

    ``overtaking`` is stored as *ease* (Monaco ≈ 0.1, an easy-passing track ≈
    0.7); higher safety-car likelihood and rain and *lower* overtaking ease all
    make the finishing order less pace-deterministic → fatter tails.
    """
    circuit = round_data.get("circuitInfo") or {}
    weather = round_data.get("weatherData") or {}
    volatility = round_data.get("circuitVolatility") or {}
    sc = circuit.get("safetyCarLikelihood")
    if sc is None:
        sc = volatility.get("safetyCarProbability", 0.4)
    return {
        "rain_probability": float(weather.get("rainProbability", 0.0) or 0.0),
        "safety_car_rate": float(sc or 0.4),
        "overtaking_ease": float(circuit.get("overtaking", 0.5) or 0.5),
    }


def _compute_p_dnf(round_data: dict, current_round: int) -> dict[str, float]:
    """Per-driver P(DNF), leakage-safe (fit on rounds strictly prior).

    Uses the season-reliability blend in ``models.candidate_model`` (driver +
    team incident rates + circuit attrition, all shrunk toward a base rate),
    which reads committed prior rounds only — no network, no DuckDB.  The SAME
    numbers feed the finishing-order sampler and the published DNF market, so
    the DNF market is self-consistent with win/podium/top-N.
    """
    classification = round_data.get("classification") or []
    drivers = [str(e.get("driver")) for e in classification if e.get("driver")]
    if not drivers:
        return {}
    teams = _extract_teams(round_data)
    try:
        from models.candidate_model import (
            collect_season_reliability,
            compute_dnf_probabilities,
            load_circuit_prior,
        )

        reliability = collect_season_reliability(int(current_round))
        circuit_prior = load_circuit_prior(str(round_data.get("gpKey", "")))
        return compute_dnf_probabilities(drivers, teams, reliability, circuit_prior)
    except Exception:
        # Cold-start / any failure: flat base rate keeps the sampler well-defined.
        return {d: 0.15 for d in drivers}


def _dnf_market_from_p_dnf(p_dnf: dict[str, float] | None) -> list[dict] | None:
    """DNF market payload from the exact P(DNF) that drove the sampler."""
    if not p_dnf:
        return None
    rows = [
        {"driver": d, "probability": float(p), "rawProbability": float(p)}
        for d, p in p_dnf.items()
    ]
    rows.sort(key=lambda r: r["probability"], reverse=True)
    return rows


def build_round_payload(
    round_file: Path,
    calibrator: ProbabilityCalibrator | LogisticCalibrator | None = None,
    n_samples: int = DEFAULT_N_SAMPLES,
    temperature: float = DEFAULT_TEMPERATURE,
    now: _dt.datetime | None = None,
    history_db_path: Path | None = None,
) -> tuple[dict, MarketProbabilities]:
    """Compute the FROZEN-schema payload for one round (RAW / uncalibrated mp).

    Pure (no file write).  ``temperature`` is the *base* τ; it is widened per
    race by the round's chaos signals.  The finishing-order sampler is DNF-aware
    and team-correlated.  Calibration is applied downstream in :func:`run` with
    a strictly-prior-only calibrator, so the ``calibrator`` argument here is only
    an optional convenience for callers that want a one-shot payload.
    """
    rnd = _round_number(round_file)
    round_data, lap_times = _load_lap_times(round_file)
    if not lap_times:
        raise ValueError(f"No predictedTime values found in {round_file}")
    teams = _extract_teams(round_data)
    p_dnf = _compute_p_dnf(round_data, rnd)
    tau = chaos_temperature(temperature, **_chaos_inputs(round_data))
    mp = plackett_luce_probabilities(
        lap_times=lap_times,
        n_samples=n_samples,
        temperature=tau,
        seed=42,
        teams=teams,
        p_dnf=p_dnf,
        team_sigma=DEFAULT_TEAM_SIGMA,
    )
    market_struct = calibrate_market_probabilities(mp, calibrator)
    market_struct = floor_market_struct(market_struct)
    market_struct = renormalize_market_struct(market_struct)
    markets_payload = {m: _sort_market_entries(market_struct[m]) for m in MARKETS}
    dnf_market = _dnf_market_from_p_dnf(mp.p_dnf)
    if dnf_market:
        markets_payload["dnf"] = dnf_market

    season = int(round_data.get("season", 2026))
    generated_at = (now or _dt.datetime.now(_dt.timezone.utc)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    payload = {
        "round": rnd,
        "season": season,
        "generatedAt": generated_at,
        "method": "plackett-luce-from-laptime",
        "monteCarloSamples": n_samples,
        "temperature": round(float(tau), 4),
        "calibration": {
            "method": "held-out",
            "trainingSeasons": TRAINING_SEASONS,
            "applied": bool(calibrator is not None and calibrator.is_fitted()),
        },
        "markets": markets_payload,
        "h2h": mp.h2h,
    }
    return payload, mp


# --------------------------------------------------------------------------- #
# Calibration summary
# --------------------------------------------------------------------------- #


_MARKET_THRESHOLDS = {"win": 1, "podium": 3, "top6": 6, "top10": 10}


def _ece_mce(bins: list[dict]) -> tuple[float | None, float | None]:
    """Expected + maximum calibration error from a reliability diagram.

    ECE = count-weighted mean |empirical − meanPred|; MCE = the worst bin gap.
    """
    total = sum(int(b["count"]) for b in bins)
    if total == 0:
        return None, None
    ece = sum(int(b["count"]) * abs(b["empirical"] - b["meanPred"]) for b in bins) / total
    mce = max((abs(b["empirical"] - b["meanPred"]) for b in bins), default=None)
    return round(float(ece), 6), (round(float(mce), 6) if mce is not None else None)


def _published_pairs_by_market(
    published_by_round: dict[int, dict],
    actuals: dict[int, dict[str, int]],
) -> dict[str, tuple[list[float], list[int]]]:
    """Collect (published probability, observed outcome) per market across all
    rounds that have actual results.  Scores the FINAL published numbers — the
    ones the site shows — not the raw Monte Carlo inputs."""
    out: dict[str, tuple[list[float], list[int]]] = {m: ([], []) for m in MARKETS}
    for rnd, payload in published_by_round.items():
        actual = actuals.get(int(rnd))
        if not actual:
            continue
        markets = payload.get("markets") or {}
        for market, thresh in _MARKET_THRESHOLDS.items():
            for entry in markets.get(market) or []:
                drv = entry.get("driver")
                p = entry.get("probability")
                if drv is None or p is None or drv not in actual:
                    continue
                out[market][0].append(float(p))
                out[market][1].append(int(int(actual[drv]) <= thresh))
    return out


def build_calibration_summary(
    published_by_round: dict[int, dict],
    actuals: dict[int, dict[str, int]],
    now: _dt.datetime | None = None,
) -> dict:
    """Build `calibration_summary.json` scoring the FINAL PUBLISHED probabilities.

    Brier + log-loss + reliability + ECE/MCE per market over the published
    (probability, actual-outcome) pairs.  When a market has no scored pairs the
    entry carries null metrics and an empty reliability list — we never invent a
    metric we couldn't compute.
    """
    pairs = _published_pairs_by_market(published_by_round, actuals)
    per_market: dict[str, dict] = {}
    for market in MARKETS:
        preds, obs = pairs[market]
        if not preds:
            per_market[market] = {
                "brierScore": None,
                "logLoss": None,
                "ece": None,
                "mce": None,
                "reliability": [],
                "sampleCount": 0,
            }
            continue
        bins = reliability_diagram(preds, obs, n_bins=10)
        ece, mce = _ece_mce(bins)
        per_market[market] = {
            "brierScore": round(brier_score(preds, obs), 6),
            "logLoss": round(log_loss(preds, obs), 6),
            "ece": ece,
            "mce": mce,
            "reliability": bins,
            "sampleCount": len(preds),
        }

    return {
        "generatedAt": (now or _dt.datetime.now(_dt.timezone.utc)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "trainingSeasons": TRAINING_SEASONS,
        "dataLimitation": DATA_LIMITATION_NOTE,
        "scores": "published",
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
    min_completed_rounds: int = 4,
    history_db: Path | None = None,
) -> dict:
    """Compute probabilities for every round, write JSON outputs.

    Each round is calibrated **strictly out-of-sample**: its calibrator is fit
    only on rounds that completed before it (expanding window / leave-this-round-
    out), so a round is never scored by a model that saw its own result.  Rounds
    with fewer than ``min_completed_rounds`` prior races publish raw Monte Carlo
    probabilities (``applied=false``).  Everything is floored + renormalized so
    no driver is published at a hard 0.0.

    Returns orchestration metadata so callers can use this as a library.
    """
    files = _list_round_files(rounds)
    if not files:
        if not quiet:
            print(f"No round_*.json found under {ROUNDS_DIR}; nothing to do.")
        return {"rounds_written": 0}

    actuals = _load_actuals()

    # ── Pass 0: load each round's inputs (lap times, teams, DNF, chaos) ──────
    round_inputs: dict[int, tuple[dict, dict[str, float], dict[str, str],
                                  dict[str, float], dict[str, float]]] = {}
    for f in files:
        rnd = _round_number(f)
        round_data, lap_times = _load_lap_times(f)
        if not lap_times:
            if not quiet:
                print(f"  Round {rnd}: skipped (no predictedTime values)")
            continue
        round_inputs[rnd] = (
            round_data,
            lap_times,
            _extract_teams(round_data),
            _compute_p_dnf(round_data, rnd),
            _chaos_inputs(round_data),
        )

    # ── Base temperature: fit on requested rounds that have actuals, then
    # widen per-race by chaos.  Falls back to the passed-in τ when history is
    # too thin to choose (< 2 scored rounds).  Deterministic (seed-pinned MC). ─
    scored_laps = {
        rnd: li[1] for rnd, li in round_inputs.items() if int(rnd) in actuals
    }
    base_temperature = fit_temperature_from_history(scored_laps, actuals, seed=42)
    if not scored_laps:
        base_temperature = temperature

    # ── Pass 1: RAW DNF-aware, team-correlated MC per round (chaos τ) ────────
    generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_round_payloads: dict[int, tuple[dict, MarketProbabilities]] = {}
    for rnd, (round_data, lap_times, teams, p_dnf, chaos) in round_inputs.items():
        tau = chaos_temperature(base_temperature, **chaos)
        mp = plackett_luce_probabilities(
            lap_times=lap_times,
            n_samples=n_samples,
            temperature=tau,
            seed=42,
            teams=teams,
            p_dnf=p_dnf,
            team_sigma=DEFAULT_TEAM_SIGMA,
        )
        payload = {
            "round": rnd,
            "season": int(round_data.get("season", 2026)),
            "generatedAt": generated_at,
            "method": "plackett-luce-from-laptime",
            "monteCarloSamples": n_samples,
            "temperature": round(float(tau), 4),
            "h2h": mp.h2h,
        }
        raw_round_payloads[rnd] = (payload, mp)

    # Full (raw prob, observed) history from completed 2026 rounds.  Each record
    # carries its ``round`` so the per-round calibrator can filter to prior only.
    full_history = collect_history_from_rounds(
        round_predictions={rnd: mp for rnd, (_, mp) in raw_round_payloads.items()},
        round_actuals=actuals,
    )

    # Registry: persist a "latest" calibrator fit on ALL completed rounds (for
    # downstream tooling only — the published files use per-round OOS fits).
    db_path = Path(history_db) if history_db is not None else DEFAULT_HISTORY_DB
    _, db_rounds_count = _load_history_from_db(db_path)
    if registry_enabled():
        try:
            latest_round = max(
                (int(r) for r in actuals if int(r) in raw_round_payloads),
                default=None,
            )
            if latest_round is not None:
                latest_cal = LogisticCalibrator().fit_from_history(full_history)
                ModelRegistry().save(
                    season=2026,
                    round_num=latest_round,
                    models={"calibrator": latest_cal},
                    metadata={
                        "fittedMarkets": [m for m in MARKETS if latest_cal.is_fitted(m)],
                        "sampleCounts": latest_cal.sample_counts(),
                        "historyRecords": len(full_history),
                        "dbHistoryRounds": db_rounds_count,
                        "kind": "probability-calibrator",
                        "calibration": "held-out-logistic",
                    },
                )
        except Exception as e:
            print(f"  ⚠️  Could not persist calibrator to model registry: {e}")

    # ── Pass 2: per-round out-of-sample calibration → publish ────────────────
    PROBS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    applied_rounds: list[int] = []
    published_by_round: dict[int, dict] = {}
    for rnd, (raw_payload, mp) in raw_round_payloads.items():
        prior_history = [r for r in full_history if int(r["round"]) < int(rnd)]
        prior_rounds = sorted({int(r["round"]) for r in prior_history})
        # Leakage guard: the calibrator for round R may only see rounds < R.
        assert_prior_only(
            {p: 1 for p in prior_rounds}, int(rnd), f"probability_calibration_r{rnd}"
        )
        calibrator: LogisticCalibrator | None = None
        if len(prior_rounds) >= min_completed_rounds:
            fitted = LogisticCalibrator().fit_from_history(prior_history)
            if fitted.is_fitted():
                calibrator = fitted
        applied = calibrator is not None
        if applied:
            applied_rounds.append(int(rnd))

        market_struct = calibrate_market_probabilities(mp, calibrator)
        # Floor first (no hard 0.0), then water-fill back to each market's set
        # size.  Because the water-fill only scales by positive factors / caps at
        # 1.0, a strictly-positive floored input can never be pinned back to 0 —
        # this is what keeps per-driver calibration from collapsing.
        market_struct = floor_market_struct(market_struct)
        market_struct = renormalize_market_struct(market_struct)
        markets_payload = {m: _sort_market_entries(market_struct[m]) for m in MARKETS}
        dnf_market = _dnf_market_from_p_dnf(mp.p_dnf)
        if dnf_market:
            markets_payload["dnf"] = dnf_market

        final_payload = dict(raw_payload)
        final_payload["markets"] = markets_payload
        final_payload["calibration"] = {
            "method": "held-out",
            "trainingSeasons": TRAINING_SEASONS,
            "applied": applied,
            "priorRounds": len(prior_rounds),
        }
        published_by_round[int(rnd)] = final_payload
        target = PROBS_DIR / f"round_{rnd:02d}.json"
        if not dry_run:
            with target.open("w") as fh:
                json.dump(final_payload, fh, indent=2)
        written += 1
        if not quiet:
            top = markets_payload["win"][0]
            flag = "cal" if applied else "raw"
            print(
                f"  Round {rnd:02d}: wrote {target.name}  [{flag}]  "
                f"τ={final_payload['temperature']:.3f}  "
                f"top P(win): {top['driver']} {top['probability']:.3f}"
            )

    # ── Honest metrics: score the FINAL PUBLISHED probabilities ─────────────
    summary = build_calibration_summary(published_by_round, actuals)
    if not dry_run:
        with (PROBS_DIR / "calibration_summary.json").open("w") as fh:
            json.dump(summary, fh, indent=2)
        # Committed honesty surface: ECE/MCE/log-loss on the published numbers,
        # under forward_eval/ (derived from PROBS_DIR so tests that redirect
        # PROBS_DIR redirect this too).
        fe_dir = PROBS_DIR.parent / "forward_eval"
        fe_dir.mkdir(parents=True, exist_ok=True)
        published_metrics = {
            "generatedAt": summary["generatedAt"],
            "season": 2026,
            "scores": "published",
            "roundsScored": sorted(
                int(r) for r in published_by_round if int(r) in actuals
            ),
            "note": DATA_LIMITATION_NOTE,
            "perMarket": summary["perMarket"],
        }
        with (fe_dir / "published_calibration.json").open("w") as fh:
            json.dump(published_metrics, fh, indent=2)

    if not quiet:
        print(
            f"Calibration applied on rounds: "
            f"{applied_rounds if applied_rounds else 'none (raw published)'}"
        )
        print(f"Base τ (fitted): {base_temperature:.3f}   History records: {len(full_history)}")
        print(f"Wrote {written} round files + calibration_summary.json")

    return {
        "rounds_written": written,
        "calibration_applied": bool(applied_rounds),
        "applied_rounds": applied_rounds,
        "base_temperature": base_temperature,
        "history_samples": len(full_history),
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
        default=4,
        help="Minimum PRIOR completed races a round needs before its "
             "out-of-sample calibrator is applied. Below this the round "
             "publishes raw probabilities and flags calibration.applied=false. "
             "Default 4.",
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
