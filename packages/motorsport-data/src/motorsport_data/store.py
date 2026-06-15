"""History store for (predicted, actual) pairs — calibration's data source.

Generalises the F1 project's ``data/history.duckdb`` schema. The table holds
one row per (sport, season, round, competitor) with the predicted and actual
finishing positions plus the underlying model value. This is what the
calibration layer reads to fit isotonic/stratified calibrators, and what
forward-eval scores against.

DuckDB is an optional dependency: import this module freely, but constructing a
:class:`HistoryStore` requires ``duckdb`` installed (``pip install duckdb``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS historical_predictions (
    sport               TEXT    NOT NULL,
    season              INTEGER NOT NULL,
    round               INTEGER NOT NULL,
    competitor          TEXT    NOT NULL,
    predicted_position  INTEGER,
    actual_position     INTEGER,
    predicted_value     DOUBLE,
    source              TEXT,
    PRIMARY KEY (sport, season, round, competitor)
);
"""


@dataclass
class HistoryRow:
    sport: str
    season: int
    round: int
    competitor: str
    predicted_position: int | None = None
    actual_position: int | None = None
    predicted_value: float | None = None
    source: str | None = None


class HistoryStore:
    """Thin DuckDB wrapper around the canonical history table.

    Idempotent upserts on the composite primary key, mirroring the F1
    backfill's "skip rounds already present unless --force" behaviour.
    """

    def __init__(self, path: str | Path):
        try:
            import duckdb  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "HistoryStore requires duckdb — `pip install duckdb`"
            ) from exc
        import duckdb

        self.path = str(path)
        self._con = duckdb.connect(self.path)
        self._con.execute(SCHEMA)

    def upsert(self, rows: list[HistoryRow]) -> int:
        """Insert-or-replace rows; returns the number written."""
        if not rows:
            return 0
        self._con.executemany(
            """
            INSERT OR REPLACE INTO historical_predictions
            (sport, season, round, competitor, predicted_position,
             actual_position, predicted_value, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.sport, r.season, r.round, r.competitor,
                    r.predicted_position, r.actual_position,
                    r.predicted_value, r.source,
                )
                for r in rows
            ],
        )
        return len(rows)

    def completed_rounds(self, sport: str, season: int) -> list[int]:
        rows = self._con.execute(
            """
            SELECT DISTINCT round FROM historical_predictions
            WHERE sport = ? AND season = ? AND actual_position IS NOT NULL
            ORDER BY round
            """,
            [sport, season],
        ).fetchall()
        return [r[0] for r in rows]

    def pairs(self, sport: str) -> list[tuple[int, int]]:
        """All (predicted_position, actual_position) pairs for a sport — the
        raw material the calibration layer consumes."""
        rows = self._con.execute(
            """
            SELECT predicted_position, actual_position
            FROM historical_predictions
            WHERE sport = ?
              AND predicted_position IS NOT NULL
              AND actual_position IS NOT NULL
            """,
            [sport],
        ).fetchall()
        return [(int(p), int(a)) for p, a in rows]

    def close(self) -> None:
        self._con.close()


__all__ = ["SCHEMA", "HistoryRow", "HistoryStore"]
