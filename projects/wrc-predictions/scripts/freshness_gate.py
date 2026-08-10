"""Cron freshness gate: has a new rally been scored beyond the committed snapshot?

Prints ``should_run=true`` (for ``$GITHUB_OUTPUT``) when the official results API
shows more rallies with published results than the committed snapshot's completed
rounds. On any network/API hiccup it prints ``should_run=false`` so a transient
failure just skips the heavy pull and last-good data keeps serving.
"""
from __future__ import annotations

from wrc_predictions import config


def main() -> None:
    try:
        from wrc_predictions.sources.redbull_source import DRIVERS_CHAMP, WrcApi

        api = WrcApi()
        season_id = api.wrc_season_id(config.SEASON)
        champ = api.championship_id(season_id, DRIVERS_CHAMP) if season_id else None
        finished = 0
        if champ:
            res = api.championship_results(champ, season_id)
            events = set()
            for ent in res.get("entryResults", []):
                for rr in ent.get("roundResults", []):
                    if rr.get("publishedStatus") == "Published" and str(rr.get("position", "")).isdigit():
                        events.add(rr.get("eventId"))
            finished = len(events)
        committed = len((config.load_snapshot(config.SEASON) or {}).get("completedRounds") or [])
        print("should_run=true" if finished > committed else "should_run=false")
    except Exception:  # noqa: BLE001 - any failure → skip the heavy pull
        print("should_run=false")


if __name__ == "__main__":
    main()
