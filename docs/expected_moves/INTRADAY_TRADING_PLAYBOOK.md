# Intraday Trading Playbook (EM-Based)

This playbook provides data-driven strategies for intraday trading using Expected Move (EM) levels derived from comprehensive backtesting.

## Analysis Parameters

| Parameter | Value |
| :--- | :--- |
| **Ticker** | SPY |
| **Date Range** | 2023-12-19 to 2025-12-18 |
| **Trading Days** | 502 |
| **Data Location** | `docs/expected_moves/analysis_data/` |

---

## Quick Reference: Recommended Method

| Method | Formula | Containment @ 100% | Best For |
| :--- | :--- | :--- | :--- |
| **Synth VIX 1.0x (Open)** | `Open * (VIX_930/100) * sqrt(1/252) * 2.0` | **97.8%** | All-purpose intraday |
| Straddle 1.0x (Open) | `Open * (Straddle%_from_Close)` | 99.3% | Conservative boundary |

---

## Section 1: Method Rankings by Use Case

### 1A. Options Selling (Highest Containment)
| Method | Containment @ 100% | Median MFE | Median MAE |
| :--- | :--- | :--- | :--- |
| straddle_100_open | **99.3%** | 0.1504 | 0.1596 |
| straddle_085_open | 98.6% | 0.1770 | 0.1878 |
| synth_vix_100_open | 97.8% | 0.1765 | 0.1843 |

### 1B. S/R Identification (Most Touches at 50%)
| Method | Touch Upper % | Touch Lower % | Use |
| :--- | :--- | :--- | :--- |
| iv365_close | 88.5% | 18.2% | Aggressive targets |
| iv252_close | 85.1% | 14.9% | Statistical 1-SD |
| vix_raw_close | 83.1% | 10.2% | Raw VIX projection |

### 1C. Target Setting (Tightest Range)
| Method | Median MFE | Median MAE | Price Uses |
| :--- | :--- | :--- | :--- |
| straddle_100_open | 0.150 | 0.160 | ~16% of EM |
| synth_vix_100_open | 0.177 | 0.184 | ~18% of EM |

---

## Section 2: Level Usage Table

Based on **Synth VIX 1.0x (Open 9:30 AM)**:

| Level | Containment | Use Case |
| :--- | :--- | :--- |
| **50%** | 82.7% | Initial target / Speed bump |
| **61.8%** | 90.2% | Fibonacci retracement |
| **100%** | 97.8% | Hard boundary / Stop zone |
| **127.2%** | 99.2% | Extension target (trend days) |
| **150%** | 99.6% | Extreme move / Fade zone |
| **200%** | 100.0% | Black swan / Never fade |

---

## Section 3: Options Strategies

### Iron Condor Wing Placement
| Short Strike Level | Method: synth_vix_100_open | Method: straddle_100_close |
| :--- | :--- | :--- |
| 100% EM | 97.8% POP | 95.7% POP |
| 127% EM | 99.2% POP | 99.3% POP |
| 150% EM | 99.6% POP | 99.8% POP |

### Straddle Seller Edge
- **Win Rate (Contained @ 100%)**: 97.8%
- **Avg Price Usage**: 23% of EM
- **Implied Edge**: Straddles are priced for 100% of the EM, but price typically only uses 23%. This is the theoretical "theta decay" edge.

### Jade Lizard Setup
- Sell naked Put @ 100% EM Lower
- Sell Call Spread @ 127% - 150% EM Upper
- Net credit covers directional risk

---

## Section 4: Direct Trading Playbook

### Daily Setup (9:30 AM)
1. Get VIX at 9:30 AM (first 5m bar after open)
2. Get SPY Open price
3. Calculate: `EM = Open * (VIX/100) * sqrt(1/252) * 2.0`
4. Mark levels:
   - 50% Up/Down
   - 100% Up/Down
   - 150% Up/Down

### Entry Strategies

#### Mean Reversion
| Condition | Action |
| :--- | :--- |
| Price touches 50% EM | Look for reversal candle |
| Reversal confirmed | Enter counter-trend |
| Stop | Below 100% EM |
| Target | Open Price |

#### Breakout
| Condition | Action |
| :--- | :--- |
| Price breaks 50% EM with momentum | Enter in direction |
| Target 1 | 100% EM |
| Stop | Back inside 50% EM |

#### Fade Extreme
| Condition | Action |
| :--- | :--- |
| Price reaches 150% EM | Enter counter-trend |
| Confidence | 99.6% of days don't exceed this |
| Target | 100% EM |
| Stop | 200% EM |

---

## Section 5: Data Files

| File | Description |
| :--- | :--- |
| `data/analysis/em_daily_levels.csv` | All levels for each day/method |
| `data/analysis/em_daily_performance.csv` | MFE/MAE for each day/method |
| `data/analysis/em_level_touches.csv` | 5m touch/reversal data |
| `data/analysis/em_method_summary.csv` | Summary statistics |

---

## Key Insights

1. **Open-Anchored > Close-Anchored**: Using the Open price as anchor dramatically improves containment (99% vs 72%).
2. **9:30 AM VIX is the Best Proxy**: The synthetic VIX straddle matches actual market behavior better than EOD data.
3. **50% EM is the "Speed Bump"**: Touched on ~17% of days, high reversal rate, ideal for mean reversion.
4. **100% EM is the "Wall"**: Only 2.2% of days breach this level - use for stop placement.
5. **150% EM is "Fade Territory"**: Only 0.4% of days breach - aggressive faders win here.
