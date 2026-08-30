# Marci Silfrain "Measured Move / Little RZY" — Reference Register

> Living reference log for everything gathered on the Marci Silfrain measured-move
> strategy family: source pages, interviews, third-party backtests, PineScript
> implementations, and what each source contributes or fails to contribute.
> Companion to the in-house falsification record [MM_MEASURED_MOVE.md](MM_MEASURED_MOVE.md)
> (E34/E35 batteries). Update this file as new references are gathered.

**Identity note:** the trader's name is **Marci Silfrain** (often misspelled
"Silfarani" in search results). 2nd place, Robbins World Cup of Futures Trading,
206% return (peaked 319%) per multiple interview summaries. Robbins is a
leverage-tolerant competition; she herself calls the contest leverage
"irresponsible" outside contests — treat competition returns as marketing
context, not strategy validation.

---

## Reference Index

| # | Source | Type | Claimed evidence | Our status |
|---|---|---|---|---|
| R1 | TradeZella strategy page | Strategy writeup (no numbers) | none cited | E34: falsified on ES 5m |
| R2 | Words of Rizdom interview + transcript | Interview | 206% World Cup (leverage-heavy) | context only; no strategy stats |
| R3 | ChartFanatics playbook | Rewrite of R1 | none | duplicate of R1 content |
| R4 | PickMyTrade blog + PineScript v6 | Backtest + code (XAUUSD) | PF 1.99 / PF 1.95, 896 & 272 trades | **logged below — partially reproduced** |
| R5 | Scribd "Marci Silfrain Strategy [PickMyTrade]" | PDF mirror | same as R4 | not separately fetched |

---

## R1 — TradeZella: "Measured Move Trend Strategy"

- URL: https://www.tradezella.com/strategies/measured-move-trend-strategy
- Full strategy rules captured in this doc's history and in MM_MEASURED_MOVE.md §design.
- **Zero performance data anywhere on the page** — no WR, PF, expectancy, sample.
- Core claims: pullback-to-trendline distance = next move size (1:1 projection);
  1st/2nd "Little RZY" strongest, 4th/5th exhausted; BB outer-band context for
  early structures; close beyond trendline invalidates.
- **Our falsification (E34, ES NT MergeBA 19mo, 5m):** ordinal decay ✗ (ord4 1.28,
  ord6 1.90 > ord2 1.05), near-band context ✗ (6 trades, PF 0.21), entry-only edge
  ✗ (MMRaw fixed-exit PF 0.91 — projection exits carry the P&L), base PF 1.16
  (long-only 1.38), NQ no-transfer (PF 1.04).

## R2 — Interview: Words of Rizdom, "The World's #2 Trader"

- Video: https://www.youtube.com/watch?v=Dt9vzMmf__o (transcript summary via
 EliteTrader thread: https://www.elitetrader.com/et/threads/388340/)
- Key claims (from transcript): 15-16 years trading, ~$250k lost pre-profitability;
  trades only S&P/NASDAQ; massive manual backtesting incl. 1929/2008 replays;
  **hard stops, never trailing** ("let it hit target or stop out"); mental prep to
  lose 20 in a row; competition leverage "irresponsible" outside contests; scaling
  INTO winners was learned in the Cup; Simon's data-driven philosophy as model.
- **Usefulness:** discipline context + market-focus discipline (consistent with our
  ES-specificity finding). **No strategy statistics cited anywhere.**
- Related live-trade derivative content: Spanish NT8 series trading "Little RZY"
  in futures (YT mZdOJgwx4FQ) — not reviewed in detail.

## R3 — ChartFanatics playbook

- URL: https://www.chartfanatics.com/strategies/measured-move-trend-strategy
- Content-identical rewrite of R1 (same 10 rules, same Little RZY framing, same
  BB guidance). Adds an Apex Funding ad and PDF download; adds no data.
- Treat R1+R3 as one source.

## R4 — PickMyTrade blog: "Marci Silfrain Strategy on Gold" (2026-06-24)

- URL: https://blog.pickmytrade.trade/marci-silfrain-strategy-gold/
- The only public source so far WITH numbers + a full PineScript v6 implementation.
- **Backtest platform:** TradingView strategy(). XAUUSD spot, 2022-11-20 → 2025-11-20
  (3 years), commission 0%, margin 5%, initial $100k.

### Their reported stats

