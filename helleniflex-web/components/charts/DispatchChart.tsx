"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, ReferenceLine,
} from "recharts";
import { TIME_LABELS } from "@/lib/utils";

interface Props {
  chargeMw: number[];
  dischargeMw: number[];
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const net = payload[0]?.value ?? 0;
  return (
    <div className="rounded-lg border border-slate-700 bg-navy-900 px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      <p className={`font-semibold ${net >= 0 ? "text-emerald-400" : "text-red-400"}`}>
        {net >= 0 ? "Discharge" : "Charge"}: {Math.abs(net).toFixed(3)} MW
      </p>
    </div>
  );
};

export default function DispatchChart({ chargeMw, dischargeMw }: Props) {
  const data = chargeMw.map((c, i) => ({
    time: i % 8 === 0 ? TIME_LABELS[i] : "",
    fullTime: TIME_LABELS[i],
    net: Math.round((dischargeMw[i] - c) * 1000) / 1000,
  }));

  const maxAbs = Math.max(...data.map((d) => Math.abs(d.net)), 0.1);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barSize={3}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" />
        <XAxis
          dataKey="time"
          tick={{ fill: "#64748b", fontSize: 10 }}
          axisLine={{ stroke: "#1e293b" }}
          tickLine={false}
        />
        <YAxis
          domain={[-maxAbs * 1.1, maxAbs * 1.1]}
          tick={{ fill: "#64748b", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => v.toFixed(1)}
          width={36}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0} stroke="rgba(148,163,184,0.3)" />
        <Bar dataKey="net" radius={[1, 1, 0, 0]}>
          {data.map((d, i) => (
            <Cell
              key={i}
              fill={d.net >= 0 ? "#4ade80" : "#f87171"}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
