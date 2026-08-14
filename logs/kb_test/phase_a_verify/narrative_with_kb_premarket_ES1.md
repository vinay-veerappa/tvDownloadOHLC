# Premarket Prep Notes — Thursday, August 6, 2026

## The Overnight Story

Globex was a ghost town. NQ opened at 7,756.75, rallied immediately to 7,770.75 by 18:34 ET, then spent the rest of the night bleeding back to where it started — currently sitting at 7,757.00, basically flat. That's a textbook "drift higher, late-session pullback" pattern: early strength that couldn't hold, fading into the pre-dawn. The high came in the first 34 minutes of the overnight session, which tells you there was no sustained buying interest after that initial pop. What this means for the open: we're looking at a cautious start. The overnight range was only 22.75 points — tight. No conviction. Price is sitting right in the middle of that range, which is a no-man's-land. The London session broke the overnight low (LdnBreak:True in the classification block), so there was at least one intra-session liquidity grab below 7,748.00, but it didn't hold.

KB context unavailable; inference uses quantitative cheat-sheet data only.

## GEX Structure — Where the Magnets and Walls Are

We're in **NEGATIVE GAMMA** territory. That's the destabilizing regime — dealers are hedging by selling into strength and buying into weakness, which amplifies moves. Price is currently at 7,757.00, sandwiched between the Put Wall at 7,734.53 (22 points below) and the Call Wall at 7,805.02 (48 points above). The Gamma Flip is way down at 7,281.33 — irrelevant for today's action. The price magnet sits at 7,738.96, which is just above the Put Wall.

Here's the key read: in negative gamma, price tends to trend rather than chop. But right now we're in a 70-point range between the two walls. The Put Wall at 7,734.53 is the downside floor — if price drops there, expect a bounce or at least a stall. The Call Wall at 7,805.02 is the upside ceiling — if we rally there, expect resistance. The magnet at 7,738.96 is the nearest gamma concentration, so price is "heat-seeking" toward that level. That's bearish bias for the open — we're above the magnet, so the path of least resistance is a drift down toward it.

## Prior EOD Classification — Does It Carry Forward?

Yesterday was classified as **DWP (Directional With Pullbacks)** — a trend day that broke the opening range and never returned, but had structural retracements along the way. That's a directional close with conviction. The overnight key shows "short false | short false | LdnBreak:True" — meaning the London session did break the overnight low, but the two "short false" flags suggest those breakdowns didn't sustain. The sequential model gives today's most likely outcome as **R2 (Range 2 — Reversal)** at 36.6% probability, with R1 at 24.7% and DWP at 23.6%.

**Overnight action contradicts the prior EOD classification.** Yesterday closed directional (DWP), but overnight was a flat, rangebound session with no follow-through. That's a loss of momentum. The model is calling for a reversal day (R2), not continuation. This is a classic "trend exhaustion" setup — yesterday's trend fades overnight, and today we're set up for a failed expansion that returns to the opening range after 11:00.

## Calendar Check — What Could Change the Picture

Today is a **SPECIAL** day type with a **HIGH** event at 08:30 ET: Initial Jobless Claims. That's the big one. We also have Unit Labor Costs, Nonfarm Productivity, and a slew of other releases at the same time. The guidance says "Reduce size" — 50% of normal position sizing. This is also **FOMC WEEK** and **NFP WEEK**, which adds a layer of caution. The 08:30 data dump is the primary risk event. If claims come in hot or cold, it could override the GEX structure and the classification model entirely. After 08:30, the calendar is low-impact until the Atlanta Fed GDPNow at 11:30 and FOMC Member Musalem speaks at 17:30 — both are after the main trading windows.

## Weekly Event Timeline — Where We Are

It's **Thursday** of FOMC week and NFP week. The KB context has a specific note about FOMC week protocol: "Normal FOMC week protocol" from the 2023-09-20 unit (conf=0.80) describes a pattern where the market builds a range early in the week, then resolves directionally around the event. We're past the FOMC decision (that was Wednesday), so today is the "aftermath" day — typically lower probability, tighter ranges, and a holding pattern before Friday's NFP. The regime tag for today is not explicitly stated in the cheat sheet, but given the flat overnight, the R2 classification, and the FOMC-week context, I'd tag this as **[CHOP → POTENTIAL EXPANSION]** — chop into the 08:30 data, then possible expansion after the release.

