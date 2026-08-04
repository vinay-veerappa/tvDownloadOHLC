# Abbreviations & Nomenclature Registry

**Schema version:** `1.0`

> **Single source of truth:** `scripts/config/abbreviations.json`.
> This Markdown is **auto-generated** — do not edit by hand.
> Regenerate with `python -m scripts.tools.generate_abbreviations_md`.

## Naming policy

- **Compact form:** `True`
- **Midpoint suffix:** `M`
- **Case:** `UPPER`
- **Rule:** Compact form everywhere. Midpoint suffix is M. Full names in logs/docs, compact in code/charts.

## Categories

- **`price_level`** — Prior-period, intraday, session, and volume-profile price levels (PDH, HOD, P12L, VAH).
- **`session`** — Session and time-window concepts (IB, OR, RTH, Globex, P12, Overnight).
- **`options_gamma`** — Options and gamma-exposure terms (EM, DTE, GEX, DEX, ZG, CW/PW).
- **`ict_structure`** — ICT / market-structure terms (FVG, OB, BOS, CHOCH, HTF, Sweep).
- **`statistics`** — Statistical and probability terms (P50, Stretch, MFE, MAE, HitRate, R:R).
- **`classification`** — Day-type and regime classification (R1, R2, DWP, DNP).
- **`narrative_state`** — Narrative and element state (Bull/Bear/Neutral, PINNED, Active/Inactive).
- **`trade_infra`** — Trade execution and infrastructure (TP1, SL, BE, VWAP, ATR, HUD).

## price_level

| Abbrev | Full name | Definition | Legacy | Status |
|---|---|---|---|---|
| `PDH` | Prior Day High | High of the previous trading day. | PD H | active |
| `PDL` | Prior Day Low | Low of the previous trading day. | PD L | active |
| `PDM` | Prior Day Mid | Midpoint of prior day high and low. | PD M, PD Mid | active |
| `PDC` | Prior Day Close | Close of the previous trading day. | PD C | active |
| `PWH` | Prior Week High | High of the previous trading week. | PW H | active |
| `PWL` | Prior Week Low | Low of the previous trading week. | PW L | active |
| `PWM` | Prior Week Mid | Midpoint of prior week high and low. | PW M | active |
| `PWC` | Prior Week Close | Close of the previous trading week. | PW C | active |
| `PWO` | Prior Week Open | Open of the previous trading week. | PW O | active |
| `PMH` | Prior Month High | High of the previous trading month. | PM H | active |
| `PML` | Prior Month Low | Low of the previous trading month. | PM L | active |
| `PMM` | Prior Month Mid | Midpoint of prior month high and low. | PM M | active |
| `PMO` | Prior Month Open | Open of the previous trading month. | PM O | active |
| `Settle` | Prior Settlement | Prior day futures settlement price. | Settlement | active |
| `HOD` | High of Day | Highest price of the current trading day. | — | active |
| `LOD` | Low of Day | Lowest price of the current trading day. | — | active |
| `NYH` | NY Session High | High of the NY session. | NY H | active |
| `NYL` | NY Session Low | Low of the NY session. | NY L | active |
| `NY1H` | NY1 Session High | High of the NY1 (morning) session window. | NY1 H | active |
| `NY1L` | NY1 Session Low | Low of the NY1 (morning) session window. | NY1 L | active |
| `NY1M` | NY1 Session Mid | Midpoint of NY1 session high and low. | NY1 Mid | active |
| `NY2H` | NY2 Session High | High of the NY2 (afternoon) session window. | NY2 H | active |
| `NY2L` | NY2 Session Low | Low of the NY2 (afternoon) session window. | NY2 L | active |
| `NY2M` | NY2 Session Mid | Midpoint of NY2 session high and low. | NY2 Mid | active |
| `AsiaH` | Asia Session High | High of the Asia session. | Asia H | active |
| `AsiaL` | Asia Session Low | Low of the Asia session. | Asia L | active |
| `AsiaM` | Asia Session Mid | Midpoint of Asia session high and low. | Asia Mid | active |
| `LonH` | London Session High | High of the London session. | London H | active |
| `LonL` | London Session Low | Low of the London session. | London L | active |
| `LonM` | London Session Mid | Midpoint of London session high and low. | London Mid | active |
| `IBH` | Initial Balance High | High of the initial balance window. | IB H | active |
| `IBL` | Initial Balance Low | Low of the initial balance window. | IB L | active |
| `IBM` | Initial Balance Mid | Midpoint of initial balance high and low. | IB Mid | active |
| `P12H` | P12 High | High of the P12 overnight window (18:00-06:00 ET). | P12 H | active |
| `P12L` | P12 Low | Low of the P12 overnight window (18:00-06:00 ET). | P12 L | active |
| `P12M` | P12 Mid | Midpoint of P12 high and low. | P12 Mid | active |
| `GlbH` | Globex Session High | High of the Globex session. | Globex H | active |
| `GlbL` | Globex Session Low | Low of the Globex session. | Globex L | active |
| `GlbM` | Globex Session Mid | Midpoint of Globex session high and low. | Globex Mid | active |
| `VAH` | Value Area High | Upper boundary of the value area (volume profile). | — | active |
| `VAL` | Value Area Low | Lower boundary of the value area (volume profile). | — | active |
| `POC` | Point of Control | Price level with the highest traded volume (volume profile). | — | active |

