"""Calibration diagnostics: reliability diagrams, ECE, MCE, Brier.

`forward_eval.py` already reports point-prediction metrics (MAE,
RMSE, NDCG@5, Spearman, last-race-winner baseline). What it doesn't
do is measure whether the *probabilities* the system publishes are
calibrated — that's what this module adds.

Definitions
-----------

For a binary outcome (e.g. "this driver won"), with predicted
probability ``p̂_i`` and observed indicator ``y_i ∈ {0, 1}``:

* **Reliability bin:** group rows by predicted-probability bucket
  (default 10 equal-width bins). Within each bucket, compute the
  mean predicted probability and the mean observed outcome rate.
  A perfectly calibrated model has bin-mean predicted ==
  bin-mean observed for every bucket.

* **ECE (Expected Calibration Error):** mean over bins of the
  absolute gap between mean predicted and mean observed,
  weighted by bin size:

      ECE = Σᵢ (nᵢ/N) · |mean_pred_i − mean_obs_i|

* **MCE (Maximum Calibration Error):** max over bins of the same
  per-bin gap (unweighted). Catches the *worst* bucket.

* **Brier score:** mean squared error between predicted probability
  and observed indicator. Lower = better. Useful as a single
  scalar summary of probabilistic forecast quality.

Reliability plots
-----------------

:func:`save_reliability_diagram` writes a matplotlib PNG that shows
the bin-wise calibration curve plus the diagonal, with bar shading
proportional to bin sample count. Plot styling follows
:mod:`viz_style` so the file fits the rest of the chart catalogue.

Multi-market support
--------------------

F1 publishes several probability markets (win, podium, top6,
top10). All four are binary outcomes with different base rates, so
calibration should be measured per market.
:class:`MarketReliabilityReport` is the aggregating dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np


DEFAULT_N_BINS = 10
DEFAULT_MIN_BIN_COUNT = 1


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_predicted: float
    mean_observed: float

    @property
    def gap(self) -> float:
        return abs(self.mean_predicted - self.mean_observed)


@dataclass(frozen=True)
class CalibrationMetrics:
    n_samples: int
    n_bins: int
    ece: float
    mce: float
    brier: float
    bins: tuple[ReliabilityBin, ...]


def brier_score(
    predicted: Sequence[float] | np.ndarray,
    observed: Sequence[int] | np.ndarray,
) -> float:
    p = np.asarray(predicted, dtype=np.float64)
    y = np.asarray(observed, dtype=np.float64)
    if p.shape != y.shape:
        raise ValueError(f"shape mismatch: {p.shape} vs {y.shape}")
    if p.size == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def reliability_bins(
    predicted: Sequence[float] | np.ndarray,
    observed: Sequence[int] | np.ndarray,
    *,
    n_bins: int = DEFAULT_N_BINS,
) -> tuple[ReliabilityBin, ...]:
    """Group predictions into equal-width bins and report per-bin stats."""
    p = np.asarray(predicted, dtype=np.float64)
    y = np.asarray(observed, dtype=np.float64)
    if p.shape != y.shape:
        raise ValueError(f"shape mismatch: {p.shape} vs {y.shape}")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out: list[ReliabilityBin] = []
    for i in range(n_bins):
        lo = edges[i]
        hi = edges[i + 1]
        if i == n_bins - 1:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        count = int(mask.sum())
        if count == 0:
            mean_p = (lo + hi) / 2.0
            mean_y = float("nan")
        else:
            mean_p = float(p[mask].mean())
            mean_y = float(y[mask].mean())
        out.append(
            ReliabilityBin(
                lower=float(lo),
                upper=float(hi),
                count=count,
                mean_predicted=mean_p,
                mean_observed=mean_y,
            )
        )
    return tuple(out)


def expected_calibration_error(
    bins: Sequence[ReliabilityBin],
    *,
    min_count: int = DEFAULT_MIN_BIN_COUNT,
) -> float:
    """Sample-weighted mean of per-bin |mean_pred − mean_obs|."""
    total = sum(b.count for b in bins if b.count >= min_count)
    if total == 0:
        return float("nan")
    return float(
        sum(
            (b.count / total) * b.gap
            for b in bins
            if b.count >= min_count and not np.isnan(b.mean_observed)
        )
    )


def maximum_calibration_error(
    bins: Sequence[ReliabilityBin],
    *,
    min_count: int = DEFAULT_MIN_BIN_COUNT,
) -> float:
    """Max over bins of |mean_pred − mean_obs|."""
    gaps = [
        b.gap
        for b in bins
        if b.count >= min_count and not np.isnan(b.mean_observed)
    ]
    if not gaps:
        return float("nan")
    return float(max(gaps))


def compute_calibration_metrics(
    predicted: Sequence[float] | np.ndarray,
    observed: Sequence[int] | np.ndarray,
    *,
    n_bins: int = DEFAULT_N_BINS,
    min_bin_count: int = DEFAULT_MIN_BIN_COUNT,
) -> CalibrationMetrics:
    """End-to-end ECE + MCE + Brier + per-bin breakdown."""
    p = np.asarray(predicted, dtype=np.float64)
    y = np.asarray(observed, dtype=np.float64)
    bins = reliability_bins(p, y, n_bins=n_bins)
    return CalibrationMetrics(
        n_samples=int(p.size),
        n_bins=n_bins,
        ece=expected_calibration_error(bins, min_count=min_bin_count),
        mce=maximum_calibration_error(bins, min_count=min_bin_count),
        brier=brier_score(p, y),
        bins=bins,
    )


def metrics_to_dict(m: CalibrationMetrics) -> dict[str, object]:
    """JSON-serialisable view, suitable for forward_eval per-round files."""
    return {
        "n_samples": m.n_samples,
        "n_bins": m.n_bins,
        "ece": None if np.isnan(m.ece) else m.ece,
        "mce": None if np.isnan(m.mce) else m.mce,
        "brier": None if np.isnan(m.brier) else m.brier,
        "bins": [
            {
                "lower": b.lower,
                "upper": b.upper,
                "count": b.count,
                "mean_predicted": b.mean_predicted,
                "mean_observed": (
                    None if np.isnan(b.mean_observed) else b.mean_observed
                ),
            }
            for b in m.bins
        ],
    }


@dataclass(frozen=True)
class MarketReliabilityReport:
    """Per-market calibration metrics for a single round (or season)."""

    by_market: dict[str, CalibrationMetrics] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {market: metrics_to_dict(m) for market, m in self.by_market.items()}


def save_reliability_diagram(
    metrics: CalibrationMetrics,
    output_path: str | Path,
    *,
    title: str = "Reliability diagram",
) -> Path:
    """Render a per-market reliability diagram as a PNG."""
    # Local imports so the module loads when matplotlib isn't installed
    # (e.g. lightweight test environments).
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    try:
        from viz_style import apply_viz_style, VIZ_COLORS, style_axis  # type: ignore

        apply_viz_style()
        text_color = VIZ_COLORS.get("text", "#FFFFFF")
        bar_color = VIZ_COLORS.get("accent", "#F76B15")
    except Exception:  # pragma: no cover - viz_style is optional at unit-test time
        text_color = "#FFFFFF"
        bar_color = "#F76B15"
        style_axis = None  # type: ignore

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 6))
    centres = np.array(
        [(b.lower + b.upper) / 2.0 for b in metrics.bins], dtype=np.float64
    )
    observed = np.array(
        [b.mean_observed if not np.isnan(b.mean_observed) else 0.0 for b in metrics.bins]
    )
    counts = np.array([b.count for b in metrics.bins], dtype=np.float64)
    if counts.max() > 0:
        widths = (1.0 / metrics.n_bins) * (0.4 + 0.55 * (counts / counts.max()))
    else:
        widths = np.full_like(counts, 1.0 / metrics.n_bins, dtype=np.float64)

    ax.bar(
        centres,
        observed,
        width=widths,
        align="center",
        alpha=0.75,
        color=bar_color,
        label="Observed",
    )
    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1.0, color=text_color, alpha=0.6, label="Ideal")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed frequency")
    ax.set_title(
        f"{title}\nECE={metrics.ece:.3f}  MCE={metrics.mce:.3f}  Brier={metrics.brier:.3f}",
        color=text_color,
    )
    if style_axis is not None:
        style_axis(ax)
    ax.legend(loc="upper left", framealpha=0.0)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def compute_market_report_from_probabilities(
    market_probabilities: Mapping[str, Sequence[float]],
    market_outcomes: Mapping[str, Sequence[int]],
    *,
    n_bins: int = DEFAULT_N_BINS,
) -> MarketReliabilityReport:
    """Build a :class:`MarketReliabilityReport` from market dicts.

    Both arguments share the same keys (one per market: 'win',
    'podium', 'top6', 'top10'). Values are equal-length sequences
    of per-row predicted probabilities and observed 0/1 outcomes.
    """
    by_market: dict[str, CalibrationMetrics] = {}
    for market, preds in market_probabilities.items():
        outs = market_outcomes.get(market)
        if outs is None or len(preds) != len(outs):
            continue
        by_market[market] = compute_calibration_metrics(
            preds, outs, n_bins=n_bins
        )
    return MarketReliabilityReport(by_market=by_market)


__all__ = [
    "DEFAULT_N_BINS",
    "DEFAULT_MIN_BIN_COUNT",
    "ReliabilityBin",
    "CalibrationMetrics",
    "MarketReliabilityReport",
    "brier_score",
    "reliability_bins",
    "expected_calibration_error",
    "maximum_calibration_error",
    "compute_calibration_metrics",
    "metrics_to_dict",
    "save_reliability_diagram",
    "compute_market_report_from_probabilities",
]
