"""Synthetic FE results — the deterministic fallback and test fixture.

Each race is a seeded draw from ``config._TRUTH_PACE`` plus per-race noise,
deterministic in ``(year, round)``. Street rounds draw with a wider noise
scale than permanent circuits — FE's walls-and-restarts variance — so the
offline pipeline exercises the same street/circuit calibration strata the real
feed produces. It is the always-available bottom of the source stack, so the
pipeline never breaks while a real feed is being validated. The predictor
never sees ``_TRUTH_PACE`` — it only ever reads these classified results
(leakage-safe).
"""
from __future__ import annotations

import numpy as np

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "synthetic"

_NOISE = {"street": 0.60, "circuit": 0.40}


class SyntheticFESource:
    name = SOURCE_NAME

    def results(self, year: int, round: int, race_index: int = 0) -> list[Result]:
        """Classified order; ``[]`` for rounds not yet run. Never ``None`` —
        this is the fallback source, so it always answers.

        Only the ACTIVE season is synthesised: past seasons come exclusively
        from real snapshots (fabricating history would poison the Elo seed and
        the historical backtest), so any other year answers "no rounds".
        """
        if year != config.SEASON or round > config.COMPLETED_ROUNDS or round < 1:
            return []
        order = self._sample_order(year, round)
        return [
            Result(competitor=code, position=pos, grid=pos, status="Finished", points=None)
            for pos, code in enumerate(order, start=1)
        ]

    def _sample_order(self, year: int, round: int) -> list[str]:
        codes = list(config._TRUTH_PACE.keys())
        pace = np.array([config._TRUTH_PACE[c] for c in codes], dtype=float)
        seed = (year * 1000 + round * 10) & 0xFFFFFFFF
        rng = np.random.default_rng(seed)
        kind = "street"
        if 1 <= round <= len(config.CALENDAR):
            kind = getattr(config.CALENDAR[round - 1], "kind", "street") or "street"
        noise = rng.normal(0.0, _NOISE.get(str(kind), 0.60), size=pace.shape)
        ranked_idx = np.argsort(pace + noise)
        return [codes[i] for i in ranked_idx]
