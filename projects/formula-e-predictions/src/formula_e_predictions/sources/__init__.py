"""FE results sources behind the DataSource seam.

The sources here all answer the same question — "what was the classified order
of round R's race?" — and return either a list of
:class:`motorsport_data.schema.Result`, ``[]`` (round not run yet), or ``None``
(this source has no data; try the next one).

:class:`CompositeFESource` tries the real sources in priority order and always
falls back to :class:`SyntheticFESource`, recording per-race provenance so the
calibration gate can stay honest about which rounds are real.
"""
from .composite import CompositeFESource
from .pulselive_source import PulseliveClient, PulseliveFESource, WrongEventError
from .snapshot import SnapshotFESource
from .synthetic import SyntheticFESource

__all__ = [
    "SyntheticFESource",
    "SnapshotFESource",
    "PulseliveClient",
    "PulseliveFESource",
    "WrongEventError",
    "CompositeFESource",
]
