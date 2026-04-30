"use client";

import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";
import { TIME_LABELS } from "@/lib/utils";

interface Props {
  forecastPrices: number[];
  chargeMw:       number[];
  dischargeMw:    number[];
}

const DT = 0.25;

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const rev: number = payload.find((p: any) => p.dataKey === "revenue")?.value ?? 0;
  const cum: number = payload.find((p: any) => p.dataKey === "cumulative")?.value ?? 0;
  return (
    <div className="rounded border border-aegean-700 bg-aegean-900 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-marble-500">{label}</p>
      <p className={`font-semibold ${rev >= 0 ? "text-gold-400" : "text-azure-400"}`}>
        {rev >= 0 ? "Sell income" : "Buy cost"}: {rev >= 0 ? "+" : ""}{rev.toFixed(2)} €
      </p>
      <p className="text-marble-400">Cumulative: +{cum.toFixed(2)} €</p>
    </div>
  );
};

export default function BidChart({ forecastPrices, chargeMw, dischargeMw }: Props) {
  let running = 0;
  const data = forecastPrices.map((price, i) => {
    const net = dischargeMw[i] - chargeMw[i];
    const revenue = Math.round(net * price * DT * 100) / 100;
    running += revenue;
    return {
      time:       i % 8 === 0 ? TIME_LABELS[i] : "",
      fullTime:   TIME_LABELS[i],
      revenue,
      cumulative: Math.round(running * 100) / 100,
    };
  });

  const maxAbs = Math.max(...data.map((d) => Math.abs(d.revenue)), 0.5);
  const maxCum = Math.max(...data.map((d) => d.cumulative), 1);
  const minCum = Math.min(...data.map((d) => d.cumulative), 0);

  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={data} margin={{ top: 4, right: 44, left: 0, bottom: 0 }} barSize={3}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(23,51,83,0.8)" />
        <XAxis
          dataKey="time"
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={{ stroke: "#173353" }}
          tickLine={false}
        />
        <YAxis
          yAxisId="left"
          domain={[-maxAbs * 1.15, maxAbs * 1.15]}
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`}
          width={40}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          domain={[Math.min(minCum * 1.1, 0), maxCum * 1.15]}
          tick={{ fill: "#C8A84B", fontSize: 9 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `€${v.toFixed(0)}`}
          width={38}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine yAxisId="left" y={0} stroke="rgba(23,51,83,1)" strokeWidth={1} />
        <Bar yAxisId="left" dataKey="revenue" radius={[1, 1, 0, 0]}>
          {data.map((d, i) => (
            <Cell
              key={i}
              fill={d.revenue >= 0 ? "#C8A84B" : "#4A7FB5"}
              fillOpacity={0.9}
            />
          ))}
        </Bar>
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="cumulative"
          stroke="#C8A84B"
          strokeWidth={1.5}
          dot={false}
          strokeOpacity={0.75}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
