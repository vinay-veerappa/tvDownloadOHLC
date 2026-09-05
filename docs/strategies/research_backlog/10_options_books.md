# The Options Books: Multi-Discipline Trading Systems — Research Backlog F10

> **Dedicated Google NotebookLM Registries**:
> 1. **0DTE & Intraday Options**: [738e4a0a-5bd4-4c30-8f3a-378d33e57c7a](https://notebooklm.google.com/notebook/738e4a0a-5bd4-4c30-8f3a-378d33e57c7a)
> 2. **Options Order Flow & Sweeps**: [38589732-c5f0-43e5-9c29-b6fd0be0e051](https://notebooklm.google.com/notebook/38589732-c5f0-43e5-9c29-b6fd0be0e051)
> 3. **Options Volatility & Events**: [0861f9b9-ce76-4cbb-84a7-532fd157880e](https://notebooklm.google.com/notebook/0861f9b9-ce76-4cbb-84a7-532fd157880e)
> 4. **Options Spreads & Income**: [ef3a98ae-ac9a-40f6-b423-13b63f6d87a1](https://notebooklm.google.com/notebook/ef3a98ae-ac9a-40f6-b423-13b63f6d87a1)
> **Standard**: Universal Basis Points (bps), Defined Greeks Exposure, Zero Lookahead.

---

## Architecture: Why Options Must Be Split into Distinct Books

Options are multidimensional non-linear derivatives. A single generic "options strategy" category is a design flaw:
1. **Intraday 0DTE Credit**: Exploits rapid intraday gamma decay ($\Gamma/\Theta$) within 6.5 hours of expiration.
2. **Order Flow & Sweeps**: Exploits asymmetric institutional informational advantage via aggressive ask-side sweep detection across multi-exchange books (CBOE, ISE, PHLX, BOX).
3. **Volatility & Events**: Exploits structural Implied Volatility (IV) mispricings, IV crush surrounding binary earnings events, and VIX term structure roll yield (Contango vs Backwardation).
4. **Multi-Leg Spreads & Income**: Exploits the persistent Volatility Risk Premium (VRP) over 30–60 DTE horizons via defined-risk delta-neutral structures (Broken Wing Butterflies, Calendars, The Wheel).

---

## Book 1: 0DTE & Intraday Options (`options_0dte_intraday`)

### OPT-0DTE-1. Asymmetric 0DTE Iron Condor with GEX-Informed Wings
**Status**: ⬜

* **Source**: Option Alpha 0DTE Research (`ENWFZOnb1qU`, `79415rgbUr8`), Tammy Chambless (`o-CmLEeiaoU`, `cqnL6-44ZOk`), Austin Bouley (`_2ztC63Ehtk`).
* **Triage Score**: **90 / 100** (Pass)
* **Core Hypothesis**: Selling 0DTE credit wings outside the daily Expected Move ($\pm 1.0\sigma$) and anchored to the Call/Put Walls yields a win rate $>78\%$ with positive expectancy when exited at 50% max profit or stopped at $2\times$ credit received.
* **Mechanics**:
  * *Entry Window*: 09:45–10:00 ET (allowing initial 15m opening discovery to settle).
  * *Strikes*: Short Call at $\max(\text{Expected Move High}, \text{Call Wall})$; Short Put at $\min(\text{Expected Move Low}, \text{Put Wall})$. Long wings placed 5 to 10 points further OTM.
  * *Trade Management*: Target = 50% of premium collected; Hard Stop Loss = $2.0\times$ credit collected; Mandatory hard exit at 15:45 ET.
* **Param Grid**:
  * Wing Width: `[5, 10, 15]`
  * Stop Multiple: `[1.5x, 2.0x, 2.5x]`

---

## Book 2: Options Order Flow & Sweeps (`options_orderflow_sweeps`)

### OPT-FLOW-1. Golden Sweep Smart Money Confluence Scanner
**Status**: ⬜

* **Source**: Unusual Whales (`TTfxnHQ1xog`), FlowAlgo / BrandonTrades (`HTfjhTlzlQw`), TC Trading (`g0eN0_-sVis`), Cheddar Flow (`GduN99Od31E`).
* **Triage Score**: **91 / 100** (Pass)
* **Core Hypothesis**: Filtering options tape for Golden Sweeps ($>\$1\text{M}$ premium, OTM, 30–60 DTE, Vol > OI) executed at the ask on non-ETF equities predicts directional momentum over 5–20 trading days with $>64\%$ win rate when confirmed by equity price holding above 20 EMA.
* **Mechanics**:
  * *Screener Filters*:
    1. Equity only (exclude SPY/QQQ/IWM to eliminate macro hedging).
    2. Premium $\ge \$1,000,000$.
    3. Moneyness: OTM (Delta between 0.20 and 0.40).
    4. Volume > Open Interest ($\text{Vol} > \text{OI}$).
    5. Execution: Multi-exchange sweep at or above the Ask.
  * *Trigger*: Equity breaks intraday resistance or holds daily 8 EMA following the sweep alert.
  * *Risk*: Stop loss placed under previous day's low; Target 1 at +200 bps; Target 2 at +500 bps (or trailing along 20 EMA).

---

## Book 3: Options Volatility & Events (`options_volatility_events`)

### OPT-VOL-1. Post-Earnings Announcement Drift (PEAD) Options Engine
**Status**: ⬜

* **Source**: tastylive (`CCLZNhKTwAQ`, `dF8ejgY-Sq8`), Financial Wisdom (`JwCQHdwj9lc`), Vincent Desiano (`9ZeYQ4vBMvQ`).
* **Triage Score**: **87 / 100** (Pass)
* **Core Hypothesis**: Buying ATM debit spreads or directional risk reversals immediately following a $>2.0\sigma$ earnings surprise and opening gap $>+5\%$ captures post-earnings institutional accumulation drift over a 15–30 day window with Sharpe $>1.3$.
* **Mechanics**:
  * *Screener Filters*: EPS Surprise $\ge +10\%$; Day-1 Gap $\ge +5\%$; Day-1 Close in top 30% of day's range.
  * *Entry*: Day 2 at 09:45 ET. Buy 30–45 DTE 40-delta call spread (financed by selling 20-delta put or debit spread).
  * *Risk*: Invalidation stop at announcement-day low; Profit target: 75% max value of spread or 21 DTE time-stop.

### OPT-VOL-2. VIX Term Structure Contango Roll-Yield Harvester
**Status**: ⬜

* **Source**: TraderMemento (`3CI-gjzslZE`), Live Options Trading with JR (`6foGx7Z1R1E`).
* **Triage Score**: **89 / 100** (Pass)
* **Core Hypothesis**: When the VIX futures term structure is in steep contango (M2 / M1 $> 1.08$), shorting short-term volatility products (SVXY / short VIX call spreads) captures structural roll yield with an annual win rate $>75\%$, gated by an immediate hedge when VIX crosses above its 50-day SMA.

---

## Book 4: Multi-Leg Spreads & Systematic Income (`options_spreads_income`)

### OPT-INC-1. 45-DTE Broken Wing Butterfly (BWB) with Zero Upside Risk
**Status**: ⬜

* **Source**: tastylive 45 DTE Mechanics (`v_gyQeYxOys`, `ZCcs2CgY-mI`), Prosper Trading Academy (`Gz-A9rCvH1s`).
* **Triage Score**: **93 / 100** (Pass)
* **Core Hypothesis**: Deploying 45-DTE Put Broken Wing Butterflies for a net credit or flat cost creates an asymmetric payout structure with zero risk to the upside and high probability of profit ($>82\%$) inside the profit tent, closed systematically at 21 DTE.
* **Mechanics**:
  * *Structure*: Buy 1 ATM/OTM Put ($K_1$), Sell 2 lower Puts ($K_2$), Buy 1 further OTM Put ($K_3$) such that $(K_1 - K_2) < (K_2 - K_3)$ and initial trade is entered for a small net credit or zero cost.
  * *Entry DTE*: 45 DTE $\pm 4$ days.
  * *Management*: Take profit at 25% of theoretical tent max; Hard close at 21 DTE regardless of PnL to eliminate tail gamma risk.
