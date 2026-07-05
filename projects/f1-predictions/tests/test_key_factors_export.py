"""Tests for the explainability (keyFactors) export helper.

Exercises `export_website_data._build_key_factors` — the bridge between the L1
feature matrix + model importances and the plain-language keyFactors surfaced
on each classification entry.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import pytest

import export_website_data as ewd

# The factor generator lives in the shared monorepo package and the export
# degrades to omitting keyFactors without it; these tests exercise the wired
# path, so skip (rather than fail) in a standalone env without the package.
pytest.importorskip("motorsport_core.explain")


class _FakeModel:
    def __init__(self, importances):
        self.feature_importances_ = np.asarray(importances, dtype=float)


def _make_merged():
    # Three drivers, a couple of real feature columns from DEFAULT_FEATURE_COLS.
    return pd.DataFrame(
        {
            "Driver": ["VER", "HAM", "NOR"],
            "BestLapTime": [78.0, 80.0, 79.0],       # lower is better
            "CurrentForm": [90.0, 30.0, 60.0],       # higher is better
            "TeamPerformanceScore": [95.0, 40.0, 70.0],
        }
    )


def test_key_factors_labels_are_plain_language():
    merged = _make_merged()
    feat_cols = ["BestLapTime", "CurrentForm", "TeamPerformanceScore"]
    gb = _FakeModel([0.5, 0.3, 0.2]).feature_importances_
    xgb = _FakeModel([0.5, 0.3, 0.2]).feature_importances_
    out = ewd._build_key_factors(merged, feat_cols, gb, xgb, top_k=4)
    assert set(out.keys()) == {"VER", "HAM", "NOR"}
    allowed = {
        "Qualifying pace", "Recent form", "Circuit history", "Team performance",
        "Reliability risk", "Weather", "Race strategy", "Experience",
    }
    for factors in out.values():
        for f in factors:
            assert f["factor"] in allowed  # no algorithm names leak
            assert 0.0 <= f["weight"] <= 1.0
            assert f["direction"] in {"advantage", "risk", "neutral"}


def test_key_factors_direction_signs_lower_is_better():
    merged = _make_merged()
    feat_cols = ["BestLapTime", "CurrentForm", "TeamPerformanceScore"]
    imp = np.array([0.5, 0.3, 0.2])
    out = ewd._build_key_factors(merged, feat_cols, imp, imp, top_k=4)
    # VER: fastest lap (low) + best form + best team -> all advantages.
    ver = {f["factor"]: f["direction"] for f in out["VER"]}
    assert ver.get("Qualifying pace") == "advantage"
    # HAM: slowest lap (high) + worst form -> risks.
    ham = {f["factor"]: f["direction"] for f in out["HAM"]}
    assert ham.get("Qualifying pace") == "risk"
    assert ham.get("Recent form") == "risk"


def test_key_factors_graceful_without_driver_column():
    merged = pd.DataFrame({"BestLapTime": [78.0, 80.0]})
    out = ewd._build_key_factors(merged, ["BestLapTime"], np.array([1.0]),
                                 np.array([1.0]))
    assert out == {}


def test_key_factors_ignores_unmapped_features():
    merged = pd.DataFrame({
        "Driver": ["A", "B", "C"],
        "SomeUnknownFeature": [1.0, 2.0, 3.0],
    })
    out = ewd._build_key_factors(merged, ["SomeUnknownFeature"],
                                 np.array([1.0]), np.array([1.0]))
    # No mapped feature -> no factors at all.
    assert out == {}


def test_key_factors_output_matches_schema():
    from tests.test_website_data_schema import KeyFactor

    merged = _make_merged()
    feat_cols = ["BestLapTime", "CurrentForm", "TeamPerformanceScore"]
    imp = np.array([0.5, 0.3, 0.2])
    out = ewd._build_key_factors(merged, feat_cols, imp, imp)
    for factors in out.values():
        for f in factors:
            KeyFactor(**f)  # validates factor/weight/direction shape
