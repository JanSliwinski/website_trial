"""
Live data feeds for HelleniFlex.

Three real-time sources, all no-auth (or optional yfinance):

  1. Open-Meteo   — hourly weather forecast for any delivery date (free, no key)
  2. IPTO/ADMIE   — Greek TSO day-ahead load + RES forecasts (ISP1 Requirements)
  3. TTF gas      — Dutch TTF Natural Gas front-month settlement via yfinance

Each fetch result is cached to a local Parquet store so the model accumulates
history over time. Default store: ~/.helleniflex/live_data/

Typical daily workflow
----------------------
    from helleniflex.live_feeds import LiveDataCollector

    c = LiveDataCollector()
    c.fetch_and_store()                  # fetch everything for tomorrow, save
    inputs = c.build_feature_inputs()    # dict compatible with FeatureBuilder
"""

from __future__ import annotations

import io
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Types & paths
# ---------------------------------------------------------------------------

DateLike = Union[str, date, datetime]

_DEFAULT_DATA_DIR = Path.home() / ".helleniflex" / "live_data"

_OPENMETEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_OPENMETEO_ARCHIVE_URL  = "https://archive-api.open-meteo.com/v1/archive"
_ADMIE_API_URL          = "https://www.admie.gr/getOperationMarketFile"

_OPENMETEO_HOURLY_VARS  = "temperature_2m,shortwave_radiation,wind_speed_10m,cloud_cover"

# Keyword lists for flexible IPTO column detection (match anywhere in lowercase name)
_LOAD_KEYWORDS  = ["load", "φορτ"]
_WIND_KEYWORDS  = ["wind", "αιολ"]
_SOLAR_KEYWORDS = ["solar", "pv", "φ/β", "φωτοβολτ", "photovolt"]

