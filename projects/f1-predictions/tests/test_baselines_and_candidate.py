"""Unit tests for the naive-baseline module, the probability-coherence
renormalizer, and the A/B candidate re-ranker components (2026-07 overhaul)."""
import json

import numpy as np
import pytest

from baselines import (
    baseline_order_streams,
    compute_season_baselines,
)
from models.calibration import renormalize_market_struct
from models.candidate_model import (
    candidate_ablation,
    candidate_enabled,
    collect_season_reliability,
    compute_dnf_probabilities,
    dnf_composed_mean_finish,
)


# ── fixtures: a tiny two-round season on disk ───────────────────────────────

def _write_round(rounds_dir, rnd, grid, status):
    payload = {
        "round": rnd,
        "gpKey": f"GP{rnd}",
        "classification": [
            {"driver": d, "position": i + 1, "team": f"T{d}"}
            for i, d in enumerate(grid)
        ],
        "actualStatus": status,
        "weekendResults": {
            "sessions": [
                {
                    "key": "qualifying",
                    "rows": [
                        {"driver": d, "position": i + 1}
                        for i, d in enumerate(grid)
                    ],
                }
            ]
        },
    }
    (rounds_dir / f"round_{rnd:02d}.json").write_text(json.dumps(payload))


@pytest.fixture()
def season_dir(tmp_path):
    data = tmp_path / "data"
    rounds = data / "rounds"
    rounds.mkdir(parents=True)
    # R1: grid A,B,C,D — A wins; D retires.
    _write_round(rounds, 1, ["A", "B", "C", "D"], {"A": "1", "B": "2", "C": "3", "D": "R"})
    # R2: grid B,A,C,D — B wins.
    _write_round(rounds, 2, ["B", "A", "C", "D"], {"B": "1", "A": "2", "C": "3", "D": "4"})
    results = {
        "1": {"A": 1, "B": 2, "C": 3, "D": 4},
        "2": {"B": 1, "A": 2, "C": 3, "D": 4},
    }
    (data / "season_results_2026.json").write_text(json.dumps(results))
    return data


# ── baselines ────────────────────────────────────────────────────────────────

def test_grid_baseline_scores_each_round(season_dir):
    out = compute_season_baselines(str(season_dir), 2026)
    grid = out["gridOrder"]
    assert grid["season"]["roundsScored"] == 2
    assert grid["perRound"]["1"]["winnerHit"] is True   # pole A won R1
    assert grid["perRound"]["2"]["winnerHit"] is True   # pole B won R2
    assert out["poleSitter"]["season"]["winnerHits"] == 2


def test_points_leader_baseline_uses_prior_rounds_only(season_dir):
    out = compute_season_baselines(str(season_dir), 2026)
    leader = out["pointsLeader"]
    # R1 has no prior standings → not scored; R2 leader is A (won R1) but B won.
    assert "1" not in leader["perRound"]
    assert leader["perRound"]["2"]["predictedWinner"] == "A"
    assert leader["perRound"]["2"]["winnerHit"] is False


def test_baseline_order_streams_are_leakage_safe(season_dir):
    streams = baseline_order_streams(str(season_dir), 2026)
    # standings_order for round 2 must reflect ONLY round 1 results.
    assert 1 not in streams["standings_order"]  # nothing before R1
    r2 = streams["standings_order"][2]
    assert r2["A"] == 1  # A leads after winning R1
    # grid stream = the real quali grids.
    assert streams["grid_order"][1]["A"] == 1
    assert streams["grid_order"][2]["B"] == 1


def test_dnf_driver_does_not_score_points(season_dir):
    """R1's D retired: even though season_results carries a position, D must
    not accumulate championship points for the standings baseline."""
    streams = baseline_order_streams(str(season_dir), 2026)
    r2 = streams["standings_order"][2]
    assert r2["D"] == 4  # zero points → last


# ── probability coherence ───────────────────────────────────────────────────

def _struct(market, probs):
    return {market: {d: {"probability": p, "rawProbability": p} for d, p in probs.items()}}


def test_renormalize_win_market_sums_to_one():
    struct = _struct("win", {"A": 0.5, "B": 0.5, "C": 0.4, "D": 0.4})  # sums 1.8
    out = renormalize_market_struct(struct)
    total = sum(v["probability"] for v in out["win"].values())
    assert abs(total - 1.0) < 1e-9


