"""Bet sizing primitives: Kelly, expected value, portfolio capping.

This module is *purely* arithmetic — no I/O, no network, no random.  Wiring it
this way keeps the unit tests fast and means the same functions are used by
both the live `export_value_data.py` exporter and the historical `backtest.py`
replay.

Design choices:

* Fractional Kelly (default 0.25x) by convention — full Kelly is theoretically
  growth-optimal but with the variance of an F1 race week, real-money sizing
  using it is reckless.  The fraction is a CLI / call argument, not a constant.
* `cap_portfolio` accepts arbitrary opportunity dicts and only inspects /
  mutates the `kellyFraction` field; the rest of the dict is left untouched.
  That lets the exporter and backtester share this function without coupling
  to either's schema.
* Negative-edge bets return Kelly = 0, never short / fade.  We're not a hedge
  fund.
"""
from __future__ import annotations

from typing import Iterable


def kelly_fraction(p: float, decimal_odds: float, fraction: float = 0.25) -> float:
    """Fractional Kelly stake as a fraction of bankroll.

    Parameters
    ----------
    p
        Model probability of the bet winning, in [0, 1].
    decimal_odds
        European-style decimal odds (e.g. 2.50 means a 1-unit stake returns 2.5
        units on win, including stake — net profit 1.5 units).  Must be > 1.
    fraction
        Multiplier on the full-Kelly result.  Typical 0.25 (quarter-Kelly).

    Returns
    -------
    float
        Fraction of bankroll to stake.  Always in [0, fraction].  Returns 0
        if the expected value is non-positive (no edge) or if inputs are
        degenerate.
    """
    if not (0.0 <= p <= 1.0):
        return 0.0
    if decimal_odds <= 1.0:
        return 0.0
    b = decimal_odds - 1.0
    # Full Kelly: f* = (p*(b+1) - 1) / b
    full = (p * (b + 1.0) - 1.0) / b
    if full <= 0.0:
        return 0.0
    return full * fraction


def expected_value(p: float, decimal_odds: float) -> float:
    """Expected value per unit stake.

    EV = p * (odds - 1) - (1 - p) * 1.  Positive => +EV bet.
    """
    if not (0.0 <= p <= 1.0) or decimal_odds <= 1.0:
        return 0.0
    return p * (decimal_odds - 1.0) - (1.0 - p)


def cap_portfolio(
    opportunities: list[dict],
    per_bet_cap: float = 0.05,
    total_cap: float = 0.30,
) -> list[dict]:
    """Clip and rescale a portfolio of bets so it respects sizing caps.

    Two caps are applied, in order:

    1. **Per-bet cap**: each `kellyFraction` is clipped to `per_bet_cap`.
       Hard ceiling: no single bet eats more than 5% of bankroll by default,
       no matter how strong the edge.
    2. **Total cap**: if the sum of post-clip fractions still exceeds
       `total_cap`, *all* fractions are scaled down proportionally so the
       total equals exactly `total_cap`.  Relative sizing within the
       portfolio is preserved.

    Each input dict is treated as immutable from the caller's perspective —
    we return new dicts with the `kellyFraction` field replaced.  Other
    fields are forwarded unchanged.

    Notes on order of operations:
    - We clip first, then rescale.  This means a 20% raw Kelly bet is first
      clipped to 5%, then potentially scaled further if total still > 30%.
    - If `total_cap` >= sum after clip, no rescale happens (rescale only
      shrinks, never grows).
    """
    if not opportunities:
        return []
    if per_bet_cap < 0 or total_cap < 0:
        raise ValueError("Caps must be non-negative.")

    # Step 1: per-bet clip.
    clipped: list[dict] = []
    for op in opportunities:
        new_op = dict(op)
        k = float(new_op.get("kellyFraction") or 0.0)
        if k < 0.0:
            k = 0.0
        if k > per_bet_cap:
            k = per_bet_cap
        new_op["kellyFraction"] = k
        clipped.append(new_op)

    # Step 2: total cap rescale.
    total = sum(op["kellyFraction"] for op in clipped)
    if total > total_cap and total > 0.0:
        scale = total_cap / total
        for op in clipped:
            op["kellyFraction"] = op["kellyFraction"] * scale

    return clipped


def total_exposure(opportunities: Iterable[dict]) -> float:
    """Sum the `kellyFraction` field across the portfolio.  Convenience helper."""
    return sum(float(op.get("kellyFraction") or 0.0) for op in opportunities)
