# Futures Options Symbology Library — Design Document

> **Status**: In progress · **Last updated**: 2026-07-22 · **Author**: vveerappa  
> **Related files**: `DailyEM_merged.pine`, `DealerLevels.pine`, `Daily_OC_levels.pine`  
> **Source of truth**: CME Group Quote Vendor Codes (`quote-vendor-codes.xlsx`)

---

## 1. Motivation

The Daily Expected Move indicator (and other indicators like DealerLevels, Daily_OC_levels) 
all need to build CME/CBOT/NYMEX/COMEX option symbols and fetch their prices via 
`request.security()`. The symbology is complex — each product has:

- Different exchange prefixes (CME_MINI, CBOT_MINI, CBOT, COMEX, NYMEX, OPRA)
- Different daily 0DTE roots per day of week (CL: ML/NL/WL/XL, SI: M1S/S1T/W1S/R4S)
- Different Friday weekly formats (root+week vs week+root)
- Different strike formatting (integer vs decimal vs 4-decimal FX)
- EOM options (YM only), roll-to-Friday for products without daily 0DTE

This logic is duplicated across indicators. A **Pine Script library** will be the 
single source of truth, imported by all indicators.

---

## 2. Library declaration

```pine
//@version=6
library("FuturesOptionsSymbology", "CME/CBOT/NYMEX/COMEX option symbol builder", overlay=true)
```

Publish as: `vveerappa/FuturesOptionsSymbology/1`

---

## 3. Exported types

### ProductConfig

Structured configuration for each futures product. Returned by `productConfig()`.

```pine
export type ProductConfig
    bool   found              // true if product is recognized
    string exch               // exchange prefix: CME_MINI, CBOT_MINI, CBOT, COMEX, NYMEX, OPRA
    string quarterlyRoot      // root for standard monthly/quarterly (e.g. ES, GC, CL)
    string fridayRoot         // root for Friday weekly (e.g. EW, OG, LO)
    string eomRoot           // root for End-of-Month (e.g. EYM), empty if none
    string dailyPrefix        // single root for daily 0DTE (used when dailyRoots is empty)
    string dailyDayLetters    // 4 chars: day letters for Mon-Thu (e.g. "ABCD", "MTWR")
    bool   dailyWeeklies     // true if product has Mon-Thu daily 0DTE
    bool   fridayHasWeekNum   // true if Friday symbol includes week number
    bool   decimalStrike      // true for sub-1.0 strike spacing (CL, NG, FX)
    bool   weekNumBeforePrefix // true for ZC/6E-style: week number before root
    string dailyRoots        // 8 chars: 2-char root per day (CL: "MLNLWLXL"), 4 chars for SI product letters
    bool   dailyFormatReversed // true for SI: {dayLetter}{weekNum}{productLetter} format
```

### ATMResult

Result of ATM straddle lookup.

```pine
export type ATMResult
    float  strike             // ATM strike that was found
    float  callCost           // call option price (na if not found)
    float  putCost            // put option price (na if not found)
    string callSymbol         // full call option symbol used
    string putSymbol          // full put option symbol used
    bool   usedETFProxy       // true if ETF proxy fallback was used (not direct futures)
    float  spacing            // strike spacing that worked
```

---

## 4. Exported functions

### Layer 1: Symbology (pure functions, no request.security)

#### `productConfig(string ticker) → ProductConfig`

Returns the full product configuration for any futures ticker.

```pine
ProductConfig cfg = productConfig("YM1!")
// cfg.exch = "CBOT_MINI", cfg.fridayRoot = "YM", cfg.eomRoot = "EYM", etc.
```

**Products supported** (verified from CME vendor codes):

