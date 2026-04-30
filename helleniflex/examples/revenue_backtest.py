"""
HelleniFlex — Revenue Backtest on Real Greek DAM Data.

For each day in the held-out test set:
  1. Use the trained forecaster to predict tomorrow's 96 prices.
  2. Run the MILP optimizer on the forecast to get a charge/discharge schedule.
  3. SETTLE the schedule against the ACTUAL realized prices.
  4. Compute realized revenue.

Compares four strategies:
  • Perfect Foresight  — oracle, upper bound (optimizer sees actual prices)
  • Ridge Forecast     — the production strategy (optimizer sees Ridge prediction)
  • LightGBM Forecast  — alternative production strategy
  • Naive Forecast     — last-week baseline
  • No Forecast        — fixed schedule (charge cheapest 4 hrs / discharge peak 4 hrs by hour-of-day from training data)

The headline metric is "% of perfect-foresight revenue captured".
That is the number that matters for the battery operator.
"""
import sys
import os
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
import numpy as np

from helleniflex import (
    BatteryAsset,
    BatteryOptimizer,
    load_entsoe_prices_directory,
    load_entsoe_load_directory,
    load_entsoe_total_generation_directory,
    load_entsoe_renewable_directory,
    FeatureBuilder,
    RidgeMLForecaster,
    GBMForecaster,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "entsoe")

# ----------------------------------------------------------------------
# Step 1: Load data and train forecasters
# ----------------------------------------------------------------------
print("=" * 75)
print(" HelleniFlex — Revenue Backtest on Real Greek DAM Data")
print("=" * 75)

print("\n[1/5] Loading data...")
prices = load_entsoe_prices_directory(D)
load = load_entsoe_load_directory(D)
gen_total = load_entsoe_total_generation_directory(D)
wind = load_entsoe_renewable_directory(D, label="wind")
solar = load_entsoe_renewable_directory(D, label="solar")

builder = FeatureBuilder(
    prices=prices, load=load, wind=wind, solar=solar,
    flows=None, gen_total=gen_total,
)
df = builder.build()
df_clean = df.dropna(subset=["price_lag_14d", "load_forecast_mw"])

train = df_clean.loc["2025-01-15":"2025-12-31"].copy()
test = df_clean.loc["2026-04-01":"2026-04-30"].copy()

# Drop columns with poor coverage in either set
to_drop = [c for c in train.columns if c != "dam_price_eur_mwh"
           and (train[c].notna().mean() < 0.5 or test[c].notna().mean() < 0.5)]
if to_drop:
    train = train.drop(columns=to_drop)
    test = test.drop(columns=to_drop)

print(f"  train: {len(train):,} rows ({train.index.min().date()} → {train.index.max().date()})")
print(f"  test:  {len(test):,} rows ({test.index.min().date()} → {test.index.max().date()})")

print("\n[2/5] Training forecasters...")
ridge = RidgeMLForecaster(alpha=1.0)
ridge.fit(train)
gbm = GBMForecaster(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=20)
gbm.fit(train)
print("  Ridge OK  LightGBM OK")

# Build per-day price arrays for the test period
test_dates = sorted(set(test.index.normalize()))
print(f"  Test days: {len(test_dates)}")

# Generate all forecasts up front
y_actual = test["dam_price_eur_mwh"].values
y_ridge = ridge.predict(test)
y_gbm = gbm.predict(test)
y_naive = test["price_lag_7d"].values

# Index → 24h shape per day
def per_day(arr, idx):
    out = {}
    for d in test_dates:
        mask = idx.normalize() == d
        out[d] = arr[mask]
    return out

actual_by_day = per_day(y_actual, test.index)
ridge_by_day = per_day(y_ridge, test.index)
gbm_by_day = per_day(y_gbm, test.index)
naive_by_day = per_day(y_naive, test.index)

# ----------------------------------------------------------------------
# Step 3: Define the asset, the optimizer, and the settlement function
# ----------------------------------------------------------------------
print("\n[3/5] Battery asset:")
asset = BatteryAsset(
    name="1 MW / 2 MWh standalone",
    power_mw=1.0,
    capacity_mwh=2.0,
    eta_charge=0.94,
    eta_discharge=0.94,
    soc_min_pct=0.10,
    soc_max_pct=0.90,
    initial_soc_pct=0.50,
    daily_cycle_limit=1.5,
    cycle_cost_eur_per_mwh=0.0,
)
print(f"  {asset.name}")
print(f"  power: {asset.power_mw} MW, capacity: {asset.capacity_mwh} MWh, eta_rt: {asset.eta_charge*asset.eta_discharge:.2f}")

opt = BatteryOptimizer(asset)


