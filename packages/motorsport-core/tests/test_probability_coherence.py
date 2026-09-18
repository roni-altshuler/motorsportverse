import numpy as np
import pytest
from scipy.optimize import minimize

from motorsport_core.calibration import renormalize_market_struct, water_fill_to_target
from motorsport_core.probability_coherence import coherent_top_k


def test_joint_projection_matches_independent_constrained_optimizer():
    values = np.array([[.8, .5], [.1, .9], [.05, .8], [.05, .8]])
    repaired = coherent_top_k(values, [1, 3])
    optimum = minimize(lambda z: np.sum((z.reshape(4, 2) - values) ** 2),
                       np.full((4, 2), [.25, .75]).ravel(), method='SLSQP',
                       bounds=[(0, 1)] * 8,
                       constraints=[{'type': 'eq', 'fun': lambda z: z.reshape(4, 2).sum(0) - [1, 3]},
                                    {'type': 'ineq', 'fun': lambda z: np.diff(z.reshape(4, 2), axis=1).ravel()}],
                       options={'ftol': 1e-12})
    assert optimum.success
    np.testing.assert_allclose(repaired, optimum.x.reshape(4, 2), atol=1e-6)


@pytest.mark.parametrize('n', [2, 5, 20, 40])
def test_conserves_all_market_masses_bounds_and_nested_order(n):
    rng = np.random.default_rng(123)
    values = rng.random((n, 4))
    repaired = coherent_top_k(values, [1, 3, 6, 10], floor=.005)
    np.testing.assert_allclose(repaired.sum(0), np.minimum([1, 3, 6, 10], n), atol=1e-8)
    assert (repaired >= .005 - 1e-10).all() and (repaired <= 1).all()
    assert (np.diff(repaired, axis=1) >= -1e-9).all()
    np.testing.assert_allclose(coherent_top_k(values[::-1], [1, 3, 6, 10], floor=.005)[::-1], repaired, atol=1e-8)
    np.testing.assert_allclose(coherent_top_k(repaired, [1, 3, 6, 10], floor=.005), repaired, atol=1e-8)


def test_export_repairs_nested_markets_but_preserves_raw_and_missing_fields():
    raw = {'win': {'A': .8, 'B': .1, 'C': .05, 'D': .05},
           'podium': {'A': .5, 'B': .9, 'C': .8, 'D': .8}}
    payload = {m: {c: {'probability': p, 'rawProbability': p} for c, p in rows.items()} for m, rows in raw.items()}
    out = renormalize_market_struct(payload, digits=4)
    for code in raw['win']:
        assert out['win'][code]['probability'] <= out['podium'][code]['probability']
        assert out['win'][code]['rawProbability'] == raw['win'][code]
    assert set(out) == set(payload)
    assert payload['win']['A']['probability'] == .8


def test_zero_support_receives_residual_mass_after_favourites_saturate():
    np.testing.assert_allclose(water_fill_to_target([1, 0, 0], 2), [1, .5, .5])
    np.testing.assert_allclose(water_fill_to_target([1, 0, 0], 3), [1, 1, 1])


def test_nonfinite_values_cannot_escape_to_json():
    with pytest.raises(ValueError, match='finite'):
        coherent_top_k([[np.nan, 1]], [1, 3])
    with pytest.raises(ValueError, match='finite'):
        water_fill_to_target([np.inf, .2], 1)
