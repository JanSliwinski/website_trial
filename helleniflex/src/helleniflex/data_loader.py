"""
Data loaders, API helpers, and synthetic data generators.

The framework is data-source-agnostic: any pd.Series of €/MWh prices
indexed by datetime works. This module ships:

* `make_synthetic_greek_dam_prices` — realistic-looking Greek DAM
  prices, calibrated against publicly observed 2024–2025 patterns.
  Useful for the demo and for unit tests; runs offline.

* `load_csv_prices` — generic CSV loader with sensible defaults.

* Live/API helpers for:
  - Open-Meteo historical weather (`fetch_openmeteo_weather`)
  - Open-Meteo forward weather forecast (`fetch_openmeteo_forecast`)
  - Generic daily external series from CSV files (`load_daily_series_csv`)
  - Generic CSV downloads from a vendor/API URL (`fetch_daily_series_csv_url`)

  In practice this lets the project combine:
  - historical actual prices from HEnEx / ENTSO-E
  - day-ahead load / RES / total-generation forecasts from ENTSO-E
  - tomorrow's weather forecast from Open-Meteo
  - daily market drivers such as TTF gas and EUA carbon from external feeds
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Synthetic Greek DAM prices
# ----------------------------------------------------------------------

def make_synthetic_greek_dam_prices(
    start: str = "2024-01-01",
    end: str = "2025-12-31",
    freq: str = "15min",
    seed: int = 42,
) -> pd.Series:
    """Generate synthetic Greek DAM prices that capture the qualitative
    features of the real market:

      * strong daily shape: morning ramp, midday solar dip, evening peak
      * day-of-week seasonality (weekends softer)
      * seasonal level (winter > summer evening peak; summer midday dips
        deeper because of solar)
      * occasional negative-price 15-min slots in spring/summer noon
      * gas-price-like slow drift

    Calibrated so daily price spreads average ~€80/MWh — comparable to
    observed Greek DAM in 2024–2025. Use this for demos and offline
    development; replace with real data via `load_csv_prices` for the
    final backtest.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start=start, end=end, freq=freq)
    n = len(idx)

    hours = np.asarray(idx.hour + idx.minute / 60.0, dtype=float)
    dow = np.asarray(idx.dayofweek, dtype=int)
    doy = np.asarray(idx.dayofyear, dtype=float)
    is_weekend = (dow >= 5).astype(float)

    # ---- Daily shape (two peaks: morning ~08:00 and evening ~20:00) ----
    morning = 30 * np.exp(-((hours - 8) ** 2) / 4)
    evening = 60 * np.exp(-((hours - 20) ** 2) / 5)
    midday_solar_dip = -45 * np.exp(-((hours - 13) ** 2) / 6)
    daily_shape = morning + evening + midday_solar_dip

    # ---- Seasonal modulation ----
    # Winter: stronger evening peak; Summer: deeper midday dip
    season = np.cos(2 * np.pi * (doy - 15) / 365)  # +1 in mid-January, -1 in mid-July
    seasonal_level = 25 * season + 110              # mean varies 85–135 €/MWh
    summer_dip_amp = 1.0 + 0.6 * (-season).clip(min=0)  # deeper midday dips in summer
    daily_shape = (
        morning + evening * (1.0 + 0.3 * season.clip(min=0))
        + midday_solar_dip * summer_dip_amp
    )

    # ---- Weekend softening ----
    weekend_factor = 1.0 - 0.15 * is_weekend

    # ---- Slow gas-price-like drift ----
    drift = 15 * np.sin(2 * np.pi * doy / 365 * 1.3 + 0.5) \
        + 5 * np.sin(2 * np.pi * np.arange(n) / (96 * 30) + 1.7)

    # ---- Noise ----
    noise = rng.normal(0, 8, n) + rng.normal(0, 25, n) * (rng.random(n) > 0.97)

    prices = (seasonal_level + daily_shape) * weekend_factor + drift + noise

    # ---- Inject occasional negative-price 15-min slots near solar peak in spring/summer ----
    spring_summer_mask = (idx.month >= 3) & (idx.month <= 9)
    midday_mask = (hours >= 12) & (hours <= 15)
    candidate = spring_summer_mask & midday_mask
    flip = rng.random(n) < 0.05  # 5% of candidate slots
    neg_mask = candidate & flip
    prices[neg_mask] = rng.uniform(-30, -2, neg_mask.sum())

    # Light clipping (Greek DAM cap is +/-4000 but this is well within)
    prices = np.clip(prices, -50, 400)

    return pd.Series(prices, index=idx, name="dam_price_eur_mwh")


# ----------------------------------------------------------------------
# CSV loader
# ----------------------------------------------------------------------

def load_csv_prices(
    path: str,
    timestamp_col: str = "timestamp",
    price_col: str = "price_eur_mwh",
    tz: Optional[str] = None,
) -> pd.Series:
    """Load a CSV of DAM prices into a datetime-indexed Series.

    Expects two columns: a timestamp and a price. Pass column names as
    needed. Resamples to a uniform grid (assumed already uniform in
    most exports — this is just a safety check).
    """
    df = pd.read_csv(path)
    ts = pd.to_datetime(df[timestamp_col])
    if tz:
        ts = ts.dt.tz_localize(tz, nonexistent="shift_forward", ambiguous="NaT")
    s = pd.Series(df[price_col].values, index=ts, name="dam_price_eur_mwh")
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="first")]
    return s