| Ticker | Exchange | Daily 0DTE | Friday Root | EOM | Strike | Source |
|---|---|---|---|---|---|---|
| ES/MES | CME_MINI | E#A-E#D (ABCD) | EW | — | integer | user confirmed |
| NQ/MNQ | CME_MINI | Q#A-Q#D (ABCD) | QN | — | integer | pattern from ES |
| RTY/M2K | CME_MINI | R#A-R#D (ABCD) | RW | — | integer | pattern from ES |
| YM/MYM | CBOT_MINI | no daily (roll) | YM | EYM | integer | user confirmed |
| GC/MGC | COMEX | G#M-G#R (MTWR) | OG | — | integer | user confirmed |
| CL/MCL | NYMEX | ML/NL/WL/XL | LO | — | decimal | user + vendor codes |
| NG/MNG | NYMEX | KN (no day letter) | KN | — | decimal | user confirmed |
| ZB | CBOT | HB (no day letter) | HB | — | integer | user confirmed |
| ZN | CBOT | HY (no day letter) | HY | — | decimal | user confirmed |
| ZC | CBOT | weekNum+code (4HC) | OZC | — | integer | vendor codes |
| SI | COMEX | M1S/S1T/W1S/R4S (reversed) | SO | — | decimal | user + vendor codes |
| HG | COMEX | H#M-H#R (MTWR) | HG | — | decimal | user confirmed |
| 6E/M6E | CME | MO/TU/WE/SU | EU (week-first) | — | 4-decimal | vendor codes |
| 6B/M6B | CME | MB/TG/WG/SB | BP (week-first) | — | 4-decimal | vendor codes |
| 6J/M6J | CME | MJ/TJ/WJ/SJ | JY (week-first) | — | 4-decimal | vendor codes |
| 6S/M6S | CME | no daily (roll) | SF (week-first) | — | 4-decimal | vendor codes |
| 6A/M6A | CME | MA/TA/WA/SA | AD (week-first) | — | 4-decimal | vendor codes |
| 6C/M6C | CME | MD/TL/WD/SD | CD (week-first) | — | 4-decimal | vendor codes |
| RB | NYMEX | OB (no day letter) | OB | — | decimal | user confirmed |

#### `buildOptionSymbol(string ticker, int targetTime, string side, float strikeVal) → string`

Builds a single option symbol for any product. Handles:
- Daily 0DTE (Mon-Thu) with per-day roots, day letters, or reversed format
- Friday weekly with week-before-root or root-before-week
- EOM (End-of-Month) for YM
- Quarterly (3rd Friday of Mar/Jun/Sep/Dec)
- Roll-to-Friday for products without daily 0DTE
- Decimal vs integer strike formatting

Returns `na` if the product doesn't offer options on the target day.

#### `strikeSpacing(float price, string ticker) → float`

Returns the best-guess strike spacing for ATM calculation.

#### `formatStrike(float strikeVal) → string`

Formats a strike value to OPRA rules:
- Whole integers: `"5500.0"` (with .0 suffix)
- Fractional: `"1.1425"` (up to 4 decimal places)

#### `thirdFriday(int year, int month) → int`

Returns the timestamp of the 3rd Friday of the given month (standard monthly expiry).

#### `expirationDates(string root, int barTime, bool isClose) → array<string>`

Returns candidate expiration date strings (yyMMdd format). For 0DTE products (SPX, NDX, 
SPY, QQQ, IWM), returns today + tomorrow. For standard products, returns upcoming Friday 
+ monthly 3rd Friday.

#### `etfProxy(string ticker) → string`

Returns the ETF proxy root for futures tickers (YM→DIA, ES→SPY, NQ→QQQ, etc.). 
Used when direct futures options return na via request.security.

#### `sessionProxy(string ticker) → string`

Returns the ETF ticker for RTH session trigger detection (same as etfProxy but includes 
ZB→TLT, 6E→FXE, etc.). Used for `request.security(equity_ref, ..., session.isfirstbar_regular)`.

### Layer 2: Data fetching (wraps request.security)

#### `contractPrice(string symbol, bool isClose) → float`

Fetches the open (isClose=false) or close (isClose=true) of any symbol via 
request.security with ignore_invalid_symbol=true.

#### `optionPrice(string optSym, bool isClose) → float`

Same as contractPrice but auto-prefixes with "OPRA:" if the symbol doesn't contain ":" 
and isn't SPX/NDX. Used for ETF/stock options.

### Layer 3: ATM straddle finder

#### `atmStraddle(string ticker, float anchorPrice, bool isClose, bool debug) → ATMResult`

