"""
ML-based price forecasters.

Three concrete forecasters that consume the feature matrix produced by
`FeatureBuilder` and predict day-ahead prices:

  * `RidgeMLForecaster`     — linear baseline (interpretable, fast)
  * `GBMForecaster`         — LightGBM regression (best accuracy)
  * `QuantileGBMForecaster` — LightGBM quantile regression (P10/P50/P90)

All three implement the same `fit(train_df)` / `predict(test_df)` API.
They expect a DataFrame with `dam_price_eur_mwh` as the target column
and any number of feature columns alongside.

Usage
-----
>>> from helleniflex import FeatureBuilder
>>> builder = FeatureBuilder(prices, load, renewables, flows, gen_total)
>>> df = builder.build()
>>> train, test = builder.split_train_test(df, test_days=30)
>>> model = GBMForecaster()
>>> model.fit(train)
>>> y_pred = model.predict(test)
>>> mae = np.abs(y_pred - test['dam_price_eur_mwh']).mean()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

# All sklearn imports are stdlib for our purposes
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

try:
    import lightgbm as lgb

    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


TARGET_COL = "dam_price_eur_mwh"


def _split_xy(df: pd.DataFrame, drop_na_target: bool = True):
    """Pull X/y out of a feature DataFrame, dropping rows with NaN target."""
    if drop_na_target:
        df = df.dropna(subset=[TARGET_COL])
    y = df[TARGET_COL].values
    X = df.drop(columns=[TARGET_COL])
    return X, y


# ======================================================================
# RIDGE (linear baseline)
# ======================================================================


@dataclass
class RidgeMLForecaster:
    """Linear regression with L2 regularisation. Interpretable baseline.

    Parameters
    ----------
    alpha : float
        L2 regularisation strength. Default 1.0.
    """

    alpha: float = 1.0
    name: str = "Ridge (linear)"
    pipeline_: Optional[Pipeline] = field(default=None, init=False, repr=False)
    feature_names_: list = field(default_factory=list, init=False, repr=False)

    def fit(self, train_df: pd.DataFrame) -> "RidgeMLForecaster":
        X, y = _split_xy(train_df)
        self.feature_names_ = list(X.columns)
        self.pipeline_ = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("ridge", Ridge(alpha=self.alpha, random_state=0)),
            ]
        )
        self.pipeline_.fit(X.values, y)
        return self

    def predict(self, test_df: pd.DataFrame) -> np.ndarray:
        if self.pipeline_ is None:
            raise RuntimeError("Call .fit() first.")
        X = test_df[self.feature_names_]
        return self.pipeline_.predict(X.values)

    def coefficients(self) -> pd.Series:
        """Return standardised coefficients (interpretable feature importance)."""
        if self.pipeline_ is None:
            raise RuntimeError("Call .fit() first.")
        coef = self.pipeline_.named_steps["ridge"].coef_
        return pd.Series(coef, index=self.feature_names_).sort_values(
            key=lambda s: s.abs(), ascending=False
        )


# ======================================================================
# LIGHTGBM (point forecast)
# ======================================================================


@dataclass
class GBMForecaster:
    """Gradient-boosted decision trees via LightGBM.

    Best single-model accuracy for European DAM forecasting in the
    literature. Handles nonlinearities, interactions, missing data
    natively. No scaling/imputation needed.

    Parameters
    ----------
    n_estimators : int
        Number of boosting rounds.
    learning_rate : float
    num_leaves : int
    min_child_samples : int
    """

    n_estimators: int = 500
    learning_rate: float = 0.05
    num_leaves: int = 63
    min_child_samples: int = 20
    name: str = "LightGBM"
    model_: Optional[object] = field(default=None, init=False, repr=False)
    feature_names_: list = field(default_factory=list, init=False, repr=False)

    def fit(self, train_df: pd.DataFrame, valid_df: Optional[pd.DataFrame] = None):
        if not LIGHTGBM_AVAILABLE:
            raise ImportError(
                "lightgbm is not installed. `pip install lightgbm`."
            )
        X, y = _split_xy(train_df)
        self.feature_names_ = list(X.columns)
        params = dict(
            objective="regression",
            metric="mae",
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            num_leaves=self.num_leaves,
            min_child_samples=self.min_child_samples,
            verbose=-1,
            random_state=0,
        )
        self.model_ = lgb.LGBMRegressor(**params)
        if valid_df is not None:
            Xv, yv = _split_xy(valid_df)
            self.model_.fit(
                X.values,
                y,
                eval_set=[(Xv.values, yv)],
                callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)],
            )
        else:
            self.model_.fit(X.values, y)
        return self

    def predict(self, test_df: pd.DataFrame) -> np.ndarray:
        if self.model_ is None:
            raise RuntimeError("Call .fit() first.")
        X = test_df[self.feature_names_]
        return self.model_.predict(X.values)

    def feature_importance(self) -> pd.Series:
        """Native LightGBM gain-based feature importance."""
        if self.model_ is None:
            raise RuntimeError("Call .fit() first.")
        imp = self.model_.booster_.feature_importance(importance_type="gain")
        return pd.Series(imp, index=self.feature_names_).sort_values(
            ascending=False
        )


# ======================================================================
# QUANTILE LIGHTGBM (prediction intervals)
# ======================================================================


@dataclass
class QuantileGBMForecaster:
    """LightGBM with quantile-loss regression at multiple quantiles.

    Fits one model per requested quantile. Default {0.1, 0.5, 0.9} gives
    P10 / P50 / P90 — an 80% prediction interval around the median.

    The optimizer can use these intervals for confidence-aware bidding:
    on high-uncertainty days, charge less aggressively or hold reserve.
    """

    quantiles: tuple = (0.1, 0.5, 0.9)
    n_estimators: int = 500
    learning_rate: float = 0.05
    num_leaves: int = 63
    min_child_samples: int = 20
    name: str = "LightGBM (quantile)"
    models_: dict = field(default_factory=dict, init=False, repr=False)
    feature_names_: list = field(default_factory=list, init=False, repr=False)

    def fit(self, train_df: pd.DataFrame):
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm not installed.")
        X, y = _split_xy(train_df)
        self.feature_names_ = list(X.columns)
        for q in self.quantiles:
            params = dict(
                objective="quantile",
                alpha=q,
                metric="quantile",
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                num_leaves=self.num_leaves,
                min_child_samples=self.min_child_samples,
                verbose=-1,
                random_state=0,
            )
            m = lgb.LGBMRegressor(**params)
            m.fit(X.values, y)
            self.models_[q] = m
        return self

    def predict(self, test_df: pd.DataFrame) -> pd.DataFrame:
        """Return a DataFrame with one column per quantile."""
        if not self.models_:
            raise RuntimeError("Call .fit() first.")
        X = test_df[self.feature_names_]
        out = pd.DataFrame(index=test_df.index)
        for q, m in self.models_.items():
            out[f"q{int(q*100):02d}"] = m.predict(X.values)
        return out

    def predict_median(self, test_df: pd.DataFrame) -> np.ndarray:
        """Convenience: return just the median (P50) point forecast."""
        return self.predict(test_df)["q50"].values


# ======================================================================
# FORECAST DIAGNOSTICS
# ======================================================================


def forecast_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, threshold_spike: float = 200.0
) -> dict:
    """Compute standard regression and trader-specific metrics.

    Parameters
    ----------
    y_true, y_pred : np.ndarray
        Actual and predicted prices, same shape.
    threshold_spike : float
        Price (€/MWh) above which a slot counts as a "spike". Default 200.

    Returns
    -------
    dict with:
        rmse, mae : standard regression error
        mape_positive : MAPE on slots where actual price > €5/MWh
        bias : mean signed error (predicted − actual)
        spike_recall : fraction of true spikes correctly flagged
            (predicted price also above threshold)
        neg_recall : fraction of true negative-price slots correctly flagged
        directional_accuracy : fraction of slots where the sign of the
            forecast change vs previous slot matches the actual change.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    err = y_pred - y_true
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mae = float(np.mean(np.abs(err)))
    bias = float(np.mean(err))

    pos_mask = y_true > 5
    if pos_mask.sum() > 0:
        mape_pos = float(np.mean(np.abs(err[pos_mask]) / y_true[pos_mask]))
    else:
        mape_pos = float("nan")

    spike_mask = y_true > threshold_spike
    if spike_mask.sum() > 0:
        spike_recall = float(((y_pred > threshold_spike) & spike_mask).sum() / spike_mask.sum())
    else:
        spike_recall = float("nan")

    neg_mask = y_true < 0
    if neg_mask.sum() > 0:
        neg_recall = float(((y_pred < 0) & neg_mask).sum() / neg_mask.sum())
    else:
        neg_recall = float("nan")

    if len(y_true) > 1:
        true_diff = np.sign(np.diff(y_true))
        pred_diff = np.sign(np.diff(y_pred))
        directional = float(np.mean(true_diff == pred_diff))
    else:
        directional = float("nan")

    return {
        "rmse_eur_mwh": rmse,
        "mae_eur_mwh": mae,
        "bias_eur_mwh": bias,
        "mape_positive_only": mape_pos,
        "spike_recall_above_200": spike_recall,
        "negative_price_recall": neg_recall,
        "directional_accuracy": directional,
        "n": int(len(y_true)),
    }
