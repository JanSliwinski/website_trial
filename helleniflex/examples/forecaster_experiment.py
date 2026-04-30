"""HelleniFlex — full forecasting experiment on real Greek DAM data.

Trains four models (Naive, Ridge, LightGBM, Quantile LightGBM) on Jan 2025
through March 2026 and tests on April 2026 (held-out 30 days).
"""
import sys
import warnings
import os

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
import numpy as np

from helleniflex import (
    load_entsoe_prices_directory,
    load_entsoe_load_directory,
    load_entsoe_flows_directory,
    load_entsoe_total_generation_directory,
    load_entsoe_renewable_directory,
    FeatureBuilder,
    RidgeMLForecaster,
    GBMForecaster,
    QuantileGBMForecaster,
    forecast_metrics,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "entsoe")

print("=" * 75)
print(" HelleniFlex — Real-Data Forecasting Experiment")
print("=" * 75)

print("\n[1/4] Loading data")
prices = load_entsoe_prices_directory(D)
load = load_entsoe_load_directory(D)
flows = load_entsoe_flows_directory(D)
gen_total = load_entsoe_total_generation_directory(D)
wind = load_entsoe_renewable_directory(D, label="wind")
solar = load_entsoe_renewable_directory(D, label="solar")

print(
    f"  prices:    {len(prices):>6}  ({prices.index.min().date()} → {prices.index.max().date()})"
)
print(f"  load fcst: {load['load_forecast_mw'].notna().sum():>6}")
print(f"  wind DA:   {wind.iloc[:,0].notna().sum():>6}")
print(f"  solar DA:  {solar.iloc[:,0].notna().sum():>6}")
print(f"  flows:     {len(flows):>6}")
print(f"  gen total: {gen_total['gen_forecast_mw'].notna().sum():>6}")

print("\n[2/4] Building feature matrix")
builder = FeatureBuilder(
    prices=prices,
    load=load,
    wind=wind,
    solar=solar,
    flows=flows,
    gen_total=gen_total,
)
df = builder.build()
print(f"  raw shape: {df.shape}")

# Drop rows where critical features are NaN
df_clean = df.dropna(subset=["price_lag_14d", "load_forecast_mw"])
print(f"  after dropping rows with missing lag features: {df_clean.shape}")

# Coverage of optional features
print("  Feature coverage:")
for col in [
    "wind_da_forecast_mw",
    "solar_da_forecast_mw",
    "flow_net_import_mw",
    "gen_total_forecast_mw",
    "renewables_total_da_forecast_mw",
]:
    if col in df_clean.columns:
        n_valid = df_clean[col].notna().sum()
        pct = n_valid / len(df_clean) * 100
        print(f"    {col:42s} {n_valid:>7,d} / {len(df_clean):,d}  ({pct:5.1f}%)")

print("\n[3/4] Train / test split (last 30 days held out)")
train, test = builder.split_train_test(df_clean, test_days=30)
print(
    f"  train: {len(train):>6,d} rows ({train.index.min().date()} → {train.index.max().date()}, "
    f"~{len(train)//96:.0f} days)"
)
print(
    f"  test:  {len(test):>6,d} rows ({test.index.min().date()} → {test.index.max().date()}, "
    f"~{len(test)//96:.0f} days)"
)
print(
    f"  test mean price: €{test['dam_price_eur_mwh'].mean():.2f}/MWh, "
    f"range [{test['dam_price_eur_mwh'].min():.0f}, {test['dam_price_eur_mwh'].max():.0f}], "
    f"negative slots: {(test['dam_price_eur_mwh'] < 0).sum()}"
)

print("\n[4/4] Training and evaluating four models")
y_test = test["dam_price_eur_mwh"].values

