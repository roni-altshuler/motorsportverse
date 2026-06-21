"""OddsAPI ingest + cache + de-vig.

Lightweight client around https://the-odds-api.com/ for F1 outright (race
winner) markets.  This is the only network-touching module in the betting
layer; it must therefore be:

* Deterministic in offline mode (read from `odds_cache/` if present).
* Free of side effects beyond writing the cache JSON.
* Easy to mock for tests — every HTTP call goes through a single `requests.get`
  invocation in `_fetch_raw`.

Design choices:

* We do **not** post-process inside `fetch_winner_odds` (no de-vig, no model
  joining).  That returns the raw bookmaker view; downstream code decides what
  to do with it.
* Driver normalization is by **substring match on the OddsAPI participant
  name** against `DRIVER_FULL_NAMES`.  OddsAPI is inconsistent across books
  ("Max Verstappen" vs "Verstappen, Max" vs "M. Verstappen") so substring
  matching on last name is more robust than an exact-match dict.
* `devig_proportional` is the simplest reasonable method.  Shin's method is
  better but requires solving for the overround parameter; not worth the
  complexity for a v1 quarter-Kelly tool.

Env contract:
    ODDS_API_KEY   required, no default.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Optional .env loading.  python-dotenv is in requirements-dev.txt; the
# try/except keeps runtime installs of just requirements.txt working — missing
# dotenv silently falls back to plain os.environ.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import requests

from f1_prediction_utils import DRIVER_FULL_NAMES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "odds_cache"
API_BASE = "https://api.the-odds-api.com/v4/sports/motorsport_f1/odds"
DEFAULT_TIMEOUT_S = 10


# ---------------------------------------------------------------------------
# Driver normalization
# ---------------------------------------------------------------------------


def _build_lastname_lookup() -> dict[str, str]:
    """Map lowercased last name -> driver code.

    Last name is the last whitespace-separated token of `DRIVER_FULL_NAMES`,
    lowercased and stripped of accents-removed via NFKD where convenient.
    We keep it simple: lowercase + last token.  Ambiguity (two drivers sharing
    a last name) would need handling — currently the 2026 grid has none.
    """
    out: dict[str, str] = {}
    for code, full in DRIVER_FULL_NAMES.items():
        # Strip trailing punctuation ("Sainz Jr." -> "Sainz Jr")
        clean = full.replace(".", "").strip()
        tokens = clean.split()
        if not tokens:
            continue
        last = tokens[-1].lower()
        # "Sainz Jr" -> use "Sainz" as the last name.
        if last == "jr" and len(tokens) >= 2:
            last = tokens[-2].lower()
        out[last] = code
    return out


_LASTNAME_TO_CODE: dict[str, str] = _build_lastname_lookup()


def normalize_driver(name: str) -> str | None:
    """Map an OddsAPI participant name to a driver code, or None if unknown.

    Strategy:
      1. Exact match on a full-name in `DRIVER_FULL_NAMES` (case-insensitive).
      2. Last-token (last name) match against the precomputed lookup.
      3. Substring scan: any token of the input that equals a known last name.

    Returns None if no driver can be resolved.  Callers should log + drop.
    """
    if not name:
        return None
    n = name.strip().lower()
    if not n:
        return None

    # 1. Exact full-name.
    for code, full in DRIVER_FULL_NAMES.items():
        if full.lower() == n:
            return code

    # 2. Last token.
    last = n.split()[-1].rstrip(".,;:")
    if last in _LASTNAME_TO_CODE:
        return _LASTNAME_TO_CODE[last]

    # 3. Any token equal to a known last name.
    for tok in n.replace(",", " ").split():
        tok = tok.rstrip(".").lower()
        if tok in _LASTNAME_TO_CODE:
            return _LASTNAME_TO_CODE[tok]

    return None


# ---------------------------------------------------------------------------
# De-vig
# ---------------------------------------------------------------------------


def devig_proportional(odds: dict[str, float]) -> dict[str, float]:
    """Convert decimal odds to a proper probability distribution.

    Implied prob per outcome = 1 / odds.  The sum exceeds 1 because of the
    bookmaker's overround (vig).  We rescale proportionally so the
    distribution sums to 1.  This is the cheapest de-vig method; it implicitly
    assumes the bookmaker spreads the vig uniformly across outcomes, which is
    usually wrong but is a fine v1 default.

    Returns an empty dict if input is empty or all odds are non-positive.
    """
    if not odds:
        return {}
    implied: dict[str, float] = {}
    for k, o in odds.items():
        if o is None or o <= 1.0:
            continue
        implied[k] = 1.0 / float(o)
    total = sum(implied.values())
    if total <= 0.0:
        return {}
    return {k: v / total for k, v in implied.items()}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_path(round_number: int, when: datetime) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    return CACHE_DIR / f"round_{round_number:02d}_{stamp}.json"


def latest_cached_snapshot(round_number: int) -> Path | None:
    """Return the most recent cached odds file for this round, or None."""
    if not CACHE_DIR.exists():
        return None
    pat = f"round_{round_number:02d}_*.json"
    candidates = sorted(CACHE_DIR.glob(pat))
    return candidates[-1] if candidates else None


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _fetch_raw(api_key: str, regions: str = "eu,uk,us") -> list[dict]:
    """Single HTTP call.  Isolated so tests can mock this with `unittest.mock`."""
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": "outrights",
        "oddsFormat": "decimal",
    }
    resp = requests.get(API_BASE, params=params, timeout=DEFAULT_TIMEOUT_S)
    if resp.status_code == 404:
        # The Odds API does not currently include F1 / motorsport in its catalog
        # (verified 2026-05 — the catalog covers 160+ sports but no auto racing).
        # Surface this clearly instead of a generic HTTP 404 trace.
        raise SystemExit(
            "ERROR: OddsAPI has no F1 sport key in this account's catalog.\n"
            "  Endpoint hit: " + API_BASE + "\n"
            "  Status: 404 (sport key 'motorsport_f1' not recognised).\n"
            "\n"
            "  F1 is not available on The Odds API today, even on paid tiers.\n"
            "  Alternative odds sources to consider (see project plan for context):\n"
            "    - Pinnacle direct API (requires funded account)\n"
            "    - Betfair Exchange API (requires KYC; UK/AU/EU regions)\n"
            "    - Manual CSV import from Oddschecker or similar aggregator\n"
            "\n"
            "  No quota was charged for this call."
        )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError(f"OddsAPI returned unexpected payload type: {type(data).__name__}")
    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_winner_odds(
    round_number: int,
    season: int,
    *,
    api_key: str | None = None,
    write_cache: bool = True,
) -> dict[str, dict[str, float]]:
    """Fetch race-winner outright odds for the next F1 event from OddsAPI.

    Parameters
    ----------
    round_number
        Numeric round; used only for cache filename.  OddsAPI itself does not
        accept a round filter — it returns the *next* scheduled event.
        Production code should sanity-check that the returned event matches
        the requested round (the response contains the event start date).
    season
        Calendar year; same purpose as `round_number`.
    api_key
        Override the `ODDS_API_KEY` env var.  Primarily a test hook.
    write_cache
        If True (default), write the response to `odds_cache/round_NN_*.json`.

    Returns
    -------
    dict
        ``{bookmaker_key: {driver_code: decimal_odds}}``

    Drivers OddsAPI lists but we can't normalize are silently dropped.
    Bookmakers with zero recognized drivers are dropped.
    """
    key = api_key or os.environ.get("ODDS_API_KEY")
    if not key:
        print(
            "ERROR: ODDS_API_KEY env var not set.\n"
            "  Get a free key at https://the-odds-api.com/ and export it:\n"
            "    export ODDS_API_KEY=...\n"
            "Aborting.",
            file=sys.stderr,
        )
        sys.exit(2)

    raw = _fetch_raw(key)

    if write_cache:
        path = _cache_path(round_number, datetime.now(timezone.utc))
        with path.open("w") as f:
            json.dump(
                {
                    "season": season,
                    "round": round_number,
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                    "payload": raw,
                },
                f,
                indent=2,
            )

    return parse_winner_odds(raw)


def parse_winner_odds(raw: list[dict]) -> dict[str, dict[str, float]]:
    """Convert OddsAPI payload -> {bookmaker: {driver_code: decimal_odds}}.

    Schema (excerpt) — the v4 API returns a list of events; we expect one
    upcoming event but iterate defensively and take the soonest::

        [
          { "id": ..., "commence_time": "...", "bookmakers": [
              { "key": "pinnacle", "markets": [
                  { "key": "outrights", "outcomes": [
                      { "name": "Max Verstappen", "price": 3.5 },
                      ...
                  ]}
              ]},
              ...
          ]}
        ]
    """
    if not raw:
        return {}

    # Choose the soonest event (assume it's the round being fetched).
    events = sorted(
        (e for e in raw if isinstance(e, dict)),
        key=lambda e: e.get("commence_time", ""),
    )
    if not events:
        return {}
    event = events[0]

    out: dict[str, dict[str, float]] = {}
    for book in event.get("bookmakers", []) or []:
        if not isinstance(book, dict):
            continue
        book_key = book.get("key") or book.get("title")
        if not book_key:
            continue
        book_odds: dict[str, float] = {}
        for market in book.get("markets", []) or []:
            if market.get("key") != "outrights":
                continue
            for outcome in market.get("outcomes", []) or []:
                name = outcome.get("name")
                price = outcome.get("price")
                if not name or price is None:
                    continue
                code = normalize_driver(name)
                if code is None:
                    continue
                try:
                    book_odds[code] = float(price)
                except (TypeError, ValueError):
                    continue
        if book_odds:
            out[book_key] = book_odds
    return out


def load_cached_payload(path: Path) -> dict[str, dict[str, float]]:
    """Load a previously-cached snapshot and run it through `parse_winner_odds`."""
    with path.open() as f:
        blob = json.load(f)
    raw = blob.get("payload", blob)  # supports both wrapped + bare payloads
    if not isinstance(raw, list):
        return {}
    return parse_winner_odds(raw)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch F1 winner outright odds.")
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--season", type=int, required=True)
    args = parser.parse_args()

    odds = fetch_winner_odds(args.round, args.season)
    for book, d in sorted(odds.items()):
        print(f"\n[{book}]")
        for code, price in sorted(d.items(), key=lambda kv: kv[1]):
            print(f"  {code:3s}  {price:6.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
