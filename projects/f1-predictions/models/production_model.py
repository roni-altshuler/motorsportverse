"""Production model facade — the Phase 10 freeze entry point.

After the Phases 5-9 architecture sweep, the strongest variant on every
backtest was ``regime_routed_with_weekend_static``: Phase-5 regime
routing on top of an elite head trained over the 7-column Phase-7
static weekend feature set. This module wraps that pipeline as a
stable, deterministic callable so production callers
(``gp_weekend.py`` / ``export_website_data.py``) can opt in via a
feature flag.

Single source of truth for the production prediction path.

Feature flag
------------
The flag is the environment variable
``F1_PRODUCTION_MODEL_ENABLED``. It defaults to "0" (off). Set it to
"1" before invoking the production pipeline to route predictions
through this module. Defaulting OFF means the existing live behaviour
is unchanged until the flag is flipped — flip can be staged through
CI / config rather than baked into source.

Determinism
-----------
The underlying variant uses fixed-seed sklearn classifiers and a
rule-based regime router. Inputs (round number, predicted positions,
weekend feature parquet) being identical produces identical outputs.
There is no random state added by this module.

Versioning
----------
``PRODUCTION_MODEL_VERSION`` is bumped any time the wrapped variant or
the weekend feature column set changes. Bumping the version is the
trigger for re-running the freeze benchmark.

Do NOT modify
-------------
Don't change the wrapped variant or the column set in this module
without:

1. Re-running ``python benchmark_models.py run --seasons 2024 2025`` and
   showing the new candidate beats ``regime_routed_with_weekend_static``
   on aggregate winner-hit by at least +1pp with no per-season
   regression beyond 1pp.
2. Bumping ``PRODUCTION_MODEL_VERSION``.
3. Updating ``docs/ARCHITECTURE_AUDIT.md`` with the new freeze decision.

This contract is what makes ``F1_PRODUCTION_MODEL_ENABLED`` safe to
flip without coordination.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np


PRODUCTION_MODEL_VERSION = "2026.07.phase7-static"
PRODUCTION_MODEL_VARIANT = "regime_routed_with_weekend_static"
FEATURE_FLAG_ENV = "F1_PRODUCTION_MODEL_ENABLED"


if TYPE_CHECKING:  # pragma: no cover - typing only
    from benchmark_models import RoundFrame


def is_enabled() -> bool:
    """Return True iff the production model feature flag is set.

    Reads ``$F1_PRODUCTION_MODEL_ENABLED``. Anything that parses as
    truthy ("1", "true", "yes", "on", case-insensitive) enables the
    flag; everything else (including unset) leaves it disabled.
    """
    raw = os.environ.get(FEATURE_FLAG_ENV, "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ProductionPrediction:
    """One round's frozen production prediction payload.

    Stable schema — bumping ``PRODUCTION_MODEL_VERSION`` is the protocol
    for changing this shape. Callers can rely on these fields being
    present and meaning what they say.
    """

    season: int
    round: int
    drivers: tuple[str, ...]
    predicted_positions: tuple[int, ...]
    model_version: str = PRODUCTION_MODEL_VERSION
    model_variant: str = PRODUCTION_MODEL_VARIANT


def predict_for_round(
    frame: "RoundFrame",
    prior: list["RoundFrame"],
) -> ProductionPrediction:
    """Produce a frozen Phase-7-static prediction for one round.

    Thin facade over
    :func:`benchmark_models.predict_regime_routed_with_weekend_static`
    that packages the output in a stable schema. Importing
    ``benchmark_models`` is deferred so this module can be loaded
    without dragging in the full research surface.
    """
    from benchmark_models import predict_regime_routed_with_weekend_static

    raw_ranks = predict_regime_routed_with_weekend_static(frame, prior)
    raw_ranks = np.asarray(raw_ranks, dtype=int)
    drivers = tuple(frame.df["driver"].tolist())
    return ProductionPrediction(
        season=int(frame.season),
        round=int(frame.round),
        drivers=drivers,
        predicted_positions=tuple(int(p) for p in raw_ranks),
    )


__all__ = [
    "FEATURE_FLAG_ENV",
    "PRODUCTION_MODEL_VARIANT",
    "PRODUCTION_MODEL_VERSION",
    "ProductionPrediction",
    "is_enabled",
    "predict_for_round",
]
