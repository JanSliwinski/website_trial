"use client";

import Link from "next/link";
import { Sun, ArrowLeft, Activity, ShieldCheck, Waves } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const PRICE_SIGNAL = [
  { time: "00:00", price: 82, spread: 18 },
  { time: "03:00", price: 64, spread: 31 },
  { time: "06:00", price: 71, spread: 24 },
  { time: "09:00", price: 112, spread: 42 },
  { time: "12:00", price: 48, spread: 56 },
  { time: "15:00", price: 54, spread: 49 },
  { time: "18:00", price: 146, spread: 74 },
  { time: "21:00", price: 128, spread: 61 },
];

const DISPATCH_PROFILE = [
  { label: "00", charge: 12, discharge: 0 },
  { label: "03", charge: 26, discharge: 0 },
  { label: "06", charge: 9, discharge: 5 },
  { label: "09", charge: 0, discharge: 24 },
  { label: "12", charge: 31, discharge: 0 },
  { label: "15", charge: 18, discharge: 0 },
  { label: "18", charge: 0, discharge: 34 },
  { label: "21", charge: 0, discharge: 22 },
];

const RISK_CURVE = [
  { day: "Mon", volatility: 38, headroom: 72 },
  { day: "Tue", volatility: 44, headroom: 68 },
  { day: "Wed", volatility: 57, headroom: 61 },
  { day: "Thu", volatility: 51, headroom: 64 },
  { day: "Fri", volatility: 66, headroom: 55 },
  { day: "Sat", volatility: 42, headroom: 70 },
  { day: "Sun", volatility: 35, headroom: 76 },
];

const CARDS = [
  { label: "Verified Backtest", value: "Not loaded", sub: "No hard-coded historical claims" },
  { label: "Data Policy", value: "Transparent", sub: "Demo scenarios stay labelled" },
  { label: "Greek DAM Focus", value: "Ready", sub: "Built for HEnEx/ENTSO-E feeds" },
  { label: "Optimization", value: "MILP", sub: "15-minute battery dispatch" },
];

function Panel({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded border border-azure-500/25 bg-aegean-900/90 p-5 shadow-2xl shadow-aegean-950/30">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="helios-label text-azure-300">{eyebrow}</p>
          <h2 className="mt-1 text-sm font-semibold uppercase tracking-widest text-marble-100">
            {title}
          </h2>
        </div>
        <Waves size={17} className="text-azure-300" />
      </div>
      {children}
    </section>
  );
}