## session

| Abbrev | Full name | Definition | Legacy | Status |
|---|---|---|---|---|
| `IB` | Initial Balance | The opening range window used to define the initial balance. | — | active |
| `OR` | Opening Range | The opening range window (default 09:30-10:30 ET). | — | active |
| `ORB` | Opening Range Breakout | A breakout strategy based on the opening range. | — | active |
| `RTH` | Regular Trading Hours | Regular trading hours (09:30-16:00 ET). | — | active |
| `Globex` | Globex Session | Overnight electronic futures session (18:00 ET). | Glx | active |
| `Asia` | Asia Session | Asia session window. | — | active |
| `London` | London Session | London session window. | — | active |
| `NY` | NY Session | New York session window. | — | active |
| `NY1` | NY1 Session | NY morning session window. | — | active |
| `NY2` | NY2 Session | NY afternoon session window. | — | active |
| `P12` | P12 Window | The 12-hour overnight window (18:00-06:00 ET). | — | active |
| `ON` | Overnight | Overnight session. | Overnight, ONS | active |
| `Macro` | Macro Window | Intraday macro window (e.g. NY AM Macro). | — | active |
| `ET` | Eastern Time | Eastern Time timezone. | EST | active |

## options_gamma

| Abbrev | Full name | Definition | Legacy | Status |
|---|---|---|---|---|
| `EM` | Expected Move | Expected price move derived from options (straddle-based). | — | active |
| `EM85` | Expected Move 85% | Expected move at the 85% straddle band. | — | active |
| `DTE` | Days to Expiry | Number of days until option expiry. | — | active |
| `0DTE` | Zero Days to Expiry | Same-day-expiring options. | 0D | active |
| `GEX` | Gamma Exposure | Gamma exposure of market makers. | — | active |
| `GEX_DA` | Delta-Adjusted Gamma Exposure | Gamma exposure adjusted for delta. | GEX DA | active |
| `DEX` | Delta Exposure | Delta exposure of market makers. | — | active |
| `DEX_C` | Delta Exposure Call | Delta exposure from call options. | DEX C | active |
| `DEX_P` | Delta Exposure Put | Delta exposure from put options. | DEX P | active |
| `ZG` | Zero Gamma | Strike where gamma is zero. | Zero Gamma | active |
| `ZG_DA` | Delta-Adjusted Zero Gamma | Zero gamma adjusted for delta. | ZG DA | active |
| `MAG` | Gamma Magnet | Strike that attracts price (gamma magnet). | Gamma Magnet | active |
| `CW` | Call Wall | Dealer call wall strike. | — | active |
| `PW` | Put Wall | Dealer put wall strike. | — | active |
| `LOC` | Local Node | Local call/put node. | — | active |
| `CLIFF` | Gamma Cliff | Gamma cliff level (up/down). | — | active |
| `PIN` | Pin Strike | Strike where price tends to pin at expiry. | PIN STRIKE | active |
| `MaxPain` | Max Pain | Strike where option buyers lose the most. | Max Pain | active |
| `IV` | Implied Volatility | Implied volatility of an option. | — | active |
| `IVChg` | Implied Volatility Change | Change in implied volatility. | — | active |
| `Vanna` | Vanna | Vol/IV-skew sensitivity of an option. | — | active |
| `Charm` | Charm | Delta-decay sensitivity of an option. | — | active |
| `Skew` | Volatility Skew | Volatility skew across strikes. | — | active |
| `OIVel` | Open Interest Velocity | Rate of change of open interest. | OI Vel | active |
| `Straddle` | Straddle | ATM call + put combination (EM derivation). | — | active |
| `ATM` | At The Money | Option whose strike equals the underlying price. | — | active |

