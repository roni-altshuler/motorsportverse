"""Forward-time evaluation for IndyCar — scores leakage-safe predictions vs actuals.

**This is the headline validation surface for the IndyCar model.** For every
completed round we re-run the model with *only* prior-round data (the same
leakage-safe forecast the website shows pre-race) and score it against the
actual classification. The metrics are the shared
:func:`motorsport_core.eval.score_round` bundle. Scoring is against the
**full classified field**: IndyCar classifies every car (retirees keep a
finishing position), so every started car counts — matching the NASCAR
convention rather than the open-wheel finishers-only one.

Two trivial baselines ride alongside the model, per round:

* ``lastRace`` — the previous completed round's actual order re-scored as the
  prediction (None for round 1);
* ``gridOrder`` — the round's actual starting grid as the prediction. Grid
  availability varies in the curated files (older grid-backed rounds carry
  none) — a round without a real grid gets an honest ``None`` baseline, never
  a fabricated one.

The season is scored by walking forward one completed round at a time and
aggregating the per-round metrics via
:func:`motorsport_core.eval.walk_forward_summary` (mean / median / min / max /
last / OLS-trend per metric), model and baselines side-by-side.

Outputs (under ``website/public/data/forward_eval/``):
    round_NN.json           per-round metrics + per-market Brier/log-loss +
                            the two baselines
    season.json             season roll-up + the ``walkForward``
                            model-vs-baselines summary
    position_model_ab.json  (opt-in, ``--position-model-ab``) walk-forward A/B
                            of the direct finishing-position head vs production

Run:  python -m indycar_predictions.forward_eval --season 2026 [--allow-empty]
          [--out <dir>] [--position-model-ab] [--min-prior-rounds N]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from motorsport_core import eval as core_eval

from . import config, pipeline
from .datasource import IndycarDataSource

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data" / "forward_eval"

BASELINES = ("lastRace", "gridOrder")


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _score_race(fc_race, actual: dict[str, int]) -> dict:
    predicted = {code: i for i, code in enumerate(fc_race.order, start=1)}
    return core_eval.score_round(predicted, actual)


def _market_scores(fc_race, actual: dict[str, int]) -> dict:
    """Per-market probability quality (Brier + log-loss) for one race."""
    if not actual:
        return {}
    winner = min(actual, key=actual.get)
    win_outcomes = {c: 1.0 if c == winner else 0.0 for c in actual}
    podium = {c for c, p in actual.items() if p <= 3}
    podium_outcomes = {c: 1.0 if c in podium else 0.0 for c in actual}
    out: dict[str, dict] = {}
    for market, probs, outcomes in (
        ("win", fc_race.markets.p_win, win_outcomes),
        ("podium", fc_race.markets.p_podium, podium_outcomes),
    ):
        brier = core_eval.brier_score(probs, outcomes)
        ll = core_eval.log_loss(probs, outcomes)
        out[market] = {
            "brier": round(brier, 6) if brier is not None else None,
            "logLoss": round(ll, 6) if ll is not None else None,
        }
    return out


def _actuals(source: IndycarDataSource, year: int, rnd: int) -> dict[str, int]:
    return {
        r.competitor: r.position
        for r in source.results(year, rnd)
        if r.position is not None
    }


def _grid_map(source: IndycarDataSource, year: int, rnd: int) -> dict[str, int] | None:
    """The round's actual starting grid ({code: slot}), or None when unknown.

    Prefers the classification rows' recorded grid; falls back to a captured
    qualifying order. Real data only — a synthetic grid would not be a
    meaningful baseline, and grid-backed old rounds honestly have none.
    """
    rows = source.race_rows(year, rnd)
    if rows:
        grid = {r["code"]: int(r["grid"]) for r in rows if r.get("grid")}
        if len(grid) >= 3:
            return grid
    quali = source.qualifying(year, rnd)
    if quali:
        return {c: i for i, c in enumerate(quali, start=1)}
    return None


def evaluate_season(year: int, *, source: IndycarDataSource | None = None) -> list[dict]:
    """Score every completed round, walking forward with leakage-safe replays.

    Each per-round dict carries ``round``/``venueName``/``trackType``/``race``
    (the score bundle) plus ``markets`` (win/podium Brier + log-loss) and
    ``baselines`` (lastRace + gridOrder score bundles, each ``None`` when its
    input does not exist).
    """
    source = source or IndycarDataSource()
    rounds: list[dict] = []
    prev_actual: dict[str, int] | None = None
    for rnd in source.completed_rounds(year):
        fc = pipeline.forecast_round(source, year, rnd)
        actual = _actuals(source, year, rnd)
        if not actual:
            continue
        baselines: dict[str, dict | None] = {b: None for b in BASELINES}
        if prev_actual:
            baseline_pred = core_eval.last_order_baseline(prev_actual)
            baselines["lastRace"] = core_eval.score_round(baseline_pred, actual)
        grid = _grid_map(source, year, rnd)
        race_post_quali = None
        if grid:
            baselines["gridOrder"] = core_eval.score_round(grid, actual)
            # The FAIR arm against the gridOrder baseline: the model's own
            # post-quali replay, conditioned on the same pre-race-public grid
            # the baseline uses (the pre-quali arm never saw it).
            known_grid = [c for c, _ in sorted(grid.items(), key=lambda kv: kv[1])]
            fc_pq = pipeline.forecast_round(source, year, rnd, known_grid=known_grid)
            race_post_quali = _score_race(fc_pq.race, actual)
        rounds.append(
            {
                "round": rnd,
                "venueName": fc.venue_name,
                "trackType": fc.track_type,
                "trackGroup": fc.track_group,
                "race": _score_race(fc.race, actual),
                "racePostQuali": race_post_quali,
                "markets": {"race": _market_scores(fc.race, actual)},
                "baselines": baselines,
            }
        )
        prev_actual = actual
    return rounds


# --------------------------------------------------------------------------- #
# Walk-forward summary (headline validation surface)
# --------------------------------------------------------------------------- #
def _round_metric_bundle(r: dict) -> dict[str, float]:
    """Numeric per-round metric view for :func:`walk_forward_summary`.

    ``winner_hit`` (bool) becomes ``winnerHit`` (0/1) so it survives the
    summary (which skips bools); the per-market Brier / log-loss fold in flat
    (``winBrier`` ...) so probability quality trends alongside accuracy.
    """
    score = r.get("race") or {}
    out: dict[str, float] = {}
    for key, val in score.items():
        if key == "n":
            continue
        if key == "winner_hit":
            out["winnerHit"] = 1.0 if val else 0.0
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        out[key] = float(val)
    for market, metrics in (r.get("markets", {}).get("race") or {}).items():
        for name, val in (metrics or {}).items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[f"{market}{name[0].upper()}{name[1:]}"] = float(val)
    return out


def _baseline_metric_bundle(r: dict, baseline: str) -> dict[str, float] | None:
    score = (r.get("baselines") or {}).get(baseline)
    if not score:
        return None
    out: dict[str, float] = {}
    for key, val in score.items():
        if key == "n":
            continue
        if key == "winner_hit":
            out["winnerHit"] = 1.0 if val else 0.0
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        out[key] = float(val)
    return out


def _post_quali_bundle(r: dict) -> dict[str, float] | None:
    score = r.get("racePostQuali")
    if not score:
        return None
    out: dict[str, float] = {}
    for key, val in score.items():
        if key == "n":
            continue
        if key == "winner_hit":
            out["winnerHit"] = 1.0 if val else 0.0
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        out[key] = float(val)
    return out


def build_walk_forward_summary(rounds: list[dict]) -> dict:
    """Aggregate every scored round into a model-vs-baselines walk-forward
    block — the season-level headline surface. ``modelPostQuali`` is the
    model's grid-conditioned arm, the like-for-like comparator for the
    ``gridOrder`` baseline."""
    model_rows = [_round_metric_bundle(r) for r in rounds]
    pq_rows = [m for m in (_post_quali_bundle(r) for r in rounds) if m is not None]
    baselines = {
        b: core_eval.walk_forward_summary(
            [m for m in (_baseline_metric_bundle(r, b) for r in rounds) if m is not None]
        )
        for b in BASELINES
    }
    return {
        "race": {
            "model": core_eval.walk_forward_summary(model_rows),
            "modelPostQuali": core_eval.walk_forward_summary(pq_rows),
            "baselines": baselines,
        }
    }


def _season_summary(year: int, rounds: list[dict]) -> dict:
    def _mean(key: str) -> float | None:
        vals = [
            r["race"][key]
            for r in rounds
            if r["race"].get(key) is not None and r["race"].get("n", 0) > 0
        ]
        return round(sum(vals) / len(vals), 4) if vals else None

    winner_hits = sum(1 for r in rounds if r["race"].get("winner_hit"))
    podium_hits = sum(r["race"].get("podium_hits", 0) for r in rounds)
    scored = len(rounds)
    return {
        # Original keys — the website reads these; never rename/remove.
        "season": year,
        "roundsScored": scored,
        "meanPositionError": _mean("mean_position_error"),
        "meanNdcgAt5": _mean("ndcg_at_5"),
        "winnerHitRate": round(winner_hits / scored, 4) if scored else None,
        "podiumHitRate": round(podium_hits / (scored * 3), 4) if scored else None,
        # Additive: the walk-forward headline block.
        "generatedAt": _utc_now_iso(),
        # IndyCar classifies retirees, so scoring covers the whole field.
        "finishersOnly": False,
        "scoring": "pre-race forecast vs the full official classification",
        "walkForward": build_walk_forward_summary(rounds),
    }


def write(out_dir: Path, year: int) -> int:
    rounds = evaluate_season(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in rounds:
        (out_dir / f"round_{_pad2(r['round'])}.json").write_text(json.dumps(r, indent=2) + "\n")
    (out_dir / "season.json").write_text(json.dumps(_season_summary(year, rounds), indent=2) + "\n")
    return len(rounds)


# --------------------------------------------------------------------------- #
# Direct finishing-position head A/B (opt-in; the default path is unchanged)
# --------------------------------------------------------------------------- #
def run_position_head_ab(
    out_dir: Path,
    year: int,
    *,
    min_prior_rounds: int | None = None,
) -> Path | None:
    """Walk-forward A/B of the position head vs the production path.

    Retrains the head on ``< N`` for each completed round N and writes the
    head-to-head comparison (with a data-driven promotion verdict) to
    ``<out_dir>/position_model_ab.json``. Returns the path, or ``None`` when
    there are no completed rounds to score.
    """
    from . import position_head

    if min_prior_rounds is None:
        min_prior_rounds = position_head.DEFAULT_MIN_PRIOR_ROUNDS
    result = position_head.run_backtest(
        IndycarDataSource(), year,
        min_prior_rounds=min_prior_rounds,
        generated_at=_utc_now_iso(),
    )
    if not result.get("roundsScored"):
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "position_model_ab.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    return target


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--season", type=int, default=config.SEASON)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--allow-empty", action="store_true",
                   help="exit 0 even if no rounds are scorable")
    p.add_argument("--position-model-ab", action="store_true",
                   help="Also run the direct finishing-position head walk-forward "
                        "A/B (train on <N, predict N) against the production path "
                        "and write position_model_ab.json into --out.")
    p.add_argument("--min-prior-rounds", type=int, default=None)
    args = p.parse_args()
    n = write(args.out, args.season)
    if n == 0 and not args.allow_empty:
        print("forward_eval: no completed rounds to score", flush=True)
        return 1
    print(f"forward_eval: scored {n} round(s) → {args.out}")

    if args.position_model_ab:
        try:
            ab_path = run_position_head_ab(
                args.out, args.season, min_prior_rounds=args.min_prior_rounds
            )
        except Exception as e:  # never block the primary report
            print(f"forward_eval: position-head A/B failed: {e}")
            ab_path = None
        if ab_path is not None:
            ab = json.loads(ab_path.read_text())
            verdict = ab.get("verdict", {})
            print(
                f"forward_eval: position-head A/B → {verdict.get('recommendation', '—')} "
                f"(head meanErr={verdict.get('positionHeadMeanError')} vs "
                f"prod meanErr={verdict.get('productionMeanError')} over "
                f"{ab.get('roundsCompared', 0)} round(s)) → {ab_path.name}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