def settle(forecast_prices, actual_prices, dt_hours=0.25):
    """Run optimizer on `forecast_prices`, settle dispatch vs `actual_prices`.

    Returns a dict with: forecast_revenue, realized_revenue, schedule_optimal_for_actual.
    """
    # Skip days with NaN forecast (e.g. naive baseline early days)
    if np.any(np.isnan(forecast_prices)) or len(forecast_prices) != 96:
        return None
    # Plan based on forecast
    result = opt.optimize(forecast_prices, dt_hours=dt_hours, enforce_cyclic=True)
    if result.status not in ("optimal", "optimal_inaccurate"):
        return None
    # Realized revenue = (discharge - charge) * dt * actual_prices
    schedule = result.discharge_mw - result.charge_mw  # net MW per slot
    realized = float(np.sum(schedule * dt_hours * actual_prices))
    forecast_rev = float(result.revenue_eur)
    cycles = float(result.cycles)
    return {
        "forecast_revenue": forecast_rev,
        "realized_revenue": realized,
        "cycles": cycles,
    }


# ----------------------------------------------------------------------
# Step 4: Day-by-day backtest
# ----------------------------------------------------------------------
print("\n[4/5] Running revenue backtest day by day...")
records = []

for i, d in enumerate(test_dates):
    actual = actual_by_day[d]
    if len(actual) != 96:
        print(f"  skip {d.date()}: only {len(actual)} slots")
        continue

    # PERFECT FORESIGHT: optimizer sees actual prices
    pf = settle(actual, actual)

    # RIDGE
    ridge_res = settle(ridge_by_day[d], actual)

    # LightGBM
    gbm_res = settle(gbm_by_day[d], actual)

    # NAIVE (might be NaN)
    naive_pred = naive_by_day[d]
    naive_res = settle(naive_pred, actual) if not np.any(np.isnan(naive_pred)) else None

    rec = {
        "date": d,
        "actual_mean_eur": float(np.mean(actual)),
        "actual_negative_slots": int(np.sum(actual < 0)),
        "perfect_revenue": pf["realized_revenue"] if pf else np.nan,
        "ridge_revenue": ridge_res["realized_revenue"] if ridge_res else np.nan,
        "gbm_revenue": gbm_res["realized_revenue"] if gbm_res else np.nan,
        "naive_revenue": naive_res["realized_revenue"] if naive_res else np.nan,
    }
    records.append(rec)
    if (i + 1) % 5 == 0 or i == 0:
        print(f"  {d.date()}  PF €{rec['perfect_revenue']:6.2f}  Ridge €{rec['ridge_revenue']:6.2f}"
              f"  LGBM €{rec['gbm_revenue']:6.2f}  Naive €{rec['naive_revenue'] if rec['naive_revenue'] is not None else float('nan'):6.2f}")

bt = pd.DataFrame(records).set_index("date")

# ----------------------------------------------------------------------
# Step 5: Aggregate and report
# ----------------------------------------------------------------------
print("\n[5/5] AGGREGATE RESULTS — April 2026 (30 days)")
print("=" * 75)

n_days = len(bt)
print(f"\nDays:                        {n_days}")
print(f"Asset:                       1 MW / 2 MWh")
print(f"Realized revenue per day (€):")
print(f"  Perfect Foresight (oracle):    €{bt['perfect_revenue'].mean():>7.2f}/day  (= 100.0%)")

for label, col in [("Ridge ML forecast    ", "ridge_revenue"),
                   ("LightGBM forecast    ", "gbm_revenue"),
                   ("Naive (last-week)    ", "naive_revenue")]:
    avg = bt[col].mean()
    pct = avg / bt["perfect_revenue"].mean() * 100
    print(f"  {label}:        €{avg:>7.2f}/day  (= {pct:>5.1f}% of oracle)")

print(f"\nTotal revenue across {n_days} days (€):")
print(f"  Perfect Foresight (oracle):    €{bt['perfect_revenue'].sum():>9,.2f}")
for label, col in [("Ridge ML forecast    ", "ridge_revenue"),
                   ("LightGBM forecast    ", "gbm_revenue"),
                   ("Naive (last-week)    ", "naive_revenue")]:
    s = bt[col].sum()
    pct = s / bt["perfect_revenue"].sum() * 100
    print(f"  {label}:        €{s:>9,.2f}  (= {pct:>5.1f}%)")

print(f"\nAnnualized revenue per MWh:")
for label, col in [("Perfect Foresight    ", "perfect_revenue"),
                   ("Ridge ML forecast    ", "ridge_revenue"),
                   ("LightGBM forecast    ", "gbm_revenue"),
                   ("Naive (last-week)    ", "naive_revenue")]:
    annual = bt[col].mean() * 365 / asset.capacity_mwh
    print(f"  {label}:    €{annual:>7,.0f}/MWh/yr")

# Save
out = os.path.join(ROOT, "data", "revenue_backtest_april_2026.csv")
bt.to_csv(out)
print(f"\nSaved: {os.path.relpath(out, ROOT)}")
print("\nDone.")
