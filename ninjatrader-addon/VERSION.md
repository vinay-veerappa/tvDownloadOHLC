# RiskGuard & McpBridge AddOn — Version History & Changelog

## Current Release: `v1.7.0-ui-audit` (2026-07-25)

### UI/UX Critical Audit & Feature Enhancements
1. **Interactive UI Enhancements (`TradeCopierWindow.cs`)**:
   - Added inline `🔓 Unquarantine / ☣ Quarantine` toggle buttons to relationships and group controls.
   - Designed non-blocking 1.5s Hold-To-Confirm Panic controls for mass account liquidations.
   - Added real-time Execution Audit stream panel for tracking order fills and auto-sync drift.

2. **3 Core Copier Safety Rules (`TradeCopierEngine.cs`)**:
   - **Hedging Prevention**: Delta-based netting logic blocks opposite-side market orders when flat and caps reduction quantities.
   - **Position Reconciler**: Event-driven fill verification comparing follower vs leader position direction.
   - **Auto-Close Follower Positions**: Automatically flattens follower positions and cancels working orders when leader reaches 0 qty.

3. **Multi-Agent Industry Benchmark Roadmap**:
   - Planned **Execution Latency & Slippage Badges** (100ms real-time WPF binding).
   - Planned **Red-Folder News Shield Overlay** with Break-Glass override controls.

---

## Past Releases

### `v1.6.0-audit` (2026-07-25)
- **Thread-Safe Emergency Flatten Sequence (`AUDIT-NT8-001`)**.
- **Atomic RiskGuard Persistence Model (`AUDIT-NT8-002`)**.
- **Trade Copier Threading & Scaling Precision (`AUDIT-NT8-003`)**.

### `v1.5.0` (2026-07-21)
- **Local Trade Copier Engine (`TradeCopierEngine.cs`)**: Multi-Account Leader-to-Follower replication with ratio scaling.
- **Prop-Firm Protection Suite (`PropFirmProtectionSuite.cs`)**: USD Red-Folder News Shield, Evaluation Target Lock.
- **Five New MCP Protocol Expansion Tools (`McpBridgeAddOn.cs`)**: `nt_inspect_strategy`, `nt_get_logs`, `nt_capture_chart`, `nt_open_chart`, `nt_subscribe_fills`.

### `v1.0.0` (Initial Release)
- Base RiskGuard AddOn release with protective stop guard (FSM state machine), daily loss limits, trailing drawdown limits.

