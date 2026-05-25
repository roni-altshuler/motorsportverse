"""Round-trip tests for the conformal residual cache."""
from __future__ import annotations

import numpy as np
import pytest

from models.conformal import (
    load_residual_history,
    save_round_residuals,
)


def test_save_then_load_round_trips(tmp_path):
    save_round_residuals(2026, 1, [0.5, -0.3, 0.2], cache_dir=tmp_path)
    save_round_residuals(2026, 2, [0.1, 0.4], cache_dir=tmp_path)
    out = load_residual_history(
        current_season=2026, current_round=3, cache_dir=tmp_path
    )
    # Absolute residuals preserved across both rounds.
    assert sorted(out.tolist()) == sorted([0.5, 0.3, 0.2, 0.1, 0.4])


def test_load_excludes_at_or_after_cutoff(tmp_path):
    save_round_residuals(2026, 1, [1.0], cache_dir=tmp_path)
    save_round_residuals(2026, 2, [2.0], cache_dir=tmp_path)
    save_round_residuals(2026, 3, [3.0], cache_dir=tmp_path)
    out = load_residual_history(
        current_season=2026, current_round=2, cache_dir=tmp_path
    )
    # Only round 1 is prior; rounds 2 and 3 are excluded.
    np.testing.assert_array_equal(out, [1.0])


def test_load_respects_max_seasons_back(tmp_path):
    save_round_residuals(2024, 22, [9.0], cache_dir=tmp_path)
    save_round_residuals(2025, 22, [5.0], cache_dir=tmp_path)
    save_round_residuals(2026, 1, [1.0], cache_dir=tmp_path)
    out = load_residual_history(
        current_season=2026,
        current_round=2,
        max_seasons_back=1,
        cache_dir=tmp_path,
    )
    # 2024 row excluded (older than the cutoff).
    assert 9.0 not in out.tolist()
    assert 5.0 in out.tolist()
    assert 1.0 in out.tolist()


def test_load_returns_empty_for_missing_dir(tmp_path):
    missing = tmp_path / "nope"
    out = load_residual_history(
        current_season=2026, current_round=5, cache_dir=missing
    )
    assert out.size == 0


def test_save_file_path_format(tmp_path):
    path = save_round_residuals(2026, 3, [0.1], cache_dir=tmp_path)
    assert path.name == "2026_round_03.json"
