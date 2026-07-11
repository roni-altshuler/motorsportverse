"""Seeded race simulator for Prism Cup Karting.

Genre-faithful mechanics, original names, stdlib only:

- Positions evolve lap by lap from a pace score (accel matters early, top
  speed late), positional inertia, boost-pad chains, and hazard-scaled noise.
- Item draws are position-weighted rubber-banding: the back of the field pulls
  the strong equalisers (Seeker Orb, Tempest, Comet Boost), the front mostly
  defensive tools.
- The Seeker Orb always hunts the current leader; a Static Shield blocks one
  hit; knock-back scales inversely with knock_resistance, so heavies lose
  fewer places per hit.

Every race yields a per-lap event log and a full-field classification. The
same seed always reproduces the same race/season.
"""

from __future__ import annotations

import random
from collections import defaultdict

from prism_cup import config

ROSTER_BY_ID = {r["id"]: r for r in config.ROSTER}
TRACKS_BY_ID = {t["id"]: t for t in config.TRACKS}
ITEMS_BY_ID = {i["id"]: i for i in config.ITEMS}

# Per-lap chance a racer draws an item (scaled by their item_luck trait).
ITEM_PICK_CHANCE = 0.42
SEEKER_BASE_DROP = 3.0
SLICK_BASE_DROP = 2.0

# Highlight selection order for the exported race reports.
HIGHLIGHT_PRIORITY = [
    "seeker-strike",
    "shield-block",
    "tempest",
    "comet-boost",
    "boost-chain",
    "slick-spin",
    "swap",
    "overtake",
]


def position_tier(position: int, field_size: int) -> str:
    """front / mid / back thirds of the field (1-indexed position)."""
    third = field_size / 3.0
    if position <= third:
        return "front"
    if position > 2 * third:
        return "back"
    return "mid"


def draw_item(rng: random.Random, position: int, field_size: int) -> str:
    weights = config.ITEM_TIER_WEIGHTS[position_tier(position, field_size)]
    ids = [item["id"] for item in config.ITEMS]
    return rng.choices(ids, weights=[weights[i] for i in ids], k=1)[0]


def _knock_drop(rng: random.Random, base: float, knock_resistance: int) -> int:
    """Places lost by a hit — heavier (higher knock_resistance) loses less."""
    scaled = (base + rng.uniform(0.0, 1.5)) * (1.0 - knock_resistance / 14.0)
    return max(1, round(scaled))


def simulate_race(track_id: str, seed: int) -> dict:
    return simulate_race_on(TRACKS_BY_ID[track_id], seed)


