"""Split conformal prediction intervals for the Layer 1 lap-time output.

The existing percentile-clipped confidence buckets ("High", "Medium",
"Low") in :mod:`f1_prediction_utils.apply_race_postprocessing` are
hand-tuned heuristics — they have no coverage guarantee and can't be
audited against observed outcomes. Split conformal prediction replaces
that with a statistically valid interval that, under exchangeability,
covers the true value with probability at least 1 − α.

Algorithm (split / inductive conformal)
---------------------------------------

1. Pick a held-out *calibration* set disjoint from training.
2. For each calibration row, compute the residual ``|y - ŷ|`` from
   the trained model.
3. Set ``q_α`` to the ``(1 − α)(1 + 1/n)`` empirical quantile of
   those residuals (the small finite-sample correction is the
   "split conformal" step).
4. At inference, the interval is ``[ŷ − q_α, ŷ + q_α]``.

Coverage guarantee: ``P(y ∈ interval) ≥ 1 − α`` for any exchangeable
test row, with no distributional assumption on the model or the data.

Stratified variant
------------------

F1 has obvious exchangeability violations: wet vs dry races, rookie
vs settled driver, early-season vs settled. The :class:`StratifiedConformal`
wraps the base estimator and stores a residual quantile per stratum,
falling back to the global quantile when a stratum has too few rows.
That preserves coverage for the well-populated strata while remaining
conservative for the sparse ones.

Calibrated confidence label
---------------------------

For display, we also map the per-row interval *width* into a
three-band confidence label ("High" / "Medium" / "Low"). The bands
are quantile cuts of the width distribution itself — that's just an
ergonomic UI label, not a statistical claim. The interval endpoints
are the load-bearing output.

Limitations
-----------

* Exchangeability is approximate at best; the stratified variant
  improves this but no F1 model satisfies it exactly.
* Intervals are symmetric around ``ŷ``. For lap time this is fine
  (residuals are roughly Gaussian around the median); for finishing
  position it would be wrong (clipped at 1).
* The split reduces training data. Use 70/30 by default; with very
  small samples (n < 20) the variant degenerates and we fall back
  to the percentile-clipped heuristic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np


DEFAULT_ALPHA = 0.10  # 90% coverage target
DEFAULT_CALIBRATION_FRACTION = 0.30
MIN_CALIBRATION_SAMPLES = 8


def split_conformal_quantile(
    residuals: Sequence[float] | np.ndarray,
    *,
    alpha: float = DEFAULT_ALPHA,
) -> float:
    """Empirical ``(1 − α)(1 + 1/n)`` quantile of absolute residuals.

    This is the load-bearing conformal step: the small finite-sample
    correction guarantees marginal coverage at level ``1 − α`` for an
    exchangeable test point.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1); got {alpha}")
    res = np.abs(np.asarray(residuals, dtype=np.float64))
    n = len(res)
    if n == 0:
        raise ValueError("residuals array is empty")
    # Numpy quantile with the higher-side empirical convention.
    q_level = np.clip((1.0 - alpha) * (1.0 + 1.0 / n), 0.0, 1.0)
    return float(np.quantile(res, q_level, method="higher"))


