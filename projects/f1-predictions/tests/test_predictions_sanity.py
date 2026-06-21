"""Cheap sanity checks on the latest generated predictions.

These exist so a CI run that completes the export pipeline but produces
nonsense (all-NaN, all-identical, missing drivers) fails the build instead of
silently overwriting good data on GitHub Pages.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from tests.conftest import WEBSITE_DATA

ROUNDS_DIR = WEBSITE_DATA / "rounds"

EXPECTED_DRIVER_COUNT = 22  # 2026 grid
MIN_SANE_LAP_S = 60.0       # no F1 lap is sub-60s anywhere on the calendar
MAX_SANE_LAP_S = 130.0      # Monaco peaks ~ 75s, generous upper bound
MIN_SPREAD_S = 0.05         # if all predicted times are equal, model is dead


def _round_files() -> list[Path]:
    if not ROUNDS_DIR.exists():
        return []
    return sorted(ROUNDS_DIR.glob("round_*.json"))


@pytest.mark.parametrize("round_file", _round_files(), ids=lambda p: p.name)
def test_round_has_full_grid(round_file: Path):
    data = json.loads(round_file.read_text())
    classification = data.get("classification", [])
    assert len(classification) == EXPECTED_DRIVER_COUNT, (
        f"{round_file.name}: expected {EXPECTED_DRIVER_COUNT} drivers, "
        f"got {len(classification)}"
    )


@pytest.mark.parametrize("round_file", _round_files(), ids=lambda p: p.name)
def test_predicted_times_are_finite_and_in_range(round_file: Path):
    data = json.loads(round_file.read_text())
    times = [c["predictedTime"] for c in data.get("classification", [])]
    for t in times:
        assert isinstance(t, (int, float)), f"non-numeric time: {t!r}"
        assert math.isfinite(t), f"non-finite predicted time: {t!r}"
        assert MIN_SANE_LAP_S < t < MAX_SANE_LAP_S, (
            f"{round_file.name}: lap time {t} outside [{MIN_SANE_LAP_S}, "
            f"{MAX_SANE_LAP_S}] — model probably degenerate"
        )


@pytest.mark.parametrize("round_file", _round_files(), ids=lambda p: p.name)
def test_predicted_times_not_all_identical(round_file: Path):
    data = json.loads(round_file.read_text())
    times = [c["predictedTime"] for c in data.get("classification", [])]
    if not times:
        pytest.skip("no classification")
    spread = max(times) - min(times)
    assert spread >= MIN_SPREAD_S, (
        f"{round_file.name}: predicted-time spread {spread:.4f}s is degenerate "
        f"(model output is effectively constant)"
    )


@pytest.mark.parametrize("round_file", _round_files(), ids=lambda p: p.name)
def test_positions_are_one_through_n(round_file: Path):
    data = json.loads(round_file.read_text())
    positions = sorted(c["position"] for c in data.get("classification", []))
    expected = list(range(1, len(positions) + 1))
    assert positions == expected, (
        f"{round_file.name}: positions {positions} are not a "
        f"contiguous 1..N sequence"
    )


@pytest.mark.parametrize("round_file", _round_files(), ids=lambda p: p.name)
def test_win_probabilities_sum_to_about_100(round_file: Path):
    data = json.loads(round_file.read_text())
    probs = [
        c.get("winProbability")
        for c in data.get("classification", [])
        if c.get("winProbability") is not None
    ]
    if not probs:
        pytest.skip("winProbability not reported")
    total = sum(probs)
    assert 95.0 <= total <= 105.0, (
        f"{round_file.name}: winProbability sums to {total:.2f}, "
        f"expected ~100.0 (within ±5 for rounding)"
    )
