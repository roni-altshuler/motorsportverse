"""Shared FIA feeder-series scraper — offline parser + degradation tests."""

import builtins

import pytest

from motorsport_data.sources.fia_feeder import FiaFeederSource, WrongEventError

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


# ── Wrong-event ingestion guards ────────────────────────────────────────────
# A cache/proxy/CMS hiccup can serve a DIFFERENT round's page for a requested
# raceid; the page's own title is the identity that must match before any
# classification is parsed (see the F1 wrong-event incident of 2026-07-05).

_ROUND2_PAGE = _MINI_PAGE.replace(
    "Round 1 : Bahrain , Sakhir", "Round 2 : Australia , Melbourne"
)


def _primed_source(round_num, page):
    """Source with caches primed (no network): ``round_num`` → raceid 999 → page."""
    src = _source()
    src._round_map_cache[2026] = {round_num: 999}
    src._page_cache[999] = page
    return src


def test_parse_event_identity_reads_the_title():
    identity = FiaFeederSource.parse_event_identity(_MINI_PAGE)
    assert identity == {
        "round": 1,
        "country": "Bahrain",
        "city": "Sakhir",
        "dates": "01-03 March 2026",
    }
    assert FiaFeederSource.parse_event_identity("<html>no title</html>") is None
    assert FiaFeederSource.parse_event_identity(None) is None


def test_verify_page_identity_accepts_matching_round_and_country():
    identity = FiaFeederSource.verify_page_identity(
        _MINI_PAGE, expected_round=1, expected_country="Bahrain"
    )
    assert identity["round"] == 1


def test_verify_page_identity_rejects_round_mismatch():
    with pytest.raises(WrongEventError, match="round 2"):
        FiaFeederSource.verify_page_identity(_ROUND2_PAGE, expected_round=1)


def test_verify_page_identity_rejects_country_mismatch():
    with pytest.raises(WrongEventError, match="Bahrain"):
        FiaFeederSource.verify_page_identity(
            _MINI_PAGE, expected_round=1, expected_country="Australia"
        )


def test_verify_page_identity_folds_parenthetical_country_variants():
    page = _MINI_PAGE.replace("Bahrain", "Spain")
    FiaFeederSource.verify_page_identity(
        page, expected_round=1, expected_country="Spain (Madrid)"
    )


def test_verify_page_identity_rejects_titleless_page():
    with pytest.raises(WrongEventError, match="no parseable round title"):
        FiaFeederSource.verify_page_identity(
            "<html><span>Feature Race</span></html>", expected_round=1
        )


def test_results_defer_when_page_is_another_round():
    # Raceid resolves for round 1, but the served page is round 2's — the
    # scraper must return None (composite defers), never round 2's rows.
    src = _primed_source(1, _ROUND2_PAGE)
    assert src.results(2026, 1, race_index=1) is None
    assert src.entry_list(2026) == {}  # nothing leaked from the wrong page


def test_results_defer_when_page_has_no_identity():
    titleless = _MINI_PAGE.replace(
        "<h1>Formula X Round 1 : Bahrain , Sakhir 01-03 March 2026</h1>", ""
    )
    # The results table still parses — identity, not table shape, admits a page.
    assert FiaFeederSource._parse_session(titleless, "Feature Race")
    src = _primed_source(1, titleless)
    assert src.results(2026, 1, race_index=1) is None


def test_results_accept_the_requested_round():
    src = _primed_source(1, _MINI_PAGE)
    rows = src.results(2026, 1, race_index=1)
    assert [r.competitor for r in rows] == ["AAA", "BBB"]


def test_qualifying_defers_when_page_is_another_round():
    quali_page = _ROUND2_PAGE.replace("Feature Race", "Qualifying")
    src = _primed_source(1, quali_page)
    assert src.qualifying(2026, 1) is None


def test_qualifying_accepts_the_requested_round():
    quali_page = _MINI_PAGE.replace("Feature Race", "Qualifying")
    src = _primed_source(1, quali_page)
    assert src.qualifying(2026, 1) == ["AAA", "BBB"]
