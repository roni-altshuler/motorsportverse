"""Per-lap race-pace regression model — substrate for the race simulator.

Why this exists
---------------
The legacy ``RaceProjectionScore`` in [f1_prediction_utils.py:1122] is a
hand-tuned weighted sum of 14 terms in which qualifying time can carry up to
82% of the weight at low-overtaking circuits, and 7 game-theory coefficients
were fit on a 3-round sample.  Per the audit this is the single biggest
accuracy bottleneck: pole-sitter is heavily over-weighted; race pace, pit
strategy, safety-car lottery, and traffic dynamics are not learned.

This module is the replacement substrate.  It trains a per-lap lap-time
regressor on FastF1's lap-by-lap race telemetry with features the race
simulator in ``models/race_simulator.py`` (built in Step 2 of the A-P1.1
push) can reproduce one lap at a time.  The simulator runs ``predict_lap_times``
2000 × N_drivers × N_laps times per race; trees are fast enough for that
without a GPU.

Track A-P1.1 build steps
------------------------
* **Step 1 (this file)** — data loading + feature engineering + train +
  predict on the lap-level data.  Pure-additive; no integration yet.
* **Step 2** (``models/race_simulator.py``) — Monte Carlo race simulator
  that consumes this model's predictions lap-by-lap, handles pit stops,
  SC/VSC events, and traffic, and outputs P(finishing position).
* **Step 3** — Refactor ``apply_race_postprocessing`` in
  ``f1_prediction_utils.py`` to optionally route through the simulator
  (legacy formula remains behind a flag for A/B).

Constraints honoured
--------------------
* Pure-additive — does not touch ``f1_prediction_utils.py``, ``leakage.py``,
  ``forward_eval.py``, ``advanced_models.py``, or any exporter.
* Single FastF1 entry point (``_load_race_session``) so tests monkeypatch
  one function and never hit the network.
* Lap-level leakage discipline: every feature on a given lap row references
  only state up to and including that lap (gap to car ahead at end of lap,
  current tyre + age, current track-status flags).  No "what happens N laps
  later" features.
* Persistence through ``models/registry.py`` (A-P0.3), keyed by
  (season, round) just like the qualifying-time ensemble.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

# XGBoost is already a hard dep via requirements.txt; importing it here is fine.
try:
    from xgboost import XGBRegressor

    _XGB_AVAILABLE = True
except ImportError:  # pragma: no cover — xgboost is a required dep
    _XGB_AVAILABLE = False
    XGBRegressor = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)

# Compound code mapping.  Stable integer encoding so the trees can split on
# specific compounds rather than us one-hot-blowing the feature width.
# UNKNOWN catches the sporadic NaN / "TEST" rows FastF1 occasionally emits.
COMPOUND_CODES: dict[str, int] = {
    "SOFT": 0,
    "MEDIUM": 1,
    "HARD": 2,
    "INTERMEDIATE": 3,
    "WET": 4,
    "UNKNOWN": 5,
}

# FastF1 TrackStatus values that map to race-state flags.  The field is a
# concatenation of single-digit codes (e.g. "27" = yellow + red), so we test
# membership of each code in the string.  Reference:
#   1 = AllClear, 2 = Yellow, 3 = SCDeployed (older), 4 = SCDeployed,
#   5 = RedFlag, 6 = VSC, 7 = VSCEnding.
TRACK_STATUS_SC_CODES = {"4"}
TRACK_STATUS_VSC_CODES = {"6", "7"}
TRACK_STATUS_YELLOW_CODES = {"2"}

# Leader sentinel: a value much larger than any plausible inter-car gap.
# Tree models split cleanly on this; using NaN would force imputation.
LEADER_GAP_SENTINEL_S: float = 30.0

# Features the model trains on.  The order is load-bearing — ``predict_lap_times``
# extracts these columns and feeds them into the artifacts in this order.
FEATURE_COLUMNS: tuple[str, ...] = (
    "driver_id",
    "team_id",
    "circuit_id",
    "lap_number",
    "lap_progress",
    "track_position",
    "tyre_compound_code",
    "tyre_age_laps",
    "gap_to_car_ahead_s",
    "gap_to_car_behind_s",
    "sc_active",
    "vsc_active",
    "yellow_active",
    "air_temp_c",
    "track_temp_c",
    "rain_intensity",
)

TARGET_COLUMN: str = "lap_time_s"


# --------------------------------------------------------------------------- #
# Row schema
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LapRecord:
    """One lap from one driver in one race — the training-data atom.

    All fields are either primitives or ``None`` for missing data.  The
    feature engineer in ``laps_to_features`` decides how to encode each
    field (sentinel value, code lookup, drop row, …).
    """

    season: int
    round: int
    circuit_key: str
    driver: str
    team: str
    lap_number: int
    lap_time_s: float
    total_laps: int
    track_position: int
    tyre_compound: str            # SOFT / MEDIUM / HARD / INTERMEDIATE / WET / UNKNOWN
    tyre_age_laps: int
    sc_active: bool
    vsc_active: bool
    yellow_active: bool
    gap_to_car_ahead_s: float | None
    gap_to_car_behind_s: float | None
    air_temp_c: float | None
    track_temp_c: float | None
    rain_intensity: float | None  # 0.0 → 1.0; FastF1 Rainfall is bool, so 0/1


# --------------------------------------------------------------------------- #
# FastF1 loader (single network surface, mocked in tests)
# --------------------------------------------------------------------------- #


def _load_race_session(season: int, round_num: int) -> Any:
    """Open + load a FastF1 race session with laps + weather.

    Isolated in its own function so tests monkeypatch the FastF1 surface in
    one place.  Returns the session object (FastF1's ``Session``).  Raises
    on FastF1 errors; callers catch and convert to per-round warnings.

    Cache is enabled lazily; the cache dir matches the existing convention
    in ``backfill_history.py`` (``f1_cache/`` relative to the project root).
    """
    # Lazy import so the module loads on machines without FastF1 installed.
    import fastf1  # noqa: PLC0415

    cache_dir = Path(__file__).resolve().parent.parent / "f1_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        fastf1.Cache.enable_cache(str(cache_dir))
    except Exception:  # noqa: BLE001 — cache is best-effort
        LOGGER.debug("race_pace: FastF1 cache enable failed", exc_info=True)

    session = fastf1.get_session(season, round_num, "R")
    session.load(laps=True, telemetry=False, weather=True, messages=False)
    return session


def load_race_laps(
    season: int,
    round_num: int,
    circuit_key: str | None = None,
) -> list[LapRecord]:
    """Pull lap-by-lap race data from FastF1, return as ``LapRecord``s.

    Returns an empty list on any error (network, cache miss, partial
    season data).  Per-driver outliers (e.g. SC laps, in-laps with anomalous
    times) are still emitted — the model sees the race-state flags and
    learns to weight them appropriately.

    The ``circuit_key`` argument is the project-internal key (matches the
    keys in [f1_prediction_utils.py::CIRCUIT_CHARACTERISTICS]); if omitted
    we attempt to read it from ``session.event['Location']``.
    """
    try:
        session = _load_race_session(season, round_num)
    except Exception as exc:  # noqa: BLE001 — every FastF1 failure path
        warnings.warn(f"[race_pace] {season} R{round_num}: session load failed ({exc})")
        return []

    laps_df = getattr(session, "laps", None)
    if laps_df is None or len(laps_df) == 0:
        return []

    weather_df = getattr(session, "weather_data", None)
    total_laps = int(laps_df["LapNumber"].max()) if "LapNumber" in laps_df.columns else 0
    if total_laps <= 0:
        return []

    if circuit_key is None:
        event = getattr(session, "event", None)
        circuit_key = (event or {}).get("Location", f"unknown_R{round_num}")

    records: list[LapRecord] = []
    for _, lap in laps_df.iterrows():
        record = _lap_row_to_record(
            lap=lap,
            laps_df=laps_df,
            weather_df=weather_df,
            season=season,
            round_num=round_num,
            circuit_key=circuit_key,
            total_laps=total_laps,
        )
        if record is not None:
            records.append(record)
    return records


def _lap_row_to_record(
    lap: pd.Series,
    laps_df: pd.DataFrame,
    weather_df: pd.DataFrame | None,
    season: int,
    round_num: int,
    circuit_key: str,
    total_laps: int,
) -> LapRecord | None:
    """Convert one FastF1 laps DataFrame row to a ``LapRecord``.

    Returns ``None`` for rows we can't recover meaningful data from — e.g.
    rows with no lap-time (DNF / pit-lap timings FastF1 sometimes ships as
    NaT) — so the caller filters cleanly.
    """
    lap_time = lap.get("LapTime")
    if pd.isna(lap_time):
        return None
    lap_time_s = _td_to_seconds(lap_time)
    if lap_time_s is None or lap_time_s <= 0:
        return None

    driver = str(lap.get("Driver", "")).upper()
    if not driver:
        return None
    team = str(lap.get("Team") or lap.get("Constructor") or "UNK").upper()
    lap_number = _safe_int(lap.get("LapNumber"))
    if lap_number is None or lap_number < 1:
        return None
    track_position = _safe_int(lap.get("Position")) or 0

    track_status = str(lap.get("TrackStatus") or "")
    sc_active = any(c in track_status for c in TRACK_STATUS_SC_CODES)
    vsc_active = any(c in track_status for c in TRACK_STATUS_VSC_CODES)
    yellow_active = any(c in track_status for c in TRACK_STATUS_YELLOW_CODES)

    compound_raw = str(lap.get("Compound") or "").upper()
    if compound_raw not in COMPOUND_CODES:
        compound_raw = "UNKNOWN"
    tyre_age = _safe_int(lap.get("TyreLife")) or 0

    gap_ahead, gap_behind = _compute_gaps(lap, laps_df, lap_number, track_position)

    air_temp, track_temp, rain_intensity = _weather_snapshot(weather_df, lap.get("Time"))

    return LapRecord(
        season=season,
        round=round_num,
        circuit_key=circuit_key,
        driver=driver,
        team=team,
        lap_number=lap_number,
        lap_time_s=float(lap_time_s),
        total_laps=total_laps,
        track_position=track_position,
        tyre_compound=compound_raw,
        tyre_age_laps=tyre_age,
        sc_active=sc_active,
        vsc_active=vsc_active,
        yellow_active=yellow_active,
        gap_to_car_ahead_s=gap_ahead,
        gap_to_car_behind_s=gap_behind,
        air_temp_c=air_temp,
        track_temp_c=track_temp,
        rain_intensity=rain_intensity,
    )


def _td_to_seconds(value: Any) -> float | None:
    """Convert pandas/numpy timedelta or numeric to seconds.  None on garbage."""
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    if hasattr(value, "total_seconds"):
        try:
            return float(value.total_seconds())
        except (TypeError, ValueError):
            return None
    return None


def _safe_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _compute_gaps(
    lap: pd.Series,
    laps_df: pd.DataFrame,
    lap_number: int,
    track_position: int,
) -> tuple[float | None, float | None]:
    """Gap to car ahead / behind at the end of this lap.

    We use the cumulative ``Time`` column (timestamp at end of lap).  For
    the car at position N, gap-to-ahead = my_time - position_(N-1)_time;
    gap-to-behind = position_(N+1)_time - my_time.  Returns ``None`` when
    a neighbour is missing (e.g. leader → no car ahead) or the timing
    column is absent.
    """
    if "Time" not in laps_df.columns or "Position" not in laps_df.columns:
        return None, None
    same_lap = laps_df[laps_df["LapNumber"] == lap_number]
    if same_lap.empty:
        return None, None
    my_time = _td_to_seconds(lap.get("Time"))
    if my_time is None:
        return None, None
    pos_to_time: dict[int, float] = {}
    for _, row in same_lap.iterrows():
        p = _safe_int(row.get("Position"))
        t = _td_to_seconds(row.get("Time"))
        if p is None or t is None:
            continue
        pos_to_time[p] = t
    gap_ahead: float | None = None
    if track_position > 1:
        ahead_time = pos_to_time.get(track_position - 1)
        if ahead_time is not None:
            gap_ahead = max(0.0, my_time - ahead_time)
    gap_behind: float | None = None
    behind_time = pos_to_time.get(track_position + 1)
    if behind_time is not None:
        gap_behind = max(0.0, behind_time - my_time)
    return gap_ahead, gap_behind


def _weather_snapshot(
    weather_df: pd.DataFrame | None,
    lap_time: Any,
) -> tuple[float | None, float | None, float | None]:
    """Nearest-time weather sample at the lap's end-of-lap timestamp."""
    if weather_df is None or len(weather_df) == 0 or lap_time is None:
        return None, None, None
    if "Time" not in weather_df.columns:
        return None, None, None
    target_s = _td_to_seconds(lap_time)
    if target_s is None:
        return None, None, None
    diffs = (weather_df["Time"].apply(_td_to_seconds) - target_s).abs()
    if diffs.empty:
        return None, None, None
    idx = diffs.idxmin()
    row = weather_df.loc[idx]
    air = row.get("AirTemp")
    track = row.get("TrackTemp")
    rain = row.get("Rainfall")
    return (
        float(air) if air is not None and not pd.isna(air) else None,
        float(track) if track is not None and not pd.isna(track) else None,
        (1.0 if bool(rain) else 0.0) if rain is not None and not pd.isna(rain) else None,
    )


# --------------------------------------------------------------------------- #
# Feature engineering
# --------------------------------------------------------------------------- #


def laps_to_features(
    laps: Sequence[LapRecord],
    label_encoders: dict[str, dict[str, int]] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    """Convert ``LapRecord``s to a feature matrix for training/inference.

    Returns the feature DataFrame plus a dict of label encoders so the same
    encoding can be applied to fresh data at inference time.  Unknown
    categorical values at inference time map to a sentinel id (``-1``).
    """
    if not laps:
        empty = pd.DataFrame(columns=[*FEATURE_COLUMNS, TARGET_COLUMN])
        return empty, label_encoders or {"driver": {}, "team": {}, "circuit": {}}

    encoders = label_encoders or {"driver": {}, "team": {}, "circuit": {}}
    rows: list[dict[str, Any]] = []
    for lap in laps:
        rows.append(
            {
                "driver_id": _encode(encoders["driver"], lap.driver),
                "team_id": _encode(encoders["team"], lap.team),
                "circuit_id": _encode(encoders["circuit"], lap.circuit_key),
                "lap_number": lap.lap_number,
                "lap_progress": (
                    lap.lap_number / lap.total_laps if lap.total_laps > 0 else 0.0
                ),
                "track_position": lap.track_position or 0,
                "tyre_compound_code": COMPOUND_CODES.get(lap.tyre_compound, COMPOUND_CODES["UNKNOWN"]),
                "tyre_age_laps": lap.tyre_age_laps,
                "gap_to_car_ahead_s": (
                    lap.gap_to_car_ahead_s
                    if lap.gap_to_car_ahead_s is not None
                    else LEADER_GAP_SENTINEL_S
                ),
                "gap_to_car_behind_s": (
                    lap.gap_to_car_behind_s
                    if lap.gap_to_car_behind_s is not None
                    else LEADER_GAP_SENTINEL_S
                ),
                "sc_active": int(lap.sc_active),
                "vsc_active": int(lap.vsc_active),
                "yellow_active": int(lap.yellow_active),
                # Weather defaults match the existing F1 baseline assumptions
                # in [f1_prediction_utils.py:344] — dry conditions, ambient
                # 25°C / track 35°C — when FastF1 doesn't have a snapshot.
                "air_temp_c": lap.air_temp_c if lap.air_temp_c is not None else 25.0,
                "track_temp_c": (
                    lap.track_temp_c if lap.track_temp_c is not None else 35.0
                ),
                "rain_intensity": (
                    lap.rain_intensity if lap.rain_intensity is not None else 0.0
                ),
                TARGET_COLUMN: lap.lap_time_s,
            }
        )
    df = pd.DataFrame(rows, columns=[*FEATURE_COLUMNS, TARGET_COLUMN])
    return df, encoders


def _encode(encoder: dict[str, int], key: str) -> int:
    """Stable label-encoding.  Unknown values at inference get id ``-1``."""
    if not key:
        return -1
    code = encoder.get(key)
    if code is None:
        # We mutate the encoder in-place during training so subsequent calls
        # see the same mapping.  At inference time the caller passes a
        # frozen encoder and unknown keys return -1 instead of being added.
        code = len(encoder)
        encoder[key] = code
    return code


def transform_features(
    laps: Sequence[LapRecord],
    encoders: dict[str, dict[str, int]],
) -> pd.DataFrame:
    """Inference-time feature builder.

    Uses a *frozen* encoder dict — unknown categorical values get id ``-1``
    instead of extending the codebook (otherwise inference would non-
    deterministically grow the feature space).
    """
    if not laps:
        return pd.DataFrame(columns=FEATURE_COLUMNS)
    frozen = {kind: dict(mapping) for kind, mapping in encoders.items()}
    rows: list[dict[str, Any]] = []
    for lap in laps:
        rows.append(
            {
                "driver_id": frozen["driver"].get(lap.driver, -1),
                "team_id": frozen["team"].get(lap.team, -1),
                "circuit_id": frozen["circuit"].get(lap.circuit_key, -1),
                "lap_number": lap.lap_number,
                "lap_progress": (
                    lap.lap_number / lap.total_laps if lap.total_laps > 0 else 0.0
                ),
                "track_position": lap.track_position or 0,
                "tyre_compound_code": COMPOUND_CODES.get(lap.tyre_compound, COMPOUND_CODES["UNKNOWN"]),
                "tyre_age_laps": lap.tyre_age_laps,
                "gap_to_car_ahead_s": (
                    lap.gap_to_car_ahead_s
                    if lap.gap_to_car_ahead_s is not None
                    else LEADER_GAP_SENTINEL_S
                ),
                "gap_to_car_behind_s": (
                    lap.gap_to_car_behind_s
                    if lap.gap_to_car_behind_s is not None
                    else LEADER_GAP_SENTINEL_S
                ),
                "sc_active": int(lap.sc_active),
                "vsc_active": int(lap.vsc_active),
                "yellow_active": int(lap.yellow_active),
                "air_temp_c": lap.air_temp_c if lap.air_temp_c is not None else 25.0,
                "track_temp_c": (
                    lap.track_temp_c if lap.track_temp_c is not None else 35.0
                ),
                "rain_intensity": (
                    lap.rain_intensity if lap.rain_intensity is not None else 0.0
                ),
            }
        )
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)


# --------------------------------------------------------------------------- #
# Training / inference
# --------------------------------------------------------------------------- #


def train_race_pace_model(
    feature_df: pd.DataFrame,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
    gbr_params: dict | None = None,
    xgb_params: dict | None = None,
) -> dict:
    """Fit GBR + XGB on ``lap_time_s``.  Returns an artifacts dict ready for
    persistence via ``models/registry.py``.

    The dict layout is intentionally flat and registry-compatible::

        {
            "gbr": fitted GradientBoostingRegressor,
            "xgb": fitted XGBRegressor,
            "feature_columns": list[str],
            "ensemble_weights": {"gbr": 0.5, "xgb": 0.5},  (inverse-MAE blend)
            "metrics": {"gbr_mae": float, "xgb_mae": float, "ensemble_mae": float,
                        "n_train": int, "n_test": int},
        }
    """
    if TARGET_COLUMN not in feature_df.columns:
        raise ValueError(f"feature_df missing target column {TARGET_COLUMN!r}")
    missing = [c for c in FEATURE_COLUMNS if c not in feature_df.columns]
    if missing:
        raise ValueError(f"feature_df missing required columns: {missing}")
    if len(feature_df) < 4:
        raise ValueError(
            f"need at least 4 rows to train race-pace model, got {len(feature_df)}"
        )
    if not _XGB_AVAILABLE:
        raise RuntimeError("xgboost is required for race-pace training but is not installed")

    X = feature_df[list(FEATURE_COLUMNS)].astype(float)
    y = feature_df[TARGET_COLUMN].astype(float).to_numpy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    gbr = GradientBoostingRegressor(
        **(gbr_params or dict(n_estimators=300, learning_rate=0.05, max_depth=4, random_state=random_state))
    )
    gbr.fit(X_train, y_train)
    gbr_pred = gbr.predict(X_test)
    gbr_mae = float(mean_absolute_error(y_test, gbr_pred))

    xgb = XGBRegressor(
        **(xgb_params or dict(
            n_estimators=400,
            learning_rate=0.05,
            max_depth=5,
            random_state=random_state,
            verbosity=0,
            tree_method="hist",
        ))
    )
    xgb.fit(X_train, y_train)
    xgb_pred = xgb.predict(X_test)
    xgb_mae = float(mean_absolute_error(y_test, xgb_pred))

    # Inverse-MAE blend: better model gets higher weight; matches the
    # ensemble strategy in [f1_prediction_utils.py::train_ensemble].
    inv_gbr = 1.0 / max(gbr_mae, 1e-6)
    inv_xgb = 1.0 / max(xgb_mae, 1e-6)
    total = inv_gbr + inv_xgb
    w_gbr = inv_gbr / total
    w_xgb = inv_xgb / total
    ensemble_pred = w_gbr * gbr_pred + w_xgb * xgb_pred
    ensemble_mae = float(mean_absolute_error(y_test, ensemble_pred))

    return {
        "gbr": gbr,
        "xgb": xgb,
        "feature_columns": list(FEATURE_COLUMNS),
        "ensemble_weights": {"gbr": w_gbr, "xgb": w_xgb},
        "metrics": {
            "gbr_mae_s": gbr_mae,
            "xgb_mae_s": xgb_mae,
            "ensemble_mae_s": ensemble_mae,
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
        },
    }


def predict_lap_times(
    artifacts: dict,
    feature_df: pd.DataFrame,
) -> np.ndarray:
    """Run the trained ensemble on a feature DataFrame.

    Expects ``feature_df`` to contain at least the columns in
    ``artifacts['feature_columns']``; extra columns are ignored.  Returns
    one predicted lap time (in seconds) per row.
    """
    feature_cols = artifacts.get("feature_columns") or list(FEATURE_COLUMNS)
    missing = [c for c in feature_cols if c not in feature_df.columns]
    if missing:
        raise ValueError(f"feature_df missing required columns: {missing}")
    X = feature_df[feature_cols].astype(float)
    gbr_pred = artifacts["gbr"].predict(X)
    xgb_pred = artifacts["xgb"].predict(X)
    weights = artifacts.get("ensemble_weights") or {"gbr": 0.5, "xgb": 0.5}
    return weights["gbr"] * gbr_pred + weights["xgb"] * xgb_pred


# --------------------------------------------------------------------------- #
# Bulk loader — combines multiple race sessions into one training DataFrame
# --------------------------------------------------------------------------- #


def build_training_dataset(
    season_round_pairs: Iterable[tuple[int, int]],
    circuit_key_for: dict[tuple[int, int], str] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    """Load + feature-engineer many races at once.

    Used by the offline training script (and by the eventual
    ``backfill_history.yml`` extension that will land in Step 2's CI work).
    Returns the concatenated feature DataFrame and the label-encoder dict
    so callers can persist both via the registry.
    """
    all_laps: list[LapRecord] = []
    for season, rnd in season_round_pairs:
        circuit_key = (circuit_key_for or {}).get((season, rnd))
        laps = load_race_laps(season, rnd, circuit_key=circuit_key)
        if not laps:
            warnings.warn(f"[race_pace] {season} R{rnd}: no laps loaded")
            continue
        all_laps.extend(laps)
    return laps_to_features(all_laps)
