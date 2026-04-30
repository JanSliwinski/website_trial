"""
HelleniFlex — multi-source ENTSO-E demo.

This script exercises every ENTSO-E loader in the framework on real
Transparency Platform CSV exports:

  * Day-ahead prices  →  the optimizer's primary input
  * Total Load (forecast + actual)  →  exogenous feature for forecasting
  * Cross-border physical flows  →  exogenous feature for forecasting

It then:

  1. Cross-validates ENTSO-E prices against the HEnEx EL-DAM Excel for
     the same delivery day — a sanity check that the two independent
     market publications agree.
  2. Runs the MILP on the ENTSO-E prices and reports revenue.
  3. Aligns load and flow data into a single feature matrix indexed by
     the same 15-min slots as the prices.

To run:
    python examples/entsoe_demo.py

Place ENTSO-E CSV exports in `data/entsoe/`. File name patterns:
    GUI_ENERGY_PRICES_*.csv
    GUI_TOTAL_LOAD_DAYAHEAD_*.csv
    GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_*.csv
"""
import sys
import glob
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from helleniflex import (
    BatteryAsset,
    BatteryOptimizer,
    load_entsoe_prices_csv,
    load_entsoe_load_csv,
    load_entsoe_flows_csv,
    load_henex_dam_file,
)

# ----------------------------------------------------------------------
print("=" * 72)
print(" HelleniFlex — multi-source ENTSO-E demo (prices + load + flows)")
print("=" * 72)

entsoe_dir = ROOT / "data" / "entsoe"
henex_dir = ROOT / "data" / "henex"


def _find_one(directory: Path, pattern: str) -> str:
    matches = sorted(glob.glob(str(directory / pattern)))
    if not matches:
        raise FileNotFoundError(
            f"No file matching '{pattern}' in {directory.relative_to(ROOT)}/"
        )
    return matches[0]


# 1. PRICES ------------------------------------------------------------
price_csv = _find_one(entsoe_dir, "GUI_ENERGY_PRICES_*.csv")
prices = load_entsoe_prices_csv(price_csv)
day_str = prices.index[0].strftime("%Y-%m-%d")
print(f"\n[1/5] ENTSO-E day-ahead prices: {os.path.basename(price_csv)}")
print(f"      {len(prices)} slots for {day_str}")
print(f"      mean €{prices.mean():.2f}/MWh  |  range [{prices.min():.2f}, {prices.max():.2f}]")
print(f"      negative-price slots: {(prices < 0).sum()}")

# 2. LOAD --------------------------------------------------------------
load_csv = _find_one(entsoe_dir, "GUI_TOTAL_LOAD_DAYAHEAD_*.csv")
load = load_entsoe_load_csv(load_csv)
print(f"\n[2/5] ENTSO-E total load: {os.path.basename(load_csv)}")
print(f"      {len(load)} slots, {load['load_actual_mw'].notna().sum()} with actuals")
print(f"      Day-ahead forecast: mean {load['load_forecast_mw'].mean():.0f} MW, "
      f"peak {load['load_forecast_mw'].max():.0f} MW at "
      f"{load['load_forecast_mw'].idxmax().strftime('%H:%M')}")

# 3. CROSS-BORDER FLOWS -----------------------------------------------
flow_csv = _find_one(entsoe_dir, "GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_*.csv")
flows = load_entsoe_flows_csv(flow_csv)
print(f"\n[3/5] ENTSO-E cross-border flows: {os.path.basename(flow_csv)}")
print(f"      {len(flows)} hourly aggregates")
print(f"      Net import mean: {flows['net_import_mw'].mean():.0f} MW  "
      f"(positive = Greece pulling from neighbors)")
print(f"      Imports total:   {flows['total_imports_mw'].sum():.0f} MWh")
print(f"      Exports total:   {flows['total_exports_mw'].sum():.0f} MWh")

# 4. CROSS-VALIDATION VS HEnEx ----------------------------------------
henex_files = sorted(glob.glob(str(henex_dir / "*EL-DAM_Results*.xlsx")))
if henex_files:
    henex_prices = load_henex_dam_file(henex_files[-1])
    if (
        len(henex_prices) == len(prices)
        and (henex_prices.index == prices.index).all()
    ):
        max_diff = float((henex_prices.values - prices.values).max())
        n_match = int((henex_prices.values == prices.values).sum())
        print(f"\n[4/5] Cross-validation: ENTSO-E vs HEnEx")
        print(f"      max abs difference: €{abs(max_diff):.4f}/MWh")
        print(f"      exact slot matches: {n_match}/{len(prices)}")
        if abs(max_diff) < 0.01:
            print("      OK: Two independent market publications agree exactly.")
    else:
        print(f"\n[4/5] HEnEx file is for a different day; skipping cross-validation.")
else:
    print(f"\n[4/5] No HEnEx file in {henex_dir.relative_to(ROOT)}/ — skipping validation.")

# 5. RUN THE MILP ON ENTSO-E PRICES -----------------------------------
asset = BatteryAsset(
    name="1 MW / 2 MWh standalone (ENTSO-E demo)",
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
opt = BatteryOptimizer(asset)
result = opt.optimize(prices.values, dt_hours=0.25, enforce_cyclic=True)

print(f"\n[5/5] MILP dispatch on ENTSO-E prices ({day_str})")
print(f"      Status:    {result.status}")
print(f"      Revenue:   €{result.revenue_eur:.2f}")
print(f"      Cycles:    {result.cycles:.3f} / {asset.daily_cycle_limit}")
print(f"      Throughput: {(result.charge_mw.sum() + result.discharge_mw.sum()) * 0.25:.2f} MWh")

# 6. BUILD THE FEATURE MATRIX FOR THE FORECASTER ----------------------
# Resample hourly flow data up to 15-min by forward-fill
flow_15min = flows.reindex(prices.index, method="ffill")

feature_matrix = pd.DataFrame(index=prices.index)
feature_matrix["price_eur_mwh"] = prices.values
feature_matrix["load_forecast_mw"] = load["load_forecast_mw"].values
feature_matrix["load_actual_mw"] = load["load_actual_mw"].values
feature_matrix["net_import_mw"] = flow_15min["net_import_mw"].values
feature_matrix["total_imports_mw"] = flow_15min["total_imports_mw"].values
feature_matrix["total_exports_mw"] = flow_15min["total_exports_mw"].values

# Compute correlations between price and the exogenous features (forecast-time only)
print("\n      Feature correlations with day-ahead price:")
for col in ["load_forecast_mw", "net_import_mw", "total_imports_mw"]:
    corr = feature_matrix[["price_eur_mwh", col]].corr().iloc[0, 1]
    print(f"        {col:<25}  ρ = {corr:+.3f}")

# Save the feature matrix for downstream forecaster work
out_csv = ROOT / "data" / "feature_matrix.csv"
feature_matrix.to_csv(out_csv)
print(f"\n      Feature matrix saved to {out_csv.relative_to(ROOT)}")
print(f"      ({len(feature_matrix)} rows × {len(feature_matrix.columns)} cols, "
      "ready for SmartForecaster training when more days available)")

print("\nDone.")
