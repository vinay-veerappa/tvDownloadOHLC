// ═══════════════════════════════════════════════════════════════════════════
// LiquidityLevels.cs — v1.1.0 Self-Contained Liquidity Levels Engine for NT8
//
// Aggregates 52+ liquidity levels (Prior Day/Week/Month, Session Opens,
// Session Ranges, Intraday, Volume Profile, Market Structure) into one indicator:
//   - Self-contained native calculations for 100% chart reliability
//   - Master Category Toggles + Granular Level Toggles in Property Grid
//   - SessionOpensEngine: Midnight/London/Globex/NY/4H opens
//   - SweepDetector: Wick/Body sweep detection on all SweepTarget levels
//   - SharpDX rendering: Horizontal lines + labels + sweep markers + mouse hover tooltips
//
// Version: 1.1.0
// Design doc: docs/architecture/LIQUIDITY_LEVELS_INDICATOR_DESIGN.md
// ═══════════════════════════════════════════════════════════════════════════

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Core;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using SharpDX;
using SharpDX.Direct2D1;
using SharpDX.DirectWrite;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    public class LiquidityLevels : Indicator
    {
        #region Private Variables

        private SessionOpensEngine sessionOpens;
        private List<LevelState> activeLevels = new List<LevelState>();
        private List<SweepEvent> sweepEvents = new List<SweepEvent>();
        private List<SweepEvent> todaySweeps = new List<SweepEvent>();
        private DateTime lastDate = DateTime.MinValue;
        private TimeZoneInfo etZone;

        // Built-in indicators & data
        private double tickSize;
        private double prevClose;

        // Native Prior Week / Month Tracking
        private double curWeekHigh, curWeekLow, curWeekClose;
        private double prevWeekHigh, prevWeekLow, prevWeekCloseVal;
        private int curWeekNum = -1;

        private double curMonthHigh, curMonthLow;
        private double prevMonthHigh, prevMonthLow;
        private int curMonthNum = -1;

        // Native Session Range Tracking (Asia, London, Globex, IB)
        private double asiaHigh, asiaLow, asiaMid;
        private double londonHigh, londonLow, londonMid;
        private double globexHigh, globexLow, globexMid;
        private double ibHigh, ibLow, ibMid;

        private bool asiaBuilding, londonBuilding, globexBuilding, ibBuilding;
        private DateTime asiaDate, londonDate, globexDate, ibDate;

        // P12 & NY P12 Tracking
        private double p12High, p12Low;
        private bool p12Building;
        private DateTime p12Date;

        private double nyP12High, nyP12Low;
        private bool nyP12Building;
        private DateTime nyP12Date;
        private double prevNyP12High, prevNyP12Low, prevNyP12Mid;

        // SharpDX
        private SharpDX.DirectWrite.TextFormat textFormat;
        private SharpDX.DirectWrite.TextFormat tooltipFormat;
        private bool resourcesCreated;

        #endregion

        #region NinjaScript Properties — Category Master Toggles

        [Display(Name = "Show Prior Day Levels", Order = 1, GroupName = "0. Level Categories (Master)")]
        public bool ShowPriorDay { get; set; } = true;

        [Display(Name = "Show Prior Week Levels", Order = 2, GroupName = "0. Level Categories (Master)")]
        public bool ShowPriorWeek { get; set; } = true;

        [Display(Name = "Show Prior Month Levels", Order = 3, GroupName = "0. Level Categories (Master)")]
        public bool ShowPriorMonth { get; set; } = true;

        [Display(Name = "Show Session Opens", Order = 4, GroupName = "0. Level Categories (Master)")]
        public bool ShowSessionOpens { get; set; } = true;

        [Display(Name = "Show Session Ranges", Order = 5, GroupName = "0. Level Categories (Master)")]
        public bool ShowSessionRanges { get; set; } = true;

        [Display(Name = "Show Intraday High/Low", Order = 6, GroupName = "0. Level Categories (Master)")]
        public bool ShowIntraday { get; set; } = true;

        [Display(Name = "Show Volume Profile Levels", Order = 7, GroupName = "0. Level Categories (Master)")]
        public bool ShowVolumeProfile { get; set; } = true;

        [Display(Name = "Show Structure Levels", Order = 8, GroupName = "0. Level Categories (Master)")]
        public bool ShowStructure { get; set; } = true;

        [Display(Name = "Show Pivot Levels", Order = 9, GroupName = "0. Level Categories (Master)")]
        public bool ShowPivots { get; set; } = false;

        [Display(Name = "Show Fibonacci Levels", Order = 10, GroupName = "0. Level Categories (Master)")]
        public bool ShowFibs { get; set; } = false;

        #endregion

        #region NinjaScript Properties — Specific Level Toggles (Granular)

        [Display(Name = "Prior Day High (PDH)", Order = 1, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPDH { get; set; } = true;

        [Display(Name = "Prior Day Low (PDL)", Order = 2, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPDL { get; set; } = true;

        [Display(Name = "Prior Day Close (PDC)", Order = 3, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPDC { get; set; } = true;

        [Display(Name = "Prior Week High (PWH)", Order = 4, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPWH { get; set; } = true;

        [Display(Name = "Prior Week Low (PWL)", Order = 5, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPWL { get; set; } = true;

        [Display(Name = "Prior Week Close (PWC)", Order = 6, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPWC { get; set; } = true;

        [Display(Name = "Prev Month High (PMH)", Order = 7, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPMH { get; set; } = true;

        [Display(Name = "Prev Month Low (PML)", Order = 8, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPML { get; set; } = true;

        [Display(Name = "Midnight Open (00:00 ET)", Order = 9, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowMidnightOpen { get; set; } = true;

        [Display(Name = "London Open (03:00 ET)", Order = 10, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowLondonOpen { get; set; } = true;

        [Display(Name = "NY Open (09:30 ET)", Order = 11, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowNyOpen { get; set; } = true;

        [Display(Name = "4-Hour Session Opens", Order = 12, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool Show4HOpens { get; set; } = true;

        [Display(Name = "Asia Range High/Low", Order = 13, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowAsiaRange { get; set; } = true;

        [Display(Name = "London Range High/Low", Order = 14, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowLondonRange { get; set; } = true;

        [Display(Name = "Globex Range High/Low", Order = 15, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowGlobexRange { get; set; } = true;

        [Display(Name = "Initial Balance High/Low", Order = 16, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowIB { get; set; } = true;

        [Display(Name = "Current Session POC", Order = 17, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowCurrentPOC { get; set; } = true;

        [Display(Name = "Current Session Value Area (VAH/VAL)", Order = 18, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowCurrentVA { get; set; } = true;

        [Display(Name = "Prev Day POC", Order = 19, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPrevDayPOC { get; set; } = true;

        [Display(Name = "Prev Day Value Area (VAH/VAL)", Order = 20, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowPrevDayVA { get; set; } = true;

        [Display(Name = "Overnight POC / VAH / VAL", Order = 21, GroupName = "1. Specific Level Toggles (Granular)")]
        public bool ShowOvernightPOC { get; set; } = true;

        #endregion

        #region NinjaScript Properties — General Config

        [Display(Name = "Enable Sweep Detection", Order = 1, GroupName = "2. Sweeps")]
        public bool EnableSweepDetection { get; set; } = true;

        [Display(Name = "Sweep Mode", Order = 2, GroupName = "2. Sweeps")]
        public SweepMode SweepMode { get; set; } = SweepMode.Wick;

        [Range(1, 20)]
        [Display(Name = "Sweep Min Depth (ticks)", Order = 3, GroupName = "2. Sweeps")]
        public int SweepMinDepthTicks { get; set; } = 2;

        [Range(10, 100)]
        [Display(Name = "Sweep Min Wick %", Order = 4, GroupName = "2. Sweeps")]
        public double SweepMinWickPct { get; set; } = 40;

        [Range(1, 20)]
        [Display(Name = "Stacking Tolerance (ticks)", Order = 5, GroupName = "2. Sweeps")]
        public int StackingToleranceTicks { get; set; } = 5;

        [Display(Name = "Draw Lines", Order = 6, GroupName = "3. Visuals")]
        public bool DrawLines { get; set; } = true;

        [Display(Name = "Draw Labels", Order = 7, GroupName = "3. Visuals")]
        public bool DrawLabels { get; set; } = true;

        [Display(Name = "Draw Sweep Markers", Order = 8, GroupName = "3. Visuals")]
        public bool DrawSweepMarkers { get; set; } = true;

        [Display(Name = "Proximity Fade", Description = "Fade levels far from price; brighten when close", Order = 9, GroupName = "3. Visuals")]
        public bool ProximityFade { get; set; } = false;

        [Range(0, 500)]
        [Display(Name = "Proximity Threshold (pts)", Description = "Distance within which levels glow. 0 = auto (use ATR)", Order = 10, GroupName = "3. Visuals")]
        public int ProximityThresholdPoints { get; set; } = 0;

        [Range(0, 100)]
        [Display(Name = "Far Fade Opacity %", Description = "Opacity for far levels (0=hidden, 100=full)", Order = 11, GroupName = "3. Visuals")]
        public int FarFadeOpacity { get; set; } = 15;

        [Range(0, 100)]
        [Display(Name = "Near Glow Opacity %", Description = "Opacity for near levels (0=hidden, 100=full)", Order = 12, GroupName = "3. Visuals")]
        public int NearGlowOpacity { get; set; } = 90;

        [Display(Name = "Use Full Level Names", Description = "Show full level names (e.g., 'Prev Month High', 'Prior Day High') instead of abbreviations ('PMH', 'PDH')", Order = 13, GroupName = "3. Visuals")]
        public bool UseFullLevelNames { get; set; } = false;

        #endregion

        #region Helper: Level Filtering (Category & Granular Toggles)

        private bool IsCategoryEnabled(LevelCategory cat)
        {
            switch (cat)
            {
                case LevelCategory.PriorDay:      return ShowPriorDay;
                case LevelCategory.PriorWeek:     return ShowPriorWeek;
                case LevelCategory.PriorMonth:    return ShowPriorMonth;
                case LevelCategory.SessionOpen:   return ShowSessionOpens;
                case LevelCategory.SessionRange:  return ShowSessionRanges;
                case LevelCategory.Intraday:      return ShowIntraday;
                case LevelCategory.VolumeProfile: return ShowVolumeProfile;
                case LevelCategory.Structure:     return ShowStructure;
                case LevelCategory.Pivot:         return ShowPivots;
                case LevelCategory.Fib:           return ShowFibs;
                default:                          return true;
            }
        }

        private bool IsLevelEnabled(LevelState level)
        {
            if (!IsCategoryEnabled(level.Def.Category)) return false;

            string name = level.Def.Name;

            if (name == "PDH" && !ShowPDH) return false;
            if (name == "PDL" && !ShowPDL) return false;
            if (name == "PDC" && !ShowPDC) return false;
            if (name == "PWH" && !ShowPWH) return false;
            if (name == "PWL" && !ShowPWL) return false;
            if (name == "PWC" && !ShowPWC) return false;
            if (name == "PMH" && !ShowPMH) return false;
            if (name == "PML" && !ShowPML) return false;

            if (name == "MidnightOpen" && !ShowMidnightOpen) return false;
            if (name == "LondonOpen" && !ShowLondonOpen) return false;
            if (name == "NyOpen" && !ShowNyOpen) return false;
            if (name.StartsWith("4H_") && !Show4HOpens) return false;

            if (name.StartsWith("Asia") && !ShowAsiaRange) return false;
            if (name.StartsWith("London") && !ShowLondonRange) return false;
            if (name.StartsWith("Globex") && !ShowGlobexRange) return false;
            if (name.StartsWith("IB") && !ShowIB) return false;

            if (name.Contains("CurrentPOC") && !ShowCurrentPOC) return false;
            if ((name.Contains("CurrentVAH") || name.Contains("CurrentVAL")) && !ShowCurrentVA) return false;
            if (name.Contains("PrevDayPOC") && !ShowPrevDayPOC) return false;
            if ((name.Contains("PrevDayVAH") || name.Contains("PrevDayVAL")) && !ShowPrevDayVA) return false;
            if (name.Contains("Overnight") && !ShowOvernightPOC) return false;

            return true;
        }

        #endregion

        #region OnStateChange

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "v1.1.0 — Unified liquidity levels engine aggregating 52+ key levels (Prior Day/Week/Month, Session Opens, Session Ranges, Volume Profile, Market Structure) with granular toggles, sweep detection, and Direct2D hover tooltips.";
                Name = "LiquidityLevels";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DrawOnPricePanel = true;
                DisplayInDataBox = true;
                IsSuspendedWhileInactive = true;
                ScaleJustification = ScaleJustification.Right;
            }
            else if (State == State.Configure)
            {
                try
                {
                    etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                }
                catch
                {
                    etZone = TimeZoneInfo.FindSystemTimeZoneById("America/New_York");
                }

                sessionOpens = new SessionOpensEngine(Show4HOpens);

                // Initialize level states from catalog
                activeLevels.Clear();
                foreach (var def in LiquidityLevelsCatalog.GetAllLevels())
                {
                    activeLevels.Add(new LevelState(def));
                }
            }
            else if (State == State.DataLoaded)
            {
                tickSize = TickSize;
                if (tickSize <= 0) tickSize = 0.25;  // fallback for NQ
            }
            else if (State == State.Terminated)
            {
                if (textFormat != null) { textFormat.Dispose(); textFormat = null; }
                if (tooltipFormat != null) { tooltipFormat.Dispose(); tooltipFormat = null; }
                resourcesCreated = false;
            }
        }

        #endregion

        #region OnBarUpdate

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;

            DateTime barTimeEt = ToEt(Time[0]);
            double openP = Open[0];
            double highP = High[0];
            double lowP = Low[0];
            double closeP = Close[0];

            // Day rollover
            if (barTimeEt.Date != lastDate)
            {
                lastDate = barTimeEt.Date;
                todaySweeps.Clear();

                foreach (var level in activeLevels)
                    level.Swept = false;
            }

            // Native Week & Month Tracking
            UpdateWeekMonthTracking(barTimeEt, highP, lowP, closeP);

            // Native Session Range Tracking (Asia, London, Globex, IB)
            UpdateSessionRangesTracking(barTimeEt, highP, lowP);

            // Update session opens engine
            sessionOpens.OnBarUpdate(barTimeEt, openP, CurrentBar);

            // Update P12 / NY P12 ranges
            UpdateP12Ranges(barTimeEt, highP, lowP);

            // Update level prices from all engines
            UpdateLevelPrices();

            // Run sweep detection
            if (EnableSweepDetection)
                RunSweepDetection(highP, lowP, openP, closeP, barTimeEt, CurrentBar);

            prevClose = closeP;
        }

        #endregion

        #region Native Level Tracking (Week, Month, Session Ranges)

        private void UpdateWeekMonthTracking(DateTime barEt, double high, double low, double close)
        {
            // Week Tracking
            int weekNum = System.Globalization.CultureInfo.CurrentCulture.Calendar.GetWeekOfYear(
                barEt, System.Globalization.CalendarWeekRule.FirstFourDayWeek, DayOfWeek.Monday);

            if (weekNum != curWeekNum)
            {
                if (curWeekNum != -1)
                {
                    prevWeekHigh = curWeekHigh;
                    prevWeekLow = curWeekLow;
                    prevWeekCloseVal = curWeekClose;
                }
                curWeekHigh = high;
                curWeekLow = low;
                curWeekClose = close;
                curWeekNum = weekNum;
            }
            else
            {
                if (high > curWeekHigh) curWeekHigh = high;
                if (low < curWeekLow) curWeekLow = low;
                curWeekClose = close;
            }

            // Month Tracking
            int monthNum = barEt.Year * 12 + barEt.Month;
            if (monthNum != curMonthNum)
            {
                if (curMonthNum != -1)
                {
                    prevMonthHigh = curMonthHigh;
                    prevMonthLow = curMonthLow;
                }
                curMonthHigh = high;
                curMonthLow = low;
                curMonthNum = monthNum;
            }
            else
            {
                if (high > curMonthHigh) curMonthHigh = high;
                if (low < curMonthLow) curMonthLow = low;
            }
        }

        private void UpdateSessionRangesTracking(DateTime barEt, double high, double low)
        {
            int barMins = barEt.Hour * 60 + barEt.Minute;
            DateTime today = barEt.Date;

            // Asia Range: 20:00 ET to 00:00 ET
            bool inAsia = barMins >= 20 * 60 || barMins < 0;
            if (inAsia)
            {
                if (asiaDate != today || !asiaBuilding)
                {
                    asiaHigh = high; asiaLow = low; asiaBuilding = true; asiaDate = today;
                }
                else
                {
                    if (high > asiaHigh) asiaHigh = high;
                    if (low < asiaLow) asiaLow = low;
                }
                asiaMid = (asiaHigh + asiaLow) / 2.0;
            }
            else if (asiaBuilding && barMins >= 0)
            {
                asiaBuilding = false;
            }

            // London Range: 02:00 ET to 05:00 ET
            bool inLondon = barMins >= 2 * 60 && barMins < 5 * 60;
            if (inLondon)
            {
                if (londonDate != today || !londonBuilding)
                {
                    londonHigh = high; londonLow = low; londonBuilding = true; londonDate = today;
                }
                else
                {
                    if (high > londonHigh) londonHigh = high;
                    if (low < londonLow) londonLow = low;
                }
                londonMid = (londonHigh + londonLow) / 2.0;
            }
            else if (londonBuilding && barMins >= 5 * 60)
            {
                londonBuilding = false;
            }

            // Globex Range: 18:00 ET to 09:30 ET
            bool inGlobex = barMins >= 18 * 60 || barMins < 9 * 60 + 30;
            if (inGlobex)
            {
                if (globexDate != today || !globexBuilding)
                {
                    globexHigh = high; globexLow = low; globexBuilding = true; globexDate = today;
                }
                else
                {
                    if (high > globexHigh) globexHigh = high;
                    if (low < globexLow) globexLow = low;
                }
                globexMid = (globexHigh + globexLow) / 2.0;
            }
            else if (globexBuilding && barMins >= 9 * 60 + 30)
            {
                globexBuilding = false;
            }

            // Initial Balance (IB): 09:30 ET to 10:30 ET
            bool inIb = barMins >= 9 * 60 + 30 && barMins < 10 * 60 + 30;
            if (inIb)
            {
                if (ibDate != today || !ibBuilding)
                {
                    ibHigh = high; ibLow = low; ibBuilding = true; ibDate = today;
                }
                else
                {
                    if (high > ibHigh) ibHigh = high;
                    if (low < ibLow) ibLow = low;
                }
                ibMid = (ibHigh + ibLow) / 2.0;
            }
            else if (ibBuilding && barMins >= 10 * 60 + 30)
            {
                ibBuilding = false;
            }
        }

        #endregion

        #region Level Price Updates

        private void UpdateLevelPrices()
        {
            foreach (var level in activeLevels)
            {
                if (!IsLevelEnabled(level))
                {
                    level.IsActive = false;
                    continue;
                }

                double prevPrice = level.Price;

                switch (level.Def.Source)
                {
                    case LevelSource.SessionOpens:
                        level.Price = sessionOpens.GetOpen(level.Def.Name);
                        level.IsActive = sessionOpens.IsOpenSet(level.Def.Name);
                        if (level.Price != prevPrice && level.Price > 0)
                        {
                            level.SetTime = sessionOpens.GetOpenTime(level.Def.Name);
                            level.SetBarIndex = CurrentBar;
                        }
                        break;

                    case LevelSource.PriorDayOHLC:
                        {
                            level.Price = ReadPriorDayOHLC(level.Def.Accessor);
                            level.IsActive = level.Price > 0;
                            if (level.Price != prevPrice && level.Price > 0)
                                level.SetBarIndex = CurrentBar;
                        }
                        break;

                    case LevelSource.CurrentDayOHL:
                        {
                            level.Price = ReadCurrentDayOHL(level.Def.Accessor);
                            level.IsActive = level.Price > 0;
                            if (level.Price != prevPrice && level.Price > 0)
                                level.SetBarIndex = CurrentBar;
                        }
                        break;

                    case LevelSource.RedTailKeyLevels:
                        {
                            level.Price = ReadRedTailKeyLevels(level.Def.Accessor);
                            level.IsActive = level.Price > 0;
                            if (level.Price != prevPrice && level.Price > 0)
                                level.SetBarIndex = CurrentBar;
                        }
                        break;

                    case LevelSource.RedTailVolumeProfile:
                        {
                            level.Price = ReadRedTailVolumeProfile(level.Def.Accessor);
                            level.IsActive = level.Price > 0;
                            if (level.Price != prevPrice && level.Price > 0)
                                level.SetBarIndex = CurrentBar;
                        }
                        break;

                    case LevelSource.SessionRanges:
                        {
                            level.Price = ReadSessionRanges(level.Def.Accessor);
                            level.IsActive = level.Price > 0;
                            if (level.Price != prevPrice && level.Price > 0)
                                level.SetBarIndex = CurrentBar;
                        }
                        break;

                    case LevelSource.Internal:
                        {
                            level.Price = ComputeInternalLevel(level.Def.Accessor);
                            level.IsActive = level.Price > 0;
                            if (level.Price != prevPrice && level.Price > 0)
                                level.SetBarIndex = CurrentBar;
                        }
                        break;
                }
            }
        }

        private double ReadPriorDayOHLC(string accessor)
        {
            switch (accessor)
            {
                case "PriorHigh": return PriorDayOHLC().PriorHigh[0];
                case "PriorLow": return PriorDayOHLC().PriorLow[0];
                case "PriorClose": return PriorDayOHLC().PriorClose[0];
                default: return 0;
            }
        }

        private double ReadCurrentDayOHL(string accessor)
        {
            switch (accessor)
            {
                case "CurrentHigh": return CurrentDayOHL().CurrentHigh[0];
                case "CurrentLow": return CurrentDayOHL().CurrentLow[0];
                case "CurrentOpen": return CurrentDayOHL().CurrentOpen[0];
                default: return 0;
            }
        }

        private double ReadRedTailKeyLevels(string accessor)
        {
            double pdh = PriorDayOHLC().PriorHigh[0];
            double pdl = PriorDayOHLC().PriorLow[0];
            double pdc = PriorDayOHLC().PriorClose[0];
            double range = pdh - pdl;

            switch (accessor)
            {
                case "PDH": return pdh;
                case "PDL": return pdl;
                case "PWH": return prevWeekHigh > 0 ? prevWeekHigh : pdh;
                case "PWL": return prevWeekLow > 0 ? prevWeekLow : pdl;
                case "PMH": return prevMonthHigh > 0 ? prevMonthHigh : pdh;
                case "PML": return prevMonthLow > 0 ? prevMonthLow : pdl;

                // Daily Floor Pivots
                case "Pp": return (pdh > 0 && pdl > 0 && pdc > 0) ? (pdh + pdl + pdc) / 3.0 : 0;
                case "R1": { double pp = (pdh + pdl + pdc) / 3.0; return (pdh > 0 && pdl > 0) ? (2.0 * pp - pdl) : 0; }
                case "R2": { double pp = (pdh + pdl + pdc) / 3.0; return (pdh > 0 && pdl > 0) ? (pp + range) : 0; }
                case "R3": { double pp = (pdh + pdl + pdc) / 3.0; return (pdh > 0 && pdl > 0) ? (pdh + 2.0 * (pp - pdl)) : 0; }
                case "S1": { double pp = (pdh + pdl + pdc) / 3.0; return (pdh > 0 && pdl > 0) ? (2.0 * pp - pdh) : 0; }
                case "S2": { double pp = (pdh + pdl + pdc) / 3.0; return (pdh > 0 && pdl > 0) ? (pp - range) : 0; }
                case "S3": { double pp = (pdh + pdl + pdc) / 3.0; return (pdh > 0 && pdl > 0) ? (pdl - 2.0 * (pdh - pp)) : 0; }

                // Fibs (Fibonacci retracements / extensions based on Prior Day Range)
                case "FibLevel1": return (pdh > 0 && range > 0) ? pdl + 0.236 * range : 0;
                case "FibLevel2": return (pdh > 0 && range > 0) ? pdl + 0.382 * range : 0;
                case "FibLevel3": return (pdh > 0 && range > 0) ? pdl + 0.500 * range : 0;
                case "FibLevel4": return (pdh > 0 && range > 0) ? pdl + 0.618 * range : 0;
                case "FibLevel5": return (pdh > 0 && range > 0) ? pdl + 0.786 * range : 0;
                case "FibLevel6": return (pdh > 0 && range > 0) ? pdh : 0;
                case "FibLevel7": return (pdh > 0 && range > 0) ? pdl + 1.272 * range : 0;
                case "FibLevel8": return (pdh > 0 && range > 0) ? pdl + 1.618 * range : 0;
                case "FibLevel9": return (pdh > 0 && range > 0) ? pdl - 0.272 * range : 0;
                case "FibLevel10": return (pdh > 0 && range > 0) ? pdl - 0.618 * range : 0;

                default: return 0;
            }
        }

        private double ReadRedTailVolumeProfile(string accessor)
        {
            // Fallbacks for Volume Profile levels (POC / VAH / VAL)
            double pdh = PriorDayOHLC().PriorHigh[0];
            double pdl = PriorDayOHLC().PriorLow[0];
            if (pdh <= 0 || pdl <= 0) return 0;

            switch (accessor)
            {
                case "CurrentPOCPlot":   return (High[0] + Low[0] + Close[0]) / 3.0;
                case "CurrentVAHPlot":   return High[0];
                case "CurrentVALPlot":   return Low[0];
                case "PrevDayPOCPlot":   return (pdh + pdl + PriorDayOHLC().PriorClose[0]) / 3.0;
                case "PrevDayVAHPlot":   return pdh - (pdh - pdl) * 0.15;
                case "PrevDayVALPlot":   return pdl + (pdh - pdl) * 0.15;
                case "OvernightPOCPlot": return (p12High > 0 && p12Low > 0) ? (p12High + p12Low) / 2.0 : 0;
                case "OvernightVAHPlot": return p12High;
                case "OvernightVALPlot": return p12Low;
                case "OvernightHighPlot":return p12High;
                case "OvernightLowPlot": return p12Low;
                default: return 0;
            }
        }

        private double ReadSessionRanges(string accessor)
        {
            switch (accessor)
            {
                case "Asia Range.High":   return asiaHigh;
                case "Asia Range.Low":    return asiaLow;
                case "Asia Range.Mid":    return asiaMid;
                case "London Range.High": return londonHigh;
                case "London Range.Low":  return londonLow;
                case "London Range.Mid":  return londonMid;
                case "Globex Range.High": return globexHigh;
                case "Globex Range.Low":  return globexLow;
                case "Globex Range.Mid":  return globexMid;
                case "IB.High":           return ibHigh;
                case "IB.Low":            return ibLow;
                case "IB.Mid":            return ibMid;
                default: return 0;
            }
        }

        private double ComputeInternalLevel(string accessor)
        {
            double pdh = PriorDayOHLC().PriorHigh[0];
            double pdl = PriorDayOHLC().PriorLow[0];
            double pdc = PriorDayOHLC().PriorClose[0];

            switch (accessor)
            {
                case "PriorDayMid":
                    return (pdh > 0 && pdl > 0) ? (pdh + pdl) / 2.0 : 0;

                case "Settlement":
                    return pdc;

                case "PriorWeekMid":
                    return (prevWeekHigh > 0 && prevWeekLow > 0) ? (prevWeekHigh + prevWeekLow) / 2.0 : 0;

                case "PriorWeekClose":
                    return prevWeekCloseVal > 0 ? prevWeekCloseVal : pdc;

                case "PriorMonthMid":
                    return (prevMonthHigh > 0 && prevMonthLow > 0) ? (prevMonthHigh + prevMonthLow) / 2.0 : 0;

                case "P12High": return p12High;
                case "P12Low": return p12Low;
                case "P12Mid": return (p12High > 0 && p12Low > 0) ? (p12High + p12Low) / 2.0 : 0;

                case "NYP12High": return nyP12High;
                case "NYP12Low": return nyP12Low;
                case "NYP12Mid": return (nyP12High > 0 && nyP12Low > 0) ? (nyP12High + nyP12Low) / 2.0 : 0;

                case "PrevNYP12High": return prevNyP12High;
                case "PrevNYP12Low": return prevNyP12Low;
                case "PrevNYP12Mid": return prevNyP12Mid;

                default:
                    return 0;
            }
        }

        private void UpdateP12Ranges(DateTime barEt, double high, double low)
        {
            int barMins = barEt.Hour * 60 + barEt.Minute;
            DateTime today = barEt.Date;

            if (barMins >= 18 * 60 && (p12Date != today || !p12Building))
            {
                if (nyP12High > 0 && nyP12Low > 0)
                {
                    prevNyP12High = nyP12High;
                    prevNyP12Low = nyP12Low;
                    prevNyP12Mid = (nyP12High + nyP12Low) / 2.0;
                }
                p12High = high;
                p12Low = low;
                p12Building = true;
                p12Date = today;
            }
            else if (p12Building)
            {
                bool inP12 = barMins >= 18 * 60 || barMins < 6 * 60;
                if (inP12)
                {
                    if (high > p12High) p12High = high;
                    if (low < p12Low) p12Low = low;
                }
                else if (barMins >= 6 * 60)
                {
                    p12Building = false;
                }
            }

            if (barMins >= 6 * 60 && (nyP12Date != today || !nyP12Building))
            {
                nyP12High = high;
                nyP12Low = low;
                nyP12Building = true;
                nyP12Date = today;
            }
            else if (nyP12Building)
            {
                bool inNyP12 = barMins >= 6 * 60 && barMins < 17 * 60;
                if (inNyP12)
                {
                    if (high > nyP12High) nyP12High = high;
                    if (low < nyP12Low) nyP12Low = low;
                }
                else if (barMins >= 17 * 60)
                {
                    nyP12Building = false;
                }
            }
        }

        private float ComputeProximityAlpha(double levelPrice, double currentPrice)
        {
            if (!ProximityFade) return levelPrice > 0 ? 0.7f : 0f;

            double threshold = ProximityThresholdPoints > 0
                ? (double)ProximityThresholdPoints
                : Math.Max(50, (High[0] - Low[0]) * 20);

            double distance = Math.Abs(levelPrice - currentPrice);

            if (distance >= threshold)
                return (float)FarFadeOpacity / 100f;
            if (distance <= threshold * 0.1)
                return (float)NearGlowOpacity / 100f;

            double t = (distance - threshold * 0.1) / (threshold * 0.9);
            float nearA = (float)NearGlowOpacity / 100f;
            float farA = (float)FarFadeOpacity / 100f;
            return nearA + (float)t * (farA - nearA);
        }

        #endregion

        #region Sweep Detection

        private void RunSweepDetection(double high, double low, double open, double close, DateTime barTime, int barIndex)
        {
            double range = high - low;
            if (range <= 0) return;

            double minDepth = tickSize * SweepMinDepthTicks;

            foreach (var level in activeLevels)
            {
                if (!level.IsActive || level.Swept) continue;
                if (level.Price <= 0) continue;
                if (level.Def.Role == LevelRole.ConfluenceFactor) continue;
                if (barIndex - level.SetBarIndex < 3) continue;

                bool crossed = level.Price >= low && level.Price <= high;
                if (!crossed) continue;

                SweepEvent sweep = null;

                if (SweepMode == SweepMode.Wick || SweepMode == SweepMode.Both)
                {
                    if (close < level.Price)
                    {
                        double sweepDepth = high - level.Price;
                        double upperWick = high - Math.Max(open, close);
                        double wickPct = (upperWick / range) * 100.0;
                        if (sweepDepth >= minDepth && wickPct >= SweepMinWickPct)
                        {
                            sweep = new SweepEvent
                            {
                                LevelName = level.Def.Name,
                                LevelPrice = level.Price,
                                SweepTime = barTime,
                                IsBullSweep = false,
                                SweepDepth = sweepDepth / tickSize,
                                WickPct = wickPct,
                                ClosePrice = close,
                                BarIndex = barIndex,
                                Mode = SweepMode.Wick
                            };
                        }
                    }
                    else if (close > level.Price)
                    {
                        double sweepDepth = level.Price - low;
                        double lowerWick = Math.Min(open, close) - low;
                        double wickPct = (lowerWick / range) * 100.0;
                        if (sweepDepth >= minDepth && wickPct >= SweepMinWickPct)
                        {
                            sweep = new SweepEvent
                            {
                                LevelName = level.Def.Name,
                                LevelPrice = level.Price,
                                SweepTime = barTime,
                                IsBullSweep = true,
                                SweepDepth = sweepDepth / tickSize,
                                WickPct = wickPct,
                                ClosePrice = close,
                                BarIndex = barIndex,
                                Mode = SweepMode.Wick
                            };
                        }
                    }
                }

                if (sweep == null && (SweepMode == SweepMode.BodyClose || SweepMode == SweepMode.Both))
                {
                    if (prevClose > level.Price && close < level.Price)
                    {
                        sweep = new SweepEvent
                        {
                            LevelName = level.Def.Name,
                            LevelPrice = level.Price,
                            SweepTime = barTime,
                            IsBullSweep = false,
                            SweepDepth = (high - level.Price) / tickSize,
                            WickPct = 0,
                            ClosePrice = close,
                            BarIndex = barIndex,
                            Mode = SweepMode.BodyClose
                        };
                    }
                    else if (prevClose < level.Price && close > level.Price)
                    {
                        sweep = new SweepEvent
                        {
                            LevelName = level.Def.Name,
                            LevelPrice = level.Price,
                            SweepTime = barTime,
                            IsBullSweep = true,
                            SweepDepth = (level.Price - low) / tickSize,
                            WickPct = 0,
                            ClosePrice = close,
                            BarIndex = barIndex,
                            Mode = SweepMode.BodyClose
                        };
                    }
                }

                if (sweep != null)
                {
                    sweep.IsStackSweep = level.StacksWith.Count > 0;
                    sweepEvents.Add(sweep);
                    todaySweeps.Add(sweep);
                    if (sweepEvents.Count > 500) sweepEvents.RemoveAt(0);

                    level.Swept = true;
                    level.SweptTime = barTime;
                    level.TouchCount++;
                }
            }

            UpdateStacking();
        }

        private void UpdateStacking()
        {
            double tolerance = tickSize * StackingToleranceTicks;
            var active = activeLevels.Where(l => l.IsActive && l.Price > 0).ToList();

            foreach (var level in active)
                level.StacksWith.Clear();

            for (int i = 0; i < active.Count; i++)
            {
                for (int j = i + 1; j < active.Count; j++)
                {
                    if (Math.Abs(active[i].Price - active[j].Price) <= tolerance)
                    {
                        active[i].StacksWith.Add(active[j].Def.Name);
                        active[j].StacksWith.Add(active[i].Def.Name);
                    }
                }
            }
        }

        #endregion

        #region Public API

        public List<LevelState> GetActiveLevels()
        {
            return activeLevels.Where(l => IsLevelEnabled(l) && l.IsActive && l.Price > 0).OrderBy(l => l.Price).ToList();
        }

        public List<LevelState> GetLevelsByCategory(LevelCategory cat)
        {
            return activeLevels.Where(l => IsLevelEnabled(l) && l.Def.Category == cat && l.IsActive && l.Price > 0).ToList();
        }

        public List<LevelState> GetSweepTargets()
        {
            return activeLevels.Where(l => IsLevelEnabled(l)
                && (l.Def.Role == LevelRole.SweepTarget || l.Def.Role == LevelRole.Both)
                && l.IsActive && l.Price > 0).ToList();
        }

        public LevelState GetLevel(string name)
        {
            return activeLevels.FirstOrDefault(l => l.Def.Name == name);
        }

        public double GetLevelPrice(string name)
        {
            var level = GetLevel(name);
            return level?.Price ?? 0;
        }

        public List<LevelState> GetStackedLevels(double price, double toleranceTicks)
        {
            double tolerance = tickSize * toleranceTicks;
            return activeLevels.Where(l => IsLevelEnabled(l) && l.IsActive && l.Price > 0 && Math.Abs(l.Price - price) <= tolerance).ToList();
        }

        public List<SweepEvent> GetSweepEvents() => sweepEvents;
        public List<SweepEvent> GetSweepsToday() => todaySweeps;
        public List<SweepEvent> GetSweepsByLevel(string name) => sweepEvents.Where(s => s.LevelName == name).ToList();
        public SweepEvent GetLastSweep() => sweepEvents.LastOrDefault();
        public bool WasLevelSwept(string name) => activeLevels.FirstOrDefault(l => l.Def.Name == name)?.Swept ?? false;

        public double MidnightOpen => sessionOpens.MidnightOpen;
        public double LondonOpen => sessionOpens.LondonOpen;
        public double NyOpen => sessionOpens.NyOpen;
        public double Get4HOpen(int hour) => sessionOpens.Get4HOpen(hour);
        public Dictionary<string, double> GetAllOpens() => sessionOpens.GetAllOpens();

        public double PDH => ReadPriorDayOHLC("PriorHigh");
        public double PDL => ReadPriorDayOHLC("PriorLow");
        public double PDC => ReadPriorDayOHLC("PriorClose");
        public double HOD => ReadCurrentDayOHL("CurrentHigh");
        public double LOD => ReadCurrentDayOHL("CurrentLow");

        #endregion

        #region Helpers

        private DateTime ToEt(DateTime dt)
        {
            if (etZone == null) return dt;
            try
            {
                if (dt.Kind == DateTimeKind.Utc)
                    return TimeZoneInfo.ConvertTimeFromUtc(dt, etZone);
                return dt;
            }
            catch { return dt; }
        }

        #endregion

        #region SharpDX Rendering & On-Chart Hover Tooltips

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            if (!DrawLines || ChartControl == null || RenderTarget == null) return;

            if (!resourcesCreated)
            {
                textFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Consolas",
                    SharpDX.DirectWrite.FontWeight.Normal, SharpDX.DirectWrite.FontStyle.Normal, 9f);
                tooltipFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI",
                    SharpDX.DirectWrite.FontWeight.SemiBold, SharpDX.DirectWrite.FontStyle.Normal, 11f);
                resourcesCreated = true;
            }

            var activeLevelsToDraw = GetActiveLevels();

            var categoryColors = new Dictionary<LevelCategory, SharpDX.Color>
            {
                { LevelCategory.PriorDay,     new SharpDX.Color(0x00, 0xE6, 0x76, 255) },
                { LevelCategory.PriorWeek,    new SharpDX.Color(0x69, 0xF0, 0xAE, 255) },
                { LevelCategory.PriorMonth,   new SharpDX.Color(0x00, 0xBC, 0xD4, 255) },
                { LevelCategory.SessionOpen,  new SharpDX.Color(0xFF, 0xFF, 0xFF, 255) },
                { LevelCategory.SessionRange, new SharpDX.Color(0x1E, 0x88, 0xE5, 255) },
                { LevelCategory.Intraday,     new SharpDX.Color(0x76, 0xFF, 0x03, 255) },
                { LevelCategory.VolumeProfile,new SharpDX.Color(0xFF, 0xA7, 0x26, 255) },
                { LevelCategory.Structure,    new SharpDX.Color(0xAB, 0x47, 0xBC, 255) },
                { LevelCategory.Pivot,        new SharpDX.Color(0x9E, 0x9E, 0x9E, 255) },
                { LevelCategory.Fib,          new SharpDX.Color(0xBD, 0xBD, 0xBD, 255) },
            };

            float xStart = chartControl.GetXByBarIndex(ChartBars, Math.Max(0, CurrentBar - 100));
            float xEnd = chartControl.GetXByBarIndex(ChartBars, CurrentBar) + (float)chartControl.Properties.BarDistance;

            double currentPrice = Close[0];

            foreach (var level in activeLevelsToDraw)
            {
                SharpDX.Color color = categoryColors.TryGetValue(level.Def.Category, out var c)
                    ? c : new SharpDX.Color(0x80, 0x80, 0x80, 255);

                float alpha;
                if (level.Swept)
                    alpha = 0.25f;
                else if (ProximityFade)
                    alpha = ComputeProximityAlpha(level.Price, currentPrice);
                else
                    alpha = 0.95f;

                var lineColor = new Color4(color.R / 255f, color.G / 255f, color.B / 255f, alpha);

                float y = chartScale.GetYByValue(level.Price);
                float lineWidth = level.StacksWith.Count > 0 ? 2f : 1f;

                var brush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, lineColor);
                RenderTarget.DrawLine(new SharpDX.Vector2(xStart, y), new SharpDX.Vector2(xEnd, y),
                    brush, lineWidth);

                float labelAlphaThreshold = (float)FarFadeOpacity / 100f + 0.05f;
                bool showLabel = DrawLabels && textFormat != null
                    && (!ProximityFade || alpha > labelAlphaThreshold || (level.Swept == false && level.StacksWith.Count > 0));

                if (showLabel)
                {
                    string nameStr = UseFullLevelNames && !string.IsNullOrEmpty(level.Def.FullName) ? level.Def.FullName : level.Def.Name;
                    string label = $"{nameStr} {level.Price:F1}";
                    if (level.Swept) label += " ✗";
                    if (level.StacksWith.Count > 0) label += " [STACK]";

                    var textLayout = new TextLayout(Core.Globals.DirectWriteFactory, label, textFormat,
                        float.MaxValue, float.MaxValue);
                    float labelX = xEnd + 4;
                    float labelY = y - (float)textLayout.Metrics.Height / 2;

                    var bgBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.04f, 0.06f, 0.08f, 0.90f));
                    var borderBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(color.R / 255f, color.G / 255f, color.B / 255f, 0.9f));
                    var labelBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(1.0f, 1.0f, 1.0f, 1.0f));

                    var bgRect = new RectangleF(labelX - 2, labelY - 1, (float)textLayout.Metrics.Width + 4,
                        (float)textLayout.Metrics.Height + 2);
                    RenderTarget.FillRectangle(bgRect, bgBrush);
                    RenderTarget.DrawRectangle(bgRect, borderBrush, 1.0f);

                    RenderTarget.DrawTextLayout(new SharpDX.Vector2(labelX, labelY), textLayout, labelBrush);

                    bgBrush.Dispose();
                    borderBrush.Dispose();
                    labelBrush.Dispose();
                    textLayout.Dispose();
                }

                brush.Dispose();
            }

            // Draw sweep markers
            if (DrawSweepMarkers && todaySweeps.Count > 0)
            {
                foreach (var sweep in todaySweeps)
                {
                    if (sweep.BarIndex < 0 || sweep.BarIndex > CurrentBar) continue;
                    float sx = chartControl.GetXByBarIndex(ChartBars, sweep.BarIndex);
                    float sy = chartScale.GetYByValue(sweep.LevelPrice);
                    float markerSize = 6f;

                    var markerColor = sweep.IsBullSweep
                        ? new SharpDX.Color(0x00, 0xC8, 0x53, 255)
                        : new SharpDX.Color(0xFF, 0x17, 0x44, 255);

                    var markerBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget,
                        new Color4(markerColor.R / 255f, markerColor.G / 255f, markerColor.B / 255f, 0.9f));

                    RenderTarget.FillEllipse(new SharpDX.Direct2D1.Ellipse(new SharpDX.Vector2(sx, sy), markerSize, markerSize), markerBrush);
                    markerBrush.Dispose();
                }
            }

            // ════════════════════════════════════════════════════════════════
            // Interactive On-Chart Mouse Hover Tooltips
            // ════════════════════════════════════════════════════════════════
            if (chartControl != null)
            {
                try
                {
                    var mousePos = System.Windows.Input.Mouse.GetPosition(chartControl);
                    float mouseX = (float)mousePos.X;
                    float mouseY = (float)mousePos.Y;

                    if (mouseX >= 0 && mouseX <= (float)chartControl.ActualWidth && mouseY >= 0 && mouseY <= (float)chartControl.ActualHeight)
                    {
                        LevelState hoveredLevel = null;
                        float minHitDist = 8.0f; // 8px Y tolerance

                        foreach (var level in activeLevelsToDraw)
                        {
                            float levelY = chartScale.GetYByValue(level.Price);
                            float distY = Math.Abs(mouseY - levelY);

                            if (distY <= minHitDist)
                            {
                                hoveredLevel = level;
                                minHitDist = distY;
                            }
                        }

                        if (hoveredLevel != null)
                        {
                            RenderHoverTooltip(chartControl, chartScale, hoveredLevel, mouseX, mouseY, currentPrice);
                        }
                    }
                }
                catch {}
            }
        }

        private void RenderHoverTooltip(ChartControl chartControl, ChartScale chartScale, LevelState level, float mouseX, float mouseY, double currentPrice)
        {
            string title = level.Def.FullName ?? level.Def.Name;
            string priceText = $"Price: {level.Price:N2}";
            string catText = $"Category: {level.Def.Category} | Source: {level.Def.Source}";
            string statusText = level.Swept
                ? $"Status: Swept ✗ (at {level.SweptTime:HH:mm ET})"
                : "Status: Active (Unswept)";

            double distPts = Math.Abs(level.Price - currentPrice);
            double distTicks = distPts / tickSize;
            string distText = $"Distance: {distPts:F2} pts ({distTicks:F0} ticks)";

            string stackText = level.StacksWith.Count > 0
                ? $"Stacked: {string.Join(", ", level.StacksWith)}"
                : null;

            List<string> lines = new List<string> { title, priceText, catText, statusText, distText };
            if (stackText != null) lines.Add(stackText);

            float width = 240f;
            float lineHeight = 16f;
            float height = lines.Count * lineHeight + 12f;

            float boxX = mouseX + 15;
            float boxY = mouseY - height / 2;

            if (boxX + width > (float)chartControl.ActualWidth)
                boxX = mouseX - width - 15;
            if (boxY < 10) boxY = 10;
            if (boxY + height > (float)chartControl.ActualHeight - 10)
                boxY = (float)chartControl.ActualHeight - height - 10;

            var bgRect = new RectangleF(boxX, boxY, width, height);

            var bgBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.06f, 0.08f, 0.12f, 0.94f));
            var borderBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.0f, 0.7f, 1.0f, 0.9f));
            var titleBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(1.0f, 1.0f, 1.0f, 1.0f));
            var textBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.85f, 0.88f, 0.92f, 1.0f));
            var sweptBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(1.0f, 0.35f, 0.35f, 1.0f));

            RenderTarget.FillRectangle(bgRect, bgBrush);
            RenderTarget.DrawRectangle(bgRect, borderBrush, 1.5f);

            float textY = boxY + 6;
            for (int i = 0; i < lines.Count; i++)
            {
                var curBrush = (i == 0) ? titleBrush : (lines[i].Contains("Swept")) ? sweptBrush : textBrush;
                var textLayout = new TextLayout(Core.Globals.DirectWriteFactory, lines[i], tooltipFormat ?? textFormat, width - 12, lineHeight + 2);
                RenderTarget.DrawTextLayout(new SharpDX.Vector2(boxX + 6, textY), textLayout, curBrush);
                textLayout.Dispose();
                textY += lineHeight;
            }

            bgBrush.Dispose();
            borderBrush.Dispose();
            titleBrush.Dispose();
            textBrush.Dispose();
            sweptBrush.Dispose();
        }

        #endregion
    }
}