"""Tests for hands-off season rollover: the FastF1 calendar bootstrap, the
generated-season loader, and the safety guard that keeps a pre-staged future
calendar from hijacking the live season before it starts racing."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import f1_prediction_utils as fpu  # noqa: E402
import bootstrap_next_season as boot  # noqa: E402


# ── Safety guard: a pre-staged future calendar must stay dormant ──────────────

def test_future_calendar_does_not_hijack_active_season():
    """Adding CALENDAR_<future> (first race in the future) must NOT change the
    active season — this is the core protection for the live pipeline."""
    baseline = fpu._default_season_year()
    fpu.CALENDAR_9999 = {1: {"date": "9999-03-01", "gp_key": "Test"}}
    try:
        assert 9999 in fpu._available_season_years("CALENDAR")
        assert fpu._season_started(9999) is False
        # Active season is unchanged despite a newer calendar existing.
        assert fpu._default_season_year() == baseline
    finally:
        del fpu.CALENDAR_9999


def test_started_future_season_becomes_active():
    """Once a newer season's first race date has passed, it becomes active."""
    baseline = fpu._default_season_year()
    fpu.CALENDAR_2099 = {1: {"date": "2000-01-01", "gp_key": "Test"}}
    try:
        assert fpu._season_started(2099) is True
        assert fpu._default_season_year() == 2099
        assert fpu._default_season_year() > baseline
    finally:
        del fpu.CALENDAR_2099


def test_season_started_handles_missing_or_bad_dates():
    fpu.CALENDAR_9998 = {1: {"gp_key": "NoDate"}}
    try:
        assert fpu._season_started(9998) is False
    finally:
        del fpu.CALENDAR_9998
    assert fpu._season_started(1234) is False  # no such calendar


# ── Loader: generated_seasons/<year>.json → module globals ────────────────────

def test_loader_registers_generated_calendar(tmp_path, monkeypatch):
    """A generated_seasons JSON file registers CALENDAR/lineup globals with
    int-keyed rounds and int driver numbers."""
    gen = tmp_path / "generated_seasons"
    gen.mkdir()
    (gen / "9997.json").write_text(
        '{"calendar": {"1": {"date": "9997-03-01", "gp_key": "Test", "laps": 50}},'
        ' "driver_team": {"VER": "Red Bull Racing"},'
        ' "driver_numbers": {"VER": "1"}}'
    )
    # Point the loader at the temp dir.
    monkeypatch.setattr(fpu.os.path, "dirname", lambda _p: str(tmp_path))
    try:
        fpu._load_generated_seasons()
        cal = getattr(fpu, "CALENDAR_9997")
        assert 1 in cal and cal[1]["gp_key"] == "Test"  # int-keyed
        assert fpu.DRIVER_TEAM_9997 == {"VER": "Red Bull Racing"}
        assert fpu.DRIVER_NUMBERS_9997 == {"VER": 1}  # coerced to int
    finally:
        for attr in ("CALENDAR_9997", "DRIVER_TEAM_9997", "DRIVER_NUMBERS_9997"):
            if hasattr(fpu, attr):
                delattr(fpu, attr)


def test_loader_noop_without_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(fpu.os.path, "dirname", lambda _p: str(tmp_path / "nope"))
    fpu._load_generated_seasons()  # must not raise


# ── gp_key resolution: disambiguates multi-race countries ─────────────────────

@pytest.mark.parametrize("location,country,event,expected", [
    ("Austin", "United States", "United States Grand Prix", "United States"),
    ("Miami", "United States", "Miami Grand Prix", "Miami"),
    ("Las Vegas", "United States", "Las Vegas Grand Prix", "Las Vegas"),
    ("Monza", "Italy", "Italian Grand Prix", "Italy"),
    ("Imola", "Italy", "Emilia Romagna Grand Prix", "Emilia Romagna"),
    ("Silverstone", "Great Britain", "British Grand Prix", "Great Britain"),
    ("Sakhir", "Bahrain", "Bahrain Grand Prix", "Bahrain"),
    # FastF1 has reported Abu Dhabi as both "Yas Marina" and "Yas Island".
    ("Yas Island", "United Arab Emirates", "Abu Dhabi Grand Prix", "Abu Dhabi"),
    ("Unknownville", "Atlantis", "Atlantis Grand Prix", "Atlantis"),
])
def test_resolve_gp_key(location, country, event, expected):
    assert boot._resolve_gp_key(location, country, event) == expected


