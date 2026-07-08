"""Source-stack tests: snapshot, synthetic, composite, and the Pulselive parser."""
from __future__ import annotations

import json

from conftest import load_fixture

from formula_e_predictions import config
from formula_e_predictions.sources.composite import CompositeFESource
from formula_e_predictions.sources.pulselive_source import (
    parse_race_rows,
    points_races,
    season_of_championship,
)
from formula_e_predictions.sources.snapshot import load_snapshot
from formula_e_predictions.sources.synthetic import SyntheticFESource


# --------------------------------------------------------------------------- #
# Snapshot source (committed real data, offline)
# --------------------------------------------------------------------------- #
def test_snapshot_serves_real_completed_rounds(snapshot_source):
    snap = load_snapshot(config.SEASON)
    assert snap["season"] == config.SEASON
    completed = snapshot_source.completed_rounds(config.SEASON)
    assert len(completed) == snap["completedRounds"] >= 13

    res = snapshot_source.results(config.SEASON, 1)
    assert res is not None and len(res) >= 10
    assert res[0].position == 1
    # Points ride on the rows (bonuses included) — the winner scores >= 25.
    assert res[0].points >= 25


def test_snapshot_returns_none_for_unknown(snapshot_source):
    assert snapshot_source.results(config.SEASON, 99) is None
    assert snapshot_source.results(1999, 1) is None


def test_snapshot_qualifying_only_when_captured(snapshot_source):
    q1 = snapshot_source.qualifying(config.SEASON, 1)
    assert q1 and len(q1) >= 15
    assert snapshot_source.qualifying(config.SEASON, 99) is None


def test_past_season_snapshots_available(snapshot_source):
    """The backfill-committed Elo-window seasons resolve offline."""
    for year in (2023, 2024, 2025):
        res = snapshot_source.results(year, 1)
        assert res is not None and len(res) >= 10, year


# --------------------------------------------------------------------------- #
# Synthetic source (deterministic fallback)
# --------------------------------------------------------------------------- #
def test_synthetic_deterministic():
    a = SyntheticFESource().results(config.SEASON, 1)
    b = SyntheticFESource().results(config.SEASON, 1)
    assert [r.competitor for r in a] == [r.competitor for r in b]
    assert len(a) == len(config.DRIVERS)


def test_synthetic_never_fabricates_past_seasons():
    """Fabricated history would poison the Elo seed and the backtest."""
    assert SyntheticFESource().results(2025, 1) == []
    assert SyntheticFESource().results(2019, 3) == []


def test_synthetic_empty_for_future_rounds():
    assert SyntheticFESource().results(config.SEASON, config.COMPLETED_ROUNDS + 1) == []


# --------------------------------------------------------------------------- #
# Composite (provenance honesty)
# --------------------------------------------------------------------------- #
def test_composite_prefers_real_and_records_provenance():
    src = CompositeFESource.default()
    res = src.results(config.SEASON, 1)
    assert res and src.provenance(config.SEASON, 1) == "snapshot"
    assert CompositeFESource.is_real("snapshot")
    assert CompositeFESource.is_real("pulselive")
    assert not CompositeFESource.is_real("synthetic")


def test_composite_falls_back_to_synthetic_beyond_snapshot():
    src = CompositeFESource.default()
    beyond = load_snapshot(config.SEASON)["completedRounds"] + 1
    if beyond <= len(config.CALENDAR) and beyond <= config.COMPLETED_ROUNDS:
        src.results(config.SEASON, beyond)
        assert src.provenance(config.SEASON, beyond) == "synthetic"


def test_composite_qualifying_is_real_only():
    """The synthetic source has no qualifying, so any answer is real."""
    src = CompositeFESource.default()
    assert src.qualifying(config.SEASON, 1)
    assert src.qualifying(config.SEASON, len(config.CALENDAR)) is None


# --------------------------------------------------------------------------- #
# Pulselive race-list interpretation (fixtures — no network)
# --------------------------------------------------------------------------- #
def test_points_races_filters_tests_and_orders_by_date():
    races = load_fixture("pulselive_race_list.json")
    picked = points_races(races, 2026)
    assert len(picked) == 17
    # Date-ordered; round numbers are index+1.
    dates = [r["date"] for r in picked]
    assert dates == sorted(dates)
    assert picked[0]["city"] == "São Paulo"
    assert [r["city"] for r in picked[11:13]] == ["Shanghai", "Shanghai"]
    # No test event slips in even though tests share the championship NAME.
    assert not any("test" in r["name"].lower() for r in picked)


def test_season_of_championship_keys_by_ending_year():
    races = load_fixture("pulselive_race_list.json")
    regular = next(
        r for r in races if (r["championship"].get("series") or {}).get("seriesType") == "FE_REGULAR"
    )
    assert season_of_championship(regular["championship"]) in (2025, 2026)
    tests = next(
        r for r in races if (r["championship"].get("series") or {}).get("seriesType") == "FE_TESTS"
    )
    assert season_of_championship(tests["championship"]) is None


def test_parse_race_rows_real_payload():
    rows = parse_race_rows(load_fixture("pulselive_race_results.json"))
    assert len(rows) == 20
    classified = [r for r in rows if r["position"]]
    dnf = [r for r in rows if not r["position"]]
    assert len(classified) == 18 and len(dnf) == 2
    # Classified first, ordered by position.
    assert [r["position"] for r in rows[:18]] == list(range(1, 19))
    winner = rows[0]
    assert winner["code"] == "DIG" and winner["points"] == 25.0 and winner["grid"] == 19
    # Team alias normalisation.
    assert winner["team"] == "Lola Yamaha ABT"
    # Bonus flags survive: Drugovich pole (+3 on P6's 8), Rowland FL (+1 on P8's 4).
    dru = next(r for r in rows if r["code"] == "DRU")
    assert dru["pole"] is True and dru["points"] == 11.0
    row_ = next(r for r in rows if r["code"] == "ROW")
    assert row_["fastestLap"] is True and row_["points"] == 5.0
    # DNFs carry status, not a fake position.
    assert all(r["status"] == "DNF" for r in dnf)


def test_snapshot_matches_official_standings_totals():
    """Official totals equal the sum of captured per-race points (bonuses incl.)."""
    snap = load_snapshot(config.SEASON)
    by_code: dict[str, float] = {}
    for block in snap["results"].values():
        for row in block["race"]:
            by_code[row["code"]] = by_code.get(row["code"], 0.0) + float(row.get("points") or 0.0)
    for d in snap["driverStandings"]:
        assert abs(by_code.get(d["code"], 0.0) - d["points"]) < 0.5, d["code"]


def test_season_snapshot_files_are_valid_json():
    from formula_e_predictions.sources.snapshot import _snapshot_path

    for year in (2023, 2024, 2025):
        p = _snapshot_path(year)
        snap = json.loads(p.read_text(encoding="utf-8"))
        assert snap["season"] == year
        assert snap["completedRounds"] == len(snap["results"]) >= 10
