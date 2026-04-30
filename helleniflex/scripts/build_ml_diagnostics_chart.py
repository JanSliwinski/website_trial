"""Build the diagnostic chart for the ML forecasting pipeline."""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from helleniflex import (
    load_entsoe_prices_directory, load_entsoe_load_directory,
    load_entsoe_total_generation_directory, load_entsoe_renewable_directory,
    FeatureBuilder, RidgeMLForecaster, GBMForecaster,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "entsoe")

# Build features and train models
prices = load_entsoe_prices_directory(D)
load = load_entsoe_load_directory(D)
gen_total = load_entsoe_total_generation_directory(D)
wind = load_entsoe_renewable_directory(D, label="wind")
solar = load_entsoe_renewable_directory(D, label="solar")
builder = FeatureBuilder(prices=prices, load=load, wind=wind, solar=solar,
                          flows=None, gen_total=gen_total)
df = builder.build()
df_clean = df.dropna(subset=['price_lag_14d', 'load_forecast_mw'])
train = df_clean.loc['2025-01-15':'2025-12-31'].copy()
test = df_clean.loc['2026-04-01':'2026-04-30'].copy()
to_drop = [c for c in train.columns if c != 'dam_price_eur_mwh'
           and (train[c].notna().mean() < 0.5 or test[c].notna().mean() < 0.5)]
if to_drop:
    train = train.drop(columns=to_drop); test = test.drop(columns=to_drop)

ridge = RidgeMLForecaster(alpha=1.0); ridge.fit(train)
gbm = GBMForecaster(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=20)
gbm.fit(train)

y_actual = test['dam_price_eur_mwh'].values
y_ridge = ridge.predict(test)
y_gbm = gbm.predict(test)
y_naive = test['price_lag_7d'].values

# Load revenue backtest results
bt = pd.read_csv(os.path.join(ROOT, "data", "revenue_backtest_april_2026.csv"),
                 parse_dates=['date'], index_col='date')

# Build the figure
fig = plt.figure(figsize=(16, 11))
gs = fig.add_gridspec(3, 3, hspace=0.42, wspace=0.32, left=0.06, right=0.98, top=0.94, bottom=0.05)

# Title
fig.suptitle(
    "HelleniFlex — Real-Data ML Forecasting Pipeline   ·   Trained 2025, Tested April 2026",
    fontsize=15, fontweight='bold'
)

# ========== Row 1: Time-series predictions ==========
# Show first 5 days
ax = fig.add_subplot(gs[0, :])
n_show = 5 * 96
hours = np.arange(n_show) / 4
ax.plot(hours, y_actual[:n_show], color='#222', lw=1.8, label='Actual', zorder=5)
ax.plot(hours, y_ridge[:n_show], color='#3a7bd5', lw=1.2, alpha=0.9, label=f'Ridge MAE €{np.abs(y_ridge - y_actual).mean():.1f}')
ax.plot(hours, y_gbm[:n_show], color='#e8744f', lw=1.2, alpha=0.9, label=f'LightGBM MAE €{np.abs(y_gbm - y_actual).mean():.1f}')
ax.axhline(0, color='black', lw=0.5, alpha=0.5)
ax.set_xlabel('Hours from start of test period', fontsize=10)
ax.set_ylabel('Price [€/MWh]', fontsize=10)
ax.set_title("Forecast vs realized prices  ·  first 5 days of test (April 1–5, 2026)",
             loc='left', fontweight='bold')
ax.legend(loc='upper left', framealpha=0.9, ncol=3)
ax.grid(alpha=0.3)
for d in range(1, 5):
    ax.axvline(d * 24, color='#aaa', lw=0.5, alpha=0.5, zorder=0)