| Config | Return | PF | WR | Trades | Max DD |
|---|---|---|---|---|---|
| 5% risk/trade (intraday TF) | **+1,574%** | 1.988 | **20.1%** | 896 | 43.6% |
| 1% risk/trade (Daily TF) | +122% | 1.948 | 37.1% | 272 | 18.6% |
| Buy & hold gold same 3y | +134% | — | — | — | — |

Their explanation of 20% WR + PF 1.99: 50% partial exit at 1× measured move
(bank + breakeven), runner to 2× measured move (mmMult=2.0). Winners are 4-6× size
of losers; 180/896 winners carry everything. 5% risk = ~20× effective leverage —
the +1,574% is a leverage artifact, their own doc admits it.

Their exhaustion filter: **Touch 1/2 = enter, Touch 3 = warn, Touch 4+ = blocked**
(rzyCount reset on new HH/HL or LH/LL trend structure). This is the ordinal gate we
tested in E34b — ours found NO early-ordinal edge on ES 5m; theirs is armed per
new-trend structure (not per-direction consecutive), a materially different counter.

### PineScript implementation notes (vs our engine)

| Mechanic | Their Pine | Our engine (R34) |
|---|---|---|
| Pivots | `ta.pivothigh/low(7,7)` — 2 most recent | `find_pivot_highs/lows(k=3)` — same family, smaller k |
| Trend gate | HH/HL or LH/LL strict mode | DI dominance (`di_edge`) |
| Touch zone | within 1.0 ATR of trendline | `touch_buf_atr=0.10` (much tighter) |
| Entry | close-direction bar off the line (close>open) | directional close-vs-close + open sign (stricter) |
| Stop | beyond line/low − 1.0×ATR (in their 1,574% config) | structure extreme ± 0.25×ATR (tighter) |
| Target | partial 50% at 1×MM, BE at 0.5R, runner to 2×MM | TP1 1×MM / TP2 2×MM, BE after TP1 (same shape) |
| Sizing | % equity per stop-out, margin-capped | micro contracts, 2-15 bps risk bracket |
| Short side | mirror, default OFF (gold bull) | both sides; SHORT lost on ES (E34S PF 0.95) |
| BB | optional band-tag filter (default OFF) | E34c tested (near-band context) ✗ |

Same exit skeleton (partial+BE+runner), materially different triggers (looser touch,
looser structure, ordinal reset semantics). Their 896 trades/3y on XAUUSD is a
~10× higher frequency per instrument than our 298 ES longs/19mo — consistent with
looser gates + leverage-heavy spot gold, NOT directly comparable.

### Honest-caveat checklist for R4's numbers (their own page implies these)

1. **0% commission, 0 spread model** on XAUUSD spot — costs are ~1-3 bps/round-turn
   on gold; at 272-896 trades this is material against PF 1.95-1.99.
2. **5% risk = 20× leverage path** — +1,574% and 43.6% DD are the same coin.
3. **Runner target = 2×MM limit order** — in a bullish 3-year gold run, the runner
   fills asymmetrically often; the strategy is partially a long-gold beta harvest.
