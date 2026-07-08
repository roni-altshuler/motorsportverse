"""Package smoke tests — imports, config shapes, the ecosystem Predictor contract."""
from __future__ import annotations

from nascar_predictions import config


def test_imports():
    from nascar_predictions.datasource import NascarDataSource, SportDataSource  # noqa: F401
    from nascar_predictions.predict import NascarPredictor, SportPredictor  # noqa: F401


def test_config_shapes():
    assert config.SEASON == 2026
    assert config.SEASON_LABEL == "2026"
    assert len(config.CALENDAR) == 36
    assert len(config.CALENDAR_META) == 36
    assert len(config.DRIVERS) == 38
    # 2026 points: win raised to 55, P2 unchanged at 35, floor 1.
    assert config.RACE_POINTS_2026[1] == 55
    assert config.RACE_POINTS_2026[2] == 35
    assert config.RACE_POINTS_2026[36] == 1
    assert config.STAGE_POINTS[1] == 10 and config.STAGE_POINTS[10] == 1
    # The 2026 Chase: 26 + 10, top-16 on points, no eliminations.
    fmt = config.CUP_CHASE_FORMAT_2026
    assert fmt.regular_season_races == 26
    assert fmt.qualification == "points"
    assert len(fmt.rounds) == 1 and fmt.rounds[0].n_races == 10
    assert fmt.probability_keys == ("p_make_playoffs", "p_title")
    # Every roster driver has a team, make, and unique code.
    codes = [d["code"] for d in config.DRIVERS]
    assert len(set(codes)) == len(codes)
    for d in config.DRIVERS:
        assert d["make"] in config.MANUFACTURERS
        assert d["team"]


def test_track_types_cover_the_calendar():
    kinds = {meta["trackType"] for meta in config.CALENDAR_META.values()}
    assert kinds == set(config.TRACK_TYPES)
    # Verified classifications for landmark venues.
    assert config.CALENDAR_META[1]["trackType"] == "superspeedway"   # Daytona 500
    assert config.CALENDAR_META[8]["trackType"] == "short"           # Bristol
    assert config.CALENDAR_META[18]["trackType"] == "road"           # Sonoma
    assert config.CALENDAR_META[13]["trackType"] == "intermediate"   # Charlotte 600


def test_track_type_of_handles_history():
    # Road-course substrings win over the superspeedway host track.
    assert config.track_type_of("Daytona International Speedway Road Course", 2021) == "road"
    # Atlanta was an intermediate before the 2022 reprofile.
    assert config.track_type_of("Atlanta Motor Speedway", 2021) == "intermediate"
    assert config.track_type_of("Atlanta Motor Speedway", 2022) == "superspeedway"
    assert config.track_type_of("Chicago Street Course", 2023) == "road"
    assert config.track_type_of("Dover Motor Speedway", 2023) == "short"


def test_driver_code_is_deterministic_and_disambiguates():
    assert config.driver_code("Kyle Larson") == "KYLARSON"
    assert config.driver_code("Kyle Busch") == "KYBUSCH"
    assert config.driver_code("Kurt Busch") == "KUBUSCH"
    assert config.driver_code("Austin Dillon") == "AUDILLON"
    assert config.driver_code("Ty Dillon") == "TYDILLON"
    assert config.driver_code("Ricky Stenhouse Jr") == "RISTENHOUSE"
    assert config.driver_code("Martin Truex Jr.") == "MATRUEX"
    assert config.driver_code("Daniel Suárez") == "DASUAREZ"
    assert config.driver_code("Shane Van Gisbergen") == "SHGISBERGEN"


def test_predictor_contract(real_source):
    from nascar_predictions.predict import NascarPredictor

    predictor = NascarPredictor()
    predictor.fit(real_source, config.SEASON, upto_round=2)
    fc = predictor.predict(real_source, config.SEASON, 2)
    assert fc.season == config.SEASON and fc.round == 2
    n = len(fc.predicted_order)
    assert n >= 36
    assert set(fc.predicted_order.values()) == set(range(1, n + 1))
    assert fc.probabilities is not None
    assert abs(sum(fc.probabilities.p_win.values()) - 1.0) < 0.05
    assert fc.metadata["track_type"] in config.TRACK_TYPES
    assert fc.metadata["p_dnf"]
