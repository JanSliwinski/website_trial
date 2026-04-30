"""
Price forecasting layer.

Implements three forecasters, deliberately ordered from "upper bound"
to "production-realistic". Reporting all three turns the deliverable
into a story:

    Perfect foresight  →  the theoretical maximum revenue
    Smart forecaster   →  what we actually deliver
    Naive forecaster   →  the floor any sensible operator beats

The optimizer is forecaster-agnostic. All three return arrays of the
same length and units (€/MWh) and can be plugged into the same
backtester.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


class PriceForecaster(Protocol):
    """Common interface for all forecasters."""

    name: str

    def predict(self, target_date: pd.Timestamp, history: pd.Series) -> np.ndarray:
        """Return forecasted prices for `target_date` given history.

        Parameters
        ----------
        target_date
            The day we want to forecast (00:00 of that day).
        history
            Series of historical prices indexed by datetime, with
            entries strictly before target_date.

        Returns
        -------
        np.ndarray of length 96 (15-min) or 24 (hourly), depending on
        the resolution of `history`.
        """
        ...


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _periods_per_day(history: pd.Series) -> int:
    """Infer 24 (hourly) or 96 (15-min) from the index frequency."""
    if len(history) < 2:
        return 96
    delta = history.index[1] - history.index[0]
    minutes = delta.total_seconds() / 60.0
    if abs(minutes - 60.0) < 1e-3:
        return 24
    return 96  # default to 15-min


def _day_slice(history: pd.Series, day_offset_back: int, periods: int) -> Optional[np.ndarray]:
    """Return the price series for `day_offset_back` days before the
    *last* timestamp in `history`. None if not enough data."""
    if len(history) < day_offset_back * periods:
        return None
    end = len(history) - (day_offset_back - 1) * periods
    start = end - periods
    if start < 0:
        return None
    return history.iloc[start:end].values


# ----------------------------------------------------------------------
# Tier 1: Perfect foresight (oracle)
# ----------------------------------------------------------------------

@dataclass
class PerfectForesightForecaster:
    """Returns the actual realised prices for the target day.

    This is *not* a real forecaster. It is the upper-bound benchmark:
    the revenue achievable if you knew tomorrow's prices exactly. Every
    realistic strategy is judged as a percentage of this number.
    """

    name: str = "Perfect Foresight"

    def predict(
        self,
        target_date: pd.Timestamp,
        history: pd.Series,
        actual_prices: Optional[pd.Series] = None,
    ) -> np.ndarray:
        if actual_prices is None:
            raise ValueError(
                "PerfectForesightForecaster requires `actual_prices`."
            )
        # Slice the actual prices for that date
        end = target_date + pd.Timedelta(days=1)
        day = actual_prices.loc[(actual_prices.index >= target_date)
                                & (actual_prices.index < end)]
        return day.values


# ----------------------------------------------------------------------
# Tier 2: Naive — same day last week
# ----------------------------------------------------------------------

@dataclass
class NaiveForecaster:
    """Tomorrow's prices = same hour, same day-of-week, last week.

    Hard-to-beat baseline in markets with strong weekly seasonality.
    Doubles as a sanity check: if your fancy model loses to this, the
    fancy model is broken.
    """

    name: str = "Naive (last-week)"

    def predict(self, target_date: pd.Timestamp, history: pd.Series) -> np.ndarray:
        periods = _periods_per_day(history)
        last_week = _day_slice(history, day_offset_back=7, periods=periods)
        if last_week is None:
            # Not enough history → fall back to yesterday
            last_week = _day_slice(history, day_offset_back=1, periods=periods)
        if last_week is None:
            # Truly nothing → flat €100/MWh
            last_week = np.full(periods, 100.0)
        return last_week


# ----------------------------------------------------------------------
# Tier 3: Smart — Ridge regression with calendar + lag features
# ----------------------------------------------------------------------

class SmartForecaster:
    """Ridge regression on lagged prices and calendar features.

    Deliberately simple: linear, interpretable, trains in milliseconds,
    and beats LSTM-style models on day-ahead price forecasting in most
    published benchmarks. Designed for a hackathon: zero hyperparameter
    tuning, no train/val splits to babysit.

    Optional exogenous features (load, RES, gas, weather) can be passed
    via the `exog` argument to fit() and predict(); the forecaster will
    use them if present.
    """

    name = "Smart (Ridge + calendar)"

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self._models: dict[int, Ridge] = {}  # one model per period-of-day
        self._periods: int = 96
        self._fitted = False

    # -- Feature engineering -------------------------------------------------

    def _make_X(self, history: pd.Series, target_date: pd.Timestamp,
                exog: Optional[pd.DataFrame] = None) -> np.ndarray:
        """Build a feature row for every period-of-day on target_date.

        Returns an array of shape (periods, n_features).
        """
        periods = self._periods
        # Same period yesterday, 2 days ago, 7 days ago
        feats = []
        for back in (1, 2, 7):
            day = _day_slice(history, day_offset_back=back, periods=periods)
            if day is None:
                day = np.full(periods, history.mean() if len(history) else 100.0)
            feats.append(day)
        # Rolling 7-day mean per period
        try:
            recent = history.iloc[-7 * periods:].values.reshape(-1, periods)
            rolling_mean = recent.mean(axis=0)
        except Exception:
            rolling_mean = np.full(periods, history.mean() if len(history) else 100.0)
        feats.append(rolling_mean)

        X = np.column_stack(feats)  # (periods, 4)

        # Calendar features (constant across the day)
        dow = target_date.dayofweek
        is_weekend = float(dow >= 5)
        month = target_date.month
        cal = np.tile(
            [is_weekend, np.sin(2 * np.pi * month / 12), np.cos(2 * np.pi * month / 12)],
            (periods, 1),
        )
        X = np.hstack([X, cal])

        # Exogenous (optional, e.g. day-ahead load / RES forecast)
        if exog is not None:
            day_exog = exog.loc[(exog.index >= target_date)
                                & (exog.index < target_date + pd.Timedelta(days=1))]
            if len(day_exog) == periods:
                X = np.hstack([X, day_exog.values])
        return X

    # -- Fit & predict -------------------------------------------------------

    def fit(self, history: pd.Series, exog: Optional[pd.DataFrame] = None) -> "SmartForecaster":
        """Fit one Ridge model per period-of-day on the supplied history."""
        self._periods = _periods_per_day(history)
        periods = self._periods
        # Build (n_days, periods) matrix of prices
        n_days = len(history) // periods
        if n_days < 14:
            raise ValueError("Need at least 14 days of history to fit SmartForecaster")
        prices_matrix = history.iloc[: n_days * periods].values.reshape(n_days, periods)

        # For each target day d (starting from day 7 to have a week of lags)
        # build X by replaying _make_X on the truncated history.
        Xs, ys = [], []
        for d in range(7, n_days):
            target_date = history.index[d * periods]
            hist_so_far = history.iloc[: d * periods]
            X_d = self._make_X(hist_so_far, target_date,
                               exog=exog.iloc[: d * periods] if exog is not None else None)
            y_d = prices_matrix[d]  # (periods,)
            Xs.append(X_d)
            ys.append(y_d)

        # Train one model per period-of-day
        # Stack: each period gets (n_train_days,) target and (n_train_days, n_features) X
        X_all = np.stack(Xs, axis=0)  # (n_train_days, periods, n_features)
        y_all = np.stack(ys, axis=0)  # (n_train_days, periods)
        for p in range(periods):
            m = Ridge(alpha=self.alpha)
            m.fit(X_all[:, p, :], y_all[:, p])
            self._models[p] = m
        self._fitted = True
        return self

    def predict(self, target_date: pd.Timestamp, history: pd.Series,
                exog: Optional[pd.DataFrame] = None) -> np.ndarray:
        if not self._fitted:
            # Auto-fit if user forgot. Fail-safe for the hackathon.
            self.fit(history, exog=exog)
        X = self._make_X(history, target_date, exog=exog)
        out = np.zeros(self._periods)
        for p in range(self._periods):
            out[p] = self._models[p].predict(X[p:p + 1, :])[0]
        return out
