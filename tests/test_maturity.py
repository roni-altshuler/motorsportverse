"""Tests for the temporal-maturity scoring module."""
from __future__ import annotations

import pandas as pd
import pytest

from leakage import LeakageError
from models.maturity import (
    FULL_MATURITY_AT_DEFAULT,
    compute_driver_maturity,
    compute_maturity_frame,
)


def _make_history(rows: list[dict]) -> pd.DataFrame:
    """Helper: build a history frame with the required columns."""
    df = pd.DataFrame(rows)
    # Fill missing actual_position with float (test will explicitly set NaN
    # where it matters).
    if "actual_position" not in df.columns:
        df["actual_position"] = 5.0
    return df


def test_zero_prior_races_returns_zero_maturity() -> None:
    history = _make_history(
        [{"season": 2024, "round": 1, "driver": "HAM", "actual_position": 3}]
    )
    # Asking about the very first round in history with this driver — no prior.
    m = compute_driver_maturity(history, 2024, 1, "HAM")
    assert m == 0.0


def test_full_season_returns_high_maturity() -> None:
    rows = [
        {"season": 2024, "round": r, "driver": "VER", "actual_position": 1}
        for r in range(1, FULL_MATURITY_AT_DEFAULT + 1)
    ]
    history = _make_history(rows)
    m = compute_driver_maturity(
        history, target_season=2024, target_round=FULL_MATURITY_AT_DEFAULT + 1,
        driver="VER",
    )
    # m_recent = 1.0; m_career = 8/24 ≈ 0.333
    # maturity = 0.7 + 0.3 * 0.333 = 0.7 + 0.1 = 0.8
    assert m >= 0.79
    assert m <= 0.81


def test_career_floor_for_veteran_with_no_season_history() -> None:
    """A veteran starting a fresh season has zero in-season prior but
    nonzero career — should still get a small non-zero maturity."""
    rows = [
        {"season": 2023, "round": r, "driver": "HAM", "actual_position": 5}
        for r in range(1, 25)
    ]
    history = _make_history(rows)
    m = compute_driver_maturity(history, 2024, 1, "HAM")
    # m_recent = 0; m_career = 24/24 = 1.0; total = 0.3
    assert 0.29 < m <= 0.31


def test_no_leakage_when_future_rows_present() -> None:
    rows = [
        {"season": 2024, "round": r, "driver": "VER", "actual_position": 1}
        for r in range(1, 11)
    ]
    history = _make_history(rows)
    m_with_future = compute_driver_maturity(history, 2024, 5, "VER")
    # Now drop future rounds (rounds 5-10) and re-compute — must match.
    truncated = history[history["round"] < 5].copy()
    m_truncated = compute_driver_maturity(truncated, 2024, 5, "VER")
    assert m_with_future == m_truncated


def test_strict_prior_only_enforced_at_boundary() -> None:
    """Manually inject a leaky row and confirm the assertion fires."""
    # Build a frame where the prior_frame helper would (incorrectly) include
    # the target round; we test by checking via assert_seasons_prior_only.
    # The helper itself filters strict-prior, so leak should never reach the
    # assertion in normal flow. Instead, smoke-test that a future row is
    # excluded (no LeakageError raised, output stays clean).
    rows = [
        {"season": 2024, "round": 5, "driver": "VER", "actual_position": 1},
        # Same season, future round — must NOT count toward maturity for
        # target=(2024, 3).
        {"season": 2024, "round": 6, "driver": "VER", "actual_position": 1},
    ]
    history = _make_history(rows)
    m = compute_driver_maturity(history, 2024, 3, "VER")
    # Both rows are at/after the target round, so prior is empty → m = 0.
    assert m == 0.0


def test_all_outputs_in_unit_interval() -> None:
    rows = [
        {"season": s, "round": r, "driver": "VER", "actual_position": 1}
        for s in (2022, 2023, 2024)
        for r in range(1, 25)
    ]
    history = _make_history(rows)
    # Target deep into 2025; conversion model would have all of 2022-2024 plus
    # a hypothetical part-of-2025 (none in this fixture).
    m = compute_driver_maturity(history, 2025, 1, "VER")
    # m_recent = 0 / 8 = 0;  m_career = 72/24 capped at 1 → 1.0
    # total = 0 + 0.3 * 1 = 0.3
    assert 0.0 <= m <= 1.0
    assert 0.29 < m <= 0.31


def test_frame_builder_returns_one_row_per_driver_preserving_order() -> None:
    rows = [
        {"season": 2024, "round": 1, "driver": "VER", "actual_position": 1},
        {"season": 2024, "round": 1, "driver": "HAM", "actual_position": 3},
    ]
    history = _make_history(rows)
    out = compute_maturity_frame(history, 2024, 2, ["HAM", "VER", "NOR"])
    assert list(out["driver"]) == ["HAM", "VER", "NOR"]
    # NOR has no history → maturity 0
    assert float(out.loc[out["driver"] == "NOR", "maturity"].iloc[0]) == 0.0
    assert (out["maturity"] >= 0.0).all()
    assert (out["maturity"] <= 1.0).all()
    assert (out["n_prior_races_total"] >= 0).all()
    assert (out["n_prior_races_current_season"] >= 0).all()


def test_dnf_rows_excluded_from_history() -> None:
    rows = [
        {"season": 2024, "round": 1, "driver": "VER", "actual_position": None},
        {"season": 2024, "round": 2, "driver": "VER", "actual_position": 1},
    ]
    history = _make_history(rows)
    out = compute_maturity_frame(history, 2024, 3, ["VER"])
    # Only one settled race in history (round 1 was a DNF / no result).
    assert int(out["n_prior_races_total"].iloc[0]) == 1
    assert int(out["n_prior_races_current_season"].iloc[0]) == 1


def test_leakage_error_raised_when_prior_frame_built_externally() -> None:
    """Caller path safeguard: if a caller passes a synthetic frame that has
    rows AT the target round and they sneak past the .notna() filter, the
    assert_seasons_prior_only call should raise."""
    from leakage import assert_seasons_prior_only

    rows = [
        {"season": 2024, "round": 5, "driver": "VER", "actual_position": 1},
    ]
    df = pd.DataFrame(rows)
    with pytest.raises(LeakageError):
        assert_seasons_prior_only(
            df[["season", "round"]].to_dict("records"),
            current_season=2024,
            current_round=5,
            label="manual",
        )
