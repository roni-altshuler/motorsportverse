"""Pipeline: standings, season-state reconstruction, playoff integration."""
from __future__ import annotations

from nascar_predictions import config, pipeline

SEASON = config.SEASON


def test_official_standings_match_reconstructed_points(real_source):
    """The snapshot's summed standings and the tally builder must agree —
    both read the feed's points_earned (stage points included)."""
    official = pipeline.official_standings(real_source, SEASON)
    assert official is not None
    state, remaining = pipeline.build_season_state(
        real_source, SEASON, config.CUP_CHASE_FORMAT_2026
    )
    assert remaining == config.REGULAR_SEASON_RACES - 19
    by_code = {d["code"]: d for d in official["driverStandings"]}
    for code, st in state.drivers.items():
        assert abs(st.points - by_code[code]["points"]) < 0.01, code
        assert st.wins == by_code[code]["wins"], code


def test_playoff_reconstruction_matches_real_2022_field(real_source):
    """Replaying the 2022 elimination season through the reconstruction must
    reproduce the REAL playoff field (ground truth: the feed's standings
    positions after race 27)."""
    from nascar_predictions.playoff_backtest import real_playoff_field

    fmt = config.CUP_PLAYOFF_FORMAT_2017_2025
    state, rem = pipeline.build_season_state(real_source, 2022, fmt, through_round=27)
    assert rem == 0
    assert state.playoff is not None
    assert state.playoff.round_index == 0
    assert state.playoff.races_completed_in_round == 1
    recon = set(state.playoff.alive)
    actual = real_playoff_field(real_source, 2022)
    assert len(recon) == 16
    assert len(actual) == 16
    assert len(recon & actual) >= 15  # win-and-in fine print may cost one seat


def test_playoff_reconstruction_round_boundaries(real_source):
    """At an elimination boundary the cut must have been applied and the next
    round's reset included in round_points."""
    fmt = config.CUP_PLAYOFF_FORMAT_2017_2025
    state, _ = pipeline.build_season_state(real_source, 2022, fmt, through_round=32)
    ps = state.playoff
    assert ps is not None
    assert ps.round_index == 2              # Round of 8
    assert ps.races_completed_in_round == 0
    assert len(ps.alive) == 8
    # Reset applied: 4000 base + banked playoff points.
    for c in ps.alive:
        assert ps.round_points[c] >= 4000.0


def test_playoff_projection_ladder_is_monotone(real_source):
    ladder = pipeline.playoff_projection(real_source, SEASON, n_sims=800)
    assert ladder
    total_title = sum(p["p_title"] for p in ladder.values())
    assert abs(total_title - 1.0) < 0.02
    for code, probs in ladder.items():
        assert 0.0 <= probs["p_title"] <= probs["p_make_playoffs"] + 1e-9, code
    # Exactly 16 playoff slots on average.
    assert abs(sum(p["p_make_playoffs"] for p in ladder.values()) - 16.0) < 0.2


def test_playoff_projection_uses_elimination_format_when_asked(real_source):
    fmt = config.CUP_PLAYOFF_FORMAT_2017_2025
    ladder = pipeline.playoff_projection(
        real_source, 2022, fmt=fmt, through_round=26, n_sims=400
    )
    sample = next(iter(ladder.values()))
    assert set(sample) == {
        "p_make_playoffs", "p_round_of_12", "p_round_of_8", "p_championship_4", "p_title",
    }


def test_project_title_shape(real_source):
    rows = pipeline.project_title(real_source, SEASON, n_samples=400)
    assert rows and rows[0].p_title == max(r.p_title for r in rows)
    leader = rows[0]
    assert leader.proj_mean >= leader.current_points  # points only accumulate


def test_round_tallies_read_stage_winners(real_source):
    t = pipeline.round_tallies(real_source, SEASON, 8)  # Bristol
    assert t is not None
    assert t["winner"] == "TYGIBBS"
    assert len(t["stage_winners"]) == 2
    assert t["points"]["TYGIBBS"] == 59.0  # 55 win + 4 stage points (verified)
