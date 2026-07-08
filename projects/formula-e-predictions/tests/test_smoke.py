"""Package smoke tests — imports + the ecosystem Predictor contract."""
from __future__ import annotations

from formula_e_predictions import config


def test_imports():
    from formula_e_predictions.datasource import FEDataSource, SportDataSource  # noqa: F401
    from formula_e_predictions.predict import FEPredictor, SportPredictor  # noqa: F401


def test_config_shapes():
    assert config.SEASON == 2026
    assert config.SEASON_LABEL == "SEASON 2025-2026"
    assert len(config.CALENDAR) == 17
    assert len(config.DRIVERS) == 20
    assert len(config.TEAMS) == 10
    # Two drivers per team, every roster team is a configured team.
    team_names = {t.name for t in config.TEAMS}
    per_team: dict[str, int] = {}
    for d in config.DRIVERS:
        assert d["team"] in team_names
        per_team[d["team"]] = per_team.get(d["team"], 0) + 1
    assert all(n == 2 for n in per_team.values())
    # FE points: 25..1 with pole +3 and fastest lap +1.
    assert config.POINTS[1] == 25 and config.POINTS[10] == 1
    assert config.POLE_POINTS == 3 and config.FASTEST_LAP_POINTS == 1


def test_doubleheaders_share_venue_key():
    # Jeddah / Berlin / Monaco / Shanghai / Tokyo / London are doubleheaders:
    # consecutive rounds sharing a venue key.
    keys = [v.key for v in config.CALENDAR]
    for city_key in ("jeddah", "berlin", "monaco", "shanghai", "tokyo", "london"):
        idxs = [i for i, k in enumerate(keys) if k == city_key]
        assert len(idxs) == 2 and idxs[1] == idxs[0] + 1, city_key


def test_predictor_contract(real_source):
    from formula_e_predictions.predict import FEPredictor

    predictor = FEPredictor()
    predictor.fit(real_source, config.SEASON, upto_round=2)
    fc = predictor.predict(real_source, config.SEASON, 2)
    assert fc.season == config.SEASON and fc.round == 2
    assert len(fc.predicted_order) == 20
    assert set(fc.predicted_order.values()) == set(range(1, 21))
    assert fc.probabilities is not None
    assert abs(sum(fc.probabilities.p_win.values()) - 1.0) < 0.05
    assert fc.metadata["venue_kind"] in ("street", "circuit")
