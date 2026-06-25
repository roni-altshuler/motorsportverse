"""Race-weekend parity: qualifying ingestion, the grid-aware post-quali forecast,
and the freshness gate / phase detector that drives the polling workflow.

These cover the F2 additions that bring it to F1 parity — the moment qualifying
publishes, the model conditions on the real grid; the moment a result publishes,
the gate flags work pending — without ever depending on the live network (every
"live" feed here is a deterministic stub).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from f2_predictions import config, export, model, race_weekend as rw
from f2_predictions import refresh as f2refresh
from f2_predictions.datasource import F2DataSource
from f2_predictions.sources.composite import CompositeF2Source
from f2_predictions.sources.snapshot import SnapshotF2Source, load_snapshot
from f2_predictions.sources.synthetic import SyntheticF2Source

CODES = [d["code"] for d in config.DRIVERS]
NEXT = config.COMPLETED_ROUNDS + 1


# --------------------------------------------------------------------------- #
# Calendar-based detection (no snapshot, no network)
# --------------------------------------------------------------------------- #
def test_detect_target_round_is_calendar_based():
    # Round 6 (Austria) weekend is 2026-06-27/28; mid-week before it is "round 6".
    now = datetime(2026, 6, 25, 12, tzinfo=timezone.utc)
    assert rw.detect_target_round(2026, now) == 6
    # Saturday of the weekend is still round 6.
    assert rw.is_race_weekend(6, datetime(2026, 6, 27, 14, tzinfo=timezone.utc))
    # A week later it is not round 6's weekend any more.
    assert not rw.is_race_weekend(6, datetime(2026, 7, 10, tzinfo=timezone.utc))


def test_detect_pins_to_last_round_after_season():
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    assert rw.detect_target_round(2026, now) == len(config.CALENDAR)


# --------------------------------------------------------------------------- #
# Qualifying ingestion + provenance (real-only by construction)
# --------------------------------------------------------------------------- #
def test_snapshot_qualifying_round_trips(tmp_path):
    snap = {
        "season": 2026,
        "calendar": [{"round": 1, "completed": False}],
        "results": {},
        "qualifying": {"3": list(reversed(CODES))},
    }
    p = tmp_path / "official_2026.json"
    p.write_text(json.dumps(snap))
    load_snapshot.cache_clear()
    src = SnapshotF2Source(path=str(p))
    assert src.qualifying(2026, 3) == list(reversed(CODES))
    assert src.qualifying(2026, 4) is None  # absent → None
    load_snapshot.cache_clear()


def test_synthetic_has_no_qualifying_so_default_stays_honest():
    # The default (offline) source must NOT fabricate qualifying — otherwise the
    # site would claim a post-quali grid it never scraped.
    assert not hasattr(SyntheticF2Source(), "qualifying")
    src = F2DataSource(source=CompositeF2Source([SyntheticF2Source()]))
    assert src.qualifying(2026, NEXT) is None


class _StubQualiSource:
    """A real-feed stand-in that serves a fixed qualifying order."""

    name = "fia"

    def __init__(self, order):
        self._order = order

    def results(self, year, round, race_index=1):
        return None

    def qualifying(self, year, round):
        return list(self._order) if round == NEXT else None


def test_composite_prefers_real_qualifying():
    order = list(reversed(CODES))
    comp = CompositeF2Source([_StubQualiSource(order), SyntheticF2Source()])
    src = F2DataSource(source=comp)
    assert src.qualifying(2026, NEXT) == order


# --------------------------------------------------------------------------- #
# Grid-aware (post-quali) forecast conditions on the real grid
# --------------------------------------------------------------------------- #
def test_forecast_conditions_on_known_grid():
    src = F2DataSource()
    pre = model.forecast_round(src, 2026, NEXT, n_samples=2000)
    upset = list(reversed(pre.feature.grid))  # actual quali ≠ predicted merit
    post = model.forecast_round(src, 2026, NEXT, n_samples=2000, known_grid=upset)
    # Feature grid is now the real qualifying order.
    assert post.feature.grid == upset
    # Sprint grid is the reverse of the real feature top-10.
    assert post.sprint.grid[:10] == upset[:10][::-1]
    # Pole now has a materially better win chance than in the pure-pace pre-quali run.
    pole = upset[0]
    assert post.feature.markets.p_win[pole] > pre.feature.markets.p_win[pole]
    # Both heads remain full, valid permutations.
    for race in (post.feature, post.sprint):
        assert sorted(race.grid) == sorted(CODES)
        assert sorted(race.order) == sorted(CODES)


def test_partial_grid_completes_to_full_permutation():
    merit = sorted(CODES)
    grid = model._complete_grid([CODES[5], CODES[2], "ZZZ", CODES[5]], merit)
    assert sorted(grid) == sorted(CODES)  # full permutation
    assert grid[0] == CODES[5] and grid[1] == CODES[2]  # real order kept, deduped


# --------------------------------------------------------------------------- #
# export wires the post-quali phase into the season summary
# --------------------------------------------------------------------------- #
def test_build_payload_marks_post_quali():
    src = F2DataSource()
    grid = list(reversed(sorted(CODES)))
    fcs = {
        r: model.forecast_round(src, 2026, r, n_samples=1500, known_grid=grid if r == NEXT else None)
        for r in range(1, len(config.CALENDAR) + 1)
    }
    post = export.build_payload(fcs, src, 2026, known_grid=grid)
    assert post["nextPrediction"]["phase"] == "post-quali"
    assert post["nextPrediction"]["qualifyingActual"] is True
    assert [e["code"] for e in post["nextPrediction"]["qualifying"]] == grid

    pre = export.build_payload(fcs, src, 2026, known_grid=None)
    assert pre["nextPrediction"]["phase"] == "pre"
    assert pre["nextPrediction"]["qualifyingActual"] is False


# --------------------------------------------------------------------------- #
# Freshness gate — phase + work-pending against a stub live feed
# --------------------------------------------------------------------------- #
class _StubLive:
    """Stub live feed: serves a feature result and/or qualifying for one round."""

    def __init__(self, *, feature=None, quali=None, round=NEXT):
        self._feature, self._quali, self._round = feature, quali, round

    def results(self, year, round, race_index=1):
        return self._feature if round == self._round and race_index == 1 else None

    def qualifying(self, year, round):
        return self._quali if round == self._round else None


def test_phase_pre_when_nothing_published():
    assert rw.weekend_phase(NEXT, 2026, live=_StubLive()) == "pre"


def test_phase_post_quali_then_post_race():
    quali = list(reversed(CODES))
    assert rw.weekend_phase(NEXT, 2026, live=_StubLive(quali=quali)) == "post-quali"
    result = [type("R", (), {"competitor": c})() for c in CODES]
    assert rw.weekend_phase(NEXT, 2026, live=_StubLive(feature=result, quali=quali)) == "post-race"


def test_refresh_refuses_to_regress_a_healthy_snapshot(tmp_path, monkeypatch):
    """The exact failure that shipped an empty snapshot to main: a transient empty
    live scrape must NOT overwrite a healthy committed snapshot."""
    out = tmp_path / "official_2026.json"
    good = {"season": 2026, "completedRounds": 5, "results": {"1": {}}, "driverStandings": [1]}
    out.write_text(json.dumps(good))

    # Simulate the live scrape coming back empty (site down / restructured).
    monkeypatch.setattr(
        f2refresh, "build_snapshot", lambda season: {"season": 2026, "completedRounds": 0, "results": {}}
    )
    monkeypatch.setattr("sys.argv", ["refresh", "--season", "2026", "--out", str(out)])
    with pytest.raises(SystemExit) as exc:
        f2refresh.main()
    assert exc.value.code == 0
    # The healthy snapshot survived untouched.
    assert json.loads(out.read_text())["completedRounds"] == 5


def test_work_pending_detects_fresh_quali_and_result():
    # Fresh qualifying the snapshot lacks → work pending.
    assert rw.check_work_pending(NEXT, 2026, live=_StubLive(quali=list(reversed(CODES))))
    # Fresh feature result for an uncompleted round → work pending.
    result = [type("R", (), {"competitor": c})() for c in CODES]
    assert rw.check_work_pending(NEXT, 2026, live=_StubLive(feature=result))
    # Nothing fresh → no work.
    assert not rw.check_work_pending(NEXT, 2026, live=_StubLive())
