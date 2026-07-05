"""Real F2 results scraped from fiaformula2.com — the working Phase 3 feed.

The parsing/calendar/entry-list machinery lives in the shared
:class:`motorsport_data.sources.fia_feeder.FiaFeederSource` (fiaformula2.com and
fiaformula3.com run the same CMS); this module binds it to F2's configuration —
base URL, season anchor raceids, and the Sprint/Feature session headings.

F2 runs a single qualifying session on Friday that sets the FEATURE grid (the
sprint is the reverse of its top 10), so qualifying order is the one session
that drives both races.
"""
from __future__ import annotations

from motorsport_data.sources.fia_feeder import (
    _RE_TITLE_ROUND,  # noqa: F401 — re-exported for tests/tools that verify titles
    FiaFeederSource,
)

from .. import config

SOURCE_NAME = "fia"

_SESSION_HEADING = {0: "Sprint Race", 1: "Feature Race"}

_QUALI_HEADINGS = ("Qualifying", "Qualifying Session", "Qualifying Result")


class FiaF2Source(FiaFeederSource):
    name = SOURCE_NAME

    def __init__(self, *, timeout: int = 20):
        super().__init__(
            base_url=config.FIA_F2_BASE_URL,
            season_anchors=config.FIA_F2_SEASON_ANCHORS,
            session_headings=_SESSION_HEADING,
            quali_headings=_QUALI_HEADINGS,
            user_agent="Mozilla/5.0 (motorsportverse/f2 research)",
            timeout=timeout,
        )