## ict_structure

| Abbrev | Full name | Definition | Legacy | Status |
|---|---|---|---|---|
| `FVG` | Fair Value Gap | Three-candle imbalance gap (ICT). | — | active |
| `OB` | Order Block | Origin candle of a significant move (ICT). | — | active |
| `BOS` | Break of Structure | Price breaks a prior swing high/low (older ICT style). | — | active |
| `CHOCH` | Change of Character | Change in market character / structure shift (older ICT style). | — | active |
| `HTF` | Higher Timeframe | A higher timeframe than the current. | — | active |
| `LTF` | Lower Timeframe | A lower timeframe than the current. | — | active |
| `Judas` | Judas Swing | Fake-out then commitment move (ICT). | — | active |
| `Sweep` | Liquidity Sweep | Price sweeps a liquidity level then reverses. | Liquidity Sweep | active |
| `OTE` | Optimal Trade Entry | Optimal entry zone (ICT). | — | active |
| `CE` | Candle Extreme | Midpoint of an FVG (ICT). | — | active |
| `Liquidity` | Liquidity | Liquidity pool / hunt (ICT). | — | active |
| `Displacement` | Displacement | Displacement candle creating FVG/OB (ICT). | — | active |
| `Premium` | Premium Zone | ICT premium zone (above equilibrium). | — | active |
| `Discount` | Discount Zone | ICT discount zone (below equilibrium). | — | active |
| `MSS` | Market Structure Shift | Market structure shift (planned; no indicator yet). | — | planned |
| `CISD` | CISD | CISD concept (planned; to be added step by step). | — | planned |

## statistics

| Abbrev | Full name | Definition | Legacy | Status |
|---|---|---|---|---|
| `P20` | 20th Percentile | 20th percentile of a distribution. | — | active |
| `P25` | 25th Percentile | 25th percentile of a distribution. | — | active |
| `P50` | 50th Percentile | Median percentile of a distribution. | — | active |
| `P70` | 70th Percentile | 70th percentile of a distribution. | — | active |
| `P75` | 75th Percentile | 75th percentile of a distribution. | — | active |
| `P90` | 90th Percentile | 90th percentile of a distribution. | — | active |
| `Stretch` | Stretch Level | Extreme-excursion percentile level (default P90). | — | active |
| `Median` | Median | Statistical median. | — | active |
| `Avg` | Average | Arithmetic mean. | Mean | active |
| `MFE` | Maximum Favorable Excursion | Maximum favorable price excursion. | — | active |
| `MAE` | Maximum Adverse Excursion | Maximum adverse price excursion. | — | active |
| `HitRate` | Hit Rate | Probability a level is reached. | Hit %, Hit Prob | active |
| `Streak` | Streak | Consecutive hit/win streak. | — | active |
| `Prob` | Probability | Probability. | — | active |
| `SD` | Standard Deviation | Standard deviation. | Std | active |
| `R:R` | Risk to Reward | Risk-to-reward ratio. | RR | active |
| `EXP` | Expectancy | Expectancy in R units. | Exp | active |
| `N` | Sample Count | Number of samples. | — | active |

## classification

| Abbrev | Full name | Definition | Legacy | Status |
|---|---|---|---|---|
| `R1` | Range 1 Day | Range day: 4+ OR touches, stays near OR. | — | active |
| `R2` | Range 2 Day | Range day: broke OR then returned after window. | — | active |
| `DWP` | Directional With Pullbacks | Trend day with structural retracements. | — | active |
| `DNP` | Directional No Pullbacks | Trend day without structural retracements. | — | active |
| `Breakout` | Breakout | Breakout play / day type. | BO | active |
| `Retest` | Retest | Retest play / day type. | — | active |
| `Fade` | Fade | Fade play / day type. | — | active |
| `DayType` | Day Type | Daily regime classification. | DAY TYPE | active |

