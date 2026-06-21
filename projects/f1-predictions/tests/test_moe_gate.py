"""Tests for the learned mixture-of-experts gate + combine helpers."""
from __future__ import annotations

import numpy as np
import pytest

from models.moe_combine import fuse_with_gate
from models.moe_gate import (
    DEFAULT_EXPERT_NAMES,
    DEFAULT_FEATURE_NAMES,
    LearnedGate,
    TrainingExample,
    build_gate_features,
)


# --------------------------------------------------------------------------- #
# fuse_with_gate
# --------------------------------------------------------------------------- #


def test_fuse_with_gate_uniform_weights_averages_experts() -> None:
    K = 3
    pw = np.array(
        [
            [0.50, 0.30, 0.15, 0.05],
            [0.40, 0.25, 0.20, 0.15],
            [0.30, 0.30, 0.25, 0.15],
        ]
    )
    pp = pw + 0.05
    w = np.ones(K) / K
    fused_win, fused_pod = fuse_with_gate(pw, pp, w)
    np.testing.assert_allclose(fused_win, pw.mean(axis=0), atol=1e-12)
    np.testing.assert_allclose(fused_pod, pp.mean(axis=0), atol=1e-12)


def test_fuse_with_gate_one_hot_weight_picks_expert() -> None:
    pw = np.array(
        [
            [0.50, 0.30, 0.15, 0.05],
            [0.40, 0.25, 0.20, 0.15],
            [0.30, 0.30, 0.25, 0.15],
        ]
    )
    pp = pw + 0.05
    w = np.array([0.0, 1.0, 0.0])
    fused_win, fused_pod = fuse_with_gate(pw, pp, w)
    np.testing.assert_allclose(fused_win, pw[1], atol=1e-12)
    np.testing.assert_allclose(fused_pod, pp[1], atol=1e-12)


def test_fuse_with_gate_shape_mismatch_raises() -> None:
    pw = np.zeros((3, 4))
    pp = np.zeros((3, 4))
    w = np.ones(2) / 2
    with pytest.raises(ValueError):
        fuse_with_gate(pw, pp, w)


# --------------------------------------------------------------------------- #
# build_gate_features
# --------------------------------------------------------------------------- #


def test_features_length_matches_default_names() -> None:
    x = build_gate_features(
        round_index=10,
        volatility=0.5,
        mean_maturity=0.7,
        qualifying_dispersion=0.01,
        archetype_qualifying_importance=0.8,
    )
    assert x.shape == (len(DEFAULT_FEATURE_NAMES),)


def test_features_normalize_round() -> None:
    x = build_gate_features(
        round_index=12,
        volatility=0.5,
        mean_maturity=0.5,
        qualifying_dispersion=0.01,
        archetype_qualifying_importance=0.5,
        max_round=24,
    )
    # round_normalized should be first
    assert abs(x[0] - 0.5) < 1e-12


def test_features_clip_volatility() -> None:
    x = build_gate_features(
        round_index=1,
        volatility=2.0,
        mean_maturity=0.0,
        qualifying_dispersion=0.0,
        archetype_qualifying_importance=0.0,
    )
    assert x[2] == 1.0


# --------------------------------------------------------------------------- #
# LearnedGate — empty / unfitted behaviour
# --------------------------------------------------------------------------- #


def test_unfitted_gate_returns_uniform_weights() -> None:
    gate = LearnedGate(n_experts=5, n_features=4)
    w = gate.predict_weights(np.array([0.1, 0.2, 0.3, 0.4]))
    assert w.shape == (5,)
    np.testing.assert_allclose(w, np.full(5, 0.2), atol=1e-12)


def test_empty_examples_leaves_gate_unfitted() -> None:
    gate = LearnedGate(n_experts=3, n_features=2)
    gate.fit([])
    assert not gate.is_fitted
    w = gate.predict_weights(np.array([0.5, 0.5]))
    np.testing.assert_allclose(w, np.ones(3) / 3, atol=1e-12)


# --------------------------------------------------------------------------- #
# LearnedGate — convergence on a synthetic signal
# --------------------------------------------------------------------------- #


def _make_synthetic_examples(
    n_rounds: int = 30,
    n_drivers: int = 8,
    rng_seed: int = 0,
    feature_dim: int = 3,
) -> tuple[list[TrainingExample], int]:
    """Construct a synthetic regime where:

    * Expert 0 puts almost all win-prob on driver 0
    * Expert 1 puts almost all win-prob on driver 1
    * The TRUE winner is driver 1 in every round
    * Features are random noise

    A correctly trained gate should learn to put nearly all weight on
    expert 1 regardless of the features.
    """
    rng = np.random.default_rng(rng_seed)
    expert_p_win_0 = np.full(n_drivers, 0.01)
    expert_p_win_0[0] = 1.0 - 0.01 * (n_drivers - 1)
    expert_p_win_1 = np.full(n_drivers, 0.01)
    expert_p_win_1[1] = 1.0 - 0.01 * (n_drivers - 1)
    examples: list[TrainingExample] = []
    for _ in range(n_rounds):
        feats = rng.standard_normal(feature_dim)
        expert_p_win = np.vstack([expert_p_win_0, expert_p_win_1])
        expert_p_pod = expert_p_win.copy()
        examples.append(
            TrainingExample(
                features=feats,
                expert_p_win=expert_p_win,
                expert_p_pod=expert_p_pod,
                winner_idx=1,
                drivers=[f"D{i}" for i in range(n_drivers)],
            )
        )
    return examples, 1  # winner is always expert 1


def test_gate_learns_to_favour_correct_expert_on_synthetic() -> None:
    examples, correct_expert = _make_synthetic_examples()
    gate = LearnedGate(n_experts=2, n_features=3, l2=0.01)
    gate.fit(examples, max_iter=200)
    assert gate.is_fitted
    # Probe with several random feature vectors.
    rng = np.random.default_rng(123)
    for _ in range(5):
        x = rng.standard_normal(3)
        w = gate.predict_weights(x)
        assert w[correct_expert] > 0.8, (
            f"expected w[{correct_expert}] > 0.8 after training but got {w}"
        )


def test_gate_weights_sum_to_one() -> None:
    examples, _ = _make_synthetic_examples()
    gate = LearnedGate(n_experts=2, n_features=3)
    gate.fit(examples)
    w = gate.predict_weights(np.zeros(3))
    assert abs(float(w.sum()) - 1.0) < 1e-9


def test_gate_handles_K_experts_dimension_match() -> None:
    # Sanity: feature shape mismatch raises.
    gate = LearnedGate(n_experts=4, n_features=5)
    with pytest.raises(ValueError):
        gate.predict_weights(np.zeros(3))


# --------------------------------------------------------------------------- #
# DEFAULT_EXPERT_NAMES is non-empty (sanity for the benchmark code)
# --------------------------------------------------------------------------- #


def test_default_expert_names_nonempty() -> None:
    assert len(DEFAULT_EXPERT_NAMES) >= 2
    assert len(DEFAULT_FEATURE_NAMES) >= 2
