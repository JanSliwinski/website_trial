"""
Feature engineering for day-ahead price forecasting.

The `FeatureBuilder` produces a single 15-minute-indexed DataFrame ready
for model training. It enforces the central rule of price forecasting:

    EVERY FEATURE USED TO PREDICT PRICE AT TIME t MUST BE KNOWN
    AT THE FORECAST CUT-OFF TIME (11:00 CET on day D-1).

Concretely, for each delivery day D, we have access to:
  • Historical actual prices up to and including day D-1
  • Day-ahead TSO load forecast for day D (published before auction close)
  • Day-ahead TSO RES (wind+solar) forecast for day D
  • Day-ahead TSO total generation forecast for day D
  • Cross-border scheduled flows for day D-1 (used as proxy for D-day
    flow patterns; we DO NOT use realised D-day flows)
  • Calendar features (deterministic)
  • Weather forecast for day D (Open-Meteo gives day-ahead forecasts)

We MUST NOT use:
  • Actual realised prices on day D (this is the target)
  • Actual realised load/RES/generation on day D
  • Actual realised cross-border flows on day D

The builder keeps these two sets cleanly separate via column naming:
  • `*_da_forecast_*`  → day-ahead, available at forecast time, OK as input
  • `*_actual_*`       → realised, NOT OK as input, used only for evaluation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


def _hourly_to_15min(hourly_df: pd.DataFrame, target_idx: pd.DatetimeIndex) -> pd.DataFrame:
    """Upsample an hourly DataFrame to a 15-min target index.

    Forward-fills WITHIN the original hour, but does NOT propagate values
    beyond the last available timestamp + 1 hour. This prevents stale
    values from leaking forward when the source data ends earlier than
    the target index.
    """
    if len(hourly_df) == 0:
        return pd.DataFrame(index=target_idx, columns=hourly_df.columns)
    # Mark the natural end of each row as last_ts + 1 hour
    last_valid = hourly_df.index.max() + pd.Timedelta(hours=1)
    # ffill but only within data range
    upsampled = hourly_df.reindex(target_idx, method="ffill")
    # Mask out any rows beyond last_valid
    mask = target_idx >= last_valid
    if mask.any():
        upsampled.loc[mask, :] = np.nan
    return upsampled


@dataclass
class FeatureBuilder:
    """Build a 15-minute feature matrix from multi-source ENTSO-E data.

    Parameters
    ----------
    prices : pd.Series
        15-minute DAM prices (target). Indexed by datetime.
    load : pd.DataFrame
        Output of `load_entsoe_load_csv`. Columns: load_forecast_mw,
        load_actual_mw.
    renewables : pd.DataFrame
        Output of `load_entsoe_renewable_forecast_csv`. Columns:
        renewables_da_forecast_mw, renewables_actual_mw. HOURLY → forward
        filled to 15-min.
    flows : pd.DataFrame, optional
        Output of `load_entsoe_flows_csv`. HOURLY → forward filled.
    gen_total : pd.DataFrame, optional
        Output of `load_entsoe_total_generation_forecast_csv`. HOURLY.
    weather : pd.DataFrame, optional
        Open-Meteo aggregated weather features. HOURLY.

    Notes
    -----
    Hourly features are forward-filled to 15-minute resolution because
    the underlying value is constant within the hour (the TSO publishes
    one forecast per hour). This is mathematically correct, not an
    interpolation hack.
    """

    prices: pd.Series
    load: pd.DataFrame
    wind: Optional[pd.DataFrame] = None
    solar: Optional[pd.DataFrame] = None
    renewables: Optional[pd.DataFrame] = None  # combined; used if wind+solar not given
    flows: Optional[pd.DataFrame] = None
    flows_per_neighbor: Optional[pd.DataFrame] = None  # per-neighbor net flows
    gen_total: Optional[pd.DataFrame] = None
    weather: Optional[pd.DataFrame] = None
    # External market features
    gas_eur_per_mwh: Optional[pd.Series] = None  # daily TTF, ffill within day
    carbon_eur_per_t: Optional[pd.Series] = None  # daily EUA
    external_prices: Optional[dict] = None  # {country_code: pd.Series of DAM prices}

    # ---- public API ----

    def build(
        self,
        with_lags: bool = True,
        with_rolling: bool = True,
        with_calendar: bool = True,
        drop_leakage: bool = True,
    ) -> pd.DataFrame:
        """Return the full feature DataFrame indexed by 15-min timestamp.

        Parameters
        ----------
        with_lags : bool
            Add lagged price features (1, 2, 7, 14 days).
        with_rolling : bool
            Add rolling-window statistics (24h, 7d).
        with_calendar : bool
            Add calendar features (hour, day-of-week, month, holiday flag).
        drop_leakage : bool
            If True, drop columns containing actual/realised values that
            would leak future information into the training set.
            Set to False ONLY for evaluation metrics.

        Returns
        -------
        pd.DataFrame
            One row per 15-minute slot, with `dam_price_eur_mwh` as the
            target column. Other columns are predictive features.
        """
        idx = self.prices.index
        df = pd.DataFrame(index=idx)
        df["dam_price_eur_mwh"] = self.prices.values

        # === Load (15-min resolution natively) ===
        df["load_forecast_mw"] = self.load["load_forecast_mw"].reindex(idx)
        if not drop_leakage:
            df["load_actual_mw"] = self.load["load_actual_mw"].reindex(idx)

        # === Wind & solar separately if provided, else combined renewables ===
        # Track total RES forecast for residual demand calculation.
        # Residual demand = load - (wind + solar). Requires BOTH to be known
        # to avoid systematic over-/under-estimation when one is missing.
        res_da_total = pd.Series(0.0, index=idx)
        wind_known = pd.Series(False, index=idx)
        solar_known = pd.Series(False, index=idx)

        if self.wind is not None:
            w_15 = _hourly_to_15min(self.wind, idx)
            wind_col = [c for c in w_15.columns if "da_forecast" in c][0]
            df["wind_da_forecast_mw"] = w_15[wind_col].values
            res_da_total = res_da_total.add(
                w_15[wind_col].fillna(0).values, fill_value=0
            )
            wind_known = pd.Series(w_15[wind_col].notna().values, index=idx)
            if not drop_leakage:
                actual_col = [c for c in w_15.columns if "actual" in c][0]
                df["wind_actual_mw"] = w_15[actual_col].values

        if self.solar is not None:
            s_15 = _hourly_to_15min(self.solar, idx)
            solar_col = [c for c in s_15.columns if "da_forecast" in c][0]
            df["solar_da_forecast_mw"] = s_15[solar_col].values
            res_da_total = res_da_total.add(
                s_15[solar_col].fillna(0).values, fill_value=0
            )
            solar_known = pd.Series(s_15[solar_col].notna().values, index=idx)
            if not drop_leakage:
                actual_col = [c for c in s_15.columns if "actual" in c][0]
                df["solar_actual_mw"] = s_15[actual_col].values

        # Total RES forecast: only valid when both wind AND solar are known.
        # When either is missing we set NaN (LightGBM handles this; Ridge
        # imputes via median).
        if self.wind is not None and self.solar is not None:
            both_known = wind_known.values & solar_known.values
        elif self.wind is not None:
            both_known = wind_known.values
        elif self.solar is not None:
            both_known = solar_known.values
        else:
            both_known = np.zeros(len(idx), dtype=bool)

        df["renewables_total_da_forecast_mw"] = pd.Series(
            np.where(both_known, res_da_total.values, np.nan), index=idx
        )

        if self.renewables is not None and self.wind is None and self.solar is None:
            r_15 = _hourly_to_15min(self.renewables, idx)
            renew_col = [c for c in r_15.columns if "da_forecast" in c][0]
            df["renewables_da_forecast_mw"] = r_15[renew_col].values
            res_da_total = pd.Series(r_15[renew_col].fillna(0).values, index=idx)
            if not drop_leakage:
                actual_col = [c for c in r_15.columns if "actual" in c][0]
                df["renewables_actual_mw"] = r_15[actual_col].values

        # Residual demand = load forecast − total RES forecast.
        # THE single most predictive feature for European DAM prices.
        df["residual_demand_mw"] = (
            df["load_forecast_mw"] - df["renewables_total_da_forecast_mw"]
        )

        # === Cross-border flows (hourly → ffill) ===
        if self.flows is not None:
            flows_15 = _hourly_to_15min(self.flows, idx)
            df["flow_net_import_mw"] = flows_15["net_import_mw"].values
            df["flow_imports_mw"] = flows_15["total_imports_mw"].values
            df["flow_exports_mw"] = flows_15["total_exports_mw"].values

        if self.flows_per_neighbor is not None:
            fpn_15 = _hourly_to_15min(self.flows_per_neighbor, idx)
            for col in fpn_15.columns:
                df[col] = fpn_15[col].values

        # === Total generation forecast (hourly) ===
        if self.gen_total is not None:
            gt_15 = _hourly_to_15min(self.gen_total, idx)
            df["gen_total_forecast_mw"] = gt_15["gen_forecast_mw"].values

        # === Weather (if provided) ===
        if self.weather is not None:
            w_15 = _hourly_to_15min(self.weather, idx)
            for col in w_15.columns:
                df[f"weather_{col}"] = w_15[col].values

        # === Gas (TTF) — daily series, broadcast to 15-min ===
        # Forward-fill within the day; values are constant across slots in
        # one day. NOT future-leaking: TTF for day D is published before day D
        # opens (it's the spot/front-month settle from the prior session).
        if self.gas_eur_per_mwh is not None:
            df["gas_ttf_eur_per_mwh"] = (
                self.gas_eur_per_mwh.reindex(idx, method="ffill").values
            )

        # === Carbon (EUA) — daily series, broadcast to 15-min ===
        if self.carbon_eur_per_t is not None:
            df["carbon_eua_eur_per_t"] = (
                self.carbon_eur_per_t.reindex(idx, method="ffill").values
            )

        # === External (neighboring-country) DAM prices — LAGGED ===
        # We use price_lag_1d of each neighboring market, NOT the same-day
        # price (which is published simultaneously and could be argued either
        # way). Lag-1 is unambiguously known at forecast time and captures
        # the regional level that propagates into Greece.
        if self.external_prices is not None:
            for cc, ext_series in self.external_prices.items():
                if ext_series is None or len(ext_series) == 0:
                    continue
                # Align to our 15-min index, then shift by 1 day (96 slots
                # if 15-min, 24 if hourly — let's be safe and shift by time)
                aligned = ext_series.reindex(idx, method="ffill")
                # If the foreign series resolution is coarser, the simple
                # shift of 96 rows may not equal exactly 1 day; use time
                # shift instead.
                lag1_time = aligned.shift(1, freq="D")
                df[f"price_{cc.lower()}_lag_1d"] = lag1_time.reindex(idx).values

        # === Lagged target prices ===
        if with_lags:
            # 96 slots = 1 day @ 15-min resolution
            for days_back, label in [(1, "1d"), (2, "2d"), (7, "7d"), (14, "14d")]:
                shift = days_back * 96
                df[f"price_lag_{label}"] = self.prices.shift(shift).reindex(idx)

        # === Rolling statistics ===
        if with_rolling:
            df["price_roll24h_mean"] = (
                self.prices.shift(96).rolling("1D").mean().reindex(idx)
            )
            df["price_roll7d_mean"] = (
                self.prices.shift(96).rolling("7D").mean().reindex(idx)
            )
            df["price_roll7d_std"] = (
                self.prices.shift(96).rolling("7D").std().reindex(idx)
            )

        # === Calendar features ===
        if with_calendar:
            df["cal_hour"] = idx.hour
            df["cal_minute"] = idx.minute
            df["cal_dayofweek"] = idx.dayofweek
            df["cal_is_weekend"] = (idx.dayofweek >= 5).astype(int)
            df["cal_month"] = idx.month
            df["cal_dayofyear"] = idx.dayofyear
            # Sinusoidal time-of-day encoding helps tree models very little
            # but linear models a lot
            slot = idx.hour * 4 + idx.minute // 15  # 0..95
            df["cal_slot_sin"] = np.sin(2 * np.pi * slot / 96)
            df["cal_slot_cos"] = np.cos(2 * np.pi * slot / 96)

        return df

    def feature_columns(self, df: pd.DataFrame) -> list:
        """Return the feature column names (everything except the target)."""
        return [c for c in df.columns if c != "dam_price_eur_mwh"]

    @staticmethod
    def split_train_test(
        df: pd.DataFrame, test_days: int = 30
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Time-based split: last `test_days` are held out as test set.

        Critical: NEVER use random splits in time-series forecasting.
        That leaks future information into the training set.
        """
        cutoff = df.index.max().normalize() - pd.Timedelta(days=test_days)
        train = df[df.index < cutoff].copy()
        test = df[df.index >= cutoff].copy()
        return train, test