# ── build_calendar: shape FastF1 schedule into a CALENDAR dict ────────────────

def _fake_schedule(rows):
    return pd.DataFrame(rows)


def test_build_calendar_from_schedule(monkeypatch):
    import fastf1
    sched = _fake_schedule([
        {"RoundNumber": 0, "Country": "Bahrain", "Location": "Sakhir",
         "EventName": "Pre-Season Test", "EventDate": pd.Timestamp("2027-02-20"),
         "EventFormat": "testing"},
        {"RoundNumber": 1, "Country": "Australia", "Location": "Melbourne",
         "EventName": "Australian Grand Prix", "EventDate": pd.Timestamp("2027-03-07"),
         "EventFormat": "conventional"},
        {"RoundNumber": 2, "Country": "China", "Location": "Shanghai",
         "EventName": "Chinese Grand Prix", "EventDate": pd.Timestamp("2027-03-21"),
         "EventFormat": "sprint_qualifying"},
    ])
    monkeypatch.setattr(fastf1, "get_event_schedule", lambda *a, **k: sched)

    calendar, warnings = boot.build_calendar(2027)
    assert calendar is not None
    assert set(calendar.keys()) == {1, 2}  # round 0 (testing) dropped
    assert calendar[1]["gp_key"] == "Australia"
    assert calendar[1]["date"] == "2027-03-07"
    assert calendar[1]["sprint"] is False
    # Round 2 is a sprint; specs are carried from the known China calendar entry.
    assert calendar[2]["sprint"] is True
    assert "sprint_laps" in calendar[2]
    assert calendar[2]["laps"] == fpu.get_calendar(2026)[2]["laps"]


def test_build_calendar_new_circuit_gets_defaults(monkeypatch):
    import fastf1
    sched = _fake_schedule([
        {"RoundNumber": 1, "Country": "Narnia", "Location": "Cair Paravel",
         "EventName": "Narnia Grand Prix", "EventDate": pd.Timestamp("2030-04-01"),
         "EventFormat": "conventional"},
    ])
    monkeypatch.setattr(fastf1, "get_event_schedule", lambda *a, **k: sched)
    calendar, warnings = boot.build_calendar(2030)
    assert calendar[1]["gp_key"] == "Narnia"
    assert calendar[1]["laps"] >= 1  # estimated, not None
    assert calendar[1]["circuit_km"] == boot._DEFAULT_CIRCUIT_KM
    assert any("Narnia" in w for w in warnings)


def test_build_calendar_unpublished_returns_none(monkeypatch):
    import fastf1
    monkeypatch.setattr(fastf1, "get_event_schedule", lambda *a, **k: pd.DataFrame())
    calendar, reason = boot.build_calendar(2099)
    assert calendar is None
    assert "published" in reason or "empty" in reason


def test_build_calendar_fetch_failure_returns_none(monkeypatch):
    import fastf1

    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(fastf1, "get_event_schedule", _boom)
    calendar, reason = boot.build_calendar(2099)
    assert calendar is None
    assert "failed" in reason


# ── rollover trigger helpers ──────────────────────────────────────────────────

def test_rollover_current_website_year(monkeypatch, tmp_path):
    rollover = importlib.import_module("season_rollover")
    for y in (2025, 2026):
        (tmp_path / f"season_tracker_{y}.json").write_text("{}")
    monkeypatch.setattr(rollover, "ROOT", tmp_path)
    assert rollover._current_website_year() == 2026


def test_rollover_auto_no_roll_when_same(monkeypatch):
    rollover = importlib.import_module("season_rollover")
    monkeypatch.setattr(rollover, "_active_year", lambda: 2026)
    monkeypatch.setattr(rollover, "_current_website_year", lambda: 2026)
    # dry_run avoids touching disk / seasons.json.
    rollover.auto(dry_run=True)  # must not raise; no rollover


def test_rollover_auto_rolls_when_newer_started(monkeypatch):
    rollover = importlib.import_module("season_rollover")
    calls = {}
    monkeypatch.setattr(rollover, "_active_year", lambda: 2027)
    monkeypatch.setattr(rollover, "_current_website_year", lambda: 2026)
    monkeypatch.setattr(rollover, "archive",
                        lambda y, dry_run=False: calls.setdefault("archive", y))
    monkeypatch.setattr(rollover, "start",
                        lambda y, dry_run=False: calls.setdefault("start", y))
    rollover.auto(dry_run=True)
    assert calls == {"archive": 2026, "start": 2027}