## ICT Intraday Time Map — Entry Timing Windows

The relevant windows for today:

- **08:30-11:00 NY Killzone** — This is the main event. The 08:30 data release kicks it off. The KB unit from 01_January 15 2024 (conf=0.90) identifies the "liquidity hunt macro" from 08:15 to 09:45. That's the window where the market runs stops and sweeps liquidity before establishing the day's direction. With the 08:30 data, the first 15 minutes will be volatile — don't read the first M1 candle (KB tip from 2023-11-10, conf=0.90: "Don't read this candle. Statistically, it doesn't make sense" — except on news days, which this is). So we can read the first M1 candle today because it's a news event.

- **10:00-11:00 Silver Bullet** — This is the second key window. After the initial 08:30 volatility settles, the Silver Bullet window is where the algorithm often delivers the "real" move of the day — a liquidity sweep followed by a reversal or expansion. Given the R2 classification (reversal after 11:00), the Silver Bullet could be the setup window for that reversal.

- **11:30-13:30 NY Lunch — NO-TRADE ZONE**. The cheat sheet explicitly calls this out. No new entries during lunch chop.

- **12:45 Macro** — The KB unit from 2023-05-19 (conf=0.90) describes the 12:45 macro as a time-based liquidity run. If we get a range established before 12:45, that window could see a sweep and then a CSD (change in state of delivery — a structural shift) for an afternoon entry. But given the no-trade zone until 13:30, this is only relevant if you're holding through lunch, which is not recommended.

## Bias Consensus

| Component | Signal |
|-----------|--------|
| Overnight Trajectory | Neutral (flat, drift higher then pullback) |
| GEX Regime | Negative Gamma — bearish bias, trend-favored |
| GEX Walls | Between Put Wall (7,734.53) and Call Wall (7,805.02) — range-bound |
| Classification (EOD) | DWP (directional) — but overnight contradicts |
| Sequential Model | R2 (reversal) — 36.6% probability |
| Weekly Context | FOMC aftermath — low probability morning, tight range expected |
| Calendar | 08:30 Jobless Claims — high impact, could override everything |

**Consensus: Mixed, leaning neutral-to-bearish with a reversal bias.** The GEX structure says negative gamma amplifies moves, but the walls create a 70-point range. The classification says reversal. The overnight says no conviction. The 08:30 data is the wildcard. No single dominant directional read — the core components are not aligned.

## KB-Evidenced Drivers

**1. FOMC Week Protocol — Low Probability Morning**
- **Conditional Rule:** "On principle, the morning of FOMC is generally low probability" with a tight range, shorter targets, and a slow holding pattern before the announcement. [KB:2023-06-14|conf=0.80]
- **How Today's Data Matches:** It's the day after FOMC (Thursday of FOMC week), and the overnight range was only 22.75 points — extremely tight. The sequential model calls for R2 (reversal), which is a range-expansion-failure pattern, consistent with a low-probability morning that resolves later. The 08:30 data release is the only catalyst that could break the tight range.
- **Inference:** Expect a slow, choppy open with a tight range until 08:30. After the data, we may get a quick expansion, but the FOMC-week context suggests the morning is not the time for directional conviction. Wait for the Silver Bullet window (10-11) for a higher-probability setup.

**2. Liquidity Hunt Macro (08:15-09:45) — Sweep Before Direction**
- **Conditional Rule:** "The liquidity hunt macro is 8:15 to 9:45" — this window is where liquidity is run (stops are taken) before the algorithm establishes the day's direction. [KB:01_January 15 2024|conf=0.90]
- **How Today's Data Matches:** The 08:30 Jobless Claims release falls right in the middle of this window. The overnight low is 7,748.00, and the London session already broke that level (LdnBreak:True). The Put Wall at 7,734.53 is the next major downside target. If the data is weak (higher claims), we could see a sweep down to the Put Wall during the liquidity hunt macro, then a reversal.
- **Inference:** Watch for a sweep of the overnight low (7,748.00) or the Put Wall (7,734.53) between 08:30 and 09:45. If price sweeps and then closes back above the swept level on the M5 timeframe, that's a potential MSS (market structure shift — a change in the direction of the trend) and a long entry setup for the Silver Bullet window.

