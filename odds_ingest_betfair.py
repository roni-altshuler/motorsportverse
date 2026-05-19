"""Betfair Exchange odds ingest for F1 race-winner outrights.

Free-tier path (no paid OddsAPI required) but it does need:

1. A Betfair account with KYC completed (UK / IE / AU / GR / ES / IT / DE only).
2. A Developer Application Key from https://developer.betfair.com/.
3. Either:
   (a) An interactive session token refreshed periodically (simpler), OR
   (b) A non-interactive cert-based login (more reliable in CI).

Env vars expected (place in `.env` at project root):

    BETFAIR_USERNAME=...
    BETFAIR_PASSWORD=...
    BETFAIR_APP_KEY=...

Optional, for cert-based login:

    BETFAIR_CERT_PATH=/path/to/client-2048.crt
    BETFAIR_CERT_KEY_PATH=/path/to/client-2048.key

This module uses the `betfairlightweight` library which handles auth and
JSON-RPC for us — install with `pip install betfairlightweight`.  The library
is not pinned in `requirements-dev.txt` because most consumers won't use
Betfair; the import is lazy with a clear error message if missing.

CLI::

    python odds_ingest_betfair.py --round 5 --season 2026

Writes ``odds_cache/round_NN_<timestamp>_betfair.json`` in the same wrapped
schema `odds_ingest.fetch_winner_odds` produces, so the downstream value
exporter consumes it with no changes.

Selecting which Betfair market: the script lists every F1 outright market
with "winner" in the name whose `marketStartTime` falls within the upcoming
14 days, then picks the one whose start date is closest to the configured
round's date in `website/public/data/season.json`.  If no candidate matches,
the script aborts cleanly — no bad snapshots get written.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Optional .env loading — same pattern as odds_ingest.py.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from f1_prediction_utils import DRIVER_FULL_NAMES  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_ROOT / "odds_cache"
SEASON_FILE = PROJECT_ROOT / "website" / "public" / "data" / "season.json"

BETFAIR_F1_EVENT_TYPE_ID = "7"  # Motor Sport on the Betfair Exchange
WINNER_KEYWORDS = ("winner", "race winner", "race finalist")
MARKET_LOOKAHEAD_DAYS = 14
MIN_DRIVERS_MATCHED = 10  # mirrors odds_import_csv


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


class BetfairAuthError(RuntimeError):
    """Surface auth misconfiguration with an actionable message."""


def _require(env_var: str) -> str:
    val = os.environ.get(env_var)
    if not val:
        raise BetfairAuthError(
            f"{env_var} not set. Add it to your .env or export it.\n"
            "  Get a Betfair app key at https://developer.betfair.com/."
        )
    return val


def _build_client():
    """Construct and log in a betfairlightweight APIClient.  Returns the client.

    Prefers cert-based login if BETFAIR_CERT_PATH is set, otherwise falls back
    to interactive login (username + password).
    """
    try:
        import betfairlightweight  # type: ignore[import-untyped]
    except ImportError as exc:
        raise BetfairAuthError(
            "betfairlightweight not installed. Run:\n"
            "  pip install betfairlightweight\n"
            "(intentionally not in requirements-dev.txt because most users "
            "won't use Betfair.)"
        ) from exc

    username = _require("BETFAIR_USERNAME")
    password = _require("BETFAIR_PASSWORD")
    app_key = _require("BETFAIR_APP_KEY")
    cert_path = os.environ.get("BETFAIR_CERT_PATH")

    if cert_path:
        client = betfairlightweight.APIClient(
            username=username,
            password=password,
            app_key=app_key,
            certs=cert_path,
        )
        client.login()
    else:
        client = betfairlightweight.APIClient(
            username=username,
            password=password,
            app_key=app_key,
        )
        client.login_interactive()
    return client


# --------------------------------------------------------------------------- #
# Market discovery + odds extraction
# --------------------------------------------------------------------------- #


def _load_round_date(round_number: int) -> datetime | None:
    if not SEASON_FILE.exists():
        return None
    with SEASON_FILE.open() as f:
        season = json.load(f)
    for entry in season.get("calendar", []):
        if entry.get("round") == round_number:
            try:
                return datetime.fromisoformat(entry["date"]).replace(tzinfo=timezone.utc)
            except (ValueError, KeyError):
                return None
    return None


def list_winner_markets(client, lookahead_days: int = MARKET_LOOKAHEAD_DAYS) -> list[dict]:
    """List upcoming Betfair F1 race-winner outright markets.

    Returns a list of dicts with keys: marketId, marketName, marketStartTime,
    competition, runners ([{selectionId, runnerName}, ...]).
    """
    from betfairlightweight import filters  # type: ignore[import-untyped]

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=lookahead_days)
    market_filter = filters.market_filter(
        event_type_ids=[BETFAIR_F1_EVENT_TYPE_ID],
        market_start_time={"from": now.isoformat(), "to": horizon.isoformat()},
        text_query="winner",
    )
    catalogue = client.betting.list_market_catalogue(
        filter=market_filter,
        market_projection=["RUNNER_METADATA", "MARKET_START_TIME", "COMPETITION"],
        max_results=100,
    )
    out: list[dict] = []
    for m in catalogue:
        name = (getattr(m, "market_name", "") or "").lower()
        if not any(k in name for k in WINNER_KEYWORDS):
            continue
        out.append(
            {
                "marketId": m.market_id,
                "marketName": m.market_name,
                "marketStartTime": getattr(m, "market_start_time", None),
                "competition": getattr(getattr(m, "competition", None), "name", None),
                "runners": [
                    {"selectionId": r.selection_id, "runnerName": r.runner_name}
                    for r in (m.runners or [])
                ],
            }
        )
    return out


def select_market_for_round(markets: list[dict], round_date: datetime | None) -> dict | None:
    """Pick the market closest to the round date; fall back to the soonest market."""
    if not markets:
        return None
    if round_date is None:
        return min(markets, key=lambda m: m["marketStartTime"] or datetime.max.replace(tzinfo=timezone.utc))
    return min(
        markets,
        key=lambda m: abs(
            (m["marketStartTime"] or datetime.max.replace(tzinfo=timezone.utc)) - round_date
        ),
    )


def fetch_market_book(client, market_id: str) -> dict:
    """Fetch live prices for one market. Returns {selectionId: best_back_price}."""
    from betfairlightweight import filters  # type: ignore[import-untyped]

    books = client.betting.list_market_book(
        market_ids=[market_id],
        price_projection=filters.price_projection(price_data=["EX_BEST_OFFERS"]),
    )
    if not books:
        return {}
    runners = books[0].runners or []
    out: dict[int, float] = {}
    for r in runners:
        # Prefer the best available-to-back price; that's the price you'd
        # actually take a bet at on the exchange.
        ex = getattr(r, "ex", None)
        if ex is None:
            continue
        backs = getattr(ex, "available_to_back", None) or []
        if backs:
            price = float(getattr(backs[0], "price", 0.0))
            if price > 1.0:
                out[int(r.selection_id)] = price
    return out


def _normalize_runner_name(runner_name: str) -> str | None:
    """Match a Betfair runner name against the 2026 grid → 3-letter code."""
    label = (runner_name or "").lower().strip()
    if not label:
        return None
    for code, full in DRIVER_FULL_NAMES.items():
        last = full.split()[-1].lower()
        if last and last in label:
            return code
        if full.lower() in label:
            return code
    return None


# --------------------------------------------------------------------------- #
# Snapshot writing (same schema as odds_ingest.fetch_winner_odds)
# --------------------------------------------------------------------------- #


def _cache_path(round_number: int, when: datetime) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    return CACHE_DIR / f"round_{round_number:02d}_{stamp}_betfair.json"


def _build_snapshot(
    round_number: int,
    season: int,
    market: dict,
    runner_prices: dict[int, float],
) -> tuple[dict, dict[str, float]]:
    """Assemble the cache-shaped snapshot + a {code: price} map.

    Returns ``(snapshot_dict, code_to_price)``.  The map is also returned so
    the CLI can print it for sanity-checking without reparsing the JSON.
    """
    now = datetime.now(timezone.utc)
    code_to_price: dict[str, float] = {}
    outcomes: list[dict[str, Any]] = []
    for runner in market["runners"]:
        sel = int(runner["selectionId"])
        price = runner_prices.get(sel)
        if price is None or price <= 1.0:
            continue
        code = _normalize_runner_name(runner["runnerName"])
        if code is None:
            continue
        code_to_price.setdefault(code, price)
        outcomes.append({"name": runner["runnerName"], "price": float(price)})

    payload = [
        {
            "id": f"betfair-{market['marketId']}",
            "sport_key": "motorsport_f1",
            "sport_title": "Formula 1",
            "commence_time": (
                market.get("marketStartTime").isoformat()
                if isinstance(market.get("marketStartTime"), datetime)
                else (market.get("marketStartTime") or now.isoformat())
            ),
            "home_team": None,
            "away_team": None,
            "bookmakers": [
                {
                    "key": "betfair_ex_eu",
                    "title": "Betfair Exchange",
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
    snapshot = {
        "season": season,
        "round": round_number,
        "fetchedAt": now.isoformat(),
        "source": "betfair-exchange",
        "marketId": market["marketId"],
        "marketName": market["marketName"],
        "payload": payload,
    }
    return snapshot, code_to_price


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def fetch_betfair_prices(round_number: int, season: int) -> tuple[dict, dict[str, float]]:
    """Fetch Betfair odds in-memory; no file write.  Returns (snapshot, code→price).

    Exposed so the unified ingester (`odds_ingest_unified.py`) can compose
    Betfair + CSV without leaving a spurious Betfair-only file in odds_cache.
    Raises ``SystemExit`` on the same conditions as `fetch_betfair_winner_odds`
    (no markets / too few drivers priced); callers that want to suppress those
    failures should catch ``SystemExit`` explicitly.
    """
    client = _build_client()
    try:
        markets = list_winner_markets(client)
    finally:
        try:
            client.logout()
        except Exception:  # noqa: BLE001
            pass

    round_date = _load_round_date(round_number)
    market = select_market_for_round(markets, round_date)
    if market is None:
        raise SystemExit(
            "ERROR: no F1 race-winner market found on Betfair Exchange in the "
            f"next {MARKET_LOOKAHEAD_DAYS} days. Try again closer to race weekend."
        )

    client = _build_client()
    try:
        runner_prices = fetch_market_book(client, market["marketId"])
    finally:
        try:
            client.logout()
        except Exception:  # noqa: BLE001
            pass

    snapshot, code_to_price = _build_snapshot(round_number, season, market, runner_prices)
    if len(code_to_price) < MIN_DRIVERS_MATCHED:
        raise SystemExit(
            f"ERROR: only {len(code_to_price)} drivers priced on Betfair market "
            f"{market['marketId']!r} ({market['marketName']!r}). Need >= "
            f"{MIN_DRIVERS_MATCHED}. Refusing to write a partial snapshot."
        )
    return snapshot, code_to_price


def fetch_betfair_winner_odds(round_number: int, season: int) -> Path:
    """End-to-end: log in, find the right market, fetch prices, write cache."""
    snapshot, _ = fetch_betfair_prices(round_number, season)
    out_path = _cache_path(round_number, datetime.now(timezone.utc))
    with out_path.open("w") as f:
        json.dump(snapshot, f, indent=2, default=str)
    return out_path


def _main() -> int:
    parser = argparse.ArgumentParser(description="Fetch F1 winner odds from Betfair Exchange.")
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--season", type=int, required=True)
    args = parser.parse_args()

    try:
        out = fetch_betfair_winner_odds(args.round, args.season)
    except BetfairAuthError as exc:
        print(f"ERROR (auth): {exc}", file=sys.stderr)
        return 2
    print(f"OK: wrote {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
