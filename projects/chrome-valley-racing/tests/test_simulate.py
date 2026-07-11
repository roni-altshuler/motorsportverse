"""The physics of personality — the simulator's contract."""

from __future__ import annotations

import random

from chrome_valley import config, simulate


def _season_fingerprint(season: simulate.Season) -> list[tuple]:
    return [
        (race.round, race.venue_slug, tuple((r.slug, r.position, r.points, r.dnf, r.gap_seconds)
                                            for r in race.results), tuple(race.story))
        for race in season.races
    ]


def test_same_seed_identical_season():
    a = simulate.simulate_season(seed=1234)
    b = simulate.simulate_season(seed=1234)
    assert _season_fingerprint(a) == _season_fingerprint(b)
    assert [(r.slug, r.points) for r in a.standings] == [(r.slug, r.points) for r in b.standings]


def test_different_seed_different_season():
    a = simulate.simulate_season(seed=1)
    b = simulate.simulate_season(seed=2)
    assert _season_fingerprint(a) != _season_fingerprint(b)


def test_standings_sum_to_awarded_points():
    season = simulate.simulate_season(seed=7)
    awarded = sum(r.points for race in season.races for r in race.results)
    in_standings = sum(row.points for row in season.standings)
    assert awarded == in_standings
    # Each race awards the full points table.
    per_race = sum(config.POINTS)
    assert awarded == per_race * len(season.races)


def test_every_race_classifies_the_full_field():
    season = simulate.simulate_season(seed=99)
    slugs = {c.slug for c in config.CHARACTERS}
    for race in season.races:
        assert [r.position for r in race.results] == list(range(1, len(slugs) + 1))
        assert {r.slug for r in race.results} == slugs
        for r in race.results:
            if r.dnf:
                assert r.dnf_reason
                assert r.gap_seconds is None
                venue = config.venue_by_slug(race.venue_slug)
                assert 0 < r.laps_completed <= venue.laps
            else:
                assert r.gap_seconds is not None and r.gap_seconds >= 0.0


def test_standings_sorted_and_positions_sequential():
    season = simulate.simulate_season(seed=5)
    pts = [row.points for row in season.standings]
    assert pts == sorted(pts, reverse=True)
    assert [row.position for row in season.standings] == list(range(1, 13))


def test_high_showboat_characters_crash_more_while_leading():
    """Over 200 simulated races, the showboats bin far more leads than the
    disciplined racers do. Round 0 is used so mentor discipline hasn't kicked in."""
    venue = config.venue_by_slug("chrome-valley-speedbowl")
    crashes: dict[str, int] = {c.slug: 0 for c in config.CHARACTERS}
    for i in range(200):
        rng = random.Random(10_000 + i)
        race = simulate.simulate_race(rng, venue, round_index=0, total_rounds=10)
        for event in race.events:
            if event.kind == "showboat_crash":
                crashes[event.slug] += 1
    high = max(config.CHARACTERS, key=lambda c: c.showboat)  # Dash, showboat 92
    low_slugs = [c.slug for c in config.CHARACTERS if c.showboat <= 30]
    assert crashes[high.slug] >= 5, "the biggest showboat should crash while leading sometimes"
    assert crashes[high.slug] > max(crashes[s] for s in low_slugs)


def test_mentored_rookie_gains_pace_over_the_season():
    rookie = config.character_by_slug("dash-calloway")
    venue = config.venue_by_slug("chrome-valley-speedbowl")
    first = simulate.effective_pace(rookie, 0, 10, venue)
    last = simulate.effective_pace(rookie, 9, 10, venue)
    assert last > first
    assert last - first == simulate.MENTOR_PACE_GAIN
    # ...and the mentor coaches some showboating away too.
    assert simulate.effective_showboat(rookie, 9, 10) < simulate.effective_showboat(rookie, 0, 10)
    # Non-mentored characters don't drift.
    veteran = config.character_by_slug("sterling-voss")
    assert simulate.effective_pace(veteran, 0, 10, venue) == simulate.effective_pace(
        veteran, 9, 10, venue
    )


def test_heart_bonus_monotonic_and_measurable_late():
    """High-heart racers gain ground in the final third; low-heart racers give it up."""
    ranked = sorted(config.CHARACTERS, key=lambda c: c.heart)
    assert simulate.late_heart_bonus(ranked[-1]) > simulate.late_heart_bonus(ranked[0])

    venue = config.venue_by_slug("salt-pan-superoval")  # low chaos isolates the heart term
    gains: dict[str, list[int]] = {"june-alvarado": [], "percy-beaumont": []}
    for i in range(200):
        rng = random.Random(20_000 + i)
        race = simulate.simulate_race(rng, venue, round_index=0, total_rounds=10)
        final_pos = {r.slug: r.position for r in race.results}
        for slug in gains:
            if slug in race.final_third_order and not next(
                r for r in race.results if r.slug == slug
            ).dnf:
                before = race.final_third_order.index(slug) + 1
                gains[slug].append(before - final_pos[slug])
    june = sum(gains["june-alvarado"]) / len(gains["june-alvarado"])
    percy = sum(gains["percy-beaumont"]) / len(gains["percy-beaumont"])
    assert june > percy, f"heart should show up late (june {june:.2f} vs percy {percy:.2f})"


def test_story_has_three_bullets_per_race():
    season = simulate.simulate_season(seed=7)
    for race in season.races:
        assert len(race.story) == 3
        assert all(isinstance(b, str) and b for b in race.story)


def test_venue_affinity_applies():
    nova = config.character_by_slug("nova-okafor")
    night = config.venue_by_slug("neon-mesa-nights")
    day = config.venue_by_slug("chrome-valley-speedbowl")
    assert simulate.effective_pace(nova, 0, 10, night) > simulate.effective_pace(nova, 0, 10, day)
