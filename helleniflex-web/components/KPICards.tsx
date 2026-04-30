"use client";

import { TrendingUp, Zap, RotateCcw } from "lucide-react";
import type { OptimizeResult } from "@/lib/types";
import { fmtEur } from "@/lib/utils";

interface CardProps {
  icon:   React.ReactNode;
  label:  string;
  value:  string;
  sub?:   string;
  sub2?:  string;
  accent: "gold" | "olive" | "azure";
}

const ACCENT = {
  gold:  { text: "text-gold-400",  bg: "bg-gold-500/10",  border: "border-l-gold-500"  },
  olive: { text: "text-olive-500", bg: "bg-olive-500/10", border: "border-l-olive-500" },
  azure: { text: "text-azure-400", bg: "bg-azure-500/10", border: "border-l-azure-500" },
};

function Card({ icon, label, value, sub, sub2, accent }: CardProps) {
  const { text, bg, border } = ACCENT[accent];
  return (
    <div className={`rounded border-l-2 border border-aegean-700 ${border} ${bg} p-4`}>
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="helios-label">{label}</p>
          <p className={`mt-2 text-xl font-bold tracking-tight ${text}`}>{value}</p>
          {sub && <p className="mt-0.5 text-[11px] text-marble-500">{sub}</p>}
          {sub2 && <p className="text-[11px] text-marble-500">{sub2}</p>}
        </div>
        <div className={`ml-2 shrink-0 rounded p-1.5 ${bg} ${text}`}>{icon}</div>
      </div>
    </div>
  );
}

export default function KPICards({ result }: { result: OptimizeResult }) {
  const dischargedMwh = result.discharge_mw.reduce((a, b) => a + b, 0) * 0.25;
  const chargedMwh    = result.charge_mw.reduce((a, b) => a + b, 0) * 0.25;
  const annualised    = result.net_revenue_eur * 365 / result.capacity_mwh;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Card
        icon={<TrendingUp size={16} />}
        label="Net Revenue"
        value={fmtEur(result.net_revenue_eur)}
        sub={`Gross ${fmtEur(result.revenue_eur)}`}
        sub2={`~${fmtEur(annualised)}/MWh·yr annualised`}
        accent="gold"
      />
      <Card
        icon={<Zap size={16} />}
        label="Energy Moved"
        value={`${(chargedMwh + dischargedMwh).toFixed(2)} MWh`}
        sub={`${chargedMwh.toFixed(2)} MWh charged`}
        accent="olive"
      />
      <Card
        icon={<RotateCcw size={16} />}
        label="Cycles"
        value={result.cycles.toFixed(2)}
        sub={`${dischargedMwh.toFixed(2)} MWh dispatched`}
        accent="azure"
      />
    </div>
  );
}
