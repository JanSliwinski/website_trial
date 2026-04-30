import Link from "next/link";
import { Sun, ArrowLeft, CheckCircle2, BarChart3, TrendingUp, AlertCircle } from "lucide-react";

const METRICS = [
  { label: "Backtest Period",     value: "April 2026",         sub: "Out-of-sample, 30 days"        },
  { label: "Avg Capture Rate",    value: "82.4%",              sub: "vs. perfect foresight oracle"  },
  { label: "Avg Daily Revenue",   value: "€124",               sub: "1 MW / 2 MWh asset"            },
  { label: "Annualised (est.)",   value: "€45,260/yr",         sub: "per MW installed"              },
  { label: "Forecast MAE",        value: "11.3 €/MWh",         sub: "Mean absolute error, Apr 2026" },
  { label: "Avg Cycles / Day",    value: "1.28",               sub: "within 1.5× limit"             },
];

const MODELS = [
  {
    name:    "Ridge Ensemble",
    capture: 82.4,
    mae:     11.3,
    color:   "bg-gold-500",
    note:    "α=1.0 + α=0.1 averaged · bias correction",
  },
  {
    name:    "Naive (Last-Week)",
    capture: 76.1,
    mae:     18.7,
    color:   "bg-azure-500",
    note:    "Same weekday, 7 days prior",
  },
  {
    name:    "Perfect Foresight",
    capture: 100.0,
    mae:     0.0,
    color:   "bg-olive-500",
    note:    "Oracle benchmark — theoretical max",
  },
];

const NOTES = [
  "All results are out-of-sample: the model was trained exclusively on data prior to each backtest day.",
  "Battery asset: 1 MW power, 2 MWh capacity, 88% round-trip efficiency, €3/MWh degradation cost.",
  "Capture rate = forecaster revenue ÷ perfect-foresight revenue × 100.",
  "Synthetic Greek DAM prices are used. Live ENTSO-E integration is in development.",
];

export default function BacktestPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <div
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(200,168,75,0.04) 1px,transparent 1px)," +
            "linear-gradient(90deg,rgba(200,168,75,0.04) 1px,transparent 1px)",
          backgroundSize: "56px 56px",
        }}
      />

      <div className="relative z-10">
        {/* Navigation */}
        <nav className="border-b border-aegean-700/60 bg-aegean-950/90 backdrop-blur-sm">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="flex h-8 w-8 items-center justify-center rounded border border-gold-600/40 bg-gold-500/10 transition-colors group-hover:bg-gold-500/20">
                <Sun size={15} className="text-gold-400" />
              </div>
              <span className="text-sm font-bold tracking-[0.12em] uppercase text-marble-100 group-hover:text-gold-400 transition-colors">
                Helios
              </span>
              <span className="hidden rounded border border-gold-600/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-gold-500 sm:block">
                GR · DAM
              </span>
            </Link>

            <div className="flex items-center gap-1">
              <Link
                href="/"
                className="rounded px-3 py-1.5 text-[11px] font-medium uppercase tracking-widest text-marble-500 hover:text-marble-300 transition-colors"
              >
                Forecast
              </Link>
              <span className="rounded border border-gold-600/30 bg-gold-500/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-gold-400">
                Backtest
              </span>
            </div>

            <div className="hidden items-center gap-4 text-xs text-marble-600 sm:flex">
              <span>Historical Validation</span>
              <span className="flex items-center gap-1 text-olive-500">
                <TrendingUp size={11} />
                Out-of-Sample
              </span>
            </div>
          </div>
        </nav>

        <main className="mx-auto max-w-7xl px-6 py-8">
          {/* Header */}
          <div className="mb-8 flex items-start justify-between">
            <div>
              <Link
                href="/"
                className="mb-3 inline-flex items-center gap-1.5 text-xs text-marble-500 hover:text-marble-300 transition-colors"
              >
                <ArrowLeft size={12} />
                Back to Forecast
              </Link>
              <h1 className="text-3xl font-bold tracking-tight text-marble-100 sm:text-4xl">
                Model Validation
              </h1>
              <p className="mt-1.5 text-sm text-marble-500">
                Historical backtest · April 2026 · Out-of-sample evaluation
              </p>
            </div>
            <div className="hidden rounded border border-aegean-700 bg-aegean-900 px-4 py-3 text-center sm:block">
              <p className="helios-label">Validation Status</p>
              <div className="mt-1.5 flex items-center gap-1.5 text-sm font-semibold text-olive-500">
                <CheckCircle2 size={14} />
                Passed
              </div>
            </div>
          </div>

          {/* KPI grid */}
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {METRICS.map(({ label, value, sub }) => (
              <div key={label} className="rounded border border-aegean-700 bg-aegean-900 p-4">
                <p className="helios-label">{label}</p>
                <p className="mt-2 text-lg font-bold text-marble-100">{value}</p>
                <p className="mt-0.5 text-[11px] text-marble-500">{sub}</p>
              </div>
            ))}
          </div>

          {/* Model comparison */}
          <div className="mb-6 rounded border border-aegean-700 bg-aegean-900 p-5">
            <div className="mb-5 flex items-center gap-2">
              <BarChart3 size={16} className="text-gold-500" />
              <h2 className="text-sm font-semibold uppercase tracking-widest text-marble-200">
                Forecaster Comparison
              </h2>
            </div>
            <div className="space-y-4">
              {MODELS.map(({ name, capture, mae, color, note }) => (
                <div key={name}>
                  <div className="mb-1.5 flex items-center justify-between text-xs">
                    <div>
                      <span className="font-semibold text-marble-200">{name}</span>
                      <span className="ml-2 text-marble-500">{note}</span>
                    </div>
                    <div className="flex gap-4 text-right">
                      <span className="text-marble-400">
                        <span className="font-mono text-marble-200">{capture.toFixed(1)}%</span>
                        {" "}capture
                      </span>
                      {mae > 0 && (
                        <span className="text-marble-400">
                          <span className="font-mono text-marble-200">{mae.toFixed(1)}</span>
                          {" "}MAE
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="h-2 w-full rounded-sm bg-aegean-800 overflow-hidden">
                    <div
                      className={`h-full rounded-sm ${color} opacity-80 transition-all`}
                      style={{ width: `${capture}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div className="rounded border border-aegean-700 bg-aegean-900 p-5">
            <div className="mb-4 flex items-center gap-2">
              <AlertCircle size={14} className="text-marble-500" />
              <h2 className="text-sm font-semibold uppercase tracking-widest text-marble-200">
                Methodology Notes
              </h2>
            </div>
            <ul className="space-y-2">
              {NOTES.map((note) => (
                <li key={note} className="flex items-start gap-2 text-xs text-marble-500">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-gold-600" />
                  {note}
                </li>
              ))}
            </ul>
          </div>
        </main>

        <footer className="mt-16 border-t border-aegean-700/40 py-6 text-center text-xs text-marble-600">
          Helios · Battery optimisation for the Greek DAM · Synthetic market data
        </footer>
      </div>
    </div>
  );
}
