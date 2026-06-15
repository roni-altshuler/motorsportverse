"""motorsport-data — canonical schema, history store, and ingestion adapters.

The data-layer half of MotorsportVerse's shared infrastructure:

- :mod:`~motorsport_data.schema` — sport-agnostic Pydantic models
  (Season, Round, Competitor, Team, Venue, Result, Prediction).
- :mod:`~motorsport_data.store` — DuckDB history store for (predicted, actual)
  pairs that calibration + forward-eval consume.
- :mod:`~motorsport_data.sources` — `DataSource` ABC + the shared Jolpica/Ergast
  client for open-wheel series.
- :mod:`~motorsport_data.rollover` — config-driven multi-season archival.
"""

from . import rollover, schema, sources, store  # noqa: F401

__version__ = "0.1.0"

__all__ = ["schema", "store", "sources", "rollover", "__version__"]
