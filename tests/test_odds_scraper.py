"""Tests for the multi-source scraper + bulk-CSV ingester."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import odds_scraper as sc
from odds_scraper import (
    OddscheckerScraper,
    ScrapeError,
    discover_inbox_csvs,
    run,
    write_scraped_to_inbox,
)


FULL_CSV = """driver,odds
Lando Norris,3.5
Oscar Piastri,4.0
Max Verstappen,5.5
George Russell,7.0
Charles Leclerc,9.0
Kimi Antonelli,11.0
Lewis Hamilton,13.0
Isack Hadjar,21.0
Fernando Alonso,34.0
Carlos Sainz Jr.,41.0
Alexander Albon,51.0
Lance Stroll,67.0
Oliver Bearman,81.0
Pierre Gasly,81.0
Franco Colapinto,101.0
Liam Lawson,151.0
Esteban Ocon,151.0
Gabriel Bortoleto,201.0
Arvid Lindblad,301.0
Nico Hülkenberg,401.0
Sergio Pérez,501.0
Valtteri Bottas,501.0
"""


# --------------------------------------------------------------------------- #
# Bulk-ingest layer
# --------------------------------------------------------------------------- #


class TestDiscoverInboxCsvs:
    def test_finds_legacy_default_naming(self, tmp_path):
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06.csv").write_text(FULL_CSV)
        books = discover_inbox_csvs(6, inbox)
        assert len(books) == 1
        assert books[0].bookmaker == "oddschecker_manual"
        assert len(books[0].odds) == 22

    def test_extracts_bookmaker_from_filename(self, tmp_path):
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06_pinnacle.csv").write_text(FULL_CSV)
        (inbox / "round_06_betfair_ex_eu.csv").write_text(FULL_CSV)
        books = discover_inbox_csvs(6, inbox)
        keys = {b.bookmaker for b in books}
        assert keys == {"pinnacle", "betfair_ex_eu"}

    def test_filters_by_round(self, tmp_path):
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06_pinnacle.csv").write_text(FULL_CSV)
        (inbox / "round_07_pinnacle.csv").write_text(FULL_CSV)
        books = discover_inbox_csvs(6, inbox)
        assert len(books) == 1
        assert books[0].csv_path.name == "round_06_pinnacle.csv"

    def test_missing_inbox_returns_empty(self, tmp_path):
        assert discover_inbox_csvs(6, tmp_path / "nope") == []

    def test_skips_unparseable_csv_without_crashing(self, tmp_path, capsys):
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06_good.csv").write_text(FULL_CSV)
        (inbox / "round_06_bad.csv").write_text("not,a,real,csv\n")
        books = discover_inbox_csvs(6, inbox)
        assert len(books) == 1
        assert books[0].bookmaker == "good"
        assert "round_06_bad.csv" in capsys.readouterr().err

    def test_ignores_irrelevant_files(self, tmp_path):
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "notes.txt").write_text("hi")
        (inbox / "round_99XX.csv").write_text(FULL_CSV)
        (inbox / "race06.csv").write_text(FULL_CSV)  # wrong prefix
        books = discover_inbox_csvs(6, inbox)
        assert books == []


# --------------------------------------------------------------------------- #
# Multi-bookmaker snapshot
# --------------------------------------------------------------------------- #


class TestSnapshotShape:
    def test_multi_book_round_trips_via_load_cached_payload(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "CACHE_DIR", tmp_path / "odds_cache")
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06_pinnacle.csv").write_text(FULL_CSV)
        # Same CSV but slightly different prices to simulate two books.
        bf_csv = FULL_CSV.replace("3.5", "3.4")
        (inbox / "round_06_betfair_ex_eu.csv").write_text(bf_csv)

        result = run(6, 2026, ingest_only=True, inbox_dir=inbox)
        snap_path = Path(result["snapshot"])
        assert snap_path.exists()

        from odds_ingest import load_cached_payload

        books = load_cached_payload(snap_path)
        assert {"pinnacle", "betfair_ex_eu"} <= set(books)
        assert books["pinnacle"]["NOR"] == 3.5
        assert books["betfair_ex_eu"]["NOR"] == 3.4

    def test_select_bookmaker_prefers_pinnacle(self, tmp_path, monkeypatch):
        """End-to-end gauntlet: drop multiple CSVs, snapshot, downstream picker
        must select Pinnacle because it's at the top of PREFERRED_BOOKS."""
        monkeypatch.setattr(sc, "CACHE_DIR", tmp_path / "odds_cache")
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06_pinnacle.csv").write_text(FULL_CSV)
        (inbox / "round_06_oddschecker_manual.csv").write_text(FULL_CSV)

        result = run(6, 2026, ingest_only=True, inbox_dir=inbox)
        snap_path = Path(result["snapshot"])

        from export_value_data import select_bookmaker
        from odds_ingest import load_cached_payload

        books = load_cached_payload(snap_path)
        assert select_bookmaker(books) == "pinnacle"

    def test_empty_inbox_returns_no_snapshot(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "CACHE_DIR", tmp_path / "odds_cache")
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        result = run(6, 2026, ingest_only=True, inbox_dir=inbox)
        assert result["snapshot"] is None
        assert "no CSVs" in result["reason"]


