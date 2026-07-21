# RiskGuard AddOn — Version History & Changelog

## Current Release: `v1.1.0` (2026-07-21)

### Major Changes & Failsafe Improvements
1. **Multi-Contract Trade Lifecycle Counting**:
   - Trade counting (`TradesToday`) is debounced and strictly incremented on genuine `Flat -> Non-Flat` transitions.
   - Multi-contract scaling ($1 \rightarrow 2$ contracts), split-bracket orders, or partial fills while position is non-flat no longer inflate the daily trade count.
2. **Lockout Safety Sweep Watchdog**:
   - Added active account polling inside `ExecuteSafetySweep` (1-second timer loop) for all locked accounts.
   - Ensures that if an account is locked with an open position, `FlattenPosition` is continuously retried until position quantity reaches `0` (eliminating the "locked with open position" deadlock).
3. **Risk-Reducing Order Permissibility**:
   - Orders that reduce position size (e.g. `Sell` when Long, `BuyToCover` when Short, or manual flatten orders) are **always allowed**, even when an account is locked out.
4. **Versioning System**:
   - Centralized `RiskGuardAddOn.Version = "1.1.0"` constant.
   - Dashboard Window Title displays `NinjaTrader Cross-Account Risk Guard Dashboard v1.1.0`.
   - Exposed `GET /api/riskguard/version` and `"version": "1.1.0"` in REST state inspections.

---

## Past Versions

### `v1.0.0` (Initial Release)
- Base RiskGuard AddOn release with event-driven protective stop guard (FSM state machine), daily loss limits, trailing drawdown limits, cooldown timers, edge window gates, and MCP bridge REST inspection endpoints.
