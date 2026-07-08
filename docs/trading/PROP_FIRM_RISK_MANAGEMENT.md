# Prop Firm Trading & Risk Management — GEX-Driven Framework

> **Version:** 0.1 (Draft — 2026-07-07)
> **Status:** Living document. Tune parameters after each evaluation cycle.
> **Scope:** MES and MNQ futures on separate $50k prop-firm accounts with a $2,000 trailing drawdown limit each.
> **Data source:** SPY options chain → MES proxy; QQQ options chain → MNQ proxy. No direct futures options data is available, so all GEX levels are translated via the pipeline's `futures_px = strike × ratio + basis` conversion ([briefing_core.py L280](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trader/briefing_core.py#L280)).

---

## 1. Objective

Preserve the evaluation account. Keep total drawdown well below the $2,000 trailing limit. Only trade when the live GEX regime supports the setup. The goal is **capital preservation first, profit second** — a passed evaluation with modest gains is strictly superior to a blown evaluation with high theoretical returns.

---

## 2. Account Structure

| Parameter | MES Account | MNQ Account |
|---|---|---|
| Instrument | MES (Micro S&P 500 futures) | MNQ (Micro Nasdaq-100 futures) |
| Proxy underlying | SPY options chain | QQQ options chain |
| Starting balance | $50,000 | $50,000 |
| Trailing drawdown limit | $2,000 (4.0% of account) | $2,000 (4.0% of account) |
| Contract multiplier | $5 per point | $2 per point |
| Tick size | 0.25 points ($1.25/tick) | 0.25 points ($0.50/tick) |

**Rules:**
- Each account trades **one instrument only**. No cross-account hedging.
- One active position per account at a time. A second entry is allowed only as a **confirmed scale-in** (defined in §3.5) and must stay within the account risk cap.
- If either account hits its daily stop, that account stops trading for the day. No exceptions.
- **Correlation guard:** If both accounts are positioned in the same direction (both long or both short), the combined dollar risk across both accounts must not exceed **$200 total**. If the combined structural risk exceeds $200, reduce size on the weaker setup or skip the weaker one.
- **Max trades per day:** 3 entries per account. After 3 entries (regardless of outcome), that account is done for the day. This prevents death-by-a-thousand-cuts in choppy sessions.

---

## 3. Risk Parameters

### 3.1 Per-Trade Risk

| Parameter | MES | MNQ | Rationale |
|---|---|---|---|
| Risk per trade | **0.30% = $150** | **0.20% = $100** | MES is typically lower volatility than MNQ, so it can carry slightly more dollar risk. MNQ can overshoot faster, so it gets the tighter cap. |
| Max stop distance | Determined by structure | Determined by structure | If the structural stop is wider than the risk cap allows, **skip the trade**. Never widen the stop to force a position. |

### 3.2 Daily & Weekly Loss Limits

| Parameter | MES | MNQ | Rationale |
|---|---|---|---|
| Hard daily stop | **0.90% = $450** | **0.60% = $300** | Three full losses triggers a stop. Prevents a single bad day from consuming a large fraction of the $2,000 trailing drawdown. |
| Soft daily stop | **0.60% = $300** | **0.40% = $200** | If the tape is not giving clean follow-through, stop after two losses. Do not force trades in a choppy or regime-ambiguous session. |
| Weekly drawdown cap | **2.0% = $1,000** | **1.5% = $750** | Aligns with the repo's backtest engine concept ([BACKTEST_ENGINE_ARCHITECTURE.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/trading_system/BACKTEST_ENGINE_ARCHITECTURE.md)). Prevents a bad week from breaching the trailing drawdown before the weekend reset. |
| Max trades per day | **3** | **3** | Caps overtrading in chop. Each entry consumes attention and risk budget. |

### 3.3 Risk-of-Ruin Math

The $2,000 trailing drawdown is only 4% of a $50k account. At $150 risk per trade (MES), the account can absorb **13 consecutive full losses** before breach. At $100 risk per trade (MNQ), it can absorb **20 consecutive full losses**.

**Minimum reward-to-risk (R:R):** Every trade must target at least **1:2 R:R**. If the structural target does not offer 2× the stop distance, skip the trade. This ensures a 40% win rate produces positive expectancy:

