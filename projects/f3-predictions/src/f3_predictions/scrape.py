"""Proof CLI: scrape a real F3 season and compute real standings via the core.

Demonstrates the Phase 3 real feed end-to-end — fiaformula3.com → ``FiaF3Source``
→ ``motorsport_core.standings`` — for a completed season, so the output can be
checked against a completed season (e.g. 2025 champion Câmara).

This hits the network, so it is a manual/opt-in tool (not part of CI). The
scraper's parser is unit-tested offline against a saved fixture.

Run:  python -m f3_predictions.scrape --season 2024
"""
from __future__ import annotations

import argparse

from motorsport_core import standings

from . import config
from .sources.fia_f3_source import FiaF3Source


def scrape_standings(year: int):
    src = FiaF3Source()
    n = src.num_rounds(year)
    if not n:
        raise SystemExit(
            f"no anchor raceid for {year} — add it to config.FIA_F3_SEASON_ANCHORS"
        )

    sprints: list[dict[str, int]] = []
    features: list[dict[str, int]] = []
    for rnd in range(1, n + 1):
        spr = src.results(year, rnd, race_index=0)
        fea = src.results(year, rnd, race_index=1)
        if spr:
            sprints.append({r.competitor: r.position for r in spr})
        if fea:
            features.append({r.competitor: r.position for r in fea})

    entries = src.entry_list(year)
    team_of = {code: e["team"] for code, e in entries.items()}

    drivers = standings.merge_standings(
        standings.compute_driver_standings(sprints, config.SPRINT_POINTS),
        standings.compute_driver_standings(features, config.FEATURE_POINTS),
    )
    teams = standings.merge_standings(
        standings.compute_team_standings(sprints, config.SPRINT_POINTS, team_of),
        standings.compute_team_standings(features, config.FEATURE_POINTS, team_of),
    )
    return drivers, teams, entries, n


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--season", type=int, default=2024)
    p.add_argument("--top", type=int, default=10)
    args = p.parse_args()

    drivers, teams, entries, n = scrape_standings(args.season)
    print(f"FIA F3 {args.season} — scraped {n} rounds (sprint + feature)\n")
    print(f"{'Drivers':<28}{'Team':<24}{'Pts':>6}{'W':>4}{'P':>4}")
    for i, row in enumerate(drivers[: args.top], start=1):
        name = entries.get(row.key, {}).get("name", row.key)
        team = entries.get(row.key, {}).get("team", "")
        print(f"{i:>2} {name:<25}{team:<24}{row.points:>6.0f}{row.wins:>4}{row.podiums:>4}")
    print()
    print(f"{'Teams':<28}{'Pts':>6}")
    for i, row in enumerate(teams[:5], start=1):
        print(f"{i:>2} {row.key:<25}{row.points:>6.0f}")
    print(
        "\nNote: pole/fastest-lap bonus points are not on the race classification "
        "table, so absolute totals differ slightly from official — the order is the "
        "real result. (Bonuses are a Phase-3+ refinement.)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
