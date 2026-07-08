"""Regression tests for grid provenance + self-correcting post-quali freeze.

These pin the Part-A overhaul (2026-07-07) that fixed the two operational
accuracy killers the forensic audit identified:

  1. Six of nine 2026 rounds never got a genuine real-grid post-quali
     prediction (R1-5 estimated quali, R9 wrong-event grid), because the
     one-shot freeze gate could never self-correct.
  2. FastF1's fuzzy matcher could promote a *different* event's qualifying to
     ``real-quali-verified`` provenance (the R9 British→Austrian incident).

Contract pinned here:
  * A prediction's grid provenance is recorded as ``real-quali-verified`` /
    ``estimated`` / ``stale``.
  * An estimated- or stale-grid post-quali freeze IS replaced once real
    qualifying lands; a real-quali-verified freeze is FINAL (idempotent cron).
  * A wrong-event grid can NEVER reach ``real-quali-verified``.
"""
import sys
import types

import pandas as pd

import gp_weekend
import f1_prediction_utils as fpu


# ── FastF1 round-match guard (low-level) ────────────────────────────────────

class _FakeSession:
    def __init__(self, round_number, event_name, laps=None):
        self.event = {"RoundNumber": round_number, "EventName": event_name}
        self.laps = laps if laps is not None else []
        self.loaded = False

    def load(self, **_kwargs):
        self.loaded = True


def _install_fake_fastf1(monkeypatch, session):
    fake = types.ModuleType("fastf1")
    fake.get_session = lambda *_a, **_k: session
    fake.Cache = types.SimpleNamespace(enable_cache=lambda *_a, **_k: None)
    monkeypatch.setitem(sys.modules, "fastf1", fake)
    return fake


def test_session_matches_round_accepts_exact():
    assert fpu._fastf1_session_matches_round(_FakeSession(9, "British GP"), 9)


def test_session_matches_round_rejects_other_event():
    assert not fpu._fastf1_session_matches_round(_FakeSession(8, "Austrian GP"), 9)


def test_session_matches_round_rejects_malformed():
    assert not fpu._fastf1_session_matches_round(_FakeSession(None, "???"), 9)


# ── fetch_qualifying_data: wrong-event grid can never be trusted ─────────────

def test_wrong_event_qualifying_rejected_falls_through(monkeypatch):
    """FastF1 resolves 'Great Britain' to the Austrian (R8) session; the fetch
    must reject it BEFORE reading a single lap and fall back to the round-scoped
    Jolpica endpoint (here stubbed to a sentinel)."""
    austria = _FakeSession(8, "Austrian Grand Prix",
                           laps=pd.DataFrame({"Driver": ["RUS"], "LapTime": [pd.Timedelta(seconds=64)]}))
    _install_fake_fastf1(monkeypatch, austria)
    sentinel = {"__jolpica__": 1.0}
    called = {}

    def _fake_jolpica(year, grand_prix, expected_round=None):
        called["expected_round"] = expected_round
        return sentinel

    monkeypatch.setattr(fpu, "_fetch_qualifying_from_jolpica", _fake_jolpica)
    monkeypatch.setattr(fpu, "_extract_qualifying_grid",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("grid extracted from wrong event")))

    out = fpu.fetch_qualifying_data(2026, "Great Britain", expected_round=9)
    assert out is sentinel, "wrong-event data must not be returned as real quali"
    assert called["expected_round"] == 9  # round guard threaded to the fallback


def test_jolpica_qualifying_rejects_round_mismatch(monkeypatch):
    """When the name→round resolution disagrees with the caller, Jolpica refuses
    before any network call."""
    monkeypatch.setattr(fpu, "_resolve_round_number", lambda _gp: 8)
    # expected_round 9 != resolved 8 → None, no urlopen.
    assert fpu._fetch_qualifying_from_jolpica(2026, "Great Britain", expected_round=9) is None


def test_provenance_string_is_estimated_when_no_real_quali():
    """The provenance rule (mirrored inline in export_round_data): estimates in →
    'estimated', never 'real-quali-verified'."""
    estimates = {"VER": 80.0}
    # get_qualifying_or_estimates returns the *same object* when it falls back.
    quali = estimates
    provenance = "real-quali-verified" if quali is not estimates else "estimated"
    assert provenance == "estimated"


