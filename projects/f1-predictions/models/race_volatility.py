"""Race volatility / chaos model — Priority-3 of the post-audit roadmap.

The objective is NOT to predict exact incidents but to estimate how likely a
race is to deviate from the expected pace-based finishing order. Outputs per
circuit:

  * ``safety_car_probability`` — P(at least one full Safety Car)
  * ``vsc_probability``        — P(at least one Virtual Safety Car)
  * ``red_flag_probability``   — P(a red flag)
  * ``volatility_score``       — [0,1] expected deviation from pace order

Two sources, combined:

1. **Track-archetype priors** ([`models/track_archetype.py`]) — historically
   grounded per-circuit `safety_car_probability`, `qualifying_importance`,
   `overtaking_difficulty`, `tire_deg_sensitivity`. These are the canonical
   priors and the default.
2. **Empirical rates from FastF1 ``track_status``** — ``compute_circuit_status_rates``
   aggregates real SC/VSC/red-flag occurrences (codes 4 / 6,7 / 5) across cached
   races into per-circuit frequencies. When supplied, empirical rates are blended
   with the prior (shrinkage by sample size) so a circuit seen only a few times
   doesn't swing wildly.

Volatility-score rationale (matches the learned `volatility_model.py` behaviour):
a race deviates from pace order when interruptions reshuffle it (SC/VSC) AND
when track position is easy to lose. Monaco has a high SC prob but is
qualifying-locked (overtaking ~impossible), so its *volatility* is LOW even
though its *incident* probability is high — the score encodes exactly that.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Sequence

# Track-status codes (FastF1 `session.track_status`).
SC_CODE = "4"
RED_CODE = "5"
VSC_CODES = ("6", "7")

# Volatility-score weights (sum to 1): how much each driver contributes to
# "deviation from pace order".
_W_SC = 0.45            # interruptions reshuffle the field
_W_LOSE_POS = 0.35      # ease of losing track position (1 - qualifying lock)
_W_DEG = 0.20           # tyre-deg sensitivity → strategy divergence
# Shrinkage strength for blending empirical rates with the archetype prior.
_SHRINKAGE = 4.0


@dataclass
class CircuitVolatility:
    circuit_key: str
    safety_car_probability: float
    vsc_probability: float
    red_flag_probability: float
    volatility_score: float
    n_empirical: int = 0

    def as_dict(self) -> dict:
        return {
            "circuit": self.circuit_key,
            "safetyCarProbability": round(self.safety_car_probability, 3),
            "vscProbability": round(self.vsc_probability, 3),
            "redFlagProbability": round(self.red_flag_probability, 3),
            "volatilityScore": round(self.volatility_score, 3),
            "nEmpirical": self.n_empirical,
        }


def _archetype(circuit_key: str):
    try:
        from models.track_archetype import get_archetype
        return get_archetype(circuit_key)
    except Exception:
        return None


def _prior_sc(circuit_key: str) -> float:
    arch = _archetype(circuit_key)
    if arch is not None:
        return float(getattr(arch, "safety_car_probability", 0.4))
    return 0.4


def _qualifying_importance(circuit_key: str) -> float:
    arch = _archetype(circuit_key)
    if arch is not None:
        return float(getattr(arch, "qualifying_importance", 0.5))
    return 0.5


def _tire_deg(circuit_key: str) -> float:
    arch = _archetype(circuit_key)
    if arch is not None:
        return float(getattr(arch, "tire_deg_sensitivity", 0.5))
    return 0.5


def _blend(prior: float, empirical: Optional[float], n: int) -> float:
    """Shrinkage blend: empirical pulls the prior proportional to sample size."""
    if empirical is None or n <= 0:
        return prior
    w = n / (n + _SHRINKAGE)
    return float(max(0.0, min(1.0, w * empirical + (1.0 - w) * prior)))


def compute_circuit_status_rates(
    session_loader,
    pairs: Sequence[tuple],
) -> Dict[str, dict]:
    """Aggregate empirical SC/VSC/red-flag rates per circuit from race sessions.

    ``session_loader`` is a callable ``(year, gp_key) -> track_status_df`` (a
    DataFrame with a ``Status`` column), or returns ``None`` on failure — this
    keeps FastF1 out of the module so it stays unit-testable. ``pairs`` is an
    iterable of ``(year, gp_key)``. Returns ``{gp_key: {sc, vsc, red, n}}``
    where each rate is the fraction of that circuit's races showing the event.
    """
    acc: Dict[str, dict] = {}
    for year, gp_key in pairs:
        try:
            ts = session_loader(year, gp_key)
        except Exception:
            ts = None
        if ts is None:
            continue
        codes = {str(c) for c in ts}
        rec = acc.setdefault(gp_key, {"sc": 0, "vsc": 0, "red": 0, "n": 0})
        rec["n"] += 1
        rec["sc"] += 1 if SC_CODE in codes else 0
        rec["vsc"] += 1 if any(c in codes for c in VSC_CODES) else 0
        rec["red"] += 1 if RED_CODE in codes else 0
    out: Dict[str, dict] = {}
    for gp_key, rec in acc.items():
        n = rec["n"]
        out[gp_key] = {
            "sc": rec["sc"] / n if n else None,
            "vsc": rec["vsc"] / n if n else None,
            "red": rec["red"] / n if n else None,
            "n": n,
        }
    return out


def circuit_volatility(
    circuit_key: str,
    empirical: Optional[Mapping[str, dict]] = None,
) -> CircuitVolatility:
    """Combined chaos estimate for a circuit (prior, optionally blended)."""
    emp = (empirical or {}).get(circuit_key, {})
    n = int(emp.get("n", 0) or 0)

    sc = _blend(_prior_sc(circuit_key), emp.get("sc"), n)
    # VSC/red-flag priors derive from SC prior when no archetype field exists.
    vsc = _blend(min(1.0, _prior_sc(circuit_key) * 0.8), emp.get("vsc"), n)
    red = _blend(0.12 if _qualifying_importance(circuit_key) > 0.7 else 0.06,
                 emp.get("red"), n)

    lose_pos = 1.0 - _qualifying_importance(circuit_key)
    score = (_W_SC * sc + _W_LOSE_POS * lose_pos + _W_DEG * _tire_deg(circuit_key))
    score = float(max(0.0, min(1.0, score)))
    return CircuitVolatility(
        circuit_key=circuit_key,
        safety_car_probability=sc,
        vsc_probability=vsc,
        red_flag_probability=red,
        volatility_score=score,
        n_empirical=n,
    )


def volatility_table(circuits: Iterable[str],
                     empirical: Optional[Mapping[str, dict]] = None
                     ) -> Dict[str, CircuitVolatility]:
    return {c: circuit_volatility(c, empirical) for c in circuits}


__all__ = [
    "CircuitVolatility", "circuit_volatility", "compute_circuit_status_rates",
    "volatility_table", "SC_CODE", "RED_CODE", "VSC_CODES",
]
