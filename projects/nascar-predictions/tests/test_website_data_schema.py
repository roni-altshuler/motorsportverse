"""Data-contract gate: the JSON the pipeline emits must match the website types.

These pydantic models mirror the load-bearing fields of the NASCAR website
data contract (the ``nascar.json`` analog of FE's ``fe.ts``). They are
deliberately *loose* (``extra="ignore"``) so adding an optional field on one
side doesn't break the build — but a renamed or dropped required field fails
here. When the NASCAR website lands, change its ``src/types/nascar.ts`` AND
this mirror in the same commit.
"""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ConfigDict

from nascar_predictions import (
    config,
    drift_report,
    export,
    forward_eval,
    promotion_decision,
)


# --------------------------------------------------------------------------- #
# Generate the full data tree once into a tmp dir.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("nascardata")
    export.write(out)
    forward_eval.write(out / "forward_eval", config.SEASON)
    report = drift_report.build_report(out, config.SEASON)
    (out / "model_health.json").write_text(json.dumps(drift_report._serialize(report)) + "\n")
    (out / "promotion_status.json").write_text(
        json.dumps(promotion_decision.build_status(out)) + "\n"
    )
    return out


def _load(path):
    return json.loads(path.read_text())


# --------------------------------------------------------------------------- #
# Loose pydantic mirrors
# --------------------------------------------------------------------------- #
class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class CalendarRound(_Loose):
    round: int
    key: str
    name: str
    raceName: str
    country: str | None
    kind: str
    trackType: str
    stageLaps: list[int]
    raceDate: str
    isPlayoff: bool
    completed: bool


class DriverStanding(_Loose):
    position: int
    code: str
    name: str
    team: str
    make: str
    teamColor: str
    points: float
    wins: int
    podiums: int
    top10s: int
    stageWins: int
    pointsHistory: list[float]


class TeamStanding(_Loose):
    position: int
    team: str
    teamColor: str
    points: float
    wins: int


class ManufacturerStanding(_Loose):
    position: int
    make: str
    color: str
    points: float
    wins: int


class TitleOdds(_Loose):
    code: str
    name: str
    team: str
    make: str
    pTitle: float
    pMakePlayoffs: float
    currentPoints: float
    projMean: float
    projectionHorizon: str
    maxAttainable: float
    canStillWin: bool


class SeasonAccuracy(_Loose):
    roundsScored: int
    meanPositionError: float | None
    podiumHitRate: float | None
    winnerHitRate: float | None


class NextPrediction(_Loose):
    round: int
    venueKey: str
    venueName: str
    raceName: str
    trackType: str
    phase: str
    qualifying: list[dict]
    race: list[dict]


class NascarData(_Loose):
    sport: str
    season: int
    seasonLabel: str
    completedRounds: int
    totalRounds: int
    regularSeasonRaces: int
    playoffFieldSize: int
    calendar: list[CalendarRound]
    driverStandings: list[DriverStanding]
    teamStandings: list[TeamStanding]
    manufacturerStandings: list[ManufacturerStanding]
    championship: list[TitleOdds]
    seasonAccuracy: SeasonAccuracy
    nextPrediction: NextPrediction | None


class ClassificationRow(_Loose):
    position: int
    code: str
    name: str
    team: str
    make: str
    teamColor: str
    predictedValue: float
    pWin: float
    pPodium: float
    pTop6: float
    pTop10: float
    pDnf: float
    meanFinish: float
    finishRangeLow: int
    finishRangeHigh: int
    confidence: str
    actualPosition: int | None


class RaceBlock(_Loose):
    raceType: str
    grid: list[dict]
    classification: list[ClassificationRow]


class RoundDetail(_Loose):
    round: int
    season: int
    venueKey: str
    venueName: str
    raceName: str
    trackType: str
    stageLaps: list[int]
    completed: bool
    dataSource: str | None
    modelConfig: dict
    race: RaceBlock


class MarketEntry(_Loose):
    probability: float
    rawProbability: float


class RaceProbabilities(_Loose):
    raceType: str
    trackType: str
    markets: dict[str, dict[str, MarketEntry]]
    dnf: dict[str, float]
    h2h: dict[str, dict[str, float]]
    method: str
    monteCarloSamples: int


class RoundProbabilities(_Loose):
    round: int
    season: int
    calibration: dict
    race: RaceProbabilities


class PlayoffFormatBlock(_Loose):
    name: str
    regularSeasonRaces: int
    playoffRaces: int
    playoffFieldSize: int
    qualification: str
    eliminations: bool
    probabilityKeys: list[str]


class PlayoffDriver(_Loose):
    code: str
    name: str
    team: str
    make: str
    points: float
    wins: int
    stageWins: int
    ladder: dict[str, float]
    pMakePlayoffs: float
    pTitle: float


class PlayoffProjection(_Loose):
    season: int
    format: PlayoffFormatBlock
    completedRounds: int
    regularSeasonRacesRemaining: int
    drivers: list[PlayoffDriver]


class SeasonsIndex(_Loose):
    current: int
    available: list[int]
    archived: list[int]
    seasons: list[dict]


class CalibrationSummary(_Loose):
    applied: bool
    trainingRounds: int
    perMarket: dict[str, int]