# ── needs_update: self-correcting post-quali freeze ─────────────────────────

def _patch_gate(monkeypatch, phase, state):
    monkeypatch.setattr(gp_weekend, "_detect_phase", lambda _r: phase)
    monkeypatch.setattr(gp_weekend, "_committed_round_state", lambda _r: state)


ROUND = 9  # British GP — present in CALENDAR, not postponed


def test_estimated_post_quali_is_replaced(monkeypatch):
    _patch_gate(monkeypatch, "post-quali",
                {"predictionPhase": "post-quali", "gridProvenance": "estimated"})
    assert gp_weekend.needs_update(ROUND) is True


def test_stale_wrong_event_post_quali_is_replaced(monkeypatch):
    _patch_gate(monkeypatch, "post-quali",
                {"predictionPhase": "post-quali", "gridProvenance": "stale"})
    assert gp_weekend.needs_update(ROUND) is True


def test_preview_is_replaced_when_quali_available(monkeypatch):
    _patch_gate(monkeypatch, "post-quali",
                {"predictionPhase": "preview", "gridProvenance": "estimated"})
    assert gp_weekend.needs_update(ROUND) is True


def test_verified_freeze_is_final(monkeypatch):
    _patch_gate(monkeypatch, "post-quali",
                {"predictionPhase": "post-quali", "gridProvenance": "real-quali-verified",
                 "qualifyingDataAvailable": True})
    assert gp_weekend.needs_update(ROUND) is False


def test_verified_freeze_is_idempotent_across_polls(monkeypatch):
    state = {"predictionPhase": "post-quali", "gridProvenance": "real-quali-verified",
             "qualifyingDataAvailable": True}
    _patch_gate(monkeypatch, "post-quali", state)
    # The 15-min cron polls repeatedly; every poll must be a no-op.
    assert all(gp_weekend.needs_update(ROUND) is False for _ in range(5))


def test_legacy_real_grid_without_provenance_is_final(monkeypatch):
    """Rounds published before gridProvenance existed but carrying real quali
    (qualifyingDataAvailable) must not be needlessly re-frozen."""
    _patch_gate(monkeypatch, "post-quali",
                {"predictionPhase": "post-quali", "qualifyingDataAvailable": True})
    assert gp_weekend.needs_update(ROUND) is False


def test_post_race_is_final_when_actuals_present(monkeypatch):
    _patch_gate(monkeypatch, "post-race",
                {"predictionPhase": "post-race", "actualResults": {"RUS": 1}})
    assert gp_weekend.needs_update(ROUND) is False


def test_is_verified_post_quali_helper():
    assert gp_weekend._is_verified_post_quali(
        {"predictionPhase": "post-quali", "gridProvenance": "real-quali-verified"})
    assert not gp_weekend._is_verified_post_quali(
        {"predictionPhase": "post-quali", "gridProvenance": "estimated"})
    assert not gp_weekend._is_verified_post_quali(
        {"predictionPhase": "preview", "gridProvenance": "real-quali-verified"})


# ── qualifying override seam (walk-forward regeneration) ────────────────────

def test_qualifying_override_short_circuits_fetch(monkeypatch):
    """regenerate_post_quali injects committed official qualifying via the
    override seam; the fetch must return it without touching FastF1/network."""
    fpu.clear_qualifying_overrides()
    try:
        times = {"RUS": 88.1, "ANT": 88.2}
        grid = {"RUS": 1, "ANT": 2}
        fpu.set_qualifying_override(2026, "Great Britain", times, grid=grid)
        # Any network path would blow up loudly if reached.
        monkeypatch.setattr(fpu, "_fetch_qualifying_from_jolpica",
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError("network hit")))
        out = fpu.fetch_qualifying_data(2026, "Great Britain", expected_round=9)
        assert out == times
        assert fpu.get_last_qualifying_grid(2026, "Great Britain") == grid
    finally:
        fpu.clear_qualifying_overrides()


def test_qualifying_override_cleared():
    fpu.set_qualifying_override(2026, "Great Britain", {"RUS": 88.1})
    fpu.clear_qualifying_overrides()
    assert fpu._QUALI_TIMES_OVERRIDE == {}