def load_daily_series_csv(
    path: str,
    date_col: Optional[str] = None,
    value_col: Optional[str] = None,
    name: Optional[str] = None,
) -> pd.Series:
    """Load a daily external time series from CSV.

    This is the normal path for market drivers such as:
      * TTF front-month gas settlement (EUR/MWh)
      * EUA carbon settlement (EUR/t)
      * fuel indices or other daily explanatory variables

    The file may be in either of these simple forms:

    1. implicit date index
        ,ttf_eur_per_mwh
        2026-04-28,31.4
        2026-04-29,31.9

    2. explicit date column
        date,ttf_eur_per_mwh
        2026-04-28,31.4
        2026-04-29,31.9
    """
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"{path} is empty.")

    cols = list(df.columns)
    if date_col is None:
        date_col = cols[0]
    if value_col is None:
        candidates = [c for c in cols if c != date_col]
        if not candidates:
            raise ValueError(
                f"Could not infer value column in {path}. "
                "Pass `value_col=` explicitly."
            )
        value_col = candidates[0]

    idx = pd.to_datetime(df[date_col]).dt.normalize()
    values = pd.to_numeric(df[value_col], errors="coerce")
    series = pd.Series(values.values, index=idx, name=name or value_col)
    series = series.sort_index()
    series = series[~series.index.duplicated(keep="last")]
    return series


def fetch_daily_series_csv_url(
    url: str,
    date_col: str,
    value_col: str,
    headers: Optional[dict] = None,
    name: Optional[str] = None,
) -> pd.Series:
    """Fetch a daily external market series from a vendor-provided CSV URL.

    This is intentionally generic because vendor schemas differ. It is the
    cleanest way to plug a licensed ICE / broker / data-vendor CSV export
    into the existing forecasting pipeline without hard-coding a single
    provider.

    Example
    -------
    >>> ttf = fetch_daily_series_csv_url(
    ...     url=os.environ["HELLENIFLEX_TTF_CSV_URL"],
    ...     date_col="Business Date",
    ...     value_col="Settlement Price",
    ...     headers={"Authorization": f"Bearer {token}"},
    ...     name="ttf_eur_per_mwh",
    ... )
    """
    import io
    import urllib.request

    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(raw))
    idx = pd.to_datetime(df[date_col]).dt.normalize()
    values = pd.to_numeric(df[value_col], errors="coerce")
    series = pd.Series(values.values, index=idx, name=name or value_col)
    series = series.sort_index()
    series = series[~series.index.duplicated(keep="last")]
    return series


def _fetch_json(url: str) -> object:
    import json
    import urllib.request

    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def _json_records_to_frame(payload: object) -> pd.DataFrame:
    """Best-effort conversion of a JSON payload into a tabular DataFrame."""
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        for key in ("data", "items", "files", "results"):
            if key in payload and isinstance(payload[key], list):
                return pd.DataFrame(payload[key])
        return pd.DataFrame([payload])
    return pd.DataFrame({"value": [payload]})


def fetch_admie_filetypes(language: str = "EN") -> pd.DataFrame:
    """Fetch available ADMIE file categories from the public JSON service.

    ADMIE documents the endpoint family here:
    https://www.admie.gr/en/market/market-statistics/file-download-api

    Valid values include:
      * `EN` -> https://www.admie.gr/getFiletypeInfoEN
      * `GR` -> https://www.admie.gr/getFiletypeInfoGR
      * `ALL` -> https://www.admie.gr/getFiletypeInfo
    """
    lang = language.upper()
    endpoint = {
        "EN": "https://www.admie.gr/getFiletypeInfoEN",
        "GR": "https://www.admie.gr/getFiletypeInfoGR",
        "ALL": "https://www.admie.gr/getFiletypeInfo",
    }.get(lang)
    if endpoint is None:
        raise ValueError("language must be one of {'EN', 'GR', 'ALL'}.")
    return _json_records_to_frame(_fetch_json(endpoint))


def fetch_admie_market_file_index(
    file_category: str,
    date_start: str,
    date_end: str,
    overlap: bool = False,
) -> pd.DataFrame:
    """Fetch ADMIE market-file metadata for a file category and date window.

    Parameters
    ----------
    file_category : str
        ADMIE file type such as `ISP2DayAheadLoadForecast`,
        `ISP1DayAheadRESForecast`, or `ISPWeekAheadLoadForecast`.
    date_start, date_end : str
        Dates in YYYY-MM-DD format.
    overlap : bool
        If False, match files whose coverage period exactly equals the
        provided dates. If True, match files whose coverage window partially
        or fully overlaps the provided range.
    """
    import urllib.parse

    base = (
        "https://www.admie.gr/getOperationMarketFilewRange"
        if overlap
        else "https://www.admie.gr/getOperationMarketFile"
    )
    params = urllib.parse.urlencode(
        {
            "dateStart": date_start,
            "dateEnd": date_end,
            "FileCategory": file_category,
        }
    )
    return _json_records_to_frame(_fetch_json(f"{base}?{params}"))


def download_admie_file(url: str) -> bytes:
    """Download a file referenced by the ADMIE market-file API."""
    import urllib.request

    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def load_admie_excel_url(url: str, sheet_name=0, **kwargs) -> pd.DataFrame:
    """Load an ADMIE Excel workbook directly from URL into a DataFrame."""
    import io

    raw = download_admie_file(url)
    return pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name, **kwargs)


