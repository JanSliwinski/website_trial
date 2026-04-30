"use client";

import { TrendingUp, Target, RotateCcw } from "lucide-react";
import type { OptimizeResult } from "@/lib/types";
import { fmtEur, fmtPct } from "@/lib/utils";

interface CardProps {
  icon:   React.ReactNode;
  label:  string;
  value:  string;
  sub?:   string;
  accent: "gold" | "olive" | "azure";
}

const ACCENT = {
  gold:  { text: "text-gold-400",  bg: "bg-gold-500/10",  border: "border-l-gold-500"  },
  olive: { text: "text-olive-500", bg: "bg-olive-500/10", border: "border-l-olive-500" },
  azure: { text: "text-azure-400", bg: "bg-azure-500/10", border: "border-l-azure-500" },
};

function Card({ icon, label, value, sub, accent }: CardProps) {
  const { text, bg, border } = ACCENT[accent];
  return (
    <div className={`rounded border-l-2 border border-aegean-700 ${border} ${bg} p-4`}>
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="helios-label">{label}</p>
          <p className={`mt-2 text-xl font-bold tracking-tight ${text}`}>{value}</p>
          {sub && <p className="mt-0.5 text-[11px] text-marble-500">{sub}</p>}
        </div>
        <div className={`ml-2 shrink-0 rounded p-1.5 ${bg} ${text}`}>{icon}</div>
      </div>
    </div>
  );
}

export default function KPICards({ result }: { result: OptimizeResult }) {
  const dischargedMwh = result.discharge_mw.reduce((a, b) => a + b, 0) * 0.25;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Card
        icon={<TrendingUp size={16} />}
        label="Net Revenue"
        value={fmtEur(result.net_revenue_eur)}
        sub={`Gross ${fmtEur(result.revenue_eur)}`}
        accent="gold"
      />
      <Card
        icon={<Target size={16} />}
        label="Capture Rate"
        value={fmtPct(result.capture_rate)}
        sub={result.capture_rate_window ?? "vs. perfect foresight"}
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
