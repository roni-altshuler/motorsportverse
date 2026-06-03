"""Priority-1 qualifying reliability fix — no-time drivers must never be
promoted to the front of the field.

Covers the failure modes from the Round-1 (Australia 2026) audit:
  * DNS qualifying (driver absent from the times dict)
  * deleted lap times (driver present with NaN time)
  * missing telemetry / incomplete session (partial field timed)
  * Monaco-specific scenario (grid position disproportionately important)

The contract under test (``apply_qualifying_data`` in f1_prediction_utils):
  - A driver with no valid qualifying time is seated BEHIND every driver who
    set a time (QualifyingRank strictly larger, GridAdvantage negative).
  - Pre-qualifying previews (every driver synthetic) are unaffected.
  - Complete sessions (everyone timed) are unaffected.
"""
import pandas as pd

from f1_prediction_utils import apply_qualifying_data, _timed_drivers


def _grid(drivers, clean_air=90.0):
    """Minimal `merged` frame with the columns apply_qualifying_data needs."""
    return pd.DataFrame({
        "Driver": drivers,
        "CleanAirPace": [clean_air + i * 0.1 for i in range(len(drivers))],
        "WetPerformance": [1.0] * len(drivers),
    })


FIELD = ["VER", "NOR", "PIA", "RUS", "LEC", "HAM", "SAI", "STR", "ALO", "GAS"]


def _times(timed):
    """Realistic qualifying-time dict: ~90s spread by index order."""
    return {d: 90.0 + i * 0.15 for i, d in enumerate(timed)}


# ── DNS qualifying: driver absent from the times dict ──────────────────────
def test_dns_driver_seated_behind_timed_field():
    timed = [d for d in FIELD if d not in ("SAI", "STR")]   # SAI, STR set no time
    merged = apply_qualifying_data(_grid(FIELD), _times(timed),
                                   fallback_times={d: 90.0 for d in FIELD})
    rank = merged.set_index("Driver")["QualifyingRank"]
    worst_timed = rank[timed].max()
    assert rank["SAI"] > worst_timed
    assert rank["STR"] > worst_timed
    # And they must NOT be at the front.
    assert rank["SAI"] >= len(timed) + 1
    assert rank["STR"] >= len(timed) + 1


def test_dns_driver_has_negative_grid_advantage():
    timed = FIELD[:-1]
    merged = apply_qualifying_data(_grid(FIELD), _times(timed),
                                   fallback_times={d: 90.0 for d in FIELD})
    ga = merged.set_index("Driver")["GridAdvantage"]
    assert ga["GAS"] < 0.0                   # behind the median → disadvantaged
    assert merged.set_index("Driver")["QualifyingDataMissing"]["GAS"]


# ── Deleted lap times: driver present but NaN ──────────────────────────────
def test_deleted_laptime_nan_is_treated_as_no_time():
    times = _times(FIELD)
    times["STR"] = float("nan")              # lap deleted → NaN
    merged = apply_qualifying_data(_grid(FIELD), times,
                                   fallback_times={d: 90.0 for d in FIELD})
    rank = merged.set_index("Driver")["QualifyingRank"]
    timed = [d for d in FIELD if d != "STR"]
    assert rank["STR"] > rank[timed].max()
    assert "STR" not in _timed_drivers(times)


# ── The exact Round-1 regression: optimistic estimate must NOT win pole ────
def test_round1_sai_str_not_promoted_to_front():
    # SAI/STR have the *fastest* fallback estimates but set no real time.
    timed = ["VER", "NOR", "PIA", "RUS", "LEC", "HAM", "ALO", "GAS"]
    real = {d: 90.0 + i * 0.15 for i, d in enumerate(timed)}
    fallback = {d: 90.0 for d in FIELD}
    fallback["SAI"] = 80.0                    # absurdly optimistic
    fallback["STR"] = 80.1
    merged = apply_qualifying_data(_grid(FIELD), real, fallback_times=fallback)
    order = merged.sort_values("QualifyingRank")["Driver"].tolist()
    assert order[0] != "SAI" and order[1] != "STR"
    assert set(order[-2:]) == {"SAI", "STR"}  # both at the very back


# ── Missing telemetry / incomplete session (only a few drivers timed) ──────
def test_incomplete_session_partial_field():
    timed = ["VER", "NOR", "PIA"]            # only 3 of 10 set a time
    merged = apply_qualifying_data(_grid(FIELD), _times(timed),
                                   fallback_times={d: 90.0 for d in FIELD})
    rank = merged.set_index("Driver")["QualifyingRank"]
    for d in timed:
        for nd in set(FIELD) - set(timed):
            assert rank[d] < rank[nd]


# ── Preview phase: every driver synthetic → no penalty, original order kept ─
def test_preview_phase_all_estimates_unaffected():
    estimates = {d: 90.0 + i * 0.2 for i, d in enumerate(FIELD)}
    merged = apply_qualifying_data(_grid(FIELD), estimates,
                                   fallback_times=estimates)
    # No driver flagged missing; ranks follow the estimate order exactly.
    assert not merged["QualifyingDataMissing"].any()
    order = merged.sort_values("QualifyingRank")["Driver"].tolist()
    assert order == FIELD


def test_complete_session_all_timed_unaffected():
    merged = apply_qualifying_data(_grid(FIELD), _times(FIELD),
                                   fallback_times={d: 90.0 for d in FIELD})
    assert not merged["QualifyingDataMissing"].any()


# ── Official grid ordering of no-time drivers ──────────────────────────────
def test_grid_positions_order_no_time_drivers():
    timed = ["VER", "NOR", "PIA", "RUS", "LEC", "HAM", "ALO", "GAS"]
    # STR officially ahead of SAI on the grid → STR should rank ahead of SAI.
    grid = {"STR": 19, "SAI": 21}
    merged = apply_qualifying_data(_grid(FIELD), _times(timed),
                                   fallback_times={d: 90.0 for d in FIELD},
                                   grid_positions=grid)
    rank = merged.set_index("Driver")["QualifyingRank"]
    assert rank["STR"] < rank["SAI"]
    assert rank["STR"] > rank[timed].max()


# ── Monaco scenario: grid position disproportionately important ────────────
def test_monaco_no_time_driver_cannot_steal_pole():
    """At Monaco, overtaking is near-impossible — a no-time driver wrongly
    seated at the front would catastrophically corrupt the race prediction.
    Assert the fix holds with Monaco-like tight quali gaps (~0.1s)."""
    monaco_field = ["LEC", "VER", "NOR", "PIA", "RUS", "HAM", "SAI", "ALO"]
    timed = [d for d in monaco_field if d != "SAI"]   # SAI's only flying lap deleted
    real = {d: 70.0 + i * 0.08 for i, d in enumerate(timed)}   # tight gaps
    fallback = {d: 70.0 for d in monaco_field}
    fallback["SAI"] = 69.0                    # optimistic — would be pole
    merged = apply_qualifying_data(_grid(monaco_field), real,
                                   fallback_times=fallback,
                                   rain_probability=0.0)
    order = merged.sort_values("QualifyingRank")["Driver"].tolist()
    assert order[0] == "LEC"                  # real pole preserved
    assert order[-1] == "SAI"                 # no-time driver dead last
    assert merged.set_index("Driver")["GridAdvantage"]["SAI"] < 0


def test_timed_drivers_helper_filters_nan_and_none():
    assert _timed_drivers({"A": 90.0, "B": float("nan"), "C": None, "D": 91.0}) == {"A", "D"}
    assert _timed_drivers({}) == set()
    assert _timed_drivers(None) == set()
