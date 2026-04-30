"""
Walk-forward backtest for Greek DAM price forecasting in 2026.

This script tests the model properly:

For each available day in 2026:
1. Hide the target day from the model.
2. Train only on data strictly before the target day.
3. Build target-day features from past profiles only.
4. Forecast the 96 quarter-hour DAM prices.
5. Compare against actual DAM prices.
6. Save daily accuracy metrics and an averaged summary.

This prevents leakage from the day being predicted.

Run from repo root:

    python helleniflex\\examples\\backtest_2026_walkforward.py

Optional date range:

    python helleniflex\\examples\\backtest_2026_walkforward.py 2026-01-01 2026-04-30
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import Optional

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd

from helleniflex import (
    FeatureBuilder,
    GBMForecaster,
    ProductionEstimator,
    RidgeMLForecaster,
    add_estimated_supply_features,
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
OUT = os.path.join(ROOT, "data", "backtest_2026")

os.makedirs(OUT, exist_ok=True)


# =============================================================================
# Date helpers
# =============================================================================

def parse_date_range() -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Default: all of 2026.
    Optional:
        python script.py 2026-01-01 2026-04-30
    """
    if len(sys.argv) >= 3:
        start = pd.Timestamp(sys.argv[1]).normalize()
        end = pd.Timestamp(sys.argv[2]).normalize()
    else:
        start = pd.Timestamp("2026-01-01")
        end = pd.Timestamp("2026-12-31")

    return start, end


def target_15min_index(target_day: pd.Timestamp) -> pd.DatetimeIndex:
    return pd.date_range(
        start=target_day,
        end=target_day + pd.Timedelta(days=1) - pd.Timedelta(minutes=15),
        freq="15min",
    )


def target_hourly_index(target_day: pd.Timestamp) -> pd.DatetimeIndex:
    return pd.date_range(
        start=target_day,
        end=target_day + pd.Timedelta(days=1) - pd.Timedelta(hours=1),
        freq="h",
    )


# =============================================================================
# Leakage protection / trimming
# =============================================================================

def trim_before_day(obj, target_day: pd.Timestamp):
    """
    Keep only rows strictly before target_day.

    Works for:
    - DataFrame
    - Series
    - dict of DataFrames/Series
    """
    if obj is None:
        return obj

    if isinstance(obj, dict):
        return {
            key: trim_before_day(value, target_day)
            for key, value in obj.items()
        }

    if not isinstance(obj, (pd.DataFrame, pd.Series)):
        return obj

    if len(obj) == 0:
        return obj

    if not isinstance(obj.index, pd.DatetimeIndex):
        return obj

    return obj[obj.index < target_day].copy()


def remove_target_day_rows(obj, target_day: pd.Timestamp):
    """
    Remove only rows from the target day.

    Works for:
    - DataFrame
    - Series
    - dict of DataFrames/Series
    """
    if obj is None:
        return obj

    if isinstance(obj, dict):
        return {
            key: remove_target_day_rows(value, target_day)
            for key, value in obj.items()
        }

    if not isinstance(obj, (pd.DataFrame, pd.Series)):
        return obj

    if len(obj) == 0:
        return obj

    if not isinstance(obj.index, pd.DatetimeIndex):
        return obj

    return obj[obj.index.normalize() != target_day].copy()


def add_empty_target_price_rows(
    prices_before: pd.Series,
    target_day: pd.Timestamp,
) -> pd.Series:
    """
    Add NaN DAM price rows for the target day.

    These are the rows the model will predict.
    Actual target-day prices are kept separately for evaluation.
    """
    idx = target_15min_index(target_day)

    horizon = pd.Series(
        np.nan,
        index=idx,
        name=prices_before.name,
    )

    return pd.concat([prices_before, horizon]).sort_index()


# =============================================================================
# Generic profile projection helpers
# =============================================================================

def lagged_profile(
    series: pd.Series,
    target_idx: pd.DatetimeIndex,
) -> pd.Series:
    """
    Forecast a target-day profile using known historical profiles.

    Priority:
    1. Same day last week.
    2. Yesterday.
    3. Forward/backward fill.
    """
    last_week = pd.Series(
        series.reindex(target_idx - pd.Timedelta(days=7)).values,
        index=target_idx,
    )

    yesterday = pd.Series(
        series.reindex(target_idx - pd.Timedelta(days=1)).values,
        index=target_idx,
    )

    out = last_week.combine_first(yesterday)
    out = out.ffill().bfill()

    return out