The full ATM straddle finder. Tries in order:
1. **Direct futures options** — builds symbol via buildOptionSymbol, tries 3 spacing candidates
2. **ETF proxy fallback** (SOURCE_FUTURES only) — if direct returns na, probes ETF proxy 
   options with auto-detect spacing (e.g. DIA for YM)
3. **OPRA brute-force** (non-FUTURES mode only) — multi-spacing, multi-date search against 
   the configured ETF/index/stock root

Returns ATMResult with call/put costs, symbols, and whether ETF proxy was used.

---

## 5. Workflow: How indicators consume the library

### Daily Expected Move indicator

```pine
import vveerappa/FuturesOptionsSymbology/1 as OptSym

// At barstate.isfirst — determine source mode
ProductConfig cfg = OptSym.productConfig(syminfo.ticker)
string etfRef = OptSym.sessionProxy(syminfo.ticker)

// At RTH open/close trigger
ATMResult atm = OptSym.atmStraddle(syminfo.ticker, anchorPrice, isClose, iDebug)
if not na(atm.callCost) and not na(atm.putCost)
    float em = atm.callCost + atm.putCost
    // Scale if ETF proxy was used
    if atm.usedETFProxy
        em := em * (futuresPrice / etfPrice)
```

### Dealer Levels indicator

```pine
import vveerappa/FuturesOptionsSymbology/1 as OptSym

ProductConfig cfg = OptSym.productConfig(syminfo.ticker)

// Build specific delta-level options
string call25 = OptSym.buildOptionSymbol(syminfo.ticker, targetTime, "C", delta25Strike)
float call25Price = OptSym.optionPrice(call25, isClose)
```

### Any future indicator

```pine
import vveerappa/FuturesOptionsSymbology/1 as OptSym

// Just need a symbol?
string sym = OptSym.buildOptionSymbol(syminfo.ticker, time, "C", 5500.0)

// Just need spacing?
float spacing = OptSym.strikeSpacing(close, syminfo.ticker)

// Just need expiry dates?
array<string> dates = OptSym.expirationDates("SPY", time, false)
```

---

## 6. What stays in each indicator (not in the library)

| Component | Why it stays | Where |
|---|---|---|
| Fib levels / drawing | Indicator-specific UI | DailyEM only |
| Session trigger detection | Uses `session.isfirstbar_regular` — must be in main script | Each indicator |
| Table display | Indicator-specific | Each indicator |
| Input handling (iOptionSource, useSPX) | User-facing settings | Each indicator |
| barstate.isfirst product mapping | Depends on iOptionSource — indicator-specific | Each indicator |
| EM scaling (useETFConv ratio) | Depends on iOptionSource setting | DailyEM only |
| Debug logging | Indicator-specific | Each indicator |

---

## 7. CME Vendor Codes Reference

> **Source**: `quote-vendor-codes.xlsx` from CME Group  
> **Purpose**: Authoritative reference for all CME/CBOT/NYMEX/COMEX option symbology

### Agriculture (CBOT)

| Product | Futures | Monthly Opt | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|---|---|
| Corn (ZC) | ZC | OZC | #CA | #BC | #CW | #HC | ZC# |
| Soybeans (ZS) | ZS | OZS | #SA | #SB | #SC | #SD | ZS# |
| Wheat (ZW) | ZW | OZW | ZW# | WZ# | (similar) | (similar) | ZW# |

Format: Corn daily = {weekNum}{2-char-day-code} (4CA for Mon week 4). 
Friday = ZC{weekNum}. Monthly = OZC.

### Energy (NYMEX)

| Product | Futures | Monthly Opt | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|---|---|
| Crude Oil (CL) | CL | LO | ML# | NL# | WL# | XL# | LO# |
| Natural Gas (NG) | NG | — | KN# | KN# | KN# | KN# | KN# |
| RBOB Gasoline (RB) | RB | OB | OB | OB | OB | OB | OB# |
| Heating Oil (HO) | HO | OH | (check vendor) | | | | |

