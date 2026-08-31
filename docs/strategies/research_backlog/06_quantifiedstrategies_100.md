# QuantifiedStrategies 100 Free Strategies — Cross-Reference (F6)

> Source: [quantifiedstrategies.substack.com/p/100-free-trading-strategies](https://quantifiedstrategies.substack.com/p/100-free-trading-strategies) (~100 free backtested strategies, updated continuously; most are **daily-bar/EOD** backtests by this shop — their edge claims are on daily data, NOT intraday).
> **Framing for this backlog**: these are learning-extraction targets, not drop-in strategies. An EOD result becomes a repo test by asking *"does the daily effect compress into a session window on NQ?"* (e.g., turnaround-Tuesday → Tuesday 10:00 hour stats; IBS mean reversion → 5m IBS fades).

---

## A. Mapping to existing backlog (do not duplicate)

| Q Strategies item | Maps to | Compress-to-intraday angle |
|---|---|---|
| Larry Connors RSI(2) (70–80% WR daily) | §8.1 RSI variants | Repo tested Connors RSI on 5m BB ("dead weight") — but the **daily Connors edge compresses into `close-below-MA-then-RSI-hook` intraday**: test 1m/5m RSI(2)<10 fade toward VWAP during RTH. Distinct from the retired BB family |
| Multiple Days Up / Multiple Days Down (Connors) | F2 reversion | Intraday analog: N consecutive same-direction 15m bars → fade probability |
| %B Strategy (Connors) | Q3 VWAP-band reversion | %B measures position within bands — usable as continuous 0–1 stretch score on VWAP σ-bands |
| IBS Indicator (Internal Bar Strength) | **F2 — NEW Q8 below** | Pure close-location-in-range oscillator; cheapest possible reversion signal |
| Bollinger Band Squeeze | **P6** TTM Squeeze | Same family; their variant uses squeeze breakouts on daily |
| Rubber Band Strategy (volatility reversion) | Q3 | Extreme-deviation snapback — VWAP-band analog |
| NR7 / Price Compression | repo `volatility_leading.py` (Kaufman ER, bar overlap) | NR7 = narrowest-range-of-7 bars → next-day range expansion. Intraday: NR7-bar clusters before 09:30 predict ORB day |
| Volume Trading Strategy ("does volume predict tomorrow") | F3 O5 spike classifier | Same question, intraday |
| Heikin Ashi | P6/P7 adjacent | Trend-filter variant, low priority |
| Turnaround Tuesday / Turn of Month / OPEX week | **F2 Q7** expiry conditioning + day-of-week | Directly stratifies every intraday test by weekday — cheap meta-learning |
| Overnight Edge (SPY close-to-close) | repo overnight-VWAP core (BB_EXPERIMENTS surviving core) | Validates the repo's surviving reversion engine exists as a known pub effect |
| Donchian Trend-Following | **P7** | Their results are daily; P7 already covers intraday Donchian |
| Supertrend | §8.2 validated | — |
| Golden Cross / 200MA / Coppock / Faber | Out of scope | Swing/annual horizons, not intraday NQ |
| Rotation / Seasonal / Macro / Bond / FX / Crypto / Gold / Oil | Out of scope | Different markets/horizons; revisit only if multi-asset scope expands beyond futures+stocks |
| Candlestick patterns ranked by data (they quantified all 75) | **P8** Candle Science | Their ranked list is a free prior for which 3-candle formations to test in the FTC pipeline |

## B. New intraday-translatable items (addTo backlog)

### F6.1 IBS fade (Internal Bar Strength) — Q-new for F2
- **Signal**: IBS = (close − low)/(high − low) ∈ [0,1]. Published effect: extreme IBS extremes revert next session (their published IBS strategy).
- **Intraday test**: 5m IBS ≤ 0.1 after ≥k-bar down-leg → long fade to VWAP/PD midline; mirror for short. Arms: raw vs gated by IB-regime router (repo prior: fades only compress days).
- **Why**: zero new infra (pure OHLC arithmetic), orthogonal to Bollinger (which failed), and directly comparable to O1 proxy-delta (IBS is a volume-free absorption proxy).

### F6.2 Consecutive down/up bars fade with trend alignment — Q-new for F2
- Connors' multiple-days-down daily result compresses to: N consecutive same-direction 5m closes during RTH → fade probability & MFE measurement. Test the count N where the effect inverts (2 vs 3 vs 4 bars) — this is the same "confirmation-count" question as P4 (H1 vs H2) from the opposite side, giving one shared learning if both agree.

### F6.3 Reversal-day / Inside-bar day-type priors — meta for F2
- Their reversal-day and inside-bar publications give EOD priors for day-type classification. Cheap repo test: does an inside-bar *first 60 minutes* (bar 1 contains bar 0 on 15m) predict DNP day type? Feeds DAILY_CLASSIFICATION directly.

### F6.4 New high/new low momentum (5-day) — F4 trend seat
- "New High Strategy" logic as intraday: session-high retest *without* sweep → continuation entry. This is the exact complement of S1/S2 (which fade the sweep version). One backtest classifies: close-beyond vs wick-beyond of session extremes → continuation vs fade WR split. That single test yields a reusable "session-extreme handling rule" for ALL strategies.

### F6.5 Their 90%-win-rate & low-risk pullback items — review list
- `High Win Rate Strategy (90%)`, `Low Risk Pullback Strategy`, `Pullback Strategy For The S&P 500`: fetch the full articles when P2 (EMA pullback) testing starts — they define the published stop/target frameworks to A/B against.

## C. Their portfolio-level advice (adopted here)

1. **Uncorrelated stack**: their core thesis — combine uncorrelated strategies across timeframe/asset/direction — matches the repo's 2-engine portfolio concept (R01/E31 trend+reversion seats in measured_move doc). New backlog items should declare which seat (trend vs reversion) they compete for.
2. **Mean reversion works best on equity-index shorts/longs but with fat left tail** ("average loser bigger than average winner") — expect F2 reversion tests to show high WR / low PF, and evaluate with PF + CVaR, not WR alone.
3. **Seasonals are their favorite because of persistence** — maps to repo's time-seasonality strength (killzones, macros, Q7). Any F2 effect found should get a weekday/season stratum column in the results table by default.

## D. What to fetch later

Full article pages (free, ungated, unlike FX Replay PDFs) hold exact rules + their backtest metrics. Priority fetches when the corresponding test enters the queue: **IBS Indicator**, **RSI(2)**, **NR7**, **Reversal Day**, **Multiple Days Up/Down**, **Bollinger Band Squeeze**, **Rubber Band**, **90% WR strategy**.