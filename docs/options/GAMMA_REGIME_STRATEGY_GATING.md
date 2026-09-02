# Options Gamma (GEX) Regimes & Asymmetric Strategy Gating
## The Empirical Framework: Regime-First Strategy Selection & Veto Rules

**Source / Authority**: PatternProfits (Ben) Empirical Trading Findings & NQStats Options Physics  
**Applies To**: NinjaTrader 8 Strategy Bots (`IBBreakoutBot`, `IBFadeBot`, `IBRetestBot`), Pine Script Indicators, Pre-Market Wargaming, and Daily Bias Briefings.

---

## 1. Executive Summary: Theory vs. Empirical Reality

A major pitfall in systematic and discretionary trading is the misapplication of options gamma theory to intraday momentum setups (Opening Range Breakouts, Initial Balance breaks, Golden Trifectas, and Fair Value Gap continuations).

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             THE CORE ASYMMETRIC PRINCIPLE                                │
│                                                                                          │
│  Options Gamma Regime is an ASYMMETRIC VETO FILTER, not a trade confirmation signal.     │
│  Negative Gamma does NOT mean "ride breakouts into a trend day."                         │
│  Negative Gamma means "trend continuation will fail into violent overshoots &            │
│  two-sided round-trips — VETO continuation algos and stand aside or fade overshoots."    │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### The Breakdown: Textbook Myth vs. Empirical Reality

| Metric / Dimension | Textbook Options Theory ("The Retail Trap") | PatternProfits (Ben) Empirical Reality |
| :--- | :--- | :--- |
| **Dealer Posture ($\Gamma < 0$)** | Dealers are short gamma $\rightarrow$ forced to sell into drops and buy into rallies. | Dealer hedging causes **extreme localized velocity and overshoots**, but **zero structural volume acceptance**. |
| **Trend Expectation** | "Hedging will accelerate the market into a runaway 1-way trend day." | "Hedging quickly pushes price to liquidity exhaustion, followed by an immediate, violent snapback in reverse." |
| **ORB / IB Behavior** | Breakouts/breakdowns will expand cleanly to $0.5\times\text{--}1.0\times$ IB extension targets. | **Double breaks of the Opening Range** (breaking the low first, trapping breakout shorts, then violently ripping to break the high). |
| **Strategy Decision** | Turn on Breakout Algos / trail wide stops for runners. | **VETO / Turn OFF Trend-Continuation Algos entirely.** Run mean-reversion fades only or stand aside. |

---

## 2. Mechanical Anatomy of Negative Gamma Failure Modes

### Why Negative Gamma Destroys Trend Continuation

In a genuine institutional trend day (e.g., structural value migration), buyers or sellers continuously bid/offer at new price tiers, building sustained volume acceptance.

In a **Negative Gamma ($\Gamma < 0$)** environment:
1. **Mechanical Speed Without Volume:** The initial move (e.g., ORB breakdown) is driven by dealer algorithms rebalancing delta. It creates large, aggressive candles that look like high-conviction institutional breakouts.
2. **The "Hedging Wall" Exhaustion:** As soon as dealers complete their delta adjustments for that strike cluster (or price reaches the Put Wall / Gamma Magnet), the mechanical selling abruptly halts.
3. **The Squeeze Back to Start:** Because liquidity is thin and order books are skittish in negative gamma, any responsive buying or short-covering forces dealers to **instantly flip into aggressive buyers**.
4. **The Round-Trip:** The counter-rally rips straight back through the opening range, turning what looked like a textbook $78\%$ win-rate setup into a full round-trip loss.

```
                         [09:30 RTH Open]
                                │
               ┌────────────────┴────────────────┐
               │                                 │
        (1) Fast Drop                     (3) Violent Snapback
     Dealers dump futures               Dealer selling exhausts.
     into the breakdown.                Dip buyers / short covering trigger
     Textbook ORB breakdown fires.      dealer buy-back cascade.
               │                                 │
               ▼                                 ▼
      [Overshoots IB Low]              [Rips Through IB High]
      Traps Breakout Traders            Traps Initial Sellers
      (Hits "Hedging Wall")            ("Double Break" of Range)
```

---

## 3. The 3-Regime Strategy Selection Matrix