Format: CL daily = {2-char-root}{weekNum} (ML4 for Mon week 4). 
Friday = LO{weekNum}. NG daily = KN{weekNum} (same root all days).

### Metals (COMEX)

| Product | Futures | Monthly Opt | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|---|---|
| Gold (GC) | GC | OG | G#M | G#T | G#W | G#R | OG# |
| Silver (SI) | SI | SO | M#S | S#T | W#S | R#S | SO# |
| Copper (HG) | HG | HG | H#M | H#T | H#W | H#R | HG# |

Format: GC daily = G{weekNum}{dayLetter} (G4W for Wed week 4). Day letters = MTWR.
SI daily = {dayLetter}{weekNum}{productLetter} (R4S for Thu week 4). Reversed format.
SI product letter changes: S for Mon/Wed/Thu, T for Tue.

### Equities (CME_MINI / CBOT_MINI)

| Product | Futures | Monthly Opt | Mon | Tue | Wed | Thu | Fri | EOM |
|---|---|---|---|---|---|---|---|---|
| E-mini S&P (ES) | ES | ES | E#A | E#B | E#C | E#D | EW# | — |
| E-mini NQ (NQ) | NQ | NQ | Q#A | Q#B | Q#C | Q#D | QN# | — |
| E-mini RTY (RTY) | RTY | RTY | R#A | R#B | R#C | R#D | RW# | — |
| E-mini Dow (YM) | YM | YM | — | — | — | — | YM# | EYM |

Format: ES daily = E{weekNum}{dayLetter} (E3A for Mon week 3). Day letters = ABCD.
YM: no daily 0DTE — roll to Friday. EOM = EYM{date} (no week number).

### Currencies (CME)

| Product | Futures | Monthly Opt | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|---|---|
| Euro FX (6E) | 6E | EUU | MO# | TU# | WE# | SU# | #EU |
| British Pound (6B) | 6B | GBU | MB# | TG# | WG# | SB# | #BP |
| Japanese Yen (6J) | 6J | JPU | MJ# | TJ# | WJ# | SJ# | #JY |
| Swiss Franc (6S) | 6S | CHU | — | — | — | — | #SF |
| Australian Dollar (6A) | 6A | OAU | MA# | TA# | WA# | SA# | #AD |
| Canadian Dollar (6C) | 6C | CAU | MD# | TL# | WD# | SD# | #CD |

Format: daily = {2-char-root}{weekNum} (MO4 for Mon week 4).
Friday = {weekNum}{root} (4EU — week before root). Only 6S has no daily 0DTE.

### Treasuries (CBOT)

| Product | Futures | Monthly Opt | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|---|---|
| 30-yr Bond (ZB) | ZB | OZB | HB# | (check) | (check) | HB# | HB# |
| 10-yr Note (ZN) | ZN | OZN | VY# | GY# | WY# | HY# | ZN# |

Format: daily = {2-char-root}{weekNum} (HB4 for week 4). No day letter.
ZN daily roots vary by day: VY/GY/WY/HY (Mon/Tue/Wed/Thu).

---

## 8. Implementation plan

### Phase 1: Create the library file (current session)
- [ ] Create `FuturesOptionsSymbology.pine` with `library()` declaration
- [ ] Extract all symbology functions from `DailyEM_merged.pine`
- [ ] Add exported types (ProductConfig, ATMResult)
- [ ] Test compilation

### Phase 2: Publish the library
- [ ] Open Pine Editor
- [ ] Save the library
- [ ] Publish as `vveerappa/FuturesOptionsSymbology/1`
- [ ] Verify import works from another script

### Phase 3: Refactor existing indicators
- [ ] Refactor `DailyEM_merged.pine` to import the library
- [ ] Refactor `DealerLevels.pine` to import the library
- [ ] Refactor `Daily_OC_levels.pine` to import the library
- [ ] Test each indicator after refactor

### Phase 4: Expand product coverage
- [ ] Add HO (Heating Oil) from vendor codes
- [ ] Add ZS (Soybeans) from vendor codes
- [ ] Add ZW (Wheat) from vendor codes
- [ ] Verify all products against live TradingView option chains

