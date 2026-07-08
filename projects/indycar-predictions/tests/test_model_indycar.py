"""The IndyCar model: dual oval/road-street Elo, DNF composition, grid conditioning."""
from __future__ import annotations

import numpy as np
from motorsport_data.schema import Result

from indycar_predictions import config, model
from indycar_predictions.datasource import IndycarDataSource

SEASON = config.SEASON


def test_estimate_skill_covers_entrants_and_is_deterministic(real_source):
    pace1 = model.estimate_skill(real_source, SEASON, 8)
    pace2 = model.estimate_skill(real_source, SEASON, 8)
    assert pace1 == pace2
    entrants = set(real_source.entrants(SEASON, 8))
    assert set(pace1) == entrants
    assert len(set(round(p, 6) for p in pace1.values())) > 5  # real spread


def test_incremental_elo_matches_fresh_replay(real_source):
    """Walking rounds forward incrementally must equal a from-scratch replay."""
    model.estimate_skill(real_source, SEASON, 5)
    incremental = model.estimate_skill(real_source, SEASON, 9)
    fresh = IndycarDataSource()
    scratch = model.estimate_skill(fresh, SEASON, 9)
    assert incremental == scratch


def test_indy500_entrants_include_one_off_drivers(real_source):
    """The 500's entry picture carries the Indy-500-only cars; a normal round
    does not (pre-race entry lists, not results)."""
    from conftest import TruncatedSource

    from indycar_predictions.sources.composite import CompositeIndycarSource
    from indycar_predictions.sources.snapshot import SnapshotIndycarSource

    trunc = IndycarDataSource(
        source=CompositeIndycarSource([TruncatedSource(SnapshotIndycarSource(), SEASON, 6)])
    )
    entrants_500 = set(trunc.entrants(SEASON, 7))     # upcoming 500 (round 7 hidden)
    entrants_r12 = set(trunc.entrants(SEASON, 12))    # upcoming normal round
    assert set(config.INDY500_ONLY_DRIVERS) <= entrants_500
    assert not set(config.INDY500_ONLY_DRIVERS) & entrants_r12
    assert len(entrants_500) == 33


# --------------------------------------------------------------------------- #
# Dual-Elo sanity — the dominant split
# --------------------------------------------------------------------------- #
def test_dual_track_elo_orders_differ_on_real_data(real_source):
    """The oval Elo and the road/street Elo must actually rank the field
    differently — otherwise the dual split adds nothing."""
    stack = model._elo_skill(real_source, SEASON, 12)
    oval = stack["track"]["oval"]
    rs = stack["track"]["road_street"]
    common = [c for c in oval if c in rs and oval[c] != 1500.0 and rs[c] != 1500.0]
    assert len(common) >= 20
    oval_order = sorted(common, key=lambda c: -oval[c])
    rs_order = sorted(common, key=lambda c: -rs[c])
    assert oval_order != rs_order


class _SpecialistSource:
    """Fake 2026 source: ALPALOU is an oval specialist (wins every oval,
    finishes last elsewhere), SCDIXON the mirror-image road/street specialist.
    Everyone else finishes in fixed roster order between them."""

    name = "snapshot"

    def __init__(self):
        self._codes = [d["code"] for d in config.DRIVERS]

    def results(self, year, round, race_index: int = 0):
        if year != SEASON or round < 1 or round > 11:
            return []
        oval = config.CALENDAR_META[round]["trackType"] == "oval"
        ace, mule = ("ALPALOU", "SCDIXON") if oval else ("SCDIXON", "ALPALOU")
        rest = [c for c in self._codes if c not in ("ALPALOU", "SCDIXON")]
        order = [ace] + rest + [mule]
        return [
            Result(competitor=c, position=i, grid=i, status="Running", points=None)
            for i, c in enumerate(order, start=1)
        ]

    def race_rows(self, year, round):
        return None

    def qualifying(self, year, round):
        return None

    def calendar(self, year):
        return []

    def standings(self, year):
        return []

    def provenance(self, year, round, race_index: int = 0):
        return "snapshot"


def test_oval_specialist_ranked_higher_on_ovals():
    """Blend sanity for the dominant split: with identical overall history,
    the oval specialist must out-rank the road specialist on an oval round and
    vice versa on a road round."""
    src_oval = IndycarDataSource(source=_SpecialistSource())
    pace_oval = model.estimate_skill(src_oval, SEASON, 12)   # Nashville: oval
    src_road = IndycarDataSource(source=_SpecialistSource())
    pace_road = model.estimate_skill(src_road, SEASON, 13)   # Portland: road
    # Lower pace = faster.
    assert pace_oval["ALPALOU"] < pace_oval["SCDIXON"]
    assert pace_road["SCDIXON"] < pace_road["ALPALOU"]


# --------------------------------------------------------------------------- #
# DNF hazard + composition
# --------------------------------------------------------------------------- #
def test_dnf_risk_bounds_and_track_effect(real_source):
    """Oval hazard must exceed road-course hazard (walls + pack racing —
    learned from the curated status fields)."""
    lo, hi = config.DNF_CLIP
    oval = model.estimate_dnf_risk(real_source, SEASON, 12)   # Nashville oval
    road = model.estimate_dnf_risk(real_source, SEASON, 13)   # Portland road
    for p in list(oval.values()) + list(road.values()):
        assert lo <= p <= hi
    assert sum(oval.values()) / len(oval) > sum(road.values()) / len(road)