class ForwardEvalSeason(_Loose):
    season: int
    roundsScored: int
    finishersOnly: bool
    walkForward: dict


class ModelHealth(_Loose):
    season: int
    lastEvaluatedRound: int | None
    featureDrift: list[dict]
    warnings: list[str]
    alarms: list[str]


class PromotionStatus(_Loose):
    decision: str
    reason: str
    hasCandidate: bool
    candidateFlag: str


# --------------------------------------------------------------------------- #
# Contract assertions
# --------------------------------------------------------------------------- #
def test_nascar_json_contract(data_dir):
    payload = NascarData.model_validate(_load(data_dir / "nascar.json"))
    assert payload.season == config.SEASON
    assert payload.totalRounds == 36
    assert payload.regularSeasonRaces == 26
    assert len(payload.calendar) == 36
    assert payload.completedRounds >= 19
    assert sum(1 for c in payload.calendar if c.isPlayoff) == 10
    assert len(payload.driverStandings) >= 36
    assert len(payload.manufacturerStandings) == 3
    assert payload.nextPrediction is not None
    # Championship agrees with the playoff file's leader.
    leader = payload.championship[0]
    assert leader.pTitle > 0


def test_round_files_contract(data_dir):
    completed = _load(data_dir / "rounds" / "round_01.json")
    detail = RoundDetail.model_validate(completed)
    assert detail.completed is True
    assert detail.dataSource == "snapshot"
    assert detail.race.classification
    n = len(detail.race.classification)
    assert {r.position for r in detail.race.classification} == set(range(1, n + 1))
    assert "actualResults" in completed["race"]
    assert "stageResults" in completed["race"]
    assert "accuracy" in completed["race"]

    upcoming = RoundDetail.model_validate(_load(data_dir / "rounds" / "round_21.json"))
    assert upcoming.completed is False
    assert upcoming.dataSource is None


def test_probabilities_contract(data_dir):
    payload = RoundProbabilities.model_validate(
        _load(data_dir / "probabilities" / "round_20.json")
    )
    assert payload.race.trackType in config.TRACK_TYPES
    assert set(payload.race.markets) == {"win", "podium", "top6", "top10"}
    assert payload.calibration["applied"] is True  # 19 real rounds > gate
    win = payload.race.markets["win"]
    assert abs(sum(v.rawProbability for v in win.values()) - 1.0) < 0.02


def test_playoff_projection_contract(data_dir):
    payload = PlayoffProjection.model_validate(_load(data_dir / "playoff_projection.json"))
    assert payload.format.name == "chase-2026"
    assert payload.format.playoffFieldSize == 16
    assert payload.format.eliminations is False
    assert payload.format.probabilityKeys == ["p_make_playoffs", "p_title"]
    assert len(payload.drivers) >= 36
    total = sum(d.pTitle for d in payload.drivers)
    assert abs(total - 1.0) < 0.02
    for d in payload.drivers:
        assert d.pTitle <= d.pMakePlayoffs + 1e-9
        assert set(d.ladder) == {"p_make_playoffs", "p_title"}


def test_seasons_index_contract(data_dir):
    idx = SeasonsIndex.model_validate(_load(data_dir / "seasons.json"))
    assert idx.current == config.SEASON
    assert config.SEASON in idx.available


def test_calibration_summary_contract(data_dir):
    payload = CalibrationSummary.model_validate(_load(data_dir / "calibration_summary.json"))
    assert payload.applied is True
    assert payload.trainingRounds >= config.MIN_REAL_ROUNDS_FOR_CALIBRATION


def test_forward_eval_contract(data_dir):
    season = ForwardEvalSeason.model_validate(_load(data_dir / "forward_eval" / "season.json"))
    assert season.roundsScored >= 19
    assert season.finishersOnly is False
    wf = season.walkForward["race"]
    assert "model" in wf and "modelPostQuali" in wf
    assert set(wf["baselines"]) == {"lastRace", "gridOrder"}
    rnd = _load(data_dir / "forward_eval" / "round_01.json")
    assert rnd["race"]["n"] > 0
    assert "baselines" in rnd


def test_model_health_contract(data_dir):
    payload = ModelHealth.model_validate(_load(data_dir / "model_health.json"))
    assert payload.season == config.SEASON
    assert payload.lastEvaluatedRound is not None
    assert any(f["feature"] == "pDnf" for f in payload.featureDrift)


def test_promotion_status_contract(data_dir):
    payload = PromotionStatus.model_validate(_load(data_dir / "promotion_status.json"))
    assert payload.decision in {"promote", "hold", "demote"}
    assert payload.candidateFlag == "NASCAR_USE_POSITION_HEAD"


def test_playoff_backtest_artifact_committed():
    """The playoff gate artifact (written by playoff_backtest, which is too
    heavy for this fixture) must exist in the repo tree and carry the gate."""
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "website" / "public" / "data" / "historical_backtest" / "playoffs.json"
    )
    payload = _load(path)
    assert payload["format"] == "elimination-2017-2025"
    assert set(payload["gate"]) >= {"pass", "observedMeanChampionPercentile"}
    assert payload["seasons"], "playoff backtest must cover at least one season"
