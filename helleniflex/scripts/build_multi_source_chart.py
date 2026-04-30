"""Generate a 4-panel chart showing the full ENTSO-E + dispatch story."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from helleniflex import (
    BatteryAsset, BatteryOptimizer,
    load_entsoe_prices_csv, load_entsoe_load_csv, load_entsoe_flows_csv,
)

# Load all three data sources
prices = load_entsoe_prices_csv(
    str(ROOT / "data" / "entsoe" / "GUI_ENERGY_PRICES_202604282200-202604292200.csv")
)
load = load_entsoe_load_csv(
    str(ROOT / "data" / "entsoe" / "GUI_TOTAL_LOAD_DAYAHEAD_202604282200-202604292200.csv")
)
flows = load_entsoe_flows_csv(
    str(ROOT / "data" / "entsoe" / "GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_202604282200-202604292200__1_.csv")
)
flows_15 = flows.reindex(prices.index, method="ffill")

# Run the optimizer
asset = BatteryAsset(power_mw=1.0, capacity_mwh=2.0,
                     eta_charge=0.94, eta_discharge=0.94,
                     soc_min_pct=0.10, soc_max_pct=0.90,
                     initial_soc_pct=0.50, daily_cycle_limit=1.5,
                     cycle_cost_eur_per_mwh=0.0)
result = BatteryOptimizer(asset).optimize(
    prices.values, dt_hours=0.25, enforce_cyclic=True
)

day_str = prices.index[0].strftime("%Y-%m-%d")
hours = np.arange(96) * 0.25

fig, axes = plt.subplots(
    4, 1, figsize=(13, 11), sharex=True,
    gridspec_kw={"height_ratios": [2.2, 1.6, 1.6, 1.4]},
)

# Panel 1 — DAM prices with negative regions highlighted
ax = axes[0]
ax.plot(hours, prices.values, color="#1f4e79", lw=2, drawstyle="steps-post")
ax.fill_between(hours, prices.values, where=(prices.values >= 0),
                step="post", alpha=0.18, color="#1f4e79")
ax.fill_between(hours, prices.values, where=(prices.values < 0),
                step="post", alpha=0.45, color="#a83232")
ax.axhline(0, color="black", lw=0.6, alpha=0.6)
ax.set_ylabel("DAM price [€/MWh]", fontsize=11)
ax.set_title(
    f"HelleniFlex — Greek DAM, {day_str}  ·  multi-source pipeline view",
    fontsize=14, fontweight="bold", loc="left",
)
ax.grid(alpha=0.3)
ax.text(
    0.02, 0.95,
    f"€{result.revenue_eur:.0f} revenue  ·  {result.cycles:.2f} cycles  ·  "
    f"5 negative-price slots",
    transform=ax.transAxes, fontsize=10, va="top",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#888", alpha=0.9),
)

# Panel 2 — Battery dispatch
ax = axes[1]
ax.bar(hours, -result.charge_mw, width=0.25, color="#3a7bd5",
       label="Charge", align="edge", alpha=0.85)
ax.bar(hours, result.discharge_mw, width=0.25, color="#e8744f",
       label="Discharge", align="edge", alpha=0.85)
ax.axhline(0, color="black", lw=0.5)
ax.set_ylabel("Power [MW]", fontsize=11)
ax.legend(loc="upper left", framealpha=0.9)
ax.grid(alpha=0.3)

# Panel 3 — Total load (forecast vs actual)
ax = axes[2]
ax.plot(hours, load["load_forecast_mw"].values,
        color="#888", ls="--", lw=1.5, label="Day-ahead forecast")
actual = load["load_actual_mw"].values
mask = ~np.isnan(actual)
ax.plot(hours[mask], actual[mask],
        color="#2c8c5a", lw=2, label="Actual (where published)")
ax.set_ylabel("Total load [MW]", fontsize=11)
ax.legend(loc="upper left", framealpha=0.9)
ax.grid(alpha=0.3)

# Panel 4 — Net cross-border imports
ax = axes[3]
net = flows_15["net_import_mw"].values
ax.fill_between(hours, net, where=(net >= 0), step="post",
                alpha=0.5, color="#3a7bd5", label="Net import (Greece short)")
ax.fill_between(hours, net, where=(net < 0), step="post",
                alpha=0.5, color="#e8744f", label="Net export (Greece surplus)")
ax.axhline(0, color="black", lw=0.5)
ax.set_ylabel("Net flow [MW]", fontsize=11)
ax.set_xlabel("Hour of day", fontsize=11)
ax.set_xlim(0, 24)
ax.set_xticks(range(0, 25, 2))
ax.legend(loc="upper left", framealpha=0.9)
ax.grid(alpha=0.3)

plt.tight_layout()
out = ROOT / "docs" / "multi_source_dispatch.png"
plt.savefig(out, dpi=130, bbox_inches="tight")
plt.close()
print(f"Saved: {out.relative_to(ROOT)}")
