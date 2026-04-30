"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { SOC_TIME_LABELS } from "@/lib/utils";

interface Props {
  socMwh:      number[];
  socMinMwh:   number;
  socMaxMwh:   number;
  capacityMwh: number;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-aegean-700 bg-aegean-900 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-marble-500">{label}</p>
      <p className="font-semibold text-gold-400">{payload[0].value.toFixed(1)}%</p>
    </div>
  );
};

export default function SoCChart({ socMwh, socMinMwh, socMaxMwh, capacityMwh }: Props) {
  const toPct = (mwh: number) =>
    Math.round((Math.min(socMaxMwh, Math.max(socMinMwh, mwh)) / capacityMwh) * 1000) / 10;

  const minPct = Math.round((socMinMwh / capacityMwh) * 1000) / 10;
  const maxPct = Math.round((socMaxMwh / capacityMwh) * 1000) / 10;

  const data = socMwh.map((soc, i) => ({
    time: i % 8 === 0 ? SOC_TIME_LABELS[i] : "",
    soc:  toPct(soc),
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
        <YAxis
          domain={[minPct, maxPct]}
          tick={{ fill: "#7A8FA8", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v}%`}
          width={38}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine
          y={minPct}
          stroke="rgba(196,83,58,0.5)"
          strokeDasharray="4 4"
          label={{ value: `${minPct}%`, fill: "#C4533A", fontSize: 9, position: "insideTopRight" }}
        />
        <ReferenceLine
          y={maxPct}
          stroke="rgba(76,175,130,0.5)"
          strokeDasharray="4 4"
          label={{ value: `${maxPct}%`, fill: "#4CAF82", fontSize: 9, position: "insideTopRight" }}
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
