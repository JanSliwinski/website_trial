# HelleniFlex

> **Universal battery optimization for the Greek electricity market.**
> One framework, any asset, any day, any forecast.

![Optimal dispatch on real Greek DAM with ENTSO-E exogenous data](docs/multi_source_dispatch.png)

> **Real Greek DAM data, 29 April 2026.** A 1 MW / 2 MWh standalone battery would have made **€323** in a single day by charging through the 10am–4pm solar trough (5 negative-price slots, 29 near-zero slots) and discharging into the morning peak (€182/MWh) and evening peak (€224/MWh). The schedule above is the provably-optimal MILP solution, computed in 40 milliseconds.
>
> The four panels stitch together three independent ENTSO-E publications: day-ahead clearing prices, total system load (forecast vs actual), and net cross-border physical flows. Greece was a heavy net exporter from 5am–noon (~1.1 GW outflow at peak) — that's the surplus driving prices to zero. The same prices reconcile to **HEnEx EL-DAM Results** within 0.0000 €/MWh across all 96 slots, so the pipeline is fed by mutually-validating sources.

The Greek DAM moved to a **15-minute Market Time Unit** on 1 October 2025 and the first standalone batteries entered the market in **April 2026**. As renewable penetration rises, intraday price spreads widen and curtailment grows — creating a multi-billion-euro opportunity for storage to absorb cheap renewable energy and deliver it during scarcity hours.

**HelleniFlex** is a complete, production-ready optimization framework that decides when a battery should **charge, discharge, or stay idle** to maximize economic value while respecting every operational constraint. It works with **any asset specification** and runs on Day 1 of operation — no historical battery telemetry required.

---

## What it does

```
            ┌────────────────────────────────────────────────────────────┐
            │                                                            │
DAM prices ─┤              ┌──────────────────┐                          │
RES forecast├─────────────►│  Price forecast  │─────┐                    │
Load fcst   │              │  (Ridge / Naive  │     │                    │
Weather     │              │   / Oracle)      │     ▼                    │
TTF gas    ─┤              └──────────────────┘   ┌──────────────────┐   │
            │                                     │   MILP optimizer │   │
            │                                     │   (HiGHS / cvxpy)│   │
Asset specs ────────────────────────────────────► │                  │   │
            │                                     └────────┬─────────┘   │
            │                                              │             │
            │                                              ▼             │
            │                                     ┌──────────────────┐   │
            │                                     │   24h schedule   │   │
            │                                     │   + SoC + KPIs   │   │
            │                                     └──────────────────┘   │
            └────────────────────────────────────────────────────────────┘
```

Three pluggable modules, one clean abstraction:

| Module | Job | Implementation |
|---|---|---|
| `BatteryAsset` | Capture every spec the optimizer needs (power, capacity, η, SoC limits, cycle cap, degradation cost) | Validated dataclass + preset library |
| `BatteryOptimizer` | Solve the day-ahead dispatch problem | **MILP** in cvxpy → HiGHS solver, ~40 ms per day |
| `Backtester` | Roll the optimizer over history, settle at realised prices | Honest train/test separation by design |

Plus three forecasters — **Perfect Foresight** (oracle / upper bound), **Naive** (last-week baseline), and **Smart** (Ridge regression on lagged prices and calendar features) — that turn the deliverable into a story:

> **Smart forecaster captures 87% of perfect-foresight revenue. Even the naive baseline captures 80%. The optimizer is forecast-tolerant by design.**

---

## Why this design wins under data scarcity

The hackathon brief explicitly frames this as a **data-scarce problem** because Greek standalone batteries only began operating in test mode in April 2026 — there is no rich battery telemetry history to learn from. HelleniFlex solves this the right way:

1. **The optimizer is purely model-based.** Given asset specs and a price forecast, it computes the provably-optimal schedule from physics — zero historical battery data required. Works on Day 1.
2. **The forecaster needs only public market data.** DAM prices, day-ahead RES and load forecasts, weather — all available from HEnEx, IPTO, ENTSO-E and Open-Meteo. No proprietary telemetry.
3. **The asset abstraction is universal.** Swap in a 1 MW / 2 MWh asset, a 50 MW utility-scale block, or any specification in between — the same optimizer handles all of them.

This design also avoids the trap of reinforcement learning, which would need years of operational data Greece does not yet have.

---

## Quick start

```bash
git clone <this-repo>
cd helleniflex
pip install -r requirements.txt

# Synthetic-data demo (no API or downloads needed):
python examples/quickstart.py

# Real-data demo (parses HEnEx EL-DAM Excel from data/henex/):
python examples/real_data_demo.py

# Multi-source ENTSO-E demo (prices + load + cross-border flows, with cross-validation):
python examples/entsoe_demo.py

# ML forecasting experiment (train Ridge + LightGBM on 2025, test on April 2026):
python examples/forecaster_experiment.py

# End-to-end revenue backtest (the headline result):
python examples/revenue_backtest.py
```

