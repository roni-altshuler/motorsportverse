"""Tests for the unified Betfair + CSV odds ingester."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import odds_ingest_unified as uni
from odds_ingest_unified import (
    MIN_DRIVERS_MATCHED,
    VALID_STRATEGIES,
    _apply_strategy,
    _merge_average,
    _merge_best_back,
)


# 22-driver baseline used by most of the strategy tests.
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


def _fake_betfair_22() -> dict[str, float]:
    return {
        "VER": 5.0,   # cheaper than CSV (3.5 in CSV is McLaren-on-form)
        "NOR": 3.6,
        "PIA": 4.2,
        "RUS": 6.5,   # better than CSV (7.0)
        "LEC": 9.5,
        "ANT": 11.5,
        "HAM": 14.0,
        "HAD": 22.0,
        "ALO": 36.0,
        "SAI": 40.0,
        "ALB": 50.0,
        "STR": 70.0,
        "BEA": 85.0,
        "GAS": 80.0,
        "COL": 110.0,
        "LAW": 140.0,
        "OCO": 145.0,
        "BOR": 210.0,
        "LIN": 290.0,
        "HUL": 410.0,
        "PER": 480.0,
        "BOT": 520.0,
    }


# --------------------------------------------------------------------------- #
# Pure merge logic
# --------------------------------------------------------------------------- #


class TestMergeBestBack:
    def test_picks_higher_price_per_driver(self):
        a = {"VER": 3.5, "NOR": 4.0}
        b = {"VER": 4.0, "NOR": 3.5}
        merged = _merge_best_back(a, b)
        assert merged == {"VER": 4.0, "NOR": 4.0}

    def test_keeps_singletons(self):
        a = {"VER": 3.5}
        b = {"NOR": 4.0}
        merged = _merge_best_back(a, b)
        assert merged == {"VER": 3.5, "NOR": 4.0}

    def test_empty_inputs(self):
        assert _merge_best_back(None, None) == {}
        assert _merge_best_back({}, None) == {}
        assert _merge_best_back({"VER": 3.0}, None) == {"VER": 3.0}

    def test_drops_invalid_prices(self):
        a = {"VER": 0.9, "NOR": 4.0}  # 0.9 is below 1.0 — invalid
        merged = _merge_best_back(a, None)
        assert merged == {"NOR": 4.0}


class TestMergeAverage:
    def test_average_implied_probs(self):
        # VER: 1/4 + 1/2 = 0.75 → avg 0.375 → 1/0.375 ≈ 2.6667
        a = {"VER": 4.0}
        b = {"VER": 2.0}
        merged = _merge_average(a, b)
        assert merged["VER"] == pytest.approx(8.0 / 3.0)

    def test_singleton_passes_through(self):
        a = {"VER": 3.5}
        b = {"NOR": 4.0}
        merged = _merge_average(a, b)
        assert merged["VER"] == 3.5
        assert merged["NOR"] == 4.0


# --------------------------------------------------------------------------- #
# Strategy selection
# --------------------------------------------------------------------------- #


class TestApplyStrategy:
    @pytest.fixture
    def bf(self):
        return _fake_betfair_22()

    @pytest.fixture
    def csv(self):
        from odds_import_csv import parse_csv  # parse from string via tmp file

        return {
            "NOR": 3.5, "PIA": 4.0, "VER": 5.5, "RUS": 7.0, "LEC": 9.0,
            "ANT": 11.0, "HAM": 13.0, "HAD": 21.0, "ALO": 34.0, "SAI": 41.0,
            "ALB": 51.0, "STR": 67.0, "BEA": 81.0, "GAS": 81.0, "COL": 101.0,
            "LAW": 151.0, "OCO": 151.0, "BOR": 201.0, "LIN": 301.0,
            "HUL": 401.0, "PER": 501.0, "BOT": 501.0,
        }

    def test_auto_with_both_uses_best_back(self, bf, csv):
        odds, label = _apply_strategy("auto", bf, csv)
        assert label == "combined_best_back"
        # VER best-back is max(5.0, 5.5) = 5.5
        assert odds["VER"] == 5.5

    def test_auto_with_only_betfair(self, bf):
        odds, label = _apply_strategy("auto", bf, None)
        assert label == "betfair_ex_eu"
        assert odds == bf

    def test_auto_with_only_csv(self, csv):
        odds, label = _apply_strategy("auto", None, csv)
        assert label == "oddschecker_manual"
        assert odds == csv

    def test_auto_with_neither_returns_empty(self):
        odds, label = _apply_strategy("auto", None, None)
        assert odds == {}
        assert label == "none"

    def test_prefer_betfair_uses_betfair_when_present(self, bf, csv):
        odds, label = _apply_strategy("prefer-betfair", bf, csv)
        assert label == "betfair_ex_eu"
        assert odds == bf

    def test_prefer_betfair_falls_back_to_csv(self, csv):
        odds, label = _apply_strategy("prefer-betfair", None, csv)
        assert label == "oddschecker_manual"
        assert odds == csv

    def test_prefer_csv_uses_csv_when_present(self, bf, csv):
        odds, label = _apply_strategy("prefer-csv", bf, csv)
        assert label == "oddschecker_manual"
        assert odds == csv

    def test_best_back_always_merges(self, bf, csv):
        odds, label = _apply_strategy("best-back", bf, csv)
        assert label == "combined_best_back"
        # The merge picks max — VER is 5.5 in CSV vs 5.0 in BF.
        assert odds["VER"] == 5.5
        # RUS: 6.5 in BF, 7.0 in CSV → 7.0.
        assert odds["RUS"] == 7.0

    def test_average_strategy(self, bf, csv):
        odds, label = _apply_strategy("average", bf, csv)
        assert label == "combined_average"
        # VER: avg of 1/5.0 and 1/5.5 → 0.19091 → 1/0.19091 ≈ 5.238
        assert odds["VER"] == pytest.approx(5.238, rel=1e-3)

    def test_unknown_strategy_raises(self, bf, csv):
        with pytest.raises(ValueError, match="Unknown merge strategy"):
            _apply_strategy("kelly-weighted", bf, csv)

    def test_below_threshold_source_skipped_in_auto(self, bf):
        # CSV with only 3 drivers shouldn't trigger merge; betfair wins solo.
        sparse_csv = {"VER": 3.0, "NOR": 4.0, "PIA": 5.0}
        odds, label = _apply_strategy("auto", bf, sparse_csv)
        assert label == "betfair_ex_eu"
        assert odds == bf


# --------------------------------------------------------------------------- #
# Source discovery
# --------------------------------------------------------------------------- #


class TestSourceDiscovery:
    def test_betfair_creds_missing_returns_none(self, monkeypatch):
        for var in ("BETFAIR_USERNAME", "BETFAIR_PASSWORD", "BETFAIR_APP_KEY"):
            monkeypatch.delenv(var, raising=False)
        assert uni._try_betfair(6, 2026) is None

    def test_csv_auto_discovery_finds_inbox_file(self, tmp_path, monkeypatch):
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        csv = inbox / "round_06.csv"
        csv.write_text(FULL_CSV)
        monkeypatch.setattr(uni, "INBOX_DIR", inbox)

        odds = uni._try_csv(None, 6)
        assert odds is not None
        assert len(odds) == 22
        assert odds["VER"] == 5.5

    def test_csv_no_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(uni, "INBOX_DIR", tmp_path / "empty_inbox")
        assert uni._try_csv(None, 6) is None

    def test_csv_explicit_path_used_over_inbox(self, tmp_path, monkeypatch):
        inbox = tmp_path / "odds_inbox"
        inbox.mkdir()
        (inbox / "round_06.csv").write_text("driver,odds\nVER,99.0\n")  # bad

        explicit = tmp_path / "monaco.csv"
        explicit.write_text(FULL_CSV)
        monkeypatch.setattr(uni, "INBOX_DIR", inbox)

        odds = uni._try_csv(explicit, 6)
        assert len(odds) == 22
        assert odds["VER"] == 5.5  # not the 99.0 from the inbox


# --------------------------------------------------------------------------- #
# End-to-end ingest
# --------------------------------------------------------------------------- #


class TestIngest:
    def test_csv_only_writes_unified_snapshot(self, tmp_path, monkeypatch):
        monkeypatch.setattr(uni, "CACHE_DIR", tmp_path / "odds_cache")
        # Disable Betfair by clearing env.
        for var in ("BETFAIR_USERNAME", "BETFAIR_PASSWORD", "BETFAIR_APP_KEY"):
            monkeypatch.delenv(var, raising=False)
        csv_file = tmp_path / "monaco.csv"
        csv_file.write_text(FULL_CSV)

        out, odds, label = uni.ingest(6, 2026, csv_path=csv_file)
        assert out is not None
        assert label == "oddschecker_manual"
        assert len(odds) == 22

        blob = json.loads(out.read_text())
        assert blob["source"] == "unified"
        assert blob["strategy"] == "auto"
        assert blob["sourcesUsed"] == ["csv"]
        # Downstream value exporter consumes this via load_cached_payload.
        from odds_ingest import load_cached_payload

        books = load_cached_payload(out)
        assert "oddschecker_manual" in books

    def test_both_sources_best_back_merges(self, tmp_path, monkeypatch):
        monkeypatch.setattr(uni, "CACHE_DIR", tmp_path / "odds_cache")
        # Force Betfair to "look configured" so the function attempts it.
        monkeypatch.setenv("BETFAIR_USERNAME", "x")
        monkeypatch.setenv("BETFAIR_PASSWORD", "x")
        monkeypatch.setenv("BETFAIR_APP_KEY", "x")
        # ...but mock the network layer to return a fake price book.
        monkeypatch.setattr(
            "odds_ingest_betfair.fetch_betfair_prices",
            lambda _r, _s: ({}, _fake_betfair_22()),
        )
        csv_file = tmp_path / "monaco.csv"
        csv_file.write_text(FULL_CSV)

        out, odds, label = uni.ingest(
            6, 2026, strategy="best-back", csv_path=csv_file
        )
        assert out is not None
        assert label == "combined_best_back"
        # VER: max(BF 5.0, CSV 5.5) = 5.5
        assert odds["VER"] == 5.5
        blob = json.loads(out.read_text())
        assert sorted(blob["sourcesUsed"]) == ["betfair", "csv"]

    def test_betfair_failure_falls_back_to_csv(self, tmp_path, monkeypatch):
        monkeypatch.setattr(uni, "CACHE_DIR", tmp_path / "odds_cache")
        monkeypatch.setenv("BETFAIR_USERNAME", "x")
        monkeypatch.setenv("BETFAIR_PASSWORD", "x")
        monkeypatch.setenv("BETFAIR_APP_KEY", "x")
        # Simulate Betfair raising SystemExit (no market / too few drivers).
        def _boom(_r, _s):
            raise SystemExit("no market")
        monkeypatch.setattr("odds_ingest_betfair.fetch_betfair_prices", _boom)
        csv_file = tmp_path / "monaco.csv"
        csv_file.write_text(FULL_CSV)

        out, odds, label = uni.ingest(6, 2026, csv_path=csv_file)
        assert out is not None
        assert label == "oddschecker_manual"
        assert len(odds) == 22

    def test_both_fail_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(uni, "CACHE_DIR", tmp_path / "odds_cache")
        monkeypatch.setattr(uni, "INBOX_DIR", tmp_path / "odds_inbox")
        for var in ("BETFAIR_USERNAME", "BETFAIR_PASSWORD", "BETFAIR_APP_KEY"):
            monkeypatch.delenv(var, raising=False)
        out, odds, label = uni.ingest(6, 2026)
        assert out is None
        assert odds == {}
        assert label == "none"

    def test_no_write_flag(self, tmp_path, monkeypatch):
        monkeypatch.setattr(uni, "CACHE_DIR", tmp_path / "odds_cache")
        csv_file = tmp_path / "monaco.csv"
        csv_file.write_text(FULL_CSV)

        out, odds, label = uni.ingest(6, 2026, csv_path=csv_file, write=False)
        assert out is None
        assert len(odds) == 22  # data still parsed
        # Cache dir shouldn't even exist since write=False short-circuits.
        assert not (tmp_path / "odds_cache").exists()


class TestStrategyValidation:
    def test_invalid_strategy_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid strategy"):
            uni.ingest(6, 2026, strategy="kelly-weighted")

    def test_valid_strategies_constant_matches_choices(self):
        # Sanity: the CLI choices list and the dispatcher's accepted set agree.
        for s in VALID_STRATEGIES:
            # Should not raise on input validation alone.
            uni.ingest(6, 2026, strategy=s, write=False)
