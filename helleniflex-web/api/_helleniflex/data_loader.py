from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd


def make_synthetic_greek_dam_prices(
    start: str = "2024-01-01",
    end: str = "2026-12-31",
    freq: str = "15min",
    seed: int = 42,
) -> pd.Series:
    """Synthetic Greek DAM prices with realistic daily/seasonal patterns."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start=start, end=end, freq=freq)
    n = len(idx)

    hours = np.asarray(idx.hour + idx.minute / 60.0, dtype=float)
    dow = np.asarray(idx.dayofweek, dtype=int)
    doy = np.asarray(idx.dayofyear, dtype=float)
    is_weekend = (dow >= 5).astype(float)

    morning = 30 * np.exp(-((hours - 8) ** 2) / 4)
    evening = 60 * np.exp(-((hours - 20) ** 2) / 5)
    midday_solar_dip = -45 * np.exp(-((hours - 13) ** 2) / 6)

    season = np.cos(2 * np.pi * (doy - 15) / 365)
    seasonal_level = 25 * season + 110
    summer_dip_amp = 1.0 + 0.6 * (-season).clip(min=0)
    daily_shape = (
        morning + evening * (1.0 + 0.3 * season.clip(min=0))
        + midday_solar_dip * summer_dip_amp
    )

    weekend_factor = 1.0 - 0.15 * is_weekend

    drift = 15 * np.sin(2 * np.pi * doy / 365 * 1.3 + 0.5) \
        + 5 * np.sin(2 * np.pi * np.arange(n) / (96 * 30) + 1.7)

    noise = rng.normal(0, 8, n) + rng.normal(0, 25, n) * (rng.random(n) > 0.97)

    prices = (seasonal_level + daily_shape) * weekend_factor + drift + noise

    spring_summer_mask = (idx.month >= 3) & (idx.month <= 9)
    midday_mask = (hours >= 12) & (hours <= 15)
    candidate = spring_summer_mask & midday_mask
    flip = rng.random(n) < 0.05
    neg_mask = candidate & flip
    prices[neg_mask] = rng.uniform(-30, -2, neg_mask.sum())

    prices = np.clip(prices, -50, 400)

    return pd.Series(prices, index=idx, name="dam_price_eur_mwh")
