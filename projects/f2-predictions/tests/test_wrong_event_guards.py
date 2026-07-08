"""Regression tests for the wrong-event ingestion guards (F2).

On 2026-07-05 (F1, British GP race morning) FastF1's fuzzy event matcher
silently "corrected" 'Great Britain' to the Austrian Grand Prix and the
pipeline published Austria's classification as Silverstone's official result.
F2 scrapes fiaformula2.com per-raceid instead, but the same class of bug —
a cache/proxy/CMS serving a *different round's page* for a requested raceid —
would flow straight into the committed snapshot. These tests pin the guards
that make that impossible:

  * ``FiaFeederSource.verify_page_identity`` — the page's own title (round
    number + country + city + dates) must match the requested round before
    anything is parsed; a mismatch raises ``WrongEventError``.
  * ``FiaF2Source.results``/``qualifying`` refuse (return ``None`` → the
    composite defers) when the fetched page is not the requested round.
  * ``refresh.build_snapshot`` cross-checks every round page against the
    human-verified calendar in ``config`` (round number AND country) and
    raises before ``main()`` ever writes — a wrong event can never mutate
    ``data/official_2026.json``.
  * A truncated/garbage page (no parseable round title) is rejected the same
    way, even if a stray results table would still regex-match.
"""
from __future__ import annotations

import json
import sys

import pytest
from f2_predictions import config, refresh
from f2_predictions.sources.fia_f2_source import FiaF2Source, WrongEventError

SEASON = config.SEASON


def _round_page(round_num: int, country: str, city: str, codes: list[str]) -> str:
    """A minimal fiaformula2.com-shaped round page: title + Feature/Sprint tables."""
    def _rows(order: list[str]) -> str:
        return "".join(
            f'<tr><td><div class="pos">{i}</div><div class="car-no">{i}</div>'
            f'<span class="visible-desktop-up">D. {code.title()}</span>'
            f'<span class="visible-desktop-down">{code}</span>'
            f'<span class="team-name">Team {code}</span></td></tr>'
            for i, code in enumerate(order, start=1)
        )

    title = (
        f"Formula 2 {SEASON} Result for Round {round_num} : {country} , "
        f"{city} 01-03 May {SEASON}"
    )
    return (
        f"<html><body><h1>{title}</h1>"
        f"<span>Feature Race</span><table><tbody>{_rows(codes)}</tbody></table>"
        f"<span>Sprint Race</span><table><tbody>{_rows(list(reversed(codes)))}</tbody></table>"
        f"</body></html>"
    )


_CODES = ["AAA", "BBB", "CCC"]
SILVERSTONE = _round_page(7, "United Kingdom", "Silverstone", _CODES)
AUSTRIA = _round_page(6, "Austria", "Spielberg", _CODES)
# A results table with NO round title — the shape of a truncated/garbage page.
GARBAGE = SILVERSTONE.split("</h1>", 1)[1]


def _offline_source(round_num: int, page: str) -> FiaF2Source:
    """A FiaF2Source whose caches are primed so no network happens: the round
    map says ``round_num`` lives at raceid 999, and raceid 999 serves ``page``."""
    src = FiaF2Source()
    src._round_map_cache[SEASON] = {round_num: 999}
    src._page_cache[999] = page
    return src


# ── verify_page_identity: the identity gate itself ──────────────────────────

def test_identity_accepts_the_requested_round():
    identity = FiaF2Source.verify_page_identity(SILVERSTONE, expected_round=7)
    assert identity["round"] == 7
    assert identity["country"] == "United Kingdom"


def test_identity_rejects_another_rounds_page():
    with pytest.raises(WrongEventError, match="round 6"):
        FiaF2Source.verify_page_identity(AUSTRIA, expected_round=7)


def test_identity_rejects_country_mismatch():
    # Right round number, wrong venue — e.g. a stale CMS page reused a title.
    with pytest.raises(WrongEventError, match="Austria"):
        FiaF2Source.verify_page_identity(
            _round_page(7, "Austria", "Spielberg", _CODES),
            expected_round=7,
            expected_country="United Kingdom",
        )


def test_identity_accepts_matching_country_and_parenthetical_variants():
    FiaF2Source.verify_page_identity(
        SILVERSTONE, expected_round=7, expected_country="United Kingdom"
    )
    # Round 11: config says "Spain" for Madrid; a "Spain (Madrid)" label folds to it.
    madrid = _round_page(11, "Spain", "Madrid", _CODES)
    FiaF2Source.verify_page_identity(
        madrid, expected_round=11, expected_country="Spain (Madrid)"
    )


def test_identity_rejects_truncated_or_garbage_page():
    for page in (GARBAGE, "", None, "<html>503 Service Unavailable</html>"):
        with pytest.raises(WrongEventError, match="no parseable round title"):
            FiaF2Source.verify_page_identity(page, expected_round=7)


# ── results()/qualifying(): the fetch path refuses, the composite defers ────

def test_results_refuse_wrong_event_page():
    src = _offline_source(7, AUSTRIA)  # raceid resolves, but serves round 6's page
    assert src.results(SEASON, 7, race_index=1) is None
    assert src.results(SEASON, 7, race_index=0) is None
    # Nothing from the wrong page leaked into the entry list.
    assert src.entry_list(SEASON) == {}


