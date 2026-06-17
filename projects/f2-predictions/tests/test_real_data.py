"""Phase 3 real-data layer: snapshot source, official calendar, exact standings.

These guard the repoint to the real 2026 FIA F2 season — the committed snapshot
(data/official_2026.json) must stay internally consistent and flow through the
export unchanged, and the calendar must match the official schedule.
"""

import json

import pytest

from f2_predictions import config, export
from f2_predictions.datasource import F2DataSource
from f2_predictions.sources.fia_f2_source import _RE_TITLE_ROUND
from f2_predictions.sources.snapshot import SnapshotF2Source, load_snapshot


# --------------------------------------------------------------------------- #
# Official calendar
# --------------------------------------------------------------------------- #
def test_calendar_is_the_official_14_round_2026_schedule():
    keys = [v.key for v in config.CALENDAR]
    assert len(keys) == 14
    # Correct order incl. the fly-aways that the old placeholder calendar dropped.
    assert keys[:6] == ["melbourne", "miami", "montreal", "monaco", "catalunya", "spielberg"]
    assert keys[-1] == "yas-marina"
    assert set(config.CALENDAR_META) == set(range(1, 15))


def test_title_round_regex_parses_round_country_city_date():
    title = "Formula 2 2026 Result for Round 2 : USA , Miami 01-03 May 2026"
    m = _RE_TITLE_ROUND.search(title)
    assert m and int(m.group(1)) == 2
    assert m.group(2).strip() == "USA"
    assert m.group(3).strip() == "Miami"


# --------------------------------------------------------------------------- #
# Snapshot source
# --------------------------------------------------------------------------- #
def test_snapshot_serves_real_completed_rounds_only():
    s = SnapshotF2Source()
    feature = s.results(config.SEASON, 1, race_index=1)
    assert feature is not None and len(feature) >= 12  # real classified finishers
    # positions ascending & unique (classified order)
    pos = [r.position for r in feature]
    assert pos == sorted(pos) and len(set(pos)) == len(pos)
    # a not-yet-run round is absent from the snapshot → defer
    assert s.results(config.SEASON, len(config.CALENDAR), race_index=1) is None


def test_snapshot_standings_reconcile_to_totals():
    snap = load_snapshot()
    assert snap and snap["season"] == config.SEASON
    for d in snap["driverStandings"]:
        per = sum((sp or 0) + (ft or 0) for sp, ft in d["perRound"])
        assert per == pytest.approx(d["points"]), f"{d['code']} {per} != {d['points']}"
    # teams reconcile too
    for t in snap["teamStandings"]:
        per = sum((sp or 0) + (ft or 0) for sp, ft in t["perRound"])
        assert per == pytest.approx(t["points"]), f"{t['team']} {per} != {t['points']}"


def test_team_points_equal_sum_of_driver_points_official():
    snap = load_snapshot()
    drivers = sum(d["points"] for d in snap["driverStandings"])
    teams = sum(t["points"] for t in snap["teamStandings"])
    assert drivers == pytest.approx(teams)


# --------------------------------------------------------------------------- #
# Export uses the exact official standings (incl. pole/FL bonuses)
# --------------------------------------------------------------------------- #
def test_export_driver_standings_match_official_snapshot(tmp_path):
    export.write(tmp_path)
    data = json.loads((tmp_path / "f2.json").read_text())
    snap = load_snapshot()
    by_code = {d["code"]: d["points"] for d in snap["driverStandings"]}
    # Top 10 displayed totals equal the official snapshot totals exactly.
    for row in data["driverStandings"][:10]:
        assert row["points"] == pytest.approx(by_code[row["code"]])
    assert data["completedRounds"] == snap["completedRounds"]
    # completed rounds carry real provenance, not "synthetic".
    completed = [c for c in data["calendar"] if c["completed"]]
    assert completed and all(c["dataSource"] in {"snapshot", "fia"} for c in completed)


def test_default_datasource_completed_rounds_match_snapshot():
    src = F2DataSource()
    assert src.completed_rounds(config.SEASON) == list(
        range(1, load_snapshot()["completedRounds"] + 1)
    )