def load_admie_96_forecast_url(
    url: str,
    name: str,
    sheet_name=0,
) -> pd.Series:
    """Parse an ADMIE 96-slot forecast workbook from URL.

    This handles the compact ADMIE forecast files such as:
      * `ISP1DayAheadLoadForecast`
      * `ISP2DayAheadLoadForecast`
      * `ISP1DayAheadRESForecast`
      * `ISP2DayAheadRESForecast`

    Observed shape:
      * one worksheet
      * the first row contains slot labels 1..96
      * the second row contains the forecast date and 96 forecast values

    Returns
    -------
    pd.Series
        96 fifteen-minute values indexed by local naive timestamps.
    """
    raw = load_admie_excel_url(url, sheet_name=sheet_name, header=None)
    rows = raw.dropna(how="all")
    if rows.empty:
        raise ValueError(f"ADMIE workbook is empty: {url}")

    value_row = None
    delivery_date = None
    for _, row in rows.iterrows():
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            date_cells = pd.to_datetime(row, errors="coerce")
        date_cells = date_cells[
            date_cells.notna()
            & (date_cells.dt.year >= 2000)
            & (date_cells.dt.year <= 2100)
        ]
        if date_cells.notna().any():
            numeric = pd.to_numeric(row, errors="coerce")
            # Forecast rows have at least the 96 quarter-hour values.
            if numeric.notna().sum() >= 90:
                value_row = numeric.dropna()
                delivery_date = date_cells[date_cells.notna()].iloc[0].normalize()
                break

    if value_row is None or delivery_date is None:
        raise ValueError(f"Could not find a 96-slot forecast row in {url}")

    values = value_row.tail(96).astype(float).values
    if len(values) != 96:
        raise ValueError(f"Expected 96 forecast slots in {url}, found {len(values)}")

    idx = pd.date_range(
        start=delivery_date,
        end=delivery_date + pd.Timedelta(days=1) - pd.Timedelta(minutes=15),
        freq="15min",
    )
    return pd.Series(values, index=idx, name=name)


# ----------------------------------------------------------------------
# Live API stubs (document where to plug in real calls)
# ----------------------------------------------------------------------

def load_henex_dam_file(path: str) -> pd.Series:
    """Parse a single HEnEx EL-DAM-Results Excel file.

    HEnEx publishes one Excel per delivery day at
    https://www.enexgroup.gr/en/markets-publications-el-day-ahead-market

    File naming convention: `YYYYMMDD_EL-DAM_Results_EN_v01.xlsx`
    Sheet name: `EL-DAM_Results`

    The file contains 1,500-1,700 rows covering all bidding-zone segments
    (LOAD, SUPPLY, exports, imports, storage). The Market Clearing Price
    (MCP) column is identical across every segment within a given
    DELIVERY_MTU — it is the single price at which the day-ahead auction
    cleared. We extract one canonical 96-row slice (LOAD/HV) and return
    just the price series.

    Parameters
    ----------
    path : str
        Path to the HEnEx daily Excel file.

    Returns
    -------
    pd.Series
        96 fifteen-minute prices in €/MWh, indexed by datetime
        (Europe/Athens local time).
    """
    df = pd.read_excel(path, sheet_name="EL-DAM_Results")
    canonical = df[
        (df["ASSET_DESCR"] == "LOAD") & (df["CLASSIFICATION"] == "HV")
    ].sort_values("DELIVERY_MTU")
    if len(canonical) == 0:
        # Some days may not have the LOAD/HV row — fall back to the first
        # full 96-row segment available.
        for (asset, side, classif), group in df.groupby(
            ["ASSET_DESCR", "SIDE_DESCR", "CLASSIFICATION"]
        ):
            if len(group) == 96:
                canonical = group.sort_values("DELIVERY_MTU")
                break
    if len(canonical) == 0:
        raise ValueError(
            f"No 96-row canonical segment found in {path}. "
            "File may be incomplete or use a different schema."
        )
    ts = pd.to_datetime(canonical["DELIVERY_MTU"])
    series = pd.Series(
        canonical["MCP"].values, index=ts, name="dam_price_eur_mwh"
    )
    return series


def load_henex_dam_directory(directory: str) -> pd.Series:
    """Concatenate every HEnEx daily Excel in a directory into one series.

    Walks `directory` for files matching `*EL-DAM_Results*.xlsx`, parses
    each via `load_henex_dam_file`, and returns the concatenated
    chronological price series.

    Parameters
    ----------
    directory : str
        Folder containing the daily HEnEx Excels.

    Returns
    -------
    pd.Series
        Concatenated prices indexed by datetime.
    """
    import glob
    import os

    pattern = os.path.join(directory, "*EL-DAM_Results*.xlsx")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"No HEnEx files matching '*EL-DAM_Results*.xlsx' in {directory}"
        )
    pieces = []
    for f in files:
        try:
            pieces.append(load_henex_dam_file(f))
        except Exception as e:
            print(f"  warning: skipped {os.path.basename(f)} ({e})")
    if not pieces:
        raise ValueError("No files could be parsed.")
    series = pd.concat(pieces).sort_index()
    series = series[~series.index.duplicated(keep="first")]
    series.name = "dam_price_eur_mwh"
    return series


# Back-compat alias for the original stub name
def fetch_henex_dam(start: str = None, end: str = None, directory: str = None) -> pd.Series:
    """Backwards-compatible wrapper. Pass `directory` (folder of Excels) or
    use the more explicit `load_henex_dam_file` / `load_henex_dam_directory`.
    """
    if directory is None:
        raise ValueError(
            "fetch_henex_dam now expects a `directory` argument pointing "
            "to a folder of HEnEx daily Excel files. "
            "For a single file, use `load_henex_dam_file(path)` instead."
        )
    series = load_henex_dam_directory(directory)
    if start is not None:
        series = series[series.index >= pd.Timestamp(start)]
    if end is not None:
        series = series[series.index <= pd.Timestamp(end)]
    return series


