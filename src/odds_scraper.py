"""Multi-source odds scraper + bulk CSV ingester.

Two jobs that share an output contract:

1. **Bulk-ingest** every CSV in ``odds_inbox/`` matching ``round_NN*.csv``,
   treating each file as a separate bookmaker.  The bookmaker key is taken
   from the filename suffix (``round_06_pinnacle.csv`` → ``pinnacle``).  A
   single combined snapshot is written to ``odds_cache/`` listing all
   bookmakers; downstream ``select_bookmaker`` in `export_value_data.py`
   picks the sharpest available book automatically.

2. **Scrape** odds from public web sources (Oddschecker by default), saving
   the parsed table to ``odds_inbox/round_NN_<source>.csv`` so it joins the
   bulk-ingest pool.  Each source is a plugin (``OddscheckerScraper``,
   future: ``OddsPortalScraper``, etc.).

CLI patterns::

    # Just ingest whatever CSVs are already in odds_inbox/
    python odds_scraper.py --round 6 --season 2026 --ingest-only

    # Scrape Oddschecker, save to odds_inbox/, then ingest everything
    python odds_scraper.py --round 6 --season 2026 --scrape oddschecker

    # Scrape all enabled sources, then ingest
    python odds_scraper.py --round 6 --season 2026 --scrape all

Scraping caveats (be a responsible citizen):
- Sets a polite User-Agent identifying the project.
- One request per source per run; no auto-retry.
- Respects ``robots.txt`` only as a best-effort signal — see SCRAPING.md.
- HTML parsers are fragile; if a scrape fails, fall back to manual CSV.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import requests

from f1_prediction_utils import CALENDAR, DRIVER_FULL_NAMES  # noqa: E402
from odds_import_csv import MIN_DRIVERS_MATCHED, parse_csv  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = PROJECT_ROOT / "odds_inbox"
CACHE_DIR = PROJECT_ROOT / "odds_cache"
SEASON_DATA = PROJECT_ROOT / "website" / "public" / "data" / "season.json"

USER_AGENT = (
    "f1-predictions-bot/0.1 "
    "(personal-use; https://github.com/<you>/f1_predictions; "
    "contact via repo issues)"
)
REQUEST_TIMEOUT_S = 20.0
ROBOTS_TIMEOUT_S = 5.0


# --------------------------------------------------------------------------- #
# Bulk-ingest layer
# --------------------------------------------------------------------------- #


@dataclass
class IngestedBook:
    bookmaker: str
    csv_path: Path
    odds: dict[str, float] = field(default_factory=dict)


_INBOX_FILE_RE = re.compile(r"^round_(\d{2})(?:_([A-Za-z0-9_\-]+))?\.csv$")


def discover_inbox_csvs(round_number: int, inbox_dir: Path = INBOX_DIR) -> list[IngestedBook]:
    """Find every CSV in ``inbox_dir`` belonging to ``round_number``.

    Filename → bookmaker mapping:
      - ``round_06.csv``                → bookmaker ``"oddschecker_manual"`` (legacy default)
      - ``round_06_pinnacle.csv``       → ``"pinnacle"``
      - ``round_06_betfair_ex_eu.csv``  → ``"betfair_ex_eu"``
      - ``round_06_anything.csv``       → ``"anything"``

    Each CSV is parsed via ``odds_import_csv.parse_csv`` (which already enforces
    ``MIN_DRIVERS_MATCHED``); failures are logged and that file is skipped.
    """
    if not inbox_dir.exists():
        return []
    out: list[IngestedBook] = []
    for path in sorted(inbox_dir.glob(f"round_{round_number:02d}*.csv")):
        m = _INBOX_FILE_RE.match(path.name)
        if not m:
            continue
        if int(m.group(1)) != round_number:
            continue
        bookmaker = m.group(2) or "oddschecker_manual"
        try:
            odds = parse_csv(path)
        except ValueError as exc:
            print(f"  skipping {path.name}: {exc}", file=sys.stderr)
            continue
        out.append(IngestedBook(bookmaker=bookmaker, csv_path=path, odds=odds))
    return out


# --------------------------------------------------------------------------- #
# Snapshot writing — multi-bookmaker variant
# --------------------------------------------------------------------------- #


def _cache_path(round_number: int, when: datetime) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    return CACHE_DIR / f"round_{round_number:02d}_{stamp}_multi.json"


def _build_snapshot(
    round_number: int,
    season: int,
    books: list[IngestedBook],
) -> dict:
    """Wrap multiple bookmakers into one wrapped-payload snapshot.

    `select_bookmaker` in export_value_data.py iterates a preferred list
    (Pinnacle > Betfair > …) — so the more bookmakers you stuff in here, the
    better chance the downstream picks a sharp line.
    """
    now = datetime.now(timezone.utc)
    bookmaker_entries: list[dict[str, Any]] = []
    for book in books:
        outcomes = [
            {"name": DRIVER_FULL_NAMES.get(code, code), "price": float(price)}
            for code, price in book.odds.items()
        ]
        bookmaker_entries.append(
            {
                "key": book.bookmaker,
                "title": book.bookmaker.replace("_", " ").title(),
                "last_update": now.isoformat(),
                "markets": [
                    {
                        "key": "outrights",
                        "last_update": now.isoformat(),
                        "outcomes": outcomes,
                    }
                ],
            }
        )
    payload = [
        {
            "id": f"multi-{season}-{round_number:02d}",
            "sport_key": "motorsport_f1",
            "sport_title": "Formula 1",
            "commence_time": now.isoformat(),
            "home_team": None,
            "away_team": None,
            "bookmakers": bookmaker_entries,
        }
    ]
    return {
        "season": season,
        "round": round_number,
        "fetchedAt": now.isoformat(),
        "source": "odds_scraper",
        "sourcesUsed": [b.bookmaker for b in books],
        "payload": payload,
    }


# --------------------------------------------------------------------------- #
# Scraper plugin interface
# --------------------------------------------------------------------------- #


class Scraper(ABC):
    """One scraper per source.  Each instance is a single attempt; do not reuse."""

    name: str = "abstract"

    @abstractmethod
    def fetch(self, round_number: int, season: int) -> dict[str, float]:
        """Return ``{driver_code: decimal_odds}`` or raise ``ScrapeError``."""


class ScrapeError(RuntimeError):
    """Surfaced to callers when a scraper fails.  Always treat as non-fatal —
    fall back to manual CSV."""


def _polite_get(url: str, *, session: requests.Session | None = None) -> str:
    """Single HTTP GET with project UA, modest timeout, and a robots.txt check.

    If robots.txt explicitly disallows our UA, raises ScrapeError without
    issuing the request.  Failures to fetch robots.txt are treated as "allow"
    (best-effort behaviour).
    """
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(f"{base}/robots.txt")
        rp.read()
        if not rp.can_fetch(USER_AGENT, url):
            raise ScrapeError(f"robots.txt disallows {url} for our UA")
    except ScrapeError:
        raise
    except Exception:  # noqa: BLE001 — robots.txt fetch is best-effort
        pass
    sess = session or requests.Session()
    resp = sess.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en;q=0.9"},
        timeout=REQUEST_TIMEOUT_S,
    )
    if resp.status_code == 403:
        raise ScrapeError(
            f"{url} returned 403 (likely UA/Cloudflare block). "
            "Fall back to manual CSV from the same page."
        )
    if resp.status_code >= 500:
        raise ScrapeError(f"{url} returned {resp.status_code}")
    resp.raise_for_status()
    return resp.text


def _race_slug(round_number: int) -> str | None:
    """Return the Oddschecker-style slug for the round, e.g. 'canadian'.

    Pulls from the season calendar if available; falls back to None so the
    scraper can ask the user to pass --slug.
    """
    if SEASON_DATA.exists():
        try:
            data = json.loads(SEASON_DATA.read_text())
            for entry in data.get("calendar", []):
                if entry.get("round") == round_number:
                    name = entry.get("name", "")
                    # "Canadian Grand Prix" → "canadian"; strip non-alphanum.
                    m = re.match(r"([A-Za-z\-]+)\s+Grand\s+Prix", name)
                    if m:
                        return m.group(1).lower().replace(" ", "-")
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback: derive from f1_prediction_utils CALENDAR if shaped helpfully.
    for entry in CALENDAR.values():
        if isinstance(entry, dict) and entry.get("round") == round_number:
            name = entry.get("name") or entry.get("gp_key", "")
            if name:
                return name.lower().replace(" ", "-")
    return None


class OddscheckerScraper(Scraper):
    """Scrape the F1 race-winner table at oddschecker.com.

    URL pattern: ``https://www.oddschecker.com/motorsport/formula-1/{slug}-grand-prix/winner``.

    Oddschecker renders the odds grid in JavaScript; the data is available
    as embedded JSON in a ``<script id="__NEXT_DATA__">`` tag (Next.js SSR
    pattern).  We parse that JSON.  If the structure changes the scraper
    raises ScrapeError with the URL so the user can fall back to manual CSV.
    """

    name = "oddschecker"

    BASE = "https://www.oddschecker.com/motorsport/formula-1"

    def __init__(self, slug: str | None = None) -> None:
        self.slug = slug

    def fetch(self, round_number: int, season: int) -> dict[str, float]:
        slug = self.slug or _race_slug(round_number)
        if not slug:
            raise ScrapeError(
                f"Could not derive Oddschecker slug for round {round_number}. "
                "Pass --slug explicitly (e.g. --slug canadian)."
            )
        url = f"{self.BASE}/{slug}-grand-prix/winner"
        html = _polite_get(url)
        return self._parse_next_data(html, url)

    @staticmethod
    def _parse_next_data(html: str, url: str) -> dict[str, float]:
        # Pull the Next.js hydration payload.
        m = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(?P<json>.*?)</script>',
            html,
            re.DOTALL,
        )
        if not m:
            raise ScrapeError(
                f"No __NEXT_DATA__ in {url}. Page structure changed; fall back to manual CSV."
            )
        try:
            data = json.loads(m.group("json"))
        except json.JSONDecodeError as exc:
            raise ScrapeError(f"Malformed __NEXT_DATA__ JSON at {url}: {exc}") from exc

        # Walk the nested page-props to find the runners.  Oddschecker's
        # internal shape changes every few months — we look for any leaf that
        # has both `name`/`label` and `bestPrice`/`decimalPrice`/`odds` fields.
        candidates: list[tuple[str, float]] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                name = node.get("name") or node.get("label") or node.get("runnerName")
                price = (
                    node.get("bestPrice")
                    or node.get("decimalPrice")
                    or node.get("decimalOdds")
                    or node.get("odds")
                )
                if isinstance(price, dict):
                    price = price.get("decimal") or price.get("value")
                if name and price is not None:
                    try:
                        p = float(price)
                        if p > 1.0 and isinstance(name, str):
                            candidates.append((name, p))
                    except (TypeError, ValueError):
                        pass
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(data)

        if not candidates:
            raise ScrapeError(
                f"Found no runner+price pairs in {url}. Page structure changed."
            )

        # Normalise driver names → 3-letter code; keep the lowest seen odds
        # per driver (some pages list bookmaker-by-bookmaker; we want one
        # consensus price per driver, not 22 × N rows).  Best-back logic at
        # the cross-book level happens in odds_ingest_unified.py.
        from odds_import_csv import _normalize_driver  # local import

        per_driver: dict[str, float] = {}
        for name, price in candidates:
            code = _normalize_driver(name)
            if code is None:
                continue
            cur = per_driver.get(code)
            if cur is None or price < cur:  # the best-priced row per driver
                per_driver[code] = price
        return per_driver


SCRAPERS: dict[str, type[Scraper]] = {
    "oddschecker": OddscheckerScraper,
}


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def write_scraped_to_inbox(
    round_number: int,
    scraper_name: str,
    odds: dict[str, float],
    inbox_dir: Path = INBOX_DIR,
) -> Path:
    """Persist a scraper's output as a CSV in the inbox.

    The downstream bulk-ingest then treats it like any other CSV (same code
    path as manual user drops).  This makes scrape sources first-class
    citizens with zero special-casing.
    """
    inbox_dir.mkdir(parents=True, exist_ok=True)
    out_path = inbox_dir / f"round_{round_number:02d}_{scraper_name}.csv"
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["driver", "odds"])
        for code, price in sorted(odds.items(), key=lambda kv: kv[1]):
            writer.writerow([code, f"{price:.2f}"])
    return out_path


def run(
    round_number: int,
    season: int,
    *,
    scrape: list[str] | None = None,
    ingest_only: bool = False,
    inbox_dir: Path = INBOX_DIR,
    write: bool = True,
) -> dict:
    """High-level pipeline: optional scrape → bulk-ingest → snapshot.

    Returns a dict with run metadata (scraped sources, ingested bookmakers,
    snapshot path).  When ``write=False`` the snapshot is computed but not
    written — handy for tests.
    """
    scraped: list[tuple[str, int]] = []
    if not ingest_only and scrape:
        names = list(SCRAPERS.keys()) if "all" in scrape else scrape
        for name in names:
            cls = SCRAPERS.get(name)
            if cls is None:
                print(f"  unknown scraper: {name}", file=sys.stderr)
                continue
            print(f"  scraping {name}...")
            try:
                odds = cls().fetch(round_number, season)
            except ScrapeError as exc:
                print(f"  {name} scrape failed: {exc}", file=sys.stderr)
                continue
            if len(odds) < MIN_DRIVERS_MATCHED:
                print(
                    f"  {name}: only {len(odds)} drivers parsed (need >= "
                    f"{MIN_DRIVERS_MATCHED}); skipping.",
                    file=sys.stderr,
                )
                continue
            path = write_scraped_to_inbox(round_number, name, odds, inbox_dir)
            scraped.append((name, len(odds)))
            # `relative_to` fails if the inbox is outside PROJECT_ROOT (tmp dirs
            # in tests, custom --inbox paths).  Fall back to the absolute path.
            try:
                display = str(path.relative_to(PROJECT_ROOT))
            except ValueError:
                display = str(path)
            print(f"  {name}: {len(odds)} drivers → {display}")
            # Polite pacing between scrapers.
            time.sleep(1.0)

    books = discover_inbox_csvs(round_number, inbox_dir)
    if not books:
        return {
            "round": round_number,
            "season": season,
            "scraped": scraped,
            "ingested": [],
            "snapshot": None,
            "reason": "no CSVs found in inbox",
        }

    out_path = None
    if write:
        snapshot = _build_snapshot(round_number, season, books)
        out_path = _cache_path(round_number, datetime.now(timezone.utc))
        with out_path.open("w") as f:
            json.dump(snapshot, f, indent=2)

    return {
        "round": round_number,
        "season": season,
        "scraped": scraped,
        "ingested": [(b.bookmaker, len(b.odds)) for b in books],
        "snapshot": str(out_path) if out_path else None,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape + bulk-ingest F1 odds from multiple sources.",
    )
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument(
        "--scrape",
        nargs="+",
        default=None,
        choices=list(SCRAPERS.keys()) + ["all"],
        help="Sources to scrape (default: none). Use 'all' for every registered scraper.",
    )
    parser.add_argument(
        "--ingest-only",
        action="store_true",
        help="Skip scraping; just bulk-ingest CSVs already in odds_inbox/.",
    )
    parser.add_argument(
        "--inbox",
        type=Path,
        default=INBOX_DIR,
        help="Inbox directory (default: ./odds_inbox/).",
    )
    args = parser.parse_args()

    if not args.ingest_only and args.scrape is None:
        parser.error("Pass --scrape <source>... or --ingest-only.")

    result = run(
        args.round,
        args.season,
        scrape=args.scrape,
        ingest_only=args.ingest_only,
        inbox_dir=args.inbox,
    )

    if result.get("snapshot") is None:
        reason = result.get("reason") or "unknown"
        print(f"NO SNAPSHOT WRITTEN ({reason}).", file=sys.stderr)
        return 1

    snap = Path(result["snapshot"])
    try:
        display = str(snap.relative_to(PROJECT_ROOT))
    except ValueError:
        display = str(snap)
    print(f"OK: ingested {len(result['ingested'])} bookmaker(s) → {display}")
    for book, n in result["ingested"]:
        print(f"  {book:25s}  {n} drivers")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
