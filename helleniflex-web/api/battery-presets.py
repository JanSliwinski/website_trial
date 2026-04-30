"""GET /api/battery-presets — returns available battery configurations."""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))

PRESETS = [
    {
        "id": "1h",
        "name": "1h BESS",
        "label": "Greek Standalone · 1 MW / 1 MWh",
        "battery": {
            "power_mw": 1.0,
            "capacity_mwh": 1.0,
            "eta_charge": 0.95,
            "eta_discharge": 0.95,
            "soc_min_pct": 0.10,
            "soc_max_pct": 0.90,
            "initial_soc_pct": 0.50,
            "daily_cycle_limit": 1.5,
            "cycle_cost_eur_per_mwh": 3.0,
        },
    },
    {
        "id": "2h",
        "name": "2h BESS",
        "label": "Greek Standalone · 1 MW / 2 MWh",
        "battery": {
            "power_mw": 1.0,
            "capacity_mwh": 2.0,
            "eta_charge": 0.94,
            "eta_discharge": 0.94,
            "soc_min_pct": 0.10,
            "soc_max_pct": 0.90,
            "initial_soc_pct": 0.50,
            "daily_cycle_limit": 1.5,
            "cycle_cost_eur_per_mwh": 3.0,
        },
    },
    {
        "id": "4h",
        "name": "4h BESS",
        "label": "Greek Standalone · 1 MW / 4 MWh",
        "battery": {
            "power_mw": 1.0,
            "capacity_mwh": 4.0,
            "eta_charge": 0.93,
            "eta_discharge": 0.93,
            "soc_min_pct": 0.10,
            "soc_max_pct": 0.90,
            "initial_soc_pct": 0.50,
            "daily_cycle_limit": 1.0,
            "cycle_cost_eur_per_mwh": 3.0,
        },
    },
    {
        "id": "utility",
        "name": "Utility",
        "label": "Utility Scale · 50 MW / 100 MWh",
        "battery": {
            "power_mw": 50.0,
            "capacity_mwh": 100.0,
            "eta_charge": 0.94,
            "eta_discharge": 0.94,
            "soc_min_pct": 0.10,
            "soc_max_pct": 0.90,
            "initial_soc_pct": 0.50,
            "daily_cycle_limit": 1.5,
            "cycle_cost_eur_per_mwh": 3.0,
        },
    },
]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        encoded = json.dumps(PRESETS).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_):
        pass
