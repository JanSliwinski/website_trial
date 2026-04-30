"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { SOC_TIME_LABELS } from "@/lib/utils";

interface Props {
  socMwh:    number[];
  socMinMwh: number;
  socMaxMwh: number;
}

const CustomTooltip = ({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-aegean-700 bg-aegean-900 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-marble-500">{label}</p>
      <p className="font-semibold text-gold-400">{payload[0].value.toFixed(3)} MWh</p>
    </div>
  );
};

export default function SoCChart({ socMwh, socMinMwh, socMaxMwh }: Props) {
  // Clamp values to the declared operating window — fixes the >90% display bug
  const data = socMwh.map((soc, i) => ({
    time: i % 8 === 0 ? SOC_TIME_LABELS[i] : "",
    soc:  Math.round(Math.min(socMaxMwh, Math.max(socMinMwh, soc)) * 1000) / 1000,
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="socGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#C8A84B" stopOpacity={0.35} />
            <stop offset="95%" stopColor="#C8A84B" stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(23,51,83,0.8)" />
        <XAxis
          dataKey="time"
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={{ stroke: "#173353" }}
          tickLine={false}
        />
        {/* Y-axis domain hard-capped to [socMinMwh, socMaxMwh] — no padding beyond the constraint */}
        <YAxis
          domain={[socMinMwh, socMaxMwh]}
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => v.toFixed(1)}
          width={36}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine
          y={socMinMwh}
          stroke="rgba(196,83,58,0.5)"
          strokeDasharray="4 4"
          label={{ value: "min", fill: "#C4533A", fontSize: 9, position: "insideTopRight" }}
        />
        <ReferenceLine
          y={socMaxMwh}
          stroke="rgba(76,175,130,0.5)"
          strokeDasharray="4 4"
          label={{ value: "max", fill: "#4CAF82", fontSize: 9, position: "insideTopRight" }}
        />
        <Area
          type="monotone"
          dataKey="soc"
          stroke="#C8A84B"
          strokeWidth={1.5}
          fill="url(#socGrad)"
          dot={false}
          activeDot={{ r: 3, fill: "#C8A84B", stroke: "#0C1A2C", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
