"""Core contracts every MotorsportVerse sport plugs into.

These ABCs and dataclasses are the *seam* that keeps sport-specific projects
(``f1-predictions``, ``f2-predictions``, …) interchangeable on top of the
shared ``motorsport-core`` infrastructure. A new sport implements a
:class:`DataSource` (where its data comes from) and a :class:`Predictor`
(how it turns a grid into a ranked forecast); everything else — calibration,
the model registry, drift, promotion, evaluation — is reused unchanged.

Dataclasses are intentionally neutral: ``competitor`` (not ``driver``),
``venue`` (not ``circuit``), so motorcycle / rally / endurance categories map
cleanly. The ``MarketProbabilities`` output type is re-exported from
:mod:`motorsport_core.calibration` so a predictor's probabilistic output and
the calibration layer share one type.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .calibration import MarketProbabilities  # re-exported as the canonical prob type

__all__ = [
    "Competitor",
    "Venue",
    "GridEntry",
    "RoundForecast",
    "DataSource",
    "Predictor",
    "MarketProbabilities",
]


@dataclass(frozen=True)
class Competitor:
    """A single competing entity — driver, rider, or crew.

    ``code`` is the stable short identifier (e.g. "VER", "HAM"); ``team`` is
    the constructor/manufacturer/entrant the competitor races for.
    """

    code: str
    name: str
    team: str
    number: int | None = None
    nationality: str | None = None


@dataclass(frozen=True)
class Venue:
    """Where a round is held — circuit, oval, street course, or rally base."""

    key: str
    name: str
    country: str | None = None
    kind: str = "circuit"  # circuit | oval | street | stage


@dataclass
class GridEntry:
    """A competitor's pre-event state feeding the predictor for one round."""

    competitor: Competitor
    grid_position: int | None = None
    features: dict[str, float] = field(default_factory=dict)


@dataclass
class RoundForecast:
    """A predictor's output for a single round.

    ``predicted_order`` maps competitor code → predicted finishing position
    (1 = winner). ``probabilities`` is the optional calibrated market layer.
    """

    season: int
    round: int
    venue: Venue
    predicted_order: dict[str, int]
    probabilities: MarketProbabilities | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class DataSource(ABC):
    """Where a sport's calendar, results, and timing come from.

    Implementations wrap an upstream API (Jolpica/Ergast, FastF1, a sport's
    own timing feed). Keep methods leakage-safe: ``results`` for a round must
    only return data once that round has actually been run.
    """

    sport: str

    @abstractmethod
    def calendar(self, season: int) -> Sequence[Venue]:
        """Ordered venues for the given season (index 0 == round 1)."""

    @abstractmethod
    def grid(self, season: int, round: int) -> Sequence[GridEntry]:
        """Entry list + pre-event state for one round."""

    @abstractmethod
    def results(self, season: int, round: int) -> Mapping[str, int]:
        """Classified finishing order ``{competitor_code: position}`` once run."""


class Predictor(ABC):
    """Turns a grid into a ranked, optionally-probabilistic forecast.

    The whole point of the shared core: a sport supplies features and a fit
    procedure, then reuses calibration/registry/drift/eval verbatim around it.
    """

    @abstractmethod
    def fit(self, source: DataSource, season: int, upto_round: int) -> None:
        """Train on rounds strictly prior to ``upto_round`` (leakage-safe)."""

    @abstractmethod
    def predict(self, source: DataSource, season: int, round: int) -> RoundForecast:
        """Produce the forecast for a single round."""
