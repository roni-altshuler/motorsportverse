"""Forward-time evaluation for MotoGP — leakage-safe predictions vs actuals.

**This is the headline validation surface for the MotoGP model.** For every
completed round we re-run the model with *only* prior-round data — conditioned on
that round's real qualifying grid (an input, not the label: qualifying runs before
the race), which is the **post-quali** production surface the website shows — and
score it against the actual classification, per race-type and pooled. The metrics
are the shared :func:`motorsport_core.eval.score_round` bundle plus per-market
Brier / log-loss, so MotoGP's accuracy page renders with the same components as
F1/F3. Scoring is **finishers-only** (retirements are unranked).

Two baselines run side-by-side so "is the model beating the trivial predictor?"
is a single read:

* **grid-order** — predict the finishing order = the real qualifying grid. This is
  the bar the post-quali model must clear; MotoGP qualifying is hugely predictive,
  so a form-only (pre-quali) order does *not* beat it, but the grid-conditioned
  model does (win- and podium-Brier both lower — see ``config.GRID_WEIGHT``).
* **last-standings-order** — predict the order = the championship standings going
  into the round (rounds strictly before, leakage-safe).

The season is scored by walking forward one round at a time and aggregating via
:func:`motorsport_core.eval.walk_forward_summary` (mean / median / min / max /
last / OLS-trend per metric), model and both baselines together. A
``phaseComparison`` block records the honest post-quali-vs-pre-quali-vs-grid story.

Outputs (under ``website/public/data/``):
    forward_eval/round_NN.json  per-round sprint + GP metrics + per-market Brier +
                                the two baselines
    forward_eval/season.json    season roll-up + walk-forward model-vs-baselines
    model_health.json           drift + rolling-Brier health, with the forward-eval
                                headline folded in

Run:  python -m motogp_predictions.forward_eval --season 2026 [--allow-empty] [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from motorsport_core import calibration, drift, eval as core_eval, standings

from . import config, model
from .datasource import MotoGPDataSource

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"

RACE_TYPES = (model.SPRINT, model.FEATURE)
# Race-head temperatures (match the model heads) so the baselines are scored with
# the same Monte-Carlo variance structure — only the *pace* differs (pure grid /
# pure standings vs skill+grid), making the Brier comparison apples-to-apples.
_TEMPERATURE = {model.FEATURE: 0.5, model.SPRINT: 0.5 + config.SPRINT_TEMPERATURE_BOOST}

# Model-output columns model_health monitors for distribution drift.
_FEATURE_COLUMNS = ("predictedValue", "pWin", "pPodium", "meanFinish", "finishRangeHigh")
_DRIFT_WINDOW = 3


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Scoring helpers
# --------------------------------------------------------------------------- #
def _order_to_positions(order: list[str]) -> dict[str, int]:
    return {code: i for i, code in enumerate(order, start=1)}


def _score_order(order: list[str], actual: dict[str, int]) -> dict:
    return core_eval.score_round(_order_to_positions(order), actual)


def _market_scores(p_win, p_podium, actual: dict[str, int]) -> dict:
    """Per-market probability quality (Brier + log-loss) for one race, over the
    classified finishers."""
    if not actual:
        return {}
    winner = min(actual, key=actual.get)
    win_outcomes = {c: 1.0 if c == winner else 0.0 for c in actual}
    podium = {c for c, p in actual.items() if p <= 3}
    podium_outcomes = {c: 1.0 if c in podium else 0.0 for c in actual}
    out: dict[str, dict] = {}
    for market, probs, outcomes in (
        ("win", p_win, win_outcomes),
        ("podium", p_podium, podium_outcomes),
    ):
        brier = core_eval.brier_score(probs, outcomes)
        ll = core_eval.log_loss(probs, outcomes)
        out[market] = {
            "brier": round(brier, 6) if brier is not None else None,
            "logLoss": round(ll, 6) if ll is not None else None,
        }
    return out


def _actuals(source: MotoGPDataSource, year: int, rnd: int) -> dict[str, dict[str, int]]:
    races = source.race_results_for_round(year, rnd)
    return {
        rt: {r.competitor: r.position for r in races[rt] if r.position is not None}
        for rt in RACE_TYPES
    }


def _standings_order_before(source: MotoGPDataSource, year: int, rnd: int) -> list[str] | None:
    """Championship order going INTO ``rnd`` (rounds strictly before). None for R1."""
    if rnd <= 1:
        return None
    sprints, features = [], []
    for r in range(1, rnd):
        races = source.race_results_for_round(year, r)
        sprints.append({res.competitor: res.position for res in races["sprint"]})
        features.append({res.competitor: res.position for res in races["feature"]})
    merged = standings.merge_standings(
        standings.compute_driver_standings(sprints, config.SPRINT_POINTS),
        standings.compute_driver_standings(features, config.FEATURE_POINTS),
    )
    order = [row.key for row in merged]
    return order or None


def _baseline_block(order: list[str], actual: dict[str, int], temperature: float) -> dict:
    """Score a deterministic baseline ORDER: positional metrics + the per-market
    Brier of a Plackett-Luce forecast whose pace IS the baseline order (P1 = best)."""
    score = _score_order(order, actual)
    pace = {code: float(i + 1) for i, code in enumerate(order)}
    mkts = calibration.plackett_luce_probabilities(
        pace, n_samples=config.DEFAULT_SAMPLES, temperature=temperature
    )
    return {"score": score, "markets": _market_scores(mkts.p_win, mkts.p_podium, actual)}


def evaluate_season(source: MotoGPDataSource, year: int) -> list[dict]:
    """Score every completed round, walking forward with leakage-safe replays."""
    rounds: list[dict] = []
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        actual = _actuals(source, year, rnd)
        if not actual[model.FEATURE]:
            continue
        grid = source.qualifying(year, rnd)  # real quali → post-quali forecast + grid baseline
        fc = model.forecast_round(source, year, rnd, known_grid=grid)

        grid_baselines: dict[str, dict | None] = {rt: None for rt in RACE_TYPES}
        standings_baselines: dict[str, dict | None] = {rt: None for rt in RACE_TYPES}
        st_order = _standings_order_before(source, year, rnd)
        for rt in RACE_TYPES:
            if grid:
                grid_baselines[rt] = _baseline_block(grid, actual[rt], _TEMPERATURE[rt])
            if st_order:
                standings_baselines[rt] = _baseline_block(st_order, actual[rt], _TEMPERATURE[rt])

        rounds.append(
            {
                "round": rnd,
                "venueName": fc.venue_name,
                "sprint": _score_order(fc.sprint.order, actual[model.SPRINT]),
                "feature": _score_order(fc.feature.order, actual[model.FEATURE]),
                "markets": {
                    rt: _market_scores(
                        getattr(fc, rt).markets.p_win,
                        getattr(fc, rt).markets.p_podium,
                        actual[rt],
                    )
                    for rt in RACE_TYPES
                },
                "baselines": {
                    "gridOrder": grid_baselines,
                    "lastStandings": standings_baselines,
                },
            }
        )
    return rounds


# --------------------------------------------------------------------------- #
# Walk-forward summary (headline validation surface)
# --------------------------------------------------------------------------- #
def _flatten(score: dict | None, markets: dict | None) -> dict[str, float]:
    """Numeric per-round metric view: ``winner_hit`` → ``winnerHit`` (0/1); market
    Brier/log-loss folded flat (``winBrier`` ...) so probability quality trends too."""
    out: dict[str, float] = {}
    for key, val in (score or {}).items():
        if key == "n":
            continue
        if key == "winner_hit":
            out["winnerHit"] = 1.0 if val else 0.0
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        out[key] = float(val)
    for market, metrics in (markets or {}).items():
        for name, val in (metrics or {}).items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[f"{market}{name[0].upper()}{name[1:]}"] = float(val)
    return out


def _baseline_bundle(entry: dict | None) -> dict[str, float] | None:
    if not entry:
        return None
    return _flatten(entry.get("score"), entry.get("markets"))


def build_walk_forward_summary(rounds: list[dict]) -> dict:
    """Model + grid-order + last-standings summaries, per race type (F1/F3 shape)."""
    out: dict[str, dict] = {}
    for rt in RACE_TYPES:
        model_rows = [_flatten(r.get(rt), r.get("markets", {}).get(rt)) for r in rounds]
        grid_rows = [
            b
            for b in (_baseline_bundle(r["baselines"]["gridOrder"].get(rt)) for r in rounds)
            if b is not None
        ]
        st_rows = [
            b
            for b in (_baseline_bundle(r["baselines"]["lastStandings"].get(rt)) for r in rounds)
            if b is not None
        ]
        out[rt] = {
            "model": core_eval.walk_forward_summary(model_rows),
            "baselines": {
                "gridOrder": core_eval.walk_forward_summary(grid_rows),
                "lastStandings": core_eval.walk_forward_summary(st_rows),
            },
        }
    return out


def _phase_comparison(source: MotoGPDataSource, year: int, rounds: list[dict]) -> dict:
    """The honest post-quali vs pre-quali vs grid story on the Grand Prix, over the
    scored rounds — the validated fact the config's GRID_WEIGHT was tuned on."""
    post_win, pre_win, grid_win = [], [], []
    post_pod, pre_pod, grid_pod = [], [], []
    post_hit = pre_hit = grid_hit = 0
    n = 0
    for r in rounds:
        rnd = r["round"]
        actual = _actuals(source, year, rnd)[model.FEATURE]
        if not actual:
            continue
        n += 1
        winner = min(actual, key=actual.get)
        grid = source.qualifying(year, rnd)
        post = model.forecast_round(source, year, rnd, known_grid=grid).feature
        pre = model.forecast_round(source, year, rnd).feature
        gm = calibration.plackett_luce_probabilities(
            {c: float(i + 1) for i, c in enumerate(grid)},
            n_samples=config.DEFAULT_SAMPLES,
            temperature=_TEMPERATURE[model.FEATURE],
        )
        win_out = {c: 1.0 if c == winner else 0.0 for c in actual}
        pod = {c for c, p in actual.items() if p <= 3}
        pod_out = {c: 1.0 if c in pod else 0.0 for c in actual}
        post_win.append(core_eval.brier_score(post.markets.p_win, win_out))
        pre_win.append(core_eval.brier_score(pre.markets.p_win, win_out))
        grid_win.append(core_eval.brier_score(gm.p_win, win_out))
        post_pod.append(core_eval.brier_score(post.markets.p_podium, pod_out))
        pre_pod.append(core_eval.brier_score(pre.markets.p_podium, pod_out))
        grid_pod.append(core_eval.brier_score(gm.p_podium, pod_out))
        post_hit += post.order[0] == winner
        pre_hit += pre.order[0] == winner
        grid_hit += grid[0] == winner if grid else 0

    def _mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 6) if xs else None

    win = {"post": _mean(post_win), "pre": _mean(pre_win), "grid": _mean(grid_win)}
    pod = {"post": _mean(post_pod), "pre": _mean(pre_pod), "grid": _mean(grid_pod)}
    win_ok = bool(
        win["post"] is not None and win["grid"] is not None and win["post"] < win["grid"]
    )
    pod_ok = bool(
        pod["post"] is not None and pod["grid"] is not None and pod["post"] < pod["grid"]
    )
    beats = win_ok and pod_ok
    if beats:
        state = "beats the raw-grid baseline on both the win- and podium-Brier"
    elif pod_ok:
        state = "beats the raw-grid baseline on podium-Brier but currently trails it on win-Brier"
    elif win_ok:
        state = "beats the raw-grid baseline on win-Brier but currently trails it on podium-Brier"
    else:
        state = "currently trails the raw-grid baseline on win- and podium-Brier"
    return {
        "note": (
            "Headline model is POST-quali (grid-conditioned). Over the scored rounds "
            f"it {state}. This field is descriptive, not a guarantee — the website "
            "renders whichever state holds."
        ),
        "roundsScored": n,
        "feature": {
            "winBrier": win,
            "podiumBrier": pod,
            "winnerHit": {
                "post": round(post_hit / n, 4) if n else None,
                "pre": round(pre_hit / n, 4) if n else None,
                "grid": round(grid_hit / n, 4) if n else None,
            },
        },
        "beatsGridBaseline": beats,
    }


