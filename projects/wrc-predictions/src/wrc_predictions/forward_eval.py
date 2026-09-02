"""Forward-time evaluation for WRC — leakage-safe predictions vs actuals.

**This is the headline validation surface for the WRC model.** For every completed
round we re-run the model with *only* prior-round (and prior-season) data and score
its published markets against the actual rally classification. The metrics are the
shared :func:`motorsport_core.eval.score_round` bundle plus per-market Brier /
log-loss, so WRC's accuracy page renders with the same components as the other
series. Scoring is **finishers-only** (retirements are unranked — rally attrition is
huge and largely random, so it is not held against the model).

Rally has no qualifying grid, so the model's competitor is **championship
standings**: in a dominated season the current title order is a very strong
predictor. Two baselines therefore run side-by-side so "is the model beating the
trivial predictor?" is a single read:

* **standings-order** — predict from the championship standings order going into the
  round (rounds strictly before; prior-season final order before round 1). This is
  exactly the geometric-decay form prior the ensemble carries, so it is the hard,
  honest bar. VALIDATED FACT (walk-forward 2023-2026): the **ensemble** of the skill
  model with championship form BEATS this baseline on the live 2026 season (win- and
  podium-Brier both lower) and on podium in every season, even though the skill model
  *alone* loses to standings in the dominated 2026 season — the ensemble is why it
  wins.
* **last-rally** — predict from the previous rally's finishing order.

The headline Brier is the multiclass score summed over the field and normalised per
positive slot (1 winner, 3 podium places), so the win and podium numbers are on a
comparable scale — the figures the model-vs-standings verdict is quoted in.

Outputs (under ``website/public/data/``):
    forward_eval/round_NN.json  per-round rally metrics + per-market Brier + baselines
    forward_eval/season.json    season roll-up + walk-forward + baselineComparison
    model_health.json           drift + rolling-Brier health, forward-eval headline folded

Run:  python -m wrc_predictions.forward_eval --season 2026 [--allow-empty] [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from motorsport_core import calibration, drift, eval as core_eval

from . import config, model
from .datasource import WrcDataSource

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"

# Model-output columns model_health monitors for distribution drift.
_FEATURE_COLUMNS = ("predictedValue", "pWin", "pPodium", "meanFinish", "finishRangeHigh")
_DRIFT_WINDOW = 3


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Baselines: turn an ORDER into a market via the model's geometric-decay prior
# --------------------------------------------------------------------------- #
def _decay_markets(order: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    """(p_win, p_podium) from a full ranking via the same geometric decay the model's
    championship-form prior uses — so a baseline order is scored on the model's own
    probability scale (not an over-confident point mass)."""
    n = len(order)
    dec = np.array([config.FORM_DECAY**i for i in range(n)], dtype=float)
    dec = dec / dec.sum() if dec.sum() else dec
    p_win = {c: float(dec[i]) for i, c in enumerate(order)}
    p_podium = {c: (0.7 if i < 3 else 0.15 if i < 6 else 0.03) for i, c in enumerate(order)}
    return p_win, p_podium


def _standings_order_before(source: WrcDataSource, year: int, rnd: int) -> list[str]:
    """Championship order going INTO ``rnd`` (prior rounds only). Before any round has
    run, falls back to the most recent prior season's final standings order.

    Accumulates the base ``FEATURE_POINTS`` per finish (not the bonus-inclusive real
    totals) so this order is IDENTICAL to the championship-form prior the model's
    ensemble carries — i.e. the standings-order baseline IS the form-prior half of
    the ensemble, which is exactly the validated model-vs-standings comparison."""
    codes = [d["code"] for d in config.DRIVERS]
    pts = {c: 0.0 for c in codes}
    scored = False
    for rr in range(1, rnd):
        for r in source.results(year, rr):
            if r.competitor in pts and r.position is not None:
                pts[r.competitor] += float(config.FEATURE_POINTS.get(r.position, 0))
                scored = True
    if not scored:
        for y in reversed(config.HISTORY_SEASONS):
            snap = config.load_snapshot(y)
            if snap.get("driverStandings"):
                rank = {d["code"]: i for i, d in enumerate(snap["driverStandings"])}
                pts = {c: -float(rank.get(c, len(codes))) for c in codes}
                break
    return sorted(codes, key=lambda c: -pts[c])


def _last_rally_order_before(source: WrcDataSource, year: int, rnd: int) -> list[str] | None:
    """Full ranking with the previous rally's finishers (in finish order) first, then
    the remaining crews. Before round 1, the most recent prior season's final rally."""
    codes = [d["code"] for d in config.DRIVERS]
    prev: dict[str, int] | None = None
    for rr in range(rnd - 1, 0, -1):
        a = {r.competitor: r.position for r in source.results(year, rr) if r.position is not None}
        if a:
            prev = a
            break
    if prev is None:
        for y in reversed(config.HISTORY_SEASONS):
            snap = config.load_snapshot(y)
            if not snap.get("results"):
                continue
            last = max(int(k) for k in snap["results"])
            a = {r.competitor: r.position for r in source.results(y, last) if r.position is not None}
            if a:
                prev = a
                break
    if prev is None:
        return None
    ranked = sorted(prev, key=lambda c: prev[c])
    tail = [c for c in codes if c not in prev]
    return ranked + tail


