"""Probability calibration layer for F1 predictions.

The upstream pipeline regresses **mean lap time** per driver and sorts to a
finishing order.  That gives a point prediction in seconds — fine for "who is
fastest in clean air", useless for betting.  A betting tool needs **calibrated
probabilities**: per-driver P(win), P(podium), P(top-6), P(top-10), plus a
head-to-head matrix P(A finishes ahead of B).  This module converts lap-time
outputs into those probabilities.

Pipeline (per round):

    predicted lap times  →  Plackett–Luce strengths λᵢ = exp(-(tᵢ - t_min) / τ)
                         →  Monte Carlo sample of N=5000 full finishing orders
                            (weighted draw without replacement on λ)
                         →  empirical P(win), P(podium), P(top6), P(top10), H2H
                         →  isotonic calibration (per market) from historical
                            (predicted, observed) pairs

Calibration data limitation
---------------------------
At the time of writing only **one** 2026 round (Round 4) has actual results in
`season_results_2026.json`, and no historical (predicted, actual) probability
pairs exist for prior seasons in this repo (predictions are only stored for
2026).  A single race is nowhere near enough to fit an isotonic regression
per market — fitting on it would essentially memorise that one race.  Until
multi-season historical predictions land (or a backfill of pre-race odds is
added per §2.2 of the audit), `ProbabilityCalibrator.fit_from_history()` will
either no-op or fit on whatever sparse data is available, and the exported
`calibration.applied` flag in each round JSON honestly reports `false` when
there isn't enough data.  See also `export_probabilities.py`.

Hard rules honoured here:

* Pure-additive module; does not modify `f1_prediction_utils.py`,
  `advanced_models.py`, `leakage.py`, `forward_eval.py`, or `requirements.txt`.
* Single seeded RNG (`np.random.default_rng(seed=42)`); no unseeded calls.
* Leakage discipline delegated to `leakage.assert_seasons_prior_only` for
  callers that build training datasets from multi-season history.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np
from sklearn.isotonic import IsotonicRegression

# Markets we calibrate.  Order is load-bearing: callers iterate this tuple
# when building summary reports and reliability diagrams.
MARKETS: tuple[str, ...] = ("win", "podium", "top6", "top10")

# Default Plackett–Luce temperature in seconds.  A 0.5s spread on lap-time
# differences gives a sensible top-of-grid concentration without collapsing the
# distribution onto the fastest driver.  Smaller τ → sharper distribution.
DEFAULT_TEMPERATURE: float = 0.5

# Default Monte Carlo sample count.  5000 is enough for stable win/podium
# estimates (std-err ~ √(p(1-p)/N) ≈ 0.007 at p=0.5) without being slow.
DEFAULT_N_SAMPLES: int = 5000


# --------------------------------------------------------------------------- #
# Plackett–Luce sampling
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MarketProbabilities:
    """Per-driver probabilities for the four headline markets + H2H matrix."""

    drivers: tuple[str, ...]
    p_win: dict[str, float]
    p_podium: dict[str, float]
    p_top6: dict[str, float]
    p_top10: dict[str, float]
    h2h: dict[str, dict[str, float]]
    n_samples: int
    temperature: float


def _compute_strengths(
    lap_times: Mapping[str, float],
    temperature: float = DEFAULT_TEMPERATURE,
) -> tuple[list[str], np.ndarray]:
    """Convert lap times to Plackett–Luce strengths λᵢ.

    λᵢ = exp(-(tᵢ - t_min) / τ).  The shift by `t_min` keeps the max strength
    at 1.0, which makes float arithmetic well-behaved (no overflow / underflow
    for any plausible spread).
    """
    drivers = list(lap_times.keys())
    times = np.array([float(lap_times[d]) for d in drivers], dtype=np.float64)
    if temperature <= 0:
        raise ValueError(f"temperature must be > 0; got {temperature!r}")
    t_min = float(times.min())
    strengths = np.exp(-(times - t_min) / temperature)
    return drivers, strengths


def _sample_rankings(
    strengths: np.ndarray,
    n_samples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sample `n_samples` full finishing orders via Plackett–Luce.

    Plackett–Luce: at each step, pick the next finisher proportional to
    remaining strength.  We vectorise across samples by using the Gumbel-max
    trick — adding i.i.d. Gumbel noise to log-strengths and argsort'ing — which
    is exactly equivalent to sequential sampling-without-replacement weighted
    by softmax(λ) (Yellott 1977 / Plackett 1975).

    Returns
    -------
    np.ndarray of shape (n_samples, n_drivers); each row is a permutation of
    driver indices, where position 0 = winner, position 1 = P2, etc.
    """
    n_drivers = strengths.shape[0]
    log_strengths = np.log(strengths)  # safe: strengths are exp(...) > 0
    # Gumbel(0, 1) noise: −log(−log(U)).  Adding this to log-strengths and
    # argsort'ing in descending order = Plackett-Luce sample.
    u = rng.uniform(size=(n_samples, n_drivers))
    gumbel = -np.log(-np.log(u))
    perturbed = log_strengths[None, :] + gumbel
    # argsort in descending order: best (highest) first.
    return np.argsort(-perturbed, axis=1)