def has_enough_history(df: pd.DataFrame | pd.Series, target_day: pd.Timestamp) -> bool:
    """
    Require at least 14 days of history before testing a day.
    This is needed because the model uses price_lag_14d.
    """
    if df is None or len(df) == 0:
        return False

    if not isinstance(df.index, pd.DatetimeIndex):
        return False

    min_needed = target_day - pd.Timedelta(days=14)

    return df.index.min() <= min_needed


def weather_series(
    weather: pd.DataFrame | None,
    col: str,
    idx: pd.DatetimeIndex,
) -> pd.Series:
    if weather is None or col not in weather.columns:
        return pd.Series(np.nan, index=idx)

    return pd.Series(
        weather[col].reindex(idx, method="ffill").values,
        index=idx,
    )


def extend_weather_from_past(
    weather_before: pd.DataFrame | None,
    target_day: pd.Timestamp,
) -> pd.DataFrame | None:
    """
    Build target-day weather features using only past weather profiles.

    This is stricter than a real forecast because it does not use actual
    target-day weather. It uses last week's same slots / yesterday as fallback.
    """
    if weather_before is None or len(weather_before) == 0:
        return weather_before

    idx = target_hourly_index(target_day)

    projected = pd.DataFrame(index=idx)

    for col in weather_before.columns:
        if pd.api.types.is_numeric_dtype(weather_before[col]):
            projected[col] = lagged_profile(weather_before[col], idx).values
        else:
            projected[col] = np.nan

    out = pd.concat([weather_before, projected]).sort_index()
    out = out[~out.index.duplicated(keep="last")]

    return out


