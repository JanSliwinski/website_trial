"""End-to-end smoke test: verifies the whole pipeline runs."""
import sys
from pathlib import Path

import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from helleniflex import (
    BatteryAsset, BatteryOptimizer, Backtester,
    PerfectForesightForecaster, NaiveForecaster, SmartForecaster,
    make_synthetic_greek_dam_prices, PRESETS,
)

print("=" * 70)
print("HelleniFlex smoke test")
print("=" * 70)

# 1. Generate prices
t0 = time.time()
prices = make_synthetic_greek_dam_prices(start="2024-01-01", end="2025-06-30")
print(f"\n[1] Generated {len(prices):,} synthetic 15-min prices in {time.time()-t0:.2f}s")
print(f"    Range: {prices.min():.1f} – {prices.max():.1f} €/MWh")
print(f"    Mean:  {prices.mean():.1f} €/MWh")
print(f"    Negative-price slots: {(prices < 0).sum()} ({(prices < 0).mean()*100:.1f}%)")

# 2. Single-day optimization
print("\n[2] Single-day MILP optimization")
battery = BatteryAsset(power_mw=1.0, capacity_mwh=2.0)
print(f"    Asset: {battery.summary()}")
opt = BatteryOptimizer(battery)
day_prices = prices.loc["2025-04-15"].values  # a spring day with negative prices likely
t0 = time.time()
result = opt.optimize(day_prices, dt_hours=0.25)
print(f"    Solved in {time.time()-t0:.3f}s, status={result.status}")
print(f"    Revenue: €{result.revenue_eur:.2f}")
print(f"    Cycles:  {result.cycles:.2f}")
print(f"    Charge total:    {result.charge_mw.sum() * 0.25:.2f} MWh")
print(f"    Discharge total: {result.discharge_mw.sum() * 0.25:.2f} MWh")

# 3. Backtest with all 3 forecasters
print("\n[3] 30-day backtest with three forecasters")
window_start = "2025-05-01"
window_end = "2025-05-30"

for forecaster_cls in (PerfectForesightForecaster, NaiveForecaster, SmartForecaster):
    forecaster = forecaster_cls()
    bt = Backtester(battery, forecaster=forecaster)
    t0 = time.time()
    res = bt.run(prices, start=window_start, end=window_end)
    elapsed = time.time() - t0
    print(f"    {forecaster.name:30s}  {res.summary()}  [{elapsed:.1f}s]")

# 4. Compare battery durations
print("\n[4] Asset sensitivity (perfect foresight, 30 days)")
for preset_name in ["greek_standalone_1h", "greek_standalone_2h", "greek_standalone_4h"]:
    bt = Backtester(PRESETS[preset_name], forecaster=PerfectForesightForecaster())
    res = bt.run(prices, start=window_start, end=window_end)
    print(f"    {res.summary()}")

print("\nAll tests passed.")
