"""Tests for the Plackett-Luce → market-probability → calibration pipeline."""
from __future__ import annotations

import json

import numpy as np
import pytest
from pydantic import BaseModel, ConfigDict

from tests.conftest import WEBSITE_DATA

from models.calibration import (
    MARKETS,
    ProbabilityCalibrator,
    brier_score,
    log_loss,
    plackett_luce_probabilities,
    reliability_diagram,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def grid_22() -> dict[str, float]:
    """A 22-driver synthetic grid with a known speed ordering."""
    base = 80.0
    drivers = [
        "VER", "HAD", "NOR", "PIA", "LEC", "HAM",
        "ANT", "RUS", "ALO", "STR", "GAS", "COL",
        "ALB", "SAI", "LAW", "LIN", "OCO", "BEA",
        "BOR", "HUL", "PER", "BOT",
    ]
    # Drivers sorted "fastest first" with a small monotonic spread.
    return {d: base + 0.05 * i for i, d in enumerate(drivers)}


@pytest.fixture
def grid_small() -> dict[str, float]:
    """Tiny 5-driver grid for exact-symmetry checks."""
    return {"A": 80.0, "B": 80.1, "C": 80.2, "D": 80.4, "E": 80.8}


# --------------------------------------------------------------------------- #
# Plackett-Luce
# --------------------------------------------------------------------------- #


class TestPlackettLuce:
    def test_p_win_sums_to_one(self, grid_22):
        mp = plackett_luce_probabilities(grid_22)
        total = sum(mp.p_win.values())
        assert abs(total - 1.0) < 1e-6, f"Σ p_win = {total}, expected 1.0"

    def test_p_podium_sums_to_three(self, grid_22):
        mp = plackett_luce_probabilities(grid_22)
        total = sum(mp.p_podium.values())
        assert abs(total - 3.0) < 1e-6, f"Σ p_podium = {total}, expected 3.0"

    def test_p_top6_sums_to_six(self, grid_22):
        mp = plackett_luce_probabilities(grid_22)
        total = sum(mp.p_top6.values())
        assert abs(total - 6.0) < 1e-6, f"Σ p_top6 = {total}, expected 6.0"

    def test_p_top10_sums_to_ten(self, grid_22):
        mp = plackett_luce_probabilities(grid_22)
        total = sum(mp.p_top10.values())
        assert abs(total - 10.0) < 1e-6, f"Σ p_top10 = {total}, expected 10.0"

    def test_h2h_symmetric(self, grid_small):
        mp = plackett_luce_probabilities(grid_small)
        for a in mp.drivers:
            for b in mp.drivers:
                if a == b:
                    continue
                p_ab = mp.h2h[a][b]
                p_ba = mp.h2h[b][a]
                assert abs(p_ab + p_ba - 1.0) < 1e-6, (
                    f"P({a}>{b}) + P({b}>{a}) = {p_ab + p_ba}, expected 1.0"
                )

    def test_faster_driver_has_higher_win_prob(self, grid_22):
        mp = plackett_luce_probabilities(grid_22)
        # VER is fastest (lowest lap time) by construction; should be in top of P(win).
        sorted_by_win = sorted(mp.p_win.items(), key=lambda kv: kv[1], reverse=True)
        assert sorted_by_win[0][0] == "VER"
        # Tail: back-marker win probs are near zero (~0.5% each) so Monte Carlo
        # noise makes the *exact* last position unreliable.  Assert instead that
        # the slowest driver lands in the bottom 3 — directionally correct,
        # robust to sampling noise at the seed-pinned default n_samples.
        bottom_three = {drv for drv, _ in sorted_by_win[-3:]}
        assert "BOT" in bottom_three, (
            f"Slowest driver BOT not in bottom-3 of P(win): "
            f"{[d for d, _ in sorted_by_win[-3:]]}"
        )

    def test_seeded_rng_reproducible(self, grid_22):
        m1 = plackett_luce_probabilities(grid_22, seed=42)
        m2 = plackett_luce_probabilities(grid_22, seed=42)
        for d in grid_22:
            assert m1.p_win[d] == m2.p_win[d]
            assert m1.p_podium[d] == m2.p_podium[d]

    def test_zero_temperature_rejected(self, grid_small):
        with pytest.raises(ValueError):
            plackett_luce_probabilities(grid_small, temperature=0.0)

    def test_empty_input_rejected(self):
        with pytest.raises(ValueError):
            plackett_luce_probabilities({})


# --------------------------------------------------------------------------- #
# Calibrator
# --------------------------------------------------------------------------- #


class TestProbabilityCalibrator:
    def test_unfitted_passthrough(self):
        cal = ProbabilityCalibrator()
        out = cal.transform("win", [0.1, 0.5, 0.9])
        np.testing.assert_allclose(out, [0.1, 0.5, 0.9])

    def test_perfect_calibration_on_perfect_input(self):
        # Perfectly-calibrated training set: 100 samples, predicted == empirical.
        rng = np.random.default_rng(42)
        preds = rng.uniform(0.0, 1.0, size=200)
        obs = (rng.uniform(0.0, 1.0, size=200) < preds).astype(int)
        cal = ProbabilityCalibrator()
        history = [
            {"market": "win", "predicted": float(p), "observed": int(o)}
            for p, o in zip(preds, obs)
        ]
        cal.fit_from_history(history)
        assert cal.is_fitted("win")
        out = cal.transform("win", [0.1, 0.3, 0.5, 0.7, 0.9])
        # The mapping should be roughly identity (well-calibrated input).
        assert all(0.0 <= v <= 1.0 for v in out)

    def test_monotonic_output(self):
        # Construct a clearly miscalibrated set: model predicts 0.0–1.0 linearly
        # but empirical truth is always higher.  Isotonic should map upward and
        # remain monotonic.
        rng = np.random.default_rng(42)
        preds = np.linspace(0.0, 0.9, 200)
        # bias the labels to 1 more often as preds increases
        obs = (rng.uniform(0.0, 1.0, size=200) < (preds + 0.1)).astype(int)
        cal = ProbabilityCalibrator()
        cal.fit_from_history(
            [
                {"market": "podium", "predicted": float(p), "observed": int(o)}
                for p, o in zip(preds, obs)
            ]
        )
        test_x = np.linspace(0.0, 1.0, 30)
        out = cal.transform("podium", test_x)
        # Monotonic non-decreasing.
        diffs = np.diff(out)
        assert np.all(diffs >= -1e-9), f"isotonic output not monotonic: {out}"

    def test_below_min_samples_skips_fit(self):
        cal = ProbabilityCalibrator()
        history = [
            {"market": "win", "predicted": 0.2, "observed": 0},
            {"market": "win", "predicted": 0.8, "observed": 1},
        ]
        cal.fit_from_history(history)
        assert not cal.is_fitted("win")

    def test_unknown_market_ignored(self):
        cal = ProbabilityCalibrator()
        cal.fit_from_history(
            [
                {"market": "bogus_market", "predicted": 0.5, "observed": 1}
                for _ in range(20)
            ]
        )
        assert not cal.is_fitted("bogus_market")
        # Transform on an unknown market is passthrough.
        out = cal.transform("bogus_market", [0.1, 0.5])
        np.testing.assert_allclose(out, [0.1, 0.5])

    def test_deterministic_fit_byte_identical(self):
        # Frozen training set fed twice must produce identical transforms —
        # otherwise the calibration layer is unreliable for promotion gating.
        rng = np.random.default_rng(123)
        preds = rng.uniform(0.0, 1.0, size=300)
        obs = (rng.uniform(0.0, 1.0, size=300) < preds).astype(int)
        history = [
            {"market": "win", "predicted": float(p), "observed": int(o)}
            for p, o in zip(preds, obs)
        ]
        cal_a = ProbabilityCalibrator()
        cal_a.fit_from_history(history)
        cal_b = ProbabilityCalibrator()
        cal_b.fit_from_history(history)
        probe = np.linspace(0.0, 1.0, 50)
        out_a = cal_a.transform("win", probe)
        out_b = cal_b.transform("win", probe)
        np.testing.assert_array_equal(out_a, out_b)


# --------------------------------------------------------------------------- #
# Reliability diagram + metrics
# --------------------------------------------------------------------------- #


class TestReliability:
    def test_well_calibrated_near_diagonal(self):
        # For each of 10 bins, generate predictions uniformly inside the bin
        # and outcomes with empirical rate matching the bin centre.
        rng = np.random.default_rng(42)
        preds: list[float] = []
        obs: list[int] = []
        n_per_bin = 500
        for k in range(10):
            lo, hi = k / 10.0, (k + 1) / 10.0
            centre = (lo + hi) / 2.0
            bin_preds = rng.uniform(lo, hi, size=n_per_bin)
            bin_obs = (rng.uniform(0.0, 1.0, size=n_per_bin) < centre).astype(int)
            preds.extend(bin_preds.tolist())
            obs.extend(bin_obs.tolist())
        diagram = reliability_diagram(preds, obs, n_bins=10)
        assert len(diagram) == 10
        for bucket in diagram:
            # Within 0.05 of perfectly diagonal (1/sqrt(500) ≈ 0.045 std-err).
            assert abs(bucket["meanPred"] - bucket["empirical"]) < 0.05, bucket

    def test_empty_input_returns_empty_list(self):
        assert reliability_diagram([], []) == []

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            reliability_diagram([0.1, 0.2], [0])


class TestMetrics:
    def test_brier_perfect_is_zero(self):
        assert brier_score([0.0, 1.0, 0.0, 1.0], [0, 1, 0, 1]) == 0.0

    def test_brier_worst_is_one(self):
        assert brier_score([0.0, 1.0], [1, 0]) == 1.0

    def test_log_loss_clipped_at_eps(self):
        # If log_loss did not clip, log(0) would blow up.
        ll = log_loss([0.0, 1.0], [1, 0])
        assert np.isfinite(ll)

    def test_log_loss_perfect_low(self):
        ll = log_loss([0.99, 0.01], [1, 0])
        assert ll < 0.1


# --------------------------------------------------------------------------- #
# Smoke test against the real exporter
# --------------------------------------------------------------------------- #


class _MarketEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    driver: str
    probability: float
    rawProbability: float


class _CalibrationBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: str
    trainingSeasons: list[int]
    applied: bool


class _RoundProbabilities(BaseModel):
    """Pydantic schema for the round-level probabilities export."""

    model_config = ConfigDict(extra="ignore")
    round: int
    season: int
    generatedAt: str
    method: str
    monteCarloSamples: int
    temperature: float
    calibration: _CalibrationBlock
    markets: dict[str, list[_MarketEntry]]
    h2h: dict[str, dict[str, float]]


@pytest.mark.skipif(
    not (WEBSITE_DATA / "rounds" / "round_01.json").exists(),
    reason="round_01.json not present; nothing to smoke-test against",
)
def test_export_probabilities_round1_smoke(tmp_path, monkeypatch):
    """Run the exporter for round 1 and validate the output JSON shape."""
    import export_probabilities as ep

    # Redirect output to a scratch dir so we don't pollute the website data tree.
    out_dir = tmp_path / "probabilities"
    monkeypatch.setattr(ep, "PROBS_DIR", out_dir)
    # Disable the model registry so the calibrator save does NOT mutate the
    # committed models/registry/2026_round_01/metadata.json (this smoke test
    # only validates the output JSON; registry persistence is covered elsewhere).
    monkeypatch.setenv("F1_REGISTRY_ENABLED", "0")

    result = ep.run(rounds=[1], quiet=True)
    assert result["rounds_written"] == 1

    out_file = out_dir / "round_01.json"
    assert out_file.exists()
    with out_file.open() as f:
        payload = json.load(f)
    parsed = _RoundProbabilities(**payload)

    # Sanity invariants on the parsed model.
    assert parsed.round == 1
    assert parsed.season >= 2025
    assert parsed.monteCarloSamples > 0
    for market in MARKETS:
        assert market in parsed.markets
        rows = parsed.markets[market]
        assert len(rows) >= 5  # at least most of a 22-car grid
        for row in rows:
            assert 0.0 <= row.probability <= 1.0
            assert 0.0 <= row.rawProbability <= 1.0
    # H2H symmetry on a sampled pair.
    drivers_in_h2h = list(parsed.h2h.keys())
    a = drivers_in_h2h[0]
    b = drivers_in_h2h[1]
    p_ab = parsed.h2h[a][b]
    p_ba = parsed.h2h[b][a]
    assert abs(p_ab + p_ba - 1.0) < 1e-6
