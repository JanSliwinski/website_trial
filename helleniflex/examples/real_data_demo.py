"""
HelleniFlex — REAL DATA demo using HEnEx EL-DAM Results.

This script loads the official HEnEx daily Excel file for one delivery
day, runs the MILP optimizer on the real Market Clearing Prices, and
produces a chart of the optimal battery dispatch.

Usage
-----
    python examples/real_data_demo.py

Prerequisites
-------------
At least one HEnEx Excel file in `data/henex/`. Files can be downloaded
from https://www.enexgroup.gr/en/markets-publications-el-day-ahead-market
(naming convention: YYYYMMDD_EL-DAM_Results_EN_v01.xlsx).

The script auto-discovers all files in the folder and runs the demo on
the most recent one.
"""
import sys
import glob
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from helleniflex import (
    BatteryAsset,
    BatteryOptimizer,
    load_henex_dam_file,
)


# ----------------------------------------------------------------------
print("=" * 72)
print(" HelleniFlex — REAL Greek DAM data via HEnEx EL-DAM Results")
print("=" * 72)

# Locate the HEnEx file(s)
henex_dir = ROOT / "data" / "henex"
files = sorted(glob.glob(str(henex_dir / "*EL-DAM_Results*.xlsx")))
if not files:
    print(f"\nNo HEnEx Excel files found in {henex_dir}/")
    print("Download daily files from:")
    print("  https://www.enexgroup.gr/en/markets-publications-el-day-ahead-market")
    print("and drop them in that folder.")
    sys.exit(1)

print(f"\n[1/3] Found {len(files)} HEnEx file(s) in {henex_dir.relative_to(ROOT)}/")
for f in files:
    print(f"      • {os.path.basename(f)}")

# Load the most recent file
latest = files[-1]
prices = load_henex_dam_file(latest)
day_str = prices.index[0].strftime("%Y-%m-%d")

print(f"\n[2/3] Loaded {len(prices)} prices for {day_str}")
print(f"      Mean €{prices.mean():.2f}/MWh  |  "
      f"min €{prices.min():.2f}  |  max €{prices.max():.2f}  |  "
      f"spread €{prices.max() - prices.min():.2f}")
print(f"      Negative-price slots: {(prices < 0).sum()}")
print(f"      Near-zero (≤ €1) slots: {(prices <= 1).sum()}")

# Run the MILP optimizer on real data
asset = BatteryAsset(
    name="1 MW / 2 MWh standalone (real-data demo)",
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

print(f"\n[3/3] MILP solved in HiGHS:  status = {result.status}")
print(f"      Revenue:        €{result.revenue_eur:.2f}")
print(f"      Cycles used:    {result.cycles:.3f} (cap: {asset.daily_cycle_limit})")
charge_mwh = result.charge_mw.sum() * 0.25
disch_mwh = result.discharge_mw.sum() * 0.25
print(f"      Charge MWh:     {charge_mwh:.2f}")
print(f"      Discharge MWh:  {disch_mwh:.2f}")
print(f"      Annualized:     €{result.revenue_eur * 365 / asset.capacity_mwh:,.0f}/MWh/yr")
print(f"                       (single-day extrapolation; "
      f"realistic full-year backtest needs more data)")

# Print the schedule
charge_idx = np.where(result.charge_mw > 0.01)[0]
disch_idx = np.where(result.discharge_mw > 0.01)[0]
print(f"\n      Charging slots ({len(charge_idx)}):")
for i in charge_idx:
    ts = prices.index[i].strftime("%H:%M")
    print(f"        {ts}  €{prices.values[i]:7.2f}  "
          f"charge {result.charge_mw[i]:.2f} MW")
print(f"\n      Discharging slots ({len(disch_idx)}):")
for i in disch_idx:
    ts = prices.index[i].strftime("%H:%M")
    print(f"        {ts}  €{prices.values[i]:7.2f}  "
          f"discharge {result.discharge_mw[i]:.2f} MW")

# Generate a chart
fig, axes = plt.subplots(
    3, 1, figsize=(13, 9), sharex=True,
    gridspec_kw={"height_ratios": [2.2, 2, 1.2]},
)
hours = np.arange(96) * 0.25

# Panel 1 — Prices
ax = axes[0]
ax.plot(hours, prices.values, color="#1f4e79", lw=2, drawstyle="steps-post")
ax.fill_between(hours, prices.values, where=(prices.values >= 0),
                step="post", alpha=0.18, color="#1f4e79")
ax.fill_between(hours, prices.values, where=(prices.values < 0),
                step="post", alpha=0.45, color="#a83232")
ax.axhline(0, color="black", lw=0.6, ls="-", alpha=0.6)
ax.set_ylabel("Price [€/MWh]", fontsize=11)
ax.set_title(
    f"HelleniFlex — optimal dispatch on REAL Greek DAM, {day_str}",
    fontsize=14, fontweight="bold", loc="left",
)
ax.grid(alpha=0.3)
ax.text(
    0.02, 0.95,
    f"€{result.revenue_eur:.0f} revenue  ·  {result.cycles:.2f} cycles  ·  "
    f"{(prices < 0).sum()} negative-price slots",
    transform=ax.transAxes, fontsize=10, va="top",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#888", alpha=0.9),
)

# Panel 2 — dispatch
ax = axes[1]
ax.bar(hours, -result.charge_mw, width=0.25, color="#3a7bd5",
       label="Charge", align="edge", alpha=0.85)
ax.bar(hours, result.discharge_mw, width=0.25, color="#e8744f",
       label="Discharge", align="edge", alpha=0.85)
ax.axhline(0, color="black", lw=0.5)
ax.set_ylabel("Power [MW]", fontsize=11)
ax.legend(loc="upper left", framealpha=0.9)
ax.grid(alpha=0.3)

# Panel 3 — SoC
ax = axes[2]
soc_x = np.arange(97) * 0.25
ax.plot(soc_x, result.soc_mwh, color="#d4a017", lw=2.2)
ax.fill_between(soc_x, result.soc_mwh, alpha=0.25, color="#d4a017")
ax.axhline(asset.soc_min_mwh, color="#a83232", ls="--", lw=1, alpha=0.5)
ax.axhline(asset.soc_max_mwh, color="#3a7bd5", ls="--", lw=1, alpha=0.5)
ax.set_ylabel("SoC [MWh]", fontsize=11)
ax.set_xlabel("Hour of day", fontsize=11)
ax.set_xlim(0, 24)
ax.set_xticks(range(0, 25, 2))
ax.grid(alpha=0.3)

plt.tight_layout()
out = ROOT / "docs" / "real_dispatch.png"
plt.savefig(out, dpi=130, bbox_inches="tight")
plt.close()
print(f"\nChart saved to {out.relative_to(ROOT)}")
print("\nDone.")
