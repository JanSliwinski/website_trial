"""
Battery dispatch optimizer — MILP via cvxpy + HiGHS.

Decision variables per timestep t:
    p_c[t] >= 0     charging power [MW]
    p_d[t] >= 0     discharging power [MW]
    e[t+1] >= 0     stored energy at end of step [MWh]
    z[t] in {0,1}   1=charging, 0=discharging (mutual exclusion)

Objective:
    max  sum_t lambda[t] * (p_d[t] - p_c[t]) * dt
       - c_cyc * sum_t (p_c[t] + p_d[t]) * dt
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import cvxpy as cp

from .battery import BatteryAsset


@dataclass
class DispatchResult:
    status: str
    objective_eur: float
    revenue_eur: float
    degradation_cost_eur: float
    cycles: float
    charge_mw: np.ndarray
    discharge_mw: np.ndarray
    net_mw: np.ndarray
    soc_mwh: np.ndarray
    prices: np.ndarray
    dt_hours: float

    @property
    def is_optimal(self) -> bool:
        return self.status in ("optimal", "optimal_inaccurate")


class BatteryOptimizer:
    def __init__(
        self,
        battery: BatteryAsset,
        use_binary: bool = True,
        solver: str = cp.HIGHS,
    ) -> None:
        self.battery = battery
        self.use_binary = use_binary
        self.solver = solver

    def optimize(
        self,
        prices: np.ndarray,
        dt_hours: float = 0.25,
        initial_soc_mwh: Optional[float] = None,
        terminal_soc_mwh: Optional[float] = None,
        enforce_cyclic: bool = True,
    ) -> DispatchResult:
        prices = np.asarray(prices, dtype=float)
        T = len(prices)
        b = self.battery

        e_init = initial_soc_mwh if initial_soc_mwh is not None else b.initial_soc_mwh
        e_term = terminal_soc_mwh if terminal_soc_mwh is not None else (
            e_init if enforce_cyclic else None
        )

        p_c = cp.Variable(T, nonneg=True)
        p_d = cp.Variable(T, nonneg=True)
        e = cp.Variable(T + 1)
        if self.use_binary:
            z = cp.Variable(T, boolean=True)

        constraints = [
            e[0] == e_init,
            e >= b.soc_min_mwh,
            e <= b.soc_max_mwh,
        ]

        if self.use_binary:
            constraints += [
                p_c <= b.power_mw * z,
                p_d <= b.power_mw * (1 - z),
            ]
        else:
            constraints += [p_c <= b.power_mw, p_d <= b.power_mw]

        constraints.append(
            e[1:] == e[:-1]
            + b.eta_charge * p_c * dt_hours
            - p_d * dt_hours / b.eta_discharge
        )

        if e_term is not None:
            constraints.append(e[T] == e_term)

        if b.daily_cycle_limit is not None and b.usable_capacity_mwh > 0:
            constraints.append(
                cp.sum(p_c) * dt_hours
                <= b.daily_cycle_limit * b.usable_capacity_mwh
            )

        gross_revenue = cp.sum(cp.multiply(prices, p_d - p_c)) * dt_hours
        degradation = b.cycle_cost_eur_per_mwh * cp.sum(p_c + p_d) * dt_hours
        objective = cp.Maximize(gross_revenue - degradation)

        problem = cp.Problem(objective, constraints)
        problem.solve(solver=self.solver)

        if problem.status not in ("optimal", "optimal_inaccurate"):
            return DispatchResult(
                status=problem.status,
                objective_eur=0.0,
                revenue_eur=0.0,
                degradation_cost_eur=0.0,
                cycles=0.0,
                charge_mw=np.zeros(T),
                discharge_mw=np.zeros(T),
                net_mw=np.zeros(T),
                soc_mwh=np.full(T + 1, e_init),
                prices=prices,
                dt_hours=dt_hours,
            )

        charge = np.array(p_c.value).clip(min=0)
        discharge = np.array(p_d.value).clip(min=0)
        soc = np.array(e.value)
        net = discharge - charge

        rev = float(np.sum(prices * net) * dt_hours)
        deg = float(b.cycle_cost_eur_per_mwh * np.sum(charge + discharge) * dt_hours)
        cycles = (
            float(np.sum(charge) * dt_hours / b.usable_capacity_mwh)
            if b.usable_capacity_mwh > 0 else 0.0
        )

        return DispatchResult(
            status=problem.status,
            objective_eur=float(problem.value),
            revenue_eur=rev,
            degradation_cost_eur=deg,
            cycles=cycles,
            charge_mw=charge,
            discharge_mw=discharge,
            net_mw=net,
            soc_mwh=soc,
            prices=prices,
            dt_hours=dt_hours,
        )

    @staticmethod
    def settle(schedule: DispatchResult, actual_prices: np.ndarray) -> float:
        actual_prices = np.asarray(actual_prices, dtype=float)
        return float(np.sum(actual_prices * schedule.net_mw) * schedule.dt_hours)
