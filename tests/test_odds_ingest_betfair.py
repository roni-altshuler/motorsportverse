"""Tests for the Betfair Exchange odds ingest path.

We never hit the real Betfair API in tests — all network calls go through
the `_build_client` factory which we patch.  These tests pin down the
*structure* of the pipeline (auth check → market select → book fetch →
snapshot write) without depending on live odds.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import odds_ingest_betfair as bf
from odds_ingest_betfair import (
    BetfairAuthError,
    _build_snapshot,
    _normalize_runner_name,
    _require,
    select_market_for_round,
)


class TestRequireEnv:
    def test_missing_var_raises_actionable(self, monkeypatch):
        monkeypatch.delenv("BETFAIR_USERNAME", raising=False)
        with pytest.raises(BetfairAuthError, match="BETFAIR_USERNAME"):
            _require("BETFAIR_USERNAME")

    def test_present_var_returns(self, monkeypatch):
        monkeypatch.setenv("BETFAIR_USERNAME", "alice")
        assert _require("BETFAIR_USERNAME") == "alice"


class TestNormalizeRunnerName:
    def test_full_name(self):
        assert _normalize_runner_name("Max Verstappen") == "VER"

    def test_last_name(self):
        assert _normalize_runner_name("Verstappen") == "VER"

    def test_case_insensitive(self):
        assert _normalize_runner_name("LANDO NORRIS") == "NOR"

    def test_unmatched(self):
        assert _normalize_runner_name("Jenson Button") is None
        assert _normalize_runner_name("") is None


class TestSelectMarketForRound:
    def _market(self, start: datetime, name: str = "Race Winner") -> dict:
        return {
            "marketId": f"m-{start.isoformat()}",
            "marketName": name,
            "marketStartTime": start,
            "competition": "F1",
            "runners": [],
        }

    def test_empty_returns_none(self):
        assert select_market_for_round([], None) is None

    def test_picks_closest_to_round_date(self):
        round_date = datetime(2026, 5, 24, tzinfo=timezone.utc)
        far = self._market(round_date + timedelta(days=30))
        near = self._market(round_date + timedelta(days=1))
        far2 = self._market(round_date - timedelta(days=20))
        assert select_market_for_round([far, near, far2], round_date) == near

    def test_no_round_date_falls_back_to_soonest(self):
        now = datetime.now(timezone.utc)
        late = self._market(now + timedelta(days=10))
        soon = self._market(now + timedelta(days=2))
        assert select_market_for_round([late, soon], None) == soon


class TestBuildSnapshot:
    def test_basic_snapshot_shape(self):
        market = {
            "marketId": "1.234",
            "marketName": "Race Winner",
            "marketStartTime": datetime(2026, 5, 24, tzinfo=timezone.utc),
            "competition": "F1",
            "runners": [
                {"selectionId": 1001, "runnerName": "Max Verstappen"},
                {"selectionId": 1002, "runnerName": "Lando Norris"},
                {"selectionId": 1003, "runnerName": "Unknown Driver"},
            ],
        }
        prices = {1001: 3.5, 1002: 4.0, 1003: 8.0}
        snap, code_map = _build_snapshot(5, 2026, market, prices)
        assert snap["round"] == 5
        assert snap["season"] == 2026
        assert snap["source"] == "betfair-exchange"
        # Only normalised drivers end up in the code map.
        assert code_map == {"VER": 3.5, "NOR": 4.0}
        # And the cache schema matches what load_cached_payload expects.
        books = snap["payload"][0]["bookmakers"]
        assert len(books) == 1
        assert books[0]["key"] == "betfair_ex_eu"
        outcomes = books[0]["markets"][0]["outcomes"]
        # Unknown Driver row is dropped (no driver code), so 2 outcomes only.
        assert len(outcomes) == 2

    def test_skips_runners_with_no_price(self):
        market = {
            "marketId": "1.234",
            "marketName": "Race Winner",
            "marketStartTime": datetime(2026, 5, 24, tzinfo=timezone.utc),
            "competition": "F1",
            "runners": [
                {"selectionId": 1001, "runnerName": "Max Verstappen"},
                {"selectionId": 1002, "runnerName": "Lando Norris"},
            ],
        }
        prices = {1001: 3.5}  # NOR not priced
        snap, code_map = _build_snapshot(5, 2026, market, prices)
        assert code_map == {"VER": 3.5}

    def test_snapshot_round_trips_via_load_cached_payload(self, tmp_path, monkeypatch):
        """End-to-end: write the snapshot, then re-read it via the same parser
        the value exporter uses."""
        monkeypatch.setattr(bf, "CACHE_DIR", tmp_path / "odds_cache")
        market = {
            "marketId": "1.234",
            "marketName": "Race Winner",
            "marketStartTime": datetime(2026, 5, 24, tzinfo=timezone.utc),
            "competition": "F1",
            "runners": [
                {"selectionId": i, "runnerName": full}
                for i, full in enumerate(
                    [
                        "Max Verstappen", "Lando Norris", "Oscar Piastri",
                        "Charles Leclerc", "Lewis Hamilton", "George Russell",
                        "Kimi Antonelli", "Isack Hadjar", "Fernando Alonso",
                        "Lance Stroll", "Pierre Gasly", "Franco Colapinto",
                    ],
                    start=1,
                )
            ],
        }
        prices = {i: 3.0 + i for i in range(1, 13)}
        snap, code_map = _build_snapshot(5, 2026, market, prices)
        assert len(code_map) == 12

        out = tmp_path / "snap.json"
        out.write_text(json.dumps(snap, default=str))

        from odds_ingest import load_cached_payload

        books = load_cached_payload(out)
        assert "betfair_ex_eu" in books
        assert len(books["betfair_ex_eu"]) == 12


class TestFetchBetfairWinnerOdds:
    """End-to-end with the network layer mocked."""

    def test_aborts_when_no_markets(self, monkeypatch):
        monkeypatch.setattr(bf, "_build_client", lambda: MagicMock())
        monkeypatch.setattr(bf, "list_winner_markets", lambda _client: [])
        with pytest.raises(SystemExit, match="no F1 race-winner market"):
            bf.fetch_betfair_winner_odds(5, 2026)

    def test_aborts_when_too_few_drivers_priced(self, monkeypatch, tmp_path):
        monkeypatch.setattr(bf, "CACHE_DIR", tmp_path / "odds_cache")
        monkeypatch.setattr(bf, "_build_client", lambda: MagicMock())
        # Two markets so select_market_for_round actually runs.
        market = {
            "marketId": "1.234",
            "marketName": "Race Winner",
            "marketStartTime": datetime(2026, 5, 24, tzinfo=timezone.utc),
            "competition": "F1",
            "runners": [
                {"selectionId": 1, "runnerName": "Max Verstappen"},
            ],
        }
        monkeypatch.setattr(bf, "list_winner_markets", lambda _client: [market])
        monkeypatch.setattr(bf, "fetch_market_book", lambda _c, _id: {1: 3.5})
        # Force round-date lookup to a known value so test is deterministic.
        monkeypatch.setattr(
            bf, "_load_round_date",
            lambda _r: datetime(2026, 5, 24, tzinfo=timezone.utc),
        )
        with pytest.raises(SystemExit, match=r"only \d+ drivers priced"):
            bf.fetch_betfair_winner_odds(5, 2026)

    def test_happy_path_writes_snapshot(self, monkeypatch, tmp_path):
        monkeypatch.setattr(bf, "CACHE_DIR", tmp_path / "odds_cache")
        monkeypatch.setattr(bf, "_build_client", lambda: MagicMock())
        # Build a full-ish 12-driver market so MIN_DRIVERS_MATCHED is cleared.
        names = [
            "Max Verstappen", "Lando Norris", "Oscar Piastri",
            "Charles Leclerc", "Lewis Hamilton", "George Russell",
            "Kimi Antonelli", "Isack Hadjar", "Fernando Alonso",
            "Lance Stroll", "Pierre Gasly", "Franco Colapinto",
        ]
        market = {
            "marketId": "1.234",
            "marketName": "Race Winner",
            "marketStartTime": datetime(2026, 5, 24, tzinfo=timezone.utc),
            "competition": "F1",
            "runners": [
                {"selectionId": i + 1, "runnerName": name}
                for i, name in enumerate(names)
            ],
        }
        prices = {i + 1: 3.0 + i for i in range(len(names))}
        monkeypatch.setattr(bf, "list_winner_markets", lambda _client: [market])
        monkeypatch.setattr(bf, "fetch_market_book", lambda _c, _id: prices)
        monkeypatch.setattr(
            bf, "_load_round_date",
            lambda _r: datetime(2026, 5, 24, tzinfo=timezone.utc),
        )

        out = bf.fetch_betfair_winner_odds(5, 2026)
        assert out.exists()
        assert out.name.endswith("_betfair.json")

        blob = json.loads(out.read_text())
        assert blob["round"] == 5
        assert blob["season"] == 2026
        assert blob["source"] == "betfair-exchange"
        assert blob["marketId"] == "1.234"
        # Round-trip via load_cached_payload to confirm downstream compat.
        from odds_ingest import load_cached_payload

        books = load_cached_payload(out)
        assert "betfair_ex_eu" in books
        assert len(books["betfair_ex_eu"]) == 12