def test_dnf_composition_sanity_hazard_up_finish_down():
    """First-class DNF head: raising ONE driver's hazard must worsen his
    expected finish and cut his win probability — with pace held fixed."""
    codes = [f"D{i:02d}" for i in range(20)]
    pace = {c: 90.0 + 0.05 * i for i, c in enumerate(codes)}
    target = codes[2]  # a front-runner
    low = {c: 0.05 for c in codes}
    high = dict(low)
    high[target] = 0.35
    fc_low = model._race_forecast("race", codes, pace, low, n_samples=4000)
    fc_high = model._race_forecast("race", codes, pace, high, n_samples=4000)
    assert fc_high.mean_finish[target] > fc_low.mean_finish[target] + 1.0
    assert fc_high.markets.p_win[target] < fc_low.markets.p_win[target]
    # Everyone else benefits or stays flat.
    others_low = np.mean([fc_low.mean_finish[c] for c in codes if c != target])
    others_high = np.mean([fc_high.mean_finish[c] for c in codes if c != target])
    assert others_high <= others_low


def test_composed_markets_are_coherent(real_source):
    fc = model.forecast_round(real_source, SEASON, 12)
    m = fc.race.markets
    assert abs(sum(m.p_win.values()) - 1.0) < 1e-6
    assert abs(sum(m.p_podium.values()) - 3.0) < 1e-6
    for c in m.p_win:
        assert m.p_win[c] <= m.p_podium[c] + 1e-9
        assert m.p_podium[c] <= m.p_top6[c] + 1e-9
        assert m.p_top6[c] <= m.p_top10[c] + 1e-9
    # DNF hazard rides on the forecast for the probability layer.
    assert set(fc.race.p_dnf) == set(m.p_win)
    # H2H is symmetric-complementary.
    a, b = fc.race.order[0], fc.race.order[1]
    assert abs(m.h2h[a][b] + m.h2h[b][a] - 1.0) < 1e-9


def test_zero_hazard_reduces_to_pure_plackett_luce():
    """With hazard 0 the composed sampler must reproduce the core sampler's
    probabilities (same Gumbel-max math)."""
    from motorsport_core import calibration

    codes = [f"D{i:02d}" for i in range(12)]
    pace = {c: 90.0 + 0.08 * i for i, c in enumerate(codes)}
    fc = model._race_forecast("race", codes, pace, {c: 0.0 for c in codes}, n_samples=5000)
    core = calibration.plackett_luce_probabilities(pace, n_samples=5000)
    for c in codes:
        assert abs(fc.markets.p_win[c] - core.p_win[c]) < 0.02


def test_known_grid_conditions_forecast(real_source):
    pace = model.estimate_skill(real_source, SEASON, 12)
    merit = sorted(pace, key=lambda c: pace[c])
    reversed_grid = list(reversed(merit))
    fc_pre = model.forecast_round(real_source, SEASON, 12)
    fc_post = model.forecast_round(real_source, SEASON, 12, known_grid=reversed_grid)
    assert fc_post.race.grid == reversed_grid
    # Putting the fastest driver at the back must hurt his expected finish.
    fastest = merit[0]
    assert fc_post.race.mean_finish[fastest] > fc_pre.race.mean_finish[fastest]


def test_round_forecast_metadata(real_source):
    fc = model.forecast_round(real_source, SEASON, 12)
    assert fc.track_type == "oval"
    assert fc.track_group == "oval"
    assert fc.venue_name == "Nashville Superspeedway"
    assert fc.race_name == "Borchetta Bourbon Music City Grand Prix"
    assert fc.position_head is None  # gate OFF by default


# --------------------------------------------------------------------------- #
# Eras + championship MC
# --------------------------------------------------------------------------- #
def test_era_window_admits_full_curated_history():
    assert model.indycar_era_distance(2012, 2026) == 1  # dw12 → aeroscreen
    assert model.elo_seed_seasons(2026, range(2000, 2030)) == list(range(2012, 2026))
    assert model.elo_seed_seasons(2019, range(2000, 2030)) == list(range(2012, 2019))


def test_championship_projection_shapes():
    codes = [f"D{i:02d}" for i in range(10)]
    skill = {c: 90.0 + 0.05 * i for i, c in enumerate(codes)}
    points = {c: 0.0 for c in codes}
    proj = model.project_championship_indycar(points, skill, 4, n_samples=500)
    assert abs(sum(t.p_title for t in proj) - 1.0) < 1e-6
    best = proj[0]
    # Per-round ceiling: 50 base + 4 expected-bonus cap.
    assert best.proj_mean <= 4 * (50 + 4)
    assert best.proj_mean > 4 * 20
    # Season decided → leader wins with certainty.
    done = model.project_championship_indycar({"A": 100, "B": 50}, {"A": 90.0, "B": 90.1}, 0)
    assert done[0].key == "A" and done[0].p_title == 1.0
