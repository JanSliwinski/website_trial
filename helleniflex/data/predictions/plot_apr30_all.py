import sys, io, warnings
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")
import os, datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

ROOT   = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent
DATA   = ROOT / "data"
ENTSOE = DATA / "entsoe"
EXT    = DATA / "external"
sys.path.insert(0, str(ROOT / "src"))

from helleniflex import (
    load_entsoe_load_directory, load_entsoe_renewable_directory,
    load_entsoe_flows_by_neighbor_directory,
    fetch_openmeteo_forecast, fetch_ipto_forecasts,
)

PRED_IDX = pd.date_range("2026-04-29 23:00", periods=96, freq="15min")
DELIVERY = datetime.date(2026, 4, 30)

# ── data ─────────────────────────────────────────────────────────────────────
load_h  = load_entsoe_load_directory(str(ENTSOE))
wind_h  = load_entsoe_renewable_directory(str(ENTSOE), label="wind")
solar_h = load_entsoe_renewable_directory(str(ENTSOE), label="solar")
flows_pn = load_entsoe_flows_by_neighbor_directory(str(ENTSOE))

load_da  = load_h["load_forecast_mw"].reindex(PRED_IDX)
wind_da  = wind_h["wind_da_forecast_mw"].reindex(PRED_IDX, method="ffill")
solar_da = solar_h["solar_da_forecast_mw"].reindex(PRED_IDX, method="ffill")
res_da   = wind_da.fillna(0) + solar_da.fillna(0)

fpn = flows_pn.loc["2026-04-28 23:00":"2026-04-29 22:45"]

ttf = pd.read_csv(EXT / "ttf_gas_daily_eur_per_mwh.csv", index_col=0, parse_dates=True)["ttf_eur_per_mwh"]
eua = pd.read_csv(EXT / "eua_carbon_daily_eur_per_t.csv", index_col=0, parse_dates=True).iloc[:, 0]
ttf_r = ttf[ttf.index >= "2026-04-01"]
eua_r = eua.dropna(); eua_r = eua_r[eua_r.index >= "2026-04-01"]

wx   = fetch_openmeteo_forecast(DELIVERY)
ipto = fetch_ipto_forecasts(DELIVERY)
ipto_cet = ipto.tz_convert("Europe/Berlin").tz_localize(None)

preds = pd.read_csv(Path(os.path.dirname(os.path.abspath(__file__))) / "apr30_three_branch_predictions.csv")
actual = np.array([
    123.66, 118.60, 118.37, 116.12, 115.24, 111.69, 111.62, 113.19,
    110.27, 109.37, 108.04, 107.83, 108.16, 108.84, 109.15, 110.87,
    108.48, 111.93, 117.38, 119.77, 116.81, 121.83, 128.58, 135.38,
    123.19, 136.82, 138.55, 134.83, 138.96, 125.92, 114.78, 106.44,
    138.06, 125.71, 101.83,  52.76, 112.36,  62.39,   0.02,   0.01,
      0.02,   0.01,   0.02,   0.02,   5.11,   0.20,   0.20,  10.75,
      1.43,   2.55,   0.01,   0.01,   0.01,   0.02,   0.03,   1.89,
      0.01,   0.01,   5.11,   0.01,   0.01,   0.02,   0.51,   2.18,
      0.39,   5.00,   8.43,  58.00,  87.80, 108.66, 125.38, 135.63,
    110.86, 114.61, 129.29, 146.18, 126.93, 148.40, 198.13, 213.40,
    163.67, 139.40, 136.05, 191.45, 134.19, 133.99, 138.11, 137.72,
    138.21, 128.03, 128.35, 131.06, 131.04, 121.10, 116.44, 107.64,
])

t96 = np.arange(96)
xt  = t96[::8]
xl  = [f"{(t // 4):02d}:00" for t in xt]

DARK = "#0f0f1a"
GRID = "#2a2a40"
TXT  = "#e0e0f0"
CLR  = ["#00d4ff", "#ff6b6b", "#50fa7b", "#f1fa8c", "#bd93f9", "#ff79c6", "#ffb86c"]

def ax_style(ax, title):
    ax.set_facecolor("#161628")
    ax.tick_params(colors=TXT, labelsize=7)
    ax.title.set_color(TXT); ax.title.set_fontsize(9)
    for sp in ax.spines.values(): sp.set_color(GRID)
    ax.grid(color=GRID, linewidth=0.5, alpha=0.7)
    ax.set_title(title, pad=4)
    ax.xaxis.label.set_color(TXT); ax.yaxis.label.set_color(TXT)

fig = plt.figure(figsize=(18, 22))
fig.patch.set_facecolor(DARK)
gs  = gridspec.GridSpec(5, 2, figure=fig, hspace=0.45, wspace=0.32,
                        left=0.07, right=0.97, top=0.95, bottom=0.04)

