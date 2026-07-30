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

            foreach (var level in activeLevelsToDraw)
            {
                SharpDX.Color color = categoryColors.TryGetValue(level.Def.Category, out var c)
                    ? c : new SharpDX.Color(0x80, 0x80, 0x80, 255);

                // Fade swept levels
                float alpha = level.Swept ? 0.3f : 0.7f;
                var lineColor = new Color4(color.R / 255f, color.G / 255f, color.B / 255f, alpha);

                float y = chartScale.GetYByValue(level.Price);
                float lineWidth = level.StacksWith.Count > 0 ? 2f : 1f;

                var brush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, lineColor);
                RenderTarget.DrawLine(new SharpDX.Vector2(xStart, y), new SharpDX.Vector2(xEnd, y),
                    brush, lineWidth);

                // Label
                if (DrawLabels && textFormat != null)
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