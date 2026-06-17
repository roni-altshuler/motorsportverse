"""The race-simulator seam is dormant and data-gated — verify it stays a no-op.

F2 has no lap-by-lap telemetry, so the seam must report no data and return None
(the signal the pipeline reads as "fall back to Plackett-Luce"), never raising.
"""
from f2_predictions import config, train_race_pace
from f2_predictions.datasource import F2DataSource


def test_lap_data_is_not_available_today():
    source = F2DataSource()
    assert train_race_pace.lap_data_available(source, config.SEASON) is False


def test_race_simulator_flag_defaults_off():
    assert config.USE_RACE_SIMULATOR is False


def test_train_race_pace_no_ops_without_lap_data():
    source = F2DataSource()
    rounds = list(range(1, config.COMPLETED_ROUNDS + 1))
    assert train_race_pace.train_race_pace(source, config.SEASON, rounds) is None


def test_gate_opens_when_a_lap_feed_appears(monkeypatch):
    """If a source grows a lap hook AND the flag is on, the gate opens (then the
    trainer tries to load data — which is still NotImplemented, so it returns None
    cleanly rather than crashing the pipeline)."""
    source = F2DataSource()
    monkeypatch.setattr(config, "USE_RACE_SIMULATOR", True)
    monkeypatch.setattr(source, "lap_data_for_round", lambda *a, **k: [], raising=False)
    assert train_race_pace.lap_data_available(source, config.SEASON) is True
    # No real data yet → still None, no exception.
    assert train_race_pace.train_race_pace(source, config.SEASON, [1]) is None
