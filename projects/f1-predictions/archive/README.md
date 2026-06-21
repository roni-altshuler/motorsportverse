# archive/

Superseded code kept for historical reference only. Nothing here is imported by
the live pipeline, run in CI, or linted/type-checked (it is excluded in
[`pyproject.toml`](../pyproject.toml)).

- **`F1PredictionFramework.py` / `.ipynb`** — the original notebook-derived
  prediction framework the project grew out of. The production pipeline now
  lives in the top-level modules (`f1_prediction_utils.py`, `advanced_models.py`,
  `export_website_data.py`, …) and the `models/` package. Retained so the
  project's starting point stays inspectable.
