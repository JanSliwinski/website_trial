# HelleniFlex

HelleniFlex is a Greek Day-Ahead Market (DAM) forecasting and battery bidding
prototype. It predicts 96 quarter-hour DAM prices for a target delivery day,
estimates the expected gas / solar / wind supply mix, and turns the forecast
into an optimized battery schedule.

The project is built for a data-scarce operating environment: Greek standalone
batteries are new, so the optimizer does not require historical battery
telemetry. It uses public market data, weather forecasts, fuel/carbon drivers,
and a physics-constrained battery model.

## Current Pipeline

```text
Historical market data
  Greek DAM prices, load, wind, solar, generation, flows, neighbor prices
        |
        v
Target-day public inputs
  ADMIE/IPTO load and RES forecasts
  Open-Meteo weather forecast
  TTF gas and EUA carbon prices
        |
        v
Feature engineering
  residual demand = load forecast - wind forecast - solar forecast
  lagged DAM prices, rolling prices, calendar, weather, fuel, flows
        |
        v
Supply-mix estimation
  estimated gas MW, solar MW, wind MW, DAM technology shares
        |
        v
DAM price forecast
  operational model: Ridge regression
  comparison model: LightGBM when installed
        |
        v
Battery optimization
  50 MW / 100 MWh default asset
  BUY / SELL / HOLD schedule, SoC, revenue, annualized revenue
        |
        v
CSV outputs and graphs
```

## What The Code Produces

For one target day, the main script produces:

```text
data/tomorrow_dam_forecast_YYYYMMDD.csv
data/tomorrow_bidding_schedule_YYYYMMDD.csv
docs/tomorrow_forecast_bidding_YYYYMMDD.png
```

For a date range, the period script produces:

```text
data/period_dam_forecast_START_END.csv
data/period_bidding_schedule_START_END.csv
data/period_forecast_summary_START_END.csv
docs/period_forecast_summary_START_END.png
```

The daily DAM forecast file contains:

| Column | Meaning |
|---|---|
| `ridge_price_eur_mwh` | Ridge model price forecast. This is the operational forecast. |
| `gbm_price_eur_mwh` | LightGBM forecast for comparison, if LightGBM is installed. |
| `operational_price_eur_mwh` | Price used by the battery optimizer. Currently equal to Ridge. |
| `gas_estimated_mw` | Estimated gas generation for the slot. |
| `solar_estimated_mw` | Estimated solar generation for the slot. |
| `wind_estimated_mw` | Estimated wind generation for the slot. |
| `dam_share_gas_pct` | Estimated gas share of total generation. |
| `dam_share_solar_pct` | Estimated solar share of total generation. |
| `dam_share_wind_pct` | Estimated wind share of total generation. |
| `gas_ttf_eur_per_mwh` | TTF gas price driver. |
| `carbon_eua_eur_per_t` | EUA carbon price driver. |

The bidding schedule contains:

| Column | Meaning |
|---|---|
| `price_eur_mwh` | Forecast price used by the optimizer. |
| `bid_side` | `BUY`, `SELL`, or `HOLD`. |
| `charge_mw` | Battery charge power. |
| `discharge_mw` | Battery discharge power. |
| `net_mw` | Positive for sell/discharge, negative for buy/charge. |
| `energy_mwh` | Energy moved in the 15-minute slot. |
| `soc_mwh` | Battery state of charge. |
| `slot_revenue_eur` | Forecast revenue contribution of the slot. |

## How To Run

From the repository root:

```powershell
cd C:\Users\20221005\source\repos\AthensBabyyy\helleniflex
```

Run a forecast for one delivery day:

```powershell
python examples\tomorrow_forecast.py 2026-04-30
```

Run a forecast over a period:

```powershell
python "examples\period_forecast copy.py" 2026-04-30 2026-05-03
```

Force the period script to regenerate every daily forecast instead of reusing
existing daily outputs:

```powershell
python "examples\period_forecast copy.py" 2026-04-30 2026-05-03 --refresh
```

