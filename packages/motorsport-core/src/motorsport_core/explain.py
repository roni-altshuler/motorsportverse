"""Generic, sklearn-optional key-factor generator for tree/ensemble models.

This module turns a trained model's feature importances plus the raw
per-competitor feature values into a short, ranked list of *plain-language*
"why" factors for each competitor — the kind of thing a fan-facing site can
render as "Qualifying pace: advantage / Reliability risk: risk".

It is deliberately dependency-light (numpy only) and deterministic: the same
inputs always produce the same output. It knows nothing about any particular
sport; the caller supplies the feature→group mapping.

Tech-scrub rule
---------------
The ``groups`` values (the *group labels*) are **user-facing** plain-language
strings — e.g. "Qualifying pace", "Recent form", "Circuit history", "Team
performance", "Reliability risk", "Weather", "Race strategy", "Experience".
They must never leak algorithm or implementation names (no "XGBoost feature
importance", "z-score", "gradient boosting", etc.). Only the group labels are
returned in the public output, so keeping them clean keeps the surface clean.

Method
------
For each competitor and each group *g*:

    contribution(g) = Σ_{feature f in g}  importance(f) × |z(f, competitor)|

where ``z(f, competitor)`` is the z-score of that competitor's value for
feature ``f`` across the whole field (all competitors). The magnitude measures
"how far from the pack" the competitor is on that group of signals, weighted by
how much the model relies on those signals. The **sign** (advantage vs risk) is
decided by whether the competitor's aggregate value on the group helps or hurts:
for a normal feature a high value helps (advantage); for a feature in
``lower_is_better`` a low value helps (a fast lap-time is a small number). A
competitor near the field average on a group gets "neutral".

Weights are normalised to ``[0, 1]`` per competitor (divided by that
competitor's largest group contribution) so they read as relative emphasis.
"""
from __future__ import annotations

import math
from typing import Mapping

__all__ = ["explain_scores"]


def _zscores(values: Mapping[str, float]) -> dict[str, float]:
    """Population z-scores for a single feature across the field.

    Returns 0.0 for every competitor when the feature has no spread (all equal)
    or fewer than two finite values — a flat feature carries no information.
    """
    finite = {c: float(v) for c, v in values.items()
              if v is not None and math.isfinite(float(v))}
    if len(finite) < 2:
        return {c: 0.0 for c in values}
    mean = sum(finite.values()) / len(finite)
    var = sum((v - mean) ** 2 for v in finite.values()) / len(finite)
    std = math.sqrt(var)
    if std <= 0:
        return {c: 0.0 for c in values}
    return {c: ((float(values[c]) - mean) / std)
            if (values.get(c) is not None and math.isfinite(float(values[c])))
            else 0.0
            for c in values}


def explain_scores(
    model_importances: Mapping[str, float],
    feature_values: Mapping[str, Mapping[str, float]],
    groups: Mapping[str, str],
    *,
    lower_is_better: set[str] | None = None,
    top_k: int = 4,
    neutral_threshold: float = 0.25,
) -> dict[str, list[dict[str, object]]]:
    """Rank plain-language key factors per competitor.

    Parameters
    ----------
    model_importances:
        ``{feature_name: importance}``. Importances are used as non-negative
        weights; negative values are clamped to 0. Features absent from this map
        (or with 0 importance) contribute nothing.
    feature_values:
        ``{competitor: {feature_name: value}}``. Every competitor should expose
        the same feature keys; missing/NaN values are treated as field-average
        (z-score 0) for that feature.
    groups:
        ``{feature_name: group_label}`` where the label is a **user-facing**
        plain-language string (see the tech-scrub rule in the module docstring).
        Features not present in ``groups`` are ignored.
    lower_is_better:
        Set of feature names for which a *lower* value is good (e.g. lap-time,
        DNF risk). For these, a below-average value counts as an advantage.
    top_k:
        Maximum number of factors returned per competitor (default 4).
    neutral_threshold:
        Minimum aggregate |z| a group must reach for a competitor before it is
        labelled advantage/risk rather than "neutral" (default 0.25).

    Returns
    -------
    ``{competitor: [{"factor": label, "weight": float in [0, 1],
    "direction": "advantage" | "risk" | "neutral"}, ...]}`` sorted by
    descending weight, at most ``top_k`` entries. Deterministic: ties break by
    group label alphabetically.
    """
    lower_is_better = lower_is_better or set()
    competitors = list(feature_values.keys())
    if not competitors:
        return {}

    # Clamp importances to non-negative weights.
    importances = {f: max(0.0, float(w)) for f, w in model_importances.items()}

    # Only features that are grouped AND carry importance matter.
    active_features = [
        f for f in groups
        if importances.get(f, 0.0) > 0.0
    ]

    # Precompute z-scores per active feature across the field.
    zmap: dict[str, dict[str, float]] = {}
    for f in active_features:
        col = {c: feature_values.get(c, {}).get(f) for c in competitors}
        zmap[f] = _zscores(col)

    # Group → member features.
    group_features: dict[str, list[str]] = {}
    for f in active_features:
        group_features.setdefault(groups[f], []).append(f)

    result: dict[str, list[dict[str, object]]] = {}
    for c in competitors:
        rows: list[tuple[float, float, str]] = []  # (weight_raw, signed_dir, label)
        for label, feats in group_features.items():
            magnitude = 0.0
            signed = 0.0  # positive => helps (advantage), negative => hurts
            for f in feats:
                imp = importances[f]
                z = zmap[f].get(c, 0.0)
                magnitude += imp * abs(z)
                # Direction of help: high value helps unless lower_is_better.
                helps = -z if f in lower_is_better else z
                signed += imp * helps
            rows.append((magnitude, signed, label))

        if not rows:
            result[c] = []
            continue

        max_mag = max(r[0] for r in rows)
        factors: list[dict[str, object]] = []
        for magnitude, signed, label in rows:
            weight = (magnitude / max_mag) if max_mag > 0 else 0.0
            if magnitude < neutral_threshold or abs(signed) < 1e-12:
                direction = "neutral"
            else:
                direction = "advantage" if signed > 0 else "risk"
            factors.append({
                "factor": label,
                "weight": round(weight, 4),
                "direction": direction,
            })

        # Deterministic order: weight desc, then label asc.
        factors.sort(key=lambda d: (-float(d["weight"]), str(d["factor"])))
        result[c] = factors[:top_k]

    return result
