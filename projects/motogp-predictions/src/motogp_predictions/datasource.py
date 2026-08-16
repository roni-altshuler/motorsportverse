"""MotoGP data source — the shared ``DataSource`` contract.

Implements :class:`motorsport_core.interfaces.DataSource` — ``calendar`` /
``grid`` / ``results`` — which is the contract a :class:`Predictor` consumes.
The scaffold this replaced declared the core ``Predictor`` while calling the
``motorsport_data`` DataSource's ``season``/``round``/``results``: two different
ABCs with the same name, so the seam could never have been wired up as written.

Every method is backed by the committed snapshot and returns **empty** while no
snapshot exists. It never fabricates a calendar, an entry list or a result.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from motorsport_core.interfaces import Competitor, DataSource, GridEntry, Venue

from . import config
from .sources import snapshot


class MotoGPDataSource(DataSource):
    """Snapshot-backed source. Empty, honestly, until a season is ingested."""

    sport = config.SPORT

    def __init__(self, *, strict: bool = False) -> None:
        #: In strict mode a missing snapshot raises instead of returning empty.
        #: A pipeline uses strict=True so a silent no-op cannot masquerade as a
        #: season with no rounds; exploratory code uses the default.
        self.strict = strict

    def _payload(self, season: int) -> dict:
        if self.strict:
            return snapshot.require(season)
        return snapshot.load(season) or {}

    def calendar(self, season: int) -> Sequence[Venue]:
        """Ordered venues (index 0 == round 1); empty when nothing is ingested."""
        rounds = self._payload(season).get("calendar") or []
        return [
            Venue(
                key=str(entry.get("key") or f"round-{index + 1}"),
                name=str(entry.get("name") or f"Round {index + 1}"),
                country=entry.get("country"),
                kind=str(entry.get("kind") or "circuit"),
            )
            for index, entry in enumerate(rounds)
            if isinstance(entry, dict)
        ]

    def grid(self, season: int, round: int) -> Sequence[GridEntry]:
        """Entry list for one round; empty when nothing is ingested."""
        entries = self._round_payload(season, round).get("entries") or []
        out: list[GridEntry] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            code = entry.get("code")
            if not code:
                # An entry with no stable identity is refused rather than given
                # a generated one: a junk key is permanent and competes with
                # every later lookup.
                continue
            out.append(
                GridEntry(
                    competitor=Competitor(
                        code=str(code),
                        name=str(entry.get("name") or code),
                        team=str(entry.get("team") or ""),
                        number=entry.get("number"),
                        nationality=entry.get("nationality"),
                    ),
                    grid_position=entry.get("grid"),
                    features={},
                )
            )
        return out

    def results(self, season: int, round: int) -> Mapping[str, int]:
        """Classified order once run; empty while the round has not been run.

        Only CLASSIFIED finishers appear. A retirement has no position and is
        omitted rather than given a last-place one — the same finishers-only
        convention every implemented series in this repo scores against.
        """
        payload = self._round_payload(season, round)
        if not payload.get("completed"):
            return {}
        out: dict[str, int] = {}
        for entry in payload.get("results") or []:
            if not isinstance(entry, dict):
                continue
            code, position = entry.get("code"), entry.get("position")
            if code and isinstance(position, int):
                out[str(code)] = position
        return out

    def _round_payload(self, season: int, round: int) -> dict:
        for entry in self._payload(season).get("rounds") or []:
            if isinstance(entry, dict) and entry.get("round") == round:
                return entry
        return {}


__all__ = ["MotoGPDataSource"]
