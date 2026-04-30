"""
Battery dispatch optimizer.

Formulates the day-ahead battery scheduling problem as a Mixed-Integer
Linear Program (MILP) and solves it with HiGHS. The formulation is
generic over time-step (15-min or 1-h) and over asset (any BatteryAsset).

Mathematical formulation
------------------------
Decision variables for each timestep t ∈ {0, ..., T-1}:
    p_c[t]   ≥ 0    charging power [MW]
    p_d[t]   ≥ 0    discharging power [MW]
    e[t+1]   ≥ 0    stored energy at end of step [MWh]
    z[t] ∈ {0, 1}   1 = charging, 0 = discharging (mutual exclusion)

Objective:
    max  Σ_t λ[t] · (p_d[t] − p_c[t]) · Δt        (gross revenue)
       − c_cyc · Σ_t (p_c[t] + p_d[t]) · Δt        (degradation cost)

Subject to:
    e[t+1] = e[t] + η_c · p_c[t] · Δt − p_d[t] · Δt / η_d   (SoC dynamics)
    e_min ≤ e[t] ≤ e_max                                    (energy bounds)
    p_c[t] ≤ P_max · z[t]                                   (charge gate)
    p_d[t] ≤ P_max · (1 − z[t])                             (discharge gate)
    e[T] = e[0]                                              (cyclic SoC, optional)
    Σ p_c[t] · Δt ≤ N_cyc · E_usable                         (daily throughput cap)

Why a binary z[t]?
    Without it, simultaneous charge+discharge can be exploited as a
    revenue trick when prices are negative (you "burn" energy through
    the round-trip loss to earn money). Real assets cannot do this.
    The binary variable closes that loophole. With T ≤ 96 it solves
    in milliseconds with HiGHS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import cvxpy as cp

from .battery import BatteryAsset


@dataclass
class DispatchResult:
    """Output of a single optimization run."""

    status: str
    objective_eur: float
    revenue_eur: float
    degradation_cost_eur: float
    cycles: float
    charge_mw: np.ndarray            # length T
    discharge_mw: np.ndarray         # length T
    net_mw: np.ndarray               # discharge − charge, length T
    soc_mwh: np.ndarray              # length T+1
    prices: np.ndarray               # length T (input echoed back)
    dt_hours: float

    @property
    def is_optimal(self) -> bool:
        return self.status in ("optimal", "optimal_inaccurate")

    def to_dataframe(self):
        """Return a pandas DataFrame indexed by timestep."""
        import pandas as pd

        T = len(self.prices)
        return pd.DataFrame(
            {
                "price_eur_mwh": self.prices,
                "charge_mw": self.charge_mw,
                "discharge_mw": self.discharge_mw,
                "net_mw": self.net_mw,
                "soc_mwh": self.soc_mwh[:T],
            }
        )


class BatteryOptimizer:
    """Solves single-horizon battery dispatch given a price forecast.

    Parameters
    ----------
    battery
        The asset specification.
    use_binary
        If True, enforce charge/discharge mutual exclusion via a binary
        variable. Recommended (always-on by default). Set False to get
        a fast LP relaxation when prices are guaranteed non-negative.
    solver
        cvxpy solver name. Defaults to HiGHS (free, fast, ships with
        cvxpy via highspy).
    """

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
        """Solve the dispatch problem for a given price series.

        Parameters
        ----------
        prices : array-like
            Forecast or realised prices in €/MWh, one per timestep.
        dt_hours : float
            Length of one timestep in hours. 0.25 for 15-min DAM,
            1.0 for hourly DAM.
        initial_soc_mwh : float, optional
            Override the battery's default starting SoC.
        terminal_soc_mwh : float, optional
            Pin the ending SoC. If None and enforce_cyclic, defaults
            to the initial SoC.
        enforce_cyclic : bool
            If True, force end SoC == start SoC so the schedule is
            sustainable day after day.

        Returns
        -------
        DispatchResult
        """
        prices = np.asarray(prices, dtype=float)
        T = len(prices)
        b = self.battery

        e_init = initial_soc_mwh if initial_soc_mwh is not None else b.initial_soc_mwh
        e_term = terminal_soc_mwh if terminal_soc_mwh is not None else (
            e_init if enforce_cyclic else None
        )

        # --- Variables ---
        p_c = cp.Variable(T, nonneg=True)
        p_d = cp.Variable(T, nonneg=True)
        e = cp.Variable(T + 1)  # SoC trajectory, length T+1
        if self.use_binary:
            z = cp.Variable(T, boolean=True)

        # --- Constraints ---
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
            constraints += [
                p_c <= b.power_mw,
                p_d <= b.power_mw,
            ]

        # SoC dynamics (vectorised: e[1:] depends on e[:-1])
        constraints.append(
            e[1:] == e[:-1]
            + b.eta_charge * p_c * dt_hours
            - p_d * dt_hours / b.eta_discharge
        )

        # Terminal SoC (cyclic by default)
        if e_term is not None:
            constraints.append(e[T] == e_term)

        # Daily cycle / throughput cap
        if b.daily_cycle_limit is not None and b.usable_capacity_mwh > 0:
            constraints.append(
                cp.sum(p_c) * dt_hours
                <= b.daily_cycle_limit * b.usable_capacity_mwh
            )

        # --- Objective ---
        gross_revenue = cp.sum(cp.multiply(prices, p_d - p_c)) * dt_hours
        degradation = b.cycle_cost_eur_per_mwh * cp.sum(p_c + p_d) * dt_hours
        objective = cp.Maximize(gross_revenue - degradation)

        problem = cp.Problem(objective, constraints)
        problem.solve(solver=self.solver)

        if problem.status not in ("optimal", "optimal_inaccurate"):
            # Return zeros with the failed status — caller decides what to do
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

    # ------------------------------------------------------------------ #
    # Settlement helper: given an optimised schedule (computed on a price
    # *forecast*) and the *actual* realised prices, compute the revenue
    # the asset would actually collect. Used by the backtester to
    # measure forecast-error sensitivity.
    # ------------------------------------------------------------------ #
    @staticmethod
    def settle(schedule: DispatchResult, actual_prices: np.ndarray) -> float:
        """Re-evaluate revenue at realised prices, holding the schedule fixed."""
        actual_prices = np.asarray(actual_prices, dtype=float)
        return float(np.sum(actual_prices * schedule.net_mw) * schedule.dt_hours)
