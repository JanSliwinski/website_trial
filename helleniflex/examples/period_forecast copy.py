"""Run the full DAM forecast + battery bidding workflow over a date period.

This script intentionally reuses `examples/tomorrow_forecast.py` for each
delivery day. That keeps the core forecasting, ADMIE/weather/gas feature logic,
battery optimization, and per-day graphs in one place.

Usage:
    python "examples/period_forecast copy.py" 2026-04-30 2026-05-03
    python "examples/period_forecast copy.py" 2026-04-30 2026-05-03 --refresh

Without `--refresh`, existing daily output files are reused. Missing days are
generated automatically.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = ROOT / "examples"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

DT_HOURS = 0.25


def parse_period_from_argv() -> tuple[pd.Timestamp, pd.Timestamp, bool]:
    """Read an inclusive forecast period from command-line arguments."""

    refresh = "--refresh" in sys.argv[1:]
    date_args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

    if not date_args:
        tomorrow = (
            pd.Timestamp.today(tz="Europe/Athens")
            .tz_localize(None)
            .normalize()
            + pd.Timedelta(days=1)
        )
        return tomorrow, tomorrow, refresh

    start_day = pd.Timestamp(date_args[0]).normalize()
    end_day = pd.Timestamp(date_args[1]).normalize() if len(date_args) > 1 else start_day

    if start_day > end_day:
        raise ValueError("Start date must be before or equal to end date.")

    return start_day, end_day, refresh


def iter_days(start_day: pd.Timestamp, end_day: pd.Timestamp) -> list[pd.Timestamp]:
    """Return every delivery day in an inclusive date period."""

    return [
        pd.Timestamp(day).normalize()
        for day in pd.date_range(start_day, end_day, freq="D")
    ]


def daily_paths(day: pd.Timestamp) -> dict[str, Path]:
    """Return the files produced by tomorrow_forecast.py for one day."""

    date_key = day.strftime("%Y%m%d")
    return {
        "forecast": DATA_DIR / f"tomorrow_dam_forecast_{date_key}.csv",
        "bidding": DATA_DIR / f"tomorrow_bidding_schedule_{date_key}.csv",
        "graph": DOCS_DIR / f"tomorrow_forecast_bidding_{date_key}.png",
    }


def has_daily_outputs(paths: dict[str, Path]) -> bool:
    """Check whether the daily forecast and bidding outputs already exist."""

    return paths["forecast"].exists() and paths["bidding"].exists()


def run_daily_forecast(day: pd.Timestamp, refresh: bool) -> dict[str, Path]:
    """Run tomorrow_forecast.py for a day unless reusable outputs exist."""

    paths = daily_paths(day)
    day_label = day.strftime("%Y-%m-%d")

    if has_daily_outputs(paths) and not refresh:
        print(f"  {day_label}: using existing daily outputs")
        return paths

    print(f"  {day_label}: running tomorrow_forecast.py")
    command = [
        sys.executable,
        str(EXAMPLES_DIR / "tomorrow_forecast.py"),
        day_label,
    ]
    completed = subprocess.run(command, cwd=str(ROOT), check=False)

    if completed.returncode != 0:
        raise RuntimeError(
            f"tomorrow_forecast.py failed for {day_label} "
            f"with exit code {completed.returncode}"
        )

    if not has_daily_outputs(paths):
        raise FileNotFoundError(
            f"Expected daily outputs were not created for {day_label}: "
            f"{paths['forecast']} and {paths['bidding']}"
        )

    return paths


def load_daily_outputs(day: pd.Timestamp, paths: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load one day's forecast and bidding schedule with a delivery_date column."""

    forecast = pd.read_csv(paths["forecast"], index_col=0, parse_dates=True)
    bidding = pd.read_csv(paths["bidding"], index_col=0, parse_dates=True)

    day_label = day.strftime("%Y-%m-%d")
    forecast.insert(0, "delivery_date", day_label)
    bidding.insert(0, "delivery_date", day_label)

    return forecast, bidding


def summarize_day(
    day: pd.Timestamp,
    forecast: pd.DataFrame,
    bidding: pd.DataFrame,
    paths: dict[str, Path],
) -> dict[str, object]:
    """Build one compact row describing the forecast and battery schedule."""

    price_column = "operational_price_eur_mwh"
    prices = forecast[price_column]
    expected_revenue = float(bidding["slot_revenue_eur"].sum())
    capacity_mwh = float(bidding["soc_mwh"].max())
    charge_mwh = float((bidding["charge_mw"] * DT_HOURS).sum())
    discharge_mwh = float((bidding["discharge_mw"] * DT_HOURS).sum())

    if capacity_mwh > 0:
        cycles = (charge_mwh + discharge_mwh) / (2.0 * capacity_mwh)
        annual_revenue_per_mwh = expected_revenue * 365.0 / capacity_mwh
    else:
        cycles = 0.0
        annual_revenue_per_mwh = 0.0

    peak_time = prices.idxmax()
    trough_time = prices.idxmin()

    return {
        "delivery_date": day.strftime("%Y-%m-%d"),
        "operational_mean_eur_mwh": float(prices.mean()),
        "ridge_mean_eur_mwh": float(forecast["ridge_price_eur_mwh"].mean()),
        "gbm_mean_eur_mwh": (
            float(forecast["gbm_price_eur_mwh"].mean())
            if "gbm_price_eur_mwh" in forecast
            else None
        ),
        "peak_time": peak_time,
        "peak_price_eur_mwh": float(prices.loc[peak_time]),
        "trough_time": trough_time,
        "trough_price_eur_mwh": float(prices.loc[trough_time]),
        "buy_slots": int((bidding["bid_side"] == "BUY").sum()),
        "sell_slots": int((bidding["bid_side"] == "SELL").sum()),
        "hold_slots": int((bidding["bid_side"] == "HOLD").sum()),
        "charge_mwh": charge_mwh,
        "discharge_mwh": discharge_mwh,
        "cycles": cycles,
        "expected_revenue_eur": expected_revenue,
        "annual_revenue_eur": expected_revenue * 365.0,
        "annual_revenue_eur_per_mwh": annual_revenue_per_mwh,
        "forecast_csv": str(paths["forecast"]),
        "bidding_csv": str(paths["bidding"]),
        "daily_graph_png": str(paths["graph"]),
        "status": "ok",
    }


