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
  capacityMwh:    number;
}

const DT = 0.25; // 15-min interval in hours

const CustomTooltip = ({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  const rev  = payload.find((p) => p.dataKey === "revenue")?.value ?? 0;
  const cumul = payload.find((p) => p.dataKey === "cumulative")?.value ?? 0;
  return (
    <div className="rounded border border-aegean-700 bg-aegean-900 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1.5 font-semibold text-marble-300">{label}</p>
      <p className={rev >= 0 ? "text-gold-400" : "text-azure-400"}>
        {rev >= 0 ? "Sell income" : "Buy cost"}: {rev >= 0 ? "+" : ""}{rev.toFixed(2)} €
      </p>
      <p className="mt-0.5 text-marble-500">
        Cumulative: {cumul >= 0 ? "+" : ""}{cumul.toFixed(2)} €
      </p>
    </div>
  );
};

export default function BidChart({ forecastPrices, chargeMw, dischargeMw, capacityMwh: _ }: Props) {
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
  const finalRevenue = data[data.length - 1]?.cumulative ?? 0;

  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={data} margin={{ top: 4, right: 48, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(23,51,83,0.8)" />
        <XAxis
          dataKey="time"
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={{ stroke: "#173353" }}
          tickLine={false}
        />
        {/* Left Y: slot revenue */}
        <YAxis
          yAxisId="bar"
          domain={[-maxAbs * 1.15, maxAbs * 1.15]}
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`}
          width={40}
        />
        {/* Right Y: cumulative */}
        <YAxis
          yAxisId="line"
          orientation="right"
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(0)}€`}
          width={48}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine yAxisId="bar" y={0} stroke="rgba(23,51,83,1)" strokeWidth={1} />

        <Bar yAxisId="bar" dataKey="revenue" barSize={3} radius={[1, 1, 0, 0]}>
          {data.map((d, i) => (
            <Cell
              key={i}
              fill={d.revenue >= 0 ? "#C8A84B" : "#4A7FB5"}
              fillOpacity={0.9}
            />
          ))}
        </Bar>

        <Line
          yAxisId="line"
          type="monotone"
          dataKey="cumulative"
          stroke={finalRevenue >= 0 ? "#C8A84B" : "#C4533A"}
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3, fill: "#C8A84B", stroke: "#0C1A2C", strokeWidth: 2 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
