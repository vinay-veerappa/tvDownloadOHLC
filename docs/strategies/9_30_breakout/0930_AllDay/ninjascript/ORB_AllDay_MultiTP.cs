#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public enum ORB_AllDay_EntryMode
    {
        [Display(Name = "Immediate")] Immediate,
        [Display(Name = "Pullback Only")] PullbackOnly,
        [Display(Name = "Pullback + Fallback")] PullbackFallback
    }

    public enum ORB_AllDay_ReentryMode
    {
        [Display(Name = "Immediate")] Immediate,
        [Display(Name = "Fresh Only")] FreshOnly,
        [Display(Name = "One Per Direction")] OnePerDirection
    }

    public enum ORB_AllDay_RunnerMode
    {
        [Display(Name = "Fixed TP")] FixedTP,
        [Display(Name = "Breakeven")] Breakeven,
        [Display(Name = "Trailing")] Trailing,
        [Display(Name = "Time Exit")] TimeExit,
        [Display(Name = "Dump Pouch")] DumpPouch
    }

    public class ORB_AllDay_MultiTP : Strategy
    {
        #region Variables
        private TimeZoneInfo estZone;
        private TimeZoneInfo chartZone;

        // Range Variables
        private double rHigh = double.MinValue;
        private double rLow = double.MaxValue;
        private bool rDefined = false;
        private bool rangeSynced = false;  // Flag to sync range with primary bar

        // State Tracking
        private int attemptsToday = 0;
        private int longAttempts = 0;
        private int shortAttempts = 0;
        private bool hasWonToday = false;
        private bool longPending = false;
        private bool shortPending = false;
        private int breakoutBar = -1;
        private double sigCandleExtreme = double.NaN;
        private bool longTakenToday = false;
        private bool shortTakenToday = false;
        private bool priceReturnedToRange = true;
        private bool enteredViaFallback = false;
        private DateTime lastResetDate = DateTime.MinValue;
        private double prevClosedProfit = 0;
        private int lastExitBar = -1;

        // Multi-TP State
        private bool tp1Hit = false;
        private bool tp2Hit = false;
        private double tradeEntryPrice = double.NaN;
        private double currentTrailStop = double.NaN;
        private bool isRunnerActive = false;
        private int entryQty = 0;
        private int tp1Qty = 0;
        private int remainingQty = 0;

        // Dump Pouch State
        private int dumpLevel = 0;              // 0=Initial, 1=TP1 hit, 2=50% target, 3=75% target
        private double initialSLPrice = double.NaN;
        private double currentDPStop = double.NaN;
        private double dpTP1Price = double.NaN;
        private double dpTargetPrice = double.NaN;
        private double dpLevel2Price = double.NaN;
        private double dpLevel3Price = double.NaN;

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"All-Day ORB Strategy with Multi-TP - Based on 3-year backtest optimization";
                Name = "ORB_AllDay_MultiTP";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 20;

                // Time Zone Configuration
                // All time inputs (OR Start, Trading End, etc.) are in EASTERN TIME.
                // Set ChartTimeZone to match your NinjaTrader chart's configured timezone
                // so the strategy can correctly convert bar timestamps to Eastern.
                // Common values: "Eastern Standard Time", "Central Standard Time", "Pacific Standard Time"
                ChartTimeZone = "Pacific Standard Time";

                // Core Settings
                ORStartTime = DateTime.Parse("09:30", System.Globalization.CultureInfo.InvariantCulture);
                OREndTime = DateTime.Parse("09:31", System.Globalization.CultureInfo.InvariantCulture);
                TradingEndTime = DateTime.Parse("15:00", System.Globalization.CultureInfo.InvariantCulture);
                HardExitTime = DateTime.Parse("15:50", System.Globalization.CultureInfo.InvariantCulture);

                // Entry Configuration
                EntryModel = ORB_AllDay_EntryMode.Immediate;
                MinDisplacementPct = 0.05;
                MaxPullbackDepthPct = 25.0;
                PBTimeoutBars = 5;
                FallbackProximityPct = 0.10;

                // Re-entry Rules
                ReentryModel = ORB_AllDay_ReentryMode.Immediate;
                MaxAttempts = 10;
                StopAfterWin = false;
                CooldownBars = 0;

                // Multi-TP Configuration (Optimized Settings)
                EnableMultiTP = true;
                NumTPLevels = 3;
                TP1Pct = 0.15;
                TP1PositionPct = 50;
                TP2Pct = 0.25;
                TP2PositionPct = 50;
                TP3Pct = 0.40;
                RunnerModeAfterTP1 = ORB_AllDay_RunnerMode.Breakeven;
                MoveToBreakevenAfterTP1 = true;
                TrailOffsetPct = 0.08;

                // Single TP Mode
                SingleTPPct = 0.25;

                // Risk Management
                UseMAEFilter = true;
                MAEThresholdPct = 0.05;  // Optimized: 0.10% is best
                InitialCapital = 3000;
                RiskPercent = 1.0;
                MaxContracts = 3;

                // Dump Pouch Settings
                DP_TargetMovePct = 1.00;
                DP_Level1RiskReducePct = 50;
                DP_Level2TriggerPct = 50;
                DP_Level3TriggerPct = 75;
                DP_Level3LockPct = 25;

                // Filters
                UseVVIXFilter = true;
                MaxVVIX = 108;
                MaxRangePct = 0.25;
                MinRangePct = 0.03;


                // Visuals
                ShowDashboard = true;
                ShowRangeBox = true;
                ShowTPSLLevels = true;

                // VVIX placeholder (user must input manually or use indicator)
                VVIX_Open = 100.0;
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsPeriodType.Second, 1); // Index 1: 1-Second for precise range capture
            }
            else if (State == State.DataLoaded)
            {
                try
                {
                    estZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                }
                catch
                {
                    estZone = TimeZoneInfo.Local;
                }

                try
                {
                    chartZone = TimeZoneInfo.FindSystemTimeZoneById(ChartTimeZone);
                }
                catch
                {
                    chartZone = TimeZoneInfo.Local;
                }
            }
        }

        protected override void OnBarUpdate()
        {
            // Safety Checks
            if (CurrentBars[0] < 1) return;
            if (BarsArray.Length > 1 && CurrentBars[1] < 1) return;

            // 1-Second Series: Capture Range
            if (BarsInProgress == 1)
            {
                DateTime estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);

                // Reset on new day
                if (estTime.Date != lastResetDate)
                {
                    ResetDailyState(estTime);
                }

                // Capture Range (9:30:01 - 9:31:00)
                TimeSpan timeOfDay = estTime.TimeOfDay;
                TimeSpan startTime = ORStartTime.TimeOfDay;
                TimeSpan endTime = OREndTime.TimeOfDay;

                if (timeOfDay > startTime && timeOfDay <= endTime)
                {
                    if (High[0] > rHigh) rHigh = High[0];
                    if (Low[0] < rLow) rLow = Low[0];
                }

                // Finalize Range
                if (!rDefined && timeOfDay > endTime && rHigh > double.MinValue && rLow < double.MaxValue)
                {
                    rDefined = true;
                }
            }

            // Primary Series: Trading Logic
            if (BarsInProgress == 0 && rDefined)
            {
                DateTime estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
                
                // Look-back Range Sync - ensure primary bar's High/Low is captured
                if (rDefined && !rangeSynced)
                {
                    for (int i = 0; i <= 5; i++)
                    {
                        if (CurrentBar - i < 0) continue;
                        
                        DateTime barTimeEST = TimeZoneInfo.ConvertTime(Time[i], chartZone, estZone);
                        // Match 9:30 or 9:31 bar
                        if (barTimeEST.Hour == 9 && (barTimeEST.Minute == 30 || barTimeEST.Minute == 31))
                        {
                            // Force Sync: Capture primary bar's High/Low into range
                            if (High[i] > rHigh) rHigh = High[i];
                            if (Low[i] < rLow) rLow = Low[i];
                            rangeSynced = true;
                            break;
                        }
                    }
                }
                
                ProcessTradingLogic(estTime);
            }
        }

        private void ResetDailyState(DateTime estTime)
        {
            rHigh = double.MinValue;
            rLow = double.MaxValue;
            rDefined = false;
            rangeSynced = false;
            attemptsToday = 0;
            longAttempts = 0;
            shortAttempts = 0;
            hasWonToday = false;
            longPending = false;
            shortPending = false;
            breakoutBar = -1;
            sigCandleExtreme = double.NaN;
            longTakenToday = false;
            shortTakenToday = false;
            priceReturnedToRange = true;
            enteredViaFallback = false;
            tp1Hit = false;
            tp2Hit = false;
            tradeEntryPrice = double.NaN;
            currentTrailStop = double.NaN;
            isRunnerActive = false;
            lastExitBar = -1;
            lastResetDate = estTime.Date;

            // Dump Pouch reset
            dumpLevel = 0;
            initialSLPrice = double.NaN;
            currentDPStop = double.NaN;
            dpTP1Price = double.NaN;
            dpTargetPrice = double.NaN;
            dpLevel2Price = double.NaN;
            dpLevel3Price = double.NaN;

            if (SystemPerformance.AllTrades.Count > 0)
                prevClosedProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
            else
                prevClosedProfit = 0;
        }

        private void ProcessTradingLogic(DateTime estTime)
        {
            double rSize = rHigh - rLow;
            double rPct = (rSize / Close[0]) * 100;

            // Time Checks
            bool isTradingTime = estTime.TimeOfDay >= OREndTime.TimeOfDay && estTime.TimeOfDay < TradingEndTime.TimeOfDay;
            bool isHardExit = estTime.TimeOfDay >= HardExitTime.TimeOfDay;

            bool isRangeFiltered = rPct > MaxRangePct || rPct < MinRangePct;
            bool isVVIXFiltered = UseVVIXFilter && VVIX_Open > MaxVVIX;
            bool isFiltered = isRangeFiltered || isVVIXFiltered;

            // Track price returning to range
            if (Position.MarketPosition == MarketPosition.Flat && Close[0] >= rLow && Close[0] <= rHigh)
                priceReturnedToRange = true;

            // Win tracking
            if (StopAfterWin && !hasWonToday)
            {
                double currentProfit = SystemPerformance.AllTrades.Count > 0 ?
                    SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit : 0;
                if (currentProfit > prevClosedProfit + 10)
                    hasWonToday = true;
            }

            // Cooldown check
            bool cooldownComplete = lastExitBar < 0 || (CurrentBar - lastExitBar) >= CooldownBars;

            // Re-entry eligibility
            bool reentryEligible = ReentryModel == ORB_AllDay_ReentryMode.Immediate ||
                                   (ReentryModel == ORB_AllDay_ReentryMode.FreshOnly && priceReturnedToRange) ||
                                   ReentryModel == ORB_AllDay_ReentryMode.OnePerDirection;

            bool canTakeLong = ReentryModel != ORB_AllDay_ReentryMode.OnePerDirection || !longTakenToday;
            bool canTakeShort = ReentryModel != ORB_AllDay_ReentryMode.OnePerDirection || !shortTakenToday;

            bool canTrade = isTradingTime && !isHardExit && !isFiltered &&
                            attemptsToday < MaxAttempts && cooldownComplete &&
                            reentryEligible && !(StopAfterWin && hasWonToday) &&
                            Position.MarketPosition == MarketPosition.Flat;

            // Calculate Position Size
            int qty = CalculateQty(rSize);

            // Entry Logic
            if (canTrade)
            {
                ProcessEntryLogic(estTime, qty, canTakeLong, canTakeShort, rSize);
            }

            // =============================================
            // HARD EXIT — checked FIRST, takes priority
            // =============================================
            bool hardExitTriggered = false;
            if (Position.MarketPosition != MarketPosition.Flat && isHardExit)
            {
                hardExitTriggered = true;

                if (Position.MarketPosition == MarketPosition.Long)
                {
                    ExitLong(Position.Quantity, "Time Exit", "");
                }
                else
                {
                    ExitShort(Position.Quantity, "Time Exit", "");
                }
            }

            // Only run normal exit management if NOT in hard exit window
            if (!hardExitTriggered && Position.MarketPosition != MarketPosition.Flat)
            {
                ProcessExitLogic(estTime, rSize);
            }

            // Visuals
            if (ShowDashboard)
                DrawDashboard(estTime, rSize, rPct, isFiltered, isTradingTime);

            if (ShowRangeBox)
                DrawRangeBox(estTime, rSize, rPct, isRangeFiltered);
        }

        private void ProcessEntryLogic(DateTime estTime, int qty, bool canTakeLong, bool canTakeShort, double rSize)
        {
            // Displacement levels
            double displacementHigh = rHigh * (1 + MinDisplacementPct / 100);
            double displacementLow = rLow * (1 - MinDisplacementPct / 100);

            // Pullback levels
            double maxPBLong = rHigh - (rSize * MaxPullbackDepthPct / 100);
            double maxPBShort = rLow + (rSize * MaxPullbackDepthPct / 100);

            // Fallback zones
            double fallbackLongZone = rHigh * (1 + FallbackProximityPct / 100);
            double fallbackShortZone = rLow * (1 - FallbackProximityPct / 100);

            // Breakout detection
            bool breakoutLong = CrossAbove(Close, rHigh, 1);
            bool breakoutShort = CrossBelow(Close, rLow, 1);
            bool hasDisplacementLong = Close[0] >= displacementHigh;
            bool hasDisplacementShort = Close[0] <= displacementLow;

            // IMMEDIATE MODE
            if (EntryModel == ORB_AllDay_EntryMode.Immediate)
            {
                if (breakoutLong && canTakeLong)
                {
                    EnterLong(0, qty, "Long");
                    SetupEntry(true, qty);
                }
                else if (breakoutShort && canTakeShort)
                {
                    EnterShort(0, qty, "Short");
                    SetupEntry(false, qty);
                }
            }
            // PULLBACK MODES
            else
            {
                // Arm pending entries
                if (!longPending && !shortPending)
                {
                    if (breakoutLong && hasDisplacementLong && canTakeLong)
                    {
                        longPending = true;
                        breakoutBar = CurrentBar;
                        sigCandleExtreme = Low[0];
                    }
                    else if (breakoutShort && hasDisplacementShort && canTakeShort)
                    {
                        shortPending = true;
                        breakoutBar = CurrentBar;
                        sigCandleExtreme = High[0];
                    }
                }

                // Manage pending long
                if (longPending && CurrentBar > breakoutBar)
                {
                    int barsSinceBreakout = CurrentBar - breakoutBar;
                    bool timeoutReached = barsSinceBreakout >= PBTimeoutBars;
                    bool useFallback = EntryModel == ORB_AllDay_EntryMode.PullbackFallback;

                    if (Close[0] < maxPBLong)
                    {
                        longPending = false;
                        breakoutBar = -1;
                    }
                    else if (Low[0] <= rHigh && Close[0] >= maxPBLong)
                    {
                        EnterLong(0, qty, "PB Long");
                        SetupEntry(true, qty);
                        longPending = false;
                        breakoutBar = -1;
                        enteredViaFallback = false;
                    }
                    else if (useFallback && timeoutReached && Close[0] <= fallbackLongZone && Close[0] > rHigh)
                    {
                        EnterLong(0, qty, "FB Long");
                        SetupEntry(true, qty);
                        longPending = false;
                        breakoutBar = -1;
                        enteredViaFallback = true;
                    }
                    else if (Close[0] < rLow)
                    {
                        longPending = false;
                        breakoutBar = -1;
                    }
                }

                // Manage pending short
                if (shortPending && CurrentBar > breakoutBar)
                {
                    int barsSinceBreakout = CurrentBar - breakoutBar;
                    bool timeoutReached = barsSinceBreakout >= PBTimeoutBars;
                    bool useFallback = EntryModel == ORB_AllDay_EntryMode.PullbackFallback;

                    if (Close[0] > maxPBShort)
                    {
                        shortPending = false;
                        breakoutBar = -1;
                    }
                    else if (High[0] >= rLow && Close[0] <= maxPBShort)
                    {
                        EnterShort(0, qty, "PB Short");
                        SetupEntry(false, qty);
                        shortPending = false;
                        breakoutBar = -1;
                        enteredViaFallback = false;
                    }
                    else if (useFallback && timeoutReached && Close[0] >= fallbackShortZone && Close[0] < rLow)
                    {
                        EnterShort(0, qty, "FB Short");
                        SetupEntry(false, qty);
                        shortPending = false;
                        breakoutBar = -1;
                        enteredViaFallback = true;
                    }
                    else if (Close[0] > rHigh)
                    {
                        shortPending = false;
                        breakoutBar = -1;
                    }
                }
            }
        }

        private void SetupEntry(bool isLong, int qty)
        {
            attemptsToday++;
            if (isLong)
            {
                longAttempts++;
                longTakenToday = true;
            }
            else
            {
                shortAttempts++;
                shortTakenToday = true;
            }
            priceReturnedToRange = false;
            tradeEntryPrice = Close[0];
            tp1Hit = false;
            tp2Hit = false;
            isRunnerActive = false;
            currentTrailStop = double.NaN;
            entryQty = qty;
            tp1Qty = (int)Math.Max(1, Math.Floor(qty * TP1PositionPct / 100.0));
            remainingQty = qty - tp1Qty;

            // Dump Pouch initialization
            dumpLevel = 0;
            initialSLPrice = isLong ? rLow : rHigh;
            currentDPStop = initialSLPrice;
            dpTP1Price = isLong ? Close[0] * (1 + TP1Pct / 100) : Close[0] * (1 - TP1Pct / 100);
            dpTargetPrice = isLong ? Close[0] * (1 + DP_TargetMovePct / 100) : Close[0] * (1 - DP_TargetMovePct / 100);

            double moveToTarget = Math.Abs(dpTargetPrice - Close[0]);
            dpLevel2Price = isLong ? Close[0] + moveToTarget * (DP_Level2TriggerPct / 100)
                                   : Close[0] - moveToTarget * (DP_Level2TriggerPct / 100);
            dpLevel3Price = isLong ? Close[0] + moveToTarget * (DP_Level3TriggerPct / 100)
                                   : Close[0] - moveToTarget * (DP_Level3TriggerPct / 100);
        }

        private void ProcessExitLogic(DateTime estTime, double rSize)
        {
            longPending = false;
            shortPending = false;

            double entry = Position.AveragePrice;
            bool isLong = Position.MarketPosition == MarketPosition.Long;

            // Base SL at range boundary
            double baseSL = isLong ? rLow : rHigh;

            if (EnableMultiTP && NumTPLevels >= 2)
            {
                ProcessMultiTPExits(entry, isLong, baseSL);
            }
            else
            {
                ProcessSingleTPExits(entry, isLong, baseSL);
            }

            // MAE Filter
            if (UseMAEFilter)
            {
                double heatDist = entry * (MAEThresholdPct / 100);
                if (isLong && Low[0] < entry - heatDist)
                    ExitLong("MAE Exit");
                else if (!isLong && High[0] > entry + heatDist)
                    ExitShort("MAE Exit");
            }

            // Draw levels
            if (ShowTPSLLevels)
            {
                double tp1Price = isLong ? entry * (1 + TP1Pct / 100) : entry * (1 - TP1Pct / 100);
                double tp2Price = isLong ? entry * (1 + TP2Pct / 100) : entry * (1 - TP2Pct / 100);

                double displaySL;
                if (RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.DumpPouch && tp1Hit)
                    displaySL = currentDPStop;
                else if (tp1Hit && MoveToBreakevenAfterTP1)
                    displaySL = entry;
                else
                    displaySL = baseSL;

                Draw.Line(this, "TP1_Line", false, 1, tp1Price, 0, tp1Price, Brushes.LimeGreen, DashStyleHelper.Solid, 2);
                Draw.Line(this, "TP2_Line", false, 1, tp2Price, 0, tp2Price, Brushes.Lime, DashStyleHelper.Dash, 1);
                Draw.Line(this, "SL_Line", false, 1, displaySL, 0, displaySL, Brushes.Red, DashStyleHelper.Solid, 2);

                // Draw Dump Pouch target levels when active
                if (RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.DumpPouch && !double.IsNaN(dpLevel2Price))
                {
                    Draw.Line(this, "DP_L2", false, 1, dpLevel2Price, 0, dpLevel2Price, Brushes.Gold, DashStyleHelper.Dash, 1);
                    Draw.Line(this, "DP_L3", false, 1, dpLevel3Price, 0, dpLevel3Price, Brushes.Orange, DashStyleHelper.Dash, 1);
                    Draw.Line(this, "DP_Target", false, 1, dpTargetPrice, 0, dpTargetPrice, Brushes.Cyan, DashStyleHelper.Dot, 1);
                }
            }
        }

        private void ProcessMultiTPExits(double entry, bool isLong, double baseSL)
        {
            double tp1Price = isLong ? entry * (1 + TP1Pct / 100) : entry * (1 - TP1Pct / 100);
            double tp2Price = isLong ? entry * (1 + TP2Pct / 100) : entry * (1 - TP2Pct / 100);
            double tp3Price = isLong ? entry * (1 + TP3Pct / 100) : entry * (1 - TP3Pct / 100);

            double currentSL = baseSL;

            // Check if TP1 was hit
            if (!tp1Hit)
            {
                if ((isLong && High[0] >= tp1Price) || (!isLong && Low[0] <= tp1Price))
                {
                    tp1Hit = true;
                    isRunnerActive = true;

                    if (RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.Trailing)
                    {
                        currentTrailStop = isLong ? High[0] - (entry * TrailOffsetPct / 100) :
                                                    Low[0] + (entry * TrailOffsetPct / 100);
                    }
                    else if (RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.DumpPouch)
                    {
                        // Level 1: Reduce risk by DP_Level1RiskReducePct
                        dumpLevel = 1;
                        double riskAmount = Math.Abs(entry - initialSLPrice);
                        double riskReduction = riskAmount * (DP_Level1RiskReducePct / 100.0);
                        currentDPStop = isLong ? initialSLPrice + riskReduction
                                               : initialSLPrice - riskReduction;
                    }
                }
            }

            // ==========================================
            // DUMP POUCH MODE — progressive trail levels
            // ==========================================
            if (RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.DumpPouch)
            {
                if (tp1Hit)
                {
                    // Level 2: At DP_Level2TriggerPct% of target move → SL to breakeven
                    if (dumpLevel == 1)
                    {
                        if ((isLong && High[0] >= dpLevel2Price) || (!isLong && Low[0] <= dpLevel2Price))
                        {
                            dumpLevel = 2;
                            currentDPStop = entry;  // Breakeven
                        }
                    }

                    // Level 3: At DP_Level3TriggerPct% of target move → lock DP_Level3LockPct% of move
                    if (dumpLevel == 2)
                    {
                        if ((isLong && High[0] >= dpLevel3Price) || (!isLong && Low[0] <= dpLevel3Price))
                        {
                            dumpLevel = 3;
                            double moveAmount = Math.Abs(dpLevel3Price - entry);
                            double lockAmount = moveAmount * (DP_Level3LockPct / 100.0);
                            currentDPStop = isLong ? entry + lockAmount
                                                   : entry - lockAmount;
                        }
                    }

                    currentSL = currentDPStop;
                }
                else
                {
                    // Before TP1: use initial SL
                    currentSL = initialSLPrice;
                }

                // Set exits for Dump Pouch mode
                int qty = Position.Quantity;
                int tp1ExitQty = Math.Min(tp1Qty, qty);
                int runnerQty = qty - tp1ExitQty;

                if (isLong)
                {
                    // Before TP1: partial exit at TP1 + initial SL on whole position
                    if (!tp1Hit && tp1ExitQty > 0)
                        ExitLongLimit(0, true, tp1ExitQty, tp1Price, "TP1", "");

                    // SL on full position (covers pre-TP1 and post-TP1 runner)
                    ExitLongStopMarket(0, true, qty, currentSL, dumpLevel <= 0 ? "SL" : "DP" + dumpLevel, "");
                }
                else
                {
                    if (!tp1Hit && tp1ExitQty > 0)
                        ExitShortLimit(0, true, tp1ExitQty, tp1Price, "TP1", "");

                    ExitShortStopMarket(0, true, qty, currentSL, dumpLevel <= 0 ? "SL" : "DP" + dumpLevel, "");
                }

                return;  // Skip the standard exit logic below
            }

            // ==========================================
            // NON-DUMP-POUCH MODES (original logic)
            // ==========================================

            // Move SL to breakeven after TP1
            if (tp1Hit && MoveToBreakevenAfterTP1)
                currentSL = entry;

            // Update trailing stop
            if (tp1Hit && RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.Trailing)
            {
                if (isLong)
                {
                    double newTrail = High[0] - (entry * TrailOffsetPct / 100);
                    if (double.IsNaN(currentTrailStop) || newTrail > currentTrailStop)
                        currentTrailStop = newTrail;
                    currentSL = currentTrailStop;
                }
                else
                {
                    double newTrail = Low[0] + (entry * TrailOffsetPct / 100);
                    if (double.IsNaN(currentTrailStop) || newTrail < currentTrailStop)
                        currentTrailStop = newTrail;
                    currentSL = currentTrailStop;
                }
            }

            // Set exits
            int qtyStd = Position.Quantity;
            int tp1ExitQtyStd = Math.Min(tp1Qty, qtyStd);
            int tp2ExitQtyStd = qtyStd - tp1ExitQtyStd;

            if (isLong)
            {
                if (!tp1Hit && tp1ExitQtyStd > 0)
                    ExitLongLimit(0, true, tp1ExitQtyStd, tp1Price, "TP1", "");
                if (tp2ExitQtyStd > 0)
                    ExitLongLimit(0, true, tp2ExitQtyStd, tp2Price, "TP2", "");
                ExitLongStopMarket(0, true, qtyStd, currentSL, "SL", "");
            }
            else
            {
                if (!tp1Hit && tp1ExitQtyStd > 0)
                    ExitShortLimit(0, true, tp1ExitQtyStd, tp1Price, "TP1", "");
                if (tp2ExitQtyStd > 0)
                    ExitShortLimit(0, true, tp2ExitQtyStd, tp2Price, "TP2", "");
                ExitShortStopMarket(0, true, qtyStd, currentSL, "SL", "");
            }
        }

        private void ProcessSingleTPExits(double entry, bool isLong, double baseSL)
        {
            double tpPrice = isLong ? entry * (1 + SingleTPPct / 100) : entry * (1 - SingleTPPct / 100);

            if (isLong)
            {
                ExitLongLimit(0, true, Position.Quantity, tpPrice, "Target", "");
                ExitLongStopMarket(0, true, Position.Quantity, baseSL, "Stop", "");
            }
            else
            {
                ExitShortLimit(0, true, Position.Quantity, tpPrice, "Target", "");
                ExitShortStopMarket(0, true, Position.Quantity, baseSL, "Stop", "");
            }
        }

        private int CalculateQty(double rSize)
        {
            if (RiskPercent <= 0 || rSize <= 0)
                return 1;

            double riskAmt = InitialCapital * (RiskPercent / 100.0);
            int qty = (int)Math.Max(1, Math.Floor(riskAmt / (rSize * Instrument.MasterInstrument.PointValue)));
            return Math.Min(qty, MaxContracts);
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            // Track exits for cooldown
            if (execution.Order.OrderState == OrderState.Filled &&
                (execution.Order.Name.Contains("TP") || execution.Order.Name.Contains("SL") ||
                 execution.Order.Name.Contains("MAE") || execution.Order.Name.Contains("Time") ||
                 execution.Order.Name.Contains("Target") || execution.Order.Name.Contains("Stop")))
            {
                lastExitBar = CurrentBar;
            }
        }

        private void DrawDashboard(DateTime estTime, double rSize, double rPct, bool isFiltered, bool isTradingTime)
        {
            string tpMode = EnableMultiTP ?
                $"{NumTPLevels} TPs: {TP1Pct}%/{TP2Pct}%" :
                $"Single: {SingleTPPct}%";

            string status = Position.MarketPosition != MarketPosition.Flat ? "IN TRADE" :
                           hasWonToday && StopAfterWin ? "WON - DONE" :
                           isFiltered ? "FILTERED" :
                           attemptsToday >= MaxAttempts ? "MAX ATTEMPTS" :
                           isTradingTime ? "READY" : "WAITING";

            string tp1Status = tp1Hit ? "YES ✓" : "NO";
            string runnerStatus = isRunnerActive ? RunnerModeAfterTP1.ToString() : "Inactive";
            string dpStatus = RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.DumpPouch ?
                (dumpLevel == 0 ? "INITIAL" : dumpLevel == 1 ? "LVL1(Risk-)" : dumpLevel == 2 ? "LVL2(BE)" : "LVL3(LOCK)") : "N/A";

            string hud = string.Format(
                "ORB ALL-DAY V2\n" +
                "─────────────\n" +
                "Range: {0:F2} pts ({1:F3}%)\n" +
                "VVIX: {2:F1}\n" +
                "Attempts: {3}/{4} (L:{5} S:{6})\n" +
                "TP Mode: {7}\n" +
                "TP1 Hit: {8}\n" +
                "Runner: {9}\n" +
                "Dump Pouch: {10}\n" +
                "MAE: {11}%\n" +
                "MaxQty: {12}\n" +
                "Status: {13}\n" +
                "Time: {14:HH:mm}",
                rSize, rPct, VVIX_Open,
                attemptsToday, MaxAttempts, longAttempts, shortAttempts,
                tpMode, tp1Status, runnerStatus, dpStatus,
                MAEThresholdPct, MaxContracts, status, estTime);

            Draw.TextFixed(this, "HUD", hud, TextPosition.TopRight, Brushes.White,
                new SimpleFont("Consolas", 10), Brushes.Black, Brushes.DimGray, 90);
        }

        private void DrawRangeBox(DateTime estTime, double rSize, double rPct, bool isRangeFiltered)
        {
            if (!rDefined) return;
            if (chartZone == null || estZone == null) return;

            DateTime rangeDate = estTime.Date;
            
            // Calculate start time: OR end time in EST, converted to chart time
            DateTime estOpen = rangeDate.Add(OREndTime.TimeOfDay);
            // End: 16:00:00 EST (End of Session)
            DateTime estEnd = rangeDate.Add(new TimeSpan(16, 0, 0));

            DateTime chartStart = TimeZoneInfo.ConvertTime(estOpen, estZone, chartZone);
            DateTime chartEnd = TimeZoneInfo.ConvertTime(estEnd, estZone, chartZone);

            // Extend to current time if before end, otherwise draw full
            DateTime displayEnd = (Time[0] < chartEnd) ? Time[0] : chartEnd;
            
            Brush fillBrush = isRangeFiltered ? Brushes.Red : Brushes.DeepSkyBlue;
            string suffix = rangeDate.ToString("yyyyMMdd");

            // Main Lines using DateTime coordinates
            Draw.Line(this, "High" + suffix, false, chartStart, rHigh, displayEnd, rHigh, Brushes.DeepSkyBlue, DashStyleHelper.Solid, 2);
            Draw.Line(this, "Low" + suffix, false, chartStart, rLow, displayEnd, rLow, Brushes.OrangeRed, DashStyleHelper.Solid, 2);

            // Mid line
            double mid = (rHigh + rLow) / 2;
            Draw.Line(this, "Mid" + suffix, false, chartStart, mid, displayEnd, mid, Brushes.Gold, DashStyleHelper.Dash, 1);

            // Box using DateTime coordinates
            Draw.Rectangle(this, "RangeBox" + suffix, false, chartStart, rHigh, displayEnd, rLow, Brushes.Transparent, fillBrush, 20);
        }

        #region Properties

        [NinjaScriptProperty]
        [Display(Name = "Chart Time Zone (match your chart)", Order = 0, GroupName = "1. Time",
            Description = "Must match your NinjaTrader chart timezone. All time inputs below are in Eastern Time.")]
        public string ChartTimeZone { get; set; }

        [NinjaScriptProperty]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
        [Display(Name = "OR Start Time (ET)", Order = 1, GroupName = "1. Time")]
        public DateTime ORStartTime { get; set; }

        [NinjaScriptProperty]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
        [Display(Name = "OR End Time (ET)", Order = 2, GroupName = "1. Time")]
        public DateTime OREndTime { get; set; }

        [NinjaScriptProperty]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
        [Display(Name = "Trading End Time (ET)", Order = 3, GroupName = "1. Time")]
        public DateTime TradingEndTime { get; set; }

        [NinjaScriptProperty]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
        [Display(Name = "Hard Exit Time (ET)", Order = 4, GroupName = "1. Time")]
        public DateTime HardExitTime { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Entry Mode", Order = 1, GroupName = "2. Entry")]
        public ORB_AllDay_EntryMode EntryModel { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Displacement %", Order = 2, GroupName = "2. Entry")]
        public double MinDisplacementPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Pullback Depth %", Order = 3, GroupName = "2. Entry")]
        public double MaxPullbackDepthPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Pullback Timeout Bars", Order = 4, GroupName = "2. Entry")]
        public int PBTimeoutBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Fallback Proximity %", Order = 5, GroupName = "2. Entry")]
        public double FallbackProximityPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Re-entry Mode", Order = 1, GroupName = "3. Re-entry")]
        public ORB_AllDay_ReentryMode ReentryModel { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Attempts", Order = 2, GroupName = "3. Re-entry")]
        public int MaxAttempts { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop After Win", Order = 3, GroupName = "3. Re-entry")]
        public bool StopAfterWin { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Cooldown Bars", Order = 4, GroupName = "3. Re-entry")]
        public int CooldownBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable Multi-TP", Order = 1, GroupName = "4. Multi-TP")]
        public bool EnableMultiTP { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Number of TP Levels", Order = 2, GroupName = "4. Multi-TP")]
        public int NumTPLevels { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "TP1 % (Quick Win)", Order = 3, GroupName = "4. Multi-TP")]
        public double TP1Pct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "TP1 Position %", Order = 4, GroupName = "4. Multi-TP")]
        public int TP1PositionPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "TP2 % (Medium)", Order = 5, GroupName = "4. Multi-TP")]
        public double TP2Pct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "TP2 Position %", Order = 6, GroupName = "4. Multi-TP")]
        public int TP2PositionPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "TP3 % (Runner)", Order = 7, GroupName = "4. Multi-TP")]
        public double TP3Pct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Runner Mode After TP1", Order = 8, GroupName = "4. Multi-TP")]
        public ORB_AllDay_RunnerMode RunnerModeAfterTP1 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Move to Breakeven After TP1", Order = 9, GroupName = "4. Multi-TP")]
        public bool MoveToBreakevenAfterTP1 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trail Offset %", Order = 10, GroupName = "4. Multi-TP")]
        public double TrailOffsetPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Single TP %", Order = 1, GroupName = "5. Risk")]
        public double SingleTPPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use MAE Filter", Order = 2, GroupName = "5. Risk")]
        public bool UseMAEFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "MAE Threshold %", Order = 3, GroupName = "5. Risk")]
        public double MAEThresholdPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Initial Capital", Order = 4, GroupName = "5. Risk")]
        public double InitialCapital { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Risk Percent", Order = 5, GroupName = "5. Risk")]
        public double RiskPercent { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Contracts", Order = 6, GroupName = "5. Risk")]
        public int MaxContracts { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "DP Target Move %", Order = 1, GroupName = "5b. Dump Pouch")]
        public double DP_TargetMovePct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "DP Level 1: Risk Reduce %", Order = 2, GroupName = "5b. Dump Pouch")]
        public double DP_Level1RiskReducePct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "DP Level 2 Trigger: % of Target", Order = 3, GroupName = "5b. Dump Pouch")]
        public double DP_Level2TriggerPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "DP Level 3 Trigger: % of Target", Order = 4, GroupName = "5b. Dump Pouch")]
        public double DP_Level3TriggerPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "DP Level 3: Lock % of Move", Order = 5, GroupName = "5b. Dump Pouch")]
        public double DP_Level3LockPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use VVIX Filter", Order = 1, GroupName = "6. Filters")]
        public bool UseVVIXFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max VVIX", Order = 2, GroupName = "6. Filters")]
        public double MaxVVIX { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "VVIX Open (Manual)", Order = 3, GroupName = "6. Filters")]
        public double VVIX_Open { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Range %", Order = 4, GroupName = "6. Filters")]
        public double MaxRangePct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Range %", Order = 5, GroupName = "6. Filters")]
        public double MinRangePct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Dashboard", Order = 1, GroupName = "8. Visuals")]
        public bool ShowDashboard { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Range Box", Order = 2, GroupName = "8. Visuals")]
        public bool ShowRangeBox { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show TP/SL Levels", Order = 3, GroupName = "8. Visuals")]
        public bool ShowTPSLLevels { get; set; }

        #endregion
    }
}


