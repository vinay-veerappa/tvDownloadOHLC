// ═══════════════════════════════════════════════════════════════════════════
// SessionRanges.cs — v1.1.0 Unified multi-session range indicator for NT8
//
// Tracks ALL session ranges (Asia, London, Globex, IB, NY OR, Magic Hours, custom)
// in a single indicator. Exposes range data as public properties for consumption
// by IBConfluenceEngine and other strategies.
//
// Version: 1.1.0
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
        private SharpDX.Direct2D1.StrokeStyle strokeSolid, strokeDash, strokeDot;
        private SharpDX.DirectWrite.TextFormat textFormat;
        private SharpDX.DirectWrite.TextFormat tooltipFormat;
        private bool resourcesCreated;

        // ET timezone
        private TimeZoneInfo etZone;

        #endregion

        #region NinjaScript Properties (user-configurable)

        [Display(Name = "Preset", Description = "Session range preset", Order = 1, GroupName = "1. Sessions")]
        public SessionPreset Preset { get; set; } = SessionPreset.ICTCore;

        [Display(Name = "Custom Ranges", Description = "Format: Name:HHMM-HHMM-HHMM;Name2:...", Order = 2, GroupName = "1. Sessions")]
        public string CustomRangeDefs { get; set; } = "";

        [Display(Name = "Show Asia Session", Order = 3, GroupName = "1b. Session Toggles")]
        public bool ShowAsiaSession { get; set; } = true;

        [Display(Name = "Show London Session", Order = 4, GroupName = "1b. Session Toggles")]
        public bool ShowLondonSession { get; set; } = true;

        [Display(Name = "Show Globex Session", Order = 5, GroupName = "1b. Session Toggles")]
        public bool ShowGlobexSession { get; set; } = true;

        [Display(Name = "Show IB (Initial Balance)", Order = 6, GroupName = "1b. Session Toggles")]
        public bool ShowIBSession { get; set; } = true;

        [Display(Name = "Show NY Session", Order = 7, GroupName = "1b. Session Toggles")]
        public bool ShowNYSession { get; set; } = true;

        [Display(Name = "Show Magic Hours", Order = 8, GroupName = "1b. Session Toggles")]
        public bool ShowMagicHours { get; set; } = true;

        [Display(Name = "Show Boxes", Description = "Draw range boxes", Order = 9, GroupName = "2. Visuals")]
        public bool ShowBoxes { get; set; } = true;

        [Display(Name = "Show Labels", Description = "Draw range labels", Order = 10, GroupName = "2. Visuals")]
        public bool ShowLabels { get; set; } = true;

        [Display(Name = "Show Mid Lines", Description = "Draw mid lines for each range", Order = 11, GroupName = "2. Visuals")]
        public bool ShowMidLines { get; set; } = true;

        [Display(Name = "Box Fill Opacity", Description = "0=solid, 100=transparent", Order = 12, GroupName = "2. Visuals")]
        [Range(0, 100)]
        public int BoxFillOpacity { get; set; } = 85;

        [Display(Name = "Max History Days", Description = "How many prior days to show faded boxes", Order = 13, GroupName = "2. Visuals")]
        [Range(0, 20)]
        public int MaxHistory { get; set; } = 3;

        #endregion

        #region Helper: Session Filtering

        private bool IsSessionEnabled(string sessionName)
        {
            if (sessionName.Contains("Asia") && !ShowAsiaSession) return false;
            if (sessionName.Contains("London") && !ShowLondonSession) return false;
            if (sessionName.Contains("Globex") && !ShowGlobexSession) return false;
            if (sessionName.Contains("IB") && !ShowIBSession) return false;
            if (sessionName.Contains("NY") && !ShowNYSession) return false;
            if (sessionName.Contains("Magic") && !ShowMagicHours) return false;
            return true;
        }

        #endregion

        #region OnStateChange

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "v1.1.0 — Unified multi-session range indicator (Asia, London, Globex, IB, NY OR, Magic Hours, Custom) with box fills, mid lines, excursion tracking, and Direct2D hover tooltips.";
                Name = "SessionRanges";
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

                // Resolve presets
                specs = VinayNS.PresetCatalog.ResolvePreset(Preset);

                if (Preset == SessionPreset.Custom && !string.IsNullOrWhiteSpace(CustomRangeDefs))
                {
                    specs.AddRange(VinayNS.PresetCatalog.ParseCustomRanges(CustomRangeDefs));
                }

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

            DateTime barTimeEt = ToEt(Time[0]);
            int barMins = barTimeEt.Hour * 60 + barTimeEt.Minute;
            int dow = (int)barTimeEt.DayOfWeek;

            if (barTimeEt.Date != lastBarDate)
            {
                if (lastBarDate != DateTime.MinValue)
                {
                    foreach (var kvp in states)
                    {
                        if (kvp.Value.OrComplete)
                            histories[kvp.Key].AppendDay(kvp.Value, dow, false, false, 0, 0, false, false);
                    }
                }

                foreach (var spec in specs)
                {
                    states[spec.Name].Reset();
                }
                lastBarDate = barTimeEt.Date;
            }

            foreach (var spec in specs)
            {
                var state = states[spec.Name];
                state.UpdateOr(High[0], Low[0], Open[0], Close[0], CurrentBar);
            }
        }

        #endregion

        #region Public API Methods

        public VinayNS.RangeState GetRange(string name)
        {
            return states.TryGetValue(name, out var s) ? s : null;
        }

        public double GetRangeHigh(string name) => GetRange(name)?.OrHigh ?? 0;
        public double GetRangeLow(string name) => GetRange(name)?.OrLow ?? 0;
        public double GetRangeMid(string name) => GetRange(name)?.OrMid ?? 0;
        public double GetRangeWidth(string name) => GetRange(name)?.Range ?? 0;
        public bool IsRangeComplete(string name) => GetRange(name)?.OrComplete ?? false;

        public double IbHigh => GetRange("IB")?.OrHigh ?? 0;
        public double IBLow => GetRange("IB")?.OrLow ?? 0;
        public double IBMid => GetRange("IB")?.OrMid ?? 0;
        public double IBRange => GetRange("IB")?.Range ?? 0;
        public double IBOpen => GetRange("IB")?.SessionOpen ?? 0;
        public double IBClose => GetRange("IB")?.OrLastClose ?? 0;

        public double AsiaHigh => GetRange("Asia Range")?.OrHigh ?? 0;
        public double AsiaLow => GetRange("Asia Range")?.OrLow ?? 0;
        public double AsiaRange => GetRange("Asia Range")?.Range ?? 0;

        public double LondonHigh => GetRange("London Range")?.OrHigh ?? 0;
        public double LondonLow => GetRange("London Range")?.OrLow ?? 0;
        public double LondonRange => GetRange("London Range")?.Range ?? 0;
        public double LondonOrHigh => GetRange("London OR")?.OrHigh ?? 0;
        public double LondonOrLow => GetRange("London OR")?.OrLow ?? 0;

        public double GlobexHigh => GetRange("Globex Range")?.OrHigh ?? 0;
        public double GlobexLow => GetRange("Globex Range")?.OrLow ?? 0;

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

        #region SharpDX Rendering & On-Chart Mouse Hover Tooltips

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            if (!ShowBoxes || ChartControl == null || RenderTarget == null) return;

            if (!resourcesCreated)
                CreateResources();

            VinayNS.RangeState hoveredState = null;
            VinayNS.RangeSpec hoveredSpec = null;
            RectangleF hoveredRect = RectangleF.Empty;

            var mousePos = System.Windows.Input.Mouse.GetPosition(chartControl);
            float mouseX = (float)mousePos.X;
            float mouseY = (float)mousePos.Y;

            bool isDark = IsDarkChart(chartControl);

            foreach (var spec in specs)
            {
                if (!IsSessionEnabled(spec.Name)) continue;
                if (!states.TryGetValue(spec.Name, out var state)) continue;
                if (!state.OrBuilding && !state.OrComplete) continue;
                if (state.OrHigh <= 0 || state.OrLow <= 0) continue;

                int startBarIdx = state.OrStartBarIndex;
                int endBarIdx = CurrentBar;
                if (startBarIdx < 0 || startBarIdx > CurrentBar) continue;

                float x1 = chartControl.GetXByBarIndex(ChartBars, startBarIdx);
                float x2 = chartControl.GetXByBarIndex(ChartBars, endBarIdx);
                if (!state.IsCommitted) x2 = chartControl.GetXByBarIndex(ChartBars, CurrentBar) + (float)chartControl.Properties.BarDistance;

                float yHigh = chartScale.GetYByValue(state.OrHigh);
                float yLow = chartScale.GetYByValue(state.OrLow);
                float yMid = chartScale.GetYByValue(state.OrMid);

                Color4 baseColor;
                if (isDark)
                {
                    baseColor = new Color4(0.16f, 0.60f, 1.0f, 1.0f);
                    if (spec.Name.Contains("Asia")) baseColor = new Color4(0.70f, 0.35f, 0.90f, 1.0f);
                    else if (spec.Name.Contains("London")) baseColor = new Color4(0.0f, 0.85f, 0.95f, 1.0f);
                    else if (spec.Name.Contains("Globex")) baseColor = new Color4(0.55f, 0.60f, 0.68f, 1.0f);
                    else if (spec.Name.Contains("IB")) baseColor = new Color4(1.0f, 0.68f, 0.0f, 1.0f);
                    else if (spec.Name.Contains("NY")) baseColor = new Color4(0.0f, 0.90f, 0.46f, 1.0f);
                }
                else
                {
                    baseColor = new Color4(0.10f, 0.40f, 0.80f, 1.0f);
                    if (spec.Name.Contains("Asia")) baseColor = new Color4(0.48f, 0.15f, 0.68f, 1.0f);
                    else if (spec.Name.Contains("London")) baseColor = new Color4(0.0f, 0.50f, 0.65f, 1.0f);
                    else if (spec.Name.Contains("Globex")) baseColor = new Color4(0.28f, 0.32f, 0.40f, 1.0f);
                    else if (spec.Name.Contains("IB")) baseColor = new Color4(0.85f, 0.45f, 0.0f, 1.0f);
                    else if (spec.Name.Contains("NY")) baseColor = new Color4(0.0f, 0.60f, 0.28f, 1.0f);
                }

                float fillAlpha = (100 - BoxFillOpacity) / 100f * baseColor.Alpha;
                Color4 fillColor = new Color4(baseColor.Red, baseColor.Green, baseColor.Blue, fillAlpha);
                Color4 lineColor = new Color4(baseColor.Red, baseColor.Green, baseColor.Blue, 0.9f);

                var rect = new RectangleF(x1, yHigh, Math.Max(4, x2 - x1), Math.Max(2, yLow - yHigh));
                var fillBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, fillColor);
                RenderTarget.FillRectangle(rect, fillBrush);
                fillBrush.Dispose();

                var lineBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, lineColor);
                RenderTarget.DrawLine(new SharpDX.Vector2(x1, yHigh), new SharpDX.Vector2(x2, yHigh), lineBrush, spec.LineWidth, strokeSolid);
                RenderTarget.DrawLine(new SharpDX.Vector2(x1, yLow), new SharpDX.Vector2(x2, yLow), lineBrush, spec.LineWidth, strokeSolid);

                if (ShowMidLines && state.OrMid > 0)
                {
                    var midColor = new Color4(baseColor.Red, baseColor.Green, baseColor.Blue, 0.5f);
                    var midBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, midColor);
                    RenderTarget.DrawLine(new SharpDX.Vector2(x1, yMid), new SharpDX.Vector2(x2, yMid), midBrush, 1, strokeDot);
                    midBrush.Dispose();
                }

                if (ShowLabels && textFormat != null)
                {
                    string label = $"{spec.Name} {state.OrHigh:F1}/{state.OrLow:F1} ({state.Range:F0} pts)";
                    var textLayout = new TextLayout(Core.Globals.DirectWriteFactory, label, textFormat, float.MaxValue, float.MaxValue);
                    float labelX = x2 + 4;
                    float labelY = yHigh - textLayout.Metrics.Height / 2;

                    var bgBrush = isDark
                        ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.04f, 0.06f, 0.08f, 0.90f))
                        : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.98f, 0.98f, 1.0f, 0.95f));

                    var labelBrush = isDark
                        ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(1.0f, 1.0f, 1.0f, 1.0f))
                        : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.04f, 0.06f, 0.10f, 1.0f));

                    var bgRect = new RectangleF(labelX - 2, labelY - 1, (float)textLayout.Metrics.Width + 4, (float)textLayout.Metrics.Height + 2);
                    RenderTarget.FillRectangle(bgRect, bgBrush);
                    RenderTarget.DrawRectangle(bgRect, lineBrush, 1.0f);

                    RenderTarget.DrawTextLayout(new SharpDX.Vector2(labelX, labelY), textLayout, labelBrush);
                    bgBrush.Dispose();
                    labelBrush.Dispose();
                    textLayout.Dispose();
                }

                lineBrush.Dispose();

                // Mouse hover hit-testing
                if (rect.Contains(mouseX, mouseY) || (mouseX >= x1 && mouseX <= x2 + 60 && Math.Abs(mouseY - yMid) <= 10))
                {
                    hoveredState = state;
                    hoveredSpec = spec;
                    hoveredRect = rect;
                }
            }

            // Render floating tooltip if mouse hovers on range box
            if (hoveredState != null && hoveredSpec != null)
            {
                RenderHoverTooltip(chartControl, chartScale, hoveredState, hoveredSpec, mouseX, mouseY);
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

        private void RenderHoverTooltip(ChartControl chartControl, ChartScale chartScale, VinayNS.RangeState state, VinayNS.RangeSpec spec, float mouseX, float mouseY)
        {
            bool isDark = IsDarkChart(chartControl);

            double curPrice = Close[0];
            double distHigh = Math.Abs(state.OrHigh - curPrice);
            double distLow = Math.Abs(state.OrLow - curPrice);

            string title = $"{spec.Name} Range";
            string priceRange = $"High: {state.OrHigh:N2}  |  Low: {state.OrLow:N2}";
            string midText = $"Midpoint: {state.OrMid:N2}";
            string sizeText = $"Size: {state.Range:F2} pts ({(state.Range / TickSize):F0} ticks)";
            string statusText = state.OrComplete ? "Status: Complete (Closed)" : "Status: Active (Forming)";
            string distText = $"Distance: +{distHigh:F2} pts to High | +{distLow:F2} pts to Low";

            List<string> lines = new List<string> { title, priceRange, midText, sizeText, statusText, distText };

            float width = 250f;
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

            var bgBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.06f, 0.08f, 0.12f, 0.95f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.96f, 0.97f, 0.99f, 0.96f));

            var borderBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.2f, 0.6f, 1.0f, 0.9f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.1f, 0.4f, 0.8f, 0.9f));

            var titleBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(1.0f, 1.0f, 1.0f, 1.0f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.04f, 0.06f, 0.10f, 1.0f));

            var textBrush = isDark
                ? new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.85f, 0.88f, 0.92f, 1.0f))
                : new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new Color4(0.12f, 0.15f, 0.20f, 1.0f));

            RenderTarget.FillRectangle(bgRect, bgBrush);
            RenderTarget.DrawRectangle(bgRect, borderBrush, 1.5f);

            float textY = boxY + 6;
            for (int i = 0; i < lines.Count; i++)
            {
                var curBrush = (i == 0) ? titleBrush : textBrush;
                var textLayout = new TextLayout(Core.Globals.DirectWriteFactory, lines[i], tooltipFormat ?? textFormat, width - 12, lineHeight + 2);
                RenderTarget.DrawTextLayout(new SharpDX.Vector2(boxX + 6, textY), textLayout, curBrush);
                textLayout.Dispose();
                textY += lineHeight;
            }

            bgBrush.Dispose();
            borderBrush.Dispose();
            titleBrush.Dispose();
            textBrush.Dispose();
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
            tooltipFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI", SharpDX.DirectWrite.FontWeight.SemiBold, SharpDX.DirectWrite.FontStyle.Normal, 11f);

            resourcesCreated = true;
        }

        private void DisposeResources()
        {
            if (strokeSolid != null) { strokeSolid.Dispose(); strokeSolid = null; }
            if (strokeDash != null) { strokeDash.Dispose(); strokeDash = null; }
            if (strokeDot != null) { strokeDot.Dispose(); strokeDot = null; }
            if (textFormat != null) { textFormat.Dispose(); textFormat = null; }
            if (tooltipFormat != null) { tooltipFormat.Dispose(); tooltipFormat = null; }
            resourcesCreated = false;
        }

        #endregion
    }
}