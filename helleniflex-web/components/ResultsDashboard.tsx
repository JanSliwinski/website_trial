"use client";

import { Download } from "lucide-react";
import type { OptimizeResult } from "@/lib/types";
import KPICards from "./KPICards";
import BidChart from "./charts/BidChart";
import PriceChart from "./charts/PriceChart";
import DispatchChart from "./charts/DispatchChart";
import SoCChart from "./charts/SoCChart";
import { TIME_LABELS } from "@/lib/utils";

interface Props {
  result: OptimizeResult;
  date:   string;
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded border border-aegean-700 bg-aegean-900 p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-marble-200">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-marble-500">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function downloadCSV(result: OptimizeResult, date: string) {
  const rows = [
    "interval,time,price_eur_mwh,charge_mw,discharge_mw,net_mw,slot_revenue_eur,soc_mwh",
    ...result.forecast_prices.map((p, i) => {
      const net = result.net_mw[i];
      const rev = (net * p * 0.25).toFixed(4);
      return [
        i,
        TIME_LABELS[i],
        p.toFixed(2),
        result.charge_mw[i].toFixed(4),
        result.discharge_mw[i].toFixed(4),
        net.toFixed(4),
        rev,
        result.soc_mwh[i].toFixed(4),
      ].join(",");
    }),
  ].join("\n");

  const blob = new Blob([rows], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `helios_bid_${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ResultsDashboard({ result, date }: Props) {
  const totalDischarge = result.discharge_mw.reduce((a, b) => a + b, 0) * 0.25;
  const totalCharge    = result.charge_mw.reduce((a, b) => a + b, 0) * 0.25;
  const peakPrice      = Math.max(...result.forecast_prices).toFixed(1);
  const minPrice       = Math.min(...result.forecast_prices).toFixed(1);
  const totalBidRevenue = result.forecast_prices.reduce(
    (acc, p, i) => acc + result.net_mw[i] * p * 0.25,
    0
  );

  return (
    <div className="animate-fade-up space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-marble-200">
            Dispatch Scenario &middot; {date}
          </h2>
          <p className="mt-0.5 text-xs text-marble-500">
            {result.forecaster} &middot; {result.status}
          </p>
        </div>
        <button
          onClick={() => downloadCSV(result, date)}
          className="flex items-center gap-1.5 rounded border border-aegean-700 bg-aegean-900 px-3 py-1.5 text-xs text-marble-500 hover:text-marble-200 hover:border-aegean-600 transition-all"
        >
          <Download size={11} />
          Export CSV
        </button>
      </div>

      <KPICards result={result} />

      {/* ── BID SCHEDULE ── primary chart */}
      <ChartCard
        title="Scenario Bid Schedule"
        subtitle={`Modelled revenue per 15-min slot · Gold = sell (discharge) · Blue = buy (charge) · Line = cumulative total`}
      >
        <BidChart
          forecastPrices={result.forecast_prices}
          chargeMw={result.charge_mw}
          dischargeMw={result.discharge_mw}
        />
        <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-marble-500">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm bg-gold-500" />
            Sell (discharge income)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm bg-azure-500" />
            Buy (charge cost)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 bg-gold-500" />
            Cumulative revenue
          </span>
          <span className="ml-auto font-semibold text-gold-400">
            Scenario: +{totalBidRevenue.toFixed(2)} €
          </span>
        </div>
      </ChartCard>

      {/* ── PRICE FORECAST ── */}
      <ChartCard
        title="Price Forecast"
        subtitle={`Range ${minPrice} – ${peakPrice} €/MWh · Model-generated input curve`}
      >
        <PriceChart prices={result.forecast_prices} />
      </ChartCard>

      {/* ── DISPATCH + SoC ── side by side */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="Power Schedule"
          subtitle={`${totalDischarge.toFixed(2)} MWh sold  ·  ${totalCharge.toFixed(2)} MWh bought`}
        >
          <DispatchChart chargeMw={result.charge_mw} dischargeMw={result.discharge_mw} />
          <div className="mt-2 flex gap-4 text-xs text-marble-500">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm bg-olive-500" />Discharge
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm bg-azure-500" />Charge
            </span>
          </div>
        </ChartCard>

        <ChartCard
          title="State of Charge"
          subtitle={`Operating window ${result.soc_min_mwh.toFixed(2)} – ${result.soc_max_mwh.toFixed(2)} MWh`}
        >
          <SoCChart
            socMwh={result.soc_mwh}
            socMinMwh={result.soc_min_mwh}
            socMaxMwh={result.soc_max_mwh}
            capacityMwh={result.capacity_mwh}
          />
        </ChartCard>
      </div>

      {/* Footer stats */}
      <div className="grid grid-cols-3 gap-3 rounded border border-aegean-700 bg-aegean-900 p-4">
        {[
          ["Charge throughput",   `${totalCharge.toFixed(2)} MWh`],
          ["Discharge throughput",`${totalDischarge.toFixed(2)} MWh`],
          ["Discharge / charge",  `${(totalDischarge / (totalCharge || 1) * 100).toFixed(1)}%`],
        ].map(([label, value]) => (
          <div key={label} className="text-center">
            <p className="helios-label">{label}</p>
            <p className="mt-1.5 text-sm font-semibold text-marble-200">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
