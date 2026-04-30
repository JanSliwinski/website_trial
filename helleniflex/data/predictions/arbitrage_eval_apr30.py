"""
Arbitrage evaluation — April 30 2026 delivery day.

Three branch configurations evaluated head-to-head:
  A  forecast_v2       — Ridge, ENTSO-E only, no ProductionEstimator
  B  dam-forecast-upgrade — Ridge + ProductionEstimator + per-neighbor flows
  C  merged (current)  — B + IPTO load/RES override + Open-Meteo weather

All three use:
  - identical battery config  (1 MW / 2 MWh LFP, 90% RTE, cycle_cost=3 €/MWh)
  - identical actual prices   (HEnEx 20260430_EL-DAM_Results_EN_v01.csv)
  - identical train cutoff    (ENTSO-E data strictly before 2026-04-30 CET)
  - identical delivery window (CET 2026-04-29 23:00 → 2026-04-30 22:45, 96 slots)
  - identical optimizer       (BatteryOptimizer, MILP, HiGHS)

No branch checkout required — each config is reproduced from the available
package (current merged branch) by selectively enabling features.
"""

import sys, io, warnings
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

import os, datetime
import numpy as np
import pandas as pd
from pathlib import Path

PRED_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DATA     = PRED_DIR.parent
ROOT     = DATA.parent
REPO     = ROOT.parent
ENTSOE   = DATA / "entsoe"
EXT      = DATA / "external"
FP       = DATA / "foreign_prices"

sys.path.insert(0, str(ROOT / "src"))

from helleniflex import (
    BatteryAsset, BatteryOptimizer,
    FeatureBuilder, RidgeMLForecaster,
    ProductionEstimator, add_estimated_supply_features,
    load_entsoe_prices_directory,
    load_entsoe_load_directory,
    load_entsoe_renewable_directory,
    load_entsoe_total_generation_directory,
    load_entsoe_generation_per_type_directory,
    load_entsoe_flows_directory,
    load_entsoe_flows_by_neighbor_directory,
    load_foreign_prices_directory,
    fetch_ipto_forecasts,
    fetch_openmeteo_forecast,
)

SEP = "=" * 72

# ─── delivery window (CET tz-naive) ──────────────────────────────────────────
PRED_IDX  = pd.date_range("2026-04-29 23:00", periods=96, freq="15min")
TRAIN_END = pd.Timestamp("2026-04-29 22:45")
DELIVERY  = datetime.date(2026, 4, 30)

# ─── battery (fixed across all branches) ─────────────────────────────────────
BATTERY = BatteryAsset(
    name="1MW/2MWh LFP",
    power_mw=1.0,
    capacity_mwh=2.0,
    eta_charge=0.94,
    eta_discharge=0.94,
    cycle_cost_eur_per_mwh=3.0,
    daily_cycle_limit=1.5,
)
OPT = BatteryOptimizer(BATTERY, use_binary=True)

print(SEP)
print("  Arbitrage Evaluation — April 30 2026 — Three Branch Configs")
print(SEP)
print(f"  Battery : {BATTERY.name}  (RTE {BATTERY.eta_charge*BATTERY.eta_discharge*100:.0f}%)")
print(f"  Delivery: {DELIVERY}  |  {len(PRED_IDX)} × 15-min slots  (CET {PRED_IDX[0]} → {PRED_IDX[-1]})")
print(f"  Train   : strictly before {TRAIN_END}")


# ══════════════════════════════════════════════════════════════════════════════
# LOAD ALL DATA ONCE
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}\n  [data] Loading historical ENTSO-E + external series\n{SEP}")

prices_hist = load_entsoe_prices_directory(str(ENTSOE))
load_hist   = load_entsoe_load_directory(str(ENTSOE))
wind_hist   = load_entsoe_renewable_directory(str(ENTSOE), label="wind")
solar_hist  = load_entsoe_renewable_directory(str(ENTSOE), label="solar")
gen_hist    = load_entsoe_total_generation_directory(str(ENTSOE))
gen_type    = load_entsoe_generation_per_type_directory(str(ENTSOE))
flows_hist  = load_entsoe_flows_directory(str(ENTSOE))
flows_pn    = load_entsoe_flows_by_neighbor_directory(str(ENTSOE))
ext_prices  = load_foreign_prices_directory(str(FP))
ttf_series  = pd.read_csv(EXT / "ttf_gas_daily_eur_per_mwh.csv",
                          index_col=0, parse_dates=True)["ttf_eur_per_mwh"]
