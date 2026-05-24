"""Schema tests for the JSON files consumed by the Next.js site.

These pydantic models mirror the load-bearing TypeScript interfaces in
`website/src/types/index.ts`.  They are intentionally permissive on optional
fields — the goal is to catch breakage on critical fields the UI dereferences
without null-checking, not to enforce every TS optional.

When you change a Python output, update the matching TS type in the same PR.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest
from pydantic import BaseModel, ConfigDict, Field

from tests.conftest import WEBSITE_DATA


class _Loose(BaseModel):
    """Base class that ignores extra fields so the contract can grow."""

    model_config = ConfigDict(extra="ignore")


class CalendarEntry(_Loose):
    round: int
    name: str
    gpKey: str
    date: str
    laps: int
    circuitType: str
    country: str
    sprint: bool


class DriverInfo(_Loose):
    code: str
    fullName: str
    team: str
    # Mirror of `DriverInfo.headshotUrl` in website/src/types/index.ts.
    headshotUrl: Optional[str] = None


class SeasonData(_Loose):
    season: int
    totalRounds: int
    calendar: list[CalendarEntry]
    completedRounds: list[int]
    # `drivers` is optional here — older snapshots may pre-date the field.
    drivers: list[DriverInfo] = Field(default_factory=list)


class ClassificationEntry(_Loose):
    position: int
    driver: str
    team: str
    predictedTime: float
    points: int
    # Mirror of `ClassificationEntry.headshotUrl` in website/src/types/index.ts.
    headshotUrl: Optional[str] = None


class RoundData(_Loose):
    round: int
    name: str
    gpKey: str
    date: str
    sprint: bool
    classification: list[ClassificationEntry] = Field(default_factory=list)


class SeasonTrackerRound(_Loose):
    round: int
    hasActual: bool


class SeasonTrackerData(_Loose):
    rounds: list[SeasonTrackerRound]


class DriverStanding(_Loose):
    position: int
    driver: str
    team: str
    points: float
    # Mirror of `DriverStanding.headshotUrl` in website/src/types/index.ts.
    headshotUrl: Optional[str] = None


class StandingsData(_Loose):
    lastUpdatedRound: int
    drivers: list[DriverStanding] = Field(default_factory=list)


class ProbabilityMarketEntry(_Loose):
    driver: str
    probability: float
    rawProbability: float


class ProbabilityCalibrationBlock(_Loose):
    method: str
    trainingSeasons: list[int] = Field(default_factory=list)
    applied: bool


class ProbabilityRoundData(_Loose):
    """Schema for `website/public/data/probabilities/round_NN.json`.

    Permissive: any new optional field on the contract won't break this test
    (extra="ignore" inherited from `_Loose`).  Only the load-bearing
    structural fields are required.
    """

    round: int
    season: int
    generatedAt: str
    method: str
    monteCarloSamples: int
    temperature: float
    calibration: ProbabilityCalibrationBlock
    markets: dict[str, list[ProbabilityMarketEntry]]
    h2h: dict[str, dict[str, float]] = Field(default_factory=dict)


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


@pytest.mark.skipif(
    not (WEBSITE_DATA / "season.json").exists(),
    reason="No season.json generated yet (run export_website_data.py first)",
)
def test_season_json_matches_schema():
    data = _load(WEBSITE_DATA / "season.json")
    SeasonData(**data)


@pytest.mark.skipif(
    not (WEBSITE_DATA / "season_tracker.json").exists(),
    reason="No season_tracker.json generated yet",
)
def test_season_tracker_matches_schema():
    data = _load(WEBSITE_DATA / "season_tracker.json")
    SeasonTrackerData(**data)


@pytest.mark.skipif(
    not (WEBSITE_DATA / "standings.json").exists(),
    reason="No standings.json generated yet",
)
def test_standings_json_matches_schema():
    data = _load(WEBSITE_DATA / "standings.json")
    StandingsData(**data)


@pytest.mark.parametrize(
    "round_file",
    sorted((WEBSITE_DATA / "rounds").glob("round_*.json"))
    if (WEBSITE_DATA / "rounds").exists()
    else [],
    ids=lambda p: p.name,
)
def test_round_json_matches_schema(round_file: Path):
    data = _load(round_file)
    RoundData(**data)


def test_round_classification_has_unique_positions():
    rounds_dir = WEBSITE_DATA / "rounds"
    if not rounds_dir.exists():
        pytest.skip("No rounds/ generated yet")
    for round_file in rounds_dir.glob("round_*.json"):
        data = _load(round_file)
        positions = [c["position"] for c in data.get("classification", [])]
        assert len(positions) == len(set(positions)), (
            f"{round_file.name} has duplicate positions: {positions}"
        )


def test_round_classification_drivers_unique():
    rounds_dir = WEBSITE_DATA / "rounds"
    if not rounds_dir.exists():
        pytest.skip("No rounds/ generated yet")
    for round_file in rounds_dir.glob("round_*.json"):
        data = _load(round_file)
        drivers = [c["driver"] for c in data.get("classification", [])]
        assert len(drivers) == len(set(drivers)), (
            f"{round_file.name} has duplicate drivers: {drivers}"
        )


@pytest.mark.parametrize(
    "prob_file",
    sorted((WEBSITE_DATA / "probabilities").glob("round_*.json"))
    if (WEBSITE_DATA / "probabilities").exists()
    else [],
    ids=lambda p: p.name,
)
def test_probabilities_round_json_matches_schema(prob_file: Path):
    data = _load(prob_file)
    ProbabilityRoundData(**data)
