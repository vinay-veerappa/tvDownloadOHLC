# Strategy Research Backlog — Master Index

> **Goal**: test each strategy in isolation → extract a **learning** (a conditional edge statement like "fade edge survives only in NY AM on compressed IB days") → compose learnings into multi-signal strategies afterward. No composition before isolation.
>
> **Sourcing & Discovery SOP**: See [STRATEGY_MINING_SOP.md](../STRATEGY_MINING_SOP.md) for how external strategies (YouTube, TradingView, Quantpedia, GitHub, Prop Forums) are discovered, filtered, and admitted into this backlog.

## The learning protocol

Every test run against this backlog MUST record:

1. **Hypothesis** — one sentence, falsifiable.
2. **Arms** — the variants tested (baseline + gates). One gate per arm; no shotgun stacking.
3. **Data window & universe** — which parquet(s), which years. Deep history (`data/{ticker}_1m.parquet`, 2006–2024) + live storage for recent years.
4. **Result table** — WR, PF, sample size, max DD — in **price % / bps** (ADR-002), RTH-only with 16:00 ET liquidation (ADR-020), prop-firm sim via `PropFirmSimulator` (ADR-021) when claiming viability.
5. **Learning** — the conditional statement, phrased as `IF <condition> THEN <setup> HAS <edge> ELSE <neutral>`. A learning that says "works everywhere" is a red flag (probably overfit).
6. **Composition notes** — which other backlog items this learning feeds.

Stratify every result by: **session bucket** (Asia/London/NY-AM/lunch/PM), **IB regime quint** (compression→expansion), and **day type** (R1/R2/DWP/DNP when labeled). A strategy's edge is usually a stratum, not the whole.

## Families

