"""Tests for the game-theory online learner (A-P2.1)."""
from __future__ import annotations

import numpy as np

from models.online_game_theory import (
    DEFAULT_BLEND_ALPHA,
    LEGACY_COEFFICIENTS,
    TERM_NAMES,
    GameTheoryCoefficients,
    update_from_round,
    walk_history,
)


def test_legacy_default_matches_legacy_dict():
    state = GameTheoryCoefficients.from_legacy()
    assert state.rounds_seen == 0
    assert state.coefficients == LEGACY_COEFFICIENTS


def test_too_few_rows_keeps_prior_coefficients():
    prior = GameTheoryCoefficients.from_legacy()
    state = update_from_round(
        prior,
        terms={t: [0.1, 0.2, 0.3] for t in TERM_NAMES},
        residuals=[0.0, 1.0, -0.5],
    )
    # n_rows < 4 → no update
    assert state.coefficients == prior.coefficients
    assert state.rounds_seen == 0


def test_perfect_signal_pulls_coefficient_in_direction():
    """If residual = +0.5 × UndercutEdgeAhead exactly, blend alpha must
    move that coefficient toward +0.5 from the legacy -0.30 anchor."""
    prior = GameTheoryCoefficients.from_legacy()
    # 8 drivers, varying UndercutEdgeAhead.  Other terms are 0.
    undercut = np.linspace(-1.0, 1.0, 8)
    residuals = 0.5 * undercut  # perfect linear relationship
    terms = {t: np.zeros(8) for t in TERM_NAMES}
    terms["UndercutEdgeAhead"] = undercut
    state = update_from_round(prior, terms, residuals, blend_alpha=0.5)
    legacy = LEGACY_COEFFICIENTS["UndercutEdgeAhead"]
    new_val = state.coefficients["UndercutEdgeAhead"]
    # Should move from -0.30 toward +0.5; at α=0.5 lands halfway.
    assert new_val > legacy
    assert state.rounds_seen == 1
    assert state.last_residual_rmse is not None


def test_no_signal_leaves_coefficients_near_prior():
    """If residuals are random noise uncorrelated with any term, the
    ridge fit should be tiny and the blend should keep us near the
    legacy anchor."""
    prior = GameTheoryCoefficients.from_legacy()
    rng = np.random.default_rng(0)
    n = 20
    terms = {t: rng.normal(0, 0.1, n) for t in TERM_NAMES}
    residuals = rng.normal(0, 0.1, n)  # noise
    state = update_from_round(prior, terms, residuals, blend_alpha=DEFAULT_BLEND_ALPHA)
    # Each coefficient should be close to its legacy value (within
    # blend × noise tolerance).
    for term in TERM_NAMES:
        delta = abs(state.coefficients[term] - LEGACY_COEFFICIENTS[term])
        assert delta < 0.5, f"{term} drifted too far: {delta}"


def test_walk_history_advances_rounds_seen():
    rounds = []
    rng = np.random.default_rng(1)
    for i in range(3):
        n = 10
        terms = {t: rng.normal(0, 0.1, n) for t in TERM_NAMES}
        rounds.append(
            {
                "season": 2024,
                "round": i + 1,
                "terms": terms,
                "residuals": rng.normal(0, 0.1, n),
            }
        )
    state = walk_history(None, rounds)
    assert state.rounds_seen == 3
    assert state.last_updated_season == 2024
    assert state.last_updated_round == 3


def test_metadata_preserved_when_no_terms_match():
    prior = GameTheoryCoefficients.from_legacy()
    # No matching term names → fit can't run, but metadata records the
    # attempted round so callers still know an update happened.
    state = update_from_round(
        prior,
        terms={"unknown-term": [0.1, 0.2, 0.3, 0.4]},
        residuals=[0.0, 0.0, 0.0, 0.0],
        season=2024,
        round_num=5,
    )
    assert state.coefficients == prior.coefficients
    assert state.last_updated_round == 5


def test_to_jsonable_round_trips():
    state = GameTheoryCoefficients.from_legacy()
    payload = state.to_jsonable()
    assert "coefficients" in payload
    assert payload["rounds_seen"] == 0
    assert payload["coefficients"]["UndercutEdgeAhead"] == LEGACY_COEFFICIENTS["UndercutEdgeAhead"]