# --------------------------------------------------------------------------- #
# Scoring helpers
# --------------------------------------------------------------------------- #
def _actuals(source: WrcDataSource, year: int, rnd: int) -> dict[str, int]:
    return {r.competitor: r.position for r in source.results(year, rnd) if r.position is not None}


def _order_to_positions(order: list[str]) -> dict[str, int]:
    return {code: i for i, code in enumerate(order, start=1)}


def _score_order(order: list[str], actual: dict[str, int]) -> dict:
    return core_eval.score_round(_order_to_positions(order), actual)


def _market_scores(p_win, p_podium, actual: dict[str, int]) -> dict:
    """Per-market probability quality (Brier + log-loss) over the classified
    finishers — the MotoGP-parity per-round market view."""
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


def _multiclass_brier(probs, indicator: set[str], field: list[str], slots: int) -> float:
    """Multiclass Brier summed over the field, normalised per positive slot (1 for
    win, 3 for podium) so win and podium land on a comparable scale."""
    return sum((float(probs.get(c, 0.0)) - (1.0 if c in indicator else 0.0)) ** 2 for c in field) / slots


def _headline(p_win, p_podium, actual: dict[str, int]) -> tuple[float, float, bool, str]:
    """(winBrier, podiumBrier, order-leader placeholder unused, winner) — the honest
    headline scores over the classified finishers."""
    field = list(actual.keys())
    winner = min(actual, key=actual.get)
    podset = {c for c, p in actual.items() if p <= 3}
    win_b = _multiclass_brier(p_win, {winner}, field, 1)
    pod_b = _multiclass_brier(p_podium, podset, field, 3)
    return win_b, pod_b, False, winner


def _baseline_block(order: list[str], actual: dict[str, int]) -> dict:
    """Score a deterministic baseline ORDER: positional metrics + the per-market
    Brier of the geometric-decay market whose ranking IS the baseline order."""
    score = _score_order(order, actual)
    p_win, p_podium = _decay_markets(order)
    return {"score": score, "markets": _market_scores(p_win, p_podium, actual)}


def evaluate_season(source: WrcDataSource, year: int) -> list[dict]:
    """Score every completed round, walking forward with leakage-safe replays."""
    rounds: list[dict] = []
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        actual = _actuals(source, year, rnd)
        if not actual:
            continue
        fc = model.forecast_round(source, year, rnd)
        st_order = _standings_order_before(source, year, rnd)
        last_order = _last_rally_order_before(source, year, rnd)

        rounds.append(
            {
                "round": rnd,
                "venueName": fc.venue_name,
                "surface": fc.surface,
                "rally": _score_order(fc.rally.order, actual),
                "markets": _market_scores(
                    fc.rally.markets.p_win, fc.rally.markets.p_podium, actual
                ),
                "baselines": {
                    "standingsOrder": _baseline_block(st_order, actual),
                    "lastRally": _baseline_block(last_order, actual) if last_order else None,
                },
            }
        )
    return rounds


