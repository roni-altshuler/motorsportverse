"""Weekend-session healing: sessions publish at different times across a
weekend (sprint weekends especially), and the round JSON is never rebuilt
after actuals land. Post-race ingestion must therefore refresh EVERY session
via an upgrade-only merge, and the cron sweep must flag published rounds whose
sessions are still empty when the source verifiably has the data.

Regression context: the 2026 British GP (sprint weekend) showed Qualifying /
Sprint / Sprint Qualifying as "Awaiting data" for a full day after the race,
because only the Grand Prix session was ever filled post-race.
"""
import json

import gp_weekend
from export_website_data import _merge_weekend_sessions


def _session(key, rows=None, status=None):
    rows = rows or []
    return {
        "key": key,
        "label": key,
        "kind": "race",
        "status": status or ("official" if rows else "pending"),
        "rows": rows,
        "note": None if rows else "Official session data is not published yet.",
    }


def _weekend(*sessions, generated="2026-07-04T09:00:00Z"):
    return {
        "generatedAt": generated,
        "source": "test",
        "sourceUrl": "test",
        "loadedSessions": sum(1 for s in sessions if s.get("rows")),
        "sessions": list(sessions),
    }


ROW = [{"position": 1, "driver": "LEC"}]
ROW2 = [{"position": 1, "driver": "ANT"}]


# ── _merge_weekend_sessions ─────────────────────────────────────────────────

def test_merge_upgrades_pending_sessions_with_fresh_rows():
    existing = _weekend(_session("qualifying"), _session("sprint"), _session("grandPrix", ROW))
    fresh = _weekend(
        _session("qualifying", ROW2), _session("sprint", ROW2), _session("grandPrix", ROW),
        generated="2026-07-05T18:00:00Z",
    )
    merged = _merge_weekend_sessions(existing, fresh)
    by_key = {s["key"]: s for s in merged["sessions"]}
    assert by_key["qualifying"]["rows"] == ROW2
    assert by_key["sprint"]["rows"] == ROW2
    assert merged["loadedSessions"] == 3
    assert merged["generatedAt"] == "2026-07-05T18:00:00Z"


def test_merge_never_downgrades_published_rows_on_transient_empty_fetch():
    existing = _weekend(_session("qualifying", ROW2), _session("grandPrix", ROW))
    fresh = _weekend(_session("qualifying"), _session("grandPrix"))  # source hiccup
    merged = _merge_weekend_sessions(existing, fresh)
    by_key = {s["key"]: s for s in merged["sessions"]}
    assert by_key["qualifying"]["rows"] == ROW2
    assert by_key["grandPrix"]["rows"] == ROW
    assert merged["loadedSessions"] == 2


def test_merge_appends_session_types_missing_from_committed_set():
    existing = _weekend(_session("grandPrix", ROW))
    fresh = _weekend(_session("sprint", ROW2), _session("grandPrix", ROW))
    merged = _merge_weekend_sessions(existing, fresh)
    assert [s["key"] for s in merged["sessions"]] == ["grandPrix", "sprint"]


def test_merge_handles_missing_or_empty_sides():
    fresh = _weekend(_session("grandPrix", ROW))
    assert _merge_weekend_sessions(None, fresh) is fresh
    existing = _weekend(_session("grandPrix", ROW))
    assert _merge_weekend_sessions(existing, {}) is existing


# ── _rounds_with_pending_sessions sweep ─────────────────────────────────────

def _fake_state(has_actuals, sessions):
    state = {"weekendResults": _weekend(*sessions)}
    if has_actuals:
        state["actualResults"] = {"LEC": 1}
    return state


def test_sweep_flags_published_round_with_jolpica_backed_pending_session(monkeypatch, tmp_path):
    monkeypatch.setattr(gp_weekend, "_load_calendar", lambda: {
        9: {"name": "British Grand Prix", "date": "2026-07-05", "gp_key": "Great Britain"},
    })
    monkeypatch.setattr(gp_weekend, "_utc_today", lambda: __import__("datetime").date(2026, 7, 6))
    monkeypatch.setattr(gp_weekend, "_committed_round_state", lambda rnd: _fake_state(
        True, [_session("qualifying"), _session("grandPrix", ROW)],
    ))
    monkeypatch.setattr(gp_weekend, "_jolpica_session_available", lambda y, r, kind: kind == "qualifying")
    assert gp_weekend._rounds_with_pending_sessions() == [9]


def test_sweep_skips_round_when_source_has_nothing_new(monkeypatch):
    monkeypatch.setattr(gp_weekend, "_load_calendar", lambda: {
        9: {"name": "British Grand Prix", "date": "2026-07-05", "gp_key": "Great Britain"},
    })
    monkeypatch.setattr(gp_weekend, "_utc_today", lambda: __import__("datetime").date(2026, 7, 6))
    monkeypatch.setattr(gp_weekend, "_committed_round_state", lambda rnd: _fake_state(
        True, [_session("qualifying"), _session("grandPrix", ROW)],
    ))
    monkeypatch.setattr(gp_weekend, "_jolpica_session_available", lambda y, r, kind: False)
    assert gp_weekend._rounds_with_pending_sessions() == []


def test_sweep_ignores_sprint_qualifying_only_gaps(monkeypatch):
    """SQ has no Jolpica probe — a round pending ONLY on SQ must not spin the cron."""
    calls = []
    monkeypatch.setattr(gp_weekend, "_load_calendar", lambda: {
        9: {"name": "British Grand Prix", "date": "2026-07-05", "gp_key": "Great Britain"},
    })
    monkeypatch.setattr(gp_weekend, "_utc_today", lambda: __import__("datetime").date(2026, 7, 6))
    monkeypatch.setattr(gp_weekend, "_committed_round_state", lambda rnd: _fake_state(
        True,
        [_session("sprintQualifying"), _session("qualifying", ROW2),
         _session("sprint", ROW2), _session("grandPrix", ROW)],
    ))
    monkeypatch.setattr(
        gp_weekend, "_jolpica_session_available",
        lambda y, r, kind: calls.append(kind) or True,
    )
    assert gp_weekend._rounds_with_pending_sessions() == []
    assert calls == []  # nothing probed — SQ is not sweepable


def test_sweep_skips_unpublished_rounds(monkeypatch):
    monkeypatch.setattr(gp_weekend, "_load_calendar", lambda: {
        9: {"name": "British Grand Prix", "date": "2026-07-05", "gp_key": "Great Britain"},
    })
    monkeypatch.setattr(gp_weekend, "_utc_today", lambda: __import__("datetime").date(2026, 7, 6))
    monkeypatch.setattr(gp_weekend, "_committed_round_state", lambda rnd: _fake_state(
        False, [_session("qualifying")],
    ))
    assert gp_weekend._rounds_with_pending_sessions() == []


# ── The committed round 9 must stay healed ──────────────────────────────────

def test_round9_weekend_sessions_are_populated():
    from pathlib import Path

    rounds_dir = Path(__file__).resolve().parent.parent / "website" / "public" / "data" / "rounds"
    r9 = json.loads((rounds_dir / "round_09.json").read_text())
    if not r9.get("actualResults"):
        return  # round not concluded in this checkout — nothing to assert
    sessions = {s["key"]: s for s in r9["weekendResults"]["sessions"]}
    for key in ("qualifying", "sprint", "grandPrix"):
        assert sessions[key].get("rows"), f"{key} session lost its published rows"
