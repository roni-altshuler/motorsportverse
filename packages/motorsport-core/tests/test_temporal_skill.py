import numpy as np
import pytest

from motorsport_core.temporal_skill import predict_temporal_skill
from motorsport_core.calibration import ProbabilityCalibrator, StratifiedProbabilityCalibrator


def test_features_stop_before_label_round_and_validation_is_a_whole_event():
    calls = []
    def features(rounds):
        calls.append(('features', tuple(rounds)))
        return {str(i): {'roll_mean_finish': float(i + 1), 'trend': -0.2} for i in range(12)}
    def actual(rnd):
        calls.append(('actual', rnd))
        return {str(i): float(12 - i) for i in range(12)}
    result = predict_temporal_skill([1, 2, 3, 4], ['roll_mean_finish', 'trend'], features, actual)
    assert result.validation_round == 4
    assert result.training_rounds == [2, 3]
    assert calls == [('features', (1,)), ('actual', 2), ('features', (1, 2)), ('actual', 3),
                     ('features', (1, 2, 3)), ('actual', 4), ('features', (1, 2, 3, 4))]
    assert len(result.predictions) == 12
    assert all(np.isfinite(list(result.predictions.values())))


def test_perfect_baseline_keeps_zero_learned_weight():
    def features(rounds):
        return {str(i): {'roll_mean_finish': float(i + 1)} for i in range(12)}
    result = predict_temporal_skill([1, 2, 3], ['roll_mean_finish'], features,
                                    lambda rnd: {str(i): float(i + 1) for i in range(12)})
    assert result.learned_weight == 0
    assert result.validation_baseline_mae == 0


def test_insufficient_history_never_fits_in_sample():
    assert predict_temporal_skill([1, 2], ['roll_mean_finish'], lambda _: {}, lambda _: {}) is None


@pytest.mark.parametrize('cls', [ProbabilityCalibrator, StratifiedProbabilityCalibrator])
def test_refitting_shorter_history_cannot_retain_future_calibration(cls):
    history = [{'market': 'win', 'predicted': i / 20, 'observed': i % 2, 'stratum': 'street'} for i in range(20)]
    cal = cls().fit_from_history(history)
    assert cal.is_fitted('win')
    cal.fit_from_history([])
    assert not cal.is_fitted()
    if isinstance(cal, StratifiedProbabilityCalibrator):
        assert cal.strata_with_models() == {}
    np.testing.assert_allclose(cal.transform('win', [.1, .7]), [.1, .7])


def test_fractional_observations_are_not_truncated_to_binary():
    cal = ProbabilityCalibrator().fit_from_history([
        {'market': 'win', 'predicted': i / 20, 'observed': .9} for i in range(20)])
    assert not cal.is_fitted()
