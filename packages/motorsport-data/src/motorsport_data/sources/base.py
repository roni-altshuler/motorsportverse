"""DataSource ABC for ingestion — the upstream contract every sport implements.

This mirrors ``motorsport_core.interfaces.DataSource`` but lives in the data
package so ingestion adapters can be written without importing the ML core.
A sport supplies one concrete subclass (Jolpica for F1/F2/F3, FastF1 for
telemetry, a bespoke timing feed for others).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..schema import Result, Round, Season


class DataSource(ABC):
    """Where a sport's calendar, entry lists, and results come from."""

    #: Human-readable sport name, e.g. "Formula 2".
    sport: str

    @abstractmethod
    def season(self, year: int) -> Season:
        """Calendar + roster for a season."""

    @abstractmethod
    def round(self, year: int, round: int) -> Round:
        """One round's predictions/results shell (results filled once run)."""

    @abstractmethod
    def results(self, year: int, round: int) -> list[Result]:
        """Classified order once the round has run; empty list if not yet."""


__all__ = ["DataSource"]
