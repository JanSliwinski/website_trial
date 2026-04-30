"use client";

import Link from "next/link";
import { Sun, Database } from "lucide-react";

const SOURCES = [
  {
    name: "HEnEx",
    full: "Hellenic Energy Exchange",
    category: "Market prices",
    color: "gold",
    description:
      "The Greek Day-Ahead Market (DAM) operator. Primary source for hourly and quarter-hourly clearing prices used in the MILP optimizer and revenue settlement.",
    provides: ["DAM clearing prices (€/MWh)", "Bid acceptance curves", "Intraday session results"],
  },
  {
    name: "ENTSO-E",
    full: "European Network of Transmission System Operators",
    category: "Grid data",
    color: "azure",
    description:
      "Pan-European TSO network. Provides cross-border flow data, total load forecasts, and generation-by-fuel-type breakdowns used as feature inputs to the price forecasting model.",
    provides: ["Day-Ahead prices (all bidding zones)", "Total load forecast & actuals", "Generation per production type", "Cross-border physical flows"],
  },
  {
    name: "IPTO / ADMIE",
    full: "Independent Power Transmission Operator of Greece",
    category: "Grid operations",
    color: "olive",
    description:
      "Greek transmission system operator (ΑΔΜΗΕ). Publishes real-time system load, ancillary service activation, and constraint data specific to the Greek synchronous area.",
    provides: ["Real-time system load (MW)", "Ancillary services & reserves", "Interconnection schedules (GR–BG, GR–AL, GR–MK, GR–IT)"],
  },
  {
    name: "Open-Meteo",
    full: "Open-Meteo Weather API",
    category: "Weather & renewables proxy",
    color: "azure",
    description:
      "Free, high-resolution numerical weather prediction API. Solar irradiance and wind-speed forecasts are used as renewable generation proxies — key drivers of Greek midday price dips.",
    provides: ["Surface solar irradiance (W/m²)", "Wind speed at 100 m hub height", "Temperature (demand proxy)", "48-hour ensemble forecast"],
  },
  {
    name: "TTF-ICE",
    full: "Title Transfer Facility — ICE Futures",
    category: "Fuel benchmark",
    color: "gold",
    description:
      "European natural gas benchmark traded on the Intercontinental Exchange. TTF front-month prices are a primary marginal-cost signal for Greek gas-peaker plants and are included as a lagged feature in the Ridge and LightGBM price models.",
    provides: ["TTF day-ahead gas price (€/MWh)", "Front-month futures settlement", "Seasonal spread signals"],
  },
  {
    name: "EEX",
    full: "European Energy Exchange",
    category: "Power futures & emissions",
    color: "olive",
    description:
      "Pan-European power exchange based in Leipzig. EEX Greek base- and peak-load futures provide forward-curve context; EUA carbon futures add a CO₂ cost signal to gas-fired generation cost estimates.",
    provides: ["Greek power base/peak futures (€/MWh)", "EUA carbon allowance price (€/tCO₂)", "Capacity and cross-border auction results"],
  },
];

const COLOR = {
  gold:  { badge: "border-gold-600/40 bg-gold-500/10 text-gold-400",  dot: "bg-gold-500"  },
  azure: { badge: "border-azure-500/40 bg-azure-500/10 text-azure-400", dot: "bg-azure-500"  },
  olive: { badge: "border-olive-500/40 bg-olive-500/10 text-olive-500", dot: "bg-olive-500"  },
};

export default function SourcesPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-aegean-950">
      <div
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(200,168,75,0.04) 1px,transparent 1px)," +
            "linear-gradient(90deg,rgba(200,168,75,0.04) 1px,transparent 1px)",
          backgroundSize: "56px 56px",
        }}
      />
      <div className="pointer-events-none fixed left-1/3 top-0 z-0 h-[500px] w-[500px] -translate-x-1/2 rounded-full bg-aegean-700/10 blur-[160px]" />

      <div className="relative z-10">
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
              <Link href="/" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-300 transition-colors whitespace-nowrap">
                1. Forecast
              </Link>
              <Link href="/backtest#analysis" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-300 transition-colors whitespace-nowrap">
                2. Analysis
              </Link>
              <Link href="/backtest#backtest" className="rounded px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-300 transition-colors whitespace-nowrap">
                3. Backtest
              </Link>
              <span className="rounded border border-gold-600/30 bg-gold-500/10 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-gold-400 whitespace-nowrap">
                4. Sources
              </span>
            </div>

            <div className="hidden items-center gap-2 text-xs text-marble-600 lg:flex">
              <Database size={12} className="text-gold-600" />
              Data provenance
            </div>
          </div>
        </nav>

        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
          <div className="mb-8 overflow-hidden rounded border border-gold-600/25 bg-aegean-900/80">
            <div className="h-1 bg-gradient-to-r from-azure-500 via-marble-50 to-gold-500" />
            <div className="px-5 py-5 sm:px-6">
              <p className="helios-label text-gold-400">4. Sources</p>
              <h1 className="mt-2 text-2xl font-bold tracking-tight text-marble-50 sm:text-3xl lg:text-4xl">
                Data Sources & Market Feeds
              </h1>
              <p className="mt-2 text-sm text-marble-500">
                All price, grid, weather, and fuel data underpinning the Helios forecast and optimizer.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {SOURCES.map((src) => {
              const c = COLOR[src.color as keyof typeof COLOR];
              return (
                <div
                  key={src.name}
                  className="rounded border border-aegean-700 bg-aegean-900 p-5 flex flex-col gap-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span className={`inline-block rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest ${c.badge}`}>
                        {src.category}
                      </span>
                      <h2 className="mt-2 text-lg font-bold text-marble-50">{src.name}</h2>
                      <p className="text-xs text-marble-500">{src.full}</p>
                    </div>
                    <div className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${c.dot}`} />
                  </div>

                  <p className="text-sm leading-6 text-marble-400">{src.description}</p>

                  <div>
                    <p className="helios-label mb-1.5">Provides</p>
                    <ul className="space-y-1">
                      {src.provides.map((item) => (
                        <li key={item} className="flex items-start gap-2 text-xs text-marble-500">
                          <span className={`mt-1.5 h-1 w-1 shrink-0 rounded-full ${c.dot}`} />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              );
            })}
          </div>
        </main>

        <footer className="mt-12 border-t border-aegean-700/40 py-5 text-center text-xs text-marble-600">
          Helios · Greek DAM battery analysis · Data sourced from public market and grid operators
        </footer>
      </div>
    </div>
  );
}
