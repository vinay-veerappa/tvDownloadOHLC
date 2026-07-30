#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using SharpDX;
using SharpDX.Direct2D1;
using SharpDX.DirectWrite;
#endregion

// Created by RedTail Indicators -  https://github.com/3astbeast/RedTailIndicators

namespace NinjaTrader.NinjaScript.Indicators.RedTail
{
    public class RedTailVWAPFibBands : Indicator
    {
        // ── Anchor ──────────────────────────────────────────────────────────
        private string   anchorMethod;
        private string   anchorTimeframe;
        private DateTime anchorDate;

        // ── Accumulation state ───────────────────────────────────────────────
        private double sumPV;
        private double sumPSqV;
        private double sumVol;
        private bool   hasStarted;
        private string lastAnchorBar;

        // ── Computed values (kept for OnRender) ──────────────────────────────
        private double   midasVal;
        private double   upper1Val;   // ±1σ mean-reversion band
        private double   lower1Val;
        private double   upper2Val;   // ±2σ extension band
        private double   lower2Val;
        private double[] fibUpVals;
        private double[] fibDownVals;
        private double[] fibLevels;

        // ── SharpDX resources ────────────────────────────────────────────────
        private SharpDX.Direct2D1.Brush fill1UpperBrush;
        private SharpDX.Direct2D1.Brush fill1LowerBrush;
        private SharpDX.Direct2D1.Brush fill2UpperBrush;
        private SharpDX.Direct2D1.Brush fill2LowerBrush;
        private SharpDX.Direct2D1.Brush labelMidBrush;
        private SharpDX.Direct2D1.Brush labelBand1Brush;
        private SharpDX.Direct2D1.Brush labelBand2Brush;
        private SharpDX.Direct2D1.Brush labelFibBrush;
        private SharpDX.DirectWrite.TextFormat labelFormat;
        private bool brushesBuilt;

        // Plot indices
        private const int PlotMidas    = 0;
        private const int PlotUpper1   = 1;   // +1σ
        private const int PlotLower1   = 2;   // -1σ
        private const int PlotUpper2   = 3;   // +2σ
        private const int PlotLower2   = 4;   // -2σ
        private int PlotFibUpBase;             // 5
        private int PlotFibDnBase;             // 5 + fibCount

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description              = "MIDAS (Market Interpretation/Data Analysis System), developed by Paul Levine in the 1990s, is a technical analysis approach using anchored Volume Weighted Average Price (VWAP) curves to identify support/resistance and trend reversals. Unlike daily VWAP, MIDAS anchors to specific price action points (highs/lows) and acts as a dynamic, trend-following tool, often expanded with fractal capabilities for all time frames.";
                Name                     = "RedTailVWAPFibBands";
                Calculate                = Calculate.OnBarClose;
                IsOverlay                = true;
                DisplayInDataBox         = true;
                DrawOnPricePanel         = true;
                ScaleJustification       = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive = true;

                // Anchor
                AnchorMethod    = "Session";
                AnchorTimeframe = "Daily";
                AnchorDate      = new DateTime(2025, 1, 1, 0, 0, 0, DateTimeKind.Utc);
                SessionOpenHour = 18;   // 6 PM ET — futures session open

                // Bands
                Band1Multiplier  = 1.0;   // ±1σ — mean-reversion band (long -1σ, short +1σ)
                Band2Multiplier  = 2.0;   // ±2σ — extension/trending band
                FibLevelsInput   = "0.236, 0.382, 0.5, 0.618, 0.786";
                ShowLabels       = true;
                ShowFill         = true;
                FillOpacity      = 15;

