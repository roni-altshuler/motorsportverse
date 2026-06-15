"""Tests for ``features/skill_priors.py``.

The point of skill_priors is to *replace* the leakage-prone
``PreviousPosition`` feature with a Bayesian blend that strictly uses
prior-round data. These tests pin that no future-round leakage can sneak
into the priors regardless of input shape.
"""
from __future__ import annotations

import pandas as pd
import pytest

from motorsport_core.leakage import LeakageError
from motorsport_core.features.skill_priors import attach_skill_priors, SkillPriorConfig


def _build_prior(rounds: dict[int, list[dict]]) -> dict[int, pd.DataFrame]:
    return {r: pd.DataFrame(rows) for r, rows in rounds.items()}


def test_priors_use_only_prior_rounds():
    rows = pd.DataFrame([
        {"Driver": "VER", "Team": "Red Bull Racing"},
        {"Driver": "NOR", "Team": "McLaren"},
    ])
    prior_results = _build_prior({
        1: [{"Driver": "VER", "Team": "Red Bull Racing", "FinishPosition": 1},
            {"Driver": "NOR", "Team": "McLaren", "FinishPosition": 3}],
        2: [{"Driver": "VER", "Team": "Red Bull Racing", "FinishPosition": 1},
            {"Driver": "NOR", "Team": "McLaren", "FinishPosition": 5}],
    })
    out = attach_skill_priors(rows, current_round=3, season=2026, prior_results=prior_results)
    assert "SkillPrior" in out.columns
    # VER averaged 1.0, NOR averaged 4.0 — VER's prior should be lower (better)
    ver_prior = float(out.loc[out["Driver"] == "VER", "SkillPrior"].iloc[0])
    nor_prior = float(out.loc[out["Driver"] == "NOR", "SkillPrior"].iloc[0])
    assert ver_prior < nor_prior


def test_priors_reject_future_rounds():
    rows = pd.DataFrame([{"Driver": "VER", "Team": "Red Bull Racing"}])
    bad_prior = _build_prior({
        5: [{"Driver": "VER", "Team": "Red Bull Racing", "FinishPosition": 1}],
    })
    with pytest.raises((ValueError, LeakageError)):
        attach_skill_priors(rows, current_round=3, season=2026, prior_results=bad_prior)


def test_priors_fall_back_to_field_mean_for_unknown_driver():
    rows = pd.DataFrame([
        {"Driver": "ROOKIE", "Team": "Sauber"},
    ])
    # Spread the field across both ends so the field mean is mid-pack —
    # the unknown driver should land near it, not at the leader's value.
    prior_results = _build_prior({
        1: [{"Driver": "VER", "Team": "Red Bull Racing", "FinishPosition": 1},
            {"Driver": "HAM", "Team": "Mercedes", "FinishPosition": 20}],
        2: [{"Driver": "VER", "Team": "Red Bull Racing", "FinishPosition": 1},
            {"Driver": "HAM", "Team": "Mercedes", "FinishPosition": 18}],
    })
    out = attach_skill_priors(rows, current_round=3, season=2026, prior_results=prior_results)
    val = float(out["SkillPrior"].iloc[0])
    # Field mean over the 4 observations is 10.0 — unknown driver should
    # be shrunk toward it, definitely above the leader (1.0) and below
    # the back-of-grid (20.0).
    assert 5.0 < val < 15.0


def test_priors_blend_respects_weights():
    rows = pd.DataFrame([{"Driver": "X", "Team": "Y"}])
    prior_results = _build_prior({
        1: [{"Driver": "X", "Team": "Y", "FinishPosition": 1}],
        2: [{"Driver": "X", "Team": "Y", "FinishPosition": 1}],
    })
    cfg_driver = SkillPriorConfig(alpha=1.0, beta=0.0, gamma=0.0)
    out_driver = attach_skill_priors(rows, current_round=3, season=2026,
                                     prior_results=prior_results, config=cfg_driver)
    # With pure-driver weight and shrinkage, prior is between 1.0 and the field mean.
    assert 1.0 <= float(out_driver["SkillPrior"].iloc[0]) <= 1.5
