"""Official FIA F2 timing/results — scrape-shaped, opt-in, best-effort.

The authoritative F2 results live on fiaformula2.com, but there is no stable
public API contract — the timing JSON is undocumented and changes without notice.
This source is therefore a clearly-marked integration point that defaults to
``None`` (defer to the next source) and only attempts a live fetch when a result
URL template is configured via ``config.OFFICIAL_F2_RESULTS_URL`` AND the caller
opts in. It never performs network I/O during tests or normal builds.
"""
from __future__ import annotations

import os

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "official"


class OfficialF2Source:
    name = SOURCE_NAME

    def results(self, year: int, round: int, race_index: int = 1) -> list[Result] | None:
        url_template = getattr(config, "OFFICIAL_F2_RESULTS_URL", "")
        # Network is opt-in and off by default so CI/builds stay deterministic.
        if not url_template or os.getenv("F2_ENABLE_OFFICIAL_FETCH", "0") != "1":
            return None
        try:
            return self._fetch(url_template, year, round, race_index)
        except Exception:
            return None

    def _fetch(
        self, url_template: str, year: int, round: int, race_index: int
    ) -> list[Result] | None:
        """Fetch + parse an official results document.

        Left unimplemented on purpose: the official feed has no stable schema to
        code against yet. When one is pinned, parse it here into ``Result`` rows;
        the composite + downstream calibration already handle real provenance.
        """
        import requests  # noqa: F401  (imported lazily; only when fetch is enabled)

        _ = (url_template.format(year=year, round=round, race=race_index),)
        return None