def test_results_refuse_garbage_page_despite_parseable_table():
    # GARBAGE still contains a valid Feature Race table — identity, not table
    # shape, is what admits a page.
    src = _offline_source(7, GARBAGE)
    assert src.results(SEASON, 7, race_index=1) is None


def test_results_accept_the_correct_event():
    src = _offline_source(7, SILVERSTONE)
    rows = src.results(SEASON, 7, race_index=1)
    assert [r.competitor for r in rows] == _CODES
    assert [r.position for r in rows] == [1, 2, 3]


def test_qualifying_refuses_wrong_event_page():
    quali_page = AUSTRIA.replace("Sprint Race", "Qualifying")
    src = _offline_source(7, quali_page)
    assert src.qualifying(SEASON, 7) is None


def test_qualifying_accepts_the_correct_event():
    quali_page = SILVERSTONE.replace("Sprint Race", "Qualifying")
    src = _offline_source(7, quali_page)
    assert src.qualifying(SEASON, 7) == list(reversed(_CODES))


# ── refresh: a wrong event aborts BEFORE any snapshot write ─────────────────

def _patch_refresh_feed(monkeypatch, page: str, round_num: int = 1):
    """Make refresh's FiaF2Source fully offline: one calendar entry for
    ``round_num`` whose raceid serves ``page``; standings pages unavailable."""
    entry = {
        "round": round_num,
        "raceid": 999,
        "country": config.CALENDAR[round_num - 1].country,
        "city": "Somewhere",
        "dates": f"01-03 May {SEASON}",
    }
    monkeypatch.setattr(FiaF2Source, "calendar", lambda self, year: [entry])
    monkeypatch.setattr(FiaF2Source, "_page", lambda self, raceid: page)
    monkeypatch.setattr(refresh, "_fetch", lambda url, timeout=25: None)


def test_refresh_raises_on_wrong_event_and_writes_no_snapshot(monkeypatch, tmp_path):
    out = tmp_path / "official.json"
    # Round 1 (Australia)'s raceid serves the Austria round-6 page.
    _patch_refresh_feed(monkeypatch, AUSTRIA, round_num=1)
    monkeypatch.setattr(
        sys, "argv", ["refresh", "--season", str(SEASON), "--out", str(out)]
    )
    with pytest.raises(WrongEventError):
        refresh.main()
    assert not out.exists(), "a wrong-event scrape must never write a snapshot"


def test_refresh_raises_on_country_mismatch_even_with_matching_round(monkeypatch, tmp_path):
    out = tmp_path / "official.json"
    # Round number echoes correctly but the page is a different venue.
    wrong_venue = _round_page(1, "Austria", "Spielberg", _CODES)
    _patch_refresh_feed(monkeypatch, wrong_venue, round_num=1)
    monkeypatch.setattr(
        sys, "argv", ["refresh", "--season", str(SEASON), "--out", str(out)]
    )
    with pytest.raises(WrongEventError):
        refresh.main()
    assert not out.exists()


def test_refresh_rejects_truncated_page(monkeypatch, tmp_path):
    out = tmp_path / "official.json"
    _patch_refresh_feed(monkeypatch, GARBAGE, round_num=1)
    monkeypatch.setattr(
        sys, "argv", ["refresh", "--season", str(SEASON), "--out", str(out)]
    )
    with pytest.raises(WrongEventError):
        refresh.main()
    assert not out.exists()


def test_refresh_happy_path_still_ingests(monkeypatch, tmp_path):
    out = tmp_path / "official.json"
    australia = _round_page(1, config.CALENDAR[0].country, "Melbourne", _CODES)
    _patch_refresh_feed(monkeypatch, australia, round_num=1)
    monkeypatch.setattr(
        sys, "argv", ["refresh", "--season", str(SEASON), "--out", str(out)]
    )
    refresh.main()
    snap = json.loads(out.read_text())
    assert snap["completedRounds"] == 1
    feature = snap["results"]["1"]["feature"]
    assert [r["code"] for r in feature] == _CODES


# ── The committed snapshot must agree with the config calendar ──────────────

def test_committed_snapshot_calendar_matches_config_countries():
    """Every completed round in the committed snapshot must carry the country
    the config calendar expects — i.e. the refresh guard would accept exactly
    the data we have committed (and the guard's country source of truth,
    Venue.country, matches the FIA page titles for all 14 rounds)."""
    snap_path = refresh._DEFAULT_OUT
    if not snap_path.exists():
        pytest.skip("no committed snapshot")
    snap = json.loads(snap_path.read_text())
    fold = FiaF2Source._normalise_country
    for entry in snap.get("calendar", []):
        rnd = entry["round"]
        scraped = entry.get("country")
        if not scraped:  # rounds the scrape never resolved carry no country
            continue
        expected = config.CALENDAR[rnd - 1].country
        assert fold(scraped) == fold(expected), (
            f"round {rnd}: snapshot country {scraped!r} != config {expected!r} — "
            f"either wrong-event data was committed or the guard would refuse a "
            f"legitimate refresh"
        )