**3. Disconfirming Path — What Invalidates the Reversal Setup**
- **Conditional Rule:** "If they sweep that in CSD I sell everything" — a CSD (change in state of delivery) after a liquidity sweep confirms the new direction. But if price does NOT sweep the key level and instead breaks through it without a retracement, the setup is invalid. [KB:10_October 11 2023|conf=0.70]
- **How Today's Data Matches:** The R2 classification expects a failed expansion — price breaks the opening range, fails, and returns after 11:00. If instead, price breaks the Put Wall (7,734.53) and continues lower without a retracement, that's a DNP (directional no pullback) scenario, invalidating the R2 reversal. Similarly, if price rallies through the Call Wall (7,805.02) and holds above it, the reversal bias is wrong.
- **Inference:** The invalidation for the reversal setup is a clean break of the Put Wall (7,734.53) with no retracement above it within 2-3 M5 candles. If that happens, the bias shifts to bearish continuation. Conversely, a break above the Call Wall (7,805.02) that holds would invalidate the bearish GEX bias and flip the outlook to bullish.

## Most Likely vs Alternate Outcome

**Most Likely: R2 Reversal (36.6% probability)**
- **Validation Trigger:** Price breaks the opening range (likely a small range around 7,755-7,765) in the first 30 minutes, fails to sustain the break, and returns into the range after 11:00. The 08:30 data causes a quick move that gets reversed. The Silver Bullet window (10-11) shows a sweep of either the overnight low or the Put Wall, followed by a CSD (change in state of delivery — a structural shift) back into the range.
- **Invalidation Trigger:** Price breaks the Put Wall (7,734.53) and closes below it on the M5 timeframe without retracing above it within 2 candles. Risk distance: 22.53 points from current price (7,757.00 - 7,734.53 = 22.53 points, or 0.29%).
- **No-Trade Condition:** If by 10:00 ET (Silver Bullet start) price has not made a clear sweep of either the overnight low or the Put Wall, and is still chopping in the 7,750-7,765 range, wait. Don't force a reversal trade without a liquidity sweep.

**Alternate: DWP Continuation (23.6% probability)**
- **Validation Trigger:** The 08:30 data triggers a strong directional move that breaks the Put Wall (7,734.53) and sustains the break. Price trends lower through the morning without returning to the opening range. The negative gamma regime amplifies the move — dealers sell into strength, accelerating the decline.
- **Invalidation Trigger:** Price bounces off the Put Wall and reclaims 7,760 (the overnight midpoint) within 30 minutes of the break. Risk distance: 3 points from current price to the bounce level (7,757.00 to 7,760 = 3 points, or 0.04%), but the real invalidation is reclaiming 7,770 (overnight high) — 13 points, or 0.17%.
- **No-Trade Condition:** If the 08:30 data causes a gap-and-go that doesn't retest the break level, it's a power trend (DNP). Don't chase. Wait for the first pullback to enter, or skip the trade entirely.

## What I'm Watching at the Open

1. **7,748.00 (Overnight Low) — The First Sweep Target.** If price opens below this and sweeps it, watch for a quick reversal back above it. That's the liquidity hunt macro in action. If it holds as support, the bias is neutral-to-bullish for the Silver Bullet. If it breaks and stays below, the Put Wall at 7,734.53 is the next stop.

2. **7,734.53 (Put Wall) — The Downside Floor.** This is the gamma concentration. If price reaches this level, expect a bounce or at least a stall. A clean break below it with no retracement invalidates the reversal setup and confirms bearish continuation. A bounce off it sets up the R2 reversal.

3. **7,770.75 (Overnight High) — The Resistance Ceiling.** If price can reclaim this level after the 08:30 data, it signals that the overnight weakness was a fakeout and the bulls are back in control. That would target the Call Wall at 7,805.02. But given the negative gamma regime, rallies are to be sold, not bought — so a break above 7,770.75 that fails would be a short entry opportunity.

**Scenario for the open:** Expect a volatile first 15 minutes around the 08:30 data. Don't trade the first M1 candle — wait for the M5 close after the initial spike. If price sweeps 7,748.00 and reverses, look for a long setup in the Silver Bullet (10-11) targeting a return to 7,770-7,780. If price breaks 7,734.53 cleanly, the path is open to 7,700 and below — but that's a low-probability move given the FOMC-week context. Most likely: chop, sweep, reversal.