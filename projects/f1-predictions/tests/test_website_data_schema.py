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


class KeyFactor(_Loose):
    # Mirror of `KeyFactor` in website/src/types/index.ts.
    factor: str
    weight: float
    direction: str


class ClassificationEntry(_Loose):
    position: int
    driver: str
    team: str
    predictedTime: float
    points: int
    # Mirror of `ClassificationEntry.dnfProbability` in website/src/types/index.ts.
    dnfProbability: Optional[float] = None
    # Mirror of `ClassificationEntry.keyFactors` in website/src/types/index.ts.
    keyFactors: Optional[list[KeyFactor]] = None
    # Mirror of `ClassificationEntry.headshotUrl` in website/src/types/index.ts.
    headshotUrl: Optional[str] = None


class RoundData(_Loose):
    round: int
    name: str
    gpKey: str
    date: str
    sprint: bool
    classification: list[ClassificationEntry] = Field(default_factory=list)
    # How the prediction's grid was obtained (2026-07 freeze-correctness
    # overhaul). Optional: rounds published before the field exist without it.
    gridProvenance: Optional[str] = None


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


class WalkForwardMetric(_Loose):
    # Mirror of `WalkForwardMetric` in website/src/types/index.ts.
    mean: float
    median: float
    min: float
    max: float
    last: float
    trend: Optional[float] = None
    n: int


class WalkForwardBlock(_Loose):
    n_rounds: int
    metrics: dict[str, WalkForwardMetric]


class ForwardEvalWalkForward(_Loose):
    model: WalkForwardBlock
    baselines: dict[str, WalkForwardBlock]


class ForwardEvalSummaryData(_Loose):
    """Schema for `forward_eval/summary.json` (headline validation surface)."""

    season: int
    generatedAt: str
    roundsEvaluated: int
    walkForward: ForwardEvalWalkForward


class PositionModelABVerdict(_Loose):
    recommendation: str


class PositionModelABData(_Loose):
    """Schema for `forward_eval/position_model_ab.json`."""

    season: int
    minPriorRounds: int
    roundsScored: int
    roundsCompared: int
    rounds: list[dict]
    walkForward: dict
    verdict: PositionModelABVerdict


class PositionModelConfig(_Loose):
    # Mirror of `PositionModelConfig` in website/src/types/index.ts.
    applied: bool


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


@pytest.mark.skipif(
    not (WEBSITE_DATA / "forward_eval" / "summary.json").exists(),
    reason="No forward_eval/summary.json generated yet",
)
def test_forward_eval_summary_matches_schema():
    data = _load(WEBSITE_DATA / "forward_eval" / "summary.json")
    ForwardEvalSummaryData(**data)


@pytest.mark.skipif(
    not (WEBSITE_DATA / "forward_eval" / "position_model_ab.json").exists(),
    reason="No forward_eval/position_model_ab.json generated yet",
)
def test_position_model_ab_matches_schema():
    data = _load(WEBSITE_DATA / "forward_eval" / "position_model_ab.json")
    PositionModelABData(**data)


def test_round_position_model_config_when_present():
    """When a round carries modelConfig.positionModel, it must have `applied`."""
    rounds_dir = WEBSITE_DATA / "rounds"
    if not rounds_dir.exists():
        pytest.skip("No rounds/ generated yet")
    checked = 0
    for round_file in rounds_dir.glob("round_*.json"):
        data = _load(round_file)
        block = (data.get("modelConfig") or {}).get("positionModel")
        if not isinstance(block, dict):
            continue
        checked += 1
        PositionModelConfig(**block)
    if checked == 0:
        pytest.skip("No rounds carry modelConfig.positionModel yet")


def test_circuit_geometry_is_valid_when_present():
    """When `generate_circuit_svg.py` has populated geometry, the SVG path
    must be a closed loop. Rounds without geometry (cold-start) are skipped."""
    rounds_dir = WEBSITE_DATA / "rounds"
    if not rounds_dir.exists():
        pytest.skip("No rounds/ generated yet")
    checked = 0
    for round_file in rounds_dir.glob("round_*.json"):
        data = _load(round_file)
        geometry = (data.get("circuitInfo") or {}).get("geometry")
        if not isinstance(geometry, dict):
            continue
        checked += 1
        assert isinstance(geometry.get("path"), str), (
            f"{round_file.name}: geometry.path must be a string"
        )
        path = geometry["path"]
        assert path.startswith("M "), (
            f"{round_file.name}: geometry.path must start with `M ` (got {path[:8]!r})"
        )
        assert path.rstrip().endswith("Z"), (
            f"{round_file.name}: geometry.path must close with `Z`"
        )
        assert isinstance(geometry.get("viewBox"), str)
        assert isinstance(geometry.get("corners"), list)
        assert isinstance(geometry.get("drsZones"), list)
    if checked == 0:
        pytest.skip("No rounds have geometry yet (run generate_circuit_svg.py)")


