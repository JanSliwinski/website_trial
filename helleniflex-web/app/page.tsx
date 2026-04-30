"use client";

import { useState } from "react";
import Link from "next/link";
import { Sun, TrendingUp, Loader2 } from "lucide-react";
import type { BatteryConfig, OptimizeResult } from "@/lib/types";
import { runOptimize } from "@/lib/api";
import BatteryForm from "@/components/BatteryForm";
import ResultsDashboard from "@/components/ResultsDashboard";

function getTomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatDateLong(iso: string): string {
  return new Date(iso + "T12:00:00Z").toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
}

const TOMORROW = getTomorrow();

export default function Home() {
  const [result, setResult]   = useState<OptimizeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function handleSubmit(battery: BatteryConfig) {
    setLoading(true);
    setError(null);
    try {
      const res = await runOptimize(TOMORROW, battery);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Optimisation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Gold-grid background */}
      <div
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(200,168,75,0.04) 1px,transparent 1px)," +
            "linear-gradient(90deg,rgba(200,168,75,0.04) 1px,transparent 1px)",
          backgroundSize: "56px 56px",
        }}
      />
      <div className="pointer-events-none fixed left-1/3 top-0 z-0 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-aegean-700/10 blur-[180px]" />

      <div className="relative z-10">
        {/* Navigation */}
        <nav className="border-b border-aegean-700/60 bg-aegean-950/90 backdrop-blur-sm">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
            <Link href="/" className="flex items-center gap-3 group shrink-0">
              <div className="flex h-10 w-10 items-center justify-center rounded border border-gold-600/40 bg-gold-500/10 transition-colors group-hover:bg-gold-500/20">
                <Sun size={22} className="text-gold-400" />
              </div>
              <span className="text-base font-bold tracking-[0.12em] uppercase text-marble-100 group-hover:text-gold-400 transition-colors">
                Helios
              </span>
              <span className="hidden rounded border border-gold-600/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-gold-500 md:block">
                GR · DAM
              </span>
            </Link>

            <div className="flex items-center gap-0.5 overflow-x-auto">
              <span className="rounded border border-gold-600/30 bg-gold-500/10 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-gold-400 whitespace-nowrap">
                1. Forecast
              </span>
              <Link href="/backtest#analysis" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-300 transition-colors whitespace-nowrap">2. Analysis</Link>
              <Link href="/backtest#backtest" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-300 transition-colors whitespace-nowrap">3. Backtest</Link>
              <Link href="/sources" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-300 transition-colors whitespace-nowrap">4. Sources</Link>
            </div>

            <div className="hidden items-center gap-4 text-xs text-marble-600 lg:flex">
              <span>Greek Day-Ahead Market</span>
              <span className="flex items-center gap-1 text-olive-500">
                <TrendingUp size={11} />MILP Optimal
              </span>
            </div>
          </div>
        </nav>

        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
          {/* Page header */}
          <div className="mb-6 overflow-hidden rounded border border-gold-600/25 bg-aegean-900/80 sm:mb-7">
            <div className="h-1 bg-gradient-to-r from-azure-500 via-marble-50 to-gold-500" />
            <div className="px-5 py-5 sm:px-6">
              <p className="helios-label text-gold-400">1. Forecast</p>
              <h1 className="mt-2 text-2xl font-bold tracking-tight text-marble-50 sm:text-3xl lg:text-4xl">
                Forecast Price First, Then Battery Dispatch
              </h1>
              <p className="mt-2 text-sm text-marble-500">
                Greek day-ahead price curve &middot;{" "}
                <span className="text-marble-300">{formatDateLong(TOMORROW)}</span>
              </p>
            </div>
          </div>

          {/* Main grid */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-[300px_1fr]">
            <div className="lg:sticky lg:top-6 lg:self-start">
              <BatteryForm onSubmit={handleSubmit} loading={loading} />
            </div>

            <div>
              {error && (
                <div className="mb-4 rounded border border-terra-500/40 bg-terra-500/10 px-4 py-3 text-sm text-terra-400">
                  {error}
                </div>
              )}
              {result ? (
                <ResultsDashboard result={result} date={TOMORROW} />
              ) : (
                <EmptyState loading={loading} />
              )}
            </div>
          </div>
        </main>

        <footer className="mt-12 border-t border-aegean-700/40 py-5 text-center text-xs text-marble-600">
          Helios · Greek DAM battery analysis · Demo price inputs until verified feeds are connected
        </footer>
      </div>
    </div>
  );
}

function EmptyState({ loading }: { loading: boolean }) {
  if (loading) {
    return (
      <div className="flex min-h-[440px] flex-col items-center justify-center gap-6 rounded border border-aegean-700 bg-aegean-900">
        <Loader2 size={26} className="animate-spin text-gold-500" />
        <div className="text-center">
          <p className="text-sm font-semibold text-marble-200">Solving dispatch&hellip;</p>
          <p className="mt-1 text-xs text-marble-600">Price model · HiGHS MILP · ~30s cold start</p>
        </div>
        <div className="flex flex-col gap-1.5 text-xs text-marble-600">
          {["Loading price inputs","Preparing forecast curve","Running MILP dispatch","Checking battery constraints"].map((step) => (
            <div key={step} className="flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-gold-600 animate-pulse" />
              {step}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[440px] flex-col items-center justify-center gap-5 rounded border border-dashed border-aegean-700 bg-aegean-900/50">
      <div className="flex h-14 w-14 items-center justify-center rounded border border-aegean-700 bg-aegean-900">
        <Sun size={24} className="text-gold-600" />
      </div>
      <div className="text-center px-4">
        <p className="text-sm font-semibold text-marble-300">No results yet</p>
        <p className="mt-1 text-xs text-marble-600">
          Configure your asset and run optimisation to review the dispatch scenario
        </p>
      </div>
      <div className="grid grid-cols-2 gap-2.5 text-center text-xs text-marble-600 px-4">
        {[["96 Slots","15-min resolution"],["MILP","Optimal dispatch"],["Greek DAM","Bid workflow"],["Analysis","Risk-ready output"]].map(([title, sub]) => (
          <div key={title} className="rounded border border-aegean-700 bg-aegean-900 px-3 py-2.5">
            <p className="font-semibold text-marble-400">{title}</p>
            <p className="mt-0.5">{sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