def _read_entsoe_csv(path: str) -> pd.DataFrame:
    """Read an ENTSO-E CSV, auto-handling both standard and double-quoted exports.

    The Transparency Platform produces two CSV variants depending on
    which UI flow you used:

    Standard (most common):
        "MTU (CET/CEST)","Area","Day-ahead Price (EUR/MWh)",...
        "01/01/2026 00:00:00 - 01/01/2026 00:15:00","BZN|GR","104.05",...

    Double-quoted (some 2025 exports):
        "MTU (CET/CEST),""Area"",""Day-ahead Price (EUR/MWh)"",..."
        "01/01/2025 00:00:00 - 01/01/2025 00:15:00,""BZN|GR"",""138.70"",..."

    In the second variant each line is itself wrapped in a single pair
    of outer quotes, with the inner quotes escaped as `""`. Pandas
    cannot parse this directly. We detect the variant and unwrap before
    parsing.
    """
    import io

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    first_line = raw.split("\n", 1)[0].strip()

    # Heuristic: if the header line contains the escape sequence `""` (a
    # double-quote escaped inside double-quotes), it's the wrapped variant.
    if '""' in first_line:
        fixed = "\n".join(
            line[1:-1].replace('""', '"')
            if line.startswith('"') and line.endswith('"')
            else line
            for line in raw.splitlines()
        )
        return pd.read_csv(io.StringIO(fixed))

    return pd.read_csv(path)


def _parse_mtu_start(mtu_strings: pd.Series) -> pd.DatetimeIndex:
    """Robust parser for ENTSO-E MTU interval strings.

    Handles all observed real-world formats:
      • "29/04/2026 00:00:00 - 29/04/2026 00:15:00"  (with seconds)
      • "29/04/2026 00:00 - 29/04/2026 00:15"  (no seconds)
      • "29/03/2026 01:45:00 (CET) - 29/03/2026 03:00:00 (CEST)"  (DST boundary)

    The DST suffixes appear on the spring-forward and fall-back days and
    must be stripped before parsing — pandas does not understand them.
    Returns the START timestamp of each interval as a tz-naive datetime
    (we keep CET/CEST local wall-clock time, which is what the prices
    actually clear on).
    """
    import re
    cleaned = mtu_strings.astype(str).str.replace(
        r"\s*\((?:CET|CEST)\)", "", regex=True
    )
    starts = cleaned.str.split(" - ").str[0].str.strip()
    # Try with seconds, fall back to without
    try:
        return pd.to_datetime(starts, format="%d/%m/%Y %H:%M:%S")
    except ValueError:
        return pd.to_datetime(starts, format="%d/%m/%Y %H:%M")


def load_entsoe_prices_csv(path: str) -> pd.Series:
    """Parse an ENTSO-E Transparency 'Energy Prices' CSV web export.

    These files are downloaded from the Transparency Platform UI and have
    the canonical name pattern `GUI_ENERGY_PRICES_<from>-<to>.csv`. They
    contain the day-ahead price for one or more days at 15-min resolution
    for the requested bidding zone.

    Expected schema:
        "MTU (CET/CEST)", "Area", "Sequence",
        "Day-ahead Price (EUR/MWh)", "Intraday Period (CET/CEST)",
        "Intraday Price (EUR/MWh)"

    Returns a clean datetime-indexed price series.
    """
    df = _read_entsoe_csv(path)
    ts = _parse_mtu_start(df["MTU (CET/CEST)"])
    prices = pd.to_numeric(df["Day-ahead Price (EUR/MWh)"], errors="coerce")
    series = pd.Series(prices.values, index=ts, name="dam_price_eur_mwh")
    series = series.sort_index()
    series = series[~series.index.duplicated(keep="first")]
    return series


def load_entsoe_load_csv(path: str) -> pd.DataFrame:
    """Parse an ENTSO-E Transparency 'Total Load - Day-ahead/Actual' CSV.

    File name pattern: `GUI_TOTAL_LOAD_DAYAHEAD_<from>-<to>.csv`.

    Returns a DataFrame with two columns indexed by datetime:
        load_actual_mw, load_forecast_mw

    The forecast column is the feature we use for forecasting — it is
    published by the TSO before the DAM auction closes. The actual is
    used for evaluating forecast quality.
    """
    df = _read_entsoe_csv(path)
    ts = _parse_mtu_start(df["MTU (CET/CEST)"])
    actual = pd.to_numeric(df["Actual Total Load (MW)"], errors="coerce")
    forecast = pd.to_numeric(
        df["Day-ahead Total Load Forecast (MW)"], errors="coerce"
    )
    out = pd.DataFrame(
        {"load_actual_mw": actual.values, "load_forecast_mw": forecast.values},
        index=ts,
    )
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="first")]
    return out


