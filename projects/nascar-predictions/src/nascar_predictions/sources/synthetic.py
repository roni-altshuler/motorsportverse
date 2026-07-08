"""Synthetic NASCAR results — the deterministic fallback and test fixture.

Each race is a seeded draw from ``config._TRUTH_PACE`` plus per-race noise,
deterministic in ``(year, round)``. The noise scale varies by track type —
superspeedway pack racing is close to a lottery, road courses reward the
specialists — so the offline pipeline exercises the same track-type
calibration strata the real feed produces, and a seeded slice of the field
"retires" (non-Running status) so the DNF head has signal even offline. It is
the always-available bottom of the source stack, so the pipeline never breaks
while a real feed is being validated. The predictor never sees
``_TRUTH_PACE`` — it only ever reads these classified results (leakage-safe).
"""
from __future__ import annotations

import numpy as np

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "synthetic"

_NOISE = {"superspeedway": 1.10, "intermediate": 0.55, "short": 0.60, "road": 0.50}
_DNF_RATE = {"superspeedway": 0.18, "intermediate": 0.07, "short": 0.09, "road": 0.07}


class SyntheticNascarSource:
    name = SOURCE_NAME

    def results(self, year: int, round: int, race_index: int = 0) -> list[Result]:
        """Classified order; ``[]`` for rounds not yet run. Never ``None`` —
        this is the fallback source, so it always answers.

        Only the ACTIVE season is synthesised: past seasons come exclusively
        from real snapshots (fabricating history would poison the Elo seed and
        the historical backtest), so any other year answers "no rounds".
        NASCAR classifies every car, so retirees still carry positions — the
        synthetic generator marks a seeded slice with a non-Running status.
        """
        if year != config.SEASON or round > config.COMPLETED_ROUNDS or round < 1:
            return []
        order, dnf = self._sample(year, round)
        return [
            Result(
                competitor=code,
                position=pos,
                grid=pos,
                status="Accident" if code in dnf else "Running",
                points=None,
            )
            for pos, code in enumerate(order, start=1)
        ]

    def _sample(self, year: int, round: int) -> tuple[list[str], set[str]]:
        codes = list(config._TRUTH_PACE.keys())
        pace = np.array([config._TRUTH_PACE[c] for c in codes], dtype=float)
        seed = (year * 1000 + round * 10) & 0xFFFFFFFF
        rng = np.random.default_rng(seed)
        meta = config.CALENDAR_META.get(round, {})
        tt = meta.get("trackType", "intermediate")
        noise = rng.normal(0.0, _NOISE.get(tt, 0.55), size=pace.shape)
        # Seeded retirements: retirees sink toward the back of the order.
        dnf_mask = rng.random(pace.shape) < _DNF_RATE.get(tt, 0.08)
        ranked_idx = np.argsort(pace + noise + 50.0 * dnf_mask)
        order = [codes[i] for i in ranked_idx]
        dnf = {codes[i] for i in np.flatnonzero(dnf_mask)}
        return order, dnf
