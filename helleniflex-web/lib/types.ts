export interface BatteryConfig {
  power_mw:               number;
  capacity_mwh:           number;
  eta_charge:             number;
  eta_discharge:          number;
  soc_min_pct:            number;
  soc_max_pct:            number;
  initial_soc_pct:        number;
  daily_cycle_limit:      number | null;
  cycle_cost_eur_per_mwh: number;
}

export interface BatteryPreset {
  id:      string;
  name:    string;
  label:   string;
  battery: BatteryConfig;
}

export interface OptimizeRequest {
  date:    string;
  battery: BatteryConfig;
}

export interface OptimizeResult {
  forecast_prices:     number[];      // 96 values, €/MWh
  charge_mw:           number[];      // 96 values
  discharge_mw:        number[];      // 96 values
  net_mw:              number[];      // 96 values
  soc_mwh:             number[];      // 97 values (includes t=0)
  soc_min_mwh:         number;
  soc_max_mwh:         number;
  revenue_eur:         number;        // gross dispatch revenue
  net_revenue_eur:     number;        // after degradation cost
  capture_rate:        number | null; // % of perfect foresight oracle
  capture_rate_window: string | null; // e.g. "same-day oracle (synthetic)"
  cycles:              number;        // equivalent full cycles
  status:              string;        // "optimal" | "optimal_inaccurate" | …
  forecaster:          string;        // model name used
}
