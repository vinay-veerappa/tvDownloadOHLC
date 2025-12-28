# 9:30 Breakout: Unified V3 Multi-Platform Specification

This document defines the unified logic and customization suite for the 9:30 Breakout strategy across **PineScript (TradingView)** and **NinjaScript (NinjaTrader 8)**.

## 1. Core Logic & Variables
- **Opening Range**: 09:30 - 09:31 ET.
- **Reference Tickers**: NQ (Futures) / QQQ (ETF).
- **Secondary Series Requirements**: 
    - Daily OHLC for **SMA 20** (Regime Filter).
    - Daily Open for **VVIX** (Volatility Filter).

## 2. Configuration Matrix (Toggles & Inputs)

### A. Entry Configuration (Modular)

#### Breakout Trigger
Determines **when** a valid breakout has occurred.

| Input | Options | Description |
| :--- | :--- | :--- |
| **Trigger Mode** | `Aggressive`, `Standard`, `Displacement` | How to confirm breakout |

| Mode | Long Trigger | Short Trigger |
| :--- | :--- | :--- |
| **Aggressive** | High > Range High (wick touch) | Low < Range Low (wick touch) |
| **Standard** | Close > Range High | Close < Range Low |
| **Displacement** | Close > Range High + 0.10% buffer | Close < Range Low - 0.10% buffer |

#### Entry Execution
Determines **how** to enter after breakout confirmation.

| Input | Options | Description |
| :--- | :--- | :--- |
| **Entry Mode** | `Immediate`, `Pullback Only`, `Pullback + Fallback` | Execution style |
| **Pullback Target** | `0% (Boundary)`, `25%`, `50%` | Depth into range for limit order |
| **Fallback Timeout** | Int (5 bars) | Bars before market entry (Fallback mode only) |
| **Max Attempts** | 1 to 5 | Re-entry attempts if stopped out |

| Mode | Behavior |
| :--- | :--- |
| **Immediate** | Enter at market on breakout confirmation |
| **Pullback Only** | Wait for price to touch target AND **Close validly** (retest). Enter on next Open. |
| **Pullback + Fallback** | As above + market entry after timeout (if price still outside range) |

#### Guard Logic (Safety)
- **No Fakeout Arming**: Breakout candle *must* Close beyond the Pullback Level to arm the trade.
- **Deep Pullback Cancellation**: If price Closes *deeper* than the Pullback Level (crashing through), the pending trade is **cancelled**.

> [!TIP]
> See [STRATEGY_BUILDING_BLOCKS.md](STRATEGY_BUILDING_BLOCKS.md) for detailed flowcharts.

### B. Filter Toggles (Modular Optimization)
| Input Name | Type | Action If Enabled |
| :--- | :--- | :--- |
| **Use Regime Filter** | Boolean | Skip trades if NQ Daily Close < SMA20 (Daily). |
| **Use VVIX Filter** | Boolean | Skip trades if VVIX Open > 115. |
| **VVIX Sweet Spot** | Boolean | Extra visual highlight if VVIX is between 98-115. |
| **Tuesday Avoidance** | Boolean | Skip trades on Tuesdays. |
| **Max Range %** | Float (0.25%) | Skip if the 9:30 range size is larger than X% of price. |

### C. Exit & Risk Logic

#### Profit & Loss Targets (Hybrid Multi-TP)
| Input Name | Type | Logic Description |
| :--- | :--- | :--- |
| **Stop Loss** | Auto | Uses Range Low (Long) or Range High (Short) as default SL. |
| **Enable Multi-TP** | Boolean | Enable the laddered take profit system. |
| **TP1 Level / Qty** | Float (0.10%) / Int (50%) | First profit target and % of position to close. |
| **TP2 Level / Qty** | Float (0.25%) / Int (25%) | Second profit target and % of position to close. |
| **Runner Mode** | Option: None, Trailing, Forever | Behavior for remaining 25% of position. |
| **Trail %** | Float (0.08%) | For 'Trailing' mode: distance from peak to trail. |

#### Reversal Exits (Early Stops)
| Input Name | Type | Logic Description |
| :--- | :--- | :--- |
| **MAE Heat Filter** | Boolean + Float | Exit immediately if Adverse Excursion exceeds threshold (default 0.12%). |
| **Sig Candle Exit** | Option: None, Close, Wick | Exit if price reverses past the breakout candle's extreme. |
| **Early Exit (Close)** | Boolean | Exit if a 1-min candle closes back inside the 9:30 range. |

#### Risk Management
| Input Name | Type | Logic Description |
| :--- | :--- | :--- |
| **Max SL %** | Float (0.30%) | Cap stop loss at this % from entry (prevents excessive loss on Fallback entries). |
| **Stop After Win** | Auto | Stop trading for the day after a profitable trade closes. |

#### Time-Based Exits
| Input Name | Type | Logic Description |
| :--- | :--- | :--- |
| **Hard Exit Time** | Time (10:00 AM) | Force-close all positions at this specific time. |

## 3. Visuals

### Range Display
1. **Demarkers**: Plot lines at 25%, 50%, and 75% of the 09:30 range for visual entry reference.
2. **Buffer Lines**: Lines at **0.10% of Price** above and below the range boundaries.

### ORB Box Coloring
| Condition | Box Color |
| :--- | :--- |
| Range > maxRangePct | 🔴 Red (Too Big) |
| VVIX 98-115 (Sweet Spot) | 🟠 Orange |
| Normal | 🟣 Purple/Gray |

### Candle Bar Coloring
| Candle | Color | Purpose |
| :--- | :--- | :--- |
| 09:30 Range Candle | 🟡 Yellow | Shows range source |
| Breakout Trigger | 🔵 Cyan | Shows when logic activated |
| Fallback Entry | 🟢 Lime + ⚡ | Shows chased entry |

### HUD Dashboard
- **Regime**: BULL/BEAR
- **VVIX**: Value + Classification (SAFE/SWEET SPOT/EXTREME)
- **Range Stats**: Points and % of price + "⚠️ TOO BIG" if filtered
- **Entry Config**: Trigger Mode / Entry Mode
- **Trade Status**: Shows WON / IN TRADE (PB or ⚡Fallback) / WAIT / FILTERED

## 4. Platform Implementation
| Feature | PineScript V6 | NinjaTrader 8 |
| :--- | :--- | :--- |
| Dashboard | `table.new()` | `Draw.TextFixed()` |
| Secondary Data | `request.security()` | `AddDataSeries()` |
| Bar Coloring | `barcolor()` | N/A (Draw.Region) |
