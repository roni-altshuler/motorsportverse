#!/usr/bin/env python3
"""Derive per-circuit history (past winners + grid / attrition priors) for the site.

Output ``website/public/data/circuit_history.json`` — a JSON object keyed by the
round JSON's ``gpKey`` (the stable circuit identifier used in
``website/public/data/rounds/round_NN.json`` and ``season.json``'s calendar).
Each value::

    {
      "circuit": "<display name>",
      "pastWinners": [
        {"season": 2025, "driver": "NOR", "constructor": "McLaren"}, ...
      ],                                # up to 5, most recent first
      "poleToWinPct": <0..1 | null>,    # proxy: gridFinishSpearman from circuit_priors
      "safetyCarRate": <0..1 | null>    # proxy: dnfRate (attrition) from circuit_priors
    }

Everything is derived from **committed, offline** data — no network, no FastF1:

* ``data/history.duckdb`` — real per-(season, round) finishing positions for
  2022-2025 (force-committed; refreshed by the nightly backfill cron). Winners
  are the ``actual_position == 1`` rows.
* ``SEASON_CALENDARS`` (below) — the official public F1 round->circuit calendars
  for 2022-2025. Verified round-for-round against the winners committed in
  ``history.duckdb`` (e.g. 2024 R3 Australia = SAI, R8 Monaco = LEC, R14
  Belgium = HAM; 2025 R8 Monaco = NOR). gpKeys use the SAME strings as the
  current ``season.json`` calendar so the join is exact.
* ``website/public/data/season.json`` + ``rounds/round_NN.json`` — the current
  season's calendar (round -> gpKey/circuit/safetyCarLikelihood) and its actual
  race winners as they land (``actualResults`` position 1).
* ``features/data/circuit_priors.json`` — grid-finish Spearman + DNF rate per
  Ergast circuitId (the ground-effect-era 2022-2025 window).

Winners are **never fabricated**: every winner is read from committed results
(``history.duckdb`` for prior seasons, ``round_NN.json`` actuals for the live
season) and every prior-season winner must resolve to a known constructor or it
is skipped with a warning. Circuits with no sourced winner (e.g. a brand-new
venue such as Madrid) get an empty ``pastWinners`` list and still carry the
priors-based fields when the circuit is present in ``circuit_priors.json``.

Usage::

    python src/export_circuit_history.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "website", "public", "data")
ROUNDS_DIR = os.path.join(DATA_DIR, "rounds")
SEASON_PATH = os.path.join(DATA_DIR, "season.json")
PRIORS_PATH = os.path.join(PROJECT_ROOT, "features", "data", "circuit_priors.json")
HISTORY_DB = os.path.join(PROJECT_ROOT, "data", "history.duckdb")
OUT_PATH = os.path.join(DATA_DIR, "circuit_history.json")

MAX_WINNERS = 5

# Prior full seasons available in history.duckdb (the ground-effect era, which is
# also the window circuit_priors.json aggregates). The current season is read
# separately from the committed round JSONs.
PRIOR_SEASONS = (2022, 2023, 2024, 2025)

# Official public F1 round -> gpKey calendars, verified round-for-round against
# the winners committed in data/history.duckdb. gpKey strings match season.json.
# Circuits not on the current calendar (Bahrain / Saudi Arabia / Emilia Romagna /
# France) are still listed for a correct round->circuit mapping; they simply have
# no current-calendar entry to attach to and are dropped at output time.
SEASON_CALENDARS: dict[int, dict[int, str]] = {
    2022: {
        1: "Bahrain", 2: "Saudi Arabia", 3: "Australia", 4: "Emilia Romagna",
        5: "Miami", 6: "Spain", 7: "Monaco", 8: "Azerbaijan", 9: "Canada",
        10: "Great Britain", 11: "Austria", 12: "France", 13: "Hungary",
        14: "Belgium", 15: "Netherlands", 16: "Italy", 17: "Singapore",
        18: "Japan", 19: "United States", 20: "Mexico", 21: "Brazil",
        22: "Abu Dhabi",
    },
    2023: {
        1: "Bahrain", 2: "Saudi Arabia", 3: "Australia", 4: "Azerbaijan",
        5: "Miami", 6: "Monaco", 7: "Spain", 8: "Canada", 9: "Austria",
        10: "Great Britain", 11: "Hungary", 12: "Belgium", 13: "Netherlands",
        14: "Italy", 15: "Singapore", 16: "Japan", 17: "Qatar",
        18: "United States", 19: "Mexico", 20: "Brazil", 21: "Las Vegas",
        22: "Abu Dhabi",
    },
    2024: {
        1: "Bahrain", 2: "Saudi Arabia", 3: "Australia", 4: "Japan", 5: "China",
        6: "Miami", 7: "Emilia Romagna", 8: "Monaco", 9: "Canada", 10: "Spain",
        11: "Austria", 12: "Great Britain", 13: "Hungary", 14: "Belgium",
        15: "Netherlands", 16: "Italy", 17: "Azerbaijan", 18: "Singapore",
        19: "United States", 20: "Mexico", 21: "Brazil", 22: "Las Vegas",
        23: "Qatar", 24: "Abu Dhabi",
    },
    2025: {
        1: "Australia", 2: "China", 3: "Japan", 4: "Bahrain", 5: "Saudi Arabia",
        6: "Miami", 7: "Emilia Romagna", 8: "Monaco", 9: "Spain", 10: "Canada",
        11: "Austria", 12: "Great Britain", 13: "Belgium", 14: "Hungary",
        15: "Netherlands", 16: "Italy", 17: "Azerbaijan", 18: "Singapore",
        19: "United States", 20: "Mexico", 21: "Brazil", 22: "Las Vegas",
        23: "Qatar", 24: "Abu Dhabi",
    },
}

# Constructor of each race winner across 2022-2025. Every winning driver in this
# window drove for exactly one constructor in the seasons they won, so a flat
# code->team map is unambiguous (verified against the season entry lists). Any
# winner not covered here is skipped rather than guessed.
WINNER_CONSTRUCTORS: dict[str, str] = {
    "VER": "Red Bull Racing",
    "PER": "Red Bull Racing",
    "LEC": "Ferrari",
    "SAI": "Ferrari",
    "RUS": "Mercedes",
    "HAM": "Mercedes",
    "NOR": "McLaren",
    "PIA": "McLaren",
}

# Current-calendar gpKey -> Ergast circuitId (the key circuit_priors.json uses).
# "Madrid" is intentionally absent — it is a brand-new venue with no priors.
GPKEY_TO_PRIOR: dict[str, str] = {
    "Australia": "albert_park",
    "China": "shanghai",
    "Japan": "suzuka",
    "Miami": "miami",
    "Canada": "villeneuve",
    "Monaco": "monaco",
    "Spain": "catalunya",
    "Austria": "red_bull_ring",
    "Great Britain": "silverstone",
    "Belgium": "spa",
    "Hungary": "hungaroring",
    "Netherlands": "zandvoort",
    "Italy": "monza",
    "Azerbaijan": "baku",
    "Singapore": "marina_bay",
    "United States": "americas",
    "Mexico": "rodriguez",
    "Brazil": "interlagos",
    "Las Vegas": "vegas",
    "Qatar": "losail",
    "Abu Dhabi": "yas_marina",
}


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _prior_season_winners():
    """{gpKey: [(season, driver, constructor), ...]} from committed history.duckdb.

    Returns an empty mapping (with a warning) if the DB is unavailable — the
    current-season winners and priors still export.
    """
    winners: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    if not os.path.exists(HISTORY_DB):
        print(f"  ⚠️  {HISTORY_DB} not found — skipping prior-season winners.")
        return winners
    try:
        import duckdb
    except ImportError:
        print("  ⚠️  duckdb not installed — skipping prior-season winners.")
        return winners

    con = duckdb.connect(HISTORY_DB, read_only=True)
    try:
        for season in PRIOR_SEASONS:
            calendar = SEASON_CALENDARS.get(season, {})
            rows = con.execute(
                "SELECT round, driver FROM historical_predictions "
                "WHERE season = ? AND actual_position = 1 ORDER BY round",
                [season],
            ).fetchall()
            seen_rounds: set[int] = set()
            for rnd, driver in rows:
                if rnd in seen_rounds:  # guard against duplicate winner rows
                    continue
                seen_rounds.add(rnd)
                gp_key = calendar.get(rnd)
                if gp_key is None:
                    print(f"  ⚠️  {season} round {rnd}: no calendar mapping — skipped.")
                    continue
                constructor = WINNER_CONSTRUCTORS.get(driver)
                if constructor is None:
                    print(f"  ⚠️  {season} round {rnd}: no constructor for winner "
                          f"'{driver}' — skipped (not fabricating).")
                    continue
                winners[gp_key].append((season, driver, constructor))
    finally:
        con.close()
    return winners


def _current_season_winners(season_data):
    """{gpKey: [(season, driver, constructor)]} from committed round JSON actuals."""
    winners: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    season_year = season_data.get("season")
    code_to_team = {
        d.get("code"): d.get("team") for d in season_data.get("drivers", [])
    }
    for rnd in range(1, len(season_data.get("calendar", [])) + 1):
        path = os.path.join(ROUNDS_DIR, f"round_{rnd:02d}.json")
        if not os.path.exists(path):
            continue
        data = _load_json(path)
        actual = data.get("actualResults")
        gp_key = data.get("gpKey")
        if not isinstance(actual, dict) or not gp_key:
            continue
        winner = next((code for code, pos in actual.items() if pos == 1), None)
        if not winner:
            continue
        constructor = code_to_team.get(winner)
        if constructor is None:
            print(f"  ⚠️  {season_year} round {rnd}: no team for winner "
                  f"'{winner}' — skipped.")
            continue
        winners[gp_key].append((season_year, winner, constructor))
    return winners


def build_circuit_history():
    """Return the {gpKey: circuit-history} mapping (pure — no file writes)."""
    season_data = _load_json(SEASON_PATH)
    priors = _load_json(PRIORS_PATH).get("circuits", {})

    by_gpkey: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for source in (_prior_season_winners(), _current_season_winners(season_data)):
        for gp_key, rows in source.items():
            by_gpkey[gp_key].extend(rows)

    history: dict[str, dict] = {}
    for entry in season_data.get("calendar", []):
        gp_key = entry.get("gpKey")
        if not gp_key or gp_key in history:
            continue
        # Most recent first, deduped on season (one winner per circuit per year).
        rows = sorted(set(by_gpkey.get(gp_key, [])), key=lambda r: r[0], reverse=True)
        past_winners = [
            {"season": s, "driver": d, "constructor": c}
            for s, d, c in rows[:MAX_WINNERS]
        ]
        prior = priors.get(GPKEY_TO_PRIOR.get(gp_key, ""), {})
        history[gp_key] = {
            "circuit": entry.get("circuit"),
            "pastWinners": past_winners,
            "poleToWinPct": prior.get("gridFinishSpearman"),
            "safetyCarRate": prior.get("dnfRate"),
        }
    return history


def export_circuit_history():
    """Build and write website/public/data/circuit_history.json."""
    history = build_circuit_history()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2)
    with_winners = sum(1 for v in history.values() if v["pastWinners"])
    print(f"✅ Circuit history → {OUT_PATH}")
    print(f"   {len(history)} circuits — {with_winners} with real past winners, "
          f"{len(history) - with_winners} priors-only.")
    return history


def main():
    export_circuit_history()
    return 0


if __name__ == "__main__":
    sys.exit(main())
