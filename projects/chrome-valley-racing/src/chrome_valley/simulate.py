"""Seeded season simulator for the Chrome Valley Racing League.

One ``random.Random(seed)`` drives everything, and characters are always
iterated in roster order, so a seed maps to exactly one season. Personality
is the physics engine:

* pace decides the baseline lap time;
* ``consistency`` shrinks lap-to-lap noise and keeps pit stops clean;
* ``grit`` shrugs off rough surfaces (venue ``chaos``) and mechanical gremlins;
* ``heart`` finds extra tenths in the final quarter of a race;
* ``showboat`` is the tragic flaw — leading late in a race with a crowd
  watching is exactly when a showboat throws it into the fence;
* mentored rookies gain pace (and lose a little showboat) round by round,
  which writes a visible story arc straight into the data;
* rivals carry momentum: finish ahead of your rival and next round feels easy.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from chrome_valley import config
from chrome_valley.config import Character, Venue

# ── Tuning knobs ─────────────────────────────────────────────────────────
BASE_LAP_SECONDS = 60.0
PACE_SECONDS_PER_POINT = 0.03  # lap-time gain per pace point
NOISE_FLOOR = 0.25  # everyone wobbles a little
NOISE_PER_INCONSISTENCY = 1.10  # extra sd for consistency 0 vs 100
CHAOS_GRIT_PENALTY = 0.85  # rough-surface penalty scale for low grit
HEART_LATE_SECONDS = 0.50  # per-lap gain at heart=100 in the final quarter
LATE_PHASE = 0.75  # final quarter of the race
FINAL_THIRD = 2 / 3  # where showboats start feeling the crowd
SHOWBOAT_CRASH_COEFF = 0.35  # race-level crash odds scale while leading
MENTOR_PACE_GAIN = 7.0  # rookie pace points gained by season's end
MENTOR_DISCIPLINE = 0.45  # fraction of showboat coached away by season's end
MOMENTUM_SECONDS = 0.02  # per-lap gain per momentum point
MOMENTUM_CAP = 3.0
MOMENTUM_DECAY = 0.5
PIT_STOP_SECONDS = 22.0
PIT_MISHAP_COEFF = 0.6
MECHANICAL_COEFF = 0.035


@dataclass
class RaceEvent:
    lap: int
    kind: str  # lead_change | pit_drama | showboat_crash | mechanical | heart_surge
    slug: str
    detail: str


@dataclass
class RaceResult:
    position: int
    slug: str
    points: int
    laps_completed: int
    dnf: bool
    dnf_reason: str | None
    laps_led: int
    gap_seconds: float | None  # None for DNFs


@dataclass
class Race:
    round: int
    venue_slug: str
    results: list[RaceResult]
    events: list[RaceEvent]
    story: list[str]
    # Running order (slugs) when the final third began — lets tests measure
    # who "came alive" late, and feeds the closing story bullet.
    final_third_order: list[str] = field(default_factory=list)


@dataclass
class StandingsRow:
    position: int
    slug: str
    points: int
    wins: int
    podiums: int
    dnfs: int


@dataclass
class Season:
    seed: int
    races: list[Race]
    standings: list[StandingsRow]

    @property
    def champion(self) -> StandingsRow:
        return self.standings[0]


# ── Personality mechanics ────────────────────────────────────────────────
def season_progress(round_index: int, total_rounds: int) -> float:
    return round_index / max(total_rounds - 1, 1)


def effective_pace(char: Character, round_index: int, total_rounds: int, venue: Venue) -> float:
    """Base pace + mentor coaching arc + venue affinity."""
    pace = char.base_pace
    if char.slug in config.MENTORSHIPS:
        pace += MENTOR_PACE_GAIN * season_progress(round_index, total_rounds)
    for tag, bonus in char.affinity.items():
        if tag in venue.tags:
            pace += bonus
    return pace


def effective_showboat(char: Character, round_index: int, total_rounds: int) -> float:
    """A good mentor coaches some of the showboating away as the season goes."""
    showboat = float(char.showboat)
    if char.slug in config.MENTORSHIPS:
        showboat *= 1.0 - MENTOR_DISCIPLINE * season_progress(round_index, total_rounds)
    return showboat


def late_heart_bonus(char: Character) -> float:
    """Per-lap seconds gained in the final quarter — heart, measurable."""
    return HEART_LATE_SECONDS * char.heart / 100.0


def _lap_noise_sd(char: Character) -> float:
    return NOISE_FLOOR + (100 - char.consistency) / 100.0 * NOISE_PER_INCONSISTENCY


def _showboat_crash_prob_per_lap(showboat: float, venue: Venue, final_third_laps: int) -> float:
    race_level = SHOWBOAT_CRASH_COEFF * (showboat / 100.0) ** 2 * (0.4 + venue.chaos)
    return race_level / max(final_third_laps, 1)


# ── The race ─────────────────────────────────────────────────────────────
def simulate_race(
    rng: random.Random,
    venue: Venue,
    round_index: int,
    total_rounds: int,
    momentum: dict[str, float] | None = None,
) -> Race:
    momentum = momentum or {}
    field_chars = list(config.CHARACTERS)
    laps = venue.laps
    pit_lap = max(2, int(laps * 0.55))
    late_start = int(laps * LATE_PHASE)
    final_third_start = int(laps * FINAL_THIRD)
    final_third_laps = laps - final_third_start

    total_time: dict[str, float] = {c.slug: 0.0 for c in field_chars}
    dnf_lap: dict[str, int] = {}
    dnf_reason: dict[str, str] = {}
    laps_led: dict[str, int] = {c.slug: 0 for c in field_chars}
    events: list[RaceEvent] = []
    final_third_order: list[str] = []

    # Pre-draw mechanical gremlins (rare, grit-resisted, chaos-fed).
    for char in field_chars:
        p_mech = MECHANICAL_COEFF * (0.5 + venue.chaos) * max(0.0, 1.1 - char.grit / 100.0)
        if rng.random() < p_mech:
            dnf_lap[char.slug] = rng.randint(3, laps - 2)
            dnf_reason[char.slug] = "mechanical gremlins"

    pace = {
        c.slug: effective_pace(c, round_index, total_rounds, venue) for c in field_chars
    }
    showboat = {
        c.slug: effective_showboat(c, round_index, total_rounds) for c in field_chars
    }
    noise_sd = {c.slug: _lap_noise_sd(c) for c in field_chars}

    def running_order() -> list[str]:
        alive = [c.slug for c in field_chars if c.slug not in retired]
        return sorted(alive, key=lambda s: total_time[s])

    retired: set[str] = set()
    leader: str | None = None

    for lap in range(1, laps + 1):
        for char in field_chars:
            slug = char.slug
            if slug in retired:
                continue
            # Scheduled mechanical retirement.
            if slug in dnf_reason and dnf_lap[slug] == lap:
                retired.add(slug)
                events.append(
                    RaceEvent(lap, "mechanical", slug, f"{char.name} coasts to a stop — "
                              f"{dnf_reason[slug]} at {venue.name}.")
                )
                continue

            lap_time = BASE_LAP_SECONDS - pace[slug] * PACE_SECONDS_PER_POINT
            lap_time += rng.gauss(0.0, noise_sd[slug])
            # Rough surface punishes low grit.
            lap_time += venue.chaos * (100 - char.grit) / 100.0 * CHAOS_GRIT_PENALTY * abs(
                rng.gauss(0.0, 0.8)
            )
            # Momentum from rivalries and recent glory.
            lap_time -= min(momentum.get(slug, 0.0), MOMENTUM_CAP) * MOMENTUM_SECONDS
            # Heart: the final quarter is where the valley's believers go.
            if lap > late_start:
                lap_time -= late_heart_bonus(char)
            # Pit stop.
            if lap == pit_lap:
                lap_time += PIT_STOP_SECONDS
                p_mishap = venue.pit_drama * (1 - char.consistency / 100.0) * PIT_MISHAP_COEFF
                if rng.random() < p_mishap:
                    loss = rng.uniform(4.0, 12.0)
                    lap_time += loss
                    events.append(
                        RaceEvent(lap, "pit_drama", slug,
                                  f"{char.name}'s stop goes sideways — a fumbled tire "
                                  f"costs {loss:.0f} seconds.")
                    )
            total_time[slug] += lap_time

        order = running_order()
        if lap == final_third_start:
            final_third_order = list(order)
        if order:
            new_leader = order[0]
            laps_led[new_leader] += 1
            if leader is not None and new_leader != leader and leader not in retired:
                events.append(
                    RaceEvent(lap, "lead_change", new_leader,
                              f"{config.character_by_slug(new_leader).name} takes the lead "
                              f"on lap {lap}.")
                )
            leader = new_leader

            # The tragic flaw: leading late, crowd roaring, one showoff move too many.
            if lap >= final_third_start and lap < laps:
                lead_char = config.character_by_slug(new_leader)
                p_crash = _showboat_crash_prob_per_lap(
                    showboat[new_leader], venue, final_third_laps
                )
                if rng.random() < p_crash:
                    retired.add(new_leader)
                    dnf_lap[new_leader] = lap
                    dnf_reason[new_leader] = "crashed while showboating in the lead"
                    events.append(
                        RaceEvent(lap, "showboat_crash", new_leader,
                                  f"{lead_char.name} plays to the crowd one corner too long "
                                  f"and slides off while leading on lap {lap}!")
                    )
                    leader = None

    # ── Classification: full field, DNFs ranked by distance covered ──────
    finishers = [s for s in (c.slug for c in field_chars) if s not in retired]
    finishers.sort(key=lambda s: total_time[s])
    retirees = sorted(retired, key=lambda s: (-dnf_lap[s], total_time[s]))
    classified = finishers + retirees

    winner_time = total_time[finishers[0]] if finishers else 0.0
    results: list[RaceResult] = []
    for pos, slug in enumerate(classified, start=1):
        is_dnf = slug in retired
        results.append(
            RaceResult(
                position=pos,
                slug=slug,
                points=config.POINTS[pos - 1],
                laps_completed=dnf_lap[slug] if is_dnf else laps,
                dnf=is_dnf,
                dnf_reason=dnf_reason.get(slug) if is_dnf else None,
                laps_led=laps_led[slug],
                gap_seconds=None if is_dnf else round(total_time[slug] - winner_time, 2),
            )
        )

    # Late-surge events for the feed (positions gained since the final third).
    for slug in finishers:
        if slug in final_third_order:
            gained = final_third_order.index(slug) - (classified.index(slug))
            char = config.character_by_slug(slug)
            if gained >= 3 and char.heart >= 70:
                events.append(
                    RaceEvent(laps, "heart_surge", slug,
                              f"{char.name} comes alive in the closing laps, "
                              f"up {gained} spots when it matters.")
                )

    race = Race(
        round=round_index + 1,
        venue_slug=venue.slug,
        results=results,
        events=events,
        story=[],
        final_third_order=final_third_order,
    )
    race.story = _tell_story(rng, race, venue, round_index, total_rounds)
    return race


# ── The story bullets ────────────────────────────────────────────────────
_WIN_TEMPLATES = (
    "{name} wins at {venue}, {gap} clear when the flag falls.",
    "{name} takes {venue} — {gap} in hand and not a scratch on the chrome.",
    "{name} owns {venue} today, crossing the line {gap} up on the field.",
)


def _tell_story(
    rng: random.Random, race: Race, venue: Venue, round_index: int, total_rounds: int
) -> list[str]:
    by_slug = {r.slug: r for r in race.results}
    winner = race.results[0]
    winner_char = config.character_by_slug(winner.slug)
    runner_up = race.results[1]
    gap = f"{runner_up.gap_seconds:.1f}s" if runner_up.gap_seconds is not None else "a country mile"
    bullets = [
        rng.choice(_WIN_TEMPLATES).format(name=winner_char.name, venue=venue.name, gap=gap)
    ]

    # Bullet two: the drama.
    crash = next((e for e in race.events if e.kind == "showboat_crash"), None)
    pit = next((e for e in race.events if e.kind == "pit_drama"), None)
    mech = next((e for e in race.events if e.kind == "mechanical"), None)
    if crash is not None:
        bullets.append(crash.detail + " The grandstand gasped; the tow rope did not judge.")
    elif pit is not None:
        bullets.append(pit.detail)
    elif mech is not None:
        bullets.append(mech.detail)
    else:
        bullets.append(
            f"A clean one for the history books — "
            f"{config.character_by_slug(runner_up.slug).name} pushed to {gap} and never blinked."
        )

    # Bullet three: the heart of the valley.
    surge = next((e for e in reversed(race.events) if e.kind == "heart_surge"), None)
    hitch = by_slug.get("hitch-barlow")
    mentored = [s for s in config.MENTORSHIPS if not by_slug[s].dnf and by_slug[s].position <= 3]
    if surge is not None:
        bullets.append(surge.detail)
    elif mentored and round_index >= total_rounds // 2:
        rookie = config.character_by_slug(mentored[0])
        mentor = config.character_by_slug(config.MENTORSHIPS[mentored[0]])
        bullets.append(
            f"{rookie.name} banks a podium and points at {mentor.name}'s pit box — "
            f"the old champion's homework is paying off."
        )
    elif hitch is not None and not hitch.dnf and hitch.position <= 6:
        bullets.append(
            f"Hitch Barlow hauls the old tow truck home P{hitch.position} "
            f"and the whole valley loses its mind."
        )
    else:
        bullets.append(
            f"{winner_char.name} leaves {venue.name} with {winner.points} points "
            f"and the long drive home to think about the next one."
        )
    return bullets


# ── The season ───────────────────────────────────────────────────────────
def simulate_season(seed: int = config.DEFAULT_SEED) -> Season:
    rng = random.Random(seed)
    momentum: dict[str, float] = {c.slug: 0.0 for c in config.CHARACTERS}
    races: list[Race] = []
    total_rounds = len(config.ROUNDS)

    for round_index, venue_slug in enumerate(config.ROUNDS):
        venue = config.venue_by_slug(venue_slug)
        race = simulate_race(rng, venue, round_index, total_rounds, momentum)
        races.append(race)

        # Momentum: decay, then reward the day's heroes and rivalry winners.
        for slug in momentum:
            momentum[slug] *= MOMENTUM_DECAY
        positions = {r.slug: r.position for r in race.results}
        dnfs = {r.slug for r in race.results if r.dnf}
        winner = race.results[0].slug
        momentum[winner] = min(momentum[winner] + 1.5, MOMENTUM_CAP)
        for r in race.results[1:3]:
            momentum[r.slug] = min(momentum[r.slug] + 0.75, MOMENTUM_CAP)
        for a, b in config.RIVALRIES:
            ahead = a if positions[a] < positions[b] else b
            momentum[ahead] = min(momentum[ahead] + 1.0, MOMENTUM_CAP)
        for slug in dnfs:
            momentum[slug] = max(momentum[slug] - 1.0, 0.0)

    return Season(seed=seed, races=races, standings=_standings(races))


def _standings(races: list[Race]) -> list[StandingsRow]:
    points: dict[str, int] = {c.slug: 0 for c in config.CHARACTERS}
    wins: dict[str, int] = {c.slug: 0 for c in config.CHARACTERS}
    podiums: dict[str, int] = {c.slug: 0 for c in config.CHARACTERS}
    dnfs: dict[str, int] = {c.slug: 0 for c in config.CHARACTERS}
    for race in races:
        for r in race.results:
            points[r.slug] += r.points
            if r.position == 1:
                wins[r.slug] += 1
            if r.position <= 3:
                podiums[r.slug] += 1
            if r.dnf:
                dnfs[r.slug] += 1
    ordered = sorted(
        points,
        key=lambda s: (-points[s], -wins[s], -podiums[s], s),
    )
    return [
        StandingsRow(
            position=i + 1, slug=s, points=points[s],
            wins=wins[s], podiums=podiums[s], dnfs=dnfs[s],
        )
        for i, s in enumerate(ordered)
    ]


def season_summary(season: Season) -> list[str]:
    """A few warm lines about how the year went — baked into the export."""
    champ = season.champion
    champ_char = config.character_by_slug(champ.slug)
    lines = [
        f"{champ_char.name} lifts {config.TROPHY_NAME} with {champ.points} points, "
        f"{champ.wins} wins and a hometown of {champ_char.hometown} that will never be quiet again."
    ]
    most_wins = max(season.standings, key=lambda r: r.wins)
    if most_wins.slug != champ.slug and most_wins.wins > 0:
        lines.append(
            f"{config.character_by_slug(most_wins.slug).name} took the most checkered flags "
            f"({most_wins.wins}) — the cup went elsewhere, the highlight reel did not."
        )
    # The rookie arc, straight from the data.
    for rookie_slug, mentor_slug in config.MENTORSHIPS.items():
        half = len(season.races) // 2
        early = [r for race in season.races[:half] for r in race.results if r.slug == rookie_slug]
        late = [r for race in season.races[half:] for r in race.results if r.slug == rookie_slug]
        early_pts = sum(r.points for r in early)
        late_pts = sum(r.points for r in late)
        rookie = config.character_by_slug(rookie_slug)
        mentor = config.character_by_slug(mentor_slug)
        if late_pts > early_pts:
            lines.append(
                f"{rookie.name}'s season split tells the story: {early_pts} points before "
                f"{mentor.name}'s coaching stuck, {late_pts} after. The kid listened. Eventually."
            )
        else:
            lines.append(
                f"{mentor.name} spent a season coaching {rookie.name} — some lessons take "
                f"a winter to sink in."
            )
    hitch = next(r for r in season.standings if r.slug == "hitch-barlow")
    lines.append(
        f"Hitch Barlow finished P{hitch.position} overall, won nothing, and got the loudest "
        f"cheer at the banquet anyway."
    )
    return lines
