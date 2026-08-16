"""Import smoke test — the cheapest check that the package is importable.

The substantive contract, no-fabrication and leakage tests live in
`test_contract.py`. This file stays because an import error is worth a
one-line failure rather than fifteen.
"""


def test_imports():
    from lemans_predictions import config  # noqa: F401
    from lemans_predictions.datasource import LeMansDataSource  # noqa: F401
    from lemans_predictions.predict import LeMansPredictor  # noqa: F401
    from lemans_predictions.sources import snapshot  # noqa: F401