                // Independent line style pickers
                MidasStroke  = new Stroke(Brushes.DodgerBlue, DashStyleHelper.Solid, 2);
                Band1Stroke  = new Stroke(Brushes.Red,        DashStyleHelper.Solid, 2);
                Band2Stroke  = new Stroke(Brushes.Red,        DashStyleHelper.Dash,  1);
                FibBandStroke= new Stroke(Brushes.Gray,       DashStyleHelper.Dot,   1);
            }
            else if (State == State.Configure)
            {
                // Guard against blank dropdown on first load
                if (string.IsNullOrEmpty(AnchorTimeframe))
                    AnchorTimeframe = "Daily";

                ParseFibLevels();

                fibUpVals     = new double[fibLevels.Length];
                fibDownVals   = new double[fibLevels.Length];
                PlotFibUpBase = 5;
                PlotFibDnBase = 5 + fibLevels.Length;

                // Core plots
                AddPlot(MidasStroke,  PlotStyle.Line, "MIDAS");
                AddPlot(Band1Stroke,  PlotStyle.Line, "Upper1");   // +1σ mean-reversion
                AddPlot(Band1Stroke,  PlotStyle.Line, "Lower1");   // -1σ mean-reversion
                AddPlot(Band2Stroke,  PlotStyle.Line, "Upper2");   // +2σ extension
                AddPlot(Band2Stroke,  PlotStyle.Line, "Lower2");   // -2σ extension

                for (int i = 0; i < fibLevels.Length; i++)
                    AddPlot(FibBandStroke, PlotStyle.Line, $"FibUp_{fibLevels[i]:0.000}");
                for (int i = 0; i < fibLevels.Length; i++)
                    AddPlot(FibBandStroke, PlotStyle.Line, $"FibDown_{fibLevels[i]:0.000}");

                // Reset accumulation
                sumPV         = double.NaN;
                sumPSqV       = double.NaN;
                sumVol        = double.NaN;
                hasStarted    = false;
                lastAnchorBar = null;
                brushesBuilt  = false;

                anchorMethod    = AnchorMethod;
                anchorTimeframe = string.IsNullOrEmpty(AnchorTimeframe) ? "Daily" : AnchorTimeframe;
                anchorDate      = AnchorDate.Kind == DateTimeKind.Utc
                                  ? AnchorDate
                                  : DateTime.SpecifyKind(AnchorDate, DateTimeKind.Utc);
            }
            else if (State == State.Terminated)
            {
                DisposeBrushes();
            }
        }

        protected override void OnBarUpdate()
        {
            double price = (High[0] + Low[0] + Close[0]) / 3.0;
            double vol   = Volume[0];

            // ── Detect reset ─────────────────────────────────────────────────
            bool reset = false;

            if (anchorMethod == "Timeframe")
            {
                string key = GetAnchorBarKey();
                if (lastAnchorBar == null || key != lastAnchorBar)
                {
                    reset         = true;
                    lastAnchorBar = key;
                }
            }
            else if (anchorMethod == "Session")
            {
                // Session key = calendar date of the session that started at SessionOpenHour.
                // A bar at e.g. 18:30 belongs to that evening's session (date = today).
                // A bar at e.g. 02:00 belongs to the session that opened the prior evening (date = yesterday).
                DateTime t   = Time[0];
                DateTime sessionDate = t.Hour >= SessionOpenHour
                                       ? t.Date
                                       : t.Date.AddDays(-1);
                string key = sessionDate.ToString("yyyyMMdd");
                if (lastAnchorBar == null || key != lastAnchorBar)
                {
                    reset         = true;
                    lastAnchorBar = key;
                }
            }
            else  // Date
            {
                if (!hasStarted && Time[0] >= anchorDate)
                {
                    reset      = true;
                    hasStarted = true;
                }
            }

            if (reset)
            {
                sumPV   = 0.0;
                sumPSqV = 0.0;
                sumVol  = 0.0;
            }

            // ── Accumulate ───────────────────────────────────────────────────
            bool shouldAccumulate = (anchorMethod == "Timeframe" || anchorMethod == "Session")
                                    ? !double.IsNaN(sumVol)
                                    : hasStarted;

            if (shouldAccumulate)
            {
                sumPV   += price * vol;
                sumPSqV += price * price * vol;
                sumVol  += vol;
            }

            if (!shouldAccumulate || sumVol == 0.0)
            {
                Value.Reset();
                return;
            }

            // ── MIDAS + Std Dev ───────────────────────────────────────────────
            double midas    = sumPV / sumVol;
            double meanSq   = sumPSqV / sumVol;
            double variance = meanSq - midas * midas;
            double stdDev   = variance > 0 ? Math.Sqrt(variance) : 0.0;

            double u1 = midas + Band1Multiplier * stdDev;
            double l1 = midas - Band1Multiplier * stdDev;
            double u2 = midas + Band2Multiplier * stdDev;
            double l2 = midas - Band2Multiplier * stdDev;

            midasVal = midas;
            upper1Val = u1;  lower1Val = l1;
            upper2Val = u2;  lower2Val = l2;

            Values[PlotMidas][0]  = midas;
            Values[PlotUpper1][0] = u1;
            Values[PlotLower1][0] = l1;
            Values[PlotUpper2][0] = u2;
            Values[PlotLower2][0] = l2;

            // ── Fibonacci bands — interpolated between MIDAS and ±2σ ─────────
            // 0.5 fib = ±1σ (mean-reversion band), 1.0 fib = ±2σ (extension band)
            for (int i = 0; i < fibLevels.Length; i++)
            {
                double fib   = fibLevels[i];
                double fibUp = midas + fib * (u2 - midas);
                double fibDn = midas - fib * (midas - l2);

                fibUpVals[i]   = fibUp;
                fibDownVals[i] = fibDn;

                Values[PlotFibUpBase + i][0] = fibUp;
                Values[PlotFibDnBase + i][0] = fibDn;
            }
        }

        // ── SharpDX rendering ────────────────────────────────────────────────
        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            base.OnRender(chartControl, chartScale);

            if (RenderTarget == null || IsInHitTest) return;
            if (double.IsNaN(midasVal))             return;

            EnsureBrushes();

            // ── Fill — geometry path traces the actual band lines bar by bar ──
            if (ShowFill)
            {
                // Inner zone: between ±1σ bands (mean-reversion range)
                DrawBandFill(chartControl, chartScale, Values[PlotUpper1], Values[PlotMidas],  fill1UpperBrush);
                DrawBandFill(chartControl, chartScale, Values[PlotMidas],  Values[PlotLower1], fill1LowerBrush);
                // Outer zone: between ±2σ and ±1σ (extension range)
                DrawBandFill(chartControl, chartScale, Values[PlotUpper2], Values[PlotUpper1], fill2UpperBrush);
                DrawBandFill(chartControl, chartScale, Values[PlotLower1], Values[PlotLower2], fill2LowerBrush);
            }

            // ── Right-edge labels ─────────────────────────────────────────────
            if (!ShowLabels) return;

            float rightX = (float)chartControl.GetXByBarIndex(ChartBars, ChartBars.ToIndex) + 4f;
            float midY   = (float)chartScale.GetYByValue(midasVal);
            float u1Y    = (float)chartScale.GetYByValue(upper1Val);
            float l1Y    = (float)chartScale.GetYByValue(lower1Val);
            float u2Y    = (float)chartScale.GetYByValue(upper2Val);
            float l2Y    = (float)chartScale.GetYByValue(lower2Val);

            DrawLabel(rightX, midY, "MIDAS",                         labelMidBrush);
            DrawLabel(rightX, u1Y,  $"+{Band1Multiplier:0.0#}σ",    labelBand1Brush);
            DrawLabel(rightX, l1Y,  $"-{Band1Multiplier:0.0#}σ",    labelBand1Brush);
            DrawLabel(rightX, u2Y,  $"+{Band2Multiplier:0.0#}σ",    labelBand2Brush);
            DrawLabel(rightX, l2Y,  $"-{Band2Multiplier:0.0#}σ",    labelBand2Brush);

            for (int i = 0; i < fibLevels.Length; i++)
            {
                if (!double.IsNaN(fibUpVals[i]))
                    DrawLabel(rightX, (float)chartScale.GetYByValue(fibUpVals[i]),
                              fibLevels[i].ToString("0.000"), labelFibBrush);
                if (!double.IsNaN(fibDownVals[i]))
                    DrawLabel(rightX, (float)chartScale.GetYByValue(fibDownVals[i]),
                              fibLevels[i].ToString("0.000"), labelFibBrush);
            }
        }

        // ── Draw helpers ─────────────────────────────────────────────────────

        // Builds a closed polygon tracing topSeries left→right then bottomSeries right→left,
        // filling the area between them — identical in concept to Pine's fill().
        private void DrawBandFill(ChartControl cc, ChartScale cs,
                                  Series<double> topSeries, Series<double> bottomSeries,
                                  SharpDX.Direct2D1.Brush brush)
        {
            if (RenderTarget == null || brush == null) return;

            int fromBar = ChartBars.FromIndex;
            int toBar   = ChartBars.ToIndex;

            // Collect valid bar indices where both series have data
            var topPts = new List<Vector2>();
            var botPts = new List<Vector2>();

            for (int barIdx = fromBar; barIdx <= toBar; barIdx++)
            {
                int barsAgo = CurrentBar - barIdx;
                if (barsAgo < 0 || barsAgo >= topSeries.Count) continue;

                double tv = topSeries.GetValueAt(barIdx);
                double bv = bottomSeries.GetValueAt(barIdx);
                if (double.IsNaN(tv) || double.IsNaN(bv)) continue;

                float x = (float)cc.GetXByBarIndex(ChartBars, barIdx);
                topPts.Add(new Vector2(x, (float)cs.GetYByValue(tv)));
                botPts.Add(new Vector2(x, (float)cs.GetYByValue(bv)));
            }

            if (topPts.Count < 2) return;

            using (var geo  = new SharpDX.Direct2D1.PathGeometry(Core.Globals.D2DFactory))
            using (var sink = geo.Open())
            {
                sink.SetFillMode(FillMode.Winding);
                sink.BeginFigure(topPts[0], FigureBegin.Filled);

                // Forward: top series left → right
                for (int i = 1; i < topPts.Count; i++)
                    sink.AddLine(topPts[i]);

                // Reverse: bottom series right → left
                for (int i = botPts.Count - 1; i >= 0; i--)
                    sink.AddLine(botPts[i]);

                sink.EndFigure(FigureEnd.Closed);
                sink.Close();

                RenderTarget.FillGeometry(geo, brush);
            }
        }

        private void DrawLabel(float x, float y, string text, SharpDX.Direct2D1.Brush bgBrush)
        {
            if (labelFormat == null || RenderTarget == null) return;

            using (var layout = new SharpDX.DirectWrite.TextLayout(
                Core.Globals.DirectWriteFactory, text, labelFormat, 200f, 20f))
            {
                float tw  = layout.Metrics.Width  + 6f;
                float th  = layout.Metrics.Height + 2f;
                float top = y - th / 2f;

                RenderTarget.FillRoundedRectangle(
                    new RoundedRectangle
                    { Rect = new RectangleF(x, top, tw, th), RadiusX = 2f, RadiusY = 2f },
                    bgBrush);

                using (var white = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, SharpDX.Color.White))
                    RenderTarget.DrawTextLayout(new Vector2(x + 3f, top + 1f), layout, white);
            }
        }

        // ── Brush management ─────────────────────────────────────────────────
        private void EnsureBrushes()
        {
            if (brushesBuilt) return;

            float alpha = Math.Max(0, Math.Min(100, FillOpacity)) / 100f;

            Color4 midC   = StrokeToColor4(MidasStroke);
            Color4 b1C    = StrokeToColor4(Band1Stroke);
            Color4 b2C    = StrokeToColor4(Band2Stroke);
            Color4 fibC   = StrokeToColor4(FibBandStroke);

            // Inner fill (±1σ zone) uses Band1 color
            fill1UpperBrush = MakeBrush(new Color4(b1C.Red, b1C.Green, b1C.Blue, alpha));
            fill1LowerBrush = MakeBrush(new Color4(b1C.Red, b1C.Green, b1C.Blue, alpha));
            // Outer fill (±1σ to ±2σ zone) uses Band2 color at half opacity so it reads lighter
            float alpha2 = alpha * 0.5f;
            fill2UpperBrush = MakeBrush(new Color4(b2C.Red, b2C.Green, b2C.Blue, alpha2));
            fill2LowerBrush = MakeBrush(new Color4(b2C.Red, b2C.Green, b2C.Blue, alpha2));

            // Label backgrounds
            labelMidBrush   = MakeBrush(new Color4(midC.Red, midC.Green, midC.Blue, 0.85f));
            labelBand1Brush = MakeBrush(new Color4(b1C.Red,  b1C.Green,  b1C.Blue,  0.85f));
            labelBand2Brush = MakeBrush(new Color4(b2C.Red,  b2C.Green,  b2C.Blue,  0.70f));
            labelFibBrush   = MakeBrush(new Color4(fibC.Red, fibC.Green, fibC.Blue, 0.85f));

            labelFormat = new SharpDX.DirectWrite.TextFormat(
                Core.Globals.DirectWriteFactory, "Arial", 10f);

            brushesBuilt = true;
        }

        private SharpDX.Direct2D1.SolidColorBrush MakeBrush(Color4 c)
            => new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, c);

        private void DisposeBrushes()
        {
            fill1UpperBrush?.Dispose();  fill1UpperBrush = null;
            fill1LowerBrush?.Dispose();  fill1LowerBrush = null;
            fill2UpperBrush?.Dispose();  fill2UpperBrush = null;
            fill2LowerBrush?.Dispose();  fill2LowerBrush = null;
            labelMidBrush?.Dispose();    labelMidBrush   = null;
            labelBand1Brush?.Dispose();  labelBand1Brush = null;
            labelBand2Brush?.Dispose();  labelBand2Brush = null;
            labelFibBrush?.Dispose();    labelFibBrush   = null;
            labelFormat?.Dispose();      labelFormat     = null;
            brushesBuilt = false;
        }

        private Color4 StrokeToColor4(Stroke stroke)
        {
            if (stroke?.Brush is System.Windows.Media.SolidColorBrush scb)
            {
                var c = scb.Color;
                return new Color4(c.R / 255f, c.G / 255f, c.B / 255f, c.A / 255f);
            }
            return SharpDX.Color.White;
        }

        // ── Anchor key ───────────────────────────────────────────────────────
        private string GetAnchorBarKey()
        {
            DateTime t = Time[0];
            switch (anchorTimeframe)
            {
                case "Weekly":
                    System.Globalization.Calendar cal = System.Globalization.CultureInfo.InvariantCulture.Calendar;
                    int week = cal.GetWeekOfYear(t,
                        System.Globalization.CalendarWeekRule.FirstFourDayWeek,
                        DayOfWeek.Monday);
                    return $"{t.Year}-W{week}";
                case "Monthly":
                    return $"{t.Year}-{t.Month}";
                case "Quarterly":
                    return $"{t.Year}-Q{(t.Month - 1) / 3}";
                case "Yearly":
                    return $"{t.Year}";
                default: // "Daily"
                    return t.Date.ToString("yyyyMMdd");
            }
        }

        private void ParseFibLevels()
        {
            var parts = FibLevelsInput
                .Replace(" ", "")
                .Split(new char[] { ',' }, StringSplitOptions.RemoveEmptyEntries);

            var list = new List<double>();
            foreach (var p in parts)
                if (double.TryParse(p,
                    System.Globalization.NumberStyles.Any,
                    System.Globalization.CultureInfo.InvariantCulture,
                    out double v))
                    list.Add(v);

            fibLevels = list.ToArray();
        }

        // ── Properties ───────────────────────────────────────────────────────
        #region Properties

        // 1 | Anchor
        [NinjaScriptProperty]
        [Display(Name = "Anchor Method", GroupName = "1 | Anchor", Order = 0,
                 Description = "Session resets at the futures open (6 PM ET by default). Timeframe resets at each new anchor bar. Date anchors from a fixed point in history.")]
        [TypeConverter(typeof(AnchorMethodConverter))]
        public string AnchorMethod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Anchor Timeframe", GroupName = "1 | Anchor", Order = 1,
                 Description = "When Anchor Method = Timeframe, the VWAP resets at the start of each new period of this type.")]
        [TypeConverter(typeof(AnchorTimeframeConverter))]
        public string AnchorTimeframe { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Anchor Date", GroupName = "1 | Anchor", Order = 2,
                 Description = "When Anchor Method = Date, calculations start from this UTC timestamp.")]
        public DateTime AnchorDate { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Session Open Hour (ET)", GroupName = "1 | Anchor", Order = 3,
                 Description = "When Anchor Method = Session, the VWAP resets at this hour (ET) each day. Default 18 = 6 PM futures open.")]
        public int SessionOpenHour { get; set; }

        // 2 | Bands
        [NinjaScriptProperty]
        [Range(0.01, double.MaxValue)]
        [Display(Name = "Band 1 Multiplier (±1σ)", GroupName = "2 | Bands", Order = 0,
                 Description = "Std dev multiplier for the inner mean-reversion bands. Price ranging between +1σ and -1σ = range market; long bounces off -1σ, short bounces off +1σ.")]
        public double Band1Multiplier { get; set; }

        [NinjaScriptProperty]
        [Range(0.01, double.MaxValue)]
        [Display(Name = "Band 2 Multiplier (±2σ)", GroupName = "2 | Bands", Order = 1,
                 Description = "Std dev multiplier for the outer extension bands. A close beyond ±2σ signals a trending/breakout market.")]
        public double Band2Multiplier { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Fibonacci Levels", GroupName = "2 | Bands", Order = 2,
                 Description = "Comma-separated ratios interpolated between MIDAS and ±2σ. 0.5 = ±1σ (mean-reversion band), 1.0 = ±2σ (extension band).")]
        public string FibLevelsInput { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Labels", GroupName = "2 | Bands", Order = 3,
                 Description = "Toggles right-edge labels for each level.")]
        public bool ShowLabels { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Fill", GroupName = "2 | Bands", Order = 4,
                 Description = "Toggles the shaded fill. Inner zone (MIDAS to ±1σ) uses Band 1 color; outer zone (±1σ to ±2σ) uses Band 2 color at half opacity.")]
        public bool ShowFill { get; set; }

        [NinjaScriptProperty]
        [Range(0, 100)]
        [Display(Name = "Fill Opacity %", GroupName = "2 | Bands", Order = 5,
                 Description = "Opacity of the inner fill (0 = transparent, 100 = fully opaque). Outer zone is rendered at half this value.")]
        public int FillOpacity { get; set; }

        // 3 | Style
        [Display(Name = "MIDAS Line", GroupName = "3 | Style", Order = 0,
                 Description = "Color, dash style, and width for the central MIDAS VWAP line.")]
        public Stroke MidasStroke { get; set; }

        [Display(Name = "Band 1 (±1σ)", GroupName = "3 | Style", Order = 1,
                 Description = "Color, dash style, and width for the inner mean-reversion bands. Inner fill color also follows this.")]
        public Stroke Band1Stroke { get; set; }

        [Display(Name = "Band 2 (±2σ)", GroupName = "3 | Style", Order = 2,
                 Description = "Color, dash style, and width for the outer extension bands. Outer fill color also follows this.")]
        public Stroke Band2Stroke { get; set; }

        [Display(Name = "Fib Bands", GroupName = "3 | Style", Order = 3,
                 Description = "Color, dash style, and width shared by all Fibonacci sub-band lines.")]
        public Stroke FibBandStroke { get; set; }

        // Series accessors
        [Browsable(false)] [XmlIgnore]
        public Series<double> MIDAS   => Values[PlotMidas];
        [Browsable(false)] [XmlIgnore]
        public Series<double> Upper1  => Values[PlotUpper1];
        [Browsable(false)] [XmlIgnore]
        public Series<double> Lower1  => Values[PlotLower1];
        [Browsable(false)] [XmlIgnore]
        public Series<double> Upper2  => Values[PlotUpper2];
        [Browsable(false)] [XmlIgnore]
        public Series<double> Lower2  => Values[PlotLower2];

        #endregion
    }

    public class AnchorMethodConverter : TypeConverter
    {
        public override bool GetStandardValuesSupported(ITypeDescriptorContext context) => true;
        public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) => true;
        public override StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            => new StandardValuesCollection(new[] { "Session", "Timeframe", "Date" });
    }

    public class AnchorTimeframeConverter : TypeConverter
    {
        public override bool GetStandardValuesSupported(ITypeDescriptorContext context) => true;
        public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) => true;
        public override StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
            => new StandardValuesCollection(new[] { "Daily", "Weekly", "Monthly", "Quarterly", "Yearly" });
    }
}

