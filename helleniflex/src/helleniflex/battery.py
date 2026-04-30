"""
Battery asset specification.

The BatteryAsset class captures every parameter the optimizer needs.
It is intentionally generic: any standalone battery in the Greek market
(or anywhere else) can be expressed by instantiating this class with
the appropriate values. This is the heart of the framework's
"works with every asset" property.
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class BatteryAsset:
    """Physical and operational specification of a battery energy storage asset.

    All fields have defaults that match a representative 1 MW / 2 MWh
    lithium-iron-phosphate battery, consistent with publicly disclosed
    specs of the first standalone batteries entering the Greek DAM in
    test mode (April 2026). Override any field to model a different asset.

    Attributes
    ----------
    name
        Human-readable identifier (used in reports and plots).
    power_mw
        Maximum charge / discharge power in MW (assumed symmetric).
    capacity_mwh
        Nameplate energy capacity in MWh.
    eta_charge, eta_discharge
        One-way efficiencies. Round-trip efficiency is the product.
        Defaults give a round-trip of ~88%.
    soc_min_pct, soc_max_pct
        Usable State-of-Charge window as a fraction of nameplate.
        Restricting to 10–90% prolongs cell life.
    initial_soc_pct
        Starting SoC for a fresh optimization horizon.
    daily_cycle_limit
        Soft cap on equivalent full cycles per day. Models warranty
        constraints. Set to None to disable.
    cycle_cost_eur_per_mwh
        Marginal degradation cost in € per MWh of throughput. Acts as
        a regularizer that suppresses uneconomic cycling. Typical
        utility-scale Li-ion: 2–8 €/MWh. Set to 0 to disable.
    min_dispatch_mw
        Minimum non-zero dispatch power. Most batteries can modulate
        continuously down to ~0, so default is 0. Set higher to model
        a turbine-like asset.
    """

    # Identification
    name: str = "Generic 1 MW / 2 MWh BESS"

    # Power & energy
    power_mw: float = 1.0
    capacity_mwh: float = 2.0

    # Efficiency (round-trip = eta_charge * eta_discharge)
    eta_charge: float = 0.94
    eta_discharge: float = 0.94

    # Operating envelope
    soc_min_pct: float = 0.10
    soc_max_pct: float = 0.90
    initial_soc_pct: float = 0.50

    # Lifecycle
    daily_cycle_limit: Optional[float] = 1.5
    cycle_cost_eur_per_mwh: float = 3.0

    # Dispatch granularity
    min_dispatch_mw: float = 0.0

    # ---- Derived properties ----

    @property
    def soc_min_mwh(self) -> float:
        """Minimum allowed stored energy [MWh]."""
        return self.capacity_mwh * self.soc_min_pct

    @property
    def soc_max_mwh(self) -> float:
        """Maximum allowed stored energy [MWh]."""
        return self.capacity_mwh * self.soc_max_pct

    @property
    def initial_soc_mwh(self) -> float:
        """Starting stored energy [MWh]."""
        return self.capacity_mwh * self.initial_soc_pct

    @property
    def usable_capacity_mwh(self) -> float:
        """Energy available between SoC_min and SoC_max [MWh]."""
        return self.capacity_mwh * (self.soc_max_pct - self.soc_min_pct)

    @property
    def round_trip_efficiency(self) -> float:
        """End-to-end efficiency (charge → discharge)."""
        return self.eta_charge * self.eta_discharge

    @property
    def duration_hours(self) -> float:
        """Discharge duration at rated power, ignoring SoC limits."""
        return self.capacity_mwh / self.power_mw

    # ---- Validation & serialization ----

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
        """Serialize for logging / dashboards."""
        d = asdict(self)
        d["round_trip_efficiency"] = self.round_trip_efficiency
        d["duration_hours"] = self.duration_hours
        d["usable_capacity_mwh"] = self.usable_capacity_mwh
        return d

    def summary(self) -> str:
        """One-line summary for logs and reports."""
        return (
            f"{self.name}: {self.power_mw:.1f} MW / {self.capacity_mwh:.1f} MWh "
            f"({self.duration_hours:.1f}h), eta_RT={self.round_trip_efficiency:.0%}, "
            f"SoC {self.soc_min_pct:.0%}-{self.soc_max_pct:.0%}"
        )


# ---- Preset library ----
# Convenience presets for common asset profiles. Add new ones freely.

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
        daily_cycle_limit=1.0,  # longer-duration assets typically cycle less
    ),
    "utility_50mw_2h": BatteryAsset(
        name="Utility-scale 50 MW / 100 MWh",
        power_mw=50.0, capacity_mwh=100.0,
        eta_charge=0.94, eta_discharge=0.94,
    ),
}
