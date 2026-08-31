# FX Replay Strategy Library — Cross-Reference (F5)

> Source: [fxreplay.com/strategies](https://fxreplay.com/strategies) (30 strategies as of 2026-08-30; full PDFs are behind an email gate on each page). Each strategy also has a "Backtesting …" YouTube video from the FX Replay channel with sample sizes on screen.
> This doc maps their library onto the research backlog and extracts testable rules for the NQ-native models. Catalog items marked 🆕 are NOT covered by families F1–F4.

---

## A. Mapping to existing backlog (do not duplicate)

| FX Replay strategy (slug) | Maps to | Delta vs our plan |
|---|---|---|
| `ict-turtle-soup-strategy` | **S1** Turtle Soup | — |
| `ict-amd-po3-strategy` | **S4** PO3/AMD | — |
| `judas-swing-model` | **S4** (Judas = manipulation leg) | — |
| `ict-mmxm-strategy` | **S3** Market Maker Model = S/D bases | — |
| `opening-range-break-strategy` | **Q1** ORB | — |
| `quarterly-theory-smt-strategy` | **S6** SMT + **S7** time conditioning | Adds quarterly-theory time frames as the stratum |
| `torit-trades-trendlines` (`tori-trades-trendlines-strategy`) | **S2** trendline system | Tori's is entry-on-touch (trend continuation); ours is sweep→CHoCH (reversal) — test BOTH reading styles against the same trendline engine |
| `nvidia-anchored-vwap-strategy` | **Q3** VWAP family (anchored variant) | Gap-fills VWAP anchoring: repo only has session VWAP |
| `opening-range-break-strategy` overlap with repo ORB v6/v7 | **Q1** | Their PDF may contain a variant rule worth an arm |

## B. NQ-native models — full rules extracted (ready to code)

### F5.1 Trader Mike — Failed 2s (multi-TF reversal)
> Source: [fxreplay.com/strategies/trader-mike-failed-2s-strategy](https://fxreplay.com/strategies/trader-mike-failed-2s-strategy) + [backtest video](https://www.youtube.com/watch?v=NKFEWydfc6o)

- **Concept**: MTF reversal chain. 1H **#3 candle** (TheStrat notation! sweeps both sides of prior candle and closes beyond opposite body) sets the HTF target → 15m **Failed 2** candle in that direction confirms → 1m MSS + strong close + FVG gives entry. Target = #3 continuation, fixed 1:1.
- **Why it matters here**: this is a *direct composition* of three things the repo already has — TheStrat classifier (15m Failed 2 validated in BACKTEST_RESULTS), CISD/MSS detection, and FVG entry. The unique machine is the **1H #3 → target** rule.
- **Testable arms**: (a) full 3-TF chain as written; (b) 1H #3 detection alone → 15m Failed-2 (skip 1m, use IBB-style entry); (c) swap 1:1 target for the repo's Cover-the-Queen scale-out.
- **Learning**: does the 1H #3 (both-sides sweep candle) actually predict the day's target better than Asia/London range sweeps (S4's manipulation)?

### F5.2 JJ Simon — Fair Value Theory (fair-value reversion + continuation split)
> Source: [fxreplay.com/strategies/jj-simons-fair-value-theory-nq-strategy](https://fxreplay.com/strategies/jj-simons-fair-value-theory-nq-strategy) + [backtest video](https://www.youtube.com/watch?v=SNO1wqJTq5A)

- **Fair value anchors**: 09:30 open price + 14:00 NY price. Two windows: 09:30–11:00 and 14:00–15:00, 1m chart only.
- **Two-phase**: first 10–15 min of window = **continuation** (push away from fair value, BOS entries); remainder = **mean-reversion** (return toward fair value, MSB entries). BOS = continuation signal, MSB = reversal signal, both confirmed by a **displacement candle (<20% counter-wick, measured via fib 0/0.2/1)**.
- **Risk**: ATR-tiered fixed points on NQ — above 20 ATR: 50pt SL / 75pt TP; 7–20: 25/37.5; below 7: 16.5/24.75 → fixed 1.5R, no management. ~$1k risk per trade at 1–3 contracts.
- **Testable arms**: (a) replicate the phase-split (continuation window vs reversion window WR/PF separately — the source's own FAQ says track them separately); (b) counter-wick <20% filter on/off; (c) ATR-tier stops vs structural stops (SL-1…SL-5); (d) 14:00 window standalone (it's also the Silver Bullet PM window — S5 overlap).
- **Learning**: is the 09:30-open a *better* mean-reversion magnet than VWAP (Q3) on NQ? The displacement-candle wick filter is directly reusable as a displacement-quality gate in S1–S3.

## C. New patterns worth adding to F1/F4 (one-liners from the library)

| Strategy (slug) | One-liner | Where it fits |
|---|---|---|
| `toto-capital-sbl-reversal-model` | SBL reversal model | F1 candidate |
| `tomtrades-cbr-model` | CBR model | F1 candidate |
| `icts-2025-venom-model` | ICT's 2025 Venom model | F1 candidate |
| `trader-kanes-nq-strategy-the-lab-model` | NQ "Lab Model" | F1/F5 candidate (NQ-native) |
| `ali-khan-dealing-range-theory` | Dealing range theory (premium/discount) | F1 — pairs with S3 zones |
| `omar-agag-ebp-strategy` | EBP strategy | F1 candidate |
| `bard-fx-compensation-play-nowick-strategy` | No-wick candles + structure + retest continuation | F4 (no-wick candle = Bandits' "Repair" cousin — O6) |
| `scarface-trades-scalping-strategy` | Scalping | F4 candidate |
| `jooviers-gems-hybrid-superscalp-strategy` | Hybrid super-scalp | F4 candidate |
| `waqar-asims-forex-scalping-strategy` | Forex scalping | F4 candidate |
| `doyle-exchange-strategy` | Doyle Exchange | candidate |
| `the-globex-strategy` | Globex (overnight session) strategy | **F2 candidate** — overnight/Globex session logic is absent from F1–F4 |
| `smb-capital-offsides-scalping-strategy` | SMB Offsides scalping | F2/F4 — "offsides" = momentum-chasers trapped, same family as failed-breakout fades |
| `maynes-monday-ranges` | Monday-specific ranges | **F2** — day-of-week conditioning (gap-stats Monday finding) |
| `wicksstrategy` | Liquidity/FVG/SMT wicks playbook | F3 overlap |
| `0xfibonaccis-crypto-confluence-strategy` | Crypto confluence | out of scope (indexes/forex focus) |
| `fibonacci-retracement-forex-swing-trading-strategy` | EMA + fractals + fib swing | F4 (swing) |
| `ict-unicorn-strategy` | Unicorn (OB+FVG combo) | F1 — repo already has Unicorn concept in ICT_CONCEPTS_KB |

## D. Process note

FX Replay's own backtest videos run these with on-screen sample sizes — useful calibration references when repo results diverge. PDFs (exact rules) are gated by email per page; fetch individually when a strategy is picked for the test queue. Every item here inherits the standard learning protocol from [README.md](README.md).