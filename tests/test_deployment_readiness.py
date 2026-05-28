"""Production stabilisation invariants.

This module locks in the Phase 10 freeze decisions as executable
contracts. If any of these tests fail, the production path has drifted
from the freeze and the failure MUST be triaged before merge to main.

The contracts mirror the success criteria in the Phase 11 brief:

* production_model.py is the ONLY canonical inference path
* It exclusively uses the Phase 7 static weekend feature set
* No archived dynamic column is reachable from production code
* The feature flag defaults to OFF and a falsy environment is a no-op
* The variant string is real (registered in ``benchmark_models.VARIANTS``)
* The backfill pipeline is idempotent — re-running on the same season
  does not duplicate or corrupt rows

The deployment_check.py CLI runs the same invariants and exits non-zero
on any failure, so this module pulls double duty as the CI gate.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import duckdb
import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Canonical-set invariants
# --------------------------------------------------------------------------- #


def test_canonical_weekend_set_is_phase_7_only() -> None:
    """The canonical production feature set is the 7-column Phase 7
    static lineup. Nothing else."""
    from models.weekend_features import (
        ARCHIVED_DYNAMIC_COLUMNS,
        PHASE_7_STATIC_COLUMNS,
        WEEKEND_FEATURE_COLUMNS,
    )
    assert WEEKEND_FEATURE_COLUMNS == PHASE_7_STATIC_COLUMNS
    assert len(WEEKEND_FEATURE_COLUMNS) == 7
    # None of the archived columns may leak into the canonical set.
    for col in ARCHIVED_DYNAMIC_COLUMNS:
        assert col not in WEEKEND_FEATURE_COLUMNS, (
            f"archived column {col!r} must not be in the production set"
        )


def test_archived_columns_constants_documented() -> None:
    """The archived constants exist and are exactly the three known
    demoted columns."""
    from models.weekend_features import ARCHIVED_DYNAMIC_COLUMNS
    assert set(ARCHIVED_DYNAMIC_COLUMNS) == {
        "fp2_deg_slope", "q_vs_fp2_pace_delta", "intra_stint_drift",
    }


# --------------------------------------------------------------------------- #
# Production model facade invariants
# --------------------------------------------------------------------------- #


def test_production_variant_matches_freeze_decision() -> None:
    """The production model variant string must equal the Phase 10 freeze."""
    from models.production_model import PRODUCTION_MODEL_VARIANT
    assert PRODUCTION_MODEL_VARIANT == "regime_routed_with_weekend_static"


def test_production_variant_is_registered() -> None:
    from benchmark_models import VARIANTS
    from models.production_model import PRODUCTION_MODEL_VARIANT
    assert PRODUCTION_MODEL_VARIANT in VARIANTS


def test_production_module_does_not_reference_archived_columns() -> None:
    """Static analysis: source text of production_model.py must not name
    any archived dynamic column."""
    from models.weekend_features import ARCHIVED_DYNAMIC_COLUMNS

    src = (PROJECT_ROOT / "models" / "production_model.py").read_text()
    for col in ARCHIVED_DYNAMIC_COLUMNS:
        assert col not in src, (
            f"production_model.py must not reference archived column {col!r}"
        )


def test_production_module_does_not_reference_research_variants() -> None:
    """Static analysis: the only variant production_model imports/uses
    is regime_routed_with_weekend_static."""
    src = (PROJECT_ROOT / "models" / "production_model.py").read_text()
    forbidden = (
        "moe_routed_three_layer",
        "probabilistic_three_layer",
        "temporally_robust_probabilistic",
        "predict_moe",
        "predict_temporally_robust",
        "predict_probabilistic",
        # Phase 8 full (non-static) variant is research only.
        "predict_regime_routed_with_weekend\b",
    )
    # We allow predict_regime_routed_with_weekend_static (production) but
    # NOT bare predict_regime_routed_with_weekend (Phase 8 full).
    for needle in forbidden[:-1]:
        assert needle not in src, (
            f"production_model.py must not reference {needle!r}"
        )
    # Check the static-vs-full distinction with a real boundary check.
    bare_phase8 = re.findall(
        r"\bpredict_regime_routed_with_weekend\b(?!_static)", src
    )
    assert not bare_phase8, (
        "production_model.py must not call predict_regime_routed_with_weekend "
        "(the Phase 8 full variant). Use the _static suffix."
    )


# --------------------------------------------------------------------------- #
# Feature flag safety
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _isolate_env():
    saved = os.environ.pop("F1_PRODUCTION_MODEL_ENABLED", None)
    yield
    os.environ.pop("F1_PRODUCTION_MODEL_ENABLED", None)
    if saved is not None:
        os.environ["F1_PRODUCTION_MODEL_ENABLED"] = saved


def test_flag_off_by_default_in_clean_environment() -> None:
    from models.production_model import is_enabled
    os.environ.pop("F1_PRODUCTION_MODEL_ENABLED", None)
    assert is_enabled() is False


def test_flag_off_does_not_trigger_inference() -> None:
    """When the flag is unset, simply importing or calling is_enabled()
    must not invoke any heavy inference machinery. The function must be
    a cheap dictionary lookup."""
    import time
    from models.production_model import is_enabled
    os.environ.pop("F1_PRODUCTION_MODEL_ENABLED", None)
    t0 = time.perf_counter()
    for _ in range(10_000):
        assert is_enabled() is False
    elapsed = time.perf_counter() - t0
    # 10k calls in well under a second — the flag check is O(1) env read.
    assert elapsed < 1.0, f"is_enabled() too slow: {elapsed:.3f}s for 10k calls"


def test_live_production_paths_do_not_invoke_production_model_unless_flag_on() -> None:
    """gp_weekend.py and export_website_data.py do NOT import
    production_model. The freeze is staged-but-not-flipped by design.

    If this test starts failing the live pipeline is now calling the
    production model — verify the feature flag is correctly gating that
    call before merging.
    """
    for filename in ("gp_weekend.py", "export_website_data.py"):
        path = PROJECT_ROOT / filename
        if not path.exists():
            continue
        src = path.read_text()
        if "from models.production_model" in src or "import production_model" in src:
            # The wiring exists — verify it's gated by is_enabled().
            assert "is_enabled" in src, (
                f"{filename} imports production_model but does not check "
                f"is_enabled() — feature flag is bypassed"
            )


# --------------------------------------------------------------------------- #
# Determinism invariants (sanity-checked again here for the merge gate)
# --------------------------------------------------------------------------- #


def _build_minimal_frame_chain(n_prior: int):
    from benchmark_models import RoundFrame
    from models.track_archetype import get_archetype

    drivers = [f"D{i:02d}" for i in range(1, 21)]
    frames = []
    for r in range(1, n_prior + 2):
        df = pd.DataFrame({
            "driver": drivers,
            "predicted": list(range(1, 21)),
            "actual": list(range(1, 21)),
            "predicted_lap_time": [90.0 + i * 0.1 for i in range(20)],
        })
        frames.append(
            RoundFrame(
                season=2024,
                round=r,
                gp_key="Bahrain",
                archetype=get_archetype("Bahrain"),
                df=df,
            )
        )
    return frames


def test_production_predict_is_deterministic_across_calls() -> None:
    from models.production_model import predict_for_round

    frames = _build_minimal_frame_chain(n_prior=8)
    target = frames[-1]
    prior = frames[:-1]
    results = [predict_for_round(target, prior).predicted_positions for _ in range(3)]
    assert results[0] == results[1] == results[2]


# --------------------------------------------------------------------------- #
# Backfill idempotency
# --------------------------------------------------------------------------- #


def test_backfill_idempotency_via_upsert() -> None:
    """Run an INSERT OR REPLACE round-trip on an in-memory DB and confirm
    the row count is stable across re-runs."""
    from backfill_2018_2022 import BackfillRow, upsert_rows

    # Build the schema in a temp DuckDB file.
    tmp = PROJECT_ROOT / "data" / "_test_backfill_idempotency.duckdb"
    if tmp.exists():
        tmp.unlink()
    con = duckdb.connect(str(tmp))
    con.execute("""
        CREATE TABLE historical_predictions (
            season INTEGER NOT NULL,
            round INTEGER NOT NULL,
            driver VARCHAR NOT NULL,
            predicted_position INTEGER,
            actual_position INTEGER,
            predicted_lap_time DOUBLE,
            source VARCHAR DEFAULT 'fastf1',
            PRIMARY KEY (season, round, driver)
        )
    """)
    con.close()

    rows = [
        BackfillRow(2018, 1, "HAM", 1, 1, 90.0),
        BackfillRow(2018, 1, "VET", 2, 4, 90.5),
        BackfillRow(2018, 1, "BOT", 3, 2, 90.7),
    ]
    try:
        n1 = upsert_rows(rows, tmp)
        n2 = upsert_rows(rows, tmp)
        assert n1 == n2 == 3

        # Re-running with mutated values should UPDATE not duplicate.
        mutated = [BackfillRow(2018, 1, "HAM", 1, 2, 89.9)]  # actual flipped
        upsert_rows(mutated, tmp)

        con = duckdb.connect(str(tmp), read_only=True)
        total = con.execute("SELECT COUNT(*) FROM historical_predictions").fetchone()[0]
        ham_actual = con.execute(
            "SELECT actual_position FROM historical_predictions "
            "WHERE season=2018 AND round=1 AND driver='HAM'"
        ).fetchone()[0]
        con.close()
        assert total == 3, f"row count drifted: expected 3, got {total}"
        assert ham_actual == 2, f"upsert did not update HAM actual: got {ham_actual}"
    finally:
        if tmp.exists():
            tmp.unlink()


# --------------------------------------------------------------------------- #
# Benchmark default lineup
# --------------------------------------------------------------------------- #


def test_benchmark_default_variants_are_production_lineup_only() -> None:
    """The benchmark CLI default --variants must include exactly the
    production lineup and no experimental variants."""
    import importlib
    import sys

    if "benchmark_models" in sys.modules:
        importlib.reload(sys.modules["benchmark_models"])
    bm = importlib.import_module("benchmark_models")

    parser = None
    for name in dir(bm):
        obj = getattr(bm, name)
        if callable(obj) and name == "main":
            # Build the parser by introspecting `main`'s subparsers via argv
            # parse — easiest is to call `argparse` indirectly through CLI help.
            break
    # Direct check on the documented default string.
    src = (PROJECT_ROOT / "benchmark_models.py").read_text()
    assert 'default=(\n            "baseline,elite_head_plus_hybrid,"\n            "regime_routed_with_weekend_static"\n        )' in src, (
        "benchmark_models.py default variants string drifted from the freeze"
    )
    # Confirm RESEARCH_VARIANTS includes the demoted experiments.
    expected_research = {
        "moe_routed_three_layer",
        "probabilistic_three_layer",
        "temporally_robust_probabilistic",
        "regime_routed_three_layer",
        "regime_routed_with_weekend",  # Phase 8 full
    }
    assert expected_research.issubset(set(bm.RESEARCH_VARIANTS)), (
        f"RESEARCH_VARIANTS missing entries: "
        f"{expected_research - set(bm.RESEARCH_VARIANTS)}"
    )
