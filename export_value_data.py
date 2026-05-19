"""Export per-round value-finder data for the Next.js site.

Produces ``website/public/data/value/round_NN.json`` per the frozen schema in
the project brief.

Pipeline:
    probabilities/round_NN.json   (model output, produced upstream)
                +
    odds_cache/round_NN_*.json    (raw bookmaker snapshot, latest by timestamp)
                |
                v
    value/round_NN.json           (this script's output)

Per-driver edge:
    edgePct = (modelP - marketP) / marketP * 100

Bookmaker selection: prefer Pinnacle (sharpest), fall back to lowest overround
of available books.  Documented in `select_bookmaker`.

v1 emits the **winner** market only.  Reason: the free tier of OddsAPI doesn't
reliably price podium/H2H/top-N for F1, and a half-priced market would push
mis-calibrated edges into the UI.  When upgraded to a paid plan, extend this
script to consume the `podium`/`top6`/`top10`/`h2h` keys already present in
the probabilities schema.

TODO Tier 2:
- Podium, top-6, top-10 markets (need paid OddsAPI tier or alternative source).
- H2H markets (priced via `h2h` key in probability JSON).
- Re-scale model probabilities so each market sums to its required total
  (1 for win, 3 for podium, etc.) before computing edge.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Optional .env loading — see odds_ingest.py for rationale.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from bet_sizing import (
    cap_portfolio,
    expected_value,
    kelly_fraction,
    total_exposure,
)
from f1_prediction_utils import (
    DRIVER_FULL_NAMES,
    DRIVER_TEAM_2026,
    TEAM_COLOURS,
)
from odds_ingest import devig_proportional, load_cached_payload

PROJECT_ROOT = Path(__file__).resolve().parent
PROBS_DIR = PROJECT_ROOT / "website" / "public" / "data" / "probabilities"
VALUE_DIR = PROJECT_ROOT / "website" / "public" / "data" / "value"
ODDS_CACHE_DIR = PROJECT_ROOT / "odds_cache"

# Preferred bookmakers in order — Pinnacle is the sharpest book, the rest are
# fallbacks if Pinnacle is unavailable in the snapshot.
PREFERRED_BOOKS = ("pinnacle", "betfair_ex_eu", "betfair", "marathonbet", "williamhill")


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------


def _read_probabilities(round_number: int) -> dict:
    path = PROBS_DIR / f"round_{round_number:02d}.json"
    if not path.exists():
        print(
            f"ERROR: missing probabilities file {path}.\n"
            f"  Upstream `probabilities/round_NN.json` writer must run first.",
            file=sys.stderr,
        )
        sys.exit(2)
    with path.open() as f:
        return json.load(f)


def _latest_odds_snapshot(round_number: int) -> Path | None:
    if not ODDS_CACHE_DIR.exists():
        return None
    candidates = sorted(ODDS_CACHE_DIR.glob(f"round_{round_number:02d}_*.json"))
    return candidates[-1] if candidates else None


def _snapshot_timestamp(path: Path) -> str:
    """Return the ISO timestamp encoded in a cache filename, or file mtime."""
    try:
        with path.open() as f:
            blob = json.load(f)
        if isinstance(blob, dict) and blob.get("fetchedAt"):
            return str(blob["fetchedAt"])
    except (OSError, json.JSONDecodeError):
        pass
    # Fallback: parse the timestamp from the filename `round_NN_<stamp>.json`.
    stem = path.stem
    parts = stem.split("_", 2)
    if len(parts) == 3:
        return parts[2]
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Bookmaker selection
# ---------------------------------------------------------------------------


def _overround(odds: dict[str, float]) -> float:
    return sum(1.0 / o for o in odds.values() if o and o > 1.0)


def select_bookmaker(books: dict[str, dict[str, float]]) -> str:
    """Pick the best bookmaker out of the snapshot.

    Logic:
      1. If a preferred book (Pinnacle, Betfair, …) is in the snapshot, return
         the first such match.  These are sharp books (Pinnacle, BF-Exchange)
         or large-volume softs that we trust more than a random fringe site.
      2. Else fall back to the book with the lowest overround (closest-to-fair
         pricing implies a sharper line, all else equal).
      3. If `books` is empty, raise ValueError — caller must handle.
    """
    if not books:
        raise ValueError("No bookmakers in snapshot.")
    for preferred in PREFERRED_BOOKS:
        if preferred in books:
            return preferred
    return min(books.keys(), key=lambda b: _overround(books[b]))


# ---------------------------------------------------------------------------
# Build opportunities
# ---------------------------------------------------------------------------


def _team_color(team: str) -> str:
    return TEAM_COLOURS.get(team, "#888888")


def build_opportunities(
    win_probs: list[dict],
    market_probs: dict[str, float],
    market_odds: dict[str, float],
    kelly_fraction_mult: float,
    bankroll: float,
) -> list[dict]:
    """One row per driver in the model probability list.

    Includes negative-edge rows (`edgePct < 0`) because the value-finder UI
    needs to render the full picture; the table filters / colours decide what
    to highlight.  Kelly stake / EV are computed for every row but will be 0
    for negative-edge bets per `kelly_fraction`'s contract.
    """
    rows: list[dict] = []
    for entry in win_probs:
        code = entry.get("driver")
        model_p = entry.get("probability")
        if not isinstance(code, str) or not isinstance(model_p, (int, float)):
            continue
        if code not in market_probs or code not in market_odds:
            # No bookmaker price for this driver — skip (we can't compute edge).
            continue
        market_p = float(market_probs[code])
        odds = float(market_odds[code])
        if market_p <= 0.0:
            continue
        edge_pct = (float(model_p) - market_p) / market_p * 100.0
        k = kelly_fraction(float(model_p), odds, fraction=kelly_fraction_mult)
        ev = expected_value(float(model_p), odds)
        team = DRIVER_TEAM_2026.get(code, "Unknown")
        rows.append(
            {
                "market": "win",
                "driver": code,
                "driverFullName": DRIVER_FULL_NAMES.get(code, code),
                "team": team,
                "teamColor": _team_color(team),
                "modelProbability": round(float(model_p), 6),
                "marketProbability": round(market_p, 6),
                "marketOdds": round(odds, 4),
                "edgePct": round(edge_pct, 4),
                "kellyFraction": round(k, 6),
                "kellyStake": round(k * bankroll, 2),
                "expectedValue": round(ev, 6),
            }
        )
    return rows


def _refresh_kelly_stake(rows: list[dict], bankroll: float) -> None:
    """After cap_portfolio rescales kellyFraction, regenerate stakes."""
    for r in rows:
        r["kellyStake"] = round(float(r["kellyFraction"]) * bankroll, 2)


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def export_value_data(
    round_number: int,
    season: int,
    *,
    bankroll: float = 1000.0,
    kelly_fraction_mult: float = 0.25,
    per_bet_cap: float = 0.05,
    total_cap: float = 0.30,
    output_path: Path | None = None,
    odds_snapshot_path: Path | None = None,
    probabilities_override: dict | None = None,
) -> dict:
    """Compute the value-finder dict and write it to disk.  Returns the dict.

    Test hook: `probabilities_override` and `odds_snapshot_path` bypass disk
    reads so the smoke test can run on a fixture without touching real data.
    """
    probs = probabilities_override or _read_probabilities(round_number)

    snapshot = odds_snapshot_path or _latest_odds_snapshot(round_number)
    if snapshot is None or not snapshot.exists():
        print(
            f"ERROR: no odds snapshot for round {round_number} in {ODDS_CACHE_DIR}.\n"
            f"  Run `python odds_ingest.py --round {round_number} --season {season}` first.",
            file=sys.stderr,
        )
        sys.exit(2)

    books = load_cached_payload(snapshot)
    if not books:
        print(f"ERROR: snapshot {snapshot} parsed to zero bookmakers.", file=sys.stderr)
        sys.exit(2)
    bookmaker = select_bookmaker(books)
    market_odds = books[bookmaker]
    market_probs = devig_proportional(market_odds)

    win_probs = (probs.get("markets") or {}).get("win") or []
    if not win_probs:
        print(
            f"ERROR: probabilities for round {round_number} have empty `markets.win`.",
            file=sys.stderr,
        )
        sys.exit(2)

    rows = build_opportunities(
        win_probs,
        market_probs,
        market_odds,
        kelly_fraction_mult=kelly_fraction_mult,
        bankroll=bankroll,
    )

    # Cap portfolio at per-bet + total limits — but only over positive-edge rows.
    # Negative-edge rows already have kellyFraction == 0 and stay there.
    rows = cap_portfolio(rows, per_bet_cap=per_bet_cap, total_cap=total_cap)
    _refresh_kelly_stake(rows, bankroll)

    rows.sort(key=lambda r: r["edgePct"], reverse=True)

    positive = [r for r in rows if r["edgePct"] > 0]
    output = {
        "round": round_number,
        "season": season,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "bookmaker": bookmaker,
        "oddsTimestamp": _snapshot_timestamp(snapshot),
        "bankrollRef": float(bankroll),
        "opportunities": rows,
        "summary": {
            "totalOpportunities": len(rows),
            "positiveEdgeCount": len(positive),
            "totalKellyExposure": round(total_exposure(rows), 6),
        },
        "disclaimer": (
            "Educational use only; verify with your sportsbook; "
            "gambling involves loss."
        ),
    }

    out_path = output_path or (VALUE_DIR / f"round_{round_number:02d}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--kelly-fraction", type=float, default=0.25)
    parser.add_argument("--per-bet-cap", type=float, default=0.05)
    parser.add_argument("--total-cap", type=float, default=0.30)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    out = export_value_data(
        args.round,
        args.season,
        bankroll=args.bankroll,
        kelly_fraction_mult=args.kelly_fraction,
        per_bet_cap=args.per_bet_cap,
        total_cap=args.total_cap,
        output_path=args.output,
    )
    n = out["summary"]["totalOpportunities"]
    pos = out["summary"]["positiveEdgeCount"]
    exp = out["summary"]["totalKellyExposure"]
    print(
        f"Wrote value/round_{args.round:02d}.json — "
        f"{n} ops, {pos} +edge, total Kelly exposure {exp:.3f}, book={out['bookmaker']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
