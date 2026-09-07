"""Data-contract gate: the JSON the pipeline emits must match the website types.

These pydantic models mirror the load-bearing fields of the IndyCar website
data contract (the ``indycar.json`` analog of FE's ``fe.ts``). They are
deliberately *loose* (``extra="ignore"``) so adding an optional field on one
side doesn't break the build — but a renamed or dropped required field fails
here. When the IndyCar website lands, change its ``src/types/indycar.ts`` AND
this mirror in the same commit.
"""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ConfigDict

from indycar_predictions import (
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
    out = tmp_path_factory.mktemp("indycardata")
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
    trackGroup: str
    isIndy500: bool
    raceDate: str
    completed: bool


class DriverStanding(_Loose):
    position: int
    code: str
    name: str
    team: str
    engine: str
    teamColor: str
    points: float
    wins: int
    podiums: int
    top10s: int
    pointsHistory: list[float]


class TeamStanding(_Loose):
    position: int
    team: str
    teamColor: str
    points: float
    wins: int


class EngineStanding(_Loose):
    position: int
    engine: str
    color: str
    points: float
    wins: int


class TitleOdds(_Loose):
    code: str
    name: str
    team: str
    engine: str
    pTitle: float
    currentPoints: float
    projMean: float
    projP10: float
    projP90: float
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
    trackGroup: str
    phase: str
    qualifyingActual: bool
    qualifying: list[dict]
    race: list[dict]


class IndycarData(_Loose):
    sport: str
    season: int
    seasonLabel: str
    completedRounds: int
    totalRounds: int
    trackTypeCounts: dict[str, int]
    calendar: list[CalendarRound]
    driverStandings: list[DriverStanding]
    teamStandings: list[TeamStanding]
    engineStandings: list[EngineStanding]
    championship: list[TitleOdds]
    seasonAccuracy: SeasonAccuracy
    nextPrediction: NextPrediction | None


class ClassificationRow(_Loose):
    position: int
    code: str
    name: str
    team: str
    engine: str
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
    trackGroup: str
    isIndy500: bool
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
    trackGroup: str
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
def test_indycar_json_contract(data_dir):
    payload = IndycarData.model_validate(_load(data_dir / "indycar.json"))
    assert payload.season == config.SEASON
    assert payload.totalRounds == len(config.CALENDAR)
    assert len(payload.calendar) == len(config.CALENDAR)
    # Consistency with the committed snapshot (the same source config derives
    # from), never a season-progress literal — literals freeze the cron the
    # moment a season boundary moves them (WRC lesson, 967f4c4).
    assert payload.completedRounds == config.COMPLETED_ROUNDS
    # The oval / road / street split is first-class on every surface.
    assert set(payload.trackTypeCounts) == set(config.TRACK_TYPES)
    assert sum(payload.trackTypeCounts.values()) == len(config.CALENDAR)
    assert sum(1 for c in payload.calendar if c.isIndy500) == len(config.INDY500_ROUNDS)
    assert all(c.trackGroup in config.ELO_TRACK_GROUPS for c in payload.calendar)
    assert len(payload.driverStandings) >= 25
    assert len(payload.engineStandings) == 2  # Chevrolet + Honda
    # The export honestly emits None once the finale's result is in — assert
    # whichever state the calendar implies rather than freezing on season end.
    if config.COMPLETED_ROUNDS < len(config.CALENDAR):
        assert payload.nextPrediction is not None
    else:
        assert payload.nextPrediction is None
    assert payload.championship[0].pTitle > 0


def test_round_files_contract(data_dir):
    if config.COMPLETED_ROUNDS == 0:
        pytest.skip("new season — no completed round committed yet")
    completed = _load(data_dir / "rounds" / "round_01.json")
    detail = RoundDetail.model_validate(completed)
    assert detail.completed is True
    assert detail.dataSource == "snapshot"
    assert detail.race.classification
    n = len(detail.race.classification)
    assert {r.position for r in detail.race.classification} == set(range(1, n + 1))
    assert "actualResults" in completed["race"]
    assert "accuracy" in completed["race"]

    # The 500 carries the traditional 33-car field, one-off entries included.
    # Round number is derived from config (not a literal) and the 33-car board
    # is only asserted once the race has actually run this season.
    if config.INDY500_ROUNDS:
        indy_round = config.INDY500_ROUNDS[0]
        indy500 = RoundDetail.model_validate(
            _load(data_dir / "rounds" / f"round_{indy_round:02d}.json")
        )
        assert indy500.isIndy500 is True
        if config.COMPLETED_ROUNDS >= indy_round:
            assert len(indy500.race.classification) == 33

    # The first round the committed snapshot does not yet carry.  Derived, never
    # hardcoded: a literal upcoming round starts failing the moment that round's
    # result lands — and because bot commits don't trigger CI, it surfaces inside
    # the cron's own "Validate generated outputs" gate (F3 golden-template rule).
    next_round = config.COMPLETED_ROUNDS + 1
    if next_round > len(config.CALENDAR):
        pytest.skip("season complete — no upcoming round to assert")
    upcoming = RoundDetail.model_validate(
        _load(data_dir / "rounds" / f"round_{next_round:02d}.json")
    )
    assert upcoming.completed is False
    assert upcoming.dataSource is None
    # Venue-agnostic: the upcoming circuit changes as the season advances, so
    # assert the group is populated and valid rather than naming one track.
    assert upcoming.trackGroup in config.ELO_TRACK_GROUPS


def test_probabilities_contract(data_dir):
    # The next unraced round while the season runs, else the finale — derived
    # so the file exists at every season stage (a literal starts failing the
    # moment the season advances past it).
    rnd = min(config.COMPLETED_ROUNDS + 1, len(config.CALENDAR))
    payload = RoundProbabilities.model_validate(
        _load(data_dir / "probabilities" / f"round_{rnd:02d}.json")
    )
    assert payload.race.trackType in config.TRACK_TYPES
    assert set(payload.race.markets) == {"win", "podium", "top6", "top10"}
    # Consistency, not season state: the round file's calibration flag must
    # agree with the published summary (both written by the same export pass).
    summary = _load(data_dir / "calibration_summary.json")
    assert payload.calibration["applied"] == summary["applied"]
    win = payload.race.markets["win"]
    assert abs(sum(v.rawProbability for v in win.values()) - 1.0) < 0.02


def test_seasons_index_contract(data_dir):
    idx = SeasonsIndex.model_validate(_load(data_dir / "seasons.json"))
    assert idx.current == config.SEASON
    assert config.SEASON in idx.available


def test_calibration_summary_contract(data_dir):
    payload = CalibrationSummary.model_validate(_load(data_dir / "calibration_summary.json"))
    # One-directional honesty contract: calibration may never be CLAIMED
    # without enough real rounds. Whether it is applied yet is season state —
    # early-season False must not fail the cron.
    if payload.applied:
        assert payload.trainingRounds >= config.MIN_REAL_ROUNDS_FOR_CALIBRATION


def test_forward_eval_contract(data_dir):
    season = ForwardEvalSeason.model_validate(_load(data_dir / "forward_eval" / "season.json"))
    # Every completed round is scoreable (snapshot-primary: results and
    # predictions come from the same committed history) — assert agreement
    # with config, which derives from that same snapshot.
    assert season.roundsScored == config.COMPLETED_ROUNDS
    assert season.finishersOnly is False  # IndyCar classifies every car
    wf = season.walkForward["race"]
    assert "model" in wf and "modelPostQuali" in wf
    assert set(wf["baselines"]) == {"lastRace", "gridOrder"}
    if season.roundsScored == 0:
        return  # new season — no scored round files to spot-check yet
    rnd = _load(data_dir / "forward_eval" / "round_01.json")
    assert rnd["race"]["n"] > 0
    assert "baselines" in rnd
    # Round 1 has no previous round — the lastRace baseline must be an honest None.
    assert rnd["baselines"]["lastRace"] is None


def test_model_health_contract(data_dir):
    payload = ModelHealth.model_validate(_load(data_dir / "model_health.json"))
    assert payload.season == config.SEASON
    if config.COMPLETED_ROUNDS:
        assert payload.lastEvaluatedRound is not None
        assert any(f["feature"] == "pDnf" for f in payload.featureDrift)


def test_promotion_status_contract(data_dir):
    payload = PromotionStatus.model_validate(_load(data_dir / "promotion_status.json"))
    assert payload.decision in {"promote", "hold", "demote"}
    assert payload.candidateFlag == "INDYCAR_USE_POSITION_HEAD"


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
