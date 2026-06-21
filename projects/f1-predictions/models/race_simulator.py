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
  3. Add lap-to-lap noise (sampled from a circuit-specific stddev).
  4. Apply pit-stop logic for any driver whose strategy says "pit this
     lap" — adds pit-loss seconds, resets tyre age, rotates compound.
  5. Update cumulative race time and recompute running positions/gaps.

After ``n_samples`` simulations, aggregate per-driver finishing-position
histograms → P(win), P(podium), P(top6), P(top10).

Constraints honoured
--------------------
* Pure-additive.  No existing file is touched in this step; Step 3 of the
  A-P1.1 push wires it into ``apply_race_postprocessing``.
* The simulator is **deterministic given a seed**.  We accept a
  ``np.random.Generator`` from the caller; if absent, default seed=42 per
  project convention (matches ``models/calibration.py`` and ``leakage.py``).
* No leakage by construction — the simulator generates race state forward
  in time from the grid.  All inputs (grid, weather forecast, circuit
  characteristics, race-pace artefacts) are prior-only.
* Single seeded RNG.  We never reseed mid-sim.

Future extensions (not in v1)
-----------------------------
* SC duration distribution from prior races (currently fixed 3 laps).
* Driver-specific pit-stop variance from team history.
* Tyre-compound choice per driver from prior-round strategy data.
* Wet-tyre crossover (currently fixed: if rain_intensity > 0.5, force INTERMEDIATE).
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
# that the caller can override.
DEFAULT_LAP_NOISE_S: float = 0.15

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


@dataclass(frozen=True)
class DriverInitial:
    """Per-driver pre-race inputs.

    The simulator does NOT learn driver identity — encoders embed it.  This
    struct lets callers pass driver-specific overrides (starting tyre from
    strategy data, pace offset from the quali-time model, etc.).
    """

    base_pace_offset_s: float = 0.0   # negative = faster than the field mean
    starting_tyre: str = "MEDIUM"


@dataclass
class SimulationOutput:
    """Aggregate output of ``simulate_race``.  All probabilities sum to N×p,
    where N is the number of drivers; e.g. ``sum(p_win) == 1.0`` modulo
    Monte Carlo noise."""

    drivers: tuple[str, ...]
    p_win: dict[str, float]
    p_podium: dict[str, float]
    p_top6: dict[str, float]
    p_top10: dict[str, float]
    mean_finish_position: dict[str, float]
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


# --------------------------------------------------------------------------- #
# Per-lap feature builder
# --------------------------------------------------------------------------- #


