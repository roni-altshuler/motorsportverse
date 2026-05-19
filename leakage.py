"""Leakage prevention utilities.

The prediction pipeline aggregates prior-round results into features
(`PreviousPosition`, `SeasonMomentum`, `DriverPredictionBias`, ...).  If any
caller accidentally feeds in data from a round >= the round being predicted,
the model trains on its own future and reported metrics become meaningless.

The existing filter in `f1_prediction_utils._load_season_position_maps` already
drops rounds >= `current_round` when the parameter is passed, but there is no
machine-checked assertion that catches a call site that forgets the parameter
or passes the wrong value.  This module is that assertion.

Usage in the pipeline:

    from leakage import assert_prior_only, LeakageError

    assert_prior_only(combined_results, current_round=current_round,
                      label="combined_results")

Test usage (see tests/test_leakage.py):

    with pytest.raises(LeakageError):
        assert_prior_only({"7": {...}}, current_round=5, label="...")
"""

from __future__ import annotations

from typing import Iterable, Mapping


class LeakageError(AssertionError):
    """Raised when a feature aggregator is fed data from the target round or later."""


def _coerce_round(key: object) -> int | None:
    try:
        return int(key)
    except (TypeError, ValueError):
        return None


def assert_prior_only(
    rounds_map: Mapping[object, object] | None,
    current_round: int,
    label: str = "rounds_map",
) -> None:
    """Assert `rounds_map` contains no keys >= current_round.

    Parameters
    ----------
    rounds_map
        Dict keyed by round number (int or str-coerced).  None is allowed
        (treated as empty); the caller may not yet have any history.
    current_round
        The round being predicted.  All keys must be strictly less than this.
    label
        Human-readable name used in the error message; pass the variable name
        so failures point at the right call site.

    Raises
    ------
    LeakageError
        If any key in `rounds_map` is >= current_round.
    """
    if rounds_map is None:
        return
    if not isinstance(current_round, int) or current_round < 1:
        raise LeakageError(
            f"current_round must be a positive int; got {current_round!r}"
        )
    offenders: list[int] = []
    for key in rounds_map.keys():
        rnd = _coerce_round(key)
        if rnd is None:
            continue
        if rnd >= current_round:
            offenders.append(rnd)
    if offenders:
        raise LeakageError(
            f"{label} contains round(s) {sorted(offenders)} >= current_round "
            f"{current_round}. Features built from this data would leak the target."
        )


def filter_prior_only(
    rounds_map: Mapping[object, object] | None,
    current_round: int,
) -> dict:
    """Defensive filter: return only keys < current_round.

    Use this when a call site cannot guarantee its input is clean (e.g. when
    consuming user-provided JSON).  Within the pipeline prefer
    `assert_prior_only` so violations surface as bugs instead of being silently
    masked.
    """
    if not rounds_map:
        return {}
    out: dict = {}
    for key, value in rounds_map.items():
        rnd = _coerce_round(key)
        if rnd is not None and rnd < current_round:
            out[str(rnd)] = value
    return out


def assert_seasons_prior_only(
    rows: Iterable[Mapping[str, object]],
    current_season: int,
    current_round: int,
    season_key: str = "season",
    round_key: str = "round",
    label: str = "rows",
) -> None:
    """Multi-season variant: assert no row has (season, round) >= target.

    Used when training spans multiple seasons.  A row in season S < current_season
    is always prior; a row in season S == current_season must have round < current_round.
    """
    offenders: list[tuple[int, int]] = []
    for row in rows:
        season = row.get(season_key)
        rnd = row.get(round_key)
        try:
            season_i = int(season)  # type: ignore[arg-type]
            rnd_i = int(rnd)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if season_i > current_season or (
            season_i == current_season and rnd_i >= current_round
        ):
            offenders.append((season_i, rnd_i))
    if offenders:
        raise LeakageError(
            f"{label} contains (season, round) tuples {sorted(set(offenders))} "
            f">= target ({current_season}, {current_round}). Training on this "
            f"data would leak future information."
        )
