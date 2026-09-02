"""Data-contract gate: the JSON the pipeline emits must match the website types.

These pydantic models mirror the load-bearing fields the MotoGP website reads
(the F3/F1 golden-template contract, adapted to MotoGP terms). They are
deliberately *loose* (``extra="ignore"``) so adding an optional field on one side
doesn't break the build — but a renamed or dropped required field fails here. If
you change a shape in export.py / forward_eval.py, change the site's TS types AND
this mirror in the same commit.
"""
from __future__ import annotations

import json
import os

import pytest
from pydantic import BaseModel, ConfigDict

os.environ.setdefault("OMP_NUM_THREADS", "1")

from motogp_predictions import config, export, forward_eval


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("motogpdata")
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


class TitleOdds(_Loose):
    code: str
    pTitle: float
    currentPoints: float
    projMean: float
    maxAttainable: float
    canStillWin: bool


class MotoGPData(_Loose):
    sport: str
    season: int
    completedRounds: int
    totalRounds: int
    calendar: list[CalendarRound]
    driverStandings: list[DriverStanding]
    teamStandings: list[TeamStanding]
    championship: list[TitleOdds]
    nextPrediction: _Loose | None


class ClassificationEntry(_Loose):
    position: int
    code: str
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
    headshotUrl: str
    actualPosition: int | None


class RaceBlock(_Loose):
    raceType: str
    grid: list[_Loose]
    classification: list[ClassificationEntry]


class PositionModelConfig(_Loose):
    applied: bool


class RoundModelConfig(_Loose):
    gridProvenance: str
    positionModel: PositionModelConfig


class RoundDetail(_Loose):
    round: int
    venueKey: str
    venueName: str
    completed: bool
    dataSource: str | None
    modelConfig: RoundModelConfig
    sprint: RaceBlock
    feature: RaceBlock


class RaceProbabilities(_Loose):
    raceType: str
    markets: dict
    h2h: dict
    method: str
    monteCarloSamples: int
    temperature: float


class ProbabilitiesRound(_Loose):
    round: int
    calibration: _Loose
    sprint: RaceProbabilities
    feature: RaceProbabilities


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
    sprint: dict
    feature: dict
    markets: dict
    baselines: dict


class PhaseComparison(_Loose):
    roundsScored: int
    feature: dict
    beatsGridBaseline: bool


class ForwardEvalSeason(_Loose):
    season: int
    roundsScored: int
    winnerHitRate: float | None
    podiumHitRate: float | None
    walkForward: dict
    phaseComparison: PhaseComparison


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
    data = MotoGPData.model_validate(_load(data_dir / "motogp.json"))
    assert data.season == config.SEASON
    assert len(data.teamStandings) == len(config.MANUFACTURERS)


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
    # beatsGridBaseline is an EMPIRICAL outcome, not a contract. Assert only that
    # the flag is consistent with the Briers it summarises — never that the model
    # is winning. (WRC hard-asserted its equivalent and froze every cron publish
    # for two days when a round flipped it; see 967f4c4.)
    pc = season.phaseComparison
    win, pod = pc.feature["winBrier"], pc.feature["podiumBrier"]
    expected = bool(
        win.get("post") is not None
        and win.get("grid") is not None
        and win["post"] < win["grid"]
        and pod.get("post") is not None
        and pod.get("grid") is not None
        and pod["post"] < pod["grid"]
    )
    assert pc.beatsGridBaseline == expected
    rounds = sorted((data_dir / "forward_eval").glob("round_*.json"))
    assert len(rounds) == config.COMPLETED_ROUNDS
    for f in rounds:
        ForwardEvalRound.model_validate(_load(f))


def test_seasons_index_matches_contract(data_dir):
    idx = SeasonsIndex.model_validate(_load(data_dir / "seasons.json"))
    assert idx.current == config.SEASON
    assert config.SEASON in idx.available


def test_published_probabilities_sum_to_their_market(data_dir):
    """Every market must total the size of the set it describes.

    A win market is one slot, a podium three, a top-six six, a top-ten ten. The
    site renders `probability` straight as a percentage, so an incoherent market
    is visible to any reader who adds up a column.

    Note what the OTHER sum assertions in this file check: `rawProbability` —
    the empirical Monte-Carlo frequency, which is coherent by construction and
    was never the field that broke. The calibrated `probability` the page
    actually renders went unchecked, which is how win markets summing from 0.50
    to 2.00 shipped for a month. Assert on the number the reader sees.

    Delegates to motorsport_core.integrity so the rule has ONE definition; a
    second copy here would be the next thing to drift.
    """
    from motorsport_core.integrity import check_probabilities

    checked = 0
    failures = []
    for path in sorted((data_dir / "probabilities").glob("round_*.json")):
        payload = json.loads(path.read_text())
        for finding in check_probabilities(payload, path.name):
            if finding.check != "probability_mass":
                continue
            checked += 1
            if not finding.ok:
                failures.append(f"{path.name}: {finding.message}")
    assert not failures, "incoherent published markets:\n" + "\n".join(failures)
    assert checked > 0, "no markets were checked — the glob or the payload shape changed"