def load_entsoe_flows_csv(
    path: str,
    focal_country: str = "GR",
) -> pd.DataFrame:
    """Parse an ENTSO-E 'Cross-Border Physical Flows' CSV.

    File name pattern: `GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_<from>-<to>.csv`.

    Handles both bidding-zone naming conventions seen in real exports:
      • "Greece (GR)" / "Albania (AL)" / etc.   (older/UI format)
      • "BZN|GR"     / "BZN|AL"     / etc.       (newer machine-readable)
      • Italian sub-zones (BZN|IT-Brindisi, BZN|IT-GR, BZN|IT-South)
        are aggregated into a single Italy total.

    Returns hourly net flows for `focal_country`:
        net_import_mw, total_imports_mw, total_exports_mw
    Positive net import = country is pulling from neighbors (correlates
    with higher domestic prices). Negative = country is exporting (often
    coincides with cheap surplus hours).
    """
    df = _read_entsoe_csv(path)
    ts = _parse_mtu_start(df["MTU"])
    df = df.assign(ts=ts)
    df["flow_mw"] = pd.to_numeric(df["Physical Flow (MW)"], errors="coerce")

    # Match either "Greece (GR)" or "BZN|GR" naming conventions
    code = focal_country.upper()
    in_focal = (
        df["In Area"].str.contains(rf"\({code}\)|BZN\|{code}\b", regex=True, na=False)
    )
    out_focal = (
        df["Out Area"].str.contains(rf"\({code}\)|BZN\|{code}\b", regex=True, na=False)
    )

    imports = (
        df[in_focal].groupby("ts")["flow_mw"].sum().rename("total_imports_mw")
    )
    exports = (
        df[out_focal].groupby("ts")["flow_mw"].sum().rename("total_exports_mw")
    )
    out = pd.concat([imports, exports], axis=1).fillna(0.0)
    out["net_import_mw"] = out["total_imports_mw"] - out["total_exports_mw"]
    out = out[["net_import_mw", "total_imports_mw", "total_exports_mw"]]
    out = out.sort_index()
    return out


def load_entsoe_renewable_forecast_csv(
    path: str, label: Optional[str] = None
) -> pd.DataFrame:
    """Parse an ENTSO-E 'Generation Forecast for Wind & Solar' CSV.

    File name patterns produced by the Transparency Platform:
      • `GUI_WIND_SOLAR_GENERATION_FORECAST_ONSHORE_*.csv` — typically wind onshore
      • `GUI_WIND_SOLAR_GENERATION_FORECAST_SOLAR_*.csv` — solar PV
      • `GUI_WIND_SOLAR_GENERATION_FORECAST_OFFSHORE_*.csv` — wind offshore

    Schema:
        "MTU (CET/CEST)", "Area",
        "Day-ahead (MW)", "Intraday (MW)", "Current (MW)", "Actual (MW)"

    NOTE on filename ambiguity: the ENTSO-E export tool sometimes
    returns *combined* wind+solar in a file named `_ONSHORE_`, and
    sometimes it returns *only* the named technology. We do NOT trust
    the filename. The caller can pass an explicit `label` (e.g.
    "wind", "solar", "renewables") which becomes the column name
    suffix; otherwise the loader auto-labels based on the diurnal
    profile (a midday-peaked profile = solar, a flat profile = wind).

    Hourly resolution.

    Returns a DataFrame indexed by datetime with two columns:
        {label}_da_forecast_mw, {label}_actual_mw
    """
    df = _read_entsoe_csv(path)
    ts = _parse_mtu_start(df["MTU (CET/CEST)"])
    da = pd.to_numeric(df["Day-ahead (MW)"], errors="coerce")
    actual = pd.to_numeric(df["Actual (MW)"], errors="coerce")

    if label is None:
        # Auto-detect: solar has zero output overnight and a midday peak
        tmp = pd.DataFrame({"v": da.values}, index=ts)
        tmp["hour"] = tmp.index.hour
        h = tmp.groupby("hour")["v"].mean()
        # Robust to partial coverage: only use hours with data
        h = h.dropna()
        if len(h) >= 24:
            midnight = h.iloc[0] if 0 in h.index else h.iloc[: max(1, len(h)//8)].mean()
            noon = h.loc[10:14].mean() if any(i in h.index for i in [10,11,12,13,14]) else h.max()
            ratio = noon / max(midnight, 1.0)
            label = "solar" if ratio > 2.5 else "wind"
        else:
            label = "renewables"

    out = pd.DataFrame(
        {
            f"{label}_da_forecast_mw": da.values,
            f"{label}_actual_mw": actual.values,
        },
        index=ts,
    )
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="first")]
    return out


def load_entsoe_renewable_directory(
    directory: str, label: Optional[str] = None
) -> pd.DataFrame:
    """Concatenate all renewable forecast CSVs in a directory.

    Useful when the ENTSO-E export was split across multiple time
    windows (e.g., 2025 and 2026 in separate files). Auto-detects which
    files belong to the same series via the column-name signature, so
    you can drop wind-2025, wind-2026, solar-2025, solar-2026 all in
    the same folder and call this twice with `label='wind'` and
    `label='solar'`.

    Parameters
    ----------
    directory : str
        Folder to scan (recursive=False).
    label : str
        "wind" or "solar" — which technology to extract. Required
        because the filenames are unreliable; auto-detection happens at
        the per-file level inside the loader.

    Returns
    -------
    pd.DataFrame
        Chronologically sorted, deduplicated, concatenated.
    """
    import glob
    import os

    pattern = os.path.join(directory, "GUI_WIND_SOLAR_GENERATION_FORECAST_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No renewable-forecast CSVs found in {directory}")

    pieces = []
    for f in files:
        per_file = load_entsoe_renewable_forecast_csv(f)
        col_label = list(per_file.columns)[0].split("_")[0]  # "wind"/"solar"
        if label is None or col_label == label:
            pieces.append(per_file)
    if not pieces:
        raise ValueError(
            f"No files in {directory} matched label={label!r}. "
            f"Files inspected: {[os.path.basename(f) for f in files]}"
        )
    out = pd.concat(pieces).sort_index()
    out = out[~out.index.duplicated(keep="first")]
    return out