$$\text{Expectancy} = (0.40 \times 2R) - (0.60 \times 1R) = +0.20R \text{ per trade}$$

**Consecutive-loss probability:** At 40% win rate, the probability of *n* consecutive losses starting from any given trade is $0.6^n$:

| Streak | MES ($150/loss) | MNQ ($100/loss) | Probability |
|---|---|---|---|
| 5 losses | $750 | $500 | 7.8% |
| 8 losses | $1,200 | $800 | 1.7% |
| 13 losses | $1,950 (breach) | — | 0.13% |
| 20 losses | — | $2,000 (breach) | 0.000037% |

**Important caveat:** These are per-streak probabilities from a single starting point. Over 100+ trades, the probability of encountering *some* 8+ loss streak somewhere in the sequence is materially higher. The daily stop (3 losses) and weekly cap are the real protection — they force a pause and prevent a streak from compounding into a blowup in a single session or week.

### 3.4 Why These Specific Numbers

| Factor | Reasoning |
|---|---|
| **0.20–0.30% per trade** | Industry standard for prop-firm evaluations is 0.5–1.0%, but those firms typically have larger drawdown buffers relative to account size. With only 4% trailing drawdown, we must be more conservative. At 0.30%, a full loss consumes only 7.5% of the drawdown budget. |
| **Separate accounts** | MES and MNQ are highly correlated. Separate accounts prevent accidental overexposure to a single macro thesis and keep risk accounting clean. |
| **MNQ gets tighter cap** | Nasdaq is historically 1.3–1.8× more volatile than S&P. The tighter dollar cap equalizes the *percentage-of-drawdown* risk across both instruments. |
| **Daily stop at 3× per-trade risk** | Three losses in one day is a signal that the read on the tape is wrong or the regime is ambiguous. Stopping prevents tilt-driven escalation. |
| **Soft stop at 2× per-trade risk** | In short-gamma regimes, chop is common. If two trades fail, the tape is likely not trending cleanly enough for the regime to reward continuation. |
| **Weekly cap at $1,000 / $750** | Aligns with the repo's backtest engine architecture. A bad week should never consume more than half the trailing drawdown budget. |
| **Max 3 trades/day** | Prevents overtrading in choppy sessions where small losses accumulate. |
| **Minimum 1:2 R:R** | Ensures positive expectancy at 40% win rate. Without this, a 50% win rate at 1:1 R:R only breaks even before commissions. |

### 3.5 Scale-In Definition

A "confirmed scale-in" is a second entry that meets **all** of the following:
1. The first entry is currently profitable (in-the-money).
2. The second entry is at a **better price** than the first (i.e., adding to a winner, not averaging down).
3. The combined position risk (entry to stop, both contracts) does not exceed the per-trade risk cap.
4. The regime has not changed since the first entry.

If any condition fails, no scale-in. Adding to a loser is **never** permitted (see §9).

---

## 4. Regime-Conditional Execution

The GEX regime dictates **how** to trade, not the direction. This is the repo's core doctrine ([DealerLevels.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/indicators/Options/DealerLevels.md)).

### 4.1 Regime Decision Matrix

| Regime | GEX Sign | Wall Width | Execution Style | Entry Trigger | Stop Placement | Target |
|---|---|---|---|---|---|---|
| **PINNED** | Positive | Tight | Fade walls → magnet | Limit at call/put wall | Beyond wall + buffer | Gamma magnet |
| **TRENDING** | Negative | Wide | Follow the trend | Break + retest of key wall | Beyond invalidation wall | Next structural node, then trail |
| **COILED** | Negative | Tight | Wait for breakout | Close outside gamma flip zone | Back inside flip zone | Nearest wall, then trail |
| **BATTLE ZONE** | Positive | Wide | Wall-to-wall swing | Limit at wall | Beyond opposite wall (wider) | Opposite wall |

### 4.2 Regime-Specific Rules

**PINNED (Positive GEX + tight walls):**
- Fade moves into the walls. Short near call wall, long near put wall.
- Target the gamma magnet.
- Keep stops tight — the pin can break if GEX flips negative.
- Invalidation: a confirmed close beyond the wall being faded.

