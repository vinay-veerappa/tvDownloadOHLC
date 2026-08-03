// ═══════════════════════════════════════════════════════════════════════════
// LiquidityLevels.cs — Unified liquidity levels indicator for NT8
//
// Aggregates ALL liquidity levels (prior day/week/month, session opens,
// intraday, volume profile, structure) into one indicator with:
//   - Public API: GetActiveLevels(), GetSweepEvents(), GetLevelPrice()
//   - SessionOpensEngine: midnight/4H/London/NY opens
//   - SweepDetector: wick/body sweep detection on all SweepTarget levels
//   - SharpDX rendering: horizontal lines + labels + sweep markers + mouse hover tooltips
//
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
using VinayNS = NinjaTrader.NinjaScript.Indicators.Vinay;
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

        // Composed indicators for level price streams
        private Indicators.RedTail.RedTailKeyLevels redTailKeyLevels;
        private Indicators.RedTail.RedTailVolumeProfile redTailVolumeProfile;
        private Indicators.Vinay.SessionRanges sessionRanges;

        // Built-in indicators
        private double tickSize;
        private double prevClose;

        // SharpDX
        private SharpDX.DirectWrite.TextFormat textFormat;
        private SharpDX.DirectWrite.TextFormat tooltipFormat;
        private bool resourcesCreated;

        #endregion

        #region NinjaScript Properties — Category Toggles

        [NinjaScriptProperty]
        [Display(Name = "Show Prior Day Levels", Order = 1, GroupName = "0. Level Categories")]
        public bool ShowPriorDay { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Prior Week Levels", Order = 2, GroupName = "0. Level Categories")]
        public bool ShowPriorWeek { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Prior Month Levels", Order = 3, GroupName = "0. Level Categories")]
        public bool ShowPriorMonth { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Session Opens", Order = 4, GroupName = "0. Level Categories")]
        public bool ShowSessionOpens { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Session Ranges", Order = 5, GroupName = "0. Level Categories")]
        public bool ShowSessionRanges { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Intraday High/Low", Order = 6, GroupName = "0. Level Categories")]
        public bool ShowIntraday { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Volume Profile Levels", Order = 7, GroupName = "0. Level Categories")]
        public bool ShowVolumeProfile { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Structure Levels", Order = 8, GroupName = "0. Level Categories")]
        public bool ShowStructure { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Pivot Levels", Order = 9, GroupName = "0. Level Categories")]
        public bool ShowPivots { get; set; } = false;

        [NinjaScriptProperty]
        [Display(Name = "Show Fibonacci Levels", Order = 10, GroupName = "0. Level Categories")]
        public bool ShowFibs { get; set; } = false;

        #endregion

        #region NinjaScript Properties — General Config

        [NinjaScriptProperty]
        [Display(Name = "Show 4H Opens", Description = "Track 4-hour open prices", Order = 1, GroupName = "1. Session Opens")]
        public bool Show4HOpens { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Enable Sweep Detection", Order = 2, GroupName = "2. Sweeps")]
        public bool EnableSweepDetection { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Sweep Mode", Order = 3, GroupName = "2. Sweeps")]
        public SweepMode SweepMode { get; set; } = SweepMode.Wick;

        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Sweep Min Depth (ticks)", Order = 4, GroupName = "2. Sweeps")]
        public int SweepMinDepthTicks { get; set; } = 2;

        [NinjaScriptProperty]
        [Range(10, 100)]
        [Display(Name = "Sweep Min Wick %", Order = 5, GroupName = "2. Sweeps")]
        public double SweepMinWickPct { get; set; } = 40;

        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Stacking Tolerance (ticks)", Order = 6, GroupName = "2. Sweeps")]
        public int StackingToleranceTicks { get; set; } = 5;

        [NinjaScriptProperty]
        [Display(Name = "Draw Lines", Order = 7, GroupName = "3. Visuals")]
        public bool DrawLines { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Draw Labels", Order = 8, GroupName = "3. Visuals")]
        public bool DrawLabels { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Draw Sweep Markers", Order = 9, GroupName = "3. Visuals")]
        public bool DrawSweepMarkers { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Proximity Fade", Description = "Fade levels far from price; brighten when close", Order = 10, GroupName = "3. Visuals")]
        public bool ProximityFade { get; set; } = true;

        [NinjaScriptProperty]
        [Range(0, 500)]
        [Display(Name = "Proximity Threshold (pts)", Description = "Distance within which levels glow. 0 = auto (use ATR)", Order = 11, GroupName = "3. Visuals")]
        public int ProximityThresholdPoints { get; set; } = 0;

        [NinjaScriptProperty]
        [Range(0, 100)]
        [Display(Name = "Far Fade Opacity %", Description = "Opacity for far levels (0=hidden, 100=full)", Order = 12, GroupName = "3. Visuals")]
        public int FarFadeOpacity { get; set; } = 15;

        [NinjaScriptProperty]
        [Range(0, 100)]
        [Display(Name = "Near Glow Opacity %", Description = "Opacity for near levels (0=hidden, 100=full)", Order = 13, GroupName = "3. Visuals")]
        public int NearGlowOpacity { get; set; } = 90;

        [NinjaScriptProperty]
        [Display(Name = "Use Full Level Names", Description = "Show full level names (e.g., 'Prev Month High', 'Prior Day High') instead of abbreviations ('PMH', 'PDH')", Order = 14, GroupName = "3. Visuals")]
        public bool UseFullLevelNames { get; set; } = true;

        #endregion

        #region Helper: Category Filtering

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

        #endregion

        #region OnStateChange

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Unified liquidity levels indicator (52+ levels + session opens + sweep detection + tooltips)";
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

                // Instantiate composed indicators for real price feeds
                try
                {
                    redTailKeyLevels = new Indicators.RedTail.RedTailKeyLevels();
                } catch {}

                try
                {
                    redTailVolumeProfile = new Indicators.RedTail.RedTailVolumeProfile();
                } catch {}

                try
                {
                    sessionRanges = new Indicators.Vinay.SessionRanges();
                } catch {}
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

                // Reset sweep flags on all levels
                foreach (var level in activeLevels)
                    level.Swept = false;
            }

            // Update session opens
            sessionOpens.OnBarUpdate(barTimeEt, openP, CurrentBar);

            // Update P12 / NY P12 ranges
            UpdateP12Ranges(barTimeEt, highP, lowP);

            // Update level prices from sources
            UpdateLevelPrices();

            // Run sweep detection
            if (EnableSweepDetection)
                RunSweepDetection(highP, lowP, openP, closeP, barTimeEt, CurrentBar);

            prevClose = closeP;
        }

        #endregion

        #region Level Price Updates

        private void UpdateLevelPrices()
        {
            foreach (var level in activeLevels)
            {
                if (!IsCategoryEnabled(level.Def.Category))
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
            if (redTailKeyLevels == null || redTailKeyLevels.Values == null) return 0;
            try
            {
                switch (accessor)
                {
                    case "Pp":  return redTailKeyLevels.Values[0][0];
                    case "R1":  return redTailKeyLevels.Values[1][0];
                    case "R2":  return redTailKeyLevels.Values[2][0];
                    case "R3":  return redTailKeyLevels.Values[3][0];
                    case "S1":  return redTailKeyLevels.Values[4][0];
                    case "S2":  return redTailKeyLevels.Values[5][0];
                    case "S3":  return redTailKeyLevels.Values[6][0];
                    case "PDH": return redTailKeyLevels.Values[13][0];
                    case "PDL": return redTailKeyLevels.Values[14][0];
                    case "PWH": return redTailKeyLevels.Values[15][0];
                    case "PWL": return redTailKeyLevels.Values[16][0];
                    case "PMH": return redTailKeyLevels.Values[17][0];
                    case "PML": return redTailKeyLevels.Values[18][0];
                    case "MH":  return redTailKeyLevels.Values[19][0];
                    case "ML":  return redTailKeyLevels.Values[20][0];
                    case "GH":  return redTailKeyLevels.Values[21][0];
                    case "GL":  return redTailKeyLevels.Values[22][0];
                    case "NYH": return redTailKeyLevels.Values[23][0];
                    case "NYL": return redTailKeyLevels.Values[24][0];
                    case "FibLevel1":  return redTailKeyLevels.Values[25][0];
                    case "FibLevel2":  return redTailKeyLevels.Values[26][0];
                    case "FibLevel3":  return redTailKeyLevels.Values[27][0];
                    case "FibLevel4":  return redTailKeyLevels.Values[28][0];
                    case "FibLevel5":  return redTailKeyLevels.Values[29][0];
                    case "FibLevel6":  return redTailKeyLevels.Values[30][0];
                    case "FibLevel7":  return redTailKeyLevels.Values[31][0];
                    case "FibLevel8":  return redTailKeyLevels.Values[32][0];
                    case "FibLevel9":  return redTailKeyLevels.Values[33][0];
                    case "FibLevel10": return redTailKeyLevels.Values[34][0];
                    default: return 0;
                }
            }
            catch { return 0; }
        }

        private double ReadRedTailVolumeProfile(string accessor)
        {
            if (redTailVolumeProfile == null || redTailVolumeProfile.Values == null) return 0;
            try
            {
                switch (accessor)
                {
                    case "CurrentPOCPlot":   return redTailVolumeProfile.Values[0][0];
                    case "CurrentVAHPlot":   return redTailVolumeProfile.Values[1][0];
                    case "CurrentVALPlot":   return redTailVolumeProfile.Values[2][0];
                    case "PrevDayPOCPlot":   return redTailVolumeProfile.Values[3][0];
                    case "PrevDayVAHPlot":   return redTailVolumeProfile.Values[4][0];
                    case "PrevDayVALPlot":   return redTailVolumeProfile.Values[5][0];
                    case "OvernightPOCPlot": return redTailVolumeProfile.Values[8][0];
                    case "OvernightVAHPlot": return redTailVolumeProfile.Values[9][0];
                    case "OvernightVALPlot": return redTailVolumeProfile.Values[10][0];
                    case "OvernightHighPlot":return redTailVolumeProfile.Values[11][0];
                    case "OvernightLowPlot": return redTailVolumeProfile.Values[12][0];
                    default: return 0;
                }
            }
            catch { return 0; }
        }

        private double ReadSessionRanges(string accessor)
        {
            if (sessionRanges == null) return 0;
            try
            {
                switch (accessor)
                {
                    case "Asia Range.High":   return sessionRanges.AsiaHigh;
                    case "Asia Range.Low":    return sessionRanges.AsiaLow;
                    case "Asia Range.Mid":    return (sessionRanges.AsiaHigh > 0 && sessionRanges.AsiaLow > 0) ? (sessionRanges.AsiaHigh + sessionRanges.AsiaLow) / 2.0 : 0;
                    case "London Range.High": return sessionRanges.LondonHigh;
                    case "London Range.Low":  return sessionRanges.LondonLow;
                    case "London Range.Mid":  return (sessionRanges.LondonHigh > 0 && sessionRanges.LondonLow > 0) ? (sessionRanges.LondonHigh + sessionRanges.LondonLow) / 2.0 : 0;
                    case "London OR.Mid":     return (sessionRanges.LondonOrHigh > 0 && sessionRanges.LondonOrLow > 0) ? (sessionRanges.LondonOrHigh + sessionRanges.LondonOrLow) / 2.0 : 0;
                    case "Globex Range.High": return sessionRanges.GlobexHigh;
                    case "Globex Range.Low":  return sessionRanges.GlobexLow;
                    case "Globex Range.Mid":  return (sessionRanges.GlobexHigh > 0 && sessionRanges.GlobexLow > 0) ? (sessionRanges.GlobexHigh + sessionRanges.GlobexLow) / 2.0 : 0;
                    case "IB.High":           return sessionRanges.IbHigh;
                    case "IB.Low":            return sessionRanges.IBLow;
                    case "IB.Mid":            return sessionRanges.IBMid;
                    default: return 0;
                }
            }
            catch { return 0; }
        }

        // ═══ Compute internal levels (mids, settlement, PWC, P12, NY P12) ═══
        private double prevWeekClose = 0;
        private DateTime prevWeekCloseDate = DateTime.MinValue;

        // P12 tracking (18:00-06:00 ET overnight range)
        private double p12High, p12Low;
        private bool p12Building;
        private DateTime p12Date;

        // NY P12 tracking (06:00-17:00 ET NY session range)
        private double nyP12High, nyP12Low;
        private bool nyP12Building;
        private DateTime nyP12Date;

        // Prev NY P12 (previous day's NY P12)
        private double prevNyP12High, prevNyP12Low, prevNyP12Mid;

        private double ComputeInternalLevel(string accessor)
        {
            double pdh = ReadRedTailKeyLevels("PDH");
            if (pdh <= 0) pdh = PriorDayOHLC().PriorHigh[0];

            double pdl = ReadRedTailKeyLevels("PDL");
            if (pdl <= 0) pdl = PriorDayOHLC().PriorLow[0];

            double pdc = PriorDayOHLC().PriorClose[0];

            double pwh = ReadRedTailKeyLevels("PWH");
            double pwl = ReadRedTailKeyLevels("PWL");
            double pmh = ReadRedTailKeyLevels("PMH");
            double pml = ReadRedTailKeyLevels("PML");

            switch (accessor)
            {
                case "PriorDayMid":
                    return (pdh > 0 && pdl > 0) ? (pdh + pdl) / 2.0 : 0;

                case "Settlement":
                    return pdc;

                case "PriorWeekMid":
                    return (pwh > 0 && pwl > 0) ? (pwh + pwl) / 2.0 : 0;

                case "PriorWeekClose":
                    return UpdatePriorWeekClose();

                case "PriorMonthMid":
                    return (pmh > 0 && pml > 0) ? (pmh + pml) / 2.0 : 0;

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

        private double UpdatePriorWeekClose()
        {
            DateTime barEt = ToEt(Time[0]);
            DayOfWeek dow = barEt.DayOfWeek;

            if (dow == DayOfWeek.Friday && barEt.Hour >= 15)
            {
                if (prevWeekCloseDate.Date != barEt.Date)
                {
                    prevWeekClose = Close[0];
                    prevWeekCloseDate = barEt.Date;
                }
            }

            return prevWeekClose;
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
            return activeLevels.Where(l => IsCategoryEnabled(l.Def.Category) && l.IsActive && l.Price > 0).OrderBy(l => l.Price).ToList();
        }

        public List<LevelState> GetLevelsByCategory(LevelCategory cat)
        {
            return activeLevels.Where(l => IsCategoryEnabled(cat) && l.Def.Category == cat && l.IsActive && l.Price > 0).ToList();
        }

        public List<LevelState> GetSweepTargets()
        {
            return activeLevels.Where(l => IsCategoryEnabled(l.Def.Category)
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
            return activeLevels.Where(l => IsCategoryEnabled(l.Def.Category) && l.IsActive && l.Price > 0 && Math.Abs(l.Price - price) <= tolerance).ToList();
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

        public double PDH => ReadRedTailKeyLevels("PDH");
        public double PDL => ReadRedTailKeyLevels("PDL");
        public double PDC => PriorDayOHLC().PriorClose[0];
        public double HOD => CurrentDayOHL().CurrentHigh[0];
        public double LOD => CurrentDayOHL().CurrentLow[0];

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

            RenderTarget.BeginDraw();

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
                    alpha = 0.2f;
                else if (ProximityFade)
                    alpha = ComputeProximityAlpha(level.Price, currentPrice);
                else
                    alpha = 0.7f;

                var lineColor = new Color4(color.R / 255f, color.G / 255f, color.B / 255f, alpha);

                float y = chartScale.GetYByValue(level.Price);
                float lineWidth = level.StacksWith.Count > 0 ? 2f : 1f;

                var brush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, lineColor);
                RenderTarget.DrawLine(new SharpDX.Vector2(xStart, y), new SharpDX.Vector2(xEnd, y),
                    brush, lineWidth);

                float labelAlphaThreshold = (float)FarFadeOpacity / 100f + 0.05f;
                bool showLabel = DrawLabels && textFormat != null
                    && (!ProximityFade || alpha > labelAlphaThreshold || level.Swept == false && level.StacksWith.Count > 0);

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

                    var bgBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0, 0, 0, 0.6f));
                    var bgRect = new RectangleF(labelX - 2, labelY, (float)textLayout.Metrics.Width + 4,
                        (float)textLayout.Metrics.Height);
                    RenderTarget.FillRectangle(bgRect, bgBrush);
                    bgBrush.Dispose();

                    RenderTarget.DrawTextLayout(new SharpDX.Vector2(labelX, labelY), textLayout, brush);
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