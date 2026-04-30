"use client";

import { Download } from "lucide-react";
import type { OptimizeResult } from "@/lib/types";
import KPICards from "./KPICards";
import PriceChart from "./charts/PriceChart";
import DispatchChart from "./charts/DispatchChart";
import SoCChart from "./charts/SoCChart";
import { TIME_LABELS, SOC_TIME_LABELS } from "@/lib/utils";

interface Props {
  result: OptimizeResult;
  date: string;
}

function ChartCard({ title, subtitle, children }: {
  title: string; subtitle?: string; children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-navy-900 p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function downloadCSV(result: OptimizeResult, date: string) {
  const rows = [
    "interval,time,price_eur_mwh,charge_mw,discharge_mw,net_mw,soc_mwh",
    ...result.forecast_prices.map((p, i) =>
      [
        i,
        TIME_LABELS[i],
        p.toFixed(2),
        result.charge_mw[i].toFixed(4),
        result.discharge_mw[i].toFixed(4),
        result.net_mw[i].toFixed(4),
        result.soc_mwh[i].toFixed(4),
      ].join(",")
    ),
  ].join("\n");

  const blob = new Blob([rows], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `helleniflex_${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ResultsDashboard({ result, date }: Props) {
  const totalDischarge = result.discharge_mw.reduce((a, b) => a + b, 0) * 0.25;
  const totalCharge = result.charge_mw.reduce((a, b) => a + b, 0) * 0.25;
  const peakPrice = Math.max(...result.forecast_prices).toFixed(1);
  const minPrice = Math.min(...result.forecast_prices).toFixed(1);

  return (
    <div className="animate-fade-up space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">
            Dispatch Plan · {date}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {result.forecaster} · {result.status}
          </p>
        </div>
        <button
          onClick={() => downloadCSV(result, date)}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-navy-900 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:border-slate-600 transition-all"
        >
          <Download size={12} />
          CSV
        </button>
      </div>

      <KPICards result={result} />

      {/* Price forecast */}
      <ChartCard
        title="Price Forecast"
        subtitle={`Range: ${minPrice} – ${peakPrice} €/MWh · Smart Ridge forecaster`}
      >
        <PriceChart prices={result.forecast_prices} />
      </ChartCard>

      {/* Dispatch + SoC */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="Dispatch Schedule"
          subtitle={`↑ ${totalDischarge.toFixed(2)} MWh sold  ↓ ${totalCharge.toFixed(2)} MWh bought`}
        >
          <DispatchChart
            chargeMw={result.charge_mw}
            dischargeMw={result.discharge_mw}
          />
          <div className="mt-2 flex gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-sm bg-emerald-400" />Discharge
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-sm bg-red-400" />Charge
            </span>
          </div>
        </ChartCard>

        <ChartCard
          title="State of Charge"
          subtitle={`Operating window: ${result.soc_min_mwh.toFixed(2)} – ${result.soc_max_mwh.toFixed(2)} MWh`}
        >
          <SoCChart
            socMwh={result.soc_mwh}
            socMinMwh={result.soc_min_mwh}
            socMaxMwh={result.soc_max_mwh}
          />
        </ChartCard>
      </div>

      {/* Footer stats */}
      <div className="grid grid-cols-3 gap-3 rounded-xl border border-slate-800 bg-navy-900 p-4">
        {[
          ["Charge throughput", `${totalCharge.toFixed(2)} MWh`],
          ["Discharge throughput", `${totalDischarge.toFixed(2)} MWh`],
          ["Round-trip eff.", `${(totalDischarge / (totalCharge || 1) * 100).toFixed(1)}%`],
        ].map(([label, value]) => (
          <div key={label} className="text-center">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="mt-0.5 text-sm font-semibold text-slate-200">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
