"""Synthetic F3 results — the deterministic fallback and test fixture.

This is the latent-pace model the project shipped with: each scored race is a
seeded draw from ``config._TRUTH_PACE`` plus per-race noise, deterministic in
``(year, round, race_index)``. It is the always-available bottom of the source
stack, so the pipeline never breaks while a real feed is being validated. The
predictor never sees ``_TRUTH_PACE`` — it only ever reads these classified
results (leakage-safe).
"""
from __future__ import annotations

import numpy as np

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "synthetic"


class SyntheticF3Source:
    name = SOURCE_NAME

    def results(self, year: int, round: int, race_index: int = 1) -> list[Result]:
        """Classified order; ``[]`` for rounds not yet run. Never ``None`` — this
        is the fallback source, so it always answers."""
        if round > config.COMPLETED_ROUNDS or round < 1:
            return []
        order = self._sample_order(year, round, race_index)
        return [
            Result(competitor=code, position=pos, grid=pos, status="Finished", points=None)
            for pos, code in enumerate(order, start=1)
        ]

    def _sample_order(self, year: int, round: int, race_index: int) -> list[str]:
        codes = list(config._TRUTH_PACE.keys())
        pace = np.array([config._TRUTH_PACE[c] for c in codes], dtype=float)
        seed = (year * 1000 + round * 10 + race_index) & 0xFFFFFFFF
        rng = np.random.default_rng(seed)
        noise = rng.normal(0.0, 0.45, size=pace.shape)
        ranked_idx = np.argsort(pace + noise)
        return [codes[i] for i in ranked_idx]
