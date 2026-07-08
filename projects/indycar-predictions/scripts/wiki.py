"""Wikipedia fetch + cache helpers for IndyCar curation.

Every network response is cached to ``data/raw_cache/`` (gitignored) so the
curation is reproducible and re-runs hit disk, not the API. We use the MediaWiki
``action=parse&prop=wikitext`` endpoint — season and per-race articles are the
most stable HTML/markup source and are CC BY-SA (cite in SOURCES.md).
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

UA = {
    "User-Agent": (
        "MotorsportVerse-IndyCarCuration/1.0 "
        "(research; contact shenorrlab@technion.ac.il)"
    )
}
API = "https://en.wikipedia.org/w/api.php"

_ROOT = Path(__file__).resolve().parent.parent
CACHE = _ROOT / "data" / "raw_cache"
CACHE.mkdir(parents=True, exist_ok=True)

_LAST = {"t": 0.0}
_MIN_INTERVAL = 0.6  # polite rate limit


def _throttle() -> None:
    dt = time.time() - _LAST["t"]
    if dt < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - dt)
    _LAST["t"] = time.time()


def wikitext(page: str, *, refresh: bool = False) -> str:
    """Return the raw wikitext of ``page``, caching to disk."""
    key = hashlib.sha1(page.encode()).hexdigest()[:16]
    safe = "".join(c if c.isalnum() else "_" for c in page)[:60]
    fp = CACHE / f"{safe}__{key}.wikitext"
    if fp.exists() and not refresh:
        return fp.read_text(encoding="utf-8")
    _throttle()
    r = requests.get(
        API,
        headers=UA,
        params={
            "action": "parse",
            "page": page,
            "prop": "wikitext",
            "format": "json",
            "redirects": 1,
        },
        timeout=30,
    )
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"wiki error for {page!r}: {j['error'].get('info')}")
    text = j["parse"]["wikitext"]["*"]
    fp.write_text(text, encoding="utf-8")
    return text


def exists(page: str) -> bool:
    try:
        wikitext(page)
        return True
    except Exception:
        return False
