"""Source layer: snapshot serving (the source of truth), status parsing,
composite fallback, and the strictly-validated Wikipedia scraper on fixtures."""
from __future__ import annotations

from conftest import FakeWikiClient, build_wiki_pages

from indycar_predictions import config
from indycar_predictions.sources.composite import CompositeIndycarSource
from indycar_predictions.sources.indycar_scraper_source import IndycarScraperSource
from indycar_predictions.sources.snapshot import is_dnf_status
from indycar_predictions.sources.synthetic import SyntheticIndycarSource

SEASON = config.SEASON


# --------------------------------------------------------------------------- #
# Status parsing (the attrition signal from the curated status fields)
# --------------------------------------------------------------------------- #
def test_is_dnf_status_running_variants():
    for s in ("1:52:21.6997", "+0.0233", "+1 Lap", "-2 Laps", "−1 Lap",
              "<nowiki>+1 Lap</nowiki>", None):
        assert not is_dnf_status(s), s


def test_is_dnf_status_retirement_variants():
    for s in ("Contact", "Mechanical", "Crash T3", "Engine", "Off Course",
              "Did Not Start", "Disqualified", "Retired", "Handling"):
        assert is_dnf_status(s), s


# --------------------------------------------------------------------------- #
# Snapshot — the committed, human-verified history files
# --------------------------------------------------------------------------- #
def test_snapshot_serves_active_season(snapshot_source):
    res = snapshot_source.results(SEASON, 1)
    assert res and res[0].position == 1
    assert res[0].competitor == "ALPALOU"  # Palou won St. Petersburg (curated)
    rows = snapshot_source.race_rows(SEASON, 1)
    assert rows and len(rows) == 25
    assert snapshot_source.completed_rounds(SEASON) == list(range(1, 12))
    # The Indy 500 ran the traditional 33-car field.
    r7 = snapshot_source.race_rows(SEASON, 7)
    assert len(r7) == 33
    assert r7[0]["code"] == "FEROSENQVIST"  # Rosenqvist won the 2026 500 (curated)
    assert any(r["dnf"] for r in r7)


def test_snapshot_qualifying_is_the_recorded_grid(snapshot_source):
    order = snapshot_source.qualifying(SEASON, 1)
    assert order and order[0] == "SCMCLAUGHLIN"  # McLaughlin on pole at St. Pete
    assert len(order) == len(set(order)) == 25


def test_snapshot_serves_archived_seasons(snapshot_source):
    res = snapshot_source.results(2019, 1)
    assert res and res[0].position == 1
    assert len(snapshot_source.completed_rounds(2019)) == 17
    cal = snapshot_source.calendar(2019)
    assert len(cal) == 17 and cal[0]["trackType"] in config.TRACK_TYPES
    st = snapshot_source.standings(2019)
    assert st and st[0]["code"] == "JONEWGARDEN"  # 2019 champion


def test_snapshot_none_for_unknown_season(snapshot_source):
    assert snapshot_source.results(2011, 1) is None


def test_snapshot_standings_points_as_awarded(snapshot_source):
    st = snapshot_source.standings(SEASON)
    assert st[0]["code"] == "ALPALOU"
    assert st[0]["points"] == 404.0  # verified curated total


# --------------------------------------------------------------------------- #
# Composite + synthetic
# --------------------------------------------------------------------------- #
def test_composite_provenance_real_then_synthetic():
    comp = CompositeIndycarSource.default()
    assert comp.results(SEASON, 1)
    assert comp.provenance(SEASON, 1) == "snapshot"
    assert CompositeIndycarSource.is_real("snapshot")
    assert CompositeIndycarSource.is_real("wikipedia")
    assert not CompositeIndycarSource.is_real("synthetic")


def test_live_stack_keeps_snapshot_first():
    """Snapshot-primary inversion: even the LIVE stack serves committed data
    ahead of the scraper — live parses can never displace verified data."""
    live = CompositeIndycarSource.live()
    assert [s.name for s in live._sources][0] == "snapshot"
    assert live.results(SEASON, 1)
    assert live.provenance(SEASON, 1) == "snapshot"


def test_synthetic_never_answers_for_past_seasons():
    syn = SyntheticIndycarSource()
    assert syn.results(2024, 1) == []
    res = syn.results(SEASON, 1)
    assert res  # active season, completed round
    # IndyCar classifies every car: synthetic retirees carry positions + status.
    dnfs = [r for r in res if r.status != "Running"]
    assert all(r.position is not None for r in res)
    assert dnfs, "synthetic generator must produce attrition signal"


# --------------------------------------------------------------------------- #
# Scraper on fixture wikitext (offline)
# --------------------------------------------------------------------------- #
def _scraper(pages, today="2026-07-20"):
    return IndycarScraperSource(client=FakeWikiClient(pages), today=today)


def test_scraper_parses_new_round_from_fixture_pages():
    src = _scraper(build_wiki_pages(12))
    res = src.results(SEASON, 12)
    assert res and res[0].position == 1
    assert len(res) == 25
    assert res[0].points == 53.0  # base 50 + winner bonus in the fixture
    rows = src.race_rows(SEASON, 12)
    assert rows and rows[0]["code"] and "dnf" in rows[0]
    raw = src.raw_results(SEASON, 12)
    assert raw and raw[0]["driver"]


def test_scraper_answers_empty_for_future_round():
    src = _scraper(build_wiki_pages(12))
    assert src.results(SEASON, 13) == []  # clean parse, genuinely future-dated


def test_scraper_none_when_network_down():
    src = _scraper({})
    assert src.season_state(SEASON) is None
    assert src.results(SEASON, 1) is None


def test_scraper_reparses_committed_rounds_identically(snapshot_source):
    """The scraper's parse of the curated rounds must agree with the snapshot
    (winner + classified count) — the refresh immutability contract."""
    src = _scraper(build_wiki_pages(12))
    for rnd in (1, 7, 11):
        scraped = src.results(SEASON, rnd)
        committed = snapshot_source.results(SEASON, rnd)
        assert scraped[0].competitor == committed[0].competitor
        assert len(scraped) == len(committed)


def test_scraper_standings_from_season_page():
    src = _scraper(build_wiki_pages(12))
    st = src.standings(SEASON)
    assert st and st[0]["driver"] == "Álex Palou"