def extend_load_forecast_from_past(
    load_before: pd.DataFrame,
    target_day: pd.Timestamp,
    weather_all: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Create target-day load forecast using only past load profile plus simple
    temperature adjustment.
    """
    idx = target_15min_index(target_day)

    base = lagged_profile(load_before["load_forecast_mw"], idx)

    future_temp = weather_series(weather_all, "temperature_2m", idx)
    source_temp = pd.Series(
        weather_series(
            weather_all,
            "temperature_2m",
            idx - pd.Timedelta(days=7),
        ).values,
        index=idx,
    )

    discomfort_delta = (future_temp - 20.0).abs() - (source_temp - 20.0).abs()

    adjusted = (base + discomfort_delta.fillna(0.0) * 45.0).clip(lower=0.0)

    projected = pd.DataFrame(
        {
            "load_actual_mw": np.nan,
            "load_forecast_mw": adjusted.values,
        },
        index=idx,
    )

    out = pd.concat([load_before, projected]).sort_index()
    out = out[~out.index.duplicated(keep="last")]

    return out


def extend_res_forecast_from_past(
    res_before: pd.DataFrame,
    target_day: pd.Timestamp,
    label: str,
    weather_all: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Create target-day wind/solar forecast using past RES profiles and weather.
    """
    forecast_col = [c for c in res_before.columns if "da_forecast" in c][0]
    actual_col = [c for c in res_before.columns if "actual" in c][0]

    idx = target_hourly_index(target_day)

    base = lagged_profile(res_before[forecast_col], idx)

    if label == "solar":
        rad = weather_series(weather_all, "shortwave_radiation", idx).clip(lower=0.0)

        if rad.notna().any() and rad.max() > 0:
            daily_peak = float(base.max()) if base.notna().any() else 0.0
            projected_values = daily_peak * (rad / rad.max())
        else:
            projected_values = base

    elif label == "wind":
        future_speed = weather_series(weather_all, "wind_speed_10m", idx)
        source_speed = pd.Series(
            weather_series(
                weather_all,
                "wind_speed_10m",
                idx - pd.Timedelta(days=7),
            ).values,
            index=idx,
        )

        scale = (
            future_speed
            / source_speed.replace(0, np.nan)
        ).pow(3).clip(0.4, 1.8)

        projected_values = base * scale.fillna(1.0)

    else:
        projected_values = base

    projected = pd.DataFrame(
        {
            forecast_col: projected_values.clip(lower=0.0).values,
            actual_col: np.nan,
        },
        index=idx,
    )

    out = pd.concat([res_before, projected]).sort_index()
    out = out[~out.index.duplicated(keep="last")]

    return out


def extend_hourly_profile_from_past(
    df_before: pd.DataFrame,
    target_day: pd.Timestamp,
    value_col: str,
    projected_values: Optional[pd.Series] = None,
) -> pd.DataFrame:
    idx = target_hourly_index(target_day)

    if projected_values is not None:
        values = projected_values.reindex(idx).ffill().bfill()
    else:
        values = lagged_profile(df_before[value_col], idx)

    projected = pd.DataFrame(index=idx)

    for col in df_before.columns:
        projected[col] = np.nan

    projected[value_col] = values.values

    out = pd.concat([df_before, projected]).sort_index()
    out = out[~out.index.duplicated(keep="last")]

    return out


def extend_flow_profile_from_past(
    df_before: pd.DataFrame,
    target_day: pd.Timestamp,
) -> pd.DataFrame:
    idx = target_hourly_index(target_day)

    projected = pd.DataFrame(index=idx)

    for col in df_before.columns:
        projected[col] = lagged_profile(df_before[col], idx).values

    out = pd.concat([df_before, projected]).sort_index()
    out = out[~out.index.duplicated(keep="last")]

    return out


def extend_foreign_prices_from_past(
    foreign_before,
    target_day: pd.Timestamp,
):
    """
    Extend neighbouring price dictionary using past profiles.
    """
    if not isinstance(foreign_before, dict):
        return foreign_before

    idx = target_15min_index(target_day)

    out = {}

    for key, value in foreign_before.items():
        if not isinstance(value, (pd.DataFrame, pd.Series)):
            out[key] = value
            continue

        if len(value) == 0 or not isinstance(value.index, pd.DatetimeIndex):
            out[key] = value
            continue

        if isinstance(value, pd.Series):
            projected = lagged_profile(value, idx)
            projected.name = value.name
            combined = pd.concat([value, projected]).sort_index()
            combined = combined[~combined.index.duplicated(keep="last")]
            out[key] = combined
            continue

        projected = pd.DataFrame(index=idx)

        for col in value.columns:
            if pd.api.types.is_numeric_dtype(value[col]):
                projected[col] = lagged_profile(value[col], idx).values
            else:
                projected[col] = np.nan

        combined = pd.concat([value, projected]).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]

        out[key] = combined

    return out


def extend_daily_series_from_past(
    series_before: pd.Series,
    target_day: pd.Timestamp,
) -> pd.Series:
    """
    Extend daily gas/carbon series to the target day using the latest known value.

    This avoids using the actual target-day value.
    """
    if series_before is None or len(series_before) == 0:
        return series_before

    target_value = series_before.dropna().iloc[-1]

    target = pd.Series(
        [target_value],
        index=pd.DatetimeIndex([target_day]),
        name=series_before.name,
    )

    out = pd.concat([series_before, target]).sort_index()
    out = out[~out.index.duplicated(keep="last")]

    return out


def series_or_nan(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col]

    return pd.Series(np.nan, index=df.index, name=col)


# =============================================================================
# Metrics
# =============================================================================

def calculate_metrics(actual: pd.Series, predicted: pd.Series) -> dict:
    merged = pd.DataFrame(
        {
            "actual": actual,
            "predicted": predicted,
        }
    ).dropna()

    if len(merged) == 0:
        return {
            "n": 0,
            "mae": np.nan,
            "rmse": np.nan,
            "bias": np.nan,
            "correlation": np.nan,
            "directional_accuracy": np.nan,
            "normalised_mae": np.nan,
        }

    error = merged["predicted"] - merged["actual"]
    abs_error = error.abs()

    mae = abs_error.mean()
    rmse = np.sqrt((error ** 2).mean())
    bias = error.mean()

    if len(merged) > 1:
        correlation = merged["predicted"].corr(merged["actual"])
    else:
        correlation = np.nan

    actual_diff = merged["actual"].diff()
    pred_diff = merged["predicted"].diff()

    direction_mask = actual_diff.notna() & pred_diff.notna()

    if direction_mask.sum() > 0:
        directional_accuracy = (
            np.sign(actual_diff[direction_mask])
            == np.sign(pred_diff[direction_mask])
        ).mean()
    else:
        directional_accuracy = np.nan

    price_range = merged["actual"].max() - merged["actual"].min()

    if price_range and price_range != 0:
        normalised_mae = mae / price_range
    else:
        normalised_mae = np.nan

    return {
        "n": len(merged),
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "correlation": correlation,
        "directional_accuracy": directional_accuracy,
        "normalised_mae": normalised_mae,
    }


