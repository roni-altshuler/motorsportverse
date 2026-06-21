"""Tests for the manual-CSV odds import path."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from odds_import_csv import (
    MIN_DRIVERS_MATCHED,
    _normalize_driver,
    _parse_odds,
    import_csv,
    parse_csv,
)


# 22 fake odds across the 2026 grid — enough to clear MIN_DRIVERS_MATCHED.
FULL_GRID_CSV = """driver,odds
Max Verstappen,3.5
Lando Norris,4.0
Oscar Piastri,5.0
Charles Leclerc,7.0
Lewis Hamilton,9.0
George Russell,11.0
Kimi Antonelli,13.0
Isack Hadjar,21.0
Fernando Alonso,26.0
Lance Stroll,51.0
Pierre Gasly,67.0
Franco Colapinto,151.0
Alexander Albon,101.0
Carlos Sainz Jr.,67.0
Liam Lawson,251.0
Arvid Lindblad,501.0
Esteban Ocon,151.0
Oliver Bearman,201.0
Gabriel Bortoleto,251.0
Nico Hülkenberg,301.0
Sergio Pérez,401.0
Valtteri Bottas,501.0
"""


class TestParseOdds:
    def test_decimal(self):
        assert _parse_odds("3.5") == 3.5
        assert _parse_odds("11.0") == 11.0

    def test_fractional(self):
        assert _parse_odds("5/2") == 3.5  # 1 + 5/2
        assert _parse_odds("11/10") == pytest.approx(2.1)

    def test_strips_currency(self):
        assert _parse_odds("$3.50") == 3.5

    def test_rejects_below_one(self):
        # Decimal odds <= 1.0 are not valid prices.
        assert _parse_odds("0.5") is None
        assert _parse_odds("1.0") is None

    def test_rejects_garbage(self):
        assert _parse_odds("") is None
        assert _parse_odds("foo") is None
        assert _parse_odds("3/0") is None


class TestNormalizeDriver:
    def test_three_letter_code(self):
        assert _normalize_driver("VER") == "VER"
        assert _normalize_driver("ver") == "VER"

    def test_full_name(self):
        assert _normalize_driver("Max Verstappen") == "VER"

    def test_last_name_only(self):
        assert _normalize_driver("Verstappen") == "VER"

    def test_book_format_variants(self):
        assert _normalize_driver("M. Verstappen") == "VER"
        # Hamilton/Hadjar both contain "ha" but the substring search uses last
        # name only, so this isn't ambiguous.
        assert _normalize_driver("Hamilton") == "HAM"

    def test_unrecognised(self):
        assert _normalize_driver("Jenson Button") is None
        assert _normalize_driver("") is None


class TestParseCsv:
    def test_full_grid_round_trips(self, tmp_path):
        csv_file = tmp_path / "odds.csv"
        csv_file.write_text(FULL_GRID_CSV)
        odds = parse_csv(csv_file)
        assert len(odds) == 22
        assert odds["VER"] == 3.5
        assert odds["BOT"] == 501.0

    def test_header_auto_detection(self, tmp_path):
        # Same content but no header row — the first row's last cell parses as
        # a price, so we should auto-detect "no header" and still parse it.
        no_header = "\n".join(line for line in FULL_GRID_CSV.splitlines()[1:])
        csv_file = tmp_path / "noheader.csv"
        csv_file.write_text(no_header)
        odds = parse_csv(csv_file)
        assert len(odds) == 22

    def test_too_few_drivers_rejects(self, tmp_path):
        csv_file = tmp_path / "sparse.csv"
        csv_file.write_text("driver,odds\nMax Verstappen,3.5\nLando Norris,4.0\n")
        with pytest.raises(ValueError, match=f"need >= {MIN_DRIVERS_MATCHED}"):
            parse_csv(csv_file)

    def test_unmatched_names_warned_not_fatal(self, tmp_path, capsys):
        # 22 real + 1 unmatched row should still parse (22 >= MIN).
        csv_file = tmp_path / "mixed.csv"
        csv_file.write_text(FULL_GRID_CSV + "Jenson Button,8.0\n")
        odds = parse_csv(csv_file)
        assert len(odds) == 22
        assert "Jenson Button" in capsys.readouterr().err

    def test_first_occurrence_wins(self, tmp_path):
        # If a driver appears twice with different prices (a copy/paste
        # mistake), we keep the first.
        csv_file = tmp_path / "dup.csv"
        csv_file.write_text(FULL_GRID_CSV + "Max Verstappen,99.0\n")
        odds = parse_csv(csv_file)
        assert odds["VER"] == 3.5  # first wins, 99.0 ignored


class TestImportCsv:
    def test_writes_compatible_snapshot(self, tmp_path, monkeypatch):
        # Redirect CACHE_DIR so we don't pollute the real one.
        import odds_import_csv

        monkeypatch.setattr(odds_import_csv, "CACHE_DIR", tmp_path / "odds_cache")
        csv_file = tmp_path / "odds.csv"
        csv_file.write_text(FULL_GRID_CSV)

        out = odds_import_csv.import_csv(5, 2026, "oddschecker_manual", csv_file)
        assert out.exists()
        assert out.name.endswith("_csv.json")

        # The snapshot must be in the schema the downstream value exporter
        # consumes — `load_cached_payload` then `parse_winner_odds`.
        from odds_ingest import load_cached_payload

        books = load_cached_payload(out)
        assert "oddschecker_manual" in books
        odds = books["oddschecker_manual"]
        assert odds["VER"] == 3.5
        assert len(odds) == 22

    def test_round_trip_via_parse_winner_odds(self, tmp_path, monkeypatch):
        """End-to-end: CSV → snapshot → parsed via the API path's parser."""
        import odds_import_csv

        monkeypatch.setattr(odds_import_csv, "CACHE_DIR", tmp_path / "odds_cache")
        csv_file = tmp_path / "odds.csv"
        csv_file.write_text(FULL_GRID_CSV)
        out = odds_import_csv.import_csv(5, 2026, "pinnacle", csv_file)

        blob = json.loads(out.read_text())
        assert blob["round"] == 5
        assert blob["season"] == 2026
        assert blob["source"] == "csv-import"
        # The wrapped payload must include exactly one event with one bookmaker.
        events = blob["payload"]
        assert len(events) == 1
        books = events[0]["bookmakers"]
        assert len(books) == 1
        assert books[0]["key"] == "pinnacle"

    def test_missing_csv_raises(self):
        with pytest.raises(FileNotFoundError):
            import_csv(5, 2026, "oddschecker_manual", Path("/nonexistent.csv"))