def load_entsoe_total_generation_forecast_csv(path: str) -> pd.DataFrame:
    """Parse an ENTSO-E 'Total Generation Forecast' CSV.

    File name pattern: `GUI_TOTAL_GENERATION_FORECAST_*.csv`.
    Schema:
        "MTU (CET/CEST)", "Area",
        "Generation Forecast (MW)",
        "Actual Generation (MW)",
        "Scheduled Consumption (MW)"

    Hourly resolution. The forecast column is the system-wide
    day-ahead generation forecast and is a strong proxy for expected
    supply.

    Returns a DataFrame indexed by datetime:
        gen_forecast_mw, gen_actual_mw
    """
    df = _read_entsoe_csv(path)
    ts = _parse_mtu_start(df["MTU (CET/CEST)"])
    fcst = pd.to_numeric(df["Generation Forecast (MW)"], errors="coerce")
    actual = pd.to_numeric(df["Actual Generation (MW)"], errors="coerce")
    out = pd.DataFrame(
        {"gen_forecast_mw": fcst.values, "gen_actual_mw": actual.values},
        index=ts,
    )
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="first")]
    return out


def load_entsoe_generation_per_type_csv(
    path: str, types: Optional[list] = None
) -> pd.DataFrame:
    """Parse an ENTSO-E 'Aggregated Generation per Type' CSV.

    File name pattern: `AGGREGATED_GENERATION_PER_TYPE_*.csv`.
    Schema:
        "MTU (CET/CEST)", "Area", "Production Type", "Generation (MW)"

    Long format: one row per (timestamp × production type). Pivots the
    data into wide format with one column per type. Sentinel values
    `'n/e'` (not existent — plant type doesn't exist in this country)
    and `'-'` (missing) are coerced to NaN.

    Hourly resolution.

    Parameters
    ----------
    path : str
        Path to the CSV.
    types : list of str, optional
        Subset of production types to keep. By default keeps the types
        that are populated for Greece: Solar, Wind Onshore, Fossil Gas,
        Fossil Brown coal/Lignite, Hydro Water Reservoir,
        Hydro Pumped Storage.

    Returns
    -------
    pd.DataFrame
        Wide-format generation by type, indexed by datetime. Column
        names are snake-cased and prefixed with `gen_` (e.g.,
        `gen_solar_mw`, `gen_wind_onshore_mw`, `gen_fossil_gas_mw`).
    """
    df = _read_entsoe_csv(path)
    ts = _parse_mtu_start(df["MTU (CET/CEST)"])
    df = df.assign(ts=ts)

    # Coerce sentinels to NaN
    raw = df["Generation (MW)"].astype(str).str.strip()
    df["gen_mw"] = pd.to_numeric(
        raw.where(~raw.isin(["n/e", "-", ""]), other=None), errors="coerce"
    )

    if types is None:
        # Keep only types that have any data
        valid_types = (
            df.dropna(subset=["gen_mw"])["Production Type"].unique().tolist()
        )
        types = valid_types

    df = df[df["Production Type"].isin(types)]
    pivot = df.pivot_table(
        index="ts", columns="Production Type", values="gen_mw", aggfunc="first"
    )

    # Snake-case the columns and prefix with gen_
    def to_snake(s: str) -> str:
        return (
            "gen_"
            + s.lower()
                .replace("/", "_")
                .replace(" ", "_")
                .replace("-", "_")
            + "_mw"
        )

    pivot.columns = [to_snake(c) for c in pivot.columns]
    return pivot.sort_index()





def _load_entsoe_directory(
    directory: str, pattern: str, loader_fn
):
    """Generic helper: glob files in a directory, parse each, concat.

    Used by all the per-product directory loaders below.
    """
    import glob
    import os

    files = sorted(glob.glob(os.path.join(directory, pattern)))
    if not files:
        raise FileNotFoundError(
            f"No files matching '{pattern}' in {directory}"
        )
    pieces = []
    for f in files:
        try:
            pieces.append(loader_fn(f))
        except Exception as e:
            print(f"  warning: skipped {os.path.basename(f)} ({e})")
    if not pieces:
        raise ValueError("No files could be parsed.")
    out = pd.concat(pieces).sort_index()
    out = out[~out.index.duplicated(keep="first")]
    return out


def load_entsoe_prices_directory(directory: str) -> pd.Series:
    """Concatenate all `GUI_ENERGY_PRICES_*.csv` in a directory."""
    return _load_entsoe_directory(
        directory, "GUI_ENERGY_PRICES_*.csv", load_entsoe_prices_csv
    )


def load_entsoe_load_directory(directory: str) -> pd.DataFrame:
    """Concatenate all `GUI_TOTAL_LOAD_DAYAHEAD_*.csv` in a directory."""
    return _load_entsoe_directory(
        directory, "GUI_TOTAL_LOAD_DAYAHEAD_*.csv", load_entsoe_load_csv
    )


def load_entsoe_flows_directory(directory: str) -> pd.DataFrame:
    """Concatenate all `GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_*.csv` in a directory."""
    return _load_entsoe_directory(
        directory,
        "GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_*.csv",
        load_entsoe_flows_csv,
    )


