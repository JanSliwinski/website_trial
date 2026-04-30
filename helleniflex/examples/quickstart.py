"""
HelleniFlex — quickstart demo.

Run this script to verify the framework end-to-end:

    python examples/quickstart.py

It does four things:
  1. Generate 18 months of synthetic Greek DAM prices (no internet required).
  2. Solve the dispatch MILP for one representative day and plot it.
  3. Backtest 30 days under all three forecasters and compare.
  4. Run an asset sensitivity sweep (1h vs 2h vs 4h batteries).

To run on real Greek DAM data, replace step 1 with `load_csv_prices(...)`
or `fetch_entsoe_dam(...)` — see `helleniflex.data_loader`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from helleniflex import (
    BatteryOptimizer, Backtester,
    PerfectForesightForecaster, NaiveForecaster, SmartForecaster,
    make_synthetic_greek_dam_prices, PRESETS,
)

# ----------------------------------------------------------------------
print("=" * 72)
print(" HelleniFlex — Battery Optimization for the Greek DAM")
print("=" * 72)

# 1. Data
prices = make_synthetic_greek_dam_prices(start="2024-01-01", end="2025-06-30")
print(f"\n[1/4] Loaded {len(prices):,} 15-min price points.")
print(f"      Mean €{prices.mean():.0f}/MWh, "
      f"{(prices < 0).sum()} negative-price slots.")

# 2. Single-day dispatch
battery = PRESETS["greek_standalone_2h"]
opt = BatteryOptimizer(battery)
day_str = "2025-04-15"
day_prices = prices.loc[day_str].values
result = opt.optimize(day_prices, dt_hours=0.25)
print(f"\n[2/4] Single-day dispatch ({day_str}):")
print(f"      Revenue €{result.revenue_eur:.2f}  |  "
      f"Cycles {result.cycles:.2f}  |  Status: {result.status}")

# Plot
fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True,
                         gridspec_kw={"height_ratios": [2, 2, 1]})
hours = np.arange(96) * 0.25
axes[0].plot(hours, day_prices, color="#4a9eff", lw=2, drawstyle="steps-post")
axes[0].fill_between(hours, day_prices, alpha=0.15, color="#4a9eff", step="post")
axes[0].axhline(0, color="gray", lw=0.5, ls="--")
axes[0].set_ylabel("Price [€/MWh]"); axes[0].grid(alpha=0.3)
axes[0].set_title(f"Optimal dispatch on {day_str}", fontweight="bold")

axes[1].bar(hours, -result.charge_mw, width=0.25, color="#f4b942",
            label="Charge", align="edge")
axes[1].bar(hours, result.discharge_mw, width=0.25, color="#7ed321",
            label="Discharge", align="edge")
axes[1].axhline(0, color="black", lw=0.5)
axes[1].set_ylabel("Power [MW]"); axes[1].legend(loc="upper left")
axes[1].grid(alpha=0.3)

axes[2].plot(np.arange(97)*0.25, result.soc_mwh, color="#f4b942", lw=2)
axes[2].fill_between(np.arange(97)*0.25, result.soc_mwh, alpha=0.3, color="#f4b942")
axes[2].set_ylabel("SoC [MWh]"); axes[2].set_xlabel("Hour of day")
axes[2].set_xlim(0, 24); axes[2].grid(alpha=0.3)

out = ROOT / "docs" / "example_dispatch.png"
plt.tight_layout(); plt.savefig(out, dpi=120, bbox_inches="tight"); plt.close()
print(f"      Plot saved to {out.relative_to(ROOT)}")

# 3. Forecaster comparison
print(f"\n[3/4] 30-day backtest, three forecasters:")
print(f"      {'Forecaster':<28} {'€ total':>10} {'€/day':>9} {'€/MWh/yr':>11} {'cyc/d':>7}")
print(f"      {'-'*28} {'-'*10} {'-'*9} {'-'*11} {'-'*7}")
fc_results = {}
for fc_cls in (PerfectForesightForecaster, NaiveForecaster, SmartForecaster):
    fc = fc_cls()
    bt = Backtester(battery, forecaster=fc)
    res = bt.run(prices, start="2025-05-01", end="2025-05-30")
    fc_results[fc.name] = res
    print(f"      {fc.name:<28} {res.total_revenue_eur:>10,.0f} "
          f"{res.avg_daily_revenue_eur:>9,.0f} "
          f"{res.revenue_per_mwh_per_year:>11,.0f} "
          f"{res.total_cycles/len(res.daily):>7.2f}")

pf = fc_results["Perfect Foresight"].total_revenue_eur
print(f"\n      Smart captures {fc_results['Smart (Ridge + calendar)'].total_revenue_eur/pf*100:.1f}% "
      f"of perfect-foresight revenue.")
print(f"      Naive captures {fc_results['Naive (last-week)'].total_revenue_eur/pf*100:.1f}% "
      f"of perfect-foresight revenue.")

# 4. Asset sensitivity
print(f"\n[4/4] Asset sensitivity (perfect foresight, 30 days):")
print(f"      {'Asset':<30} {'€/day':>8} {'€/MWh/yr':>11}")
print(f"      {'-'*30} {'-'*8} {'-'*11}")
for preset_name in ["greek_standalone_1h", "greek_standalone_2h", "greek_standalone_4h"]:
    bt = Backtester(PRESETS[preset_name], forecaster=PerfectForesightForecaster())
    res = bt.run(prices, start="2025-05-01", end="2025-05-30")
    print(f"      {PRESETS[preset_name].name:<30} "
          f"€{res.avg_daily_revenue_eur:>7,.0f} "
          f"{res.revenue_per_mwh_per_year:>11,.0f}")

print("\nDone.")
