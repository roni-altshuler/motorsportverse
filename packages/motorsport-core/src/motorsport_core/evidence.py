"""One evidence block per project — the model against its baselines, paired.

Every MotorsportVerse site shows probabilities, and a probability is
unfalsifiable on its own. :func:`build_evidence` reads a project's published
``forward_eval/`` tree and produces the single artifact the shared
``EvidencePanel`` renders, so the model-vs-baseline comparison is computed
**once, in Python**, rather than re-derived in six independent TypeScript
codebases that would each drift their own way.

The rules it encodes are in ``docs/EVIDENCE.md``:

- A metric with no baseline is a number about the calendar, not the model. Every
  comparison here is *paired* — model and baseline scored on the same rounds,
  differenced per round, and summarised over the differences. Comparing two
  independently-averaged means across different round sets is the mistake this
  module exists to make impossible.
- **Not beating the baseline is a publishable result.** ``verdict`` says
  ``"worse"`` in as many words and the panel prints it. There is no code path
  that hides a losing comparison.
- **A small sample does not get a claim.** Below :data:`MIN_ROUNDS_FOR_CLAIM`
  paired rounds the verdict is ``"insufficient"`` regardless of how good the
  delta looks, and a confidence interval that straddles zero yields
  ``"inconclusive"`` rather than the sign of the point estimate.

Two published shapes exist in this repo and both are handled:

``feeder``
    F2/F3 — race types ``sprint`` / ``feature``; ``baselines`` is keyed by race
    type and carries the last-race baseline only.
``single``
    NASCAR / IndyCar / Formula E — race type ``race`` (plus an optional
    ``racePostQuali``); ``baselines`` is keyed by baseline *name*
    (``lastRace``, ``gridOrder``).

Public API
----------
- :func:`build_evidence` — the whole artifact, ready to ``json.dump``.
- :func:`compare_paired` — one metric, model vs one baseline, paired + bootstrapped.
- :func:`paired_bootstrap` — deterministic percentile CI on a difference.
- :data:`METRIC_DIRECTION` — which way is better, per metric.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

# Below this many paired rounds no comparison earns a verdict, whatever the
# delta looks like. Matches the overlap floor `promotion_decision` applies
# before it will recommend promoting a candidate — the two gates disagreeing
# would let a claim reach the site that could not reach production.
MIN_ROUNDS_FOR_CLAIM = 5

# Bootstrap resamples for the paired CI. 2000 is enough for a 95% percentile
# interval to be stable to the fourth decimal, which is finer than anything
# rendered.
BOOTSTRAP_RESAMPLES = 2000

# Seeded, because a published artifact that changes when nothing changed is a
# diff every morning and a git history nobody can read.
BOOTSTRAP_SEED = 20260716

#: ``True`` where a LOWER value is better. Anything not listed is treated as
#: higher-is-better, which is the safe default for the hit-rate family.
METRIC_DIRECTION: dict[str, bool] = {
    "mean_position_error": True,
    "brier": True,
    "logLoss": True,
    "winBrier": True,
    "winLogLoss": True,
    "podiumBrier": True,
    "podiumLogLoss": True,
    "ndcg_at_5": False,
    "spearman_correlation": False,
    "within_3": False,
    "within_5": False,
    "exact_matches": False,
    "podium_hits": False,
    "winner_hit": False,
}

#: The metric the headline comparison uses. Positional error is the one metric
#: every series in the repo publishes for every race type, so it is the only
#: honest choice for a cross-page headline.
HEADLINE_METRIC = "mean_position_error"

#: Human-readable names for the baseline keys the exports emit.
BASELINE_LABELS = {
    "lastRace": "Last race order",
    "gridOrder": "Grid order",
    "sprint": "Last race order",
    "feature": "Last race order",
}


def _lower_is_better(metric: str) -> bool:
    return METRIC_DIRECTION.get(metric, False)


@dataclass
class Comparison:
    """Model vs one baseline on one metric, over the rounds they share."""

    metric: str
    baseline: str
    baseline_label: str
    race_type: str
    lower_is_better: bool
    n_rounds: int
    rounds: list[int]
    model_mean: float | None
    baseline_mean: float | None
    #: ``model - baseline`` in the metric's own units, sign left raw so a reader
    #: can reconcile it against the two means above.
    delta: float | None
    #: Positive means the model is better, whichever direction the metric runs.
    #: This is the only field a UI should branch on.
    improvement: float | None
    ci_low: float | None
    ci_high: float | None
    p_model_better: float | None
    verdict: str
    note: str

    def to_json(self) -> dict:
        return {
            "metric": self.metric,
            "baseline": self.baseline,
            "baselineLabel": self.baseline_label,
            "raceType": self.race_type,
            "lowerIsBetter": self.lower_is_better,
            "nRounds": self.n_rounds,
            "rounds": self.rounds,
            "modelMean": self.model_mean,
            "baselineMean": self.baseline_mean,
            "delta": self.delta,
            "improvement": self.improvement,
            "ciLow": self.ci_low,
            "ciHigh": self.ci_high,
            "pModelBetter": self.p_model_better,
            "verdict": self.verdict,
            "note": self.note,
        }


@dataclass
class EvidenceBlock:
    """Everything a site needs to justify the numbers on the page."""

    available: bool
    reason: str | None = None
    season: int | None = None
    sport: str | None = None
    generated_at: str | None = None
    rounds_scored: int = 0
    basis: str = (
        "forward evaluation — each round was forecast before it ran and scored "
        "afterwards; not a backtest"
    )
    headline: dict | None = None
    comparisons: list[dict] = field(default_factory=list)
    calibration: dict | None = None
    promotion: dict | None = None
    caveats: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "available": self.available,
            "reason": self.reason,
            "season": self.season,
            "sport": self.sport,
            "generatedAt": self.generated_at,
            "roundsScored": self.rounds_scored,
            "basis": self.basis,
            "headline": self.headline,
            "comparisons": self.comparisons,
            "calibration": self.calibration,
            "promotion": self.promotion,
            "caveats": self.caveats,
        }


def paired_bootstrap(
    differences: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = 0.05,
) -> tuple[float | None, float | None, float | None]:
    """Percentile CI and P(mean difference < 0) over a paired difference series.

    Resampling is **paired** — one round contributes its model and baseline
    scores together or not at all. Bootstrapping the two series independently
    would discard the round-level correlation that is the entire point of a
    paired design, and would widen the interval enough to call a real
    difference inconclusive.

    Returns ``(ci_low, ci_high, p_negative)``. ``p_negative`` is the share of
    resample means below zero; callers orient it into "probability the model is
    better" using the metric's direction.
    """
    values = [float(d) for d in differences]
    n = len(values)
    if n < 2:
        return None, None, None

    rng = random.Random(seed)
    means: list[float] = []
    negatives = 0
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += values[rng.randrange(n)]
        mean = total / n
        means.append(mean)
        if mean < 0:
            negatives += 1

    means.sort()
    lo_idx = int((alpha / 2) * resamples)
    hi_idx = min(resamples - 1, int((1 - alpha / 2) * resamples))
    return means[lo_idx], means[hi_idx], negatives / resamples


def compare_paired(
    metric: str,
    paired: Sequence[tuple[int, float, float]],
    *,
    baseline: str,
    race_type: str,
    baseline_label: str | None = None,
) -> Comparison:
    """Summarise ``(round, model_value, baseline_value)`` triples for one metric.

    Rounds where either side is missing must be dropped by the caller *before*
    this is called — a round the baseline cannot score (round 1 has no previous
    race) is not a round the model won.
    """
    lower_better = _lower_is_better(metric)
    label = baseline_label or BASELINE_LABELS.get(baseline, baseline)
    rounds = [int(r) for r, _, _ in paired]
    n = len(paired)

    if n == 0:
        return Comparison(
            metric=metric,
            baseline=baseline,
            baseline_label=label,
            race_type=race_type,
            lower_is_better=lower_better,
            n_rounds=0,
            rounds=[],
            model_mean=None,
            baseline_mean=None,
            delta=None,
            improvement=None,
            ci_low=None,
            ci_high=None,
            p_model_better=None,
            verdict="insufficient",
            note="no round has both a model score and a baseline score yet",
        )

    model_mean = sum(m for _, m, _ in paired) / n
    baseline_mean = sum(b for _, _, b in paired) / n
    diffs = [m - b for _, m, b in paired]
    delta = sum(diffs) / n
    improvement = -delta if lower_better else delta

    ci_low, ci_high, p_negative = paired_bootstrap(diffs)
    if p_negative is None:
        p_model_better = None
    else:
        p_model_better = p_negative if lower_better else 1.0 - p_negative

    # Orient the interval so it reads in "improvement" units too: a CI on the
    # raw difference is easy to misread when lower is better.
    if lower_better and ci_low is not None and ci_high is not None:
        imp_low, imp_high = -ci_high, -ci_low
    else:
        imp_low, imp_high = ci_low, ci_high

    if n < MIN_ROUNDS_FOR_CLAIM:
        verdict = "insufficient"
        note = (
            f"{n} paired round(s); {MIN_ROUNDS_FOR_CLAIM} are needed before this "
            f"comparison earns a claim either way"
        )
    elif imp_low is None or imp_high is None:
        verdict = "inconclusive"
        note = "not enough rounds to bootstrap an interval"
    elif imp_low > 0:
        verdict = "better"
        note = f"the model beats {label.lower()} over {n} paired rounds"
    elif imp_high < 0:
        verdict = "worse"
        note = (
            f"the model does NOT beat {label.lower()} over {n} paired rounds — "
            f"published as measured"
        )
    else:
        verdict = "inconclusive"
        note = (
            f"the interval straddles zero over {n} paired rounds; no difference "
            f"has been demonstrated"
        )

    return Comparison(
        metric=metric,
        baseline=baseline,
        baseline_label=label,
        race_type=race_type,
        lower_is_better=lower_better,
        n_rounds=n,
        rounds=rounds,
        model_mean=round(model_mean, 6),
        baseline_mean=round(baseline_mean, 6),
        delta=round(delta, 6),
        improvement=round(improvement, 6),
        ci_low=round(imp_low, 6) if imp_low is not None else None,
        ci_high=round(imp_high, 6) if imp_high is not None else None,
        p_model_better=round(p_model_better, 4) if p_model_better is not None else None,
        verdict=verdict,
        note=note,
    )


def _round_files(forward_eval_dir: Path) -> list[Path]:
    return sorted(p for p in forward_eval_dir.glob("round_*.json") if p.is_file())


def _race_type_blocks(payload: Mapping) -> dict[str, Mapping]:
    """The per-race-type metric blocks in one round file.

    A metric block is a dict carrying ``mean_position_error``; that shape test
    is what distinguishes ``sprint``/``feature``/``race`` from the sibling
    ``markets`` and ``baselines`` containers without hardcoding a series list.
    """
    return {
        key: value
        for key, value in payload.items()
        if isinstance(value, dict) and "mean_position_error" in value
    }


def _primary_race_type(race_types: Sequence[str]) -> str:
    """The race type a name-keyed baseline scores against.

    NASCAR and IndyCar publish TWO model blocks — ``race`` (pre-qualifying) and
    ``racePostQuali`` — but only one set of baselines, which scores the
    pre-qualifying forecast. Picking by iteration order over a set would attach
    them to whichever block happened to come out first, silently comparing the
    post-quali model against the pre-quali baseline on some runs and not others.
    ``race`` wins when present; otherwise the first in published order.
    """
    if "race" in race_types:
        return "race"
    return race_types[0] if race_types else "race"


def _baseline_blocks(payload: Mapping, race_types: Iterable[str]) -> dict[str, dict[str, Mapping]]:
    """``{baseline_name: {race_type: metrics}}`` for either published shape.

    The feeder shape keys ``baselines`` by race type with a single implicit
    last-race baseline; the single-race shape keys it by baseline name. Both
    normalise to the same nested map so the comparison code sees one thing.
    """
    raw = payload.get("baselines")
    if not isinstance(raw, dict):
        return {}

    ordered = list(race_types)
    known = set(ordered)
    primary = _primary_race_type(ordered)
    out: dict[str, dict[str, Mapping]] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        if key in known and "mean_position_error" in value:
            # feeder shape: baselines.sprint / baselines.feature
            out.setdefault("lastRace", {})[key] = value
        elif "mean_position_error" in value:
            # single-race shape: baselines.lastRace / baselines.gridOrder
            out.setdefault(key, {})[primary] = value
    return out


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def build_evidence(
    forward_eval_dir: Path | str,
    *,
    calibration_summary: Path | str | None = None,
    promotion_status: Path | str | None = None,
    sport: str | None = None,
    metrics: Sequence[str] = (HEADLINE_METRIC, "ndcg_at_5"),
) -> EvidenceBlock:
    """Assemble the evidence artifact from a project's published forward-eval.

    Reads only what ``export.py`` already publishes — this adds no new pipeline
    stage and cannot disagree with the accuracy page, because it is reading the
    same files the accuracy page reads.

    An empty or missing directory is not an error. It produces
    ``available=False`` with a reason, which is what a site should render
    before a season has run: "no benchmark has been published yet", not a
    blank panel and not a zero.
    """
    forward_eval_dir = Path(forward_eval_dir)
    if not forward_eval_dir.is_dir():
        return EvidenceBlock(
            available=False,
            reason="no forward-evaluation directory has been published",
            sport=sport,
        )

    files = _round_files(forward_eval_dir)
    if not files:
        return EvidenceBlock(
            available=False,
            reason="no round has been scored yet this season",
            sport=sport,
        )

    season_payload = _read_json(forward_eval_dir / "season.json") or {}

    # (metric, baseline, race_type) -> [(round, model, baseline)]
    paired: dict[tuple[str, str, str], list[tuple[int, float, float]]] = {}
    rounds_seen: set[int] = set()

    for path in files:
        payload = _read_json(path)
        if payload is None:
            continue
        rnd = payload.get("round")
        if not isinstance(rnd, int):
            continue
        rounds_seen.add(rnd)

        race_blocks = _race_type_blocks(payload)
        baselines = _baseline_blocks(payload, race_blocks)
        for baseline_name, per_type in baselines.items():
            for race_type, baseline_metrics in per_type.items():
                model_metrics = race_blocks.get(race_type)
                if not isinstance(model_metrics, dict):
                    continue
                for metric in metrics:
                    model_value = model_metrics.get(metric)
                    baseline_value = baseline_metrics.get(metric)
                    if not isinstance(model_value, (int, float)):
                        continue
                    if not isinstance(baseline_value, (int, float)):
                        continue
                    key = (metric, baseline_name, race_type)
                    paired.setdefault(key, []).append(
                        (rnd, float(model_value), float(baseline_value))
                    )

    comparisons = [
        compare_paired(metric, rows, baseline=baseline, race_type=race_type)
        for (metric, baseline, race_type), rows in sorted(paired.items())
        if rows
    ]

    if not comparisons:
        return EvidenceBlock(
            available=False,
            reason=(
                "rounds have been scored but no baseline was published alongside "
                "them — a metric without a baseline is not evidence"
            ),
            season=season_payload.get("season"),
            sport=sport,
            generated_at=season_payload.get("generatedAt"),
            rounds_scored=len(rounds_seen),
        )

    headline = _pick_headline(comparisons)
    calibration = _calibration_block(calibration_summary)
    promotion = _promotion_block(promotion_status)

    return EvidenceBlock(
        available=True,
        season=season_payload.get("season"),
        sport=sport,
        generated_at=season_payload.get("generatedAt"),
        rounds_scored=len(rounds_seen),
        headline=headline.to_json() if headline else None,
        comparisons=[c.to_json() for c in comparisons],
        calibration=calibration,
        promotion=promotion,
        caveats=_caveats(comparisons, calibration, len(rounds_seen)),
    )


def _pick_headline(comparisons: Sequence[Comparison]) -> Comparison | None:
    """The comparison a page leads with.

    Deliberately **not** the most flattering one. It is the headline metric
    against the hardest baseline available, on the race type with the most
    paired rounds — grid order beats last-race order as a yardstick wherever a
    series publishes it, so a project that has one is judged against it.
    """
    candidates = [c for c in comparisons if c.metric == HEADLINE_METRIC]
    if not candidates:
        candidates = list(comparisons)
    if not candidates:
        return None
    priority = {"gridOrder": 0, "lastRace": 1}
    return min(
        candidates,
        key=lambda c: (priority.get(c.baseline, 2), -c.n_rounds, c.race_type),
    )


def _calibration_block(path: Path | str | None) -> dict | None:
    payload = _read_json(Path(path)) if path else None
    if payload is None:
        return None
    applied = bool(payload.get("applied"))
    return {
        "applied": applied,
        "trainingRounds": payload.get("trainingRounds"),
        "dataLimitation": payload.get("dataLimitation"),
        "note": (
            "probabilities are calibrated on real results"
            if applied
            else "probabilities are UNCALIBRATED — the gate has not opened yet"
        ),
    }


def _promotion_block(path: Path | str | None) -> dict | None:
    payload = _read_json(Path(path)) if path else None
    if payload is None:
        return None
    return {
        "decision": payload.get("decision"),
        "reason": payload.get("reason"),
        "candidate": payload.get("candidate"),
        "roundsCompared": payload.get("roundsCompared"),
    }


def _caveats(
    comparisons: Sequence[Comparison],
    calibration: Mapping | None,
    rounds_scored: int,
) -> list[str]:
    """The sentences a page must print, whether or not the news is good.

    A caveat is emitted on a *hit* as readily as on a miss — a favourable result
    read as proof is the same error in the flattering direction.
    """
    out: list[str] = []
    if rounds_scored < MIN_ROUNDS_FOR_CLAIM:
        out.append(
            f"Only {rounds_scored} round(s) have been scored. Nothing here is a "
            f"claim yet."
        )
    losing = [c for c in comparisons if c.verdict == "worse"]
    if losing:
        names = sorted({c.baseline_label.lower() for c in losing})
        out.append(
            "The model does not beat " + ", ".join(names) + " on every measured "
            "comparison. That is stated rather than hidden."
        )
    inconclusive = [c for c in comparisons if c.verdict == "inconclusive"]
    if inconclusive:
        out.append(
            "Some comparisons straddle zero: a difference has not been "
            "demonstrated, in either direction."
        )
    if calibration is not None and not calibration.get("applied"):
        out.append(
            "The calibration gate is closed, so the probabilities are raw model "
            "output and should not be read as confidence levels."
        )
    out.append(
        "Metrics are only comparable within this series. A position error over "
        "this field size means nothing next to another series' number."
    )
    return out


def write_evidence(block: EvidenceBlock, out_path: Path | str) -> Path:
    """Write the artifact next to the rest of a project's published JSON."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(block.to_json(), fh, indent=2)
        fh.write("\n")
    return out_path


__all__ = [
    "MIN_ROUNDS_FOR_CLAIM",
    "BOOTSTRAP_RESAMPLES",
    "BOOTSTRAP_SEED",
    "METRIC_DIRECTION",
    "HEADLINE_METRIC",
    "BASELINE_LABELS",
    "Comparison",
    "EvidenceBlock",
    "paired_bootstrap",
    "compare_paired",
    "build_evidence",
    "write_evidence",
]
