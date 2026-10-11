"""Validated final-grid inputs for explicit, unpublished shadow consumers.

Qualifying rank/time remain model features. A final grid is an independent,
event-bound observation, never inferred from qualifying or driver row order.
This module performs no network, training, registry or publication writes.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit

import pandas as pd

MAX_SOURCE_AGE = timedelta(hours=1)


class StartingGridUnavailable(ValueError):
    """An explicit reason the requested official-grid shadow cannot run."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _utc(value: str | datetime, label: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise StartingGridUnavailable(f"invalid-{label}") from None


def _event_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StartingGridUnavailable("incomplete-event-identity")
    return value


@dataclass(frozen=True)
class StartingGridEvent:
    season: int
    round_num: int
    gp_key: str
    name: str
    circuit: str
    date: str
    circuit_id: str
    race_start_utc: datetime
    source_url: str

    def __post_init__(self):
        if type(self.season) is not int or self.season < 1 or type(self.round_num) is not int or self.round_num < 1:
            raise StartingGridUnavailable("invalid-event-numbers")
        if any(not isinstance(v, str) or not v.strip() for v in (
            self.gp_key, self.name, self.circuit, self.date, self.circuit_id,
        )):
            raise StartingGridUnavailable("incomplete-event-identity")
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.date):
                raise ValueError
            datetime.strptime(self.date, "%Y-%m-%d")
        except ValueError:
            raise StartingGridUnavailable("invalid-event-date") from None
        object.__setattr__(self, "race_start_utc", _utc(self.race_start_utc, "race-start"))
        if not isinstance(self.source_url, str):
            raise StartingGridUnavailable("invalid-official-source-url")
        url = urlsplit(self.source_url)
        if (url.scheme != "https" or url.netloc != "www.formula1.com" or url.query or url.fragment
                or not re.fullmatch(rf"/en/results/{self.season}/races/\d+/[a-z0-9-]+/starting-grid", url.path)):
            raise StartingGridUnavailable("invalid-official-source-url")

    @classmethod
    def from_calendar(cls, season: int, round_num: int, calendar: Mapping, *,
                      race_start_utc: str | datetime, source_url: str) -> StartingGridEvent:
        """Bind a trusted calendar entry to an explicitly verified official URL/start.

        The URL is supplied independently of the payload; no guessed provider
        race ID or default race-start hour is allowed.
        """
        entry = calendar.get(round_num)
        if not isinstance(entry, Mapping):
            raise StartingGridUnavailable("event-not-in-calendar")
        start = _utc(race_start_utc, "race-start")
        if entry.get("race_start_utc") and start != _utc(entry["race_start_utc"], "race-start"):
            raise StartingGridUnavailable("race-start-disagrees-with-calendar")
        return cls(season, round_num, _event_text(entry.get("gp_key")), _event_text(entry.get("name")),
                   _event_text(entry.get("circuit")), _event_text(entry.get("date")),
                   _event_text(entry.get("circuit_id")), start, source_url)

    def identity(self) -> dict:
        return {"season": self.season, "round": self.round_num, "gpKey": self.gp_key,
                "name": self.name, "circuit": self.circuit, "date": self.date,
                "circuitId": self.circuit_id}


