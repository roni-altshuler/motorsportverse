"""The export writes exactly the JSON shapes the website's TS types expect."""

from __future__ import annotations

import json

from chrome_valley import config, export


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_export_writes_all_files(tmp_path):
    written = export.export(tmp_path, seed=7)
    names = {p.relative_to(tmp_path).as_posix() for p in written}
    assert "chrome-valley.json" in names
    assert "roster.json" in names
    for n in range(1, len(config.ROUNDS) + 1):
        assert f"rounds/round_{n:02d}.json" in names
    assert len(names) == 2 + len(config.ROUNDS)


def test_export_deterministic(tmp_path):
    export.export(tmp_path / "a", seed=7)
    export.export(tmp_path / "b", seed=7)
    a = (tmp_path / "a" / "chrome-valley.json").read_text()
    b = (tmp_path / "b" / "chrome-valley.json").read_text()
    assert a == b


def test_league_json_shape(tmp_path):
    export.export(tmp_path, seed=7)
    data = _load(tmp_path / "chrome-valley.json")

    league = data["league"]
    assert league["name"] == config.LEAGUE_NAME
    assert league["trophy"] == config.TROPHY_NAME
    assert "fan-made" in league["disclaimer"].lower()

    season = data["season"]
    assert season["rounds"] == len(config.ROUNDS)
    assert isinstance(season["summary"], list) and len(season["summary"]) >= 3
    assert season["champion"]["slug"] == data["standings"][0]["slug"]

    assert len(data["venues"]) == len(config.VENUES)
    for venue in data["venues"]:
        for key in ("slug", "name", "kind", "tags", "laps", "chaos", "pitDrama", "night", "blurb"):
            assert key in venue

    assert len(data["calendar"]) == len(config.ROUNDS)
    venue_slugs = {v["slug"] for v in data["venues"]}
    for entry in data["calendar"]:
        assert entry["venueSlug"] in venue_slugs
        assert entry["winnerSlug"]

    standings = data["standings"]
    assert [row["position"] for row in standings] == list(range(1, 13))
    points = [row["points"] for row in standings]
    assert points == sorted(points, reverse=True)
    for row in standings:
        for key in ("slug", "name", "number", "color", "points", "wins", "podiums", "dnfs"):
            assert key in row


def test_roster_json_shape(tmp_path):
    export.export(tmp_path, seed=7)
    roster = _load(tmp_path / "roster.json")
    assert "fan-made" in roster["disclaimer"].lower()
    cards = roster["characters"]
    assert len(cards) == 12
    for card in cards:
        for key in ("slug", "name", "number", "car", "hometown", "role", "bio", "color",
                    "basePace", "traits", "affinity"):
            assert key in card
        traits = card["traits"]
        assert set(traits) == {"grit", "showboat", "consistency", "heart"}
        for value in traits.values():
            assert isinstance(value, int) and 0 <= value <= 100
        assert card["bio"].strip()


def test_round_json_shape(tmp_path):
    export.export(tmp_path, seed=7)
    for n in range(1, len(config.ROUNDS) + 1):
        payload = _load(tmp_path / "rounds" / f"round_{n:02d}.json")
        assert payload["round"] == n
        assert set(payload["venue"]) == {"slug", "name", "kind", "laps"}
        assert len(payload["story"]) == 3
        results = payload["results"]
        assert [r["position"] for r in results] == list(range(1, 13))
        for r in results:
            for key in ("slug", "name", "number", "points", "lapsCompleted", "dnf",
                        "dnfReason", "lapsLed", "gapSeconds"):
                assert key in r
            if r["dnf"]:
                assert r["dnfReason"]
            else:
                assert r["gapSeconds"] is not None
        for event in payload["events"]:
            assert set(event) == {"lap", "kind", "slug", "detail"}


def test_default_out_dir_is_the_website(tmp_path):
    assert export.DEFAULT_OUT.parts[-3:] == ("website", "public", "data")
    assert export.DEFAULT_OUT.parts[-4] == "chrome-valley-racing"