# --------------------------------------------------------------------------- #
# Scraper plugin
# --------------------------------------------------------------------------- #


SAMPLE_NEXT_DATA = """
<!doctype html><html><body>
<script id="__NEXT_DATA__" type="application/json">{"props": {"pageProps": {"market": {"runners": [
    {"name": "Max Verstappen", "bestPrice": {"decimal": 3.5}},
    {"name": "Lando Norris", "bestPrice": {"decimal": 4.0}},
    {"name": "Oscar Piastri", "bestPrice": {"decimal": 5.0}},
    {"name": "Charles Leclerc", "bestPrice": {"decimal": 7.0}},
    {"name": "Lewis Hamilton", "bestPrice": {"decimal": 9.0}},
    {"name": "George Russell", "bestPrice": {"decimal": 11.0}},
    {"name": "Kimi Antonelli", "bestPrice": {"decimal": 13.0}},
    {"name": "Isack Hadjar", "bestPrice": {"decimal": 21.0}},
    {"name": "Fernando Alonso", "bestPrice": {"decimal": 34.0}},
    {"name": "Carlos Sainz Jr.", "bestPrice": {"decimal": 41.0}},
    {"name": "Alexander Albon", "bestPrice": {"decimal": 51.0}},
    {"name": "Lance Stroll", "bestPrice": {"decimal": 67.0}},
    {"name": "Oliver Bearman", "bestPrice": {"decimal": 81.0}},
    {"name": "Pierre Gasly", "bestPrice": {"decimal": 81.0}}
]}}}}</script>
</body></html>
"""


