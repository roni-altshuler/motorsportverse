"""Reliability layer — finish / DNF / mechanical / accident probabilities.

Priority-2 of the post-audit roadmap. The Round 1–5 audit showed that the
dominant prediction error is **attrition** (24/110 finishing slots were
DNF/DNS/Retired) that the pace model has no feature for. This module estimates,
per driver per race:

  * ``p_finish``      — probability the driver is classified at the finish
  * ``p_dnf``         — probability of NOT classifying (1 - p_finish)
  * ``p_mechanical``  — DNF attributable to a car/power-unit failure
  * ``p_accident``    — DNF attributable to a crash / collision

Design notes
------------
DNF probability is a logistic regression on a leakage-safe, data-supported
feature set:

  [0] driver_hist_dnf_rate   — career DNF rate, strictly prior rounds
  [1] driver_recent_dnf_rate — rolling 10-race DNF rate
  [2] team_dnf_rate          — the driver's team reliability (prior rounds)
  [3] circuit_attrition_prior— circuit chaos prior (track-archetype SC prob)
  [4] street_circuit         — 1.0 for street circuits (crash-prone)
  [5] rookie_factor          — 1.0 if the driver has < ROOKIE_RACES prior starts
  [6] weather_risk           — rain probability for the race
  [7] power_unit_age         — STUB (see below); neutral 0.0 until PU data lands

``power_unit_age`` is listed in the roadmap but no power-unit allocation data
exists in this repo, so it is wired as a documented neutral feature (always
0.0) rather than fabricated. The model trains and predicts without it
contributing signal; the slot is kept so real PU-age data can be dropped in.

Mechanical vs accident split
----------------------------
The available results data (FastF1 ``Status``) in this environment is coarse —
only ``Finished`` / ``Lapped`` / ``Retired`` / ``Did not start`` — with NO
mechanical-vs-accident granularity. We therefore do NOT fabricate a trained
mechanical/accident classifier. Instead ``p_dnf`` is split with a transparent,
circuit-conditioned prior (``mechanical_fraction``): street circuits skew toward
accidents, permanent circuits toward mechanical failures. ``RetirementTaxonomy``
classifies granular status strings when they ARE present, and
``ReliabilityModel.fit`` will learn the real per-archetype split the moment a
dataset with granular statuses is supplied — see ``learned_mechanical_fraction``.

Training data: ``data/history.duckdb::historical_predictions`` where
``actual_position IS NULL`` marks a DNF. Falls back to a base rate on cold start.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

import numpy as np

_BASE_RATE = 0.15            # 2018-2025 historical DNF rate (~336/2233)
_MIN_TRAIN_ROWS = 200
_HISTORY_WINDOW = 10         # rolling per-driver DNF window
ROOKIE_RACES = 5            # < this many prior starts => rookie
_PROB_FLOOR, _PROB_CEIL = 0.01, 0.85

# Circuit-conditioned mechanical fraction of DNFs (prior; used when granular
# status labels are unavailable). Street circuits => more accidents.
_MECH_FRACTION_PERMANENT = 0.62
_MECH_FRACTION_STREET = 0.38

FEATURE_NAMES = (
    "driver_hist_dnf_rate",
    "driver_recent_dnf_rate",
    "team_dnf_rate",
    "circuit_attrition_prior",
    "street_circuit",
    "rookie_factor",
    "weather_risk",
    "power_unit_age",      # stub — neutral 0.0 (no PU data in repo)
)


# ── Retirement-reason taxonomy (ready for granular status data) ────────────
_MECHANICAL_KEYWORDS = (
    "engine", "power unit", "pu", "gearbox", "transmission", "hydraulic",
    "brake", "suspension", "steering", "electrical", "electronics", "battery",
    "ers", "mgu", "turbo", "exhaust", "oil", "fuel", "cooling", "water",
    "driveshaft", "differential", "clutch", "wheel", "technical", "mechanical",
    "overheating", "vibration", "throttle", "radiator",
)
_ACCIDENT_KEYWORDS = (
    "accident", "collision", "contact", "crash", "spun", "spin", "damage",
    "puncture", "debris", "off", "barrier", "wall", "incident",
)


def classify_retirement(status: str) -> str:
    """Map a FastF1 ``Status`` string to a reliability class.

    Returns one of: ``finished``, ``mechanical``, ``accident``, ``other_dnf``.
    Coarse strings ('Retired', 'Did not start') resolve to ``other_dnf`` —
    the honest answer when the cause is unknown.
    """
    if status is None:
        return "other_dnf"
    s = str(status).strip().lower()
    if s == "finished" or s.startswith("+") or "lap" in s:
        return "finished"
    if any(k in s for k in _ACCIDENT_KEYWORDS):
        return "accident"
    if any(k in s for k in _MECHANICAL_KEYWORDS):
        return "mechanical"
    return "other_dnf"


@dataclass
class ReliabilityInputs:
    """Per-driver predict-time features for the upcoming race."""

    driver: str
    predicted_position: int
    circuit_key: str
    team: Optional[str] = None
    rain_probability: float = 0.0


@dataclass
class ReliabilityPrediction:
    driver: str
    p_finish: float
    p_dnf: float
    p_mechanical: float
    p_accident: float

    def as_dict(self) -> dict:
        return {
            "driver": self.driver,
            "pFinish": round(self.p_finish, 4),
            "pDnf": round(self.p_dnf, 4),
            "pMechanical": round(self.p_mechanical, 4),
            "pAccident": round(self.p_accident, 4),
        }


def _street_circuit(circuit_key: str) -> bool:
    try:
        from models.track_archetype import get_archetype
        arch = get_archetype(circuit_key)
        if arch is not None:
            return bool(getattr(arch, "street_circuit", False))
    except Exception:
        pass
    return circuit_key.lower() in {"monaco", "singapore", "azerbaijan", "baku",
                                   "saudi arabia", "miami", "las vegas"}


def _circuit_attrition_prior(circuit_key: str) -> float:
    """Circuit chaos prior in [0,1] (track-archetype safety-car probability)."""
    try:
        from models.track_archetype import get_archetype
        arch = get_archetype(circuit_key)
        if arch is not None:
            return float(getattr(arch, "safety_car_probability", 0.4))
    except Exception:
        pass
    return 0.4


def _mechanical_fraction(circuit_key: str,
                         learned: Optional[Mapping[str, float]] = None) -> float:
    street = _street_circuit(circuit_key)
    if learned:
        key = "street" if street else "permanent"
        if key in learned:
            return float(learned[key])
    return _MECH_FRACTION_STREET if street else _MECH_FRACTION_PERMANENT


def learned_mechanical_fraction(status_rows: Sequence[tuple]) -> Dict[str, float]:
    """Learn the street/permanent mechanical fraction from granular statuses.

    ``status_rows`` = iterable of ``(circuit_key, status_string)``. Rows whose
    status classifies as ``other_dnf`` are ignored (cause unknown). Returns
    ``{"street": frac, "permanent": frac}``; absent when no usable labels.
    """
    buckets: Dict[str, list] = {"street": [], "permanent": []}
    for circuit_key, status in status_rows:
        cls = classify_retirement(status)
        if cls not in ("mechanical", "accident"):
            continue
        key = "street" if _street_circuit(circuit_key) else "permanent"
        buckets[key].append(1.0 if cls == "mechanical" else 0.0)
    out: Dict[str, float] = {}
    for key, vals in buckets.items():
        if len(vals) >= 8:           # need a minimum sample to trust the split
            out[key] = float(np.mean(vals))
    return out


class ReliabilityModel:
    """Logistic DNF model over the expanded reliability feature set."""

    def __init__(self) -> None:
        self._model = None
        self._fitted = False
        self._driver_recent: Dict[str, list] = {}
        self._driver_career: Dict[str, list] = {}
        self._team_flags: Dict[str, list] = {}
        self._learned_mech: Dict[str, float] = {}

    # -- feature assembly ---------------------------------------------------
    def _features(self, *, hist_rate, recent_rate, team_rate, attrition,
                  street, rookie, weather) -> list:
        return [hist_rate, recent_rate, team_rate, attrition,
                1.0 if street else 0.0, 1.0 if rookie else 0.0,
                max(0.0, min(1.0, weather)), 0.0]   # last slot = power_unit_age stub

    def fit(self, rows: Sequence[tuple], *,
            team_map: Optional[Mapping[str, str]] = None,
            circuit_for_round: Optional[Mapping[tuple, str]] = None,
            status_rows: Optional[Sequence[tuple]] = None) -> "ReliabilityModel":
        """Fit on historical rows ``(season, round, driver, pred_pos, actual_pos)``.

        ``team_map`` maps driver -> team (for team reliability); ``circuit_for_round``
        maps (season, round) -> circuit_key (optional; for circuit attrition).
        ``status_rows`` (optional granular statuses) enables a learned mech split.
        """
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError:
            return self

        team_map = team_map or {}
        if status_rows:
            self._learned_mech = learned_mechanical_fraction(status_rows)

        X, y = [], []
        recent: Dict[str, list] = {}
        career: Dict[str, list] = {}
        team_flags: Dict[str, list] = {}
        for season_h, round_h, driver_h, pred_h, actual_h in rows:
            is_dnf = 1 if actual_h is None else 0
            r = recent.get(driver_h, [])
            c = career.get(driver_h, [])
            hist_rate = (sum(c) / len(c)) if c else _BASE_RATE
            recent_rate = (sum(r) / len(r)) if r else _BASE_RATE
            team = team_map.get(driver_h)
            tf = team_flags.get(team, []) if team else []
            team_rate = (sum(tf) / len(tf)) if tf else _BASE_RATE
            circuit = (circuit_for_round or {}).get((season_h, round_h), "")
            attrition = _circuit_attrition_prior(circuit) if circuit else 0.4
            street = _street_circuit(circuit) if circuit else False
            rookie = len(c) < ROOKIE_RACES
            X.append(self._features(hist_rate=hist_rate, recent_rate=recent_rate,
                                    team_rate=team_rate, attrition=attrition,
                                    street=street, rookie=rookie, weather=0.0))
            y.append(is_dnf)
            # update rolling state AFTER recording (leakage-safe)
            recent.setdefault(driver_h, []).append(is_dnf)
            recent[driver_h] = recent[driver_h][-_HISTORY_WINDOW:]
            career.setdefault(driver_h, []).append(is_dnf)
            if team:
                team_flags.setdefault(team, []).append(is_dnf)

        self._driver_recent, self._driver_career, self._team_flags = recent, career, team_flags

        y_arr = np.array(y, dtype=int)
        if len(y) >= _MIN_TRAIN_ROWS and y_arr.sum() >= 10 and (len(y) - y_arr.sum()) >= 10:
            # No class balancing: we want CALIBRATED absolute probabilities
            # (mean prediction ≈ base DNF rate), not a balanced risk score.
            model = LogisticRegression(max_iter=300, random_state=42)
            model.fit(np.array(X, dtype=float), y_arr)
            self._model = model
            self._fitted = True
        return self

    # -- prediction ---------------------------------------------------------
    def predict_one(self, item: ReliabilityInputs,
                    team_map: Optional[Mapping[str, str]] = None) -> ReliabilityPrediction:
        team_map = team_map or {}
        team = item.team or team_map.get(item.driver)
        c = self._driver_career.get(item.driver, [])
        r = self._driver_recent.get(item.driver, [])
        hist_rate = (sum(c) / len(c)) if c else _BASE_RATE
        recent_rate = (sum(r) / len(r)) if r else _BASE_RATE
        tf = self._team_flags.get(team, []) if team else []
        team_rate = (sum(tf) / len(tf)) if tf else _BASE_RATE
        attrition = _circuit_attrition_prior(item.circuit_key)
        street = _street_circuit(item.circuit_key)
        rookie = len(c) < ROOKIE_RACES

        if self._fitted and self._model is not None:
            feats = np.array([self._features(
                hist_rate=hist_rate, recent_rate=recent_rate, team_rate=team_rate,
                attrition=attrition, street=street, rookie=rookie,
                weather=item.rain_probability)], dtype=float)
            p_dnf = float(self._model.predict_proba(feats)[0, 1])
        else:
            # Cold-start blend of the signals we trust.
            p_dnf = float(np.clip(
                0.5 * recent_rate + 0.2 * team_rate + 0.2 * attrition
                + 0.1 * item.rain_probability + (0.05 if rookie else 0.0),
                0.0, 1.0))

        p_dnf = max(_PROB_FLOOR, min(_PROB_CEIL, p_dnf))
        mech_frac = _mechanical_fraction(item.circuit_key, self._learned_mech)
        return ReliabilityPrediction(
            driver=item.driver,
            p_finish=1.0 - p_dnf,
            p_dnf=p_dnf,
            p_mechanical=p_dnf * mech_frac,
            p_accident=p_dnf * (1.0 - mech_frac),
        )

    def predict(self, inputs: Sequence[ReliabilityInputs],
                team_map: Optional[Mapping[str, str]] = None
                ) -> Dict[str, ReliabilityPrediction]:
        return {it.driver: self.predict_one(it, team_map) for it in inputs}

    def coefficients(self) -> Dict[str, float]:
        """Feature importance = logistic coefficients (signed log-odds)."""
        if not self._fitted or self._model is None:
            return {}
        return {name: float(coef) for name, coef in
                zip(FEATURE_NAMES, self._model.coef_[0])}


def compute_reliability(history_db_path: Path, *, season: int, current_round: int,
                        inputs: Sequence[ReliabilityInputs],
                        team_map: Optional[Mapping[str, str]] = None
                        ) -> Dict[str, ReliabilityPrediction]:
    """Convenience: load prior history, fit, predict. Cold-start safe."""
    model = ReliabilityModel()
    rows: list = []
    try:
        import duckdb
        history_db_path = Path(history_db_path)
        if history_db_path.exists():
            con = duckdb.connect(str(history_db_path), read_only=True)
            try:
                rows = con.execute(
                    """
                    SELECT season, round, driver, predicted_position, actual_position
                    FROM historical_predictions
                    WHERE (season, round) < (?, ?)
                    ORDER BY season, round, driver
                    """,
                    (season, current_round),
                ).fetchall()
            finally:
                con.close()
    except ImportError:
        rows = []
    model.fit(rows, team_map=team_map)
    return model.predict(inputs, team_map=team_map)


__all__ = [
    "ReliabilityInputs", "ReliabilityPrediction", "ReliabilityModel",
    "classify_retirement", "learned_mechanical_fraction", "compute_reliability",
    "FEATURE_NAMES",
]
