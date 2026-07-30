// ═══════════════════════════════════════════════════════════════════════════
// SessionRanges.cs — Unified multi-session range indicator for NT8
//
// Tracks ALL session ranges (Asia, London, Globex, IB, NY OR, Magic Hours, custom)
// in a single indicator. Exposes range data as public properties for consumption
// by IBConfluenceEngine and other strategies.
//
// Parity contract: docs/indicators/DailyNYLevels/CORE_ENGINE_SPEC.md
// Design doc: docs/architecture/SESSION_RANGES_INDICATOR_DESIGN.md
// ═══════════════════════════════════════════════════════════════════════════

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Xml.Serialization;
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
    public class SessionRanges : Indicator
    {
        #region Private Variables

        private List<VinayNS.RangeSpec> specs = new List<VinayNS.RangeSpec>();
        private Dictionary<string, VinayNS.RangeState> states = new Dictionary<string, VinayNS.RangeState>();
        private Dictionary<string, VinayNS.ExcursionHistory> histories = new Dictionary<string, VinayNS.ExcursionHistory>();
        private DateTime lastBarDate = DateTime.MinValue;

        // SharpDX resources
        private SharpDX.Direct2D1.SolidColorBrush dxFillBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxHighBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxLowBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxMidBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxLabelBrush;
        private SharpDX.Direct2D1.StrokeStyle strokeSolid, strokeDash, strokeDot;
        private SharpDX.DirectWrite.TextFormat textFormat;
        private bool resourcesCreated;

        // ET timezone
        private TimeZoneInfo etZone;

        #endregion

        #region NinjaScript Properties (user-configurable)

        [NinjaScriptProperty]
        [Display(Name = "Preset", Description = "Session range preset", Order = 1, GroupName = "1. Sessions")]
        public SessionPreset Preset { get; set; } = SessionPreset.ICTCore;

        [NinjaScriptProperty]
        [Display(Name = "Custom Ranges", Description = "Format: Name:HHMM-HHMM-HHMM;Name2:...", Order = 2, GroupName = "1. Sessions")]
        public string CustomRangeDefs { get; set; } = "";

        [NinjaScriptProperty]
        [Display(Name = "Show Boxes", Description = "Draw range boxes", Order = 3, GroupName = "2. Visuals")]
        public bool ShowBoxes { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Labels", Description = "Draw range labels", Order = 4, GroupName = "2. Visuals")]
        public bool ShowLabels { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Show Mid Lines", Description = "Draw mid lines for each range", Order = 5, GroupName = "2. Visuals")]
        public bool ShowMidLines { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Box Fill Opacity", Description = "0=solid, 100=transparent", Order = 6, GroupName = "2. Visuals")]
        [Range(0, 100)]
        public int BoxFillOpacity { get; set; } = 85;

        [NinjaScriptProperty]
        [Display(Name = "Max History Days", Description = "How many prior days to show faded boxes", Order = 7, GroupName = "2. Visuals")]
        [Range(0, 20)]
        public int MaxHistory { get; set; } = 3;

        #endregion

        #region OnStateChange

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Unified multi-session range indicator (Asia/London/Globex/IB/Magic Hours/Custom)";
                Name = "SessionRanges";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DrawOnPricePanel = true;
                DisplayInDataBox = true;
                IsSuspendedWhileInactive = true;
                ScaleJustification = ScaleJustification.Right;
            }
            else if (State == State.SetDefaults || State == State.Configure)
            {
                // Initialize ET timezone
                try
                {
                    etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                }
                catch
                {
                    etZone = TimeZoneInfo.FindSystemTimeZoneById("America/New_York");
                }

                // Resolve presets
                specs = VinayNS.PresetCatalog.ResolvePreset(Preset);

                // Add custom ranges if any
                if (Preset == SessionPreset.Custom && !string.IsNullOrWhiteSpace(CustomRangeDefs))
                {
                    specs.AddRange(VinayNS.PresetCatalog.ParseCustomRanges(CustomRangeDefs));
                }

                // Initialize states and histories
                states.Clear();
                histories.Clear();
                foreach (var spec in specs)
                {
                    states[spec.Name] = VinayNS.RangeState.Create(spec);
                    histories[spec.Name] = new VinayNS.ExcursionHistory();
                }
            }
            else if (State == State.Terminated)
            {
                DisposeResources();
            }
        }

        #endregion

        #region OnBarUpdate

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;

            // Get bar time in ET
            DateTime barTimeEt = ToEt(Time[0]);
            int barMins = barTimeEt.Hour * 60 + barTimeEt.Minute;
            int dow = (int)barTimeEt.DayOfWeek;  // 0=Sun, 6=Sat

            // Detect new day (reset all states)
            if (barTimeEt.Date != lastBarDate)
            {
                if (lastBarDate != DateTime.MinValue)
                {
                    // Commit previous day's states to history
                    foreach (var kvp in states)
                    {
                        if (kvp.Value.IsCommitted) continue;
                        // Auto-commit at day boundary
                        kvp.Value.IsCommitted = true;
                    }
                }
                lastBarDate = barTimeEt.Date;
                foreach (var kvp in states)
                {
                    kvp.Value.Reset();
                    kvp.Value.SessionDate = barTimeEt.Date;
                }
            }

            // Update each range
            foreach (var spec in specs)
            {
                if (!spec.IsEnabled) continue;

                // Check day filter (Pine convention: 1=Sun..7=Sat → our dow: 0=Sun..6=Sat → +1)
                int pineDow = dow == 0 ? 7 : dow;  // Pine: 7=Sat, our: 6=Sat
                if (!IsDayAllowed(spec.Days, dow)) continue;

                var state = states[spec.Name];
                bool inOr = IsInSession(barMins, spec.OrStartMin, spec.OrEndMin, spec.CrossesMidnight);
                bool inData = IsInSession(barMins, spec.OrStartMin, spec.CutoffMin,
                    spec.CutoffMin < spec.OrStartMin);  // data window may cross midnight separately

                // OR building phase
                if (inOr && !state.OrComplete)
                {
                    state.UpdateOr(High[0], Low[0], Open[0], Close[0], CurrentBar);
                }

                // OR finalization (first bar after OR window)
                if (!inOr && state.OrBuilding && !state.OrComplete)
                {
                    state.FinalizeOr();
                }

                // Data window (after OR complete, before cutoff)
                if (state.OrComplete && inData && !state.IsTerminated)
                {
                    // Check breakout
                    state.CheckBreakout(High[0], Low[0], CurrentBar, barTimeEt);

                    // Update MFE/MAE
                    state.UpdateMfe(High[0], Low[0]);
                    state.UpdateMidHit(High[0], Low[0]);

                    // Track entry triggers for fakeout
                    if (!state.EntryTriggeredBull && High[0] > state.OrHigh)
                        state.EntryTriggeredBull = true;
                    if (!state.EntryTriggeredBear && Low[0] < state.OrLow)
                        state.EntryTriggeredBear = true;
                }

                // Cutoff — commit the day
                if (!inData && state.OrComplete && !state.IsCommitted && barMins > spec.CutoffMin)
                {
                    state.CloseAtCutoff = Close[0];
                    state.IsCommitted = true;
                    state.IsTerminated = true;
                }

                state.PrevInOr = inOr;
                state.PrevInData = inData;
            }
        }

        #endregion

        #region Session Detection (minute-based, CORE_ENGINE_SPEC §4.2)

        private bool IsInSession(int barMins, int startMin, int endMin, bool crossesMidnight)
        {
            if (crossesMidnight)
                return barMins >= startMin || barMins < endMin;
            else
                return barMins >= startMin && barMins < endMin;
        }

        private bool IsDayAllowed(string days, int dow)
        {
            // days string: "23456" means Mon-Fri. Pine convention: 1=Sun, 2=Mon, ..., 7=Sat
            // Our dow: 0=Sun, 1=Mon, ..., 6=Sat
            int pineDay = dow == 0 ? 1 : dow + 1;  // 0→1(Sun), 1→2(Mon), ..., 6→7(Sat)
            return days.Contains(pineDay.ToString());
        }

        private DateTime ToEt(DateTime dt)
        {
            // NT8 chart times for futures are typically in the instrument's exchange timezone.
            // For CME equity futures, that's CT (Central Time). We need ET.
            // Simplest: treat as ET if already in ET, otherwise convert from UTC.
            // Most NT8 NQ charts display in ET already (exchange timezone mapping).
            // If the input is Unspecified or Local, assume it's already chart-time = ET.
            if (etZone == null) return dt;
            try
            {
                if (dt.Kind == DateTimeKind.Utc)
                    return TimeZoneInfo.ConvertTimeFromUtc(dt, etZone);
                // Assume chart time is ET for CME equity futures
                return dt;
            }
            catch { return dt; }
        }

        #endregion

        #region Public API — Range lookup

        public VinayNS.RangeState GetRange(string name)
        {
            return states.TryGetValue(name, out var s) ? s : null;
        }

        public VinayNS.RangeState GetRange(int index)
        {
            if (index < 0 || index >= specs.Count) return null;
            return states.TryGetValue(specs[index].Name, out var s) ? s : null;
        }

        public int RangeCount => specs.Count;

        public List<string> ActiveRangeNames
        {
            get { return specs.Where(s => s.IsEnabled).Select(s => s.Name).ToList(); }
        }

        public VinayNS.ExcursionHistory GetHistory(string rangeName)
        {
            return histories.TryGetValue(rangeName, out var h) ? h : null;
        }

        #endregion

        #region Public API — IB convenience

        public double IbHigh => GetRange("IB")?.OrHigh ?? 0;
        public double IBLow => GetRange("IB")?.OrLow ?? 0;
        public double IBMid => GetRange("IB")?.OrMid ?? 0;
        public double IBRange => GetRange("IB")?.Range ?? 0;
        public bool IBComplete => GetRange("IB")?.OrComplete ?? false;
        public double IBOpen => GetRange("IB")?.SessionOpen ?? 0;
        public double IBClose => GetRange("IB")?.OrLastClose ?? 0;
        public int IBBreakoutSide => GetRange("IB")?.SigBreakoutSide ?? 0;
        public DateTime IBBreakoutTime => GetRange("IB")?.BreakoutTime ?? DateTime.MinValue;

        #endregion

        #region Public API — Asia convenience (Herman)

        public double AsiaHigh => GetRange("Asia Range")?.OrHigh ?? 0;
        public double AsiaLow => GetRange("Asia Range")?.OrLow ?? 0;
        public double AsiaRange => GetRange("Asia Range")?.Range ?? 0;
        public double AsiaRangePct => GetRange("Asia Range")?.RangePct ?? 0;
        public bool AsiaComplete => GetRange("Asia Range")?.OrComplete ?? false;

        #endregion

        #region Public API — London convenience

        public double LondonHigh => GetRange("London Range")?.OrHigh ?? 0;
        public double LondonLow => GetRange("London Range")?.OrLow ?? 0;
        public double LondonRange => GetRange("London Range")?.Range ?? 0;
        public bool LondonComplete => GetRange("London Range")?.OrComplete ?? false;

        public double LondonOrHigh => GetRange("London OR")?.OrHigh ?? 0;
        public double LondonOrLow => GetRange("London OR")?.OrLow ?? 0;
        public bool LondonOrComplete => GetRange("London OR")?.OrComplete ?? false;

        #endregion

        #region Public API — Globex convenience

        public double GlobexHigh => GetRange("Globex Range")?.OrHigh ?? 0;
        public double GlobexLow => GetRange("Globex Range")?.OrLow ?? 0;
        public bool GlobexComplete => GetRange("Globex Range")?.OrComplete ?? false;

        #endregion

        #region Public API — Aggregate

        public bool AnyRangeForming
        {
            get { return states.Values.Any(s => s.IsForming); }
        }

        public List<VinayNS.RangeState> CompletedRanges
        {
            get { return states.Values.Where(s => s.OrComplete).ToList(); }
        }

        public List<VinayNS.RangeState> FormingRanges
        {
            get { return states.Values.Where(s => s.IsForming).ToList(); }
        }

        #endregion

        #region Methods

        public void AddCustomRange(string name, string startHHMM, string endHHMM, string cutoffHHMM, string days = "23456")
        {
            var spec = new VinayNS.RangeSpec
            {
                Name = name,
                PresetGroup = "Custom",
                OrStartMin = VinayNS.PresetCatalog.ParseHHMM(startHHMM),
                OrEndMin = VinayNS.PresetCatalog.ParseHHMM(endHHMM),
                CutoffMin = VinayNS.PresetCatalog.ParseHHMM(cutoffHHMM),
                Days = days,
                IsEnabled = true,
                FillOpacity = BoxFillOpacity,
                ShowLabel = ShowLabels,
                LineWidth = 1,
            };
            specs.Add(spec);
            states[name] = VinayNS.RangeState.Create(spec);
            histories[name] = new VinayNS.ExcursionHistory();
        }

        public void EnableRange(string name)
        {
            var spec = specs.FirstOrDefault(s => s.Name == name);
            if (spec != null) spec.IsEnabled = true;
        }

        public void DisableRange(string name)
        {
            var spec = specs.FirstOrDefault(s => s.Name == name);
            if (spec != null) spec.IsEnabled = false;
        }

        #endregion

        #region SharpDX Rendering

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            if (!ShowBoxes || ChartControl == null) return;

            if (!resourcesCreated)
                CreateResources();

            if (RenderTarget == null) return;

            RenderTarget.BeginDraw();

            // Per-range color palette (hue offset)
            var palette = new SharpDX.Color[]
            {
                new SharpDX.Color(0x1E, 0x88, 0xE5, 255),  // blue
                new SharpDX.Color(0xE5, 0x39, 0x35, 255),  // red
                new SharpDX.Color(0xFB, 0x8C, 0x00, 255),  // orange
                new SharpDX.Color(0x8E, 0x24, 0xAA, 255),  // purple
                new SharpDX.Color(0x00, 0xBC, 0xD4, 255),  // cyan
                new SharpDX.Color(0x66, 0xBB, 0x6A, 255),  // green
                new SharpDX.Color(0xFF, 0xD5, 0x4F, 255),  // yellow
                new SharpDX.Color(0xEC, 0x40, 0x7A, 255),  // pink
                new SharpDX.Color(0x5C, 0x6B, 0xC0, 255),  // indigo
                new SharpDX.Color(0x26, 0xC6, 0xDA, 255),  // light blue
                new SharpDX.Color(0xEF, 0x5E, 0x35, 255),  // deep orange
                new SharpDX.Color(0xAB, 0x47, 0xBC, 255),  // light purple
            };

            for (int i = 0; i < specs.Count; i++)
            {
                var spec = specs[i];
                if (!spec.IsEnabled) continue;

                var state = states[spec.Name];
                if (!state.OrComplete && !state.OrBuilding) continue;
                if (state.OrHigh <= 0 || state.OrLow <= 0) continue;

                Color baseColor = palette[i % palette.Length];
                float alpha = (float)(100 - BoxFillOpacity) / 100f;
                float lineAlpha = 0.8f;

                var fillColor = new Color4(baseColor.R / 255f, baseColor.G / 255f, baseColor.B / 255f, alpha);
                var lineColor = new Color4(baseColor.R / 255f, baseColor.G / 255f, baseColor.B / 255f, lineAlpha);

                // Calculate bar X coordinates
                int startBarIdx = state.OrStartBarIndex;
                int endBarIdx = state.IsCommitted ? state.SigBreakoutBarIndex > 0 ? state.SigBreakoutBarIndex : CurrentBar : CurrentBar;
                if (endBarIdx < startBarIdx) endBarIdx = CurrentBar;

                float x1 = chartControl.GetXByBarIndex(ChartBars, startBarIdx);
                float x2 = chartControl.GetXByBarIndex(ChartBars, endBarIdx);
                // Extend box to current bar if still active
                if (!state.IsCommitted) x2 = chartControl.GetXByBarIndex(ChartBars, CurrentBar) + (float)chartControl.Properties.BarDistance;

                float yHigh = chartScale.GetYByValue(state.OrHigh);
                float yLow = chartScale.GetYByValue(state.OrLow);
                float yMid = chartScale.GetYByValue(state.OrMid);

                // Draw box fill
                var rect = new RectangleF(x1, yHigh, x2 - x1, yLow - yHigh);
                var fillBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, fillColor);
                RenderTarget.FillRectangle(rect, fillBrush);
                fillBrush.Dispose();

                // Draw high line
                var lineBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, lineColor);
                RenderTarget.DrawLine(new SharpDX.Vector2(x1, yHigh), new SharpDX.Vector2(x2, yHigh),
                    lineBrush, spec.LineWidth, strokeSolid);

                // Draw low line
                RenderTarget.DrawLine(new SharpDX.Vector2(x1, yLow), new SharpDX.Vector2(x2, yLow),
                    lineBrush, spec.LineWidth, strokeSolid);

                // Draw mid line (dotted)
                if (ShowMidLines && state.OrMid > 0)
                {
                    var midColor = new Color4(baseColor.R / 255f, baseColor.G / 255f, baseColor.B / 255f, 0.5f);
                    var midBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, midColor);
                    RenderTarget.DrawLine(new SharpDX.Vector2(x1, yMid), new SharpDX.Vector2(x2, yMid),
                        midBrush, 1, strokeDot);
                    midBrush.Dispose();
                }

                // Draw label
                if (ShowLabels && textFormat != null)
                {
                    string label = $"{spec.Name} {state.OrHigh:F1}/{state.OrLow:F1} ({state.Range:F0})";
                    var textLayout = new TextLayout(Core.Globals.DirectWriteFactory, label, textFormat,
                        float.MaxValue, float.MaxValue);
                    float labelX = x2 + 4;
                    float labelY = yHigh - textLayout.Metrics.Height / 2;

                    // Background rect for readability
                    var bgRect = new RectangleF(labelX - 2, labelY, (float)textLayout.Metrics.Width + 4,
                        (float)textLayout.Metrics.Height);
                    var bgBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget,
                        new Color4(0, 0, 0, 0.6f));
                    RenderTarget.FillRectangle(bgRect, bgBrush);
                    bgBrush.Dispose();

                    RenderTarget.DrawTextLayout(new SharpDX.Vector2(labelX, labelY), textLayout, lineBrush);
                    textLayout.Dispose();
                }

                lineBrush.Dispose();
            }

            RenderTarget.EndDraw();
        }

        private void CreateResources()
        {
            if (RenderTarget == null) return;

            strokeSolid = new StrokeStyle(RenderTarget.Factory, new StrokeStyleProperties
            {
                DashStyle = DashStyle.Solid,
                LineJoin = LineJoin.Miter,
            });

            strokeDash = new StrokeStyle(RenderTarget.Factory, new StrokeStyleProperties
            {
                DashStyle = DashStyle.Dash,
                LineJoin = LineJoin.Miter,
            });

            strokeDot = new StrokeStyle(RenderTarget.Factory, new StrokeStyleProperties
            {
                DashStyle = DashStyle.Dot,
                LineJoin = LineJoin.Miter,
            });

            textFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Consolas", SharpDX.DirectWrite.FontWeight.Normal, SharpDX.DirectWrite.FontStyle.Normal, 9f);

            resourcesCreated = true;
        }

        private void DisposeResources()
        {
            if (strokeSolid != null) { strokeSolid.Dispose(); strokeSolid = null; }
            if (strokeDash != null) { strokeDash.Dispose(); strokeDash = null; }
            if (strokeDot != null) { strokeDot.Dispose(); strokeDot = null; }
            if (textFormat != null) { textFormat.Dispose(); textFormat = null; }
            resourcesCreated = false;
        }

        #endregion
    }
}