# =============================================================================
# One-day backtest
# =============================================================================

def forecast_one_day(
    target_day: pd.Timestamp,
    full_prices: pd.Series,
    full_load: pd.DataFrame,
    full_gen_total: pd.DataFrame,
    full_gen_by_type: pd.DataFrame,
    full_wind: pd.DataFrame,
    full_solar: pd.DataFrame,
    full_flows: pd.DataFrame,
    full_flows_pn: pd.DataFrame,
    full_foreign,
    full_ttf: pd.Series,
    full_eua: pd.Series,
    full_weather: pd.DataFrame | None,
    use_gbm: bool = False,
) -> tuple[pd.DataFrame | None, dict]:
    """
    Forecast one target day using only data strictly before that day.
    """
    idx15 = target_15min_index(target_day)

    actual = full_prices.reindex(idx15)

    if actual.notna().sum() < 80:
        return None, {
            "date": target_day.date(),
            "status": "skipped_no_actual_prices",
        }

    if not has_enough_history(full_prices, target_day):
        return None, {
            "date": target_day.date(),
            "status": "skipped_not_enough_history",
        }

    prices_before = trim_before_day(full_prices, target_day)
    load_before = trim_before_day(full_load, target_day)
    gen_total_before = trim_before_day(full_gen_total, target_day)
    gen_by_type_before = trim_before_day(full_gen_by_type, target_day)
    wind_before = trim_before_day(full_wind, target_day)
    solar_before = trim_before_day(full_solar, target_day)
    flows_before = trim_before_day(full_flows, target_day)
    flows_pn_before = trim_before_day(full_flows_pn, target_day)
    foreign_before = trim_before_day(full_foreign, target_day)
    ttf_before = trim_before_day(full_ttf, target_day)
    eua_before = trim_before_day(full_eua, target_day)
    weather_before = trim_before_day(full_weather, target_day)

    try:
        weather_all = extend_weather_from_past(weather_before, target_day)

        load = extend_load_forecast_from_past(
            load_before,
            target_day,
            weather_all,
        )

        wind = extend_res_forecast_from_past(
            wind_before,
            target_day,
            "wind",
            weather_all,
        )

        solar = extend_res_forecast_from_past(
            solar_before,
            target_day,
            "solar",
            weather_all,
        )

        flows = extend_flow_profile_from_past(
            flows_before,
            target_day,
        )

        flows_pn = extend_flow_profile_from_past(
            flows_pn_before,
            target_day,
        )

        foreign = extend_foreign_prices_from_past(
            foreign_before,
            target_day,
        )

        ttf = extend_daily_series_from_past(
            ttf_before,
            target_day,
        )

        eua = extend_daily_series_from_past(
            eua_before,
            target_day,
        )

        target_load_hourly = load["load_forecast_mw"].reindex(
            target_hourly_index(target_day),
            method="ffill",
        )

        gen_total = extend_hourly_profile_from_past(
            gen_total_before,
            target_day,
            "gen_forecast_mw",
            projected_values=target_load_hourly,
        )

        prices_ext = add_empty_target_price_rows(
            prices_before,
            target_day,
        )

        builder = FeatureBuilder(
            prices=prices_ext,
            load=load,
            wind=wind,
            solar=solar,
            flows=flows,
            flows_per_neighbor=flows_pn,
            gen_total=gen_total,
            weather=weather_all,
            gas_eur_per_mwh=ttf,
            carbon_eur_per_t=eua,
            external_prices=foreign,
        )

        base_df = builder.build()

        usable = base_df.dropna(
            subset=[
                "price_lag_14d",
                "load_forecast_mw",
            ]
        )

        train_base = usable[
            (usable.index < target_day)
            & usable["dam_price_eur_mwh"].notna()
        ].copy()

        target_end = target_day + pd.Timedelta(days=1) - pd.Timedelta(minutes=15)

        forecast_base = usable.loc[target_day:target_end].copy()

        if len(forecast_base) != 96:
            return None, {
                "date": target_day.date(),
                "status": f"skipped_incomplete_features_{len(forecast_base)}",
            }

        if forecast_base["dam_price_eur_mwh"].notna().any():
            return None, {
                "date": target_day.date(),
                "status": "failed_leakage_detected",
            }

        if len(train_base) < 500:
            return None, {
                "date": target_day.date(),
                "status": f"skipped_too_few_train_rows_{len(train_base)}",
            }

        mix_model = ProductionEstimator(alpha=4.0)
        mix_model.fit(train_base, gen_by_type_before)

        train = add_estimated_supply_features(
            train_base,
            mix_model.predict(train_base),
        )

        forecast = add_estimated_supply_features(
            forecast_base,
            mix_model.predict(forecast_base),
        )

        to_drop = [
            c
            for c in train.columns
            if c != "dam_price_eur_mwh"
            and (
                train[c].notna().mean() < 0.5
                or forecast[c].notna().mean() < 0.5
            )
        ]

        if to_drop:
            train = train.drop(columns=to_drop)
            forecast = forecast.drop(columns=to_drop)

        ridge = RidgeMLForecaster(alpha=1.0)
        ridge.fit(train)
        ridge_pred = ridge.predict(forecast)

        gbm_pred = np.full(len(forecast), np.nan)

        if use_gbm:
            try:
                gbm = GBMForecaster(
                    n_estimators=300,
                    learning_rate=0.05,
                    num_leaves=31,
                    min_child_samples=20,
                )

                gbm.fit(train)
                gbm_pred = gbm.predict(forecast)

            except Exception:
                gbm_pred = np.full(len(forecast), np.nan)

        result = pd.DataFrame(
            {
                "actual_dam_price_eur_mwh": actual.values,
                "ridge_price_eur_mwh": ridge_pred,
                "gbm_price_eur_mwh": gbm_pred,
                "operational_price_eur_mwh": ridge_pred,
                "gas_estimated_mw": series_or_nan(forecast, "gas_estimated_mw"),
                "solar_estimated_mw": series_or_nan(forecast, "solar_estimated_mw"),
                "wind_estimated_mw": series_or_nan(forecast, "wind_estimated_mw"),
                "dam_share_gas_pct": series_or_nan(forecast, "dam_share_gas_pct"),
                "dam_share_solar_pct": series_or_nan(forecast, "dam_share_solar_pct"),
                "dam_share_wind_pct": series_or_nan(forecast, "dam_share_wind_pct"),
                "gas_ttf_eur_per_mwh": series_or_nan(forecast, "gas_ttf_eur_per_mwh"),
                "carbon_eua_eur_per_t": series_or_nan(forecast, "carbon_eua_eur_per_t"),
            },
            index=forecast.index,
        )

        metrics = calculate_metrics(
            actual=result["actual_dam_price_eur_mwh"],
            predicted=result["operational_price_eur_mwh"],
        )

        metrics.update(
            {
                "date": target_day.date(),
                "status": "ok",
                "train_rows": len(train),
                "forecast_rows": len(forecast),
                "mean_actual": result["actual_dam_price_eur_mwh"].mean(),
                "mean_predicted": result["operational_price_eur_mwh"].mean(),
                "min_actual": result["actual_dam_price_eur_mwh"].min(),
                "max_actual": result["actual_dam_price_eur_mwh"].max(),
                "min_predicted": result["operational_price_eur_mwh"].min(),
                "max_predicted": result["operational_price_eur_mwh"].max(),
            }
        )

        return result, metrics

    except Exception as exc:
        return None, {
            "date": target_day.date(),
            "status": f"failed_{type(exc).__name__}: {exc}",
        }


