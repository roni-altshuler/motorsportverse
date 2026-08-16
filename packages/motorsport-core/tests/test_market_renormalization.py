"""Tests for post-calibration market renormalisation.

Every test here is a regression test for a defect that shipped. The flagship
audited it on 2026-07-07 and fixed it locally; because the fix lived in the F1
project rather than in this package, F2, F3, Formula E, NASCAR and IndyCar all
published incoherent markets for months — win probabilities summing anywhere
from 0.50 to 2.00. The function now lives here so a fix reaches every series.
"""
from __future__ import annotations

import pytest

from motorsport_core.calibration import MARKET_TARGET_SUM, renormalize_market_struct


def _struct(market, values):
    return {market: {f"D{i}": {"probability": v, "rawProbability": v} for i, v in enumerate(values)}}


def _total(out, market):
    return sum(v["probability"] for v in out[market].values())


def test_an_inflated_win_market_is_restored_to_one():
    out = renormalize_market_struct(_struct("win", [0.8, 0.5, 0.3, 0.2]))
    assert _total(out, "win") == pytest.approx(1.0)


def test_a_deflated_win_market_is_restored_to_one():
    out = renormalize_market_struct(_struct("win", [0.2, 0.15, 0.1, 0.05]))
    assert _total(out, "win") == pytest.approx(1.0)


@pytest.mark.parametrize("market,target", sorted(MARKET_TARGET_SUM.items()))
def test_every_market_reaches_its_own_set_size(market, target):
    """Podium is three slots, top6 is six, top10 is ten. Not all one."""
    out = renormalize_market_struct(_struct(market, [0.9] * 20))
    assert _total(out, market) == pytest.approx(target)


def test_ordering_is_preserved():
    """Renormalisation may not reorder the field — it is a rescale, not a model."""
    out = renormalize_market_struct(_struct("win", [0.4, 0.3, 0.2, 0.1]))
    values = [v["probability"] for v in out["win"].values()]
    assert values == sorted(values, reverse=True)


def test_no_probability_exceeds_one():
    """Water-filling caps at certainty and redistributes, rather than scaling past it."""
    out = renormalize_market_struct(_struct("podium", [0.99, 0.98, 0.97, 0.02, 0.01]))
    assert all(v["probability"] <= 1.0 + 1e-9 for v in out["podium"].values())
    assert _total(out, "podium") == pytest.approx(3.0)


def test_raw_probabilities_are_never_touched():
    """The pre-calibration number stays auditable beside the published one."""
    struct = {"win": {"A": {"probability": 0.9, "rawProbability": 0.42}}}
    out = renormalize_market_struct(struct)
    assert out["win"]["A"]["rawProbability"] == 0.42


def test_already_coherent_probabilities_are_a_no_op():
    """Raw Plackett-Luce output is an empirical MC frequency and already sums right."""
    values = [0.5, 0.3, 0.2]
    out = renormalize_market_struct(_struct("win", values))
    assert [v["probability"] for v in out["win"].values()] == pytest.approx(values)


def test_a_market_with_no_fixed_set_size_passes_through():
    """`dnf` is not a top-N set; forcing a sum on it would invent a constraint."""
    out = renormalize_market_struct(_struct("dnf", [0.3, 0.4, 0.9]))
    assert _total(out, "dnf") == pytest.approx(1.6)


def test_a_field_smaller_than_the_market_is_not_inflated():
    """Six cars cannot occupy ten top-10 slots; the target clamps to the field."""
    out = renormalize_market_struct(_struct("top10", [0.5] * 6))
    assert _total(out, "top10") == pytest.approx(6.0)
    assert all(v["probability"] == pytest.approx(1.0) for v in out["top10"].values())


def test_an_all_zero_market_is_left_alone_rather_than_divided_by_zero():
    out = renormalize_market_struct(_struct("win", [0.0, 0.0]))
    assert _total(out, "win") == pytest.approx(0.0)


def test_an_empty_market_survives():
    assert renormalize_market_struct({"win": {}}) == {"win": {}}


def test_rounding_happens_after_the_water_fill():
    """Rounding first reintroduces exactly the drift this removes."""
    out = renormalize_market_struct(_struct("win", [0.8, 0.5, 0.3, 0.2]), digits=4)
    assert _total(out, "win") == pytest.approx(1.0, abs=5e-4)
    assert all(
        v["probability"] == round(v["probability"], 4) for v in out["win"].values()
    )


def test_negative_input_is_floored_not_propagated():
    out = renormalize_market_struct(_struct("win", [0.9, -0.2, 0.3]))
    assert all(v["probability"] >= 0 for v in out["win"].values())
    assert _total(out, "win") == pytest.approx(1.0)
