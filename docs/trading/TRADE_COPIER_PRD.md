# Local NinjaTrader 8 Trade Copier & RiskGuard Integration — Product Requirement Document (PRD)

**Status:** Draft v1.0  
**Target Platform:** NinjaTrader 8 Desktop Add-On (C# / WPF)  
**Author:** Antigravity AI & Pair Programmer  
**Context:** Prop-firm futures trading across multiple funded/eval accounts (Apex, Topstep, Cash), local single-machine execution, integration with existing RiskGuard AddOn (`v1.1.0`).

---

## 1. Executive Summary & Objective

### 1.1 Overview
The **Local NinjaTrader 8 Trade Copier** is a high-performance, sub-millisecond execution engine built to run natively inside NinjaTrader 8. It replicates trades from a designated **Leader Account** (e.g. manual trades from Chart Trader, TradingView webhooks, Tradovate Web, or automated strategies) to multiple **Follower Accounts** in real time.

### 1.2 Core Integration Goal with RiskGuard
The Copier works in tandem with **RiskGuard AddOn (`v1.1.0`)**. While the Copier's job is to **replicate and scale opportunity**, RiskGuard's job is to **protect and enforce hard risk limits**.

Together, they form a complete **Local Institutional Trading Suite**:
1. **Copier** places scaled entries across followers.
2. **RiskGuard** automatically attaches protective stops (FSM guard), enforces daily loss/drawdown limits, debounces trade counts, and flattens breached accounts via its background sweep watchdog.

---

## 2. RiskGuard + Trade Copier Architecture Analysis

### 2.1 Architectural Decision: Separate vs. Unified AddOn

We evaluated three potential integration patterns:

| Pattern | Operating Mechanics | Pros | Cons | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Option A: Completely Separate AddOns** | Copier runs as `TradeCopierAddOn.cs`; RiskGuard runs as `RiskGuardAddOn.cs`. They communicate strictly via NinjaTrader's account event bus. | • Independent deployment<br>• Zero code coupling | • Dual event handling overhead<br>• RiskGuard's `expected_copies` must be manually updated to match copier mappings | Acceptable |
| **Option B: Single Monolithic AddOn** | All copier and risk code inside one single `AddOnBase` class. | • Single WPF window<br>• Shared event lock | • Monolithic file risk ($>5,000$ lines) | Not Recommended |
| **Option C: Modular Engine Architecture (Recommended)** | Shared `NinjaScript.AddOns` namespace with modular engines: `TradeCopierEngine.cs`, `RiskGuardEngine.cs`, and a unified `RiskSuiteWindow.xaml` dashboard. | • Clean modular separation<br>• Shared state registry<br>• Single control panel<br>• Sub-millisecond direct in-memory communication | **BEST**: Maximum performance, zero event lag, seamless UI integration | **PREFERRED** |

### 2.2 Coexistence Rules & Safeguard Alignment

1. **Stealth Order Tagging & Invariant Safety**:
   * Copier submits follower orders with `OrderEntry.Manual` (matching Chart Trader entries).
   * RiskGuard's order filter inspects these follower entries. Since Copier orders create/reduce positions intentionally, RiskGuard validates them against the follower's `MaxPositionSize` and `DailyLossLimit`.
2. **Dynamic `expected_copies` Synchronization**:
   * When Copier mirrors 1 Leader trade to $N$ Follower accounts, RiskGuard's `EvaluateAggregateSizing` automatically scales aggregate sizing limits by $N$ active followers so Copier trades are never misidentified as aggregate oversizing breaches.
3. **Master Panic Button Synchronization**:
   * Clicking "FLATTEN ALL & STOP" in the Copier UI flattens all accounts and disarms both the Copier AND RiskGuard lockouts simultaneously.

---

## 3. Core Functional Requirements

### 3.1 Execution Modes

| Mode | Trigger Event | Mechanism | Best For |
| :--- | :--- | :--- | :--- |
| **Executions Mode** | `Account.ExecutionUpdate` | Follower orders submit as `OrderType.Market` ONLY after Leader fill is confirmed. | Scalping, volatile markets, avoiding unfilled follower limit orders. |
| **Orders Mode** | `Account.OrderUpdate` | Replicates pending working orders (Limit, Stop Market) and brackets directly to followers. | Precision entry, swing trading, matching exact limit prices. |

### 3.2 Position Sizing & Contract Translation Engine

```
[Leader Trade: 2 ES Long]
          │
          ├──> (Ratio 1.0x) ─────────> Follower 1: 2 ES Long
          ├──> (Ratio 0.5x) ─────────> Follower 2: 1 ES Long
          ├──> (Ratio -1.0x Inverse) ─> Follower 3: 2 ES Short
          └──> (Auto Symbol Mapping) ─> Follower 4: 20 MES Long
```

1. **Sizing Modes**:
   * **Exact (1:1)**: Replicates exact leader contract count.
   * **Ratio ($0.1\times$ to $50\times$)**: Multiplies leader contracts by a configurable multiplier.
   * **Fixed Lot**: Uses a fixed pre-set contract quantity on follower regardless of leader size.
   * **Fade / Inverse (Negative Ratio)**: Flits direction (Long $\rightarrow$ Short) for hedging.

2. **Mini $\leftrightarrow$ Micro Cross-Instrument Mapping**:
   * Built-in matrix: $1\text{ ES} = 10\text{ MES}$, $1\text{ NQ} = 10\text{ MNQ}$, $1\text{ CL} = 10\text{ MCL}$, $1\text{ GC} = 10\text{ MGC}$, $1\text{ RTY} = 10\text{ M2K}$.
   * Automatically scales size: e.g. Leader 2 NQ with $0.5\times$ ratio on NQ$\rightarrow$MNQ follower = $2 \times 0.5 \times 10 = 10\text{ MNQ}$.

### 3.3 Follower Guard & Per-Account Risk Limits

Each follower relationship configures:
- **Max Position Size**: Hard contract limit per follower.
- **Daily Loss Limit & Daily Target**: Automatically disarms copying and flattens follower on breach.
- **Quarantine Mode**: If a follower order is rejected by the broker (e.g. margin call), the account is immediately quarantined, alerted visually/audibly, and disabled from receiving further trades until manually reset.

### 3.4 Auto-Synchronization & Drift Reconciliation

- **Background Reconciliation Sweep (3s)**: Periodic background timer compares Leader `Position.Quantity` (scaled by ratio) against Follower `Position.Quantity`.
- **Drift Correction**: Submits corrective market orders if quantity drift exceeds threshold.
- **Reconnect Cooldown (5s)**: On broker reconnect, ignores historical event bursts for 5 seconds to prevent duplicate executions.

### 3.5 Stealth Mode & Anonymization

- Omits automation tags/labels on follower orders.
- Sets `OrderEntry.Manual` so follower orders appear indistinguishable from manual DOM/Chart Trader entries.

### 2.8 Strategy-Level Risk API & Self-Contained News Calendar

1. **Generic Strategy-Level Risk API (`RiskGuardClient`)**:
   * **Account-Level Uniformity:** Because `RiskGuardAddOn` operates at the `Account` level, all orders submitted by automated NinjaScript `Strategy` instances (`SubmitOrderUnmanaged`, `EnterLong`, `EnterShort`) are **automatically governed** by RiskGuard's rules (daily loss, max contracts per instrument, lockout sweep, news shield).
   * **1-Line Pre-Trade Strategy Check:** NinjaTrader strategies can query RiskGuard's in-process API in 1 line of C# code before generating entry signals:
     ```csharp
     if (!RiskGuardAddOn.Instance.CanTrade(Account.Name, Instrument.FullName, "MyStrategyName"))
         return; // Skip entry signal if RiskGuard is locked out or in news buffer
     ```

2. **Standalone Independent Economic Calendar (Zero-Dependency Portability)**:
   * **Self-Contained HTTP REST Feed:** To support sharing the AddOn with external traders without requiring a local database (Prisma) or external server setup, `PropFirmProtectionSuite` directly fetches economic calendar events from public JSON REST APIs (e.g. ForexFactory / FinancialModelingPrep public feeds).
   * **Local Disk Fallback Cache:** Caches fetched calendar events to `Documents\NinjaTrader 8\RiskGuard_NewsCalendar.json` so the AddOn functions seamlessly offline or during temporary network outages.

---

## 4. System Data Models

```csharp
public enum CopierExecutionMode { Executions, Orders }

public enum AtmStrategyType { FixedTicks, SwingPoint, AtrAdaptive, DrawdownShield, ScaledRunner }

public class EconomicNewsEvent
{
    public DateTime EventTimeUtc { get; set; }
    public string Title { get; set; } = "CPI Release";
    public string Currency { get; set; } = "USD";
    public string Impact { get; set; } = "High"; // High (Red Folder)
}

public class PropFirmProtectionConfig
{
    public bool EnableNewsShield { get; set; } = true;
    public int NewsBufferMinutesBefore { get; set; } = 2;
    public int NewsBufferMinutesAfter { get; set; } = 2;
    public string NewsCalendarApiUrl { get; set; } = "https://napi.forexfactory.com/calendar.json";
    public bool EnableProfitTargetLock { get; set; } = true;
    public double EvaluationTargetProfit { get; set; } = 3000.0;
    public bool EnablePeakEquityProtection { get; set; } = true;
    public double MaxPeakGivebackPct { get; set; } = 0.30;
    public bool EnableConsistencyCap { get; set; } = true;
    public double MaxDailyProfitPctOfTarget { get; set; } = 0.35;
    public bool EnableAutoDayFiller { get; set; } = false;
}

public class AtmStrategyConfig
{
    public string Name { get; set; } = "PropFirm_Standard";
    public AtmStrategyType Type { get; set; } = AtmStrategyType.DrawdownShield;
    public double AtrMultiplierSL { get; set; } = 1.5;
    public double AtrMultiplierTP { get; set; } = 2.5;
    public int SwingLookbackBars { get; set; } = 5;
    public int SwingBufferTicks { get; set; } = 4;
    public int BreakevenTriggerTicks { get; set; } = 12;
    public int BreakevenOffsetTicks { get; set; } = 2;
    public double PartialProfitPct { get; set; } = 0.50; // 50% partial exit
}

public class PropFirmProfile
{
    public string Name { get; set; } = "Apex Trader Funding";
    public List<string> AllowedInstruments { get; set; } = new List<string> { "NQ", "MNQ", "ES", "MES", "YM", "MYM", "CL", "MCL", "GC", "MGC", "RTY", "M2K" };
    public List<string> BlockedInstruments { get; set; } = new List<string> { "ZB", "ZN", "6E", "6B" };
}

public class PerInstrumentRiskConfig
{
    public int MaxContracts { get; set; } = 10;
    public bool IsBlocked { get; set; } = false; // Block execution entirely
    public double StopOffsetTicks { get; set; } = 40;
}

public class CopierRelationship
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string LeaderAccountName { get; set; }
    public string FollowerAccountName { get; set; }
    public bool IsEnabled { get; set; } = true;
    public CopierExecutionMode Mode { get; set; } = CopierExecutionMode.Executions;
    public double QuantityRatio { get; set; } = 1.0;
    public bool FixedLotMode { get; set; } = false;
    public int FixedLotSize { get; set; } = 1;
    public bool AutoSymbolConversion { get; set; } = true; // ES -> MES
    public int MaxPositionSize { get; set; } = 10;
    public Dictionary<string, PerInstrumentRiskConfig> InstrumentLimits { get; set; } = new Dictionary<string, PerInstrumentRiskConfig>();
    public List<string> BlockedInstruments { get; set; } = new List<string>(); // e.g. ["NQ", "ES", "YM"]
    public string SelectedPropFirmProfile { get; set; } = "Apex Trader Funding";
    public AtmStrategyConfig AtmStrategy { get; set; } = new AtmStrategyConfig();
    public PropFirmProtectionConfig ProtectionConfig { get; set; } = new PropFirmProtectionConfig();
    public double DailyLossLimit { get; set; } = 1000.0;
    public bool IsQuarantined { get; set; } = false;
    public string QuarantineReason { get; set; }
}

public class CopierState
{
    public bool IsGlobalActive { get; set; } = true;
    public List<CopierRelationship> Relationships { get; set; } = new List<CopierRelationship>();
}
```

---

## 5. UI Control Panel & Modern Professional Design System

The control panel will feature a high-end, modern dark-mode WPF design system (`#14171D` deep slate background, glassmorphic cards, crisp status badges, and intuitive micro-interactions):

```
+-----------------------------------------------------------------------------------+
| [COPIER: ACTIVE] | [RISKGUARD: ARMED (v1.1.0)] | [EMERGENCY FLATTEN ALL & STOP]   |
+-----------------------------------------------------------------------------------+
| [Tab 1: RiskGuard Dashboard] [Tab 2: Trade Copier Manager] [Tab 3: Instrument Risk] |
+-----------------------------------------------------------------------------------+
| PER-INSTRUMENT RISK & BLOCKING MATRIX                                             |
| Symbol | Max Contracts | Status   | Block Trade | Stop Offset | Actions           |
| ------ | ------------- | -------- | ----------- | ----------- | ----------------- |
| MNQ    | [ 2 ]         | ALLOWED  | [ ] Block   | 40 ticks    | [ Save ]          |
| MES    | [ 10 ]        | ALLOWED  | [ ] Block   | 16 ticks    | [ Save ]          |
| NQ     | [ 1 ]         | BLOCKED  | [X] Blocked | 40 ticks    | [ Unblock ]       |
| ES     | [ 2 ]         | BLOCKED  | [X] Blocked | 16 ticks    | [ Unblock ]       |
+-----------------------------------------------------------------------------------+
| Status: Auto-Sync Running (3s) | Latency: <1ms | Drift: 0 | Version: v1.1.0        |
+-----------------------------------------------------------------------------------+
```

---

## 6. Development Roadmap & Milestones

1. **Phase 1: Modular Engine Architecture**:
   - Create `TradeCopierEngine.cs` in `ninjatrader-addon/`.
   - Wire `OnExecutionUpdate` and `OnOrderUpdate` leader-to-follower dispatch.
2. **Phase 2: Sizing, Cross-Mapping & Inversion**:
   - Implement `Ratio`, `FixedLot`, `Fade/Inverse`, and `Mini<->Micro` symbol translation matrix.
3. **Phase 3: Follower Guard, Instrument Risk Matrix & Instrument Blocking**:
   - Implement per-instrument contract ceilings (e.g. MNQ: 2, MES: 10).
   - Implement instrument blacklist trade blocking filter (e.g. block NQ/ES minis).
   - Implement 3s auto-sync drift correction loop & reconnect cooldown.
4. **Phase 4: Professional Modern WPF UI Overhaul**:
   - Redesign WPF Dashboard with dark slate palette, tabbed navigation (RiskGuard, Copier Manager, Instrument Risk Matrix, Audit Log), live PnL cards, and instant toggle switches.
5. **Phase 5: Automated Verification & Live Stress Testing**:
   - Unit test per-instrument limits and instrument blocking filter in `RiskGuardAddOnTests.cs`.
   - Live stress test via PowerShell script against NinjaTrader `Sim101` and follower accounts.