# ── 1. Actual vs predictions (full width) ────────────────────────────────────
ax1 = fig.add_subplot(gs[0, :])
ax1.fill_between(t96, actual, alpha=0.12, color=CLR[0])
ax1.plot(t96, actual,              color=CLR[0], lw=2.0, label="Actual MCP")
ax1.plot(t96, preds["pred_A"],     color=CLR[1], lw=1.4, ls="--", label="A  forecast_v2  (83.7%)")
ax1.plot(t96, preds["pred_B"],     color=CLR[2], lw=1.4, ls="--", label="B  dam-upgrade  (81.9%)")
ax1.plot(t96, preds["pred_C"],     color=CLR[3], lw=1.4, ls=":",  label="C  merged       (81.9%)")
ax1.set_xticks(xt); ax1.set_xticklabels(xl)
ax1.set_ylabel("EUR/MWh", color=TXT)
ax1.legend(loc="upper left", fontsize=7.5, facecolor="#1e1e30", labelcolor=TXT, framealpha=0.85)
ax_style(ax1, "April 30 2026 — Actual MCP vs Branch Predictions  (Athens time)")

# ── 2. ENTSO-E load & RES ────────────────────────────────────────────────────
ax2 = fig.add_subplot(gs[1, 0])
ax2.plot(t96, load_da.values,  color=CLR[0], lw=1.5, label="Load forecast")
ax2.plot(t96, solar_da.values, color=CLR[3], lw=1.3, label="Solar DA")
ax2.plot(t96, wind_da.values,  color=CLR[2], lw=1.3, label="Wind DA")
ax2.fill_between(t96, res_da.values, alpha=0.1, color=CLR[2])
ax2.set_xticks(xt); ax2.set_xticklabels(xl)
ax2.set_ylabel("MW", color=TXT)
ax2.legend(fontsize=7, facecolor="#1e1e30", labelcolor=TXT, framealpha=0.85)
ax_style(ax2, "ENTSO-E DA — Load / Wind / Solar")

# ── 3. IPTO ──────────────────────────────────────────────────────────────────
ax3 = fig.add_subplot(gs[1, 1])
ax3.plot(t96, ipto_cet["load_forecast_mw"].values,  color=CLR[0], lw=1.5, label="IPTO load")
ax3.plot(t96, ipto_cet["res_da_forecast_mw"].values, color=CLR[4], lw=1.5, label="IPTO RES")
ax3.fill_between(t96, ipto_cet["res_da_forecast_mw"].values, alpha=0.1, color=CLR[4])
ax3.set_xticks(xt); ax3.set_xticklabels(xl)
ax3.set_ylabel("MW", color=TXT)
ax3.legend(fontsize=7, facecolor="#1e1e30", labelcolor=TXT, framealpha=0.85)
ax_style(ax3, "IPTO ISP1 — Load & RES Forecast")

# ── 4. Residual demand ───────────────────────────────────────────────────────
ax4 = fig.add_subplot(gs[2, 0])
res_entsoe = load_da.values - res_da.values
res_ipto   = ipto_cet["load_forecast_mw"].values - ipto_cet["res_da_forecast_mw"].values
ax4.plot(t96, res_entsoe, color=CLR[1], lw=1.5, label="ENTSO-E residual")
ax4.plot(t96, res_ipto,   color=CLR[4], lw=1.5, ls="--", label="IPTO residual")
ax4.axhline(0, color=GRID, lw=0.8)
ax4.fill_between(t96, res_ipto, alpha=0.08, color=CLR[4])
ax4.set_xticks(xt); ax4.set_xticklabels(xl)
ax4.set_ylabel("MW", color=TXT)
ax4.legend(fontsize=7, facecolor="#1e1e30", labelcolor=TXT, framealpha=0.85)
ax_style(ax4, "Residual Demand  (Load - RES)")

# ── 5. Per-neighbor flows ─────────────────────────────────────────────────────
ax5 = fig.add_subplot(gs[2, 1])
if len(fpn) == 96:
    for i, col in enumerate(fpn.columns):
        lbl = col.replace("flow_", "").replace("_mw", "")
        ax5.plot(t96, fpn[col].values, color=CLR[i % len(CLR)], lw=1.2, label=lbl)
ax5.axhline(0, color=GRID, lw=0.8)
ax5.set_xticks(xt); ax5.set_xticklabels(xl)
ax5.set_ylabel("MW", color=TXT)
ax5.legend(fontsize=6.5, facecolor="#1e1e30", labelcolor=TXT, framealpha=0.85, ncol=2)
ax_style(ax5, "Interconnector Flows — Apr 29 proxy (AL/BG/IT/MK/TR)")