class TestOddscheckerScraper:
    def test_parse_next_data_finds_runners(self):
        odds = OddscheckerScraper._parse_next_data(SAMPLE_NEXT_DATA, "http://x")
        assert odds["VER"] == 3.5
        assert odds["NOR"] == 4.0
        # Only 14 unique drivers in the fixture (still < MIN); enough to test
        # parser correctness in isolation.
        assert len(odds) >= 12

    def test_parse_next_data_no_script_raises(self):
        with pytest.raises(ScrapeError, match="No __NEXT_DATA__"):
            OddscheckerScraper._parse_next_data("<html></html>", "http://x")

    def test_parse_next_data_malformed_json_raises(self):
        bad = '<script id="__NEXT_DATA__">{not json}</script>'
        with pytest.raises(ScrapeError, match="Malformed"):
            OddscheckerScraper._parse_next_data(bad, "http://x")

    def test_parse_next_data_no_runners_raises(self):
        # Valid JSON but no name/price leaves anywhere.
        empty = '<script id="__NEXT_DATA__">{"props": {"pageProps": {}}}</script>'
        with pytest.raises(ScrapeError, match="no runner"):
            OddscheckerScraper._parse_next_data(empty, "http://x")

    def test_fetch_uses_slug_argument(self, monkeypatch):
        # Patch the HTTP layer so we never hit the network.
        captured: dict = {}

        def fake_get(url, **_kw):
            captured["url"] = url
            return SAMPLE_NEXT_DATA

        monkeypatch.setattr(sc, "_polite_get", fake_get)
        scraper = OddscheckerScraper(slug="monaco")
        scraper.fetch(6, 2026)
        assert "monaco-grand-prix" in captured["url"]

    def test_fetch_missing_slug_raises_actionable_error(self, monkeypatch):
        # No slug and no calendar match → clear error.
        monkeypatch.setattr(sc, "_race_slug", lambda _r: None)
        with pytest.raises(ScrapeError, match="--slug"):
            OddscheckerScraper().fetch(99, 2026)


# --------------------------------------------------------------------------- #
# Polite HTTP layer
# --------------------------------------------------------------------------- #


class TestPoliteGet:
    def test_403_returns_actionable_error(self, monkeypatch):
        class FakeResp:
            status_code = 403
            text = ""

        class FakeSession:
            def get(self, *_a, **_k):
                return FakeResp()

        # Skip robots.txt check by short-circuiting.
        monkeypatch.setattr(sc.urllib.robotparser, "RobotFileParser",
                            lambda: _FakeRobotsAllowAll())
        with pytest.raises(ScrapeError, match="403"):
            sc._polite_get("https://example.com/foo", session=FakeSession())

    def test_5xx_returns_scrape_error(self, monkeypatch):
        class FakeResp:
            status_code = 502
            text = ""

        class FakeSession:
            def get(self, *_a, **_k):
                return FakeResp()

        monkeypatch.setattr(sc.urllib.robotparser, "RobotFileParser",
                            lambda: _FakeRobotsAllowAll())
        with pytest.raises(ScrapeError, match="502"):
            sc._polite_get("https://example.com/foo", session=FakeSession())

    def test_robots_disallow_raises_without_fetching(self, monkeypatch):
        called = {"got": False}

        class FakeSession:
            def get(self, *_a, **_k):
                called["got"] = True
                raise AssertionError("must not be called")

        monkeypatch.setattr(sc.urllib.robotparser, "RobotFileParser",
                            lambda: _FakeRobotsBlockAll())
        with pytest.raises(ScrapeError, match="robots.txt disallows"):
            sc._polite_get("https://example.com/foo", session=FakeSession())
        assert called["got"] is False


class _FakeRobotsAllowAll:
    def set_url(self, _url): pass
    def read(self): pass
    def can_fetch(self, *_a): return True


class _FakeRobotsBlockAll:
    def set_url(self, _url): pass
    def read(self): pass
    def can_fetch(self, *_a): return False


# --------------------------------------------------------------------------- #
# End-to-end run()
# --------------------------------------------------------------------------- #


