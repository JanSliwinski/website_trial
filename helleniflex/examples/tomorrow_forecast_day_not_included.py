"""
Forecast tomorrow's Greek DAM prices with external drivers and supply mix.

Workflow
--------
1. Load historical Greek and neighboring market data.
2. Remove target-day rows from local historical data to avoid leakage.
3. Discover ADMIE tomorrow-facing file metadata for load / RES forecasts.
4. Fetch tomorrow weather forecast from Open-Meteo.
5. Load latest TTF gas and EUA carbon daily series.
6. Estimate tomorrow's gas / solar / wind production and their DAM shares.
7. Forecast the 96 quarter-hour DAM prices for the target day.

Important test-mode behaviour
-----------------------------
When testing on a historical date, your local data folder may already contain
data for the day being predicted. That would leak future information into the
forecast.

This script therefore removes rows from the target day from local historical
datasets before feature building. It only allows target-day information from:
- ADMIE forecast files, if available,
- Open-Meteo forecast,
- gas/carbon daily series,
- fallback projections based on past profiles.

If your local `data/entsoe` directory already contains target-day forecast
files, the script does NOT blindly use them. It prefers ADMIE/API forecast data
or fallback profiles to avoid accidental leakage.
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
    fetch_admie_filetypes,
    fetch_admie_market_file_index,
    fetch_daily_series_csv_url,
    fetch_openmeteo_forecast,
    fetch_openmeteo_weather,
    load_admie_96_forecast_url,
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


# =============================================================================
# Date helpers
# =============================================================================

def target_day_from_argv() -> pd.Timestamp:
    if len(sys.argv) > 1:
        return pd.Timestamp(sys.argv[1]).normalize()

    return (
        pd.Timestamp.today(tz="Europe/Athens")
        .tz_localize(None)
        .normalize()
        + pd.Timedelta(days=1)
    )


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
# Leakage protection
# =============================================================================

def remove_target_day_rows(df, target_day: pd.Timestamp):
    """
    Remove rows from the day being forecast to avoid data leakage.

    Works for:
    - pandas DataFrame
    - pandas Series
    - dictionaries containing DataFrames/Series
    """
    if df is None:
        return df

    if isinstance(df, dict):
        return {
            key: remove_target_day_rows(value, target_day)
            for key, value in df.items()
        }

    if not isinstance(df, (pd.DataFrame, pd.Series)):
        return df

    if len(df) == 0:
        return df

    if not isinstance(df.index, pd.DatetimeIndex):
        return df

    return df[df.index.normalize() != target_day].copy()


# =============================================================================
# Data loading helpers
# =============================================================================

def load_weather_history(start: str, end: str):
    cache = os.path.join(EXT, "openmeteo_history_athens.csv")

    if os.path.exists(cache):
        weather = pd.read_csv(cache, index_col=0, parse_dates=True)
        weather.index = pd.to_datetime(weather.index)
        return weather

    # The Open-Meteo archive can lag real time, so if today's archive is not
    # ready yet, walk back a few days before giving up.
    end_ts = pd.Timestamp(end).normalize()
    yesterday = (
        pd.Timestamp.today(tz="Europe/Athens")
        .tz_localize(None)
        .normalize()
        - pd.Timedelta(days=1)
    )
    end_ts = min(end_ts, yesterday)

    last_exc = None

    for days_back in range(0, 4):
        try_end = end_ts - pd.Timedelta(days=days_back)

        if try_end < pd.Timestamp(start):
            break

        try:
            return fetch_openmeteo_weather(
                start=start,
                end=str(try_end.date()),
            )
        except Exception as exc:
            last_exc = exc

    print(f"  warning: weather history unavailable ({last_exc})")
    return None


def series_or_nan(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col]

    return pd.Series(np.nan, index=df.index, name=col)


def load_ttf_series() -> pd.Series:
    """
    Use a live vendor CSV URL if configured, otherwise fall back to local CSV.

    Environment variables supported:
    - HELLENIFLEX_TTF_CSV_URL
    - HELLENIFLEX_TTF_AUTH_HEADER
    - HELLENIFLEX_TTF_AUTH_VALUE
    - HELLENIFLEX_TTF_DATE_COL
    - HELLENIFLEX_TTF_VALUE_COL
    """
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


# =============================================================================
# ADMIE helpers
# =============================================================================

def discover_admie_forecast_filetypes(
    kind: str,
    filetypes: Optional[pd.DataFrame] = None,
) -> list[str]:
    """
    Use ADMIE's filetype API to find forecast categories.

    This follows the ADMIE documentation:
      1. call getFiletypeInfoEN
      2. use the returned `filetype` values as FILETYPE
      3. query getOperationMarketFile / getOperationMarketFilewRange
    """
    if filetypes is None:
        filetypes = fetch_admie_filetypes(language="EN")

    if filetypes.empty or "filetype" not in filetypes.columns:
        return []

    ftype = filetypes["filetype"].astype(str)
    process = filetypes.get("process", pd.Series("", index=filetypes.index)).astype(str)
    data_type = filetypes.get("data_type", pd.Series("", index=filetypes.index)).astype(str)
    period = filetypes.get("period_covered", pd.Series("", index=filetypes.index)).astype(str)

    if kind == "load":
        mask = ftype.str.contains("LoadForecast", case=False, na=False)
    elif kind == "res":
        mask = ftype.str.contains("RESForecast", case=False, na=False)
    else:
        raise ValueError("kind must be 'load' or 'res'")

    mask &= data_type.str.contains("Forecast", case=False, na=False)
    mask &= process.str.contains("ISP|DAM", case=False, regex=True, na=False)
    mask &= period.str.fullmatch("DAY", case=False, na=False)

    candidates = filetypes.loc[mask, "filetype"].astype(str).tolist()

    def priority(name: str) -> tuple[int, str]:
        lowered = name.lower()

        if lowered.startswith("isp1"):
            return (0, name)

        if lowered.startswith("isp2"):
            return (1, name)

        if lowered.startswith("dayahead"):
            return (2, name)

        if lowered.startswith("isp3"):
            return (3, name)

        if lowered.startswith("weekahead"):
            return (4, name)

        return (9, name)

    return sorted(candidates, key=priority)


def fetch_admie_file_rows(
    target_day: pd.Timestamp,
    categories: list[str],
    overlap: bool,
) -> pd.DataFrame:
    """Query ADMIE file lookup endpoint for each candidate category."""
    target_str = str(target_day.date())
    pieces = []

    for category in categories:
        try:
            meta = fetch_admie_market_file_index(
                file_category=category,
                date_start=target_str,
                date_end=target_str,
                overlap=overlap,
            )
        except Exception as exc:
            print(f"  ADMIE {category}: unavailable ({exc})")
            continue

        if meta.empty:
            continue

        meta = meta.copy()
        meta["file_category"] = category
        meta["lookup_mode"] = "range-overlap" if overlap else "exact-coverage"
        pieces.append(meta)

    if not pieces:
        return pd.DataFrame()

    return pd.concat(pieces, ignore_index=True)


def show_admie_metadata(target_day: pd.Timestamp) -> tuple[list[str], list[str]]:
    filetypes = fetch_admie_filetypes(language="EN")

    load_categories = discover_admie_forecast_filetypes("load", filetypes)
    res_categories = discover_admie_forecast_filetypes("res", filetypes)

    print(f"  ADMIE load filetypes: {load_categories}")
    print(f"  ADMIE RES filetypes:  {res_categories}")

    for label, categories in [("load", load_categories), ("RES", res_categories)]:
        exact = fetch_admie_file_rows(target_day, categories, overlap=False)
        ranged = fetch_admie_file_rows(target_day, categories, overlap=True)

        exact_count = 0 if exact.empty else len(exact)
        range_count = 0 if ranged.empty else len(ranged)

        print(
            f"  ADMIE {label} files: exact={exact_count} range-overlap={range_count}"
        )

    return load_categories, res_categories


def latest_admie_file(
    target_day: pd.Timestamp,
    categories: list[str],
) -> Optional[dict]:
    """Return the latest ADMIE file, using exact coverage then range lookup."""
    meta = fetch_admie_file_rows(target_day, categories, overlap=False)

    if meta.empty:
        meta = fetch_admie_file_rows(target_day, categories, overlap=True)

    if meta.empty or "file_path" not in meta.columns:
        return None

    meta = meta.copy()

    if "file_published" in meta.columns:
        meta["_published"] = pd.to_datetime(
            meta["file_published"],
            format="%d.%m.%Y %H:%M",
            errors="coerce",
        )
    else:
        meta["_published"] = pd.NaT

    meta["_category_priority"] = meta["file_category"].map(
        {category: i for i, category in enumerate(categories)}
    ).fillna(999)

    best_priority = meta["_category_priority"].min()
    best = meta[meta["_category_priority"] == best_priority]
    best = best.sort_values("_published")

    return best.iloc[-1].to_dict()


def fetch_admie_target_forecasts(
    target_day: pd.Timestamp,
    load_categories: list[str],
    res_categories: list[str],
):
    """Download target-day ADMIE load and RES forecasts if available."""
    out = {
        "load": None,
        "res": None,
        "load_meta": None,
        "res_meta": None,
    }

    load_meta = latest_admie_file(target_day, load_categories)

    if load_meta is not None:
        out["load_meta"] = load_meta
        out["load"] = load_admie_96_forecast_url(
            load_meta["file_path"],
            name="admie_load_forecast_mw",
        )

    res_meta = latest_admie_file(target_day, res_categories)

    if res_meta is not None:
        out["res_meta"] = res_meta
        out["res"] = load_admie_96_forecast_url(
            res_meta["file_path"],
            name="admie_res_forecast_mw",
        )

    return out


# =============================================================================
# Forecast extension helpers
# =============================================================================

def has_target_rows(
    df: pd.DataFrame,
    target_day: pd.Timestamp,
    col: str,
    periods: int,
) -> bool:
    mask = df.index.normalize() == target_day
    return int(df.loc[mask, col].notna().sum()) >= periods


def lagged_profile(
    series: pd.Series,
    target_idx: pd.DatetimeIndex,
) -> pd.Series:
    """
    Prefer last week's same slot, then yesterday's same slot.

    This is a realistic fallback because those profiles would be known before
    the target day.
    """
    last_week = pd.Series(
        series.reindex(target_idx - pd.Timedelta(days=7)).values,
        index=target_idx,
    )

    yesterday = pd.Series(
        series.reindex(target_idx - pd.Timedelta(days=1)).values,
        index=target_idx,
    )

    return last_week.combine_first(yesterday).ffill().bfill()


def weather_series(
    weather: pd.DataFrame,
    col: str,
    idx: pd.DatetimeIndex,
) -> pd.Series:
    if weather is None or col not in weather.columns:
        return pd.Series(np.nan, index=idx)

    return pd.Series(
        weather[col].reindex(idx, method="ffill").values,
        index=idx,
    )


def weather_lagged_as_target(
    weather: pd.DataFrame,
    col: str,
    target_idx: pd.DatetimeIndex,
    days_back: int = 7,
) -> pd.Series:
    source_idx = target_idx - pd.Timedelta(days=days_back)

    return pd.Series(
        weather_series(weather, col, source_idx).values,
        index=target_idx,
    )


def extend_load_forecast(
    load_df: pd.DataFrame,
    target_day: pd.Timestamp,
    weather_all: pd.DataFrame,
    admie_load: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Extend load forecast to the target day.

    Leakage protection:
    - We do not use existing target-day rows from local historical data.
    - We only use ADMIE forecast if available.
    - Otherwise, we create a fallback from previous profiles and weather.
    """
    load_df = remove_target_day_rows(load_df, target_day)

    idx = target_15min_index(target_day)

    if (
        admie_load is not None
        and len(admie_load.dropna()) == 96
        and (admie_load.index.normalize() == target_day).all()
    ):
        projected = pd.DataFrame(
            {
                "load_actual_mw": np.nan,
                "load_forecast_mw": admie_load.reindex(idx).values,
            },
            index=idx,
        )

        out = pd.concat([load_df, projected]).sort_index()
        return out[~out.index.duplicated(keep="last")]

    # TEST MODE:
    # Do not return existing target-day rows from local data, because they may
    # contain information that would not be available before DAM clearing.
    #
    # if has_target_rows(load_df, target_day, "load_forecast_mw", 96):
    #     return load_df

    base = lagged_profile(load_df["load_forecast_mw"], idx)

    future_temp = weather_series(weather_all, "temperature_2m", idx)
    source_temp = weather_lagged_as_target(weather_all, "temperature_2m", idx)

    discomfort_delta = (future_temp - 20.0).abs() - (source_temp - 20.0).abs()

    adjusted = (base + discomfort_delta.fillna(0.0) * 45.0).clip(lower=0.0)

    projected = pd.DataFrame(
        {
            "load_actual_mw": np.nan,
            "load_forecast_mw": adjusted.values,
        },
        index=idx,
    )

    out = pd.concat([load_df, projected]).sort_index()
    return out[~out.index.duplicated(keep="last")]


