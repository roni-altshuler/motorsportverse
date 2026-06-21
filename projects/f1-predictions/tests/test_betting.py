"""Tests for the betting / value-finder layer.

Coverage:
    bet_sizing.py        — kelly_fraction, expected_value, cap_portfolio.
    odds_ingest.py       — devig_proportional, parse_winner_odds,
                           normalize_driver, fetch_winner_odds (HTTP mocked).
    export_value_data.py — end-to-end smoke with a fixture probability JSON
                           and a fixture odds cache file.
    backtest.py          — 1-round fixture; equity curve + ROI sanity.

No real OddsAPI traffic: every test that touches the HTTP layer mocks
`odds_ingest._fetch_raw` with `unittest.mock.patch`.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# bet_sizing
# ---------------------------------------------------------------------------


class TestKellyFraction:
    def test_textbook_full_kelly(self):
        # p=0.6, odds=2.0 (so b=1) -> full Kelly = (0.6*2 - 1)/1 = 0.20.
        from bet_sizing import kelly_fraction
        assert kelly_fraction(0.6, 2.0, fraction=1.0) == pytest.approx(0.20)

    def test_quarter_kelly_applies_fraction(self):
        from bet_sizing import kelly_fraction
        assert kelly_fraction(0.6, 2.0, fraction=0.25) == pytest.approx(0.05)

    def test_negative_edge_returns_zero(self):
        from bet_sizing import kelly_fraction
        # p=0.3, odds=2.0 -> b=1, full = (0.3*2 - 1)/1 = -0.4 -> clamp to 0.
        assert kelly_fraction(0.3, 2.0, fraction=1.0) == 0.0

    def test_zero_edge_returns_zero(self):
        from bet_sizing import kelly_fraction
        # p=0.5, odds=2.0 -> exactly even money.  full = 0.  Return 0.
        assert kelly_fraction(0.5, 2.0, fraction=1.0) == 0.0

    def test_odds_at_or_below_one_returns_zero(self):
        from bet_sizing import kelly_fraction
        assert kelly_fraction(0.9, 1.0) == 0.0
        assert kelly_fraction(0.9, 0.5) == 0.0

    def test_probability_out_of_range_returns_zero(self):
        from bet_sizing import kelly_fraction
        assert kelly_fraction(-0.1, 2.0) == 0.0
        assert kelly_fraction(1.5, 2.0) == 0.0


class TestExpectedValue:
    def test_positive_ev(self):
        from bet_sizing import expected_value
        # p=0.6, odds=2.0 -> EV = 0.6*1 - 0.4 = 0.2
        assert expected_value(0.6, 2.0) == pytest.approx(0.2)

    def test_negative_ev(self):
        from bet_sizing import expected_value
        assert expected_value(0.3, 2.0) == pytest.approx(-0.4)

    def test_zero_for_bad_odds(self):
        from bet_sizing import expected_value
        assert expected_value(0.5, 1.0) == 0.0


class TestCapPortfolio:
    def test_per_bet_cap_clips_large_bets(self):
        from bet_sizing import cap_portfolio
        ops = [{"id": 1, "kellyFraction": 0.10}, {"id": 2, "kellyFraction": 0.03}]
        out = cap_portfolio(ops, per_bet_cap=0.05, total_cap=1.0)
        assert out[0]["kellyFraction"] == 0.05
        assert out[1]["kellyFraction"] == 0.03

    def test_total_cap_scales_proportionally(self):
        from bet_sizing import cap_portfolio
        # 4 ops at 0.10 each = 0.40 total.  total_cap=0.30 -> scale 0.75.
        # Per-bet cap=0.10 means clip is a no-op; only the total rescale fires.
        ops = [{"kellyFraction": 0.10} for _ in range(4)]
        out = cap_portfolio(ops, per_bet_cap=0.10, total_cap=0.30)
        for op in out:
            assert op["kellyFraction"] == pytest.approx(0.075)
        assert sum(op["kellyFraction"] for op in out) == pytest.approx(0.30)

    def test_total_cap_does_not_grow_below_target(self):
        from bet_sizing import cap_portfolio
        ops = [{"kellyFraction": 0.05}, {"kellyFraction": 0.05}]
        out = cap_portfolio(ops, per_bet_cap=0.10, total_cap=0.30)
        # Total = 0.10 < 0.30; rescale should not happen.
        assert sum(op["kellyFraction"] for op in out) == pytest.approx(0.10)

    def test_negative_fractions_clipped_to_zero(self):
        from bet_sizing import cap_portfolio
        ops = [{"kellyFraction": -0.01}, {"kellyFraction": 0.04}]
        out = cap_portfolio(ops, per_bet_cap=0.05, total_cap=1.0)
        assert out[0]["kellyFraction"] == 0.0
        assert out[1]["kellyFraction"] == 0.04

    def test_preserves_other_fields(self):
        from bet_sizing import cap_portfolio
        ops = [{"driver": "VER", "edgePct": 5.0, "kellyFraction": 0.20}]
        out = cap_portfolio(ops, per_bet_cap=0.05, total_cap=0.10)
        assert out[0]["driver"] == "VER"
        assert out[0]["edgePct"] == 5.0
        assert out[0]["kellyFraction"] == 0.05

    def test_empty_returns_empty(self):
        from bet_sizing import cap_portfolio
        assert cap_portfolio([]) == []


# ---------------------------------------------------------------------------
# odds_ingest
# ---------------------------------------------------------------------------


class TestDevigProportional:
    def test_two_equal_outcomes(self):
        from odds_ingest import devig_proportional
        out = devig_proportional({"VER": 2.0, "NOR": 2.0})
        assert out["VER"] == pytest.approx(0.5)
        assert out["NOR"] == pytest.approx(0.5)

    def test_sums_to_one(self):
        from odds_ingest import devig_proportional
        out = devig_proportional({"A": 3.0, "B": 4.0, "C": 5.0, "D": 6.0})
        assert sum(out.values()) == pytest.approx(1.0)

    def test_drops_bad_odds(self):
        from odds_ingest import devig_proportional
        out = devig_proportional({"A": 2.0, "B": 0.0, "C": 1.0, "D": -3.0})
        assert "A" in out and len(out) == 1

    def test_empty_returns_empty(self):
        from odds_ingest import devig_proportional
        assert devig_proportional({}) == {}


class TestNormalizeDriver:
    def test_full_name_exact(self):
        from odds_ingest import normalize_driver
        assert normalize_driver("Max Verstappen") == "VER"

    def test_case_insensitive(self):
        from odds_ingest import normalize_driver
        assert normalize_driver("max verstappen") == "VER"

    def test_last_name_only(self):
        from odds_ingest import normalize_driver
        assert normalize_driver("Verstappen") == "VER"
        assert normalize_driver("Norris") == "NOR"

    def test_reversed_order(self):
        from odds_ingest import normalize_driver
        assert normalize_driver("Verstappen, Max") == "VER"

    def test_unknown_returns_none(self):
        from odds_ingest import normalize_driver
        assert normalize_driver("Some Rando") is None
        assert normalize_driver("") is None


class TestParseWinnerOdds:
    def _payload(self) -> list[dict]:
        return [
            {
                "id": "evt1",
                "commence_time": "2026-05-09T18:00:00Z",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "markets": [
                            {
                                "key": "outrights",
                                "outcomes": [
                                    {"name": "Max Verstappen", "price": 3.5},
                                    {"name": "Lando Norris", "price": 4.0},
                                    {"name": "Some Rookie", "price": 100.0},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]

    def test_parses_known_drivers(self):
        from odds_ingest import parse_winner_odds
        out = parse_winner_odds(self._payload())
        assert out["pinnacle"]["VER"] == 3.5
        assert out["pinnacle"]["NOR"] == 4.0

    def test_drops_unknown_driver(self):
        from odds_ingest import parse_winner_odds
        out = parse_winner_odds(self._payload())
        assert "ROOKIE" not in out["pinnacle"]
        assert len(out["pinnacle"]) == 2

    def test_empty_payload(self):
        from odds_ingest import parse_winner_odds
        assert parse_winner_odds([]) == {}


class TestFetchWinnerOdds:
    """HTTP layer fully mocked — no real OddsAPI calls."""

    def test_calls_api_and_writes_cache(self, tmp_path, monkeypatch):
        # Redirect CACHE_DIR into tmp_path so we don't pollute the repo.
        import odds_ingest

        monkeypatch.setattr(odds_ingest, "CACHE_DIR", tmp_path / "odds_cache")

        payload = [
            {
                "id": "evt1",
                "commence_time": "2026-05-09T18:00:00Z",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "markets": [
                            {
                                "key": "outrights",
                                "outcomes": [
                                    {"name": "Max Verstappen", "price": 3.5},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        with patch("odds_ingest._fetch_raw", return_value=payload):
            out = odds_ingest.fetch_winner_odds(5, 2026, api_key="dummy")
        assert out["pinnacle"]["VER"] == 3.5
        # Cache file exists.
        files = list((tmp_path / "odds_cache").glob("round_05_*.json"))
        assert len(files) == 1

    def test_missing_api_key_exits(self, monkeypatch):
        import odds_ingest
        monkeypatch.delenv("ODDS_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            odds_ingest.fetch_winner_odds(5, 2026)


# ---------------------------------------------------------------------------
# Fixture helpers (probabilities + odds cache snapshot)
# ---------------------------------------------------------------------------


def _write_probabilities_fixture(path: Path, round_number: int) -> None:
    """Minimal probability JSON: 3 drivers, win-market only."""
    blob = {
        "round": round_number,
        "markets": {
            "win": [
                {"driver": "VER", "probability": 0.45},  # model says higher than market
                {"driver": "NOR", "probability": 0.30},
                {"driver": "PIA", "probability": 0.25},
            ],
        },
        "h2h": {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob))


def _write_odds_fixture(path: Path) -> None:
    """Cache snapshot in the same shape `odds_ingest.fetch_winner_odds` writes."""
    blob = {
        "season": 2026,
        "round": 5,
        "fetchedAt": "2026-05-09T17:00:00+00:00",
        "payload": [
            {
                "id": "evt1",
                "commence_time": "2026-05-09T18:00:00Z",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "markets": [
                            {
                                "key": "outrights",
                                "outcomes": [
                                    # Market thinks VER 0.36, NOR 0.36, PIA 0.36 -> roughly fair
                                    {"name": "Max Verstappen", "price": 3.0},
                                    {"name": "Lando Norris", "price": 3.0},
                                    {"name": "Oscar Piastri", "price": 3.0},
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob))


# ---------------------------------------------------------------------------
# export_value_data
# ---------------------------------------------------------------------------


class _ValueOutputModel:
    """Pydantic validator for the value-finder schema."""

    @staticmethod
    def get_model():
        from pydantic import BaseModel, ConfigDict

        class Op(BaseModel):
            model_config = ConfigDict(extra="ignore")
            market: str
            driver: str
            driverFullName: str
            team: str
            teamColor: str
            modelProbability: float
            marketProbability: float
            marketOdds: float
            edgePct: float
            kellyFraction: float
            kellyStake: float
            expectedValue: float

        class Summary(BaseModel):
            totalOpportunities: int
            positiveEdgeCount: int
            totalKellyExposure: float

        class Output(BaseModel):
            model_config = ConfigDict(extra="ignore")
            round: int
            season: int
            generatedAt: str
            bookmaker: str
            oddsTimestamp: str
            bankrollRef: float
            opportunities: list[Op]
            summary: Summary
            disclaimer: str

        return Output


class TestExportValueData:
    def test_smoke_with_fixtures(self, tmp_path):
        from export_value_data import export_value_data

        probs_path = tmp_path / "probabilities" / "round_05.json"
        odds_path = tmp_path / "odds_cache" / "round_05_20260509T170000Z.json"
        _write_probabilities_fixture(probs_path, 5)
        _write_odds_fixture(odds_path)

        with probs_path.open() as f:
            probs = json.load(f)

        out_path = tmp_path / "value" / "round_05.json"
        result = export_value_data(
            round_number=5,
            season=2026,
            bankroll=1000.0,
            output_path=out_path,
            odds_snapshot_path=odds_path,
            probabilities_override=probs,
        )

        # Validate schema.
        Model = _ValueOutputModel.get_model()
        validated = Model(**result)
        assert validated.round == 5
        assert validated.bookmaker == "pinnacle"
        assert len(validated.opportunities) == 3
        # VER (model 0.45, market ~0.333) should have positive edge.
        ver = next(o for o in validated.opportunities if o.driver == "VER")
        assert ver.edgePct > 0
        # NOR/PIA (model 0.30 / 0.25 < market 0.333) should have negative edge.
        nor = next(o for o in validated.opportunities if o.driver == "NOR")
        assert nor.edgePct < 0
        # Output file written.
        assert out_path.exists()
        with out_path.open() as f:
            assert json.load(f)["round"] == 5

    def test_sorted_by_edge_desc(self, tmp_path):
        from export_value_data import export_value_data

        probs_path = tmp_path / "probabilities" / "round_05.json"
        odds_path = tmp_path / "odds_cache" / "round_05_20260509T170000Z.json"
        _write_probabilities_fixture(probs_path, 5)
        _write_odds_fixture(odds_path)

        with probs_path.open() as f:
            probs = json.load(f)

        result = export_value_data(
            round_number=5, season=2026,
            output_path=tmp_path / "value" / "round_05.json",
            odds_snapshot_path=odds_path,
            probabilities_override=probs,
        )
        edges = [o["edgePct"] for o in result["opportunities"]]
        assert edges == sorted(edges, reverse=True)


# ---------------------------------------------------------------------------
# backtest
# ---------------------------------------------------------------------------


class TestBacktest:
    def test_one_round_fixture(self, tmp_path):
        from backtest import run_backtest

        # Set up directory tree.
        probs_dir = tmp_path / "probabilities"
        odds_dir = tmp_path / "odds_cache"
        season_results = tmp_path / "season_results.json"

        # Round 1: model = 0.5 VER, 0.5 NOR.  Market = 3.0/3.0 -> devig 0.5/0.5.
        # So edge = 0; Kelly = 0; no bets.  PnL = 0.
        _write_probabilities_fixture(probs_dir / "round_01.json", 1)
        _write_odds_fixture(odds_dir / "round_01_20260101T000000Z.json")
        season_results.write_text(json.dumps({"1": {"VER": 1, "NOR": 2, "PIA": 3}}))

        run = run_backtest(
            season=2026,
            bankroll=1000.0,
            probs_dir=probs_dir,
            odds_dir=odds_dir,
            season_results_path=season_results,
            persist=False,
        )
        assert len(run.rounds) == 1
        # Verify equity curve has correct length (start + 1 round).
        assert len(run.equity_curve) == 2
        # Bankroll only moves by net pnl.
        assert run.equity_curve[1] == pytest.approx(1000.0 + run.rounds[0].pnl)
        # Hit rate is well-defined.
        if run.total_bets > 0:
            assert 0.0 <= run.hit_rate <= 1.0
        # Sharpe / drawdown not reported with < 5 rounds.
        assert run.sharpe is None
        assert run.max_drawdown is None

    def test_winning_bet_increases_bankroll(self, tmp_path):
        """Construct a scenario where the model is heavily +EV on the actual winner."""
        from backtest import run_backtest

        probs_dir = tmp_path / "probabilities"
        odds_dir = tmp_path / "odds_cache"
        season_results = tmp_path / "season_results.json"

        # Strong model conviction: VER 0.8 vs market implied 0.5 (odds 2.0).
        # Kelly@0.25 = 0.25 * (0.8*2-1)/1 = 0.15 -> clip to per_bet_cap 0.05.
        # Stake 50, odds 2.0, won -> pnl = +50.
        (probs_dir).mkdir(parents=True, exist_ok=True)
        (probs_dir / "round_01.json").write_text(json.dumps({
            "round": 1,
            "markets": {"win": [
                {"driver": "VER", "probability": 0.80},
                {"driver": "NOR", "probability": 0.20},
            ]},
            "h2h": {},
        }))
        (odds_dir).mkdir(parents=True, exist_ok=True)
        (odds_dir / "round_01_20260101T000000Z.json").write_text(json.dumps({
            "season": 2026, "round": 1,
            "fetchedAt": "2026-01-01T00:00:00Z",
            "payload": [{
                "id": "evt1",
                "commence_time": "2026-01-01T00:00:00Z",
                "bookmakers": [{
                    "key": "pinnacle",
                    "markets": [{
                        "key": "outrights",
                        "outcomes": [
                            {"name": "Max Verstappen", "price": 2.0},
                            {"name": "Lando Norris", "price": 2.0},
                        ],
                    }],
                }],
            }],
        }))
        season_results.write_text(json.dumps({"1": {"VER": 1, "NOR": 2}}))

        run = run_backtest(
            season=2026, bankroll=1000.0,
            probs_dir=probs_dir, odds_dir=odds_dir,
            season_results_path=season_results,
            persist=False,
        )
        assert len(run.rounds) == 1
        rr = run.rounds[0]
        # At least one positive-Kelly bet placed.
        assert len(rr.bets) >= 1
        ver_bet = next(b for b in rr.bets if b.driver == "VER")
        assert ver_bet.won is True
        assert ver_bet.pnl > 0
        # Total PnL > 0 (VER won, NOR loss may exist but model rated NOR -EV so no NOR bet).
        assert rr.bankroll_after > 1000.0
        # ROI computed correctly.
        assert run.roi == pytest.approx(rr.pnl / rr.stake_total)
