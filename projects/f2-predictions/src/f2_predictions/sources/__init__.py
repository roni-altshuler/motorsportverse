"""F2 results sources behind the DataSource seam.

Phase 2 swaps F2 from a synthetic-only project to a real-feed-capable one without
touching the model, pipeline, or export. The sources here all answer the same
question — "what was the classified order of round R's sprint/feature race?" — and
return either a list of :class:`motorsport_data.schema.Result`, ``[]`` (round not
run yet), or ``None`` (this source has no data; try the next one).

:class:`CompositeF2Source` tries the real sources in priority order and always
falls back to :class:`SyntheticF2Source`, recording per-race provenance so the
calibration gate can stay honest about which rounds are real.
"""
from .composite import CompositeF2Source
from .fastf1_source import FastF1F2Source
from .fia_f2_source import FiaF2Source
from .official_source import OfficialF2Source
from .synthetic import SyntheticF2Source

__all__ = [
    "SyntheticF2Source",
    "FastF1F2Source",
    "FiaF2Source",
    "OfficialF2Source",
    "CompositeF2Source",
]
