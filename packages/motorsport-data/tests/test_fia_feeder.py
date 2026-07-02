"""Shared FIA feeder-series scraper — offline parser + degradation tests."""

import builtins

from motorsport_data.sources.fia_feeder import FiaFeederSource

_MINI_PAGE = """
<html><body>
<h1>Formula X Round 1 : Bahrain , Sakhir 01-03 March 2026</h1>
<span>Feature Race</span>
<table><tbody>
<tr><td><div class="pos">1</div><div class="car-no">7</div>
  <span class="visible-desktop-down">AAA</span>
  <span class="visible-desktop-up">A. Alpha</span>
  <span class="team-name">Team One</span></td></tr>
<tr><td><div class="pos">2</div><div class="car-no">8</div>
  <span class="visible-desktop-down">bbb</span>
  <span class="visible-desktop-up">B. Beta</span>
  <span class="team-name">Team Two</span></td></tr>
<tr><td><div class="pos">DNF</div><div class="car-no">9</div>
  <span class="visible-desktop-down">CCC</span>
  <span class="visible-desktop-up">C. Gamma</span>
  <span class="team-name">Team Three</span></td></tr>
</tbody></table>
</body></html>
"""


def _source(**kw):
    return FiaFeederSource(
        base_url="https://example.invalid", season_anchors={2026: 1234}, **kw
    )


def test_parse_session_classified_rows():
    rows = FiaFeederSource._parse_session(_MINI_PAGE, "Feature Race")
    assert [r["code"] for r in rows] == ["AAA", "BBB"]  # uppercased, DNF excluded
    assert rows[0] == {
        "code": "AAA",
        "name": "A. Alpha",
        "team": "Team One",
        "position": 1,
        "status": "Finished",
    }


def test_parse_session_include_unclassified():
    rows = FiaFeederSource._parse_session(
        _MINI_PAGE, "Feature Race", include_unclassified=True
    )
    assert rows[-1]["code"] == "CCC"
    assert rows[-1]["position"] is None
    assert rows[-1]["status"] == "DNF"


def test_missing_session_returns_empty():
    assert FiaFeederSource._parse_session(_MINI_PAGE, "Sprint Race") == []


def test_unconfigured_season_degrades_without_network():
    src = _source()
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
    src = _source()
    # 2026 has an anchor, but the fetch can't happen → None, never raises.
    assert src.results(2026, 1, race_index=1) is None


def test_custom_session_headings():
    src = FiaFeederSource(
        base_url="https://example.invalid",
        season_anchors={},
        session_headings={0: "Race 1", 1: "Race 2"},
    )
    assert src._session_headings == {0: "Race 1", 1: "Race 2"}
