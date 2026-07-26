# IB Strategy Automation Design Document

**Status:** Draft (2026-07-26, updated with Phase D-F findings)
**Reference:** `EDGE_VALIDATION_REPORT.md` (validated metrics), `STRATEGY_COMPENDIUM.md` (IF/THEN/ELSE rules), `STATISTICAL_DISCOVERY_PLAN.md` (coverage status)
**Target platforms:** NinjaTrader 8 (C#), TradingView (Pine Script v5)
**Instrument:** NQ1 (MNQ for live), ES1 (MES for live) — NY AM IB session, customizable to any time range

---

## 0. Resumption Guide (for future sessions)

This section is for picking up the implementation in a later session.

### 0.1 What has been done

| Phase | Script | What was validated | Commit |
|---|---|---|---|
| A | `ib_pilot_stats.py` | 6 missing derived fields, baseline stats, 5 Edgeful rules | `ff2ccca7` |
| B | `ib_pilot_stacks.py` | Condition stacks, bootstrap CIs, ES1 cross-check | `94a689b7` |
| C | `ib_pilot_5year.py` | 5-year edge survival (per year/DOW/month/target) | `0270d74d` |
| D | `ib_pilot_stops.py` | Stop optimization, MAE/MFE, pullback depth, predictive model | `27de0ac7` |
| E | `ib_pilot_comprehensive.py` | All 3 plays, all 8 bias variants, all 13 entry modules, exit features | `76f75755` |
| F | `ib_pilot_durations.py` | Multi-duration IB comparison (5/15/30/45/60 min) | `5a2913b4` |

### 0.2 What needs to be implemented

| Phase | Deliverable | Status |
|---|---|---|
| 1 | `IBStrategyBase.cs` + `IBRange.cs` indicator | NOT STARTED |
| 2 | `IBBreakoutBot.cs` (Play 1) | NOT STARTED |
| 3 | `IBFadeBot.cs` (Play 3) | NOT STARTED |
| 4 | NT backtest validation (5 steps) | NOT STARTED |
| 5 | `IBStrategyLib.pine` + `IBBreakoutStrategy.pine` | NOT STARTED |
| 6 | `IBFadeStrategy.pine` | NOT STARTED |
| 7 | TV Strategy Tester validation | NOT STARTED |
| 8 | Live sim deployment (MNQ) | NOT STARTED |

### 0.3 Key decisions already made

1. **Default IB duration = 30 min** (not 60) — IB30 has stronger Rule 1 (86.8% vs 84.6%) and 29% less dollar risk. See Section 2.1.
2. **Default stop = 0.25R** (not ib_opposite 1.0R) — tighter stops don't change E[R] because MAE rarely exceeds 0.25R. See Section 4.2.
3. **Default play = 3 (fade) at 0.25x target** — E[R] +0.259, the strongest significant edge. See Section 4.1.
4. **Rule 3 clock filter is INVERTED on NQ1/ES1** — late breaks hold (92.8%), early breaks fade (78.8%). See Section 2.4.
5. **Calendar filters: skip Monday (Play 2), May (Play 1), October (Play 3)**. See Section 2.5.
6. **Skip huge IB days** (range_pct > 0.9%) — the predictive model shows range_pct is the strongest negative predictor. See Section 2.7.
7. **The IB duration, start time, and end time are ALL fully customizable** — the strategy works on any time range, not just 09:30-10:30. See Section 2.1.

### 0.4 Files to read before starting implementation

- `docs/strategies/initial_balance_break/EDGE_VALIDATION_REPORT.md` — all validated metrics
- `docs/strategies/initial_balance_break/STRATEGY_COMPENDIUM.md` — all IF/THEN/ELSE rules
- `docs/strategies/initial_balance_break/STATISTICAL_DISCOVERY_PLAN.md` — coverage status (19 of 22 done)
- `docs/strategies/ninjatrader/risk_manager_suite/RiskManagerBase.cs` — the existing base class to extend
- `scripts/edgeful/ib_pilot_stats.py` — the Python reference implementation (all derived fields)
- `scripts/edgeful/ib_pilot_durations.py` — the multi-duration comparison logic

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    IB Strategy Automation                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │
│  │  IB Window   │──>│  Direction   │──>│  Entry Gate  │     │
│  │  (custom     │   │  Trigger     │   │  (break/     │     │
│  │  start/end/  │   │  (Rule 1)    │   │   fade)      │     │
│  │  duration)   │   │              │   │              │     │
│  └──────────────┘   └──────────────┘   └──────┬───────┘     │
│                                                │             │
│                                                v             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │
│  │  Exit Manager│<──│  Risk Manager│<──│  Position    │     │
│  │  (TP/SL/     │   │  (size, DD,  │   │  Manager     │     │
│  │   time/      │   │   daily loss,│   │  (entry,     │     │
│  │   trailing)  │   │   ADR-020)   │   │   scale-in)  │     │
│  └──────────────┘   └──────────────┘   └──────────────┘     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 Dual-platform parity

The strategy must produce **identical signals** on both NinjaTrader and TradingView. The shared logic:

| Component | NinjaTrader (C#) | TradingView (Pine v5) |
|---|---|---|
| IB window | `Bars.IsFirstBarOfSession` + time check | `time.session(start-end)` |
| Direction trigger | `bias_formation_firstreach` computed inline | Same logic in Pine |
| Entry gate | `OnBarUpdate()` close-based check | `barstate.isconfirmed` close check |
| Stop/target | `SetStopLoss()` / `SetProfitTarget()` | `strategy.entry` + `strategy.exit` |
| Risk manager | `RiskManagerBase` (existing) | Pine `strategy` with `qty` sizing |
| ADR-020 | `FlattenBy = 1600` (existing) | `session(start-1600)` + `close_entries` |

### 1.2 Custom time range support

The IB window is **fully customizable** — any start time, end time, and duration. The strategy is not hardcoded to 09:30-10:30. Examples:

| Config | Start | Duration | Use case |
|---|---|---|---|
| NY AM IB (default) | 09:30 ET | 30 min | Primary validated strategy |
| NY AM IB60 | 09:30 ET | 60 min | Original IB (more data, wider stop) |
| Midnight OR | 00:00 ET | 30 min | ICT midnight open range |
| London IB | 03:00 ET | 60 min | London session IB |
| Globex IB | 18:00 ET | 60 min | Overnight IB |
| Custom | any | any | User-defined via `ib_custom_ranges.yaml` |

The `ib_start_time` and `ib_duration_min` parameters drive everything downstream — the direction trigger, entry gate, clock filter, and exit manager all adapt automatically.

---

## 2. Strategy Parameters

### 2.1 IB Window Parameters (FULLY CUSTOMIZABLE)

| Parameter | Default | Range | Description |
|---|---|---|---|
| `ib_start_time` | 09:30 ET | any HH:MM | IB window start (any time, any session) |
| `ib_duration_min` | **30** | 5-120 | IB duration in minutes (30 = optimal per Phase F) |
| `ib_end_time` | computed | — | Auto-computed: `ib_start_time + ib_duration_min` |
| `session_end_time` | 16:00 ET | any HH:MM | Session end (for ADR-020 forced exit) |
| `flatten_by_time` | 15:50 ET | any HH:MM | Hard exit time (ADR-020) |
| `outcome_window_min` | computed | — | Auto-computed: `session_end - ib_end` |

**Phase F finding:** IB30 is the optimal duration — it captures 72% of the IB60 range, has a stronger Rule 1 trigger (86.8% vs 84.6%), and reduces dollar risk by 29% ($61 vs $86 per Micro). IB5 and IB15 cannot front-run the IB60 direction (AUC 0.47, no predictive power). The user can override to any duration (5-120 min) for custom time ranges.

### 2.2 Direction Trigger Parameters (Rule 1)

| Parameter | Default | Range | Description |
|---|---|---|---|
| `rule1_enabled` | true | bool | Enable/disable direction trigger |
| `close_position_top_pct` | 0.75 | 0.50-0.95 | Top percentile for long trigger |
| `close_position_bot_pct` | 0.25 | 0.05-0.50 | Bottom percentile for short trigger |
| `require_direction_trigger` | true | bool | Skip trade if trigger disagrees with break |

### 2.3 Play Selection

| Parameter | Default | Range | Description |
|---|---|---|---|
| `active_play` | **3** | 1, 2, 3 | Which play to execute (1=breakout, 2=retest, 3=fade) |
| `target_lvl` | **0.25** | 0.25, 0.5, 0.75, 1.0 | Target level in IB range multiples |
| `stop_type` | **mae_calibrated_025** | ib_opposite, ib_edge, mae_calibrated_025, mae_calibrated_030, fixed_r | Stop placement method |
| `stop_r_mult` | **0.25** | 0.10-1.0 | Stop distance in R-multiples (0.25R = optimal per Phase D) |

**Phase D finding:** A 0.25R stop preserves the full edge (E[R] unchanged) while reducing dollar risk by 75%. The MAE of winners rarely exceeds 0.25R (P80 winner MAE = 0.232R). The optimal stop sits between P80 winner MAE (0.232R) and P50 loser MAE (0.405R) — a 0.30R stop is the theoretical optimum.

### 2.4 Clock Filter (Rule 3)

| Parameter | Default | Range | Description |
|---|---|---|---|
| `clock_filter_enabled` | true | bool | Enable clock-based sizing |
| `early_break_threshold_min` | 90 | 60-120 | Minutes after IB close (90 = 12:00) |
| `early_break_size_mult` | 0.5 | 0.25-1.0 | Size multiplier for early breaks |
| `late_break_size_mult` | 1.0 | 0.5-1.0 | Size multiplier for late breaks |

### 2.5 Calendar Filters

| Parameter | Default | Range | Description |
|---|---|---|---|
| `skip_monday_play2` | true | bool | Skip Play 2 on Monday (E[R] -0.048) |
| `skip_february_play2` | true | bool | Skip Play 2 in February (E[R] -0.135) |
| `skip_may_play1` | true | bool | Skip Play 1 in May (E[R] -0.048) |
| `skip_october_play3` | true | bool | Skip Play 3 in October (E[R] -0.166) |

### 2.6 Risk Management

| Parameter | Default | Range | Description |
|---|---|---|---|
| `risk_per_trade_pct` | 0.50 | 0.10-2.0 | % of account risked per trade |
| `max_trades_per_day` | 2 | 1-5 | Hard cap on daily trades |
| `daily_max_loss_pct` | 2.0 | 1.0-5.0 | Daily max loss as % of account |
| `trailing_drawdown_pct` | 5.0 | 2.0-10.0 | Trailing drawdown limit |
| `starting_account` | 50000 | — | Starting account size (for sim) |
| `contract_type` | micro | micro, mini | Micro (MNQ/MES) or Mini (NQ/ES) |

### 2.7 IB Size Filter (from Phase D predictive model)

| Parameter | Default | Range | Description |
|---|---|---|---|
| `skip_huge_ib` | true | bool | Skip days where range_pct > 0.9% (huge IB = rotation, negative E[R]) |
| `max_range_pct` | 0.90 | 0.50-2.0 | Maximum IB range_pct to trade (skip above this) |
| `min_range_pct` | 0.10 | 0.01-0.50 | Minimum IB range_pct to trade (skip below — too tight) |

**Phase D finding:** `range_pct` is the strongest negative predictor in the logistic model (coefficient -0.88). Huge IB days (>0.9% range) are rotation days — the edge disappears. The optimal Play 1 stack (Rule 1A + skip huge + skip Monday) lifts E[R] from +0.079 to +0.115 (+46%).

### 2.8 Bias Variant Selection (from Phase E)

| Parameter | Default | Range | Description |
|---|---|---|---|
| `bias_variant` | bias_combined | bias_formation_firstreach, bias_formation_lasttouch, bias_close_dir, bias_fvg, bias_fvg_ifvg, bias_fvg_rth, bias_fvg_1011, bias_combined | Which bias variant to use for direction filtering |
| `use_bias_filter` | true | bool | Only trade in the bias direction |

**Phase E finding:** `bias_combined` direction +1 is the strongest bias filter (+0.022 lift, PF 1.69). `bias_fvg_1011` direction -1 is surprisingly strong (+0.025 lift). All bias variants add positive lift when filtering for the +1 direction.

### 2.9 Entry Module Selection (from Phase E)

| Parameter | Default | Range | Description |
|---|---|---|---|
| `entry_module` | none | none, E11_80_rule, E18_wick_fade, E8_failed_breakout, E9_opening_drive | Optional entry confirmation module |

**Phase E finding:** E11 80%-rule is the strongest entry module (+0.093 lift, PF 4.95) but only fires on 4% of days. E18 wick-dominant fade is second (+0.020 lift, 61% WR). Most entry modules add zero lift because they fire on ~100% of days. Default is `none` (no entry module filter) for maximum coverage.

---

## 3. Algorithm Specification

### 3.1 IB Window Builder (CUSTOMIZABLE — any start time, any duration)

```
PARAMETERS: ib_start_time (HH:MM), ib_duration_min (int), session_end_time (HH:MM)
COMPUTED: ib_end_time = ib_start_time + ib_duration_min

STATE: ib_high, ib_low, ib_open, ib_close, ib_range, ib_mid
       ib_close_position, ib_candle_color, bias_firstreach
       ib_complete (bool), first_high_done_time, first_low_done_time

ON each 1-min bar:
  IF  time >= ib_start_time AND time < ib_end_time
  THEN
      IF  first bar of IB window
      THEN ib_open = bar.open; ib_high = bar.high; ib_low = bar.low
      ELSE ib_high = max(ib_high, bar.high)
           ib_low = min(ib_low, bar.low)
           ib_close = bar.close  # updated each bar; final at 10:30

      # Track which extreme was touched first
      IF  bar.high == ib_high AND first_high_touch_time is null
      THEN first_high_touch_time = bar.time
      IF  bar.low == ib_low AND first_low_touch_time is null
      THEN first_low_touch_time = bar.time

  ELSE IF time == ib_end_time (10:30)
  THEN
      ib_range = ib_high - ib_low
      ib_mid = (ib_high + ib_low) / 2
      ib_close_position = (ib_close - ib_low) / ib_range  # guard zero range
      ib_candle_color = sign(ib_close - ib_open)
      bias_firstreach = +1 if first_low_touch < first_high_touch
                       -1 if first_high_touch < first_low_touch
                       0 if tie
      ib_complete = true
```

### 3.2 Direction Trigger (Rule 1)

```
ON ib_complete = true:
  IF  bias_firstreach == +1 AND ib_close_position >= close_position_top_pct
  THEN predicted_break_dir = +1  (long bias: expect IB high to break first)

  ELSE IF bias_firstreach == -1 AND ib_close_position <= close_position_bot_pct
  THEN predicted_break_dir = -1  (short bias: expect IB low to break first)

  ELSE
      predicted_break_dir = 0  (no directional edge; trade both directions or skip)
```

### 3.3 Entry Gate — Play 1 (Breakout)

```
ON each 1-min bar after ib_complete:
  IF  already_in_trade THEN return

  # IB size filter (Phase D)
  IF  range_pct > max_range_pct OR range_pct < min_range_pct THEN skip

  # Calendar filter
  IF  calendar_filter(active_play, dow, month) == SKIP THEN skip

  IF  bar.close > ib_high  (close-confirmed break)
  THEN
      IF  require_direction_trigger AND predicted_break_dir != +1
      THEN skip (direction trigger disagrees)
      ELSE
          entry_price = bar.close
          stop_price = entry_price - stop_r_mult * target_lvl * ib_range  (MAE-calibrated)
          target_price = ib_high + target_lvl * ib_range
          size = base_size * clock_size_multiplier(first_break_minutes)
          ENTER LONG

  ELSE IF bar.close < ib_low  (close-confirmed break)
  THEN
      IF  require_direction_trigger AND predicted_break_dir != -1
      THEN skip
      ELSE
          entry_price = bar.close
          stop_price = entry_price + stop_r_mult * target_lvl * ib_range  (MAE-calibrated)
          target_price = ib_low - target_lvl * ib_range
          size = base_size * clock_size_multiplier(first_break_minutes)
          ENTER SHORT
```

### 3.4 Entry Gate — Play 3 (Fade)

```
ON each 1-min bar after ib_complete:
  IF  already_in_trade THEN return

  # Detect overshoot
  IF  bar.high > ib_high + 0.25 * ib_range  (overshoot above)
  THEN
      overshoot_above = true

  # Detect touch-back (close back inside)
  IF  overshoot_above AND bar.close < ib_high
  THEN
      entry_price = ib_high  (fade entry at the boundary)
      stop_price = ib_high + 0.5 * ib_range
      target_price = ib_mid
      size = base_size * clock_size_multiplier(first_break_minutes)
      ENTER SHORT  (fade the overshoot)

  # Mirror for low side
  IF  bar.low < ib_low - 0.25 * ib_range
  THEN overshoot_below = true
  IF  overshoot_below AND bar.close > ib_low
  THEN
      entry_price = ib_low
      stop_price = ib_low - 0.5 * ib_range
      target_price = ib_mid
      ENTER LONG
```

### 3.5 Clock Size Multiplier (Rule 3)

```
FUNCTION clock_size_multiplier(break_minutes):
  IF  break_minutes < early_break_threshold_min  (90 = 12:00)
  THEN return early_break_size_mult  (0.5 — early breaks are noisier on NQ1)
  ELSE return late_break_size_mult  (1.0 — late breaks hold better)
```

### 3.6 Calendar Filter

```
FUNCTION calendar_filter(play, dow, month):
  IF  play == 2 AND skip_monday_play2 AND dow == Monday THEN return SKIP
  IF  play == 2 AND skip_february_play2 AND month == February THEN return SKIP
  IF  play == 1 AND skip_may_play1 AND month == May THEN return SKIP
  IF  play == 3 AND skip_october_play3 AND month == October THEN return SKIP
  return OK
```

### 3.7 Exit Manager

```
ON each bar while in_trade:
  # 1. Target hit (touch-based)
  IF  position == LONG AND bar.high >= target_price
  THEN EXIT at target_price

  IF  position == SHORT AND bar.low <= target_price
  THEN EXIT at target_price

  # 2. Stop hit (touch-based)
  IF  position == LONG AND bar.low <= stop_price
  THEN EXIT at stop_price

  IF  position == SHORT AND bar.high >= stop_price
  THEN EXIT at stop_price

  # 3. ADR-020 forced exit
  IF  time >= flatten_by_time (15:50 ET)
  THEN EXIT at market

  # 4. Trailing stop (S15 — optional)
  IF  trailing_enabled
  THEN
      IF  position == LONG AND bar.high >= entry + 0.5 * ib_range
      THEN stop_price = max(stop_price, entry_price)  # move to breakeven
      IF  position == LONG AND bar.high >= entry + 1.0 * ib_range
      THEN stop_price = max(stop_price, entry_price + 0.5 * ib_range)
      # Mirror for SHORT
```

### 3.8 Risk Manager (reuses existing RiskManagerBase)

```
ON entry:
  contracts = (account_equity * risk_per_trade_pct / 100) / (stop_distance_points * point_value)
  contracts = min(contracts, max_contracts)
  IF  contracts < 1 AND contract_type == micro THEN contracts = 1  # minimum 1 micro

ON each bar:
  IF  daily_loss > daily_max_loss THEN stop trading for day
  IF  trades_today >= max_trades_per_day THEN stop trading for day
  IF  trailing_drawdown_hit THEN stop trading for day
```

---

## 4. NinjaTrader Implementation

### 4.1 File structure

```
ninjatrader-addon/
├── Strategies/
│   └── Vinay/
│       ├── IBStrategyBase.cs      # Abstract base (IB window, direction trigger, calendar filter)
│       ├── IBBreakoutBot.cs       # Play 1 concrete strategy
│       ├── IBFadeBot.cs           # Play 3 concrete strategy
│       └── IBRetestBot.cs         # Play 2 concrete strategy (optional)
├── Indicators/
│   └── Vinay/
│       └── IBRange.cs             # Visual indicator (IB high/low/mid lines)
└── AddOns/
    └── Vinay/
        └── RiskManagerAddOn.cs    # Existing — reuse as-is
```

### 4.2 IBStrategyBase.cs — class skeleton

```csharp
public abstract class IBStrategyBase : RiskManagerBase
{
    // IB Window State
    protected double ibHigh, ibLow, ibOpen, ibClose, ibRange, ibMid;
    protected double ibClosePosition;  // 0-1
    protected int    biasFirstreach;   // +1, -1, 0
    protected bool   ibComplete;
    protected DateTime firstHighTouch, firstLowTouch;
    protected int    predictedBreakDir;  // +1, -1, 0

    // Parameters (in addition to RiskManagerBase params)
    // IB Window (FULLY CUSTOMIZABLE — any start time, any duration)
    [NinjaScriptProperty] public int IbStartHour { get; set; } = 9;
    [NinjaScriptProperty] public int IbStartMinute { get; set; } = 30;
    [NinjaScriptProperty] public int IbDurationMin { get; set; } = 30;  // Phase F: 30 is optimal
    [NinjaScriptProperty] public int SessionEndHour { get; set; } = 16;
    [NinjaScriptProperty] public int SessionEndMinute { get; set; } = 0;
    [NinjaScriptProperty] public int FlattenByHour { get; set; } = 15;
    [NinjaScriptProperty] public int FlattenByMinute { get; set; } = 50;

    // Direction Trigger (Rule 1)
    [NinjaScriptProperty] public double ClosePositionTopPct { get; set; } = 0.75;
    [NinjaScriptProperty] public double ClosePositionBotPct { get; set; } = 0.25;
    [NinjaScriptProperty] public bool RequireDirectionTrigger { get; set; } = true;

    // Play Selection
    [NinjaScriptProperty] public int ActivePlay { get; set; } = 3;  // Phase D: Play 3 is strongest
    [NinjaScriptProperty] public double TargetLvl { get; set; } = 0.25;  // Phase D: 0.25x is optimal
    [NinjaScriptProperty] public double StopRMult { get; set; } = 0.25;  // Phase D: 0.25R stop

    // Clock Filter (Rule 3 — INVERTED on NQ1/ES1)
    [NinjaScriptProperty] public int EarlyBreakThresholdMin { get; set; } = 90;
    [NinjaScriptProperty] public double EarlyBreakSizeMult { get; set; } = 0.5;
    [NinjaScriptProperty] public double LateBreakSizeMult { get; set; } = 1.0;

    // Calendar Filters
    [NinjaScriptProperty] public bool SkipMondayPlay2 { get; set; } = true;
    [NinjaScriptProperty] public bool SkipFebruaryPlay2 { get; set; } = true;
    [NinjaScriptProperty] public bool SkipMayPlay1 { get; set; } = true;
    [NinjaScriptProperty] public bool SkipOctoberPlay3 { get; set; } = true;

    // IB Size Filter (Phase D)
    [NinjaScriptProperty] public bool SkipHugeIb { get; set; } = true;
    [NinjaScriptProperty] public double MaxRangePct { get; set; } = 0.90;
    [NinjaScriptProperty] public double MinRangePct { get; set; } = 0.10;

    protected override void OnBarUpdate()
    {
        if (!InSession()) return;

        if (!ibComplete)
        {
            BuildIBWindow();
            return;
        }

        if (CurrentBar < BarsRequired) return;

        if (tradeIsActive)
        {
            ManageOpenTrade();
            if (Position.MarketPosition == MarketPosition.Flat) return;
        }
        else
        {
            if (CalendarFilter()) return;
            CheckForEntry();  // abstract — implemented by Play 1/2/3 subclasses
        }
    }

    protected abstract void CheckForEntry();

    private void BuildIBWindow() { /* ... */ }
    private void ComputeDirectionTrigger() { /* ... */ }
    private bool CalendarFilter() { /* ... */ }
    protected double ClockSizeMultiplier(int breakMinutes) { /* ... */ }
}
```

### 4.3 IBBreakoutBot.cs (Play 1)

```csharp
public class IBBreakoutBot : IBStrategyBase
{
    protected override void CheckForEntry()
    {
        if (Close[0] > ibHigh)
        {
            if (RequireDirectionTrigger && predictedBreakDir != 1) return;
            double stop = ibLow;
            double target = ibHigh + TargetLvl * ibRange;
            int qty = CalcQuantity(stop, Close[0]);
            SetStopLoss(CalcStopLoss(StopAtrMult));
            SetProfitTarget(target);
            EnterLong(qty, "IB Breakout Long");
        }
        else if (Close[0] < ibLow)
        {
            if (RequireDirectionTrigger && predictedBreakDir != -1) return;
            double stop = ibHigh;
            double target = ibLow - TargetLvl * ibRange;
            int qty = CalcQuantity(stop, Close[0]);
            SetStopLoss(CalcStopLoss(StopAtrMult));
            SetProfitTarget(target);
            EnterShort(qty, "IB Breakout Short");
        }
    }

    public override string GetStrategyName() => "IB Breakout Bot (Play 1)";
}
```

### 4.4 IBFadeBot.cs (Play 3)

```csharp
public class IBFadeBot : IBStrategyBase
{
    private bool overshootAbove, overshootBelow;

    protected override void CheckForEntry()
    {
        // Detect overshoot
        if (High[0] > ibHigh + 0.25 * ibRange) overshootAbove = true;
        if (Low[0] < ibLow - 0.25 * ibRange) overshootBelow = true;

        // Fade: close back inside after overshoot
        if (overshootAbove && Close[0] < ibHigh)
        {
            double stop = ibHigh + 0.5 * ibRange;
            double target = ibMid;
            int qty = CalcQuantity(stop, ibHigh);
            SetStopLoss(CalcStopLoss(StopAtrMult));
            SetProfitTarget(target);
            EnterShort(qty, "IB Fade Short");
            overshootAbove = false;
        }
        else if (overshootBelow && Close[0] > ibLow)
        {
            double stop = ibLow - 0.5 * ibRange;
            double target = ibMid;
            int qty = CalcQuantity(stop, ibLow);
            SetStopLoss(CalcStopLoss(StopAtrMult));
            SetProfitTarget(target);
            EnterLong(qty, "IB Fade Long");
            overshootBelow = false;
        }
    }

    public override string GetStrategyName() => "IB Fade Bot (Play 3)";
}
```

---

## 5. TradingView Implementation (Pine Script v5)

### 5.1 File structure

```
scripts/indicators-pine/
├── IBStrategyLib.pine       # Shared library (IB window, direction trigger, calendar filter)
├── IBBreakoutStrategy.pine   # Play 1 strategy
├── IBFadeStrategy.pine       # Play 3 strategy
└── IBRangeIndicator.pine     # Visual indicator (IB high/low/mid lines)
```

### 5.2 IBStrategyLib.pine — shared library

```pine
//@version=5
library("IBStrategyLib", overlay=true)

// ── IB Window Builder ──
export build_ib_window(ib_start, ib_end) =>
    var float ib_high = na
    var float ib_low = na
    var float ib_open = na
    var float ib_close = na
    var int first_high_bar = na
    var int first_low_bar = na
    var bool ib_complete = false

    in_ib = time(timeframe.period, ib_start + ":" + ib_end)
    is_first = in_ib and not in_ib[1]

    if is_first
        ib_high := high
        ib_low := low
        ib_open := open
        first_high_bar := bar_index
        first_low_bar := bar_index
    else if in_ib
        ib_high := math.max(ib_high, high)
        ib_low := math.min(ib_low, low)
        if high == ib_high
            first_high_bar := bar_index
        if low == ib_low
            first_low_bar := bar_index

    ib_close := close
    ib_range = ib_high - ib_low
    ib_mid = (ib_high + ib_low) / 2
    ib_close_pos = ib_range > 0 ? (ib_close - ib_low) / ib_range : 0.5
    bias_firstreach = first_low_bar < first_high_bar ? 1 : first_high_bar < first_low_bar ? -1 : 0

    [ib_high, ib_low, ib_mid, ib_range, ib_close_pos, bias_firstreach, ib_complete]

// ── Direction Trigger (Rule 1) ──
export direction_trigger(bias_firstreach, ib_close_pos, top_pct, bot_pct) =>
    if bias_firstreach == 1 and ib_close_pos >= top_pct
        1
    else if bias_firstreach == -1 and ib_close_pos <= bot_pct
        -1
    else
        0

// ── Clock Size Multiplier (Rule 3) ──
export clock_size_mult(break_minutes, threshold, early_mult, late_mult) =>
    break_minutes < threshold ? early_mult : late_mult

// ── Calendar Filter ──
export calendar_filter(play, skip_mon_p2, skip_feb_p2, skip_may_p1, skip_oct_p3) =>
    dow = dayofweek(time, "America/New_York")
    month = month(time, "America/New_York")
    skip = false
    if play == 2 and skip_mon_p2 and dow == dayofweek.monday
        skip := true
    if play == 2 and skip_feb_p2 and month == 2
        skip := true
    if play == 1 and skip_may_p1 and month == 5
        skip := true
    if play == 3 and skip_oct_p3 and month == 10
        skip := true
    skip
```

### 5.3 IBBreakoutStrategy.pine (Play 1)

```pine
//@version=5
strategy("IB Breakout Strategy (Play 1)", overlay=true,
     initial_capital=50000, default_qty_type=strategy.percent_of_equity,
     default_qty_value=0.5)

import Vinay/IBStrategyLib/1 as IBLib

// Parameters
ib_start = input.session("0930-0930", "IB Start Time (HHMM)")
ib_duration = input.int(30, "IB Duration (minutes)", minval=5, maxval=120)  // Phase F: 30 is optimal
ib_end = ib_start + ib_duration  // auto-computed
target_lvl = input.float(0.25, "Target Level (x IB range)", step=0.25)
stop_r_mult = input.float(0.25, "Stop Distance (R-multiples)", step=0.05)  // Phase D: 0.25R
require_trigger = input.bool(true, "Require Direction Trigger")
top_pct = input.float(0.75, "Close Position Top %")
bot_pct = input.float(0.25, "Close Position Bottom %")
early_threshold = input.int(90, "Early Break Threshold (min)")
early_mult = input.float(0.5, "Early Break Size Mult")
late_mult = input.float(1.0, "Late Break Size Mult")
skip_may = input.bool(true, "Skip May")
skip_huge = input.bool(true, "Skip Huge IB (>0.9%)")
max_range_pct = input.float(0.90, "Max IB Range %")
min_range_pct = input.float(0.10, "Min IB Range %")

// Build IB
[ib_h, ib_l, ib_m, ib_r, ib_cp, bias_fr, ib_done] = IBLib.build_ib_window(ib_start, ib_start)
predicted_dir = IBLib.direction_trigger(bias_fr, ib_cp, top_pct, bot_pct)

// Entry
var int first_break_min = na
if ib_done and not barstate.islast
    if close > ib_h and strategy.position_size == 0
        if not require_trigger or predicted_dir == 1
            if not IBLib.calendar_filter(1, false, false, skip_may, false)
                first_break_min := bar_index - bar_index[1]  # approx
                size_mult = IBLib.clock_size_mult(first_break_min, early_threshold, early_mult, late_mult)
                qty = strategy.equity * 0.005 * size_mult / (ib_r * syminfo.pointvalue)
                strategy.entry("IB Long", strategy.long, qty=math.max(1, int(qty)))
                strategy.exit("Exit Long", "IB Long", stop=ib_l, limit=ib_h + target_lvl * ib_r)

    if close < ib_l and strategy.position_size == 0
        if not require_trigger or predicted_dir == -1
            if not IBLib.calendar_filter(1, false, false, skip_may, false)
                qty = strategy.equity * 0.005 * late_mult / (ib_r * syminfo.pointvalue)
                strategy.entry("IB Short", strategy.short, qty=math.max(1, int(qty)))
                strategy.exit("Exit Short", "IB Short", stop=ib_h, limit=ib_l - target_lvl * ib_r)

// ADR-020: flatten at 15:50 ET
if time(timeframe.period, "1550-1600", "America/New_York")
    strategy.close_all()
```

---

## 6. Validation Plan

### 6.1 Backtest validation (NinjaTrader Strategy Analyzer)

| Step | What | Expected |
|---|---|---|
| 1 | Run IBBreakoutBot on NQ1 5-min, 2021-2026 | E[R] > 0, PF > 1.3 |
| 2 | Run IBFadeBot on NQ1 5-min, 2021-2026 | E[R] > 0.20 at 0.25x target |
| 3 | Compare NT results to Python play_detail | Numbers should match within 5% |
| 4 | Run with calendar filters ON vs OFF | Filters should improve E[R] |
| 5 | Run with direction trigger ON vs OFF | Trigger should improve WR by 15-20pp |

### 6.2 Forward validation (live sim)

| Step | What | Duration |
|---|---|---|
| 1 | Deploy on NinjaTrader sim with MNQ | 20 sessions |
| 2 | Compare live signals to Python prediction | Should match 100% |
| 3 | Track fill slippage vs backtest entry | < 0.01% expected |
| 4 | Track actual E[R] vs backtest E[R] | Within 1 std dev |

### 6.3 TradingView validation

| Step | What | Expected |
|---|---|---|
| 1 | Publish IBBreakoutStrategy as indicator | Compiles, plots IB levels |
| 2 | Run Strategy Tester on NQ1 5-min, 2021-2026 | E[R] matches NT within 5% |
| 3 | Compare entry/exit times to Python | Should match bar-by-bar |

---

## 7. Open Questions

1. **Stop model:** The play_detail data uses target-before-stop bar-by-bar evaluation. NinjaTrader's `SetStopLoss` + `SetProfitTarget` uses the same bar-by-bar logic, but the OCO (one-cancels-other) may differ on same-bar ambiguity. Need to verify the same-bar tie-break (stop-first vs target-first) matches.

2. **Commission model:** The validated E[R] is pre-commission. NinjaTrader's Strategy Analyzer applies commission per contract. At $2.05/round-turn per Micro, this is ~0.002R per trade on NQ1 — small but should be included in the NT backtest.

3. **Slippage model:** The play_detail uses close-based entry (no slippage). Live MNQ fills may have 1-2 ticks slippage. Need to add 1-tick slippage to the NT backtest for realistic comparison.

4. **Contract sizing:** The risk-scaled Micro model (from `scratch_micro_vs_mini.py`) should be the default. `qty = (equity * risk_pct) / (stop_distance * point_value)` with minimum 1 Micro.

5. **Play 3 overshoot detection:** The fade requires a 0.25x overshoot then a close back inside. In live trading, the overshoot may happen on one bar and the close-back on the next. Need to handle the state transition correctly in NT (the `overshootAbove` flag persists across bars).

6. **Rule 3 clock inversion:** The finding that late breaks hold better on NQ1/ES1 is inverted from YM. The clock filter should be configurable per instrument — default to `early_mult=0.5` for NQ1/ES1 but `early_mult=1.0` for YM (following Edgeful's YM finding).

---

## 8. Implementation Phases

| Phase | Deliverable | Effort | Dependencies |
|---|---|---|---|
| **1** | `IBStrategyBase.cs` + `IBRange.cs` indicator | 1 day | Existing `RiskManagerBase.cs` |
| **2** | `IBBreakoutBot.cs` (Play 1) | 0.5 day | Phase 1 |
| **3** | `IBFadeBot.cs` (Play 3) | 0.5 day | Phase 1 |
| **4** | NT backtest validation (steps 1-5) | 0.5 day | Phases 2-3 |
| **5** | `IBStrategyLib.pine` + `IBBreakoutStrategy.pine` | 1 day | Phase 4 (validated logic) |
| **6** | `IBFadeStrategy.pine` | 0.5 day | Phase 5 |
| **7** | TV Strategy Tester validation | 0.5 day | Phases 5-6 |
| **8** | Live sim deployment (MNQ) | 20 sessions | Phases 4, 7 |

**Total: ~4.5 days implementation + 20 sessions live sim.**