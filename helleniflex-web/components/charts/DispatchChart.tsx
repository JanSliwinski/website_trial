"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, ReferenceLine,
} from "recharts";
import { TIME_LABELS } from "@/lib/utils";

interface Props {
  chargeMw:    number[];
  dischargeMw: number[];
}

const CustomTooltip = ({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  const net = payload[0]?.value ?? 0;
  return (
    <div className="rounded border border-aegean-700 bg-aegean-900 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-marble-500">{label}</p>
      <p className={`font-semibold ${net >= 0 ? "text-olive-500" : "text-azure-400"}`}>
        {net >= 0 ? "Discharge" : "Charge"}: {Math.abs(net).toFixed(3)} MW
      </p>
    </div>
  );
};

export default function DispatchChart({ chargeMw, dischargeMw }: Props) {
  const data = chargeMw.map((c, i) => ({
    time:     i % 8 === 0 ? TIME_LABELS[i] : "",
    fullTime: TIME_LABELS[i],
    net:      Math.round((dischargeMw[i] - c) * 1000) / 1000,
  }));

  const maxAbs = Math.max(...data.map((d) => Math.abs(d.net)), 0.1);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barSize={3}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(23,51,83,0.8)" />
        <XAxis
          dataKey="time"
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={{ stroke: "#173353" }}
          tickLine={false}
        />
        <YAxis
          domain={[-maxAbs * 1.1, maxAbs * 1.1]}
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => v.toFixed(1)}
          width={36}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0} stroke="rgba(23,51,83,1)" />
        <Bar dataKey="net" radius={[1, 1, 0, 0]}>
          {data.map((d, i) => (
            <Cell
              key={i}
              fill={d.net >= 0 ? "#4CAF82" : "#4A7FB5"}
              fillOpacity={0.9}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