**TRENDING (Negative GEX + wide walls):**
- Do **not** fade. Follow the trend after confirmation.
- Entry: break and hold past a key wall, then enter on the retest.
- **Trailing stop rule:** After entry, move the stop to break-even once price reaches 1R (1× the initial stop distance). After 2R, trail the stop to the most recent 5-minute swing high (for longs) or swing low (for shorts). Never trail tighter than the last bar's range — that guarantees a whipsaw exit.
- Take profit: scale out 50% at the next structural node (wall or magnet). Trail the remainder.
- Invalidation: a close back inside the broken wall.

**COILED (Negative GEX + tight walls):**
- Wait. Do not enter pre-emptively.
- Entry only after a candle **closes** outside the gamma flip zone.
- Stop tucked back inside the flip zone.
- Target: nearest wall, then trail if momentum expands.
- Watch for false breakouts — require confirmation, not just a wick.

**BATTLE ZONE (Positive GEX + wide walls):**
- Trade wall-to-wall with wider stops.
- Short at call wall, long at put wall.
- Position size for the full range — wider stops mean smaller size.

### 4.3 Regime Change Protocol

- If the pipeline emits a **REGIME CHANGE** alert mid-session, all open setups are re-evaluated.
- If the new regime contradicts the open trade's logic, flatten immediately.
- Do not "wait and see" — the regime change means the rules have changed.

---

## 5. Proxy-to-Futures Translation

Since we do not have direct futures options data, all GEX levels originate from the SPY and QQQ options chains. The pipeline translates these into futures scale using:

$$\text{Futures Price} = \text{Strike} \times \text{FUTURES\_RATIO} + \text{FUTURES\_BASIS}$$

