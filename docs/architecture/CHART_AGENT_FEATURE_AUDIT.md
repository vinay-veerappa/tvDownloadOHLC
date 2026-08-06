# Feature Audit & Rebuild Plan — Chart Agent Reasoner

## What's Wrong With Current Features

### Redundant (remove)
| Feature | Why remove |
|---|---|
| IPDA-20 position | User doesn't use IPDA |
| IPDA-60 position | User doesn't use IPDA |
| Pre-computed 4-model bias | This is what we're replacing — it's a biased input |
| Killzone pivots | Review — may not be needed for bias |

### Wrong (fix)
| Feature | Current value | Actual | Problem |
|---|---|---|---|
| Asia range | "0.5 points" (from pre-computed) | 16.50 pts | Not computed from 1m data |
| Dealing Range % | None | Should be computed | Not calculated |
| Premium/Discount | "unknown" | Should be computed | Not calculated |
| BSL/SSL | None | Should be computed | Not calculated |
| Session order | Asia first, then London | London (02:00) first, then NY | Sessions not mapped to correct ET times |

### Missing (add)
| Feature | Source | Why needed |
|---|---|---|
| **PDM (Prior Day Mid)** | (PDH + PDL) / 2 | Key dealing range equilibrium level |
| **PWM (Prior Week Mid)** | (PWH + PWL) / 2 | Weekly equilibrium |
| **PMM (Prior Month Mid)** | (PMH + PML) / 2 | Monthly equilibrium |
| **Asia Mid** | (Asia High + Asia Low) / 2 | Session midpoint — key reference |
| **London Mid** | (London High + London Low) / 2 | Session midpoint |
| **NY1 Mid** | (NY AM High + NY AM Low) / 2 | Session midpoint |
| **NY2 Mid** | (NY PM High + NY PM Low) / 2 | Session midpoint |
| **Session H/L/Range** | Computed from 1m for target date | All sessions: Asia, London, Pre-NY, NY AM, Lunch, PM |
| **Midnight Open** | 00:00 ET price | Already loaded but needs to be correct |
| **Prior Day OHLC** | From 1m or 1d parquet | For PDH/PDL/PDC computation |
| **Weekly H/L** | From 1m resampled to W | PWH/PWL |
| **Monthly H/L** | From 1m resampled to M | PMH/PML |
| **Active FVGs** | `load_imbalances()` filtered to target date, unmitigated | PD arrays the reasoner needs |
| **Active Order Blocks** | `load_orderblocks()` filtered to target date | PD arrays |
| **Active Liquidity levels** | `load_liquidity()` filtered to target date | EQH, EQL, BSL, SSL |
| **Market structure** | `load_structure()` filtered — recent BOS/MSS/CISD | HTF and LTF structure |
| **HTF OHLC** | Resample 1m to 4H, 1H | For MTF analysis |
| **Current price** | Last 1m close | Premium/discount calculation |

## Session Time Definitions (ET)
From PROFILER_KNOWLEDGE_BASE.md:
| Session | Start (ET) | End (ET) | Mid available at |
|---|---|---|---|
| Asia | 20:00 prev day | 02:00 | 02:00 |
| London | 02:00 | 07:00 | 07:00 |
| Pre-NY | 07:30 | 09:30 | — |
| NY1 (NY AM) | 09:30 | 12:00 | 12:00 |
| NY2 (NY PM) | 13:30 | 16:00 | 16:00 |

Note: For futures, the trading day starts at 18:00 ET (Globex open). Sessions wrap midnight.

## Kish/TCM Levels (from KB + repo docs)
- **Dealing range**: high/low identified on daily chart, 50% level = equilibrium
- **PDM**: (PDH + PDL) / 2 — Prior Day Midpoint
- **Session mids**: Asia Mid, London Mid, NY1 Mid, NY2 Mid
- **Rule 6**: swing high/low + 50% of candle for stop placement
- **Top-down**: Monthly → Weekly → Daily → M5/M1 for entry
- **7 Rules**: Only Rule 6 found in KB — need more TCM sources ingested

## ICT Session-Specific Concepts (from KB)
### Asia Session
- Creates ranges to house liquidity
- Asia range high/low = key levels for London sweep targets
- Tight Asia range → London expansion likely
- Wide Asia range → London may be range-bound

### London Session
- 02:00-05:00 ET killzone
- Judas Swing: sweeps Asia high/low then reverses
- London range sweep behavior predicts NY
- London Close Killzone for late-day sweeps

