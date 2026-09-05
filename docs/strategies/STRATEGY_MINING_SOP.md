# Strategy Mining & Backlog Sourcing SOP

> **Status**: OPERATIONAL GUIDE  
> **Goal**: Systematically discover, harvest, filter, and distill trading strategy ideas from global public sources (YouTube, TradingView, Quantpedia, GitHub, Academic Papers, Prop Firm Communities) and funnel them into [research_backlog](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/research_backlog/README.md) as falsifiable, mechanical test candidates.

---

## 1. Sourcing Philosophy & The Zero-Bullshit Filter

Over 95% of public retail trading strategies fail immediately due to **clickbait, lookahead bias, curve-fitting, or lack of defined risk**. Our mining engine rejects narrative hype and enforces four baseline admission criteria:

1. **Falsifiability**: A strategy must be reducible to explicit Boolean and numeric expressions (`IF condition_a AND condition_b THEN enter`). Vague discretionary cues (*"wait for buyer exhaustion"*) must either have a quantifiable proxy (*"Kaufman Efficiency < 0.30 + Delta absorption"*) or be rejected.
2. **Universal Basis Points (bps) Normalization**: Point-based stops and dollar targets are banned. Every rule must be expressed in **basis points (bps)**, price percentage (%), or ATR multiples (per [universal_basis_points_and_statistics.md](file:///c:/Users/vinay/tvDownloadOHLC/.agents/rules/universal_basis_points_and_statistics.md)).
3. **Execution Realism**: Strategies relying on zero-slippage limit order fills inside tight ranges or sub-second latency arbitrage are disqualified.
4. **Isolated Hypotheses**: We test **one mechanism at a time**. Multi-indicator "kitchen sink" strategies must be dismantled into modular arms before backtesting.

---

## 2. Multi-Channel Discovery Engine

Beyond YouTube, high-conviction mechanical trading edges are distributed across specialized quant platforms, code repositories, and institutional research portals.

```
                                  ┌──────────────────────────────────────────────┐
                                  │           GLOBAL STRATEGY SOURCING           │
                                  └──────────────────────┬───────────────────────┘
                                                         │
         ┌───────────────────┬───────────────────────────┼───────────────────────────┬────────────────────┐
         ▼                   ▼                           ▼                           ▼                    ▼
   ┌───────────┐      ┌──────────────┐            ┌──────────────┐            ┌──────────────┐     ┌──────────────┐
   │  YouTube  │      │ TradingView  │            │ Quant Portals│            │ Open Source  │     │ Order Flow & │
   │ Transcripts│     │ Community    │            │ & Academic   │            │ GitHub Repos │     │ Prop Forums  │
   └─────┬─────┘      └──────┬───────┘            └──────┬───────┘            └──────┬───────┘     └──────┬───────┘
         │                   │                           │                           │                    │
         ▼                   ▼                           ▼                           ▼                    ▼
  [NotebookLM]        [PineAST Parser]           [Quantpedia/SSRN]            [Freqtrade/LEAN]     [Futures.io]
         │                   │                           │                           │                    │
         └───────────────────┴───────────────────────────┼───────────────────────────┴────────────────────┘
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │ 4-Stage Filtration Gate      │
                                          │ (Metadata, Trinity, Realism) │
                                          └──────────────┬───────────────┘
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │ Research Backlog Admission   │
                                          │ (docs/strategies/backlog/)   │
                                          └──────────────┬───────────────┘
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │ Python Hunter: hunt()        │
                                          │ Canonical Parity Backtest    │
                                          └──────────────────────────────┘
```

---

## 2.1 Autonomous Multi-Source Harvester (`scripts/mining/`)

To eliminate manual searching across websites and portals, the repository provides an automated, multi-threaded harvester:

```powershell
.\.venv\Scripts\python.exe -m scripts.mining.harvest_all `
    --channels youtube,tradingview,quantpedia,github `
    --archetypes mean_reversion,opening_range,ema_pullback,squeeze `
    --max-per-source 25 `
    --output-dir data/strategies/raw_mined
```

### What the Harvester Automates Without User Interaction:
1. **YouTube Miner**: Queries targeted mechanical phrases via `scrapetube`, checks duration/title filters, and auto-downloads complete English transcripts using `youtube_transcript_api`.
2. **TradingView Miner**: Hits TradingView's `pubscripts-suggest-json` API for each archetype, filters for `type: 2` (`strategy()`), and fetches full Pine Script source code from `pine-facade.tradingview.com`.
3. **Quantpedia Screener Crawler**: Scrapes `quantpedia.com/screener/`, downloads full strategy research profiles (rules, math formulas, and original academic paper links).
4. **GitHub Code Miner**: Queries public GitHub APIs for open-source Pine Script and Python backtest implementations matching the target archetypes.
5. **Unified Triage Engine**: Scores each candidate against the 100-point rubric (§3) and exports passing candidates into `data/strategies/raw_mined/triage_summary.json` and Markdown candidate cards ready for the backlog.

---

## 2.2 Trader-Centric Strategy Taxonomy & Dedicated NotebookLM Registries

A professional trading desk organizes strategies by **underlying mathematical edge and structural market mechanism**, never as an undifferentiated list. In particular:
* **GEX (Gamma Exposure) is a structural market microstructure discipline**, distinct from price indicators. It models mandatory institutional dealer delta-hedging obligations that dictate whether price experiences mean-reverting volatility dampening (Long Gamma) or trend-accelerating liquidation cascades (Short Gamma).
* **Options Trading strategies are divided into distinct disciplines ("books")**, because an intraday 0DTE credit spread, an institutional sweep order-flow tracker, an earnings IV-crush play, and a 45-DTE multi-leg income structure exploit completely different edges, timeframes, and Greeks exposures.

Each domain maps 1-to-1 to a dedicated **Google NotebookLM Knowledge Base** for automated AI synthesis, parameter consensus, and mechanical code extraction:

| Domain / Discipline | Archetype Key | Dedicated NotebookLM Knowledge Base | Notebook UUID | Direct URL |
| :--- | :--- | :--- | :--- | :--- |
| **Stock Scanners & Screeners** | `stock_scanners_screeners` | **Stock Scanners & Algorithmic Screener Systems** | `80b7afae-c643-4af5-89ce-fdf309ab3034` | [Open Notebook](https://notebooklm.google.com/notebook/80b7afae-c643-4af5-89ce-fdf309ab3034) |
| **Volatility Systems & VCP** | `volatility_systems_vcp` | **Volatility-Based Strategies & Contraction Patterns (VCP, ATR, NR7)** | `6c55f605-5ce5-4530-bba4-14c4be9a4cfd` | [Open Notebook](https://notebooklm.google.com/notebook/6c55f605-5ce5-4530-bba4-14c4be9a4cfd) |
| **Market Microstructure & Dealer Hedging** | `gamma_exposure_gex` | **Gamma Exposure (GEX) & Market Maker Hedging Strategies** | `dbbc0d63-d9df-4378-a958-d8f15ac60f3b` | [Open Notebook](https://notebooklm.google.com/notebook/dbbc0d63-d9df-4378-a958-d8f15ac60f3b) |
| **Options: 0DTE & Intraday Credit** | `options_0dte_intraday` | **0DTE & Intraday Options Strategies** | `738e4a0a-5bd4-4c30-8f3a-378d33e57c7a` | [Open Notebook](https://notebooklm.google.com/notebook/738e4a0a-5bd4-4c30-8f3a-378d33e57c7a) |
| **Options: Order Flow & Sweeps** | `options_orderflow_sweeps` | **Options Order Flow & Unusual Institutional Activity** | `38589732-c5f0-43e5-9c29-b6fd0be0e051` | [Open Notebook](https://notebooklm.google.com/notebook/38589732-c5f0-43e5-9c29-b6fd0be0e051) |
| **Options: Volatility & Events** | `options_volatility_events` | **Options Volatility, IV Crush & Event Trading** | `0861f9b9-ce76-4cbb-84a7-532fd157880e` | [Open Notebook](https://notebooklm.google.com/notebook/0861f9b9-ce76-4cbb-84a7-532fd157880e) |
| **Options: Spreads & Systematic Income** | `options_spreads_income` | **Options Multi-Leg Spreads & Systematic Income** | `ef3a98ae-ac9a-40f6-b423-13b63f6d87a1` | [Open Notebook](https://notebooklm.google.com/notebook/ef3a98ae-ac9a-40f6-b423-13b63f6d87a1) |
| **Indicators & Oscillators** | `indicator_oscillators` | **Indicator & Oscillator Systematic Strategies** | `c9e73ff9-b36b-4d74-af98-7a35c70c3d3d` | [Open Notebook](https://notebooklm.google.com/notebook/c9e73ff9-b36b-4d74-af98-7a35c70c3d3d) |
| **Range, Chop & Congestion** | `range_chop_congestion` | **Consolidation & Range Day Trading Strategies** | `b52fb636-8a91-40f3-9035-def8b94cb090` | [Open Notebook](https://notebooklm.google.com/notebook/b52fb636-8a91-40f3-9035-def8b94cb090) |
| **Price Action: TheStrat** | `the_strat` | **The Strat Methodology & Automated Trading Systems** | `4f569cc3-220e-408d-afaf-47add3fb67f1` | [Open Notebook](https://notebooklm.google.com/notebook/4f569cc3-220e-408d-afaf-47add3fb67f1) |
| **Price Action: Opening Range (ORB)** | `opening_range` | **0930 All Day ORB Data Analysis** | `d86e9c4d-5645-47b2-9ccb-29bd58fdfc22` | [Open Notebook](https://notebooklm.google.com/notebook/d86e9c4d-5645-47b2-9ccb-29bd58fdfc22) |
| **Price Action: Mean Reversion / VWAP**| `mean_reversion` | **VWAP Trading Strategies Master Knowledge Base** | `c9856fd5-3394-49db-ac05-9594db94dd00` | [Open Notebook](https://notebooklm.google.com/notebook/c9856fd5-3394-49db-ac05-9594db94dd00) |
| **Price Action: Squeeze & Volatility** | `squeeze_breakout` | **Keltner Channel APEX Strategy Architecture & Research** | `902133c5-3efc-4853-ac18-2631efb61397` | [Open Notebook](https://notebooklm.google.com/notebook/902133c5-3efc-4853-ac18-2631efb61397) |
| **Price Action: ICT & Orderblocks** | `ict_smc` | **ICT Orderblock Model & Market Analysis** | `00068bc6-fb1e-40ce-aa93-d032d6478db5` | [Open Notebook](https://notebooklm.google.com/notebook/00068bc6-fb1e-40ce-aa93-d032d6478db5) |

---

### Channel 1: YouTube & NotebookLM Video Mining

* **Target Creators**:
  * *Code & Backtest First*: The Art of Trading, TradeZone, Critical Trading, Dave Teaches, Quant Nomad.
  * *Market Profiling & Auction*: Matt Mickey & Austin, TradePro, Al Brooks systematic distillers.
* **Discovery Queries**:
  ```text
  "algorithmic trading strategy" "backtest" ("Pine Script" OR "NinjaTrader" OR "Python") -crypto -shorts
  "opening range breakout" "rules" ("NQ" OR "ES" OR "futures") ("win rate" OR "edge") -shorts
  "mean reversion" ("VWAP" OR "Bollinger Bands" OR "RSI") ("rules" OR "setup") "stop loss" -forex
  ```
* **Filtration Pipeline**:
  1. *Metadata*: Duration 8–35 minutes; exclude titles with "100% win rate", "infinite money", "never lose".
  2. *Description*: Require presence of indicator parameters or code links (GitHub, Pastebin, TradingView).
  3. *Spoken Transcript*: Verify the "Holy Trinity" (Indicator + Trigger + minimum 2 mentions of "stop loss" / "risk").
* **NotebookLM Synthesis**:
  * Ingest batches of 20–30 vetted video URLs into themed notebooks (`YT-MeanReversion`, `YT-Breakouts`, `YT-ICT`).
  * Query via Antigravity MCP (`notebook_query`) for parameter consensus and unified mechanical rule cards.

---

### Channel 2: TradingView Community Scripts & Open-Source Strategies

TradingView hosts over 100,000 public Pine Scripts. Many are indicators, but several thousand are full `strategy()` scripts with built-in backtest engines.

* **Target Locations**:
  * **TradingView Script Search**: Filter by **Type: Strategies** (not Indicators).
  * **Categories**: Trend Analysis, Volatility, Oscillators, Volume.
  * **Editors' Picks & Top Boosted**: High-reputation open-source scripts with active community inspection.
* **Search Operators & Queries**:
  * Keywords: `"mean reversion"`, `"opening range"`, `"institutional"`, `"volatility squeeze"`, `"fair value gap"`.
  * Pine Filter: Target `//@version=5` and `//@version=6` scripts (cleaner syntax, less legacy code).
* **Automated Screening & Red-Flag Checks**:
  1. **Repainting / Lookahead Bug**: Flag any script using `request.security(..., lookahead = barmerge.lookahead_on)` or evaluating `close` of the current higher-timeframe unclosed bar.
  2. **Intrabar Fills Distortion**: Check whether `calc_on_every_tick=true` or `calc_on_order_fills=true` is used without realistic slippage.
  3. **Commission & Slippage Setting**: Does the author test with zero commission on 1m bars? If so, recalculate with institutional defaults ($2.00/side, 1 tick slippage).

---

### Channel 3: Systematic Quant Portals & Academic Research

Academic and institutional quant websites offer pre-vetted, peer-reviewed edges that have survived statistical scrutiny.

* **1. Quantpedia (The Encyclopedia of Algorithmic Trading)**:
  * Over 800+ documented quantitative trading strategies from academic papers.
  * *Best Categories for this Repo*: Intraday Futures, Momentum/Reversal Factor, Calendar/Session Seasonality, Volatility Arbitrage.
  * *Format*: Clear summary of the academic paper, explicit mechanical rules, asset universe, and historical performance.
* **2. QuantConnect / Quantopian Archive (Alpha Streams)**:
  * Public community forums and algorithm repositories.
  * Complete, reproducible Python/C# algorithms tested against tick data.
* **3. SSRN & arXiv (Quantitative Finance / `q-fin.TR`, `q-fin.ST`)**:
  * Academic papers on order flow toxicity (VPIN), order book imbalance (OFI), high-frequency volatility jumps, and overnight vs. intraday drift.
* **4. QuantifiedStrategies.com**:
  * 100+ fully disclosed, backtested rulebooks (already indexed in [06_quantifiedstrategies_100.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/research_backlog/06_quantifiedstrategies_100.md)).

---

### Channel 4: Open-Source Quant Frameworks & Strategy Libraries

Open-source backtesting engines have vibrant communities contributing production-tested strategies:

* **1. Freqtrade Strategy Repositories**:
  * The mathematical signal logic (Kaufman Adaptive, TTM Squeeze, graded $\sigma$-tier reversion, Volume Capitulation) translates directly to intraday index futures.
  * Cross-referenced in [08_freqtrade_library.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/research_backlog/08_freqtrade_library.md).
* **2. GitHub Curated Repositories**:
  * Repositories tagging `#algorithmic-trading`, `#pine-script-strategies`, `#ninjascript`.
  * Search queries: `path:*.pine strategy.entry language:Pine`, `path:*.cs OnBarUpdate SetStopLoss language:C#`.

---

### Channel 5: Professional Futures & Prop Firm Communities

Discretionary order flow and prop firm traders frequently discover structural market nuances before quants formalize them.

* **1. Futures.io (NexusFi)**:
  * The premier community for NinjaTrader 8 (.cs) strategies, Sierra Chart studies, and Market Profile / Order Flow.
  * **Automated Miner**: `scripts/mining/futures_io_miner.py`.
  * **Session Authentication**: Futures.io requires login cookies to access elite attachments (.cs and .zip files). Export your browser cookies (e.g. via Cookie-Editor) to `data/strategies/raw_mined/futures_io_cookies.json` to enable automated downloading of forum attachments and indicators.
* **2. FXReplay & TheStrat Communities**:
  * Mechanical bar classification rules: TheStrat 1-2-3 models, Failed 2s, and Fair Value open magnets (documented in [05_fxreplay_library.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/research_backlog/05_fxreplay_library.md)).
* **3. Prop Firm Bandit / Institutional Wargaming**:
  * Mickey & Austin Re-engineering tactics: In-stat vs. Out-of-stat boundaries, P12 Mid switches, +10 bps "Cover the Queen" scale-outs.

---

### Channel 6: Reddit Algorithmic & Futures Communities

Reddit provides two high-signal subreddits when filtered aggressively:

* **r/algotrading**: High-signal quant discussions on statistical arbitrage, walk-forward testing, cointegration, and lookahead bias pitfalls.
* **r/FuturesTrading**: Practical intraday ES/NQ setups, anchored VWAP standard deviation bands, Opening Range Breakout (ORB) models, and prop-firm risk management rules.
* **Automated Miner**: `scripts/mining/reddit_miner.py` supports authenticated Reddit API OAuth (`client_id` / `client_secret`) and maintains an indexed library of verified institutional models.

---

### Channel 7: BabyPips Mechanical Systems

BabyPips is famous for classic, strictly rule-based mechanical systems. While originally designed for forex, their underlying mathematical mechanics (multi-timeframe EMA alignment, ADX trend regimes, session breakout windows) transfer seamlessly to index futures (NQ1/ES1):

* **The Cowabunga System**: Multi-timeframe trend alignment (4H trend bias with 15m/5m 5/10 EMA crossover + MACD histogram flip).
* **HLHB Trend-Catcher**: EMA crossover with ADX > 25 regime conviction and RSI filter.
* **London Daybreak**: Asian session range compression break into London Open.
* **Futures Adaptation**: The miner automatically converts pip-based distances into **universal basis points (bps)** and ATR brackets suitable for NQ1.
* **Automated Miner**: `scripts/mining/babypips_miner.py`.

---

## 3. Backlog Admission & Triage Scorecard

Before adding an idea to `docs/strategies/research_backlog/`, it must be scored out of 100 points:

| Gate | Criterion | Points | Disqualification Rule |
| :--- | :--- | :---: | :--- |
| **G1: Rule Precision** | Unambiguous Boolean entry & exit formulas. No subjective discretion. | 30 | Score < 20 = REJECT |
| **G2: Risk Architecture** | Defined Stop Loss in bps/ATR + defined Take Profit / Scale-out. | 25 | Missing SL = INSTANT REJECT |
| **G3: Lookahead Immunity** | Verified zero lookahead, zero repainting, closed-bar execution. | 20 | Lookahead bug = REJECT |
| **G4: Friction Resilience** | Survives realistic commissions + 1 tick slippage per leg. | 15 | Edge < 4 bps = REJECT |
| **G5: Regime Specificity** | Explicitly specifies session window (`NY_AM`, `ASIA`, etc.) or regime. | 10 | "Works 24/7 on all markets" = Flag |

**Admission Threshold**: Must score **$\ge 75/100$** to enter the backlog.

---

## 4. Backlog Entry Format

Every accepted strategy candidate is added to the appropriate family file in `docs/strategies/research_backlog/` using this standardized template:

```markdown
### [ITEM-ID] Strategy Title

* **Source**: URL / Channel / Paper / Repository citation.
* **Triage Score**: XX / 100 (Pass).
* **Core Hypothesis**: One falsifiable sentence (e.g., "Sweeps of the 09:30 Opening Range prior to 09:45 revert to the session VWAP with >65% probability when prior day was Range 1").
* **Independent Test Arms**:
  * `Arm 0 (Baseline)`: Raw setup trigger without secondary filters.
  * `Arm 1`: Baseline + Session Gate (09:30–10:30 ET only).
  * `Arm 2`: Baseline + Kaufman Efficiency Ratio filter (KER > 0.40).
* **Mechanics**:
  * *Timeframe*: 1m / 5m NQ1.
  * *Setup*: Math formulas for state indicator.
  * *Trigger*: Bar close event.
  * *Risk*: Stop Loss in bps / ATR; Target 1 (Cover the Queen +10 bps); Target 2 (Runner).
* **Param Grid**:
  * Parameter A: `[val1, val2, val3]`
  * Parameter B: `[val1, val2]`
```

---

## 5. From Backlog to Execution Pipeline

Once in the backlog, the strategy follows the repo's canonical life-cycle:

1. **Synthesize Python Hunter**: Implement `hunt(data, params) -> DataFrame` and `get_param_grid()` in `scripts/strategies/<family>/core/<name>.py`.
2. **Register in Factory**: Add lambda factory entry to [registry.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_framework/strategies/registry.py#L55).
3. **Execute Canonical Command**:
   ```powershell
   .\.venv\Scripts\python.exe -m scripts.trading_framework.workflow `
       --strategy <strategy_key> --ticker NQ1 `
       --price-adjustment unadjusted `
       --optimize --trials 200 --oos-start 2025-01-01
   ```
4. **Evaluate Scorecard**: Review MFE/MAE excursions, out-of-sample survival, and checklist gates (§9 in [STRATEGY_WORKFLOW.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/STRATEGY_WORKFLOW.md)).