4. **One instrument, one regime** (relentless gold bull). No 1929/2008-style stress
   replays in their backtest (ironic given Marci's own prep advice in R2).
5. **TradingView strategy() intrinsic caveats**: bar-magnifier off, intrabar SL/TP
   order assumptions, `close`-based entry semantics.

### Actionable from R4

- **Reproduce their config on ES/NQ** with our engine as ADR-017 arms:
  loosened touch (1.0 ATR), loosened stop (1.0×ATR), strict HH/HL trend gate,
  ordinal reset per new-structure (their counter semantics), partial+BE+2×MM exits,
  shorts on. This isolates whether "Little RZY + ordinal reset + partial/runner"
  carries edge on index futures at all.
- Fetch their PineScript wholesale as a reference artifact (already captured in
  this session's fetch; re-fetch from source when implementing).
- Their alert JSON confirms webhook-able entry/exit conditions if this ever goes
  live-paper on TradingView; our NT8 lineage handles execution natively.

---

## Open Questions Register

| # | Question | Status |
|---|---|---|
| Q1 | Does the ordinal-reset-per-trend-structure counter (R4 semantics) surface the edge our per-direction counter missed? | **E36 run: NO — see below** |
| Q2 | Does the BB-exhaustion exit (E35c, PF 1.26 DD 300) survive a prop-firm sim vs E34L (PF 1.38 DD 403)? | **Q2 run: 0% pass both (A/B/FTMO) — family not fundable standalone. See MM_MEASURED_MOVE.md §Q2** |
| Q3 | Is the E34L/E35c family portfolio-additive over ST+overnight-reversion (E31 baseline)? Corr E34L↔ST measured −0.015; E35c not yet. | **moot after Q2+Q6: candidate regime-broken → closed** |
| Q4 | NQ cross-check of E35c exit | closed in Q2 process (family closed) |
| Q5 | R4's loosened-config reproduction on ES/NQ — edge or gold-beta artifact? | **E36 run: REFUTED — see below** |
| Q6 | Walk-forward gate on the best arm | **Q6 run: FAIL — both E34L & E35c lose in 2026H2. See MM_MEASURED_MOVE.md §Q6** |

---

## E36 — PickMyTrade (R4) reproduction on ES/NQ (2026-08-30)

Script: `scripts/analysis/mm_e36_pickmytrade_repro.py`. Their semantics, our data:
pivot 7, touch within 1.0×ATR, stop 1.0×ATR beyond line, strict HH/HL / LH/LL
trend gate, structure-reset ordinal (blocked at touch 3), partial 50% @ 1×MM +
BE, runner to 2×MM, next-open fill.

| Arm | Trades | WR% | PF | Net$ | DD$ |
|---|---|---|---|---|---|
| ES long-only | 2,760 | 53.1 | 1.04 | +2,446 | 4,506 |
| ES both dirs | 5,381 | 51.5 | 1.11 | +13,430 | 6,590 |
| — ES SHORT leg | 2,621 | 49.8 | 1.19 | +10,984 | — |
| NQ long-only | 3,018 | 55.1 | 1.15 | +17,023 | 7,132 |

### Findings (Q1 + Q5 both answered)

1. **The R4 config does NOT carry their PF ~1.99 onto index futures.** Best arm
   PF 1.15 (NQ) / 1.11 (ES both) at 5-10× our E34 trade frequency — the loosened
   gates produce thousands of trades whose gross edge is ~breakeven. Their
   gold-bull result remains unexplained by the pattern alone → most consistent
   with **gold-beta harvest + zero-cost assumptions** (their runner limit orders
   fill asymmetrically often in a 3-year bull run).
2. **Structure-reset ordinal (Q1): still no early-touch premium.** Ordinal 1 vs 2
   WR: 52.9 vs 53.4 (ES long), 51.6 vs 51.3 (both), 56.2 vs 53.1 (NQ). Direction
   of the difference is *consistent but small* (ordinal-1 ≥ ordinal-2 everywhere),
   and touches never reached 3 in practice (the trend gate disarms first). Marci's
   "block after touch 2" rule does not create edge on ES/NQ intraday — it merely
   reduces frequency.
3. **The short leg flipped on this config** (ES shorts PF 1.19 vs longs 1.04) —
   exact opposite of E34S (0.95). Different trend gate (structure vs DI) + looser
   stops invert the direction asymmetry at 6× the trade count. Neither config's
   shorts earn their DD.
4. **DD is the killer:** $4.5-7.1k across the arms (vs E34L's $403 on 298 trades).
   20-30 trades/day of near-breakeven activity accumulates grind-down fast. This
   is the "20% WR at 5% risk" shape from R4 playing out without gold's tailwind.

### Verdict

R4's Pine semantics reproduced honestly and the edge did not transfer. Combined
with E34: the Little RZY family on index-futures intraday data caps at ~PF 1.15
with damaging DD under their OWN looser config. The single best configuration in
the whole research thread remains our **E34L wide-projection (PF 1.38, DD 403)**,
with **E35c BB-exhaustion (PF 1.26, DD 300)** as the DD-optimized variant. Next
gates unchanged: Q2 (prop sim), Q3 (portfolio additivity), Q6 (walk-forward).

## Source URL Register

- R1: https://www.tradezella.com/strategies/measured-move-trend-strategy
- R2 video: https://www.youtube.com/watch?v=Dt9vzMmf__o
- R2 transcript: https://www.elitetrader.com/et/threads/the-worlds-2-trader-futures-trading-world-champion-marci-silfrain-interview.388340/
- R2 short: https://www.youtube.com/shorts/069p7jr0R6k (206%/319% claim)
- R3: https://www.chartfanatics.com/strategies/measured-move-trend-strategy
- R4: https://blog.pickmytrade.trade/marci-silfrain-strategy-gold/
- R5: https://www.scribd.com/document/1072559212/Marci-Silfrain-Strategy-PickMyTrade (unread)
- Live-trade NT8 video (ES): https://www.youtube.com/watch?v=mZdOJgwx4FQ (unreviewed)