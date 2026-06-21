"""Circuit-conditioned grid prior + win-probability coherence.

These guard the rule the model must follow on every round: the pole-sitter has
the best chance of winning, and *how much* best depends on the circuit — strong
on hard-to-pass tracks (Monaco), light on open tracks (Bahrain). They also guard
the coherence fix: the predicted winner always holds the highest win probability.
"""
import numpy as np
import pandas as pd

from f1_prediction_utils import apply_race_postprocessing, circuit_grid_dynamics


def test_grid_dynamics_track_modulation():
    # Monaco (overtaking 0.1) vs Bahrain (overtaking 0.8), both dry.
    monaco_lock, monaco_k = circuit_grid_dynamics(0.1, 0.75, 0.0)
    bahrain_lock, bahrain_k = circuit_grid_dynamics(0.8, 0.40, 0.0)

    # Harder to pass -> grid matters more and the win decays faster (sharper
    # favourite).
    assert monaco_lock > bahrain_lock
    assert monaco_k < bahrain_k


def test_rain_softens_the_grid_lock():
    dry_lock, dry_k = circuit_grid_dynamics(0.1, 0.75, 0.0)
    wet_lock, wet_k = circuit_grid_dynamics(0.1, 0.75, 0.8)
    # Rain scrambles the order: less grid lock, wider win spread.
    assert wet_lock < dry_lock
    assert wet_k > dry_k


def _synthetic_field(n=8):
    """A field with near-identical pace so the grid prior is the deciding term.

    Driver i starts P(i+1); every pace/form signal is flat across the field, so
    any separation in the predicted order comes from the grid prior, not noise.
    """
    base = 90.0
    rank = np.arange(1, n + 1, dtype=float)
    df = pd.DataFrame({
        "Driver": [f"D{i:02d}" for i in range(n)],
        "PredictedLapTime": np.full(n, base),
        "PredictedLapTime_GB": np.full(n, base),
        "PredictedLapTime_XGB": np.full(n, base),
        "AdjustedQualiTime": base + (rank - 1) * 0.05,   # pole fastest
        "QualifyingRank": rank,
        "GridAdvantage": -(rank - rank.mean()) * 0.05,
        "CleanAirPace": np.full(n, base),
        "CurrentForm": np.zeros(n),
        "PreviousPosition": rank,
        "PositionTrend": np.zeros(n),
        "ConsistencyScore": np.full(n, 0.1),
        "PitTimeLoss": np.full(n, 22.0),
        "TyreDegFactor": np.full(n, 0.5),
        "SeasonMomentum": np.zeros(n),
    })
    return df


def test_pole_is_favourite_and_winner_matches_win_probability():
    out = apply_race_postprocessing(_synthetic_field(), circuit_key="Monaco")
    out = out.sort_values("RaceProjectionTime").reset_index(drop=True)

    # The pole-sitter (QualifyingRank == 1) is predicted to win.
    assert out.loc[0, "QualifyingRank"] == 1

    # Predicted winner holds the highest win probability — order and odds agree.
    assert out.loc[0, "WinProbability"] == out["WinProbability"].max()

    # Win probability decays monotonically down the predicted order.
    wp = out["WinProbability"].to_numpy()
    assert np.all(np.diff(wp) <= 1e-9)

    # It is a real favourite, not the old ~uniform line.
    assert out.loc[0, "WinProbability"] > 100.0 / len(out) * 1.8


def test_pole_advantage_scales_with_circuit():
    field = _synthetic_field()
    monaco = apply_race_postprocessing(field.copy(), circuit_key="Monaco")
    bahrain = apply_race_postprocessing(field.copy(), circuit_key="Bahrain")

    def pole_win(df):
        return df.loc[df["QualifyingRank"] == 1, "WinProbability"].iloc[0]

    # Same field: the pole-sitter's win chance is materially higher on the
    # hard-to-pass circuit than on the open one.
    assert pole_win(monaco) > pole_win(bahrain)
