"""Property tests for the NASCAR playoff Monte Carlo simulator.

These are the shipping gate for ``championship_playoffs``: structural
invariants (field sizes, cuts, one champion), probability monotonicity,
degenerate mid-season states, the win-and-advance rule, the playoff-points
bank, and determinism.
"""
from __future__ import annotations

import numpy as np
import pytest

from nascar_predictions.championship_playoffs import (
    DriverState,
    PlayoffPhaseState,
    SeasonState,
    project_playoffs,
    simulate_playoffs,
)
from nascar_predictions.config import (
    CUP_CHASE_FORMAT_2026,
    CUP_PLAYOFF_FORMAT,
    RACE_POINTS_2017_2025,
    RACE_POINTS_2026,
    STAGE_POINTS,
)

PROB_KEYS = (
    "p_make_playoffs",
    "p_round_of_12",
    "p_round_of_8",
    "p_championship_4",
    "p_title",
)


def make_strengths(n: int = 38, spread: float = 3.0) -> dict[str, float]:
    """Lap-time-like strengths (lower = better), D01 strongest."""
    return {f"D{i + 1:02d}": spread * i / (n - 1) for i in range(n)}


@pytest.fixture(scope="module")
def full_season_sim():
    """One shared fresh-season simulation of the elimination format."""
    strengths = make_strengths(38)
    return simulate_playoffs(
        strengths,
        CUP_PLAYOFF_FORMAT,
        completed_results=None,
        remaining_schedule=26,
        n_sims=400,
        rng_seed=7,
    )


# --------------------------------------------------------------------------- #
# 1. Structural invariants
# --------------------------------------------------------------------------- #


def test_field_sizes_and_single_champion(full_season_sim):
    sim = full_season_sim
    expected = (16, 12, 8, 4)
    assert len(sim.reached) == 4
    for stage, size in enumerate(expected):
        counts = sim.reached[stage].sum(axis=1)
        assert (counts == size).all(), f"stage {stage}: expected {size} alive everywhere"
    # Exactly one champion per sim, always drawn from the Championship 4.
    assert sim.champion.shape == (sim.n_sims,)
    c4 = sim.reached[-1]
    assert c4[np.arange(sim.n_sims), sim.champion].all()


def test_p_title_sums_to_one(full_season_sim):
    probs = full_season_sim.probabilities()
    total = sum(p["p_title"] for p in probs.values())
    assert abs(total - 1.0) < 1e-9


def test_probability_keys_match_task_contract(full_season_sim):
    probs = full_season_sim.probabilities()
    for driver_probs in probs.values():
        assert tuple(driver_probs.keys()) == PROB_KEYS


# --------------------------------------------------------------------------- #
# 2. Monotonicity
# --------------------------------------------------------------------------- #


def test_probability_ladder_is_monotone(full_season_sim):
    probs = full_season_sim.probabilities()
    for driver, p in probs.items():
        ladder = [p[k] for k in PROB_KEYS]
        for a, b in zip(ladder, ladder[1:]):
            assert b <= a + 1e-12, f"{driver}: ladder not monotone: {ladder}"


# --------------------------------------------------------------------------- #
# 3. Degenerate mid-season states
# --------------------------------------------------------------------------- #


def test_zero_remaining_races_locks_the_field():
    """With the regular season complete, playoff spots are certainties."""
    strengths = make_strengths(24)
    drivers = list(strengths)
    # Distinct points, no wins: top 16 on points are in, the rest are out.
    state = SeasonState(
        drivers={d: DriverState(points=1000 - 10 * i) for i, d in enumerate(drivers)}
    )
    probs = project_playoffs(
        strengths, CUP_PLAYOFF_FORMAT, state, remaining_schedule=0, n_sims=200, rng_seed=3
    )
    for i, d in enumerate(drivers):
        expected = 1.0 if i < 16 else 0.0
        assert probs[d]["p_make_playoffs"] == expected, d


def test_mathematically_eliminated_driver_never_qualifies():
    """Points-only qualification: an insurmountable gap means p == 0 exactly.

    Two races remain; the max haul per race is 55 (win) + 20 (both stages)
    = 75, so 150 total. DOOM sits 350 behind everyone else.
    """
    strengths = make_strengths(20)
    drivers = list(strengths)
    doom = drivers[-1]
    points = {d: 500.0 + i for i, d in enumerate(drivers)}
    points[doom] = 0.0
    state = SeasonState(drivers={d: DriverState(points=points[d]) for d in drivers})
    probs = project_playoffs(
        strengths,
        CUP_CHASE_FORMAT_2026,
        state,
        remaining_schedule=2,
        n_sims=500,
        rng_seed=11,
    )
    assert probs[doom]["p_make_playoffs"] == 0.0
    assert probs[doom]["p_title"] == 0.0


def test_resume_inside_playoffs():
    """Mid-Round-of-8 resume: fewer remaining rounds, invariants still hold."""
    strengths = make_strengths(30)
    drivers = list(strengths)
    alive = tuple(drivers[:8])
    state = SeasonState(
        drivers={d: DriverState(points=0, playoff_points=5 * (8 - i)) for i, d in enumerate(drivers)},
        playoff=PlayoffPhaseState(
            round_index=2,  # Round of 8
            races_completed_in_round=1,
            alive=alive,
            round_points={d: 4040.0 - 5 * i for i, d in enumerate(alive)},
            round_wins={alive[0]: 1},  # already won a race in the round
        ),
    )
    sim = simulate_playoffs(
        strengths, CUP_PLAYOFF_FORMAT, state, remaining_schedule=0, n_sims=300, rng_seed=5
    )
    assert (sim.reached[2].sum(axis=1) == 8).all()
    assert (sim.reached[3].sum(axis=1) == 4).all()
    probs = sim.probabilities()
    # The in-round race winner has already banked auto-advance.
    assert probs[alive[0]]["p_championship_4"] == 1.0
    # Eliminated drivers can no longer win anything.
    for d in drivers[8:]:
        assert probs[d]["p_title"] == 0.0
    total = sum(p["p_title"] for p in probs.values())
    assert abs(total - 1.0) < 1e-9