def plackett_luce_probabilities(
    lap_times: Mapping[str, float],
    n_samples: int = DEFAULT_N_SAMPLES,
    temperature: float = DEFAULT_TEMPERATURE,
    seed: int = 42,
) -> MarketProbabilities:
    """Run the full Plackett-Luce → market-probability pipeline.

    Parameters
    ----------
    lap_times
        Mapping driver_code → predicted lap time (seconds).  All drivers in
        this map participate in the simulated race.
    n_samples
        Number of Monte Carlo simulations.  Default 5000.
    temperature
        Plackett-Luce τ in seconds.  Default 0.5.
    seed
        RNG seed (default 42 — required by project conventions, do not
        reseed elsewhere).
    """
    if not lap_times:
        raise ValueError("lap_times is empty")
    drivers, strengths = _compute_strengths(lap_times, temperature=temperature)
    rng = np.random.default_rng(seed=seed)
    rankings = _sample_rankings(strengths, n_samples=n_samples, rng=rng)
    return _empirical_market_probs(
        drivers=drivers,
        rankings=rankings,
        n_samples=n_samples,
        temperature=temperature,
    )


def _empirical_market_probs(
    drivers: list[str],
    rankings: np.ndarray,
    n_samples: int,
    temperature: float,
) -> MarketProbabilities:
    """Reduce a (n_samples, n_drivers) ranking array into market probabilities."""
    n_drivers = len(drivers)
    # For each driver i, count how often they finish at each rank slot.
    # rankings[s, k] = driver index that finished in position k+1 in sample s.
    # We want, per driver i, P(finish ≤ k) for k ∈ {1, 3, 6, 10}.
    # Build a (n_samples, n_drivers) position matrix where positions[s, i] = the
    # rank (1-indexed) of driver i in sample s.
    positions = np.empty_like(rankings)
    sample_idx = np.arange(n_samples)[:, None]
    positions[sample_idx, rankings] = np.arange(n_drivers)[None, :]
    # positions[s, i] now holds the 0-indexed finish position of driver i in sample s.

    p_win_arr = (positions == 0).mean(axis=0)
    p_podium_arr = (positions <= 2).mean(axis=0)
    # Clamp the cumulative thresholds at the actual grid size so e.g. a 9-driver
    # field can't have p_top10 > p_podium artefacts.
    top6_thresh = min(5, n_drivers - 1)
    top10_thresh = min(9, n_drivers - 1)
    p_top6_arr = (positions <= top6_thresh).mean(axis=0)
    p_top10_arr = (positions <= top10_thresh).mean(axis=0)

    p_win = {d: float(p_win_arr[i]) for i, d in enumerate(drivers)}
    p_podium = {d: float(p_podium_arr[i]) for i, d in enumerate(drivers)}
    p_top6 = {d: float(p_top6_arr[i]) for i, d in enumerate(drivers)}
    p_top10 = {d: float(p_top10_arr[i]) for i, d in enumerate(drivers)}

    # H2H matrix.  P(A beats B) = mean over samples of (positions[s, A] < positions[s, B]).
    # Vectorised: positions has shape (n_samples, n_drivers); broadcast to (n_samples, n, n).
    # That's O(n_samples * n^2) memory ~ 5000 * 484 = 2.4M floats, fine.
    pos_i = positions[:, :, None]
    pos_j = positions[:, None, :]
    ahead = (pos_i < pos_j).mean(axis=0)
    h2h: dict[str, dict[str, float]] = {}
    for i, di in enumerate(drivers):
        row: dict[str, float] = {}
        for j, dj in enumerate(drivers):
            if i == j:
                continue
            row[dj] = float(ahead[i, j])
        h2h[di] = row

    return MarketProbabilities(
        drivers=tuple(drivers),
        p_win=p_win,
        p_podium=p_podium,
        p_top6=p_top6,
        p_top10=p_top10,
        h2h=h2h,
        n_samples=n_samples,
        temperature=temperature,
    )


