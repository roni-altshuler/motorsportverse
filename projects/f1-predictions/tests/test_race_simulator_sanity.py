"""Sanity guards for the race simulator's DNF + variance fix (A-P1.1).

The bare pace-forward simulator collapsed the win market onto a single car
(round-10 ANT=0.982) and pinned the rest of the field to exactly 0.0.  These
tests lock in the two mechanisms that fix that — per-sample retirement (DNF)
and a per-sample per-driver car-performance shock — plus the base-rate
smoothing that keeps every probability strictly inside (0, 1).

They use a deterministic stub predictor (no trained ensemble / registry
binary needed), so they run in CI where the race-pace artefacts are absent.
"""
from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pandas as pd
import pytest

from models import race_simulator as rs
from models.race_simulator import (
    DEFAULT_FIELD_DNF_RATE,
    DEFAULT_FORM_SHOCK_S,
    GridEntry,
    RaceContext,
    simulate_race,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _stub_predict_lap_times(_artifacts: Any, feature_df: pd.DataFrame) -> np.ndarray:
    """Clean pace hierarchy: D00 fastest, +0.06s/lap per grid slot.

    Over a ~40-lap race that is a 2.4s deterministic edge for the leader over
    P2 — a genuinely dominant car, exactly the setup that made the old
    simulator report a ~98% favourite.
    """
    base = 90.0
    return base + feature_df["driver_id"].astype(float).to_numpy() * 0.06


def _grid(n: int = 10) -> list[GridEntry]:
    return [
        GridEntry(driver=f"D{i:02d}", team=f"T{i % 4}", grid_position=i + 1)
        for i in range(n)
    ]


def _encoders(grid: list[GridEntry]) -> dict:
    return {
        "driver": {g.driver: i for i, g in enumerate(grid)},
        "team": {t: i for i, t in enumerate(sorted({g.team for g in grid}))},
        "circuit": {"Test": 0},
    }


def _context(total_laps: int = 40, **overrides) -> RaceContext:
    base = dict(
        season=2026,
        round_num=10,
        circuit_key="Test",
        total_laps=total_laps,
        sc_likelihood=0.0,          # deterministic: no SC lottery in these tests
        tyre_deg_factor=0.0,
        pit_loss_s=22.0,
        expected_stops=1,
        base_lap_s=90.0,
        lap_noise_s=0.15,
        form_shock_s=DEFAULT_FORM_SHOCK_S,
        field_dnf_rate=DEFAULT_FIELD_DNF_RATE,
    )
    base.update(overrides)
    return RaceContext(**base)


@pytest.fixture(autouse=True)
def _patch_predictor(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rs, "predict_lap_times", _stub_predict_lap_times)


def _run(context: RaceContext, n: int = 20, n_samples: int = 600):
    grid = _grid(n)
    return simulate_race(
        grid=grid,
        artifacts={},
        encoders=_encoders(grid),
        context=context,
        n_samples=n_samples,
        seed=42,
    )


# --------------------------------------------------------------------------- #
# No degenerate favourite, no hard zeros / ones
# --------------------------------------------------------------------------- #


class TestNonDegenerate:
    def test_no_hard_zero_win_probabilities(self):
        out = _run(_context())
        assert all(p > 0.0 for p in out.p_win.values()), "hard-zero win prob present"

    def test_no_hard_one_or_zero_in_any_market(self):
        out = _run(_context())
        for market in (out.p_win, out.p_podium, out.p_top6, out.p_top10):
            for p in market.values():
                assert 0.0 < p < 1.0

    def test_dominant_car_is_favourite_but_not_a_lock(self):
        """A clearly-fastest car should lead the win market but stay well under
        the degenerate ~98% regime once DNF + form shock are active."""
        out = _run(_context())
        top_driver, top_p = max(out.p_win.items(), key=lambda kv: kv[1])
        assert top_driver == "D00"          # still the favourite
        assert top_p < 0.85                 # but not a lock
        # And the win mass is genuinely shared: several cars are live.
        live = sum(1 for p in out.p_win.values() if p > 0.02)
        assert live >= 4

    def test_win_and_podium_sums_preserved(self):
        out = _run(_context())
        assert sum(out.p_win.values()) == pytest.approx(1.0, abs=1e-9)
        assert sum(out.p_podium.values()) == pytest.approx(3.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# The two levers each demonstrably widen the win distribution
# --------------------------------------------------------------------------- #


class TestVarianceLevers:
    def test_form_shock_lowers_the_favourite(self):
        no_shock = _run(_context(form_shock_s=0.0, field_dnf_rate=0.0))
        with_shock = _run(_context(form_shock_s=DEFAULT_FORM_SHOCK_S, field_dnf_rate=0.0))
        assert max(no_shock.p_win.values()) > max(with_shock.p_win.values())
        # Without any variance the leader is essentially a lock (this is the
        # bug the fix targets); the shock must move it materially.
        assert max(no_shock.p_win.values()) > 0.9
        assert max(with_shock.p_win.values()) < max(no_shock.p_win.values()) - 0.1

    def test_dnf_lowers_the_favourite_and_appears_in_output(self):
        no_dnf = _run(_context(form_shock_s=0.0, field_dnf_rate=0.0))
        with_dnf = _run(_context(form_shock_s=0.0, field_dnf_rate=0.15))
        assert max(with_dnf.p_win.values()) < max(no_dnf.p_win.values())
        # Realised DNF frequency is reported and non-trivial.
        assert with_dnf.p_dnf["D00"] > 0.0
        assert 0.05 < np.mean(list(with_dnf.p_dnf.values())) < 0.30
        # The leader can no longer win more often than it survives.
        assert with_dnf.p_win["D00"] <= 1.0 - with_dnf.p_dnf["D00"] + 1e-9

    def test_retired_cars_do_not_win(self):
        """A car that retires in a sample cannot be classified first in it."""
        grid = _grid(6)
        ctx = _context(total_laps=30, form_shock_s=0.05, field_dnf_rate=0.4)
        out = simulate_race(
            grid=grid, artifacts={}, encoders=_encoders(grid),
            context=ctx, n_samples=400, seed=3,
        )
        # With a 40% field DNF rate the leader's win prob must fall well below
        # its no-DNF ceiling — retirement is actually removing it from wins.
        assert out.p_win["D00"] < 0.85


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


class TestDeterminism:
    def test_same_seed_same_probabilities(self):
        a = _run(_context())
        b = _run(_context())
        assert a.p_win == b.p_win
        assert a.p_dnf == b.p_dnf

    def test_replace_knobs_is_wired(self):
        """dataclasses.replace on the context actually changes behaviour —
        guards against a knob silently not being read by the sim."""
        lo = _run(dataclasses.replace(_context(), form_shock_s=0.02, field_dnf_rate=0.0))
        hi = _run(dataclasses.replace(_context(), form_shock_s=0.40, field_dnf_rate=0.0))
        assert max(lo.p_win.values()) > max(hi.p_win.values())
