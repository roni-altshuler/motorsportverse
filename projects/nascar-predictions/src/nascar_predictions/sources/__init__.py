"""NASCAR results sources behind the DataSource seam.

The sources here all answer the same question — "what was the classified order
of round R's race?" — and return either a list of
:class:`motorsport_data.schema.Result`, ``[]`` (round not run yet), or ``None``
(this source has no data; try the next one).

:class:`CompositeNascarSource` tries the real sources in priority order and
always falls back to :class:`SyntheticNascarSource`, recording per-race
provenance so the calibration gate can stay honest about which rounds are real.
"""
from .composite import CompositeNascarSource
from .nascar_feed_source import NascarCacherClient, NascarFeedSource, WrongEventError
from .snapshot import SnapshotNascarSource
from .synthetic import SyntheticNascarSource

__all__ = [
    "SyntheticNascarSource",
    "SnapshotNascarSource",
    "NascarCacherClient",
    "NascarFeedSource",
    "WrongEventError",
    "CompositeNascarSource",
]
