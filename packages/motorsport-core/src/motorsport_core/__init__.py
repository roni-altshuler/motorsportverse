"""motorsport-core — shared ML & evaluation infrastructure for MotorsportVerse.

Extracted from the F1 Predictions (RaceIQ) flagship as the reusable, sport-
agnostic foundation that every MotorsportVerse project builds on:

- :mod:`~motorsport_core.interfaces` — DataSource / Predictor contracts.
- :mod:`~motorsport_core.calibration` — Plackett-Luce sampling + isotonic /
  stratified probability calibration.
- :mod:`~motorsport_core.registry` — file-backed model registry.
- :mod:`~motorsport_core.drift` / :mod:`~motorsport_core.promotion` —
  continuous-learning health monitoring + A/B promotion gate.
- :mod:`~motorsport_core.eval` — forward-time ranking metrics.
- :mod:`~motorsport_core.standings` — championship standings from results.
- :mod:`~motorsport_core.championship` — Monte Carlo title projection.
- :mod:`~motorsport_core.elo` / :mod:`~motorsport_core.conformal` /
  :mod:`~motorsport_core.hierarchical_bayes` — modelling building blocks.
- :mod:`~motorsport_core.leakage` — temporal leakage guards.
- :mod:`~motorsport_core.features` — skill priors + competitor history.
"""

__version__ = "0.2.0"

__all__ = [
    "interfaces",
    "calibration",
    "registry",
    "drift",
    "promotion",
    "conformal",
    "reliability",
    "hierarchical_bayes",
    "elo",
    "era",
    "leakage",
    "eval",
    "standings",
    "championship",
    "features",
]
