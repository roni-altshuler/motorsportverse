"""Fail closed on a provider's event identity, independently of a round number.

A round-scoped URL is not an identity: calendars can insert or move events.
Only explicitly recorded aliases are accepted; fuzzy names are never trusted.
"""
from __future__ import annotations

from collections.abc import Mapping
import unicodedata


def _name(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip().casefold()


def jolpica_matches(race: Mapping, year: int, round_num: int, calendar: Mapping) -> bool:
    expected = calendar.get(int(round_num))
    if not expected:
        return False
    try:
        numeric_match = int(race.get("season")) == int(year) and int(race.get("round")) == int(round_num)
    except (TypeError, ValueError):
        return False
    return bool(
        numeric_match
        and race.get("date") == expected.get("provider_date", expected["date"])
        and (race.get("Circuit") or {}).get("circuitId") == expected.get("circuit_id")
        and _name(race.get("raceName")) in {
            _name(expected["name"]), *map(_name, expected.get("event_aliases", []))
        }
    )


def fastf1_matches(event: Mapping, round_num: int, calendar: Mapping) -> bool:
    expected = calendar.get(int(round_num))
    if not expected:
        return False
    try:
        numeric_match = int(event.get("RoundNumber")) == int(round_num)
    except (TypeError, ValueError):
        return False
    event_date = str(event.get("EventDate", ""))[:10]
    return bool(
        numeric_match
        and event_date == expected.get("fastf1_date", expected["date"])
        and _name(event.get("EventName")) in {
            _name(expected["name"]), *map(_name, expected.get("event_aliases", []))
        }
        and _name(event.get("Location")) in set(map(_name, expected.get("locations", [])))
    )


def published_matches(state: Mapping, round_num: int, calendar: Mapping) -> bool:
    """Legacy snapshots may omit provider metadata, but never contradict the calendar."""
    expected = calendar.get(int(round_num))
    return bool(
        expected
        and state.get("round") == int(round_num)
        and state.get("gpKey") == expected["gp_key"]
        and state.get("name") == expected["name"]
        and state.get("circuit") == expected["circuit"]
        and state.get("date") == expected["date"]
    )


def provider_identity(race: Mapping) -> dict:
    return {
        "season": int(race["season"]), "round": int(race["round"]),
        "name": race["raceName"], "date": race["date"],
        "circuitId": race["Circuit"]["circuitId"],
    }