Five demos covering five integration paths:

* **Synthetic** — generates 18 months of realistic-looking Greek DAM prices, runs the optimizer, the 30-day forecaster comparison, and an asset duration sweep. No internet required.
* **HEnEx real-data** — parses the official `EL-DAM_Results_EN_v01.xlsx` files HEnEx publishes daily and runs the MILP on them.
* **Multi-source ENTSO-E** — loads three independent ENTSO-E Transparency Platform CSV exports (day-ahead prices, total load forecast vs actual, and net cross-border physical flows), cross-validates the prices against HEnEx, runs the MILP, and assembles a forecaster-ready feature matrix.
* **ML forecasting experiment** — builds a 22-feature matrix from real 2025 ENTSO-E data, trains Ridge and LightGBM, evaluates on held-out April 2026 (MAE €19.5/MWh, negative-price recall up to 74%).
* **Revenue backtest** — the production loop: forecast → optimize → settle → repeat. On 29 days of April 2026, ML pipeline captures **84% of perfect-foresight revenue** vs 76% for the naive baseline.

### Run on real data programmatically

```python
from helleniflex import (
    BatteryAsset, BatteryOptimizer,
    load_henex_dam_file,
    load_entsoe_prices_csv, load_entsoe_load_csv, load_entsoe_flows_csv,
)

# HEnEx (official Greek market publication)
prices = load_henex_dam_file("data/henex/20260429_EL-DAM_Results_EN_v01.xlsx")

# ENTSO-E (alternative source, same prices)
prices = load_entsoe_prices_csv("data/entsoe/GUI_ENERGY_PRICES_*.csv")
load   = load_entsoe_load_csv("data/entsoe/GUI_TOTAL_LOAD_DAYAHEAD_*.csv")
flows  = load_entsoe_flows_csv("data/entsoe/GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_*.csv")

battery = BatteryAsset(power_mw=1.0, capacity_mwh=2.0)
result = BatteryOptimizer(battery).optimize(prices.values, dt_hours=0.25)
print(f"Revenue: €{result.revenue_eur:.2f}, cycles: {result.cycles:.2f}")
```

---

## The MILP formulation

For each timestep `t ∈ {0, ..., T−1}` (typically `T = 96` for a 15-min day):

**Decision variables**
- `p_c[t] ≥ 0` — charging power [MW]
- `p_d[t] ≥ 0` — discharging power [MW]
- `e[t+1] ∈ [E_min, E_max]` — stored energy [MWh]
- `z[t] ∈ {0, 1}` — 1 ⇒ charging, 0 ⇒ discharging

**Objective**

$$\max \quad \sum_t \lambda_t \cdot (p_d[t] - p_c[t]) \cdot \Delta t \;-\; c_\text{cyc} \cdot \sum_t (p_c[t] + p_d[t]) \cdot \Delta t$$

**Constraints**

- SoC dynamics: `e[t+1] = e[t] + η_c · p_c[t] · Δt − p_d[t] · Δt / η_d`
- Power gates: `p_c[t] ≤ P_max · z[t]`, `p_d[t] ≤ P_max · (1 − z[t])`
- Cyclic SoC: `e[T] = e[0]`
- Daily throughput: `Σ p_c[t] · Δt ≤ N_cyc · E_usable`

