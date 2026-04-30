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

export interface OptimizeResult {
  forecast_prices:     number[];
  charge_mw:           number[];
  discharge_mw:        number[];
  net_mw:              number[];
  soc_mwh:             number[];      // 97 values (includes t=0)
  soc_min_mwh:         number;
  soc_max_mwh:         number;
  capacity_mwh:        number;        // total battery capacity
  revenue_eur:         number;
  net_revenue_eur:     number;
  cycles:              number;
  status:              string;
  forecaster:          string;
}