def _build_lap_features(
    state: _RaceState,
    lap_number: int,
    context: RaceContext,
    encoders: dict[str, dict[str, int]],
    sc_active: bool,
    vsc_active: bool,
    yellow_active: bool,
) -> pd.DataFrame:
    """One DataFrame row per driver for this lap, in FEATURE_COLUMNS order."""
    rows = []
    drivers_enc = encoders.get("driver", {})
    teams_enc = encoders.get("team", {})
    circuit_id = encoders.get("circuit", {}).get(context.circuit_key, -1)
    lap_progress = lap_number / context.total_laps if context.total_laps else 0.0
    for i, entry in enumerate(state.grid):
        rows.append(
            {
                "driver_id": drivers_enc.get(entry.driver, -1),
                "team_id": teams_enc.get(entry.team, -1),
                "circuit_id": circuit_id,
                "lap_number": lap_number,
                "lap_progress": lap_progress,
                "track_position": int(state.position[i]),
                "tyre_compound_code": int(state.compound_code[i]),
                "tyre_age_laps": int(state.tyre_age[i]),
                "gap_to_car_ahead_s": float(state.gap_ahead[i]),
                "gap_to_car_behind_s": float(state.gap_behind[i]),
                "sc_active": int(sc_active),
                "vsc_active": int(vsc_active),
                "yellow_active": int(yellow_active),
                "air_temp_c": float(context.air_temp_c),
                "track_temp_c": float(context.track_temp_c),
                "rain_intensity": float(context.rain_intensity),
            }
        )
    return pd.DataFrame(rows, columns=list(FEATURE_COLUMNS))


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
) -> np.ndarray:
    """Run one MC sample.  Returns a length-N array of final positions
    (1-indexed), driver-indexed in the same order as ``grid``.

    The race-pace model gives us a *predicted* lap time; on top of that we
    add:
      - per-driver base_pace_offset (e.g. -0.4s for the fastest driver) to
        bake in the quali signal the upstream pipeline already extracted
      - tyre-degradation linear term (deg_factor × tyre_age)
      - pit-loss when a driver pits this lap
      - SC normalisation (compress the pack toward the leader's lap time
        when SC is active)
      - lap-to-lap noise
    """
    state = _RaceState(grid, context, initials, rng)
    for lap in range(1, context.total_laps + 1):
        sc_active = lap in state.sc_laps
        feature_df = _build_lap_features(
            state=state,
            lap_number=lap,
            context=context,
            encoders=encoders,
            sc_active=sc_active,
            vsc_active=False,
            yellow_active=False,
        )
        predicted = predict_lap_times(artifacts, feature_df)
        # Per-driver base-pace offset (quali signal carried forward).
        predicted = predicted + state.base_pace_offset
        # Tyre degradation: linear in tyre age (cleared on pit stops).
        predicted = predicted + context.tyre_deg_factor * state.tyre_age
        # Per-lap noise.
        noise = rng.normal(0.0, context.lap_noise_s, size=state.n)
        lap_times = predicted + noise

        # SC compresses lap times — every car runs roughly the same time.
        if sc_active:
            sc_lap_time = float(np.median(lap_times)) + 8.0  # ~8s slower than racing
            lap_times = np.full_like(lap_times, sc_lap_time)

        # Pit-stop bookkeeping for any driver pitting *this* lap.
        for i in range(state.n):
            if lap in state.pit_plan[i]:
                lap_times[i] += context.pit_loss_s
                state.tyre_age[i] = 0
                # Compound rotation: advance one step in the rotation list,
                # wrapping at the end so 2-stop strategies don't crash.
                cur_idx = COMPOUND_ROTATION.index(state.starting_compound_name[i]) \
                    if state.starting_compound_name[i] in COMPOUND_ROTATION else 0
                next_name = COMPOUND_ROTATION[(cur_idx + 1) % len(COMPOUND_ROTATION)]
                state.starting_compound_name[i] = next_name
                state.compound_code[i] = COMPOUND_CODES.get(next_name, COMPOUND_CODES["UNKNOWN"])
                state.n_stops[i] += 1

        # Advance race time.
        state.cum_time = state.cum_time + lap_times
        state.tyre_age = state.tyre_age + 1

        # Recompute positions from cumulative time (1-indexed).
        order = np.argsort(state.cum_time)
        ranks = np.empty(state.n, dtype=int)
        ranks[order] = np.arange(1, state.n + 1)
        state.position = ranks

        # Recompute gaps.
        for i in range(state.n):
            pos = int(state.position[i])
            ahead_idx = next(
                (j for j in range(state.n) if int(state.position[j]) == pos - 1),
                None,
            )
            behind_idx = next(
                (j for j in range(state.n) if int(state.position[j]) == pos + 1),
                None,
            )
            state.gap_ahead[i] = (
                max(0.0, float(state.cum_time[i] - state.cum_time[ahead_idx]))
                if ahead_idx is not None
                else LEADER_GAP_SENTINEL_S
            )
            state.gap_behind[i] = (
                max(0.0, float(state.cum_time[behind_idx] - state.cum_time[i]))
                if behind_idx is not None
                else LEADER_GAP_SENTINEL_S
            )

    # Final classification: 1-indexed positions driver-indexed in grid order.
    final_order = np.argsort(state.cum_time)
    final_positions = np.empty(state.n, dtype=int)
    final_positions[final_order] = np.arange(1, state.n + 1)
    return final_positions


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


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
        forecast).
    initials
        Per-driver overrides (starting tyre, base pace offset).  Drivers
        absent from this map get defaults (``MEDIUM`` tyre, zero offset).
    n_samples
        Monte Carlo sample count.  Default 2000 — empirical std-err on
        a p≈0.3 estimate is ~1%, fast enough on CPU.
    seed
        RNG seed.  Default 42 per project convention; never reseed
        mid-sim.

    Returns
    -------
    ``SimulationOutput`` with per-driver win/podium/top6/top10 probabilities,
    a per-driver finishing-position list (length ``n_samples`` each), and
    the mean finishing position.
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

    for s in range(n_samples):
        finish_records[s] = _simulate_one_sample(
            grid=grid_list,
            artifacts=artifacts,
            encoders=encoders,
            context=context,
            initials=initials,
            rng=rng,
        )

    # Aggregate: per-driver position counts across samples.
    p_win: dict[str, float] = {}
    p_podium: dict[str, float] = {}
    p_top6: dict[str, float] = {}
    p_top10: dict[str, float] = {}
    mean_finish: dict[str, float] = {}
    position_dist: dict[str, list[int]] = {}
    for i, drv in enumerate(drivers):
        finishes = finish_records[:, i]
        p_win[drv] = float(np.mean(finishes == 1))
        p_podium[drv] = float(np.mean(finishes <= 3))
        p_top6[drv] = float(np.mean(finishes <= 6))
        p_top10[drv] = float(np.mean(finishes <= 10))
        mean_finish[drv] = float(np.mean(finishes))
        position_dist[drv] = finishes.tolist()

    return SimulationOutput(
        drivers=drivers,
        p_win=p_win,
        p_podium=p_podium,
        p_top6=p_top6,
        p_top10=p_top10,
        mean_finish_position=mean_finish,
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
    )