def extend_res_forecast(
    res_df: pd.DataFrame,
    target_day: pd.Timestamp,
    label: str,
    weather_all: pd.DataFrame,
) -> pd.DataFrame:
    """
    Extend RES forecast to the target day.

    Leakage protection:
    - We remove existing target-day rows.
    - We then project target-day wind/solar using previous profiles and weather.
    """
    res_df = remove_target_day_rows(res_df, target_day)

    forecast_col = [c for c in res_df.columns if "da_forecast" in c][0]
    actual_col = [c for c in res_df.columns if "actual" in c][0]

    # TEST MODE:
    # Do not use existing target-day RES rows from local data.
    #
    # if has_target_rows(res_df, target_day, forecast_col, 24):
    #     return res_df

    idx = target_hourly_index(target_day)
    base = lagged_profile(res_df[forecast_col], idx)

    if label == "solar":
        rad = weather_series(weather_all, "shortwave_radiation", idx).clip(lower=0.0)

        if rad.notna().any() and rad.max() > 0:
            daily_peak = float(base.max()) if base.notna().any() else 0.0
            projected_values = daily_peak * (rad / rad.max())
        else:
            projected_values = base

    elif label == "wind":
        future_speed = weather_series(weather_all, "wind_speed_10m", idx)
        source_speed = weather_lagged_as_target(weather_all, "wind_speed_10m", idx)

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

    out = pd.concat([res_df, projected]).sort_index()
    return out[~out.index.duplicated(keep="last")]


