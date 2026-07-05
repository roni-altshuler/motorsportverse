"""F3 results sources behind the DataSource seam.

Phase 2 swaps F3 from a synthetic-only project to a real-feed-capable one without
touching the model, pipeline, or export. The sources here all answer the same
question — "what was the classified order of round R's sprint/feature race?" — and
return either a list of :class:`motorsport_data.schema.Result`, ``[]`` (round not
run yet), or ``None`` (this source has no data; try the next one).

:class:`CompositeF3Source` tries the real sources in priority order and always
falls back to :class:`SyntheticF3Source`, recording per-race provenance so the
calibration gate can stay honest about which rounds are real.
"""
from .composite import CompositeF3Source
from .fastf1_source import FastF1F3Source
from .fia_f3_source import FiaF3Source
from .official_source import OfficialF3Source
from .synthetic import SyntheticF3Source

__all__ = [
    "SyntheticF3Source",
    "FastF1F3Source",
    "FiaF3Source",
    "OfficialF3Source",
    "CompositeF3Source",
]