# --------------------------------------------------------------------------- #
# 4. A round race win guarantees advancement
# --------------------------------------------------------------------------- #


def test_round_race_win_auto_advances(full_season_sim):
    sim = full_season_sim
    for r in range(3):  # the three elimination rounds
        winners = sim.round_wins[r]  # alive drivers who won a race in round r
        advanced = sim.reached[r + 1]
        assert advanced[winners].all(), f"round {r}: a race winner was eliminated"
        assert winners.any(), f"round {r}: no alive winners sampled (test vacuous)"


# --------------------------------------------------------------------------- #
# 5. The playoff-points bank
# --------------------------------------------------------------------------- #


def test_bank_helps_advancement_but_not_the_finale():
    """Identical-strength drivers, one with a 60-point bank.

    The banked driver must advance more often through every elimination
    round; but conditional on reaching the Championship 4 (equal strengths,
    winner-take-all race, bank not applied) the title chance is 1/4 for both.
    """
    drivers = [f"D{i:02d}" for i in range(20)]
    strengths = {d: 1.0 for d in drivers}  # perfectly equal field
    nobank, bank = drivers[0], drivers[1]  # nobank first => tiebreaks favour it
    points = {d: 600.0 for d in drivers}
    points[nobank] = 701.0
    points[bank] = 700.0
    pp = {d: 0.0 for d in drivers}
    pp[bank] = 60.0
    state = SeasonState(
        drivers={d: DriverState(points=points[d], playoff_points=pp[d]) for d in drivers}
    )
    probs = project_playoffs(
        strengths, CUP_PLAYOFF_FORMAT, state, remaining_schedule=0, n_sims=6000, rng_seed=17
    )
    for key in ("p_round_of_12", "p_round_of_8", "p_championship_4"):
        assert probs[bank][key] > probs[nobank][key] + 0.03, key
    # Bank must NOT influence the Championship 4 race itself.
    for d in (bank, nobank):
        cond_title = probs[d]["p_title"] / probs[d]["p_championship_4"]
        assert abs(cond_title - 0.25) < 0.05, (d, cond_title)


# --------------------------------------------------------------------------- #
# 6. Determinism
# --------------------------------------------------------------------------- #


def test_deterministic_under_fixed_seed():
    strengths = make_strengths(30)
    kwargs = dict(remaining_schedule=10, n_sims=300)
    state = SeasonState(
        drivers={d: DriverState(points=800 - 20 * i) for i, d in enumerate(strengths)}
    )
    a = project_playoffs(strengths, CUP_PLAYOFF_FORMAT, state, rng_seed=99, **kwargs)
    b = project_playoffs(strengths, CUP_PLAYOFF_FORMAT, state, rng_seed=99, **kwargs)
    assert a == b
    c = project_playoffs(strengths, CUP_PLAYOFF_FORMAT, state, rng_seed=100, **kwargs)
    assert a != c  # 300 sims x 30 drivers: identical output is astronomically unlikely


# --------------------------------------------------------------------------- #
# 2026 Chase format (the rules actually in force this season)
# --------------------------------------------------------------------------- #


def test_chase_2026_shape_and_invariants():
    strengths = make_strengths(38)
    sim = simulate_playoffs(
        strengths, CUP_CHASE_FORMAT_2026, remaining_schedule=26, n_sims=400, rng_seed=21
    )
    # Single round, no eliminations: exactly 16 qualify, champion is one of them.
    assert len(sim.reached) == 1
    assert (sim.reached[0].sum(axis=1) == 16).all()
    assert sim.reached[0][np.arange(sim.n_sims), sim.champion].all()
    probs = sim.probabilities()
    for p in probs.values():
        assert tuple(p.keys()) == ("p_make_playoffs", "p_title")
        assert p["p_title"] <= p["p_make_playoffs"] + 1e-12
    assert abs(sum(p["p_title"] for p in probs.values()) - 1.0) < 1e-9


# --------------------------------------------------------------------------- #
# Config sanity
# --------------------------------------------------------------------------- #


def test_points_tables_encode_verified_values():
    assert RACE_POINTS_2017_2025[1] == 40
    assert RACE_POINTS_2026[1] == 55
    for table in (RACE_POINTS_2017_2025, RACE_POINTS_2026):
        assert table[2] == 35 and table[3] == 34 and table[35] == 2
        assert table[36] == 1 and table[40] == 1
    assert STAGE_POINTS == {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
    # 2026 Chase seeding: 2100 / 2075 / 2065 then -5 per seed down to 2000.
    seeds = [2000 + b for b in CUP_CHASE_FORMAT_2026.rounds[0].seed_bonus]
    assert seeds[:3] == [2100, 2075, 2065]
    assert seeds[-1] == 2000 and len(seeds) == 16
    assert all(a - b == 5 for a, b in zip(seeds[2:], seeds[3:]))


def test_stronger_drivers_get_higher_title_probability(full_season_sim):
    """Coarse sanity: the top-strength tercile out-titles the bottom tercile."""
    probs = full_season_sim.probabilities()
    drivers = sorted(probs)  # D01 strongest by construction
    top = sum(probs[d]["p_title"] for d in drivers[:12])
    bottom = sum(probs[d]["p_title"] for d in drivers[-12:])
    assert top > 0.6
    assert bottom < 0.05
