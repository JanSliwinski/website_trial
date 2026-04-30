from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class BatteryAsset:
    name: str = "Generic 1 MW / 2 MWh BESS"
    power_mw: float = 1.0
    capacity_mwh: float = 2.0
    eta_charge: float = 0.94
    eta_discharge: float = 0.94
    soc_min_pct: float = 0.10
    soc_max_pct: float = 0.90
    initial_soc_pct: float = 0.50
    daily_cycle_limit: Optional[float] = 1.5
    cycle_cost_eur_per_mwh: float = 3.0
    min_dispatch_mw: float = 0.0

    @property
    def soc_min_mwh(self) -> float:
        return self.capacity_mwh * self.soc_min_pct

    @property
    def soc_max_mwh(self) -> float:
        return self.capacity_mwh * self.soc_max_pct

    @property
    def initial_soc_mwh(self) -> float:
        return self.capacity_mwh * self.initial_soc_pct

    @property
    def usable_capacity_mwh(self) -> float:
        return self.capacity_mwh * (self.soc_max_pct - self.soc_min_pct)

    @property
    def round_trip_efficiency(self) -> float:
        return self.eta_charge * self.eta_discharge

    @property
    def duration_hours(self) -> float:
        return self.capacity_mwh / self.power_mw

    def __post_init__(self) -> None:
        if self.power_mw <= 0:
            raise ValueError("power_mw must be positive")
        if self.capacity_mwh <= 0:
            raise ValueError("capacity_mwh must be positive")
        if not (0 < self.eta_charge <= 1 and 0 < self.eta_discharge <= 1):
            raise ValueError("efficiencies must be in (0, 1]")
        if not (0 <= self.soc_min_pct < self.soc_max_pct <= 1):
            raise ValueError("require 0 <= soc_min < soc_max <= 1")
        if not (self.soc_min_pct <= self.initial_soc_pct <= self.soc_max_pct):
            raise ValueError("initial_soc_pct must lie inside the SoC window")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["round_trip_efficiency"] = self.round_trip_efficiency
        d["duration_hours"] = self.duration_hours
        d["usable_capacity_mwh"] = self.usable_capacity_mwh
        return d


PRESETS: dict[str, BatteryAsset] = {
    "greek_standalone_1h": BatteryAsset(
        name="Greek Standalone 1h BESS",
        power_mw=1.0, capacity_mwh=1.0,
        eta_charge=0.95, eta_discharge=0.95,
    ),
    "greek_standalone_2h": BatteryAsset(
        name="Greek Standalone 2h BESS",
        power_mw=1.0, capacity_mwh=2.0,
        eta_charge=0.94, eta_discharge=0.94,
    ),
    "greek_standalone_4h": BatteryAsset(
        name="Greek Standalone 4h BESS",
        power_mw=1.0, capacity_mwh=4.0,
        eta_charge=0.93, eta_discharge=0.93,
        daily_cycle_limit=1.0,
    ),
    "utility_50mw_2h": BatteryAsset(
        name="Utility-scale 50 MW / 100 MWh",
        power_mw=50.0, capacity_mwh=100.0,
        eta_charge=0.94, eta_discharge=0.94,
    ),
}
