"""Replay-backtest the value-finder over completed rounds.

For each completed round R in the season:

    1. Load `website/public/data/probabilities/round_NN.json` (model output).
    2. Load the latest `odds_cache/round_NN_*.json` snapshot.
    3. Read actuals from `season_results_<season>.json` (winner only — v1).
    4. Build opportunities just like `export_value_data` does.
    5. Simulate placing each (capped) Kelly bet:
         - won = (driver == actual winner)
         - pnl = stake * (odds - 1) if won else -stake
    6. Update the equity curve.

Outputs:
    - JSON report at `--output` containing per-round rollups and the full
      ledger of placed bets.
    - DuckDB rows in `data/betting.duckdb` (`backtest_runs`, `placed_bets`).

Run metrics:
    - total_bets, hit_rate, ROI, equity curve.
    - Sharpe + max drawdown only when >= 5 completed rounds — under that the
      numbers are noise and would be misleading on the dashboard.

Currently only round 4 has actuals (`season_results_2026.json`); the script
deliberately handles N=1 gracefully so the structure is verifiable today.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3  # used as a stdlib fallback if duckdb is missing
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bet_sizing import cap_portfolio, expected_value, kelly_fraction
from f1_prediction_utils import DRIVER_FULL_NAMES
from odds_ingest import devig_proportional, load_cached_payload

PROJECT_ROOT = Path(__file__).resolve().parent
PROBS_DIR = PROJECT_ROOT / "website" / "public" / "data" / "probabilities"
ODDS_CACHE_DIR = PROJECT_ROOT / "odds_cache"
DATA_DIR = PROJECT_ROOT / "data"
DUCKDB_PATH = DATA_DIR / "betting.duckdb"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PlacedBet:
    run_id: str
    round: int
    driver: str
    market: str
    stake: float
    decimal_odds: float
    model_p: float
    market_p: float
    won: bool
    pnl: float


@dataclass
class RoundResult:
    round: int
    bets: list[PlacedBet]
    pnl: float
    stake_total: float
    bankroll_before: float
    bankroll_after: float

    def roi(self) -> float | None:
        return self.pnl / self.stake_total if self.stake_total > 0 else None


@dataclass
class BacktestRun:
    run_id: str
    config: dict
    started_at: str
    rounds: list[RoundResult] = field(default_factory=list)
    total_bets: int = 0
    hit_rate: float = 0.0
    roi: float = 0.0
    sharpe: float | None = None
    max_drawdown: float | None = None
    equity_curve: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_actuals(season: int, season_results_path: Path | None = None) -> dict[int, dict[str, int]]:
    path = season_results_path or (PROJECT_ROOT / f"season_results_{season}.json")
    if not path.exists():
        return {}
    with path.open() as f:
        raw = json.load(f)
    out: dict[int, dict[str, int]] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        try:
            r = int(k)
        except (TypeError, ValueError):
            continue
        if isinstance(v, dict):
            cleaned: dict[str, int] = {}
            for drv, pos in v.items():
                value = pos.get("position") if isinstance(pos, dict) else pos
                try:
                    cleaned[str(drv)] = int(value)
                except (TypeError, ValueError):
                    continue
            if cleaned:
                out[r] = cleaned
    return out


def _completed_rounds(actuals: dict[int, dict[str, int]]) -> list[int]:
    return sorted(actuals.keys())


def _latest_odds_for_round(round_number: int, odds_dir: Path) -> Path | None:
    if not odds_dir.exists():
        return None
    cands = sorted(odds_dir.glob(f"round_{round_number:02d}_*.json"))
    return cands[-1] if cands else None


def _read_probs(round_number: int, probs_dir: Path) -> dict | None:
    path = probs_dir / f"round_{round_number:02d}.json"
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Bookmaker pick (consistent with export_value_data)
# ---------------------------------------------------------------------------


def _select_book(books: dict[str, dict[str, float]]) -> str:
    from export_value_data import select_bookmaker

    return select_bookmaker(books)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


def _simulate_round(
    run_id: str,
    round_number: int,
    probs: dict,
    odds_path: Path,
    actual_winner: str,
    bankroll_before: float,
    *,
    kelly_fraction_mult: float,
    per_bet_cap: float,
    total_cap: float,
) -> RoundResult:
    books = load_cached_payload(odds_path)
    if not books:
        return RoundResult(
            round=round_number, bets=[], pnl=0.0, stake_total=0.0,
            bankroll_before=bankroll_before, bankroll_after=bankroll_before,
        )
    book = _select_book(books)
    market_odds = books[book]
    market_probs = devig_proportional(market_odds)

    win_probs = (probs.get("markets") or {}).get("win") or []

    raw_rows: list[dict] = []
    for entry in win_probs:
        code = entry.get("driver")
        mp = entry.get("probability")
        if not isinstance(code, str) or not isinstance(mp, (int, float)):
            continue
        if code not in market_odds or code not in market_probs:
            continue
        odds = float(market_odds[code])
        k = kelly_fraction(float(mp), odds, fraction=kelly_fraction_mult)
        raw_rows.append({
            "driver": code,
            "marketOdds": odds,
            "modelP": float(mp),
            "marketP": float(market_probs[code]),
            "kellyFraction": k,
        })

    rows = cap_portfolio(raw_rows, per_bet_cap=per_bet_cap, total_cap=total_cap)

    placed: list[PlacedBet] = []
    pnl_total = 0.0
    stake_total = 0.0
    for row in rows:
        kf = float(row["kellyFraction"])
        if kf <= 0.0:
            continue
        stake = kf * bankroll_before
        won = row["driver"] == actual_winner
        pnl = stake * (row["marketOdds"] - 1.0) if won else -stake
        pnl_total += pnl
        stake_total += stake
        placed.append(PlacedBet(
            run_id=run_id,
            round=round_number,
            driver=row["driver"],
            market="win",
            stake=stake,
            decimal_odds=row["marketOdds"],
            model_p=row["modelP"],
            market_p=row["marketP"],
            won=won,
            pnl=pnl,
        ))

    return RoundResult(
        round=round_number,
        bets=placed,
        pnl=pnl_total,
        stake_total=stake_total,
        bankroll_before=bankroll_before,
        bankroll_after=bankroll_before + pnl_total,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _sharpe(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    sd = math.sqrt(var)
    if sd == 0.0:
        return None
    return mean / sd


def _max_drawdown(equity: list[float]) -> float | None:
    if len(equity) < 2:
        return None
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def _finalize_run(run: BacktestRun) -> None:
    run.equity_curve = [run.config["bankroll"]]
    eq = run.config["bankroll"]
    round_returns: list[float] = []
    for rr in run.rounds:
        if rr.stake_total > 0:
            round_returns.append(rr.pnl / rr.stake_total)
        eq += rr.pnl
        run.equity_curve.append(eq)

    run.total_bets = sum(len(rr.bets) for rr in run.rounds)
    wins = sum(1 for rr in run.rounds for b in rr.bets if b.won)
    run.hit_rate = wins / run.total_bets if run.total_bets else 0.0

    total_stake = sum(rr.stake_total for rr in run.rounds)
    total_pnl = sum(rr.pnl for rr in run.rounds)
    run.roi = total_pnl / total_stake if total_stake else 0.0

    # Sharpe + drawdown only meaningful with enough rounds.
    if len(run.rounds) >= 5:
        run.sharpe = _sharpe(round_returns)
        run.max_drawdown = _max_drawdown(run.equity_curve)


# ---------------------------------------------------------------------------
# Persistence (DuckDB w/ sqlite fallback for sandboxes without duckdb)
# ---------------------------------------------------------------------------


def _persist(run: BacktestRun, db_path: Path = DUCKDB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import duckdb

        con = duckdb.connect(str(db_path))
        con.execute(
            "CREATE TABLE IF NOT EXISTS backtest_runs ("
            "run_id VARCHAR, config_json VARCHAR, started_at VARCHAR, "
            "total_bets INTEGER, hit_rate DOUBLE, roi DOUBLE, "
            "sharpe DOUBLE, max_drawdown DOUBLE)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS placed_bets ("
            "run_id VARCHAR, round INTEGER, driver VARCHAR, market VARCHAR, "
            "stake DOUBLE, decimal_odds DOUBLE, model_p DOUBLE, market_p DOUBLE, "
            "won BOOLEAN, pnl DOUBLE)"
        )
        con.execute(
            "INSERT INTO backtest_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run.run_id, json.dumps(run.config), run.started_at,
                run.total_bets, run.hit_rate, run.roi,
                run.sharpe, run.max_drawdown,
            ],
        )
        for rr in run.rounds:
            for b in rr.bets:
                con.execute(
                    "INSERT INTO placed_bets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [b.run_id, b.round, b.driver, b.market, b.stake, b.decimal_odds,
                     b.model_p, b.market_p, b.won, b.pnl],
                )
        con.close()
    except ImportError:
        # Fallback: sqlite at same path (different format but useful for sandbox).
        con = sqlite3.connect(str(db_path.with_suffix(".sqlite")))
        con.execute(
            "CREATE TABLE IF NOT EXISTS backtest_runs ("
            "run_id TEXT, config_json TEXT, started_at TEXT, "
            "total_bets INTEGER, hit_rate REAL, roi REAL, "
            "sharpe REAL, max_drawdown REAL)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS placed_bets ("
            "run_id TEXT, round INTEGER, driver TEXT, market TEXT, "
            "stake REAL, decimal_odds REAL, model_p REAL, market_p REAL, "
            "won INTEGER, pnl REAL)"
        )
        con.execute(
            "INSERT INTO backtest_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run.run_id, json.dumps(run.config), run.started_at,
             run.total_bets, run.hit_rate, run.roi,
             run.sharpe, run.max_drawdown),
        )
        for rr in run.rounds:
            for b in rr.bets:
                con.execute(
                    "INSERT INTO placed_bets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (b.run_id, b.round, b.driver, b.market, b.stake, b.decimal_odds,
                     b.model_p, b.market_p, int(b.won), b.pnl),
                )
        con.commit()
        con.close()


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------


def run_backtest(
    season: int,
    *,
    bankroll: float = 1000.0,
    kelly_fraction_mult: float = 0.25,
    per_bet_cap: float = 0.05,
    total_cap: float = 0.30,
    probs_dir: Path = PROBS_DIR,
    odds_dir: Path = ODDS_CACHE_DIR,
    season_results_path: Path | None = None,
    persist: bool = True,
    db_path: Path = DUCKDB_PATH,
) -> BacktestRun:
    actuals = _load_actuals(season, season_results_path)
    rounds = _completed_rounds(actuals)
    config = {
        "season": season,
        "bankroll": bankroll,
        "kelly_fraction": kelly_fraction_mult,
        "per_bet_cap": per_bet_cap,
        "total_cap": total_cap,
    }
    run = BacktestRun(
        run_id=str(uuid.uuid4()),
        config=config,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    eq = bankroll
    for r in rounds:
        probs = _read_probs(r, probs_dir)
        if probs is None:
            print(f"[backtest] WARN: no probabilities/round_{r:02d}.json; skipping round {r}.")
            continue
        odds_path = _latest_odds_for_round(r, odds_dir)
        if odds_path is None:
            print(f"[backtest] WARN: no odds cache for round {r}; skipping.")
            continue
        winner = _actual_winner(actuals[r])
        if winner is None:
            print(f"[backtest] WARN: no winner in actuals for round {r}; skipping.")
            continue
        rr = _simulate_round(
            run.run_id, r, probs, odds_path, winner, eq,
            kelly_fraction_mult=kelly_fraction_mult,
            per_bet_cap=per_bet_cap,
            total_cap=total_cap,
        )
        run.rounds.append(rr)
        eq = rr.bankroll_after

    _finalize_run(run)
    if persist:
        _persist(run, db_path)
    return run


def _actual_winner(positions: dict[str, int]) -> str | None:
    if not positions:
        return None
    winner = min(positions.items(), key=lambda kv: kv[1])
    return winner[0]


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------


def _run_to_jsonable(run: BacktestRun) -> dict:
    return {
        "runId": run.run_id,
        "config": run.config,
        "startedAt": run.started_at,
        "totalBets": run.total_bets,
        "hitRate": round(run.hit_rate, 4),
        "roi": round(run.roi, 4),
        "sharpe": run.sharpe,
        "maxDrawdown": run.max_drawdown,
        "equityCurve": run.equity_curve,
        "rounds": [
            {
                "round": rr.round,
                "bankrollBefore": round(rr.bankroll_before, 2),
                "bankrollAfter": round(rr.bankroll_after, 2),
                "stakeTotal": round(rr.stake_total, 2),
                "pnl": round(rr.pnl, 2),
                "roi": round(rr.roi(), 4) if rr.roi() is not None else None,
                "bets": [asdict(b) for b in rr.bets],
            }
            for rr in run.rounds
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--kelly-fraction", type=float, default=0.25)
    parser.add_argument("--per-bet-cap", type=float, default=0.05)
    parser.add_argument("--total-cap", type=float, default=0.30)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports" / "backtest.json")
    parser.add_argument("--no-persist", action="store_true",
                        help="Skip writing to data/betting.duckdb")
    args = parser.parse_args()

    run = run_backtest(
        season=args.season,
        bankroll=args.bankroll,
        kelly_fraction_mult=args.kelly_fraction,
        per_bet_cap=args.per_bet_cap,
        total_cap=args.total_cap,
        persist=not args.no_persist,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(_run_to_jsonable(run), f, indent=2)

    print(
        f"Backtest {args.season}: {len(run.rounds)} rounds, "
        f"{run.total_bets} bets, hit_rate={run.hit_rate:.3f}, "
        f"ROI={run.roi:.4f}, "
        f"sharpe={'n/a' if run.sharpe is None else f'{run.sharpe:.3f}'}, "
        f"maxDD={'n/a' if run.max_drawdown is None else f'{run.max_drawdown:.3f}'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
