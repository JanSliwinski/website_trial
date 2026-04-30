"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { TIME_LABELS } from "@/lib/utils";

interface Props {
  prices: number[];
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-700 bg-navy-900 px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      <p className="font-semibold text-cyan-400">
        {payload[0].value.toFixed(1)} €/MWh
      </p>
    </div>
  );
};

export default function PriceChart({ prices }: Props) {
  const data = prices.map((price, i) => ({
    time: i % 8 === 0 ? TIME_LABELS[i] : "",
    fullTime: TIME_LABELS[i],
    price: Math.round(price * 10) / 10,
  }));

  const min = Math.floor(Math.min(...prices) / 10) * 10;
  const max = Math.ceil(Math.max(...prices) / 10) * 10;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" />
        <XAxis
          dataKey="time"
          tick={{ fill: "#64748b", fontSize: 10 }}
          axisLine={{ stroke: "#1e293b" }}
          tickLine={false}
        />
        <YAxis
          domain={[min, max]}
          tick={{ fill: "#64748b", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v}`}
          width={36}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0} stroke="rgba(148,163,184,0.2)" strokeDasharray="4 4" />
        <Area
          type="monotone"
          dataKey="price"
          stroke="#22d3ee"
          strokeWidth={1.5}
          fill="url(#priceGrad)"
          dot={false}
          activeDot={{ r: 3, fill: "#22d3ee", stroke: "#0d1526", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
