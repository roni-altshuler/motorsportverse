"""Smoke test: every public module imports and exposes its key symbols."""


def test_top_level_import():
    import motorsport_core as mc

    assert mc.__version__


def test_all_modules_import():
    from motorsport_core import (  # noqa: F401
        calibration,
        conformal,
        drift,
        elo,
        era,
        eval,
        hierarchical_bayes,
        interfaces,
        leakage,
        promotion,
        registry,
        reliability,
    )
    from motorsport_core.features import competitor_history, skill_priors  # noqa: F401


def test_interfaces_reexport():
    from motorsport_core.interfaces import (
        Competitor,
        DataSource,
        MarketProbabilities,
        Predictor,
        RoundForecast,
        Venue,
    )

    c = Competitor(code="VER", name="Max Verstappen", team="Red Bull")
    assert c.code == "VER"
    assert issubclass(DataSource, object) and issubclass(Predictor, object)
    assert RoundForecast and Venue and MarketProbabilities
