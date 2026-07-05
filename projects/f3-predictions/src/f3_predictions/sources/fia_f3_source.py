"""Real F3 results scraped from fiaformula3.com — the working Phase 3 feed.

The parsing/calendar/entry-list machinery lives in the shared
:class:`motorsport_data.sources.fia_feeder.FiaFeederSource` (fiaformula3.com and
fiaformula3.com run the same CMS); this module binds it to F3's configuration —
base URL, season anchor raceids, and the Sprint/Feature session headings.

F3 runs a single qualifying session on Friday that sets the FEATURE grid (the
sprint is the reverse of its top 12), so qualifying order is the one session
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


class FiaF3Source(FiaFeederSource):
    name = SOURCE_NAME

    def __init__(self, *, timeout: int = 20):
        super().__init__(
            base_url=config.FIA_F3_BASE_URL,
            season_anchors=config.FIA_F3_SEASON_ANCHORS,
            session_headings=_SESSION_HEADING,
            quali_headings=_QUALI_HEADINGS,
            user_agent="Mozilla/5.0 (motorsportverse/f3 research)",
            timeout=timeout,
        )