def _season_summary(source: MotoGPDataSource, year: int, rounds: list[dict]) -> dict:
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
        "season": year,
        "roundsScored": scored,
        "meanPositionError": _mean("mean_position_error"),
        "meanNdcgAt5": _mean("ndcg_at_5"),
        "winnerHitRate": round(winner_hits / scored, 4) if scored else None,
        "podiumHitRate": round(podium_hits / (scored * 3), 4) if scored else None,
        "generatedAt": _utc_now_iso(),
        "finishersOnly": True,
        "walkForward": build_walk_forward_summary(rounds),
        "phaseComparison": _phase_comparison(source, year, rounds),
    }


# --------------------------------------------------------------------------- #
# model_health.json — drift + rolling Brier, with the forward-eval headline folded
# --------------------------------------------------------------------------- #
def _load_round_file(data_dir: Path, rnd: int) -> dict | None:
    path = data_dir / "rounds" / f"round_{_pad2(rnd)}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _feature_records(round_json: dict) -> list[dict]:
    return list(round_json.get("feature", {}).get("classification", []))


def _round_brier(round_json: dict) -> float | None:
    rows = [r for r in _feature_records(round_json) if r.get("actualPosition") is not None]
    if not rows:
        return None
    return sum(
        (float(r.get("pWin", 0.0)) - (1.0 if r["actualPosition"] == 1 else 0.0)) ** 2 for r in rows
    ) / len(rows)


