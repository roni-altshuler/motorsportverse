"""WEC data source — per-class results + leakage-safe history for the model.

Wraps :class:`wec_predictions.sources.snapshot.SnapshotWecSource` and adds the
aggregation the model needs: the current field for a class, this-season prior
form (with a cross-season fallback so round 1 isn't blind), and the cross-season
finishing-order corpus the Elo builder replays. Every aggregation is leakage-safe
— it reads only rounds strictly before the one being forecast.
"""
from __future__ import annotations

from motorsport_data.schema import Result

from . import config
from .sources.snapshot import SnapshotWecSource


class WecDataSource:
    sport = config.SPORT

    def __init__(self) -> None:
        self.snapshot = SnapshotWecSource()

    # ---- direct results ----------------------------------------------------
    def class_results(self, year: int, round: int, cls: str) -> list[Result] | None:
        return self.snapshot.results(year, round, cls)

    def completed_rounds(self, year: int) -> list[int]:
        return self.snapshot.completed_rounds(year)

    def classes(self, year: int) -> list[str]:
        return self.snapshot.classes(year)

    def classes_for_round(self, year: int, round: int) -> list[str]:
        """Classes actually racing at a round.

        A completed round reports the classes it ran (Le Mans adds LMP2; regular
        rounds don't). For a not-yet-run round we use the most recent completed
        round's classes — the regular grid — so we never forecast a class that
        won't be there. Falls back to the season's class list.
        """
        snap = config.load_snapshot(year)
        block = (snap.get("results", {}) or {}).get(str(round))
        if block:
            present = [c for c in self.classes(year) if c in block]
            if present:
                return present
        prior = [r for r in self.completed_rounds(year) if r < round]
        if prior:
            pblock = (snap.get("results", {}) or {}).get(str(max(prior))) or {}
            present = [c for c in self.classes(year) if c in pblock]
            if present:
                return present
        return self.classes(year) or config.CLASSES

    # ---- the field to forecast --------------------------------------------
    def field_for(self, year: int, round: int, cls: str) -> list[str]:
        """Entries to forecast for a class at a round.

        If the round has run (validation / re-forecast) use its actual field.
        Otherwise (a live forecast of the next round) use the most recent
        completed round's field for that class — the realistic current grid.
        """
        actual = self.snapshot.class_field(year, round, cls)
        if actual:
            return actual
        for r in sorted((r for r in self.completed_rounds(year) if r < round), reverse=True):
            fld = self.snapshot.class_field(year, r, cls)
            if fld:
                return fld
        # fall back to the season roster for the class
        return [e["code"] for e in config.entries_in_class(cls)]

    # ---- leakage-safe prior form ------------------------------------------
    def prior_form(self, year: int, current_round: int, cls: str
                   ) -> tuple[dict[str, float], dict[str, int]]:
        """Average within-class finishing position over prior rounds this season.

        Falls back to the most recent prior season's full-season average for a
        class when this season has no prior rounds (early-season is not blind).
        """
        prior = [r for r in self.completed_rounds(year) if r < current_round]
        sums, counts = self._accumulate(year, prior, cls)
        if not sums:
            for y in reversed([s for s in config.HISTORY_SEASONS if s < year] or config.HISTORY_SEASONS):
                rounds = self.completed_rounds(y)
                sums, counts = self._accumulate(y, rounds, cls)
                if sums:
                    break
        avg = {c: sums[c] / counts[c] for c in sums}
        return avg, counts

    def _accumulate(self, year: int, rounds: list[int], cls: str
                    ) -> tuple[dict[str, float], dict[str, int]]:
        sums: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in rounds:
            res = self.class_results(year, r, cls)
            if not res:
                continue
            for row in res:
                sums[row.competitor] = sums.get(row.competitor, 0.0) + (row.position or 0)
                counts[row.competitor] = counts.get(row.competitor, 0) + 1
        return sums, counts

    # ---- cross-season corpus for Elo --------------------------------------
    def history_events(self, year: int, current_round: int, cls: str
                       ) -> list[tuple[int, int, dict[str, int]]]:
        """(season, sub_round, {code: within-class position}) newest-exclusive.

        Prior seasons are admitted whole; the current season only up to (but not
        including) ``current_round``. ``sub_round`` is a monotone counter so the
        Elo builder's ``(season, round)`` cutoff orders events correctly.
        """
        events: list[tuple[int, int, dict[str, int]]] = []
        seasons = [s for s in config.HISTORY_SEASONS if s < year] + [year]
        for y in seasons:
            rounds = self.completed_rounds(y)
            if y == year:
                rounds = [r for r in rounds if r < current_round]
            for sub, r in enumerate(sorted(rounds), start=1):
                res = self.class_results(y, r, cls)
                if res:
                    events.append((y, sub, {row.competitor: int(row.position) for row in res}))
        return events

    def team_of_field(self, field: list[str]) -> dict[str, str]:
        return {c: config.TEAM_OF.get(c, "?") for c in field}
