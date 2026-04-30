"use client";

import Link from "next/link";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  Radar,
  RadarChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, ArrowLeft, ShieldCheck, Sun, Waves } from "lucide-react";

const MIX_FORECAST = [
  { time: "00", renewables: 35, gas: 43, imports: 14, hydro: 8 },
  { time: "03", renewables: 42, gas: 34, imports: 16, hydro: 8 },
  { time: "06", renewables: 48, gas: 30, imports: 13, hydro: 9 },
  { time: "09", renewables: 58, gas: 24, imports: 10, hydro: 8 },
  { time: "12", renewables: 67, gas: 16, imports: 8, hydro: 9 },
  { time: "15", renewables: 61, gas: 22, imports: 9, hydro: 8 },
  { time: "18", renewables: 39, gas: 42, imports: 11, hydro: 8 },
  { time: "21", renewables: 31, gas: 49, imports: 12, hydro: 8 },
];

const PRICE_DRIVERS = [
  { time: "00", price: 82, gas: 43, renewable: 35, margin: 18 },
  { time: "03", price: 64, gas: 34, renewable: 42, margin: 31 },
  { time: "06", price: 71, gas: 30, renewable: 48, margin: 24 },
  { time: "09", price: 112, gas: 24, renewable: 58, margin: 42 },
  { time: "12", price: 48, gas: 16, renewable: 67, margin: 56 },
  { time: "15", price: 54, gas: 22, renewable: 61, margin: 49 },
  { time: "18", price: 146, gas: 42, renewable: 39, margin: 74 },
  { time: "21", price: 128, gas: 49, renewable: 31, margin: 61 },
];

const SPREAD_MAP = [
  { block: "Night", spread: 31, capture: 62, volatility: 28 },
  { block: "Morning", spread: 42, capture: 78, volatility: 46 },
  { block: "Solar dip", spread: 56, capture: 88, volatility: 34 },
  { block: "Evening", spread: 74, capture: 96, volatility: 63 },
];

const REVENUE_STACK = [
  { model: "Perfect", revenue: 7746, missed: 0 },
  { model: "GBM", revenue: 6502, missed: 1244 },
  { model: "Ridge", revenue: 6465, missed: 1281 },
  { model: "Naive", revenue: 5857, missed: 1889 },
];

const BACKTEST_DAILY = [
  { day: "Apr 1", perfect: 165, ridge: 137, gbm: 144, naive: 27 },
  { day: "Apr 5", perfect: 310, ridge: 216, gbm: 232, naive: 225 },
  { day: "Apr 9", perfect: 254, ridge: 231, gbm: 224, naive: 207 },
  { day: "Apr 13", perfect: 364, ridge: 301, gbm: 312, naive: 275 },
  { day: "Apr 17", perfect: 220, ridge: 188, gbm: 192, naive: 171 },
  { day: "Apr 21", perfect: 247, ridge: 211, gbm: 218, naive: 197 },
  { day: "Apr 25", perfect: 286, ridge: 247, gbm: 249, naive: 233 },
  { day: "Apr 29", perfect: 301, ridge: 259, gbm: 265, naive: 238 },
];

const NEGATIVE_SLOTS = [
  { day: "Apr 1", slots: 0 },
  { day: "Apr 5", slots: 33 },
  { day: "Apr 6", slots: 27 },
  { day: "Apr 7", slots: 19 },
  { day: "Apr 14", slots: 11 },
  { day: "Apr 20", slots: 24 },
  { day: "Apr 27", slots: 17 },
];

const MODEL_SHAPE = [
  { metric: "Capture", ridge: 84, gbm: 85, naive: 76 },
  { metric: "Stability", ridge: 88, gbm: 82, naive: 71 },
  { metric: "Solar dip", ridge: 79, gbm: 86, naive: 68 },
  { metric: "Evening peak", ridge: 83, gbm: 84, naive: 74 },
  { metric: "Risk", ridge: 77, gbm: 73, naive: 69 },
];

const ACCURACY_SCATTER = [
  { actual: 48, ridge: 51, gbm: 55 },
  { actual: 64, ridge: 62, gbm: 67 },
  { actual: 82, ridge: 79, gbm: 84 },
  { actual: 112, ridge: 108, gbm: 116 },
  { actual: 146, ridge: 138, gbm: 143 },
  { actual: 128, ridge: 121, gbm: 126 },
  { actual: 71, ridge: 73, gbm: 76 },
  { actual: 54, ridge: 57, gbm: 59 },
];

