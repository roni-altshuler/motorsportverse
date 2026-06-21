"""Loader for the pre-race weekend feature parquet.

The parquet is built by ``extract_weekend_features.py`` from the FastF1
cache. This module provides a clean lookup API for the prediction
pipeline to enrich the elite-head training set with weekend signals.

Columns delivered to the elite head
-----------------------------------
* ``fp2_longrun_pace_norm`` — median long-run lap time / session's fastest.
  1.0 = fastest long-run pace; >1 = slower.
* ``fp2_longrun_consistency`` — std of long-run lap times (seconds).
* ``q_sector_dominance_norm`` — ideal-lap (best S1+S2+S3) / session's fastest.
* ``q_top_speed_norm`` — driver max trap speed / session's max.
* ``race_track_temp`` — track temperature near race start.
* ``race_air_temp`` — air temperature.
* ``race_rainfall`` — 1.0 if Q rainfall flag was true, else 0.0.

Coverage caveat
---------------
Some rounds (e.g. 2025 R13-R24 at the time of writing) are not yet in
the local FastF1 cache. Lookups for those rounds return rows filled
with NaN — the elite-head imputer handles them gracefully so the
benchmark can still run end-to-end.

Leak-safety
-----------
All seven features are KNOWN at pre-race time. They depend only on
FP2, Q and the early-race weather snapshot — which are all logged
before lights-out. No future-race contamination.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARQUET = PROJECT_ROOT / "data" / "weekend_features.parquet"


# --------------------------------------------------------------------------- #
# Production-approved columns (the canonical set after the Phase 10 freeze)
# --------------------------------------------------------------------------- #
# These seven columns are the production-approved weekend feature set. They
# were validated through Phases 7-9 (multi-season expansion) and consistently
# outperform every alternative architecture this codebase has produced.
# Treat as load-bearing — do not modify the order or content without a
# follow-up benchmark cycle.
PHASE_7_STATIC_COLUMNS: tuple[str, ...] = (
    "fp2_longrun_pace_norm",
    "fp2_longrun_consistency",
    "q_sector_dominance_norm",
    "q_top_speed_norm",
    "race_track_temp",
    "race_air_temp",
    "race_rainfall",
)

# Canonical alias used by production code paths. After Phase 10 this is the
# Phase 7 static set; the Phase 8 dynamic curves were demoted to research-
# only after their combined importance dropped to 1.6% under a 3-season
# training prior (see docs/BENCHMARK_PHASE_9.md).
WEEKEND_FEATURE_COLUMNS: tuple[str, ...] = PHASE_7_STATIC_COLUMNS

# --------------------------------------------------------------------------- #
# Research-only columns (NOT in any production training path)
# --------------------------------------------------------------------------- #
# These three dynamic Phase-8 columns are preserved in the parquet on disk
# for reproducibility / future research, but are NOT in the canonical
# WEEKEND_FEATURE_COLUMNS tuple. Production callers must NEVER pull these
# into training. Research benchmarks (``benchmark_models.py --include-research``)
# can opt in via WEEKEND_FEATURE_COLUMNS_WITH_RESEARCH below.
#
# Rationale for archival (do not re-promote without new evidence):
# * 2-season backtest: 4.1% combined importance (gate was >5%)
# * 3-season backtest: 1.6% combined importance — went the wrong direction
#   under added data
# * The Phase 8 full variant regressed winner-hit by -2.1pp on apples-to-
#   apples coverage vs the Phase 7 static set.
ARCHIVED_DYNAMIC_COLUMNS: tuple[str, ...] = (
    "fp2_deg_slope",
    "q_vs_fp2_pace_delta",
    "intra_stint_drift",
)

# Convenience tuple for research benchmark code that wants the legacy 10-
# column set. Production code MUST NOT import this.
WEEKEND_FEATURE_COLUMNS_WITH_RESEARCH: tuple[str, ...] = (
    *PHASE_7_STATIC_COLUMNS,
    *ARCHIVED_DYNAMIC_COLUMNS,
)


_cache: dict[str, pd.DataFrame] = {}


def _load(path: Path = DEFAULT_PARQUET) -> pd.DataFrame:
    key = str(path)
    if key not in _cache:
        if not path.exists():
            _cache[key] = pd.DataFrame(
                columns=("season", "round", "driver", *WEEKEND_FEATURE_COLUMNS)
            )
            return _cache[key]
        df = pd.read_parquet(path)
        df["season"] = df["season"].astype(int)
        df["round"] = df["round"].astype(int)
        df["driver"] = df["driver"].astype(str)
        _cache[key] = df
    return _cache[key]


def get_weekend_features(
    season: int,
    round_: int,
    drivers: list[str],
    *,
    path: Path = DEFAULT_PARQUET,
) -> pd.DataFrame:
    """Return one row per requested driver with weekend features attached.

    Drivers / rounds without coverage receive NaN values for every
    weekend column. The output preserves the input ``drivers`` order.
    """
    src = _load(path)
    base = pd.DataFrame({"driver": [str(d) for d in drivers]})
    base["season"] = int(season)
    base["round"] = int(round_)
    if src.empty:
        for col in WEEKEND_FEATURE_COLUMNS:
            base[col] = float("nan")
        return base
    subset = src[(src["season"] == season) & (src["round"] == round_)][
        ["driver", *WEEKEND_FEATURE_COLUMNS]
    ]
    merged = base.merge(subset, on="driver", how="left")
    return merged[["season", "round", "driver", *WEEKEND_FEATURE_COLUMNS]]


def attach_weekend_to_history(
    history_df: pd.DataFrame,
    *,
    path: Path = DEFAULT_PARQUET,
) -> pd.DataFrame:
    """Left-join the weekend parquet onto a DB-style history frame.

    ``history_df`` must contain ``season``, ``round``, ``driver``.
    Returned frame is the same shape with the seven weekend columns
    appended (NaN where coverage is missing).
    """
    src = _load(path)
    if src.empty:
        out = history_df.copy()
        for col in WEEKEND_FEATURE_COLUMNS:
            out[col] = float("nan")
        return out
    merged = history_df.merge(
        src[["season", "round", "driver", *WEEKEND_FEATURE_COLUMNS]],
        on=["season", "round", "driver"],
        how="left",
    )
    return merged


def clear_cache() -> None:
    """For tests — drop the in-memory parquet cache."""
    _cache.clear()


__all__ = [
    "WEEKEND_FEATURE_COLUMNS",
    "get_weekend_features",
    "attach_weekend_to_history",
    "clear_cache",
]
