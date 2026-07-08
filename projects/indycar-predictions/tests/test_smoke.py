"""Package smoke tests — imports, config shapes, the ecosystem Predictor contract."""
from __future__ import annotations

from indycar_predictions import config


def test_imports():
    from indycar_predictions.datasource import IndycarDataSource, SportDataSource  # noqa: F401
    from indycar_predictions.predict import IndycarPredictor, SportPredictor  # noqa: F401


def test_config_shapes():
    assert config.SEASON == 2026
    assert config.SEASON_LABEL == "2026"
    assert len(config.CALENDAR) == 18
    assert len(config.CALENDAR_META) == 18
    assert len(config.DRIVERS) == 25
    assert len(config.INDY500_ONLY_DRIVERS) == 8
    # Base points table (verified against the curated awarded points).
    assert config.POINTS[1] == 50
    assert config.POINTS[2] == 40
    assert config.POINTS[3] == 35
    assert config.POINTS[10] == 20
    assert config.POINTS[24] == 6
    assert config.POINTS[25] == 5
    assert config.POINTS[33] == 5  # everyone from 25th back scores 5
    # 2026 curated data: the 500 pays NO double points (winner earned 60).
    assert config.INDY500_DOUBLE_POINTS is False
    # Every roster driver has a team, engine, and unique code.
    codes = [d["code"] for d in config.DRIVERS]
    assert len(set(codes)) == len(codes)
    for d in config.DRIVERS:
        assert d["engine"] in config.ENGINES
        assert d["team"]
    # Indy-500-only entries never collide with the full-season roster.
    assert not set(config.INDY500_ONLY_DRIVERS) & set(codes)


def test_calendar_track_types_and_indy500():
    kinds = {meta["trackType"] for meta in config.CALENDAR_META.values()}
    assert kinds == set(config.TRACK_TYPES)
    # Verified classifications for landmark rounds.
    assert config.CALENDAR_META[1]["trackType"] == "street"   # St. Petersburg
    assert config.CALENDAR_META[7]["trackType"] == "oval"     # Indy 500
    assert config.CALENDAR_META[12]["trackType"] == "oval"    # Nashville
    assert config.CALENDAR_META[18]["trackType"] == "road"    # Laguna Seca
    # The 500 is round 7 (the IMS *oval*) — the road-course GP (round 6, also
    # at IMS) must NOT be flagged.
    assert config.INDY500_ROUNDS == (7,)
    assert config.is_indy500_round(7)
    assert not config.is_indy500_round(6)


def test_track_groups_are_the_dual_elo_split():
    assert config.track_group_of("oval") == "oval"
    assert config.track_group_of("road") == "road_street"
    assert config.track_group_of("street") == "road_street"
    assert set(config.ELO_TRACK_GROUPS) == {"oval", "road_street"}


def test_driver_code_is_deterministic_and_disambiguates():
    assert config.driver_code("Álex Palou") == "ALPALOU"
    assert config.driver_code("Pato O'Ward") == "PAWARD"
    assert config.driver_code("Marcus Ericsson") == "MAERICSSON"
    assert config.driver_code("Marcus Armstrong") == "MAARMSTRONG"
    assert config.driver_code("Scott Dixon") == "SCDIXON"
    assert config.driver_code("Scott McLaughlin") == "SCMCLAUGHLIN"
    # Accent-insensitive: both curated spellings fold to one identity.
    assert config.driver_code("Sébastien Bourdais") == config.driver_code("Sebastian Bourdais")


def test_predictor_contract(real_source):
    from indycar_predictions.predict import IndycarPredictor

    predictor = IndycarPredictor()
    predictor.fit(real_source, config.SEASON, upto_round=2)
    fc = predictor.predict(real_source, config.SEASON, 2)
    assert fc.season == config.SEASON and fc.round == 2
    n = len(fc.predicted_order)
    assert n >= 25
    assert set(fc.predicted_order.values()) == set(range(1, n + 1))
    assert fc.probabilities is not None
    assert abs(sum(fc.probabilities.p_win.values()) - 1.0) < 0.05
    assert fc.metadata["track_type"] in config.TRACK_TYPES
    assert fc.metadata["track_group"] in config.ELO_TRACK_GROUPS
    assert fc.metadata["p_dnf"]
