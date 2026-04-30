"use client";

import { useState, useEffect } from "react";
import { Zap, Calendar, ChevronDown, ChevronUp, Play } from "lucide-react";
import type { BatteryConfig, BatteryPreset } from "@/lib/types";
import { fetchPresets } from "@/lib/api";
import { DATE_MIN, DATE_MAX, cn } from "@/lib/utils";

interface Props {
  onSubmit: (date: string, battery: BatteryConfig) => void;
  loading: boolean;
}

const SLIDER = "w-full accent-cyan-400 h-1 cursor-pointer";

function Slider({
  label, value, min, max, step, unit, onChange,
}: {
  label: string; value: number; min: number; max: number; step: number;
  unit: string; onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono text-slate-300">{value.toFixed(step < 0.1 ? 2 : step < 1 ? 1 : 0)}{unit}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className={SLIDER}
      />
    </div>
  );
}

export default function BatteryForm({ onSubmit, loading }: Props) {
  const [presets, setPresets] = useState<BatteryPreset[]>([]);
  const [activePreset, setActivePreset] = useState("2h");
  const [date, setDate] = useState("2025-06-15");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [battery, setBattery] = useState<BatteryConfig>({
    power_mw: 1.0,
    capacity_mwh: 2.0,
    eta_charge: 0.94,
    eta_discharge: 0.94,
    soc_min_pct: 0.10,
    soc_max_pct: 0.90,
    initial_soc_pct: 0.50,
    daily_cycle_limit: 1.5,
    cycle_cost_eur_per_mwh: 3.0,
  });

  useEffect(() => {
    fetchPresets()
      .then((ps) => {
        setPresets(ps);
        const p2h = ps.find((p) => p.id === "2h");
        if (p2h) setBattery(p2h.battery);
      })
      .catch(() => {});
  }, []);

  function applyPreset(id: string) {
    setActivePreset(id);
    const p = presets.find((p) => p.id === id);
    if (p) setBattery(p.battery);
  }

  function update(key: keyof BatteryConfig, val: number | null) {
    setBattery((b) => ({ ...b, [key]: val }));
  }

  const rte = Math.round(battery.eta_charge * battery.eta_discharge * 100);

  return (
    <div className="rounded-2xl border border-slate-800 bg-navy-900 p-6 space-y-5">
      {/* Presets */}
      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-widest text-slate-500">Asset</p>
        <div className="grid grid-cols-4 gap-1.5 rounded-xl bg-navy-950 p-1">
          {(presets.length ? presets : [
            { id: "1h", name: "1h" }, { id: "2h", name: "2h" },
            { id: "4h", name: "4h" }, { id: "utility", name: "Utility" },
          ] as BatteryPreset[]).map((p) => (
            <button
              key={p.id}
              onClick={() => applyPreset(p.id)}
              className={cn(
                "rounded-lg py-1.5 text-xs font-medium transition-all",
                activePreset === p.id
                  ? "bg-cyan-500 text-navy-950 shadow-lg shadow-cyan-500/20"
                  : "text-slate-400 hover:text-slate-200"
              )}
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      {/* Date */}
      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-widest text-slate-500">
          Optimisation Date
        </p>
        <div className="relative">
          <Calendar size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="date"
            value={date}
            min={DATE_MIN}
            max={DATE_MAX}
            onChange={(e) => setDate(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-navy-800 py-2 pl-8 pr-3 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500/30 [color-scheme:dark]"
          />
        </div>
      </div>

      {/* Core sliders */}
      <div className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Specifications</p>
        <Slider label="Power" value={battery.power_mw} min={0.1} max={100} step={0.1} unit=" MW"
          onChange={(v) => update("power_mw", v)} />
        <Slider label="Capacity" value={battery.capacity_mwh} min={0.1} max={400} step={0.1} unit=" MWh"
          onChange={(v) => update("capacity_mwh", v)} />
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Round-trip Efficiency</span>
            <span className="font-mono text-slate-300">{rte}%</span>
          </div>
          <input
            type="range" min={50} max={99} step={1} value={rte}
            onChange={(e) => {
              const η = parseFloat(e.target.value) / 100;
              const ηOW = Math.sqrt(η);
              update("eta_charge", ηOW);
              update("eta_discharge", ηOW);
            }}
            className={SLIDER}
          />
        </div>
        <Slider label="Degradation Cost" value={battery.cycle_cost_eur_per_mwh} min={0} max={20} step={0.5} unit=" €/MWh"
          onChange={(v) => update("cycle_cost_eur_per_mwh", v)} />
      </div>

      {/* Advanced toggle */}
      <button
        onClick={() => setShowAdvanced((v) => !v)}
        className="flex w-full items-center justify-between text-xs text-slate-500 hover:text-slate-300 transition-colors"
      >
        <span>Advanced</span>
        {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {showAdvanced && (
        <div className="space-y-3 border-t border-slate-800 pt-4">
          <Slider label="SoC Min" value={battery.soc_min_pct * 100} min={0} max={40} step={1} unit="%"
            onChange={(v) => update("soc_min_pct", v / 100)} />
          <Slider label="SoC Max" value={battery.soc_max_pct * 100} min={60} max={100} step={1} unit="%"
            onChange={(v) => update("soc_max_pct", v / 100)} />
          <Slider label="Initial SoC" value={battery.initial_soc_pct * 100} min={10} max={90} step={1} unit="%"
            onChange={(v) => update("initial_soc_pct", v / 100)} />
          <Slider
            label="Daily Cycle Limit"
            value={battery.daily_cycle_limit ?? 2.0}
            min={0.5} max={4} step={0.25} unit="×"
            onChange={(v) => update("daily_cycle_limit", v)}
          />
        </div>
      )}

      {/* Submit */}
      <button
        onClick={() => onSubmit(date, battery)}
        disabled={loading}
        className={cn(
          "relative w-full overflow-hidden rounded-xl py-3 text-sm font-semibold tracking-wide transition-all",
          loading
            ? "cursor-not-allowed bg-slate-700 text-slate-500"
            : "bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-lg shadow-cyan-500/25 hover:from-cyan-400 hover:to-blue-400 hover:shadow-cyan-400/30 active:scale-[0.98]"
        )}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-slate-300" />
            Solving MILP…
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <Zap size={15} />
            Optimize Dispatch
          </span>
        )}
      </button>
    </div>
  );
}
