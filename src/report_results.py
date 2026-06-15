"""
report_results.py
=================
Generate a full race-results report for the configured-season Australian Grand Prix.

Outputs:
  1. Predicted finishing order with championship points (P1–P22)
  2. ML model evaluation statistics (MAE, RMSE, R²)
  3. Additional model diagnostics

Uses cached FastF1 data, so runs in seconds.
"""

from f1_prediction_utils import *

# ── Pipeline (cached — fast) ─────────────────────────────────────────────
enable_cache()

GP_NAME         = "Australia"
GP_DISPLAY_NAME = "Australian Grand Prix"
GP_YEARS        = [2023, 2024, 2025]
GP_ROUND        = 1

laps         = load_multi_year_data(GP_NAME, years=GP_YEARS)
driver_stats = aggregate_driver_stats(laps)
grid         = build_grid_dataframe()
merged       = build_training_dataset(grid, driver_stats,
                                      circuit_key=GP_NAME,
                                      current_round=GP_ROUND)

QUALIFYING_ESTIMATES = {
    "VER": 74.80, "HAD": 75.70, "NOR": 74.95, "PIA": 74.90,
    "LEC": 75.05, "HAM": 75.20, "RUS": 75.10, "ANT": 75.35,
    "ALO": 76.00, "STR": 76.30, "GAS": 75.80, "COL": 76.40,
    "ALB": 75.60, "SAI": 75.50, "LAW": 75.30, "LIN": 76.50,
    "OCO": 76.10, "BEA": 76.00, "HUL": 76.20, "BOR": 76.60,
    "PER": 75.40, "BOT": 76.35,
}
quali   = get_qualifying_or_estimates(SEASON_YEAR, GP_NAME, QUALIFYING_ESTIMATES)
merged  = apply_qualifying_data(merged, quali, rain_probability=0.10, temperature_c=25.0)

results = train_ensemble(merged, max_spread_s=3.5)  # v2: calibrated spread
merged  = results["merged"]
metrics = evaluate_models(results)

# ── 1. FULL RACE CLASSIFICATION WITH POINTS ──────────────────────────────
classification = predicted_classification(merged, GP_DISPLAY_NAME)

# ── 2. CONSTRUCTOR POINTS FROM THIS RACE ─────────────────────────────────
constructor_pts = (
    classification.groupby("Team")["Points"]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)
constructor_pts.columns = ["Team", "Points"]
constructor_pts.index += 1
constructor_pts.index.name = "Pos"

print(f"\n  🏗️  CONSTRUCTOR STANDINGS — {SEASON_YEAR} AUSTRALIAN GP")
print("  " + "-" * 40)
for pos, row in constructor_pts.iterrows():
    print(f"  {pos:>3}.  {row['Team']:<18s}  {row['Points']:>3} pts")
print()

# ── 4. ML MODEL STATISTICS ───────────────────────────────────────────────
print("=" * 90)
print("  📊  ML MODEL EVALUATION — TEST SET METRICS")
print("=" * 90)
print()
print(f"  {'Model':<30s}  {'MAE (s)':>10}  {'RMSE (s)':>10}  {'R²':>8}")
print("  " + "-" * 64)
for _, r in metrics.iterrows():
    print(f"  {r['Model']:<30s}  {r['MAE (s)']:>10.4f}  {r['RMSE (s)']:>10.4f}  "
          f"{r['R²']:>8.4f}")
print("  " + "-" * 64)

# Additional diagnostics
X_imp = results["X_imputed"]
y_imp = results["y_imputed"]
gb_model  = results["gb_model"]
xgb_model = results["xgb_model"]

print("\n  📐  ADDITIONAL MODEL DIAGNOSTICS")
print("  " + "-" * 64)
print(f"  Training samples         : {len(results['X_imputed']) - len(results['X_test'])}")
print(f"  Test samples             : {len(results['X_test'])}")
print(f"  Total samples            : {len(results['X_imputed'])}")
print(f"  Features used            : {len(results['feature_cols'])}")
print(f"  Feature names            : {', '.join(results['feature_cols'])}")
print()

# Feature importance comparison
print("  📈  FEATURE IMPORTANCE (Ensemble avg)")
print("  " + "-" * 50)
feat_imp_gb  = gb_model.feature_importances_
feat_imp_xgb = xgb_model.feature_importances_
feat_imp_avg = (feat_imp_gb + feat_imp_xgb) / 2
feat_names   = results["feature_cols"]

# Sort by importance
sorted_idx = np.argsort(feat_imp_avg)[::-1]
for rank, idx in enumerate(sorted_idx, 1):
    bar = "█" * int(feat_imp_avg[idx] * 40)
    print(f"  {rank}. {feat_names[idx]:<25s}  {feat_imp_avg[idx]:.4f}  {bar}")

print()

# Prediction spread
pred_times = merged["PredictedLapTime"]
print("  📊  PREDICTION SPREAD")
print("  " + "-" * 50)
print(f"  Fastest predicted time   : {pred_times.min():.3f}s  "
      f"({classification.iloc[0]['Driver']} — {classification.iloc[0]['DriverName']})")
print(f"  Slowest predicted time   : {pred_times.max():.3f}s  "
      f"({classification.iloc[-1]['Driver']} — {classification.iloc[-1]['DriverName']})")
print(f"  Spread (max - min)       : {pred_times.max() - pred_times.min():.3f}s")
print(f"  Mean predicted time      : {pred_times.mean():.3f}s")
print(f"  Std dev                  : {pred_times.std():.3f}s")
print("=" * 90)
# ── 5. HTML REPORT ────────────────────────────────────────────────────────
print("\n📄 Generating HTML report …")
report_path = generate_html_report(
    classification, metrics, results, merged,
    gp_name=GP_DISPLAY_NAME, circuit_key=GP_NAME, gp_round=GP_ROUND,
)
print(f"✅ Report saved to {report_path}")
print("\n✅ Report complete.")
