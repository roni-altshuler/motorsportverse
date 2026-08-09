"""Monte Carlo race simulator on top of the per-lap race-pace model.

Why this exists
---------------
This is Step 2 of the A-P1.1 push.  ``models/race_pace.py`` (Step 1) learned
to predict one lap's lap-time given driver, tyre, traffic, weather, and
race-state features.  This module runs that model forward — driver-by-driver,
lap-by-lap — to produce a *distribution* of finishing positions instead of
a deterministic ranking.

The output replaces the Plackett-Luce-from-qualifying-time sampler in
[models/calibration.py:129] for the race-finishing markets (win, podium,
top6, top10).  Quali time stays as an input feature; the model decides how
much weight it carries based on the circuit's overtaking difficulty (learned
from data, not the hand-tuned ``quali_lock_in ∈ [0.28, 0.82]`` in
[f1_prediction_utils.py:1122]).

What the simulator does each iteration
--------------------------------------
For one MC sample, for each of N laps:
  1. Compute the per-driver feature vector (current position, tyre state,
     current gaps, weather snapshot, SC/VSC flags from the per-sample
     event sequence).
  2. Call ``race_pace.predict_lap_times`` once on the 20-row feature
     matrix.
  3. Add a *per-sample per-driver car-performance shock* (constant across
     the race — "how good is this car today") plus lap-to-lap noise.
  4. Apply pit-stop logic for any driver whose strategy says "pit this
     lap" — adds pit-loss seconds, resets tyre age, rotates compound.
  5. Update cumulative race time and recompute running positions/gaps.

Two forms of race-day chaos keep the win market out of the degenerate
"one car at 98%" regime that a pure-pace forward-run collapses into:

* **Retirement / DNF** — each sample draws a per-driver Bernoulli(p_dnf).
  A retired car stops accumulating time at a sampled retirement lap and is
  classified behind every car that finished, so the win/podium mass
  redistributes to the field roughly as often as the real leader breaks
  down.  Without this a fast-pace car finishes in ~every sample and the win
  probability collapses onto one driver (the round-10 ANT=0.982 symptom).
* **Per-sample car-performance shock** — a once-per-sample per-driver
  offset (s/lap, held constant across the race, because a car that is "on
  it" today is on it all race) tied to real lap-time spread.  This widens
  the finishing distribution so a dominant car is a strong favourite but
  not a lock.

Aggregation applies a weak Dirichlet (base-rate) smoothing so no market
probability is ever exactly 0.0 or 1.0 while the sum invariants
(``sum(p_win)==1``, ``sum(p_podium)==3`` …) are preserved exactly.

Constraints honoured
--------------------
* The simulator is **deterministic given a seed**.  We accept a
  ``np.random.Generator`` from the caller; if absent, default seed=42 per
  project convention (matches ``models/calibration.py`` and ``leakage.py``).
* No leakage by construction — the simulator generates race state forward
  in time from the grid.  All inputs (grid, weather forecast, circuit
  characteristics, race-pace artefacts) are prior-only.
* Single seeded RNG.  We never reseed mid-sim.

Future extensions
-----------------
* SC duration distribution from prior races (currently fixed 3 laps).
* Retirement-lap hazard from real data (currently uniform over the race).
* Team-correlated performance shock (currently per-driver iid).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from models.race_pace import (
    COMPOUND_CODES,
    FEATURE_COLUMNS,
    LEADER_GAP_SENTINEL_S,
    predict_lap_times,
)

LOGGER = logging.getLogger(__name__)

# Default seed — mandated by project convention (see models/calibration.py).
DEFAULT_SEED: int = 42
DEFAULT_N_SAMPLES: int = 2000

# Per-lap noise default.  In FastF1 data the lap-to-lap std for a driver on
# stable conditions is roughly 0.10-0.25s.  0.15s is a reasonable mid-point
# that the caller can override.  This is *iid* per lap, so it only contributes
# ~sigma·sqrt(N_laps) to finishing time — small next to the multi-second pace
# gaps.  The reshuffling lever is DEFAULT_FORM_SHOCK_S below.
DEFAULT_LAP_NOISE_S: float = 0.15

# Per-sample per-driver car-performance shock (s/lap), held constant across
# the race.  Because it is fully correlated across laps it contributes
# ~sigma·N_laps to finishing time — comparable to real pace gaps — so it is
# what actually mixes the finishing order.  0.16 s/lap sits inside the
# real race-to-race pace-variation band (~0.15-0.25 s/lap) and, on a typical
# ~55-lap race, keeps a dominant car near a 35-55% favourite rather than a
# 95%+ lock.  Tuned against the completed-2026 rounds vs the published
# Plackett-Luce baseline (see tests/test_race_simulator_sanity.py).
DEFAULT_FORM_SHOCK_S: float = 0.16

# Per-driver base retirement probability when the caller supplies no
# per-driver override.  ~0.13 keeps mean retirements at ~3/race for a
# 22-car field, matching the modern-era DNF base rate used in models/dnf.py.
DEFAULT_FIELD_DNF_RATE: float = 0.13

# Dirichlet / base-rate smoothing pseudo-count applied at aggregation.  A
# weak (alpha=1 pseudo-sample, spread across the market base rate) prior:
# it lifts every probability off exactly 0.0 / 1.0 without materially moving
# well-sampled estimates, and — crucially — preserves the sum invariants
# (sum p_win == 1, sum p_podium == 3, …) because the mass added per market
# equals the market's slot count K.
SMOOTHING_ALPHA: float = 1.0

# Pit-stop logistics.  Window is the +/- range around the strategy-target lap
# at which the driver actually pits — adds realism without over-engineering.
PIT_WINDOW_LAPS: int = 2
# Compound rotation when pitting.  Soft → Medium → Hard mirrors the typical
# 2-stop pattern; circuit-specific overrides land in v2.
COMPOUND_ROTATION: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD")
# Wet-condition threshold.  When rain_intensity exceeds this, the simulator
# forces every driver onto INTERMEDIATE compounds from lap 1.
WET_THRESHOLD: float = 0.5


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GridEntry:
    """One driver on the starting grid."""

    driver: str
    team: str
    grid_position: int


@dataclass(frozen=True)
class RaceContext:
    """Static parameters of the race the simulator needs.

    Populated by the caller from CIRCUIT_CHARACTERISTICS and the live
    weather forecast (A-P1.4).  Kept dataclass-frozen so the simulator can't
    accidentally mutate it across MC samples.
    """

    season: int
    round_num: int
    circuit_key: str
    total_laps: int
    sc_likelihood: float          # 0..1 — P(at least one SC during race)
    tyre_deg_factor: float        # added per lap of tyre age, s/lap
    pit_loss_s: float
    expected_stops: int           # 1 or 2 (per circuit)
    base_lap_s: float             # representative lap time (quali-ish)
    air_temp_c: float = 25.0
    track_temp_c: float = 35.0
    rain_intensity: float = 0.0
    lap_noise_s: float = DEFAULT_LAP_NOISE_S
    # Race-day chaos knobs (A-P1.1 DNF + variance fix).
    form_shock_s: float = DEFAULT_FORM_SHOCK_S
    field_dnf_rate: float = DEFAULT_FIELD_DNF_RATE


@dataclass(frozen=True)
class DriverInitial:
    """Per-driver pre-race inputs.

    The simulator does NOT learn driver identity — encoders embed it.  This
    struct lets callers pass driver-specific overrides (starting tyre from
    strategy data, pace offset from the quali-time model, a per-driver
    retirement probability from the reliability model, etc.).
    """

    base_pace_offset_s: float = 0.0   # negative = faster than the field mean
    starting_tyre: str = "MEDIUM"
    p_dnf: float | None = None        # None → RaceContext.field_dnf_rate


@dataclass
class SimulationOutput:
    """Aggregate output of ``simulate_race``.

    Win probabilities sum to 1.0 and podium probabilities sum to 3.0 (modulo
    the base-rate smoothing, which is sum-preserving).  No probability is ever
    exactly 0.0 or 1.0."""

    drivers: tuple[str, ...]
    p_win: dict[str, float]
    p_podium: dict[str, float]
    p_top6: dict[str, float]
    p_top10: dict[str, float]
    mean_finish_position: dict[str, float]
    p_dnf: dict[str, float] = field(default_factory=dict)
    finish_position_distribution: dict[str, list[int]] = field(default_factory=dict)
    n_samples: int = 0
    n_laps: int = 0


# --------------------------------------------------------------------------- #
# Internal per-sample state
# --------------------------------------------------------------------------- #


class _RaceState:
    """Mutable race state for a single MC sample.

    Kept as a class (not a dataclass) so column-wise numpy mutations are
    cheap.  All arrays are indexed by ``driver_idx`` matching the order of
    the ``grid`` list passed into ``simulate_race``.
    """

    def __init__(
        self,
        grid: list[GridEntry],
        context: RaceContext,
        initials: dict[str, DriverInitial],
        encoders: dict[str, dict[str, int]],
        rng: np.random.Generator,
    ) -> None:
        n = len(grid)
        self.n = n
        self.grid = grid
        self.cum_time = np.zeros(n)
        # Track positions: start = grid positions (1-indexed); will update each lap.
        self.position = np.array([entry.grid_position for entry in grid], dtype=int)
        self.tyre_age = np.zeros(n, dtype=int)
        # Compound code (matches race_pace.COMPOUND_CODES values)
        starting_compounds = self._initial_compounds(grid, initials, context)
        self.compound_code = np.array(
            [COMPOUND_CODES.get(c, COMPOUND_CODES["UNKNOWN"]) for c in starting_compounds],
            dtype=int,
        )
        self.starting_compound_name = list(starting_compounds)
        self.n_stops = np.zeros(n, dtype=int)
        self.gap_ahead = np.full(n, LEADER_GAP_SENTINEL_S)
        self.gap_behind = np.full(n, LEADER_GAP_SENTINEL_S)
        self.base_pace_offset = np.array(
            [initials.get(g.driver, DriverInitial()).base_pace_offset_s for g in grid]
        )
        # Per-driver retirement probability (Bernoulli param per MC sample).
        self.p_dnf = np.array(
            [_resolve_p_dnf(initials.get(g.driver), context.field_dnf_rate) for g in grid]
        )
        # Pre-compute static feature columns once so the per-lap builder only
        # touches the lap-varying entries.
        drivers_enc = encoders.get("driver", {})
        teams_enc = encoders.get("team", {})
        self.driver_ids = np.array(
            [drivers_enc.get(g.driver, -1) for g in grid], dtype=float
        )
        self.team_ids = np.array(
            [teams_enc.get(g.team, -1) for g in grid], dtype=float
        )
        self.circuit_id = float(encoders.get("circuit", {}).get(context.circuit_key, -1))
        # Pre-compute the planned pit laps for each driver (per-sample noise so
        # MC samples differ in strategy timing slightly).
        self.pit_plan = _plan_pit_laps(
            n_drivers=n,
            total_laps=context.total_laps,
            expected_stops=context.expected_stops,
            rng=rng,
        )
        # SC laps drawn once per sample from a Poisson process keyed on the
        # circuit's safety_car_likelihood.  Conservative: cap at 1 event per sample.
        self.sc_laps: set[int] = _sample_sc_laps(
            context.sc_likelihood, context.total_laps, rng
        )

    @staticmethod
    def _initial_compounds(
        grid: list[GridEntry],
        initials: dict[str, DriverInitial],
        context: RaceContext,
    ) -> list[str]:
        if context.rain_intensity > WET_THRESHOLD:
            return ["INTERMEDIATE"] * len(grid)
        return [initials.get(g.driver, DriverInitial()).starting_tyre for g in grid]


def _resolve_p_dnf(initial: DriverInitial | None, field_rate: float) -> float:
    """Per-driver retirement probability, clipped to a plausible band."""
    p = field_rate if initial is None or initial.p_dnf is None else initial.p_dnf
    return float(min(0.6, max(0.005, p)))


def _plan_pit_laps(
    n_drivers: int,
    total_laps: int,
    expected_stops: int,
    rng: np.random.Generator,
) -> list[list[int]]:
    """Pick pit-stop laps per driver with circuit-driven defaults + per-sample noise.

    1-stop: pit near halfway.
    2-stop: pit near 1/3 and 2/3.
    Per driver, add a small noise window so MC samples produce distinct
    strategy timings.
    """
    stops = max(1, min(expected_stops, 2))
    if stops == 1:
        base_laps = [total_laps // 2]
    else:
        base_laps = [total_laps // 3, (2 * total_laps) // 3]
    plans: list[list[int]] = []
    for _ in range(n_drivers):
        plan = []
        for base in base_laps:
            jitter = int(rng.integers(-PIT_WINDOW_LAPS, PIT_WINDOW_LAPS + 1))
            plan.append(max(2, min(total_laps - 1, base + jitter)))
        plans.append(sorted(plan))
    return plans


def _sample_sc_laps(
    sc_likelihood: float,
    total_laps: int,
    rng: np.random.Generator,
) -> set[int]:
    """Decide which laps the safety car is on the track for this sample.

    Simple two-stage process: with probability ``sc_likelihood`` the race
    has at least one SC, in which case we draw the trigger lap uniformly
    and freeze 3 laps of SC activity.  No multi-SC modelling in v1.
    """
    if sc_likelihood <= 0:
        return set()
    if rng.uniform() >= sc_likelihood:
        return set()
    # Place the SC trigger uniformly inside laps 5..total_laps-3 so it's
    # neither lap-1 (where it'd compress the pack instantly) nor the
    # last laps (where the race-pace effect is minimal).
    earliest = min(5, max(1, total_laps // 6))
    latest = max(earliest + 1, total_laps - 3)
    trigger = int(rng.integers(earliest, latest + 1))
    return set(range(trigger, min(trigger + 3, total_laps) + 1))


def _sample_retirements(
    p_dnf: np.ndarray,
    total_laps: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw per-driver retirement for one MC sample.

    Returns ``(retire_lap, retired_mask)`` where ``retire_lap[i]`` is the lap
    on which driver ``i`` retires (they complete laps ``1..retire_lap-1``);
    finishers get ``total_laps + 1``.  Retirement laps are drawn uniformly
    over the race distance — a deliberately simple hazard for v1.
    """
    n = p_dnf.shape[0]
    retired_mask = rng.random(n) < p_dnf
    retire_lap = np.full(n, total_laps + 1, dtype=int)
    n_ret = int(retired_mask.sum())
    if n_ret:
        retire_lap[retired_mask] = rng.integers(1, total_laps + 1, size=n_ret)
    return retire_lap, retired_mask


