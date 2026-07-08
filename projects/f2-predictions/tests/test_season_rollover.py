"""Multi-season rollover + archival + seasons-index coverage.

Everything runs against tmp dirs (the injectable-path seams on
``season_rollover`` / ``bootstrap_next_season`` / ``export.write_seasons_index``)
— nothing here touches the repo's real ``website/public/data`` or ``data/``.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from f2_predictions import bootstrap_next_season, config, export, season_rollover


# --------------------------------------------------------------------------- #
# Fixtures: a fake active-season website data tree + results snapshot.
# --------------------------------------------------------------------------- #
@pytest.fixture()
def site_dir(tmp_path: Path) -> Path:
    data = tmp_path / "public_data"
    data.mkdir()
    (data / "f2.json").write_text(json.dumps({"season": 2026}))
    (data / "calibration_summary.json").write_text("{}")
    (data / "model_health.json").write_text("{}")
    for sub in ("rounds", "probabilities", "forward_eval"):
        (data / sub).mkdir()
        (data / sub / "round_01.json").write_text("{}")
    return data


@pytest.fixture()
def snapshot_dir(tmp_path: Path) -> Path:
    snap = tmp_path / "snapshots"
    snap.mkdir()
    return snap


def _write_snapshot(snapshot_dir: Path, year: int, completed: int, total: int = 14) -> None:
    (snapshot_dir / f"official_{year}.json").write_text(
        json.dumps({"season": year, "completedRounds": completed, "totalRounds": total})
    )


# --------------------------------------------------------------------------- #
# Archival
# --------------------------------------------------------------------------- #
def test_archive_copies_site_data_and_refreshes_index(site_dir, snapshot_dir):
    _write_snapshot(snapshot_dir, 2026, completed=14)
    dest = season_rollover.archive(2026, data_dir=site_dir, snapshot_dir=snapshot_dir,
                                   current_season=2027)

    assert dest == site_dir / "seasons" / "2026"
    assert (dest / "f2.json").exists()
    assert (dest / "calibration_summary.json").exists()
    assert (dest / "model_health.json").exists()
    assert (dest / "rounds" / "round_01.json").exists()
    assert (dest / "probabilities" / "round_01.json").exists()
    assert (dest / "forward_eval" / "round_01.json").exists()
    # The canonical results snapshot travels into the archive.
    assert (dest / "official_2026.json").exists()

    index = json.loads((site_dir / "seasons.json").read_text())
    assert index["current"] == 2027
    assert index["archived"] == [2026]
    assert index["available"] == [2026, 2027]
    by_year = {s["year"]: s for s in index["seasons"]}
    assert by_year[2026]["path"] == "seasons/2026"
    assert by_year[2026]["isCurrent"] is False
    assert by_year[2027]["path"] == ""
    assert by_year[2027]["isCurrent"] is True


def test_archive_dry_run_writes_nothing(site_dir, snapshot_dir):
    season_rollover.archive(2026, data_dir=site_dir, snapshot_dir=snapshot_dir, dry_run=True)
    assert not (site_dir / "seasons").exists()
    assert not (site_dir / "seasons.json").exists()


# --------------------------------------------------------------------------- #
# Season completion
# --------------------------------------------------------------------------- #
def test_season_complete_from_snapshot(snapshot_dir):
    _write_snapshot(snapshot_dir, 2026, completed=14, total=14)
    assert season_rollover.season_complete(2026, snapshot_dir=snapshot_dir)
    _write_snapshot(snapshot_dir, 2026, completed=5, total=14)
    assert not season_rollover.season_complete(2026, snapshot_dir=snapshot_dir)
    # No snapshot at all -> never complete.
    assert not season_rollover.season_complete(2031, snapshot_dir=snapshot_dir)


# --------------------------------------------------------------------------- #
# Start
# --------------------------------------------------------------------------- #
def test_start_requires_announced_calendar(site_dir, snapshot_dir):
    with pytest.raises(SystemExit):
        season_rollover.start(2027, data_dir=site_dir, snapshot_dir=snapshot_dir)


def test_start_activates_year_and_clears_rounds(site_dir, snapshot_dir):
    announced = snapshot_dir / "announced_seasons"
    assert bootstrap_next_season.bootstrap(2027, announced_dir=announced) == 0
    season_rollover.start(2027, data_dir=site_dir, snapshot_dir=snapshot_dir)

    marker = json.loads((snapshot_dir / "active_season.json").read_text())
    assert marker == {"season": 2027}
    # Active round files cleared (the new season's export regenerates them)...
    assert not list((site_dir / "rounds").glob("round_*.json"))
    assert not list((site_dir / "probabilities").glob("round_*.json"))
    # ...but forward_eval history is untouched and the index says 2027 is live.
    assert (site_dir / "forward_eval" / "round_01.json").exists()
    assert json.loads((site_dir / "seasons.json").read_text())["current"] == 2027


# --------------------------------------------------------------------------- #
# Auto rollover — the cron-safe gate
# --------------------------------------------------------------------------- #
def test_auto_noop_while_season_in_progress(site_dir, snapshot_dir):
    _write_snapshot(snapshot_dir, config.SEASON, completed=5)
    fired = season_rollover.auto(data_dir=site_dir, snapshot_dir=snapshot_dir,
                                 today=date(2099, 1, 1))
    assert fired is False
    assert not (site_dir / "seasons").exists()
    # The no-op path still refreshes the index (mirrors F1's --auto).
    assert json.loads((site_dir / "seasons.json").read_text())["current"] == config.SEASON


def test_auto_noop_until_next_season_begins(site_dir, snapshot_dir):
    _write_snapshot(snapshot_dir, config.SEASON, completed=14)
    announced = snapshot_dir / "announced_seasons"
    bootstrap_next_season.bootstrap(config.SEASON + 1, announced_dir=announced)
    first_race = json.loads(
        (announced / f"{config.SEASON + 1}.json").read_text()
    )["first_race_date"]
    day_before = date.fromisoformat(first_race).toordinal() - 1
    fired = season_rollover.auto(data_dir=site_dir, snapshot_dir=snapshot_dir,
                                 today=date.fromordinal(day_before))
    assert fired is False
    assert not (site_dir / "seasons").exists()


def test_auto_rolls_over_once_complete_and_begun(site_dir, snapshot_dir):
    year, nxt = config.SEASON, config.SEASON + 1
    _write_snapshot(snapshot_dir, year, completed=14)
    announced = snapshot_dir / "announced_seasons"
    bootstrap_next_season.bootstrap(nxt, announced_dir=announced)
    first_race = json.loads((announced / f"{nxt}.json").read_text())["first_race_date"]

    fired = season_rollover.auto(data_dir=site_dir, snapshot_dir=snapshot_dir,
                                 today=date.fromisoformat(first_race))
    assert fired is True
    # Finished season archived, next season active.
    assert (site_dir / "seasons" / str(year) / "f2.json").exists()
    assert json.loads((snapshot_dir / "active_season.json").read_text()) == {"season": nxt}
    index = json.loads((site_dir / "seasons.json").read_text())
    assert index["current"] == nxt
    assert year in index["archived"]


# --------------------------------------------------------------------------- #
# Bootstrap (announced-calendar placeholder)
# --------------------------------------------------------------------------- #
def test_bootstrap_placeholder_shape_and_idempotence(tmp_path):
    announced = tmp_path / "announced_seasons"
    assert bootstrap_next_season.bootstrap(2027, announced_dir=announced) == 0
    payload = json.loads((announced / "2027.json").read_text())

    assert payload["season"] == 2027
    assert payload["placeholder"] is True
    assert payload["lineup_provisional"] is True
    assert len(payload["calendar"]) == len(config.CALENDAR)
    assert len(payload["roster"]) == len(config.DRIVERS)
    assert len(payload["teams"]) == len(config.TEAMS)
    # Dates shifted +364 days per year: same weekday, one year on.
    r1 = payload["calendar"][0]
    src = date.fromisoformat(config.CALENDAR_META[1]["sprint"])
    assert date.fromisoformat(r1["sprint"]) == date.fromordinal(src.toordinal() + 364)
    assert payload["first_race_date"] == r1["sprint"]

    # Idempotent: a second run without --force leaves the file alone.
    (announced / "2027.json").write_text(json.dumps(payload | {"sentinel": True}))
    assert bootstrap_next_season.bootstrap(2027, announced_dir=announced) == 0
    assert json.loads((announced / "2027.json").read_text()).get("sentinel") is True


# --------------------------------------------------------------------------- #
# Export path contract: the CURRENT season's files never move
# --------------------------------------------------------------------------- #
def test_export_default_paths_unchanged_for_current_season():
    project_root = Path(export.__file__).resolve().parents[2]
    assert export.DEFAULT_OUT == project_root / "website" / "public" / "data"
    # Current season stays at the top-level data root...
    assert export.out_dir_for_season(config.SEASON) == export.DEFAULT_OUT
    # ...archived seasons nest under seasons/<year>/.
    assert (
        export.out_dir_for_season(config.SEASON - 1)
        == export.DEFAULT_OUT / "seasons" / str(config.SEASON - 1)
    )


def test_write_seasons_index_single_current_season(tmp_path):
    index = export.write_seasons_index(tmp_path)
    assert index["current"] == config.SEASON
    assert index["available"] == [config.SEASON]
    assert index["archived"] == []
    assert index["seasons"] == [
        {
            "year": config.SEASON,
            "isCurrent": True,
            "path": "",
            "label": str(config.SEASON),
        }
    ]
    on_disk = json.loads((tmp_path / "seasons.json").read_text())
    assert on_disk["current"] == config.SEASON
