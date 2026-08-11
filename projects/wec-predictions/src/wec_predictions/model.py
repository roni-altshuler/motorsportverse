"""The FIA WEC prediction model — per class.

Endurance is multi-class and car-based, so the model forecasts each class as its
own field and the competitor is the **car entry**. For a class at a round it
estimates a leakage-safe latent *pace* per entry (lower = faster) by blending:

* **cross-season entry Elo** — the car's own strength, carried year to year
  (top entries keep their number, so ``HYP-7`` is Toyota #7 across seasons);
* **this-season form** — average within-class finishing position so far, with a
  prior-season fallback so the opener isn't blind;
* **team strength** and **manufacturer strength** — a works Ferrari/Toyota/
  Porsche is a different weapon from a customer car, and endurance rewards the
  operation (pit crew, strategy, reliability) as much as the entry.

That pace is routed through the shared Plackett-Luce sampler to per-class
win/podium/top-N markets and finishing-range bands. Endurance's high attrition is
absorbed by a hotter sampler temperature. Everything numerically heavy is reused
from ``motorsport-core``; only the per-class endurance logic lives here.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Mapping

import numpy as np

from motorsport_core import calibration, conformal, elo, leakage
from motorsport_core.calibration import MarketProbabilities

from . import config
from .datasource import WecDataSource


@dataclass
class ClassForecast:
    cls: str
    field: list[str]
    order: list[str]
    score: dict[str, float]
    markets: MarketProbabilities
    mean_finish: dict[str, float]
    range_low: dict[str, int]
    range_high: dict[str, int]
    confidence: dict[str, str]
    n_samples: int
    temperature: float


@dataclass
class RoundForecast:
    season: int
    round: int
    place: str
    country: str | None
    event: str
    classes: list[ClassForecast] = dc_field(default_factory=list)


# --------------------------------------------------------------------------- #
def _zscores(values: Mapping[str, float]) -> dict[str, float]:
    keys = list(values.keys())
    if not keys:
        return {}
    arr = np.array([values[k] for k in keys], dtype=float)
    sd = float(arr.std())
    if sd <= 1e-9:
        return {k: 0.0 for k in keys}
    mu = float(arr.mean())
    return {k: (float(values[k]) - mu) / sd for k in keys}


@dataclass
class _SeasonMeta:
    """Team/manufacturer/class lookups for a season (any historical year)."""
    team_of: dict[str, str]
    manuf_of: dict[str, str]

    @classmethod
    def for_year(cls, year: int) -> "_SeasonMeta":
        snap = config.load_snapshot(year)
        team_of, manuf_of = {}, {}
        for e in snap.get("entries") or []:
            team_of[e["code"]] = e.get("team") or "?"
            manuf_of[e["code"]] = e.get("manufacturer") or "?"
        return cls(team_of=team_of, manuf_of=manuf_of)


def _teammates(field: list[str], team_of: Mapping[str, str]) -> dict[str, str | None]:
    by_team: dict[str, list[str]] = {}
    for c in field:
        by_team.setdefault(team_of.get(c, "?"), []).append(c)
    out: dict[str, str | None] = {}
    for codes in by_team.values():
        for c in codes:
            others = [o for o in codes if o != c]
            out[c] = others[0] if others else None
    return out


def _elo_ratings(source: WecDataSource, year: int, round: int, cls: str,
                 field: list[str], meta: _SeasonMeta) -> tuple[dict[str, float], dict[str, float]]:
    builder = elo.EloFeatureBuilder()
    events: list[elo.RaceEvent] = []
    for (yr, sub, finish) in source.history_events(year, round, cls):
        events.append(
            elo.RaceEvent(
                season=yr, round=sub, finish_order=dict(finish),
                grid_order=dict(finish), team_of=meta.team_of,
            )
        )
    # current-season cutoff: sub-rounds are 1..N; forecasting uses everything
    # replayed (history_events already excludes >= round), so cutoff is +inf.
    builder.replay_history(events, current_season=year, current_round=10**6)
    builder.ensure_rookies({c: meta.team_of.get(c, "?") for c in field})
    teammate = _teammates(field, meta.team_of)
    entry_elo, team_elo = {}, {}
    for c in field:
        feats = builder.features_for(c, meta.team_of.get(c, "?"), teammate.get(c))
        entry_elo[c] = feats["driver_elo"]
        team_elo[c] = feats["team_elo"]
    return entry_elo, team_elo


def _lastrace_signal(source: WecDataSource, year: int, round: int, cls: str,
                     field: list[str]) -> dict[str, float]:
    """Previous within-class finishing order (negated position); recency signal.

    Uses the most recent prior round this season, falling back to the previous
    season's final round for the opener so the signal is never blank. Entries not
    in that race are placed one slot behind the field.
    """
    prior = [r for r in source.completed_rounds(year) if r < round]
    pos: dict[str, int] = {}
    if prior:
        res = source.class_results(year, max(prior), cls)
        pos = {r.competitor: r.position for r in res} if res else {}
    if not pos:
        for y in reversed([s for s in config.HISTORY_SEASONS if s < year]):
            rounds = source.completed_rounds(y)
            if rounds:
                res = source.class_results(y, max(rounds), cls)
                if res:
                    pos = {r.competitor: r.position for r in res}
                    break
    worst = (max(pos.values()) + 1) if pos else 1
    return {c: -float(pos.get(c, worst)) for c in field}


def estimate_class_skill(source: WecDataSource, year: int, round: int, cls: str,
                         field: list[str]) -> dict[str, float]:
    """Per-entry latent pace (lower = faster) from leakage-safe prior signals.

    Ensembles four signals (see :data:`config.SKILL_WEIGHTS`): the last race's
    order (recency), a smoothed cross-season entry Elo, this-season average
    finish, and the team's Elo — blended in z-score space, then mapped to the
    pace scale the Plackett-Luce sampler reads.
    """
    prior = [r for r in source.completed_rounds(year) if r < round]
    leakage.assert_prior_only(
        {r: None for r in prior}, current_round=round, label=f"wec.model.skill.{cls}"
    )
    if not field:
        return {}
    meta = _SeasonMeta.for_year(year)
    entry_elo, team_elo = _elo_ratings(source, year, round, cls, field, meta)
    avg_pos, _counts = source.prior_form(year, round, cls)
    field_mean = (sum(avg_pos.values()) / len(avg_pos)) if avg_pos else 0.0
    history_signal = {c: -avg_pos.get(c, field_mean) for c in field}
    last_signal = _lastrace_signal(source, year, round, cls, field)

    z_last = _zscores(last_signal)
    z_elo = _zscores(entry_elo)
    z_team = _zscores(team_elo)
    z_hist = _zscores(history_signal)
    w = config.SKILL_WEIGHTS
    merit = {
        c: (w["last"] * z_last.get(c, 0.0) + w["elo"] * z_elo.get(c, 0.0)
            + w["history"] * z_hist.get(c, 0.0) + w["team"] * z_team.get(c, 0.0))
        for c in field
    }
    # Re-normalise the blended merit to unit spread so ``PACE_SPREAD`` controls
    # the Plackett-Luce sharpness consistently regardless of how many signals or
    # what weights the ensemble carries (the weights set the *mix*, not the
    # overall confidence). This is what the walk-forward tuning assumed.
    z_merit = _zscores(merit)
    return {c: config.PACE_BASE - config.PACE_SPREAD * z_merit.get(c, 0.0) for c in field}


# --------------------------------------------------------------------------- #
def _positional_stats(orders: list[list[str]], codes: list[str]):
    idx = {c: i for i, c in enumerate(codes)}
    pos = np.empty((len(orders), len(codes)), dtype=float)
    for s, order in enumerate(orders):
        for p, c in enumerate(order, start=1):
            pos[s, idx[c]] = p
    mean = pos.mean(axis=0)
    p10 = np.percentile(pos, 10, axis=0)
    p90 = np.percentile(pos, 90, axis=0)
    return (
        {c: float(mean[i]) for c, i in idx.items()},
        {c: int(round(p10[i])) for c, i in idx.items()},
        {c: int(round(p90[i])) for c, i in idx.items()},
    )


def forecast_class(source: WecDataSource, year: int, round: int, cls: str, *,
                   n_samples: int | None = None, field: list[str] | None = None
                   ) -> ClassForecast | None:
    n_samples = n_samples or config.DEFAULT_SAMPLES
    field = field if field is not None else source.field_for(year, round, cls)
    field = [c for c in field]
    if len(field) < 2:
        return None
    score = estimate_class_skill(source, year, round, cls, field)
    temperature = config.BASE_TEMPERATURE
    markets = calibration.plackett_luce_probabilities(
        score, n_samples=n_samples, temperature=temperature
    )
    orders = calibration.sample_finishing_orders(
        score, n_samples=n_samples, temperature=temperature
    )
    mean_finish, range_low, range_high = _positional_stats(orders, field)
    order = sorted(field, key=lambda c: mean_finish[c])
    widths = [range_high[c] - range_low[c] for c in field]
    labels = conformal.width_to_confidence_label(widths)
    confidence = {c: labels[i] for i, c in enumerate(field)} if labels else {}
    return ClassForecast(
        cls=cls, field=field, order=order, score=dict(score), markets=markets,
        mean_finish=mean_finish, range_low=range_low, range_high=range_high,
        confidence=confidence, n_samples=markets.n_samples, temperature=markets.temperature,
    )


def forecast_round(source: WecDataSource, year: int, round: int, *,
                   n_samples: int | None = None, classes: list[str] | None = None
                   ) -> RoundForecast:
    classes = classes or source.classes_for_round(year, round)
    meta = config.round_meta(round)
    out = RoundForecast(
        season=year, round=round, place=meta.get("place", f"Round {round}"),
        country=meta.get("country") or None, event=meta.get("event", f"Round {round}"),
    )
    for cls in classes:
        fc = forecast_class(source, year, round, cls, n_samples=n_samples)
        if fc is not None:
            out.classes.append(fc)
    return out