# --- Naive ---
print("\n  MODEL: Naive (price = price 7 days ago)")
y_naive = test["price_lag_7d"].values
mask = ~np.isnan(y_naive)
m_naive = forecast_metrics(y_test[mask], y_naive[mask])
print(
    f"    MAE €{m_naive['mae_eur_mwh']:.2f}    RMSE €{m_naive['rmse_eur_mwh']:.2f}    "
    f"bias €{m_naive['bias_eur_mwh']:+.2f}"
)
print(
    f"    directional {m_naive['directional_accuracy']*100:.0f}%  "
    f"spike-recall {m_naive['spike_recall_above_200']*100:.0f}%  "
    f"neg-recall {m_naive['negative_price_recall']*100:.0f}%"
)

# --- Ridge ---
print("\n  MODEL: Ridge (linear regression with all features)")
ridge = RidgeMLForecaster(alpha=1.0)
ridge.fit(train)
y_pred_r = ridge.predict(test)
m_ridge = forecast_metrics(y_test, y_pred_r)
print(
    f"    MAE €{m_ridge['mae_eur_mwh']:.2f}    RMSE €{m_ridge['rmse_eur_mwh']:.2f}    "
    f"bias €{m_ridge['bias_eur_mwh']:+.2f}"
)
print(
    f"    directional {m_ridge['directional_accuracy']*100:.0f}%  "
    f"spike-recall {m_ridge['spike_recall_above_200']*100:.0f}%  "
    f"neg-recall {m_ridge['negative_price_recall']*100:.0f}%"
)
print("    Top 10 features by |std-coef|:")
for name, coef in ridge.coefficients().head(10).items():
    print(f"      {name:42s} {coef:+8.2f}")

# --- LightGBM ---
print("\n  MODEL: LightGBM (gradient-boosted trees)")
gbm = GBMForecaster(
    n_estimators=500, learning_rate=0.05, num_leaves=63, min_child_samples=30
)
gbm.fit(train)
y_pred_g = gbm.predict(test)
m_gbm = forecast_metrics(y_test, y_pred_g)
print(
    f"    MAE €{m_gbm['mae_eur_mwh']:.2f}    RMSE €{m_gbm['rmse_eur_mwh']:.2f}    "
    f"bias €{m_gbm['bias_eur_mwh']:+.2f}"
)
print(
    f"    directional {m_gbm['directional_accuracy']*100:.0f}%  "
    f"spike-recall {m_gbm['spike_recall_above_200']*100:.0f}%  "
    f"neg-recall {m_gbm['negative_price_recall']*100:.0f}%"
)
print("    Top 10 features by gain importance:")
for name, imp in gbm.feature_importance().head(10).items():
    print(f"      {name:42s} {imp:>14,.0f}")

# --- Quantile LightGBM ---
print("\n  MODEL: Quantile LightGBM (P10/P50/P90 prediction intervals)")
qgbm = QuantileGBMForecaster(
    quantiles=(0.1, 0.5, 0.9),
    n_estimators=500,
    learning_rate=0.05,
    num_leaves=63,
)
qgbm.fit(train)
q_preds = qgbm.predict(test)
m_q = forecast_metrics(y_test, q_preds["q50"].values)
print(
    f"    P50 MAE €{m_q['mae_eur_mwh']:.2f}    "
    f"P50 RMSE €{m_q['rmse_eur_mwh']:.2f}"
)
in_band = (
    (y_test >= q_preds["q10"].values) & (y_test <= q_preds["q90"].values)
).mean()
print(f"    P10-P90 interval coverage: {in_band*100:.1f}% (target: 80%)")
print(f"    Mean band width: €{(q_preds['q90'] - q_preds['q10']).mean():.2f}/MWh")

# --- Save predictions for downstream revenue backtest ---
predictions = pd.DataFrame(
    {
        "actual":   y_test,
        "naive":    np.where(mask, y_naive, np.nan),
        "ridge":    y_pred_r,
        "gbm":      y_pred_g,
        "qgbm_p10": q_preds["q10"].values,
        "qgbm_p50": q_preds["q50"].values,
        "qgbm_p90": q_preds["q90"].values,
    },
    index=test.index,
)
out_csv = os.path.join(ROOT, "data", "forecast_test_predictions.csv")
predictions.to_csv(out_csv)
print(f"\n  Saved predictions to {os.path.relpath(out_csv, ROOT)}")
print("\nDone.")