Use this matrix pre-market (at 08:00 AM ET) to determine which automated bots and discretionary execution playbooks are authorized for the session:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             OPTIONS GAMMA REGIME                                 │
└──────────────────────┬───────────────────────────────────┬───────────────────────┘
                       │                                   │
           Positive Gamma (Γ > 0)                 Negative Gamma (Γ < 0)
         (Dealers Buy Dips, Sell Rips)             (Dealers Amplify Moves)
                       │                                   │
         ┌─────────────┴─────────────┐         ┌───────────┴───────────┐
         ▼                           ▼         ▼                       ▼
    [High Pin Odds]           [Breakout Fails]  [Inside Walls]     [Outside Walls]
         │                           │         │                       │
         ▼                           ▼         ▼                       ▼
   ✅ IBFadeBot (Play 3)      ❌ IBBreakoutBot   ⚠️ STAND ASIDE     ✅ IBBreakoutBot
   • Sweep of IB High/Low     • High fail rate  • Whipsaws &       (Play 1) / Retest (Play 2)
   • Target IB Mid / Pin      • False breaks      round-trips      • Ride dealer hedging cascade
```

### Strategy Deployment Rules

| Regime Condition | Active Strategy / Bot | Inactive / Vetoed Bots | Execution Mandate |
| :--- | :--- | :--- | :--- |
| **Positive Gamma ($\Gamma > 0$)**<br>High Pin Odds ($>20\%$), Compressed Walls | **`IBFadeBot` (Play 3)**<br>Discretionary FVG Sweeps | **`IBBreakoutBot` (Play 1)**<br>`IBRetestBot` (Play 2) | **Fade Extremes**: Expect false breakouts. Target IB Midpoint (TP1) and opposite boundary (TP2). |
| **Negative Gamma ($\Gamma < 0$)**<br>*Inside* Put/Call Walls ($<10\%$ Pin Odds) | **STAND ASIDE (Preferred)**<br>OR Discretionary Overshoot Fades | **`IBBreakoutBot` (Play 1)**<br>ORB Continuation Algos | **Take What's Offered**: No reaching. If trading, enforce +10 bps immediate 50% scale + BE lock (`CoverTheQueen`). |
| **Negative Gamma ($\Gamma < 0$)**<br>*Accepted Outside* Put or Call Wall | **`IBBreakoutBot` (Play 1)**<br>**`IBRetestBot` (Play 2)** | **`IBFadeBot` (Play 3)** | **Runaway Expansion**: Join momentum after close-confirmed acceptance outside the major wall. Do NOT fade. |

---

## 4. Morning Pre-Market Checklist (08:00 AM Routine)

Before enabling any automated strategy or committing to a directional bias, extract the live options profile via `nq-data-bridge`:

1. **Total GEX & GEX Regime:**
   * Is Total GEX positive or negative?
   * Is Put Gamma or Call Gamma dominating?
2. **Key Mechanical Coordinates:**
   * **Put Wall:** Structural floor where dealer short put hedging concentrates.
   * **Call Wall:** Structural ceiling where dealer short call hedging concentrates.
   * **Gamma Magnet:** The gravitational strike price where net dealer gamma approaches zero/neutrality.
   * **Expected Move (EM) Band:** $\pm 1.0\,\text{EM}$ range for the session.
3. **Pin Odds Calibration:**
   * Pin Odds $>20\% \implies$ Sticky session; favor mean reversion.
   * Pin Odds $<10\% \implies$ Diffuse gamma; slippery tape; high risk of multi-hundred point whiplashes.
4. **The Gate Decision:**
   * If $\Gamma < 0$ and spot is inside the Put/Call walls $\implies$ **VETO continuation algos**. Flag session as high-risk chop/overshoot.

---

## 5. Forward Validation & Quantitative Telemetry

To continually validate this empirical edge as data accumulates, all backtests and live trade logs must track the following metrics partitioned by **GEX Regime** (`POSITIVE_GEX` vs. `NEGATIVE_GEX`):

1. **ORB / IB Breakout Continuation Rate:** Percentage of IB breaks that reach $0.5\times$ and $1.0\times$ IB extension without breaking the opposite IB boundary.
2. **Double Break Rate:** Frequency of sessions where *both* IB High and IB Low are breached.
3. **MFE vs. MAE Ratio:** Distribution of Maximum Favorable Excursion vs. Maximum Adverse Excursion across percentiles ($p_{10}, p_{50}, p_{90}$).
4. **Round-Trip Rate:** Percentage of trades that reach $\ge +10$ bps MFE but subsequently reverse to hit the initial stop loss.

---

## 6. Governing Psychological Maxim

> **"A losing trifecta is variance, not a rule change — nothing here changes the framework, it's just what negative gamma does. Standing aside on a good-looking setup in a hostile regime is a victory of discipline, not a missed opportunity."**  
> — *PatternProfits (Ben)*
