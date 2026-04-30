"use client";

import { TrendingUp, Target, RotateCcw, Cpu } from "lucide-react";
import type { OptimizeResult } from "@/lib/types";
import { fmtEur, fmtPct } from "@/lib/utils";

interface Props {
  result: OptimizeResult;
}

interface CardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  color: string;
}

function Card({ icon, label, value, sub, color }: CardProps) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-navy-900 p-5">
      <div className={`absolute inset-0 opacity-5 bg-gradient-to-br ${color}`} />
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-slate-500">{label}</p>
          <p className={`mt-2 text-2xl font-bold tracking-tight ${color.includes("cyan") ? "text-cyan-400" : color.includes("emerald") ? "text-emerald-400" : color.includes("amber") ? "text-amber-400" : "text-violet-400"}`}>
            {value}
          </p>
          {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
        </div>
        <div className={`rounded-lg p-2 ${color.includes("cyan") ? "bg-cyan-400/10 text-cyan-400" : color.includes("emerald") ? "bg-emerald-400/10 text-emerald-400" : color.includes("amber") ? "bg-amber-400/10 text-amber-400" : "bg-violet-400/10 text-violet-400"}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

export default function KPICards({ result }: Props) {
  const grossMw = result.charge_mw.reduce((a, b) => a + b, 0) * 0.25;
  const dischargedMwh = result.discharge_mw.reduce((a, b) => a + b, 0) * 0.25;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card
        icon={<TrendingUp size={18} />}
        label="Net Revenue"
        value={fmtEur(result.net_revenue_eur)}
        sub={`Gross ${fmtEur(result.revenue_eur)}`}
        color="from-emerald-500 to-cyan-500"
      />
      <Card
        icon={<Target size={18} />}
        label="Capture Rate"
        value={fmtPct(result.capture_rate)}
        sub="vs. perfect foresight"
        color="from-cyan-500 to-blue-500"
      />
      <Card
        icon={<RotateCcw size={18} />}
        label="Cycles"
        value={result.cycles.toFixed(2)}
        sub={`${dischargedMwh.toFixed(2)} MWh dispatched`}
        color="from-amber-500 to-orange-500"
      />
      <Card
        icon={<Cpu size={18} />}
        label="Model"
        value={result.status === "optimal" ? "Optimal" : result.status}
        sub={result.forecaster}
        color="from-violet-500 to-purple-500"
      />
    </div>
  );
}
