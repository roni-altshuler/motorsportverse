"""Tests for the Priority-3 race volatility model (models/race_volatility.py)."""
from models.race_volatility import (
    circuit_volatility, compute_circuit_status_rates, volatility_table,
    CircuitVolatility,
)


def test_outputs_bounded_and_coherent():
    v = circuit_volatility("Monaco")
    for x in (v.safety_car_probability, v.vsc_probability,
              v.red_flag_probability, v.volatility_score):
        assert 0.0 <= x <= 1.0


def test_monaco_low_volatility_despite_high_safety_car():
    """Monaco: high SC probability but qualifying-locked → LOW volatility.
    (Mirrors the learned behaviour asserted in test_volatility_model.py.)"""
    monaco = circuit_volatility("Monaco")
    monza = circuit_volatility("Italy")
    # Monaco's incident probability is high...
    assert monaco.safety_car_probability >= monza.safety_car_probability
    # ...but its race-order volatility is LOWER (overtaking near-impossible).
    assert monaco.volatility_score < circuit_volatility("Bahrain").volatility_score


def test_street_circuit_has_high_safety_car_prob():
    for street in ("Monaco", "Singapore", "Azerbaijan"):
        assert circuit_volatility(street).safety_car_probability >= 0.5


def test_empirical_rates_blend_toward_observations():
    # A circuit the prior thinks is calm, but empirically had SC every time.
    base = circuit_volatility("Italy").safety_car_probability
    emp = {"Italy": {"sc": 1.0, "vsc": 1.0, "red": 0.5, "n": 8}}
    blended = circuit_volatility("Italy", empirical=emp).safety_car_probability
    assert blended > base                      # pulled up toward 1.0
    assert blended <= 1.0


def test_empirical_shrinkage_small_sample_stays_near_prior():
    base = circuit_volatility("Italy").safety_car_probability
    emp_small = {"Italy": {"sc": 1.0, "vsc": 0.0, "red": 0.0, "n": 1}}
    emp_large = {"Italy": {"sc": 1.0, "vsc": 0.0, "red": 0.0, "n": 20}}
    small = circuit_volatility("Italy", empirical=emp_small).safety_car_probability
    large = circuit_volatility("Italy", empirical=emp_large).safety_car_probability
    # Larger sample moves further from the prior.
    assert abs(large - base) > abs(small - base)


def test_compute_circuit_status_rates_from_loader():
    # Fake track_status "Status" columns per (year, circuit).
    fake = {
        (2024, "Monaco"): ["1", "4", "1"],       # SC
        (2023, "Monaco"): ["1", "5", "4"],       # SC + red
        (2024, "Italy"): ["1", "2", "1"],        # nothing
    }
    def loader(year, gp):
        return fake.get((year, gp))
    rates = compute_circuit_status_rates(loader, list(fake.keys()))
    assert rates["Monaco"]["n"] == 2
    assert rates["Monaco"]["sc"] == 1.0          # SC in both Monaco races
    assert rates["Monaco"]["red"] == 0.5         # red flag in 1 of 2
    assert rates["Italy"]["sc"] == 0.0


def test_loader_failure_is_skipped():
    def loader(year, gp):
        if gp == "Boom":
            raise RuntimeError("session unavailable")
        return ["1", "4"]
    rates = compute_circuit_status_rates(loader, [(2024, "Boom"), (2024, "Spain")])
    assert "Boom" not in rates
    assert rates["Spain"]["sc"] == 1.0


def test_volatility_table_covers_all_requested():
    table = volatility_table(["Monaco", "Italy", "Bahrain"])
    assert set(table) == {"Monaco", "Italy", "Bahrain"}
    assert all(isinstance(v, CircuitVolatility) for v in table.values())


def test_as_dict_shape():
    d = circuit_volatility("Monaco").as_dict()
    assert set(d) == {"circuit", "safetyCarProbability", "vscProbability",
                      "redFlagProbability", "volatilityScore", "nEmpirical"}