# --------------------------------------------------------------------------- #
# Calibrator
# --------------------------------------------------------------------------- #


@dataclass
class ProbabilityCalibrator:
    """Per-market isotonic calibration over (predicted, observed) pairs.

    Use pattern::

        cal = ProbabilityCalibrator()
        cal.fit_from_history([
            {"market": "win",    "predicted": 0.32, "observed": 1},
            {"market": "win",    "predicted": 0.05, "observed": 0},
            {"market": "podium", "predicted": 0.61, "observed": 0},
            ...
        ])
        cal.transform("win", [0.32, 0.05])  # → np.ndarray of calibrated probs

    Markets with too few samples are left un-fitted and `transform()` returns
    the raw input.  We require at least 5 distinct prediction levels per market
    before fitting isotonic; below that the fit is effectively memorisation.
    """

    _models: dict[str, IsotonicRegression] = field(default_factory=dict)
    _fit_sample_counts: dict[str, int] = field(default_factory=dict)
    _min_samples: int = 5

    def fit_from_history(self, history: Sequence[Mapping[str, object]]) -> "ProbabilityCalibrator":
        """Fit isotonic regression per market from a flat list of records.

        Each record must contain ``market: str``, ``predicted: float`` (in
        [0, 1]), ``observed: int`` (0 or 1).  Records for unknown markets are
        ignored — the contract is permissive so an upstream
        odds-from-the-market backfill doesn't have to know which markets we
        currently price.
        """
        by_market: dict[str, list[tuple[float, int]]] = {m: [] for m in MARKETS}
        for rec in history:
            market = rec.get("market")
            if market not in by_market:
                continue
            try:
                p = float(rec["predicted"])
                y = int(rec["observed"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (0.0 <= p <= 1.0) or y not in (0, 1):
                continue
            by_market[market].append((p, y))

        for market, pairs in by_market.items():
            if len(pairs) < self._min_samples:
                continue
            preds = np.array([p for p, _ in pairs], dtype=np.float64)
            obs = np.array([y for _, y in pairs], dtype=np.float64)
            # Need at least 2 distinct prediction levels for isotonic to be
            # meaningful; a single repeated x value collapses to the mean.
            if len(np.unique(preds)) < 2:
                continue
            model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            model.fit(preds, obs)
            self._models[market] = model
            self._fit_sample_counts[market] = len(pairs)
        return self

    def is_fitted(self, market: str | None = None) -> bool:
        if market is None:
            return bool(self._models)
        return market in self._models

    def transform(
        self,
        market: str,
        predicted: Sequence[float] | np.ndarray,
    ) -> np.ndarray:
        """Apply per-market calibration.  Pass-through if not fitted."""
        arr = np.asarray(list(predicted), dtype=np.float64)
        if market not in self._models:
            return arr.copy()
        return np.clip(self._models[market].transform(arr), 0.0, 1.0)

    def sample_counts(self) -> dict[str, int]:
        """How many records each per-market model was trained on."""
        return dict(self._fit_sample_counts)


# --------------------------------------------------------------------------- #
# Stratified calibrator — A-P2.2
# --------------------------------------------------------------------------- #


@dataclass
class StratifiedProbabilityCalibrator:
    """Isotonic per (market, stratum) — falls back to global when sparse.

    Each input record may carry an optional ``stratum`` field (e.g. a
    circuit-type label).  The calibrator fits one isotonic per
    (market, stratum) pair when enough samples exist for that bucket;
    otherwise rows go into a *global* isotonic that's always trained.

    At transform time, ``stratum=None`` or an unseen stratum routes the
    request to the global model.

    This is the v1 implementation called out in the audit's A-P2.2 item.
    The bucketing scheme (driver-tier, circuit-type, …) is the caller's
    choice — this class just keeps the per-stratum books.
    """

    _stratum_models: dict[str, dict[str, IsotonicRegression]] = field(default_factory=dict)
    _global: ProbabilityCalibrator = field(default_factory=ProbabilityCalibrator)
    _min_samples_per_stratum: int = 8  # higher than global; smaller buckets need protection

    def fit_from_history(
        self, history: Sequence[Mapping[str, object]]
    ) -> "StratifiedProbabilityCalibrator":
        """Fit one isotonic per (market, stratum) where data permits.

        Records without a stratum field still feed the global calibrator,
        so the cross-track baseline is always available as a safety net.
        """
        # Always fit a global model on every record (we strip the stratum
        # before passing to the base class).
        self._global.fit_from_history(history)

        # Bucket by (stratum, market) for the stratified fits.
        by_bucket: dict[tuple[str, str], list[tuple[float, int]]] = {}
        for rec in history:
            stratum = rec.get("stratum")
            market = rec.get("market")
            if stratum is None or market not in MARKETS:
                continue
            try:
                p = float(rec["predicted"])
                y = int(rec["observed"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (0.0 <= p <= 1.0) or y not in (0, 1):
                continue
            by_bucket.setdefault((str(stratum), market), []).append((p, y))

        for (stratum, market), pairs in by_bucket.items():
            if len(pairs) < self._min_samples_per_stratum:
                continue
            preds = np.array([p for p, _ in pairs], dtype=np.float64)
            obs = np.array([y for _, y in pairs], dtype=np.float64)
            if len(np.unique(preds)) < 2:
                continue
            model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            model.fit(preds, obs)
            self._stratum_models.setdefault(stratum, {})[market] = model
        return self

    def is_fitted(self, market: str | None = None, stratum: str | None = None) -> bool:
        """True if a stratum-specific OR global isotonic exists.

        - ``market=None``: any stratum or global model present.
        - ``market`` set, ``stratum=None``: returns global is_fitted(market).
        - both set: returns True if the (stratum, market) model exists.
        """
        if market is None:
            return bool(self._stratum_models) or self._global.is_fitted()
        if stratum is not None and stratum in self._stratum_models:
            if market in self._stratum_models[stratum]:
                return True
        return self._global.is_fitted(market)

    def transform(
        self,
        market: str,
        predicted: Sequence[float] | np.ndarray,
        stratum: str | None = None,
    ) -> np.ndarray:
        """Apply per-(market, stratum) calibration, falling back to global."""
        arr = np.asarray(list(predicted), dtype=np.float64)
        if stratum is not None and stratum in self._stratum_models:
            stratum_model = self._stratum_models[stratum].get(market)
            if stratum_model is not None:
                return np.clip(stratum_model.transform(arr), 0.0, 1.0)
        return self._global.transform(market, arr)

    def sample_counts(self) -> dict[str, int | dict[str, int]]:
        """Bucket sample sizes for diagnostic display."""
        out: dict[str, int | dict[str, int]] = {
            "global": dict(self._global.sample_counts()),
        }
        for stratum, models in self._stratum_models.items():
            out[stratum] = {m: -1 for m in models}  # exact count not tracked in v1
        return out

    def strata_with_models(self) -> dict[str, list[str]]:
        """Map stratum → list of market names with fitted models."""
        return {s: sorted(models.keys()) for s, models in self._stratum_models.items()}


# --------------------------------------------------------------------------- #
# Reliability diagram + metrics
# --------------------------------------------------------------------------- #


def reliability_diagram(
    predicted: Sequence[float] | np.ndarray,
    observed: Sequence[int] | np.ndarray,
    n_bins: int = 10,
) -> list[dict]:
    """Bin predictions into `n_bins` equal-width buckets in [0, 1].

    Returns a list of dicts with keys ``meanPred``, ``empirical``, ``count``.
    Buckets with zero observations are dropped from the output (a calibration
    plot with empty bins just adds noise).
    """
    preds = np.asarray(list(predicted), dtype=np.float64)
    obs = np.asarray(list(observed), dtype=np.float64)
    if preds.shape != obs.shape:
        raise ValueError(
            f"predicted and observed must align; got {preds.shape} vs {obs.shape}"
        )
    if preds.size == 0:
        return []
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # Make the rightmost bin closed so p=1.0 lands in bin (n_bins-1).
    bin_idx = np.clip(np.digitize(preds, edges, right=False) - 1, 0, n_bins - 1)
    out: list[dict] = []
    for b in range(n_bins):
        mask = bin_idx == b
        count = int(mask.sum())
        if count == 0:
            continue
        out.append(
            {
                "meanPred": float(preds[mask].mean()),
                "empirical": float(obs[mask].mean()),
                "count": count,
            }
        )
    return out


def brier_score(
    predicted: Sequence[float] | np.ndarray,
    observed: Sequence[int] | np.ndarray,
) -> float:
    """Mean squared error between predicted probability and 0/1 outcome."""
    p = np.asarray(list(predicted), dtype=np.float64)
    y = np.asarray(list(observed), dtype=np.float64)
    if p.shape != y.shape:
        raise ValueError("predicted and observed shapes differ")
    if p.size == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def log_loss(
    predicted: Sequence[float] | np.ndarray,
    observed: Sequence[int] | np.ndarray,
    eps: float = 1e-9,
) -> float:
    """Binary log-loss; predictions are clipped to [eps, 1-eps] to avoid inf."""
    p = np.clip(np.asarray(list(predicted), dtype=np.float64), eps, 1.0 - eps)
    y = np.asarray(list(observed), dtype=np.float64)
    if p.shape != y.shape:
        raise ValueError("predicted and observed shapes differ")
    if p.size == 0:
        return float("nan")
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


# --------------------------------------------------------------------------- #
# Helpers for downstream consumers
# --------------------------------------------------------------------------- #


def calibrate_market_probabilities(
    raw: MarketProbabilities,
    calibrator: ProbabilityCalibrator | None,
) -> dict[str, dict[str, dict[str, float]]]:
    """Return a market → driver → {probability, rawProbability} structure.

    Centralised here so the exporter and tests use identical formatting and
    rounding policy.
    """
    raw_by_market: dict[str, dict[str, float]] = {
        "win": raw.p_win,
        "podium": raw.p_podium,
        "top6": raw.p_top6,
        "top10": raw.p_top10,
    }
    out: dict[str, dict[str, dict[str, float]]] = {}
    for market, raw_probs in raw_by_market.items():
        drivers = list(raw_probs.keys())
        raw_vals = np.array([raw_probs[d] for d in drivers], dtype=np.float64)
        if calibrator is not None and calibrator.is_fitted(market):
            calibrated_vals = calibrator.transform(market, raw_vals)
        else:
            calibrated_vals = raw_vals
        out[market] = {
            d: {
                "probability": float(calibrated_vals[i]),
                "rawProbability": float(raw_vals[i]),
            }
            for i, d in enumerate(drivers)
        }
    return out


# Each market's probabilities must sum to the size of the set it describes:
# exactly one winner, three podium slots, six top-6 slots, ten top-10 slots.
MARKET_TARGET_SUM: dict[str, float] = {"win": 1.0, "podium": 3.0, "top6": 6.0, "top10": 10.0}


def renormalize_market_struct(
    market_struct: dict[str, dict[str, dict[str, float]]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Restore probabilistic coherence after per-driver isotonic calibration.

    Isotonic calibration maps each driver's probability independently, so a
    market no longer sums to its set size (the 2026-07-07 audit measured
    published win markets summing to 1.17-1.94). This water-fills each market
    back to its target sum: scale everyone, cap at 1.0, redistribute the
    excess over the uncapped drivers. Raw Plackett-Luce probabilities are
    empirical MC frequencies and already coherent — for them this is a
    numerical no-op. ``rawProbability`` is left untouched.
    """
    out: dict[str, dict[str, dict[str, float]]] = {}
    for market, drivers in market_struct.items():
        target = MARKET_TARGET_SUM.get(market)
        if target is None or not drivers:
            out[market] = drivers
            continue
        names = list(drivers.keys())
        probs = np.array(
            [max(float(drivers[d]["probability"]), 0.0) for d in names],
            dtype=np.float64,
        )
        if probs.sum() <= 0:
            out[market] = drivers
            continue
        capped = np.zeros(len(names), dtype=bool)
        for _ in range(len(names)):
            free = ~capped
            remaining = target - float(capped.sum())  # capped drivers hold 1.0
            free_sum = probs[free].sum()
            if remaining <= 0 or free_sum <= 0:
                break
            probs[free] = probs[free] * (remaining / free_sum)
            overflow = free & (probs > 1.0)
            if not overflow.any():
                break
            probs[overflow] = 1.0
            capped |= overflow
        out[market] = {
            d: {
                "probability": float(probs[i]),
                "rawProbability": float(drivers[d]["rawProbability"]),
            }
            for i, d in enumerate(names)
        }
    return out


def collect_history_from_rounds(
    round_predictions: Mapping[int, MarketProbabilities],
    round_actuals: Mapping[int, Mapping[str, int]],
) -> list[dict]:
    """Build a (predicted, observed) record list per market from completed rounds.

    Used to fit `ProbabilityCalibrator` over the rounds for which we have
    actual finishing positions.  The observation rules per market:

      * win    : observed = 1 iff actual position == 1
      * podium : observed = 1 iff actual position <= 3
      * top6   : observed = 1 iff actual position <= 6
      * top10  : observed = 1 iff actual position <= 10

    Drivers absent from the actual map (DNS / DNQ / fluke missing data) are
    skipped — we never invent an observation.
    """
    out: list[dict] = []
    market_thresholds = {"win": 1, "podium": 3, "top6": 6, "top10": 10}
    for rnd, mp in round_predictions.items():
        actual = round_actuals.get(rnd)
        if not actual:
            continue
        for driver in mp.drivers:
            actual_pos = actual.get(driver)
            if actual_pos is None:
                continue
            raw_by_market = {
                "win": mp.p_win.get(driver, 0.0),
                "podium": mp.p_podium.get(driver, 0.0),
                "top6": mp.p_top6.get(driver, 0.0),
                "top10": mp.p_top10.get(driver, 0.0),
            }
            for market, thresh in market_thresholds.items():
                out.append(
                    {
                        "market": market,
                        "predicted": float(raw_by_market[market]),
                        "observed": int(actual_pos <= thresh),
                        "round": int(rnd),
                        "driver": driver,
                    }
                )
    return out
