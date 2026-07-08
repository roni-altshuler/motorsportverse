"""Season rollover + next-season bootstrap: archive/start/auto, all offline."""
from __future__ import annotations

import json

import pytest

from nascar_predictions import bootstrap_next_season as boot, config, season_rollover as ro

SEASON = config.SEASON


def _fake_site(tmp_path):
    data_dir = tmp_path / "site"
    (data_dir / "rounds").mkdir(parents=True)
    (data_dir / "probabilities").mkdir()
    (data_dir / "nascar.json").write_text("{}")
    (data_dir / "playoff_projection.json").write_text("{}")
    (data_dir / "rounds" / "round_01.json").write_text("{}")
    (data_dir / "probabilities" / "round_01.json").write_text("{}")
    return data_dir


def _fake_snapshot_dir(tmp_path, completed: int, total: int = 36):
    snap_dir = tmp_path / "data"
    snap_dir.mkdir(exist_ok=True)
    (snap_dir / f"official_{SEASON}.json").write_text(
        json.dumps({"season": SEASON, "completedRounds": completed, "totalRounds": total})
    )
    return snap_dir


def test_season_complete_reads_snapshot(tmp_path):
    snap_dir = _fake_snapshot_dir(tmp_path, completed=19)
    assert ro.season_complete(SEASON, snapshot_dir=snap_dir) is False
    snap_dir = _fake_snapshot_dir(tmp_path, completed=36)
    assert ro.season_complete(SEASON, snapshot_dir=snap_dir) is True


def test_archive_copies_site_data(tmp_path):
    data_dir = _fake_site(tmp_path)
    snap_dir = _fake_snapshot_dir(tmp_path, completed=36)
    dest = ro.archive(SEASON, data_dir=data_dir, snapshot_dir=snap_dir, current_season=SEASON)
    assert (dest / "nascar.json").exists()
    assert (dest / "playoff_projection.json").exists()
    assert (dest / "rounds" / "round_01.json").exists()
    assert (dest / f"official_{SEASON}.json").exists()
    index = json.loads((data_dir / "seasons.json").read_text())
    assert index["current"] == SEASON


def test_start_requires_announced_calendar(tmp_path):
    data_dir = _fake_site(tmp_path)
    with pytest.raises(SystemExit):
        ro.start(
            SEASON + 1,
            data_dir=data_dir,
            snapshot_dir=tmp_path / "data",
            announced_dir=tmp_path / "announced",
        )


def test_bootstrap_then_start(tmp_path):
    announced_dir = tmp_path / "announced"
    rc = boot.bootstrap(SEASON + 1, announced_dir=announced_dir)
    assert rc == 0
    payload = json.loads((announced_dir / f"{SEASON + 1}.json").read_text())
    assert payload["season"] == SEASON + 1
    assert payload["placeholder"] is True
    assert len(payload["calendar"]) == 36
    assert payload["calendar"][0]["raceId"] is None  # race ids are season-specific
    assert len(payload["roster"]) == 38
    # Idempotent without --force.
    assert boot.bootstrap(SEASON + 1, announced_dir=announced_dir) == 0

    data_dir = _fake_site(tmp_path)
    snap_dir = _fake_snapshot_dir(tmp_path, completed=36)
    ro.start(
        SEASON + 1, data_dir=data_dir, snapshot_dir=snap_dir, announced_dir=announced_dir
    )
    marker = json.loads((snap_dir / "active_season.json").read_text())
    assert marker == {"season": SEASON + 1}
    assert not list((data_dir / "rounds").glob("round_*.json"))  # cleared


def test_auto_noop_when_season_incomplete(tmp_path):
    data_dir = _fake_site(tmp_path)
    snap_dir = _fake_snapshot_dir(tmp_path, completed=19)
    rolled = ro.auto(data_dir=data_dir, snapshot_dir=snap_dir,
                     announced_dir=tmp_path / "announced")
    assert rolled is False
    assert (data_dir / "seasons.json").exists()  # index still refreshed


def test_auto_noop_before_next_first_race(tmp_path):
    from datetime import date

    announced_dir = tmp_path / "announced"
    boot.bootstrap(SEASON + 1, announced_dir=announced_dir)
    data_dir = _fake_site(tmp_path)
    snap_dir = _fake_snapshot_dir(tmp_path, completed=36)
    rolled = ro.auto(
        data_dir=data_dir,
        snapshot_dir=snap_dir,
        announced_dir=announced_dir,
        today=date(SEASON, 12, 1),  # before the next season's opener
    )
    assert rolled is False


def test_auto_rolls_over_when_ready(tmp_path):
    from datetime import date

    announced_dir = tmp_path / "announced"
    boot.bootstrap(SEASON + 1, announced_dir=announced_dir)
    data_dir = _fake_site(tmp_path)
    snap_dir = _fake_snapshot_dir(tmp_path, completed=36)
    rolled = ro.auto(
        data_dir=data_dir,
        snapshot_dir=snap_dir,
        announced_dir=announced_dir,
        today=date(SEASON + 1, 3, 1),  # after the shifted Daytona date
    )
    assert rolled is True
    assert (data_dir / "seasons" / str(SEASON) / "nascar.json").exists()
    assert json.loads((snap_dir / "active_season.json").read_text())["season"] == SEASON + 1
