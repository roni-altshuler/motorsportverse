"""NASCAR playoff/elimination championship Monte Carlo simulator.

``motorsport_core.championship.project_championship`` simulates cumulative-points
title races; NASCAR's postseason (points resets, elimination cuts, win-and-advance,
a winner-take-all finale) cannot be expressed there. This module adds a
config-driven playoff engine on top of the *same* Plackett-Luce race sampler
(:func:`motorsport_core.calibration.sample_finishing_orders`), so per-race
finishing orders come from exactly one place in the ecosystem.

Two families of formats are expressible through :class:`PlayoffFormat`:

* the 2014-2025 elimination playoffs (16 drivers, Round of 16/12/8 cut to
  12/8/4, points resets 2000/3000/4000 + banked playoff points, a race win
  inside a round auto-advances, Championship 4 finale where the best finisher
  of the four takes the title — banked playoff points do NOT apply there);
* the 2026 "Chase" (announced by NASCAR in January 2026): pure points
  qualification for a 16-driver field, one 10-race round with NO eliminations,
  staggered seeding reset (2100 / 2075 / 2065, then -5 per seed down to 2000),
  no playoff points at all, most points after race 36 wins the title.

Modelling simplifications (documented, deliberate)
--------------------------------------------------
* **Stage results are sampled i.i.d. from the same driver strengths as the
  race finish.** Real stage results correlate with the final finishing order
  (track position carries over); treating them as independent Plackett-Luce
  draws slightly widens stage-point spread but keeps the sampler reusable and
  unbiased in expectation.
* Races are homogeneous: every remaining race uses the same strength vector
  (no track-type effects yet) and every race scores ``stages_per_race``
  stages (the Coca-Cola 600's extra stage is ignored).
* DNFs are not modelled explicitly — the Plackett-Luce tail already assigns
  weak-finish probability mass to everyone.
* Win-and-in qualification ignores the "top 30 in points + attempted every
  race" fine print; any race winner is playoff-eligible.
* The regular-season top-10 playoff-point bonus is awarded from the simulated
  final regular-season standings **only when at least one regular-season race
  remains to be simulated**. If you pass a season state with the regular
  season already complete, include the bonus in each driver's
  ``playoff_points`` yourself (in reality it has been awarded by then).
* Ties are broken deterministically: points, then wins, then a tiny
  strength-order epsilon (better-strength driver wins exact ties).

Determinism: the whole projection is a pure function of its inputs plus
``rng_seed``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

from motorsport_core.calibration import DEFAULT_TEMPERATURE, sample_finishing_orders

__all__ = [
    "PlayoffRound",
    "PlayoffFormat",
    "DriverState",
    "PlayoffPhaseState",
    "SeasonState",
    "PlayoffSimulation",
    "simulate_playoffs",
    "project_playoffs",
]

# Key-ordering weights for composite sort keys. All point totals in either
# format stay < 1e4 (a Championship 4 reset is 5000 + ~360 attainable), so
# these scales keep every tiebreak level from bleeding into the next while
# staying well inside float64 integer-exact range.
_AUTO_ADVANCE_BONUS = 1e7  # race-win auto-advance / "is a race winner" flag
_WINS_SCALE = 1e4          # wins dominate points in win-and-in qualification
_WINS_TIEBREAK = 1e-3      # wins break exact points ties (points are >= 1 apart)
_EPS_SCALE = 1e-6          # strength-order epsilon breaks any remaining tie


# --------------------------------------------------------------------------- #
# Format description
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PlayoffRound:
    """One postseason round.

    Parameters
    ----------
    key
        Machine identifier (``"round_of_12"``); result dict keys are built
        from the *next* round's key (surviving the Round of 16 = reaching the
        ``round_of_12``).
    n_races
        Races in the round.
    advancing
        How many drivers survive the cut at the end of the round; ``None``
        means no cut (final round — the champion is decided after it).
    base_points
        Points-reset base applied when the round starts; ``None`` carries the
        previous round's points forward (no reset).
    bank_playoff_points
        Whether each alive driver's banked playoff points are added on top of
        the reset. NASCAR 2017-2025: True for Round of 16/12/8, False for the
        Championship 4.
    seed_bonus
        Optional per-seed additive bonus applied at the reset (2026 Chase
        staggering: +100/+75/+65/... over the 2000 base). Seed order is the
        qualification order (round 0) or the pre-reset points order (later
        rounds).
    win_advances
        Whether a race win inside the round auto-advances an alive driver.
    winner_take_all
        Whether the title is decided by best finishing position among the
        alive drivers in the round's final race (Championship 4 semantics)
        instead of by accumulated points.
    """

    key: str
    name: str
    n_races: int
    advancing: int | None
    base_points: float | None
    bank_playoff_points: bool = True
    seed_bonus: tuple[float, ...] = ()
    win_advances: bool = True
    winner_take_all: bool = False


@dataclass(frozen=True)
class PlayoffFormat:
    """A complete NASCAR-style championship format.

    ``race_points`` / ``stage_points`` map 1-based finishing position to
    points; positions beyond the table earn the table's minimum (race) or 0
    (stage). ``qualification`` is ``"wins_first"`` (2014-2025 win-and-in:
    race winners fill the field first — most wins, then points — remainder on
    points) or ``"points"`` (2026 Chase: top-N on points, wins as tiebreak).
    """

    regular_season_races: int
    playoff_field_size: int
    rounds: tuple[PlayoffRound, ...]
    race_points: Mapping[int, float]
    stage_points: Mapping[int, float]
    stages_per_race: int = 2
    qualification: str = "wins_first"
    win_playoff_points: float = 0.0
    stage_win_playoff_points: float = 0.0
    regular_season_playoff_points: Mapping[int, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.rounds:
            raise ValueError("PlayoffFormat needs at least one round")
        if self.qualification not in ("wins_first", "points"):
            raise ValueError(f"unknown qualification rule {self.qualification!r}")
        prev = self.playoff_field_size
        for i, rnd in enumerate(self.rounds):
            if rnd.n_races < 1:
                raise ValueError(f"round {rnd.key!r} has no races")
            if rnd.advancing is None:
                if i != len(self.rounds) - 1:
                    raise ValueError(f"only the final round may have advancing=None ({rnd.key!r})")
            else:
                if not (0 < rnd.advancing < prev):
                    raise ValueError(
                        f"round {rnd.key!r}: advancing={rnd.advancing} must shrink the field ({prev})"
                    )
                prev = rnd.advancing
            if rnd.seed_bonus and len(rnd.seed_bonus) not in (0, self.playoff_field_size):
                raise ValueError(
                    f"round {rnd.key!r}: seed_bonus must have playoff_field_size entries"
                )

    @property
    def probability_keys(self) -> tuple[str, ...]:
        """Result-dict keys in monotone order (each implies the previous)."""
        keys = ["p_make_playoffs"]
        keys += [f"p_{rnd.key}" for rnd in self.rounds[1:]]
        keys.append("p_title")
        return tuple(keys)


# --------------------------------------------------------------------------- #
# Season state
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DriverState:
    """Accumulated season tallies for one driver, as of 'now'."""

    points: float = 0.0
    wins: int = 0
    stage_wins: int = 0
    playoff_points: float = 0.0


@dataclass(frozen=True)
class PlayoffPhaseState:
    """Where we are inside the postseason (omit if still in the regular season).

    ``round_points`` are the current standings points of the *alive* drivers,
    including the round's reset base and any banked playoff points already
    applied. ``round_wins`` lists alive drivers who have already won a race in
    the current round (auto-advance credit).
    """

    round_index: int
    races_completed_in_round: int
    alive: tuple[str, ...]
    round_points: Mapping[str, float]
    round_wins: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SeasonState:
    """Mid-season snapshot: per-driver tallies + optional playoff phase."""

    drivers: Mapping[str, DriverState] = field(default_factory=dict)
    playoff: PlayoffPhaseState | None = None


# --------------------------------------------------------------------------- #
# Simulation result
# --------------------------------------------------------------------------- #


@dataclass
class PlayoffSimulation:
    """Raw per-simulation outcomes (property tests introspect these)."""

    drivers: tuple[str, ...]
    playoff_format: PlayoffFormat
    n_sims: int
    #: reached[r] : (n_sims, n_drivers) bool — alive at the start of rounds[r].
    #: reached[0] is "made the playoffs".
    reached: list[np.ndarray]
    #: champion[s] : winning driver index in simulation s.
    champion: np.ndarray
    #: round_wins[r] : (n_sims, n_drivers) bool — won a race in rounds[r] while alive.
    round_wins: list[np.ndarray]

    def probabilities(self) -> dict[str, dict[str, float]]:
        """Per-driver monotone probability ladder (see PlayoffFormat.probability_keys)."""
        keys = self.playoff_format.probability_keys
        stage_means = [r.mean(axis=0) for r in self.reached]
        title = np.bincount(self.champion, minlength=len(self.drivers)) / self.n_sims
        out: dict[str, dict[str, float]] = {}
        for i, d in enumerate(self.drivers):
            probs = {keys[j]: float(stage_means[j][i]) for j in range(len(stage_means))}
            probs["p_title"] = float(title[i])
            out[d] = probs
        return out


# --------------------------------------------------------------------------- #
# Sampling helpers (thin wrappers over motorsport_core.calibration)
# --------------------------------------------------------------------------- #


def _sample_positions(
    strengths: Mapping[str, float],
    driver_index: Mapping[str, int],
    n_draws: int,
    temperature: float,
    seed: int,
) -> np.ndarray:
    """Sample ``n_draws`` full-field finishing orders; return a positions matrix.

    Reuses :func:`motorsport_core.calibration.sample_finishing_orders` (the
    shared Plackett-Luce Gumbel-max sampler) and converts each sampled order
    into ``pos[d, i]`` = 0-indexed finishing position of driver *i* in draw *d*.
    """
    n = len(strengths)
    if n_draws == 0:
        return np.zeros((0, n), dtype=np.int64)
    orders = sample_finishing_orders(
        strengths, n_samples=n_draws, temperature=temperature, seed=seed
    )
    rank = np.fromiter(
        (driver_index[c] for row in orders for c in row),
        dtype=np.int64,
        count=n_draws * n,
    ).reshape(n_draws, n)
    pos = np.empty_like(rank)
    pos[np.arange(n_draws)[:, None], rank] = np.arange(n)[None, :]
    return pos


def _points_vector(table: Mapping[int, float], n_drivers: int, beyond: float) -> np.ndarray:
    """Position-indexed points lookup (index 0 = winner)."""
    return np.array(
        [float(table.get(p, beyond)) for p in range(1, n_drivers + 1)], dtype=np.float64
    )


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #


def simulate_playoffs(
    strengths: Mapping[str, float],
    playoff_format: PlayoffFormat,
    completed_results: SeasonState | None = None,
    remaining_schedule: int | Sequence[object] = 0,
    n_sims: int = 2000,
    rng_seed: int = 42,
    *,
    temperature: float = DEFAULT_TEMPERATURE,
) -> PlayoffSimulation:
    """Monte Carlo the rest of a NASCAR-style season; return raw outcomes.

    Parameters
    ----------
    strengths
        driver -> score where **lower is better** (lap-time-like), matching the
        ``motorsport_core.calibration`` convention. Every driver in the map
        races in every remaining event (full-field sampling — non-playoff
        drivers occupy finishing positions and can win playoff races).
    playoff_format
        The championship format to simulate (see config.py for Cup presets).
    completed_results
        Season so far. ``None`` = fresh season. If ``.playoff`` is set the
        projection resumes inside the postseason.
    remaining_schedule
        Remaining *regular-season* races: an int count or a sequence of race
        labels (only its length is used — races are modelled homogeneously).
        Must be 0/empty when resuming inside the playoffs.
    n_sims, rng_seed, temperature
        Monte Carlo controls; results are deterministic for fixed inputs.
    """
    fmt = playoff_format
    drivers = list(strengths.keys())
    n = len(drivers)
    if n == 0:
        raise ValueError("strengths is empty")
    index = {d: i for i, d in enumerate(drivers)}
    state = completed_results or SeasonState()
    for d in state.drivers:
        if d not in index:
            raise ValueError(f"driver {d!r} in completed_results but not in strengths")

    n_reg = (
        int(remaining_schedule)
        if isinstance(remaining_schedule, int)
        else len(remaining_schedule)
    )
    if n_reg < 0 or n_reg > fmt.regular_season_races:
        raise ValueError(f"remaining regular-season races out of range: {n_reg}")
    if state.playoff is not None and n_reg != 0:
        raise ValueError("remaining_schedule must be empty when already in the playoffs")

    field_size = min(fmt.playoff_field_size, n)
    sim_idx = np.arange(n_sims)[:, None]
    seed_rng = np.random.default_rng(rng_seed)

    def next_seed() -> int:
        return int(seed_rng.integers(0, 2**31 - 1))

    # Deterministic tie-break epsilon: better-strength drivers win exact ties.
    strength_rank = np.argsort(np.argsort([float(strengths[d]) for d in drivers]))
    eps = (n - strength_rank).astype(np.float64) * _EPS_SCALE

    race_pts = _points_vector(fmt.race_points, n, beyond=min(fmt.race_points.values()))
    stage_pts = _points_vector(fmt.stage_points, n, beyond=0.0)
    use_stages = fmt.stages_per_race > 0 and bool(fmt.stage_points)

    # ---- per-driver base tallies, broadcast across sims -------------------- #
    def _tile(attr: str) -> np.ndarray:
        base = np.array(
            [float(getattr(state.drivers.get(d, DriverState()), attr)) for d in drivers]
        )
        return np.tile(base, (n_sims, 1))

    pts = _tile("points")
    wins = _tile("wins")
    bank = _tile("playoff_points")

    reached: list[np.ndarray] = []
    all_round_wins: list[np.ndarray] = []

    # ---- regular season + qualification ------------------------------------ #
    if state.playoff is None:
        if n_reg > 0:
            pos = _sample_positions(strengths, index, n_sims * n_reg, temperature, next_seed())
            pos = pos.reshape(n_sims, n_reg, n)
            pts += race_pts[pos].sum(axis=1)
            new_wins = (pos == 0).sum(axis=1)
            wins += new_wins
            bank += fmt.win_playoff_points * new_wins
            if use_stages:
                n_stage_draws = n_sims * n_reg * fmt.stages_per_race
                spos = _sample_positions(strengths, index, n_stage_draws, temperature, next_seed())
                spos = spos.reshape(n_sims, n_reg * fmt.stages_per_race, n)
                pts += stage_pts[spos].sum(axis=1)
                bank += fmt.stage_win_playoff_points * (spos == 0).sum(axis=1)
            # Regular-season top-10 playoff-point bonus from simulated final
            # standings (only when we simulated part of the regular season —
            # see module docstring for the already-complete convention).
            if fmt.regular_season_playoff_points:
                order = np.argsort(-(pts + wins * _WINS_TIEBREAK + eps), axis=1)
                for rank_pos, bonus in fmt.regular_season_playoff_points.items():
                    if 1 <= rank_pos <= n:
                        bank[sim_idx[:, 0], order[:, rank_pos - 1]] += float(bonus)

        if fmt.qualification == "wins_first":
            qual_key = (wins > 0) * _AUTO_ADVANCE_BONUS + wins * _WINS_SCALE + pts + eps
        else:
            qual_key = pts + wins * _WINS_TIEBREAK + eps
        seed_order = np.argsort(-qual_key, axis=1)[:, :field_size]
        alive = np.zeros((n_sims, n), dtype=bool)
        alive[sim_idx, seed_order] = True
        reached.append(alive.copy())

        start_round = 0
        races_done_in_round = 0
        rp = np.zeros((n_sims, n))
        resume_playoff = False
        carried_round_wins = np.zeros((n_sims, n), dtype=bool)
    else:
        ps = state.playoff
        if not (0 <= ps.round_index < len(fmt.rounds)):
            raise ValueError(f"playoff round_index out of range: {ps.round_index}")
        alive = np.zeros((n_sims, n), dtype=bool)
        for d in ps.alive:
            alive[:, index[d]] = True
        rp = np.full((n_sims, n), -np.inf)
        for d in ps.alive:
            rp[:, index[d]] = float(ps.round_points.get(d, 0.0))
        carried_round_wins = np.zeros((n_sims, n), dtype=bool)
        for d, w in ps.round_wins.items():
            if w:
                carried_round_wins[:, index[d]] = True
        # Stages already decided aren't reconstructed: currently-alive drivers
        # count as having reached them, eliminated drivers as not.
        for _ in range(ps.round_index + 1):
            reached.append(alive.copy())
        start_round = ps.round_index
        races_done_in_round = ps.races_completed_in_round
        seed_order = None
        # round_points from the caller already include the reset — never re-reset
        # the round we resume into.
        resume_playoff = True

    for _ in range(start_round):
        all_round_wins.append(np.zeros((n_sims, n), dtype=bool))

    # ---- playoff rounds ----------------------------------------------------- #
    final_race_pos: np.ndarray | None = None
    for r in range(start_round, len(fmt.rounds)):
        rnd = fmt.rounds[r]
        resuming_mid_round = resume_playoff and r == start_round
        if not resuming_mid_round:
            # Fresh round start: apply the points reset.
            if rnd.base_points is not None:
                new_rp = np.where(alive, float(rnd.base_points), -np.inf)
                if rnd.seed_bonus:
                    if seed_order is None or seed_order.shape[1] < field_size:
                        # Rank alive drivers by pre-reset points for seeding.
                        seed_key = np.where(alive, rp + eps, -np.inf)
                        seed_order = np.argsort(-seed_key, axis=1)[:, :field_size]
                    k = min(len(rnd.seed_bonus), seed_order.shape[1])
                    for j in range(k):
                        new_rp[sim_idx[:, 0], seed_order[:, j]] += float(rnd.seed_bonus[j])
                if rnd.bank_playoff_points:
                    new_rp = np.where(alive, new_rp + bank, -np.inf)
                rp = new_rp
            races_left = rnd.n_races
            round_wins = np.zeros((n_sims, n), dtype=bool)
        else:
            races_left = rnd.n_races - races_done_in_round
            if races_left < 0:
                raise ValueError("races_completed_in_round exceeds the round length")
            round_wins = carried_round_wins.copy()

        if races_left > 0:
            pos = _sample_positions(strengths, index, n_sims * races_left, temperature, next_seed())
            pos = pos.reshape(n_sims, races_left, n)
            rp = rp + race_pts[pos].sum(axis=1)
            race_winners = pos == 0  # (n_sims, races_left, n)
            round_wins |= (race_winners & alive[:, None, :]).any(axis=1)
            bank += fmt.win_playoff_points * (race_winners & alive[:, None, :]).sum(axis=1)
            if use_stages:
                n_stage_draws = n_sims * races_left * fmt.stages_per_race
                spos = _sample_positions(strengths, index, n_stage_draws, temperature, next_seed())
                spos = spos.reshape(n_sims, races_left * fmt.stages_per_race, n)
                rp = rp + stage_pts[spos].sum(axis=1)
                bank += fmt.stage_win_playoff_points * (
                    (spos == 0) & alive[:, None, :]
                ).sum(axis=1)
            if r == len(fmt.rounds) - 1:
                final_race_pos = pos[:, -1, :]

        all_round_wins.append(round_wins & alive)

        if rnd.advancing is not None:
            auto = (round_wins & alive) if rnd.win_advances else np.zeros_like(round_wins)
            cut_key = np.where(alive, auto * _AUTO_ADVANCE_BONUS + rp + eps, -np.inf)
            cut_order = np.argsort(-cut_key, axis=1)[:, : rnd.advancing]
            new_alive = np.zeros_like(alive)
            new_alive[sim_idx, cut_order] = True
            alive = new_alive & alive
            seed_order = cut_order
            reached.append(alive.copy())

    # ---- champion ------------------------------------------------------------ #
    last = fmt.rounds[-1]
    if last.winner_take_all and final_race_pos is not None:
        champ_key = np.where(alive, -final_race_pos.astype(np.float64), -np.inf)
    else:
        champ_key = np.where(alive, rp + eps, -np.inf)
    champion = np.argmax(champ_key, axis=1)

    return PlayoffSimulation(
        drivers=tuple(drivers),
        playoff_format=fmt,
        n_sims=n_sims,
        reached=reached,
        champion=champion,
        round_wins=all_round_wins,
    )


def project_playoffs(
    strengths: Mapping[str, float],
    playoff_format: PlayoffFormat,
    completed_results: SeasonState | None = None,
    remaining_schedule: int | Sequence[object] = 0,
    n_sims: int = 2000,
    rng_seed: int = 42,
    *,
    temperature: float = DEFAULT_TEMPERATURE,
) -> dict[str, dict[str, float]]:
    """Monte Carlo championship probabilities for a NASCAR-style format.

    Returns ``driver -> {p_make_playoffs, p_round_of_12, p_round_of_8,
    p_championship_4, p_title}`` for the standard Cup elimination format
    (key names follow ``playoff_format.probability_keys`` for other formats,
    e.g. the 2026 Chase yields ``{p_make_playoffs, p_title}``).

    See :func:`simulate_playoffs` for parameter semantics; this is the
    probability-summary wrapper over the same engine.
    """
    sim = simulate_playoffs(
        strengths,
        playoff_format,
        completed_results=completed_results,
        remaining_schedule=remaining_schedule,
        n_sims=n_sims,
        rng_seed=rng_seed,
        temperature=temperature,
    )
    return sim.probabilities()