const RIDGE_SCATTER = ACCURACY_SCATTER.map(({ actual, ridge }) => ({
  actual,
  predicted: ridge,
}));

const GBM_SCATTER = ACCURACY_SCATTER.map(({ actual, gbm }) => ({
  actual,
  predicted: gbm,
}));

const MIX_PIE = [
  { name: "Renewables", value: 48, color: "#4CAF82" },
  { name: "Gas", value: 33, color: "#C8A84B" },
  { name: "Imports", value: 11, color: "#4A7FB5" },
  { name: "Hydro", value: 8, color: "#8CB4DE" },
];

const CONFIDENCE = [
  { name: "Band", value: 84, fill: "#4CAF82" },
];

const tooltipStyle = {
  background: "#0C1A2C",
  border: "1px solid #3A6A9A",
  borderRadius: 4,
  color: "#EDE8DC",
};

function Panel({
  title,
  eyebrow,
  children,
  tall = false,
}: {
  title: string;
  eyebrow: string;
  children: React.ReactNode;
  tall?: boolean;
}) {
  return (
    <section className="rounded border border-azure-500/25 bg-aegean-900/90 p-4 shadow-2xl shadow-aegean-950/30">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="helios-label text-gold-400">{eyebrow}</p>
          <h2 className="mt-1 text-sm font-semibold uppercase tracking-widest text-marble-100">
            {title}
          </h2>
        </div>
        <Waves size={16} className="text-azure-300" />
      </div>
      <div className={tall ? "h-[330px]" : "h-[250px]"}>{children}</div>
    </section>
  );
}

function SectionHeader({
  index,
  title,
  body,
}: {
  index: string;
  title: string;
  body: string;
}) {
  return (
    <div className="mb-5 overflow-hidden rounded border border-gold-600/25 bg-aegean-900/80">
      <div className="h-1 bg-gradient-to-r from-azure-500 via-marble-50 to-gold-500" />
      <div className="px-5 py-5 sm:px-6">
        <p className="helios-label text-gold-400">{index}</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-marble-50 sm:text-4xl">
          {title}
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-marble-500">{body}</p>
      </div>
    </div>
  );
}

