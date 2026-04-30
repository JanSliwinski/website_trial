"use client";

import { useState } from "react";
import { Zap, Github, Activity } from "lucide-react";
import type { BatteryConfig, OptimizeResult } from "@/lib/types";
import { runOptimize } from "@/lib/api";
import BatteryForm from "@/components/BatteryForm";
import ResultsDashboard from "@/components/ResultsDashboard";

export default function Home() {
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeDate, setActiveDate] = useState("");

  async function handleSubmit(date: string, battery: BatteryConfig) {
    setLoading(true);
    setError(null);
    setActiveDate(date);
    try {
      const res = await runOptimize(date, battery);
      setResult(res);
    } catch (e: any) {
      setError(e.message ?? "Optimization failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Grid background */}
      <div
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(34,211,238,0.03) 1px, transparent 1px), " +
            "linear-gradient(90deg, rgba(34,211,238,0.03) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      {/* Glow orbs */}
      <div className="pointer-events-none fixed left-1/4 top-0 z-0 h-[500px] w-[500px] -translate-x-1/2 rounded-full bg-cyan-500/5 blur-[120px]" />
      <div className="pointer-events-none fixed right-1/4 bottom-0 z-0 h-[400px] w-[400px] translate-x-1/2 rounded-full bg-blue-500/5 blur-[120px]" />

      <div className="relative z-10">
        {/* Nav */}
        <nav className="border-b border-slate-800/60 bg-navy-950/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 ring-1 ring-cyan-500/30">
                <Zap size={15} className="text-cyan-400" />
              </div>
              <span className="font-bold tracking-tight text-white">
                Hellen<span className="text-cyan-400">iFlex</span>
              </span>
              <span className="hidden rounded-full bg-cyan-500/10 px-2 py-0.5 text-xs font-medium text-cyan-400 ring-1 ring-cyan-500/20 sm:block">
                BESS Optimizer
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span className="hidden sm:block">Greek Day-Ahead Market</span>
              <span className="flex items-center gap-1">
                <Activity size={12} className="text-emerald-400" />
                <span className="text-emerald-400">MILP</span>
              </span>
            </div>
          </div>
        </nav>

        <main className="mx-auto max-w-7xl px-6 py-10">
          {/* Hero */}
          <div className="mb-10 text-center">
            <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
              Battery Arbitrage
            </h1>
            <p className="mt-3 text-lg text-slate-400">
              Day-ahead MILP dispatch optimizer · Greek electricity market
            </p>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs">
              {[
                "cvxpy + HiGHS solver",
                "Ridge price forecaster",
                "Charge/discharge mutual exclusion",
                "Cyclic SoC constraint",
              ].map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-slate-700 bg-slate-800/50 px-2.5 py-1 text-slate-400"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Main layout */}
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-[360px_1fr]">
            {/* Config panel */}
            <div className="lg:sticky lg:top-6 lg:self-start">
              <BatteryForm onSubmit={handleSubmit} loading={loading} />
            </div>

            {/* Results or empty state */}
            <div>
              {error && (
                <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              {result ? (
                <ResultsDashboard result={result} date={activeDate} />
              ) : (
                <EmptyState loading={loading} />
              )}
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="mt-20 border-t border-slate-800/60 py-8 text-center text-xs text-slate-600">
          <p>HelleniFlex · Battery optimization for the Greek DAM · Synthetic market data</p>
        </footer>
      </div>
    </div>
  );
}

function EmptyState({ loading }: { loading: boolean }) {
  if (loading) {
    return (
      <div className="flex h-full min-h-[500px] flex-col items-center justify-center gap-6 rounded-2xl border border-slate-800 bg-navy-900">
        <div className="relative">
          <div className="h-16 w-16 rounded-full border-2 border-slate-700" />
          <div className="absolute inset-0 h-16 w-16 animate-spin rounded-full border-2 border-transparent border-t-cyan-400" />
          <Zap size={20} className="absolute inset-0 m-auto text-cyan-400" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-slate-300">Solving MILP…</p>
          <p className="mt-1 text-xs text-slate-500">HiGHS · cvxpy · ~30s cold start</p>
        </div>
        <div className="flex flex-col gap-1.5 text-xs text-slate-600">
          {["Loading synthetic prices", "Fitting Ridge forecaster", "Running MILP dispatch", "Computing capture rate"].map(
            (step) => (
              <div key={step} className="flex items-center gap-2">
                <div className="h-1 w-1 rounded-full bg-slate-600 animate-pulse" />
                {step}
              </div>
            )
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[500px] flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-slate-800 bg-navy-900/50">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-700 bg-navy-900">
        <Activity size={22} className="text-slate-600" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-slate-400">No results yet</p>
        <p className="mt-1 text-xs text-slate-600">
          Configure your battery and click Optimize Dispatch
        </p>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-3 text-center text-xs text-slate-600">
        {[
          ["96 slots", "15-min resolution"],
          ["MILP", "Binary charge gate"],
          ["Ridge ML", "Price forecaster"],
          ["Capture %", "vs. perfect foresight"],
        ].map(([title, sub]) => (
          <div key={title} className="rounded-lg border border-slate-800 bg-navy-950 px-4 py-2">
            <p className="font-medium text-slate-500">{title}</p>
            <p className="mt-0.5">{sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
