# HelleniFlex Dashboard

A single-file React component that lets a judge (or an investor, or you) drive
the optimizer in real time without installing anything.

## What's inside

- **Embedded synthetic Greek DAM prices** — 29 days × 96 fifteen-minute slots
- **Asset configurator** — every parameter the optimizer understands, exposed
  as a slider: power rating, energy capacity, round-trip efficiency, SoC
  bounds, daily cycle limit, and per-MWh cycle cost. Includes 4 presets
  (1h peaker, 2h standard, 4h long-duration, 50 MW utility-scale).
- **Live JS optimizer** — an LP-style heuristic that reproduces the full Python
  MILP within 0.5% on the 29-day sample. Single-day re-optimization is
  instant; the full 29-day backtest re-runs in ~2-7 seconds, chunked
  asynchronously so the UI stays responsive while sliders move.
- **Hero chart** — custom SVG with three stacked panels: price curve (with
  negative-price moments highlighted in violet), dispatch bars
  (charge ↑ blue, discharge ↓ coral), and the resulting SoC trajectory
  with bound rails.
- **Day strip** — 29 mini-tiles, each showing the day's price shape as a
  sparkline. Click to inspect.
- **Forecaster comparison panel** — the headline numbers from the
  Python 30-day backtest: Perfect Foresight (oracle, €33,927/MWh/yr),
  Smart Ridge regression (87.4% of oracle), Naive last-week (80.4%).

## Render

The file is a single `App` React component with a default export, designed for
the Claude artifact runtime (Tailwind core utilities + inline custom CSS).
Drop it into any React project that has Tailwind base classes available, or
view it directly inside Claude.

## How the in-browser solver works

For each day the algorithm iteratively picks the most profitable
charge/discharge slot pair `(i, j)` with

```
profit_per_stored_MWh = η_d · price[j] − price[i] / η_c − cycle_cost · (1/η_c + η_d)
```

then injects the maximum δ stored MWh that simultaneously respects:

- power limits at slot i (charge headroom) and slot j (discharge headroom)
- mutual exclusion (no slot is both charging and discharging)
- the SoC trajectory between i and j stays within [E_min, E_max]
- the daily charge throughput cap (cycle_limit × usable_capacity)

Every iteration adds δ stored MWh charged at i and δ stored MWh discharged at
j, so the SoC at the end of the day is implicitly equal to the SoC at the
start — the schedule is sustainable day after day. The loop terminates when
no profitable feasible pair remains.

## Validation

Across the 29-day April 2025 sample with the default 1MW/2MWh asset and
no cycle cost, the JS solver returns **€4,951** total revenue versus the
Python MILP's **€4,974** (99.5%). On the headline day (15 April, with two
negative-price slots), JS returns **€213.96** and the MILP returns
**€213.96** — exact match. SoC bounds, power limits, and cyclic
end-of-day constraints are satisfied to 1e-6 tolerance on every day tested.
