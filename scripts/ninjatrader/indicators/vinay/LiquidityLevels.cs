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
        private NtTagRenderer levelRenderer = new NtTagRenderer();

        // Performance caches
        private HashSet<string> enabledLevelNames;
        private bool enabledCacheDirty = true;
        private List<LevelState> cachedActiveLevels;
        private bool activeLevelsDirty = true;
        private Dictionary<LevelCategory, SharpDX.Color> cachedCategoryColors;
        private NtScheme cachedScheme = NtScheme.Midnight;
        private bool categoryColorsDirty = true;
        private List<RenderLabelItem> reusableLabelItems = new List<RenderLabelItem>();
        private float cachedBadgeHeight = 0f;


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

        // ── Hit Rate Tracking State ──
        private HitRateConfig hrCfg;
        private HitWindow hrWindow;
        private List<SessionBars> hrSessionBars;
        private Dictionary<string, List<HitSample>> hrHistory;           // per-level committed history
        private Dictionary<string, LevelHitStats> hrStats;              // per-level computed stats
        private Dictionary<string, Func<DateTime, double>> hrProviders;  // per-level price providers
        private Dictionary<string, bool> hrTodayHit;                    // per-level: did today hit?
        private Dictionary<string, int> hrTodayHitMin;                   // per-level: first-hit time today
        private Dictionary<string, double> hrTodayLevel;                 // per-level: today's level price
        private List<string> hrTrackedLevels;                            // ordered list of tracked sweep-target level names
        private int hrDebugLevelIdx;                                      // index into hrTrackedLevels for cycling
        private int hrNewDaysDetected;                                    // total session dates detected
        private DateTime hrLastSessionDate;                               // last committed session date
        private RectangleF hrDebugTableRect;                              // hit-test rect for click-to-cycle
        private bool hrEngineReady;                                      // set true after DataLoaded build
        private bool hrTodayPriceRefreshed;                               // set true after first OnBarUpdate refreshes TodayPrice

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

        [Display(Name = "Data Model Retention (Days)", Description = "Number of historical days to retain in the MCP data model", Order = 11, GroupName = "7. Visuals & Layout")]
        public int DataModelRetentionDays { get; set; } = 5;

        #endregion

        #region Public API for MCP
        /// <summary>
        /// Returns a snapshot of the current semantic level records for the MCP data-model endpoint.
        /// </summary>
        public List<NtLevelRecord> GetLevelRecords()
        {
            var records = levelRenderer.Snapshot();
            
            // Prune based on RetentionDays
            if (DataModelRetentionDays > 0)
            {
                DateTime cutoff = DateTime.Now.AddDays(-DataModelRetentionDays);
                records = records.Where(r => r.Date >= cutoff).ToList();
            }
            
            return records;
        }
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

        #region NinjaScript Properties — Hit Rate Tracking

        [Display(Name = "Enable Hit Rate", Description = "Track per-level hit rate statistics", Order = 1, GroupName = "9. Hit Rate Tracking")]
        public bool EnableHitRate { get; set; } = true;

        [Display(Name = "Lookback (days)", Description = "Maximum number of historical days to include in hit rate stats", Order = 2, GroupName = "9. Hit Rate Tracking")]
        [Range(10, 2000)]
        public int HitRateLookbackDays { get; set; } = 500;

        [Display(Name = "Window Start (HH:mm)", Description = "Hit-check window start time in ET (e.g. 09:30)", Order = 3, GroupName = "9. Hit Rate Tracking")]
        public string HitRateWindowStart { get; set; } = "09:30";

        [Display(Name = "Window End (HH:mm)", Description = "Hit-check window end time in ET (e.g. 16:00)", Order = 4, GroupName = "9. Hit Rate Tracking")]
        public string HitRateWindowEnd { get; set; } = "16:00";

        [Display(Name = "Debug Level", Description = "Level name to show in the debug table (e.g. PDH, PDL, P12High). Click the debug table on chart to cycle.", Order = 5, GroupName = "9. Hit Rate Tracking")]
        public string HitRateDebugLevel { get; set; } = "PDH";

        [Display(Name = "Show Debug Table", Description = "Display the hit rate debug table in the top-right corner", Order = 6, GroupName = "9. Hit Rate Tracking")]
        public bool ShowHitRateDebugTable { get; set; } = true;

        [Display(Name = "Show Hit Rate in Tooltips", Description = "Append hit rate stats to hover tooltips on levels", Order = 7, GroupName = "9. Hit Rate Tracking")]
        public bool ShowHitRateTooltips { get; set; } = true;

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

                // Hit rate tracking — initialize collections
                hrCfg = new HitRateConfig { LookbackDays = HitRateLookbackDays, RecentN = 10, StreakMinHits = 1, Mode = HitMode.Through };
                hrHistory = new Dictionary<string, List<HitSample>>();
                hrStats = new Dictionary<string, LevelHitStats>();
                hrProviders = new Dictionary<string, Func<DateTime, double>>();
                hrTodayHit = new Dictionary<string, bool>();
                hrTodayHitMin = new Dictionary<string, int>();
                hrTodayLevel = new Dictionary<string, double>();
                hrTrackedLevels = new List<string>();
                hrDebugLevelIdx = 0;
                hrNewDaysDetected = 0;
                hrLastSessionDate = DateTime.MinValue;
                hrEngineReady = false;
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

                if (EnableHitRate)
                {
                    try
                    {
                        BuildHitRateEngine();
                    }
                    catch (Exception ex)
                    {
                        Print("LiquidityLevels: Hit rate engine build error: " + ex.Message);
                    }
                }
            }
        }

        #endregion

        #region Hit Rate Tracking — Engine Build, Live Update, Commit, Rendering

        // ── Session date mapping: a bar's ET time → its session date ──────────
        // Futures Globex day boundary = 18:00 ET. Bars at/after 18:00 ET belong
        // to the NEXT calendar day's session.
        private DateTime HrSessionDateFromBarEt(DateTime barEt)
        {
            // Match TV ProbabilityMap: new day at 17:00 ET (CME settlement boundary)
            // TV line 404: if hhmm >= 1700 and hhmm < 1801 → new day
            int barMins = barEt.Hour * 60 + barEt.Minute;
            return barMins >= 17 * 60 ? barEt.Date.AddDays(1) : barEt.Date;
        }

        // ── Build the hit-rate engine on DataLoaded ──────────────────────────
        // Scans intraday bars (BarsArray[0]) to build per-session window-bar
        // groupings, registers level price providers, then computes history +
        // stats for each tracked sweep-target level.
        private void BuildHitRateEngine()
        {
            // Build the hit window from config props
            int startMin = HitWindow.TimeStrToMin(HitRateWindowStart);
            int endMin = HitWindow.TimeStrToMin(HitRateWindowEnd);
            if (startMin < 0 || endMin < 0)
            {
                Print("LiquidityLevels: HitRateWindowStart/End invalid, defaulting to 09:30-16:00");
                startMin = 570; endMin = 960;
            }
            hrWindow = new HitWindow { StartMin = startMin, EndMin = endMin, Label = "Hit Window" };
            hrCfg = new HitRateConfig
            {
                LookbackDays = HitRateLookbackDays,
                RecentN = 10,
                StreakMinHits = 1,
                Mode = HitMode.Through
            };

            // Collect all bars from BarsArray[0] (intraday)
            var allBars = new List<BarData>();
            int totalBars = BarsArray[0].Count;
            for (int i = 0; i < totalBars; i++)
            {
                DateTime bt = ToEt(BarsArray[0].GetTime(i));
                if (etZone != null && bt.Kind != DateTimeKind.Utc)
                {
                    // ToEt already converts UTC→ET; if not UTC, assume it's already ET
                }
                allBars.Add(new BarData
                {
                    TimeEt = bt,
                    BarMins = bt.Hour * 60 + bt.Minute,
                    High = BarsArray[0].GetHigh(i),
                    Low = BarsArray[0].GetLow(i),
                    Open = BarsArray[0].GetOpen(i),
                    Close = BarsArray[0].GetClose(i),
                    BarIndex = i
                });
            }

            // Build session-date groupings (one pass)
            hrSessionBars = HitRateEngine.BuildSessionBars(allBars, hrWindow, HrSessionDateFromBarEt);
            hrNewDaysDetected = hrSessionBars.Count;

            // Separate today's session (the last one) from historical
            // Use the LAST bar's time, not Time[0] (which is bar 0 = oldest during DataLoaded)
            DateTime lastBarEt = ToEt(BarsArray[0].GetTime(BarsArray[0].Count - 1));
            DateTime todaySessionDate = HrSessionDateFromBarEt(lastBarEt);
            var historicalSessions = hrSessionBars
                .Where(s => s.SessionDate < todaySessionDate)
                .ToList();

            // Register level price providers for all levels
            RegisterLevelProviders();

            // Force a level price update so today's prices are available
            // (UpdateLevelPrices normally runs in OnBarUpdate, but we need
            // the prices during DataLoaded for the hit-rate stats snapshot)
            UpdateLevelPrices();

            // Build history + stats for each tracked level
            foreach (var levelName in hrTrackedLevels)
            {
                if (!hrProviders.TryGetValue(levelName, out var provider)) continue;

                var history = HitRateEngine.BuildHistory(levelName, provider, historicalSessions, hrCfg);
                hrHistory[levelName] = history;

                // Today's state (live)
                double todayPrice = GetTodayLevelPrice(levelName);
                hrTodayLevel[levelName] = todayPrice;
                hrTodayHit[levelName] = false;
                hrTodayHitMin[levelName] = 0;

                DateTime lastBarEt0 = ToEt(BarsArray[0].GetTime(BarsArray[0].Count - 1));
                bool inWindow = hrWindow.InWindow(lastBarEt0.Hour * 60 + lastBarEt0.Minute);
                hrStats[levelName] = HitRateEngine.ComputeStats(
                    levelName, history, todayPrice, false, inWindow,
                    CurrentBar, hrNewDaysDetected, hrCfg, hrWindow);
            }

            // Set debug level index
            hrDebugLevelIdx = Math.Max(0, hrTrackedLevels.IndexOf(HitRateDebugLevel));
            if (hrDebugLevelIdx < 0) hrDebugLevelIdx = 0;

            hrLastSessionDate = todaySessionDate;
            hrEngineReady = true;
            hrTodayPriceRefreshed = false;
            Print($"LiquidityLevels: Hit rate engine ready — {hrTrackedLevels.Count} levels, {hrNewDaysDetected} sessions detected");
        }

        // ── Register level price providers for ALL levels ───────────────────
        // Each provider takes a session date D and returns the level price
        // that was active FOR that session. Reconstructed from intraday bars
        // matching TV ProbabilityMap session windows.
        private void RegisterLevelProviders()
        {
            hrTrackedLevels.Clear();
            hrProviders.Clear();

            // ═══ Prior Day (daily series) ═══
            hrProviders["PDH"] = (sd) => GetPriorDailyBar(sd, "High");
            hrProviders["PDL"] = (sd) => GetPriorDailyBar(sd, "Low");
            hrProviders["PDC"] = (sd) => GetPriorDailyBar(sd, "Close");
            hrProviders["PDM"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"); return (h > 0 && l > 0) ? (h + l) / 2.0 : 0; };
            hrProviders["Settlement"] = (sd) => GetPriorDailyBar(sd, "Close");

            // ═══ Prior Week (intraday reconstruction) ═══
            hrProviders["PWH"] = (sd) => ReconstructWeekHighLow(sd, true);
            hrProviders["PWL"] = (sd) => ReconstructWeekHighLow(sd, false);
            hrProviders["PWM"] = (sd) => { double h = ReconstructWeekHighLow(sd, true), l = ReconstructWeekHighLow(sd, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };
            hrProviders["PWC"] = (sd) => ReconstructWeekClose(sd);
            hrProviders["PWO"] = (sd) => ReconstructWeekOpen(sd);
            hrProviders["MonH"] = (sd) => ReconstructDayOfWeek(sd, DayOfWeek.Monday, true);
            hrProviders["MonL"] = (sd) => ReconstructDayOfWeek(sd, DayOfWeek.Monday, false);
            hrProviders["GlbH"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 9 * 60 + 30, true, true);  // Globex 18:00→09:30
            hrProviders["GlbL"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 9 * 60 + 30, true, false);

            // ═══ Prior Month (daily series) ═══
            hrProviders["PMH"] = (sd) => GetPriorMonthHighLow(sd, true);
            hrProviders["PML"] = (sd) => GetPriorMonthHighLow(sd, false);
            hrProviders["PMM"] = (sd) => { double h = GetPriorMonthHighLow(sd, true), l = GetPriorMonthHighLow(sd, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };
            hrProviders["PMO"] = (sd) => GetPriorMonthOpen(sd);

            // ═══ Session Opens (intraday reconstruction) ═══
            hrProviders["MNO"] = (sd) => ReconstructSessionOpen(sd, 0, 0);
            hrProviders["LonO"] = (sd) => ReconstructSessionOpen(sd, 2, 0);
            hrProviders["DOpen"] = (sd) => ReconstructSessionOpen(sd, 18, 0);
            hrProviders["NYO"] = (sd) => ReconstructSessionOpen(sd, 9, 30);
            hrProviders["TueO"] = (sd) => ReconstructDayOfWeekOpen(sd, DayOfWeek.Tuesday);
            hrProviders["WedO"] = (sd) => ReconstructDayOfWeekOpen(sd, DayOfWeek.Wednesday);
            hrProviders["ThuO"] = (sd) => ReconstructDayOfWeekOpen(sd, DayOfWeek.Thursday);
            hrProviders["FriO"] = (sd) => ReconstructDayOfWeekOpen(sd, DayOfWeek.Friday);
            hrProviders["0400"] = (sd) => ReconstructSessionOpen(sd, 4, 0);
            hrProviders["0800"] = (sd) => ReconstructSessionOpen(sd, 8, 0);
            hrProviders["1200"] = (sd) => ReconstructSessionOpen(sd, 12, 0);
            hrProviders["1600"] = (sd) => ReconstructSessionOpen(sd, 16, 0);
            hrProviders["2000"] = (sd) => ReconstructSessionOpen(sd, 20, 0);

            // ═══ Session Ranges (intraday reconstruction) ═══
            // TV: inAsia = hhmm >= 1930 or hhmm < 230
            hrProviders["AsiaH"] = (sd) => ReconstructSessionRange(sd, 19 * 60 + 30, 2 * 60 + 30, true, true);
            hrProviders["AsiaL"] = (sd) => ReconstructSessionRange(sd, 19 * 60 + 30, 2 * 60 + 30, true, false);
            hrProviders["AsiaM"] = (sd) => { double h = ReconstructSessionRange(sd, 19 * 60 + 30, 2 * 60 + 30, true, true), l = ReconstructSessionRange(sd, 19 * 60 + 30, 2 * 60 + 30, true, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };

            // TV: inLondon = hhmm >= 230 and hhmm < 800
            hrProviders["LonH"] = (sd) => ReconstructSessionRange(sd, 2 * 60 + 30, 8 * 60, false, true);
            hrProviders["LonL"] = (sd) => ReconstructSessionRange(sd, 2 * 60 + 30, 8 * 60, false, false);
            hrProviders["LonM"] = (sd) => { double h = ReconstructSessionRange(sd, 2 * 60 + 30, 8 * 60, false, true), l = ReconstructSessionRange(sd, 2 * 60 + 30, 8 * 60, false, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };

            // London OR (02:00-05:00 ET for the OR sub-range)
            hrProviders["LonORM"] = (sd) => { double h = ReconstructSessionRange(sd, 2 * 60, 5 * 60, false, true), l = ReconstructSessionRange(sd, 2 * 60, 5 * 60, false, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };

            // Globex range (18:00→09:30 ET)
            hrProviders["GlbH"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 9 * 60 + 30, true, true);
            hrProviders["GlbL"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 9 * 60 + 30, true, false);
            hrProviders["GlbM"] = (sd) => { double h = ReconstructSessionRange(sd, 18 * 60, 9 * 60 + 30, true, true), l = ReconstructSessionRange(sd, 18 * 60, 9 * 60 + 30, true, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };

            // IB (09:30-10:00 ET)
            hrProviders["IBH"] = (sd) => ReconstructSessionRange(sd, 9 * 60 + 30, 10 * 60, false, true);
            hrProviders["IBL"] = (sd) => ReconstructSessionRange(sd, 9 * 60 + 30, 10 * 60, false, false);
            hrProviders["IBM"] = (sd) => { double h = ReconstructSessionRange(sd, 9 * 60 + 30, 10 * 60, false, true), l = ReconstructSessionRange(sd, 9 * 60 + 30, 10 * 60, false, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };

            // P12 (18:00-06:00 ET overnight)
            hrProviders["P12H"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, true);
            hrProviders["P12L"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, false);
            hrProviders["P12M"] = (sd) => { double h = ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, true), l = ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };

            // NY P12 (06:00-17:00 ET)
            hrProviders["NYP12H"] = (sd) => ReconstructSessionRange(sd, 6 * 60, 17 * 60, false, true);
            hrProviders["NYP12L"] = (sd) => ReconstructSessionRange(sd, 6 * 60, 17 * 60, false, false);
            hrProviders["NYP12M"] = (sd) => { double h = ReconstructSessionRange(sd, 6 * 60, 17 * 60, false, true), l = ReconstructSessionRange(sd, 6 * 60, 17 * 60, false, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };

            // Prev NY P12 (prior session date)
            hrProviders["PrevNYP12H"] = (sd) => ReconstructSessionRange(sd.AddDays(-1), 6 * 60, 17 * 60, false, true);
            hrProviders["PrevNYP12L"] = (sd) => ReconstructSessionRange(sd.AddDays(-1), 6 * 60, 17 * 60, false, false);
            hrProviders["PrevNYP12M"] = (sd) => { double h = ReconstructSessionRange(sd.AddDays(-1), 6 * 60, 17 * 60, false, true), l = ReconstructSessionRange(sd.AddDays(-1), 6 * 60, 17 * 60, false, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };

            // ═══ Pivots (computed from PDH/PDL/PDC) ═══
            hrProviders["PP"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"), c = GetPriorDailyBar(sd, "Close"); return (h > 0 && l > 0 && c > 0) ? (h + l + c) / 3.0 : 0; };
            hrProviders["R1"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"), c = GetPriorDailyBar(sd, "Close"); if (h <= 0 || l <= 0) return 0; double pp = (h + l + c) / 3.0; return 2.0 * pp - l; };
            hrProviders["R2"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"), c = GetPriorDailyBar(sd, "Close"); if (h <= 0 || l <= 0) return 0; double pp = (h + l + c) / 3.0; return pp + (h - l); };
            hrProviders["R3"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"), c = GetPriorDailyBar(sd, "Close"); if (h <= 0 || l <= 0) return 0; double pp = (h + l + c) / 3.0; return h + 2.0 * (pp - l); };
            hrProviders["S1"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"), c = GetPriorDailyBar(sd, "Close"); if (h <= 0 || l <= 0) return 0; double pp = (h + l + c) / 3.0; return 2.0 * pp - h; };
            hrProviders["S2"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"), c = GetPriorDailyBar(sd, "Close"); if (h <= 0 || l <= 0) return 0; double pp = (h + l + c) / 3.0; return pp - (h - l); };
            hrProviders["S3"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"), c = GetPriorDailyBar(sd, "Close"); if (h <= 0 || l <= 0) return 0; double pp = (h + l + c) / 3.0; return l - 2.0 * (h - pp); };

            // ═══ Fibs (computed from PDH/PDL range) ═══
            string[] fibNames = { "0.236", "0.382", "0.500", "0.618", "0.786", "1.000", "1.272", "1.618", "-0.272", "-0.618" };
            double[] fibRatios = { 0.236, 0.382, 0.500, 0.618, 0.786, 1.0, 1.272, 1.618, -0.272, -0.618 };
            for (int fi = 0; fi < fibNames.Length; fi++)
            {
                string fn = fibNames[fi];
                double fr = fibRatios[fi];
                hrProviders[fn] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"); return (h > 0 && l > 0) ? l + fr * (h - l) : 0; };
            }

            // ═══ Volume Profile fallbacks (computed from PDH/PDL) ═══
            hrProviders["PPOC"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"), c = GetPriorDailyBar(sd, "Close"); return (h > 0 && l > 0 && c > 0) ? (h + l + c) / 3.0 : 0; };
            hrProviders["PVAH"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"); return (h > 0 && l > 0) ? h - (h - l) * 0.15 : 0; };
            hrProviders["PVAL"] = (sd) => { double h = GetPriorDailyBar(sd, "High"), l = GetPriorDailyBar(sd, "Low"); return (h > 0 && l > 0) ? l + (h - l) * 0.15 : 0; };
            hrProviders["ovnPOC"] = (sd) => { double h = ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, true), l = ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, false); return (h > 0 && l > 0 && l < double.MaxValue) ? (h + l) / 2.0 : 0; };
            hrProviders["ovnVAH"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, true);
            hrProviders["ovnVAL"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, false);
            hrProviders["ovnH"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, true);
            hrProviders["ovnL"] = (sd) => ReconstructSessionRange(sd, 18 * 60, 6 * 60, true, false);

            // Add all to tracked levels list (iterate catalog to get proper order)
            foreach (var def in LiquidityLevelsCatalog.GetAllLevels())
            {
                if (hrProviders.ContainsKey(def.Name))
                    hrTrackedLevels.Add(def.Name);
            }
        }

        // ── Reconstruct prior week close (last trading day's close) ──────────
        private double ReconstructWeekClose(DateTime sessDate)
        {
            int dow = (int)sessDate.DayOfWeek;
            DateTime weekStart = sessDate.AddDays(-(dow == 0 ? 6 : dow - 1));
            DateTime prevWeekEnd = weekStart.AddDays(-1);
            double result = 0;
            for (int i = 0; i < BarsArray[1].Count; i++)
            {
                DateTime dEt = ToEt(BarsArray[1].GetTime(i));
                DateTime dSessDate = HrSessionDateFromBarEt(dEt);
                if (dSessDate > prevWeekEnd) break;
                if (dSessDate >= weekStart.AddDays(-7) && dSessDate <= prevWeekEnd)
                    result = BarsArray[1].GetClose(i);
            }
            return result;
        }

        // ── Reconstruct prior week open (first trading day's open) ───────────
        private double ReconstructWeekOpen(DateTime sessDate)
        {
            int dow = (int)sessDate.DayOfWeek;
            DateTime weekStart = sessDate.AddDays(-(dow == 0 ? 6 : dow - 1));
            DateTime prevWeekStart = weekStart.AddDays(-7);
            for (int i = 0; i < BarsArray[1].Count; i++)
            {
                DateTime dEt = ToEt(BarsArray[1].GetTime(i));
                DateTime dSessDate = HrSessionDateFromBarEt(dEt);
                if (dSessDate >= prevWeekStart)
                    return BarsArray[1].GetOpen(i);
            }
            return 0;
        }

        // ── Reconstruct a specific day-of-week's high/low for the current week ─
        private double ReconstructDayOfWeek(DateTime sessDate, DayOfWeek targetDay, bool isHigh)
        {
            int dow = (int)sessDate.DayOfWeek;
            DateTime weekStart = sessDate.AddDays(-(dow == 0 ? 6 : dow - 1));
            DateTime targetDate = weekStart.AddDays((int)targetDay - 1);
            double result = isHigh ? 0 : double.MaxValue;
            for (int i = 0; i < BarsArray[1].Count; i++)
            {
                DateTime dEt = ToEt(BarsArray[1].GetTime(i));
                DateTime dSessDate = HrSessionDateFromBarEt(dEt);
                if (dSessDate != targetDate) continue;
                if (isHigh) { if (BarsArray[1].GetHigh(i) > result) result = BarsArray[1].GetHigh(i); }
                else { if (BarsArray[1].GetLow(i) < result) result = BarsArray[1].GetLow(i); }
            }
            return isHigh ? result : (result == double.MaxValue ? 0 : result);
        }

        // ── Reconstruct a specific day-of-week's open for the current week ────
        private double ReconstructDayOfWeekOpen(DateTime sessDate, DayOfWeek targetDay)
        {
            int dow = (int)sessDate.DayOfWeek;
            DateTime weekStart = sessDate.AddDays(-(dow == 0 ? 6 : dow - 1));
            DateTime targetDate = weekStart.AddDays((int)targetDay - 1);
            for (int i = 0; i < BarsArray[1].Count; i++)
            {
                DateTime dEt = ToEt(BarsArray[1].GetTime(i));
                DateTime dSessDate = HrSessionDateFromBarEt(dEt);
                if (dSessDate == targetDate)
                    return BarsArray[1].GetOpen(i);
            }
            return 0;
        }

        // ── Reconstruct prior month open ─────────────────────────────────────
        private double GetPriorMonthOpen(DateTime sessDate)
        {
            DateTime prevMonth = sessDate.AddMonths(-1);
            for (int i = 0; i < BarsArray[1].Count; i++)
            {
                DateTime dEt = ToEt(BarsArray[1].GetTime(i));
                if (dEt.Year == prevMonth.Year && dEt.Month == prevMonth.Month)
                    return BarsArray[1].GetOpen(i);
            }
            return 0;
        }

        // ── Get prior day OHLC from daily series ──────────────────────────────
        private double GetPriorDailyBar(DateTime sessDate, string field)
        {
            for (int i = BarsArray[1].Count - 1; i >= 0; i--)
            {
                DateTime dEt = ToEt(BarsArray[1].GetTime(i));
                DateTime dSessDate = HrSessionDateFromBarEt(dEt);
                if (dSessDate < sessDate)
                {
                    switch (field)
                    {
                        case "High": return BarsArray[1].GetHigh(i);
                        case "Low": return BarsArray[1].GetLow(i);
                        case "Close": return BarsArray[1].GetClose(i);
                        case "Open": return BarsArray[1].GetOpen(i);
                    }
                }
            }
            return 0;
        }

        // ── Reconstruct session open price at a specific ET hour:minute ───────
        private double ReconstructSessionOpen(DateTime sessDate, int hour, int minute)
        {
            int targetMins = hour * 60 + minute;
            // Session opens are set on the session date itself
            for (int i = 0; i < BarsArray[0].Count; i++)
            {
                DateTime bt = ToEt(BarsArray[0].GetTime(i));
                DateTime bSessDate = HrSessionDateFromBarEt(bt);
                if (bSessDate < sessDate) continue;
                if (bSessDate > sessDate) break;
                int barMins = bt.Hour * 60 + bt.Minute;
                // First bar at or after the target time on the session date
                if (barMins >= targetMins)
                    return BarsArray[0].GetOpen(i);
            }
            return 0;
        }

        // ── Reconstruct session range high/low for a given window ─────────────
        // crossesMidnight: window spans midnight ET (e.g., Asia 19:30→02:30)
        // isHigh: true = return high, false = return low
        private double ReconstructSessionRange(DateTime sessDate, int startMin, int endMin,
            bool crossesMidnight, bool isHigh)
        {
            double result = isHigh ? 0 : double.MaxValue;

            if (crossesMidnight)
            {
                // Window: startMin on (sessDate-1) → endMin on sessDate
                // e.g., P12: 18:00 prev day → 06:00 session day
                // e.g., Asia: 19:30 prev day → 02:30 session day
                DateTime windowStart = sessDate.AddDays(-1).Date;
                DateTime windowEnd = sessDate.Date;
                for (int i = 0; i < BarsArray[0].Count; i++)
                {
                    DateTime bt = ToEt(BarsArray[0].GetTime(i));
                    if (bt.Date < windowStart) continue;
                    if (bt.Date > windowEnd) break;
                    int barMins = bt.Hour * 60 + bt.Minute;
                    // On prev day: barMins >= startMin; On session day: barMins <= endMin
                    bool inWindow = (bt.Date == windowStart && barMins >= startMin) ||
                                    (bt.Date == windowEnd && barMins <= endMin);
                    if (!inWindow) continue;
                    double val = isHigh ? BarsArray[0].GetHigh(i) : BarsArray[0].GetLow(i);
                    if (isHigh && val > result) result = val;
                    if (!isHigh && val < result) result = val;
                }
            }
            else
            {
                // Same-day window: startMin → endMin on sessDate
                DateTime windowDate = sessDate.Date;
                for (int i = 0; i < BarsArray[0].Count; i++)
                {
                    DateTime bt = ToEt(BarsArray[0].GetTime(i));
                    DateTime bSessDate = HrSessionDateFromBarEt(bt);
                    if (bSessDate < sessDate) continue;
                    if (bSessDate > sessDate) break;
                    int barMins = bt.Hour * 60 + bt.Minute;
                    if (barMins < startMin || barMins > endMin) continue;
                    double val = isHigh ? BarsArray[0].GetHigh(i) : BarsArray[0].GetLow(i);
                    if (isHigh && val > result) result = val;
                    if (!isHigh && val < result) result = val;
                }
            }
            return isHigh ? result : (result == double.MaxValue ? 0 : result);
        }

        // ── Reconstruct prior week high/low ───────────────────────────────────
        // Week = 5 trading days prior to sessDate (not including sessDate's session)
        private double ReconstructWeekHighLow(DateTime sessDate, bool isHigh)
        {
            double result = isHigh ? 0 : double.MaxValue;
            // Find the start of the current week (Monday) and go back one week
            // For futures, the week starts at Globex open Sunday/Monday 18:00 ET
            int dow = (int)sessDate.DayOfWeek;  // 0=Sun, 1=Mon, ... 6=Sat
            DateTime weekStart = sessDate.AddDays(-(dow == 0 ? 6 : dow - 1));  // Monday of sessDate's week
            DateTime prevWeekStart = weekStart.AddDays(-7);
            DateTime prevWeekEnd = weekStart.AddDays(-1);

            for (int i = 0; i < BarsArray[0].Count; i++)
            {
                DateTime bt = ToEt(BarsArray[0].GetTime(i));
                DateTime bSessDate = HrSessionDateFromBarEt(bt);
                if (bSessDate < prevWeekStart) continue;
                if (bSessDate > prevWeekEnd) break;
                double h = BarsArray[0].GetHigh(i);
                double l = BarsArray[0].GetLow(i);
                if (isHigh && h > result) result = h;
                if (!isHigh && l < result) result = l;
            }
            return isHigh ? result : (result == double.MaxValue ? 0 : result);
        }

        // ── Reconstruct prior month high/low ──────────────────────────────────
        private double GetPriorMonthHighLow(DateTime sessDate, bool isHigh)
        {
            double result = isHigh ? 0 : double.MaxValue;
            int targetMonth = sessDate.AddMonths(-1).Month;
            int targetYear = sessDate.AddMonths(-1).Year;

            for (int i = 0; i < BarsArray[1].Count; i++)
            {
                DateTime dEt = ToEt(BarsArray[1].GetTime(i));
                if (dEt.Year == targetYear && dEt.Month == targetMonth)
                {
                    double h = BarsArray[1].GetHigh(i);
                    double l = BarsArray[1].GetLow(i);
                    if (isHigh && h > result) result = h;
                    if (!isHigh && l < result) result = l;
                }
            }
            return isHigh ? result : (result == double.MaxValue ? 0 : result);
        }

        // ── Get today's live level price (from the indicator's current state) ──
        private double GetTodayLevelPrice(string levelName)
        {
            var level = GetLevel(levelName);
            return level?.Price ?? 0;
        }

        // ── Live update within today's window (called from OnBarUpdate) ─────
        private void HrAdvanceToday(DateTime barEt, double barHigh, double barLow)
        {
            if (!hrEngineReady || !EnableHitRate) return;
            int barMins = barEt.Hour * 60 + barEt.Minute;
            if (!hrWindow.InWindow(barMins)) return;

            foreach (var levelName in hrTrackedLevels)
            {
                if (!hrTodayHit.ContainsKey(levelName)) continue;
                if (hrTodayHit[levelName]) continue;  // first hit only

                double price = hrTodayLevel.ContainsKey(levelName) ? hrTodayLevel[levelName] : 0;
                if (price <= 0)
                {
                    // Refresh today's price if not yet set
                    price = GetTodayLevelPrice(levelName);
                    if (price <= 0) continue;
                    hrTodayLevel[levelName] = price;
                }

                if (barHigh >= price && barLow <= price)
                {
                    hrTodayHit[levelName] = true;
                    hrTodayHitMin[levelName] = barMins;
                }
            }
        }

        // ── Commit today's results into history on day rollover ──────────────
        private void HrCommitDay(DateTime newSessionDate)
        {
            if (!hrEngineReady || !EnableHitRate) return;

            // Commit the previous session's results
            foreach (var levelName in hrTrackedLevels)
            {
                if (!hrHistory.ContainsKey(levelName)) continue;
                if (!hrTodayHit.ContainsKey(levelName)) continue;

                double levelPrice = hrTodayLevel.ContainsKey(levelName) ? hrTodayLevel[levelName] : 0;
                bool hit = hrTodayHit[levelName];
                int hitMin = hrTodayHitMin.ContainsKey(levelName) ? hrTodayHitMin[levelName] : 0;

                var sample = HitRateEngine.CommitToday(levelName, hrLastSessionDate, levelPrice, hit, hitMin);
                hrHistory[levelName].Add(sample);

                // Trim to lookback
                hrHistory[levelName] = HitRateEngine.TrimHistory(hrHistory[levelName], hrCfg.LookbackDays);
            }

            // Recompute stats for all levels
            foreach (var levelName in hrTrackedLevels)
            {
                if (!hrHistory.ContainsKey(levelName)) continue;
                double todayPrice = GetTodayLevelPrice(levelName);
                hrTodayLevel[levelName] = todayPrice;
                hrTodayHit[levelName] = false;
                hrTodayHitMin[levelName] = 0;

                DateTime lastBarEtC = ToEt(BarsArray[0].GetTime(BarsArray[0].Count - 1));
                bool inWindow = hrWindow.InWindow(lastBarEtC.Hour * 60 + lastBarEtC.Minute);
                hrStats[levelName] = HitRateEngine.ComputeStats(
                    levelName, hrHistory[levelName], todayPrice, false, inWindow,
                    CurrentBar, hrNewDaysDetected, hrCfg, hrWindow);
            }

            hrLastSessionDate = newSessionDate;
        }

        // ── Refresh stats for a level (called when lookback/window changes) ──
        private void HrRefreshStats()
        {
            if (!hrEngineReady || !EnableHitRate) return;

            hrCfg.LookbackDays = HitRateLookbackDays;

            int startMin = HitWindow.TimeStrToMin(HitRateWindowStart);
            int endMin = HitWindow.TimeStrToMin(HitRateWindowEnd);
            if (startMin >= 0 && endMin >= 0)
            {
                hrWindow.StartMin = startMin;
                hrWindow.EndMin = endMin;
            }

            DateTime lastBarEtR = ToEt(BarsArray[0].GetTime(BarsArray[0].Count - 1));
            DateTime todaySessDate = HrSessionDateFromBarEt(lastBarEtR);
            var historicalSessions = hrSessionBars
                .Where(s => s.SessionDate < todaySessDate)
                .ToList();

            foreach (var levelName in hrTrackedLevels)
            {
                if (!hrProviders.TryGetValue(levelName, out var provider)) continue;
                var history = HitRateEngine.BuildHistory(levelName, provider, historicalSessions, hrCfg);
                hrHistory[levelName] = history;

                double todayPrice = GetTodayLevelPrice(levelName);
                hrTodayLevel[levelName] = todayPrice;
                bool inWindow = hrWindow.InWindow(lastBarEtR.Hour * 60 + lastBarEtR.Minute);
                hrStats[levelName] = HitRateEngine.ComputeStats(
                    levelName, history, todayPrice, hrTodayHit.ContainsKey(levelName) && hrTodayHit[levelName],
                    inWindow, CurrentBar, hrNewDaysDetected, hrCfg, hrWindow);
            }
        }

        // ── Cycle debug level on click ───────────────────────────────────────
        private void HrCycleDebugLevel()
        {
            if (hrTrackedLevels.Count == 0) return;
            hrDebugLevelIdx = (hrDebugLevelIdx + 1) % hrTrackedLevels.Count;
            HitRateDebugLevel = hrTrackedLevels[hrDebugLevelIdx];
        }

        // ── Render the debug table (top-right corner) ────────────────────────
        private void RenderHitRateDebugTable(ChartControl chartControl, bool isDark)
        {
            if (!ShowHitRateDebugTable || !hrEngineReady || hrTrackedLevels.Count == 0) return;
            if (!hrStats.TryGetValue(HitRateDebugLevel, out var stats)) return;
            if (stats == null) return;

            var lines = new List<string>
            {
                "Hit Rate Debug",
                $"Level,{HitRateDebugLevel}",
                $"HR Enabled?,{EnableHitRate}",
                $"Days in history,{stats.DaysInHistory}",
                $"{HitRateDebugLevel} hit_rate,{stats.HitRate:F1}%",
                $"{HitRateDebugLevel} total_hits,{stats.TotalHits}",
                $"{HitRateDebugLevel} streak,{stats.CurrentStreak}",
                $"{HitRateDebugLevel} max hits/miss,{stats.MaxHitStreak}/{stats.MaxMissStreak}",
                $"Today {HitRateDebugLevel} price,{stats.TodayPrice:F2}",
                $"Today {HitRateDebugLevel} hit?,{stats.TodayHit}",
                $"In time window?,{stats.InWindow}",
                $"Time Window,{stats.TimeWindowLabel}",
                $"New days detected,{stats.NewDaysDetected}",
                $"Local_Index,{stats.LocalIndex}",
                $"Lookback (days),{stats.LookbackDays}",
                "--- Recent History ---",
                $"Last 10 days,{stats.RecentHistoryString}",
                $"Recent 10 Hits,{stats.RecentHitsCount}/{stats.RecentN}",
                $"Streak config,{stats.StreakMinHits} Hit",
            };

            float padX = 8f;
            float padY = 5f;
            float lineHeight = 15f;

            // Measure max width
            float maxW = 0f;
            var measureFormat = textFormat ?? tooltipFormat;
            if (measureFormat == null) return;
            foreach (var line in lines)
            {
                using (var tl = new SharpDX.DirectWrite.TextLayout(
                    Core.Globals.DirectWriteFactory, line, measureFormat, float.MaxValue, float.MaxValue))
                {
                    if (tl.Metrics.Width > maxW) maxW = tl.Metrics.Width;
                }
            }

            float boxW = maxW + padX * 2;
            float boxH = lines.Count * lineHeight + padY * 2;

            // Top-right corner — moved further left (margin 60) so long level names
            // like "PrevNYP12High" don't get clipped by the right price axis
            float boxX = (float)chartControl.ActualWidth - boxW - 60;
            float boxY = 10;

            hrDebugTableRect = new RectangleF(boxX, boxY, boxW, boxH);

            var bgBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.05f, 0.07f, 0.10f, 0.92f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.97f, 0.97f, 0.99f, 0.95f));

            var borderBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.2f, 0.6f, 1.0f, 0.8f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.1f, 0.4f, 0.8f, 0.8f));

            var headerBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.4f, 0.8f, 1.0f, 1.0f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.05f, 0.3f, 0.6f, 1.0f));

            var textBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.82f, 0.85f, 0.90f, 1.0f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.10f, 0.12f, 0.16f, 1.0f));

            RenderTarget.FillRectangle(hrDebugTableRect, bgBrush);
            RenderTarget.DrawRectangle(hrDebugTableRect, borderBrush, 1.0f);

            float textY = boxY + padY;
            for (int i = 0; i < lines.Count; i++)
            {
                var brush = (i == 0) ? headerBrush : textBrush;
                using (var tl = new SharpDX.DirectWrite.TextLayout(
                    Core.Globals.DirectWriteFactory, lines[i], measureFormat, float.MaxValue, float.MaxValue))
                {
                    RenderTarget.DrawTextLayout(new SharpDX.Vector2(boxX + padX, textY), tl, brush);
                }
                textY += lineHeight;
            }

            bgBrush.Dispose();
            borderBrush.Dispose();
            headerBrush.Dispose();
            textBrush.Dispose();
        }

        // ── Check if mouse click is on debug table and cycle ──────────────────
        private void HrCheckDebugTableClick(float mouseX, float mouseY)
        {
            if (!ShowHitRateDebugTable || !hrEngineReady) return;
            if (hrDebugTableRect.Contains(mouseX, mouseY))
            {
                HrCycleDebugLevel();
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
            // Fast path: use cached HashSet if available
            if (!enabledCacheDirty && enabledLevelNames != null)
                return enabledLevelNames.Contains(level.Def.Name);

            return IsLevelEnabledSlow(level);
        }

        private void RebuildEnabledCache()
        {
            if (enabledLevelNames == null)
                enabledLevelNames = new HashSet<string>();
            else
                enabledLevelNames.Clear();

            foreach (var level in activeLevels)
            {
                if (IsLevelEnabledSlow(level))
                    enabledLevelNames.Add(level.Def.Name);
            }
            enabledCacheDirty = false;
        }

        private bool IsLevelEnabledSlow(LevelState level)
        {
            if (!IsCategoryEnabled(level.Def.Category)) return false;

            string name = level.Def.Name;

            // 1. Prior Day / Week / Month
            if (name == "PDH" && !ShowPDH) return false;
            if (name == "PDL" && !ShowPDL) return false;
            if (name == "PDC" && !ShowPDC) return false;
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
            if (name == "MNO" && !ShowMidnightOpen) return false;
            if (name == "LonO" && !ShowLondonOpen) return false;
            if (name == "NYO" && !ShowRTHOpen) return false;
            if (name == "DOpen" && !ShowGlobexOpen) return false;

            if (name == "0400" && !ShowOpen04H) return false;
            if (name == "0800" && !ShowOpen08H) return false;
            if (name == "1200" && !ShowOpen12H) return false;
            if (name == "1600" && !ShowOpen16H) return false;
            if (name == "2000" && !ShowOpen20H) return false;

            if (name == "TueO" && !ShowTueOpen) return false;
            if (name == "WedO" && !ShowWedOpen) return false;
            if (name == "ThuO" && !ShowThuOpen) return false;
            if (name == "FriO" && !ShowFriOpen) return false;

            // 3. Session Ranges
            if ((name == "AsiaH" || name == "AsiaL" || name == "AsiaM") && !ShowAsiaRange) return false;
            if ((name == "LonH" || name == "LonL" || name == "LonM" || name == "LonORM") && !ShowLondonRange) return false;
            if ((name == "GlbH" || name == "GlbL" || name == "GlbM") && !ShowGlobexRange) return false;
            if ((name == "IBH" || name == "IBL" || name == "IBM") && !ShowIB) return false;
            if (name == "P12H" || name == "P12L" || name == "P12M") { if (!ShowP12) return false; }
            if ((name == "NYP12H" || name == "NYP12L" || name == "NYP12M") && !ShowNYP12) return false;
            if ((name == "PrevNYP12H" || name == "PrevNYP12L" || name == "PrevNYP12M") && !ShowNYP12) return false;

            // 4. Pivots & Fibs
            if (name == "PP" && !ShowPivotPP) return false;
            if ((name == "R1" || name == "S1") && !ShowPivotR1S1) return false;
            if ((name == "R2" || name == "S2") && !ShowPivotR2S2) return false;
            if ((name == "R3" || name == "S3") && !ShowPivotR3S3) return false;

            if (name == "0.236" && !ShowFib236) return false;
            if (name == "0.382" && !ShowFib382) return false;
            if (name == "0.500" && !ShowFib500) return false;
            if (name == "0.618" && !ShowFib618) return false;
            if (name == "0.786" && !ShowFib786) return false;
            if (name == "1.000" && !ShowFib100) return false;
            if ((name == "1.272" || name == "1.618" || name == "-0.272" || name == "-0.618") && !ShowFibExt) return false;

            // 5. Volume Profile & Intraday
            if (name == "HOD" && !ShowHOD) return false;
            if (name == "LOD" && !ShowLOD) return false;

            if (name == "POC" && !ShowCurrentPOC) return false;
            if ((name == "VAH" || name == "VAL") && !ShowCurrentVA) return false;
            if (name == "PPOC" && !ShowPrevDayPOC) return false;
            if ((name == "PVAH" || name == "PVAL") && !ShowPrevDayVA) return false;
            if ((name == "ovnPOC" || name == "ovnVAH" || name == "ovnVAL" || name == "ovnH" || name == "ovnL") && !ShowOvernightPOC) return false;

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
                // Hit rate: commit previous day's results before resetting
                // Only on the live bar (not historical replay) to avoid duplicating history
                if (hrEngineReady && EnableHitRate && hrLastSessionDate != DateTime.MinValue
                    && CurrentBar == BarsArray[0].Count - 1)
                    HrCommitDay(globexDate);

                lastDate = globexDate;
                dayStartBar = CurrentBar;
                todaySweeps.Clear();
                enabledCacheDirty = true;
                activeLevelsDirty = true;

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

            // Hit rate: refresh TodayPrice on first live bar (sub-indicators not ready during DataLoaded)
            if (hrEngineReady && EnableHitRate && !hrTodayPriceRefreshed && CurrentBar == BarsArray[0].Count - 1)
            {
                foreach (var levelName in hrTrackedLevels)
                {
                    double tp = GetTodayLevelPrice(levelName);
                    if (tp > 0)
                    {
                        hrTodayLevel[levelName] = tp;
                        if (hrStats.ContainsKey(levelName))
                            hrStats[levelName].TodayPrice = tp;
                    }
                }
                hrTodayPriceRefreshed = true;
            }

            // Hit rate: live update within today's window (first-hit only, live bar only)
            if (hrEngineReady && EnableHitRate && CurrentBar == BarsArray[0].Count - 1)
                HrAdvanceToday(barTimeEt, highP, lowP);

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
            if (enabledCacheDirty)
                RebuildEnabledCache();

            DateTime currentEtDate = ToEt(Time[0]).Date;

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

                // Sync to NtTagRenderer data model — diff-guarded, zero-alloc on no-change
                if (level.IsActive)
                {
                    string key = NtTagRenderer.InstanceKey(level.Def.Name, currentEtDate);

                    if (levelRenderer.TryGetRecord(key, out var existing))
                    {
                        // Mutate in-place if price changed (avoids NtLevelRecord allocation)
                        if (Math.Abs(existing.Price - level.Price) >= TickSize / 2.0)
                            existing.Price = level.Price;
                    }
                    else
                    {
                        // First time seeing this key — allocate
                        levelRenderer.Upsert(new NtLevelRecord
                        {
                            Key = key,
                            Label = level.Def.Name,
                            Price = level.Price,
                            Category = "price_level",
                            Date = currentEtDate,
                            State = "active"
                        });
                    }
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

                case "TueO": return tueOpen;
                case "WedO": return wedOpen;
                case "ThuO": return thuOpen;
                case "FriO": return friOpen;

                case "P12H": return p12High;
                case "P12L": return p12Low;
                case "P12M": return (p12High > 0 && p12Low > 0) ? (p12High + p12Low) / 2.0 : 0;

                case "NYP12H": return nyP12High;
                case "NYP12L": return nyP12Low;
                case "NYP12M": return (nyP12High > 0 && nyP12Low > 0) ? (nyP12High + nyP12Low) / 2.0 : 0;

                case "PrevNYP12H": return prevNyP12High;
                case "PrevNYP12L": return prevNyP12Low;
                case "PrevNYP12M": return prevNyP12Mid;

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
            activeLevelsDirty = true;
        }

        #endregion

        #region Public API

        public List<LevelState> GetActiveLevels()
        {
            if (activeLevelsDirty || cachedActiveLevels == null)
            {
                if (enabledCacheDirty)
                    RebuildEnabledCache();

                cachedActiveLevels = activeLevels
                    .Where(l => enabledLevelNames.Contains(l.Def.Name) && l.IsActive && l.Price > 0)
                    .OrderBy(l => l.Price)
                    .ToList();
                activeLevelsDirty = false;
            }
            return cachedActiveLevels;
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

        // ── Hit Rate Public API ──
        /// <summary>Get hit-rate statistics for a specific level by name (e.g. "PDH", "P12High").</summary>
        public LevelHitStats GetHitRateStats(string levelName)
        {
            if (hrStats != null && hrStats.TryGetValue(levelName, out var stats))
                return stats;
            return null;
        }

        /// <summary>Get all computed hit-rate statistics, keyed by level name.</summary>
        public Dictionary<string, LevelHitStats> GetAllHitRateStats()
        {
            return hrStats != null ? new Dictionary<string, LevelHitStats>(hrStats) : new Dictionary<string, LevelHitStats>();
        }

        /// <summary>List of level names currently being tracked for hit rate.</summary>
        public List<string> GetHitRateTrackedLevels()
        {
            return hrTrackedLevels != null ? new List<string>(hrTrackedLevels) : new List<string>();
        }

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
                cachedBadgeHeight = 0f; // invalidate height cache on font change
            }

            var activeLevelsToDraw = GetActiveLevels();

            // v5: resolve category colors through the canonical scheme system
            // (NtPalette) — cached, only rebuilt when scheme changes
            NtScheme scheme = NtPalette.DetectScheme(chartControl.Properties.ChartBackground as System.Windows.Media.SolidColorBrush);
            bool isDark = scheme == NtScheme.Midnight;

            if (categoryColorsDirty || cachedScheme != scheme || cachedCategoryColors == null)
            {
                cachedScheme = scheme;
                cachedCategoryColors = new Dictionary<LevelCategory, SharpDX.Color>
                {
                    { LevelCategory.PriorDay,     NtPalette.Resolve(NtPalette.Bull, scheme) },
                    { LevelCategory.PriorWeek,    NtPalette.Resolve(NtPalette.Average, scheme) },
                    { LevelCategory.PriorMonth,   NtPalette.Resolve(NtPalette.Pivot, scheme) },
                    { LevelCategory.SessionOpen,  NtPalette.Resolve(NtPalette.Caution, scheme) },
                    { LevelCategory.SessionRange, NtPalette.Resolve(NtPalette.Pivot, scheme) },
                    { LevelCategory.Intraday,     NtPalette.Resolve(NtPalette.Bull, scheme) },
                    { LevelCategory.VolumeProfile,NtPalette.Resolve(NtPalette.Stretch, scheme) },
                    { LevelCategory.Structure,    NtPalette.Resolve(NtPalette.Ny2, scheme) },
                    { LevelCategory.Pivot,        NtPalette.Resolve(NtPalette.MaxReversal, scheme) },
                    { LevelCategory.Fib,          NtPalette.Resolve(NtPalette.Median, scheme) },
                };
                categoryColorsDirty = false;
            }
            var categoryColors = cachedCategoryColors;

            float chartLeftX = chartControl.GetXByBarIndex(ChartBars, ChartBars.FromIndex);
            float chartRightX = chartControl.GetXByBarIndex(ChartBars, ChartBars.ToIndex) + (float)chartControl.Properties.BarDistance;

            double currentPrice = Close[0];
            reusableLabelItems.Clear();

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

                    reusableLabelItems.Add(new RenderLabelItem
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
            if (reusableLabelItems.Count > 0)
            {
                var sortedLabels = reusableLabelItems.OrderBy(l => l.Y).ToList();
                float minSpacing = 16f;

                // 1. Render Right Margin Labels (Y-Staggered) — v5 NtBadge pills
                if (LabelPlacement == LabelPlacement.RightMargin || LabelPlacement == LabelPlacement.Both)
                {
                    // Cache text height once (all labels use same font/format)
                    if (cachedBadgeHeight == 0f && textFormat != null)
                    {
                        using (var measureLayout = new TextLayout(Core.Globals.DirectWriteFactory, "Ay", textFormat, float.MaxValue, float.MaxValue))
                        {
                            cachedBadgeHeight = (float)measureLayout.Metrics.Height;
                        }
                    }
                    float textH = cachedBadgeHeight;

                    float prevY = -1000f;
                    foreach (var item in sortedLabels)
                    {
                        float labelY = item.Y - textH / 2f;

                        if (labelY < prevY + minSpacing)
                            labelY = prevY + minSpacing;
                        prevY = labelY;

                        var textColor = new Color4(item.Color.R / 255f, item.Color.G / 255f, item.Color.B / 255f, 1.0f);
                        NtBadge.Draw(RenderTarget, textFormat, item.Text, textColor, chartRightX + 4, labelY);
                    }
                }

                // 2. Render Origin Labels (Y-Staggered) — v5 NtBadge pills
                if (LabelPlacement == LabelPlacement.Origin || LabelPlacement == LabelPlacement.Both)
                {
                    float textH = cachedBadgeHeight;
                    float prevY = -1000f;
                    foreach (var item in sortedLabels)
                    {
                        float labelY = item.Y - textH / 2f;

                        if (labelY < prevY + minSpacing)
                            labelY = prevY + minSpacing;
                        prevY = labelY;

                        var textColor = new Color4(item.Color.R / 255f, item.Color.G / 255f, item.Color.B / 255f, 1.0f);
                        NtBadge.Draw(RenderTarget, textFormat, item.Text, textColor, item.XStart + 4, labelY);
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

                    // v5: Route sweep marker colors through NtPalette (scheme-aware, no isDark branching)
                    var markerColor = NtPalette.Resolve(sweep.IsBullSweep ? NtPalette.Bull : NtPalette.Bear, scheme);

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
                        // Hit rate debug table click-to-cycle
                        if (System.Windows.Input.Mouse.LeftButton == System.Windows.Input.MouseButtonState.Pressed)
                        {
                            try { HrCheckDebugTableClick(mouseX, mouseY); } catch {}
                        }

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

            // Hit rate debug table (top-right corner)
            try
            {
                RenderHitRateDebugTable(chartControl, isDark);
            }
            catch {}
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

            // Hit rate stats block (if enabled and stats available for this level)
            if (ShowHitRateTooltips && hrEngineReady && hrStats != null)
            {
                string hrLevelName = level.Def.Name;
                if (hrStats.TryGetValue(hrLevelName, out var hrStat) && hrStat != null && hrStat.DaysInHistory > 0)
                {
                    lines.Add($"── {hrLevelName} Hit Rate Stats ──");
                    lines.Add($"Hit Ratio: {hrStat.HitRate:F1}%");
                    lines.Add($"Days Tracked: {hrStat.DaysInHistory}");
                    lines.Add($"Current Streak: {hrStat.CurrentStreakDisplay}");
                    lines.Add($"Max Hit Streak: {hrStat.MaxHitStreak}");
                    lines.Add($"Max Miss Streak: -{hrStat.MaxMissStreak}");
                }
            }

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

            // v5: Route tooltip brushes through NtStyleResolver (scheme-aware, no isDark branching)
            NtScheme scheme = NtPalette.DetectScheme(chartControl.Properties.ChartBackground as System.Windows.Media.SolidColorBrush);
            var bgBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, NtStyleResolver.ResolveColor(NtPalette.BgSecondary, scheme, 5, NtDisplayProfile.Normal));
            var borderBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, NtStyleResolver.ResolveColor(NtPalette.BgBorder, scheme, 10, NtDisplayProfile.Normal));
            var titleBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, NtStyleResolver.ResolveColor(NtPalette.TextPrimary, scheme));
            var textBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, NtStyleResolver.ResolveColor(NtPalette.TextSecondary, scheme));
            var sweptBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, NtStyleResolver.ResolveColor(NtPalette.Bear, scheme));

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