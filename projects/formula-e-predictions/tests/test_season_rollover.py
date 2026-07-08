"""Season rollover + next-season bootstrap (tmp-dir sandboxed)."""
from __future__ import annotations

import json

import pytest

from formula_e_predictions import bootstrap_next_season as bootstrap
from formula_e_predictions import config, season_rollover as rollover

SEASON = config.SEASON


@pytest.fixture()
def web_data(tmp_path):
    """A minimal active-season website data tree."""
    d = tmp_path / "webdata"
    d.mkdir()
    (d / "fe.json").write_text(json.dumps({"season": SEASON}))
    (d / "calibration_summary.json").write_text("{}")
    rounds = d / "rounds"
    rounds.mkdir()
    (rounds / "round_01.json").write_text("{}")
    probs = d / "probabilities"
    probs.mkdir()
    (probs / "round_01.json").write_text("{}")
    return d


@pytest.fixture()
def snap_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


def _write_snapshot(snap_dir, year, completed, total=17):
    (snap_dir / f"official_{year}.json").write_text(
        json.dumps({"season": year, "completedRounds": completed, "totalRounds": total})
    )


# --------------------------------------------------------------------------- #
# season_complete
# --------------------------------------------------------------------------- #
def test_season_complete_gate(snap_dir):
    _write_snapshot(snap_dir, SEASON, 13)
    assert not rollover.season_complete(SEASON, snapshot_dir=snap_dir)
    _write_snapshot(snap_dir, SEASON, 17)
    assert rollover.season_complete(SEASON, snapshot_dir=snap_dir)
    assert not rollover.season_complete(1999, snapshot_dir=snap_dir)


# --------------------------------------------------------------------------- #
# archive / start
# --------------------------------------------------------------------------- #
def test_archive_copies_season_tree(web_data, snap_dir):
    _write_snapshot(snap_dir, SEASON, 17)
    dest = rollover.archive(
        SEASON, data_dir=web_data, snapshot_dir=snap_dir, current_season=SEASON
    )
    assert (dest / "fe.json").exists()
    assert (dest / "rounds" / "round_01.json").exists()
    assert (dest / f"official_{SEASON}.json").exists()
    index = json.loads((web_data / "seasons.json").read_text())
    assert index["current"] == SEASON


def test_start_requires_announced_calendar(web_data, snap_dir):
    with pytest.raises(SystemExit):
        rollover.start(
            SEASON + 1, data_dir=web_data, snapshot_dir=snap_dir,
            announced_dir=snap_dir / "announced_seasons",
        )


def test_start_activates_and_clears(web_data, snap_dir):
    announced = snap_dir / "announced_seasons"
    bootstrap.bootstrap(SEASON + 1, announced_dir=announced)
    rollover.start(
        SEASON + 1, data_dir=web_data, snapshot_dir=snap_dir, announced_dir=announced
    )
    marker = json.loads((snap_dir / "active_season.json").read_text())
    assert marker == {"season": SEASON + 1}
    assert not list((web_data / "rounds").glob("round_*.json"))
    index = json.loads((web_data / "seasons.json").read_text())
    assert index["current"] == SEASON + 1
    # FE labels use the split-year championship form.
    labels = {s["year"]: s["label"] for s in index["seasons"]}
    assert labels[SEASON + 1] == f"{SEASON}-{str(SEASON + 1)[2:]}"


# --------------------------------------------------------------------------- #
# auto
# --------------------------------------------------------------------------- #
def test_auto_noop_when_season_incomplete(web_data, snap_dir):
    _write_snapshot(snap_dir, SEASON, 13)
    rolled = rollover.auto(data_dir=web_data, snapshot_dir=snap_dir)
    assert rolled is False
    assert (web_data / "seasons.json").exists()  # index still refreshed


def test_auto_noop_until_next_season_begins(web_data, snap_dir):
    from datetime import date

    _write_snapshot(snap_dir, SEASON, 17)
    announced = snap_dir / "announced_seasons"
    bootstrap.bootstrap(SEASON + 1, announced_dir=announced)
    # Next season's first race (early Dec 2026) has not happened yet.
    rolled = rollover.auto(
        data_dir=web_data, snapshot_dir=snap_dir, announced_dir=announced,
        today=date(2026, 9, 1),
    )
    assert rolled is False


def test_auto_rolls_over_when_ready(web_data, snap_dir):
    from datetime import date

    _write_snapshot(snap_dir, SEASON, 17)
    announced = snap_dir / "announced_seasons"
    bootstrap.bootstrap(SEASON + 1, announced_dir=announced)
    rolled = rollover.auto(
        data_dir=web_data, snapshot_dir=snap_dir, announced_dir=announced,
        today=date(2026, 12, 31),
    )
    assert rolled is True
    assert (web_data / "seasons" / str(SEASON) / "fe.json").exists()
    marker = json.loads((snap_dir / "active_season.json").read_text())
    assert marker == {"season": SEASON + 1}


# --------------------------------------------------------------------------- #
# bootstrap
# --------------------------------------------------------------------------- #
def test_bootstrap_placeholder_payload(tmp_path):
    announced = tmp_path / "announced"
    assert bootstrap.bootstrap(SEASON + 1, announced_dir=announced) == 0
    payload = json.loads((announced / f"{SEASON + 1}.json").read_text())
    assert payload["season"] == SEASON + 1
    assert payload["label"] == f"SEASON {SEASON}-{SEASON + 1}"
    assert payload["placeholder"] is True
    assert len(payload["calendar"]) == len(config.CALENDAR)
    # Dates shift +364 days (same weekday) — round 1 lands in Dec of SEASON.
    assert payload["calendar"][0]["date"].startswith(f"{SEASON}-12")
    assert len(payload["roster"]) == len(config.DRIVERS)


def test_bootstrap_idempotent(tmp_path, capsys):
    announced = tmp_path / "announced"
    bootstrap.bootstrap(SEASON + 1, announced_dir=announced)
    before = (announced / f"{SEASON + 1}.json").read_text()
    assert bootstrap.bootstrap(SEASON + 1, announced_dir=announced) == 0
    assert (announced / f"{SEASON + 1}.json").read_text() == before
    assert "already exists" in capsys.readouterr().out


def test_bootstrap_rejects_invalid_install(tmp_path):
    announced = tmp_path / "announced"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"season": SEASON + 1, "calendar": []}))
    assert bootstrap.bootstrap(SEASON + 1, announced_dir=announced, from_file=bad) == 1
    assert not (announced / f"{SEASON + 1}.json").exists()
