"""
POST /api/optimize

Body:
  {
    "date": "YYYY-MM-DD",
    "battery": {
      "power_mw": float,
      "capacity_mwh": float,
      "eta_charge": float,       # default 0.94
      "eta_discharge": float,    # default 0.94
      "soc_min_pct": float,      # default 0.10
      "soc_max_pct": float,      # default 0.90
      "initial_soc_pct": float,  # default 0.50
      "daily_cycle_limit": float | null,
      "cycle_cost_eur_per_mwh": float  # default 3.0
    }
  }

Returns DispatchResult + price forecast + capture rate.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd

from _helleniflex.battery import BatteryAsset
from _helleniflex.optimizer import BatteryOptimizer
from _helleniflex.forecaster import SmartForecaster, NaiveForecaster
from _helleniflex.data_loader import make_synthetic_greek_dam_prices

DT = 0.25
T = 96


def _make_battery(b: dict) -> BatteryAsset:
    return BatteryAsset(
        power_mw=float(b["power_mw"]),
        capacity_mwh=float(b["capacity_mwh"]),
        eta_charge=float(b.get("eta_charge", 0.94)),
        eta_discharge=float(b.get("eta_discharge", 0.94)),
        soc_min_pct=float(b.get("soc_min_pct", 0.10)),
        soc_max_pct=float(b.get("soc_max_pct", 0.90)),
        initial_soc_pct=float(b.get("initial_soc_pct", 0.50)),
        daily_cycle_limit=(
            float(b["daily_cycle_limit"])
            if b.get("daily_cycle_limit") is not None
            else None
        ),
        cycle_cost_eur_per_mwh=float(b.get("cycle_cost_eur_per_mwh", 3.0)),
    )


def run_optimization(date: str, battery_dict: dict) -> dict:
    prices_all = make_synthetic_greek_dam_prices(start="2024-01-01", end="2026-12-31")
    target = pd.Timestamp(date)
    day_end = target + pd.Timedelta(days=1)

    history = prices_all[prices_all.index < target]
    actual_slice = prices_all[(prices_all.index >= target) & (prices_all.index < day_end)]

    # Forecast
    forecaster_name = "Smart (Ridge + calendar)"
    try:
        fc = SmartForecaster()
        fc.fit(history)
        forecast = fc.predict(target, history)
    except Exception:
        try:
            forecast = NaiveForecaster().predict(target, history)
            forecaster_name = "Naive (last-week)"
        except Exception:
            forecast = np.full(T, 100.0)
            forecaster_name = "Flat fallback"

    forecast = np.asarray(forecast, dtype=float)
    if len(forecast) != T:
        forecast = np.resize(forecast, T)

    # MILP dispatch
    battery = _make_battery(battery_dict)
    opt = BatteryOptimizer(battery, use_binary=True)
    result = opt.optimize(forecast, dt_hours=DT, enforce_cyclic=True)

    if not result.is_optimal:
        return {
            "forecast_prices":     forecast.tolist(),
            "charge_mw":           [0.0] * T,
            "discharge_mw":        [0.0] * T,
            "net_mw":              [0.0] * T,
            "soc_mwh":             [battery.initial_soc_mwh] * (T + 1),
            "soc_min_mwh":         float(battery.soc_min_mwh),
            "soc_max_mwh":         float(battery.soc_max_mwh),
            "revenue_eur":         0.0,
            "net_revenue_eur":     0.0,
            "capture_rate":        None,
            "capture_rate_window": None,
            "cycles":              0.0,
            "status":              result.status,
            "forecaster":          forecaster_name,
        }

    # Perfect-foresight benchmark for capture rate
    capture_rate = None
    capture_rate_window = None
    if len(actual_slice) >= T:
        pf = opt.optimize(actual_slice.values[:T], dt_hours=DT, enforce_cyclic=True)
        if pf.is_optimal and pf.objective_eur > 1e-6:
            capture_rate = float(
                np.clip(result.objective_eur / pf.objective_eur * 100.0, 0.0, 200.0)
            )
            capture_rate_window = "same-day oracle (synthetic data)"

    # Clamp SoC to declared operating window to prevent floating-point overshoot
    soc_clamped = np.clip(
        result.soc_mwh, battery.soc_min_mwh, battery.soc_max_mwh
    ).tolist()

    return {
        "forecast_prices":     forecast.tolist(),
        "charge_mw":           result.charge_mw.tolist(),
        "discharge_mw":        result.discharge_mw.tolist(),
        "net_mw":              result.net_mw.tolist(),
        "soc_mwh":             soc_clamped,
        "soc_min_mwh":         float(battery.soc_min_mwh),
        "soc_max_mwh":         float(battery.soc_max_mwh),
        "revenue_eur":         float(result.revenue_eur),
        "net_revenue_eur":     float(result.objective_eur),
        "capture_rate":        capture_rate,
        "capture_rate_window": capture_rate_window,
        "cycles":              float(result.cycles),
        "status":              result.status,
        "forecaster":          forecaster_name,
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        try:
            payload = run_optimization(body["date"], body["battery"])
            self._respond(200, payload)
        except Exception as exc:
            self._respond(500, {"error": str(exc)})

    def _respond(self, code: int, data: dict) -> None:
        encoded = json.dumps(data).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, *_):
        pass