# --------------------------------------------------------------------------- #
# Walk-forward summary
# --------------------------------------------------------------------------- #
def _flatten(score: dict | None, markets: dict | None) -> dict[str, float]:
    """Numeric per-round metric view: ``winner_hit`` -> ``winnerHit`` (0/1); market
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
    """Model + standings-order + last-rally summaries for the single rally head."""
    model_rows = [_flatten(r.get("rally"), r.get("markets")) for r in rounds]
    st_rows = [
        b for b in (_baseline_bundle(r["baselines"]["standingsOrder"]) for r in rounds) if b
    ]
    last_rows = [
        b for b in (_baseline_bundle(r["baselines"]["lastRally"]) for r in rounds) if b
    ]
    return {
        "rally": {
            "model": core_eval.walk_forward_summary(model_rows),
            "baselines": {
                "standingsOrder": core_eval.walk_forward_summary(st_rows),
                "lastRally": core_eval.walk_forward_summary(last_rows),
            },
        }
    }


def _baseline_comparison(source: WrcDataSource, year: int, rounds: list[dict]) -> dict:
    """The honest model-vs-baselines headline (multiclass win/podium Brier + winner-
    hit), over the scored rounds. Reports the validated fact: the ensemble beats the
    standings-order baseline, while the skill model alone loses to it."""
    m_win, m_pod = [], []
    st_win, st_pod = [], []
    lr_win, lr_pod = [], []
    sk_win, sk_pod = [], []
    m_hit = st_hit = lr_hit = 0
    lr_n = 0
    n = 0
    for r in rounds:
        rnd = r["round"]
        actual = _actuals(source, year, rnd)
        if not actual:
            continue
        n += 1
        fc = model.forecast_round(source, year, rnd)
        # Skill-only markets = the raw Plackett-Luce over the skill pace, BEFORE the
        # championship-form ensemble (leakage-safe: estimate_skill reads prior rounds
        # only). This is the honest "does the ensemble help?" comparison.
        pace = model.estimate_skill(source, year, rnd)
        skill_mk = calibration.plackett_luce_probabilities(pace, n_samples=config.DEFAULT_SAMPLES)

        mw, mp, _, winner = _headline(fc.rally.markets.p_win, fc.rally.markets.p_podium, actual)
        m_win.append(mw)
        m_pod.append(mp)
        m_hit += fc.rally.order[0] == winner

        kw, kp, _, _ = _headline(skill_mk.p_win, skill_mk.p_podium, actual)
        sk_win.append(kw)
        sk_pod.append(kp)

        st_order = _standings_order_before(source, year, rnd)
        sw, sp = _decay_markets(st_order)
        w, p, _, _ = _headline(sw, sp, actual)
        st_win.append(w)
        st_pod.append(p)
        st_hit += st_order[0] == winner

        last_order = _last_rally_order_before(source, year, rnd)
        if last_order:
            lr_n += 1
            lw, lp = _decay_markets(last_order)
            w2, p2, _, _ = _headline(lw, lp, actual)
            lr_win.append(w2)
            lr_pod.append(p2)
            lr_hit += last_order[0] == winner

    def _mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 4) if xs else None

    win = {"model": _mean(m_win), "standings": _mean(st_win), "lastRally": _mean(lr_win)}
    pod = {"model": _mean(m_pod), "standings": _mean(st_pod), "lastRally": _mean(lr_pod)}
    win_ok = bool(
        win["model"] is not None
        and win["standings"] is not None
        and win["model"] <= win["standings"]
    )
    pod_ok = bool(
        pod["model"] is not None
        and pod["standings"] is not None
        and pod["model"] <= pod["standings"]
    )
    beats = win_ok and pod_ok
    if beats:
        state = "beats the standings-order baseline on both the win- and podium-Brier"
    elif pod_ok:
        state = (
            "beats the standings-order baseline on podium-Brier but currently "
            "trails it on win-Brier"
        )
    elif win_ok:
        state = (
            "beats the standings-order baseline on win-Brier but currently "
            "trails it on podium-Brier"
        )
    else:
        state = "currently trails the standings-order baseline on win- and podium-Brier"
    return {
        "note": (
            "Headline model is the ENSEMBLE of the surface-aware skill model with a "
            f"championship-form prior. Over the scored rounds it {state}; the skill "
            "model ALONE loses to standings in the dominated season. This field is "
            "descriptive, not a guarantee — the website renders whichever state holds."
        ),
        "roundsScored": n,
        "winBrier": win,
        "podiumBrier": pod,
        "winnerHit": {
            "model": round(m_hit / n, 4) if n else None,
            "standings": round(st_hit / n, 4) if n else None,
            "lastRally": round(lr_hit / lr_n, 4) if lr_n else None,
        },
        "skillOnly": {"winBrier": _mean(sk_win), "podiumBrier": _mean(sk_pod)},
        "beatsStandingsBaseline": beats,
    }


def _season_summary(source: WrcDataSource, year: int, rounds: list[dict]) -> dict:
    def _mean(key: str) -> float | None:
        vals = [
            r["rally"][key]
            for r in rounds
            if r["rally"].get(key) is not None and r["rally"].get("n", 0) > 0
        ]
        return round(sum(vals) / len(vals), 4) if vals else None

    winner_hits = sum(1 for r in rounds if r["rally"].get("winner_hit"))
    podium_hits = sum(r["rally"].get("podium_hits", 0) for r in rounds)
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
        "baselineComparison": _baseline_comparison(source, year, rounds),
    }


# --------------------------------------------------------------------------- #
# model_health.json — drift + rolling Brier, forward-eval headline folded in
# --------------------------------------------------------------------------- #
def _load_round_file(data_dir: Path, rnd: int) -> dict | None:
    path = data_dir / "rounds" / f"round_{_pad2(rnd)}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _rally_records(round_json: dict) -> list[dict]:
    return list(round_json.get("rally", {}).get("classification", []))


def _round_brier(round_json: dict) -> float | None:
    rows = [r for r in _rally_records(round_json) if r.get("actualPosition") is not None]
    if not rows:
        return None
    return sum(
        (float(r.get("pWin", 0.0)) - (1.0 if r["actualPosition"] == 1 else 0.0)) ** 2 for r in rows
    ) / len(rows)


def build_model_health(data_dir: Path, year: int, season_summary: dict) -> dict:
    """Feature-drift + rolling-Brier health from the exported round files, with the
    forward-eval headline (model vs standings vs last-rally) folded in. Mirrors the
    MotoGP model_health shape and adds a ``forwardEval`` summary."""
    completed = [
        rj
        for rnd in range(1, config.COMPLETED_ROUNDS + 1)
        if (rj := _load_round_file(data_dir, rnd)) is not None
    ]
    current = [rec for rj in completed[-_DRIFT_WINDOW:] for rec in _rally_records(rj)]
    baseline = [
        rec for rj in completed[-2 * _DRIFT_WINDOW : -_DRIFT_WINDOW] for rec in _rally_records(rj)
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
    wf = season_summary.get("walkForward", {}).get("rally", {})
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
        "forwardEval": {
            "roundsScored": season_summary.get("roundsScored", 0),
            "meanPositionError": season_summary.get("meanPositionError"),
            "winnerHitRate": season_summary.get("winnerHitRate"),
            "podiumHitRate": season_summary.get("podiumHitRate"),
            "walkForward": {"rally": wf} if wf else {},
            "baselineComparison": season_summary.get("baselineComparison"),
        },
    }
    return payload


# --------------------------------------------------------------------------- #
def write(data_dir: Path, year: int) -> int:
    """Write ``forward_eval/*.json`` under ``data_dir`` and ``data_dir/model_health.json``.
    Returns the number of rounds scored."""
    source = WrcDataSource()
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
    bc = season.get("baselineComparison", {})
    win = bc.get("winBrier", {})
    pod = bc.get("podiumBrier", {})
    print(
        f"forward_eval: scored {n} round(s) -> {args.out}/forward_eval\n"
        f"  win-Brier    model={win.get('model')} standings={win.get('standings')} "
        f"last-rally={win.get('lastRally')} (skill-only={bc.get('skillOnly', {}).get('winBrier')})\n"
        f"  podium-Brier model={pod.get('model')} standings={pod.get('standings')} "
        f"last-rally={pod.get('lastRally')}\n"
        f"  beats standings baseline: {bc.get('beatsStandingsBaseline')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
