"""The exporter writes valid JSON whose shapes match the website's TS types
(src/lib/types.ts): LeagueData, RosterData, TracksData, CupData."""

from __future__ import annotations

import json

from prism_cup import config
from prism_cup.export import build_payloads, export_all

EXPECTED_FILES = [
    "prism-cup.json",
    "roster.json",
    "tracks.json",
    "cups/cup_1.json",
    "cups/cup_2.json",
    "cups/cup_3.json",
    "cups/cup_4.json",
]


def _check_standing_row(row: dict) -> None:
    assert isinstance(row["rank"], int)
    assert row["racerId"] in {r["id"] for r in config.ROSTER}
    assert isinstance(row["name"], str)
    assert row["weightClass"] in config.WEIGHT_CLASSES
    assert row["color"].startswith("#")
    for key in ("points", "wins", "podiums", "bestFinish"):
        assert isinstance(row[key], int)


def test_export_writes_expected_files(tmp_path):
    written = export_all(tmp_path, seed=123)
    rels = sorted(str(p.relative_to(tmp_path)) for p in written)
    assert rels == sorted(EXPECTED_FILES)
    for path in written:
        json.loads(path.read_text(encoding="utf-8"))  # every file is valid JSON


def test_export_is_deterministic(tmp_path):
    a = build_payloads(seed=config.SEASON_SEED)
    b = build_payloads(seed=config.SEASON_SEED)
    assert a == b


def test_league_payload_matches_ts_types():
    data = build_payloads(seed=config.SEASON_SEED)["prism-cup.json"]
    assert data["league"] == "Prism Cup Karting"
    assert data["disclaimer"] == config.DISCLAIMER
    assert data["summary"]["totalRaces"] == 16
    assert data["summary"]["totalCups"] == 4
    assert data["summary"]["fieldSize"] == config.FIELD_SIZE
    assert len(data["standings"]) == config.FIELD_SIZE
    for row in data["standings"]:
        _check_standing_row(row)
    _check_standing_row(data["champion"])
    assert data["champion"] == data["standings"][0]
    assert len(data["cupWinners"]) == 4
    for winner in data["cupWinners"]:
        assert set(winner) == {"cup", "number", "winner", "racerId", "points"}
    assert len(data["items"]) == len(config.ITEMS)
    for item in data["items"]:
        assert item["rarity"] in ("common", "uncommon", "rare")
        assert isinstance(item["power"], int)
        assert isinstance(item["effect"], str)


def test_roster_payload_matches_ts_types():
    data = build_payloads(seed=config.SEASON_SEED)["roster.json"]
    assert len(data["racers"]) == config.FIELD_SIZE
    classes = {r["weightClass"] for r in data["racers"]}
    assert classes == {"light", "medium", "heavy"}
    for racer in data["racers"]:
        assert set(racer) == {"id", "name", "vibe", "weightClass", "color", "bio", "stats"}
        stats = racer["stats"]
        assert set(stats) == {"accel", "topSpeed", "knockResistance", "itemLuck"}
        for key in ("accel", "topSpeed", "knockResistance"):
            assert 1 <= stats[key] <= 10
        assert 0.8 <= stats["itemLuck"] <= 1.2
        assert racer["bio"]


def test_tracks_payload_matches_ts_types():
    data = build_payloads(seed=config.SEASON_SEED)["tracks.json"]
    assert len(data["tracks"]) == 8
    for track in data["tracks"]:
        assert set(track) == {
            "id", "name", "laps", "hazard", "boostPadDensity", "color", "character",
        }
        assert 1 <= track["hazard"] <= 5
        assert 0.0 <= track["boostPadDensity"] <= 1.0
        assert track["laps"] >= 3


def test_cup_payloads_match_ts_types():
    payloads = build_payloads(seed=config.SEASON_SEED)
    track_ids = {t["id"] for t in config.TRACKS}
    for n in range(1, 5):
        cup = payloads[f"cups/cup_{n}.json"]
        assert cup["number"] == n
        assert isinstance(cup["name"], str)
        assert len(cup["races"]) == 4
        assert len(cup["standings"]) == config.FIELD_SIZE
        for row in cup["standings"]:
            _check_standing_row(row)
        for race in cup["races"]:
            assert race["trackId"] in track_ids
            rows = race["classification"]
            assert [r["position"] for r in rows] == list(range(1, config.FIELD_SIZE + 1))
            assert len(race["highlights"]) > 0
            for h in race["highlights"]:
                assert set(h) == {"lap", "kind", "text"}
                assert 1 <= h["lap"] <= race["laps"]
