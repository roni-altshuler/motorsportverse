import json
from dataclasses import asdict

import pytest

from motorsport_core.promotion import evaluate_promotion


def test_trailing_window_must_itself_meet_sample_floor():
    scores = [(r, 4.0) for r in range(20)]
    result = evaluate_promotion(scores, [(r, 3.0) for r in range(20)], trailing_window=3)
    assert result.decision == 'hold'
    assert result.rounds_compared == 3


def test_noisy_average_win_is_not_a_demonstrated_improvement():
    prod = [(r, 4.0) for r in range(5)]
    cand = list(enumerate([2.0, 4.6, 4.6, 4.6, 3.5]))
    result = evaluate_promotion(prod, cand)
    assert result.relative_change < -0.02
    assert result.improvement_ci_low < 0 < result.improvement_ci_high
    assert result.decision == 'hold'


def test_regression_against_perfect_round_blocks_promotion_and_serializes():
    result = evaluate_promotion(list(enumerate([0, 4, 4, 4, 4])), list(enumerate([1, 2, 2, 2, 2])))
    assert result.blocked_by_per_round_guard
    assert result.decision == 'hold'
    json.dumps(asdict(result), allow_nan=False)


@pytest.mark.parametrize('invalid', [float('nan'), float('inf'), float('-inf'), -1, None, 'bad', True])
def test_invalid_scores_do_not_count_as_evidence(invalid):
    prod = [(r, 4.0) for r in range(5)]
    result = evaluate_promotion(prod, [(r, 3.0 if r < 4 else invalid) for r in range(5)])
    assert result.rounds_compared == 4
    assert result.decision == 'hold'


@pytest.mark.parametrize('kwargs', [{'trailing_window': 0}, {'min_rounds_to_decide': 0},
                                   {'relative_improvement_threshold': float('nan')},
                                   {'max_per_round_regression': -1}])
def test_invalid_gate_configuration_raises(kwargs):
    with pytest.raises(ValueError):
        evaluate_promotion([], [], **kwargs)
