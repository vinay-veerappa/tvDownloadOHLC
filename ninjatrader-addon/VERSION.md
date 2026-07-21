# RiskGuard & McpBridge AddOn — Version History & Changelog

## Current Release: `v1.5.0` (2026-07-21)


### Major Changes & Feature Additions
1. **Local Trade Copier Engine (`TradeCopierEngine.cs`)**:
   - Multi-Account Leader-to-Follower replication with ratio scaling, fixed-lot sizing, and Mini-to-Micro symbol translation ($1\text{ NQ} = 10\text{ MNQ}$).
2. **Prop-Firm Protection Suite (`PropFirmProtectionSuite.cs`)**:
   - High-Impact USD Red-Folder News Shield (CPI/FOMC), Evaluation Target Lock ($+\$3,000$), Intraday Peak Equity Protection (30% giveback cap).
3. **Four Dynamic Prop-Firm ATM Strategies (`DynamicAtmManager.cs`)**:
   - Swing-Point Trailing, ATR Volatility-Adaptive, Drawdown Shield (Breakeven to `Entry + 2` at $+1.0R$), Scaled Runner ATM.
4. **Per-Instrument Caps & Blacklist Filtering (`RiskGuardAddOn.cs`)**:
   - Per-instrument max contract limits (e.g. `MNQ`: 10, `MES`: 10) and blacklisted ticker cancellation (`NQ`, `ES`, `YM`).
5. **Five New MCP Protocol Expansion Tools (`McpBridgeAddOn.cs`)**:
   - `nt_inspect_strategy` (C# reflection schema discovery for 62 loaded strategies), `nt_get_logs` (Tail `interventions.jsonl`), `nt_capture_chart` (WPF RenderTargetBitmap base64 PNG rendering), `nt_open_chart` (Programmatic chart tab opening), `nt_subscribe_fills` / `/api/events/fills` (Real-time fill streaming).
6. **Multi-Contract Trade Lifecycle Counting & Sweep Watchdog**:
   - Trade counting (`TradesToday`) debounced on genuine `Flat -> Non-Flat` transitions.
   - Active 1s watchdog sweep flattens locked accounts with open positions.
   - Position-reducing closing orders (`Sell`/`BuyToCover`) permitted during lockouts.
7. **Versioning & Endpoints**:
   - Centralized `Version = "1.1.0"`, exposed `GET /api/riskguard/version`.

---

## Past Versions

### `v1.0.0` (Initial Release)
- Base RiskGuard AddOn release with event-driven protective stop guard (FSM state machine), daily loss limits, trailing drawdown limits, cooldown timers, edge window gates, and MCP bridge REST inspection endpoints.
