"""Canonical, sport-agnostic data schema for MotorsportVerse.

Generalises the F1 project's Python→JSON→TypeScript contract into neutral
terms so every category (open-wheel, stock, endurance, rally, motorcycle,
electric) maps onto the same shapes. Field names are deliberately neutral —
``competitor`` not ``driver``, ``venue`` not ``circuit`` — so the same models
serve a rally crew or a MotoGP rider.

These are Pydantic models: validated at the boundary, JSON-serialisable for the
website data layer, and mirror-able to TypeScript interfaces.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VenueKind(str, Enum):
    circuit = "circuit"
    oval = "oval"
    street = "street"
    stage = "stage"


class _Base(BaseModel):
    # permissive on additions (forward-compatible), strict on required fields —
    # matches the F1 project's `extra="ignore"` discipline.
    model_config = ConfigDict(extra="ignore")


class Competitor(_Base):
    code: str = Field(..., description="Stable short id, e.g. 'VER'")
    name: str
    team: str
    number: int | None = None
    nationality: str | None = None


class Team(_Base):
    name: str
    color: str | None = Field(None, description="Hex accent for charts/badges")
    nationality: str | None = None


class Venue(_Base):
    key: str = Field(..., description="Stable slug, e.g. 'monaco'")
    name: str
    country: str | None = None
    kind: VenueKind = VenueKind.circuit


class Result(_Base):
    competitor: str = Field(..., description="Competitor code")
    position: int | None = Field(None, description="Classified finishing position; null = DNF/DNS")
    grid: int | None = None
    status: str | None = Field(None, description="Finished / +1 Lap / Accident / ...")
    points: float | None = None


class Prediction(_Base):
    competitor: str
    predicted_position: int
    predicted_value: float | None = Field(
        None, description="Underlying model score (lap time, rating, etc.)"
    )
    p_win: float | None = None
    p_podium: float | None = None
    low: float | None = Field(None, description="Lower bound of prediction interval")
    high: float | None = Field(None, description="Upper bound of prediction interval")


class Round(_Base):
    season: int
    round: int
    venue: Venue
    completed: bool = False
    predictions: list[Prediction] = Field(default_factory=list)
    results: list[Result] = Field(default_factory=list)


class Season(_Base):
    sport: str = Field(..., description="e.g. 'Formula 1', 'Formula 2'")
    year: int
    competitors: list[Competitor] = Field(default_factory=list)
    teams: list[Team] = Field(default_factory=list)
    calendar: list[Venue] = Field(default_factory=list)
    completed_rounds: list[int] = Field(default_factory=list)


__all__ = [
    "VenueKind",
    "Competitor",
    "Team",
    "Venue",
    "Result",
    "Prediction",
    "Round",
    "Season",
]