def save_period_summary_graph(summary: pd.DataFrame, period_key: str) -> Path:
    """Save a period-level overview graph."""

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DOCS_DIR / f"period_forecast_summary_{period_key}.png"

    ok = summary[summary["status"] == "ok"].copy()
    ok["delivery_date"] = pd.to_datetime(ok["delivery_date"])

    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    fig.suptitle(f"DAM Forecast and Battery Bidding Summary {period_key}", fontsize=14)

    axes[0].plot(
        ok["delivery_date"],
        ok["operational_mean_eur_mwh"],
        marker="o",
        color="#2f6f9f",
        label="Mean forecast price",
    )
    axes[0].set_ylabel("EUR/MWh")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left")

    axes[1].bar(
        ok["delivery_date"],
        ok["expected_revenue_eur"],
        color="#3f8f5f",
        label="Expected daily revenue",
    )
    axes[1].set_ylabel("EUR/day")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(loc="upper left")

    axes[2].plot(
        ok["delivery_date"],
        ok["charge_mwh"],
        marker="o",
        color="#3f7fbf",
        label="Charge MWh",
    )
    axes[2].plot(
        ok["delivery_date"],
        ok["discharge_mwh"],
        marker="o",
        color="#bf5f3f",
        label="Discharge MWh",
    )
    axes[2].set_ylabel("MWh/day")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="upper left")

    fig.autofmt_xdate()
    plt.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

    return output_path


def main() -> None:
    start_day, end_day, refresh = parse_period_from_argv()
    period_key = f"{start_day:%Y%m%d}_{end_day:%Y%m%d}"

    print("=" * 78)
    print(f"HelleniFlex Period DAM Forecast: {start_day:%Y-%m-%d} -> {end_day:%Y-%m-%d}")
    print("=" * 78)

    forecast_frames: list[pd.DataFrame] = []
    bidding_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []

    for day in iter_days(start_day, end_day):
        day_label = day.strftime("%Y-%m-%d")
        try:
            paths = run_daily_forecast(day, refresh=refresh)
            forecast, bidding = load_daily_outputs(day, paths)
            forecast_frames.append(forecast)
            bidding_frames.append(bidding)
            summary_rows.append(summarize_day(day, forecast, bidding, paths))
        except Exception as exc:
            summary_rows.append(
                {
                    "delivery_date": day_label,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"  {day_label}: failed - {exc}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    summary = pd.DataFrame(summary_rows)
    summary_path = DATA_DIR / f"period_forecast_summary_{period_key}.csv"
    summary.to_csv(summary_path, index=False)

    forecast_path = None
    bidding_path = None
    graph_path = None

    if forecast_frames:
        combined_forecast = pd.concat(forecast_frames).sort_index()
        forecast_path = DATA_DIR / f"period_dam_forecast_{period_key}.csv"
        combined_forecast.to_csv(forecast_path)

    if bidding_frames:
        combined_bidding = pd.concat(bidding_frames).sort_index()
        bidding_path = DATA_DIR / f"period_bidding_schedule_{period_key}.csv"
        combined_bidding.to_csv(bidding_path)

    if not summary.empty and (summary["status"] == "ok").any():
        graph_path = save_period_summary_graph(summary, period_key)

    print("\nPeriod outputs:")
    print(f"  Summary:          {summary_path}")
    if forecast_path:
        print(f"  Forecasts:        {forecast_path}")
    if bidding_path:
        print(f"  Bidding schedule: {bidding_path}")
    if graph_path:
        print(f"  Period graph:     {graph_path}")

    ok_summary = summary[summary["status"] == "ok"]
    if not ok_summary.empty:
        total_revenue = float(ok_summary["expected_revenue_eur"].sum())
        print("\nPeriod totals:")
        print(f"  Successful days:  {len(ok_summary)} / {len(summary)}")
        print(f"  Expected revenue: EUR{total_revenue:,.2f}")
        print(f"  Daily average:    EUR{total_revenue / len(ok_summary):,.2f}/day")

    failed = summary[summary["status"] == "failed"]
    if not failed.empty:
        print("\nFailed days:")
        for _, row in failed.iterrows():
            print(f"  {row['delivery_date']}: {row.get('error', 'unknown error')}")


if __name__ == "__main__":
    main()