Where `FUTURES_RATIO` and `FUTURES_BASIS` are stored as `META_FUTURES_RATIO` and `META_FUTURES_BASIS` in the unified levels file ([briefing_core.py L280](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trader/briefing_core.py#L280)).

**Current live values (from `unified_levels_open.txt`):**

| Proxy | Futures | Ratio | Basis |
|---|---|---|---|
| SPY → MES/ES | 10.1264 | 0.00 (not present for SPY open) |
| QQQ → MNQ/NQ | 41.9508 | 0.00 (not present for QQQ open) |

**Caveat:** This is an approximation, not true futures options data. The basis can drift intraday. The translation is good enough for structural levels (walls, gamma flip, magnet) but should not be treated as tick-precise futures pricing. Always confirm entries against the live futures tape before execution.

---

## 6. Position Sizing

### 6.1 Formula

$$\text{Contracts} = \left\lfloor \frac{\text{Risk Cap (\$)}}{\text{Stop Distance (points)} \times \text{Multiplier (\$/point)}} \right\rfloor$$

If the result is **0**, the stop is too wide for the risk cap — **skip the trade**.

### 6.2 Worked Examples

**MES example:**
- Risk cap: $150
- Stop distance: 5.00 points
- Multiplier: $5/point
- Contracts: $\lfloor 150 / (5.0 \times 5) \rfloor = \lfloor 6 \rfloor = 6$ contracts

**MNQ example:**
- Risk cap: $100
- Stop distance: 10.00 points
- Multiplier: $2/point
- Contracts: $\lfloor 100 / (10.0 \times 2) \rfloor = \lfloor 5 \rfloor = 5$ contracts

### 6.3 Sizing Table (Quick Reference)

**MES — $150 risk cap ($5/point multiplier):**

| Stop Distance (pts) | Max Contracts | Risk/Contract |
|---|---|---|
| 2.00 | 15 | $10 |
| 3.00 | 10 | $15 |
| 5.00 | 6 | $25 |
| 7.50 | 4 | $37.50 |
| 10.00 | 3 | $50 |
| 15.00 | 2 | $75 |
| 30.00 | 1 | $150 |

**MNQ — $100 risk cap ($2/point multiplier):**

| Stop Distance (pts) | Max Contracts | Risk/Contract |
|---|---|---|
| 5.00 | 10 | $10 |
| 10.00 | 5 | $20 |
| 15.00 | 3 | $33.33 |
| 20.00 | 2 | $50 |
| 25.00 | 2 | $50 |
| 50.00 | 1 | $100 |

---

## 7. Trade Execution Checklist

### 7.1 Pre-Open (8:30 AM ET)
- [ ] Read the daily open narrative and GEX levels.
- [ ] Identify the regime for SPY (→ MES) and QQQ (→ MNQ).
- [ ] Identify the bias (bullish / bearish / neutral).
- [ ] Map key levels to futures: call wall, put wall, zero gamma, gamma magnet, triggers, invalidations.
- [ ] Confirm the futures ratio and basis from the unified levels file.
- [ ] Check the economic events calendar (injected into the TOON JSON). Flag any high-impact releases (CPI, FOMC, NFP, Powell speech).
- [ ] Decide: which account(s) will trade today, and in what direction.
- [ ] If regime is COILED, plan to wait — no pre-emptive entries.
- [ ] **News rule:** No new entries 15 minutes before or 5 minutes after a high-impact release. Existing positions may be managed but not scaled into.

### 7.2 The Open (9:30 – 10:00 AM ET)
- [ ] Watch the first 30 minutes. Do not enter in the first 5 minutes unless the setup is extremely clear.
- [ ] Compare price action to the mapped triggers:
  - Acceptance above long trigger → bullish lean confirmed.
  - Break below short trigger → bearish lean confirmed.
  - Chop between triggers → wait for a clear break.
- [ ] In TRENDING: wait for break + retest before entry.
- [ ] In COILED: wait for a candle close outside the gamma flip zone.
- [ ] In PINNED: fade the wall only on rejection wicks.

### 7.3 Mid-Session (10:00 AM – 1:00 PM ET)
- [ ] Execute per regime rules.
- [ ] Trail stops in TRENDING.
- [ ] Check for regime change alerts from the pipeline.
- [ ] If soft daily stop is hit, evaluate whether the tape is clean. If not, stop for the day.

### 7.4 Afternoon & Close (1:00 – 4:00 PM ET)
- [ ] Check pin odds. If >25%, expect convergence to pin strike — tighten targets.
- [ ] Watch net vanna. Negative vanna → late-day selling pressure as IV drops.
- [ ] Flatten 0DTE risk by 3:45 PM ET.
- [ ] Per ADR-020: all intraday positions must exit by 16:00 ET (close of 15:59 bar).

---

## 8. Daily Review Template

At EOD, log the following for each account:

```
## EOD Review — [Date]

### MES Account
- Regime: [PINNED / TRENDING / COILED / BATTLE ZONE]
- Bias: [Bullish / Bearish / Neutral]
- Trades taken: [count]
- Result: [Win $ / Loss $ / No entry]
- Daily P&L: $[amount]
- Drawdown remaining: $[amount] of $2,000
- What worked:
- What didn't:
- Lesson for tomorrow:

### MNQ Account
- Regime: [PINNED / TRENDING / COILED / BATTLE ZONE]
- Bias: [Bullish / Bearish / Neutral]
- Trades taken: [count]
- Result: [Win $ / Loss $ / No entry]
- Daily P&L: $[amount]
- Drawdown remaining: $[amount] of $2,000
- What worked:
- What didn't:
- Lesson for tomorrow:
```

---

## 9. Prohibited Actions

1. **Never fade a TRENDING regime.** A call wall in TRENDING means "if it breaks, buy the breakout," not "short here."
2. **Never widen a stop to force a position.** If the structural stop exceeds the risk cap, the trade is skipped.
3. **Never average into a losing position.** No martingale, no "adding to the red."
4. **Never hold past 16:00 ET.** Per ADR-020, prop-firm intraday positions must exit by the close of the 15:59 bar.
5. **Never trade both accounts on the same thesis as if they were one.** Separate accounts exist for clean risk accounting. If both are positioned in the same direction, the correlation guard (§2) applies.
6. **Never ignore a regime change alert.** If the regime flips, the rules change. Re-evaluate or flatten.
7. **Never enter a trade with R:R below 1:2.** If the structural target does not offer at least 2× the stop distance, the trade is skipped.
8. **Never enter within 15 minutes before a high-impact news release.** Wait for the release to pass and the tape to settle.

---

## 10. Parameter Tuning Log

| Date | Parameter Changed | Old Value | New Value | Reason |
|---|---|---|---|---|
| 2026-07-07 | Initial draft | — | See above | Framework creation |

> **Tuning rule:** Do not change more than one parameter per evaluation cycle. Log every change with a reason. Review after every 20 trades or every 5 trading days, whichever comes first.