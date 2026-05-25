"""Old-vs-new ML stack comparison.

Runs side-by-side metrics on the data we already have on disk for
the current season:

* Per-round position MAE / RMSE / podium hit-rate against the
  existing ``predicted_results_<season>.json``.
* Calibration metrics (ECE / MCE / Brier per market) against
  ``website/public/data/probabilities/round_NN.json``.
* Conformal coverage check using the residual cache built by
  ``train_ensemble``.
* Optional: fit + register the LightGBM ``RaceProjectionHead`` via
  leave-one-round-out CV, write the registry sentinel round 96.

This script is intentionally read-mostly. It does not regenerate
predictions — that's :mod:`export_website_data`'s job. It just
runs comparable metrics on what's been published, so the
architecture improvements can be measured before they're switched
on in production.

Run::

    python -m benchmarks.run_ml_comparison --season 2026
    python -m benchmarks.run_ml_comparison --season 2026 --fit-head
    python -m benchmarks.run_ml_comparison --season 2026 --reliability-plots
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.conformal import (  # noqa: E402
    ConformalIntervals,
    MIN_CALIBRATION_SAMPLES,
)
from models.reliability import (  # noqa: E402
    compute_market_report_from_probabilities,
    metrics_to_dict,
    save_reliability_diagram,
)


@dataclass
class PositionMetrics:
    rounds_evaluated: int
    mae: float
    rmse: float
    podium_hits_total: int
    podium_total: int
    winner_hits: int
    winner_total: int

    @property
    def podium_hit_rate(self) -> float:
        return self.podium_hits_total / self.podium_total if self.podium_total else 0.0

    @property
    def winner_hit_rate(self) -> float:
        return self.winner_hits / self.winner_total if self.winner_total else 0.0


def _load_results_json(path: Path) -> dict[int, dict[str, int]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    out: dict[int, dict[str, int]] = {}
    if isinstance(payload, list):
        for entry in payload:
            rnd = entry.get("round")
            data = entry.get("results") or entry.get("positions") or {}
            if rnd is not None:
                out[int(rnd)] = {
                    str(k): int(v) for k, v in data.items() if v is not None
                }
        return out
    if isinstance(payload, dict):
        rounds_block = payload.get("rounds") or payload
        for rnd, body in rounds_block.items():
            try:
                rnd_int = int(rnd)
            except (TypeError, ValueError):
                continue
            if isinstance(body, dict):
                data = body.get("results") or body.get("positions") or body
                out[rnd_int] = {
                    str(k): int(v)
                    for k, v in data.items()
                    if isinstance(v, (int, float))
                }
    return out


def evaluate_positions(
    predicted: Mapping[int, Mapping[str, int]],
    actual: Mapping[int, Mapping[str, int]],
) -> PositionMetrics:
    """Per-round MAE / RMSE / podium-hit / winner-hit across the season."""
    rounds_evaluated = 0
    err_total: list[float] = []
    podium_hits = 0
    podium_total = 0
    winner_hits = 0
    winner_total = 0

    for rnd, actual_round in actual.items():
        pred_round = predicted.get(rnd)
        if not pred_round:
            continue
        common = sorted(set(pred_round.keys()) & set(actual_round.keys()))
        if not common:
            continue
        rounds_evaluated += 1
        for drv in common:
            err_total.append(float(pred_round[drv]) - float(actual_round[drv]))

        pred_top3 = {d for d, p in pred_round.items() if p <= 3}
        actual_top3 = {d for d, p in actual_round.items() if p <= 3}
        podium_hits += len(pred_top3 & actual_top3)
        podium_total += 3

        winner_pred = next((d for d, p in pred_round.items() if p == 1), None)
        winner_actual = next((d for d, p in actual_round.items() if p == 1), None)
        if winner_pred is not None and winner_actual is not None:
            winner_hits += int(winner_pred == winner_actual)
            winner_total += 1

    if not err_total:
        return PositionMetrics(0, 0.0, 0.0, 0, 0, 0, 0)
    err = np.asarray(err_total, dtype=np.float64)
    return PositionMetrics(
        rounds_evaluated=rounds_evaluated,
        mae=float(np.abs(err).mean()),
        rmse=float(np.sqrt((err**2).mean())),
        podium_hits_total=podium_hits,
        podium_total=podium_total,
        winner_hits=winner_hits,
        winner_total=winner_total,
    )


def evaluate_probability_calibration(
    probabilities_dir: Path,
    actual: Mapping[int, Mapping[str, int]],
) -> dict[str, dict]:
    """ECE / MCE / Brier per market from per-round probability JSON."""
    if not probabilities_dir.exists():
        return {}
    pred: dict[str, list[float]] = {m: [] for m in ("win", "podium", "top6", "top10")}
    obs: dict[str, list[int]] = {m: [] for m in pred}
    threshold = {"win": 1, "podium": 3, "top6": 6, "top10": 10}

    for path in sorted(probabilities_dir.glob("round_*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        rnd = int(payload.get("round") or 0)
        actual_round = actual.get(rnd, {})
        if not actual_round:
            continue
        markets_block = payload.get("markets") or {}
        for market, thresh in threshold.items():
            for entry in markets_block.get(market) or []:
                drv = entry.get("driver") or entry.get("code")
                p = entry.get("probability")
                if p is None:
                    p = entry.get("rawProbability")
                if drv is None or p is None or drv not in actual_round:
                    continue
                pred[market].append(float(p))
                obs[market].append(1 if actual_round[drv] <= thresh else 0)

    report = compute_market_report_from_probabilities(pred, obs)
    return {market: metrics_to_dict(m) for market, m in report.by_market.items()}


def evaluate_conformal_coverage(
    season: int,
    current_round: int,
    *,
    alpha: float = 0.10,
    cache_dir: Path | None = None,
) -> dict[str, float | int | None]:
    """Estimate observed coverage of the split-conformal intervals.

    Uses the residual cache. Conservative: we fit the conformal
    calibrator on rounds 1..M and test coverage on round M+1
    (one-step-ahead). Reports mean observed coverage across all
    such (M, M+1) pairs.
    """
    residuals_by_round: dict[int, np.ndarray] = {}
    base_dir = cache_dir or PROJECT_ROOT / "data" / "conformal_residuals"
    if not base_dir.exists():
        return {"coverage": None, "n_evaluated": 0, "alpha": alpha}
    for path in sorted(base_dir.glob(f"{season}_round_*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        rnd = int(payload.get("round") or 0)
        residuals_by_round[rnd] = np.asarray(
            payload.get("abs_residuals") or [], dtype=np.float64
        )

    sorted_rounds = sorted(r for r in residuals_by_round if r < current_round)
    if len(sorted_rounds) < 2:
        return {"coverage": None, "n_evaluated": 0, "alpha": alpha}

    coverages: list[float] = []
    for cutoff_idx in range(1, len(sorted_rounds)):
        train_rounds = sorted_rounds[:cutoff_idx]
        test_round = sorted_rounds[cutoff_idx]
        train_residuals = np.concatenate(
            [residuals_by_round[r] for r in train_rounds]
        )
        test_residuals = residuals_by_round[test_round]
        if (
            len(train_residuals) < MIN_CALIBRATION_SAMPLES
            or len(test_residuals) == 0
        ):
            continue
        # Synthesise (y, ŷ) calibration pairs from absolute residuals.
        conf = ConformalIntervals(alpha=alpha).fit(
            train_residuals, np.zeros_like(train_residuals)
        )
        in_band = (test_residuals <= conf.quantile).mean()
        coverages.append(float(in_band))

    if not coverages:
        return {"coverage": None, "n_evaluated": 0, "alpha": alpha}
    return {
        "coverage": float(np.mean(coverages)),
        "n_evaluated": int(len(coverages)),
        "alpha": float(alpha),
        "target_coverage": 1.0 - alpha,
    }


def maybe_fit_and_register_head(
    season: int,
    predicted: Mapping[int, Mapping[str, int]],
    actual: Mapping[int, Mapping[str, int]],
) -> dict[str, object]:
    """Train the LightGBM head from predicted+actual history.

    A pragmatic compromise: uses ``predicted_position`` (1..22 scale)
    as the single input feature. The full 14-feature training would
    require replaying ``build_training_dataset`` per round, which is
    beyond the scope of this benchmark and is left to a follow-up
    that wires the per-round feature snapshots into the registry.

    Returns the LOO-CV metrics dict. When the registry is enabled
    the trained head is saved under sentinel round 96.
    """
    from models.race_projection_head import (
        LearnedRaceProjection,
        RaceProjectionHead,
    )
    from models.registry import ModelRegistry

    rows_X: list[float] = []
    rows_y: list[float] = []
    rows_round: list[int] = []
    for rnd, actual_round in actual.items():
        pred_round = predicted.get(rnd, {})
        if not pred_round:
            continue
        for drv, pos in actual_round.items():
            if drv not in pred_round:
                continue
            rows_X.append(float(pred_round[drv]))
            rows_y.append(float(pos))
            rows_round.append(int(rnd))

    if len(set(rows_round)) < 2:
        return {"status": "insufficient_data", "n_rows": len(rows_X)}

    X = np.asarray(rows_X, dtype=np.float64).reshape(-1, 1)
    # Pad to the head's expected feature width by repeating predicted_position;
    # downstream the full feature matrix replaces this stub.
    from models.race_projection_head import DEFAULT_HEAD_FEATURES

    pad_width = len(DEFAULT_HEAD_FEATURES)
    X_padded = np.tile(X, (1, pad_width))
    y = np.asarray(rows_y, dtype=np.float64)
    rounds = np.asarray(rows_round, dtype=np.int64)

    head = RaceProjectionHead(n_estimators=120)
    learned = LearnedRaceProjection(head=head)
    metrics = learned.leave_one_round_out_cv(X_padded, y, rounds)
    # Fit once on the full set so it can be persisted.
    learned.fit_from_history(X_padded, y)

    try:
        registry = ModelRegistry()
        registry.save(
            season=season,
            round_num=96,
            models={"race_projection_head": head},
            metadata={
                "kind": "race-projection-head",
                "feature_columns": list(DEFAULT_HEAD_FEATURES),
                "loo_cv": metrics,
                "n_training_rows": int(X.shape[0]),
                "data_provenance": "predicted_position from predicted_results_<season>.json",
            },
        )
        metrics["registered_sentinel_round"] = 96
    except Exception as exc:  # noqa: BLE001 - non-fatal
        metrics["registration_error"] = str(exc)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare legacy vs new ML stack on the current season."
    )
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument(
        "--predictions-file",
        type=Path,
        default=None,
        help="Override predicted_results path",
    )
    parser.add_argument(
        "--actual-file", type=Path, default=None, help="Override season_results path"
    )
    parser.add_argument(
        "--probabilities-dir",
        type=Path,
        default=PROJECT_ROOT / "website" / "public" / "data" / "probabilities",
        help="Where to read per-round probability JSON",
    )
    parser.add_argument(
        "--reliability-plots-dir",
        type=Path,
        default=None,
        help="Write reliability diagrams (one PNG per market) into this dir.",
    )
    parser.add_argument(
        "--fit-head",
        action="store_true",
        help="Fit + register the LightGBM RaceProjectionHead via LOO-CV.",
    )
    parser.add_argument(
        "--current-round",
        type=int,
        default=99,
        help="Cutoff round for conformal coverage estimation.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports" / "ml_benchmark.json",
        help="Where to write the consolidated JSON report.",
    )
    args = parser.parse_args(argv)

    predicted_path = (
        args.predictions_file
        or PROJECT_ROOT / f"predicted_results_{args.season}.json"
    )
    actual_path = args.actual_file or PROJECT_ROOT / f"season_results_{args.season}.json"

    predicted = _load_results_json(predicted_path)
    actual = _load_results_json(actual_path)

    pos_metrics = evaluate_positions(predicted, actual)
    cal_metrics = evaluate_probability_calibration(args.probabilities_dir, actual)
    conformal = evaluate_conformal_coverage(
        args.season, args.current_round
    )

    head_metrics: dict[str, object] | None = None
    if args.fit_head:
        head_metrics = maybe_fit_and_register_head(args.season, predicted, actual)

    payload: dict[str, object] = {
        "season": args.season,
        "predictions_path": str(predicted_path),
        "actuals_path": str(actual_path),
        "position_metrics": {
            "rounds_evaluated": pos_metrics.rounds_evaluated,
            "mae": pos_metrics.mae,
            "rmse": pos_metrics.rmse,
            "podium_hit_rate": pos_metrics.podium_hit_rate,
            "winner_hit_rate": pos_metrics.winner_hit_rate,
        },
        "calibration_metrics": cal_metrics,
        "conformal": conformal,
        "head_loo_cv": head_metrics,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))

    if args.reliability_plots_dir is not None and cal_metrics:
        args.reliability_plots_dir.mkdir(parents=True, exist_ok=True)
        # Re-build the report to access the CalibrationMetrics objects.
        from models.reliability import compute_calibration_metrics

        for market, m in cal_metrics.items():
            preds = m.get("bins", [])
            # Recover (predicted, observed) arrays from the bin summary
            # — sufficient for the diagram, even if it loses raw points.
            centres = []
            observed = []
            counts = []
            for b in preds:
                obs = b.get("mean_observed")
                if obs is None:
                    continue
                centres.append(b["mean_predicted"])
                observed.append(obs)
                counts.append(b["count"])
            if not centres:
                continue
            # Reconstruct a synthetic per-row array proportional to bin counts.
            row_preds: list[float] = []
            row_obs: list[int] = []
            for c, o, n in zip(centres, observed, counts):
                row_preds.extend([float(c)] * int(n))
                row_obs.extend([1] * int(round(o * n)))
                row_obs.extend([0] * (int(n) - int(round(o * n))))
            if not row_preds:
                continue
            metrics = compute_calibration_metrics(row_preds, row_obs)
            save_reliability_diagram(
                metrics,
                args.reliability_plots_dir / f"reliability_{market}.png",
                title=f"{args.season} season — {market}",
            )

    # Console summary.
    print("\nML benchmark summary")
    print(f"  Season: {args.season}")
    print(
        f"  Position MAE: {pos_metrics.mae:.2f}  RMSE: {pos_metrics.rmse:.2f}  "
        f"Podium hit-rate: {pos_metrics.podium_hit_rate:.2%}  "
        f"Winner hit-rate: {pos_metrics.winner_hit_rate:.2%}  "
        f"(rounds evaluated: {pos_metrics.rounds_evaluated})"
    )
    if cal_metrics:
        print("  Calibration per market:")
        for market, m in cal_metrics.items():
            ece = m.get("ece")
            mce = m.get("mce")
            brier = m.get("brier")
            pieces = [
                f"ECE={ece:.3f}" if isinstance(ece, (int, float)) else "ECE=—",
                f"MCE={mce:.3f}" if isinstance(mce, (int, float)) else "MCE=—",
                f"Brier={brier:.3f}" if isinstance(brier, (int, float)) else "Brier=—",
            ]
            print(f"    {market}: " + "  ".join(pieces))
    else:
        print("  Calibration: no probability files found.")
    if conformal.get("coverage") is not None:
        print(
            f"  Conformal coverage: {conformal['coverage']:.2%} "
            f"(target {conformal['target_coverage']:.2%}; "
            f"n={conformal['n_evaluated']})"
        )
    else:
        print("  Conformal: insufficient residual cache.")
    if head_metrics:
        print(f"  Learned head LOO-CV: {head_metrics}")
    print(f"\nWritten {args.output.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
