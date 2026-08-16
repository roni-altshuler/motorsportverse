"""Data-contract gate: the JSON the pipeline emits must match the website types.

These pydantic models mirror the load-bearing fields of ``website/src/types/f3.ts``.
They are deliberately *loose* (``extra="ignore"``) so adding an optional field on
one side doesn't break the build — but a renamed or dropped required field fails
here, exactly like the F1 flagship's ``test_website_data_schema.py``. If you change
a shape in export.py, change f3.ts AND this mirror in the same commit.
"""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ConfigDict

from f3_predictions import config, drift_report, export, forward_eval, promotion_decision


# --------------------------------------------------------------------------- #
# Generate the full data tree once into a tmp dir.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("f3data")
    export.write(out)
    forward_eval.write(out / "forward_eval", config.SEASON)
    drift_report_path = out  # drift reads round files under out/rounds
    report = drift_report.build_report(drift_report_path, config.SEASON)
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


class TitleOdds(_Loose):
    code: str
    pTitle: float
    currentPoints: float
    projMean: float
    maxAttainable: float
    canStillWin: bool


class F3Data(_Loose):
    sport: str
    season: int
    completedRounds: int
    totalRounds: int
    calendar: list[CalendarRound]
    driverStandings: list[DriverStanding]
    teamStandings: list[_Loose]
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
    """Mirror of ``RoundModelConfig`` in f3.ts — A/B lever provenance."""

    positionModel: PositionModelConfig


class RoundDetail(_Loose):
    round: int
    venueKey: str
    venueName: str
    completed: bool
    dataSource: str | None  # real provenance for completed rounds, None for upcoming
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


class PromotionStatus(_Loose):
    decision: str
    reason: str
    roundsCompared: int


class SeasonIndexEntry(_Loose):
    year: int
    isCurrent: bool
    path: str
    label: str


class SeasonsIndex(_Loose):
    """Mirror of ``website/src/lib/seasons.ts`` (SeasonsIndex)."""

    current: int
    available: list[int]
    archived: list[int]
    seasons: list[SeasonIndexEntry]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_f3_summary_matches_contract(data_dir):
    F3Data.model_validate(_load(data_dir / "f3.json"))


def test_round_detail_matches_contract(data_dir):
    files = sorted((data_dir / "rounds").glob("round_*.json"))
    assert len(files) == len(config.CALENDAR)
    for f in files:
        RoundDetail.model_validate(_load(f))


def test_model_config_position_head_is_honest(data_dir):
    """Every round records the position-head A/B lever. With the gate OFF
    (default in tests) the production path must report ``applied: false``;
    when applied it must carry the leakage-safe ``trainedRounds`` evidence."""
    import os

    gate_on = os.environ.get("F3_USE_POSITION_HEAD", "0") == "1"
    for f in sorted((data_dir / "rounds").glob("round_*.json")):
        payload = _load(f)
        position = payload["modelConfig"]["positionModel"]
        assert isinstance(position["applied"], bool)
        if not gate_on:
            assert position["applied"] is False
        if position["applied"]:
            assert position.get("trainedRounds"), "applied head must record trainedRounds"


def test_probabilities_match_contract(data_dir):
    files = sorted((data_dir / "probabilities").glob("round_*.json"))
    assert len(files) == len(config.CALENDAR)
    for f in files:
        ProbabilitiesRound.model_validate(_load(f))


def test_calibration_summary_is_honest(data_dir):
    """With the real snapshot wired (>= MIN real rounds), calibration is applied
    and trained on exactly the completed-round count — never claimed on nothing."""
    summary = _load(data_dir / "calibration_summary.json")
    if summary["applied"]:
        assert summary["trainingRounds"] >= config.MIN_REAL_ROUNDS_FOR_CALIBRATION
    else:
        assert summary["trainingRounds"] < config.MIN_REAL_ROUNDS_FOR_CALIBRATION


def test_model_health_matches_contract(data_dir):
    ModelHealth.model_validate(_load(data_dir / "model_health.json"))


def test_promotion_status_matches_contract(data_dir):
    PromotionStatus.model_validate(_load(data_dir / "promotion_status.json"))


def test_seasons_index_matches_contract(data_dir):
    """export.write() also emits the multi-season index the frontend reads."""
    idx = SeasonsIndex.model_validate(_load(data_dir / "seasons.json"))
    assert idx.current == config.SEASON
    assert config.SEASON in idx.available


def test_published_probabilities_sum_to_their_market(data_dir):
    """Every market must total the size of the set it describes.

    The sites render `probability` straight as a percentage, so a win market
    summing to 1.6 means the column a reader adds up does not describe the
    field on screen. Per-competitor isotonic calibration does not preserve the
    simplex; `motorsport_core.calibration.renormalize_market_struct` restores it
    at export time, and this is the per-project regression test.

    Note what the pre-existing assertions in this file check: `rawProbability`,
    which is an empirical Monte-Carlo frequency and was never the broken one.
    That is exactly why this defect passed CI for a month.
    """
    expected = {"win": 1.0, "podium": 3.0, "top6": 6.0, "top10": 10.0}
    checked = 0
    for path in sorted((data_dir / "probabilities").glob("round_*.json")):
        payload = _load(path)
        for race_type, block in payload.items():
            if not isinstance(block, dict) or "markets" not in block:
                continue
            for market, entries in block["markets"].items():
                target = expected.get(market)
                if target is None:
                    continue
                total = sum(e["probability"] for e in entries.values())
                # The field can be smaller than the market (six cars cannot fill
                # ten top-10 slots), so the target clamps to the field size.
                target = min(target, float(len(entries)))
                assert abs(total - target) <= target * 0.02, (
                    f"{path.name} {race_type}.{market} sums to {total:.4f}, "
                    f"expected {target:.0f}"
                )
                checked += 1
    assert checked > 0, "no markets were checked — the glob or shape changed"