### Phase 5: Documentation
- [ ] Complete the CME vendor codes reference (section 7)
- [ ] Add usage examples for each indicator
- [ ] Document the request.security budget implications
- [ ] Create a testing checklist

---

## 9. request.security budget considerations

TradingView limits scripts to 40 unique request.*() contexts (64 on Pro/Expert/Ultimate).
Each unique symbol string counts as one context. The library functions that wrap 
request.security (`contractPrice`, `optionPrice`, `atmStraddle`) will consume budget 
from the calling script's total.

**Budget per day** (with cached spacing):
- Direct futures attempt: 2 requests (call + put)
- ETF proxy fallback (if direct fails): 2-6 requests (call+put × up to 3 spacings)
- OPRA brute-force (non-futures mode): 4-12 requests (2 dates × 3 spacings × call+put)

**Mitigation**: The `atmStraddle` function caches the last successful spacing and only 
tries one spacing on subsequent days (2 requests/day for the normal case).

---

## 10. Testing checklist

For each product, test with `iDebug = true` on the chart:

- [ ] **Monday 0DTE**: verify symbol in logs matches TradingView option chain
- [ ] **Tuesday 0DTE**: verify (if product has daily 0DTE)
- [ ] **Wednesday 0DTE**: verify
- [ ] **Thursday 0DTE**: verify
- [ ] **Friday weekly**: verify (non-3rd-Friday)
- [ ] **3rd Friday monthly**: verify (quarterly month: Mar/Jun/Sep/Dec)
- [ ] **3rd Friday non-quarter**: verify (treated as weekly)
- [ ] **Last Friday (EOM)**: verify (YM only — EYM prefix)
- [ ] **ETF proxy fallback**: verify (YM — direct fails, DIA proxy works)
- [ ] **Strike spacing**: verify ATM strike matches chain
- [ ] **Decimal strikes**: verify (CL: 88.5, 6E: 1.1425)
- [ ] **EM value**: verify non-NaN, reasonable magnitude

---

## 11. Expanded scope — Full options toolkit library

> **Updated**: 2026-07-22 — after reviewing all existing indicators  
> **Indicators reviewed**: DailyEM_merged, DealerLevels, Daily_OC_levels, ExpectedVolatality, 
> ExecutionHUD, MacroDealerLevels

### 11.1 Current state of options indicators

| Indicator | Fetches options? | Computes greeks? | Fetches OI? | Builds symbols? | Dealer levels? |
|---|---|---|---|---|---|
| DailyEM_merged | ✅ (direct + ETF) | ❌ (straddle only) | ❌ | ✅ (full symbology) | ❌ |
| Daily_OC_levels | ✅ (OPRA fallback) | ❌ | ❌ | ✅ (ETF only) | ❌ |
| DealerLevels | ❌ (paste-driven) | ❌ | ❌ | ❌ | ✅ (rendered from paste) |
| ExecutionHUD | ❌ (paste-driven) | ❌ | ❌ | ❌ | ✅ (rendered from paste) |
| MacroDealerLevels | ❌ (paste-driven) | ❌ | ❌ | ❌ | ✅ (rich, from paste) |
| ExpectedVolatality | ❌ (VIX indices) | ❌ | ❌ | ❌ | ❌ |

**Key gap**: None of the indicators currently compute greeks, fetch open interest, 
or calculate dealer levels from live data. All dealer/gamma levels are pre-computed 
externally and pasted in as text. The library should provide the building blocks to 
compute these from live option data.

### 11.2 Duplicated code across indicators (extract to library)

#### Symbol utilities — identical in 3+ files
| Function | Purpose | Used by |
|---|---|---|
| `canonicalSymbol(ticker)` | Normalize micro→full (MES→ES), strip prefixes | DealerLevels, ExecutionHUD, MacroDealerLevels |
| `symbolFamily(ticker)` | Map to family (ES_FAMILY, NQ_FAMILY, etc.) | DealerLevels, ExecutionHUD, MacroDealerLevels |
| `sourceKind(ticker)` | Classify as INDEX / ETF / FUTURES / OTHER | DealerLevels, ExecutionHUD, MacroDealerLevels |
| `matchScore(assetTag, chartTicker)` | Score how well a pasted asset matches chart | DealerLevels, ExecutionHUD, MacroDealerLevels |
| `findMatchingLine(blob, chartTicker)` | Find best-matching line from pasted text | DealerLevels, ExecutionHUD, MacroDealerLevels |

