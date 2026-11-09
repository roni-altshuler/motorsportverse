"""Normal numerical contracts use only the verified pre-mismatch prefix.

Production's mismatched snapshot is tested separately as an explicit hold; it
must not be silently treated as a normal forecast corpus in contract fixtures.
"""
from __future__ import annotations

import copy
import json

import pytest


@pytest.fixture(scope="module")
def verified_publication_prefix(tmp_path_factory):
    from motogp_predictions import config
    from motogp_predictions.publication import snapshot_issues

    original = config.load_snapshot
    history = {year: original(year) for year in config.HISTORY_SEASONS}
    snapshot = copy.deepcopy(original(config.SEASON))
    full = {e["round"]: e for e in snapshot["fullCalendar"]}
    prefix = []
    for e in snapshot["calendar"]:
        if e["round"] != len(prefix) + 1 or any(e.get(k) != full[e["round"]].get(k)
                                             for k in ("shortName", "venue", "country", "date")):
            break
        prefix.append(e["round"])
    assert prefix, "normal-contract fixture requires a verified nonempty prefix"
    snapshot["completedRounds"] = prefix
    snapshot["calendar"] = [e for e in snapshot["calendar"] if e["round"] in prefix]
    for key in ("results", "qualifying"):
        snapshot[key] = {r: value for r, value in snapshot[key].items() if int(r) in prefix}
    # These provider aggregates include the later events. Let the normal
    # exporter recompute standings from the fixture's actual retained results.
    snapshot.pop("driverStandings", None)
    snapshot.pop("teamStandings", None)
    assert not snapshot_issues(snapshot)
    folder = tmp_path_factory.mktemp("verified-motogp-prefix")
    (folder / f"official_{config.SEASON}.json").write_text(json.dumps(snapshot))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config, "_DATA_DIR", folder)
        patch.setattr(config, "_SNAP", snapshot)
        patch.setattr(config, "COMPLETED_ROUNDS", len(prefix))
        patch.setattr(config, "load_snapshot", lambda y: snapshot if y == config.SEASON else history.get(y, {}))
        yield snapshot
