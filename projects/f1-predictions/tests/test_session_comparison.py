"""The pilot uses only committed rows and never combines separate lap sectors."""
import copy
import json

import pandas as pd
import pytest

from export_session_comparison import OUTPUT, export_payload, select_laps


def frame(rows):
    return pd.DataFrame(rows, columns=[
        "Driver", "Year", "LapTime (s)", "Sector1Time (s)", "Sector2Time (s)", "Sector3Time (s)",
    ])


def test_sectors_stay_on_fastest_complete_row():
    laps = frame([
        ["NOR", 2025, 75.0, 18.0, 37.0, 20.0],
        ["NOR", 2025, 74.0, 19.0, 35.0, 20.0],
        ["NOR", 2025, 70.0, None, 33.0, 18.0],
        ["NOR", 2025, 72.0, 19.0, 35.0, 20.0],  # inconsistent sum
        ["NOR", 2025, float("inf"), 19.0, 35.0, 20.0],
        ["NOR", 2025, 70.0, -1.0, 51.0, 20.0],
    ])
    row = select_laps(laps, {"NOR": "Lando Norris"})[0]
    assert row["lapMs"] == 74000
    assert row["sectorMs"] == [19000, 35000, 20000]
    assert row["completeRows"] == 2
    assert row["storedRows"] == 6


def test_no_comparison_for_driver_without_complete_rows():
    assert select_laps(frame([["NOR", 2025, None, 19.0, 35.0, 20.0]]),
                       {"NOR": "Lando Norris"}) == []


def test_reject_wrong_session_and_unverified_identity():
    with pytest.raises(ValueError, match="2025"):
        select_laps(frame([["NOR", 2026, 74.0, 19.0, 35.0, 20.0]]), {"NOR": "Lando Norris"})
    with pytest.raises(ValueError, match="identity"):
        select_laps(frame([["XXX", 2025, 74.0, 19.0, 35.0, 20.0]]), {})
    with pytest.raises(ValueError, match="Missing timing"):
        select_laps(pd.DataFrame({"Driver": ["NOR"]}), {"NOR": "Lando Norris"})


def test_committed_archive_reproduces_offline():
    expected = export_payload()
    actual = json.loads(OUTPUT.read_text())
    assert expected == actual
    assert len(actual["drivers"]) == 20
    assert sum(d["storedRows"] for d in actual["drivers"]) == 1403
    assert next(d for d in actual["drivers"] if d["code"] == "TSU")["portraitPath"] is None
    # No guessed lap identifiers or absent contextual fields enter the export.
    for driver in actual["drivers"]:
        assert not {"lapNumber", "tyre", "team", "accuracy"} & driver.keys()


def test_selection_independent_of_row_order():
    rows = [
        ["NOR", 2025, 74.0, 19.0, 35.0, 20.0],
        ["RUS", 2025, 75.0, 20.0, 35.0, 20.0],
        ["NOR", 2025, 74.0, 20.0, 34.0, 20.0],
    ]
    names = {"NOR": "Lando Norris", "RUS": "George Russell"}
    assert select_laps(frame(rows), names) == select_laps(frame(list(reversed(copy.copy(rows)))), names)