@dataclass(frozen=True)
class StartingGridSnapshot:
    """A value for trusted Python callers, not a signed source attestation.

    Use ``from_published`` at the provider boundary. Direct construction or
    ``dataclasses.replace`` validates structure/time but cannot authenticate
    the claimed source digest or bind caller-supplied positions to that source.
    """

    event: StartingGridEvent
    positions: tuple[tuple[str, int], ...]
    verified_at: datetime
    input_cutoff: datetime
    source_session_sha256: str
    fetched_at: datetime | None = None
    max_source_age: timedelta = MAX_SOURCE_AGE
    published_generated_at: datetime | None = None

    def __post_init__(self):
        if not isinstance(self.event, StartingGridEvent):
            raise StartingGridUnavailable("invalid-grid-event")
        if (not isinstance(self.positions, tuple)
                or any(not isinstance(row, tuple) or len(row) != 2 for row in self.positions)):
            raise StartingGridUnavailable("invalid-grid-rows")
        object.__setattr__(self, "verified_at", _utc(self.verified_at, "source-verification"))
        object.__setattr__(self, "input_cutoff", _utc(self.input_cutoff, "input-cutoff"))
        if self.fetched_at is not None:
            object.__setattr__(self, "fetched_at", _utc(self.fetched_at, "source-fetch"))
            if self.fetched_at > self.verified_at:
                raise StartingGridUnavailable("source-fetched-after-verification")
        if (not isinstance(self.max_source_age, timedelta)
                or not timedelta(0) < self.max_source_age <= MAX_SOURCE_AGE):
            raise StartingGridUnavailable("invalid-source-age-policy")
        if self.input_cutoff >= self.event.race_start_utc:
            raise StartingGridUnavailable("cutoff-not-before-race")
        if self.verified_at > self.input_cutoff:
            raise StartingGridUnavailable("source-verified-after-cutoff")
        if self.input_cutoff - self.verified_at > self.max_source_age:
            raise StartingGridUnavailable("stale-source-verification")
        if self.published_generated_at is not None:
            generated = _utc(self.published_generated_at, "published-source-generation")
            object.__setattr__(self, "published_generated_at", generated)
            if generated > self.input_cutoff:
                raise StartingGridUnavailable("published-source-generated-after-cutoff")
        drivers = [d for d, _ in self.positions]
        slots = [p for _, p in self.positions]
        if len(drivers) < 2 or any(not isinstance(d, str) or not re.fullmatch(r"[A-Z]{3}", d) for d in drivers):
            raise StartingGridUnavailable("invalid-grid-drivers")
        if len(set(drivers)) != len(drivers):
            raise StartingGridUnavailable("duplicate-grid-driver")
        if any(type(p) is not int for p in slots) or sorted(slots) != list(range(1, len(slots) + 1)):
            raise StartingGridUnavailable("invalid-grid-positions")
        if not isinstance(self.source_session_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", self.source_session_sha256):
            raise StartingGridUnavailable("invalid-source-digest")

    @classmethod
    def from_published(cls, payload: Mapping, *, event: StartingGridEvent,
                       expected_drivers: Iterable[str], input_cutoff: str | datetime,
                       max_source_age: timedelta = MAX_SOURCE_AGE) -> StartingGridSnapshot:
        if not isinstance(payload, Mapping):
            raise StartingGridUnavailable("invalid-published-snapshot")
        identity = event.identity()
        if type(payload.get("round")) is not int:
            raise StartingGridUnavailable("published-event-mismatch")
        if any(payload.get(k) != identity[k] for k in ("round", "gpKey", "name", "circuit", "date")):
            raise StartingGridUnavailable("published-event-mismatch")
        if type(payload.get("season", event.season)) is not int or payload.get("season", event.season) != event.season:
            raise StartingGridUnavailable("published-season-mismatch")
        weekend = payload.get("weekendResults") or {}
        if not isinstance(weekend, Mapping):
            raise StartingGridUnavailable("invalid-weekend-results")
        sessions = weekend.get("sessions", [])
        if not isinstance(sessions, list) or any(not isinstance(s, Mapping) for s in sessions):
            raise StartingGridUnavailable("invalid-weekend-sessions")
        grids = [s for s in sessions if s.get("key") == "startingGrid"]
        if len(grids) != 1:
            raise StartingGridUnavailable("missing-final-grid" if not grids else "ambiguous-final-grid")
        session = grids[0]
        if session.get("status") != "official" or session.get("sourceUrl") != event.source_url:
            raise StartingGridUnavailable("unverified-final-grid-source")
        provider = session.get("eventIdentity")
        if provider is not None and (not isinstance(provider, Mapping)
                or any(provider.get(k) != identity[k] for k in ("season", "round", "name", "date", "circuitId"))
                or any(provider[k] != identity[k] for k in ("gpKey", "circuit") if k in provider)):
            raise StartingGridUnavailable("provider-event-mismatch")
        roster = tuple(expected_drivers)
        if any(not isinstance(d, str) or not re.fullmatch(r"[A-Z]{3}", d) for d in roster):
            raise StartingGridUnavailable("invalid-expected-field")
        rows = session.get("rows") or []
        if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
            raise StartingGridUnavailable("invalid-grid-rows")
        if any(isinstance(value, str) and re.sub(r"[^A-Z]", "", value.upper()) in {"PL", "PITLANE"}
               for row in rows for value in (row.get("positionText"), row.get("status"))):
            raise StartingGridUnavailable("unsupported-pit-lane-start")
        positions = tuple((r.get("driver"), r.get("position")) for r in rows)
        if any(not isinstance(d, str) or not re.fullmatch(r"[A-Z]{3}", d) for d, _ in positions):
            raise StartingGridUnavailable("invalid-grid-drivers")
        if len(set(roster)) != len(roster) or set(d for d, _ in positions) != set(roster):
            raise StartingGridUnavailable("incomplete-final-grid-field")
        try:
            raw = json.dumps(session, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        except (ValueError, TypeError):
            raise StartingGridUnavailable("invalid-source-session") from None
        return cls(event=event, positions=positions,
                   verified_at=_utc(session.get("verifiedAt"), "source-verification"),
                   input_cutoff=_utc(input_cutoff, "input-cutoff"),
                   source_session_sha256=hashlib.sha256(raw).hexdigest(),
                   fetched_at=_utc(session["fetchedAt"], "source-fetch") if "fetchedAt" in session else None,
                   max_source_age=max_source_age,
                   published_generated_at=_utc(weekend["generatedAt"], "published-source-generation")
                   if "generatedAt" in weekend else None)

    def require_event(self, event: StartingGridEvent):
        if event != self.event:
            raise StartingGridUnavailable("shadow-event-mismatch")

    def require_round(self, season: int, round_num: int, gp_key: str):
        if (season, round_num, gp_key) != (self.event.season, self.event.round_num, self.event.gp_key):
            raise StartingGridUnavailable("shadow-event-mismatch")

    def require_cutoff(self, cutoff: str | datetime | None):
        if cutoff is None:
            raise StartingGridUnavailable("invalid-requested-input-cutoff")
        if _utc(cutoff, "requested-input-cutoff") != self.input_cutoff:
            raise StartingGridUnavailable("shadow-cutoff-mismatch")

    def attach(self, merged: pd.DataFrame) -> pd.DataFrame:
        """Add final-grid position without changing any qualifying/model feature."""
        positions = dict(self.positions)
        if ("Driver" not in merged
                or any(not isinstance(d, str) for d in merged["Driver"])
                or merged["Driver"].duplicated().any()
                or set(merged["Driver"]) != set(positions)):
            raise StartingGridUnavailable("shadow-frame-field-mismatch")
        result = merged.copy()
        slots = result["Driver"].map(positions)
        if "StartingGridPosition" in result and not result["StartingGridPosition"].eq(slots).all():
            raise StartingGridUnavailable("contradictory-starting-grid-column")
        result["StartingGridPosition"] = slots
        result.attrs["startingGridShadow"] = self.provenance()
        return result

    def provenance(self) -> dict:
        return {"mode": "shadow-only", "eventIdentity": self.event.identity(),
                "identityBasis": "published-event-and-independently-pinned-official-url",
                "sourceUrl": self.event.source_url,
                "sourceVerifiedAt": self.verified_at.isoformat(),
                "sourceFetchedAt": self.fetched_at.isoformat() if self.fetched_at else None,
                "publishedSourceGeneratedAt": self.published_generated_at.isoformat()
                if self.published_generated_at else None,
                "inputCutoff": self.input_cutoff.isoformat(),
                "raceStartUtc": self.event.race_start_utc.isoformat(),
                "maxSourceAgeSeconds": self.max_source_age.total_seconds(),
                "sourceSessionSha256": self.source_session_sha256,
                "driverCount": len(self.positions)}