// NinjaScript generated code is auto-written by NT8 at compile time — do not add it manually.

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private RedTail.RedTailVWAPFibBands[] cacheRedTailVWAPFibBands;
		public RedTail.RedTailVWAPFibBands RedTailVWAPFibBands(string anchorMethod, string anchorTimeframe, DateTime anchorDate, int sessionOpenHour, double band1Multiplier, double band2Multiplier, string fibLevelsInput, bool showLabels, bool showFill, int fillOpacity)
		{
			return RedTailVWAPFibBands(Input, anchorMethod, anchorTimeframe, anchorDate, sessionOpenHour, band1Multiplier, band2Multiplier, fibLevelsInput, showLabels, showFill, fillOpacity);
		}

		public RedTail.RedTailVWAPFibBands RedTailVWAPFibBands(ISeries<double> input, string anchorMethod, string anchorTimeframe, DateTime anchorDate, int sessionOpenHour, double band1Multiplier, double band2Multiplier, string fibLevelsInput, bool showLabels, bool showFill, int fillOpacity)
		{
			if (cacheRedTailVWAPFibBands != null)
				for (int idx = 0; idx < cacheRedTailVWAPFibBands.Length; idx++)
					if (cacheRedTailVWAPFibBands[idx] != null && cacheRedTailVWAPFibBands[idx].AnchorMethod == anchorMethod && cacheRedTailVWAPFibBands[idx].AnchorTimeframe == anchorTimeframe && cacheRedTailVWAPFibBands[idx].AnchorDate == anchorDate && cacheRedTailVWAPFibBands[idx].SessionOpenHour == sessionOpenHour && cacheRedTailVWAPFibBands[idx].Band1Multiplier == band1Multiplier && cacheRedTailVWAPFibBands[idx].Band2Multiplier == band2Multiplier && cacheRedTailVWAPFibBands[idx].FibLevelsInput == fibLevelsInput && cacheRedTailVWAPFibBands[idx].ShowLabels == showLabels && cacheRedTailVWAPFibBands[idx].ShowFill == showFill && cacheRedTailVWAPFibBands[idx].FillOpacity == fillOpacity && cacheRedTailVWAPFibBands[idx].EqualsInput(input))
						return cacheRedTailVWAPFibBands[idx];
			return CacheIndicator<RedTail.RedTailVWAPFibBands>(new RedTail.RedTailVWAPFibBands(){ AnchorMethod = anchorMethod, AnchorTimeframe = anchorTimeframe, AnchorDate = anchorDate, SessionOpenHour = sessionOpenHour, Band1Multiplier = band1Multiplier, Band2Multiplier = band2Multiplier, FibLevelsInput = fibLevelsInput, ShowLabels = showLabels, ShowFill = showFill, FillOpacity = fillOpacity }, input, ref cacheRedTailVWAPFibBands);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.RedTail.RedTailVWAPFibBands RedTailVWAPFibBands(string anchorMethod, string anchorTimeframe, DateTime anchorDate, int sessionOpenHour, double band1Multiplier, double band2Multiplier, string fibLevelsInput, bool showLabels, bool showFill, int fillOpacity)
		{
			return indicator.RedTailVWAPFibBands(Input, anchorMethod, anchorTimeframe, anchorDate, sessionOpenHour, band1Multiplier, band2Multiplier, fibLevelsInput, showLabels, showFill, fillOpacity);
		}

		public Indicators.RedTail.RedTailVWAPFibBands RedTailVWAPFibBands(ISeries<double> input , string anchorMethod, string anchorTimeframe, DateTime anchorDate, int sessionOpenHour, double band1Multiplier, double band2Multiplier, string fibLevelsInput, bool showLabels, bool showFill, int fillOpacity)
		{
			return indicator.RedTailVWAPFibBands(input, anchorMethod, anchorTimeframe, anchorDate, sessionOpenHour, band1Multiplier, band2Multiplier, fibLevelsInput, showLabels, showFill, fillOpacity);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.RedTail.RedTailVWAPFibBands RedTailVWAPFibBands(string anchorMethod, string anchorTimeframe, DateTime anchorDate, int sessionOpenHour, double band1Multiplier, double band2Multiplier, string fibLevelsInput, bool showLabels, bool showFill, int fillOpacity)
		{
			return indicator.RedTailVWAPFibBands(Input, anchorMethod, anchorTimeframe, anchorDate, sessionOpenHour, band1Multiplier, band2Multiplier, fibLevelsInput, showLabels, showFill, fillOpacity);
		}

		public Indicators.RedTail.RedTailVWAPFibBands RedTailVWAPFibBands(ISeries<double> input , string anchorMethod, string anchorTimeframe, DateTime anchorDate, int sessionOpenHour, double band1Multiplier, double band2Multiplier, string fibLevelsInput, bool showLabels, bool showFill, int fillOpacity)
		{
			return indicator.RedTailVWAPFibBands(input, anchorMethod, anchorTimeframe, anchorDate, sessionOpenHour, band1Multiplier, band2Multiplier, fibLevelsInput, showLabels, showFill, fillOpacity);
		}
	}
}

#endregion