eua_series  = pd.read_csv(EXT / "eua_carbon_daily_eur_per_t.csv",
                          index_col=0, parse_dates=True).iloc[:, 0]

prices_train = prices_hist[prices_hist.index <= TRAIN_END]
print(f"  Training prices : {len(prices_train)} slots  ({prices_train.index[0].date()} → {prices_train.index[-1]})")


# ── IPTO and weather for Config C ─────────────────────────────────────────────
print(f"\n  [live] Fetching IPTO ISP1 for {DELIVERY}...")
try:
    ipto_raw = fetch_ipto_forecasts(DELIVERY)
    ipto_cet = ipto_raw.tz_convert("Europe/Berlin").tz_localize(None)
    assert list(ipto_cet.index) == list(PRED_IDX), "IPTO index mismatch"
    print(f"  IPTO load  : {ipto_cet['load_forecast_mw'].min():.0f}–{ipto_cet['load_forecast_mw'].max():.0f} MW")
    print(f"  IPTO RES   : {ipto_cet['res_da_forecast_mw'].min():.0f}–{ipto_cet['res_da_forecast_mw'].max():.0f} MW")
    ipto_ok = True
except Exception as exc:
    print(f"  IPTO unavailable: {exc}")
    ipto_ok = False
    ipto_cet = None

print(f"\n  [live] Fetching Open-Meteo archive for {DELIVERY}...")
try:
    wx_raw = fetch_openmeteo_forecast(DELIVERY)
    # wx_raw is tz-naive Athens-local → shift -1 h to CET
    wx_cet = wx_raw.copy()
    wx_cet.index = wx_raw.index - pd.Timedelta(hours=1)
    wx_15 = wx_cet.reindex(PRED_IDX, method="ffill").ffill().bfill()
    print(f"  Weather temp: {wx_raw['temperature_2m'].min():.1f}–{wx_raw['temperature_2m'].max():.1f} °C")
    wx_ok = True
except Exception as exc:
    print(f"  Weather unavailable: {exc}")
    wx_ok = False
    wx_15 = None