| Doc | Family | Items | Highest composition value |
|---|---|---|---|
| [01_ict_smc_price_action.md](01_ict_smc_price_action.md) | ICT/SMC price action | S1–S7 | S2 trendline-liquidity-CHoCH (image #2) · S3 S/D bases (image #1) · S7 killzone meta-test |
| [02_statistical_quant_intraday.md](02_statistical_quant_intraday.md) | Statistical/quant | Q1–Q7 | Q2 gap-fill ladder · Q4 80% rule · Q7 0DTE-EM conditioning |
| [03_orderflow_volume.md](03_orderflow_volume.md) | Orderflow/volume | O1–O6 | O4 POC/LVN target model · O6 repair-decay curve |
| [04_patterns_indicators.md](04_patterns_indicators.md) | Patterns & indicators | P1–P8 | P4 H1-vs-H2 confirmation count · P5 measured-move TP module · P1 HMA vs EMA seat |
| [05_fxreplay_library.md](05_fxreplay_library.md) | FX Replay library cross-ref | F5.1–F5.2 + catalog | F5.1 Failed 2s (1H TheStrat #3 target) · F5.2 Fair Value Theory (09:30-open magnet) |
| [06_quantifiedstrategies_100.md](06_quantifiedstrategies_100.md) | QuantifiedStrategies 100 (EOD-backed) | F6.1–F6.5 + catalog | F6.1 IBS fade · F6.3 inside-bar day-type prior · F6.4 session-extreme close-vs-wick handling rule |
| [07_swing_options_investment.md](07_swing_options_investment.md) | Options / swing / investment | O-1..O-3, W-1..W-5, I-1..I-4 | O-1 0DTE credit structures (GEX/EM strikes) · W-1 PEAD event-window · W-2 Connors ETF reversion · I-1/I-2 as regime seats for everything else |
| [08_freqtrade_library.md](08_freqtrade_library.md) | Freqtrade strategies (Python, crypto-native) | F10.1–F10.4 + mechanism borrowings | F10.1 volume-spike capitulation confirm · F10.2 graded σ-tier reversion ladder · F10.4 TD Sequential · time-decaying ROI exit module |
| [09_gamma_exposure_gex.md](09_gamma_exposure_gex.md) | Gamma Exposure (GEX) & Dealer Positioning | GEX-1..GEX-3 | GEX-1 Zero Gamma Volatility Trigger · GEX-2 Call/Put Wall Fade · GEX-3 OPEX Pinning |
| [10_options_books.md](10_options_books.md) | The Options Books (4 Disciplines) | OPT-0DTE-1, OPT-FLOW-1, OPT-VOL-1..2, OPT-INC-1 | OPT-0DTE-1 GEX Iron Condors · OPT-FLOW-1 Golden Sweeps · OPT-VOL-1 PEAD Drift · OPT-INC-1 45-DTE BWB |
| [11_stock_scanners_vcp_volatility.md](11_stock_scanners_vcp_volatility.md) | Stock Scanners & Volatility Systems | SCAN-1..2, VCP-1..3 | SCAN-1 Stockbee Episodic Pivot · SCAN-2 Momentum Burst · VCP-1 Minervini VCP · VCP-2 Crabel NR7 · VCP-3 Raschke 80-20 |
| [12_range_chop_congestion.md](12_range_chop_congestion.md) | Range, Chop Zones & Anti-Chop Defense | RANGE-80PCT, KER/ADX Gates | RANGE-80PCT Dalton 80% Rule · KER < 0.30 Chop Gate · 5 Anti-Chop Circuit Breakers |
| [13_market_regime_definition.md](13_market_regime_definition.md) | **Infrastructure — not a strategy** | REG-1 | **DECIDED 2026-09-06 (user): keep the quarter proxy, adapt when something better is found.** The lookahead defects are fixed; the five arms are measured (A′ VIX-10d tercile leads but fails era stability — the reason nothing was adopted); the item stands as the record of the candidates and the adoptability checklist a future definition must beat |
| [14_session_range_lookahead.md](14_session_range_lookahead.md) | **Infrastructure — not a strategy** | REG-2 | **CLOSED 2026-09-05** (ADR-026, option A): `sessions.py` stamped the whole day's final session aggregate onto every bar — a 01:21 Asia bar read the 07:30 NY1 mid. Values are now NaN before their window closes; box status is as-of-t with a `Pending` state; the defect record and evidence remain in the item |

## Suggested first wave (cheap, high-information)

| # | Test | Why first | Family |
|---|---|---|---|
| 1 | **S7 killzone meta-test** on existing validated hunters | Signals already exist; pure stratification, no new code | F1 |
| 2 | **Q2 gap-fill ladder** on 20-yr NQ 1m | Fully published numbers to replicate; falsification is meaningful | F2 |
| 3 | **S2 trendline sweep→CHoCH** | User-driven; reuses `trendline_structure.py` (already zero-lookahead, tested) | F1 |
| 4 | **P4 H1-vs-H2** | Detectors already in price_action suite | F4 |
| 5 | **O6 repair-decay curve** | NT8 Bandits folklore; simple count study | F3 |
| 6 | **P1 HMA vs EMA pullback** | Direct A/B, same data paths; settles the "simple indicators" question | F4 |
| 7 | **F5.2 Fair Value Theory** (09:30-open & 14:00 anchors) | Fully mechanical NQ rules already extracted in F5; ATR-tiered stops defined | F5 |
| 8 | **F6.1 IBS fade** | Zero new infra (pure OHLC); volume-free absorption proxy comparable to O1 | F6 |
| 9 | **W-2 Connors ETF reversion (RSI-25 / %B)** | Daily bars from Schwab API; distinct from retired intraday BB family | F8 |
| 10 | **O-1 0DTE credit structures** | Start as live forward paper-collection via TOS RTD (historical chains unavailable); infra exists | F7 |
| 11 | **F10.1 volume-spike dip-buy** + **F10.2 σ-tier ladder** | Open-source mechanical rules fetched; merges O5+Q3+IBS into one graded-reversion test | F10 |

## Cross-cutting priors (from repo history — treat as standing hypotheses to re-verify, not facts)

- Standalone ICT bias models: **negative edge**; session-adaptive versions: positive. Expect S1–S5 to need a session gate.
- ~76% of losses pre-10:30 — every F1/F2 entry technique inherits the 10:30 fence prior.
- Confluence-stacking hurts trend systems (Supertrend/FVG evidence) but helps fade systems (BB+RSI+hook). One gate at a time when testing anything.
- ATR-regime conditioning has repeatedly been the single best filter (IBB quint router, Supertrend Q4). Default-include an IB/ATR quint stratum in every test above.
- BB mean-reversion family **retired** except the overnight-VWAP-targeted ES core (E-series in BB_EXPERIMENTS.md). Don't rebuild BB variants; Q3's VWAP-band test is the surviving reversion lane.

## Known traps to avoid in every test

1. **Proxy-delta distortion** (F3): estimated CVD ≠ true delta; decide early whether F3 routes through NT8 tick data.
2. **Overfitting session windows**: pre-register the session buckets before looking at results.
3. **Multiple comparisons**: >6 arms per test → apply Benjamini-Hochberg; note it in the result table.
4. **The Strat lesson**: raw signal WR ≠ tradable WR. Report after-cost figures (1 tick slippage + commission convention from the_strat BACKTEST_RESULTS) alongside raw.
5. **Zero-loop standard** (ADR-017): new hunters must implement `hunt()` + `get_param_grid()` or live as one-off analysis scripts under `scripts/analysis/`, not as permanent strategy code.