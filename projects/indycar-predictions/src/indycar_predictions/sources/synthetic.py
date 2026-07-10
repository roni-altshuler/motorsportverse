"""Synthetic IndyCar results — the deterministic fallback and test fixture.

Each race is a seeded draw from ``config._TRUTH_PACE`` plus per-race noise,
deterministic in ``(year, round)``. The noise/attrition scales vary by track
type — oval pack racing is closer to a lottery and retires more cars than a
road course — so the offline pipeline exercises the same track-type strata the
real data produces. It is the always-available bottom of the source stack;
because the committed history files cover every completed round, synthetic
results only ever stand in when the snapshot is deliberately absent (tests /
a hypothetical fresh season with zero curated rounds). The predictor never
sees ``_TRUTH_PACE`` — it only ever reads these classified results
(leakage-safe).
"""
from __future__ import annotations

import numpy as np

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "synthetic"

_NOISE = {"oval": 0.95, "road": 0.50, "street": 0.60}
_DNF_RATE = {"oval": 0.18, "road": 0.09, "street": 0.11}


class SyntheticIndycarSource:
    name = SOURCE_NAME

    def results(self, year: int, round: int, race_index: int = 0) -> list[Result]:
        """Classified order; ``[]`` for rounds not yet run. Never ``None`` —
        this is the fallback source, so it always answers.

        Only the ACTIVE season is synthesised: past seasons come exclusively
        from the committed history files (fabricating history would poison the
        Elo seed and the historical backtest), so any other year answers "no
        rounds". IndyCar classifies every car, so retirees still carry
        positions — the generator marks a seeded slice with a non-running
        status.
        """
        if year != config.SEASON or round > config.COMPLETED_ROUNDS or round < 1:
            return []
        order, dnf = self._sample(year, round)
        return [
            Result(
                competitor=code,
                position=pos,
                grid=pos,
                status="Contact" if code in dnf else "Running",
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
        tt = meta.get("trackType", "road")
        noise = rng.normal(0.0, _NOISE.get(tt, 0.55), size=pace.shape)
        # Seeded retirements: retirees sink toward the back of the order.
        dnf_mask = rng.random(pace.shape) < _DNF_RATE.get(tt, 0.10)
        ranked_idx = np.argsort(pace + noise + 50.0 * dnf_mask)
        order = [codes[i] for i in ranked_idx]
        dnf = {codes[i] for i in np.flatnonzero(dnf_mask)}
        return order, dnf
