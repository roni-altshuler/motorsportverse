"""Cron freshness gate: is there a scored round beyond the committed snapshot?

Prints ``should_run=true`` (for ``$GITHUB_OUTPUT``) when the official results API
shows more finished premier-class events than the committed snapshot's completed
rounds — i.e. a new race has been scored and a full re-pull is worth doing. On
any network/API hiccup it prints ``should_run=false`` so a transient failure just
skips the heavy pull and the last-good data keeps serving. Two API calls only.
"""
from __future__ import annotations

from motogp_predictions import config


def main() -> None:
    try:
        from motogp_predictions.sources.pulselive_source import MotoGPApi

        api = MotoGPApi()
        su = api.season_uuid(config.SEASON)
        finished = len(api.events(su, finished_only=True)) if su else 0
        committed = len((config.load_snapshot(config.SEASON) or {}).get("completedRounds") or [])
        print("should_run=true" if finished > committed else "should_run=false")
    except Exception:  # noqa: BLE001 - any failure → skip the heavy pull, serve last-good
        print("should_run=false")


if __name__ == "__main__":
    main()