def load_entsoe_total_generation_directory(directory: str) -> pd.DataFrame:
    """Concatenate all `GUI_TOTAL_GENERATION_FORECAST_*.csv` in a directory."""
    return _load_entsoe_directory(
        directory,
        "GUI_TOTAL_GENERATION_FORECAST_*.csv",
        load_entsoe_total_generation_forecast_csv,
    )


def load_entsoe_generation_per_type_directory(directory: str) -> pd.DataFrame:
    """Concatenate all `AGGREGATED_GENERATION_PER_TYPE_*.csv` in a directory."""
    return _load_entsoe_directory(
        directory,
        "AGGREGATED_GENERATION_PER_TYPE_*.csv",
        load_entsoe_generation_per_type_csv,
    )


def load_entsoe_flows_by_neighbor_csv(
    path: str,
    focal_country: str = "GR",
    italian_subzones: tuple = ("IT-Brindisi", "IT-GR", "IT-South"),
) -> pd.DataFrame:
    """Parse ENTSO-E cross-border flows into PER-NEIGHBOR net flows.

    Where `load_entsoe_flows_csv` aggregates all interconnectors into a
    single net flow, this loader returns a separate column per
    neighbor — useful for letting the model learn that the Italy
    interconnector behaves differently from the Bulgaria one.

    Italian sub-zones (IT-Brindisi, IT-GR, IT-South in the BZN code) are
    summed into a single Italy total.

    Parameters
    ----------
    path : str
    focal_country : str
        Two-letter code of the country we're modelling (default "GR").
    italian_subzones : tuple
        Substrings that identify Italian sub-zones to aggregate.

    Returns
    -------
    pd.DataFrame
        Hourly DataFrame with one column per neighbor, e.g.:
            flow_al_net_mw, flow_bg_net_mw, flow_it_net_mw,
            flow_mk_net_mw, flow_tr_net_mw
        Positive values = imports INTO `focal_country` from that neighbor.
        Negative = exports.
    """
    import re

    df = _read_entsoe_csv(path)
    ts = _parse_mtu_start(df["MTU"])
    df = df.assign(ts=ts)
    df["flow_mw"] = pd.to_numeric(df["Physical Flow (MW)"], errors="coerce")

    code = focal_country.upper()
    focal_re = re.compile(rf"\({code}\)|BZN\|{code}\b")

    def _neighbor_label(area_str: str) -> str:
        """Extract a normalized neighbor label."""
        s = str(area_str)
        # Italian sub-zones
        for sz in italian_subzones:
            if sz in s:
                return "it"
        m = re.search(r"BZN\|([A-Z]{2})\b", s)
        if m:
            return m.group(1).lower()
        m = re.search(r"\(([A-Z]{2})\)", s)
        if m:
            return m.group(1).lower()
        return s.lower()

    in_focal_mask = df["In Area"].astype(str).apply(lambda s: bool(focal_re.search(s)))
    out_focal_mask = df["Out Area"].astype(str).apply(lambda s: bool(focal_re.search(s)))

    # Imports INTO focal country (In Area is focal)
    imports = df[in_focal_mask].copy()
    imports["neighbor"] = imports["Out Area"].apply(_neighbor_label)
    imports_by_pair = imports.groupby(["ts", "neighbor"])["flow_mw"].sum().unstack(fill_value=0.0)

    # Exports FROM focal country (Out Area is focal)
    exports = df[out_focal_mask].copy()
    exports["neighbor"] = exports["In Area"].apply(_neighbor_label)
    exports_by_pair = exports.groupby(["ts", "neighbor"])["flow_mw"].sum().unstack(fill_value=0.0)

    # Net flow per neighbor = imports − exports
    all_neighbors = sorted(set(imports_by_pair.columns) | set(exports_by_pair.columns))
    out = pd.DataFrame(index=imports_by_pair.index.union(exports_by_pair.index))
    for n in all_neighbors:
        if n == focal_country.lower():
            continue
        imp = imports_by_pair[n] if n in imports_by_pair.columns else pd.Series(0.0, index=out.index)
        exp = exports_by_pair[n] if n in exports_by_pair.columns else pd.Series(0.0, index=out.index)
        out[f"flow_{n}_net_mw"] = imp.reindex(out.index).fillna(0.0) - exp.reindex(out.index).fillna(0.0)
    out = out.sort_index()
    return out


def load_entsoe_flows_by_neighbor_directory(
    directory: str, focal_country: str = "GR"
) -> pd.DataFrame:
    """Concatenate per-neighbor flows across multiple CSVs in a directory."""
    return _load_entsoe_directory(
        directory,
        "GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_*.csv",
        lambda p: load_entsoe_flows_by_neighbor_csv(p, focal_country=focal_country),
    )


