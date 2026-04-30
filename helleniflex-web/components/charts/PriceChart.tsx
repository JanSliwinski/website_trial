"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { TIME_LABELS } from "@/lib/utils";

interface Props { prices: number[] }

const CustomTooltip = ({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-aegean-700 bg-aegean-900 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-marble-500">{label}</p>
      <p className="font-semibold text-gold-400">{payload[0].value.toFixed(1)} €/MWh</p>
    </div>
  );
};

export default function PriceChart({ prices }: Props) {
  const data = prices.map((price, i) => ({
    time:     i % 8 === 0 ? TIME_LABELS[i] : "",
    fullTime: TIME_LABELS[i],
    price:    Math.round(price * 10) / 10,
  }));

  const min = Math.floor(Math.min(...prices) / 10) * 10;
  const max = Math.ceil(Math.max(...prices) / 10) * 10;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#C8A84B" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#C8A84B" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(23,51,83,0.8)" />
        <XAxis
          dataKey="time"
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={{ stroke: "#173353" }}
          tickLine={false}
        />
        <YAxis
          domain={[min, max]}
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v}`}
          width={36}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0} stroke="rgba(23,51,83,1)" strokeDasharray="4 4" />
        <Area
          type="monotone"
          dataKey="price"
          stroke="#C8A84B"
          strokeWidth={1.5}
          fill="url(#priceGrad)"
          dot={false}
          activeDot={{ r: 3, fill: "#C8A84B", stroke: "#0C1A2C", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