### NY Session
- NY AM (09:30-12:00): Silver Bullet windows (10:00-11:00)
- Uses London liquidity for expansion
- PM session liquidity gets run next morning

## Derived Data to Fix (for backtesting + validation)
| Dataset | Location | Issue | Fix |
|---|---|---|---|
| HTF levels (`data/derived/ICT/{sym}_htf_levels.parquet`) | `ict_data_loader.load_htf_levels()` | May have stale/incorrect PDH/PDL | Recompute from 1m, verify against raw data |
| IPDA (`data/derived/ICT/{sym}_ipda.parquet`) | `ict_data_loader.load_ipda()` | User doesn't use — skip in features | Keep for backtesting, remove from reasoner features |
| Killzone pivots (`data/derived/ICT/{sym}_kz_pivots.parquet`) | `ict_data_loader.load_kz_pivots()` | Review if needed | Verify definitions match ICT |
| Gaps (`data/derived/ICT/{sym}_gaps.parquet`) | `ict_data_loader.load_gaps()` | Check if NWOG/NDOG computed correctly | Verify against 1W/1D data |
| Imbalances/FVGs (`data/derived/ICT/{sym}_imbalances.parquet`) | `ict_data_loader.load_imbalances()` | 717K rows — need filtering | Filter to target date + unmitigated only |
| Order Blocks (`data/derived/ICT/{sym}_orderblocks.parquet`) | `ict_data_loader.load_orderblocks()` | 68K rows — need filtering | Filter to target date + unmitigated only |
| Liquidity (`data/derived/ICT/{sym}_liquidity.parquet`) | `ict_data_loader.load_liquidity()` | 299K rows — need filtering | Filter to target date, group by type |
| Structure (`data/derived/ICT/{sym}_structure.parquet`) | `ict_data_loader.load_structure()` | 572K rows — need filtering | Filter to target date, recent BOS/MSS/CISD only |
| Session ranges | Not in derived data | Need to compute from 1m | Add to `compute_ict_features` pipeline |

## Proposed New Features Block Structure

```
1. HTF LEVELS
   - Prior Day: PDH, PDL, PDM, PDC (close)
   - Prior Week: PWH, PWL, PWM
   - Prior Month: PMH, PML, PMM
   - Midnight Open (00:00 ET)
   - Current price

2. SESSION RANGES (computed from 1m for target date)
   - Asia: H, L, Mid, Range
   - London: H, L, Mid, Range
   - NY AM: H, L, Mid, Range
   - NY PM: H, L, Mid, Range
   - Which session was tightest/widest

3. DEALING RANGE
   - High (PDH), Low (PDL), Equilibrium (PDM)
   - Current position % (premium/discount)
   - BSL targets above, SSL targets below

4. PD ARRAYS (active, filtered to target date)
   - FVGs: top, bottom, type (bullish/bearish), unmitigated
   - Order Blocks: top, bottom, type
   - Liquidity levels: EQH, EQL, BSL, SSL
   - Market structure: recent BOS, MSS, CISD

5. HTF STRUCTURE (4H, 1H)
   - Recent swing highs/lows
   - BOS/MSS on 1H and 4H

6. KB CONTEXT (session-aware)
   - ICT concepts for current/next session
```

## What Needs to Be Built/Changed

| # | Task | File | Priority |
|---|---|---|---|
| 1 | Remove IPDA + pre-computed bias from `assemble_features()` | `reasoner.py` | High |
| 2 | Add PDM, PWM, PMM, session mids computation | `reasoner.py` | High |
| 3 | Add session ranges computed from 1m (Asia, London, NY AM, NY PM) | `reasoner.py` | High |
| 4 | Add active FVGs filtered to target date | `reasoner.py` | High |
| 5 | Add active OBs filtered to target date | `reasoner.py` | High |
| 6 | Add liquidity levels (EQH, EQL, BSL, SSL) filtered | `reasoner.py` | High |
| 7 | Add market structure (recent BOS/MSS/CISD) | `reasoner.py` | Medium |
| 8 | Add HTF OHLC (4H, 1H recent bars) | `reasoner.py` | Medium |
| 9 | Compute dealing range %, premium/discount, BSL/SSL | `reasoner.py` | High |
| 10 | Fix `compute_ict_features` to add session ranges to derived parquets | `scripts/context/compute_ict_features` | Medium |
| 11 | Update prompt to be session-aware | `prompts/daily_bias_reasoner.md` | High |
| 12 | Build 3 independent vision analyses (not verification) | `agent_loop.py` | High |
| 13 | Build generate-validate-correct loop | `agent_loop.py` | High |