export default function BacktestPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-aegean-950">
      <div
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(248,245,238,0.05) 1px,transparent 1px)," +
            "linear-gradient(90deg,rgba(13,94,175,0.18) 1px,transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />
      <div className="pointer-events-none fixed left-0 top-0 z-0 h-2 w-full bg-gradient-to-r from-azure-500 via-marble-50 to-azure-500" />

      <div className="relative z-10">
        <nav className="border-b border-azure-500/30 bg-aegean-950/90 backdrop-blur-sm">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="flex h-8 w-8 items-center justify-center rounded border border-azure-300/50 bg-azure-500/15 transition-colors group-hover:bg-azure-500/25">
                <Sun size={15} className="text-marble-50" />
              </div>
              <span className="text-sm font-bold tracking-[0.12em] uppercase text-marble-50 group-hover:text-azure-300 transition-colors">
                Helios
              </span>
              <span className="hidden rounded border border-azure-300/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-azure-300 sm:block">
                GR · DAM
              </span>
            </Link>

            <div className="flex items-center gap-1">
              <Link
                href="/"
                className="rounded px-3 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-200 transition-colors"
              >
                Forecast
              </Link>
              <span className="rounded border border-azure-300/40 bg-azure-500/15 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-azure-300">
                Analysis
              </span>
            </div>

            <div className="hidden items-center gap-2 text-xs text-marble-500 sm:flex">
              <ShieldCheck size={13} className="text-azure-300" />
              Evidence-ready workspace
            </div>
          </div>
        </nav>

        <main className="mx-auto max-w-7xl px-6 py-8">
          <div className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <Link
                href="/"
                className="mb-3 inline-flex items-center gap-1.5 text-xs text-marble-500 hover:text-marble-200 transition-colors"
              >
                <ArrowLeft size={12} />
                Back to Forecast
              </Link>
              <h1 className="text-3xl font-bold tracking-tight text-marble-50 sm:text-5xl">
                Greek Battery Market Analysis
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-marble-400">
                A sharper analysis layer for storage bids, price spreads, dispatch behaviour, and risk.
                Verified historical performance is intentionally hidden until a real market dataset is connected.
              </p>
            </div>
            <div className="rounded border border-azure-300/30 bg-marble-50 px-4 py-3 text-aegean-950">
              <p className="text-[10px] font-bold uppercase tracking-widest text-azure-700">
                Trust mode
              </p>
              <p className="mt-1 text-sm font-bold">No synthetic capture-rate claims</p>
            </div>
          </div>

          <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {CARDS.map(({ label, value, sub }) => (
              <div key={label} className="rounded border border-azure-500/25 bg-aegean-900 p-4">
                <p className="helios-label">{label}</p>
                <p className="mt-2 text-xl font-bold text-marble-50">{value}</p>
                <p className="mt-0.5 text-[11px] text-marble-500">{sub}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Panel eyebrow="Demo scenario" title="Price Signal & Intraday Spread">
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={PRICE_SIGNAL} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="priceBlue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8CB4DE" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#8CB4DE" stopOpacity={0.03} />
                    </linearGradient>
                    <linearGradient id="spreadWhite" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#F8F5EE" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#F8F5EE" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                  <XAxis dataKey="time" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                  <YAxis tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={36} />
                  <Tooltip contentStyle={{ background: "#0C1A2C", border: "1px solid #4A7FB5", borderRadius: 4 }} />
                  <Area type="monotone" dataKey="price" stroke="#8CB4DE" strokeWidth={2} fill="url(#priceBlue)" />
                  <Area type="monotone" dataKey="spread" stroke="#F8F5EE" strokeWidth={1.5} fill="url(#spreadWhite)" />
                </AreaChart>
              </ResponsiveContainer>
            </Panel>

            <Panel eyebrow="Demo scenario" title="Charge / Discharge Shape">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={DISPATCH_PROFILE} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                  <XAxis dataKey="label" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                  <YAxis tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={36} />
                  <Tooltip contentStyle={{ background: "#0C1A2C", border: "1px solid #4A7FB5", borderRadius: 4 }} />
                  <Bar dataKey="charge" fill="#8CB4DE" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="discharge" fill="#F8F5EE" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Panel>

            <Panel eyebrow="Risk view" title="Volatility vs Operating Headroom">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={RISK_CURVE} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.25)" />
                  <XAxis dataKey="day" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                  <YAxis tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} axisLine={false} width={36} />
                  <Tooltip contentStyle={{ background: "#0C1A2C", border: "1px solid #4A7FB5", borderRadius: 4 }} />
                  <Line type="monotone" dataKey="volatility" stroke="#8CB4DE" strokeWidth={2.5} dot={false} />
                  <Line type="monotone" dataKey="headroom" stroke="#F8F5EE" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Panel>

            <Panel eyebrow="Go-to-market" title="What This Page Can Prove Next">
              <div className="grid h-[260px] content-center gap-3">
                {[
                  ["1", "Connect verified price history", "Replace demo curves with auditable HEnEx/ENTSO-E intervals."],
                  ["2", "Run rolling backtests", "Show revenue, cycles, spread use, and constraint compliance."],
                  ["3", "Publish investor-ready evidence", "Export charts and CSVs without synthetic performance claims."],
                ].map(([step, title, body]) => (
                  <div key={step} className="flex gap-3 rounded border border-azure-500/20 bg-aegean-800/70 p-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-marble-50 text-sm font-black text-azure-700">
                      {step}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-marble-100">{title}</p>
                      <p className="mt-0.5 text-xs leading-5 text-marble-500">{body}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </div>

          <div className="mt-6 rounded border border-azure-500/25 bg-aegean-900 p-5">
            <div className="mb-3 flex items-center gap-2">
              <Activity size={15} className="text-azure-300" />
              <h2 className="text-sm font-semibold uppercase tracking-widest text-marble-100">
                Methodology Boundary
              </h2>
            </div>
            <p className="text-sm leading-6 text-marble-500">
              This screen is a marketable analysis shell, not a validated historical scoreboard. The old
              forecaster comparison, perfect-foresight capture rate, April 2026 scorecard, and annualized
              revenue claims were removed because they were based on synthetic/demo data.
            </p>
          </div>
        </main>

        <footer className="mt-16 border-t border-azure-500/25 py-6 text-center text-xs text-marble-600">
          Helios · Greek battery analytics · Forecasts and dispatch plans for review
        </footer>
      </div>
    </div>
  );
}
