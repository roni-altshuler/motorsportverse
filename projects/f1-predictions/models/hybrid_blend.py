"""Hybrid blend of historical priors and current-weekend signals.

The user's product brief:

  > Investigate whether the model should:
  >   * dynamically weight track-specific historical performance
  >   * adapt weighting based on circuit type
  >   * increase the importance of current qualifying pace closer to race start

This module captures that intuition as a small policy layer the
prediction pipeline can consult: given a circuit and the weekend phase
we're in, return a (historical, weekend) weight pair.  The Layer 1
ensemble's per-feature contribution is multiplied by this weight at
post-processing time.

Why a separate module
---------------------
``train_ensemble`` already fits to feature columns that include both
historical priors AND current weekend signals (qualifying time, FP3
pace when available).  The model itself learns SOME weighting, but it
has no built-in mechanism to *adapt* that weighting per circuit or per
phase — a Monaco prediction made on Tuesday should lean far more on
historical Monaco specialists than a Tuesday prediction for Bahrain.
This module is the explicit knob.

The numbers below are honest priors based on the product brief, not
fitted weights.  Once enough forward-eval rounds accumulate, they can
be replaced with learned values via a per-circuit hierarchical model
(see ``models/per_circuit.py``).
"""
from __future__ import annotations

from dataclasses import dataclass


# Circuits where single-lap qualifying pace is the dominant predictor
# of race outcome — overtaking is rare, the starting grid largely
# decides the race.  Weight should swing hard to weekend signal once
# we have it.
QUALI_DOMINANT = {
    "Monaco",
    "Hungary",
    "Singapore",
    "Spain",
    "Barcelona",
    "BarcelonaCatalunya",
    "Imola",
    "EmiliaRomagna",
}

# Circuits with strong historical driver specialists — track
# compatibility / driver style matters more than recent form.
SPECIALIST_HEAVY = {
    "Monaco",
    "Hungary",
    "Brazil",
    "Suzuka",
    "Japan",
    "Spa",
    "Belgium",
}

# Circuits where strategy + tyre wear + overtaking create high
# variance — historical track form matters less, recent constructor
# pace + weather matters more.
HIGH_VARIANCE = {
    "Bahrain",
    "Saudi",
    "SaudiArabia",
    "Miami",
    "Imola",
    "Austria",
    "Mexico",
    "MexicoCity",
    "USA",
    "AbuDhabi",
    "Australia",
    "Canada",
}


@dataclass(frozen=True)
class BlendWeights:
    """Weights summing to 1.0 across the two signal categories."""

    historical: float
    weekend: float

    def __post_init__(self) -> None:
        total = self.historical + self.weekend
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"BlendWeights must sum to 1.0, got {total:.4f}")


def blend_for(circuit_key: str, phase: str) -> BlendWeights:
    """Return the blend weights for a given (circuit, phase) tuple.

    ``phase`` is one of ``"preview"`` (pre-quali), ``"post-quali"``,
    ``"post-race"``.  Pre-quali means we have NO current-weekend lap
    times — everything is historical / synthetic, so the weight is
    pinned at (1.0, 0.0) regardless of circuit.
    """
    phase = (phase or "preview").lower()
    if phase == "preview":
        return BlendWeights(historical=1.0, weekend=0.0)

    if phase == "post-race":
        # The race has run; the historical signal still informs the
        # explainability narrative but the weekend signal owns the
        # outcome.  Used mostly for the predicted-vs-actual breakdown.
        return BlendWeights(historical=0.20, weekend=0.80)

    # post-quali: actual qualifying lap times are in the model. This is
    # the strongest single signal of race pace we get all weekend.
    is_quali_dominant = circuit_key in QUALI_DOMINANT
    is_specialist = circuit_key in SPECIALIST_HEAVY
    is_high_variance = circuit_key in HIGH_VARIANCE

    if is_quali_dominant:
        # Monaco / Hungary / Singapore: qualifying near-perfectly
        # decides the race. Lean hard on weekend signal.
        return BlendWeights(historical=0.20, weekend=0.80)
    if is_specialist:
        # Brazil / Spa / Suzuka / Japan: respect the historical
        # specialists (Hamilton at Brazil, Verstappen at Suzuka).
        return BlendWeights(historical=0.45, weekend=0.55)
    if is_high_variance:
        # Bahrain / Saudi / Miami / Canada: strategy & variance
        # dominate; weekend pace is informative but not decisive.
        return BlendWeights(historical=0.40, weekend=0.60)

    # Default: weekend signal modestly dominates once available.
    return BlendWeights(historical=0.35, weekend=0.65)


def apply_blend(
    historical_score: float,
    weekend_score: float,
    *,
    circuit_key: str,
    phase: str,
) -> float:
    """Combine the two scores under the blend policy."""
    w = blend_for(circuit_key, phase)
    return w.historical * historical_score + w.weekend * weekend_score
