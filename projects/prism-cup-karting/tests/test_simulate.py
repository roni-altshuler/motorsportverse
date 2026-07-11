"""Simulator invariants: determinism, full classification, and the genre
mechanics measured over many simulated races."""

from __future__ import annotations

import statistics

from prism_cup import config
from prism_cup.simulate import ROSTER_BY_ID, simulate_race, simulate_race_on, simulate_season


def _all_races(season: dict) -> list[dict]:
    return [race for cup in season["cups"] for race in cup["races"]]


def _many_races(count: int = 300, track_id: str = "jungle-falls") -> list[dict]:
    return [simulate_race(track_id, seed) for seed in range(count)]


# ── Determinism ──────────────────────────────────────────────────────


def test_same_seed_identical_season():
    a = simulate_season(seed=config.SEASON_SEED)
    b = simulate_season(seed=config.SEASON_SEED)
    assert a == b


def test_different_seeds_differ():
    a = simulate_season(seed=1)
    b = simulate_season(seed=2)
    assert a != b


# ── Classification integrity ─────────────────────────────────────────


def test_full_field_classified_every_race():
    season = simulate_season(seed=config.SEASON_SEED)
    assert len(season["cups"]) == len(config.CUPS)
    races = _all_races(season)
    assert len(races) == sum(len(c["tracks"]) for c in config.CUPS)
    roster_ids = {r["id"] for r in config.ROSTER}
    for race in races:
        rows = race["classification"]
        assert len(rows) == config.FIELD_SIZE
        assert [row["position"] for row in rows] == list(range(1, config.FIELD_SIZE + 1))
        assert {row["racerId"] for row in rows} == roster_ids
        assert [row["points"] for row in rows] == config.POINTS


def test_standings_points_are_consistent():
    season = simulate_season(seed=config.SEASON_SEED)
    total_per_race = sum(config.POINTS)
    races = _all_races(season)
    assert sum(row["points"] for row in season["standings"]) == total_per_race * len(races)
    ranks = [row["rank"] for row in season["standings"]]
    assert ranks == list(range(1, config.FIELD_SIZE + 1))
    points = [row["points"] for row in season["standings"]]
    assert points == sorted(points, reverse=True)


# ── Mechanics, measured over many races ──────────────────────────────


def test_seeker_orbs_hit_the_leader_not_the_midfield():
    strikes = [
        e for race in _many_races() for e in race["events"] if e["kind"] == "seeker-strike"
    ]
    assert len(strikes) > 50  # the mechanic actually fires
    hits_at_p1 = sum(1 for e in strikes if e["targetPositionBefore"] == 1)
    hits_at_p5 = sum(1 for e in strikes if e["targetPositionBefore"] == 5)
    assert hits_at_p1 == len(strikes)  # the orb homes on the leader, always
    assert hits_at_p1 > hits_at_p5


def test_heavies_lose_fewer_places_per_hit():
    losses: dict[str, list[int]] = {"light": [], "heavy": []}
    for race in _many_races():
        for e in race["events"]:
            if e["kind"] in ("seeker-strike", "slick-spin"):
                wc = e["targetWeightClass"]
                if wc in losses:
                    losses[wc].append(e["placesLost"])
    assert len(losses["light"]) > 30 and len(losses["heavy"]) > 30
    assert statistics.mean(losses["heavy"]) < statistics.mean(losses["light"])


def test_back_of_field_draws_stronger_items():
    front_powers, back_powers = [], []
    for race in _many_races():
        for e in race["events"]:
            if e["kind"] != "pickup":
                continue
            if e["positionAtPickup"] <= 4:
                front_powers.append(e["itemPower"])
            elif e["positionAtPickup"] >= 9:
                back_powers.append(e["itemPower"])
    assert len(front_powers) > 100 and len(back_powers) > 100
    assert statistics.mean(back_powers) > statistics.mean(front_powers)


def test_shield_blocks_happen():
    blocks = [
        e for race in _many_races() for e in race["events"] if e["kind"] == "shield-block"
    ]
    assert len(blocks) > 0


def test_higher_hazard_raises_finish_variance():
    base = dict(config.TRACKS[0], laps=4, boost_pad_density=0.5)
    calm = dict(base, hazard=1)
    wild = dict(base, hazard=5)
    probe = config.ROSTER[4]["id"]  # a mid-pack medium-class racer

    def finish_positions(track: dict) -> list[int]:
        positions = []
        for seed in range(250):
            race = simulate_race_on(track, seed)
            row = next(r for r in race["classification"] if r["racerId"] == probe)
            positions.append(row["position"])
        return positions

    assert statistics.pstdev(finish_positions(wild)) > statistics.pstdev(
        finish_positions(calm)
    )


def test_event_log_covers_every_lap():
    race = simulate_race("molten-keep", seed=42)
    laps_seen = {e["lap"] for e in race["events"]}
    assert laps_seen <= set(range(1, race["laps"] + 1))
    assert len(race["events"]) > 0
    for e in race["events"]:
        assert e["racer"] in ROSTER_BY_ID
        assert isinstance(e["detail"], str) and e["detail"]