# --------------------------------------------------------------------------- #
# Per-lap feature builder
# --------------------------------------------------------------------------- #


def _build_lap_features(
    state: _RaceState,
    lap_number: int,
    context: RaceContext,
    sc_active: bool,
    vsc_active: bool,
    yellow_active: bool,
) -> pd.DataFrame:
    """One DataFrame row per driver for this lap, in FEATURE_COLUMNS order.

    Built column-wise from pre-computed static arrays (driver/team/circuit
    ids, temps) so the hot loop never materialises 22 python dicts per lap.
    """
    n = state.n
    lap_progress = lap_number / context.total_laps if context.total_laps else 0.0
    data = {
        "driver_id": state.driver_ids,
        "team_id": state.team_ids,
        "circuit_id": np.full(n, state.circuit_id),
        "lap_number": np.full(n, float(lap_number)),
        "lap_progress": np.full(n, float(lap_progress)),
        "track_position": state.position.astype(float),
        "tyre_compound_code": state.compound_code.astype(float),
        "tyre_age_laps": state.tyre_age.astype(float),
        "gap_to_car_ahead_s": state.gap_ahead,
        "gap_to_car_behind_s": state.gap_behind,
        "sc_active": np.full(n, float(sc_active)),
        "vsc_active": np.full(n, float(vsc_active)),
        "yellow_active": np.full(n, float(yellow_active)),
        "air_temp_c": np.full(n, float(context.air_temp_c)),
        "track_temp_c": np.full(n, float(context.track_temp_c)),
        "rain_intensity": np.full(n, float(context.rain_intensity)),
    }
    return pd.DataFrame(data, columns=list(FEATURE_COLUMNS))


