from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


class PriceForecaster(Protocol):
    name: str

    def predict(self, target_date: pd.Timestamp, history: pd.Series) -> np.ndarray:
        ...


def _periods_per_day(history: pd.Series) -> int:
    if len(history) < 2:
        return 96
    delta = history.index[1] - history.index[0]
    minutes = delta.total_seconds() / 60.0
    return 24 if abs(minutes - 60.0) < 1e-3 else 96


def _day_slice(history: pd.Series, day_offset_back: int, periods: int) -> Optional[np.ndarray]:
    if len(history) < day_offset_back * periods:
        return None
    end   = len(history) - (day_offset_back - 1) * periods
    start = end - periods
    if start < 0:
        return None
    return history.iloc[start:end].values


@dataclass
class PerfectForesightForecaster:
    name: str = "Perfect Foresight"

    def predict(
        self,
        target_date: pd.Timestamp,
        history: pd.Series,
        actual_prices: Optional[pd.Series] = None,
    ) -> np.ndarray:
        if actual_prices is None:
            raise ValueError("PerfectForesightForecaster requires `actual_prices`.")
        end = target_date + pd.Timedelta(days=1)
        day = actual_prices.loc[
            (actual_prices.index >= target_date) & (actual_prices.index < end)
        ]
        return day.values


@dataclass
class NaiveForecaster:
    name: str = "Naive (last-week)"

    def predict(self, target_date: pd.Timestamp, history: pd.Series) -> np.ndarray:
        periods   = _periods_per_day(history)
        last_week = _day_slice(history, day_offset_back=7, periods=periods)
        if last_week is None:
            last_week = _day_slice(history, day_offset_back=1, periods=periods)
        if last_week is None:
            last_week = np.full(periods, 100.0)
        return last_week


class SmartForecaster:
    """Ridge regression with calendar + lag features, one model per period-of-day."""

    name = "Smart (Ridge)"

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha    = alpha
        self._models: dict[int, Ridge] = {}
        self._periods = 96
        self._fitted  = False

    def _make_X(
        self,
        history: pd.Series,
        target_date: pd.Timestamp,
        exog: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        periods = self._periods
        feats   = []
        for back in (1, 2, 7):
            day = _day_slice(history, day_offset_back=back, periods=periods)
            if day is None:
                day = np.full(periods, history.mean() if len(history) else 100.0)
            feats.append(day)

        try:
            recent      = history.iloc[-7 * periods:].values.reshape(-1, periods)
            rolling_mean = recent.mean(axis=0)
        except Exception:
            rolling_mean = np.full(periods, history.mean() if len(history) else 100.0)
        feats.append(rolling_mean)

        X   = np.column_stack(feats)
        dow = target_date.dayofweek
        month = target_date.month
        cal = np.tile(
            [
                float(dow >= 5),
                np.sin(2 * np.pi * month / 12),
                np.cos(2 * np.pi * month / 12),
            ],
            (periods, 1),
        )
        X = np.hstack([X, cal])

        if exog is not None:
            day_exog = exog.loc[
                (exog.index >= target_date) & (exog.index < target_date + pd.Timedelta(days=1))
            ]
            if len(day_exog) == periods:
                X = np.hstack([X, day_exog.values])
        return X

    def fit(self, history: pd.Series, exog: Optional[pd.DataFrame] = None) -> "SmartForecaster":
        self._periods = _periods_per_day(history)
        periods       = self._periods
        n_days        = len(history) // periods
        if n_days < 14:
            raise ValueError("Need at least 14 days of history to fit SmartForecaster")

        prices_matrix = history.iloc[: n_days * periods].values.reshape(n_days, periods)
        Xs, ys = [], []
        for d in range(7, n_days):
            target_date  = history.index[d * periods]
            hist_so_far  = history.iloc[: d * periods]
            X_d = self._make_X(
                hist_so_far, target_date,
                exog=exog.iloc[: d * periods] if exog is not None else None,
            )
            Xs.append(X_d)
            ys.append(prices_matrix[d])

        X_all = np.stack(Xs, axis=0)
        y_all = np.stack(ys, axis=0)
        for p in range(periods):
            m = Ridge(alpha=self.alpha)
            m.fit(X_all[:, p, :], y_all[:, p])
            self._models[p] = m
        self._fitted = True
        return self

    def predict(
        self,
        target_date: pd.Timestamp,
        history: pd.Series,
        exog: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        if not self._fitted:
            self.fit(history, exog=exog)
        X   = self._make_X(history, target_date, exog=exog)
        out = np.zeros(self._periods)
        for p in range(self._periods):
            out[p] = self._models[p].predict(X[p : p + 1, :])[0]
        return out


class EnsembleForecaster:
    """
    Averaged ensemble of two Ridge models with different regularisation strengths.
    Applies a D-1 bias correction: blends 30% of the most recent prediction error
    so the forecast self-corrects systematic drift.
    """

    name = "Smart (Ridge Ensemble + bias correction)"

    def __init__(self, alpha_strong: float = 2.0, alpha_light: float = 0.1) -> None:
        self._fc_strong = SmartForecaster(alpha=alpha_strong)
        self._fc_light  = SmartForecaster(alpha=alpha_light)
        self._periods   = 96
        self._fitted    = False

    def fit(self, history: pd.Series, exog: Optional[pd.DataFrame] = None) -> "EnsembleForecaster":
        self._fc_strong.fit(history, exog=exog)
        self._fc_light.fit(history, exog=exog)
        self._periods = _periods_per_day(history)
        self._fitted  = True
        return self

    def predict(
        self,
        target_date: pd.Timestamp,
        history: pd.Series,
        exog: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        if not self._fitted:
            self.fit(history, exog=exog)

        pred_strong = self._fc_strong.predict(target_date, history, exog=exog)
        pred_light  = self._fc_light.predict(target_date, history, exog=exog)
        forecast    = 0.5 * pred_strong + 0.5 * pred_light

        # Bias correction: compute D-1 forecast error and blend 30% into today's forecast
        periods = self._periods
        if len(history) >= 2 * periods:
            yesterday   = target_date - pd.Timedelta(days=1)
            hist_before = history[history.index < yesterday]
            if len(hist_before) >= 14 * periods:
                try:
                    pred_yesterday = (
                        0.5 * self._fc_strong.predict(yesterday, hist_before, exog=exog)
                        + 0.5 * self._fc_light.predict(yesterday, hist_before, exog=exog)
                    )
                    actual_yesterday = history.iloc[-periods:].values
                    error            = actual_yesterday - pred_yesterday
                    forecast         = forecast + 0.30 * error
                except Exception:
                    pass  # skip bias correction if history is too short

        return forecast
