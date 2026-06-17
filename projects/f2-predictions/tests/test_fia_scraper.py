"""Phase 3 real-feed scraper — offline parser tests + graceful degradation.

The parser is exercised against a saved fixture (a trimmed real fiaformula2.com
results page); nothing here touches the network, so it is CI-safe. The live
end-to-end path is the manual `f2_predictions.scrape` CLI.
"""

import builtins
from pathlib import Path

from f2_predictions.sources.fia_f2_source import FiaF2Source

FIXTURE = (Path(__file__).parent / "fixtures" / "fia_f2_round.html").read_text()


def test_parses_feature_classification():
    rows = FiaF2Source._parse_session(FIXTURE, "Feature Race")
    assert [r["code"] for r in rows[:3]] == ["ARO", "HAD", "BOR"]
    assert rows[0]["position"] == 1
    assert rows[0]["team"] == "Hitech Pulse-Eight"
    assert rows[0]["name"] == "P. Aron"


def test_parses_sprint_and_differs_from_feature():
    feature = FiaF2Source._parse_session(FIXTURE, "Feature Race")
    sprint = FiaF2Source._parse_session(FIXTURE, "Sprint Race")
    assert sprint[0]["code"] == "BEA"
    assert [r["code"] for r in sprint] != [r["code"] for r in feature]


def test_positions_are_unique_and_ascending():
    rows = FiaF2Source._parse_session(FIXTURE, "Feature Race")
    positions = [r["position"] for r in rows]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions)
    assert all(r["code"].isupper() for r in rows)


def test_missing_session_returns_empty():
    assert FiaF2Source._parse_session("<html><body>nope</body></html>", "Feature Race") == []


def test_unconfigured_season_degrades_without_network():
    src = FiaF2Source()
    assert src.num_rounds(1999) == 0  # no anchor → no fetch, no error
    assert src.results(1999, 1, race_index=1) is None
    assert src.entry_list(1999) == {}


def test_results_returns_none_when_requests_unavailable(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "requests":
            raise ImportError("requests not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    src = FiaF2Source()
    # 2024 has an anchor, but the fetch can't happen → None, never raises.
    assert src.results(2024, 1, race_index=1) is None
