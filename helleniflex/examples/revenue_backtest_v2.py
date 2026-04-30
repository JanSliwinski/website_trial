"""
HelleniFlex production revenue backtest with external drivers and supply mix.

This version extends the original v2 backtest with:
  - TTF gas and EUA carbon daily market drivers
  - Open-Meteo weather history when available
  - estimated gas / solar / wind production
  - estimated gas / solar / wind DAM shares

The price models consume these extra features automatically.
"""

import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd

from helleniflex import (
    BatteryAsset,
    BatteryOptimizer,
    FeatureBuilder,
    GBMForecaster,
    ProductionEstimator,
    RidgeMLForecaster,
    add_estimated_supply_features,
    fetch_daily_series_csv_url,
    fetch_openmeteo_weather,
    load_daily_series_csv,
    load_entsoe_flows_by_neighbor_directory,
    load_entsoe_flows_directory,
    load_entsoe_generation_per_type_directory,
    load_entsoe_load_directory,
    load_entsoe_prices_directory,
    load_entsoe_renewable_directory,
    load_entsoe_total_generation_directory,
    load_foreign_prices_directory,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, "data", "entsoe")
FOR = os.path.join(ROOT, "data", "foreign_prices")
EXT = os.path.join(ROOT, "data", "external")


def load_weather_history(start: str, end: str):
    """Load cached weather if present, otherwise try Open-Meteo."""
    cache = os.path.join(EXT, "openmeteo_history_athens.csv")
    if os.path.exists(cache):
        weather = pd.read_csv(cache, index_col=0, parse_dates=True)
        weather.index = pd.to_datetime(weather.index)
        return weather
    try:
        return fetch_openmeteo_weather(start=start, end=end)
    except Exception as exc:
        print(f"  warning: weather history unavailable ({exc})")
        return None


def load_ttf_series() -> pd.Series:
    """Use a live vendor CSV URL if configured, otherwise fall back to local CSV."""
    url = os.getenv("HELLENIFLEX_TTF_CSV_URL")
    if url:
        headers = {}
        header_name = os.getenv("HELLENIFLEX_TTF_AUTH_HEADER")
        header_value = os.getenv("HELLENIFLEX_TTF_AUTH_VALUE")
        if header_name and header_value:
            headers[header_name] = header_value
        try:
            return fetch_daily_series_csv_url(
                url=url,
                date_col=os.getenv("HELLENIFLEX_TTF_DATE_COL", "Business Date"),
                value_col=os.getenv("HELLENIFLEX_TTF_VALUE_COL", "Settlement Price"),
                headers=headers or None,
                name="ttf_eur_per_mwh",
            )
        except Exception as exc:
            print(f"  warning: live TTF fetch failed, using local CSV ({exc})")
    return load_daily_series_csv(
        os.path.join(EXT, "ttf_gas_daily_eur_per_mwh.csv"),
        name="ttf_eur_per_mwh",
    )


def settle_dispatch(opt: BatteryOptimizer, forecast: np.ndarray, actual: np.ndarray, dt=0.25):
    """Optimise on forecast, settle against actual."""
    if np.any(np.isnan(forecast)) or len(forecast) != 96:
        return None
    result = opt.optimize(forecast, dt_hours=dt, enforce_cyclic=True)
    if result.status not in ("optimal", "optimal_inaccurate"):
        return None
    schedule = result.discharge_mw - result.charge_mw
    return float(np.sum(schedule * dt * actual))


print("=" * 78)
print(" HelleniFlex v2 - Revenue Backtest with External Drivers and Supply Mix")
print("=" * 78)

print("\n[1/4] Loading data sources...")
prices = load_entsoe_prices_directory(ENT)
load = load_entsoe_load_directory(ENT)
gen_total = load_entsoe_total_generation_directory(ENT)
gen_by_type = load_entsoe_generation_per_type_directory(ENT)
wind = load_entsoe_renewable_directory(ENT, label="wind")
solar = load_entsoe_renewable_directory(ENT, label="solar")
flows = load_entsoe_flows_directory(ENT)
flows_pn = load_entsoe_flows_by_neighbor_directory(ENT)
foreign = load_foreign_prices_directory(FOR)
ttf = load_ttf_series()
eua = load_daily_series_csv(
    os.path.join(EXT, "eua_carbon_daily_eur_per_t.csv"),
    name="eua_eur_per_t",
)
weather = load_weather_history(
    start=str(prices.index.min().date()),
    end=str(prices.index.max().date()),
)

print(
    f"  Greek DAM:              {len(prices):,} slots "
    f"({prices.index.min().date()} -> {prices.index.max().date()})"
)
print(f"  Foreign markets:        {list(foreign.keys())}")
print(
    f"  Cross-border neighbors: "
    f"{[c.replace('flow_', '').replace('_net_mw', '') for c in flows_pn.columns]}"
)
print(f"  TTF gas series:         {ttf.index.min().date()} -> {ttf.index.max().date()}")
print(f"  EUA carbon series:      {eua.index.min().date()} -> {eua.index.max().date()}")
print(f"  Weather history:        {'available' if weather is not None else 'not loaded'}")