def simulate_race_on(track: dict, seed: int) -> dict:
    """Simulate one race on `track` (a config.TRACKS-shaped dict)."""
    rng = random.Random(seed)
    order = [r["id"] for r in config.ROSTER]
    rng.shuffle(order)
    grid = list(order)
    n = len(order)
    laps = track["laps"]
    shields: set[str] = set()
    events: list[dict] = []

    def name(rid: str) -> str:
        return ROSTER_BY_ID[rid]["name"]

    def move_back(rid: str, places: int) -> int:
        i = order.index(rid)
        j = min(n - 1, i + places)
        order.insert(j, order.pop(i))
        return j - i

    def move_up(rid: str, places: int) -> int:
        i = order.index(rid)
        j = max(0, i - places)
        order.insert(j, order.pop(i))
        return i - j

    def apply_item(rid: str, item_id: str, lap: int) -> None:
        if item_id == "seeker-orb":
            leader = order[0]
            if leader == rid:
                events.append(
                    {
                        "lap": lap,
                        "kind": "fizzle",
                        "racer": rid,
                        "detail": f"{name(rid)}'s Seeker Orb spirals off — nobody ahead to hunt",
                    }
                )
                return
            if leader in shields:
                shields.discard(leader)
                events.append(
                    {
                        "lap": lap,
                        "kind": "shield-block",
                        "racer": leader,
                        "target": rid,
                        "targetPositionBefore": 1,
                        "detail": f"{name(leader)}'s Static Shield crackles and eats the Seeker Orb",
                    }
                )
                return
            target = ROSTER_BY_ID[leader]
            lost = move_back(leader, _knock_drop(rng, SEEKER_BASE_DROP, target["knock_resistance"]))
            events.append(
                {
                    "lap": lap,
                    "kind": "seeker-strike",
                    "racer": rid,
                    "target": leader,
                    "targetPositionBefore": 1,
                    "targetWeightClass": target["weight_class"],
                    "placesLost": lost,
                    "detail": f"Seeker Orb hunts down {name(leader)} — knocked back {lost}",
                }
            )
        elif item_id == "slick-patch":
            behind = order[order.index(rid) + 1 :]
            if not behind:
                return
            victim = rng.choice(behind)
            if victim in shields:
                shields.discard(victim)
                events.append(
                    {
                        "lap": lap,
                        "kind": "shield-block",
                        "racer": victim,
                        "target": rid,
                        "targetPositionBefore": order.index(victim) + 1,
                        "detail": f"{name(victim)}'s Static Shield fizzes away the Slick Patch",
                    }
                )
                return
            v = ROSTER_BY_ID[victim]
            pos_before = order.index(victim) + 1
            lost = move_back(victim, _knock_drop(rng, SLICK_BASE_DROP, v["knock_resistance"]))
            if lost <= 0:
                return
            events.append(
                {
                    "lap": lap,
                    "kind": "slick-spin",
                    "racer": rid,
                    "target": victim,
                    "targetPositionBefore": pos_before,
                    "targetWeightClass": v["weight_class"],
                    "placesLost": lost,
                    "detail": f"{name(victim)} spins on {name(rid)}'s Slick Patch — down {lost}",
                }
            )
        elif item_id == "comet-boost":
            gain = 1 + (1 if rng.random() < 0.6 else 0) + (1 if rng.random() < 0.25 else 0)
            gained = move_up(rid, gain)
            detail = (
                f"{name(rid)} rides a Comet Boost up {gained} place{'s' if gained != 1 else ''}"
                if gained > 0
                else f"{name(rid)} lights a Comet Boost and streaks clear at the front"
            )
            events.append(
                {
                    "lap": lap,
                    "kind": "comet-boost",
                    "racer": rid,
                    "placesGained": gained,
                    "detail": detail,
                }
            )
        elif item_id == "static-shield":
            shields.add(rid)
            events.append(
                {
                    "lap": lap,
                    "kind": "shield-armed",
                    "racer": rid,
                    "detail": f"{name(rid)} arms a Static Shield",
                }
            )
        elif item_id == "tempest":
            lo, hi = 3, min(9, n - 1)
            if hi - lo < 2:
                return
            segment = order[lo:hi]
            rng.shuffle(segment)
            order[lo:hi] = segment
            events.append(
                {
                    "lap": lap,
                    "kind": "tempest",
                    "racer": rid,
                    "detail": f"{name(rid)}'s Tempest rips through — P{lo + 1}-P{hi} scrambled",
                }
            )
        elif item_id == "swap-beam":
            i = order.index(rid)
            if i == 0:
                return
            ahead = order[i - 1]
            order[i - 1], order[i] = order[i], order[i - 1]
            events.append(
                {
                    "lap": lap,
                    "kind": "swap",
                    "racer": rid,
                    "target": ahead,
                    "detail": f"Swap Beam! {name(rid)} trades places with {name(ahead)}",
                }
            )
        elif item_id == "magnet-hook":
            if move_up(rid, 1) > 0:
                events.append(
                    {
                        "lap": lap,
                        "kind": "hook",
                        "racer": rid,
                        "detail": f"{name(rid)} reels in a place with the Magnet Hook",
                    }
                )
        else:  # pragma: no cover - config/table drift guard
            raise ValueError(f"unknown item: {item_id}")

    for lap in range(1, laps + 1):
        # ── Pace phase: accel-weighted early, top-speed-weighted late. ──
        early = 1.0 - (lap - 1) / max(1, laps - 1) if laps > 1 else 1.0
        pace: dict[str, float] = {}
        boosted: list[tuple[str, float, int]] = []
        for i, rid in enumerate(order):
            racer = ROSTER_BY_ID[rid]
            stat = racer["accel"] * (0.2 + 0.6 * early) + racer["top_speed"] * (0.8 - 0.6 * early)
            inertia = (n - i) * 0.62
            boost = 0.0
            if rng.random() < track["boost_pad_density"] * 0.45:
                boost = rng.uniform(1.2, 3.4) * (0.6 + racer["accel"] / 20.0)
                boosted.append((rid, boost, i + 1))
            noise = rng.gauss(0.0, 0.9 + 0.5 * track["hazard"])
            pace[rid] = stat * 0.30 + inertia + boost + noise
        prev = list(order)
        order.sort(key=lambda rid: -pace[rid])
        for rid, amount, pos_before in boosted:
            gained = pos_before - (order.index(rid) + 1)
            if amount > 2.4 and gained >= 2:
                events.append(
                    {
                        "lap": lap,
                        "kind": "boost-chain",
                        "racer": rid,
                        "placesGained": gained,
                        "detail": f"{name(rid)} chains the boost pads — up {gained} places",
                    }
                )
        gain, climber = max(((prev.index(rid) - order.index(rid)), rid) for rid in order)
        if gain >= 3 and climber not in [b[0] for b in boosted]:
            events.append(
                {
                    "lap": lap,
                    "kind": "overtake",
                    "racer": climber,
                    "placesGained": gain,
                    "detail": f"{name(climber)} carves through traffic — up {gain} places",
                }
            )

        # ── Item phase: pickups + effects, front to back. ──
        for rid in list(order):
            racer = ROSTER_BY_ID[rid]
            if rng.random() >= ITEM_PICK_CHANCE * racer["item_luck"]:
                continue
            pos = order.index(rid) + 1
            item_id = draw_item(rng, pos, n)
            item = ITEMS_BY_ID[item_id]
            events.append(
                {
                    "lap": lap,
                    "kind": "pickup",
                    "racer": rid,
                    "item": item_id,
                    "itemPower": item["power"],
                    "positionAtPickup": pos,
                    "detail": f"{name(rid)} grabs a {item['name']} in P{pos}",
                }
            )
            apply_item(rid, item_id, lap)

    classification = [
        {
            "position": i + 1,
            "racerId": rid,
            "name": ROSTER_BY_ID[rid]["name"],
            "weightClass": ROSTER_BY_ID[rid]["weight_class"],
            "color": ROSTER_BY_ID[rid]["color"],
            "points": config.POINTS[i],
        }
        for i, rid in enumerate(order)
    ]
    return {
        "trackId": track["id"],
        "trackName": track["name"],
        "laps": laps,
        "seed": seed,
        "grid": grid,
        "classification": classification,
        "events": events,
    }


