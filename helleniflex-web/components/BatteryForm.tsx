"use client";

import { useState, useEffect } from "react";
import { Sun, ChevronDown, ChevronUp } from "lucide-react";
import type { BatteryConfig, BatteryPreset } from "@/lib/types";
import { fetchPresets } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  onSubmit: (battery: BatteryConfig) => void;
  loading:  boolean;
}

function NumInput({
  label, value, min, max, step, unit, onChange,
}: {
  label: string; value: number; min: number; max: number;
  step: number; unit: string; onChange: (v: number) => void;
}) {
  const decimals = step < 0.1 ? 2 : step < 1 ? 1 : 0;
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="helios-label flex-1">{label}</span>
      <div className="flex items-center gap-1.5">
        <input
          type="number"
          value={value.toFixed(decimals)}
          min={min} max={max} step={step}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            if (!isNaN(v)) onChange(Math.min(max, Math.max(min, v)));
          }}
          className="w-20 rounded border border-aegean-700 bg-aegean-950 px-2 py-1.5 text-right text-sm font-mono text-marble-100 focus:border-gold-500 focus:outline-none focus:ring-1 focus:ring-gold-500/30 transition-colors"
        />
        <span className="w-9 text-xs text-marble-500">{unit}</span>
      </div>
    </div>
  );
}

export default function BatteryForm({ onSubmit, loading }: Props) {
  const [presets, setPresets]           = useState<BatteryPreset[]>([]);
  const [activePreset, setActivePreset] = useState("2h");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [battery, setBattery]           = useState<BatteryConfig>({
    power_mw: 1.0, capacity_mwh: 2.0, eta_charge: 0.94, eta_discharge: 0.94,
    soc_min_pct: 0.10, soc_max_pct: 0.90, initial_soc_pct: 0.50,
    daily_cycle_limit: 1.5, cycle_cost_eur_per_mwh: 3.0,
  });

  useEffect(() => {
    fetchPresets().then((ps) => {
      setPresets(ps);
      const p2h = ps.find((p) => p.id === "2h");
      if (p2h) setBattery(p2h.battery);
    }).catch(() => {});
  }, []);

  function applyPreset(id: string) {
    setActivePreset(id);
    const p = presets.find((p) => p.id === id);
    if (p) setBattery(p.battery);
  }

  function update<K extends keyof BatteryConfig>(key: K, val: BatteryConfig[K]) {
    setBattery((b) => ({ ...b, [key]: val }));
  }

  const rte = Math.round(battery.eta_charge * battery.eta_discharge * 100);

  return (
    <div className="rounded border border-aegean-700 bg-aegean-900 p-4 sm:p-5 space-y-5">
      {/* Presets */}
      <div>
        <p className="helios-label mb-2">Asset Preset</p>
        <div className="grid grid-cols-4 gap-1 rounded bg-aegean-950 p-1">
          {(presets.length
            ? presets
            : [{ id:"1h",name:"1h" },{ id:"2h",name:"2h" },{ id:"4h",name:"4h" },{ id:"utility",name:"Utility" }] as BatteryPreset[]
          ).map((p) => (
            <button
              key={p.id}
              onClick={() => applyPreset(p.id)}
              className={cn(
                "rounded py-1.5 text-xs font-semibold tracking-wide transition-all",
                activePreset === p.id
                  ? "bg-gold-500 text-aegean-950 shadow-sm"
                  : "text-marble-500 hover:text-marble-200"
              )}
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      {/* Core specs */}
      <div className="space-y-3">
        <p className="helios-label">Specifications</p>
        <NumInput label="Power"           value={battery.power_mw}               min={0.1} max={500}  step={0.1}  unit="MW"    onChange={(v) => update("power_mw", v)} />
        <NumInput label="Capacity"        value={battery.capacity_mwh}           min={0.1} max={2000} step={0.1}  unit="MWh"   onChange={(v) => update("capacity_mwh", v)} />
        <NumInput label="Round-trip Eff." value={rte}                            min={50}  max={99}   step={1}    unit="%"     onChange={(v) => { const η = Math.sqrt(v/100); update("eta_charge",η); update("eta_discharge",η); }} />
        <NumInput label="Degradation"     value={battery.cycle_cost_eur_per_mwh} min={0}   max={30}   step={0.5}  unit="€/MWh" onChange={(v) => update("cycle_cost_eur_per_mwh", v)} />
      </div>

      {/* Advanced toggle */}
      <button
        onClick={() => setShowAdvanced((v) => !v)}
        className="flex w-full items-center justify-between text-xs text-marble-600 hover:text-marble-300 transition-colors"
      >
        <span className="helios-label">Advanced</span>
        {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>

      {showAdvanced && (
        <div className="space-y-3 border-t border-aegean-700 pt-4">
          <NumInput label="SoC Min"           value={battery.soc_min_pct * 100}        min={0}   max={40} step={1}    unit="%" onChange={(v) => update("soc_min_pct", v/100)} />
          <NumInput label="SoC Max"           value={battery.soc_max_pct * 100}        min={60}  max={100} step={1}   unit="%" onChange={(v) => update("soc_max_pct", v/100)} />
          <NumInput label="Initial SoC"       value={battery.initial_soc_pct * 100}    min={10}  max={90} step={1}    unit="%" onChange={(v) => update("initial_soc_pct", v/100)} />
          <NumInput label="Daily Cycle Limit" value={battery.daily_cycle_limit ?? 2.0} min={0.5} max={4}  step={0.25} unit="×" onChange={(v) => update("daily_cycle_limit", v)} />
        </div>
      )}

      {/* Submit */}
      <button
        onClick={() => onSubmit(battery)}
        disabled={loading}
        className={cn(
          "w-full rounded py-3 text-sm font-bold tracking-[0.08em] uppercase transition-all",
          loading
            ? "cursor-not-allowed bg-aegean-800 text-marble-500"
            : "bg-gold-500 text-aegean-950 hover:bg-gold-400 active:scale-[0.99] shadow-sm"
        )}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-aegean-800 border-t-marble-400" />
            Solving&hellip;
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <Sun size={14} />
            Optimise Dispatch
          </span>
        )}
      </button>
    </div>
  );
}