# =============================================================================
# Main
# =============================================================================

def main():
    start_date, end_date = parse_date_range()

    print("=" * 78)
    print(" HelleniFlex - 2026 Walk-Forward DAM Forecast Backtest")
    print("=" * 78)
    print(f" Backtest range: {start_date.date()} -> {end_date.date()}")
    print(" Leakage rule:   target day is removed before training/features")
    print("=" * 78)

    print("\n[1/4] Loading full datasets...")

    full_prices = load_entsoe_prices_directory(ENT)
    full_load = load_entsoe_load_directory(ENT)
    full_gen_total = load_entsoe_total_generation_directory(ENT)
    full_gen_by_type = load_entsoe_generation_per_type_directory(ENT)
    full_wind = load_entsoe_renewable_directory(ENT, label="wind")
    full_solar = load_entsoe_renewable_directory(ENT, label="solar")
    full_flows = load_entsoe_flows_directory(ENT)
    full_flows_pn = load_entsoe_flows_by_neighbor_directory(ENT)
    full_foreign = load_foreign_prices_directory(FOR)

    full_ttf = load_daily_series_csv(
        os.path.join(EXT, "ttf_gas_daily_eur_per_mwh.csv"),
        name="ttf_eur_per_mwh",
    )

    full_eua = load_daily_series_csv(
        os.path.join(EXT, "eua_carbon_daily_eur_per_t.csv"),
        name="eua_eur_per_t",
    )

    weather_cache = os.path.join(EXT, "openmeteo_history_athens.csv")

    if os.path.exists(weather_cache):
        full_weather = pd.read_csv(
            weather_cache,
            index_col=0,
            parse_dates=True,
        )
        full_weather.index = pd.to_datetime(full_weather.index)
    else:
        try:
            weather_start = str(full_prices.index.min().date())
            weather_end = str(full_prices.index.max().date())

            full_weather = fetch_openmeteo_weather(
                start=weather_start,
                end=weather_end,
            )

            full_weather.to_csv(weather_cache)

        except Exception as exc:
            print(f"  warning: weather unavailable, continuing without it ({exc})")
            full_weather = None

    print(f"  price data:     {full_prices.index.min()} -> {full_prices.index.max()}")
    print(f"  load data:      {full_load.index.min()} -> {full_load.index.max()}")
    print(f"  wind data:      {full_wind.index.min()} -> {full_wind.index.max()}")
    print(f"  solar data:     {full_solar.index.min()} -> {full_solar.index.max()}")

    available_start = max(
        start_date,
        full_prices.index.min().normalize() + pd.Timedelta(days=14),
    )

    available_end = min(
        end_date,
        full_prices.index.max().normalize(),
    )

    days = pd.date_range(
        start=available_start,
        end=available_end,
        freq="D",
    )

    print("\n[2/4] Running walk-forward forecasts...")
    print(f"  candidate days: {len(days)}")

    all_metrics = []
    all_predictions = []

    for i, day in enumerate(days, start=1):
        print(f"  [{i:03d}/{len(days):03d}] {day.date()}...", end=" ")

        result, metrics = forecast_one_day(
            target_day=day,
            full_prices=full_prices,
            full_load=full_load,
            full_gen_total=full_gen_total,
            full_gen_by_type=full_gen_by_type,
            full_wind=full_wind,
            full_solar=full_solar,
            full_flows=full_flows,
            full_flows_pn=full_flows_pn,
            full_foreign=full_foreign,
            full_ttf=full_ttf,
            full_eua=full_eua,
            full_weather=full_weather,
            use_gbm=False,
        )

        all_metrics.append(metrics)

        if result is not None:
            result = result.copy()
            result.insert(0, "date", day.date())
            all_predictions.append(result)

            print(
                f"ok | MAE={metrics['mae']:.2f} "
                f"RMSE={metrics['rmse']:.2f} "
                f"Corr={metrics['correlation']:.3f}"
            )
        else:
            print(metrics["status"])

    print("\n[3/4] Saving outputs...")

    metrics_df = pd.DataFrame(all_metrics)

    daily_metrics_path = os.path.join(
        OUT,
        f"walkforward_daily_metrics_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv",
    )

    metrics_df.to_csv(daily_metrics_path, index=False)

    if all_predictions:
        predictions_df = pd.concat(all_predictions).sort_index()

        predictions_path = os.path.join(
            OUT,
            f"walkforward_predictions_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv",
        )

        predictions_df.to_csv(predictions_path)
    else:
        predictions_path = None

    ok = metrics_df[metrics_df["status"] == "ok"].copy()

    if len(ok) == 0:
        print("\nNo successful backtest days.")
        print(f"Daily metrics saved to: {os.path.relpath(daily_metrics_path, ROOT)}")
        return

    summary = {
        "tested_days": len(metrics_df),
        "successful_days": len(ok),
        "skipped_or_failed_days": len(metrics_df) - len(ok),

        "average_mae_eur_mwh": ok["mae"].mean(),
        "median_mae_eur_mwh": ok["mae"].median(),

        "average_rmse_eur_mwh": ok["rmse"].mean(),
        "median_rmse_eur_mwh": ok["rmse"].median(),

        "average_bias_eur_mwh": ok["bias"].mean(),

        "average_daily_correlation": ok["correlation"].mean(),
        "median_daily_correlation": ok["correlation"].median(),

        "average_directional_accuracy": ok["directional_accuracy"].mean(),
        "average_normalised_mae": ok["normalised_mae"].mean(),
    }

    # Global metrics across all 15-minute intervals from all successful days.
    if all_predictions:
        global_predictions = pd.concat(all_predictions).sort_index()

        global_metrics = calculate_metrics(
            actual=global_predictions["actual_dam_price_eur_mwh"],
            predicted=global_predictions["operational_price_eur_mwh"],
        )

        summary.update(
            {
                "global_interval_count": global_metrics["n"],
                "global_mae_eur_mwh": global_metrics["mae"],
                "global_rmse_eur_mwh": global_metrics["rmse"],
                "global_bias_eur_mwh": global_metrics["bias"],
                "global_correlation": global_metrics["correlation"],
                "global_directional_accuracy": global_metrics["directional_accuracy"],
                "global_normalised_mae": global_metrics["normalised_mae"],
            }
        )

    summary_df = pd.DataFrame([summary])

    summary_path = os.path.join(
        OUT,
        f"walkforward_summary_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv",
    )

    summary_df.to_csv(summary_path, index=False)

    print("\n[4/4] Summary")
    print("=" * 78)

    print(f"  Successful days:             {summary['successful_days']}")
    print(f"  Skipped / failed days:        {summary['skipped_or_failed_days']}")
    print("")
    print(f"  Average daily MAE:            {summary['average_mae_eur_mwh']:.2f} €/MWh")
    print(f"  Average daily RMSE:           {summary['average_rmse_eur_mwh']:.2f} €/MWh")
    print(f"  Average daily bias:           {summary['average_bias_eur_mwh']:.2f} €/MWh")
    print(f"  Average daily correlation:    {summary['average_daily_correlation']:.3f}")
    print(f"  Average directional accuracy: {summary['average_directional_accuracy'] * 100:.2f}%")
    print(f"  Average normalised MAE:       {summary['average_normalised_mae'] * 100:.2f}%")

    if "global_mae_eur_mwh" in summary:
        print("")
        print("  Global interval-level metrics:")
        print(f"  Global MAE:                   {summary['global_mae_eur_mwh']:.2f} €/MWh")
        print(f"  Global RMSE:                  {summary['global_rmse_eur_mwh']:.2f} €/MWh")
        print(f"  Global bias:                  {summary['global_bias_eur_mwh']:.2f} €/MWh")
        print(f"  Global correlation:           {summary['global_correlation']:.3f}")
        print(f"  Global directional accuracy:  {summary['global_directional_accuracy'] * 100:.2f}%")
        print(f"  Global normalised MAE:        {summary['global_normalised_mae'] * 100:.2f}%")

    print("=" * 78)
    print(f"  Daily metrics saved:          {os.path.relpath(daily_metrics_path, ROOT)}")
    print(f"  Summary saved:                {os.path.relpath(summary_path, ROOT)}")

    if predictions_path:
        print(f"  Predictions saved:            {os.path.relpath(predictions_path, ROOT)}")


if __name__ == "__main__":
    main()