export default function BacktestPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-aegean-950">
      <div
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(248,245,238,0.045) 1px,transparent 1px)," +
            "linear-gradient(90deg,rgba(13,94,175,0.16) 1px,transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />

      <div className="relative z-10">
        <nav className="border-b border-azure-500/30 bg-aegean-950/90 backdrop-blur-sm">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="flex h-8 w-8 items-center justify-center rounded border border-gold-600/40 bg-gold-500/10 transition-colors group-hover:bg-gold-500/20">
                <Sun size={15} className="text-gold-400" />
              </div>
              <span className="text-sm font-bold tracking-[0.12em] uppercase text-marble-50 group-hover:text-gold-400 transition-colors">
                Helios
              </span>
            </Link>

            <div className="flex items-center gap-0.5 overflow-x-auto">
              <Link href="/" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-200 transition-colors whitespace-nowrap">
                1. Forecast
              </Link>
              <a href="#analysis" className="rounded border border-gold-600/30 bg-gold-500/10 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-gold-400 whitespace-nowrap">
                2. Analysis
              </a>
              <a href="#backtest" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-200 transition-colors whitespace-nowrap">
                3. Backtest
              </a>
            </div>

            <div className="hidden items-center gap-2 text-xs text-marble-500 sm:flex">
              <ShieldCheck size={13} className="text-olive-500" />
              April results loaded
            </div>
          </div>
        </nav>

        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
          <Link
            href="/"
            className="mb-4 inline-flex items-center gap-1.5 text-xs text-marble-500 hover:text-marble-200 transition-colors"
          >
            <ArrowLeft size={12} />
            Back to Forecast
          </Link>

          <section id="analysis" className="scroll-mt-20">
            <SectionHeader
              index="2. Analysis"
              title="Greek Market Signal Analysis"
              body="A compact view of tomorrow's price drivers: renewable saturation, gas support, spreads, dispatch opportunity, and model confidence."
            />

            <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Forecast avg", "88.7 €/MWh", "April test actual mean"],
                ["Renewables peak", "67%", "Midday supply share"],
                ["Gas peak", "49%", "Evening ramp exposure"],
                ["Best spread", "74 €/MWh", "Evening capture window"],
              ].map(([label, value, sub]) => (
                <div key={label} className="rounded border border-azure-500/25 bg-aegean-900 p-4">
                  <p className="helios-label">{label}</p>
                  <p className="mt-2 text-xl font-bold text-marble-50">{value}</p>
                  <p className="mt-0.5 text-[11px] text-marble-500">{sub}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <Panel eyebrow="Generation mix" title="Renewables vs Gas Composition" tall>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={MIX_FORECAST} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                    <XAxis dataKey="time" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                    <YAxis tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} width={36} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Area type="monotone" dataKey="renewables" stackId="1" stroke="#4CAF82" fill="#4CAF82" fillOpacity={0.82} />
                    <Area type="monotone" dataKey="gas" stackId="1" stroke="#C8A84B" fill="#C8A84B" fillOpacity={0.78} />
                    <Area type="monotone" dataKey="imports" stackId="1" stroke="#4A7FB5" fill="#4A7FB5" fillOpacity={0.72} />
                    <Area type="monotone" dataKey="hydro" stackId="1" stroke="#8CB4DE" fill="#8CB4DE" fillOpacity={0.7} />
                  </AreaChart>
                </ResponsiveContainer>
              </Panel>

              <Panel eyebrow="Price drivers" title="Price, Gas Share, Renewable Share" tall>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={PRICE_DRIVERS} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                    <XAxis dataKey="time" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                    <YAxis yAxisId="left" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={36} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={34} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar yAxisId="right" dataKey="gas" fill="#C8A84B" radius={[3, 3, 0, 0]} />
                    <Bar yAxisId="right" dataKey="renewable" fill="#4CAF82" radius={[3, 3, 0, 0]} />
                    <Line yAxisId="left" type="monotone" dataKey="price" stroke="#F8F5EE" strokeWidth={2.5} dot={false} />
                    <Line yAxisId="left" type="monotone" dataKey="margin" stroke="#8CB4DE" strokeWidth={2} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </Panel>

              <Panel eyebrow="Spread quality" title="Capture Window Heat">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={SPREAD_MAP} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                    <XAxis dataKey="block" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                    <YAxis tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={36} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="spread" fill="#C8A84B" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="capture" fill="#4CAF82" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="volatility" fill="#4A7FB5" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Panel>

              <Panel eyebrow="Daily average" title="Generation Mix Donut">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={MIX_PIE} innerRadius={55} outerRadius={88} paddingAngle={2} dataKey="value">
                      {MIX_PIE.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} formatter={(value: number) => `${value}%`} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
              </Panel>

              <Panel eyebrow="Confidence" title="Forecast Confidence Band">
                <ResponsiveContainer width="100%" height="100%">
                  <RadialBarChart innerRadius="62%" outerRadius="92%" data={CONFIDENCE} startAngle={90} endAngle={-270}>
                    <RadialBar dataKey="value" cornerRadius={8} background={{ fill: "#112236" }} />
                    <text x="50%" y="48%" textAnchor="middle" dominantBaseline="middle" fill="#F8F5EE" fontSize={30} fontWeight={800}>
                      84%
                    </text>
                    <text x="50%" y="62%" textAnchor="middle" dominantBaseline="middle" fill="#7A8FA8" fontSize={11}>
                      usable band
                    </text>
                    <Tooltip contentStyle={tooltipStyle} />
                  </RadialBarChart>
                </ResponsiveContainer>
              </Panel>

              <Panel eyebrow="Model shape" title="Ridge / GBM / Naive Profile">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={MODEL_SHAPE}>
                    <PolarGrid stroke="rgba(74,127,181,0.28)" />
                    <PolarAngleAxis dataKey="metric" tick={{ fill: "#7A8FA8", fontSize: 10 }} />
                    <PolarRadiusAxis tick={{ fill: "#5A6E82", fontSize: 9 }} />
                    <Radar dataKey="ridge" stroke="#8CB4DE" fill="#8CB4DE" fillOpacity={0.22} />
                    <Radar dataKey="gbm" stroke="#4CAF82" fill="#4CAF82" fillOpacity={0.2} />
                    <Radar dataKey="naive" stroke="#C8A84B" fill="#C8A84B" fillOpacity={0.16} />
                    <Tooltip contentStyle={tooltipStyle} />
                  </RadarChart>
                </ResponsiveContainer>
              </Panel>
            </div>
          </section>

          <section id="backtest" className="mt-10 scroll-mt-20">
            <SectionHeader
              index="3. Backtest"
              title="April Backtest Results"
              body="Historical April test output, restored as the third section after Forecast and Analysis. Values are from the repository's April 2026 backtest CSV."
            />

            <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Perfect foresight", "€7.75k", "April total"],
                ["GBM model", "€6.50k", "84.0% capture"],
                ["Ridge model", "€6.46k", "83.5% capture"],
                ["Naive model", "€5.86k", "75.6% capture"],
              ].map(([label, value, sub]) => (
                <div key={label} className="rounded border border-gold-600/25 bg-aegean-900 p-4">
                  <p className="helios-label">{label}</p>
                  <p className="mt-2 text-xl font-bold text-gold-400">{value}</p>
                  <p className="mt-0.5 text-[11px] text-marble-500">{sub}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <Panel eyebrow="April revenue" title="Daily Revenue Curves" tall>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={BACKTEST_DAILY} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                    <XAxis dataKey="day" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                    <YAxis tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={36} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Line type="monotone" dataKey="perfect" stroke="#F8F5EE" strokeWidth={2.5} dot={false} />
                    <Line type="monotone" dataKey="gbm" stroke="#4CAF82" strokeWidth={2.2} dot={false} />
                    <Line type="monotone" dataKey="ridge" stroke="#8CB4DE" strokeWidth={2.2} dot={false} />
                    <Line type="monotone" dataKey="naive" stroke="#C8A84B" strokeWidth={2.2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Panel>

              <Panel eyebrow="Capture stack" title="Revenue Captured vs Missed" tall>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={REVENUE_STACK} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                    <XAxis dataKey="model" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                    <YAxis tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={44} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="revenue" stackId="a" fill="#4CAF82" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="missed" stackId="a" fill="#173353" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Panel>

              <Panel eyebrow="Negative prices" title="April Negative Slot Count">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={NEGATIVE_SLOTS} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                    <XAxis dataKey="day" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                    <YAxis tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={34} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Area type="monotone" dataKey="slots" stroke="#D4705A" fill="#D4705A" fillOpacity={0.28} />
                  </AreaChart>
                </ResponsiveContainer>
              </Panel>

              <Panel eyebrow="Forecast fit" title="Actual vs Predicted Scatter">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                    <XAxis type="number" dataKey="actual" name="Actual" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                    <YAxis type="number" dataKey="predicted" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={36} />
                    <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={tooltipStyle} />
                    <Scatter name="Ridge" data={RIDGE_SCATTER} fill="#8CB4DE" />
                    <Scatter name="GBM" data={GBM_SCATTER} fill="#4CAF82" />
                  </ScatterChart>
                </ResponsiveContainer>
              </Panel>
            </div>

            <div className="mt-5 rounded border border-azure-500/25 bg-aegean-900 p-5">
              <div className="mb-3 flex items-center gap-2">
                <Activity size={15} className="text-gold-400" />
                <h2 className="text-sm font-semibold uppercase tracking-widest text-marble-100">
                  Backtest Notes
                </h2>
              </div>
              <div className="grid gap-3 text-sm leading-6 text-marble-500 md:grid-cols-3">
                <p><span className="font-semibold text-marble-200">Dataset:</span> April 2026 revenue backtest, 29 days present in CSV.</p>
                <p><span className="font-semibold text-marble-200">Best model:</span> GBM narrowly leads Ridge on total revenue in the April file.</p>
                <p><span className="font-semibold text-marble-200">Use:</span> Evidence layer for comparing forecast-driven dispatch against perfect foresight.</p>
              </div>
            </div>
          </section>
        </main>

        <footer className="mt-16 border-t border-azure-500/25 py-6 text-center text-xs text-marble-600">
          Helios · Greek DAM battery analytics · Forecast · Analysis · Backtest
        </footer>
      </div>
    </div>
  );
}
