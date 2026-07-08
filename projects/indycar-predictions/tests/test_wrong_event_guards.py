"""Wrong-event + poisoned-page guards: a mismatched or dirty page can never be
ingested as a round.

Root-caused from the F1 flagship's 2026-07-05 incident (FastF1 fuzzy-matched
Great Britain → Austria and published R8 results as R9 pre-race): every live
path verifies event identity and refuses partial/garbage parses BEFORE
anything can reach the committed snapshot. The committed snapshot itself is
append-only (refresh) and immutable (fingerprint check).
"""
from __future__ import annotations

import copy
import json

import pytest
from conftest import (
    FakeWikiClient,
    article_title,
    build_wiki_pages,
    load_history,
    make_race_article,
    synthetic_new_round_results,
)

from indycar_predictions import config, refresh
from indycar_predictions.sources.indycar_scraper_source import (
    DirtyParseError,
    IndycarScraperSource,
    WrongEventError,
    validate_classification,
    verify_article_title,
    verify_round_identity,
)

SEASON = config.SEASON
TODAY = "2026-07-20"


def _scraper(pages):
    return IndycarScraperSource(client=FakeWikiClient(pages), today=TODAY)


# --------------------------------------------------------------------------- #
# Identity units
# --------------------------------------------------------------------------- #
def test_round_identity_ok():
    meta = config.CALENDAR_META[12]
    verify_round_identity(
        {"venue": meta["venue"], "date": meta["date"]}, year=SEASON, round=12
    )


def test_round_identity_venue_mismatch_raises():
    with pytest.raises(WrongEventError):
        verify_round_identity(
            {"venue": "Texas Motor Speedway", "date": config.CALENDAR_META[12]["date"]},
            year=SEASON,
            round=12,
        )


def test_round_identity_date_mismatch_raises():
    with pytest.raises(WrongEventError):
        verify_round_identity(
            {"venue": config.CALENDAR_META[12]["venue"], "date": "2026-08-01"},
            year=SEASON,
            round=12,
        )


def test_article_title_must_name_the_season():
    verify_article_title("2026 Bommarito Automotive Group 500", year=2026, round=9)
    with pytest.raises(WrongEventError):
        verify_article_title("2019 Bommarito Automotive Group 500", year=2026, round=9)


# --------------------------------------------------------------------------- #
# Clean-parse gate units
# --------------------------------------------------------------------------- #
def _rows(n=25, indy500=False):
    rows = synthetic_new_round_results(12)[:n]
    return rows


def test_validate_classification_accepts_clean_rows():
    validate_classification(_rows(), year=SEASON, round=12)


def test_truncated_table_is_refused():
    with pytest.raises(DirtyParseError, match="car count"):
        validate_classification(_rows(12), year=SEASON, round=12)


def test_oversized_field_is_refused_outside_the_500():
    rows = synthetic_new_round_results(12)
    extra = [
        dict(rows[0], position=len(rows) + i + 1, driver=name)
        for i, name in enumerate(
            ["Conor Daly", "Takuma Sato", "Jack Harvey", "Ed Carpenter",
             "Hélio Castroneves", "Katherine Legge"]
        )
    ]
    with pytest.raises(DirtyParseError, match="car count"):
        validate_classification(rows + extra, year=SEASON, round=12)


def test_duplicate_positions_are_refused():
    rows = _rows()
    rows[3]["position"] = 3  # duplicate P3
    with pytest.raises(DirtyParseError, match="duplicate|contiguous"):
        validate_classification(rows, year=SEASON, round=12)


def test_missing_points_are_refused():
    rows = _rows()
    for r in rows[:6]:
        r["points"] = None
    with pytest.raises(DirtyParseError, match="points"):
        validate_classification(rows, year=SEASON, round=12)


def test_roster_poisoned_page_is_refused():
    rows = _rows()
    for i, r in enumerate(rows):
        if i % 2 == 0:  # half the field are strangers → not our series
            r["driver"] = f"Unknown Stranger{i}"
    with pytest.raises(DirtyParseError, match="whitelist"):
        validate_classification(rows, year=SEASON, round=12)


def test_indy500_band_allows_33_cars(snapshot_source):
    rows = [
        {k: r.get(k) for k in ("position", "driver", "team", "engine", "grid",
                               "laps", "status", "points")}
        for r in load_history(SEASON)["rounds"][6]["results"]
    ]
    assert len(rows) == 33
    validate_classification(rows, year=SEASON, round=7)  # is_indy500_round(7)
    with pytest.raises(DirtyParseError, match="car count"):
        validate_classification(rows, year=SEASON, round=12)  # not the 500


# --------------------------------------------------------------------------- #
# Scraper integration: poisoned pages
# --------------------------------------------------------------------------- #
def test_scraper_refuses_wrong_venue_schedule():
    pages = build_wiki_pages(12, venue_override={12: "Texas Motor Speedway"})
    with pytest.raises(WrongEventError):
        _scraper(pages).season_state(SEASON)


def test_scraper_refuses_schedule_count_drift():
    pages = build_wiki_pages(12)
    season_page = pages[f"{SEASON} IndyCar Series"]
    # Drop the last schedule row (a "cancelled" round) — 17 != 18 must refuse.
    lines = season_page.splitlines()
    idx = lines.index("! 18")
    del lines[idx - 1: idx + 2]
    pages[f"{SEASON} IndyCar Series"] = "\n".join(lines)
    with pytest.raises(WrongEventError, match="championship rounds"):
        _scraper(pages).season_state(SEASON)