def select_highlights(events: list[dict], limit: int = 6) -> list[dict]:
    """Pick the most report-worthy events of a race, in lap order."""
    rank = {kind: i for i, kind in enumerate(HIGHLIGHT_PRIORITY)}
    eligible = [e for e in events if e["kind"] in rank]
    eligible.sort(key=lambda e: (rank[e["kind"]], e["lap"]))
    chosen = eligible[:limit]
    chosen.sort(key=lambda e: (e["lap"], rank[e["kind"]]))
    return [{"lap": e["lap"], "kind": e["kind"], "text": e["detail"]} for e in chosen]


def _standings(points: dict[str, int], wins: dict[str, int], podiums: dict[str, int],
               best: dict[str, int]) -> list[dict]:
    rows = []
    for rid, pts in points.items():
        racer = ROSTER_BY_ID[rid]
        rows.append(
            {
                "racerId": rid,
                "name": racer["name"],
                "weightClass": racer["weight_class"],
                "color": racer["color"],
                "points": pts,
                "wins": wins.get(rid, 0),
                "podiums": podiums.get(rid, 0),
                "bestFinish": best[rid],
            }
        )
    rows.sort(key=lambda r: (-r["points"], -r["wins"], r["bestFinish"], r["name"]))
    for i, row in enumerate(rows):
        row["rank"] = i + 1
    return rows


def simulate_season(seed: int = config.SEASON_SEED) -> dict:
    """Simulate the full season: 4 cups x 4 races, cup + overall standings."""
    master = random.Random(seed)
    season_points: dict[str, int] = defaultdict(int)
    season_wins: dict[str, int] = defaultdict(int)
    season_podiums: dict[str, int] = defaultdict(int)
    season_best: dict[str, int] = {}
    cups = []
    for number, cup in enumerate(config.CUPS, start=1):
        cup_points: dict[str, int] = defaultdict(int)
        cup_wins: dict[str, int] = defaultdict(int)
        cup_podiums: dict[str, int] = defaultdict(int)
        cup_best: dict[str, int] = {}
        races = []
        for track_id in cup["tracks"]:
            race = simulate_race(track_id, master.randrange(2**32))
            races.append(race)
            for row in race["classification"]:
                rid, pos = row["racerId"], row["position"]
                cup_points[rid] += row["points"]
                season_points[rid] += row["points"]
                if pos == 1:
                    cup_wins[rid] += 1
                    season_wins[rid] += 1
                if pos <= 3:
                    cup_podiums[rid] += 1
                    season_podiums[rid] += 1
                cup_best[rid] = min(cup_best.get(rid, 99), pos)
                season_best[rid] = min(season_best.get(rid, 99), pos)
        cups.append(
            {
                "number": number,
                "id": cup["id"],
                "name": cup["name"],
                "trackIds": list(cup["tracks"]),
                "standings": _standings(cup_points, cup_wins, cup_podiums, cup_best),
                "races": races,
            }
        )
    standings = _standings(season_points, season_wins, season_podiums, season_best)
    return {
        "seed": seed,
        "cups": cups,
        "standings": standings,
        "champion": standings[0],
        "cupWinners": [
            {"cup": c["name"], "number": c["number"], "winner": c["standings"][0]["name"],
             "racerId": c["standings"][0]["racerId"], "points": c["standings"][0]["points"]}
            for c in cups
        ],
    }