def test_renormalize_caps_at_one_and_waterfills():
    # Podium: target 3. One dominant driver would exceed 1.0 after scaling.
    struct = _struct("podium", {"A": 0.9, "B": 0.1, "C": 0.1, "D": 0.1, "E": 0.1})
    out = renormalize_market_struct(struct)
    probs = {d: v["probability"] for d, v in out["podium"].items()}
    assert all(p <= 1.0 + 1e-9 for p in probs.values())
    assert abs(sum(probs.values()) - 3.0) < 1e-6
    assert probs["A"] == pytest.approx(1.0)


def test_renormalize_is_noop_for_coherent_input():
    struct = _struct("win", {"A": 0.6, "B": 0.3, "C": 0.1})
    out = renormalize_market_struct(struct)
    assert out["win"]["A"]["probability"] == pytest.approx(0.6)
    assert out["win"]["A"]["rawProbability"] == pytest.approx(0.6)


def test_renormalize_preserves_raw_probability():
    struct = _struct("win", {"A": 0.9, "B": 0.9})
    out = renormalize_market_struct(struct)
    assert out["win"]["A"]["rawProbability"] == pytest.approx(0.9)
    assert out["win"]["A"]["probability"] == pytest.approx(0.5)


# ── candidate model components ───────────────────────────────────────────────

def test_candidate_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("F1_CANDIDATE_MODEL", raising=False)
    assert candidate_enabled() is False


def test_candidate_ablation_parsing(monkeypatch):
    monkeypatch.setenv("F1_CANDIDATE_ABLATION", "quali_gap, dnf")
    assert candidate_ablation() == ("quali_gap", "dnf")
    # Default = the promoted A2 config; dnf is opt-in (rejected by the
    # walk-forward ablation for the point prediction).
    monkeypatch.delenv("F1_CANDIDATE_ABLATION", raising=False)
    assert candidate_ablation() == ("quali_gap", "circuit_priors")


def test_collect_season_reliability_excludes_current_round(season_dir):
    rel = collect_season_reliability(2, rounds_dir=season_dir / "rounds")
    assert rel["rounds_seen"] == 1        # only R1, never R2 itself
    assert rel["driver_dnfs"]["D"] == 1   # D retired in R1
    assert rel["total_starts"] == 4


def test_collect_season_reliability_round1_cold_start(season_dir):
    rel = collect_season_reliability(1, rounds_dir=season_dir / "rounds")
    assert rel["rounds_seen"] == 0
    assert rel["total_starts"] == 0


def test_dnf_probabilities_shrink_and_order(season_dir):
    rel = collect_season_reliability(2, rounds_dir=season_dir / "rounds")
    teams = {"A": "TA", "B": "TB", "C": "TC", "D": "TD"}
    probs = compute_dnf_probabilities(["A", "B", "C", "D"], teams, rel,
                                      circuit_prior={"dnfRate": 0.2, "races": 4})
    assert set(probs) == {"A", "B", "C", "D"}
    assert all(0.04 <= p <= 0.40 for p in probs.values())
    # The driver who retired must carry more DNF risk than one who didn't.
    assert probs["D"] > probs["A"]


def test_dnf_composition_orders_survivors_by_strength():
    strength = np.array([3.0, 2.0, 1.0, 0.0])
    p_dnf = np.zeros(4)
    mf = dnf_composed_mean_finish(strength, p_dnf, n_samples=50)
    assert list(np.argsort(mf)) == [0, 1, 2, 3]
    assert mf[0] == pytest.approx(1.0)


def test_dnf_composition_penalises_fragile_leader():
    # Two equally-fast cars; the fragile one must average a worse finish.
    strength = np.array([1.0, 1.0 - 1e-9, 0.0, -1.0])
    p_dnf = np.array([0.5, 0.0, 0.0, 0.0])
    mf = dnf_composed_mean_finish(strength, p_dnf, n_samples=2000)
    assert mf[0] > mf[1]


def test_dnf_composition_is_deterministic():
    strength = np.array([1.0, 0.5, 0.0])
    p_dnf = np.array([0.1, 0.2, 0.3])
    a = dnf_composed_mean_finish(strength, p_dnf, n_samples=200)
    b = dnf_composed_mean_finish(strength, p_dnf, n_samples=200)
    assert np.allclose(a, b)