## narrative_state

| Abbrev | Full name | Definition | Legacy | Status |
|---|---|---|---|---|
| `Bull` | Bullish | Positive directional bias. | BULL, LONG | active |
| `Bear` | Bearish | Negative directional bias. | BEAR, SHORT | active |
| `Neutral` | Neutral | No directional bias. | NEUTRAL | active |
| `PINNED` | Pinned | Gamma-pinned range regime. | — | active |
| `TRENDING` | Trending | Trending regime. | — | active |
| `COILED` | Coiled | Tight, pre-breakout regime. | — | active |
| `BATTLE_ZONE` | Battle Zone | Battle zone regime. | BATTLE ZONE | active |
| `EXPANSION` | Expansion | Expansion regime. | — | active |
| `SQUEEZE` | Squeeze | Volatility squeeze regime. | — | active |
| `Flat` | Flat | No open position. | FLAT | active |
| `Active` | Active | Element is active / current thesis. | ACTIVE | active |
| `Inactive` | Inactive | Element is visible but de-emphasized. | INACTIVE | active |
| `Invalidation` | Invalidation | Thesis-ending level / state. | INVALIDATION | active |
| `Skip` | Skip | Misaligned setup skip. | SKIP | active |

## trade_infra

| Abbrev | Full name | Definition | Legacy | Status |
|---|---|---|---|---|
| `EMA` | Exponential Moving Average | Exponential moving average. | — | active |
| `HMA` | Hull Moving Average | Hull moving average. | — | active |
| `SMA` | Simple Moving Average | Simple moving average. | — | active |
| `VWAP` | Volume Weighted Average Price | Volume-weighted average price. | — | active |
| `ATR` | Average True Range | Average true range. | — | active |
| `BB` | Bollinger Bands | Bollinger Bands. | — | active |
| `TP1` | Take Profit 1 | First take-profit level. | — | active |
| `TP2` | Take Profit 2 | Second take-profit level. | — | active |
| `TP3` | Take Profit 3 | Third take-profit level. | — | active |
| `SL` | Stop Loss | Stop-loss level. | — | active |
| `BE` | Breakeven | Breakeven level. | Breakeven | active |
| `VCP` | Volatility Contraction Pattern | Volatility contraction pattern. | — | active |
| `OPEX` | Options Expiration | Options expiration week. | — | active |
| `HUD` | Heads-Up Display | Dashboard table overlay. | — | active |

## Planned (reserved)

Reserved slots for concepts to be added step by step as indicators are built.

| Abbrev | Full name | Definition | Legacy | Status |
|---|---|---|---|---|
| `MSS` | Market Structure Shift | Market structure shift (planned; no indicator yet). | — | planned |
| `CISD` | CISD | CISD concept (planned; to be added step by step). | — | planned |

## Known conflicts

| Abbrev | Meanings | Resolution | Owner |
|---|---|---|---|
| `P12` | P12 window (18:00-06:00 ET); P12M = P12 Mid level | P12 = window; P12M/P12H/P12L = levels. Context-disambiguated by suffix. | vveerappa |
| `OR` | Opening Range; Midnight OR; classification anchor | OR defaults to session Opening Range; Midnight OR uses 'Midnight OR'; classification anchor is contextual. | vveerappa |
| `PIN` | Pin Strike; OI-velocity bucket; PINNED regime | PIN = Pin Strike; PINNED = regime; OIVel buckets use OIVel prefix. | vveerappa |
| `CE` | Candle Extreme (FVG midpoint); PineScript compiler error code | CE = Candle Extreme in trading context; compiler error codes are not registry terms. | vveerappa |
| `BOS` | Break of Structure (canonical); MSS (Market Structure Shift, planned) | BOS is canonical; MSS is a planned distinct term, not an alias. | vveerappa |

## Changelog

| Version | Date | Note |
|---|---|---|
| 1.0 | 2026-08-04 | Initial registry. Full 8-category set from Pine inventory. MSS/CISD reserved as planned. |
