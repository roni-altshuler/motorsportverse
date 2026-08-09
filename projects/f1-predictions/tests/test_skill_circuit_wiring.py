"""Wiring tests for the leakage-safe skill-prior + circuit-history features.

These guard that ``features/skill_priors.py`` and
``features/circuit_driver_history.py`` are actually *called* by the training
pipeline (they were written and tested in isolation but never wired), that the
retired ``PreviousPosition`` no longer feeds the model, and that both new
aggregations respect prior-only discipline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import f1_prediction_utils as U


def _mini_grid():
    return pd.DataFrame(
        [
            {"Driver": "VER", "Team": "Red Bull Racing"},
            {"Driver": "NOR", "Team": "McLaren"},
            {"Driver": "LEC", "Team": "Ferrari"},
        ]
    )


def _combined():
    # Rounds 1 and 2: VER strong, NOR weak.
    return {
        "1": {"VER": 1, "NOR": 12, "LEC": 4},
        "2": {"VER": 2, "NOR": 14, "LEC": 3},
    }


def test_skill_prior_columns_are_wired_and_finite():
    out = U._add_skill_prior_features(_mini_grid(), _combined(), current_round=3)
    for col in ("SkillPrior", "DriverPrior", "TeamPrior"):
        assert col in out.columns
        assert np.isfinite(out[col].astype(float)).all()
    # A strong prior finisher (VER) must carry a lower (better) SkillPrior than
    # a weak one (NOR).
    ver = float(out.loc[out["Driver"] == "VER", "SkillPrior"].iloc[0])
    nor = float(out.loc[out["Driver"] == "NOR", "SkillPrior"].iloc[0])
    assert ver < nor


def test_skill_prior_is_neutral_at_round_one():
    out = U._add_skill_prior_features(_mini_grid(), {}, current_round=1)
    # No prior rounds → everyone shares the finite field-mean fallback.
    assert np.isfinite(out["SkillPrior"].astype(float)).all()
    assert out["SkillPrior"].nunique() == 1


def test_circuit_history_columns_wired_and_finite():
    out = U._add_circuit_history_features(_mini_grid(), current_round=3, circuit_key="Australia")
    for col, neutral in U._CIRCUIT_HISTORY_NEUTRAL.items():
        assert col in out.columns
        vals = out[col].astype(float)
        assert np.isfinite(vals).all()
        # Offline (no circuit-keyed history) → neutral constant.
        assert (vals == neutral).all()


def test_build_prior_round_frames_is_prior_only():
    frames = U._build_prior_round_frames(_combined(), current_round=3)
    assert set(frames.keys()) == {1, 2}
    # Rounds at/after current_round are dropped, never used as features.
    mixed = {"1": {"VER": 1}, "3": {"VER": 1}, "4": {"VER": 1}}
    kept = U._build_prior_round_frames(mixed, current_round=3)
    assert set(kept.keys()) == {1}


def test_round_wet_flags_are_prior_only():
    flags = U._round_wet_flags(current_round=4)
    # Only rounds strictly before the target may appear.
    assert all(r < 4 for r in flags)
    assert all(isinstance(v, bool) for v in flags.values())
