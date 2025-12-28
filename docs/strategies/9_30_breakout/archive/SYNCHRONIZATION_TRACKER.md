# ORB V3 Cross-Platform Synchronization Tracker

This document tracks technical fixes and logic enhancements made to ensure parity across TradingView (Indicator/Strategy) and NinjaTrader 8.

## Technical Fixes (V6 Compliance)

| Fix Description | Pine Indicator | Pine Strategy | NinjaTrader | Notes |
| :--- | :---: | :---: | :---: | :--- |
| **nz() Boolean Error** | ✅ | ✅ | N/A | V6 doesn't allow `nz()` on booleans. Moved to price source. |
| **ta.find_first_true() Missing** | ✅ | N/A | N/A | Replaced with manual `signalSent` state tracking. |
| **location Parameter** | ✅ | N/A | N/A | `plotshape` parameter renamed from `position` to `location`. |
| **Box Object Null Checks** | ✅ | N/A | N/A | Replaced `box[0]` with `not na(box)`. |
| **Shorttitle Length** | N/A | ✅ | N/A | Strategy shortened to `ORB V6 S` (8 chars). |

## Logic & Visual Enhancements

| Feature / Fix | Pine Indicator | Pine Strategy | NinjaTrader | Notes |
| :--- | :---: | :---: | :---: | :--- |
| **Regime Data Default** | ✅ | ✅ | ✅ | Missing SMA20 daily data now defaults to `True` (No Filter). |
| **Multi-Signal Visuals** | ✅ | [ ] | ✅ | Show up to N signals on chart (configurable). |
| **Indicator Multi-TP Lines** | ✅ | N/A | ✅ | Show TP1, TP2, and Final TP projection lines. |
| **Range Too Big Visual** | ✅ | ✅ | ✅ | ORB box turns red when range > maxRangePct. |
| **HUD Diagnostic Row** | ✅ | ✅ | ✅ | Added `Diag (Filt/CanT)` cell for troubleshooting. |
| **Pullback State Machine** | ✅ | ✅ | ✅ | Visuals distinguish between BO trigger and PB fill. |
| **Pending Order Cleanup** | N/A | ✅ | ✅ | Hard resets on window close/max attempts. |
| **Visual SL/TP Levels** | ✅ | ✅ | ✅ | Plot projected or active SL/TP lines on chart. |
| **Sweet Spot Highlight** | ✅ | ✅ | ✅ | Highlight 9:30 range box in orange if VVIX 98-115. |
| **Signal Candle Exit** | N/A | ✅ | ✅ | Exit on Wick/Close breach of breakout candle extreme. |
| **Cover the Queen** | N/A | ✅ | ✅ | Partial TP at TP1 (0.10%), runners to TP2 (0.35%). |
| **Hybrid Multi-TP** | N/A | ✅ | ✅ | Laddered TP1/TP2 + Runner with Trailing/Forever mode. |
| **Max Range % Filter** | N/A | ✅ | ✅ | Skip trades if OR > configurable % (default 0.25%). |
| **Buffer Breakout + Timeout** | N/A | ✅ | ✅ | Require 0.10% buffer close; enter at market after X bars if no pullback. |

## Next Sync Tasks
- [x] Port `Diag` HUD row to Indicator for visual parity.
- [ ] Port Multi-Signal visual logic to NinjaTrader indicator.
- [ ] Verify NinjaTrader Regime default logic matches Pine (default True if na).
- [ ] Ensure NinjaTrader HUD background visibility matches the new Dark Theme.
