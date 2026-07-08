"""Data-contract gate: the JSON the pipeline emits must match the website types.

These pydantic models mirror the load-bearing fields of the FE website data
contract (the ``fe.json`` analog of F2/F3's ``f2.ts``/``f3.ts``). They are
deliberately *loose* (``extra="ignore"``) so adding an optional field on one
side doesn't break the build — but a renamed or dropped required field fails
here. When the FE website lands, change its ``src/types/fe.ts`` AND this
mirror in the same commit.
"""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ConfigDict

from formula_e_predictions import (
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
    out = tmp_path_factory.mktemp("fedata")
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
    country: str | None
    kind: str
    city: str
    raceDate: str
    completed: bool


class DriverStanding(_Loose):
    position: int
    code: str
    name: str
    team: str
    teamColor: str
    points: float
    wins: int
    podiums: int
    pointsHistory: list[float]


class TeamStanding(_Loose):
    position: int
    team: str
    teamColor: str
    points: float
    pointsHistory: list[float]


class TitleOdds(_Loose):
    code: str
    name: str
    pTitle: float
    currentPoints: float
    projMean: float
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
    phase: str
    qualifying: list[dict]
    race: list[dict]


class FEData(_Loose):
    sport: str
    season: int
    seasonLabel: str
    completedRounds: int
    totalRounds: int
    calendar: list[CalendarRound]
    driverStandings: list[DriverStanding]
    teamStandings: list[TeamStanding]
    championship: list[TitleOdds]
    seasonAccuracy: SeasonAccuracy
    nextPrediction: NextPrediction | None


class ClassificationRow(_Loose):
    position: int
    code: str
    name: str
    team: str
    teamColor: str
    predictedValue: float
    pWin: float
    pPodium: float
    pTop6: float
    pTop10: float
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
    venueKind: str
    completed: bool
    dataSource: str | None
    modelConfig: dict
    race: RaceBlock


class MarketEntry(_Loose):
    probability: float
    rawProbability: float


class RaceProbabilities(_Loose):
    raceType: str
    venueKind: str
    markets: dict[str, dict[str, MarketEntry]]
    h2h: dict[str, dict[str, float]]
    method: str
    monteCarloSamples: int


class RoundProbabilities(_Loose):
    round: int
    season: int
    calibration: dict
    race: RaceProbabilities


class CalibrationSummary(_Loose):
    applied: bool
    trainingRounds: int
    strata: dict[str, list[str]]
    perMarket: dict[str, int]


class ForwardEvalRound(_Loose):
    round: int
    venueName: str
    venueKind: str
    race: dict
    markets: dict
    baselines: dict


class ForwardEvalSeason(_Loose):
    season: int
    roundsScored: int
    meanPositionError: float | None
    winnerHitRate: float | None
    podiumHitRate: float | None
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


class SeasonsIndex(_Loose):
    current: int
    available: list[int]
    archived: list[int]
    seasons: list[dict]


# --------------------------------------------------------------------------- #
# Assertions
# --------------------------------------------------------------------------- #
def test_fe_json_contract(data_dir):
    data = FEData.model_validate(_load(data_dir / "fe.json"))
    assert data.sport == "Formula E"
    assert data.season == config.SEASON
    assert data.totalRounds == 17
    assert len(data.calendar) == 17
    assert len(data.driverStandings) == 20
    assert len(data.teamStandings) == 10
    assert data.completedRounds >= 13
    assert data.seasonAccuracy.roundsScored == data.completedRounds
    # Completed rounds are real (snapshot/pulselive), never synthetic.
    for c in data.calendar:
        if c.completed:
            raw = _load(data_dir / "rounds" / f"round_{c.round:02d}.json")
            assert raw["dataSource"] in ("snapshot", "pulselive")


def test_round_files_contract(data_dir):
    for rnd in range(1, 18):
        detail = RoundDetail.model_validate(
            _load(data_dir / "rounds" / f"round_{rnd:02d}.json")
        )
        assert detail.round == rnd
        assert detail.venueKind in ("street", "circuit")
        assert len(detail.race.classification) == 20
        assert len(detail.race.grid) == 20
        assert detail.modelConfig["positionModel"]["applied"] is False
        if detail.completed:
            actuals = [
                r.actualPosition
                for r in detail.race.classification
                if r.actualPosition is not None
            ]
            assert len(actuals) >= 10


def test_probability_files_contract(data_dir):
    for rnd in range(1, 18):
        probs = RoundProbabilities.model_validate(
            _load(data_dir / "probabilities" / f"round_{rnd:02d}.json")
        )
        assert probs.round == rnd
        assert set(probs.race.markets) == {"win", "podium", "top6", "top10"}
        win = probs.race.markets["win"]
        assert len(win) == 20
        total = sum(v.rawProbability for v in win.values())
        assert abs(total - 1.0) < 0.05


def test_calibration_summary_contract(data_dir):
    summary = CalibrationSummary.model_validate(_load(data_dir / "calibration_summary.json"))
    assert summary.applied is True  # 13 real rounds >> the 4-round gate
    assert summary.trainingRounds >= config.MIN_REAL_ROUNDS_FOR_CALIBRATION


def test_forward_eval_contract(data_dir):
    season = ForwardEvalSeason.model_validate(_load(data_dir / "forward_eval" / "season.json"))
    assert season.roundsScored >= 13
    assert season.finishersOnly is True
    block = season.walkForward["race"]
    assert "model" in block and "baselines" in block
    assert set(block["baselines"]) == {"lastRace", "gridOrder"}
    for rnd in range(1, season.roundsScored + 1):
        fer = ForwardEvalRound.model_validate(
            _load(data_dir / "forward_eval" / f"round_{rnd:02d}.json")
        )
        assert set(fer.baselines) == {"lastRace", "gridOrder"}
        # The grid-order baseline exists for every real completed round.
        assert fer.baselines["gridOrder"] is not None


def test_model_health_contract(data_dir):
    ModelHealth.model_validate(_load(data_dir / "model_health.json"))


def test_promotion_status_contract(data_dir):
    status = PromotionStatus.model_validate(_load(data_dir / "promotion_status.json"))
    assert status.decision in ("promote", "hold", "demote")
    assert status.candidateFlag == "FE_USE_POSITION_HEAD"


def test_seasons_index_contract(data_dir):
    index = SeasonsIndex.model_validate(_load(data_dir / "seasons.json"))
    assert index.current == config.SEASON
    assert config.SEASON in index.available
    labels = {s["year"]: s["label"] for s in index.seasons}
    assert labels[config.SEASON] == f"{config.SEASON - 1}-{str(config.SEASON)[2:]}"
