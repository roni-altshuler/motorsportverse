"""Forward-time evaluation for F2 — scores leakage-safe predictions vs actuals.

**This is the headline validation surface for the F2 model** (F1-parity, commit
189db5b). For every completed round we re-run the model with *only* prior-round
data (the same leakage-safe forecast the website shows pre-race) and score it
against the actual classification, per race-type and pooled. The metrics are
the shared :func:`motorsport_core.eval.score_round` bundle, so F2's accuracy
page renders with the same components as F1's. Scoring is **finishers-only**:
the actual classifications carry classified finishers exclusively (retirements
are unranked), so every metric compares the prediction to drivers who took the
flag — the same convention as the F1 flagship's headline accuracy.

The season is scored by walking forward one completed round at a time and
aggregating the per-round metrics via
:func:`motorsport_core.eval.walk_forward_summary` (mean / median / min / max /
last / OLS-trend per metric), model and last-race baseline side-by-side —
"is the model beating the trivial predictor over time?" is a single read.

Outputs (under ``website/public/data/forward_eval/``):
    round_NN.json           per-round sprint + feature metrics (original shape,
                            extended additively with per-market ``markets``
                            Brier/log-loss and a last-race ``baselines`` block)
    season.json             season roll-up (original keys, extended additively
                            with the ``walkForward`` model-vs-baseline summary)
    position_model_ab.json  (opt-in, ``--position-model-ab``) walk-forward A/B
                            of the direct finishing-position head vs production

Run:  python -m f2_predictions.forward_eval --season 2026 [--allow-empty]
          [--out <dir>] [--position-model-ab] [--min-prior-rounds N]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from motorsport_core import eval as core_eval

from . import config, model, pipeline
from .datasource import F2DataSource

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data" / "forward_eval"

RACE_TYPES = (model.SPRINT, model.FEATURE)


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _score_race(fc_race, actual: dict[str, int]) -> dict:
    predicted = {code: i for i, code in enumerate(fc_race.order, start=1)}
    return core_eval.score_round(predicted, actual)


def _market_scores(fc_race, actual: dict[str, int]) -> dict:
    """Per-market probability quality (Brier + log-loss) for one race.

    Scores the model's win and podium probabilities against the realised binary
    outcomes over the classified finishers — the per-market headline metrics the
    F1 flagship reports alongside positional accuracy.
    """
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


def _actuals(source: F2DataSource, year: int, rnd: int) -> dict[str, dict[str, int]]:
    races = source.race_results_for_round(year, rnd)
    return {
        rt: {r.competitor: r.position for r in races[rt] if r.position is not None}
        for rt in RACE_TYPES
    }


def evaluate_season(year: int) -> list[dict]:
    """Score every completed round, walking forward with leakage-safe replays.

    Each per-round dict keeps the original ``round``/``venueName``/``sprint``/
    ``feature`` shape (the website reads it) and gains two additive blocks:
    ``markets`` (win/podium Brier + log-loss per race type) and ``baselines``
    (the previous completed round's actual order re-scored as the prediction —
    ``None`` for round 1, which has no prior race).
    """
    source = F2DataSource()
    rounds: list[dict] = []
    prev_actual: dict[str, dict[str, int]] | None = None
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        fc = pipeline.forecast_round(source, year, rnd)
        actual = _actuals(source, year, rnd)
        if not actual[model.FEATURE]:
            continue
        baselines: dict[str, dict | None] = {rt: None for rt in RACE_TYPES}
        if prev_actual is not None:
            for rt in RACE_TYPES:
                if prev_actual.get(rt):
                    baseline_pred = core_eval.last_order_baseline(prev_actual[rt])
                    baselines[rt] = core_eval.score_round(baseline_pred, actual[rt])
        rounds.append(
            {
                "round": rnd,
                "venueName": fc.venue_name,
                "sprint": _score_race(fc.sprint, actual[model.SPRINT]),
                "feature": _score_race(fc.feature, actual[model.FEATURE]),
                "markets": {
                    rt: _market_scores(getattr(fc, rt), actual[rt]) for rt in RACE_TYPES
                },
                "baselines": baselines,
            }
        )
        prev_actual = actual
    return rounds


# --------------------------------------------------------------------------- #
# Walk-forward summary (headline validation surface)
# --------------------------------------------------------------------------- #
def _round_metric_bundle(r: dict, race_type: str) -> dict[str, float]:
    """Numeric per-round metric view for :func:`walk_forward_summary`.

    ``winner_hit`` (bool) becomes ``winnerHit`` (0/1) so it survives the
    summary (which skips bools); the per-market Brier / log-loss are folded in
    flat (``winBrier`` ...) so probability quality trends alongside accuracy.
    """
    score = r.get(race_type) or {}
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
    for market, metrics in (r.get("markets", {}).get(race_type) or {}).items():
        for name, val in (metrics or {}).items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[f"{market}{name[0].upper()}{name[1:]}"] = float(val)
    return out


def _baseline_metric_bundle(r: dict, race_type: str) -> dict[str, float] | None:
    score = (r.get("baselines") or {}).get(race_type)
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
    """Aggregate every scored round into a model-vs-baseline walk-forward block.

    Wraps :func:`motorsport_core.eval.walk_forward_summary` over the season's
    per-round metric dicts, keeping the model's summary and the last-race
    baseline's summary side-by-side, per race type — the season-level headline
    surface (F1's ``forward_eval/summary.json`` shape, embedded in F2's
    ``season.json``).
    """
    out: dict[str, dict] = {}
    for rt in RACE_TYPES:
        model_rows = [_round_metric_bundle(r, rt) for r in rounds]
        baseline_rows = [
            b for b in (_baseline_metric_bundle(r, rt) for r in rounds) if b is not None
        ]
        out[rt] = {
            "model": core_eval.walk_forward_summary(model_rows),
            "baselines": {"lastRace": core_eval.walk_forward_summary(baseline_rows)},
        }
    return out


def _season_summary(year: int, rounds: list[dict]) -> dict:
    def _mean(key: str) -> float | None:
        vals = [
            r["feature"][key]
            for r in rounds
            if r["feature"].get(key) is not None and r["feature"].get("n", 0) > 0
        ]
        return round(sum(vals) / len(vals), 4) if vals else None

    winner_hits = sum(1 for r in rounds if r["feature"].get("winner_hit"))
    podium_hits = sum(r["feature"].get("podium_hits", 0) for r in rounds)
    scored = len(rounds)
    return {
        # Original keys — the website reads these; never rename/remove.
        "season": year,
        "roundsScored": scored,
        "meanPositionError": _mean("mean_position_error"),
        "meanNdcgAt5": _mean("ndcg_at_5"),
        "winnerHitRate": round(winner_hits / scored, 4) if scored else None,
        "podiumHitRate": round(podium_hits / (scored * 3), 4) if scored else None,
        # Additive: the walk-forward headline block (F1 parity).
        "generatedAt": _utc_now_iso(),
        "finishersOnly": True,
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
    head-to-head comparison (per race type + pooled, with a data-driven
    promotion verdict) to ``<out_dir>/position_model_ab.json``. Returns the
    path, or ``None`` when there are no completed rounds to score.
    """
    from . import position_head

    if min_prior_rounds is None:
        min_prior_rounds = position_head.DEFAULT_MIN_PRIOR_ROUNDS
    result = position_head.run_backtest(
        F2DataSource(), year,
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
    p.add_argument("--allow-empty", action="store_true", help="exit 0 even if no rounds are scorable")
    p.add_argument("--position-model-ab", action="store_true",
                   help="Also run the direct finishing-position head walk-forward "
                        "A/B (train on <N, predict N) against the production path "
                        "and write position_model_ab.json into --out.")
    p.add_argument("--min-prior-rounds", type=int, default=None,
                   help="Minimum prior completed rounds before the position head "
                        "trains (default 2; below this a round is recorded "
                        "applied:false and excluded from the head-to-head).")
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