# ── Actual April 30 prices (HEnEx 20260430_EL-DAM_Results_EN_v01.csv) ─────────
actual_prices = np.array([
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
print(f"\n  Actual MCP : min={actual_prices.min():.2f}  max={actual_prices.max():.2f}  mean={actual_prices.mean():.2f} €/MWh")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def make_lag_features(prices_train: pd.Series) -> dict:
    """Compute price lag and rolling features for the prediction window."""
    dummy = pd.Series(np.nan, index=PRED_IDX, name="dam_price_eur_mwh")
    ext = pd.concat([prices_train, dummy])
    ext = ext[~ext.index.duplicated(keep="last")]

    feats = {}
    for days_back, label in [(1,"1d"),(2,"2d"),(7,"7d"),(14,"14d")]:
        feats[f"price_lag_{label}"] = ext.shift(days_back*96).reindex(PRED_IDX).values
    rb = ext.shift(96)
    feats["price_roll24h_mean"] = rb.rolling("1D").mean().reindex(PRED_IDX).values
    feats["price_roll7d_mean"]  = rb.rolling("7D").mean().reindex(PRED_IDX).values
    feats["price_roll7d_std"]   = rb.rolling("7D").std().reindex(PRED_IDX).values
    return feats


def make_calendar_features() -> dict:
    slot = PRED_IDX.hour * 4 + PRED_IDX.minute // 15
    return {
        "cal_hour":       PRED_IDX.hour,
        "cal_minute":     PRED_IDX.minute,
        "cal_dayofweek":  PRED_IDX.dayofweek,
        "cal_is_weekend": (PRED_IDX.dayofweek >= 5).astype(int),
        "cal_month":      PRED_IDX.month,
        "cal_dayofyear":  PRED_IDX.dayofyear,
        "cal_slot_sin":   np.sin(2 * np.pi * slot / 96),
        "cal_slot_cos":   np.cos(2 * np.pi * slot / 96),
    }


def make_ext_price_lags(ext_prices: dict, prices_train: pd.Series) -> dict:
    dummy = pd.Series(np.nan, index=PRED_IDX, name="dam_price_eur_mwh")
    ext = pd.concat([prices_train, dummy])
    ext = ext[~ext.index.duplicated(keep="last")]
    feats = {}
    for cc, s in ext_prices.items():
        aligned = s.reindex(ext.index, method="ffill")
        feats[f"price_{cc.lower()}_lag_1d"] = aligned.shift(1, freq="D").reindex(PRED_IDX).values
    return feats


def build_live_frame(
    load_vals, wind_vals, solar_vals, res_vals,
    flow_net, flow_imp, flow_exp, gen_vals,
    ttf_val, eua_val,
    price_lags, cal, ext_lags,
    weather_df=None,
) -> pd.DataFrame:
    live = pd.DataFrame(index=PRED_IDX)
    live["load_forecast_mw"]                = load_vals
    live["wind_da_forecast_mw"]             = wind_vals
    live["solar_da_forecast_mw"]            = solar_vals
    live["renewables_total_da_forecast_mw"] = res_vals
    live["residual_demand_mw"]              = load_vals - res_vals
    live["flow_net_import_mw"]              = flow_net
    live["flow_imports_mw"]                 = flow_imp
    live["flow_exports_mw"]                 = flow_exp
    live["gen_total_forecast_mw"]           = gen_vals
    live["gas_ttf_eur_per_mwh"]             = ttf_val
    live["carbon_eua_eur_per_t"]            = eua_val
    for k, v in price_lags.items(): live[k] = v
    for k, v in cal.items():        live[k] = v
    for k, v in ext_lags.items():   live[k] = v
    if weather_df is not None:
        for col in weather_df.columns:
            live[f"weather_{col}"] = weather_df[col].values
    return live


def align_and_predict(model, live_df: pd.DataFrame) -> np.ndarray:
    feat_names = model.feature_names_
    for c in feat_names:
        if c not in live_df.columns:
            live_df[c] = np.nan
    return model.predict(live_df[feat_names])


def compute_arbitrage(predicted: np.ndarray, actual: np.ndarray, label: str) -> dict:
    pred_result   = OPT.optimize(predicted, dt_hours=0.25)
    oracle_result = OPT.optimize(actual,    dt_hours=0.25)
    realized      = BatteryOptimizer.settle(pred_result,   actual)
    oracle_rev    = oracle_result.revenue_eur

    mae  = float(np.abs(predicted - actual).mean())
    rmse = float(np.sqrt(((predicted - actual)**2).mean()))
    bias = float((predicted - actual).mean())

    # annualise: EUR/MW/year = revenue_EUR / power_MW * 365
    ann_realized = realized / BATTERY.power_mw * 365
    ann_oracle   = oracle_rev / BATTERY.power_mw * 365
    pct_oracle   = realized / oracle_rev * 100 if oracle_rev > 0 else 0.0

    print(f"\n  [{label}]  MAE={mae:.1f}  RMSE={rmse:.1f}  bias={bias:+.1f} €/MWh")
    print(f"   Realized profit  : {realized:7.2f} €/day  →  {ann_realized:8.0f} €/MW/yr")
    print(f"   Oracle profit    : {oracle_rev:7.2f} €/day  →  {ann_oracle:8.0f} €/MW/yr")
    print(f"   % of oracle      : {pct_oracle:.1f}%")
    print(f"   Optimizer status : pred={pred_result.status}  oracle={oracle_result.status}")

    return dict(
        label=label,
        mae=mae, rmse=rmse, bias=bias,
        realized_eur_day=realized,
        oracle_eur_day=oracle_rev,
        realized_ann=ann_realized,
        oracle_ann=ann_oracle,
        pct_oracle=pct_oracle,
        pred_min=predicted.min(), pred_max=predicted.max(), pred_mean=predicted.mean(),
    )


# ── shared proxy data for April 30 (Apr 29 acts as proxy for flows) ───────────
APR29_CET_START = pd.Timestamp("2026-04-28 23:00")
APR29_CET_END   = pd.Timestamp("2026-04-29 22:45")
flows_apr29     = flows_hist.loc[APR29_CET_START:APR29_CET_END]
flows_pn_apr29  = flows_pn.loc[APR29_CET_START:APR29_CET_END]

# ENTSO-E day-ahead forecasts for April 30 (already in the CSVs)
load_da  = load_hist["load_forecast_mw"].reindex(PRED_IDX)
wind_da  = wind_hist["wind_da_forecast_mw"].reindex(PRED_IDX, method="ffill")
solar_da = solar_hist["solar_da_forecast_mw"].reindex(PRED_IDX, method="ffill")
gen_da   = gen_hist["gen_forecast_mw"].reindex(PRED_IDX, method="ffill") if "gen_forecast_mw" in gen_hist.columns else pd.Series(np.nan, index=PRED_IDX)
res_entsoe = wind_da.fillna(0) + solar_da.fillna(0)

flow_net_proxy = flows_apr29["net_import_mw"].values    if len(flows_apr29)==96 else np.full(96, np.nan)
flow_imp_proxy = flows_apr29["total_imports_mw"].values if len(flows_apr29)==96 else np.full(96, np.nan)
flow_exp_proxy = flows_apr29["total_exports_mw"].values if len(flows_apr29)==96 else np.full(96, np.nan)

ttf_apr29 = float(ttf_series[ttf_series.index.date <= datetime.date(2026,4,29)].iloc[-1])
eua_apr29 = float(eua_series.dropna()[eua_series.dropna().index.date <= datetime.date(2026,4,29)].iloc[-1])

lags = make_lag_features(prices_train)
cal  = make_calendar_features()
elags= make_ext_price_lags(ext_prices, prices_train)

results = []


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG A — forecast_v2 equivalent
# Ridge · ENTSO-E features only · no ProductionEstimator · no per-neighbor flows
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  CONFIG A — forecast_v2  (Ridge · ENTSO-E only · no ProductionEstimator)")
print(SEP)

fb_A = FeatureBuilder(
    prices           = prices_train,
    load             = load_hist,
    wind             = wind_hist,
    solar            = solar_hist,
    flows            = flows_hist,
    flows_per_neighbor = None,
    gen_total        = gen_hist,
    weather          = None,
    gas_eur_per_mwh  = ttf_series,
    carbon_eur_per_t = eua_series,
    external_prices  = ext_prices,
)
feat_A = fb_A.build(drop_leakage=True)
train_A = feat_A[(feat_A.index >= "2025-01-01") & feat_A["dam_price_eur_mwh"].notna()].copy()
model_A = RidgeMLForecaster(alpha=1.0)
model_A.fit(train_A)
print(f"  Trained on {len(train_A)} samples  |  {len(model_A.feature_names_)} features")

live_A = build_live_frame(
    load_vals=load_da.values,
    wind_vals=wind_da.values,
    solar_vals=solar_da.values,
    res_vals=res_entsoe.values,
    flow_net=flow_net_proxy,
    flow_imp=flow_imp_proxy,
    flow_exp=flow_exp_proxy,
    gen_vals=gen_da.values,
    ttf_val=ttf_apr29, eua_val=eua_apr29,
    price_lags=lags, cal=cal, ext_lags=elags,
)
pred_A = align_and_predict(model_A, live_A)
results.append(compute_arbitrage(pred_A, actual_prices, "A · forecast_v2"))


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG B — dam-forecast-upgrade equivalent
# Ridge · ENTSO-E + ProductionEstimator + per-neighbor flows
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  CONFIG B — dam-forecast-upgrade  (Ridge + ProductionEstimator + flows/neighbor)")
print(SEP)

fb_B = FeatureBuilder(
    prices           = prices_train,
    load             = load_hist,
    wind             = wind_hist,
    solar            = solar_hist,
    flows            = flows_hist,
    flows_per_neighbor = flows_pn,
    gen_total        = gen_hist,
    weather          = None,
    gas_eur_per_mwh  = ttf_series,
    carbon_eur_per_t = eua_series,
    external_prices  = ext_prices,
)
feat_B = fb_B.build(drop_leakage=True)
train_B_base = feat_B[(feat_B.index >= "2025-01-01") & feat_B["dam_price_eur_mwh"].notna()].copy()

mix_B = ProductionEstimator(alpha=4.0)
mix_B.fit(train_B_base, gen_type)
train_B = add_estimated_supply_features(train_B_base, mix_B.predict(train_B_base))
model_B = RidgeMLForecaster(alpha=1.0)
model_B.fit(train_B)
print(f"  Trained on {len(train_B)} samples  |  {len(model_B.feature_names_)} features")
print(f"  ProductionEstimator targets: {list(mix_B.models_.keys())}")

# Per-neighbor flows for April 30 (use Apr 29 as proxy)
if len(flows_pn_apr29) == 96:
    fpn_vals = {c: flows_pn_apr29[c].values for c in flows_pn_apr29.columns}
else:
    fpn_vals = {c: np.full(96, np.nan) for c in flows_pn.columns}

live_B_base = build_live_frame(
    load_vals=load_da.values,
    wind_vals=wind_da.values,
    solar_vals=solar_da.values,
    res_vals=res_entsoe.values,
    flow_net=flow_net_proxy,
    flow_imp=flow_imp_proxy,
    flow_exp=flow_exp_proxy,
    gen_vals=gen_da.values,
    ttf_val=ttf_apr29, eua_val=eua_apr29,
    price_lags=lags, cal=cal, ext_lags=elags,
)
for col, vals in fpn_vals.items():
    live_B_base[col] = vals

live_B_full = pd.DataFrame(index=PRED_IDX)
for c in model_B.feature_names_:
    live_B_full[c] = live_B_base.get(c, pd.Series(np.nan, index=PRED_IDX))

# Add ProductionEstimator columns to live features
mix_pred_B = mix_B.predict(live_B_full[mix_B.feature_names_])
for c in mix_pred_B.columns:
    live_B_full[c] = mix_pred_B[c].values

pred_B = align_and_predict(model_B, live_B_full)
results.append(compute_arbitrage(pred_B, actual_prices, "B · dam-forecast-upgrade"))


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG C — merged branch
# Ridge + ProductionEstimator + per-neighbor flows + IPTO override + weather
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  CONFIG C — merged  (B + IPTO load/RES override + Open-Meteo weather)")
print(SEP)

if wx_ok:
    fb_C = FeatureBuilder(
        prices           = prices_train,
        load             = load_hist,
        wind             = wind_hist,
        solar            = solar_hist,
        flows            = flows_hist,
        flows_per_neighbor = flows_pn,
        gen_total        = gen_hist,
        weather          = wx_15,   # historical weather for training slots
        gas_eur_per_mwh  = ttf_series,
        carbon_eur_per_t = eua_series,
        external_prices  = ext_prices,
    )
else:
    fb_C = fb_B  # reuse if weather unavailable

feat_C = fb_C.build(drop_leakage=True)
train_C_base = feat_C[(feat_C.index >= "2025-01-01") & feat_C["dam_price_eur_mwh"].notna()].copy()
mix_C = ProductionEstimator(alpha=4.0)
mix_C.fit(train_C_base, gen_type)
train_C = add_estimated_supply_features(train_C_base, mix_C.predict(train_C_base))
model_C = RidgeMLForecaster(alpha=1.0)
model_C.fit(train_C)
print(f"  Trained on {len(train_C)} samples  |  {len(model_C.feature_names_)} features")

# IPTO overrides for April 30
if ipto_ok:
    load_C   = ipto_cet["load_forecast_mw"].values
    res_ipto = ipto_cet["res_da_forecast_mw"].values
    # Scale ENTSO-E wind/solar so their sum matches IPTO total RES
    wind_raw  = wind_da.fillna(0).values
    solar_raw = solar_da.fillna(0).values
    entsoe_tot = wind_raw + solar_raw
    with np.errstate(divide="ignore", invalid="ignore"):
        wind_share = np.where(entsoe_tot > 0, wind_raw / entsoe_tot, 0.5)
    wind_C  = res_ipto * wind_share
    solar_C = res_ipto * (1 - wind_share)
    res_C   = res_ipto
    print(f"  IPTO override: load avg {load_C.mean():.0f} MW, RES avg {res_C.mean():.0f} MW")
else:
    load_C = load_da.values
    wind_C = wind_da.values; solar_C = solar_da.values; res_C = res_entsoe.values
    print("  IPTO unavailable — using ENTSO-E DA forecasts as fallback")

wx_for_live = wx_15 if wx_ok else None

live_C_base = build_live_frame(
    load_vals=load_C,
    wind_vals=wind_C,
    solar_vals=solar_C,
    res_vals=res_C,
    flow_net=flow_net_proxy,
    flow_imp=flow_imp_proxy,
    flow_exp=flow_exp_proxy,
    gen_vals=gen_da.values,
    ttf_val=ttf_apr29, eua_val=eua_apr29,
    price_lags=lags, cal=cal, ext_lags=elags,
    weather_df=wx_for_live,
)
for col, vals in fpn_vals.items():
    live_C_base[col] = vals

live_C_full = pd.DataFrame(index=PRED_IDX)
for c in model_C.feature_names_:
    live_C_full[c] = live_C_base.get(c, pd.Series(np.nan, index=PRED_IDX))
mix_pred_C = mix_C.predict(live_C_full[mix_C.feature_names_])
for c in mix_pred_C.columns:
    live_C_full[c] = mix_pred_C[c].values

pred_C = align_and_predict(model_C, live_C_full)
results.append(compute_arbitrage(pred_C, actual_prices, "C · merged"))


# ══════════════════════════════════════════════════════════════════════════════
# ORACLE — perfect foresight
# ══════════════════════════════════════════════════════════════════════════════
oracle_res = OPT.optimize(actual_prices, dt_hours=0.25)
oracle_eur_day = oracle_res.revenue_eur
oracle_ann     = oracle_eur_day / BATTERY.power_mw * 365


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  SUMMARY — April 30 2026  (1 MW / 2 MWh LFP, RTE 88%, cycle_cost=3 €/MWh)")
print(SEP)

header = f"  {'Branch':<32}  {'MAE':>6}  {'RMSE':>6}  {'Bias':>6}  {'Real €/d':>9}  {'Ann €/MW/yr':>12}  {'% Oracle':>9}  {'Pred mean':>10}"
print(header)
print("  " + "-" * (len(header) - 2))
for r in results:
    print(
        f"  {r['label']:<32}  "
        f"{r['mae']:>6.1f}  {r['rmse']:>6.1f}  {r['bias']:>+6.1f}  "
        f"{r['realized_eur_day']:>9.2f}  "
        f"{r['realized_ann']:>12,.0f}  "
        f"{r['pct_oracle']:>8.1f}%  "
        f"{r['pred_mean']:>10.2f}"
    )
print(f"  {'Oracle (perfect foresight)':<32}  {'—':>6}  {'—':>6}  {'—':>6}  "
      f"{oracle_eur_day:>9.2f}  {oracle_ann:>12,.0f}  {'100.0%':>9}  {'(actual)':>10}")

print(f"\n  Actual MCP: min={actual_prices.min():.2f}  max={actual_prices.max():.2f}  "
      f"mean={actual_prices.mean():.2f}  near-zero slots={int((actual_prices<1).sum())}")

best = max(results, key=lambda r: r["realized_eur_day"])
print(f"\n  Best branch: {best['label']}  ({best['pct_oracle']:.1f}% of oracle)")
print(f"  Oracle ({oracle_ann:,.0f} €/MW/yr) implies annualised revenue across 365 days with same day profile.")


# ── save predictions CSV ──────────────────────────────────────────────────────
tod = (PRED_IDX + pd.Timedelta(hours=1)).strftime("%H:%M")  # CET → Athens
out = pd.DataFrame({
    "time_athens":     tod.values,
    "actual_mcp":      actual_prices,
    "pred_A":          pred_A.round(2),
    "pred_B":          pred_B.round(2),
    "pred_C":          pred_C.round(2),
})
out_path = PRED_DIR / "apr30_three_branch_predictions.csv"
out.to_csv(out_path, index=False)
print(f"\n  Predictions saved → {out_path}")