def build_model_health(data_dir: Path, year: int, season_summary: dict) -> dict:
    """Feature-drift + rolling-Brier health from the exported round files, with the
    forward-eval headline (model vs grid vs standings) folded in. Mirrors F3's
    model_health shape and adds a ``forwardEval`` summary."""
    completed = [
        rj
        for rnd in range(1, config.COMPLETED_ROUNDS + 1)
        if (rj := _load_round_file(data_dir, rnd)) is not None
    ]
    current = [rec for rj in completed[-_DRIFT_WINDOW:] for rec in _feature_records(rj)]
    baseline = [
        rec for rj in completed[-2 * _DRIFT_WINDOW : -_DRIFT_WINDOW] for rec in _feature_records(rj)
    ]
    brier_by_round = [(rj["round"], b) for rj in completed if (b := _round_brier(rj)) is not None]
    last_round = completed[-1]["round"] if completed else None
    report = drift.build_health_report(
        season=year,
        last_evaluated_round=last_round,
        baseline_records=baseline,
        current_records=current,
        feature_columns=_FEATURE_COLUMNS,
        brier_by_round=brier_by_round,
    )
    wf = season_summary.get("walkForward", {}).get(model.FEATURE, {})
    payload = {
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
        # Folded forward-eval headline (the honest model-vs-baseline story).
        "forwardEval": {
            "roundsScored": season_summary.get("roundsScored", 0),
            "meanPositionError": season_summary.get("meanPositionError"),
            "winnerHitRate": season_summary.get("winnerHitRate"),
            "podiumHitRate": season_summary.get("podiumHitRate"),
            "walkForward": {"feature": wf} if wf else {},
            "phaseComparison": season_summary.get("phaseComparison"),
        },
    }
    return payload


