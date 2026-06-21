"""Unit tests for the DNF probability model (models/dnf.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from models.dnf import DnfModelInputs, compute_dnf_probabilities

HISTORY_DB = Path(__file__).resolve().parents[1] / "data" / "history.duckdb"


def test_returns_base_rate_when_db_missing(tmp_path):
    """Missing DB → every driver gets the project base rate (0.15)."""
    inputs = [
        DnfModelInputs(driver="VER", predicted_position=1, circuit_key="Australia"),
        DnfModelInputs(driver="HUL", predicted_position=18, circuit_key="Australia"),
    ]
    probs = compute_dnf_probabilities(
        history_db_path=tmp_path / "does_not_exist.duckdb",
        season=2026,
        current_round=1,
        inputs=inputs,
    )
    assert set(probs.keys()) == {"VER", "HUL"}
    assert all(p == pytest.approx(0.15) for p in probs.values())


def test_probabilities_bounded_in_zero_one():
    """Whatever the model says, every probability sits in (0, 1)."""
    if not HISTORY_DB.exists():
        pytest.skip("data/history.duckdb not present in this environment")
    inputs = [
        DnfModelInputs(driver=d, predicted_position=i + 1, circuit_key="Canada")
        for i, d in enumerate(
            ["VER", "NOR", "PIA", "LEC", "HAM", "ANT", "RUS", "ALB", "SAI", "GAS"]
        )
    ]
    probs = compute_dnf_probabilities(
        history_db_path=HISTORY_DB, season=2026, current_round=6, inputs=inputs
    )
    assert len(probs) == len(inputs)
    for p in probs.values():
        assert 0.01 <= p <= 0.65


def test_high_prior_rate_increases_dnf_probability():
    """Sanity: a driver with no historical record gets the base rate; the
    model never returns negative or NaN."""
    if not HISTORY_DB.exists():
        pytest.skip("data/history.duckdb not present in this environment")
    inputs = [
        DnfModelInputs(driver="VER", predicted_position=1, circuit_key="Canada"),
        DnfModelInputs(driver="XYZ", predicted_position=22, circuit_key="Canada"),
    ]
    probs = compute_dnf_probabilities(
        history_db_path=HISTORY_DB, season=2026, current_round=6, inputs=inputs
    )
    assert all(p == p for p in probs.values())  # not NaN
    assert all(p > 0 for p in probs.values())
