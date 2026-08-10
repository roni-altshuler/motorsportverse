"""Data-contract gate: the JSON the pipeline emits must match the website types.

These pydantic models mirror the load-bearing fields the WRC website reads (the
MotoGP golden-template contract, adapted to rally: one classification per round, the
surface variable, and a manufacturers championship taken directly from the
snapshot). They are deliberately *loose* (``extra="ignore"``) so adding an optional
field on one side doesn't break the build — but a renamed or dropped required field
fails here. If you change a shape in export.py / forward_eval.py, change the site's
TS types AND this mirror in the same commit.
"""
from __future__ import annotations

import json
import os

import pytest
from pydantic import BaseModel, ConfigDict

os.environ.setdefault("OMP_NUM_THREADS", "1")

from wrc_predictions import config, export, forward_eval


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("wrcdata")
    export.write(out)
    forward_eval.write(out, config.SEASON)
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
    country: str | None
    surface: str
    surfaceColor: str
    completed: bool


class DriverStanding(_Loose):
    position: int
    code: str
    name: str
    nationality: str | None
    team: str
    teamColor: str
    points: float
    wins: int
    podiums: int
    pointsHistory: list[float]


class ManufacturerStanding(_Loose):
    position: int
    team: str
    teamColor: str
    points: float


class TitleOdds(_Loose):
    code: str
    pTitle: float
    currentPoints: float
    projMean: float
    maxAttainable: float
    canStillWin: bool


class WrcData(_Loose):
    sport: str
    season: int
    completedRounds: int
    totalRounds: int
    calendar: list[CalendarRound]
    driverStandings: list[DriverStanding]
    manufacturerStandings: list[ManufacturerStanding]
    championship: list[TitleOdds]
    seasonAccuracy: _Loose
    nextPrediction: _Loose | None


class ClassificationEntry(_Loose):
    position: int
    code: str
    nationality: str | None
    team: str
    teamColor: str
    predictedValue: float
    pWin: float
    pPodium: float
    pTop6: float
    pTop10: float
    finishRangeLow: int
    finishRangeHigh: int
    confidence: str
    actualPosition: int | None


class RallyBlock(_Loose):
    surface: str
    surfaceColor: str
    classification: list[ClassificationEntry]


class EnsembleConfig(_Loose):
    applied: bool
    modelWeight: float


class RoundModelConfig(_Loose):
    ensemble: EnsembleConfig
    surface: str


class RoundDetail(_Loose):
    round: int
    venueKey: str
    venueName: str
    country: str | None
    surface: str
    surfaceColor: str
    completed: bool
    dataSource: str | None
    modelConfig: RoundModelConfig
    rally: RallyBlock


class RallyProbabilities(_Loose):
    surface: str
    markets: dict
    h2h: dict
    method: str
    monteCarloSamples: int
    temperature: float


class ProbabilitiesRound(_Loose):
    round: int
    surface: str
    calibration: _Loose
    rally: RallyProbabilities


class ModelHealth(_Loose):
    season: int
    lastEvaluatedRound: int | None
    featureDrift: list
    warnings: list
    alarms: list
    brierByRound: list
    forwardEval: _Loose


class ForwardEvalRound(_Loose):
    round: int
    venueName: str
    surface: str
    rally: dict
    markets: dict
    baselines: dict


class BaselineComparison(_Loose):
    roundsScored: int
    winBrier: dict
    podiumBrier: dict
    beatsStandingsBaseline: bool


class ForwardEvalSeason(_Loose):
    season: int
    roundsScored: int
    winnerHitRate: float | None
    podiumHitRate: float | None
    walkForward: dict
    baselineComparison: BaselineComparison


class SeasonIndexEntry(_Loose):
    year: int
    isCurrent: bool
    path: str
    label: str


class SeasonsIndex(_Loose):
    current: int
    available: list[int]
    archived: list[int]
    seasons: list[SeasonIndexEntry]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_summary_matches_contract(data_dir):
    data = WrcData.model_validate(_load(data_dir / "wrc.json"))
    assert data.season == config.SEASON
    assert len(data.manufacturerStandings) >= 1


def test_round_detail_matches_contract(data_dir):
    files = sorted((data_dir / "rounds").glob("round_*.json"))
    assert len(files) == len(config.CALENDAR)
    for f in files:
        RoundDetail.model_validate(_load(f))


def test_probabilities_match_contract(data_dir):
    files = sorted((data_dir / "probabilities").glob("round_*.json"))
    assert len(files) == len(config.CALENDAR)
    for f in files:
        ProbabilitiesRound.model_validate(_load(f))


def test_calibration_summary_is_honest(data_dir):
    summary = _load(data_dir / "calibration_summary.json")
    if summary["applied"]:
        assert summary["trainingRounds"] >= config.MIN_REAL_ROUNDS_FOR_CALIBRATION
    else:
        assert summary["trainingRounds"] < config.MIN_REAL_ROUNDS_FOR_CALIBRATION


def test_model_health_matches_contract(data_dir):
    ModelHealth.model_validate(_load(data_dir / "model_health.json"))


def test_forward_eval_matches_contract(data_dir):
    season = ForwardEvalSeason.model_validate(_load(data_dir / "forward_eval" / "season.json"))
    # The validated headline: the ensemble beats the standings-order baseline.
    assert season.baselineComparison.beatsStandingsBaseline is True
    rounds = sorted((data_dir / "forward_eval").glob("round_*.json"))
    assert len(rounds) == config.COMPLETED_ROUNDS
    for f in rounds:
        ForwardEvalRound.model_validate(_load(f))


def test_seasons_index_matches_contract(data_dir):
    idx = SeasonsIndex.model_validate(_load(data_dir / "seasons.json"))
    assert idx.current == config.SEASON
    assert config.SEASON in idx.available