@pytest.mark.parametrize(
    "prob_file",
    # Exclude *_candidate.json — the shadow stream from models/ranking_pipeline
    # has its own schema (kind: "ranker-candidate") and is not subject to the
    # legacy probability contract until the promotion gate accepts it live.
    [p for p in sorted((WEBSITE_DATA / "probabilities").glob("round_*.json"))
     if "_candidate" not in p.stem]
    if (WEBSITE_DATA / "probabilities").exists()
    else [],
    ids=lambda p: p.name,
)
def test_probabilities_round_json_matches_schema(prob_file: Path):
    data = _load(prob_file)
    ProbabilityRoundData(**data)


def test_grid_provenance_values_are_valid():
    """gridProvenance, when present, must be one of the three contract values."""
    rounds_dir = WEBSITE_DATA / "rounds"
    if not rounds_dir.exists():
        pytest.skip("No rounds/ generated yet")
    allowed = {"real-quali-verified", "estimated", "stale"}
    checked = 0
    for round_file in rounds_dir.glob("round_*.json"):
        data = _load(round_file)
        prov = data.get("gridProvenance")
        if prov is None:
            continue
        checked += 1
        assert prov in allowed, f"{round_file.name}: bad gridProvenance {prov!r}"
    if checked == 0:
        pytest.skip("No rounds carry gridProvenance yet")


def test_probability_markets_are_coherent():
    """No market's probabilities may exceed its set size (win 1, podium 3,
    top6 6, top10 10) beyond numerical tolerance — the audit found published
    win markets summing to 1.17-1.94."""
    probs_dir = WEBSITE_DATA / "probabilities"
    if not probs_dir.exists():
        pytest.skip("No probabilities/ generated yet")
    targets = {"win": 1.0, "podium": 3.0, "top6": 6.0, "top10": 10.0}
    checked = 0
    for prob_file in sorted(probs_dir.glob("round_*.json")):
        if "_candidate" in prob_file.stem:
            continue
        data = _load(prob_file)
        for market, target in targets.items():
            entries = (data.get("markets") or {}).get(market) or []
            if not entries:
                continue
            total = sum(float(e.get("probability", 0.0)) for e in entries)
            checked += 1
            assert total <= target * 1.02 + 1e-9, (
                f"{prob_file.name}: {market} sums to {total:.3f} > {target}"
            )
            for e in entries:
                assert -1e-9 <= float(e["probability"]) <= 1.0 + 1e-9, (
                    f"{prob_file.name}: {market} {e['driver']} probability out of [0,1]"
                )
    if checked == 0:
        pytest.skip("No probability markets generated yet")


class BaselineSeasonBlock(_Loose):
    roundsScored: int


class BaselineBlock(_Loose):
    label: str
    season: BaselineSeasonBlock
    perRound: dict[str, dict] = Field(default_factory=dict)


@pytest.mark.skipif(
    not (WEBSITE_DATA / "gp_accuracy_report.json").exists(),
    reason="No gp_accuracy_report.json generated yet",
)
def test_gp_accuracy_report_baselines_block():
    """The naive-baseline block (grid-order / pole-sitter / points-leader) is
    additive but, when present, must carry all three streams so the site can
    always render model-vs-baseline."""
    data = _load(WEBSITE_DATA / "gp_accuracy_report.json")
    baselines = data.get("baselines")
    if baselines is None:
        pytest.skip("gp_accuracy_report.json pre-dates the baselines block")
    for key in ("gridOrder", "poleSitter", "pointsLeader"):
        assert key in baselines, f"baselines missing {key!r}"
        BaselineBlock(**baselines[key])


@pytest.mark.parametrize(
    "candidate_file",
    sorted((WEBSITE_DATA / "probabilities").glob("round_*_candidate.json"))
    if (WEBSITE_DATA / "probabilities").exists()
    else [],
    ids=lambda p: p.name,
)
def test_ranker_candidate_json_has_expected_shape(candidate_file: Path):
    data = _load(candidate_file)
    assert data.get("kind") == "ranker-candidate", (
        f"{candidate_file.name}: expected kind='ranker-candidate', got {data.get('kind')!r}"
    )
    assert "predictions" in data and isinstance(data["predictions"], list)
    assert "metadata" in data and isinstance(data["metadata"], dict)
    positions = [p["position"] for p in data["predictions"]]
    assert positions == sorted(positions), (
        f"{candidate_file.name}: predictions must be sorted by position"
    )
    for entry in data["predictions"]:
        for field in ("position", "driver", "rankerScore",
                      "winProbability", "podiumProbability"):
            assert field in entry, f"{candidate_file.name}: missing {field!r}"
