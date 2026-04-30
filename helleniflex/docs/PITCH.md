# HelleniFlex — Hackathon Pitch Deck Outline

A 6-minute live demo + pitch flow. Each slide is ~45 seconds.

---

## Slide 1 — Title (0:00–0:30)

> **HelleniFlex**
> *Universal battery optimization for the Greek electricity market.*

**Opening line (memorize this):**
> *"In April 2026, Greece's first standalone batteries entered the Day-Ahead Market.
> Greek batteries, on Greek prices, in 15-minute slots — and not a single operator
> has the years of telemetry data normally needed to optimize them. We built the
> framework that solves that problem on Day 1."*

Don't waste this slide on logos. Put the example dispatch chart on it as a backdrop.

---

## Slide 2 — The problem (0:30–1:15)

Three numbers, big and centered:

- **15 minutes** — new Greek DAM resolution since Oct 2025
- **April 2026** — first standalone batteries went live
- **0** — years of operational telemetry available

> *"The Greek market just got faster, batteries just arrived, and there's no
> historical data to learn from. Standard data-driven approaches don't work.
> You need a framework that's right on Day 1."*

**Why this slide matters:** judges who don't know the energy domain understand the constraint immediately.

---

## Slide 3 — The architecture (1:15–2:00)

Show the three-block diagram from the README:

```
[ Asset specs + Price forecast ]  →  [ MILP Optimizer ]  →  [ 24h Schedule ]
```

Three spoken sentences:
1. *"Any battery asset is just a set of physics constraints — power, capacity, efficiency, SoC limits. We capture all of them in one validated specification."*
2. *"A Mixed-Integer Linear Program decides charge / discharge / idle for every 15-minute slot. The math is provably optimal given a price forecast."*
3. *"Three forecasters — perfect foresight as the upper bound, naive as the floor, Ridge regression as the realistic case — let us measure forecast tolerance honestly."*

---

## Slide 4 — Live demo (2:00–4:00) ⭐ The money slide

**Open the dashboard.** Walk through:

1. Drag the **capacity slider** from 1 MWh → 4 MWh. Show how the schedule changes — the longer-duration asset fills more of the midday solar trough.
2. Drag the **efficiency slider** down. Show revenue degrade smoothly. *"This is why round-trip efficiency matters: 88% vs 95% is roughly €X/year on a 1 MW asset."*
3. Hit **"Compare forecasters"**. Three bars side-by-side. *"Perfect foresight is the ceiling. Our smart forecaster captures 87% of it. Even the naive baseline gets 80% — proof that the optimizer is robust to forecast error."*
4. Pick **15 April 2025** as the demo day. *"Look at this midday: prices go negative because of the solar surplus. The battery charges through the negative-price hours — we get paid to fill the battery — then discharges into the evening peak. This is exactly what real Greek operators will be doing in 2026."*

**Tip for the live demo:** rehearse this 5 times. Pick the day in advance — `2025-04-15` has a clean negative-price midday slot that makes the story self-evident.

---

## Slide 5 — Results (4:00–4:45)

Two tables, side by side.

**Left — forecaster comparison (1 MW / 2 MWh, 30 days):**

| Forecaster | €/MWh/yr | % of upper bound |
|---|---:|---:|
| Perfect Foresight | 33,927 | 100% |
| **Smart (Ridge)** | **29,666** | **87%** |
| Naive | 27,292 | 80% |

**Right — asset duration sensitivity:**

| Duration | €/MWh/yr | €/day |
|---|---:|---:|
| 1h | 39,476 | 108 |
| 2h | 33,927 | 186 |
| 4h | 23,520 | 258 |

> *"Two clear stories. First, our forecaster captures 87% of the theoretical max — the optimizer is forecast-tolerant. Second, the framework lets investors compare any asset configuration: short-duration batteries earn more per MWh installed, long-duration batteries earn more in absolute terms. Investors get to pick their trade-off."*

---

## Slide 6 — Why this approach (4:45–5:30)

Three lines, no bullets:

> **Generic.** Any battery, any day, any forecast. Plug in your asset specs and run.
>
> **Honest under data scarcity.** No ML model trained on operational data we don't have. Pure physics + MILP, validated on synthetic Greek DAM patterns and ready for real data.
>
> **Production-ready.** 40 milliseconds per day. Deterministic. Explainable. Every constraint visible in the formulation.

> *"This isn't a demo. It's the framework a trading desk could deploy on April 27th, 2026 — the day before the next batch of Greek batteries comes online."*

---

## Slide 7 — Roadmap & ask (5:30–6:00)

Four bullets the judges can imagine you finishing in week 2:

- Stochastic optimization (price-uncertainty bounds)
- Multi-market co-optimization (DAM + Intraday + Ancillary)
- Live HEnEx integration for production bid generation
- Calendar + cycle aging in the degradation model

Closing line:
> *"We built HelleniFlex in 48 hours. With another two weeks, it ships."*

---

## Q&A prep

**Q: "Why MILP, not reinforcement learning?"**
> *"RL needs years of operational data to converge. Greece doesn't have it — the first battery went live two weeks ago. MILP gives provably-optimal schedules from physics alone, on Day 1, no training data required. RL becomes attractive in years 2–3 once telemetry accumulates; the optimizer's outputs become its training labels."*

**Q: "Your forecasts are simple. Why not deep learning?"**
> *"Day-ahead price forecasting is a small-data problem — at most ~700 days of history. Ridge regression beats LSTMs on this regime in published benchmarks. It also trains in milliseconds, is fully interpretable, and degrades gracefully in regime shifts. The framework is forecaster-agnostic — swap in any model that returns 96 numbers."*

**Q: "What if the price forecast is wrong?"**
> *"The naive baseline already captures 80% of perfect-foresight revenue. That's because the optimizer doesn't bet on small price differences — the cycle-cost regularizer keeps it from cycling on noise. The schedule is robust to forecast error by design."*

**Q: "How do you handle the October 2025 resolution change?"**
> *"Trivially. The optimizer takes any time-step. Pre-October data is hourly (T=24); post-October is 15-minute (T=96). The MILP doesn't care — same formulation, different `dt`. We backtest each regime separately."*

**Q: "What about ancillary markets?"**
> *"Out of scope per the brief, but the architecture is co-optimization-ready. Adding aFRR or FCR is a constraint set on the existing decision variables, not a redesign. Roadmap item one."*

**Q: "Where does the cycle-cost number come from?"**
> *"Industry standard for utility-scale Li-ion is €2–8 per MWh of throughput, derived from CAPEX divided by warranty cycle life. We use €3 as the default; the value is exposed as a parameter so users plug in their own asset economics."*

**Q: "How does this compare to commercial tools?"**
> *"Commercial battery optimizers like AutoGrid, Habitat, or Modo cost €50k–€200k per year per asset and are closed boxes. We deliver the core methodology in open source, transparent code, and run it in 40 ms per day. The remaining gap is operationalization — bid submission, settlement reconciliation — which is engineering, not research."*
