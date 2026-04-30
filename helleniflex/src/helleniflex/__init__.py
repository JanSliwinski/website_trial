"""HelleniFlex — universal battery optimization for the Greek electricity market.

Quick start
-----------
>>> from helleniflex import (
...     BatteryAsset, BatteryOptimizer, Backtester,
...     PerfectForesightForecaster, NaiveForecaster, SmartForecaster,
...     make_synthetic_greek_dam_prices,
... )
>>> prices = make_synthetic_greek_dam_prices()
>>> battery = BatteryAsset(power_mw=1.0, capacity_mwh=2.0)
>>> bt = Backtester(battery, forecaster=PerfectForesightForecaster())
>>> result = bt.run(prices, start="2025-01-01", end="2025-01-31")
>>> print(result.summary())
"""

from .battery import BatteryAsset, PRESETS
from .optimizer import BatteryOptimizer, DispatchResult
from .forecaster import (
    PerfectForesightForecaster,
    NaiveForecaster,
    SmartForecaster,
)
from .features import FeatureBuilder
from .production import (
    ProductionEstimator,
    build_generation_targets,
    add_estimated_supply_features,
)
from .ml_forecasters import (
    RidgeMLForecaster,
    GBMForecaster,
    QuantileGBMForecaster,
    forecast_metrics,
)
from .backtester import Backtester, BacktestResult
from .data_loader import (
    make_synthetic_greek_dam_prices,
    load_csv_prices,
    load_daily_series_csv,
    fetch_daily_series_csv_url,
    load_henex_dam_file,
    load_henex_dam_directory,
    fetch_henex_dam,
    load_entsoe_prices_csv,
    load_entsoe_prices_directory,
    load_entsoe_load_csv,
    load_entsoe_load_directory,
    load_entsoe_flows_csv,
    load_entsoe_flows_directory,
    load_entsoe_flows_by_neighbor_csv,
    load_entsoe_flows_by_neighbor_directory,
    load_foreign_prices_directory,
    load_entsoe_renewable_forecast_csv,
    load_entsoe_renewable_directory,
    load_entsoe_total_generation_forecast_csv,
    load_entsoe_total_generation_directory,
    load_entsoe_generation_per_type_csv,
    load_entsoe_generation_per_type_directory,
    fetch_entsoe_dam,
    fetch_admie_filetypes,
    fetch_admie_market_file_index,
    download_admie_file,
    load_admie_excel_url,
    load_admie_96_forecast_url,
    fetch_openmeteo_weather,
)
# live_feeds: confirmed-working IPTO parser (ISP1Requirements pivot format),
# Parquet cache, yfinance TTF, and the canonical fetch_openmeteo_forecast
# (single target_date API, auto-selects archive vs forecast endpoint).
# This import intentionally overrides data_loader's same-named function.
from .live_feeds import (
    LiveDataCollector,
    fetch_openmeteo_forecast,
    fetch_ipto_forecasts,
    fetch_ttf_price,
)

__version__ = "0.1.0"

__all__ = [
    "BatteryAsset",
    "PRESETS",
    "BatteryOptimizer",
    "DispatchResult",
    "PerfectForesightForecaster",
    "NaiveForecaster",
    "SmartForecaster",
    "FeatureBuilder",
    "ProductionEstimator",
    "build_generation_targets",
    "add_estimated_supply_features",
    "RidgeMLForecaster",
    "GBMForecaster",
    "QuantileGBMForecaster",
    "forecast_metrics",
    "Backtester",
    "BacktestResult",
    "make_synthetic_greek_dam_prices",
    "load_csv_prices",
    "load_daily_series_csv",
    "fetch_daily_series_csv_url",
    "load_henex_dam_file",
    "load_henex_dam_directory",
    "fetch_henex_dam",
    "load_entsoe_prices_csv",
    "load_entsoe_prices_directory",
    "load_entsoe_load_csv",
    "load_entsoe_load_directory",
    "load_entsoe_flows_csv",
    "load_entsoe_flows_directory",
    "load_entsoe_flows_by_neighbor_csv",
    "load_entsoe_flows_by_neighbor_directory",
    "load_foreign_prices_directory",
    "load_entsoe_renewable_forecast_csv",
    "load_entsoe_renewable_directory",
    "load_entsoe_total_generation_forecast_csv",
    "load_entsoe_total_generation_directory",
    "load_entsoe_generation_per_type_csv",
    "load_entsoe_generation_per_type_directory",
    "fetch_entsoe_dam",
    "fetch_admie_filetypes",
    "fetch_admie_market_file_index",
    "download_admie_file",
    "load_admie_excel_url",
    "load_admie_96_forecast_url",
    "fetch_openmeteo_weather",
    # live_feeds (canonical versions)
    "LiveDataCollector",
    "fetch_openmeteo_forecast",
    "fetch_ipto_forecasts",
    "fetch_ttf_price",
]