#### Level parsing — identical in 2 files
| Function | Purpose | Used by |
|---|---|---|
| `parseScoredLevels(lineText)` | Parse `PRICE:FILTER\|SIG\|LABEL` format | ExecutionHUD, MacroDealerLevels |
| `parseLevels(lineText)` | Parse `PRICE:TITLE` format | DealerLevels |

#### Proximity helpers — identical in 3 files
| Function | Purpose | Used by |
|---|---|---|
| `nearestBelow(price, levels)` | Find nearest level below price | DealerLevels, ExecutionHUD, MacroDealerLevels |
| `nearestAbove(price, levels)` | Find nearest level above price | DealerLevels, ExecutionHUD, MacroDealerLevels |
| `isNear(price, level, threshold)` | Check if price is within threshold of level | DealerLevels, ExecutionHUD, MacroDealerLevels |

#### Volatility utilities — unique to ExpectedVolatality
| Function | Purpose | Used by |
|---|---|---|
| `volIndex(ticker)` | Map ticker to volatility index (ES→VIX, NQ→VXN, etc.) | ExpectedVolatality only |
| `volToStdDev(vixValue)` | Convert VIX to daily/annual std dev fractions | ExpectedVolatality only |

#### Futures conversion — duplicated in 2 files
| Function | Purpose | Used by |
|---|---|---|
| `futuresBasis(etfPrice, futuresPrice)` | Compute additive basis | ExecutionHUD, MacroDealerLevels |
| `futuresRatio(etfPrice, futuresPrice)` | Compute multiplicative ratio | ExecutionHUD, MacroDealerLevels |
| `convertTo Futures(price, ratio)` | Apply ratio conversion to a level | ExecutionHUD, MacroDealerLevels |

### 11.3 New placeholder APIs (to be implemented)

> These are **design placeholders** — not yet implemented. They define the API surface 
> for future development. Implementation requires TradingView to support the needed 
> data (e.g. greeks, open interest) via request.security or other mechanisms.

#### Greeks calculation

```pine
export type Greeks
    float delta       // ∂V/∂S — option price sensitivity to underlying
    float gamma       // ∂²V/∂S² — delta sensitivity to underlying
    float theta       // ∂V/∂t — time decay per day
    float vega        // ∂V/∂σ — IV sensitivity (per 1% vol change)
    float rho         // ∂V/∂r — interest rate sensitivity
    float vanna       // ∂²V/∂S∂σ — delta sensitivity to IV
    float charm       // ∂²V/∂S∂t — delta sensitivity to time
    float speed       // ∂³V/∂S³ — gamma sensitivity to underlying

export greeks(string optionSymbol, float spotPrice, float strike, float timeToExpiry, 
              float riskFreeRate, bool isCall) → Greeks
```

**Implementation approach**: Black-Scholes closed-form for European options. 
Pine v6 supports math functions needed (exp, log, sqrt, erf approximation). 
The challenge is obtaining IV — either from TradingView's implied volatility data 
(if available via request.security) or by inverting BS from the option price.

**Limitations**: American-style options (most CME products) have early exercise 
premium. BS will be an approximation. For accurate greeks, a binomial tree or 
finite difference model would be needed — may exceed Pine's computation limits.

#### Open interest fetching

```pine
export type OpenInterest
    float callOI       // call open interest at this strike
    float putOI        // put open interest at this strike
    float totalOI      // call + put
    float callPutRatio // call OI / put OI

export openInterest(string optionSymbol) → OpenInterest
```

**Implementation approach**: TradingView may expose OI via `request.security` 
with the `open_interest` built-in. Need to verify if this works for option symbols.

```pine
// Placeholder — may need to use request.security with open_interest
[oi, ...] = request.security(optionSym, timeframe.period, [open_interest, ...])
```