Change the battery used for bidding:

```powershell
$env:HELLENIFLEX_BID_POWER_MW="50"
$env:HELLENIFLEX_BID_CAPACITY_MWH="100"
python examples\tomorrow_forecast.py 2026-04-30
```

## Main Scripts

| Script | Purpose |
|---|---|
| `examples/tomorrow_forecast.py` | Full target-day DAM forecast, supply-mix estimation, battery bidding, and graph generation. |
| `examples/period_forecast copy.py` | Runs the daily workflow across an inclusive date period and combines the outputs. |
| `examples/revenue_backtest_v2.py` | Historical backtest of forecast-driven battery revenue. |
| `examples/backtest_2026_walkforward.py` | Walk-forward 2026 testing script. |
| `examples/quickstart.py` | Simple project demo. |

## Data Sources

| Source | Used For |
|---|---|
| ENTSO-E exports | Historical Greek DAM prices, load, wind, solar, total generation, generation by type, and flows. |
| ADMIE / IPTO | Target-day load and RES forecasts through ISP1Requirements or ADMIE file discovery. |
| Open-Meteo | Historical weather and target-day weather forecasts. |
| TTF gas CSV or vendor URL | Gas price driver for marginal-cost pressure. |
| EUA carbon CSV | Carbon price driver for thermal generation costs. |
| Neighbor DAM prices | Lagged foreign-market price level and regional coupling signal. |

## Forecasting Theory

DAM prices are driven by expected supply and demand before the auction. The
important relationship is:

```text
high demand + low renewables + expensive gas/carbon = higher prices
low demand + high wind/solar = lower prices
```

The strongest engineered feature is residual demand:

```text
residual_demand_mw = load_forecast_mw - wind_da_forecast_mw - solar_da_forecast_mw
```

When residual demand is high, gas plants are more likely to be marginal. When
solar and wind are high, prices often fall, especially around midday.

## Data Scarcity Strategy

The code avoids pretending that future actual values are known. For the target
day it uses forecast-time data:

- ADMIE/IPTO load and RES forecasts when available.
- Open-Meteo target-day weather forecast.
- TTF gas and EUA carbon drivers.
- Lagged prices and rolling historical statistics.
- Previous-day or previous-week profiles only as fallback assumptions.

If official target-day ADMIE data is missing, the script projects the missing
inputs:

- Load is based on last-week/yesterday profiles and adjusted by temperature.
- Solar is shaped by shortwave radiation.
- Wind is adjusted using the wind-speed-cubed relationship.
- Flows use recent same-slot profiles.

These fallback values are model assumptions, not official data.

## Models

The operational DAM model is Ridge regression. Ridge is intentionally simple,
regularized, and stable under limited data. This matters because electricity
market features are highly correlated and historical samples are limited.

LightGBM is also trained when installed, but it is kept as a comparison model.
The operational forecast column currently uses Ridge:

```text
operational_price_eur_mwh = ridge_price_eur_mwh
```

The supply-mix estimator is another Ridge-based model. It learns historical
relationships between forecast-time features and actual gas / solar / wind
production, then estimates tomorrow's production mix.

## Battery Optimization

The default forecast bidding asset is:

```text
50 MW / 100 MWh
```

The optimizer respects:

- charge and discharge power limits
- energy capacity
- minimum and maximum state of charge
- charge and discharge efficiency
- cyclic end-of-day state of charge
- daily cycle limit

It charges during low-price hours and discharges during high-price hours,
maximizing expected arbitrage revenue under the physical battery constraints.

## Notes For The Team

- Generated forecast CSVs, bidding CSVs, graphs, and Python `__pycache__` files
  should not be committed unless they are intentionally part of an analysis.
- The daily forecast script writes outputs every time it runs.
- The period script reuses existing daily outputs unless `--refresh` is passed.
- The model output is a forecast, not a guarantee. Revenue estimates depend on
  forecast accuracy and market settlement.

## License

MIT.
