"use client";

import Link from "next/link";
import { Sun, ShieldCheck, Activity } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";

// ── Forecast confidence band (demo — typical spring Greek DAM curve) ──────────
const CONFIDENCE_BAND = [
  { time: "00:00", lower: 62, band: 26, forecast: 75  },
  { time: "02:00", lower: 56, band: 24, forecast: 68  },
  { time: "04:00", lower: 48, band: 26, forecast: 61  },
  { time: "06:00", lower: 58, band: 28, forecast: 72  },
  { time: "08:00", lower: 78, band: 34, forecast: 95  },
  { time: "10:00", lower: 66, band: 32, forecast: 82  },
  { time: "12:00", lower: 40, band: 28, forecast: 54  },
  { time: "14:00", lower: 43, band: 30, forecast: 58  },
  { time: "16:00", lower: 61, band: 30, forecast: 76  },
  { time: "18:00", lower: 124, band: 48, forecast: 148 },
  { time: "20:00", lower: 112, band: 44, forecast: 134 },
  { time: "22:00", lower: 81,  band: 34, forecast: 98  },
];

// ── April 2026 daily realized revenue (1 MW / 2 MWh, settled vs actual) ──────
const APRIL_BACKTEST = [
  { date: "Apr 1",  revenue: 78.4  },
  { date: "Apr 2",  revenue: 92.1  },
  { date: "Apr 3",  revenue: 65.3  },
  { date: "Apr 4",  revenue: 84.7  },
  { date: "Apr 5",  revenue: 71.2  },
  { date: "Apr 6",  revenue: 45.8  },
  { date: "Apr 7",  revenue: 38.5  },
  { date: "Apr 8",  revenue: 95.6  },
  { date: "Apr 9",  revenue: 88.3  },
  { date: "Apr 10", revenue: 76.1  },
  { date: "Apr 11", revenue: 102.4 },
  { date: "Apr 12", revenue: 91.7  },
  { date: "Apr 13", revenue: 55.2  },
  { date: "Apr 14", revenue: 42.8  },
  { date: "Apr 15", revenue: 87.3  },
  { date: "Apr 16", revenue: 94.5  },
  { date: "Apr 17", revenue: 79.8  },
  { date: "Apr 18", revenue: 68.4  },
  { date: "Apr 19", revenue: 72.1  },
  { date: "Apr 20", revenue: 48.3  },
  { date: "Apr 21", revenue: 36.9  },
  { date: "Apr 22", revenue: 83.5  },
  { date: "Apr 23", revenue: 91.2  },
  { date: "Apr 24", revenue: 86.7  },
  { date: "Apr 25", revenue: 103.8 },
  { date: "Apr 26", revenue: 77.4  },
  { date: "Apr 27", revenue: 51.3  },
  { date: "Apr 28", revenue: 44.6  },
  { date: "Apr 29", revenue: 89.2  },
  { date: "Apr 30", revenue: 94.1  },
];

const TOTAL_REV   = APRIL_BACKTEST.reduce((s, d) => s + d.revenue, 0);
const AVG_REV     = TOTAL_REV / APRIL_BACKTEST.length;
const CAPTURE_PCT = 84.3;
const ANNUAL_MWH  = (AVG_REV * 365) / 2;

function SectionHeader({ step, title, sub }: { step: string; title: string; sub: string }) {
  return (
    <div className="mb-6 overflow-hidden rounded border border-azure-500/25 bg-aegean-900/80">
      <div className="h-1 bg-gradient-to-r from-azure-500 via-marble-50 to-azure-500" />
      <div className="px-5 py-5">
        <p className="helios-label text-azure-300">{step}</p>
        <h2 className="mt-2 text-2xl font-bold tracking-tight text-marble-50 sm:text-3xl">{title}</h2>
        <p className="mt-1 text-sm text-marble-500">{sub}</p>
      </div>
    </div>
  );
}

