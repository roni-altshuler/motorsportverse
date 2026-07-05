"""IMSA data source — implements the shared DataSource contract."""
from __future__ import annotations

from motorsport_data.schema import Result, Round, Season
from motorsport_data.sources.base import DataSource


class SportDataSource(DataSource):
    sport = "IMSA"

    def season(self, year: int) -> Season:
        return Season(sport=self.sport, year=year)

    def round(self, year: int, round: int) -> Round:
        from motorsport_data.schema import Venue

        return Round(season=year, round=round, venue=Venue(key=f"round-{round}", name=f"Round {round}"))

    def results(self, year: int, round: int) -> list[Result]:
        # TODO: wire this sport's results feed.
        return []