@dataclass
class ConformalIntervals:
    """Split conformal calibrator for symmetric prediction intervals."""

    alpha: float = DEFAULT_ALPHA
    _quantile: float | None = None
    _calibration_n: int = 0

    @property
    def is_fitted(self) -> bool:
        return self._quantile is not None

    @property
    def quantile(self) -> float | None:
        return self._quantile

    @property
    def calibration_n(self) -> int:
        return self._calibration_n

    def fit(
        self,
        y_calibration: Sequence[float] | np.ndarray,
        y_pred_calibration: Sequence[float] | np.ndarray,
    ) -> "ConformalIntervals":
        """Estimate the conformal quantile from held-out residuals."""
        y = np.asarray(y_calibration, dtype=np.float64)
        yhat = np.asarray(y_pred_calibration, dtype=np.float64)
        if y.shape != yhat.shape:
            raise ValueError(
                f"y_calibration and y_pred_calibration must have the same shape; "
                f"got {y.shape} vs {yhat.shape}"
            )
        if len(y) < MIN_CALIBRATION_SAMPLES:
            raise ValueError(
                f"need >= {MIN_CALIBRATION_SAMPLES} calibration samples; "
                f"got {len(y)}"
            )
        residuals = np.abs(y - yhat)
        self._quantile = split_conformal_quantile(residuals, alpha=self.alpha)
        self._calibration_n = len(y)
        return self

    def predict_intervals(
        self,
        y_pred: Sequence[float] | np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(low, high)`` arrays for the test predictions."""
        if not self.is_fitted:
            raise RuntimeError(
                "ConformalIntervals.fit(...) must be called before predict_intervals"
            )
        yhat = np.asarray(y_pred, dtype=np.float64)
        q = self._quantile
        return yhat - q, yhat + q

    def width(self) -> float:
        """Full interval width ``2 * q``."""
        if not self.is_fitted:
            raise RuntimeError("not fitted")
        return 2.0 * float(self._quantile)


@dataclass
class StratifiedConformal:
    """Per-stratum split conformal with a global fallback.

    Strata are identified by string keys (e.g. ``"wet"``, ``"dry"``,
    ``"rookie"``, ``"settled"``). At ``transform`` time, the per-row
    stratum key picks the relevant calibrator; rows whose stratum
    has insufficient calibration data fall back to the global one.
    """

    alpha: float = DEFAULT_ALPHA
    min_samples_per_stratum: int = MIN_CALIBRATION_SAMPLES
    _global: ConformalIntervals = field(default_factory=lambda: ConformalIntervals())
    _per_stratum: dict[str, ConformalIntervals] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._global.alpha = self.alpha

    def fit(
        self,
        y_calibration: Sequence[float] | np.ndarray,
        y_pred_calibration: Sequence[float] | np.ndarray,
        strata: Sequence[str],
    ) -> "StratifiedConformal":
        """Fit one calibrator per stratum plus the global fallback."""
        y = np.asarray(y_calibration, dtype=np.float64)
        yhat = np.asarray(y_pred_calibration, dtype=np.float64)
        s = list(strata)
        if not (len(y) == len(yhat) == len(s)):
            raise ValueError(
                f"arrays must agree; got y={len(y)} yhat={len(yhat)} strata={len(s)}"
            )

        self._global = ConformalIntervals(alpha=self.alpha).fit(y, yhat)

        grouped: dict[str, list[int]] = {}
        for i, key in enumerate(s):
            grouped.setdefault(str(key), []).append(i)

        for key, idx in grouped.items():
            if len(idx) < self.min_samples_per_stratum:
                continue
            sub_y = y[idx]
            sub_yhat = yhat[idx]
            self._per_stratum[key] = ConformalIntervals(alpha=self.alpha).fit(
                sub_y, sub_yhat
            )
        return self

    @property
    def is_fitted(self) -> bool:
        return self._global.is_fitted

    def predict_intervals(
        self,
        y_pred: Sequence[float] | np.ndarray,
        strata: Sequence[str],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Per-row interval, falling back to global where stratum is sparse."""
        if not self.is_fitted:
            raise RuntimeError(
                "StratifiedConformal.fit(...) must be called before predict_intervals"
            )
        yhat = np.asarray(y_pred, dtype=np.float64)
        if len(yhat) != len(strata):
            raise ValueError(
                f"y_pred and strata must agree; got {len(yhat)} vs {len(strata)}"
            )
        lows = np.empty_like(yhat)
        highs = np.empty_like(yhat)
        for i, key in enumerate(strata):
            cal = self._per_stratum.get(str(key)) or self._global
            q = cal.quantile
            lows[i] = yhat[i] - q
            highs[i] = yhat[i] + q
        return lows, highs

    def stratum_coverage(self) -> dict[str, int]:
        """Calibration sample counts per stratum (for diagnostics)."""
        return {k: v.calibration_n for k, v in self._per_stratum.items()}


def width_to_confidence_label(
    widths: Sequence[float] | np.ndarray,
    *,
    bins: tuple[float, float] = (0.34, 0.68),
) -> list[str]:
    """Map per-row interval widths to High/Medium/Low UI labels.

    The bins are quantile cuts of the input distribution. This is a
    *display* convenience — the load-bearing output is the interval
    endpoints, not the label.
    """
    w = np.asarray(widths, dtype=np.float64)
    if len(w) == 0:
        return []
    lo_cut = float(np.quantile(w, bins[0]))
    hi_cut = float(np.quantile(w, bins[1]))
    labels: list[str] = []
    for v in w:
        if v <= lo_cut:
            labels.append("High")
        elif v <= hi_cut:
            labels.append("Medium")
        else:
            labels.append("Low")
    return labels


DEFAULT_RESIDUAL_CACHE_DIR = "data/conformal_residuals"


def save_round_residuals(
    season: int,
    round_num: int,
    residuals: Sequence[float] | np.ndarray,
    *,
    cache_dir: str | Path = DEFAULT_RESIDUAL_CACHE_DIR,
) -> Path:
    """Persist held-out residuals for one round to the residual cache.

    Each call writes ``<cache_dir>/<season>_round_<NN>.json``. The
    file is small (~hundreds of bytes) and intended to be gitignored.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(residuals, dtype=np.float64)
    path = cache_dir / f"{int(season)}_round_{int(round_num):02d}.json"
    payload = {
        "season": int(season),
        "round": int(round_num),
        "n_residuals": int(arr.size),
        "abs_residuals": [float(v) for v in np.abs(arr)],
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def load_residual_history(
    *,
    current_season: int,
    current_round: int,
    max_seasons_back: int = 1,
    cache_dir: str | Path = DEFAULT_RESIDUAL_CACHE_DIR,
) -> np.ndarray:
    """Aggregate prior-only residuals from the cache.

    Returns a 1-D float array of absolute residuals. Only rows with
    ``(season, round) < (current_season, current_round)`` are
    admitted (leakage-safe). Files older than ``max_seasons_back``
    seasons are skipped — a regulation-era hint.

    Empty array when no usable cache file exists yet.
    """
    cache_dir = Path(cache_dir)
    if not cache_dir.exists():
        return np.array([], dtype=np.float64)

    cutoff_season = current_season - max_seasons_back
    out: list[float] = []
    for file in sorted(cache_dir.glob("*.json")):
        try:
            payload = json.loads(file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        season = int(payload.get("season", -1))
        rnd = int(payload.get("round", -1))
        if season < cutoff_season:
            continue
        if (season, rnd) >= (current_season, current_round):
            continue
        residuals = payload.get("abs_residuals") or []
        out.extend(float(v) for v in residuals)
    return np.asarray(out, dtype=np.float64)


__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_CALIBRATION_FRACTION",
    "MIN_CALIBRATION_SAMPLES",
    "DEFAULT_RESIDUAL_CACHE_DIR",
    "split_conformal_quantile",
    "ConformalIntervals",
    "StratifiedConformal",
    "width_to_confidence_label",
    "save_round_residuals",
    "load_residual_history",
]