# --------------------------------------------------------------------------- #
# Per-sample inner loop
# --------------------------------------------------------------------------- #


def _simulate_one_sample(
    grid: list[GridEntry],
    artifacts: dict,
    encoders: dict[str, dict[str, int]],
    context: RaceContext,
    initials: dict[str, DriverInitial],
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Run one MC sample.  Returns ``(final_positions, retired_mask)`` — the
    length-N 1-indexed finishing positions and a boolean retirement mask, both
    driver-indexed in the same order as ``grid``.

    The race-pace model gives us a *predicted* lap time; on top of that we
    add:
      - per-driver base_pace_offset (quali signal carried forward)
      - a per-sample per-driver car-performance shock (constant across laps)
      - tyre-degradation linear term (deg_factor × tyre_age)
      - pit-loss when a driver pits this lap
      - SC normalisation (compress the pack toward the leader's lap time)
      - lap-to-lap noise

    Drivers may retire: a retired car stops accumulating time at its sampled
    retirement lap and is classified behind every finisher.
    """
    state = _RaceState(grid, context, initials, encoders, rng)
    n = state.n
    total_laps = context.total_laps

    # Per-sample per-driver car-performance shock (held constant across laps).
    if context.form_shock_s > 0:
        form_shock = rng.normal(0.0, context.form_shock_s, size=n)
    else:
        form_shock = np.zeros(n)

    # Per-sample retirements.
    retire_lap, retired_mask = _sample_retirements(state.p_dnf, total_laps, rng)
    laps_run = np.zeros(n, dtype=int)

    for lap in range(1, total_laps + 1):
        # A car is running this lap iff it hasn't retired yet (retires at the
        # start of ``retire_lap``, so it completes laps 1..retire_lap-1).
        active = retire_lap > lap
        sc_active = lap in state.sc_laps
        feature_df = _build_lap_features(
            state=state,
            lap_number=lap,
            context=context,
            sc_active=sc_active,
            vsc_active=False,
            yellow_active=False,
        )
        predicted = predict_lap_times(artifacts, feature_df)
        # Per-driver base-pace offset (quali signal) + per-sample form shock.
        predicted = predicted + state.base_pace_offset + form_shock
        # Tyre degradation: linear in tyre age (cleared on pit stops).
        predicted = predicted + context.tyre_deg_factor * state.tyre_age
        # Per-lap noise.
        noise = rng.normal(0.0, context.lap_noise_s, size=n)
        lap_times = predicted + noise

        # SC compresses lap times — every car runs roughly the same time.
        if sc_active:
            sc_lap_time = float(np.median(lap_times)) + 8.0  # ~8s slower than racing
            lap_times = np.full_like(lap_times, sc_lap_time)

        # Pit-stop bookkeeping for any driver pitting *this* lap (skip retired).
        for i in range(n):
            if active[i] and lap in state.pit_plan[i]:
                lap_times[i] += context.pit_loss_s
                state.tyre_age[i] = 0
                cur_idx = COMPOUND_ROTATION.index(state.starting_compound_name[i]) \
                    if state.starting_compound_name[i] in COMPOUND_ROTATION else 0
                next_name = COMPOUND_ROTATION[(cur_idx + 1) % len(COMPOUND_ROTATION)]
                state.starting_compound_name[i] = next_name
                state.compound_code[i] = COMPOUND_CODES.get(next_name, COMPOUND_CODES["UNKNOWN"])
                state.n_stops[i] += 1

        # Advance race time + tyre age only for cars still running.
        state.cum_time[active] += lap_times[active]
        laps_run[active] += 1
        state.tyre_age[active] += 1

        # Recompute positions + gaps.  Primary key: laps completed (more =
        # ahead, so retired cars sink); secondary: cumulative time.
        _recompute_positions_and_gaps(state, laps_run)

    # Final classification: finishers first (by time), then retired cars by
    # laps completed then time.  1-indexed, driver-indexed in grid order.
    order = np.lexsort((state.cum_time, -laps_run))
    final_positions = np.empty(n, dtype=int)
    final_positions[order] = np.arange(1, n + 1)
    return final_positions, retired_mask


def _recompute_positions_and_gaps(state: _RaceState, laps_run: np.ndarray) -> None:
    """Vectorised running-order + inter-car gap update."""
    n = state.n
    order = np.lexsort((state.cum_time, -laps_run))  # leader first
    state.position[order] = np.arange(1, n + 1)
    sorted_ct = state.cum_time[order]
    diffs = np.maximum(0.0, np.diff(sorted_ct)) if n > 1 else np.array([])
    gap_ahead_sorted = np.full(n, LEADER_GAP_SENTINEL_S)
    gap_behind_sorted = np.full(n, LEADER_GAP_SENTINEL_S)
    if n > 1:
        gap_ahead_sorted[1:] = diffs
        gap_behind_sorted[:-1] = diffs
    state.gap_ahead[order] = gap_ahead_sorted
    state.gap_behind[order] = gap_behind_sorted


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def _smooth_market(counts: np.ndarray, n_samples: int, slots: int, n_drivers: int) -> np.ndarray:
    """Dirichlet / base-rate smoothing that preserves the market sum.

    ``p_i = (count_i + alpha * slots / n_drivers) / (n_samples + alpha)``.

    Summed over drivers this gives exactly ``slots`` (1 for win, 3 for
    podium, …) because the per-driver pseudo-mass totals ``alpha * slots``.
    Every probability lands strictly inside (0, 1) whenever ``slots <
    n_drivers`` (and equals the correct value when ``slots == n_drivers``).
    """
    base = SMOOTHING_ALPHA * slots / n_drivers
    return (counts + base) / (n_samples + SMOOTHING_ALPHA)


def simulate_race(
    grid: Iterable[GridEntry],
    artifacts: dict,
    encoders: dict[str, dict[str, int]],
    context: RaceContext,
    initials: dict[str, DriverInitial] | None = None,
    n_samples: int = DEFAULT_N_SAMPLES,
    seed: int = DEFAULT_SEED,
) -> SimulationOutput:
    """Run the full MC simulator and return market probabilities.

    Parameters
    ----------
    grid
        Starting grid order.  ``grid_position`` is read from each entry.
    artifacts
        Trained race-pace ensemble from
        ``models/race_pace.train_race_pace_model``.
    encoders
        Label-encoder dict from the same training call.  Used to embed
        driver / team / circuit ids in the per-lap feature rows.
    context
        Static race parameters (laps, circuit characteristics, weather
        forecast, plus the ``form_shock_s`` / ``field_dnf_rate`` chaos knobs).
    initials
        Per-driver overrides (starting tyre, base pace offset, ``p_dnf``).
        Drivers absent from this map get defaults (``MEDIUM`` tyre, zero
        offset, ``field_dnf_rate`` retirement probability).
    n_samples
        Monte Carlo sample count.  Default 2000 — empirical std-err on
        a p≈0.3 estimate is ~1%, fast enough on CPU.
    seed
        RNG seed.  Default 42 per project convention; never reseed
        mid-sim.

    Returns
    -------
    ``SimulationOutput`` with per-driver win/podium/top6/top10 probabilities
    (base-rate smoothed so none is exactly 0.0 or 1.0), the realised DNF
    frequency, a per-driver finishing-position list (length ``n_samples``
    each), and the mean finishing position.
    """
    grid_list = list(grid)
    if not grid_list:
        raise ValueError("simulate_race: grid is empty")
    if n_samples < 1:
        raise ValueError(f"simulate_race: n_samples must be >= 1, got {n_samples}")
    if context.total_laps < 1:
        raise ValueError(
            f"simulate_race: total_laps must be >= 1, got {context.total_laps}"
        )

    drivers = tuple(g.driver for g in grid_list)
    initials = initials or {}
    rng = np.random.default_rng(seed)
    n = len(grid_list)
    finish_records = np.zeros((n_samples, n), dtype=int)
    dnf_counts = np.zeros(n, dtype=float)

    for s in range(n_samples):
        positions, retired = _simulate_one_sample(
            grid=grid_list,
            artifacts=artifacts,
            encoders=encoders,
            context=context,
            initials=initials,
            rng=rng,
        )
        finish_records[s] = positions
        dnf_counts += retired

    # Aggregate: per-driver position counts across samples, then base-rate
    # smooth each market so nothing pins to 0.0 / 1.0.
    p_win: dict[str, float] = {}
    p_podium: dict[str, float] = {}
    p_top6: dict[str, float] = {}
    p_top10: dict[str, float] = {}
    p_dnf: dict[str, float] = {}
    mean_finish: dict[str, float] = {}
    position_dist: dict[str, list[int]] = {}

    win_counts = (finish_records == 1).sum(axis=0).astype(float)
    podium_counts = (finish_records <= 3).sum(axis=0).astype(float)
    top6_counts = (finish_records <= 6).sum(axis=0).astype(float)
    top10_counts = (finish_records <= 10).sum(axis=0).astype(float)

    win_p = _smooth_market(win_counts, n_samples, 1, n)
    podium_p = _smooth_market(podium_counts, n_samples, min(3, n), n)
    top6_p = _smooth_market(top6_counts, n_samples, min(6, n), n)
    top10_p = _smooth_market(top10_counts, n_samples, min(10, n), n)

    for i, drv in enumerate(drivers):
        finishes = finish_records[:, i]
        p_win[drv] = float(win_p[i])
        p_podium[drv] = float(podium_p[i])
        p_top6[drv] = float(top6_p[i])
        p_top10[drv] = float(top10_p[i])
        mean_finish[drv] = float(np.mean(finishes))
        p_dnf[drv] = float(dnf_counts[i] / n_samples)
        position_dist[drv] = finishes.tolist()

    return SimulationOutput(
        drivers=drivers,
        p_win=p_win,
        p_podium=p_podium,
        p_top6=p_top6,
        p_top10=p_top10,
        mean_finish_position=mean_finish,
        p_dnf=p_dnf,
        finish_position_distribution=position_dist,
        n_samples=n_samples,
        n_laps=context.total_laps,
    )


# --------------------------------------------------------------------------- #
# Helpers — useful for Step 3 integration
# --------------------------------------------------------------------------- #


def race_context_from_circuit(
    season: int,
    round_num: int,
    circuit_key: str,
    total_laps: int,
    circuit_characteristics: dict,
    weather: dict | None = None,
) -> RaceContext:
    """Build a ``RaceContext`` from
    [f1_prediction_utils.py::CIRCUIT_CHARACTERISTICS][circuit_key] + weather.

    Step 3 calls this from inside ``apply_race_postprocessing``.  Kept here
    (rather than in race_pace) so the simulator owns its own input
    construction and ``race_pace.py`` stays purely about per-lap prediction.
    """
    char = circuit_characteristics.get(circuit_key, {})
    weather = weather or {}
    # Accept either the race-simulator-native key shape (air_temp_c,
    # rain_intensity) or the weather_api.py shape (temperature_c,
    # rain_probability).  Track-temp isn't reported by the API yet; fall
    # back to a 10°C-above-air heuristic (matches typical dry-track delta).
    air_temp = float(weather.get("air_temp_c", weather.get("temperature_c", 25.0)))
    track_temp = float(weather.get("track_temp_c", air_temp + 10.0))
    rain = float(
        weather.get(
            "rain_intensity",
            weather.get("rain_probability", weather.get("rain", 0.0)),
        )
    )
    return RaceContext(
        season=season,
        round_num=round_num,
        circuit_key=circuit_key,
        total_laps=total_laps,
        sc_likelihood=float(char.get("safety_car_likelihood", 0.4)),
        tyre_deg_factor=float(char.get("tyre_deg", 0.05)) * 0.05,
        pit_loss_s=float(char.get("pit_loss_s", 22.5)),
        expected_stops=int(char.get("expected_stops", 2)),
        base_lap_s=float(char.get("base_quali_s", 85.0)),
        air_temp_c=air_temp,
        track_temp_c=track_temp,
        rain_intensity=rain,
        # Street/high-SC circuits retire more cars; nudge the field DNF rate up
        # a touch with safety-car likelihood but keep it inside a sane band.
        field_dnf_rate=float(
            min(
                0.22,
                max(
                    0.08,
                    DEFAULT_FIELD_DNF_RATE
                    * (0.85 + 0.5 * float(char.get("safety_car_likelihood", 0.4))),
                ),
            )
        ),
    )