The binary `z[t]` matters: without it, simultaneous charge+discharge can be exploited as a revenue trick when prices are negative (the optimizer would burn energy through the round-trip loss to be paid for charging). With T ≤ 96 the MILP solves in milliseconds via [HiGHS](https://highs.dev).

---

## Demo dashboard

A live, interactive dashboard ships alongside the framework. Configure any battery asset with the sliders, pick a day, and watch the optimizer rebuild the schedule in real time.

[Launch the dashboard →](./dashboard) *(or open the React artifact in this repo)*

---

## Repository layout

```
helleniflex/
├── src/helleniflex/
│   ├── battery.py        # BatteryAsset dataclass + preset library
│   ├── optimizer.py      # MILP dispatch optimizer (cvxpy + HiGHS)
│   ├── forecaster.py     # Perfect / Naive / Smart forecasters
│   ├── features.py       # FeatureBuilder — multi-source feature matrix
│   ├── ml_forecasters.py # Ridge / LightGBM / Quantile LightGBM models
│   ├── backtester.py     # Daily-rolling revenue backtester
│   └── data_loader.py    # All loaders: synthetic, HEnEx, ENTSO-E, Open-Meteo
├── examples/
│   ├── quickstart.py             # End-to-end synthetic demo
│   ├── real_data_demo.py         # MILP on real HEnEx Excel files
│   ├── entsoe_demo.py            # Multi-source ENTSO-E + cross-validation
│   ├── forecaster_experiment.py  # Ridge + LightGBM training & eval
│   └── revenue_backtest.py       # The headline result: forecast → optimize → settle
├── data/
│   ├── sample_dam_prices.csv
│   ├── henex/                # HEnEx daily Excel files
│   └── entsoe/               # ENTSO-E web-export CSV files (prices, load, RES, flows, gen)
├── docs/
│   ├── ml_pipeline_diagnostics.png   # Headline 4-panel ML chart
│   ├── multi_source_dispatch.png     # Single-day real-data hero chart
│   ├── real_dispatch.png             # Single-day 3-panel dispatch chart
│   ├── example_dispatch.png          # Synthetic dispatch chart
│   └── PITCH.md                      # 6-minute demo script + Q&A prep
├── scripts/
│   ├── build_sample_data.py
│   ├── build_multi_source_chart.py
│   └── build_ml_diagnostics_chart.py
├── dashboard/                # Live React dashboard (single-file)
├── notebooks/demo.ipynb
└── tests/smoke_test.py
```

---

## Headline results

### Real Greek DAM, April 2026 — 29-day end-to-end ML pipeline backtest

![ML pipeline diagnostics v2](docs/ml_pipeline_v2_diagnostics.png)

The pipeline trains on **365 days of real 2025 ENTSO-E data** (Greek DAM clearing prices, day-ahead load forecast, day-ahead wind & solar forecasts, total generation forecast, cross-border physical flows, and **lagged DAM prices from four neighboring markets — Bulgaria, Romania, Italy-North, Italy-South**) and is held out on **April 2026 (29 days)** with strict no-leakage discipline: every input is a quantity a TSO publishes BEFORE the auction closes.

For each test day the pipeline (1) predicts the next day's 96 fifteen-minute prices, (2) feeds those predictions to the MILP optimizer to plan a battery dispatch, then (3) settles the schedule against the **actual realized prices** to compute realized revenue.

| Strategy | €/day | % of oracle | Annualized |
|---|---:|---:|---:|
| Perfect Foresight (oracle, theoretical max) | €267.12 | 100.0% | €48,748 /MWh/yr |
| **Ridge ML forecast (production)** | **€226.79** | **84.9%** | **€41,389 /MWh/yr** |
| LightGBM ML forecast | €219.22 | 82.1% | €40,007 /MWh/yr |
| Naive (last-week-same-hour) | €201.96 | 75.6% | €36,857 /MWh/yr |

**The Ridge production model captures 84.9% of theoretical maximum revenue. The ML lift over the naive baseline is +9.3 percentage points = roughly €4,500 / MWh installed / year of incremental profit** for a 1 MW / 2 MWh asset.

### Feature ablation — what the lift is made of

| Configuration | Ridge capture | Improvement |
|---|---:|---:|
| Baseline: load + wind + solar + total-gen forecasts + lagged prices + calendar | 83.5% | (reference) |
| + Aggregate cross-border flows (5 neighbors as one variable) | 83.5% | + 0.0 pp |
| + Per-neighbor flows (Albania, Bulgaria, Italy, Macedonia, Turkey separately) | 84.6% | + 1.1 pp |
| + Foreign-market lagged prices (Bulgaria, Romania, Italy-North, Italy-South) | **84.9%** | **+ 1.4 pp total** |

LightGBM sees Bulgaria and Romania prices as its #3 and #5 most important features by gain (visible in the feature-importance panel above). Greek DAM has correlation **ρ ≈ 0.90** with Bulgaria and Romania prices and **ρ ≈ 0.66** with Italian prices — the southern Balkan markets are tightly coupled through SDAC market integration.

### Forecast quality

| Model | MAE | RMSE | Negative-price recall | Spike recall (>€200) |
|---|---:|---:|---:|---:|
| Naive | €33.67 | €52.31 | 38% | 17% |
| Ridge (production) | €19.86 | €27.29 | **59%** | 9% |
| LightGBM | €19.22 | €26.19 | 20% | 14% |

Ridge and LightGBM achieve nearly identical MAE (€19.2–19.9/MWh) but learn complementary patterns — Ridge excels at predicting the negative-price moments (59% recall vs LightGBM's 20%), LightGBM picks up high-price spikes that Ridge misses. Despite LightGBM's slightly lower MAE, **Ridge wins on revenue** (84.9% vs 82.1%) because the optimizer benefits more from predicting *direction at the extremes* than from minimising overall error. This is a real and instructive finding: for a battery operator, **MAE is not the right loss function — directional accuracy at price extremes is**.

### Single-day showcase: 29 April 2026

![Optimal dispatch on real Greek DAM with ENTSO-E exogenous data](docs/multi_source_dispatch.png)

> A 1 MW / 2 MWh standalone battery would have made **€323** in a single day by charging through the 10am–4pm solar trough (5 negative-price slots, 29 near-zero slots) and discharging into the morning peak (€182/MWh) and evening peak (€224/MWh). The schedule above is the provably-optimal MILP solution, computed in 40 milliseconds.
>
> The four panels stitch together three independent ENTSO-E publications: day-ahead clearing prices, total system load (forecast vs actual), and net cross-border physical flows. Greece was a heavy net exporter from 5am–noon (~1.1 GW outflow at peak) — that's the surplus driving prices to zero. The same prices reconcile to **HEnEx EL-DAM Results** within 0.0000 €/MWh across all 96 slots, so the pipeline is fed by mutually-validating sources.

### Asset duration sensitivity (perfect foresight, real April 2026 prices)

| Asset | €/day | €/MWh/yr |
|---|---:|---:|
| 1 MW / 1 MWh (1h duration) | ~165 | ~60,000 |
| 1 MW / 2 MWh (2h duration) | 267 | 48,748 |
| 1 MW / 4 MWh (4h duration) | ~395 | ~36,000 |

Shorter-duration batteries earn more **per MWh installed** because they cycle more aggressively against the same daily price spread; longer-duration batteries earn higher **absolute** revenue because they can capture multi-hour shoulders. This is exactly the trade-off real investors care about — and the framework lets you size the asset accordingly.

---

## Data sources

The framework consumes prices from any source that produces a `pd.Series`. Working loaders are shipped for the sources that matter most:

| Source | Used for | Loader | Status |
|---|---|---|---|
| **HEnEx** EL-DAM Results (Excel) | Greek day-ahead market clearing prices | `load_henex_dam_file`, `load_henex_dam_directory` | ✅ **Working — official Excel files parsed directly** |
| **ENTSO-E** Energy Prices (CSV) | Day-ahead clearing price (alternative source) | `load_entsoe_prices_csv` | ✅ Working |
| **ENTSO-E** Total Load (CSV) | Day-ahead load forecast + actual (forecaster feature) | `load_entsoe_load_csv` | ✅ Working |
| **ENTSO-E** Cross-Border Flows (CSV) | Hourly net imports per neighbor (forecaster feature) | `load_entsoe_flows_csv` | ✅ Working |
| **ENTSO-E** Transparency API | Programmatic bulk pulls | `fetch_entsoe_dam` | ✅ Working (requires free API token) |
| **Open-Meteo** | Temperature, irradiance, wind speed | `fetch_openmeteo_weather` | ✅ Working (no auth needed) |
| **IPTO (ADMIE)** | Day-ahead load + RES forecasts | — | ⚠️ ENTSO-E covers the same data more cleanly |
| **Generic CSV** | Any other source | `load_csv_prices` | ✅ Working |

**Cross-validation built in.** The HEnEx EL-DAM Excel and the ENTSO-E day-ahead price CSV are independent publications — HEnEx is the Hellenic Energy Exchange (the Greek operator), ENTSO-E aggregates across all European TSOs. On 29 April 2026 the two sources agree exactly across all 96 fifteen-minute slots (max difference: 0.0000 €/MWh). The `entsoe_demo.py` script performs this check on every run, so any future schema drift surfaces immediately.

The **HEnEx loader** parses the official daily `YYYYMMDD_EL-DAM_Results_EN_v01.xlsx` files. Each file contains the Market Clearing Price for all 96 fifteen-minute slots of a delivery day across every bidding-zone segment (LOAD, SUPPLY, exports, imports, storage). The loader extracts the canonical `LOAD/HV` slice and returns a clean datetime-indexed price series.

The **ENTSO-E web export loaders** parse the CSVs you can download directly from the [Transparency Platform UI](https://transparency.entsoe.eu) without an API token — useful for ad-hoc analysis or hackathons before token approval comes through. The three loaders cover prices, load (forecast + actual), and cross-border flows.

---

## What we deliberately did **not** do

- ❌ **Reinforcement learning.** The data scarcity framing rules it out: there is no battery operational history to train on. RL would also be opaque to judges.
- ❌ **Intraday / ancillary markets.** The brief specifies DAM. We acknowledge multi-market arbitrage as the natural extension.
- ❌ **Fancy LSTM forecasts.** Ridge regression beats deep models on day-ahead price forecasting in published benchmarks, trains in milliseconds, and is fully interpretable.

---

## Roadmap

- Stochastic optimization with explicit price-forecast uncertainty bounds
- Co-optimization across DAM + Intraday + ancillary services (FCR, aFRR)
- Asset-aware degradation modelling (calendar + cycle aging, beyond throughput cost)
- Integration with HEnEx live API for real-time bid generation

---

## License

MIT.
