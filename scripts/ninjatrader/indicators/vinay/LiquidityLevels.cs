// ═══════════════════════════════════════════════════════════════════════════
// LiquidityLevels.cs — Unified liquidity levels indicator for NT8
//
// Aggregates ALL liquidity levels (prior day/week/month, session opens,
// intraday, volume profile, structure) into one indicator with:
//   - Public API: GetActiveLevels(), GetSweepEvents(), GetLevelPrice()
//   - SessionOpensEngine: midnight/4H/London/NY opens (NEW — fills §10a gap)
//   - SweepDetector: wick/body sweep detection on all SweepTarget levels
//   - SharpDX rendering: horizontal lines + labels + sweep markers
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

        // Built-in indicators (called inline, not added as chart indicators)
        private double priorHigh, priorLow, priorClose;
        private double currentHigh, currentLow, currentOpen;

        // Sweep config
        private double tickSize;
        private double prevClose;

        // SharpDX
        private SharpDX.DirectWrite.TextFormat textFormat;
        private bool resourcesCreated;

        #endregion

        #region NinjaScript Properties

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

        #endregion

        #region OnStateChange

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Unified liquidity levels indicator (52+ levels + session opens + sweep detection)";
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
                if (!level.IsActive) continue;

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

                    // RedTail indicators will be integrated in P5
                    // For now, these levels stay at Price=0
                    case LevelSource.RedTailKeyLevels:
                    case LevelSource.RedTailVolumeProfile:
                    case LevelSource.RedTailMarketStructure:
                    case LevelSource.SessionRanges:
                        // TODO P5: read from composed indicators
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
            double pdh = PriorDayOHLC().PriorHigh[0];
            double pdl = PriorDayOHLC().PriorLow[0];
            double pdc = PriorDayOHLC().PriorClose[0];

            switch (accessor)
            {
                // Prior Day Mid = (PDH + PDL) / 2
                case "PriorDayMid":
                    return (pdh > 0 && pdl > 0) ? (pdh + pdl) / 2.0 : 0;

                // Settlement = prior day close (futures settlement ~ PDC for daily)
                case "Settlement":
                    return pdc;

                // Prior Week Mid = (PWH + PWL) / 2 (P5: from RedTailKeyLevels)
                case "PriorWeekMid":
                    return 0;

                // Prior Week Close (settlement close)
                case "PriorWeekClose":
                    return UpdatePriorWeekClose();

                // Prior Month Mid = (PMH + PML) / 2 (P5: from RedTailKeyLevels)
                case "PriorMonthMid":
                    return 0;

                // P12 (18:00-06:00 ET overnight range)
                case "P12High": return p12High;
                case "P12Low": return p12Low;
                case "P12Mid": return (p12High > 0 && p12Low > 0) ? (p12High + p12Low) / 2.0 : 0;

                // NY P12 (06:00-17:00 ET NY session range)
                case "NYP12High": return nyP12High;
                case "NYP12Low": return nyP12Low;
                case "NYP12Mid": return (nyP12High > 0 && nyP12Low > 0) ? (nyP12High + nyP12Low) / 2.0 : 0;

                // Prev NY P12
                case "PrevNYP12High": return prevNyP12High;
                case "PrevNYP12Low": return prevNyP12Low;
                case "PrevNYP12Mid": return prevNyP12Mid;

                // Session mids (P6: from SessionRanges)
                case "Asia Range.Mid":
                case "London Range.Mid":
                case "London OR.Mid":
                case "Globex Range.Mid":
                    return 0;

                default:
                    return 0;
            }
        }

        // Track prior week close: capture Close[0] on the last bar of each week
        // (Friday ~16:00 ET or the last available bar before weekend)
        private double UpdatePriorWeekClose()
        {
            DateTime barEt = ToEt(Time[0]);
            DayOfWeek dow = barEt.DayOfWeek;

            // Capture the close on Friday after 15:00 ET (near session close)
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

        // ═══ P12 range tracking (18:00-06:00 ET overnight) ═══
        // Mirrors Profiler's p12_h/p12_l: the overnight range from 18:00 to 06:00 ET
        private void UpdateP12Ranges(DateTime barEt, double high, double low)
        {
            int barMins = barEt.Hour * 60 + barEt.Minute;
            DateTime today = barEt.Date;

            // P12: 18:00-06:00 ET (crosses midnight)
            // Reset at 18:00 ET each day
            if (barMins >= 18 * 60 && (p12Date != today || !p12Building))
            {
                // Archive previous day's NY P12 before reset
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
                // P12 builds from 18:00 to 06:00 next day
                bool inP12 = barMins >= 18 * 60 || barMins < 6 * 60;
                if (inP12)
                {
                    if (high > p12High) p12High = high;
                    if (low < p12Low) p12Low = low;
                }
                else if (barMins >= 6 * 60)
                {
                    p12Building = false;  // P12 finalized at 06:00
                }
            }

            // NY P12: 06:00-17:00 ET (NY session range, Profiler's ny_p12)
            // Reset at 06:00 ET
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
                    nyP12Building = false;  // NY P12 finalized at 17:00
                }
            }
        }

        // ═══ Proximity-based alpha computation ═══
        // Returns alpha (0-1) based on distance from current price.
        // Near = NearGlowOpacity, Far = FarFadeOpacity, linear interpolation between.
        private float ComputeProximityAlpha(double levelPrice, double currentPrice)
        {
            if (!ProximityFade) return levelPrice > 0 ? 0.7f : 0f;

            double threshold = ProximityThresholdPoints > 0
                ? (double)ProximityThresholdPoints
                : Math.Max(50, (High[0] - Low[0]) * 20);  // auto: 20x bar range or 50pts min

            double distance = Math.Abs(levelPrice - currentPrice);

            if (distance >= threshold)
                return (float)FarFadeOpacity / 100f;
            if (distance <= threshold * 0.1)
                return (float)NearGlowOpacity / 100f;

            // Linear interpolation between near and far
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
                if (barIndex - level.SetBarIndex < 3) continue;  // MinBarsAfterLevel

                // Check if bar crossed the level
                bool crossed = level.Price >= low && level.Price <= high;
                if (!crossed) continue;

                SweepEvent sweep = null;

                if (SweepMode == SweepMode.Wick || SweepMode == SweepMode.Both)
                {
                    if (close < level.Price)  // swept a high (BSL taken)
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
                    else if (close > level.Price)  // swept a low (SSL taken)
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
                    // Check stacking
                    sweep.IsStackSweep = level.StacksWith.Count > 0;

                    sweepEvents.Add(sweep);
                    todaySweeps.Add(sweep);
                    if (sweepEvents.Count > 500) sweepEvents.RemoveAt(0);

                    level.Swept = true;
                    level.SweptTime = barTime;
                    level.TouchCount++;
                }
            }

            // Update stacking detection (levels within tolerance)
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
            return activeLevels.Where(l => l.IsActive && l.Price > 0).OrderBy(l => l.Price).ToList();
        }

        public List<LevelState> GetLevelsByCategory(LevelCategory cat)
        {
            return activeLevels.Where(l => l.Def.Category == cat && l.IsActive && l.Price > 0).ToList();
        }

        public List<LevelState> GetSweepTargets()
        {
            return activeLevels.Where(l => (l.Def.Role == LevelRole.SweepTarget || l.Def.Role == LevelRole.Both)
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
            return activeLevels.Where(l => l.IsActive && l.Price > 0 && Math.Abs(l.Price - price) <= tolerance).ToList();
        }

        // ── Sweep access ──
        public List<SweepEvent> GetSweepEvents() => sweepEvents;
        public List<SweepEvent> GetSweepsToday() => todaySweeps;
        public List<SweepEvent> GetSweepsByLevel(string name) => sweepEvents.Where(s => s.LevelName == name).ToList();
        public SweepEvent GetLastSweep() => sweepEvents.LastOrDefault();
        public bool WasLevelSwept(string name) => activeLevels.FirstOrDefault(l => l.Def.Name == name)?.Swept ?? false;

        // ── Session Opens ──
        public double MidnightOpen => sessionOpens.MidnightOpen;
        public double LondonOpen => sessionOpens.LondonOpen;
        public double NyOpen => sessionOpens.NyOpen;
        public double Get4HOpen(int hour) => sessionOpens.Get4HOpen(hour);
        public Dictionary<string, double> GetAllOpens() => sessionOpens.GetAllOpens();

        // ── Convenience proxies ──
        public double PDH => PriorDayOHLC().PriorHigh[0];
        public double PDL => PriorDayOHLC().PriorLow[0];
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

        #region SharpDX Rendering

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            if (!DrawLines || ChartControl == null || RenderTarget == null) return;

            if (!resourcesCreated)
            {
                textFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Consolas",
                    SharpDX.DirectWrite.FontWeight.Normal, SharpDX.DirectWrite.FontStyle.Normal, 9f);
                resourcesCreated = true;
            }

            RenderTarget.BeginDraw();

            var activeLevelsToDraw = GetActiveLevels();

            // Category color palette
            var categoryColors = new Dictionary<LevelCategory, SharpDX.Color>
            {
                { LevelCategory.PriorDay,     new SharpDX.Color(0x00, 0xE6, 0x76, 255) },  // green
                { LevelCategory.PriorWeek,    new SharpDX.Color(0x69, 0xF0, 0xAE, 255) },  // light green
                { LevelCategory.PriorMonth,   new SharpDX.Color(0x00, 0xBC, 0xD4, 255) },  // cyan
                { LevelCategory.SessionOpen,  new SharpDX.Color(0xFF, 0xFF, 0xFF, 255) },  // white
                { LevelCategory.SessionRange, new SharpDX.Color(0x1E, 0x88, 0xE5, 255) },  // blue
                { LevelCategory.Intraday,     new SharpDX.Color(0x76, 0xFF, 0x03, 255) },  // light green
                { LevelCategory.VolumeProfile,new SharpDX.Color(0xFF, 0xA7, 0x26, 255) },  // orange
                { LevelCategory.Structure,    new SharpDX.Color(0xAB, 0x47, 0xBC, 255) },  // purple
                { LevelCategory.Pivot,        new SharpDX.Color(0x9E, 0x9E, 0x9E, 255) },  // gray
                { LevelCategory.Fib,          new SharpDX.Color(0xBD, 0xBD, 0xBD, 255) },  // light gray
            };

            float xStart = chartControl.GetXByBarIndex(ChartBars, Math.Max(0, CurrentBar - 100));
            float xEnd = chartControl.GetXByBarIndex(ChartBars, CurrentBar) + (float)chartControl.Properties.BarDistance;

            // Current price for proximity fade
            double currentPrice = Close[0];

            foreach (var level in activeLevelsToDraw)
            {
                SharpDX.Color color = categoryColors.TryGetValue(level.Def.Category, out var c)
                    ? c : new SharpDX.Color(0x80, 0x80, 0x80, 255);

                // Proximity-based alpha: brighten when close to price, fade when far
                float alpha;
                if (level.Swept)
                    alpha = 0.2f;  // swept levels always faded
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

                // Label — skip for very faded levels when proximity fade is on (clean charts)
                float labelAlphaThreshold = (float)FarFadeOpacity / 100f + 0.05f;
                bool showLabel = DrawLabels && textFormat != null
                    && (!ProximityFade || alpha > labelAlphaThreshold || level.Swept == false && level.StacksWith.Count > 0);

                if (showLabel)
                {
                    string label = $"{level.Def.Name} {level.Price:F1}";
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
                        ? new SharpDX.Color(0x00, 0xC8, 0x53, 255)   // green = SSL taken (bullish)
                        : new SharpDX.Color(0xFF, 0x17, 0x44, 255);  // red = BSL taken (bearish)

                    var markerBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget,
                        new Color4(markerColor.R / 255f, markerColor.G / 255f, markerColor.B / 255f, 0.8f));

                    // Small triangle (simplified: rectangle)
                    var markerRect = new RectangleF(sx - markerSize, sy - markerSize / 2, markerSize * 2, markerSize);
                    RenderTarget.FillRectangle(markerRect, markerBrush);
                    markerBrush.Dispose();
                }
            }

            RenderTarget.EndDraw();
        }

        #endregion
    }
}