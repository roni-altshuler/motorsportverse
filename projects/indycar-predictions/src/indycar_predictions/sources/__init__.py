"""IndyCar results sources behind the DataSource seam.

Snapshot-primary: the committed, human-verified ``data/history_<year>.json``
files (:class:`SnapshotIndycarSource`) are the source of truth — IndyCar has
no public API, so the live Wikipedia scraper
(:class:`IndycarScraperSource`) exists only as a strictly-validated refresh
mechanism, never an override. All sources answer the same question — "what was
the classified order of round R?" — returning a list of
:class:`motorsport_data.schema.Result`, ``[]`` (round not run yet), or
``None`` (this source has no data; try the next one).

:class:`CompositeIndycarSource` tries the sources in priority order and always
falls back to :class:`SyntheticIndycarSource`, recording per-race provenance
so the calibration gate stays honest about which rounds are real.
"""
from .composite import CompositeIndycarSource
from .indycar_scraper_source import (
    DirtyParseError,
    IndycarScraperSource,
    WikiClient,
    WrongEventError,
)
from .snapshot import SnapshotIndycarSource, is_dnf_status, load_snapshot
from .synthetic import SyntheticIndycarSource

__all__ = [
    "CompositeIndycarSource",
    "DirtyParseError",
    "IndycarScraperSource",
    "SnapshotIndycarSource",
    "SyntheticIndycarSource",
    "WikiClient",
    "WrongEventError",
    "is_dnf_status",
    "load_snapshot",
]