class TestRun:
    def test_scrape_then_ingest(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "CACHE_DIR", tmp_path / "odds_cache")
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()

        # Patch the scraper to return a usable 22-driver dict.
        odds_dict = {
            "VER": 3.5, "NOR": 4.0, "PIA": 5.0, "RUS": 7.0, "LEC": 9.0,
            "HAM": 11.0, "ANT": 13.0, "HAD": 21.0, "ALO": 34.0, "SAI": 41.0,
            "ALB": 51.0, "STR": 67.0, "BEA": 81.0, "GAS": 81.0, "COL": 101.0,
            "LAW": 151.0, "OCO": 151.0, "BOR": 201.0, "LIN": 301.0,
            "HUL": 401.0, "PER": 501.0, "BOT": 501.0,
        }
        with patch.object(OddscheckerScraper, "fetch", return_value=odds_dict):
            result = run(6, 2026, scrape=["oddschecker"], inbox_dir=inbox)

        assert result["snapshot"] is not None
        assert ("oddschecker", 22) in result["scraped"]
        assert ("oddschecker", 22) in result["ingested"]
        # The scrape wrote round_06_oddschecker.csv into the inbox.
        assert (inbox / "round_06_oddschecker.csv").exists()

    def test_scrape_below_min_drivers_is_dropped(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sc, "CACHE_DIR", tmp_path / "odds_cache")
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        with patch.object(OddscheckerScraper, "fetch", return_value={"VER": 3.5}):
            result = run(6, 2026, scrape=["oddschecker"], inbox_dir=inbox)
        # Scraper output too sparse → no CSV written, no scraped entry.
        assert result["scraped"] == []
        assert result["snapshot"] is None
        assert "only 1 drivers" in capsys.readouterr().err

    def test_scrape_error_is_non_fatal(self, tmp_path, monkeypatch, capsys):
        """A scraper raising ScrapeError must not kill the run.

        Inbox files (if any) still get ingested.  This is the safety net
        between fragile HTML parsers and the user actually getting odds.
        """
        monkeypatch.setattr(sc, "CACHE_DIR", tmp_path / "odds_cache")
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06_pinnacle.csv").write_text(FULL_CSV)

        def boom(_r, _s):
            raise ScrapeError("simulated 403")

        with patch.object(OddscheckerScraper, "fetch", side_effect=boom):
            result = run(6, 2026, scrape=["oddschecker"], inbox_dir=inbox)
        assert result["snapshot"] is not None
        assert result["scraped"] == []
        # Pinnacle CSV in the inbox saved the run.
        assert ("pinnacle", 22) in result["ingested"]

    def test_ingest_only_skips_scrape(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "CACHE_DIR", tmp_path / "odds_cache")
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06_pinnacle.csv").write_text(FULL_CSV)
        # Even with an explicit scrape arg, ingest_only wins.
        with patch.object(OddscheckerScraper, "fetch") as fetch_mock:
            result = run(6, 2026, scrape=["oddschecker"], ingest_only=True, inbox_dir=inbox)
        fetch_mock.assert_not_called()
        assert ("pinnacle", 22) in result["ingested"]

    def test_write_false_skips_disk(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "CACHE_DIR", tmp_path / "odds_cache")
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06_pinnacle.csv").write_text(FULL_CSV)
        result = run(6, 2026, ingest_only=True, inbox_dir=inbox, write=False)
        assert result["snapshot"] is None
        assert ("pinnacle", 22) in result["ingested"]
        assert not (tmp_path / "odds_cache").exists()


class TestWriteScrapedToInbox:
    def test_csv_round_trips(self, tmp_path):
        odds = {"VER": 3.5, "NOR": 4.0}
        path = write_scraped_to_inbox(6, "oddschecker", odds, inbox_dir=tmp_path)
        assert path.exists()
        # Re-parse the written file and confirm same data.
        from odds_import_csv import parse_csv
        # parse_csv enforces MIN_DRIVERS_MATCHED so we need a fuller fixture.
        full_path = tmp_path / "round_06_oddschecker_full.csv"
        full_odds = {f"D{i:02d}": 3.0 + i for i in range(15)}
        # Use real codes so _normalize_driver accepts them.
        codes = ["VER", "NOR", "PIA", "LEC", "HAM", "RUS", "ANT", "HAD",
                 "ALO", "STR", "GAS", "COL", "ALB", "SAI", "BOT"]
        full_odds = {c: 3.0 + i for i, c in enumerate(codes)}
        full_path = write_scraped_to_inbox(7, "x", full_odds, inbox_dir=tmp_path)
        roundtrip = parse_csv(full_path)
        assert roundtrip == full_odds
