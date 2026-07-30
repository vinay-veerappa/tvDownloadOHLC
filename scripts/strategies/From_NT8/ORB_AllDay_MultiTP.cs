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
        private bool rangeSynced = false;

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
        private int dumpLevel = 0;
        private double initialSLPrice = double.NaN;
        private double currentDPStop = double.NaN;
        private double dpTP1Price = double.NaN;
        private double dpTargetPrice = double.NaN;
        private double dpLevel2Price = double.NaN;
        private double dpLevel3Price = double.NaN;

        // Net Displacement tracking (for debug/dashboard)
        private double lastNetDispRatio = double.NaN;
        private bool lastNetDispPassed = false;
        private int netDispRejectCount = 0;

        // News Blackout State
        private List<TimeSpan> newsBlackoutTimes = new List<TimeSpan>();
        private bool newsFileLoaded = false;
        private string newsFileDate = "";

        // === DIAG PATCH === parity harness instrumentation
        // Tracks position transitions to detect entry/exit signals WITHOUT calling
        // EnterLong/Short in diagnostics (those submit orders). Reset in ResetDailyState.
        private MarketPosition _prevPosition = MarketPosition.Flat;

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"All-Day ORB Strategy with Multi-TP + Net Displacement Filter";
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

                ChartTimeZone = "Pacific Standard Time";

                // === DIAG PATCH === default ON for SA backtests; disable for live via the property grid.
                VerboseDiag = true;

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

                // Net Displacement Filter (NEW)
                EnableNetDisplacement = true;
                MinBodyRatio = 0.05;
                NetDispApplyToImmediate = true;
                NetDispApplyToPullback = true;

                // Re-entry Rules
                ReentryModel = ORB_AllDay_ReentryMode.Immediate;
                MaxAttempts = 10;
                StopAfterWin = false;
                CooldownBars = 0;

                // Multi-TP Configuration
                EnableMultiTP = true;
                NumTPLevels = 3;
                TP1Pct = 0.15;
                TP1PositionPct = 50;
                TP2Pct = 0.25;
                TP2PositionPct = 50;
                TP3Pct = 0.40;
                RunnerModeAfterTP1 = ORB_AllDay_RunnerMode.DumpPouch;
                MoveToBreakevenAfterTP1 = false;
                TrailOffsetPct = 0.08;

                // Single TP Mode
                SingleTPPct = 0.25;

                // Risk Management
                UseMAEFilter = true;
                MAEThresholdPct = 0.05;
                InitialCapital = 3000;
                RiskPercent = 1.0;
                MaxContracts = 3;

                // News Blackout
                EnableNewsBlackout = true;
                AutoLoadNewsCSV = true;
                NewsCSVPath = System.IO.Path.Combine(
                    NinjaTrader.Core.Globals.UserDataDir, "bin", "Custom", "news_blackout.csv");
                NewsTime1 = DateTime.Parse("09:45", System.Globalization.CultureInfo.InvariantCulture);
                NewsTime1_Enabled = true;
                NewsTime2 = DateTime.Parse("10:00", System.Globalization.CultureInfo.InvariantCulture);
                NewsTime2_Enabled = true;
                NewsTime3 = DateTime.Parse("10:30", System.Globalization.CultureInfo.InvariantCulture);
                NewsTime3_Enabled = false;
                NewsTime4 = DateTime.Parse("14:00", System.Globalization.CultureInfo.InvariantCulture);
                NewsTime4_Enabled = false;
                NewsPreMinutes = 1;
                NewsPostMinutes = 2;

                // Stop Loss Mode
                UsePercentSL = false;
                PercentSLPct = 0.05;

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

                VVIX_Open = 100.0;
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsPeriodType.Second, 1);
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
            if (CurrentBars[0] < 1) return;
            if (BarsArray.Length > 1 && CurrentBars[1] < 1) return;

            // 1-Second Series: Capture Range
            if (BarsInProgress == 1)
            {
                DateTime estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);

                if (estTime.Date != lastResetDate)
                {
                    ResetDailyState(estTime);
                }

                TimeSpan timeOfDay = estTime.TimeOfDay;
                TimeSpan startTime = ORStartTime.TimeOfDay;
                TimeSpan endTime = OREndTime.TimeOfDay;

                if (timeOfDay > startTime && timeOfDay <= endTime)
                {
                    if (High[0] > rHigh) rHigh = High[0];
                    if (Low[0] < rLow) rLow = Low[0];
                }

                if (!rDefined && timeOfDay > endTime && rHigh > double.MinValue && rLow < double.MaxValue)
                {
                    rDefined = true;
                }
            }

            // Primary Series: Trading Logic
            if (BarsInProgress == 0 && rDefined)
            {
                DateTime estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);

                // === DIAG PATCH START === parity-harness gate diagnostics
                // Emits per-bar gate decisions to the SA log file
                // (Documents/NinjaTrader 8/log/log.YYYYMMDD.00000.txt) so the
                // Python<->NT8 parity harness can localize the discrepancy root cause.
                //
                // Verified fixes applied (per scratch/parity_loop_result.json reviews):
                //   - Log(..., LogLevel.Information) not Print() (Print -> SA UI only).
                //   - Time[0] (bar historical time), NOT DateTime.Now (wall-clock).
                //   - NO EnterLong/Short calls here -- detects signals via position
                //     transition (Flat->Long/Short = entry, Long/Short->Flat = exit).
                //   - Cadence: out-of-window every 100th bar, in-window every 10th,
                //     decision bar (position changed) every bar.
                //   - Gatekeeper bypass for SA accounts (Sim101/Playback*/backtest).
                if (VerboseDiag)
                {
                    try
                    {
                        int barHour = estTime.Hour;
                        int barMinute = estTime.Minute;
                        bool inWindow = (barHour == 9 && barMinute >= 30) ||
                                        (barHour > 9 && barHour < 16);

                        MarketPosition curPos = Position.MarketPosition;
                        bool signalFired = (curPos != _prevPosition);

                        bool shouldLog = inWindow ? (CurrentBar % 10 == 0)
                                                  : (CurrentBar % 100 == 0);
                        if (signalFired) shouldLog = true;

                        // gatekeeper bypass for SA backtest accounts (verified Bug 2 fix)
                        bool isSaAccount = Account.Name.IndexOf("Sim", StringComparison.OrdinalIgnoreCase) >= 0
                                        || Account.Name.IndexOf("Playback", StringComparison.OrdinalIgnoreCase) >= 0
                                        || Account.Name.IndexOf("backtest", StringComparison.OrdinalIgnoreCase) >= 0;
                        string gkStatus = isSaAccount ? "BYPASS" : "OK";

                        if (shouldLog)
                        {
                            Log(string.Format(
                                "[DIAG] Bar={0} ET={1:HH:mm} Close={2} | Win={3} | " +
                                "ORH={4} ORL={5} RngDef={6} | Pos={7} PrevPos={8} Sig={9} | " +
                                "GT_H={10} LT_L={11} | GK={9}",
                                CurrentBar, estTime, Close[0],
                                inWindow, rHigh, rLow, rDefined,
                                curPos, _prevPosition, signalFired,
                                (Close[0] > rHigh), (Close[0] < rLow),
                                gkStatus),
                                LogLevel.Information);
                        }

                        // Track for next bar's transition detection
                        _prevPosition = curPos;
                    }
                    catch (Exception ex)
                    {
                        // Never let diagnostics crash the strategy.
                        Log("[DIAG_ERR] " + ex.Message, LogLevel.Error);
                    }
                }
                // === DIAG PATCH END ===

                if (rDefined && !rangeSynced)
                {
                    for (int i = 0; i <= 5; i++)
                    {
                        if (CurrentBar - i < 0) continue;

                        DateTime barTimeEST = TimeZoneInfo.ConvertTime(Time[i], chartZone, estZone);
                        if (barTimeEST.Hour == 9 && (barTimeEST.Minute == 30 || barTimeEST.Minute == 31))
                        {
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

            // Net Displacement reset
            lastNetDispRatio = double.NaN;
            lastNetDispPassed = false;
            netDispRejectCount = 0;

            // === DIAG PATCH === reset position tracker at session open
            _prevPosition = MarketPosition.Flat;

            if (SystemPerformance.AllTrades.Count > 0)
                prevClosedProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
            else
                prevClosedProfit = 0;

            LoadNewsCSV(estTime);
        }

        // =====================================================================
        // NET DISPLACEMENT CALCULATION
        // =====================================================================

        /// <summary>
        /// Calculates how much of the candle body sits beyond a boundary level,
        /// as a ratio of the total candle range.
        /// 
        /// For longs: measures body above rHigh / candle range
        /// For shorts: measures body below rLow / candle range
        /// 
        /// High ratio = committed breakout (body pushed through)
        /// Low ratio = wicky/fake breakout (wick poked through, body stayed near boundary)
        /// </summary>
        private double CalcNetBodyRatio(bool isLong)
        {
            double candleRange = High[0] - Low[0];
            if (candleRange <= 0) return 0.0;

            double bodyTop = Math.Max(Open[0], Close[0]);
            double bodyBot = Math.Min(Open[0], Close[0]);

            if (isLong)
            {
                // How much of the body is ABOVE rHigh
                double bodyAbove = Math.Max(0.0, bodyTop - Math.Max(bodyBot, rHigh));
                return bodyAbove / candleRange;
            }
            else
            {
                // How much of the body is BELOW rLow
                double bodyBelow = Math.Max(0.0, Math.Min(bodyTop, rLow) - bodyBot);
                return bodyBelow / candleRange;
            }
        }

        /// <summary>
        /// Returns true if the breakout candle passes the net displacement quality check.
        /// When EnableNetDisplacement is false, always returns true (no filtering).
        /// </summary>
        private bool PassesNetDisplacement(bool isLong, bool isImmediateMode)
        {
            if (!EnableNetDisplacement)
                return true;

            // Check if this filter applies to the current entry mode
            if (isImmediateMode && !NetDispApplyToImmediate)
                return true;
            if (!isImmediateMode && !NetDispApplyToPullback)
                return true;

            double ratio = CalcNetBodyRatio(isLong);
            lastNetDispRatio = ratio;

            bool passes = ratio >= MinBodyRatio;
            lastNetDispPassed = passes;

            if (!passes)
            {
                netDispRejectCount++;
                Print(string.Format("NetDisp REJECT: {0} ratio={1:F3} < min={2:F3} (reject #{3} today)",
                    isLong ? "LONG" : "SHORT", ratio, MinBodyRatio, netDispRejectCount));
            }

            return passes;
        }

        private void ProcessTradingLogic(DateTime estTime)
        {
            double rSize = rHigh - rLow;
            double rPct = (rSize / Close[0]) * 100;

            bool isTradingTime = estTime.TimeOfDay >= OREndTime.TimeOfDay && estTime.TimeOfDay < TradingEndTime.TimeOfDay;
            bool isHardExit = estTime.TimeOfDay >= HardExitTime.TimeOfDay;

            bool isRangeFiltered = rPct > MaxRangePct || rPct < MinRangePct;
            bool isVVIXFiltered = UseVVIXFilter && VVIX_Open > MaxVVIX;
            bool isFiltered = isRangeFiltered || isVVIXFiltered;

            if (Position.MarketPosition == MarketPosition.Flat && Close[0] >= rLow && Close[0] <= rHigh)
                priceReturnedToRange = true;

            if (StopAfterWin && !hasWonToday)
            {
                double currentProfit = SystemPerformance.AllTrades.Count > 0 ?
                    SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit : 0;
                if (currentProfit > prevClosedProfit + 10)
                    hasWonToday = true;
            }

            bool cooldownComplete = lastExitBar < 0 || (CurrentBar - lastExitBar) >= CooldownBars;

            bool reentryEligible = ReentryModel == ORB_AllDay_ReentryMode.Immediate ||
                                   (ReentryModel == ORB_AllDay_ReentryMode.FreshOnly && priceReturnedToRange) ||
                                   ReentryModel == ORB_AllDay_ReentryMode.OnePerDirection;

            bool canTakeLong = ReentryModel != ORB_AllDay_ReentryMode.OnePerDirection || !longTakenToday;
            bool canTakeShort = ReentryModel != ORB_AllDay_ReentryMode.OnePerDirection || !shortTakenToday;

            bool inNewsBlackout = IsInNewsBlackout(estTime);

            bool canTrade = isTradingTime && !isHardExit && !isFiltered &&
                            attemptsToday < MaxAttempts && cooldownComplete &&
                            reentryEligible && !(StopAfterWin && hasWonToday) &&
                            !inNewsBlackout &&
                            Position.MarketPosition == MarketPosition.Flat;

            int qty = CalculateQty(rSize);

            if (canTrade)
            {
                ProcessEntryLogic(estTime, qty, canTakeLong, canTakeShort, rSize);
            }

            // Hard Exit
            bool hardExitTriggered = false;
            if (Position.MarketPosition != MarketPosition.Flat && isHardExit)
            {
                hardExitTriggered = true;

                if (Position.MarketPosition == MarketPosition.Long)
                    ExitLong(Position.Quantity, "Time Exit", "");
                else
                    ExitShort(Position.Quantity, "Time Exit", "");
            }

            if (!hardExitTriggered && Position.MarketPosition != MarketPosition.Flat)
            {
                ProcessExitLogic(estTime, rSize);
            }

            if (ShowDashboard)
                DrawDashboard(estTime, rSize, rPct, isFiltered, isTradingTime);

            if (ShowRangeBox)
                DrawRangeBox(estTime, rSize, rPct, isRangeFiltered);
        }

        private void LoadNewsCSV(DateTime estDate)
        {
            newsBlackoutTimes.Clear();
            newsFileLoaded = false;
            string dateStr = estDate.ToString("yyyy-MM-dd");

            if (!AutoLoadNewsCSV || string.IsNullOrEmpty(NewsCSVPath))
                return;

            try
            {
                if (!System.IO.File.Exists(NewsCSVPath))
                {
                    Print("NewsBlackout: CSV not found at " + NewsCSVPath);
                    return;
                }

                string[] lines = System.IO.File.ReadAllLines(NewsCSVPath);
                bool headerSkipped = false;

                foreach (string line in lines)
                {
                    if (string.IsNullOrWhiteSpace(line) || line.StartsWith("#"))
                        continue;

                    if (!headerSkipped && line.StartsWith("date"))
                    {
                        headerSkipped = true;
                        continue;
                    }
                    headerSkipped = true;

                    string[] parts = line.Split(',');
                    if (parts.Length < 3)
                        continue;

                    string eventDate = parts[0].Trim();
                    string eventTime = parts[1].Trim();

                    if (eventDate != dateStr)
                        continue;

                    TimeSpan ts;
                    if (TimeSpan.TryParse(eventTime, out ts))
                    {
                        newsBlackoutTimes.Add(ts);
                        string impact = parts.Length > 2 ? parts[2].Trim() : "";
                        string eventName = parts.Length > 3 ? parts[3].Trim() : "";
                        Print(string.Format("NewsBlackout: Loaded {0} {1} - {2} ({3})",
                            eventDate, eventTime, eventName, impact));
                    }
                }

                newsFileLoaded = true;
                newsFileDate = dateStr;
                Print(string.Format("NewsBlackout: {0} events loaded for {1}",
                    newsBlackoutTimes.Count, dateStr));
            }
            catch (Exception ex)
            {
                Print("NewsBlackout: Error reading CSV - " + ex.Message);
            }
        }

        private bool IsInNewsBlackout(DateTime estTime)
        {
            if (!EnableNewsBlackout) return false;

            TimeSpan now = estTime.TimeOfDay;

            if (AutoLoadNewsCSV && newsFileLoaded)
            {
                foreach (TimeSpan newsTime in newsBlackoutTimes)
                {
                    if (IsInWindow(now, newsTime, NewsPreMinutes, NewsPostMinutes))
                        return true;
                }
            }

            if (NewsTime1_Enabled && IsInWindow(now, NewsTime1.TimeOfDay, NewsPreMinutes, NewsPostMinutes)) return true;
            if (NewsTime2_Enabled && IsInWindow(now, NewsTime2.TimeOfDay, NewsPreMinutes, NewsPostMinutes)) return true;
            if (NewsTime3_Enabled && IsInWindow(now, NewsTime3.TimeOfDay, NewsPreMinutes, NewsPostMinutes)) return true;
            if (NewsTime4_Enabled && IsInWindow(now, NewsTime4.TimeOfDay, NewsPreMinutes, NewsPostMinutes)) return true;

            return false;
        }

        private bool IsInWindow(TimeSpan now, TimeSpan newsTime, int preMins, int postMins)
        {
            TimeSpan windowStart = newsTime.Subtract(TimeSpan.FromMinutes(preMins));
            TimeSpan windowEnd = newsTime.Add(TimeSpan.FromMinutes(postMins));
            return now >= windowStart && now <= windowEnd;
        }

        private double GetInitialSLPrice(bool isLong, double entryPrice)
        {
            if (UsePercentSL)
            {
                return isLong
                    ? entryPrice * (1 - PercentSLPct / 100.0)
                    : entryPrice * (1 + PercentSLPct / 100.0);
            }
            else
            {
                return isLong ? rLow : rHigh;
            }
        }

        private void ProcessEntryLogic(DateTime estTime, int qty, bool canTakeLong, bool canTakeShort, double rSize)
        {
            double displacementHigh = rHigh * (1 + MinDisplacementPct / 100);
            double displacementLow = rLow * (1 - MinDisplacementPct / 100);

            double maxPBLong = rHigh - (rSize * MaxPullbackDepthPct / 100);
            double maxPBShort = rLow + (rSize * MaxPullbackDepthPct / 100);

            double fallbackLongZone = rHigh * (1 + FallbackProximityPct / 100);
            double fallbackShortZone = rLow * (1 - FallbackProximityPct / 100);

            bool breakoutLong = CrossAbove(Close, rHigh, 1);
            bool breakoutShort = CrossBelow(Close, rLow, 1);

            // Standard displacement check
            bool hasDisplacementLong = Close[0] >= displacementHigh;
            bool hasDisplacementShort = Close[0] <= displacementLow;

            // IMMEDIATE MODE
            if (EntryModel == ORB_AllDay_EntryMode.Immediate)
            {
                if (breakoutLong && canTakeLong)
                {
                    // >>> NET DISPLACEMENT GATE <<<
                    if (PassesNetDisplacement(true, true))
                    {
                        EnterLong(0, qty, "Long");
                        SetupEntry(true, qty);
                    }
                }
                else if (breakoutShort && canTakeShort)
                {
                    // >>> NET DISPLACEMENT GATE <<<
                    if (PassesNetDisplacement(false, true))
                    {
                        EnterShort(0, qty, "Short");
                        SetupEntry(false, qty);
                    }
                }
            }
            // PULLBACK MODES
            else
            {
                // Arm pending entries — net displacement gates the arming
                if (!longPending && !shortPending)
                {
                    if (breakoutLong && hasDisplacementLong && canTakeLong)
                    {
                        // >>> NET DISPLACEMENT GATE (arming) <<<
                        if (PassesNetDisplacement(true, false))
                        {
                            longPending = true;
                            breakoutBar = CurrentBar;
                            sigCandleExtreme = Low[0];
                        }
                    }
                    else if (breakoutShort && hasDisplacementShort && canTakeShort)
                    {
                        // >>> NET DISPLACEMENT GATE (arming) <<<
                        if (PassesNetDisplacement(false, false))
                        {
                            shortPending = true;
                            breakoutBar = CurrentBar;
                            sigCandleExtreme = High[0];
                        }
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

            double slPrice = GetInitialSLPrice(isLong, Close[0]);

            // Dump Pouch initialization
            dumpLevel = 0;
            initialSLPrice = slPrice;
            currentDPStop = slPrice;
            dpTP1Price = isLong ? Close[0] * (1 + TP1Pct / 100) : Close[0] * (1 - TP1Pct / 100);
            dpTargetPrice = isLong ? Close[0] * (1 + DP_TargetMovePct / 100) : Close[0] * (1 - DP_TargetMovePct / 100);

            double moveToTarget = Math.Abs(dpTargetPrice - Close[0]);
            dpLevel2Price = isLong ? Close[0] + moveToTarget * (DP_Level2TriggerPct / 100)
                                   : Close[0] - moveToTarget * (DP_Level2TriggerPct / 100);
            dpLevel3Price = isLong ? Close[0] + moveToTarget * (DP_Level3TriggerPct / 100)
                                   : Close[0] - moveToTarget * (DP_Level3TriggerPct / 100);

            if (isLong)
                ExitLongStopMarket(0, true, qty, slPrice, "SL", "");
            else
                ExitShortStopMarket(0, true, qty, slPrice, "SL", "");
        }

        private void ProcessExitLogic(DateTime estTime, double rSize)
        {
            longPending = false;
            shortPending = false;

            double entry = Position.AveragePrice;
            bool isLong = Position.MarketPosition == MarketPosition.Long;

            double baseSL = GetInitialSLPrice(isLong, entry);

            bool maeTriggered = false;
            if (UseMAEFilter && !tp1Hit)
            {
                double heatDist = entry * (MAEThresholdPct / 100);
                if (isLong && Low[0] < entry - heatDist)
                {
                    ExitLong(Position.Quantity, "MAE Exit", "");
                    maeTriggered = true;
                }
                else if (!isLong && High[0] > entry + heatDist)
                {
                    ExitShort(Position.Quantity, "MAE Exit", "");
                    maeTriggered = true;
                }
            }

            if (!maeTriggered)
            {
                if (EnableMultiTP && NumTPLevels >= 2)
                {
                    ProcessMultiTPExits(entry, isLong, baseSL);
                }
                else
                {
                    ProcessSingleTPExits(entry, isLong, baseSL);
                }
            }

            if (ShowTPSLLevels && !maeTriggered)
            {
                double tp1Price = isLong ? entry * (1 + TP1Pct / 100) : entry * (1 - TP1Pct / 100);
                double tp2Price = isLong ? entry * (1 + TP2Pct / 100) : entry * (1 - TP2Pct / 100);
                double tp3Price = isLong ? entry * (1 + TP3Pct / 100) : entry * (1 - TP3Pct / 100);

                double displaySL;
                if (RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.DumpPouch && tp1Hit)
                    displaySL = currentDPStop;
                else if (tp1Hit && RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.Trailing && !double.IsNaN(currentTrailStop))
                    displaySL = currentTrailStop;
                else if (tp1Hit && MoveToBreakevenAfterTP1)
                    displaySL = entry;
                else
                    displaySL = baseSL;

                Draw.Line(this, "TP1_Line", false, 1, tp1Price, 0, tp1Price,
                    tp1Hit ? Brushes.Gray : Brushes.LimeGreen, DashStyleHelper.Solid, 2);
                Draw.Line(this, "TP2_Line", false, 1, tp2Price, 0, tp2Price, Brushes.Lime, DashStyleHelper.Dash, 1);
                if (NumTPLevels >= 3)
                    Draw.Line(this, "TP3_Line", false, 1, tp3Price, 0, tp3Price, Brushes.Aqua, DashStyleHelper.Dot, 1);
                Draw.Line(this, "SL_Line", false, 1, displaySL, 0, displaySL, Brushes.Red, DashStyleHelper.Solid, 2);

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
                        dumpLevel = 1;
                        double riskAmount = Math.Abs(entry - initialSLPrice);
                        double riskReduction = riskAmount * (DP_Level1RiskReducePct / 100.0);
                        currentDPStop = isLong ? initialSLPrice + riskReduction
                                               : initialSLPrice - riskReduction;
                    }
                }
            }

            if (tp1Hit && !tp2Hit && NumTPLevels >= 3)
            {
                if ((isLong && High[0] >= tp2Price) || (!isLong && Low[0] <= tp2Price))
                    tp2Hit = true;
            }

            // Dump Pouch Mode
            if (RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.DumpPouch)
            {
                if (tp1Hit)
                {
                    if (dumpLevel == 1)
                    {
                        if ((isLong && High[0] >= dpLevel2Price) || (!isLong && Low[0] <= dpLevel2Price))
                        {
                            dumpLevel = 2;
                            currentDPStop = entry;
                        }
                    }

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
                    currentSL = initialSLPrice;
                }

                int qty = Position.Quantity;
                int tp1ExitQty = tp1Hit ? 0 : Math.Min(tp1Qty, qty);

                if (isLong)
                {
                    if (tp1ExitQty > 0)
                        ExitLongLimit(0, true, tp1ExitQty, tp1Price, "TP1", "");
                    ExitLongStopMarket(0, true, qty, currentSL, "SL", "");
                }
                else
                {
                    if (tp1ExitQty > 0)
                        ExitShortLimit(0, true, tp1ExitQty, tp1Price, "TP1", "");
                    ExitShortStopMarket(0, true, qty, currentSL, "SL", "");
                }

                return;
            }

            // Non-Dump-Pouch Modes
            if (tp1Hit && MoveToBreakevenAfterTP1)
                currentSL = entry;

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

            int qtyNow = Position.Quantity;

            if (NumTPLevels >= 3)
            {
                int tp1ExitQ = tp1Hit ? 0 : Math.Min(tp1Qty, qtyNow);
                int tp2Qty = (int)Math.Max(1, Math.Floor(entryQty * TP2PositionPct / 100.0));
                int tp2ExitQ = tp2Hit ? 0 : Math.Min(tp2Qty, qtyNow - tp1ExitQ);
                int tp3ExitQ = qtyNow - tp1ExitQ - tp2ExitQ;

                if (isLong)
                {
                    if (tp1ExitQ > 0)
                        ExitLongLimit(0, true, tp1ExitQ, tp1Price, "TP1", "");
                    if (tp2ExitQ > 0)
                        ExitLongLimit(0, true, tp2ExitQ, tp2Price, "TP2", "");
                    if (tp3ExitQ > 0 && tp1Hit)
                        ExitLongLimit(0, true, tp3ExitQ, tp3Price, "TP3", "");
                    ExitLongStopMarket(0, true, qtyNow, currentSL, "SL", "");
                }
                else
                {
                    if (tp1ExitQ > 0)
                        ExitShortLimit(0, true, tp1ExitQ, tp1Price, "TP1", "");
                    if (tp2ExitQ > 0)
                        ExitShortLimit(0, true, tp2ExitQ, tp2Price, "TP2", "");
                    if (tp3ExitQ > 0 && tp1Hit)
                        ExitShortLimit(0, true, tp3ExitQ, tp3Price, "TP3", "");
                    ExitShortStopMarket(0, true, qtyNow, currentSL, "SL", "");
                }
            }
            else
            {
                int tp1ExitQ = tp1Hit ? 0 : Math.Min(tp1Qty, qtyNow);
                int tp2ExitQ = qtyNow - tp1ExitQ;

                if (isLong)
                {
                    if (tp1ExitQ > 0)
                        ExitLongLimit(0, true, tp1ExitQ, tp1Price, "TP1", "");
                    if (tp2ExitQ > 0)
                        ExitLongLimit(0, true, tp2ExitQ, tp2Price, "TP2", "");
                    ExitLongStopMarket(0, true, qtyNow, currentSL, "SL", "");
                }
                else
                {
                    if (tp1ExitQ > 0)
                        ExitShortLimit(0, true, tp1ExitQ, tp1Price, "TP1", "");
                    if (tp2ExitQ > 0)
                        ExitShortLimit(0, true, tp2ExitQ, tp2Price, "TP2", "");
                    ExitShortStopMarket(0, true, qtyNow, currentSL, "SL", "");
                }
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
            double slDistance;
            if (UsePercentSL)
                slDistance = Close[0] * (PercentSLPct / 100.0);
            else
                slDistance = rSize;

            if (RiskPercent <= 0 || slDistance <= 0)
                return 1;

            double riskAmt = InitialCapital * (RiskPercent / 100.0);
            int qty = (int)Math.Max(1, Math.Floor(riskAmt / (slDistance * Instrument.MasterInstrument.PointValue)));
            return Math.Min(qty, MaxContracts);
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.Order.OrderState == OrderState.Filled &&
                (execution.Order.Name.Contains("TP") || execution.Order.Name.Contains("SL") ||
                 execution.Order.Name.Contains("MAE") || execution.Order.Name.Contains("Time") ||
                 execution.Order.Name.Contains("Target") || execution.Order.Name.Contains("Stop") ||
                 execution.Order.Name.Contains("DP")))
            {
                lastExitBar = CurrentBar;
            }
        }

        private void DrawDashboard(DateTime estTime, double rSize, double rPct, bool isFiltered, bool isTradingTime)
        {
            string slMode = UsePercentSL ? $"Pct({PercentSLPct}%)" : "Range";
            string newsInfo = AutoLoadNewsCSV && newsFileLoaded
                ? $"Auto({newsBlackoutTimes.Count} events)"
                : "Manual";
            string tpMode = EnableMultiTP ?
                $"{NumTPLevels} TPs: {TP1Pct}%/{TP2Pct}%" :
                $"Single: {SingleTPPct}%";

            string status = Position.MarketPosition != MarketPosition.Flat ? "IN TRADE" :
                           hasWonToday && StopAfterWin ? "WON - DONE" :
                           isFiltered ? "FILTERED" :
                           attemptsToday >= MaxAttempts ? "MAX ATTEMPTS" :
                           IsInNewsBlackout(estTime) ? "NEWS BLACKOUT" :
                           isTradingTime ? "READY" : "WAITING";

            string tp1Status = tp1Hit ? "YES ✓" : "NO";
            string runnerStatus = isRunnerActive ? RunnerModeAfterTP1.ToString() : "Inactive";
            string dpStatus = RunnerModeAfterTP1 == ORB_AllDay_RunnerMode.DumpPouch ?
                (dumpLevel == 0 ? "INITIAL" : dumpLevel == 1 ? "LVL1(Risk-)" : dumpLevel == 2 ? "LVL2(BE)" : "LVL3(LOCK)") : "N/A";

            // Net Displacement status line
            string ndStatus = EnableNetDisplacement
                ? string.Format("ON (≥{0:F2}) Rej:{1}", MinBodyRatio, netDispRejectCount)
                : "OFF";
            string ndScope = EnableNetDisplacement
                ? (NetDispApplyToImmediate ? "IM " : "") + (NetDispApplyToPullback ? "PB" : "")
                : "-";
            string ndLast = !double.IsNaN(lastNetDispRatio)
                ? string.Format("{0:F3}{1}", lastNetDispRatio, lastNetDispPassed ? " ✓" : " ✗")
                : "-";

            string hud = string.Format(
                "ORB ALL-DAY V2\n" +
                "─────────────\n" +
                "Range: {0:F2} pts ({1:F3}%)\n" +
                "VVIX: {2:F1}\n" +
                "Attempts: {3}/{4} (L:{5} S:{6})\n" +
                "TP Mode: {7}\n" +
                "SL Mode: {8}\n" +
                "News: {9}\n" +
                "TP1 Hit: {10}\n" +
                "Runner: {11}\n" +
                "Dump Pouch: {12}\n" +
                "MAE: {13}%\n" +
                "MaxQty: {14}\n" +
                "Net Disp: {15}\n" +
                "  Scope: {16} Last: {17}\n" +
                "Status: {18}\n" +
                "Time: {19:HH:mm}",
                rSize, rPct, VVIX_Open,
                attemptsToday, MaxAttempts, longAttempts, shortAttempts,
                tpMode, slMode, newsInfo, tp1Status, runnerStatus, dpStatus,
                MAEThresholdPct, MaxContracts,
                ndStatus, ndScope, ndLast,
                status, estTime);

            Draw.TextFixed(this, "HUD", hud, TextPosition.TopRight, Brushes.White,
                new SimpleFont("Consolas", 10), Brushes.Black, Brushes.DimGray, 90);
        }

        private void DrawRangeBox(DateTime estTime, double rSize, double rPct, bool isRangeFiltered)
        {
            if (!rDefined) return;
            if (chartZone == null || estZone == null) return;

            DateTime rangeDate = estTime.Date;

            DateTime estOpen = rangeDate.Add(OREndTime.TimeOfDay);
            DateTime estEnd = rangeDate.Add(new TimeSpan(16, 0, 0));

            DateTime chartStart = TimeZoneInfo.ConvertTime(estOpen, estZone, chartZone);
            DateTime chartEnd = TimeZoneInfo.ConvertTime(estEnd, estZone, chartZone);

            DateTime displayEnd = (Time[0] < chartEnd) ? Time[0] : chartEnd;

            Brush fillBrush = isRangeFiltered ? Brushes.Red : Brushes.DeepSkyBlue;
            string suffix = rangeDate.ToString("yyyyMMdd");

            Draw.Line(this, "High" + suffix, false, chartStart, rHigh, displayEnd, rHigh, Brushes.DeepSkyBlue, DashStyleHelper.Solid, 2);
            Draw.Line(this, "Low" + suffix, false, chartStart, rLow, displayEnd, rLow, Brushes.OrangeRed, DashStyleHelper.Solid, 2);

            double mid = (rHigh + rLow) / 2;
            Draw.Line(this, "Mid" + suffix, false, chartStart, mid, displayEnd, mid, Brushes.Gold, DashStyleHelper.Dash, 1);

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

        // --- Net Displacement Filter Properties (NEW) ---

        [NinjaScriptProperty]
        [Display(Name = "Enable Net Displacement", Order = 1, GroupName = "2b. Net Displacement",
            Description = "Require breakout candle body to be substantially beyond range boundary")]
        public bool EnableNetDisplacement { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Body Ratio", Order = 2, GroupName = "2b. Net Displacement",
            Description = "Fraction of candle range that body must be beyond boundary. 0.30=moderate, 0.50=strict")]
        [Range(0.05, 0.90)]
        public double MinBodyRatio { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Apply to Immediate Mode", Order = 3, GroupName = "2b. Net Displacement",
            Description = "Gate Immediate entries with net displacement check")]
        public bool NetDispApplyToImmediate { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Apply to Pullback Arm", Order = 4, GroupName = "2b. Net Displacement",
            Description = "Gate Pullback/Fallback arming with net displacement check")]
        public bool NetDispApplyToPullback { get; set; }

        // --- Re-entry ---

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

        // --- Multi-TP ---

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

        // --- Risk ---

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
        [Display(Name = "Use Percent-Based SL", Order = 7, GroupName = "5. Risk",
            Description = "If true, SL is set at PercentSLPct% from entry. If false, SL is at range High/Low.")]
        public bool UsePercentSL { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Percent SL %", Order = 8, GroupName = "5. Risk",
            Description = "Stop loss distance as % of entry price (used when Use Percent-Based SL is enabled)")]
        public double PercentSLPct { get; set; }

        // --- Dump Pouch ---

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

        // --- Filters ---

        // === DIAG PATCH === parity-harness instrumentation toggle
        [NinjaScriptProperty]
        [Display(Name = "Verbose Diag", Order = 99, GroupName = "9. Diagnostics",
            Description = "Emit per-bar gate decisions to the SA log file for the Python<->NT8 parity harness. Disable for live trading.")]
        public bool VerboseDiag { get; set; }

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

        // --- News Blackout ---

        [NinjaScriptProperty]
        [Display(Name = "Enable News Blackout", Order = 1, GroupName = "7. News Blackout",
            Description = "Block new entries during configurable windows around news events (all times ET)")]
        public bool EnableNewsBlackout { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Auto-Load from CSV", Order = 2, GroupName = "7. News Blackout",
            Description = "Automatically load news times from CSV (generated by news_calendar_fetcher.py)")]
        public bool AutoLoadNewsCSV { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "News CSV Path", Order = 3, GroupName = "7. News Blackout",
            Description = "Full path to news_blackout.csv file")]
        public string NewsCSVPath { get; set; }

        [NinjaScriptProperty]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
        [Display(Name = "News Time 1 (ET)", Order = 4, GroupName = "7. News Blackout")]
        public DateTime NewsTime1 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "News Time 1 Enabled", Order = 5, GroupName = "7. News Blackout")]
        public bool NewsTime1_Enabled { get; set; }

        [NinjaScriptProperty]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
        [Display(Name = "News Time 2 (ET)", Order = 6, GroupName = "7. News Blackout")]
        public DateTime NewsTime2 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "News Time 2 Enabled", Order = 7, GroupName = "7. News Blackout")]
        public bool NewsTime2_Enabled { get; set; }

        [NinjaScriptProperty]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
        [Display(Name = "News Time 3 (ET)", Order = 8, GroupName = "7. News Blackout")]
        public DateTime NewsTime3 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "News Time 3 Enabled", Order = 9, GroupName = "7. News Blackout")]
        public bool NewsTime3_Enabled { get; set; }

        [NinjaScriptProperty]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
        [Display(Name = "News Time 4 (ET)", Order = 10, GroupName = "7. News Blackout")]
        public DateTime NewsTime4 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "News Time 4 Enabled", Order = 11, GroupName = "7. News Blackout")]
        public bool NewsTime4_Enabled { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Pre-News Buffer (minutes)", Order = 12, GroupName = "7. News Blackout")]
        public int NewsPreMinutes { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Post-News Buffer (minutes)", Order = 13, GroupName = "7. News Blackout")]
        public int NewsPostMinutes { get; set; }

        // --- Visuals ---

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
