"""Regression tests for the wrong-event ingestion guards.

On 2026-07-05 (British GP race morning) FastF1's schedule backend failed and
its fuzzy event matcher silently "corrected" 'Great Britain' to the Austrian
Grand Prix. The phase detector saw a fully-loaded (Austrian) race session and
flipped to post-race at 07:06 UTC, and the results fetch then published
Austria's classification as the British GP's official result — hours before
the race started. These tests pin the guards that make that impossible:

  * FastF1 sessions are only trusted when the resolved event's RoundNumber
    matches the requested round (probe + results fallback + viz loader).
  * Jolpica round-scoped responses must echo the requested round back.
"""
import io
import json
import sys
import types

import pandas as pd

import gp_weekend
import export_website_data as ew


class _FakeSession:
    def __init__(self, round_number, event_name, laps=(), results=None):
        self.event = {"RoundNumber": round_number, "EventName": event_name}
        self.laps = list(laps)
        self.results = results
        self.loaded = False

    def load(self, **_kwargs):
        self.loaded = True


def _install_fake_fastf1(monkeypatch, session):
    fake = types.ModuleType("fastf1")
    fake.get_session = lambda *_a, **_k: session
    fake.Cache = types.SimpleNamespace(enable_cache=lambda *_a, **_k: None)
    monkeypatch.setitem(sys.modules, "fastf1", fake)
    return fake


# ── _event_matches_round ────────────────────────────────────────────────────

def test_event_matches_round_accepts_exact_match():
    s = _FakeSession(9, "British Grand Prix")
    assert gp_weekend._event_matches_round(s, 9)


def test_event_matches_round_rejects_other_event():
    s = _FakeSession(8, "Austrian Grand Prix")
    assert not gp_weekend._event_matches_round(s, 9)


def test_event_matches_round_rejects_malformed_event():
    s = _FakeSession(None, "???")
    assert not gp_weekend._event_matches_round(s, 9)


# ── _session_available: the phase-detection probe ───────────────────────────

def test_session_available_rejects_fuzzy_matched_wrong_event(monkeypatch):
    # FastF1 resolves the requested GP to a *different, already-run* event:
    # the session has laps, but it must NOT count as availability.
    austria = _FakeSession(8, "Austrian Grand Prix", laps=[1, 2, 3])
    _install_fake_fastf1(monkeypatch, austria)
    assert gp_weekend._session_available(2026, "Great Britain", "R", expected_round=9) is False
    assert austria.loaded is False  # rejected before any data load


def test_session_available_accepts_correct_event(monkeypatch):
    silverstone = _FakeSession(9, "British Grand Prix", laps=[1, 2, 3])
    _install_fake_fastf1(monkeypatch, silverstone)
    assert gp_weekend._session_available(2026, "Great Britain", "R", expected_round=9) is True


# ── _fetch_actual_race_results: the FastF1 results fallback ─────────────────

def _silence_jolpica(monkeypatch):
    """Jolpica correctly has no results yet — force the FastF1 fallback."""
    monkeypatch.setattr(ew, "_fetch_live_round_actual_results", lambda *_a, **_k: None)


def test_results_fallback_refuses_wrong_event(monkeypatch):
    _silence_jolpica(monkeypatch)
    results = pd.DataFrame({"Abbreviation": ["RUS", "VER"], "Position": [1.0, 2.0]})
    austria = _FakeSession(8, "Austrian Grand Prix", results=results)
    _install_fake_fastf1(monkeypatch, austria)
    assert gp_weekend._fetch_actual_race_results(9, "Great Britain", year=2026) is None


def test_results_fallback_accepts_correct_event(monkeypatch):
    _silence_jolpica(monkeypatch)
    results = pd.DataFrame({"Abbreviation": ["RUS", "VER"], "Position": [1.0, 2.0]})
    silverstone = _FakeSession(9, "British Grand Prix", results=results)
    _install_fake_fastf1(monkeypatch, silverstone)
    assert gp_weekend._fetch_actual_race_results(9, "Great Britain", year=2026) == {
        "RUS": 1,
        "VER": 2,
    }


# ── Jolpica round-echo verification ─────────────────────────────────────────

def _jolpica_payload(round_str, results_rows):
    return {
        "MRData": {
            "RaceTable": {
                "Races": [{"round": round_str, "Results": results_rows}],
            },
        },
    }


def test_jolpica_results_fetch_rejects_round_mismatch(monkeypatch):
    rows = [{"position": "1", "Driver": {"code": "RUS"}}]
    monkeypatch.setattr(ew, "_fetch_jolpica_json", lambda _p: _jolpica_payload("8", rows))
    assert ew._fetch_live_round_actual_results(9, season_year=2026) is None


def test_jolpica_results_fetch_accepts_matching_round(monkeypatch):
    rows = [
        {"position": "1", "Driver": {"code": "RUS"}},
        {"position": "2", "Driver": {"code": "VER"}},
    ]
    monkeypatch.setattr(ew, "_fetch_jolpica_json", lambda _p: _jolpica_payload("9", rows))
    assert ew._fetch_live_round_actual_results(9, season_year=2026) == {"RUS": 1, "VER": 2}


def test_jolpica_availability_probe_rejects_round_mismatch(monkeypatch):
    import urllib.request

    payload = _jolpica_payload("8", [{"position": "1"}])

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *_a, **_k: _Resp(json.dumps(payload).encode()),
    )
    assert gp_weekend._jolpica_session_available(2026, 9, "results") is False


def test_jolpica_availability_probe_accepts_matching_round(monkeypatch):
    import urllib.request

    payload = _jolpica_payload("9", [{"position": "1"}])

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *_a, **_k: _Resp(json.dumps(payload).encode()),
    )
    assert gp_weekend._jolpica_session_available(2026, 9, "results") is True


# ── The committed data must never regress to the phantom state ──────────────

def test_round9_carries_no_actuals_before_the_race_concluded():
    """Round 9's committed JSON was polluted with round 8's classification
    (the incident this file guards against). If actuals exist, they must not
    be a duplicate of the previous round's order."""
    from pathlib import Path

    rounds_dir = Path(__file__).resolve().parent.parent / "website" / "public" / "data" / "rounds"
    r8 = json.loads((rounds_dir / "round_08.json").read_text())
    r9 = json.loads((rounds_dir / "round_09.json").read_text())
    a8, a9 = r8.get("actualResults"), r9.get("actualResults")
    if a8 and a9:
        assert a8 != a9, "round 9 actualResults duplicate round 8 — wrong-event ingestion"