def load_foreign_prices_directory(
    directory: str,
    country_map: Optional[dict] = None,
) -> dict:
    """Load DAM prices for multiple foreign countries from a directory of CSVs.

    Expects filenames containing the country/zone code as a token, e.g.:
        BG_2025.csv         → Bulgaria
        BG_2026.csv         → Bulgaria
        RO_2025.csv         → Romania
        IT_South_2025.csv   → Italy South
        IT_North_2026.csv   → Italy North
        MK_2025.csv         → North Macedonia

    Files for the same country are concatenated chronologically. The
    return value is a dict suitable for passing as the `external_prices`
    argument to `FeatureBuilder`.

    Parameters
    ----------
    directory : str
        Folder containing the CSV files.
    country_map : dict, optional
        Mapping from filename prefix to country code key. If None, the
        function uses the prefix before the first underscore-year-token
        (e.g. "BG", "IT_South", "RO").

    Returns
    -------
    dict[str, pd.Series]
        {country_code: price_series}, one entry per distinct country
        found. Series are datetime-indexed and sorted.
    """
    import glob
    import os
    import re

    files = sorted(glob.glob(os.path.join(directory, "*.csv")))
    if not files:
        raise FileNotFoundError(f"No CSV files in {directory}")

    by_country: dict = {}
    for f in files:
        base = os.path.basename(f)
        # Strip the year-range token "_YYYY" or "_YYYY.csv" from the end
        m = re.match(r"^(.+?)_2\d{3}(?:\.csv)?$", base)
        if not m:
            print(f"  skip {base}: doesn't look like a country file")
            continue
        country = m.group(1)
        try:
            series = load_entsoe_prices_csv(f)
        except Exception as e:
            print(f"  skip {base}: {e}")
            continue
        by_country.setdefault(country, []).append(series)

    out = {}
    for country, pieces in by_country.items():
        merged = pd.concat(pieces).sort_index()
        merged = merged[~merged.index.duplicated(keep="first")]
        merged.name = f"price_{country.lower()}_eur_mwh"
        out[country] = merged
    return out


def fetch_entsoe_dam(
    start: str,
    end: str,
    api_token: str,
    bidding_zone: str = "GR",
) -> pd.Series:
    """Fetch Greek DAM prices from the ENTSO-E Transparency Platform.

    Recommended approach (one-liner with the entsoe-py library):

        from entsoe import EntsoePandasClient
        client = EntsoePandasClient(api_key=api_token)
        s = client.query_day_ahead_prices(
            bidding_zone, start=pd.Timestamp(start), end=pd.Timestamp(end)
        )

    The free token is issued via the user's ENTSO-E account; allow
    1–2 days. Greek bidding zone code: 'GR'.
    """
    try:
        from entsoe import EntsoePandasClient  # type: ignore
    except ImportError as e:
        raise ImportError(
            "Install `entsoe-py` to use this loader: pip install entsoe-py"
        ) from e
    client = EntsoePandasClient(api_key=api_token)
    s = client.query_day_ahead_prices(
        bidding_zone,
        start=pd.Timestamp(start, tz="Europe/Athens"),
        end=pd.Timestamp(end, tz="Europe/Athens"),
    )
    s.name = "dam_price_eur_mwh"
    return s


def fetch_ipto_load(start: str, end: str) -> pd.DataFrame:
    """Fetch system load and RES generation forecasts from IPTO (ADMIE).

    See https://www.admie.gr/en/market/market-statistics/data
    Daily ISP files publish day-ahead load and RES forecasts. Useful
    as exogenous features for the SmartForecaster.

    Returns
    -------
    DataFrame with columns: load_mw, solar_mw, wind_mw
    """
    raise NotImplementedError(
        "Wire up to IPTO ISP files (https://www.admie.gr) and return "
        "a DataFrame indexed by datetime with columns "
        "[load_mw, solar_mw, wind_mw]."
    )


def fetch_openmeteo_weather(
    lat: float = 38.0,
    lon: float = 23.7,  # Athens-ish
    start: str = "2024-01-01",
    end: str = "2025-12-31",
) -> pd.DataFrame:
    """Fetch hourly historical weather from Open-Meteo.

    Open-Meteo is free and requires no API key for historical data.
    Endpoint: https://archive-api.open-meteo.com/v1/archive

    Returns
    -------
    DataFrame with columns: temperature_2m, shortwave_radiation,
    wind_speed_10m, cloudcover.
    """
    import urllib.parse
    import urllib.request
    import json

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": "temperature_2m,shortwave_radiation,wind_speed_10m,cloud_cover",
        "timezone": "Europe/Athens",
    }
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        + urllib.parse.urlencode(params)
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read())
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns={"cloud_cover": "cloudcover"})
    return df.set_index("time")


def fetch_openmeteo_forecast(
    lat: float = 38.0,
    lon: float = 23.7,  # Athens-ish
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    forecast_days: int = 2,
    timezone: str = "Europe/Athens",
) -> pd.DataFrame:
    """Fetch hourly forward weather forecast from Open-Meteo.

    Open-Meteo's forecast endpoint returns tomorrow-facing weather without an
    API key for non-commercial use. This is the right feed for DAM price
    forecasting because the auction cares about tomorrow's solar, wind, and
    temperature conditions rather than historical weather.

    Parameters
    ----------
    lat, lon : float
        Coordinates for the area of interest. Default is Athens-ish.
    start_date, end_date : str, optional
        If provided, request exactly this local-date window (YYYY-MM-DD).
    forecast_days : int
        Number of forward days if `start_date` / `end_date` are omitted.
    timezone : str
        Local timezone for returned timestamps.

    Returns
    -------
    pd.DataFrame
        Hourly DataFrame with columns: temperature_2m, shortwave_radiation,
        wind_speed_10m, cloudcover.
    """
    import json
    import urllib.parse
    import urllib.request

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,shortwave_radiation,wind_speed_10m,cloud_cover",
        "timezone": timezone,
    }
    if start_date is not None and end_date is not None:
        params["start_date"] = start_date
        params["end_date"] = end_date
    else:
        params["forecast_days"] = forecast_days

    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read())

    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns={"cloud_cover": "cloudcover"})
    return df.set_index("time")
