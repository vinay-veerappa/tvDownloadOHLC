#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// IBBreakoutBotStandalone — Play 1 (Breakout) inheriting directly from Strategy.
    /// Bypasses RiskManagerBase to avoid the BarsRequiredToTrade=50 / 5-min secondary
    /// / GetCurrentATR gate that blocks all entries. This is a proof-of-concept to
    /// verify the IB logic works; the full RiskManagerBase integration will be fixed
    /// separately by making BarsRequiredToTrade configurable.
    /// </summary>
    public class IBBreakoutBotStandalone : Strategy
    {
        #region Parameters
        [NinjaScriptProperty]
        [Display(Name = "Range Start Hour", Order = 1, GroupName = "IB Window")]
        public int RangeStartHour { get; set; } = 9;

        [NinjaScriptProperty]
        [Display(Name = "Range Start Minute", Order = 2, GroupName = "IB Window")]
        public int RangeStartMinute { get; set; } = 30;

        [NinjaScriptProperty]
        [Display(Name = "Range Duration (min)", Order = 3, GroupName = "IB Window")]
        public int RangeDurationMin { get; set; } = 30;

        [NinjaScriptProperty]
        [Display(Name = "Target Level (R)", Order = 4, GroupName = "IB Window")]
        public double TargetLvl { get; set; } = 0.5;

        [NinjaScriptProperty]
        [Display(Name = "Stop R Mult", Order = 5, GroupName = "IB Window")]
        public double StopRMult { get; set; } = 0.25;

        [NinjaScriptProperty]
        [Display(Name = "Require Direction Bias", Order = 6, GroupName = "IB Window")]
        public bool RequireDirectionBias { get; set; } = false;

        [NinjaScriptProperty]
        [Display(Name = "Close Position Top %", Order = 7, GroupName = "IB Window")]
        public double ClosePositionTopPct { get; set; } = 0.75;

        [NinjaScriptProperty]
        [Display(Name = "Close Position Bot %", Order = 8, GroupName = "IB Window")]
        public double ClosePositionBotPct { get; set; } = 0.25;
        #endregion

        #region State
        private double rangeHigh, rangeLow, rangeOpen, rangeClose, rangeRange, rangeMid;
        private double rangeClosePosition;
        private int biasFirstreach;
        private int predictedDir;
        private bool rangeComplete;
        private bool rangeStarted;
        private DateTime firstHighTouch, firstLowTouch, rangeCompleteTime;
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "IB Breakout Bot (Play 1) — standalone, no RiskManagerBase";
                Name = "IBBreakoutBotStandalone";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 60;
                BarsRequiredToTrade = 1;  // minimal warmup
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;

            DateTime now = Time[0];
            DateTime rangeStart = new DateTime(now.Year, now.Month, now.Day, RangeStartHour, RangeStartMinute, 0);
            DateTime rangeEnd = rangeStart.AddMinutes(RangeDurationMin);

            // Session reset — detect new day
            if (now.TimeOfDay < TimeSpan.FromMinutes(1) && CurrentBar > 1)
            {
                rangeComplete = false;
                rangeStarted = false;
                rangeHigh = rangeLow = rangeOpen = rangeClose = rangeRange = rangeMid = 0;
                rangeClosePosition = 0;
                biasFirstreach = 0;
                predictedDir = 0;
                firstHighTouch = firstLowTouch = DateTime.MinValue;
            }

            // Build IB window
            if (!rangeComplete)
            {
                if (now >= rangeEnd)
                {
                    // Finalize
                    rangeRange = rangeHigh - rangeLow;
                    rangeMid = (rangeHigh + rangeLow) / 2.0;
                    rangeClosePosition = rangeRange > 0 ? (rangeClose - rangeLow) / rangeRange : 0.5;
                    rangeComplete = true;
                    rangeCompleteTime = now;

                    // Compute bias (Rule 1)
                    biasFirstreach = firstLowTouch < firstHighTouch ? 1 : firstHighTouch < firstLowTouch ? -1 : 0;
                    if (!RequireDirectionBias) predictedDir = 0;
                    else if (biasFirstreach == 1 && rangeClosePosition >= ClosePositionTopPct) predictedDir = 1;
                    else if (biasFirstreach == -1 && rangeClosePosition <= ClosePositionBotPct) predictedDir = -1;
                    else predictedDir = 0;

                    Print($"[DIAG] IB finalized: H={rangeHigh} L={rangeLow} R={rangeRange} pos={rangeClosePosition} bias={predictedDir} time={now:HH:mm}");
                }
                else if (now >= rangeStart && now < rangeEnd)
                {
                    if (!rangeStarted)
                    {
                        rangeHigh = High[0]; rangeLow = Low[0]; rangeOpen = Open[0];
                        firstHighTouch = now; firstLowTouch = now;
                        rangeStarted = true;
                    }
                    else
                    {
                        if (High[0] > rangeHigh) { rangeHigh = High[0]; firstHighTouch = now; }
                        if (Low[0] < rangeLow) { rangeLow = Low[0]; firstLowTouch = now; }
                    }
                    rangeClose = Close[0];
                }
                return;
            }

            // Entry: breakout
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                // Long break
                if (Close[0] > rangeHigh)
                {
                    if (RequireDirectionBias && predictedDir != 1) return;

                    double entry = Close[0];
                    double stop = entry - StopRMult * TargetLvl * rangeRange;
                    double target = rangeHigh + TargetLvl * rangeRange;

                    if (target <= entry) return;  // sanity guard

                    EnterLong(1, "IB BO Long");
                    SetProfitTarget(CalculationMode.Price, target);
                    SetStopLoss(CalculationMode.Price, stop);
                    Print($"[DIAG] LONG entry at {entry} stop={stop} target={target} time={now:HH:mm}");
                }
                // Short break
                else if (Close[0] < rangeLow)
                {
                    if (RequireDirectionBias && predictedDir != -1) return;

                    double entry = Close[0];
                    double stop = entry + StopRMult * TargetLvl * rangeRange;
                    double target = rangeLow - TargetLvl * rangeRange;

                    if (target >= entry) return;

                    EnterShort(1, "IB BO Short");
                    SetProfitTarget(CalculationMode.Price, target);
                    SetStopLoss(CalculationMode.Price, stop);
                    Print($"[DIAG] SHORT entry at {entry} stop={stop} target={target} time={now:HH:mm}");
                }
            }

            // ADR-020: flatten at 15:50 ET
            if (now.Hour == 15 && now.Minute >= 50 && Position.MarketPosition != MarketPosition.Flat)
            {
                ExitLong("ADR-020 flatten");
                ExitShort("ADR-020 flatten");
            }
        }
    }
}