print("\n[2/4] Building feature matrix and supply-mix features...")
builder = FeatureBuilder(
    prices=prices,
    load=load,
    wind=wind,
    solar=solar,
    flows=flows,
    flows_per_neighbor=flows_pn,
    gen_total=gen_total,
    weather=weather,
    gas_eur_per_mwh=ttf,
    carbon_eur_per_t=eua,
    external_prices=foreign,
)
base_df = builder.build()
df_clean = base_df.dropna(subset=["price_lag_14d", "load_forecast_mw"])
train_base = df_clean.loc["2025-01-15":"2025-12-31"].copy()
test_base = df_clean.loc["2026-04-01":"2026-04-30"].copy()

mix_model = ProductionEstimator(alpha=4.0)
mix_model.fit(train_base, gen_by_type)
train = add_estimated_supply_features(train_base, mix_model.predict(train_base))
test = add_estimated_supply_features(test_base, mix_model.predict(test_base))

to_drop = [
    c
    for c in train.columns
    if c != "dam_price_eur_mwh"
    and (train[c].notna().mean() < 0.5 or test[c].notna().mean() < 0.5)
]
if to_drop:
    train = train.drop(columns=to_drop)
    test = test.drop(columns=to_drop)

mix_cols = [
    c for c in train.columns if c.endswith("_estimated_mw") or c.startswith("dam_share_")
]
print(f"  train: {len(train):,} rows, {len(train.columns) - 1} features")
print(
    f"  test:  {len(test):,} rows "
    f"({test.index.min().date()} -> {test.index.max().date()})"
)
print(
    f"  test mean price: EUR{test['dam_price_eur_mwh'].mean():.2f}/MWh, "
    f"negative slots: {(test['dam_price_eur_mwh'] < 0).sum()}"
)
print(f"  supply-mix columns:     {mix_cols}")

print("\n[3/4] Training Ridge and LightGBM models...")
ridge = RidgeMLForecaster(alpha=1.0)
ridge.fit(train)

y_actual = test["dam_price_eur_mwh"].values
y_ridge = ridge.predict(test)
try:
    gbm = GBMForecaster(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=20,
    )
    gbm.fit(train)
    y_gbm = gbm.predict(test)
    gbm_available = True
except ImportError as exc:
    print(f"  warning: LightGBM unavailable; skipping GBM strategy ({exc})")
    y_gbm = np.full(len(test), np.nan)
    gbm_available = False
y_naive = test["price_lag_7d"].values

print("\n[4/4] Day-by-day revenue backtest...")
asset = BatteryAsset(
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

records = []
for day in sorted(set(test.index.normalize())):
    mask = test.index.normalize() == day
    if mask.sum() != 96:
        continue
    actual = y_actual[mask]
    rev_pf = settle_dispatch(opt, actual, actual)
    rev_r = settle_dispatch(opt, y_ridge[mask], actual)
    rev_g = settle_dispatch(opt, y_gbm[mask], actual) if gbm_available else np.nan
    if np.any(np.isnan(y_naive[mask])):
        rev_n = None
    else:
        rev_n = settle_dispatch(opt, y_naive[mask], actual)
    records.append(
        {
            "date": day,
            "perfect_revenue": rev_pf,
            "ridge_revenue": rev_r,
            "gbm_revenue": rev_g,
            "naive_revenue": rev_n,
            "actual_neg_slots": int(np.sum(actual < 0)),
        }
    )

bt = pd.DataFrame(records).set_index("date")

print("\n" + "=" * 78)
print(" RESULTS - Percent of theoretical maximum revenue captured")
print("=" * 78)
total_pf = bt["perfect_revenue"].sum()
for label, col in [
    ("Perfect Foresight (oracle)", "perfect_revenue"),
    ("Ridge ML (production model)", "ridge_revenue"),
    ("LightGBM ML", "gbm_revenue"),
    ("Naive (last-week)", "naive_revenue"),
]:
    series = bt[col].dropna() if col == "naive_revenue" else bt[col]
    if series.dropna().empty:
        print(f"  {label:30s}  unavailable")
        continue
    total = series.sum()
    pct = total / total_pf * 100 if total_pf else np.nan
    avg = series.mean()
    annual = avg * 365 / asset.capacity_mwh
    print(
        f"  {label:30s}  EUR{total:>9,.0f}  ({pct:5.1f}%)"
        f"   = EUR{avg:6.2f}/day   ann. EUR{annual:>7,.0f}/MWh/yr"
    )

out_path = os.path.join(ROOT, "data", "revenue_backtest_v2_april_2026.csv")
bt.to_csv(out_path)
print(f"\n  Saved {os.path.relpath(out_path, ROOT)}")
print("\nDone.")
