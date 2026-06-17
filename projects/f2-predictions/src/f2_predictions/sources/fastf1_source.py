"""FastF1-backed F2 results — best-effort, probed at runtime.

FastF1's public API targets Formula 1; its Formula 2 coverage is partial and
version-dependent and there is no stable documented way to load an F2 session's
classification. So this source *probes* and returns ``None`` on any failure
(missing dependency, unsupported session, empty frame, rate-limit) rather than
guessing — ``None`` tells the composite to fall through to the next source. The
mapping below is written so that if/when FastF1 exposes F2 results, only this file
changes.
"""
from __future__ import annotations

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "fastf1"

# FastF1 session codes for the two F2 races on a weekend.
_SESSION_CODE = {0: "Sprint", 1: "Feature"}


class FastF1F2Source:
    name = SOURCE_NAME

    def results(self, year: int, round: int, race_index: int = 1) -> list[Result] | None:
        try:
            import fastf1  # noqa: F401
        except ImportError:
            return None
        try:
            return self._load(year, round, race_index)
        except Exception:
            # Any failure → defer to the next source. Never raise into the pipeline.
            return None

    def _load(self, year: int, round: int, race_index: int) -> list[Result] | None:
        """Attempt to load an F2 classification via FastF1.

        FastF1 does not currently expose F2 sessions, so this returns ``None``.
        Kept as the single integration point: when F2 session loading lands, fill
        this in to return ``Result`` rows (mapping driver code, position, grid,
        status) and the rest of the stack works unchanged.
        """
        _ = (year, round, _SESSION_CODE.get(race_index), config.SPORT)
        return None
