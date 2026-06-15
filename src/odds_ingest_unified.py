"""Unified F1 odds ingestion: orchestrates Betfair Exchange + manual CSV.

Single command that pulls odds from whatever sources are available and writes
ONE combined snapshot to ``odds_cache/round_NN_<ts>_unified.json``.  The output
is in the same schema `odds_ingest.fetch_winner_odds` produces, so
`export_value_data.py` consumes it with no changes.

Sources (auto-detected):

1. **Betfair Exchange** — used if `BETFAIR_USERNAME`, `BETFAIR_PASSWORD`,
   and `BETFAIR_APP_KEY` are all set in `.env` AND `betfairlightweight` is
   installed.

2. **Manual CSV** — used if `--csv PATH` is given OR a file exists at
   ``odds_inbox/round_NN.csv``.  The CSV is parsed via the same logic as
   ``odds_import_csv.py`` (driver names accept 3-letter codes, last names,
   or full names; odds accept decimal or fractional).

Merge strategies (``--merge``):

* ``auto`` (default) — if both sources return ≥ MIN_DRIVERS_MATCHED drivers,
  apply ``best-back``.  If only one does, use that one verbatim.  If neither
  does, exit non-zero with an actionable error.
* ``prefer-betfair`` — use Betfair if it succeeds; fall back to CSV otherwise.
* ``prefer-csv`` — use CSV if available; fall back to Betfair otherwise.
* ``best-back`` — for each driver, take the **highest decimal odds** across
  both sources.  This is what an arb-aware bettor wants: the best price you
  could actually take.  Drivers present in only one source keep that price.
* ``average`` — average the **implied probabilities** (1/odds), then convert
  back to decimal.  Closer to a consensus line; gentler on outlier prices.

CLI::

    python odds_ingest_unified.py --round 6 --season 2026
    python odds_ingest_unified.py --round 6 --season 2026 --merge best-back
    python odds_ingest_unified.py --round 6 --season 2026 --csv /path/to/monaco.csv

The CLI exits 0 on success, 2 on auth/config error, 1 on data-quality error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from f1_prediction_utils import DRIVER_FULL_NAMES  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "odds_cache"
INBOX_DIR = PROJECT_ROOT / "odds_inbox"

MIN_DRIVERS_MATCHED = 10

# Order matters — the first match wins for "prefer-*" strategies.
MergeStrategy = str  # auto | prefer-betfair | prefer-csv | best-back | average
VALID_STRATEGIES = ("auto", "prefer-betfair", "prefer-csv", "best-back", "average")


# --------------------------------------------------------------------------- #
# Source attempts
# --------------------------------------------------------------------------- #


def _betfair_creds_present() -> bool:
    return all(
        os.environ.get(v)
        for v in ("BETFAIR_USERNAME", "BETFAIR_PASSWORD", "BETFAIR_APP_KEY")
    )


def _try_betfair(round_number: int, season: int) -> dict[str, float] | None:
    """Attempt the Betfair path.  Returns None on any failure — caller decides
    whether absence is fatal or fall-through.

    Failure modes covered:
      - betfairlightweight not installed
      - Missing credentials
      - Network / auth errors
      - Market not found / too few drivers priced (raised as SystemExit by the
        underlying module; we re-classify as "no data" so the unified caller
        can fall back to CSV)
    """
    if not _betfair_creds_present():
        return None
    try:
        from odds_ingest_betfair import fetch_betfair_prices  # local import
    except ImportError:
        return None
    try:
        _, code_to_price = fetch_betfair_prices(round_number, season)
    except SystemExit as exc:
        print(f"  (betfair) {exc}", file=sys.stderr)
        return None
    except Exception as exc:  # noqa: BLE001 — defensive: betfairlightweight raises a zoo of exceptions
        print(f"  (betfair) unexpected error: {exc!r}", file=sys.stderr)
        return None
    return code_to_price if code_to_price else None


def _try_csv(csv_path: Path | None, round_number: int) -> dict[str, float] | None:
    """Attempt the CSV path.  Returns None on any failure.

    Auto-discovery: if `csv_path` is None, look for ``odds_inbox/round_NN.csv``.
    """
    if csv_path is None:
        candidate = INBOX_DIR / f"round_{round_number:02d}.csv"
        if not candidate.exists():
            return None
        csv_path = candidate
    if not csv_path.exists():
        print(f"  (csv) file not found: {csv_path}", file=sys.stderr)
        return None
    from odds_import_csv import parse_csv  # local import

    try:
        return parse_csv(csv_path)
    except ValueError as exc:
        print(f"  (csv) {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Merge strategies
# --------------------------------------------------------------------------- #


def _merge_best_back(
    betfair: dict[str, float] | None,
    csv: dict[str, float] | None,
) -> dict[str, float]:
    """Per-driver max decimal odds across both sources."""
    out: dict[str, float] = {}
    for src in (betfair, csv):
        if not src:
            continue
        for code, price in src.items():
            if price <= 1.0:
                continue
            cur = out.get(code)
            if cur is None or price > cur:
                out[code] = price
    return out


def _merge_average(
    betfair: dict[str, float] | None,
    csv: dict[str, float] | None,
) -> dict[str, float]:
    """Average implied probability across sources, converted back to decimal.

    Drivers present in only one source keep that source's price verbatim
    (rather than being penalised for the gap in the other book).
    """
    out: dict[str, float] = {}
    all_drivers = set()
    for src in (betfair, csv):
        if src:
            all_drivers.update(src.keys())
    for code in all_drivers:
        prices = []
        for src in (betfair, csv):
            if src and code in src and src[code] > 1.0:
                prices.append(src[code])
        if not prices:
            continue
        if len(prices) == 1:
            out[code] = prices[0]
            continue
        implied = sum(1.0 / p for p in prices) / len(prices)
        if implied <= 0.0 or implied >= 1.0:
            out[code] = max(prices)  # safety fallback
            continue
        out[code] = 1.0 / implied
    return out


def _apply_strategy(
    strategy: MergeStrategy,
    betfair: dict[str, float] | None,
    csv: dict[str, float] | None,
) -> tuple[dict[str, float], str]:
    """Return ``(odds, bookmaker_label)`` for the chosen strategy.

    The bookmaker label is recorded in the snapshot so `select_bookmaker` in
    `export_value_data.py` and the website show a meaningful source name.
    """
    bf_ok = bool(betfair) and len(betfair) >= MIN_DRIVERS_MATCHED
    csv_ok = bool(csv) and len(csv) >= MIN_DRIVERS_MATCHED

    if strategy == "auto":
        if bf_ok and csv_ok:
            return _merge_best_back(betfair, csv), "combined_best_back"
        if bf_ok:
            return betfair or {}, "betfair_ex_eu"
        if csv_ok:
            return csv or {}, "oddschecker_manual"
        return {}, "none"

    if strategy == "prefer-betfair":
        if bf_ok:
            return betfair or {}, "betfair_ex_eu"
        if csv_ok:
            return csv or {}, "oddschecker_manual"
        return {}, "none"

    if strategy == "prefer-csv":
        if csv_ok:
            return csv or {}, "oddschecker_manual"
        if bf_ok:
            return betfair or {}, "betfair_ex_eu"
        return {}, "none"

    if strategy == "best-back":
        merged = _merge_best_back(betfair, csv)
        return merged, "combined_best_back"

    if strategy == "average":
        merged = _merge_average(betfair, csv)
        return merged, "combined_average"

    raise ValueError(f"Unknown merge strategy: {strategy!r}")


# --------------------------------------------------------------------------- #
# Snapshot writing (same wrapped schema as the existing ingesters)
# --------------------------------------------------------------------------- #


def _cache_path(round_number: int, when: datetime) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    return CACHE_DIR / f"round_{round_number:02d}_{stamp}_unified.json"


def _build_snapshot(
    round_number: int,
    season: int,
    bookmaker: str,
    odds: dict[str, float],
    sources_used: list[str],
    strategy: str,
) -> dict:
    now = datetime.now(timezone.utc)
    outcomes: list[dict[str, Any]] = [
        {"name": DRIVER_FULL_NAMES.get(code, code), "price": float(price)}
        for code, price in odds.items()
    ]
    payload = [
        {
            "id": f"unified-{season}-{round_number:02d}",
            "sport_key": "motorsport_f1",
            "sport_title": "Formula 1",
            "commence_time": now.isoformat(),
            "home_team": None,
            "away_team": None,
            "bookmakers": [
                {
                    "key": bookmaker,
                    "title": bookmaker.replace("_", " ").title(),
                    "last_update": now.isoformat(),
                    "markets": [
                        {
                            "key": "outrights",
                            "last_update": now.isoformat(),
                            "outcomes": outcomes,
                        }
                    ],
                }
            ],
        }
    ]
    return {
        "season": season,
        "round": round_number,
        "fetchedAt": now.isoformat(),
        "source": "unified",
        "strategy": strategy,
        "sourcesUsed": sources_used,
        "payload": payload,
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def ingest(
    round_number: int,
    season: int,
    *,
    strategy: MergeStrategy = "auto",
    csv_path: Path | None = None,
    write: bool = True,
) -> tuple[Path | None, dict[str, float], str]:
    """Pull odds from both sources, merge, and (optionally) write to cache.

    Returns ``(snapshot_path_or_none, merged_odds, bookmaker_label)``.
    `snapshot_path_or_none` is None when ``write=False`` or when no data was
    obtained.
    """
    if strategy not in VALID_STRATEGIES:
        raise ValueError(
            f"Invalid strategy {strategy!r}; choose from {VALID_STRATEGIES}"
        )

    bf = _try_betfair(round_number, season)
    csv = _try_csv(csv_path, round_number)

    sources_used: list[str] = []
    if bf is not None and len(bf) >= MIN_DRIVERS_MATCHED:
        sources_used.append("betfair")
    if csv is not None and len(csv) >= MIN_DRIVERS_MATCHED:
        sources_used.append("csv")

    odds, bookmaker = _apply_strategy(strategy, bf, csv)
    if len(odds) < MIN_DRIVERS_MATCHED:
        return None, odds, bookmaker

    if not write:
        return None, odds, bookmaker

    snapshot = _build_snapshot(
        round_number, season, bookmaker, odds, sources_used, strategy
    )
    out_path = _cache_path(round_number, datetime.now(timezone.utc))
    with out_path.open("w") as f:
        json.dump(snapshot, f, indent=2)
    return out_path, odds, bookmaker


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified F1 odds ingestion (Betfair Exchange + manual CSV).",
    )
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument(
        "--merge",
        choices=VALID_STRATEGIES,
        default="auto",
        help="How to combine sources. Default: auto (best-back if both available, "
             "single source if only one).",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to a manual CSV. If omitted, auto-discovers "
             "odds_inbox/round_NN.csv.",
    )
    args = parser.parse_args()

    sources_attempted: list[str] = []
    if _betfair_creds_present():
        sources_attempted.append("betfair (creds present)")
    else:
        sources_attempted.append("betfair (creds missing — skipped)")

    inbox_csv = args.csv or (INBOX_DIR / f"round_{args.round:02d}.csv")
    if inbox_csv.exists():
        sources_attempted.append(f"csv ({inbox_csv.name})")
    else:
        sources_attempted.append(f"csv ({inbox_csv.name} not found — skipped)")

    print(f"Sources: {', '.join(sources_attempted)}")
    print(f"Strategy: {args.merge}")

    try:
        out_path, odds, bookmaker = ingest(
            args.round, args.season, strategy=args.merge, csv_path=args.csv
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if out_path is None:
        print(
            f"ERROR: only {len(odds)} drivers ended up in the merged snapshot "
            f"(need >= {MIN_DRIVERS_MATCHED}). No file written.\n"
            f"  Hint: drop a CSV at {INBOX_DIR / f'round_{args.round:02d}.csv'} "
            f"or set BETFAIR_* env vars.",
            file=sys.stderr,
        )
        return 1

    print(f"OK ({bookmaker}, {len(odds)} drivers): {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
