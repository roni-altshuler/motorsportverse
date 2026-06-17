"""Per-lap race-pace ensemble for F2 — a ready seam, NOT active today.

Status: DORMANT / DATA-GATED. F2 lap-by-lap telemetry is not available from any
source this project wires up (the FIA F2 site publishes classifications, not
per-lap timing, and FastF1's F2 lap coverage is partial-to-absent). So this
module is a *seam*, mirroring the F1 flagship's ``models/race_pace.py`` +
``train_race_pace.py``, that activates automatically the day a lap feed lands —
and until then no-ops cleanly so the live pipeline keeps running the existing
Plackett-Luce ordering in :func:`f2_predictions.model.forecast_round`.

What the F1 reference does (and what this would do once fed)
-----------------------------------------------------------
A per-lap GBR + XGB lap-time regressor trained on lap-by-lap race telemetry,
with a ~16-feature catalogue the Monte-Carlo race simulator reproduces one lap
at a time: driver/team ids, lap_number, lap_progress, track_position,
tyre_compound_code, tyre_age_laps, gap_to_car_ahead/behind, sc/vsc/yellow flags,
air/track temp, rain_intensity. The simulator then iterates ``predict_lap_times``
per driver per lap, maintaining running gaps + positions, sampling pit laps and
SC events — replacing the position-only PL sampler with a physically-grounded
race model. F2's reverse-grid sprint would be a first-class win for that model:
overtaking dynamics are exactly what PL sampling cannot express.

Why it's gated rather than stubbed with fake data
-------------------------------------------------
Synthesising lap telemetry would be inventing the very signal the model is
supposed to learn — it would look like capability without being it (the project's
honest-calibration discipline, applied to the simulator layer). So instead:

* :func:`lap_data_available` is the single gate. It returns ``False`` today.
* :func:`train_race_pace` returns ``None`` when the gate is closed — the caller
  treats that as "fall back to the PL ordering", exactly how the F1 exporter's
  ``--use-race-simulator`` silently no-ops when no race-pace ensemble is
  registered.

When a real lap feed arrives, implement :func:`load_lap_dataset` to return the
per-lap frame (one row per driver-lap with the feature columns + a ``lap_time``
target), flip :data:`f2_predictions.config.USE_RACE_SIMULATOR` on, and the rest
of the ensemble code below trains/persists without further plumbing.

Run:  python -m f2_predictions.train_race_pace --season 2026   # no-ops today
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import config

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .datasource import F2DataSource

# The 16-ish-feature catalogue the simulator would reproduce lap-by-lap. Kept here
# (not in core) until a second sport needs it — at which point it graduates to a
# sport-agnostic ``motorsport_core`` simulator core, the same way Elo did.
LAP_FEATURE_COLUMNS: list[str] = [
    "driver_id",
    "team_id",
    "lap_number",
    "lap_progress",
    "track_position",
    "tyre_compound_code",
    "tyre_age_laps",
    "gap_to_car_ahead",
    "gap_to_car_behind",
    "safety_car_flag",
    "vsc_flag",
    "yellow_flag",
    "air_temp",
    "track_temp",
    "rain_intensity",
    "is_sprint",  # F2-specific: sprint laps behave differently from feature laps
]


@dataclass
class RacePaceEnsemble:
    """Trained per-lap GBR + XGB ensemble (populated only once lap data exists)."""

    gb: Any
    xgb: Any
    scaler: Any
    w_gb: float
    w_xgb: float
    feature_columns: list[str]


def lap_data_available(source: "F2DataSource", year: int) -> bool:
    """Whether a per-lap F2 telemetry feed is wired up. ``False`` today.

    The gate the whole module hangs on. It probes the data source for an optional
    ``lap_data_for_round`` hook (a source that implements it has lap telemetry);
    no source does yet, so this returns ``False`` and the simulator stays dormant.
    """
    return config.USE_RACE_SIMULATOR and hasattr(source, "lap_data_for_round")


def load_lap_dataset(source: "F2DataSource", year: int, rounds: list[int]):
    """Per-lap training frame (one row per driver-lap). Raises until a feed lands.

    Intentionally unimplemented: there is no lap data to load. Kept as the single
    integration point so adding a feed is a one-function change, not a rewrite.
    """
    raise NotImplementedError(
        "F2 lap-by-lap telemetry is not available. Implement this to return a "
        "per-lap frame with LAP_FEATURE_COLUMNS + a 'lap_time' target once a feed "
        "is wired into datasource.py, then set config.USE_RACE_SIMULATOR=1."
    )


def train_race_pace(source: "F2DataSource", year: int, rounds: list[int]) -> RacePaceEnsemble | None:
    """Train the per-lap ensemble, or ``None`` when no lap data is available.

    Returns ``None`` today (the gate is closed), which the pipeline reads as
    "fall back to the existing Plackett-Luce ordering". The training body mirrors
    :func:`f2_predictions.ml_skill.predict_ml_skill` / the F1 race-pace trainer:
    standardise, fit GBR + XGB, weight by inverse held-out MAE. It only runs once
    :func:`lap_data_available` flips to ``True``.
    """
    if not lap_data_available(source, year):
        return None
    try:  # pragma: no cover - dormant until a lap feed exists
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from xgboost import XGBRegressor

        frame = load_lap_dataset(source, year, rounds)
        X = np.asarray([[row[f] for f in LAP_FEATURE_COLUMNS] for row in frame], dtype=float)
        y = np.asarray([row["lap_time"] for row in frame], dtype=float)
        scaler = StandardScaler().fit(X)
        Xs = scaler.transform(X)
        Xtr, Xte, ytr, yte = train_test_split(Xs, y, test_size=0.2, random_state=42)
        gb = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05, max_depth=3, random_state=42)
        xgb = XGBRegressor(n_estimators=350, learning_rate=0.05, max_depth=3, random_state=42, verbosity=0)
        gb.fit(Xtr, ytr)
        xgb.fit(Xtr, ytr)
        inv_gb = 1.0 / max(mean_absolute_error(yte, gb.predict(Xte)), 1e-6)
        inv_xgb = 1.0 / max(mean_absolute_error(yte, xgb.predict(Xte)), 1e-6)
        total = inv_gb + inv_xgb
        return RacePaceEnsemble(gb, xgb, scaler, inv_gb / total, inv_xgb / total, list(LAP_FEATURE_COLUMNS))
    except NotImplementedError:
        return None
    except Exception:  # pragma: no cover - never destabilise the pipeline
        return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--season", type=int, default=config.SEASON)
    args = p.parse_args()
    from .datasource import F2DataSource

    source = F2DataSource()
    rounds = list(range(1, config.COMPLETED_ROUNDS + 1))
    ensemble = train_race_pace(source, args.season, rounds)
    if ensemble is None:
        print(
            "train_race_pace: no F2 lap-by-lap data available — race simulator "
            "stays dormant; predictions use the Plackett-Luce ordering. "
            "(This is expected; see the module docstring.)"
        )
        return 0
    print(f"train_race_pace: trained ensemble (w_gb={ensemble.w_gb:.2f}, w_xgb={ensemble.w_xgb:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