# ========== Row 2 col 0: Predicted vs Actual scatter (Ridge) ==========
ax = fig.add_subplot(gs[1, 0])
ax.scatter(y_actual, y_ridge, s=4, alpha=0.3, color='#3a7bd5')
lim = [min(y_actual.min(), y_ridge.min()) - 10, max(y_actual.max(), y_ridge.max()) + 10]
ax.plot(lim, lim, 'k--', lw=1, alpha=0.5)
ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel('Actual price [€/MWh]')
ax.set_ylabel('Predicted price [€/MWh]')
ax.set_title("Ridge: predicted vs actual", loc='left', fontweight='bold', fontsize=11)
ax.axhline(0, color='gray', lw=0.5); ax.axvline(0, color='gray', lw=0.5)
ax.grid(alpha=0.3)
mae_r = np.abs(y_ridge - y_actual).mean()
neg_recall_r = ((y_ridge < 0) & (y_actual < 0)).sum() / max(1, (y_actual < 0).sum())
ax.text(0.04, 0.96, f'MAE €{mae_r:.1f}/MWh\nNeg-recall {neg_recall_r*100:.0f}%',
        transform=ax.transAxes, va='top', fontsize=9,
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#888', alpha=0.9))

# ========== Row 2 col 1: Predicted vs Actual scatter (LightGBM) ==========
ax = fig.add_subplot(gs[1, 1])
ax.scatter(y_actual, y_gbm, s=4, alpha=0.3, color='#e8744f')
ax.plot(lim, lim, 'k--', lw=1, alpha=0.5)
ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel('Actual price [€/MWh]')
ax.set_ylabel('Predicted price [€/MWh]')
ax.set_title("LightGBM: predicted vs actual", loc='left', fontweight='bold', fontsize=11)
ax.axhline(0, color='gray', lw=0.5); ax.axvline(0, color='gray', lw=0.5)
ax.grid(alpha=0.3)
mae_g = np.abs(y_gbm - y_actual).mean()
neg_recall_g = ((y_gbm < 0) & (y_actual < 0)).sum() / max(1, (y_actual < 0).sum())
ax.text(0.04, 0.96, f'MAE €{mae_g:.1f}/MWh\nNeg-recall {neg_recall_g*100:.0f}%',
        transform=ax.transAxes, va='top', fontsize=9,
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#888', alpha=0.9))

# ========== Row 2 col 2: LightGBM feature importance ==========
ax = fig.add_subplot(gs[1, 2])
fi = gbm.feature_importance().head(10)[::-1]  # reverse for horizontal bar
y_pos = np.arange(len(fi))
ax.barh(y_pos, fi.values / 1e6, color='#e8744f', alpha=0.85)
ax.set_yticks(y_pos)
ax.set_yticklabels([n.replace('_mw','').replace('_',' ') for n in fi.index], fontsize=8)
ax.set_xlabel('Gain importance (millions)', fontsize=9)
ax.set_title("LightGBM top 10 features", loc='left', fontweight='bold', fontsize=11)
ax.grid(alpha=0.3, axis='x')

# ========== Row 3: Per-day revenue ==========
ax = fig.add_subplot(gs[2, :])
days = np.arange(len(bt))
day_labels = bt.index.strftime('%d').tolist()
width = 0.22
ax.bar(days - 1.5*width, bt['perfect_revenue'], width, color='#d4a017', label='Perfect Foresight (oracle)', alpha=0.95)
ax.bar(days - 0.5*width, bt['ridge_revenue'],   width, color='#3a7bd5', label='Ridge', alpha=0.95)
ax.bar(days + 0.5*width, bt['gbm_revenue'],     width, color='#e8744f', label='LightGBM', alpha=0.95)
ax.bar(days + 1.5*width, bt['naive_revenue'],   width, color='#888',    label='Naive', alpha=0.95)
ax.set_xticks(days)
ax.set_xticklabels(day_labels, fontsize=8)
ax.set_xlabel('Day of April 2026', fontsize=10)
ax.set_ylabel('Realized revenue [€]', fontsize=10)
ax.set_title(
    f"Realized revenue by day  ·  Ridge: {bt['ridge_revenue'].sum()/bt['perfect_revenue'].sum()*100:.1f}% of oracle  ·  "
    f"LightGBM: {bt['gbm_revenue'].sum()/bt['perfect_revenue'].sum()*100:.1f}%  ·  "
    f"Naive: {bt['naive_revenue'].sum()/bt['perfect_revenue'].sum()*100:.1f}%",
    loc='left', fontweight='bold')
ax.legend(loc='upper left', framealpha=0.9, ncol=4)
ax.grid(alpha=0.3, axis='y')
ax.set_ylim(0, max(bt['perfect_revenue'].max(), bt['ridge_revenue'].max()) * 1.15)

out = os.path.join(ROOT, "docs", "ml_pipeline_diagnostics.png")
plt.savefig(out, dpi=130, bbox_inches='tight', facecolor='white')
plt.close()
print(f"Saved: {out}")
