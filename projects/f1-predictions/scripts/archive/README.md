# Archived analysis scripts

One-off exploratory / benchmarking scripts kept for reference but no longer part
of the active pipeline. They are **not** wired into CI, the cron workflows, or
the test suite, and are excluded from `ruff check .` (see `pyproject.toml`).

| Script | What it was for |
|---|---|
| `benchmark_gbm_libraries.py` | One-time XGBoost vs LightGBM comparison. |
| `optuna_hp_search.py` | Exploratory hyperparameter search (not part of the trained pipeline). |
| `shap_ablation.py` | One-off SHAP feature-importance ablation study. |

If you revive one of these, move it back to the repo root (or a proper
`scripts/` location) and re-include it in linting.