def test_scraper_refuses_wrong_year_article():
    pages = build_wiki_pages(12)
    wrong_title = "2019 Bommarito Automotive Group 500"
    season_page = pages[f"{SEASON} IndyCar Series"]
    pages[f"{SEASON} IndyCar Series"] = season_page.replace(
        f"[[{article_title(12)}|Report]]", f"[[{wrong_title}|Report]]"
    )
    pages[wrong_title] = pages.pop(article_title(12))
    with pytest.raises(WrongEventError, match="does not name"):
        _scraper(pages).season_state(SEASON)


def test_scraper_refuses_truncated_classification():
    truncated = make_race_article(synthetic_new_round_results(12)[:12])
    pages = build_wiki_pages(12, article_override={12: truncated})
    with pytest.raises(DirtyParseError, match="car count"):
        _scraper(pages).results(SEASON, 12)


def test_scraper_refuses_schedule_page_served_as_results():
    """An article carrying only a schedule-ish table (no points column) must
    never count as a race classification — and the season parse goes dirty."""
    schedule_page = "\n".join(
        [
            "==Schedule==",
            '{| class="wikitable"',
            "! Rd !! Date !! Track/Location",
            "|-",
            "! 1",
            "| July 19 || [[Nashville Superspeedway]]",
            "|}",
        ]
    )
    pages = build_wiki_pages(12, article_override={12: schedule_page})
    src = _scraper(pages)
    with pytest.raises(DirtyParseError, match="not clean"):
        src.results(SEASON, 12)


# --------------------------------------------------------------------------- #
# refresh: --require-clean-parse semantics (ANY failure = no snapshot write)
# --------------------------------------------------------------------------- #
def test_refresh_appends_validated_new_round():
    existing = load_history(SEASON)
    src = _scraper(build_wiki_pages(12))
    snapshot, appended = refresh.build_refreshed_snapshot(SEASON, existing, source=src)
    assert appended == [12]
    assert snapshot["rounds_curated"] == 12
    assert snapshot["rounds"][11]["round"] == 12
    assert snapshot["rounds"][11]["venue_key"] == config.CALENDAR_META[12]["key"]
    v = snapshot["verification"]
    assert v["champion_match"] and v["top5_match"]
    assert v["n_mismatches"] == 0
    # Committed rounds are byte-identical (append-only).
    assert snapshot["rounds"][:11] == existing["rounds"]


def test_refresh_noop_when_nothing_new():
    existing = load_history(SEASON)
    src = _scraper(build_wiki_pages(11))
    snapshot, appended = refresh.build_refreshed_snapshot(SEASON, existing, source=src)
    assert appended == []
    assert snapshot["rounds"] == existing["rounds"]


def test_refresh_refuses_truncated_new_round():
    existing = load_history(SEASON)
    truncated = make_race_article(synthetic_new_round_results(12)[:12])
    src = _scraper(build_wiki_pages(12, article_override={12: truncated}))
    with pytest.raises(DirtyParseError):
        refresh.build_refreshed_snapshot(SEASON, existing, source=src)


def test_refresh_refuses_retro_edited_history():
    """A committed round whose fresh parse has a different winner is a
    wrong-event/vandalism signal — the whole refresh must refuse."""
    existing = load_history(SEASON)
    pages = build_wiki_pages(12)
    # Swap P1/P2 in round 5's article.
    r5 = copy.deepcopy(load_history(SEASON)["rounds"][4]["results"])
    r5[0]["position"], r5[1]["position"] = 2, 1
    r5[0], r5[1] = r5[1], r5[0]
    pages[article_title(5)] = make_race_article(r5)
    with pytest.raises(WrongEventError, match="retro-edit|disagrees"):
        refresh.build_refreshed_snapshot(SEASON, existing, source=_scraper(pages))


def test_refresh_refuses_wrong_season_file():
    with pytest.raises(RuntimeError, match="refresh only ever appends"):
        refresh.build_refreshed_snapshot(SEASON, {"season": 2025, "rounds": []})


def test_refresh_refuses_corrupt_standings():
    """If summed per-race points no longer reproduce the official grid's
    champion/top-5, something is deeply wrong — refuse."""
    existing = load_history(SEASON)
    pages = build_wiki_pages(12)
    season_page = pages[f"{SEASON} IndyCar Series"]
    # Corrupt the standings grid: make a backmarker the "official" champion.
    pages[f"{SEASON} IndyCar Series"] = season_page.replace(
        "| [[Álex Palou]]", "| [[Mick Schumacher]]", 1
    )
    with pytest.raises(DirtyParseError, match="standings verification"):
        refresh.build_refreshed_snapshot(SEASON, existing, source=_scraper(pages))


def test_refresh_calendar_sync(tmp_path):
    cal_src = json.loads(
        (config._DATA_DIR / f"calendar_{SEASON}.json").read_text(encoding="utf-8")
    )
    p = tmp_path / "calendar.json"
    p.write_text(json.dumps(cal_src))
    refresh.update_calendar_file(SEASON, 12, path=p)
    out = json.loads(p.read_text())
    assert out["completed_rounds"] == 12
    assert out["remaining_rounds"] == out["total_rounds"] - 12
    assert [c["completed"] for c in out["calendar"]] == [r <= 12 for r in range(1, 19)]
