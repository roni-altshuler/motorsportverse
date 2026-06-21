"""Import bookmaker odds from a manual CSV into the odds_cache.

Workflow:
1. Open the Oddschecker page for the upcoming race, e.g.
   https://www.oddschecker.com/motorsport/formula-1/canadian-grand-prix/winner
2. Copy the table into Excel / Google Sheets, save as CSV.
3. Run::

       python odds_import_csv.py --round 5 --season 2026 \\
           --bookmaker oddschecker_avg --csv ~/Downloads/canadian-gp.csv

The script writes ``odds_cache/round_NN_<timestamp>_csv.json`` in the same
shape `odds_ingest.fetch_winner_odds` produces, so `export_value_data.py`
consumes it with no changes.

Accepted CSV shapes (header optional, case-insensitive):

    Driver,Odds
    Max Verstappen,3.5
    Lando Norris,4.0
    ...

Or, with a different price column:

    driver,decimal_odds
    VER,3.5

Or even fractional odds:

    driver,price
    Verstappen,5/2

Driver normalization is permissive:
- 3-letter code: matched directly against ``DRIVER_TEAM_2026``.
- Last name: matched via substring against ``DRIVER_FULL_NAMES``.
- Full name: same substring match (the same logic ``odds_ingest`` uses).

Unmatched drivers are reported and dropped; cache snapshot still writes if at
least 10 drivers were matched (a 22-grid with 12 missing is junk; refuse it).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "odds_cache"

# Reuse the same driver dictionary the API path uses.
from f1_prediction_utils import DRIVER_FULL_NAMES, DRIVER_TEAM_2026  # noqa: E402

MIN_DRIVERS_MATCHED = 10


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def _parse_odds(raw: str) -> float | None:
    """Accept '3.5', '3/1', '5/2', '7/4', or '11/10' and return decimal odds.

    Returns ``None`` on anything we can't parse — caller skips that row.
    """
    s = raw.strip()
    if not s:
        return None
    # Fractional: "5/2" -> 1 + 5/2 = 3.5
    if "/" in s:
        try:
            num, denom = s.split("/", 1)
            n, d = float(num), float(denom)
            if d <= 0:
                return None
            return 1.0 + (n / d)
        except (ValueError, ZeroDivisionError):
            return None
    # Decimal: drop currency symbols and stray text
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 1.0 else None


def _normalize_driver(label: str) -> str | None:
    """Return a 3-letter driver code or None if unrecognised."""
    s = label.strip().upper()
    if not s:
        return None
    # Direct 3-letter code hit (the file may already use codes).
    if s in DRIVER_TEAM_2026:
        return s
    # Substring on full names — same logic the OddsAPI path uses for
    # cross-bookmaker driver-name variance ("Max Verstappen" vs
    # "Verstappen, M." vs "Max VERSTAPPEN").
    label_low = label.strip().lower()
    for code, full in DRIVER_FULL_NAMES.items():
        # Last name match is strongest; check full and last separately.
        last = full.split()[-1].lower()
        if last and last in label_low:
            return code
        if full.lower() in label_low or label_low in full.lower():
            return code
    return None


def _identify_columns(header: list[str]) -> tuple[int, int]:
    """Return (driver_col_idx, odds_col_idx) from a CSV header row.

    Permissive: anything name-like (driver/runner/name/horse) wins driver;
    anything numeric-tagged (odds/price/decimal/back) wins odds.
    """
    h_low = [c.strip().lower() for c in header]
    driver_keys = ("driver", "runner", "name", "player", "selection")
    odds_keys = ("odds", "price", "decimal", "back", "win")

    driver_idx = next(
        (i for i, c in enumerate(h_low) if any(k in c for k in driver_keys)),
        None,
    )
    odds_idx = next(
        (i for i, c in enumerate(h_low) if any(k in c for k in odds_keys)),
        None,
    )
    if driver_idx is None or odds_idx is None:
        # Heuristic fallback: assume two-column file, driver first then odds.
        if len(header) >= 2:
            return 0, 1
        raise ValueError(
            f"Could not find driver/odds columns in CSV header {header!r}. "
            "Expected columns containing one of "
            f"{driver_keys!r} and one of {odds_keys!r}."
        )
    return driver_idx, odds_idx


def parse_csv(path: Path) -> dict[str, float]:
    """Parse a CSV into ``{driver_code: decimal_odds}`` after normalization.

    Skips header rows (auto-detected: if both fields are non-numeric/non-name,
    we treat it as a header).  Skips unparseable rows.

    Raises ``ValueError`` if fewer than MIN_DRIVERS_MATCHED drivers were
    recognised; the snapshot would be too sparse to compute meaningful edges.
    """
    with path.open(newline="") as f:
        rows = [r for r in csv.reader(f) if r and any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError(f"{path} is empty.")

    first = rows[0]
    # If first row's "odds" cell doesn't parse to a price, treat as header.
    parsed_first_odds = _parse_odds(first[-1]) if len(first) >= 2 else None
    has_header = parsed_first_odds is None
    header = first if has_header else ["driver", "odds"]
    data_rows = rows[1:] if has_header else rows

    driver_idx, odds_idx = _identify_columns(header)

    out: dict[str, float] = {}
    unmatched: list[str] = []
    for row in data_rows:
        if max(driver_idx, odds_idx) >= len(row):
            continue
        label = row[driver_idx]
        odds = _parse_odds(row[odds_idx])
        if odds is None:
            continue
        code = _normalize_driver(label)
        if code is None:
            unmatched.append(label)
            continue
        # If a driver appears twice (some Oddschecker tables list multiple
        # books per row), prefer the first occurrence — caller can pre-filter.
        out.setdefault(code, odds)

    if unmatched:
        print(f"  Warning: {len(unmatched)} unmatched name(s): {unmatched}",
              file=sys.stderr)

    if len(out) < MIN_DRIVERS_MATCHED:
        raise ValueError(
            f"Only {len(out)} drivers matched in {path}; need >= "
            f"{MIN_DRIVERS_MATCHED}. Check that driver names in the CSV "
            f"are recognisable (full name, last name, or 3-letter code)."
        )
    return out


# --------------------------------------------------------------------------- #
# Snapshot writing — exactly the schema odds_ingest.fetch_winner_odds produces
# --------------------------------------------------------------------------- #


def _build_snapshot(
    round_number: int,
    season: int,
    bookmaker: str,
    odds: dict[str, float],
    commence_time: str | None = None,
) -> dict:
    """Wrap the parsed odds into the cache schema downstream code expects."""
    now = datetime.now(timezone.utc)
    outcomes = [
        {"name": DRIVER_FULL_NAMES.get(code, code), "price": float(price)}
        for code, price in odds.items()
    ]
    payload = [
        {
            "id": f"csv-import-{season}-{round_number:02d}",
            "sport_key": "motorsport_f1",
            "sport_title": "Formula 1",
            "commence_time": commence_time or now.isoformat(),
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
        "source": "csv-import",
        "payload": payload,
    }


def _cache_path(round_number: int, when: datetime) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    return CACHE_DIR / f"round_{round_number:02d}_{stamp}_csv.json"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _print_template() -> None:
    print("# Save this as e.g. canadian-gp.csv and edit:")
    print("driver,odds")
    for code, full in DRIVER_FULL_NAMES.items():
        print(f"{full},")


def import_csv(
    round_number: int,
    season: int,
    bookmaker: str,
    csv_path: Path,
    commence_time: str | None = None,
) -> Path:
    """Library entrypoint: parse CSV, build snapshot, write file, return path."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    odds = parse_csv(csv_path)
    snapshot = _build_snapshot(round_number, season, bookmaker, odds, commence_time)
    out_path = _cache_path(round_number, datetime.now(timezone.utc))
    with out_path.open("w") as f:
        json.dump(snapshot, f, indent=2)
    return out_path


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Import bookmaker odds from a manual CSV into odds_cache/",
    )
    parser.add_argument("--round", type=int, help="Race round number (1-22).")
    parser.add_argument("--season", type=int, help="Season year, e.g. 2026.")
    parser.add_argument(
        "--bookmaker",
        type=str,
        default="oddschecker_manual",
        help="Bookmaker key recorded in the cache (default 'oddschecker_manual'). "
             "Use a 'pinnacle' / 'betfair_ex_eu' / etc. key to make select_bookmaker "
             "prefer this snapshot.",
    )
    parser.add_argument("--csv", type=Path, help="Path to the CSV file.")
    parser.add_argument(
        "--commence-time",
        type=str,
        default=None,
        help="ISO timestamp of the race start; defaults to 'now'. Only affects "
             "the snapshot metadata, not edge math.",
    )
    parser.add_argument(
        "--print-template",
        action="store_true",
        help="Print a CSV template with every 2026 driver and exit. Pipe to a "
             "file, fill in the odds column, then re-run with --csv.",
    )
    args = parser.parse_args()

    if args.print_template:
        _print_template()
        return 0

    if not (args.round and args.season and args.csv):
        parser.error("--round, --season, and --csv are required (unless --print-template).")

    try:
        out_path = import_csv(
            args.round, args.season, args.bookmaker, args.csv, args.commence_time
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: wrote {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
