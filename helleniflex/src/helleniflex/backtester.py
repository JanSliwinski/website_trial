"""
Daily-rolling backtester.

For each day in the evaluation window:
  1. Build a forecast from price history strictly before that day
  2. Solve the dispatch MILP on the forecasted prices
  3. Settle the resulting schedule at the *actual* prices for that day
  4. Roll the SoC forward (the next day starts where this one ended)

This is the only honest way to evaluate a forecast-driven scheduler:
the optimizer never peeks at tomorrow's actual prices.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .battery import BatteryAsset
from .optimizer import BatteryOptimizer, DispatchResult
from .forecaster import PerfectForesightForecaster


@dataclass
class BacktestResult:
    """Aggregate output of a backtest run."""
    daily: pd.DataFrame              # one row per day (revenue, cycles, ...)
    schedules: list[DispatchResult]  # full per-day schedules
    asset_name: str
    forecaster_name: str

    # ----- KPIs the dashboard / pitch deck care about -----

    @property
    def total_revenue_eur(self) -> float:
        return float(self.daily["revenue_actual_eur"].sum())

    @property
    def total_cycles(self) -> float:
        return float(self.daily["cycles"].sum())

    @property
    def avg_daily_revenue_eur(self) -> float:
        return float(self.daily["revenue_actual_eur"].mean())

    @property
    def revenue_per_mwh_per_year(self) -> float:
        """Annualised €/MWh of installed capacity — the standard
        industry metric for storage profitability."""
        if len(self.daily) == 0:
            return 0.0
        days = len(self.daily)
        cap = self.daily["capacity_mwh"].iloc[0]
        if cap <= 0:
            return 0.0
        return self.total_revenue_eur / cap / days * 365

    def summary(self) -> str:
        return (
            f"[{self.asset_name} | {self.forecaster_name}]  "
            f"days={len(self.daily)}  "
            f"total=€{self.total_revenue_eur:,.0f}  "
            f"avg/day=€{self.avg_daily_revenue_eur:,.0f}  "
            f"€/MWh/yr={self.revenue_per_mwh_per_year:,.0f}  "
            f"cycles/day={self.total_cycles / max(len(self.daily), 1):.2f}"
        )


class Backtester:
    """Roll the optimizer over a price history, day by day.

    Parameters
    ----------
    battery
        Asset spec.
    forecaster
        Object with a .predict(target_date, history, ...) method.
    optimizer_kwargs
        Forwarded to BatteryOptimizer (e.g. ``use_binary=False``).
    """

    def __init__(
        self,
        battery: BatteryAsset,
        forecaster=None,
        optimizer_kwargs: Optional[dict] = None,
    ) -> None:
        self.battery = battery
        self.forecaster = forecaster or PerfectForesightForecaster()
        self.optimizer = BatteryOptimizer(battery, **(optimizer_kwargs or {}))

    # ---------------------------------------------------------------- #

    def run(
        self,
        prices: pd.Series,
        start: Optional[pd.Timestamp] = None,
        end: Optional[pd.Timestamp] = None,
        exog: Optional[pd.DataFrame] = None,
        progress: bool = False,
    ) -> BacktestResult:
        """
        Parameters
        ----------
        prices
            Datetime-indexed price series (€/MWh) at uniform spacing.
        start, end
            Window for backtesting. Default: first full day with enough
            history → last full day.
        exog
            Optional exogenous features for forecasters that use them.

        Notes
        -----
        Requires at least 14 days of history before `start` so the
        SmartForecaster has something to fit on.
        """
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError("`prices` must be datetime-indexed")

        # Infer resolution
        delta = prices.index[1] - prices.index[0]
        dt_hours = delta.total_seconds() / 3600.0
        periods_per_day = int(round(24 / dt_hours))

        # Default window
        first_day = prices.index[0].normalize() + pd.Timedelta(days=14)
        last_day = (prices.index[-1] - pd.Timedelta(days=1)).normalize()
        start = pd.Timestamp(start).normalize() if start is not None else first_day
        end = pd.Timestamp(end).normalize() if end is not None else last_day
        if start > end:
            raise ValueError("Empty backtest window: start > end")

        # Pre-fit smart forecaster on history before `start`
        if hasattr(self.forecaster, "fit") and not getattr(self.forecaster, "_fitted", False):
            history_for_fit = prices.loc[prices.index < start]
            try:
                self.forecaster.fit(history_for_fit,
                                    exog=exog.loc[exog.index < start] if exog is not None else None)
            except Exception:
                # Forecaster will fall back on its own
                pass

        # Roll
        rows = []
        schedules = []
        soc_carry = self.battery.initial_soc_mwh
        days = pd.date_range(start, end, freq="D")
        iterator = days
        if progress:
            try:
                from tqdm import tqdm
                iterator = tqdm(days, desc="Backtesting")
            except ImportError:
                pass

        for day in iterator:
            day_end = day + pd.Timedelta(days=1)
            history = prices.loc[prices.index < day]
            actual_day = prices.loc[(prices.index >= day) & (prices.index < day_end)]
            if len(actual_day) != periods_per_day:
                continue  # incomplete day, skip

            # Forecast
            try:
                if isinstance(self.forecaster, PerfectForesightForecaster):
                    forecast = self.forecaster.predict(day, history, actual_prices=prices)
                else:
                    if exog is not None:
                        forecast = self.forecaster.predict(day, history, exog=exog)
                    else:
                        forecast = self.forecaster.predict(day, history)
            except Exception as e:
                # If forecasting fails, skip the day
                print(f"Forecast failed for {day}: {e}")
                continue

            # Optimize on forecasted prices
            schedule = self.optimizer.optimize(
                forecast,
                dt_hours=dt_hours,
                initial_soc_mwh=soc_carry,
                enforce_cyclic=True,
            )

            # Settle at actual prices
            actual_revenue = BatteryOptimizer.settle(schedule, actual_day.values)
            forecast_mae = float(np.mean(np.abs(forecast - actual_day.values)))

            rows.append({
                "date": day,
                "revenue_forecast_eur": schedule.revenue_eur,
                "revenue_actual_eur": actual_revenue,
                "degradation_eur": schedule.degradation_cost_eur,
                "net_pnl_eur": actual_revenue - schedule.degradation_cost_eur,
                "cycles": schedule.cycles,
                "forecast_mae_eur_mwh": forecast_mae,
                "actual_price_min": float(actual_day.min()),
                "actual_price_max": float(actual_day.max()),
                "actual_price_spread": float(actual_day.max() - actual_day.min()),
                "status": schedule.status,
                "capacity_mwh": self.battery.capacity_mwh,
                "power_mw": self.battery.power_mw,
            })
            schedules.append(schedule)

            # Roll SoC: next day starts where this one ended (but cyclic
            # constraint already enforces e[T] = e[0], so this is a no-op
            # in the default flow — kept here for non-cyclic variants).
            soc_carry = float(schedule.soc_mwh[-1])

        df = pd.DataFrame(rows)
        if len(df):
            df = df.set_index("date")
        return BacktestResult(
            daily=df,
            schedules=schedules,
            asset_name=self.battery.name,
            forecaster_name=getattr(self.forecaster, "name", type(self.forecaster).__name__),
        )