# ── 6. Open-Meteo temperature & radiation ────────────────────────────────────
ax6 = fig.add_subplot(gs[3, 0])
wx_t = np.arange(len(wx))
ax6.plot(wx_t, wx["temperature_2m"].values, color=CLR[1], lw=1.5, label="Temp C")
ax6b = ax6.twinx()
ax6b.fill_between(wx_t, wx["shortwave_radiation"].values, alpha=0.2, color=CLR[3])
ax6b.plot(wx_t, wx["shortwave_radiation"].values, color=CLR[3], lw=1.3, label="Radiation W/m2")
ax6b.tick_params(colors=TXT, labelsize=7)
for sp in ax6b.spines.values(): sp.set_color(GRID)
ax6b.set_ylabel("W/m2", color=TXT); ax6b.yaxis.label.set_color(TXT)
ax6.set_xticks(range(0, len(wx), 4))
ax6.set_xticklabels([f"{h:02d}:00" for h in range(0, len(wx), 4)])
ax6.set_ylabel("C", color=TXT)
l1, ll1 = ax6.get_legend_handles_labels()
l2, ll2 = ax6b.get_legend_handles_labels()
ax6.legend(l1+l2, ll1+ll2, fontsize=7, facecolor="#1e1e30", labelcolor=TXT, framealpha=0.85)
ax_style(ax6, "Open-Meteo — Temperature & Solar Radiation")

# ── 7. Open-Meteo wind & cloud cover ─────────────────────────────────────────
ax7 = fig.add_subplot(gs[3, 1])
ax7.plot(wx_t, wx["wind_speed_10m"].values, color=CLR[2], lw=1.5, label="Wind m/s")
ax7b = ax7.twinx()
ax7b.fill_between(wx_t, wx["cloud_cover"].values, alpha=0.15, color="#888888")
ax7b.plot(wx_t, wx["cloud_cover"].values, color="#aaaaaa", lw=1.2, ls="--", label="Cloud %")
ax7b.tick_params(colors=TXT, labelsize=7)
for sp in ax7b.spines.values(): sp.set_color(GRID)
ax7b.set_ylabel("%", color=TXT); ax7b.yaxis.label.set_color(TXT)
ax7.set_xticks(range(0, len(wx), 4))
ax7.set_xticklabels([f"{h:02d}:00" for h in range(0, len(wx), 4)])
ax7.set_ylabel("m/s", color=TXT)
l1, ll1 = ax7.get_legend_handles_labels()
l2, ll2 = ax7b.get_legend_handles_labels()
ax7.legend(l1+l2, ll1+ll2, fontsize=7, facecolor="#1e1e30", labelcolor=TXT, framealpha=0.85)
ax_style(ax7, "Open-Meteo — Wind Speed & Cloud Cover")

# ── 8. TTF & EUA ─────────────────────────────────────────────────────────────
ax8 = fig.add_subplot(gs[4, 0])
xt8 = range(len(ttf_r))
ax8.plot(xt8, ttf_r.values, color=CLR[5], lw=1.8, marker="o", ms=4, label="TTF EUR/MWh")
ax8b = ax8.twinx()
ax8b.plot(range(len(eua_r)), eua_r.values, color=CLR[6], lw=1.8, marker="s", ms=4, label="EUA EUR/t")
ax8b.tick_params(colors=TXT, labelsize=7)
for sp in ax8b.spines.values(): sp.set_color(GRID)
ax8b.set_ylabel("EUR/t", color=TXT); ax8b.yaxis.label.set_color(TXT)
xlabs8 = [d.strftime("%d/%m") for d in ttf_r.index]
ax8.set_xticks(list(xt8)[::3]); ax8.set_xticklabels(xlabs8[::3], rotation=45, ha="right")
ax8.set_ylabel("EUR/MWh", color=TXT)
l1,ll1=ax8.get_legend_handles_labels(); l2,ll2=ax8b.get_legend_handles_labels()
ax8.legend(l1+l2, ll1+ll2, fontsize=7, facecolor="#1e1e30", labelcolor=TXT, framealpha=0.85)
ax_style(ax8, "TTF Gas & EUA Carbon — April 2026")

# ── 9. Prediction error ───────────────────────────────────────────────────────
ax9 = fig.add_subplot(gs[4, 1])
ax9.axhline(0, color=GRID, lw=1.0)
ax9.fill_between(t96, preds["pred_A"] - actual, alpha=0.2, color=CLR[1])
ax9.plot(t96, preds["pred_A"] - actual, color=CLR[1], lw=1.2, label="A error")
ax9.plot(t96, preds["pred_B"] - actual, color=CLR[2], lw=1.2, ls="--", label="B error")
ax9.set_xticks(xt); ax9.set_xticklabels(xl)
ax9.set_ylabel("EUR/MWh", color=TXT)
ax9.legend(fontsize=7, facecolor="#1e1e30", labelcolor=TXT, framealpha=0.85)
ax_style(ax9, "Prediction Error  (pred - actual)")

fig.suptitle("April 30 2026 — All Data Sources + Branch Predictions",
             color=TXT, fontsize=13, fontweight="bold", y=0.98)

out = Path(os.path.dirname(os.path.abspath(__file__))) / "apr30_all_curves.png"
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK)
print(f"Saved: {out}")
