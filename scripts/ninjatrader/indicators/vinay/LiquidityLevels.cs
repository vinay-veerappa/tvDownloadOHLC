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
using System.IO;
using System.Linq;
using System.Speech.Synthesis;
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
        #region Private Fields — State & Engines

        private List<LevelState> activeLevels;
        private DateTime lastDate = DateTime.MinValue;
        private double prevClose;
        private TimeZoneInfo etZone;
        private List<SweepEvent> sweepEvents;
        private List<SweepEvent> todaySweeps;

        // Open & Settlement Tracking Fields
        private double currentMonthOpen, prevMonthOpen;
        private double currentWeekOpen, prevWeekOpen;
        private double tueOpen, wedOpen, thuOpen, friOpen;
        private double settlementPrice;
        private double dailySettlementPrice;

        // Native Engines & Helpers
        private SessionOpensEngine sessionOpens;

        // Cached sub-indicator references (must be initialized in State.Configure)
        private NinjaTrader.NinjaScript.Indicators.PriorDayOHLC _priorDayOHLC;
        private NinjaTrader.NinjaScript.Indicators.CurrentDayOHL _currentDayOHL;

        // Origin Bar Tracking (where levels originated)
        private int dayStartBar = -1;
        private int weekStartBar = -1;
        private int monthStartBar = -1;
        private int asiaStartBar = -1;
        private int londonStartBar = -1;
        private int globexStartBar = -1;
        private int ibStartBar = -1;

        // Native Week & Month Tracking
        private double prevWeekHigh, prevWeekLow, prevWeekCloseVal;
        private double curWeekHigh, curWeekLow, curWeekClose, curWeekOpen;
        private int curWeekNum = -1;
        private DateTime lastGlobexTrackingDate = DateTime.MinValue;

        private double prevMonthHigh, prevMonthLow, prevMonthCloseVal;
        private double curMonthHigh, curMonthLow, curMonthClose, curMonthOpen;
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

        // Voice Alerts — pre-generated WAV files (edge-tts neural voices)
        private Dictionary<string, string> voiceAlertPaths = new Dictionary<string, string>();
        private Dictionary<string, DateTime> lastAlertTime = new Dictionary<string, DateTime>();
        private string instrumentName = "";

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
        public bool ShowVolumeProfile { get; set; } = false;

        [Display(Name = "Show Structure Levels", Order = 8, GroupName = "0. Level Categories (Master)")]
        public bool ShowStructure { get; set; } = false;

        [Display(Name = "Show Pivot Levels", Order = 9, GroupName = "0. Level Categories (Master)")]
        public bool ShowPivots { get; set; } = false;

        [Display(Name = "Show Fibonacci Levels", Order = 10, GroupName = "0. Level Categories (Master)")]
        public bool ShowFibs { get; set; } = false;

        #endregion

        #region NinjaScript Properties — Granular Level Toggles

        // ── 1. Prior Day / Week / Month ──
        [Display(Name = "Prior Day High (PDH)", Order = 1, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPDH { get; set; } = true;

        [Display(Name = "Prior Day Low (PDL)", Order = 2, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPDL { get; set; } = true;

        [Display(Name = "Prior Day Close (PDC)", Order = 3, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPDC { get; set; } = false;

        [Display(Name = "Prior Day Open (PDO)", Order = 4, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPDO { get; set; } = false;

        [Display(Name = "Daily Settlement", Order = 5, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowSettlement { get; set; } = false;

        [Display(Name = "Prior Week High (PWH)", Order = 6, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPWH { get; set; } = true;

        [Display(Name = "Prior Week Low (PWL)", Order = 7, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPWL { get; set; } = true;

        [Display(Name = "Prior Week Close (PWC)", Order = 8, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPWC { get; set; } = false;

        [Display(Name = "Prior Week Open (PWO)", Order = 9, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPWO { get; set; } = false;

        [Display(Name = "Prev Month High (PMH)", Order = 10, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPMH { get; set; } = true;

        [Display(Name = "Prev Month Low (PML)", Order = 11, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPML { get; set; } = true;

        [Display(Name = "Prev Month Mid (PMM)", Order = 12, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPMM { get; set; } = false;

        [Display(Name = "Prev Month Open (PMO)", Order = 13, GroupName = "1. Toggles — Prior Day/Week/Month")]
        public bool ShowPMO { get; set; } = false;

        // ── 2. Session Opens ──
        [Display(Name = "Midnight Open (00:00 ET)", Order = 1, GroupName = "2. Toggles — Session Opens")]
        public bool ShowMidnightOpen { get; set; } = true;

        [Display(Name = "London Open (03:00 ET)", Order = 2, GroupName = "2. Toggles — Session Opens")]
        public bool ShowLondonOpen { get; set; } = true;

        [Display(Name = "RTH / NY Open (09:30 ET)", Order = 3, GroupName = "2. Toggles — Session Opens")]
        public bool ShowRTHOpen { get; set; } = true;

        [Display(Name = "Globex Open (18:00 ET)", Order = 4, GroupName = "2. Toggles — Session Opens")]
        public bool ShowGlobexOpen { get; set; } = false;

        [Display(Name = "Open 04:00 ET", Order = 5, GroupName = "2. Toggles — Session Opens")]
        public bool ShowOpen04H { get; set; } = false;

        [Display(Name = "Open 08:00 ET", Order = 6, GroupName = "2. Toggles — Session Opens")]
        public bool ShowOpen08H { get; set; } = false;

        [Display(Name = "Open 12:00 ET", Order = 7, GroupName = "2. Toggles — Session Opens")]
        public bool ShowOpen12H { get; set; } = false;

        [Display(Name = "Open 16:00 ET", Order = 8, GroupName = "2. Toggles — Session Opens")]
        public bool ShowOpen16H { get; set; } = false;

        [Display(Name = "Open 20:00 ET", Order = 9, GroupName = "2. Toggles — Session Opens")]
        public bool ShowOpen20H { get; set; } = false;

        [Display(Name = "Tuesday Open", Order = 10, GroupName = "2. Toggles — Session Opens")]
        public bool ShowTueOpen { get; set; } = false;

        [Display(Name = "Wednesday Open", Order = 11, GroupName = "2. Toggles — Session Opens")]
        public bool ShowWedOpen { get; set; } = false;

        [Display(Name = "Thursday Open", Order = 12, GroupName = "2. Toggles — Session Opens")]
        public bool ShowThuOpen { get; set; } = false;

        [Display(Name = "Friday Open", Order = 13, GroupName = "2. Toggles — Session Opens")]
        public bool ShowFriOpen { get; set; } = false;

        // ── 3. Session Ranges ──
        [Display(Name = "Asia Range High/Low", Order = 1, GroupName = "3. Toggles — Session Ranges")]
        public bool ShowAsiaRange { get; set; } = true;

        [Display(Name = "London Range High/Low", Order = 2, GroupName = "3. Toggles — Session Ranges")]
        public bool ShowLondonRange { get; set; } = true;

        [Display(Name = "Globex Range High/Low", Order = 3, GroupName = "3. Toggles — Session Ranges")]
        public bool ShowGlobexRange { get; set; } = true;

        [Display(Name = "Initial Balance High/Low", Order = 4, GroupName = "3. Toggles — Session Ranges")]
        public bool ShowIB { get; set; } = true;

        [Display(Name = "Overnight P12 Range (18:00-06:00 ET)", Order = 5, GroupName = "3. Toggles — Session Ranges")]
        public bool ShowP12 { get; set; } = false;

        [Display(Name = "NY P12 Range (06:00-17:00 ET)", Order = 6, GroupName = "3. Toggles — Session Ranges")]
        public bool ShowNYP12 { get; set; } = false;

        // ── 4. Pivots & Fibs ──
        [Display(Name = "Pivot Point (PP)", Order = 1, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowPivotPP { get; set; } = false;

        [Display(Name = "Resistance 1 / Support 1", Order = 2, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowPivotR1S1 { get; set; } = false;

        [Display(Name = "Resistance 2 / Support 2", Order = 3, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowPivotR2S2 { get; set; } = false;

        [Display(Name = "Resistance 3 / Support 3", Order = 4, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowPivotR3S3 { get; set; } = false;

        [Display(Name = "Fib 23.6%", Order = 5, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowFib236 { get; set; } = false;

        [Display(Name = "Fib 38.2%", Order = 6, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowFib382 { get; set; } = false;

        [Display(Name = "Fib 50.0%", Order = 7, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowFib500 { get; set; } = false;

        [Display(Name = "Fib 61.8%", Order = 8, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowFib618 { get; set; } = false;

        [Display(Name = "Fib 78.6%", Order = 9, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowFib786 { get; set; } = false;

        [Display(Name = "Fib 100%", Order = 10, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowFib100 { get; set; } = false;

        [Display(Name = "Fib Extensions (127.2%, 161.8%, -27.2%, -61.8%)", Order = 11, GroupName = "4. Toggles — Pivots & Fibs")]
        public bool ShowFibExt { get; set; } = false;

        // ── 5. Volume Profile & Intraday ──
        [Display(Name = "High of Day (HOD)", Order = 1, GroupName = "5. Toggles — Volume Profile & Intraday")]
        public bool ShowHOD { get; set; } = true;

        [Display(Name = "Low of Day (LOD)", Order = 2, GroupName = "5. Toggles — Volume Profile & Intraday")]
        public bool ShowLOD { get; set; } = true;

        [Display(Name = "Current Session POC", Order = 3, GroupName = "5. Toggles — Volume Profile & Intraday")]
        public bool ShowCurrentPOC { get; set; } = false;

        [Display(Name = "Current Session Value Area (VAH/VAL)", Order = 4, GroupName = "5. Toggles — Volume Profile & Intraday")]
        public bool ShowCurrentVA { get; set; } = false;

        [Display(Name = "Prev Day POC", Order = 5, GroupName = "5. Toggles — Volume Profile & Intraday")]
        public bool ShowPrevDayPOC { get; set; } = false;

        [Display(Name = "Prev Day Value Area (VAH/VAL)", Order = 6, GroupName = "5. Toggles — Volume Profile & Intraday")]
        public bool ShowPrevDayVA { get; set; } = false;

        [Display(Name = "Overnight POC / VAH / VAL", Order = 7, GroupName = "5. Toggles — Volume Profile & Intraday")]
        public bool ShowOvernightPOC { get; set; } = false;

        #endregion

        #region NinjaScript Properties — General Config

        [Display(Name = "Enable Sweep Detection", Order = 1, GroupName = "6. Sweeps & Proximity")]
        public bool EnableSweepDetection { get; set; } = true;

        [Display(Name = "Sweep Mode", Order = 2, GroupName = "6. Sweeps & Proximity")]
        public SweepMode SweepMode { get; set; } = SweepMode.Wick;

        [Display(Name = "Min Sweep Depth (ticks)", Order = 3, GroupName = "6. Sweeps & Proximity")]
        public int SweepMinDepthTicks { get; set; } = 1;

        [Display(Name = "Min Wick % of Bar Range", Order = 4, GroupName = "6. Sweeps & Proximity")]
        public double SweepMinWickPct { get; set; } = 25.0;

        [Display(Name = "Stacking Tolerance (ticks)", Order = 5, GroupName = "6. Sweeps & Proximity")]
        public int StackingToleranceTicks { get; set; } = 5;

        [Display(Name = "Proximity Fade", Order = 6, GroupName = "6. Sweeps & Proximity")]
        public bool ProximityFade { get; set; } = false;

        [Display(Name = "Proximity Threshold (points)", Order = 7, GroupName = "6. Sweeps & Proximity")]
        public int ProximityThresholdPoints { get; set; } = 0;

        [Display(Name = "Near Glow Opacity %", Order = 8, GroupName = "6. Sweeps & Proximity")]
        public int NearGlowOpacity { get; set; } = 100;

        [Display(Name = "Far Fade Opacity %", Order = 9, GroupName = "6. Sweeps & Proximity")]
        public int FarFadeOpacity { get; set; } = 25;

        [Display(Name = "Draw Lines", Order = 1, GroupName = "7. Visuals & Layout")]
        public bool DrawLines { get; set; } = true;

        [Display(Name = "Draw Labels", Order = 2, GroupName = "7. Visuals & Layout")]
        public bool DrawLabels { get; set; } = true;

        [Display(Name = "Draw Sweep Markers", Order = 3, GroupName = "7. Visuals & Layout")]
        public bool DrawSweepMarkers { get; set; } = true;

        [Display(Name = "Use Full Level Names", Order = 4, GroupName = "7. Visuals & Layout")]
        public bool UseFullLevelNames { get; set; } = false;

        [Display(Name = "Label Placement", Description = "Where to draw line labels: RightMargin (default), Origin, or Both", Order = 5, GroupName = "7. Visuals & Layout")]
        public LabelPlacement LabelPlacement { get; set; } = LabelPlacement.RightMargin;

        [Display(Name = "Font Size", Description = "Font size for chart label badges and hover tooltips (default: 11)", Order = 6, GroupName = "7. Visuals & Layout")]
        public int FontSize { get; set; } = 11;

        #endregion

        #region NinjaScript Properties — Voice Alerts

        [Display(Name = "Enable Voice Alerts", Description = "Pre-generate neural voice WAV files and play them when levels are swept", Order = 1, GroupName = "8. Voice Alerts")]
        public bool EnableVoiceAlerts { get; set; } = false;

        [Display(Name = "Voice Gender", Description = "Female or Male neural voice", Order = 2, GroupName = "8. Voice Alerts")]
        public VoiceGenderSelection VoiceGender { get; set; } = VoiceGenderSelection.Female;

        [Display(Name = "Voice Rate (-10 to 10)", Description = "Speech rate speed (-10 slowest, 10 fastest)", Order = 3, GroupName = "8. Voice Alerts")]
        public int VoiceRate { get; set; } = 0;

        [Display(Name = "Alert Cooldown (seconds)", Description = "Minimum seconds between alerts for the same level", Order = 4, GroupName = "8. Voice Alerts")]
        [Range(5, 300)]
        public int AlertCooldownSeconds { get; set; } = 30;

        [Display(Name = "Fallback Sound", Description = "NT8 sound file to use if voice WAV generation fails", Order = 5, GroupName = "8. Voice Alerts")]
        public string AlertFallbackSound { get; set; } = "Alert1.wav";

        #endregion

        #region State Initialization

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Displays key liquidity levels (PDH/PDL, PWH/PWL, PMH/PML, Session Opens, Session Ranges, Pivots, Fibs) with hover tooltips, voice alerts, and origin-anchored rays. v1.3.0";
                Name = "LiquidityLevels";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawHorizontalGridLines = false;
                DrawVerticalGridLines = false;
                PaintPriceMarkers = false;
                ScaleJustification = ScaleJustification.Right;
                IsSuspendedWhileInactive = true;
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsArray[0].Instrument.FullName, BarsPeriodType.Day, 1);

                // Cache sub-indicator references here so their AddDataSeries calls happen during Configure
                _priorDayOHLC = PriorDayOHLC();
                _currentDayOHL = CurrentDayOHL();

                sweepEvents = new List<SweepEvent>();
                todaySweeps = new List<SweepEvent>();
                sessionOpens = new SessionOpensEngine(include4H: true);
                activeLevels = new List<LevelState>();
                foreach (var def in LiquidityLevelsCatalog.GetAllLevels())
                    activeLevels.Add(new LevelState(def));

                try
                {
                    etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                }
                catch
                {
                    etZone = TimeZoneInfo.FindSystemTimeZoneById("America/New_York");
                }
            }
            else if (State == State.Terminated)
            {
                if (textFormat != null) textFormat.Dispose();
                if (tooltipFormat != null) tooltipFormat.Dispose();
                resourcesCreated = false;
            }
            else if (State == State.DataLoaded)
            {
                if (EnableVoiceAlerts)
                {
                    instrumentName = Instrument != null ? Instrument.MasterInstrument.Name : "Instrument";
                    // Run async so chart loading isn't blocked by voice generation
                    System.Threading.ThreadPool.QueueUserWorkItem(_ =>
                    {
                        try { GenerateVoiceAlerts(); }
                        catch (Exception ex) { Print("LiquidityLevels: Voice gen error: " + ex.Message); }
                    });
                }
            }
        }

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

            // 1. Prior Day / Week / Month
            if (name == "PDH" && !ShowPDH) return false;
            if (name == "PDL" && !ShowPDL) return false;
            if (name == "PDC" && !ShowPDC) return false;
            if (name == "PDO" && !ShowPDO) return false;
            if (name == "Settlement" && !ShowSettlement) return false;

            if (name == "PWH" && !ShowPWH) return false;
            if (name == "PWL" && !ShowPWL) return false;
            if (name == "PWC" && !ShowPWC) return false;
            if (name == "PWO" && !ShowPWO) return false;

            if (name == "PMH" && !ShowPMH) return false;
            if (name == "PML" && !ShowPML) return false;
            if (name == "PMM" && !ShowPMM) return false;
            if (name == "PMO" && !ShowPMO) return false;

            // 2. Session Opens
            if (name == "MidnightOpen" && !ShowMidnightOpen) return false;
            if (name == "LondonOpen" && !ShowLondonOpen) return false;
            if ((name == "RTHOpen" || name == "NYOpen") && !ShowRTHOpen) return false;
            if (name == "GlobexOpen" && !ShowGlobexOpen) return false;

            if (name == "Open_04H" && !ShowOpen04H) return false;
            if (name == "Open_08H" && !ShowOpen08H) return false;
            if (name == "Open_12H" && !ShowOpen12H) return false;
            if (name == "Open_16H" && !ShowOpen16H) return false;
            if (name == "Open_20H" && !ShowOpen20H) return false;

            if (name == "TueOpen" && !ShowTueOpen) return false;
            if (name == "WedOpen" && !ShowWedOpen) return false;
            if (name == "ThuOpen" && !ShowThuOpen) return false;
            if (name == "FriOpen" && !ShowFriOpen) return false;

            // 3. Session Ranges
            if ((name == "AsiaH" || name == "AsiaL" || name == "AsiaMid") && !ShowAsiaRange) return false;
            if ((name == "LonH" || name == "LonL" || name == "LonMid" || name == "LonOrMid") && !ShowLondonRange) return false;
            if ((name == "GlbH" || name == "GlbL" || name == "GlbMid") && !ShowGlobexRange) return false;
            if ((name == "IBH" || name == "IBL" || name == "IBMid") && !ShowIB) return false;
            if (name.StartsWith("P12") && !ShowP12) return false;
            if (name.Contains("NYP12") && !ShowNYP12) return false;

            // 4. Pivots & Fibs
            if (name == "PP" && !ShowPivotPP) return false;
            if ((name == "R1" || name == "S1") && !ShowPivotR1S1) return false;
            if ((name == "R2" || name == "S2") && !ShowPivotR2S2) return false;
            if ((name == "R3" || name == "S3") && !ShowPivotR3S3) return false;

            if (name == "Fib 23.6%" && !ShowFib236) return false;
            if (name == "Fib 38.2%" && !ShowFib382) return false;
            if (name == "Fib 50.0%" && !ShowFib500) return false;
            if (name == "Fib 61.8%" && !ShowFib618) return false;
            if (name == "Fib 78.6%" && !ShowFib786) return false;
            if (name == "Fib 100%" && !ShowFib100) return false;
            if ((name == "Fib 127.2%" || name == "Fib 161.8%" || name == "Fib -27.2%" || name == "Fib -61.8%") && !ShowFibExt) return false;

            // 5. Volume Profile & Intraday
            if (name == "HOD" && !ShowHOD) return false;
            if (name == "LOD" && !ShowLOD) return false;

            if (name.Contains("CurrentPOC") && !ShowCurrentPOC) return false;
            if ((name.Contains("CurrentVAH") || name.Contains("CurrentVAL")) && !ShowCurrentVA) return false;
            if (name.Contains("PrevDayPOC") && !ShowPrevDayPOC) return false;
            if ((name.Contains("PrevDayVAH") || name.Contains("PrevDayVAL")) && !ShowPrevDayVA) return false;
            if (name.Contains("Overnight") && !ShowOvernightPOC) return false;

            return true;
        }

        #endregion

        #region OnBarUpdate

        protected override void OnBarUpdate()
        {
            if (BarsInProgress == 1)
            {
                if (CurrentBar >= 1)
                {
                    dailySettlementPrice = Closes[1][1];
                }
                return;
            }

            if (CurrentBar < 1)
            {
                prevClose = Close[0];
                return;
            }

            DateTime barTimeEt = ToEt(Time[0]);
            double openP = Open[0];
            double highP = High[0];
            double lowP = Low[0];
            double closeP = Close[0];

            // Day rollover — use Globex 18:00 ET boundary for futures
            int barMins = barTimeEt.Hour * 60 + barTimeEt.Minute;
            DateTime globexDate = barMins >= 18 * 60 ? barTimeEt.Date.AddDays(1) : barTimeEt.Date;

            if (globexDate != lastDate)
            {
                lastDate = globexDate;
                dayStartBar = CurrentBar;
                todaySweeps.Clear();

                foreach (var level in activeLevels)
                    level.Swept = false;
            }

            if (dayStartBar < 0) dayStartBar = CurrentBar;

            if (barMins == 17 * 60 || barMins == 16 * 60 + 15)
            {
                settlementPrice = closeP;
            }

            // Native Week & Month Tracking
            UpdateWeekMonthTracking(barTimeEt, highP, lowP, closeP);

            // Native Session Range Tracking (Asia, London, Globex, IB)
            UpdateSessionRangesTracking(barTimeEt, highP, lowP);

            // Update session opens engine (pass both openP and closeP for exact open matching)
            sessionOpens.OnBarUpdate(barTimeEt, openP, closeP, CurrentBar);

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
            int barMins = barEt.Hour * 60 + barEt.Minute;

            // ── Globex Day Boundary: 18:00 ET ──
            // For CME futures the new trading day starts at 18:00 ET.
            // In NinjaTrader (close-timestamped bars), the bar that OPENED at 18:00 ET
            // has Time[0] slightly AFTER 18:00 (e.g. 18:05 on a 5-min chart).
            // So we detect "new Globex session started" when barMins > 18*60
            // and the Globex date has changed.
            //
            // Globex date mapping: 18:00–23:59 ET belong to the NEXT calendar day.
            DateTime globexDate = barMins >= 18 * 60 ? barEt.Date.AddDays(1) : barEt.Date;

            bool isFirstBarOfGlobexSession = barMins > 18 * 60 && globexDate != lastGlobexTrackingDate;
            if (isFirstBarOfGlobexSession)
            {
                lastGlobexTrackingDate = globexDate;

                // ── Day-of-Week Opens (capture at Globex session open = 18:00 ET prev calendar day) ──
                // NT: Open[0] on the first bar AFTER 18:00 ET = the 18:00 ET open price ✅
                // TradingView: Tuesday's daily bar open = 18:00 ET Monday's price → same value ✅
                switch (barEt.DayOfWeek)  // barEt is still the prior calendar day (e.g. Monday evening)
                {
                    case DayOfWeek.Monday:    // Monday 18:05 → Tuesday's session open
                        tueOpen = Open[0];
                        break;
                    case DayOfWeek.Tuesday:   // Tuesday 18:05 → Wednesday's session open
                        wedOpen = Open[0];
                        break;
                    case DayOfWeek.Wednesday: // Wednesday 18:05 → Thursday's session open
                        thuOpen = Open[0];
                        break;
                    case DayOfWeek.Thursday:  // Thursday 18:05 → Friday's session open
                        friOpen = Open[0];
                        break;
                }
            }

            // ── Week Tracking: roll at Sunday 18:00 ET (Globex week open) ──
            // globexDate == Monday when barEt == Sunday evening
            bool isNewGlobexWeek = globexDate.DayOfWeek == DayOfWeek.Monday && isFirstBarOfGlobexSession;
            if (isNewGlobexWeek)
            {
                if (curWeekNum != -1)
                {
                    prevWeekHigh     = curWeekHigh;
                    prevWeekLow      = curWeekLow;
                    prevWeekCloseVal = curWeekClose;
                    prevWeekOpen     = curWeekOpen;
                }
                curWeekOpen  = Open[0];   // Sunday 18:00 ET open = weekly open (matches TradingView)
                curWeekHigh  = high;
                curWeekLow   = low;
                curWeekClose = close;
                curWeekNum   = 1;         // marker: week is active
                weekStartBar = CurrentBar;
                tueOpen = 0; wedOpen = 0; thuOpen = 0; friOpen = 0;
            }
            else
            {
                if (high > curWeekHigh) curWeekHigh = high;
                if (low  < curWeekLow)  curWeekLow  = low;
                curWeekClose = close;
            }
            if (weekStartBar < 0) weekStartBar = CurrentBar;

            // ── Month Tracking: roll at first Globex session open of a new calendar month ──
            // The Globex date tells us which month we're "in" for futures.
            int monthNum = globexDate.Year * 12 + globexDate.Month;
            if (monthNum != curMonthNum)
            {
                if (curMonthNum != -1)
                {
                    prevMonthHigh     = curMonthHigh;
                    prevMonthLow      = curMonthLow;
                    prevMonthCloseVal = curMonthClose;
                    prevMonthOpen     = curMonthOpen;
                }
                curMonthOpen  = Open[0];   // first Globex session open of new month (matches TradingView)
                curMonthHigh  = high;
                curMonthLow   = low;
                curMonthClose = close;
                curMonthNum   = monthNum;
                monthStartBar = CurrentBar;
            }
            else
            {
                if (high > curMonthHigh) curMonthHigh = high;
                if (low  < curMonthLow)  curMonthLow  = low;
            }
            if (monthStartBar < 0) monthStartBar = CurrentBar;
        }

        private void UpdateSessionRangesTracking(DateTime barEt, double high, double low)
        {
            int barMins = barEt.Hour * 60 + barEt.Minute;
            DateTime today = barEt.Date;

            // Asia Range: 20:00 ET to 00:00 ET
            // End-of-bar: barMins=1205 covers 20:00-20:05 (opened at 20:00) → first bar in window.
            // barMins=0 covers 23:55-00:00 (opened at 23:55) → last bar in window.
            bool inAsia = barMins > 20 * 60 || barMins == 0;
            if (inAsia)
            {
                if (asiaDate != today || !asiaBuilding)
                {
                    asiaHigh = high; asiaLow = low; asiaBuilding = true; asiaDate = today;
                    asiaStartBar = CurrentBar;
                }
                else
                {
                    if (high > asiaHigh) asiaHigh = high;
                    if (low < asiaLow) asiaLow = low;
                }
                asiaMid = (asiaHigh + asiaLow) / 2.0;
            }
            else if (asiaBuilding && barMins > 0)
            {
                asiaBuilding = false;
            }

            // London Range: 02:00 ET to 05:00 ET (end-of-bar: first bar at barMins>120, last at barMins<=300)
            bool inLondon = barMins > 2 * 60 && barMins <= 5 * 60;
            if (inLondon)
            {
                if (londonDate != today || !londonBuilding)
                {
                    londonHigh = high; londonLow = low; londonBuilding = true; londonDate = today;
                    londonStartBar = CurrentBar;
                }
                else
                {
                    if (high > londonHigh) londonHigh = high;
                    if (low < londonLow) londonLow = low;
                }
                londonMid = (londonHigh + londonLow) / 2.0;
            }
            else if (londonBuilding && barMins > 5 * 60)
            {
                londonBuilding = false;
            }

            // Globex Range: 18:00 ET to 09:30 ET (crosses midnight)
            bool inGlobex = barMins > 18 * 60 || barMins <= 9 * 60 + 30;
            if (inGlobex)
            {
                if (globexDate != today || !globexBuilding)
                {
                    globexHigh = high; globexLow = low; globexBuilding = true; globexDate = today;
                    globexStartBar = CurrentBar;
                }
                else
                {
                    if (high > globexHigh) globexHigh = high;
                    if (low < globexLow) globexLow = low;
                }
                globexMid = (globexHigh + globexLow) / 2.0;
            }
            else if (globexBuilding && barMins > 9 * 60 + 30)
            {
                globexBuilding = false;
            }

            // Initial Balance (IB): 09:30 ET to 10:30 ET (first bar at barMins>570, last at barMins<=630)
            bool inIb = barMins > 9 * 60 + 30 && barMins <= 10 * 60 + 30;
            if (inIb)
            {
                if (ibDate != today || !ibBuilding)
                {
                    ibHigh = high; ibLow = low; ibBuilding = true; ibDate = today;
                    ibStartBar = CurrentBar;
                }
                else
                {
                    if (high > ibHigh) ibHigh = high;
                    if (low < ibLow) ibLow = low;
                }
                ibMid = (ibHigh + ibLow) / 2.0;
            }
            else if (ibBuilding && barMins > 10 * 60 + 30)
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

                switch (level.Def.Source)
                {
                    case LevelSource.SessionOpens:
                        level.Price = sessionOpens.GetOpen(level.Def.Name);
                        level.IsActive = sessionOpens.IsOpenSet(level.Def.Name);
                        int openIdx = sessionOpens.GetOpenBarIndex(level.Def.Name);
                        level.SetBarIndex = openIdx > 0 ? openIdx : (dayStartBar > 0 ? dayStartBar : CurrentBar);
                        break;

                    case LevelSource.PriorDayOHLC:
                    case LevelSource.CurrentDayOHL:
                    case LevelSource.RedTailKeyLevels:
                    case LevelSource.RedTailVolumeProfile:
                    case LevelSource.Internal:
                        {
                            if (level.Def.Category == LevelCategory.PriorWeek)
                                level.SetBarIndex = weekStartBar > 0 ? weekStartBar : (dayStartBar > 0 ? dayStartBar : CurrentBar);
                            else if (level.Def.Category == LevelCategory.PriorMonth)
                                level.SetBarIndex = monthStartBar > 0 ? monthStartBar : (dayStartBar > 0 ? dayStartBar : CurrentBar);
                            else
                                level.SetBarIndex = dayStartBar > 0 ? dayStartBar : CurrentBar;

                            if (level.Def.Source == LevelSource.PriorDayOHLC) level.Price = ReadPriorDayOHLC(level.Def.Accessor);
                            else if (level.Def.Source == LevelSource.CurrentDayOHL) level.Price = ReadCurrentDayOHL(level.Def.Accessor);
                            else if (level.Def.Source == LevelSource.RedTailKeyLevels) level.Price = ReadRedTailKeyLevels(level.Def.Accessor);
                            else if (level.Def.Source == LevelSource.RedTailVolumeProfile) level.Price = ReadRedTailVolumeProfile(level.Def.Accessor);
                            else if (level.Def.Source == LevelSource.Internal) level.Price = ComputeInternalLevel(level.Def.Accessor);

                            level.IsActive = level.Price > 0;
                        }
                        break;

                    case LevelSource.SessionRanges:
                        {
                            level.Price = ReadSessionRanges(level.Def.Accessor);
                            level.IsActive = level.Price > 0;
                            if (level.Def.Accessor.StartsWith("Asia"))
                                level.SetBarIndex = asiaStartBar > 0 ? asiaStartBar : (dayStartBar > 0 ? dayStartBar : CurrentBar);
                            else if (level.Def.Accessor.StartsWith("London"))
                                level.SetBarIndex = londonStartBar > 0 ? londonStartBar : (dayStartBar > 0 ? dayStartBar : CurrentBar);
                            else if (level.Def.Accessor.StartsWith("Globex"))
                                level.SetBarIndex = globexStartBar > 0 ? globexStartBar : (dayStartBar > 0 ? dayStartBar : CurrentBar);
                            else if (level.Def.Accessor.StartsWith("IB"))
                                level.SetBarIndex = ibStartBar > 0 ? ibStartBar : (dayStartBar > 0 ? dayStartBar : CurrentBar);
                            else
                                level.SetBarIndex = dayStartBar > 0 ? dayStartBar : CurrentBar;
                        }
                        break;
                }
            }
        }

        private double ReadPriorDayOHLC(string accessor)
        {
            if (_priorDayOHLC == null) return 0;
            switch (accessor)
            {
                case "PriorHigh":  return _priorDayOHLC.PriorHigh[0];
                case "PriorLow":   return _priorDayOHLC.PriorLow[0];
                case "PriorClose": return _priorDayOHLC.PriorClose[0];
                case "PriorOpen":  return _priorDayOHLC.PriorOpen[0];
                default: return 0;
            }
        }

        private double ReadCurrentDayOHL(string accessor)
        {
            if (_currentDayOHL == null) return 0;
            switch (accessor)
            {
                case "CurrentHigh": return _currentDayOHL.CurrentHigh[0];
                case "CurrentLow":  return _currentDayOHL.CurrentLow[0];
                case "CurrentOpen": return _currentDayOHL.CurrentOpen[0];
                default: return 0;
            }
        }

        private double ReadRedTailKeyLevels(string accessor)
        {
            if (_priorDayOHLC == null) return 0;
            double pdh = _priorDayOHLC.PriorHigh[0];
            double pdl = _priorDayOHLC.PriorLow[0];
            double pdc = _priorDayOHLC.PriorClose[0];
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
            if (_priorDayOHLC == null) return 0;
            double pdh = _priorDayOHLC.PriorHigh[0];
            double pdl = _priorDayOHLC.PriorLow[0];
            if (pdh <= 0 || pdl <= 0) return 0;

            switch (accessor)
            {
                case "CurrentPOCPlot":   return (High[0] + Low[0] + Close[0]) / 3.0;
                case "CurrentVAHPlot":   return High[0];
                case "CurrentVALPlot":   return Low[0];
                case "PrevDayPOCPlot":   return (pdh + pdl + _priorDayOHLC.PriorClose[0]) / 3.0;
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
            double pdh = _priorDayOHLC != null ? _priorDayOHLC.PriorHigh[0] : 0;
            double pdl = _priorDayOHLC != null ? _priorDayOHLC.PriorLow[0]  : 0;
            double pdc = _priorDayOHLC != null ? _priorDayOHLC.PriorClose[0] : 0;

            switch (accessor)
            {
                case "PriorDayMid":
                    return (pdh > 0 && pdl > 0) ? (pdh + pdl) / 2.0 : 0;

                case "Settlement":
                    return dailySettlementPrice > 0 ? dailySettlementPrice : (settlementPrice > 0 ? settlementPrice : pdc);

                case "PriorWeekMid":
                    return (prevWeekHigh > 0 && prevWeekLow > 0) ? (prevWeekHigh + prevWeekLow) / 2.0 : 0;

                case "PriorWeekClose":
                    return prevWeekCloseVal > 0 ? prevWeekCloseVal : pdc;

                case "PriorWeekOpen":
                    return prevWeekOpen;

                case "PriorMonthMid":
                    return (prevMonthHigh > 0 && prevMonthLow > 0) ? (prevMonthHigh + prevMonthLow) / 2.0 : 0;

                case "PriorMonthOpen":
                    return prevMonthOpen;

                case "TueOpen": return tueOpen;
                case "WedOpen": return wedOpen;
                case "ThuOpen": return thuOpen;
                case "FriOpen": return friOpen;

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

            // P12 Overnight: 18:00 ET to 06:00 ET (crosses midnight)
            // End-of-bar: first bar at barMins>1080, last bar at barMins<=360
            if (barMins > 18 * 60 && (p12Date != today || !p12Building))
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
                bool inP12 = barMins > 18 * 60 || barMins <= 6 * 60;
                if (inP12)
                {
                    if (high > p12High) p12High = high;
                    if (low < p12Low) p12Low = low;
                }
                else if (barMins > 6 * 60)
                {
                    p12Building = false;
                }
            }

            // NY P12: 06:00 ET to 17:00 ET (first bar at barMins>360, last at barMins<=1020)
            if (barMins > 6 * 60 && (nyP12Date != today || !nyP12Building))
            {
                nyP12High = high;
                nyP12Low = low;
                nyP12Building = true;
                nyP12Date = today;
            }
            else if (nyP12Building)
            {
                bool inNyP12 = barMins > 6 * 60 && barMins <= 17 * 60;
                if (inNyP12)
                {
                    if (high > nyP12High) nyP12High = high;
                    if (low < nyP12Low) nyP12Low = low;
                }
                else if (barMins > 17 * 60)
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

            double minDepth = TickSize * SweepMinDepthTicks;

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
                                SweepDepth = sweepDepth / TickSize,
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
                                SweepDepth = sweepDepth / TickSize,
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
                            SweepDepth = (high - level.Price) / TickSize,
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
                            SweepDepth = (level.Price - low) / TickSize,
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

                    if (EnableVoiceAlerts)
                    {
                        // Only fire alerts on the live/realtime bar, not during historical bar processing.
                        if (State == State.DataLoaded && CurrentBar == BarsArray[0].Count - 1)
                        {
                            string alertKey = level.Def.Name + "_" + (sweep.IsBullSweep ? "Bull" : "Bear");
                            if (CanAlert(alertKey))
                            {
                                double roundedP = TickSize > 0 ? Math.Round(level.Price / TickSize) * TickSize : level.Price;
                                string formattedP = Instrument != null ? Instrument.MasterInstrument.FormatPrice(roundedP) : roundedP.ToString("F2");
                                string side = sweep.IsBullSweep ? "Bullish Sweep" : "Bearish Sweep";
                                string spokenName = level.Def.FullName ?? level.Def.Name;
                                string alertMsg = $"{side}: {spokenName} swept at {formattedP}";
                                PlaySweepAlert(alertKey, alertMsg);
                                RecordAlert(alertKey);
                            }
                        }
                    }
                }
            }

            UpdateStacking();
        }

        #region Voice Alert Infrastructure (System.Speech pre-generated WAV files)

        private bool CanAlert(string key)
        {
            if (!lastAlertTime.ContainsKey(key)) return true;
            return (DateTime.Now - lastAlertTime[key]).TotalSeconds >= AlertCooldownSeconds;
        }

        private void RecordAlert(string key)
        {
            lastAlertTime[key] = DateTime.Now;
        }

        private void PlaySweepAlert(string alertKey, string message)
        {
            string soundPath = GetVoiceAlertPath(alertKey, AlertFallbackSound);
            Alert("LiqSweep_" + alertKey + "_" + CurrentBar, Priority.High, message,
                soundPath, 10, System.Windows.Media.Brushes.White, System.Windows.Media.Brushes.DarkRed);
        }

        private string GetVoiceAlertPath(string alertKey, string fallbackSoundFile)
        {
            if (EnableVoiceAlerts && voiceAlertPaths.ContainsKey(alertKey))
                return voiceAlertPaths[alertKey];
            return ResolveSoundPath(fallbackSoundFile);
        }

        private string ResolveSoundPath(string raw)
        {
            if (string.IsNullOrWhiteSpace(raw)) return null;
            if (Path.IsPathRooted(raw)) return raw;
            var install = Path.Combine(NinjaTrader.Core.Globals.InstallDir, "sounds", raw);
            if (File.Exists(install)) return install;
            var user = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "sounds", raw);
            if (File.Exists(user)) return user;
            return raw;
        }

        private void GenerateVoiceAlerts()
        {
            string soundDir = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "sounds");
            if (!Directory.Exists(soundDir))
                Directory.CreateDirectory(soundDir);

            // Build alert phrases for all sweep target levels (two per level: Bull + Bear)
            var alerts = new Dictionary<string, string>();
            foreach (var def in LiquidityLevelsCatalog.GetSweepTargets())
            {
                string name = def.FullName ?? def.Name;
                alerts[def.Name + "_Bull"] = instrumentName + " bullish sweep at " + name;
                alerts[def.Name + "_Bear"] = instrumentName + " bearish sweep at " + name;
            }
            int totalAlerts = alerts.Count;

            // Marker file to cache voice settings
            string markerPath = Path.Combine(soundDir, "LiqLevel_" + instrumentName + "_voicesettings.txt");
            string currentSettings = "rate=" + VoiceRate + "|gender=" + VoiceGender;
            bool settingsChanged = true;

            if (File.Exists(markerPath))
            {
                try
                {
                    string savedSettings = File.ReadAllText(markerPath).Trim();
                    if (savedSettings == currentSettings) settingsChanged = false;
                }
                catch { }
            }

            // Check if all files exist
            bool allExist = true;
            foreach (var kvp in alerts)
            {
                string fileName = "LiqLevel_" + instrumentName + "_" + kvp.Key + ".wav";
                if (!File.Exists(Path.Combine(soundDir, fileName)))
                {
                    allExist = false;
                    break;
                }
            }

            if (settingsChanged || !allExist)
            {
                // Delete old files
                foreach (var kvp in alerts)
                {
                    string fileName = "LiqLevel_" + instrumentName + "_" + kvp.Key + ".wav";
                    string filePath = Path.Combine(soundDir, fileName);
                    try { if (File.Exists(filePath)) File.Delete(filePath); } catch { }
                }

                Print("LiquidityLevels: Generating voice alerts for " + instrumentName + " (" + totalAlerts + " files)...");

                int successCount = GenerateSapiVoiceAlerts(soundDir, alerts);

                if (successCount > 0)
                    Print("LiquidityLevels: Voice generation complete (" + successCount + "/" + totalAlerts + " files).");
                else
                    Print("LiquidityLevels: Voice generation failed. Using fallback sound.");

                try { File.WriteAllText(markerPath, currentSettings); } catch { }
            }
            else
            {
                Print("LiquidityLevels: Voice alert files already cached for " + instrumentName + ".");
            }

            // Register all paths
            foreach (var kvp in alerts)
            {
                string fileName = "LiqLevel_" + instrumentName + "_" + kvp.Key + ".wav";
                string filePath = Path.Combine(soundDir, fileName);
                if (File.Exists(filePath))
                    voiceAlertPaths[kvp.Key] = filePath;
            }

            Print("LiquidityLevels: Voice alerts ready for " + instrumentName + " (" + voiceAlertPaths.Count + "/" + totalAlerts + " files).");
        }

        private int GenerateSapiVoiceAlerts(string soundDir, Dictionary<string, string> alerts)
        {
            int successCount = 0;
            try
            {
                using (var synth = new SpeechSynthesizer())
                {
                    // Select voice by gender
                    var voices = synth.GetInstalledVoices();
                    string[] femaleNames = { "Zira", "Hazel", "Susan", "Catherine", "Helena" };
                    string[] maleNames = { "David", "George", "Mark", "Richard", "Sean" };
                    var names = VoiceGender == VoiceGenderSelection.Female ? femaleNames : maleNames;

                    bool voiceSelected = false;
                    foreach (var vn in names)
                    {
                        var match = voices.FirstOrDefault(v => v.VoiceInfo.Name.Contains(vn));
                        if (match != null)
                        {
                            synth.SelectVoice(match.VoiceInfo.Name);
                            Print("LiquidityLevels: Using voice: " + match.VoiceInfo.Name);
                            voiceSelected = true;
                            break;
                        }
                    }
                    if (!voiceSelected && voices.Count > 0)
                    {
                        Print("LiquidityLevels: Preferred voice not found, using default: " + voices[0].VoiceInfo.Name);
                    }

                    int rate = Math.Min(10, Math.Max(-10, VoiceRate));
                    synth.Rate = rate;

                    foreach (var kvp in alerts)
                    {
                        string fileName = "LiqLevel_" + instrumentName + "_" + kvp.Key + ".wav";
                        string wavPath = Path.Combine(soundDir, fileName);

                        try
                        {
                            synth.SetOutputToWaveFile(wavPath);
                            synth.Speak(kvp.Value);
                            synth.SetOutputToNull();
                            successCount++;
                        }
                        catch (Exception ex)
                        {
                            Print("LiquidityLevels: Voice gen FAIL " + kvp.Key + ": " + ex.Message);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Print("LiquidityLevels: SAPI voice error: " + ex.Message);
            }
            return successCount;
        }

        #endregion

        private void UpdateStacking()
        {
            double tolerance = TickSize * StackingToleranceTicks;
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
            double tolerance = TickSize * toleranceTicks;
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

            if (!resourcesCreated || textFormat == null || Math.Abs(textFormat.FontSize - (float)FontSize) > 0.1f)
            {
                if (textFormat != null) textFormat.Dispose();
                if (tooltipFormat != null) tooltipFormat.Dispose();

                float fontSize = Math.Max(8f, (float)FontSize);
                textFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI",
                    SharpDX.DirectWrite.FontWeight.SemiBold, SharpDX.DirectWrite.FontStyle.Normal, fontSize);
                tooltipFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI",
                    SharpDX.DirectWrite.FontWeight.Normal, SharpDX.DirectWrite.FontStyle.Normal, fontSize);
                resourcesCreated = true;
            }

            var activeLevelsToDraw = GetActiveLevels();

            bool isDark = IsDarkChart(chartControl);

            var categoryColors = isDark
                ? new Dictionary<LevelCategory, SharpDX.Color>
                {
                    { LevelCategory.PriorDay,     new SharpDX.Color(0x00, 0xE6, 0x76, 255) }, // Neon Green
                    { LevelCategory.PriorWeek,    new SharpDX.Color(0x00, 0xE5, 0xFF, 255) }, // Electric Cyan
                    { LevelCategory.PriorMonth,   new SharpDX.Color(0x00, 0xB0, 0xFF, 255) }, // Sky Blue
                    { LevelCategory.SessionOpen,  new SharpDX.Color(0xFF, 0xEA, 0x00, 255) }, // Bright Yellow
                    { LevelCategory.SessionRange, new SharpDX.Color(0x29, 0x79, 0xFF, 255) }, // Vivid Blue
                    { LevelCategory.Intraday,     new SharpDX.Color(0x76, 0xFF, 0x03, 255) }, // Lime
                    { LevelCategory.VolumeProfile,new SharpDX.Color(0xFF, 0x91, 0x00, 255) }, // Vivid Orange
                    { LevelCategory.Structure,    new SharpDX.Color(0xD5, 0x00, 0xF9, 255) }, // Bright Purple
                    { LevelCategory.Pivot,        new SharpDX.Color(0xFF, 0x40, 0x81, 255) }, // Pink/Magenta
                    { LevelCategory.Fib,          new SharpDX.Color(0xFF, 0xAB, 0x00, 255) }, // Gold
                }
                : new Dictionary<LevelCategory, SharpDX.Color>
                {
                    { LevelCategory.PriorDay,     new SharpDX.Color(0x00, 0x7E, 0x33, 255) }, // Dark Green
                    { LevelCategory.PriorWeek,    new SharpDX.Color(0x00, 0x83, 0x8F, 255) }, // Deep Cyan
                    { LevelCategory.PriorMonth,   new SharpDX.Color(0x02, 0x77, 0xBD, 255) }, // Deep Ocean Blue
                    { LevelCategory.SessionOpen,  new SharpDX.Color(0xD8, 0x43, 0x15, 255) }, // Burnt Orange
                    { LevelCategory.SessionRange, new SharpDX.Color(0x15, 0x65, 0xC0, 255) }, // Royal Blue
                    { LevelCategory.Intraday,     new SharpDX.Color(0x2E, 0x7D, 0x32, 255) }, // Dark Lime/Forest
                    { LevelCategory.VolumeProfile,new SharpDX.Color(0xEF, 0x6C, 0x00, 255) }, // Dark Orange
                    { LevelCategory.Structure,    new SharpDX.Color(0x6A, 0x1B, 0x9A, 255) }, // Deep Purple
                    { LevelCategory.Pivot,        new SharpDX.Color(0xC2, 0x18, 0x5B, 255) }, // Deep Crimson
                    { LevelCategory.Fib,          new SharpDX.Color(0xF5, 0x7F, 0x17, 255) }, // Dark Amber
                };

            float chartLeftX = chartControl.GetXByBarIndex(ChartBars, ChartBars.FromIndex);
            float chartRightX = chartControl.GetXByBarIndex(ChartBars, ChartBars.ToIndex) + (float)chartControl.Properties.BarDistance;

            double currentPrice = Close[0];
            var labelItems = new List<RenderLabelItem>();

            foreach (var level in activeLevelsToDraw)
            {
                int originBar = level.SetBarIndex > 0 ? Math.Min(CurrentBar, level.SetBarIndex) : ChartBars.FromIndex;
                float xStart = chartControl.GetXByBarIndex(ChartBars, originBar);
                if (xStart < chartLeftX) xStart = chartLeftX;
                float xEnd = chartRightX;

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

                using (var lineBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, lineColor))
                {
                    RenderTarget.DrawLine(new SharpDX.Vector2(xStart, y), new SharpDX.Vector2(xEnd, y), lineBrush, lineWidth);
                }

                float labelAlphaThreshold = (float)FarFadeOpacity / 100f + 0.05f;
                bool showLabel = DrawLabels && textFormat != null
                    && (!ProximityFade || alpha > labelAlphaThreshold || (level.Swept == false && level.StacksWith.Count > 0));

                if (showLabel)
                {
                    string nameStr = UseFullLevelNames && !string.IsNullOrEmpty(level.Def.FullName) ? level.Def.FullName : level.Def.Name;
                    double roundedPrice = TickSize > 0 ? Math.Round(level.Price / TickSize) * TickSize : level.Price;
                    string priceStr = Instrument != null ? Instrument.MasterInstrument.FormatPrice(roundedPrice) : roundedPrice.ToString("F2");
                    string label = $"{nameStr} {priceStr}";
                    if (level.Swept) label += " ✗";

                    labelItems.Add(new RenderLabelItem
                    {
                        Level = level,
                        Y = y,
                        XStart = xStart,
                        Color = color,
                        Text = label
                    });
                }
            }

            // ── Smart Label Harmonization (Y-Staggering) ──
            if (labelItems.Count > 0)
            {
                var sortedLabels = labelItems.OrderBy(l => l.Y).ToList();
                float minSpacing = 16f;

                // 1. Render Right Margin Labels (Y-Staggered)
                if (LabelPlacement == LabelPlacement.RightMargin || LabelPlacement == LabelPlacement.Both)
                {
                    float prevY = -1000f;
                    foreach (var item in sortedLabels)
                    {
                        var textLayout = new TextLayout(Core.Globals.DirectWriteFactory, item.Text, textFormat, float.MaxValue, float.MaxValue);
                        float textW = (float)textLayout.Metrics.Width;
                        float textH = (float)textLayout.Metrics.Height;
                        float labelY = item.Y - textH / 2f;

                        if (labelY < prevY + minSpacing)
                            labelY = prevY + minSpacing;
                        prevY = labelY;

                        var bgBrush = isDark
                            ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.04f, 0.06f, 0.08f, 0.90f))
                            : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.98f, 0.98f, 1.0f, 0.95f));

                        var borderBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(item.Color.R / 255f, item.Color.G / 255f, item.Color.B / 255f, 0.9f));

                        var labelBrush = isDark
                            ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(1.0f, 1.0f, 1.0f, 1.0f))
                            : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.04f, 0.06f, 0.10f, 1.0f));

                        float rightLabelX = chartRightX + 4;
                        var rightBgRect = new RectangleF(rightLabelX - 2, labelY - 1, textW + 4, textH + 2);
                        RenderTarget.FillRectangle(rightBgRect, bgBrush);
                        RenderTarget.DrawRectangle(rightBgRect, borderBrush, 1.0f);
                        RenderTarget.DrawTextLayout(new SharpDX.Vector2(rightLabelX, labelY), textLayout, labelBrush);

                        bgBrush.Dispose();
                        borderBrush.Dispose();
                        labelBrush.Dispose();
                        textLayout.Dispose();
                    }
                }

                // 2. Render Origin Labels (Y-Staggered)
                if (LabelPlacement == LabelPlacement.Origin || LabelPlacement == LabelPlacement.Both)
                {
                    float prevY = -1000f;
                    foreach (var item in sortedLabels)
                    {
                        var textLayout = new TextLayout(Core.Globals.DirectWriteFactory, item.Text, textFormat, float.MaxValue, float.MaxValue);
                        float textW = (float)textLayout.Metrics.Width;
                        float textH = (float)textLayout.Metrics.Height;
                        float labelY = item.Y - textH / 2f;

                        if (labelY < prevY + minSpacing)
                            labelY = prevY + minSpacing;
                        prevY = labelY;

                        var bgBrush = isDark
                            ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.04f, 0.06f, 0.08f, 0.90f))
                            : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.98f, 0.98f, 1.0f, 0.95f));

                        var borderBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(item.Color.R / 255f, item.Color.G / 255f, item.Color.B / 255f, 0.9f));

                        var labelBrush = isDark
                            ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(1.0f, 1.0f, 1.0f, 1.0f))
                            : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.04f, 0.06f, 0.10f, 1.0f));

                        float originLabelX = item.XStart + 4;
                        var originBgRect = new RectangleF(originLabelX - 2, labelY - 1, textW + 4, textH + 2);
                        RenderTarget.FillRectangle(originBgRect, bgBrush);
                        RenderTarget.DrawRectangle(originBgRect, borderBrush, 1.0f);
                        RenderTarget.DrawTextLayout(new SharpDX.Vector2(originLabelX, labelY), textLayout, labelBrush);

                        bgBrush.Dispose();
                        borderBrush.Dispose();
                        labelBrush.Dispose();
                        textLayout.Dispose();
                    }
                }
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
                        ? (isDark ? new SharpDX.Color(0x00, 0xE6, 0x76, 255) : new SharpDX.Color(0x00, 0x89, 0x7B, 255))
                        : (isDark ? new SharpDX.Color(0xFF, 0x17, 0x44, 255) : new SharpDX.Color(0xC6, 0x28, 0x28, 255));

                    var markerBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget,
                        new Color4(markerColor.R / 255f, markerColor.G / 255f, markerColor.B / 255f, 0.9f));

                    RenderTarget.FillEllipse(new SharpDX.Direct2D1.Ellipse(new SharpDX.Vector2(sx, sy), markerSize, markerSize), markerBrush);
                    markerBrush.Dispose();
                }
            }

            // Interactive On-Chart Mouse Hover Tooltips
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
                        float minHitDist = 8.0f;

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

        private bool IsDarkChart(ChartControl chartControl)
        {
            if (chartControl != null && chartControl.Properties != null && chartControl.Properties.ChartBackground != null)
            {
                if (chartControl.Properties.ChartBackground is System.Windows.Media.SolidColorBrush scb)
                {
                    double luminance = (0.299 * scb.Color.R + 0.587 * scb.Color.G + 0.114 * scb.Color.B) / 255.0;
                    return luminance < 0.5;
                }
            }
            return true;
        }

        private class RenderLabelItem
        {
            public LevelState Level { get; set; }
            public float Y { get; set; }
            public float XStart { get; set; }
            public SharpDX.Color Color { get; set; }
            public string Text { get; set; }
        }

        private void RenderHoverTooltip(ChartControl chartControl, ChartScale chartScale, LevelState level, float mouseX, float mouseY, double currentPrice)
        {
            bool isDark = IsDarkChart(chartControl);

            string title = level.Def.FullName ?? level.Def.Name;
            string priceText = $"Price: {level.Price:N2}";
            string catText = $"Category: {level.Def.Category} | Source: {level.Def.Source}";
            string statusText = level.Swept
                ? $"Status: Swept ✗ (at {level.SweptTime:HH:mm ET})"
                : "Status: Active (Unswept)";

            double distPts = Math.Abs(level.Price - currentPrice);
            double distTicks = distPts / TickSize;
            string distText = $"Distance: {distPts:F2} pts ({distTicks:F0} ticks)";

            string stackText = level.StacksWith.Count > 0
                ? $"Stacked: {string.Join(", ", level.StacksWith)}"
                : null;

            List<string> lines = new List<string> { title, priceText, catText, statusText, distText };
            if (stackText != null) lines.Add(stackText);

            var activeFormat = tooltipFormat ?? textFormat;

            // Measure maximum required text width dynamically
            float maxLineWidth = 0f;
            if (activeFormat != null)
            {
                foreach (var line in lines)
                {
                    using (var layout = new TextLayout(Core.Globals.DirectWriteFactory, line, activeFormat, float.MaxValue, float.MaxValue))
                    {
                        if (layout.Metrics.Width > maxLineWidth)
                            maxLineWidth = layout.Metrics.Width;
                    }
                }
            }

            float width = Math.Max(260f, maxLineWidth + 24f);
            float lineHeight = Math.Max(16f, (activeFormat?.FontSize ?? 11f) + 5f);
            float height = lines.Count * lineHeight + 12f;

            float boxX = mouseX + 15;
            float boxY = mouseY - height / 2;

            if (boxX + width > (float)chartControl.ActualWidth)
                boxX = mouseX - width - 15;
            if (boxY < 10) boxY = 10;
            if (boxY + height > (float)chartControl.ActualHeight - 10)
                boxY = (float)chartControl.ActualHeight - height - 10;

            var bgRect = new RectangleF(boxX, boxY, width, height);

            var bgBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.06f, 0.08f, 0.12f, 0.95f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.96f, 0.97f, 0.99f, 0.96f));

            var borderBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.0f, 0.7f, 1.0f, 0.9f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.1f, 0.4f, 0.8f, 0.9f));

            var titleBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(1.0f, 1.0f, 1.0f, 1.0f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.04f, 0.06f, 0.10f, 1.0f));

            var textBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.85f, 0.88f, 0.92f, 1.0f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.12f, 0.15f, 0.20f, 1.0f));

            var sweptBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(1.0f, 0.3f, 0.3f, 1.0f));

            RenderTarget.FillRectangle(bgRect, bgBrush);
            RenderTarget.DrawRectangle(bgRect, borderBrush, 1.5f);

            float textY = boxY + 6;
            for (int i = 0; i < lines.Count; i++)
            {
                var curBrush = (i == 0) ? titleBrush : (lines[i].Contains("Swept")) ? sweptBrush : textBrush;
                var textLayout = new TextLayout(Core.Globals.DirectWriteFactory, lines[i], activeFormat, float.MaxValue, float.MaxValue);
                textLayout.WordWrapping = WordWrapping.NoWrap;
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