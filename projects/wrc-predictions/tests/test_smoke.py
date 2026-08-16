"""Import smoke test — the cheapest check that the package is importable.

The substantive contract, no-fabrication and leakage tests live in
`test_contract.py`. This file stays because an import error is worth a
one-line failure rather than fifteen.
"""


def test_imports():
    from wrc_predictions import config  # noqa: F401
    from wrc_predictions.datasource import WRCDataSource  # noqa: F401
    from wrc_predictions.predict import WRCPredictor  # noqa: F401
    from wrc_predictions.sources import snapshot  # noqa: F401
