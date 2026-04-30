"""Estimate tomorrow's supply mix from forecast-time inputs.

The DAM forecast benefits from knowing not only the raw drivers
(weather, load, gas, carbon) but also what those drivers imply for the
generation stack:

    * expected gas production
    * expected solar production
    * expected wind production
    * their percentage shares in total generation

This module learns that mapping from historical ENTSO-E generation-by-type
data using only variables that are known before the day-ahead auction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _align_hourly_to_target(
    hourly_df: pd.DataFrame, target_idx: pd.DatetimeIndex
) -> pd.DataFrame:
    """Forward-fill hourly data within its valid range onto `target_idx`."""
    if len(hourly_df) == 0:
        return pd.DataFrame(index=target_idx, columns=hourly_df.columns)
    last_valid = hourly_df.index.max() + pd.Timedelta(hours=1)
    out = hourly_df.reindex(target_idx, method="ffill")
    mask = target_idx >= last_valid
    if mask.any():
        out.loc[mask, :] = np.nan
    return out


def _sum_matching_columns(df: pd.DataFrame, token: str) -> pd.Series:
    cols = [c for c in df.columns if token in c]
    if not cols:
        return pd.Series(np.nan, index=df.index)
    return df[cols].sum(axis=1, min_count=1)


def build_generation_targets(
    generation_by_type: pd.DataFrame,
    target_index: Optional[pd.DatetimeIndex] = None,
) -> pd.DataFrame:
    """Extract gas / solar / wind actual generation targets from ENTSO-E data."""
    targets = pd.DataFrame(index=generation_by_type.index)
    targets["gas_actual_mw"] = _sum_matching_columns(generation_by_type, "fossil_gas")
    targets["solar_actual_mw"] = _sum_matching_columns(generation_by_type, "solar")
    targets["wind_actual_mw"] = _sum_matching_columns(generation_by_type, "wind")
    targets = targets.sort_index()
    if target_index is not None:
        targets = _align_hourly_to_target(targets, target_index)
    return targets


def _safe_pct(numer: pd.Series, denom: pd.Series) -> pd.Series:
    denom = denom.where(denom > 0)
    return (100.0 * numer / denom).clip(lower=0.0, upper=100.0)


@dataclass
class ProductionEstimator:
    """Estimate gas / solar / wind production from forecast-time features."""

    alpha: float = 4.0
    target_names_: tuple = field(
        default=("gas_actual_mw", "solar_actual_mw", "wind_actual_mw"),
        init=False,
        repr=False,
    )
    feature_names_: list = field(default_factory=list, init=False, repr=False)
    models_: dict = field(default_factory=dict, init=False, repr=False)

    @staticmethod
    def candidate_feature_columns(feature_df: pd.DataFrame) -> list[str]:
        """Select forecast-time explanatory columns for supply estimation."""
        allowed_prefixes = (
            "load_",
            "wind_da_",
            "solar_da_",
            "renewables_",
            "residual_",
            "flow_",
            "gen_total_",
            "weather_",
            "gas_ttf_",
            "carbon_eua_",
            "cal_",
        )
        cols = []
        for col in feature_df.columns:
            if col == "dam_price_eur_mwh":
                continue
            if "actual" in col:
                continue
            if "estimated" in col or "dam_share_" in col:
                continue
            if col.startswith(allowed_prefixes):
                cols.append(col)
        return cols

    def fit(
        self,
        feature_df: pd.DataFrame,
        generation_by_type: pd.DataFrame,
    ) -> "ProductionEstimator":
        targets = build_generation_targets(generation_by_type, target_index=feature_df.index)
        self.feature_names_ = self.candidate_feature_columns(feature_df)
        if not self.feature_names_:
            raise ValueError("No eligible feature columns found for production estimation.")

        X = feature_df[self.feature_names_]
        self.models_.clear()
        for target_name in self.target_names_:
            y = targets[target_name]
            mask = y.notna()
            if mask.sum() == 0:
                continue
            pipe = Pipeline(
                [
                    ("impute", SimpleImputer(strategy="median")),
                    ("scale", StandardScaler()),
                    ("ridge", Ridge(alpha=self.alpha, random_state=0)),
                ]
            )
            pipe.fit(X.loc[mask].values, y.loc[mask].values)
            self.models_[target_name] = pipe
        return self

    def predict(self, feature_df: pd.DataFrame) -> pd.DataFrame:
        if not self.models_:
            raise RuntimeError("Call .fit() before .predict().")

        X = feature_df[self.feature_names_]
        out = pd.DataFrame(index=feature_df.index)
        rename = {
            "gas_actual_mw": "gas_estimated_mw",
            "solar_actual_mw": "solar_estimated_mw",
            "wind_actual_mw": "wind_estimated_mw",
        }
        for target_name, model in self.models_.items():
            col = rename[target_name]
            out[col] = np.clip(model.predict(X.values), 0.0, None)

        for col in ("gas_estimated_mw", "solar_estimated_mw", "wind_estimated_mw"):
            if col not in out.columns:
                out[col] = np.nan

        if "gen_total_forecast_mw" in feature_df.columns:
            total = feature_df["gen_total_forecast_mw"].copy()
        else:
            total = out[["gas_estimated_mw", "solar_estimated_mw", "wind_estimated_mw"]].sum(
                axis=1, min_count=1
            )

        known_total = out[["gas_estimated_mw", "solar_estimated_mw", "wind_estimated_mw"]].sum(
            axis=1, min_count=1
        )
        scale = pd.Series(1.0, index=out.index)
        mask = (total > 0) & (known_total > total)
        scale.loc[mask] = total.loc[mask] / known_total.loc[mask]
        for col in ("gas_estimated_mw", "solar_estimated_mw", "wind_estimated_mw"):
            out[col] = out[col] * scale

        denom = total.where(total > 0, known_total)
        out["dam_share_gas_pct"] = _safe_pct(out["gas_estimated_mw"], denom)
        out["dam_share_solar_pct"] = _safe_pct(out["solar_estimated_mw"], denom)
        out["dam_share_wind_pct"] = _safe_pct(out["wind_estimated_mw"], denom)
        return out


def add_estimated_supply_features(
    feature_df: pd.DataFrame, estimated_supply_df: pd.DataFrame
) -> pd.DataFrame:
    """Join estimated production and share features onto a feature matrix."""
    out = feature_df.copy()
    for col in estimated_supply_df.columns:
        out[col] = estimated_supply_df[col].reindex(out.index)
    return out
