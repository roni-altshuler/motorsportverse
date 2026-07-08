"""Regression tests for the wrong-event ingestion guards (FE).

On 2026-07-05 (F1, British GP race morning) FastF1's fuzzy event matcher
silently "corrected" 'Great Britain' to the Austrian Grand Prix and the
pipeline published Austria's classification as Silverstone's official result.
FE reads a REST API keyed by opaque race UUIDs instead — the same class of bug
(a CDN/API serving a *different* race's payload for a requested id, or the
calendar drifting out of sync with config) would flow straight into the
committed snapshot. These tests pin the guards that make that impossible:

  * ``verify_race_identity`` — the race's own metadata (date / city / season)
    must match the requested calendar entry before anything is parsed; a
    mismatch (or an identity-less payload) raises ``WrongEventError``.
  * ``PulseliveFESource`` cross-checks every active-season round against the
    human-verified ``config.CALENDAR_META`` (an independent source of truth
    from the API's own ordering).
  * ``refresh.build_snapshot`` refuses to run when the API's points-race count
    disagrees with the config calendar, and raises before ``main()`` ever
    writes — a wrong event can never mutate ``data/official_2026.json``.
  * The empty-scrape regression guard: a refresh that would REDUCE the
    committed snapshot's completed rounds refuses to overwrite it.
"""
from __future__ import annotations

import json

import pytest
from conftest import load_fixture

from formula_e_predictions import config, refresh
from formula_e_predictions.sources.pulselive_source import (
    PulseliveFESource,
    WrongEventError,
    verify_race_identity,
)

SEASON = config.SEASON


def _race(round_: int) -> dict:
    races = load_fixture("pulselive_race_list.json")
    from formula_e_predictions.sources.pulselive_source import points_races

    return points_races(races, SEASON)[round_ - 1]


# --------------------------------------------------------------------------- #
# verify_race_identity
# --------------------------------------------------------------------------- #
def test_identity_ok_for_matching_race():
    race = _race(13)  # Shanghai II, 2026-07-05
    verify_race_identity(
        race, round=13, expected={"date": config.CALENDAR_META[13]["date"], "season": SEASON}
    )


def test_identity_rejects_wrong_date():
    race = _race(13)
    with pytest.raises(WrongEventError):
        verify_race_identity(race, round=13, expected={"date": "2026-07-04"})


def test_identity_rejects_wrong_city():
    race = _race(13)  # Shanghai
    with pytest.raises(WrongEventError):
        verify_race_identity(race, round=13, expected={"city": "Tokyo"})


def test_identity_rejects_wrong_season():
    race = _race(13)
    with pytest.raises(WrongEventError):
        verify_race_identity(race, round=13, expected={"season": SEASON - 1})


def test_identity_rejects_payload_without_identity():
    with pytest.raises(WrongEventError):
        verify_race_identity({}, round=1, expected={"date": "2025-12-06"})
    with pytest.raises(WrongEventError):
        verify_race_identity({"name": "mystery"}, round=1, expected={})


# --------------------------------------------------------------------------- #
# The live source's per-round cross-check against config
# --------------------------------------------------------------------------- #
class _FixtureClient:
    """PulseliveClient stand-in serving the fixture race list (no network)."""

    def __init__(self, races):
        self._races = races

    def all_races(self):
        return self._races

    def sessions(self, race_id):
        return None  # never reached in these tests

    def session_results(self, race_id, session_id):
        return None


def test_source_accepts_consistent_calendar():
    src = PulseliveFESource(client=_FixtureClient(load_fixture("pulselive_race_list.json")))
    races = src.season_races(SEASON)
    assert len(races) == 17
    # _race_for_round verifies identity for the active season without raising.
    assert src._race_for_round(SEASON, 13)["city"] == "Shanghai"


def test_source_refuses_shifted_calendar():
    """If the API listing drifts (a race removed/added upstream), every
    downstream round would map to the WRONG event — the guard must trip."""
    races = load_fixture("pulselive_race_list.json")
    from formula_e_predictions.sources.pulselive_source import points_races

    season_races = points_races(races, SEASON)
    dropped = season_races[0]  # pretend São Paulo vanished from the listing
    remaining = [r for r in races if r.get("id") != dropped["id"]]
    src = PulseliveFESource(client=_FixtureClient(remaining))
    with pytest.raises(WrongEventError):
        src.race_rows(SEASON, 13)  # would fetch Tokyo's payload as "round 13"


def test_source_refuses_wrong_championship_id(monkeypatch):
    races = load_fixture("pulselive_race_list.json")
    monkeypatch.setitem(config.CHAMPIONSHIP_IDS, SEASON, "not-the-real-id")
    src = PulseliveFESource(client=_FixtureClient(races))
    with pytest.raises(WrongEventError):
        src.season_races(SEASON)


# --------------------------------------------------------------------------- #
# refresh.build_snapshot guards
# --------------------------------------------------------------------------- #
class _CountMismatchSource:
    def season_races(self, season):
        return [{"id": f"race-{i}", "date": "2026-01-01"} for i in range(3)]  # != 17


def test_build_snapshot_refuses_calendar_count_mismatch():
    with pytest.raises(WrongEventError):
        refresh.build_snapshot(SEASON, source=_CountMismatchSource())


def test_build_snapshot_propagates_wrong_event(monkeypatch):
    """A wrong-event detection inside the per-round fetch aborts the build —
    nothing is ever written for a mismatched round."""

    class _WrongEventSource:
        def season_races(self, season):
            return [{"id": f"race-{i}", "date": "2026-01-01"} for i in range(len(config.CALENDAR))]

        def qualifying(self, season, rnd):
            raise WrongEventError(f"round {rnd}: fetched a different race's payload")

    with pytest.raises(WrongEventError):
        refresh.build_snapshot(SEASON, source=_WrongEventSource())


# --------------------------------------------------------------------------- #
# Empty-scrape regression guard
# --------------------------------------------------------------------------- #
def test_refresh_refuses_completed_rounds_regression(tmp_path, monkeypatch, capsys):
    out = tmp_path / "official_2026.json"
    out.write_text(json.dumps({"season": SEASON, "completedRounds": 13}))

    regressed = {"season": SEASON, "completedRounds": 0, "totalRounds": 17,
                 "calendar": [], "driverStandings": [], "teamStandings": [],
                 "results": {}, "qualifying": {}}
    monkeypatch.setattr(refresh, "build_snapshot", lambda season, **kw: regressed)
    monkeypatch.setattr(
        "sys.argv", ["refresh", "--season", str(SEASON), "--out", str(out)]
    )
    with pytest.raises(SystemExit) as exc:
        refresh.main()
    assert exc.value.code == 0  # graceful no-op, not a crash
    # The healthy snapshot is untouched.
    assert json.loads(out.read_text())["completedRounds"] == 13
    assert "refusing to regress" in capsys.readouterr().out


def test_refresh_allows_regression_with_flag(tmp_path, monkeypatch):
    out = tmp_path / "official_2026.json"
    out.write_text(json.dumps({"season": SEASON, "completedRounds": 13}))
    regressed = {"season": SEASON, "completedRounds": 2, "totalRounds": 17,
                 "calendar": [], "driverStandings": [], "teamStandings": [],
                 "results": {}, "qualifying": {}}
    monkeypatch.setattr(refresh, "build_snapshot", lambda season, **kw: regressed)
    monkeypatch.setattr(
        "sys.argv",
        ["refresh", "--season", str(SEASON), "--out", str(out), "--allow-regression"],
    )
    refresh.main()
    assert json.loads(out.read_text())["completedRounds"] == 2
