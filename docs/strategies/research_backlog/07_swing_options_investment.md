# Swing, Options & Investment Strategies — Research Backlog F7/F8/F9

> Scope expansion (user request 2026-08-30): multi-day/week swing strategies (stocks/options/ETFs), options income/premium structures, and months+ investment systems.
> **Data reality check**: repo's deep history is NQ/ES 1m futures. Stock/ETF swing tests need daily bars (Yahoo/IQFeed-style sources — the repo historically pulled SPY/QQQ data for gap studies; Schwab API also available). Options tests need the existing TOS RTD feed + Schwab auth (see OPTIONS_INVENTORY.md) or historical chains.
> Status legend per [README.md](README.md).

---

## F7. Options (0DTE / income / premium)

**Repo synergy**: EM walls (0DTE ±1σ), DealerLevels (GEX/gamma flip), TOS RTD live feed, and Q7's "0DTE-EM conditioning" — this family makes the options layer a strategy family of its own instead of a filter.

### O-1. 0DTE credit structures (SPX/NQX iron condors, credit spreads, iron flys)
**Status**: ⬜ (infrastructure exists; no backtest yet)

- **Published evidence** (SSRN 2026, 3,909 OptionAlpha backtests): median PF **1.98**, median WR 53.7%, 99.9% "profitable" in-sample — but heavily right-skewed (PF up to 138), many small samples → **selection-bias warning baked into the source itself**. Credit spreads had the best risk-adjusted profile; iron flies max per-trade return but low WR.
- **Counter-evidence** (FatTail 0DTE math): break-even needs ~70% win rate vs the ±1σ ≈68% containment → naive ±1σ condors are ~EV-zero before costs. Improvements that DO carry math: GEX-informed short strikes (pinning levels), skewed wing widths, entry after midday (peg probability rises), 50%-of-credit profit management, hard daily-loss cap.
- **Fully mechanical variant to port** (Jim Olson 0DTE iron fly): sell ATM straddle + wings at the open (wing width scaled to implied move: add $10 wings while each step earns ≥$1 credit), profit target $1.50 on the combined credit, hard stop at either break-even stock price, exit everything by 11:00 ET (decay is sparse 12:00–15:00), re-enter once after a stop-out.
- **Learning to extract**: (a) does GEX-flip + EM-wall strike selection beat delta-fixed strikes? (b) does the 2pm peg data (OptionAlpha table: 65.6% close within 0.2% of 2pm price) hold on repo SPX/ES data? (c) is the iron-fly open-sale + $1.5 target + BE stops net-positive after 5-cent tick economics?
- **Sources**: [SSRN 3,909 backtests](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7055179), [CBOE Schwartz deep-dive](https://www.cboe.com/insights/posts/henry-schwartzs-zero-day-spx-iron-condor-strategy-a-deep-dive), [OptionAlpha 0DTE research](https://optionalpha.com/learn/top-0dte-options-strategies), [FatTail math critique](https://fattail.ai/0dte-iron-condor/), [0dte.com Olson plan](https://0dte.com/jim-olson-iron-butterfly-0dte-trade-plan)

### O-2. Overnight theta / 0x-premium harvest (sell at close, buy at open)
**Status**: ⬜

- Classic structure: sell 1-dte OTM credit after close → buy back at open (theta accrues overnight; the "overnight edge" in equities is documented — F6's overnight SPY item). Options version monetizes the same drift with defined risk.
- **Learning**: overnight premium harvest EV vs futures overnight session (repo has Globex data!) — compare direct overnight futures fade vs options overnight premium on the same nights.

### O-3. Dealer-level strategies (GEX flip, charm/vanna flow)
**Status**: 🟡 indicators exist (DealerLevels.md); never traded standalone

- Hypotheses to test on 1m+GEX data: (a) above gamma flip point → mean reversion to POC/pin; below → volatility expansion (breakout-favoring — a regime gate for S1/S2/Q1); (b) OPEX-week pinning at max-pain (feeds F2 Q7); (c) large charm flows into 3–3:30 pm create predictable drift (afternoon drift test).

---

## F8. Swing (days to weeks — stocks/ETFs)

### W-1. PEAD (Post-Earnings Announcement Drift) — highest-priority academic anomaly
**Status**: ⬜

- One of the most persistent anomalies in finance (Wikipedia documents 8.76–43% annualized across studies). Drift lasts **60+ days** in surprise direction; ~25–30% of drift concentrates in the 3-day windows around the **next two earnings announcements** (Bernard & Thomas 1990) — meaning: hold to the next-earnings event.
- **Two implementable variants**:
  1. **Classic directional**: earnings surprise > k× std (SUE) → long, hold 40–60 trading days with stop at announcement-day low. Simple stock-level port; needs an earnings-surprise dataset (Schwab/FMP).
  2. **Event-window (higher concentration)**: build position 15 days *before* recurring-announcement date of stocks with prior strong surprise → hold through the announcement. One paper's estimated 67% annualized on exactly this structure.
- **Learning**: does the drift survive post-2015 (arbitrage erosion documented), which surprise-measure (SUE vs % price reaction day-1) predicts better, and does it work on liquid large-caps only (transaction costs) or does the small-cap premium survive costs?
- **Sources**: [Wikipedia PEAD](https://en.wikipedia.org/wiki/Post%E2%80%93earnings-announcement_drift), [Quantpedia variant](https://quantpedia.com/strategies/reversal-in-post-earnings-announcement-drift), [HHS thesis](http://arc.hhs.se/download.aspx?MediumId=297)

### W-2. Connors-style ETF mean reversion (RSI-25 / %B / Triple RSI)
**Status**: ⬜ (daily variant distinct from the retired intraday BB family — do NOT conflate)

- **RSI-25 ETF strategy**: ETFs in long-term uptrends (close > 200-day MA) bought at RSI(2) ≤ ~25 extremes, exit on close above the 5-day SMA; average hold 3–7 days ([swingfolio write-up](https://swingfolio.com/education/level-6-advanced-strategies/rsi-25-strategy-etfs)).
- **%B strategy** (Connors "High Probability Trading" ch.5): close above 200-day MA AND %b < 0.2 (below lower BB) for 3 consecutive closes → long.
- Repo note: independent re-tests (reddit algotrading) find modern Connors underperformance vs buy&hold in some windows — treat as a hypothesis to falsify on 2020–2026 data, not gospel.
- **Learning**: which of RSI(2) / %b / Triple-RSI survives post-2020 regime? Does adding the repo's day-type/season strata (turnaround-Tuesday, OPEX week) improve the exits?

### W-3. Leveraged ETF short-term mean reversion
**Status**: ⬜

- Connors/TradingMarkets documented: single-stock & index leveraged ETFs (SSO, QLD, TQQQ) are prime RSI(2)-fade vehicles *intraday-to-days* due to amplified swings. CXO note: high WR but fat left tail.
- **Investment-level caution built into the test**: variance drain (not "rebalance drag") makes leveraged ETFs poor buy-and-hold; only 1–3 day holds. The test: RSI(2)<10 fade on TQQQ/SPXL vs same signal on QQQ/SPY — measure WR delta AND tail loss (CVaR) delta. Expect: leverage amplifies WR and tail symmetrically → position-sizing learning.

### W-4. Overnight edge (close→close) on SPY/stocks
**Status**: 🟡 repo already owns the surviving core: "ES overnight VWAP-targeted mean reversion" (BB_EXPERIMENTS)

- Q Strategies documents the SPY overnight edge as a free effect. The repo's version trades it on futures. Backlog delta: test whether the edge is *weekday-conditional* (their turnaround-Tuesday finding) and whether it vanishes in high-VIX regimes (regime gate = standing repo prior).

### W-5. Day-type & seasonal swing priors (feeds F2 Q7 and F6.3)
- From Q-Strategies' ~50 documented seasonals, the intraday-testable set: **turnaround Tuesday**, **options expiration week effect** (feeds O-3), **turn of month** (buy last 4 / sell first 3 — compressible to an intraday drift term), **Monday gap-up fade 61%** (already F2 Q2).

---

## F9. Investment (weeks to months — portfolio layer)

### I-1. Trend-following core (Faber/Turtle heritage)
- 200-day MA / Golden Cross on SPY & NQ proxies; multi-asset trend (stocks/bonds/gold); Donchian daily (P7's elder sibling). Low WR ~30–40%, payoff asymmetry. Test on repo-adjacent daily data; treat as the **trend seat** for the portfolio; the intraday systems must show correlation-benefit against it, not standalone returns.

### I-2. Rotation / momentum ranking
- Monthly ETF rotation by 6/12-month momentum (Faber); value-vs-growth rotation; SPY/TLT risk-on-off. Cheap to implement on daily closes; provides the *risk-state variable* (risk-on/risk-off) that could gate F8 swing exposure.

### I-3. Sentiment/anomaly overlays
- Put/call & VIX-regime extremes as fade timers; COT positioning for futures; short-interest. Low standalone priority; useful as strata gates on O-1/W-2 tests.

### I-4. Seasonal calendar strategies (~50 documented by Q-Strategies)
- Turn of month, Santa rally, January effect, options-expiry week — test as *drift terms* added to any position-holding strategy rather than standalone systems (persistence is the claim; per-trade edge is thin).

---

## Composition notes (the why behind this family)

1. **0DTE EM/GEX ↔ F2 intraday**: the same EM-wall stat that gates O-1 condor strikes is Q7's fade-conditioning variable — one dataset (TOS RTD) powers both families.
2. **PEAD ↔ day-type engine**: earnings-gap days are their own R1/R2-like day class; a PEAD-flagged ticker could run a *modified* intraday playbook (gap-and-go vs gap-fade) — the "earnings-day classification" learning is the bridge.
3. **I-1 trend seat ↔ all intraday**: portfolio-level long/short of the 200-day MA is the coarsest regime gate available; every intraday stratum table should add it as one more column before final adoption decisions.
4. **Connors ETF reversion ↔ F6.1 IBS**: same reversion seat; A/B across horizon (intraday IBS vs 3–7-day RSI-25) to find where the edge actually lives.

## Data prerequisites to fetch when this family enters the queue

| Item | What | Source |
|---|---|---|
| Daily bars: SPY/QQQ/TLT/GLD/TQQQ + 20 liquid stocks | 2006→now | Schwab API / Yahoo |
| Earnings dates + surprise (SUE) | last 10y | Schwab / FMP |
| Historical option chains (SPX) | for O-1/O-2 backtests | TOS RTD live only → start as **forward paper-collection**, OR vendor history (ORATS/CBOE) |
| VIX/put-call daily | strata gates | free (CBOE) |

⚠️ Historical SPX chains are expensive/absent — O-1/O-2 likely start as **live forward paper tests** through the TOS RTD pipeline rather than historical backtests; the intraday-side uses of EM/GEX (Q7/O-3) can still backtest on futures data with current-surface approximation.