**If not available**: OI-based levels will continue to be paste-driven from external 
data sources (e.g. spotgamma, MenthorQ).

#### Gamma exposure / GEX calculation

```pine
export type GammaExposure
    float callGEX      // dealer gamma from calls at this strike
    float putGEX       // dealer gamma from puts (negative)
    float netGEX       // callGEX + putGEX
    float totalGEX     // summed across all strikes

export gammaExposure(string ticker, float spotPrice, float timeToExpiry, 
                     float riskFreeRate, int numStrikes) → array<GammaExposure>
```

**Implementation approach**:
1. Build option symbols for N strikes above and below spot
2. Fetch call/put prices for each strike
3. Compute gamma for each via BS
4. Multiply gamma by OI × spot² × 0.01 (1% gamma exposure)
5. Sum across all strikes for total GEX

**Assumption**: Dealer positioning is short calls, long puts (standard assumption). 
Adjustable via parameter.

#### Dealer levels (call wall, put wall, zero gamma, gamma flip)

```pine
export type DealerLevels
    float callWall         // strike with highest call OI
    float putWall          // strike with highest put OI
    float zeroGamma        // strike where net GEX = 0
    float gammaFlipUpper   // strike where GEX turns positive above
    float gammaFlipLower   // strike where GEX turns negative below
    float gammaMagnet      // strike with highest absolute GEX
    float maxPain          // strike where total option value is minimized
    float pinStrike        // strike with highest total OI

export dealerLevels(string ticker, float spotPrice, float timeToExpiry, 
                    float riskFreeRate, int numStrikes) → DealerLevels
```

**Implementation approach**:
1. Call `gammaExposure()` to get GEX per strike
2. Find max call GEX → call wall
3. Find max put GEX → put wall
4. Find where cumulative GEX crosses zero → zero gamma
5. Find inflection points → gamma flip levels
6. Compute max pain by iterating strikes and summing option values

#### Volatility data

```pine
export type VolatilityData
    float impliedVol     // current IV (from vol index or BS inversion)
    float historicalVol  // 20-day realized vol
    float volRiskPremium // IV - HV
    float skew           // IV difference between puts and calls at same delta

export impliedVolatility(string ticker) → VolatilityData
```

**Implementation approach**:
- Use volatility index mapping (ES→VIX, NQ→VXN, etc.) from ExpectedVolatality
- Or invert Black-Scholes from ATM option price to get IV
- Skew requires fetching multiple strikes and computing IV for each

#### Straddle and expected move

```pine
export type ExpectedMoveResult
    float atmStrike
    float straddleCost    // call + put at ATM
    float expectedMove     // straddle cost (or straddle × multiplier)
    float emHigh           // anchor + EM
    float emLow            // anchor - EM
    float straddleImpliedVol  // straddle / spot / sqrt(DTE) × 100

export expectedMove(string ticker, float anchorPrice, bool isClose, bool debug) → ExpectedMoveResult
```

**Implementation approach**: This is the existing `calcEM` function, wrapped in 
the structured return type. Already implemented in the current indicator.

### 11.4 Cross-indicator refactoring plan

| Indicator | Current approach | After library |
|---|---|---|
| DailyEM_merged | Self-contained (all symbology inline) | `import OptSym` — uses library for all symbology + ATM |
| Daily_OC_levels | Self-contained (ETF fallback only) | `import OptSym` — uses library for symbology + ATM + ETF proxy |
| DealerLevels | Paste-driven (no live data) | `import OptSym` — uses library for symbol normalization + matching |
| ExecutionHUD | Paste-driven + futures conversion | `import OptSym` — uses library for symbol utils + futures conversion |
| MacroDealerLevels | Paste-driven + rich metadata | `import OptSym` — uses library for symbol utils + META parser + futures conversion |
| ExpectedVolatality | VIX indices only | `import OptSym` — uses library for vol index mapping + std dev conversion |

### 11.5 Library module structure

The library is a single Pine file but organized into clear sections:

```
FuturesOptionsSymbology.pine
├── Types
│   ├── ProductConfig
│   ├── ATMResult
│   ├── Greeks (placeholder)
│   ├── OpenInterest (placeholder)
│   ├── GammaExposure (placeholder)
│   ├── DealerLevels (placeholder)
│   ├── VolatilityData (placeholder)
│   └── ExpectedMoveResult
├── Layer 1: Symbology
│   ├── productConfig()
│   ├── buildOptionSymbol()
│   ├── strikeSpacing()
│   ├── formatStrike()
│   ├── thirdFriday()
│   ├── expirationDates()
│   ├── etfProxy()
│   └── sessionProxy()
├── Layer 2: Data fetching
│   ├── contractPrice()
│   ├── optionPrice()
│   └── atmStraddle()
├── Layer 3: EM calculation
│   └── expectedMove()
├── Layer 4: Symbol utilities (from paste-driven indicators)
│   ├── canonicalSymbol()
│   ├── symbolFamily()
│   ├── sourceKind()
│   ├── matchScore()
│   └── findMatchingLine()
├── Layer 5: Level utilities
│   ├── parseScoredLevels()
│   ├── parseLevels()
│   ├── nearestBelow()
│   ├── nearestAbove()
│   └── isNear()
├── Layer 6: Volatility utilities
│   ├── volIndex()
│   ├── volToStdDev()
│   └── impliedVolatility() (placeholder)
├── Layer 7: Futures conversion
│   ├── futuresBasis()
│   ├── futuresRatio()
│   └── convertToFutures()
├── Layer 8: Greeks (placeholder)
│   ├── greeks()
│   └── impliedVolFromPrice() (BS inversion)
├── Layer 9: Open interest (placeholder)
│   ├── openInterest()
│   └── openInterestProfile()
├── Layer 10: Gamma exposure (placeholder)
│   ├── gammaExposure()
│   └── dealerLevels()
�└── Layer 11: Metadata parsing (from paste-driven indicators)
    ├── parseMetaTokens()
    └── metaSchema()
```

### 11.6 Priority for implementation

| Priority | Module | Complexity | Depends on |
|---|---|---|---|
| P0 (now) | Layer 1: Symbology | Done — just extract | — |
| P0 (now) | Layer 2: Data fetching | Done — just extract | Layer 1 |
| P0 (now) | Layer 3: EM calculation | Done — just extract | Layer 2 |
| P1 (next) | Layer 4: Symbol utils | Low — extract from existing | — |
| P1 (next) | Layer 5: Level utils | Low — extract from existing | — |
| P1 (next) | Layer 6: Volatility | Low — extract from existing | — |
| P1 (next) | Layer 7: Futures conversion | Low — extract from existing | — |
| P2 (later) | Layer 8: Greeks | High — BS implementation | Layer 2 |
| P2 (later) | Layer 9: Open interest | Medium — verify TV data availability | Layer 2 |
| P3 (future) | Layer 10: Gamma exposure | High — needs OI + greeks | Layer 8, 9 |
| P3 (future) | Layer 11: Metadata parsing | Medium — extract from existing | — |

### 11.7 Key assumptions and risks

1. **Black-Scholes accuracy**: CME options are American-style. BS (European) will 
   underestimate early exercise premium. For short-dated options (0DTE, weeklies), 
   the difference is small. For LEAPS, it's significant.

2. **request.security for greeks/OI**: TradingView may not expose greeks or open 
   interest for option symbols via `request.security`. If not, these features will 
   remain paste-driven from external sources.

3. **request.security budget**: Computing gamma exposure for 20 strikes requires 
   40 request.security calls (20 calls + 20 puts). This alone would exhaust the 
   40-context budget. May need to batch or use a single request with a tuple.

4. **IV inversion**: Inverting BS to find IV from option price requires a root-finding 
   algorithm (Newton-Raphson or bisection). Pine v6 supports the math needed, but 
   it adds computation. An alternative is to use the volatility index (VIX/VXN/etc.) 
   as a proxy for ATM IV.

5. **Pine computation limits**: Computing greeks for many strikes may hit Pine's 
   loop/computation limits. The library should be designed to compute greeks for 
   a small number of strikes (e.g. 10-20) rather than the full chain.