def extend_hourly_profile(
    df: pd.DataFrame,
    target_day: pd.Timestamp,
    value_col: str,
    projected_values: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Extend an hourly dataframe to the target day using projected values or
    lagged profile.

    Leakage protection:
    - Existing target-day rows are removed before projection.
    """
    df = remove_target_day_rows(df, target_day)

    idx = target_hourly_index(target_day)

    values = (
        projected_values.reindex(idx)
        if projected_values is not None
        else lagged_profile(df[value_col], idx)
    )

    projected = pd.DataFrame(index=idx)

    for col in df.columns:
        projected[col] = np.nan

    projected[value_col] = values.values

    out = pd.concat([df, projected]).sort_index()
    return out[~out.index.duplicated(keep="last")]


def extend_flow_profile(
    df: pd.DataFrame,
    target_day: pd.Timestamp,
) -> pd.DataFrame:
    """
    Extend flow data to the target day using previous profiles.

    Leakage protection:
    - Existing target-day flow rows are ignored.
    """
    df = remove_target_day_rows(df, target_day)

    idx = target_hourly_index(target_day)

    # TEST MODE:
    # Do not use existing target-day flow rows from local data.
    #
    # if len(df.loc[df.index.normalize() == target_day]) >= 24:
    #     return df

    projected = pd.DataFrame(index=idx)

    for col in df.columns:
        projected[col] = lagged_profile(df[col], idx).values

    out = pd.concat([df, projected]).sort_index()
    return out[~out.index.duplicated(keep="last")]


def align_res_to_admie_total(
    wind_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    target_day: pd.Timestamp,
    admie_res: pd.Series | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Scale wind and solar forecasts so their sum matches ADMIE total RES.

    This is allowed because ADMIE RES is a target-day forecast, not actual data.
    """
    if (
        admie_res is None
        or len(admie_res.dropna()) != 96
        or not (admie_res.index.normalize() == target_day).all()
    ):
        return wind_df, solar_df

    idx15 = target_15min_index(target_day)
    idxh = target_hourly_index(target_day)

    admie_hourly = admie_res.reindex(idx15).resample("h").mean().reindex(idxh)

    wind_col = [c for c in wind_df.columns if "da_forecast" in c][0]
    solar_col = [c for c in solar_df.columns if "da_forecast" in c][0]

    wind_vals = wind_df[wind_col].reindex(idxh)
    solar_vals = solar_df[solar_col].reindex(idxh)

    total = wind_vals.fillna(0.0) + solar_vals.fillna(0.0)

    wind_share = (wind_vals / total.replace(0.0, np.nan)).fillna(0.5)
    solar_share = 1.0 - wind_share

    wind_df = wind_df.copy()
    solar_df = solar_df.copy()

    wind_df.loc[idxh, wind_col] = (admie_hourly * wind_share).clip(lower=0.0).values
    solar_df.loc[idxh, solar_col] = (admie_hourly * solar_share).clip(lower=0.0).values

    return wind_df, solar_df


def extend_prices_with_target(
    prices: pd.Series,
    target_day: pd.Timestamp,
) -> pd.Series:
    """
    Add empty target-day rows for DAM price.

    The model will predict these. Actual target-day DAM prices are deliberately
    not used.
    """
    prices = remove_target_day_rows(prices, target_day)

    future_idx = target_15min_index(target_day)

    horizon = pd.Series(
        np.nan,
        index=future_idx,
        name=prices.name,
    )

    return pd.concat([prices, horizon]).sort_index()


# =============================================================================
# Main pipeline
# =============================================================================

target_day = target_day_from_argv()
target_end = target_day + pd.Timedelta(days=1) - pd.Timedelta(minutes=15)

print("=" * 78)
print(f" HelleniFlex - Tomorrow DAM Forecast for {target_day.date()}")
print("=" * 78)

print("\n[1/5] Loading historical inputs...")

prices = load_entsoe_prices_directory(ENT)
load = load_entsoe_load_directory(ENT)
gen_total = load_entsoe_total_generation_directory(ENT)
gen_by_type = load_entsoe_generation_per_type_directory(ENT)
wind = load_entsoe_renewable_directory(ENT, label="wind")
solar = load_entsoe_renewable_directory(ENT, label="solar")
flows = load_entsoe_flows_directory(ENT)
flows_pn = load_entsoe_flows_by_neighbor_directory(ENT)
foreign = load_foreign_prices_directory(FOR)

# -------------------------------------------------------------------------
# TEST MODE: remove target-day rows from local historical data.
# This prevents the model from accidentally using the day it is supposed to
# predict, especially during backtests.
# -------------------------------------------------------------------------
prices = remove_target_day_rows(prices, target_day)
load = remove_target_day_rows(load, target_day)
gen_total = remove_target_day_rows(gen_total, target_day)
gen_by_type = remove_target_day_rows(gen_by_type, target_day)
wind = remove_target_day_rows(wind, target_day)
solar = remove_target_day_rows(solar, target_day)
flows = remove_target_day_rows(flows, target_day)
flows_pn = remove_target_day_rows(flows_pn, target_day)
foreign = remove_target_day_rows(foreign, target_day)

ttf = load_ttf_series()
eua = load_daily_series_csv(
    os.path.join(EXT, "eua_carbon_daily_eur_per_t.csv"),
    name="eua_eur_per_t",
)

# Do not use target-day cached historical weather as actual history.
# Target-day weather will come from forecast below.
weather_hist = load_weather_history(
    start=str(prices.index.min().date()),
    end=str(
        min(
            prices.index.max().normalize(),
            target_day - pd.Timedelta(days=1),
        ).date()
    ),
)

if weather_hist is not None:
    weather_hist = remove_target_day_rows(weather_hist, target_day)

print(
    f"  price history:          {prices.index.min().date()} -> {prices.index.max().date()}"
)
print(
    f"  target requires local forecasts through: {target_day.date()}"
)
print(
    "  leakage protection:    target-day local historical rows removed"
)

print("\n[2/5] Discovering ADMIE tomorrow-facing files...")

admie_load_categories, admie_res_categories = show_admie_metadata(target_day)

admie = fetch_admie_target_forecasts(
    target_day,
    load_categories=admie_load_categories,
    res_categories=admie_res_categories,
)

if admie["load_meta"] is not None:
    print(
        "  ADMIE load selected: "
        f"{admie['load_meta'].get('file_category')} "
        f"{admie['load_meta'].get('file_description')}"
    )
else:
    print("  ADMIE load selected: none; will project from recent profiles")

if admie["res_meta"] is not None:
    print(
        "  ADMIE RES selected:  "
        f"{admie['res_meta'].get('file_category')} "
        f"{admie['res_meta'].get('file_description')}"
    )
else:
    print("  ADMIE RES selected:  none; will project from recent profiles")

print("\n[3/5] Fetching tomorrow weather forecast...")

weather_future = fetch_openmeteo_forecast(
    start_date=str(target_day.date()),
    end_date=str(target_day.date()),
)

if weather_hist is None:
    weather_all = weather_future
else:
    weather_all = pd.concat([weather_hist, weather_future])

weather_all = weather_all.sort_index()
weather_all = weather_all[~weather_all.index.duplicated(keep="last")]

print(
    f"  weather forecast slots: {weather_future.index.min()} -> {weather_future.index.max()}"
)

print("\n[4/5] Building features and estimating tomorrow supply mix...")

load = extend_load_forecast(
    load,
    target_day,
    weather_all,
    admie_load=admie["load"],
)

wind = extend_res_forecast(
    wind,
    target_day,
    "wind",
    weather_all,
)

solar = extend_res_forecast(
    solar,
    target_day,
    "solar",
    weather_all,
)

wind, solar = align_res_to_admie_total(
    wind,
    solar,
    target_day,
    admie["res"],
)

flows = extend_flow_profile(flows, target_day)
flows_pn = extend_flow_profile(flows_pn, target_day)

target_load_hourly = load["load_forecast_mw"].reindex(
    target_hourly_index(target_day),
    method="ffill",
)

gen_total = extend_hourly_profile(
    gen_total,
    target_day,
    "gen_forecast_mw",
    projected_values=target_load_hourly,
)

prices_ext = extend_prices_with_target(prices, target_day)

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

forecast_base = usable.loc[target_day:target_end].copy()

if len(forecast_base) != 96:
    raise ValueError(
        "Target-day feature coverage is incomplete even after projection. "
        "Check that historical load / wind / solar files contain at least "
        "yesterday or last week's same-day profiles."
    )

# Additional safety check: the target-day DAM price must be unknown.
if forecast_base["dam_price_eur_mwh"].notna().any():
    raise ValueError(
        "Leakage detected: forecast_base contains target-day DAM prices. "
        "The target day must have NaN DAM prices before prediction."
    )

mix_model = ProductionEstimator(alpha=4.0)
mix_model.fit(train_base, gen_by_type)

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

mix_cols = [
    c
    for c in forecast.columns
    if c.endswith("_estimated_mw") or c.startswith("dam_share_")
]

print(f"  train rows:             {len(train):,}")
print(f"  forecast rows:          {len(forecast):,}")
print(f"  mix columns:            {mix_cols}")

print("\n[5/5] Training models and forecasting tomorrow...")

ridge = RidgeMLForecaster(alpha=1.0)
ridge.fit(train)

ridge_pred = ridge.predict(forecast)

# Based on your validation, Ridge is currently better than GBM.
operational_pred = ridge_pred
operational_model = "Ridge"

try:
    gbm = GBMForecaster(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=20,
    )

    gbm.fit(train)
    gbm_pred = gbm.predict(forecast)

except ImportError as exc:
    print(f"  warning: LightGBM unavailable; Ridge remains operational ({exc})")
    gbm_pred = np.full(len(forecast), np.nan)

result = pd.DataFrame(
    {
        "ridge_price_eur_mwh": ridge_pred,
        "gbm_price_eur_mwh": gbm_pred,
        "operational_price_eur_mwh": operational_pred,
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

out_path = os.path.join(
    ROOT,
    "data",
    f"tomorrow_dam_forecast_{target_day.strftime('%Y%m%d')}.csv",
)

result.to_csv(out_path)

print(
    f"  Ridge mean forecast:    EUR{result['ridge_price_eur_mwh'].mean():.2f}/MWh"
)

if result["gbm_price_eur_mwh"].notna().any():
    print(
        f"  GBM mean forecast:      EUR{result['gbm_price_eur_mwh'].mean():.2f}/MWh"
    )

print(
    f"  Operational model:      {operational_model}"
)

peak = result["operational_price_eur_mwh"].idxmax()
trough = result["operational_price_eur_mwh"].idxmin()

print(
    f"  Peak slot:              {peak} -> "
    f"EUR{result.loc[peak, 'operational_price_eur_mwh']:.2f}/MWh"
)

print(
    f"  Trough slot:            {trough} -> "
    f"EUR{result.loc[trough, 'operational_price_eur_mwh']:.2f}/MWh"
)

print(f"\nSaved: {os.path.relpath(out_path, ROOT)}")