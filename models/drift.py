"""Drift detection — feature-distribution PSI + output-side rolling Brier.

Why this exists
---------------
The user explicitly asked for heavy MLOps: model registry (A-P0.3),
forward-eval feedback loop (A-P0.2), and **drift detection** that flags
when the model's environment is changing in ways that hurt accuracy.

Two complementary signals:
  1. **Feature drift** (input-side) — has the *distribution* of predicted
     lap times / confidence / finish-range widened or shifted vs the
     trailing baseline?  Detected via the Population Stability Index
     (PSI), the industry-standard summary for that question.
  2. **Output drift** (target-side) — is the rolling Brier (lower is
     better) trending up?  That's the direct accuracy signal —
     deteriorating regardless of whether features changed.

Output
------
``website/public/data/model_health.json`` with the structure documented
in ``ModelHealthReport`` below.  The website's /accuracy page can render
this without any other infrastructure; CI commits it alongside the rest
of the website data.

Severity thresholds
-------------------
PSI bands match the standard convention used in credit-risk / fraud
modelling:
  * **< 0.10** — no meaningful change (no warning)
  * **0.10 ≤ x < 0.25** — moderate change (warn)
  * **≥ 0.25** — significant change (alarm)

For Brier degradation, we compute the rolling-5 average vs the prior
rolling-5 average:
  * **< 5% regression** — stable
  * **5%–15%** — moderate (warn)
  * **≥ 15%** — significant (alarm)

CI integration is in ``drift_report.py`` (CLI) — this module is the
pure computational core, network-free and FastF1-free.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

PSI_MODERATE_THRESHOLD: float = 0.10
PSI_SIGNIFICANT_THRESHOLD: float = 0.25

# Sentinel additive constant used when a bin has zero observations on either
# side, so the log doesn't blow up.  Same convention as the Khandani &
# Lo PSI formulation.
PSI_EPSILON: float = 1e-4

# Output-drift bands on the *relative* Brier change (newer / older - 1):
BRIER_MODERATE_REGRESSION: float = 0.05
BRIER_SIGNIFICANT_REGRESSION: float = 0.15


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #


@dataclass
class FeatureDriftSummary:
    feature: str
    psi: float
    severity: str  # "ok" | "warn" | "alarm"
    baseline_n: int
    current_n: int


@dataclass
class OutputDriftSummary:
    rolling_brier_recent: float | None
    rolling_brier_baseline: float | None
    relative_change: float | None    # (recent - baseline) / baseline
    severity: str                    # "ok" | "warn" | "alarm"
    rounds_compared: int


@dataclass
class ModelHealthReport:
    season: int
    last_evaluated_round: int | None
    feature_drift: list[FeatureDriftSummary] = field(default_factory=list)
    output_drift: OutputDriftSummary | None = None
    warnings: list[str] = field(default_factory=list)
    alarms: list[str] = field(default_factory=list)
    # Per-round Brier sequence for the website to chart over time.
    brier_by_round: list[dict] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# PSI — feature drift core
# --------------------------------------------------------------------------- #


def population_stability_index(
    baseline: Sequence[float],
    current: Sequence[float],
    n_bins: int = 10,
) -> float:
    """Compute the Population Stability Index between two numeric samples.

    PSI = Σ (current_pct - baseline_pct) × ln(current_pct / baseline_pct),
    summed over equal-width quantile bins of the baseline.  Empty bins are
    smoothed by ``PSI_EPSILON`` so the log is well-defined.

    Returns 0.0 when either sample is empty (no drift signal available).
    """
    baseline_arr = np.asarray([x for x in baseline if x is not None and not _isnan(x)], dtype=float)
    current_arr = np.asarray([x for x in current if x is not None and not _isnan(x)], dtype=float)
    if baseline_arr.size == 0 or current_arr.size == 0:
        return 0.0
    if n_bins < 2:
        raise ValueError(f"n_bins must be >= 2, got {n_bins}")

    # Equal-width bins on the *combined* min/max so we don't over-bin the
    # baseline.  This is more robust than quantile bins on a tiny sample
    # (e.g. 22 drivers per round).
    edges = np.linspace(
        min(baseline_arr.min(), current_arr.min()),
        max(baseline_arr.max(), current_arr.max()),
        n_bins + 1,
    )
    if not np.all(np.diff(edges) > 0):
        # All values identical → no spread → zero drift.
        return 0.0
    baseline_hist, _ = np.histogram(baseline_arr, bins=edges)
    current_hist, _ = np.histogram(current_arr, bins=edges)
    baseline_pct = baseline_hist / max(baseline_hist.sum(), 1)
    current_pct = current_hist / max(current_hist.sum(), 1)
    # Smooth zero bins so log is finite.
    baseline_pct = np.where(baseline_pct == 0, PSI_EPSILON, baseline_pct)
    current_pct = np.where(current_pct == 0, PSI_EPSILON, current_pct)
    return float(np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct)))


def _isnan(value: object) -> bool:
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def classify_psi(psi: float) -> str:
    """Map PSI to the ``ok`` / ``warn`` / ``alarm`` band."""
    if psi >= PSI_SIGNIFICANT_THRESHOLD:
        return "alarm"
    if psi >= PSI_MODERATE_THRESHOLD:
        return "warn"
    return "ok"


def feature_drift_report(
    baseline_records: Sequence[dict],
    current_records: Sequence[dict],
    feature_columns: Iterable[str],
) -> list[FeatureDriftSummary]:
    """Compute PSI per feature.

    Inputs are lists of dicts (e.g. classification entries from round
    JSONs).  Each feature column is pulled from both lists and run through
    ``population_stability_index``.  Missing columns / non-numeric values
    are silently skipped per feature (we never crash on a malformed entry).
    """
    summaries: list[FeatureDriftSummary] = []
    for feat in feature_columns:
        baseline_values = _extract_numeric(baseline_records, feat)
        current_values = _extract_numeric(current_records, feat)
        if not baseline_values or not current_values:
            continue
        psi = population_stability_index(baseline_values, current_values)
        summaries.append(
            FeatureDriftSummary(
                feature=feat,
                psi=round(psi, 4),
                severity=classify_psi(psi),
                baseline_n=len(baseline_values),
                current_n=len(current_values),
            )
        )
    return summaries


def _extract_numeric(records: Sequence[dict], key: str) -> list[float]:
    out: list[float] = []
    for r in records:
        value = r.get(key)
        if value is None:
            continue
        try:
            f = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(f) or math.isinf(f):
            continue
        out.append(f)
    return out


# --------------------------------------------------------------------------- #
# Output drift — rolling-Brier trend
# --------------------------------------------------------------------------- #


def rolling_brier_trend(
    brier_by_round: Sequence[tuple[int, float]],
    window: int = 5,
) -> OutputDriftSummary:
    """Compare the trailing ``window`` Brier scores against the previous
    ``window`` scores.  Brier is "lower is better", so a *positive*
    relative change is a regression.

    Returns severity ``ok`` when we lack enough rounds to make a comparison
    (need at least ``2 × window``).
    """
    valid = [
        (int(rnd), float(brier))
        for rnd, brier in brier_by_round
        if brier is not None and not _isnan(brier)
    ]
    valid.sort(key=lambda kv: kv[0])
    n = len(valid)
    if n < 2 * window:
        return OutputDriftSummary(
            rolling_brier_recent=valid[-1][1] if valid else None,
            rolling_brier_baseline=None,
            relative_change=None,
            severity="ok",
            rounds_compared=n,
        )
    recent = [b for _, b in valid[-window:]]
    baseline = [b for _, b in valid[-2 * window : -window]]
    mean_recent = sum(recent) / len(recent)
    mean_baseline = sum(baseline) / len(baseline)
    if mean_baseline <= 0:
        relative = 0.0
    else:
        relative = (mean_recent - mean_baseline) / mean_baseline
    if relative >= BRIER_SIGNIFICANT_REGRESSION:
        severity = "alarm"
    elif relative >= BRIER_MODERATE_REGRESSION:
        severity = "warn"
    else:
        severity = "ok"
    return OutputDriftSummary(
        rolling_brier_recent=round(mean_recent, 4),
        rolling_brier_baseline=round(mean_baseline, 4),
        relative_change=round(relative, 4),
        severity=severity,
        rounds_compared=n,
    )


# --------------------------------------------------------------------------- #
# Top-level report builder
# --------------------------------------------------------------------------- #


def build_health_report(
    *,
    season: int,
    last_evaluated_round: int | None,
    baseline_records: Sequence[dict],
    current_records: Sequence[dict],
    feature_columns: Iterable[str],
    brier_by_round: Sequence[tuple[int, float]] = (),
    rolling_window: int = 5,
) -> ModelHealthReport:
    """One-shot: feature drift + output drift + warnings/alarms aggregator."""
    feature_summaries = feature_drift_report(
        baseline_records, current_records, feature_columns
    )
    output_summary = rolling_brier_trend(brier_by_round, window=rolling_window)

    warnings: list[str] = []
    alarms: list[str] = []
    for fs in feature_summaries:
        if fs.severity == "warn":
            warnings.append(
                f"{fs.feature}: PSI {fs.psi:.3f} (moderate drift vs baseline)"
            )
        elif fs.severity == "alarm":
            alarms.append(
                f"{fs.feature}: PSI {fs.psi:.3f} (significant drift vs baseline)"
            )
    if output_summary.severity == "warn":
        warnings.append(
            f"rolling Brier regression {output_summary.relative_change:+.1%}"
        )
    elif output_summary.severity == "alarm":
        alarms.append(
            f"rolling Brier regression {output_summary.relative_change:+.1%} "
            f"(significant)"
        )

    return ModelHealthReport(
        season=season,
        last_evaluated_round=last_evaluated_round,
        feature_drift=feature_summaries,
        output_drift=output_summary,
        warnings=warnings,
        alarms=alarms,
        brier_by_round=[{"round": int(r), "brier": float(b)} for r, b in brier_by_round],
    )
