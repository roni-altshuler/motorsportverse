"""Tests for the Priority-2 reliability layer (models/reliability_model.py)."""
import numpy as np

from models.reliability_model import (
    ReliabilityModel, ReliabilityInputs, ReliabilityPrediction,
    classify_retirement, learned_mechanical_fraction, compute_reliability,
    FEATURE_NAMES,
)


# ── Retirement taxonomy ────────────────────────────────────────────────────
def test_classify_retirement_buckets():
    assert classify_retirement("Finished") == "finished"
    assert classify_retirement("+1 Lap") == "finished"
    assert classify_retirement("Lapped") == "finished"
    assert classify_retirement("Engine") == "mechanical"
    assert classify_retirement("Hydraulics") == "mechanical"
    assert classify_retirement("Gearbox") == "mechanical"
    assert classify_retirement("Accident") == "accident"
    assert classify_retirement("Collision damage") == "accident"
    assert classify_retirement("Puncture") == "accident"
    # Coarse / unknown causes stay honest.
    assert classify_retirement("Retired") == "other_dnf"
    assert classify_retirement("Did not start") == "other_dnf"
    assert classify_retirement(None) == "other_dnf"


def test_learned_mechanical_fraction_needs_minimum_sample():
    # Too few labels -> no learned fraction (falls back to prior downstream).
    assert learned_mechanical_fraction([("Monza", "Engine")]) == {}
    rows = [("Monza", "Engine")] * 6 + [("Monza", "Accident")] * 4
    learned = learned_mechanical_fraction(rows)
    assert "permanent" in learned
    assert learned["permanent"] == 0.6   # 6 mechanical / 10


# ── Synthetic training: signal recovery ────────────────────────────────────
def _history(n_drivers=12, n_rounds=30, reliable=("AAA", "BBB"), fragile=("ZZZ",)):
    """Build leakage-ordered (season, round, driver, pred, actual) rows where
    `fragile` drivers DNF often and `reliable` drivers almost never."""
    rng = np.random.default_rng(0)
    drivers = [f"D{i:02d}" for i in range(n_drivers)]
    drivers[:len(reliable)] = list(reliable)
    drivers[-len(fragile):] = list(fragile)
    rows = []
    for rnd in range(1, n_rounds + 1):
        for pos, drv in enumerate(drivers, start=1):
            if drv in fragile:
                dnf = rng.random() < 0.6
            elif drv in reliable:
                dnf = rng.random() < 0.03
            else:
                dnf = rng.random() < 0.15
            actual = None if dnf else pos
            rows.append((2025, rnd, drv, pos, actual))
    return rows


def test_fragile_driver_gets_higher_dnf_than_reliable():
    rows = _history()
    m = ReliabilityModel().fit(rows)
    assert m._fitted
    fragile = m.predict_one(ReliabilityInputs("ZZZ", 20, "Bahrain"))
    reliable = m.predict_one(ReliabilityInputs("AAA", 2, "Bahrain"))
    assert fragile.p_dnf > reliable.p_dnf
    assert fragile.p_dnf > 0.3
    assert reliable.p_dnf < 0.2


def test_probabilities_are_coherent():
    rows = _history()
    m = ReliabilityModel().fit(rows)
    p = m.predict_one(ReliabilityInputs("D05", 10, "Monaco"))
    assert 0.0 <= p.p_dnf <= 1.0
    assert abs(p.p_finish + p.p_dnf - 1.0) < 1e-9
    # mechanical + accident must reconstruct p_dnf
    assert abs(p.p_mechanical + p.p_accident - p.p_dnf) < 1e-9
    assert p.p_mechanical >= 0 and p.p_accident >= 0


def test_street_circuit_skews_accident_over_mechanical():
    rows = _history()
    m = ReliabilityModel().fit(rows)
    monaco = m.predict_one(ReliabilityInputs("D05", 10, "Monaco"))      # street
    monza = m.predict_one(ReliabilityInputs("D05", 10, "Italy"))        # permanent
    # Same driver/position: Monaco's DNF is more accident-weighted than Monza's.
    monaco_acc_share = monaco.p_accident / monaco.p_dnf
    monza_acc_share = monza.p_accident / monza.p_dnf
    assert monaco_acc_share > monza_acc_share


def test_learned_split_overrides_prior_when_supplied():
    rows = _history()
    status_rows = [("Italy", "Engine")] * 9 + [("Italy", "Accident")] * 1  # 90% mech
    m = ReliabilityModel().fit(rows, status_rows=status_rows)
    p = m.predict_one(ReliabilityInputs("D05", 10, "Italy"))
    # Learned permanent fraction (0.9) should dominate the mechanical share.
    assert p.p_mechanical / p.p_dnf > 0.8


# ── Cold start ─────────────────────────────────────────────────────────────
def test_cold_start_returns_base_rate_band():
    m = ReliabilityModel()  # never fitted
    p = m.predict_one(ReliabilityInputs("NEW", 11, "Bahrain"))
    assert 0.0 < p.p_dnf < 0.85
    assert abs(p.p_finish + p.p_dnf - 1.0) < 1e-9


def test_compute_reliability_missing_db_is_safe(tmp_path):
    preds = compute_reliability(tmp_path / "nope.duckdb", season=2026,
                                current_round=6,
                                inputs=[ReliabilityInputs("VER", 3, "Monaco")])
    assert "VER" in preds
    assert 0.0 < preds["VER"].p_dnf < 0.85


def test_feature_importance_exposes_named_coefficients():
    rows = _history()
    m = ReliabilityModel().fit(rows)
    coefs = m.coefficients()
    assert set(coefs).issubset(set(FEATURE_NAMES))
    assert "driver_recent_dnf_rate" in coefs


def test_prediction_as_dict_shape():
    p = ReliabilityPrediction("VER", 0.9, 0.1, 0.06, 0.04)
    d = p.as_dict()
    assert d == {"driver": "VER", "pFinish": 0.9, "pDnf": 0.1,
                 "pMechanical": 0.06, "pAccident": 0.04}