# --------------------------------------------------------------------------- #
def write(data_dir: Path, year: int) -> int:
    """Write ``forward_eval/*.json`` under ``data_dir`` and ``data_dir/model_health.json``.
    Returns the number of rounds scored."""
    source = MotoGPDataSource()
    rounds = evaluate_season(source, year)
    fe_dir = data_dir / "forward_eval"
    fe_dir.mkdir(parents=True, exist_ok=True)
    for r in rounds:
        (fe_dir / f"round_{_pad2(r['round'])}.json").write_text(json.dumps(r, indent=2) + "\n")
    season = _season_summary(source, year, rounds)
    (fe_dir / "season.json").write_text(json.dumps(season, indent=2) + "\n")

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "model_health.json").write_text(
        json.dumps(build_model_health(data_dir, year, season), indent=2) + "\n"
    )
    return len(rounds)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--season", type=int, default=config.SEASON)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="the website data root")
    p.add_argument("--allow-empty", action="store_true", help="exit 0 even if no rounds scorable")
    args = p.parse_args()
    n = write(args.out, args.season)
    if n == 0 and not args.allow_empty:
        print("forward_eval: no completed rounds to score", flush=True)
        return 1
    season = json.loads((args.out / "forward_eval" / "season.json").read_text())
    pc = season.get("phaseComparison", {}).get("feature", {})
    win = pc.get("winBrier", {})
    pod = pc.get("podiumBrier", {})
    print(
        f"forward_eval: scored {n} round(s) → {args.out}/forward_eval\n"
        f"  win-Brier    model={win.get('post')} grid={win.get('grid')} "
        f"(pre-quali={win.get('pre')})\n"
        f"  podium-Brier model={pod.get('post')} grid={pod.get('grid')} "
        f"(pre-quali={pod.get('pre')})\n"
        f"  beats grid baseline: {season.get('phaseComparison', {}).get('beatsGridBaseline')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
