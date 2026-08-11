"""Cron freshness gate: has a new IMSA round been scored beyond the snapshot?

Prints ``should_run=true`` (for ``$GITHUB_OUTPUT``) when the official Al Kamel
timing archive shows more WeatherTech rounds with a published race classification
than the committed snapshot's completed rounds. On any network/parse hiccup it
prints ``should_run=false`` so a transient failure just skips the heavy pull and
the last-good committed data keeps serving.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from imsa_predictions import config


def main() -> None:
    try:
        from motorsport_data.sources.alkamel import AlKamelClient

        from imsa_predictions.build_snapshot import _CHAMP_HINT, _HOST, _SKIP_EVENT

        client = AlKamelClient(_HOST, _CHAMP_HINT, Path(tempfile.mkdtemp()))
        folder_for = {y: sf for sf, y in client.list_seasons()}
        sf = folder_for.get(config.SEASON)
        finished = 0
        if sf:
            for ev in client.list_events(sf):
                if _SKIP_EVENT.search(ev.name):
                    continue
                if client._race_classification_url(ev):
                    finished += 1
        committed = len((config.load_snapshot(config.SEASON) or {}).get("completedRounds") or [])
        print("should_run=true" if finished > committed else "should_run=false")
    except Exception:  # noqa: BLE001 - any failure → skip the heavy pull
        print("should_run=false")


if __name__ == "__main__":
    main()