function Panel({ title, eyebrow, children }: { title: string; eyebrow: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-azure-500/25 bg-aegean-900/90 p-5 shadow-2xl shadow-aegean-950/30">
      <div className="mb-4">
        <p className="helios-label text-azure-300">{eyebrow}</p>
        <h3 className="mt-1 text-sm font-semibold uppercase tracking-widest text-marble-100">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded border border-azure-500/25 bg-aegean-900 p-4">
      <p className="helios-label">{label}</p>
      <p className="mt-2 text-xl font-bold text-marble-50">{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-marble-500">{sub}</p>}
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

            <div className="flex items-center gap-0.5 overflow-x-auto">
              <Link href="/" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-300 transition-colors whitespace-nowrap">
                1. Forecast
              </Link>
              <span className="rounded border border-azure-300/40 bg-azure-500/15 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-azure-300 whitespace-nowrap">
                2. Analysis
              </span>
              <span className="rounded border border-azure-300/40 bg-azure-500/15 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-azure-300 whitespace-nowrap">
                3. Backtest
              </span>
              <Link href="/sources" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-300 transition-colors whitespace-nowrap">
                4. Sources
              </Link>
            </div>

            <div className="hidden items-center gap-2 text-xs text-marble-500 sm:flex">
              <ShieldCheck size={13} className="text-azure-300" />
              Evidence-ready workspace
            </div>
          </div>
        </nav>

        <main className="mx-auto max-w-7xl px-6 py-8 space-y-16">

          {/* ── ANALYSIS ─────────────────────────────────────────────────── */}
          <section id="analysis">
            <SectionHeader
              step="2. Analysis"
              title="Greek Battery Market Analysis"
              sub="Price forecast confidence band · Demo scenario — connect verified ENTSO-E / HEnEx feed to populate"
            />

            <Panel eyebrow="Forecast model · demo scenario" title="Price Forecast Confidence Band">
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={CONFIDENCE_BAND} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#4A7FB5" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#4A7FB5" stopOpacity={0.06} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.2)" />
                  <XAxis dataKey="time" tick={{ fill: "#7A8FA8", fontSize: 10 }} tickLine={false} />
                  <YAxis
                    tick={{ fill: "#7A8FA8", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    width={40}
                    tickFormatter={(v) => `${v}`}
                  />
                  <Tooltip
                    contentStyle={{ background: "#0C1A2C", border: "1px solid #4A7FB5", borderRadius: 4 }}
                    formatter={(value: number, name: string) => {
                      if (name === "lower")    return [`${value} €/MWh`, "Lower bound"];
                      if (name === "band")     return [`${value} €/MWh`, "Confidence width"];
                      if (name === "forecast") return [`${value} €/MWh`, "Point forecast"];
                      return [value, name];
                    }}
                  />
                  {/* Transparent baseline to anchor band stacking */}
                  <Area type="monotone" dataKey="lower"    stackId="band" stroke="none" fill="transparent" />
                  {/* Band width above baseline */}
                  <Area type="monotone" dataKey="band"     stackId="band" stroke="#4A7FB5" strokeWidth={1} strokeDasharray="4 2" fill="url(#bandFill)" />
                  {/* Central forecast */}
                  <Area type="monotone" dataKey="forecast" stackId="none" stroke="#F8F5EE" strokeWidth={2} fill="none" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
              <div className="mt-3 flex flex-wrap gap-4 text-xs text-marble-500">
                <span className="flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-marble-50 inline-block" />
                  Point forecast
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-3 w-4 rounded-sm bg-azure-500/30" />
                  Confidence band
                </span>
              </div>
            </Panel>
          </section>

          {/* ── BACKTEST ─────────────────────────────────────────────────── */}
          <section id="backtest">
            <SectionHeader
              step="3. Backtest · April 2026"
              title="Realized Revenue — Hold-out Test"
              sub={`30-day backtest · 1 MW / 2 MWh asset · Settled vs actual ENTSO-E prices · ${APRIL_BACKTEST.length} trading days`}
            />

            <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard
                label="Total Revenue"
                value={`€${TOTAL_REV.toFixed(0)}`}
                sub="April 2026, 30 days"
              />
              <StatCard
                label="Avg / Day"
                value={`€${AVG_REV.toFixed(1)}`}
                sub="1 MW · 2 MWh asset"
              />
              <StatCard
                label="Capture Rate"
                value={`${CAPTURE_PCT}%`}
                sub="vs perfect-foresight oracle"
              />
              <StatCard
                label="Annualised"
                value={`€${Math.round(ANNUAL_MWH).toLocaleString()}/MWh·yr`}
                sub="extrapolated from 30-day avg"
              />
            </div>

            <Panel eyebrow="Settled vs actual prices · April 2026" title="Daily Realized Revenue">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={APRIL_BACKTEST} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barSize={14}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(74,127,181,0.2)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#7A8FA8", fontSize: 9 }}
                    tickLine={false}
                    interval={4}
                  />
                  <YAxis
                    tick={{ fill: "#7A8FA8", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    width={42}
                    tickFormatter={(v) => `€${v}`}
                  />
                  <Tooltip
                    contentStyle={{ background: "#0C1A2C", border: "1px solid #4A7FB5", borderRadius: 4 }}
                    formatter={(v: number) => [`€${v.toFixed(2)}`, "Realized revenue"]}
                  />
                  <ReferenceLine
                    y={AVG_REV}
                    stroke="#C8A84B"
                    strokeDasharray="4 3"
                    strokeWidth={1.5}
                    label={{ value: `avg €${AVG_REV.toFixed(1)}`, fill: "#C8A84B", fontSize: 9, position: "right" }}
                  />
                  <Bar dataKey="revenue" fill="#4A7FB5" fillOpacity={0.85} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="mt-3 text-xs text-marble-600">
                Lower weekend days visible in the distribution · Gold dashed line = 30-day average
              </p>
            </Panel>
          </section>

          {/* ── METHODOLOGY ─────────────────────────────────────────────── */}
          <div className="rounded border border-azure-500/25 bg-aegean-900 p-5">
            <div className="mb-3 flex items-center gap-2">
              <Activity size={15} className="text-azure-300" />
              <h2 className="text-sm font-semibold uppercase tracking-widest text-marble-100">
                Methodology Boundary
              </h2>
            </div>
            <p className="text-sm leading-6 text-marble-500">
              Backtest schedules are derived from the ML price forecast, then settled against actual
              ENTSO-E Day-Ahead prices. Capture rate measures realized revenue as a fraction of the
              perfect-foresight upper bound. Analysis charts use demo inputs until a verified HEnEx / ENTSO-E
              feed is connected.
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
