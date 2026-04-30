"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { SOC_TIME_LABELS } from "@/lib/utils";

interface Props {
  socMwh: number[];
  socMinMwh: number;
  socMaxMwh: number;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-700 bg-navy-900 px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      <p className="font-semibold text-amber-400">
        {payload[0].value.toFixed(3)} MWh
      </p>
    </div>
  );
};

export default function SoCChart({ socMwh, socMinMwh, socMaxMwh }: Props) {
  const data = socMwh.map((soc, i) => ({
    time: i % 8 === 0 ? SOC_TIME_LABELS[i] : "",
    soc: Math.round(soc * 1000) / 1000,
  }));

  const padding = (socMaxMwh - socMinMwh) * 0.1;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="socGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#fb923c" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#fb923c" stopOpacity={0.02} />
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
          domain={[Math.max(0, socMinMwh - padding), socMaxMwh + padding]}
          tick={{ fill: "#64748b", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => v.toFixed(1)}
          width={36}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine
          y={socMinMwh}
          stroke="rgba(248,113,113,0.4)"
          strokeDasharray="4 4"
          label={{ value: "min", fill: "#f87171", fontSize: 9, position: "insideTopRight" }}
        />
        <ReferenceLine
          y={socMaxMwh}
          stroke="rgba(74,222,128,0.4)"
          strokeDasharray="4 4"
          label={{ value: "max", fill: "#4ade80", fontSize: 9, position: "insideTopRight" }}
        />
        <Area
          type="monotone"
          dataKey="soc"
          stroke="#fb923c"
          strokeWidth={1.5}
          fill="url(#socGrad)"
          dot={false}
          activeDot={{ r: 3, fill: "#fb923c", stroke: "#0d1526", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
