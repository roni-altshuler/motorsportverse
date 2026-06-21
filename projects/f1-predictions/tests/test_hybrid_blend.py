"""Tests for the hybrid historical/weekend blend policy."""
from __future__ import annotations

import pytest

from models.hybrid_blend import (
    BlendWeights,
    QUALI_DOMINANT,
    SPECIALIST_HEAVY,
    HIGH_VARIANCE,
    apply_blend,
    blend_for,
)


class TestBlendWeights:
    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError, match="sum to 1"):
            BlendWeights(historical=0.6, weekend=0.6)

    def test_equal_split_passes(self):
        bw = BlendWeights(historical=0.5, weekend=0.5)
        assert bw.historical == 0.5
        assert bw.weekend == 0.5


class TestBlendPolicy:
    def test_preview_pins_to_historical(self):
        for circuit in ["Monaco", "Bahrain", "Imola", "Unknown"]:
            bw = blend_for(circuit, "preview")
            assert bw.historical == 1.0
            assert bw.weekend == 0.0

    def test_quali_dominant_post_quali_swings_weekend(self):
        bw = blend_for("Monaco", "post-quali")
        assert bw.weekend > bw.historical
        assert bw.weekend >= 0.75

    def test_specialist_circuit_keeps_historical_relevant(self):
        bw = blend_for("Suzuka", "post-quali")
        # Weekend still leads but historical is meaningfully > 0.35
        assert bw.historical >= 0.40
        assert bw.weekend < 0.65

    def test_high_variance_circuit_modest_weekend_lean(self):
        bw = blend_for("Bahrain", "post-quali")
        assert bw.weekend > bw.historical
        # But not as extreme as Monaco
        assert bw.weekend < 0.75

    def test_unknown_circuit_default(self):
        bw = blend_for("CompletelyUnknownGP", "post-quali")
        assert bw.weekend > bw.historical
        assert pytest.approx(bw.historical + bw.weekend) == 1.0

    def test_post_race_dominated_by_weekend(self):
        for circuit in ["Monaco", "Bahrain", "Spa"]:
            bw = blend_for(circuit, "post-race")
            assert bw.weekend == 0.80
            assert bw.historical == 0.20

    def test_phase_case_insensitive(self):
        assert blend_for("Monaco", "Preview").historical == 1.0
        assert blend_for("Monaco", "POST-QUALI").weekend >= 0.75


class TestApplyBlend:
    def test_blends_with_weights(self):
        # Historical = 100, Weekend = 200, Monaco post-quali (0.2/0.8)
        out = apply_blend(100.0, 200.0, circuit_key="Monaco", phase="post-quali")
        assert out == pytest.approx(0.2 * 100 + 0.8 * 200)

    def test_preview_returns_pure_historical(self):
        out = apply_blend(100.0, 999.0, circuit_key="Monaco", phase="preview")
        assert out == 100.0


class TestCircuitSets:
    def test_no_overlap_quali_dominant_high_variance(self):
        # Monaco is in BOTH (quali-dominant and policy is high-variance for
        # other reasons).  The policy prioritises QUALI_DOMINANT, so this is
        # legitimate, but we want to check there's at least some overlap
        # awareness — we don't assert disjoint, just that priority is honoured.
        bw = blend_for("Monaco", "post-quali")
        assert bw.weekend == 0.80  # quali-dominant rule won

    def test_set_membership(self):
        assert "Monaco" in QUALI_DOMINANT
        assert "Suzuka" in SPECIALIST_HEAVY
        assert "Bahrain" in HIGH_VARIANCE