# yfinance tickers tried in order: TTF front-month, Henry Hub proxy
_TTF_TICKERS = ["TTF=F", "NG=F"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _as_date(d: DateLike) -> date:
    if isinstance(d, str):
        return datetime.fromisoformat(d).date()
    if isinstance(d, datetime):
        return d.date()
    return d


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _detect_col(df: pd.DataFrame, keywords: list[str]) -> Optional[str]:
    """Return the first column whose lowercase name contains any keyword."""
    for col in df.columns:
        cl = str(col).lower()
        if any(kw in cl for kw in keywords):
            return col
    return None


# ---------------------------------------------------------------------------
# 1. Open-Meteo weather forecast
# ---------------------------------------------------------------------------

def fetch_openmeteo_forecast(
    target_date: DateLike,
    lat: float = 37.98,
    lon: float = 23.73,
    timezone: str = "Europe/Athens",
) -> pd.DataFrame:
    """Fetch hourly Open-Meteo data for `target_date`.

    Uses the forecast API for near-future/recent dates (within the 16-day
    forecast window) and the archive API for older historical dates.

    Parameters
    ----------
    target_date : date-like
        Delivery date to retrieve weather for.
    lat, lon : float
        Coordinates. Default: Athens city centre.
    timezone : str
        IANA timezone. Must match the market's local time (Europe/Athens).

    Returns
    -------
    pd.DataFrame
        Hourly, datetime-indexed, with columns:
        temperature_2m, shortwave_radiation, wind_speed_10m, cloud_cover
    """
    try:
        import requests
    except ImportError:
        raise ImportError(
            "requests is required for live feeds — "
            "run: pip install helleniflex[live]"
        )

    target = _as_date(target_date)
    today  = date.today()

    # Archive API covers up to ~5 days ago; forecast API covers today + 16 days
    use_archive = (today - target).days > 5
    url = _OPENMETEO_ARCHIVE_URL if use_archive else _OPENMETEO_FORECAST_URL

    resp = requests.get(
        url,
        params={
            "latitude":   lat,
            "longitude":  lon,
            "hourly":     _OPENMETEO_HOURLY_VARS,
            "start_date": str(target),
            "end_date":   str(target),
            "timezone":   timezone,
        },
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()

    hourly = payload.get("hourly", {})
    if not hourly or "time" not in hourly:
        raise ValueError(f"Open-Meteo returned empty hourly data for {target}")

    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    df.index.name = None
    return df.rename(columns={"cloud_cover": "cloud_cover"})  # identity; documents expected cols


# ---------------------------------------------------------------------------
# 2. IPTO / ADMIE — ISP1 Requirements
# ---------------------------------------------------------------------------

def fetch_ipto_forecasts(target_date: DateLike) -> pd.DataFrame:
    """Fetch IPTO (ADMIE) day-ahead load and RES forecasts.

    Calls the ADMIE REST API to discover the ISP1Requirements Excel for
    `target_date`, downloads it, and returns a 96-row 15-min DataFrame.

    The ISP1 Excel is a pivoted table: rows = data categories, columns =
    15-min time slots (00:00 … 23:45). We extract the "Greece" aggregate
    rows for load and total RES and transpose them into a tidy time series.

    ADMIE publishes the ISP1 file for delivery day D on day D-1 ~13:00-18:00.

    Returns
    -------
    pd.DataFrame
        96-row, datetime-indexed (Europe/Athens), columns:
            load_forecast_mw   — non-dispatchable load forecast
            res_da_forecast_mw — total non-dispatchable RES forecast
    """
    try:
        import requests
    except ImportError:
        raise ImportError(
            "requests is required for live feeds — "
            "run: pip install helleniflex[live]"
        )

    target   = _as_date(target_date)
    date_str = target.strftime("%Y-%m-%d")

    # ── Step 1: get file list from ADMIE REST API ─────────────────────────
    # Response is a plain JSON list (not wrapped in {"Result": ...})
    r = requests.get(
        _ADMIE_API_URL,
        params={
            "FileCategory": "ISP1Requirements",
            "StartDate":    date_str,
            "EndDate":      date_str,
        },
        timeout=20,
    )
    r.raise_for_status()
    result = r.json()
    if not isinstance(result, list) or not result:
        raise ValueError(
            f"ADMIE API returned no ISP1Requirements files for {date_str}. "
            "The file may not yet be published (published ~13:00-18:00 on D-1)."
        )

    # Pick latest version (file_path ends with _NN.xlsx; highest NN = latest)
    entry     = sorted(result, key=lambda x: x.get("file_path", ""))[-1]
    file_url  = entry.get("file_path", "")
    if not file_url:
        raise ValueError(f"ADMIE API entry has no file_path: {entry}")
    # file_path is already a full URL in the real response
    if not file_url.startswith("http"):
        file_url = "https://www.admie.gr" + (
            file_url if file_url.startswith("/") else "/" + file_url
        )

    # ── Step 2: download ──────────────────────────────────────────────────
    r2 = requests.get(file_url, timeout=30)
    r2.raise_for_status()
    raw_bytes = io.BytesIO(r2.content)

    # ── Step 3: load sheet (name pattern: YYYYMMDD_ISP1) ─────────────────
    import warnings as _warnings
    raw_bytes.seek(0)
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")   # suppress openpyxl style warnings
        xf = pd.ExcelFile(raw_bytes)
    sheet = xf.sheet_names[0]              # always one sheet in ISP1 files

    raw_bytes.seek(0)
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        raw = pd.read_excel(raw_bytes, sheet_name=sheet, header=None)

    # ── Step 4: locate the 96 time-slot columns ───────────────────────────
    # The pivot layout: col 0 = category label, col 1 = geography,
    # cols 2..97 = values for 00:00, 00:15, …, 23:45, col 98 = daily total.
    # Time labels appear in "header" rows where col[0] is a section title
    # (e.g. "RES Forecast") and col[2] == "00:00".
    time_col_start = 2   # fixed by ADMIE's layout
    n_slots        = 96

    # Build the datetime index: target_date 00:00 … 23:45 (Athens local)
    ts_index = pd.date_range(
        start=str(target),
        periods=n_slots,
        freq="15min",
        tz="Europe/Athens",
    )

    # ── Step 5: extract rows by label keywords ────────────────────────────
    # Row matching: column 0 contains the category name (English or Greek)
    labels = raw.iloc[:, 0].astype(str).str.strip()
    geo    = raw.iloc[:, 1].astype(str).str.strip()

    def _extract_row(row_keywords: list[str], geo_keyword: str = "Greece") -> Optional[np.ndarray]:
        """Return the 96-value array from the first matching row."""
        for i, lbl in enumerate(labels):
            lbl_l = str(lbl).lower()
            if any(kw.lower() in lbl_l for kw in row_keywords):
                if geo_keyword.lower() in str(geo.iloc[i]).lower():
                    vals = pd.to_numeric(
                        raw.iloc[i, time_col_start : time_col_start + n_slots],
                        errors="coerce",
                    )
                    if vals.notna().sum() > n_slots // 2:
                        return vals.values
        return None

    # "Non-Dispatcheble Load" (ADMIE typo preserved) + Greece
    load_vals = _extract_row(
        ["non-dispatchable load", "non-dispatcheble load", "φορτ"],
    )
    # "Non-Dispatchable RES" + Greece = total non-dispatchable RES
    res_vals = _extract_row(
        ["non-dispatchable res", "non-dispatcheble res"],
    )
    if res_vals is None:
        # Older files: "Total System" row under the RES Forecast section has NaN geo
        res_vals = _extract_row(["total system"], geo_keyword="nan")

    if load_vals is None and res_vals is None:
        raise ValueError(
            f"Could not identify load or RES rows in IPTO ISP1 file {file_url}. "
            f"Row labels found: {labels[labels != 'nan'].unique()[:20].tolist()}"
        )

    # ── Step 6: assemble tidy output ─────────────────────────────────────
    out = pd.DataFrame(index=ts_index)
    out.index.name = None
    if load_vals is not None:
        out["load_forecast_mw"] = load_vals
    if res_vals is not None:
        out["res_da_forecast_mw"] = res_vals

    return out


# ---------------------------------------------------------------------------
# 3. TTF gas futures
# ---------------------------------------------------------------------------

def fetch_ttf_price(target_date: DateLike) -> Optional[float]:
    """Fetch Dutch TTF Natural Gas front-month settlement price.

    Uses yfinance to obtain the most recent settlement on or before
    `target_date`. Tries 'TTF=F' first (European TTF on Yahoo Finance),
    then 'NG=F' (NYMEX Henry Hub) as a correlated proxy.

    Returns the close price in the ticker's native unit:
      - TTF=F → EUR/MWh (ICE)
      - NG=F  → USD/MMBtu (NYMEX; use as a directional proxy only)

    Returns None if yfinance is not installed or no data is available.

    Install yfinance separately:
        pip install yfinance
    """
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        warnings.warn(
            "yfinance is not installed — TTF price unavailable. "
            "Install with: pip install yfinance",
            stacklevel=2,
        )
        return None

    target = _as_date(target_date)
    start  = target - timedelta(days=7)

    for ticker in _TTF_TICKERS:
        try:
            hist = yf.download(
                ticker,
                start=str(start),
                end=str(target + timedelta(days=1)),
                progress=False,
                auto_adjust=True,
            )
            if hist.empty:
                continue
            # Keep only rows up to and including target_date
            close_col = "Close"
            if hasattr(hist.index, "date"):
                mask = hist.index.date <= target
            else:
                mask = hist.index <= pd.Timestamp(target)
            hist = hist[mask]
            if hist.empty:
                continue
            val = hist[close_col].iloc[-1]
            # yfinance MultiIndex workaround: col may be (Close, ticker)
            if hasattr(val, "__len__"):
                val = float(val.iloc[0])
            return float(val)
        except Exception:
            continue

    warnings.warn(
        f"Could not retrieve TTF/gas price for {target} from any ticker.",
        stacklevel=2,
    )
    return None


# ---------------------------------------------------------------------------
# LiveDataCollector — orchestrator with Parquet cache
# ---------------------------------------------------------------------------

class LiveDataCollector:
    """Fetch live data, cache it locally, and expose historical series.

    Storage layout under `data_dir`:
        openmeteo/YYYY-MM-DD.parquet   — hourly weather forecast per day
        ipto/YYYY-MM-DD.parquet        — 15-min IPTO ISP1 forecasts per day
        ttf/history.parquet            — daily TTF close prices (cumulative)

    Parameters
    ----------
    data_dir : str or Path, optional
        Root of the Parquet cache. Default: ``~/.helleniflex/live_data``.
    lat, lon : float
        Grid point for Open-Meteo. Default: Athens (37.98, 23.73).

    Examples
    --------
    >>> c = LiveDataCollector()
    >>> c.fetch_and_store()                   # fetch for tomorrow, cache
    >>> c.fetch_and_store("2026-05-01")       # fetch a specific date
    >>> weather = c.load_openmeteo_history()  # all cached Open-Meteo data
    >>> inputs  = c.build_feature_inputs()    # dict for FeatureBuilder
    """

    def __init__(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        lat: float = 37.98,
        lon: float = 23.73,
    ):
        self.data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        self.lat  = lat
        self.lon  = lon
        for sub in ("openmeteo", "ipto", "ttf"):
            _ensure_dir(self.data_dir / sub)

    # ── path helpers ──────────────────────────────────────────────────────

    def _openmeteo_path(self, d: date) -> Path:
        return self.data_dir / "openmeteo" / f"{d}.parquet"

    def _ipto_path(self, d: date) -> Path:
        return self.data_dir / "ipto" / f"{d}.parquet"

    def _ttf_history_path(self) -> Path:
        return self.data_dir / "ttf" / "history.parquet"

    # ── individual fetch-and-store methods ────────────────────────────────

    def fetch_and_store_openmeteo(
        self,
        target_date: DateLike,
        force_refresh: bool = False,
    ) -> Optional[pd.DataFrame]:
        """Fetch Open-Meteo forecast for `target_date` and persist to cache.

        Skips the network call if the Parquet file already exists and
        `force_refresh` is False.
        """
        d    = _as_date(target_date)
        path = self._openmeteo_path(d)
        if path.exists() and not force_refresh:
            return pd.read_parquet(path)
        try:
            df = fetch_openmeteo_forecast(d, lat=self.lat, lon=self.lon)
            df.to_parquet(path)
            print(f"  [openmeteo] {d}: {len(df)} rows saved → {path}")
            return df
        except Exception as exc:
            warnings.warn(f"Open-Meteo fetch failed for {d}: {exc}", stacklevel=2)
            return None

    def fetch_and_store_ipto(
        self,
        target_date: DateLike,
        force_refresh: bool = False,
    ) -> Optional[pd.DataFrame]:
        """Fetch IPTO ISP1 forecasts for `target_date` and persist to cache.

        Note: IPTO publishes the ISP1 for delivery day D around 18:00 on D-1.
        Calling this before publication will raise a ValueError.
        """
        d    = _as_date(target_date)
        path = self._ipto_path(d)
        if path.exists() and not force_refresh:
            return pd.read_parquet(path)
        try:
            df = fetch_ipto_forecasts(d)
            df.to_parquet(path)
            print(f"  [ipto]      {d}: {len(df)} rows saved → {path}")
            return df
        except Exception as exc:
            warnings.warn(f"IPTO fetch failed for {d}: {exc}", stacklevel=2)
            return None

    def fetch_and_store_ttf(
        self,
        target_date: DateLike,
        force_refresh: bool = False,
    ) -> Optional[float]:
        """Fetch TTF settlement price for `target_date` and append to history.

        The TTF price for day D is the settlement price of the front-month
        contract on day D-1 (the last trading day before delivery).
        In practice `target_date` is D-1 to capture the pre-DAM price signal.
        """
        d         = _as_date(target_date)
        hist_path = self._ttf_history_path()

        if hist_path.exists():
            hist_df = pd.read_parquet(hist_path)
        else:
            hist_df = pd.DataFrame(columns=["ttf_close"])

        d_ts = pd.Timestamp(d)
        if d_ts in hist_df.index and not force_refresh:
            return float(hist_df.loc[d_ts, "ttf_close"])

        price = fetch_ttf_price(d)
        if price is not None:
            new_row = pd.DataFrame({"ttf_close": [price]}, index=[d_ts])
            hist_df = pd.concat([hist_df, new_row]).sort_index()
            hist_df = hist_df[~hist_df.index.duplicated(keep="last")]
            hist_df.to_parquet(hist_path)
            print(f"  [ttf]       {d}: {price:.2f} saved → {hist_path}")
        return price

    # ── main daily entrypoint ─────────────────────────────────────────────

    def fetch_and_store(
        self,
        target_date: Optional[DateLike] = None,
        force_refresh: bool = False,
    ) -> dict:
        """Fetch all three sources for `target_date` and persist to disk.

        Parameters
        ----------
        target_date : date-like, optional
            Delivery day to fetch data for. Defaults to *tomorrow*.
        force_refresh : bool
            If True, re-fetch even if cached data exists.

        Returns
        -------
        dict
            ``{"openmeteo": DataFrame|None, "ipto": DataFrame|None,
               "ttf": float|None}``
        """
        if target_date is None:
            target_date = date.today() + timedelta(days=1)

        d = _as_date(target_date)
        print(f"Fetching live data for delivery day {d} ...")

        return {
            "openmeteo": self.fetch_and_store_openmeteo(d, force_refresh=force_refresh),
            "ipto":      self.fetch_and_store_ipto(d, force_refresh=force_refresh),
            "ttf":       self.fetch_and_store_ttf(d, force_refresh=force_refresh),
        }

    # ── history loaders ───────────────────────────────────────────────────

    def load_openmeteo_history(self) -> pd.DataFrame:
        """Return all cached Open-Meteo rows, sorted chronologically."""
        pieces = []
        for p in sorted((self.data_dir / "openmeteo").glob("*.parquet")):
            try:
                pieces.append(pd.read_parquet(p))
            except Exception as exc:
                warnings.warn(f"Could not read {p.name}: {exc}", stacklevel=2)
        if not pieces:
            return pd.DataFrame()
        out = pd.concat(pieces).sort_index()
        return out[~out.index.duplicated(keep="first")]

    def load_ipto_history(self) -> pd.DataFrame:
        """Return all cached IPTO forecasts, sorted chronologically."""
        pieces = []
        for p in sorted((self.data_dir / "ipto").glob("*.parquet")):
            try:
                pieces.append(pd.read_parquet(p))
            except Exception as exc:
                warnings.warn(f"Could not read {p.name}: {exc}", stacklevel=2)
        if not pieces:
            return pd.DataFrame()
        out = pd.concat(pieces).sort_index()
        return out[~out.index.duplicated(keep="first")]

    def load_ttf_history(self) -> pd.Series:
        """Return cached TTF daily close prices as a Series (index = datetime)."""
        path = self._ttf_history_path()
        if not path.exists():
            return pd.Series(dtype=float, name="ttf_close")
        df = pd.read_parquet(path)
        return df["ttf_close"].sort_index()

    # ── FeatureBuilder-compatible dict ────────────────────────────────────

    def build_feature_inputs(self) -> dict:
        """Return a dict of DataFrames ready to pass to FeatureBuilder.

        The keys and DataFrame shapes match FeatureBuilder's constructor
        parameters. Pass the dict as keyword arguments:

            fb = FeatureBuilder(prices=prices, **collector.build_feature_inputs())

        Returns
        -------
        dict with keys:
            "load"       → pd.DataFrame with load_forecast_mw column,
                           or None if no IPTO data is cached yet.
            "renewables" → pd.DataFrame with wind_da_forecast_mw and/or
                           solar_da_forecast_mw, or None.
            "weather"    → pd.DataFrame from Open-Meteo (hourly), or None.
            "ttf"        → pd.Series of daily TTF close prices, or None.
        """
        ipto    = self.load_ipto_history()
        weather = self.load_openmeteo_history()
        ttf     = self.load_ttf_history()

        # Split IPTO into load and renewables DataFrames
        load_df = ren_df = None

        if not ipto.empty:
            load_cols = [c for c in ipto.columns if "load" in c.lower()]
            ren_cols  = [
                c for c in ipto.columns
                if any(kw in c.lower() for kw in ["wind", "solar", "pv"])
            ]
            if load_cols:
                load_df = ipto[load_cols].copy()
                # Ensure the canonical column name
                if load_cols[0] != "load_forecast_mw":
                    load_df = load_df.rename(columns={load_cols[0]: "load_forecast_mw"})
            if ren_cols:
                ren_df = ipto[ren_cols].copy()

        return {
            "load":       load_df,
            "renewables": ren_df,
            "weather":    weather if not weather.empty else None,
            "ttf":        ttf     if not ttf.empty     else None,
        }
