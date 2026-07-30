#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Core;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.NinjaScript;
using SharpDX;
using SharpDX.Direct2D1;
using SharpDX.DirectWrite;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class SessionStatisticalLevels : Indicator
    {
        #region Private Classes

        private class SessionData
        {
            public double Open;
            public double High;
            public double Low;
            public double Close;
            public double MAE;  // max adverse excursion from open (open - low for default)
            public double MFE;  // max favorable excursion from open (high - open for default)
            public bool   Active;
            public int    StartBar;

            public List<double> Ranges   = new List<double>();
            public List<double> BullUp   = new List<double>();  // bull MFE (upside from open)
            public List<double> BullDn   = new List<double>();  // bull MAE (downside from open)
            public List<double> BearDn   = new List<double>();  // bear MFE (downside from open)
            public List<double> BearUp   = new List<double>();  // bear MAE (upside from open)

            public int BullCount;
            public int BearCount;

            public void Reset(double open, double high, double low, double close)
            {
                Open   = open;
                High   = high;
                Low    = low;
                Close  = close;
                MAE    = 0;
                MFE    = 0;
                Active = true;
            }

            public void Update(double high, double low, double close)
            {
                if (high > High) High = high;
                if (low  < Low)  Low  = low;
                Close = close;
                MAE = Math.Max(MAE, Open - low);
                MFE = Math.Max(MFE, high - Open);
            }

            public void Record(int maxSessions)
            {
                if (double.IsNaN(Open)) return;

                double rng = High - Low;
                Ranges.Add(rng);

                if (Close > Open)
                {
                    BullUp.Add(MFE);
                    BullDn.Add(MAE);
                    BullCount++;
                }
                else if (Close < Open)
                {
                    BearDn.Add(MAE);
                    BearUp.Add(MFE);
                    BearCount++;
                }

                TrimList(Ranges, maxSessions);
                TrimList(BullUp, maxSessions);
                TrimList(BullDn, maxSessions);
                TrimList(BearDn, maxSessions);
                TrimList(BearUp, maxSessions);

                Active = false;
            }

            private static void TrimList(List<double> list, int max)
            {
                while (list.Count > max)
                    list.RemoveAt(0);
            }
        }

        private class LevelInfo
        {
            public double Price;
            public string Label;
            public System.Windows.Media.Brush WpfBrush;
            public int    Style;   // 0=solid, 1=dashed, 2=dotted
        }

        private class SessionLevels
        {
            public string Name;
            public double SessionOpen;
            public int    StartBar;
            public int    EndBar;
            public List<LevelInfo> Levels = new List<LevelInfo>();
            public bool   Visible;

            // Band fill pairs: (topPrice, botPrice, fillBrush)
            public List<Tuple<double, double, System.Windows.Media.Brush>> Fills = new List<Tuple<double, double, System.Windows.Media.Brush>>();
        }

        #endregion

        #region Private Fields

        private SessionData asiaData;
        private SessionData londonData;
        private SessionData nyData;
        private SessionData customData;

        private SessionLevels asiaLevels;
        private SessionLevels londonLevels;
        private SessionLevels nyLevels;
        private SessionLevels customLevels;

        private bool prevInAsia;
        private bool prevInLondon;
        private bool prevInNY;
        private bool prevInCustom;

        // Session time boundaries (ET hours/minutes)
        private int asiaStartH = 19, asiaStartM = 0;
        private int asiaEndH   = 2,  asiaEndM   = 0;
        private int lonStartH  = 2,  lonStartM  = 0;
        private int lonEndH    = 8,  lonEndM    = 0;
        private int nyStartH   = 8,  nyStartM   = 0;
        private int nyEndH     = 16, nyEndM     = 0;
        private int cusStartH, cusStartM, cusEndH, cusEndM;

        // SharpDX resources
        private SharpDX.Direct2D1.Brush dxBrushMedian;
        private SharpDX.Direct2D1.Brush dxBrushIQR;
        private SharpDX.Direct2D1.Brush dxBrushP10P90;
        private SharpDX.Direct2D1.Brush dxBrushP95;
        private SharpDX.Direct2D1.Brush dxBrushMean;
        private SharpDX.Direct2D1.Brush dxBrushStDev;
        private SharpDX.Direct2D1.Brush dxBrushMAE;
        private SharpDX.Direct2D1.Brush dxBrushMFE;
        private SharpDX.Direct2D1.Brush dxFillIQR;
        private SharpDX.Direct2D1.Brush dxFillP90;
        private SharpDX.Direct2D1.Brush dxBrushTableBg;
        private SharpDX.Direct2D1.Brush dxBrushTableHeader;
        private SharpDX.Direct2D1.Brush dxBrushTableText;
        private SharpDX.Direct2D1.Brush dxBrushTableHeaderText;
        private SharpDX.Direct2D1.Brush dxBrushTableBorder;
        private SharpDX.Direct2D1.Brush dxBrushTableRowAlt;

        private SharpDX.DirectWrite.TextFormat textFormatLabel;
        private SharpDX.DirectWrite.TextFormat textFormatTable;

        private bool resourcesCreated;

        private TimeZoneInfo etZone;

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description             = "Session Statistical Levels - plots percentile-based range levels from session open for Asia/London/NY sessions. Original Pine Script by @notprofgreen. NinjaTrader 8 conversion by @_hawkeye_13.";
                Name                    = "SessionStatisticalLevels";
                Calculate               = Calculate.OnBarClose;
                IsOverlay               = true;
                DisplayInDataBox        = false;
                DrawOnPricePanel        = true;
                IsSuspendedWhileInactive = true;

                // Global
                LookbackSessions = 100;
                LabelSize        = TextSize.Tiny;
                ShowTable        = true;
                TablePosition    = StatTablePosition.BottomRight;

                // Sessions
                ShowAsia    = true;
                ShowLondon  = true;
                ShowNY      = true;
                ShowCustom  = false;
                CustomStart = "0900";
                CustomEnd   = "1200";
                CustomLabel = "Custom";

                // Levels
                ShowMedian   = true;
                ShowIQR      = true;
                ShowP10P90   = true;
                ShowP95      = false;
                ShowMean     = true;
                ShowStDev    = false;
                ShowMAEMFE   = true;
                ShowBullBear = true;
                ShowFills    = true;

                // Colors
                MedianColor  = System.Windows.Media.Brushes.Black;
                IQRColor     = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(80, 80, 80));
                P10P90Color  = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(120, 120, 120));
                P95Color     = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(160, 80, 80));
                MeanColor    = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(60, 60, 160));
                StDevColor   = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(100, 100, 200));
                MAEColor     = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(180, 80, 80));
                MFEColor     = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(80, 140, 80));
                IQRFillColor = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromArgb(20, 128, 128, 128));
                P90FillColor = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromArgb(10, 128, 128, 128));

                // Freeze brushes
                MedianColor.Freeze();  IQRColor.Freeze();  P10P90Color.Freeze();
                P95Color.Freeze();     MeanColor.Freeze(); StDevColor.Freeze();
                MAEColor.Freeze();     MFEColor.Freeze();  IQRFillColor.Freeze();
                P90FillColor.Freeze();
            }
            else if (State == State.Configure)
            {
                ParseCustomSession();
                etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            }
            else if (State == State.DataLoaded)
            {
                asiaData   = new SessionData();
                londonData = new SessionData();
                nyData     = new SessionData();
                customData = new SessionData();

                asiaLevels   = new SessionLevels { Name = "Asia" };
                londonLevels = new SessionLevels { Name = "Lon" };
                nyLevels     = new SessionLevels { Name = "NY" };
                customLevels = new SessionLevels { Name = CustomLabel };

                prevInAsia   = false;
                prevInLondon = false;
                prevInNY     = false;
                prevInCustom = false;
            }
            else if (State == State.Terminated)
            {
                DisposeResources();
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;

            DateTime etTime = TimeZoneInfo.ConvertTime(Time[0], etZone);
            int hhmm = etTime.Hour * 100 + etTime.Minute;

            // Determine which sessions we're in
            bool inAsia   = IsInSession(hhmm, asiaStartH * 100 + asiaStartM, asiaEndH * 100 + asiaEndM, true);
            bool inLondon = IsInSession(hhmm, lonStartH * 100 + lonStartM, lonEndH * 100 + lonEndM, false);
            bool inNY     = IsInSession(hhmm, nyStartH * 100 + nyStartM, nyEndH * 100 + nyEndM, false);
            bool inCustom = IsInSession(hhmm, cusStartH * 100 + cusStartM, cusEndH * 100 + cusEndM,
                                        cusStartH * 100 + cusStartM > cusEndH * 100 + cusEndM);

            // --- Asia ---
            if (ShowAsia)
                ProcessSession(ref asiaData, ref asiaLevels, inAsia, prevInAsia, "Asia");

            // --- London ---
            if (ShowLondon)
                ProcessSession(ref londonData, ref londonLevels, inLondon, prevInLondon, "Lon");

            // --- NY ---
            if (ShowNY)
                ProcessSession(ref nyData, ref nyLevels, inNY, prevInNY, "NY");

            // --- Custom ---
            if (ShowCustom)
                ProcessSession(ref customData, ref customLevels, inCustom, prevInCustom, CustomLabel);

            prevInAsia   = inAsia;
            prevInLondon = inLondon;
            prevInNY     = inNY;
            prevInCustom = inCustom;
        }

        #region Session Processing

        private void ProcessSession(ref SessionData data, ref SessionLevels levels, bool inSession, bool wasIn, string label)
        {
            bool sessionStart = inSession && !wasIn;
            bool sessionEnd   = !inSession && wasIn;

            if (sessionStart)
            {
                data.Reset(Open[0], High[0], Low[0], Close[0]);
                data.StartBar = CurrentBar;
                BuildLevels(ref levels, data, label);
            }
            else if (inSession && data.Active)
            {
                data.Update(High[0], Low[0], Close[0]);
                levels.EndBar = CurrentBar;
            }

            if (sessionEnd && data.Active)
            {
                data.Record(LookbackSessions);
                levels.Visible = false;
            }
        }

        private void BuildLevels(ref SessionLevels levels, SessionData data, string label)
        {
            levels.Levels.Clear();
            levels.Fills.Clear();
            levels.SessionOpen = data.Open;
            levels.StartBar    = CurrentBar;
            levels.EndBar      = CurrentBar;
            levels.Visible     = true;
            levels.Name        = label;

            int n = data.Ranges.Count;
            if (n < 2) return;

            var sorted = data.Ranges.OrderBy(x => x).ToList();

            double p10 = Percentile(sorted, 10);
            double p25 = Percentile(sorted, 25);
            double p50 = Percentile(sorted, 50);
            double p75 = Percentile(sorted, 75);
            double p90 = Percentile(sorted, 90);
            double p95 = Percentile(sorted, 95);
            double avg = sorted.Average();
            double sd  = StdDev(sorted, avg);

            double sOpen = data.Open;

            // Symmetric range-based levels
            if (ShowP10P90)
            {
                AddLevel(levels, sOpen + p90, label + " P90",  P10P90Color, 2);
                AddLevel(levels, sOpen - p90, label + " -P90", P10P90Color, 2);
                AddLevel(levels, sOpen + p10, label + " P10",  P10P90Color, 2);
                AddLevel(levels, sOpen - p10, label + " -P10", P10P90Color, 2);
                if (ShowFills)
                {
                    levels.Fills.Add(Tuple.Create(sOpen + p90, sOpen - p90, (System.Windows.Media.Brush)P90FillColor));
                    levels.Fills.Add(Tuple.Create(sOpen + p10, sOpen - p10, (System.Windows.Media.Brush)P90FillColor));
                }
            }

            if (ShowIQR)
            {
                AddLevel(levels, sOpen + p75, label + " P75",  IQRColor, 2);
                AddLevel(levels, sOpen - p75, label + " -P75", IQRColor, 2);
                AddLevel(levels, sOpen + p25, label + " P25",  IQRColor, 2);
                AddLevel(levels, sOpen - p25, label + " -P25", IQRColor, 2);
                if (ShowFills)
                {
                    levels.Fills.Add(Tuple.Create(sOpen + p75, sOpen - p75, (System.Windows.Media.Brush)IQRFillColor));
                    levels.Fills.Add(Tuple.Create(sOpen + p25, sOpen - p25, (System.Windows.Media.Brush)IQRFillColor));
                }
            }

            if (ShowMedian)
            {
                AddLevel(levels, sOpen + p50, label + " Med",  MedianColor, 1);
                AddLevel(levels, sOpen - p50, label + " -Med", MedianColor, 1);
            }

            if (ShowMean)
            {
                AddLevel(levels, sOpen + avg, label + " Mean",  MeanColor, 1);
                AddLevel(levels, sOpen - avg, label + " -Mean", MeanColor, 1);
            }

            if (ShowStDev)
            {
                AddLevel(levels, sOpen + avg + sd, label + " +1SD", StDevColor, 2);
                AddLevel(levels, sOpen - avg - sd, label + " -1SD", StDevColor, 2);
            }

            if (ShowP95)
            {
                AddLevel(levels, sOpen + p95, label + " P95",  P95Color, 2);
                AddLevel(levels, sOpen - p95, label + " -P95", P95Color, 2);
            }

            // Directional MAE/MFE
            if (ShowMAEMFE && ShowBullBear)
            {
                // Bull
                if (data.BullUp.Count >= 2)
                {
                    var bullUpSorted = data.BullUp.OrderBy(x => x).ToList();
                    var bullDnSorted = data.BullDn.OrderBy(x => x).ToList();
                    double bullMFE50 = Percentile(bullUpSorted, 50);
                    double bullMFE75 = Percentile(bullUpSorted, 75);
                    double bullMAE50 = Percentile(bullDnSorted, 50);

                    AddLevel(levels, sOpen + bullMFE50, label + " Bull MFE50", MFEColor, 0);
                    AddLevel(levels, sOpen + bullMFE75, label + " Bull MFE75", MFEColor, 2);
                    AddLevel(levels, sOpen - bullMAE50, label + " Bull MAE50", MAEColor, 0);
                }

                // Bear
                if (data.BearDn.Count >= 2)
                {
                    var bearDnSorted = data.BearDn.OrderBy(x => x).ToList();
                    var bearUpSorted = data.BearUp.OrderBy(x => x).ToList();
                    double bearMFE50 = Percentile(bearDnSorted, 50);
                    double bearMFE75 = Percentile(bearDnSorted, 75);
                    double bearMAE50 = Percentile(bearUpSorted, 50);

                    AddLevel(levels, sOpen - bearMFE50, label + " Bear MFE50", MFEColor, 0);
                    AddLevel(levels, sOpen - bearMFE75, label + " Bear MFE75", MFEColor, 2);
                    AddLevel(levels, sOpen + bearMAE50, label + " Bear MAE50", MAEColor, 0);
                }
            }
        }

        private void AddLevel(SessionLevels levels, double price, string label, System.Windows.Media.Brush brush, int style)
        {
            levels.Levels.Add(new LevelInfo
            {
                Price    = price,
                Label    = label,
                WpfBrush = brush,
                Style    = style
            });
        }

        #endregion

        #region Rendering

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            base.OnRender(chartControl, chartScale);

            if (chartControl == null || chartScale == null) return;

            var renderTarget = RenderTarget;
            if (renderTarget == null) return;

            if (!resourcesCreated)
                CreateResources(renderTarget);

            // Draw each active session's levels
            if (ShowAsia)   DrawSessionLevels(renderTarget, chartControl, chartScale, asiaLevels);
            if (ShowLondon) DrawSessionLevels(renderTarget, chartControl, chartScale, londonLevels);
            if (ShowNY)     DrawSessionLevels(renderTarget, chartControl, chartScale, nyLevels);
            if (ShowCustom) DrawSessionLevels(renderTarget, chartControl, chartScale, customLevels);

            // Draw stats table
            if (ShowTable)
                DrawTable(renderTarget, chartControl, chartScale);
        }

        private void DrawSessionLevels(SharpDX.Direct2D1.RenderTarget rt, ChartControl cc, ChartScale cs, SessionLevels sl)
        {
            if (!sl.Visible || sl.Levels.Count == 0) return;

            int startIdx = sl.StartBar - ChartBars.FromIndex;
            int endIdx   = sl.EndBar   - ChartBars.FromIndex;

            if (startIdx < 0) startIdx = 0;
            if (endIdx < startIdx) return;

            float x1 = cc.GetXByBarIndex(ChartBars, Math.Max(ChartBars.FromIndex, sl.StartBar));
            float x2 = cc.GetXByBarIndex(ChartBars, Math.Min(ChartBars.ToIndex, sl.EndBar));

            if (x2 <= x1) x2 = x1 + 1;

            // Draw fills
            if (ShowFills)
            {
                foreach (var fill in sl.Fills)
                {
                    float yTop = cs.GetYByValue(fill.Item1);
                    float yBot = cs.GetYByValue(fill.Item2);
                    if (yBot < yTop) { float tmp = yTop; yTop = yBot; yBot = tmp; }

                    var fillBrush = fill.Item3.ToDxBrush(rt);
                    rt.FillRectangle(new SharpDX.RectangleF(x1, yTop, x2 - x1, yBot - yTop), fillBrush);
                    fillBrush.Dispose();
                }
            }

            // Draw levels
            foreach (var lv in sl.Levels)
            {
                float y = cs.GetYByValue(lv.Price);

                var brush = lv.WpfBrush.ToDxBrush(rt);
                var strokeStyle = GetStrokeStyle(lv.Style);

                rt.DrawLine(new SharpDX.Vector2(x1, y), new SharpDX.Vector2(x2, y), brush, 1f, strokeStyle);

                // Label
                if (textFormatLabel != null)
                {
                    using (var layout = new SharpDX.DirectWrite.TextLayout(
                        Core.Globals.DirectWriteFactory, " " + lv.Label, textFormatLabel, 300, 20))
                    {
                        rt.DrawTextLayout(new SharpDX.Vector2(x2 + 2, y - 7), layout, brush);
                    }
                }

                brush.Dispose();
                if (strokeStyle != null) strokeStyle.Dispose();
            }
        }

        private SharpDX.Direct2D1.StrokeStyle GetStrokeStyle(int style)
        {
            if (style == 0) return null; // solid

            var props = new StrokeStyleProperties();
            if (style == 1) // dashed
            {
                props.DashStyle = SharpDX.Direct2D1.DashStyle.Dash;
            }
            else // dotted
            {
                props.DashStyle  = SharpDX.Direct2D1.DashStyle.Custom;
                props.DashOffset = 0;
            }

            if (style == 2)
            {
                return new SharpDX.Direct2D1.StrokeStyle(
                    Core.Globals.D2DFactory, props, new float[] { 2f, 4f });
            }
            return new SharpDX.Direct2D1.StrokeStyle(Core.Globals.D2DFactory, props);
        }

        #endregion

        #region Stats Table Rendering

        private void DrawTable(SharpDX.Direct2D1.RenderTarget rt, ChartControl cc, ChartScale cs)
        {
            float cellW   = 70;
            float cellH   = 18;
            float headerH = 20;
            int   cols    = 7;
            int   rows    = 6; // header + 4 sessions + footer
            float tableW  = cols * cellW;
            float tableH  = headerH + (rows - 1) * cellH;
            float padding = 10;

            float tableX, tableY;
            switch (TablePosition)
            {
                case StatTablePosition.TopLeft:
                    tableX = padding; tableY = padding; break;
                case StatTablePosition.TopRight:
                    tableX = cc.CanvasRight - cc.CanvasLeft - tableW - padding; tableY = padding; break;
                case StatTablePosition.BottomLeft:
                    tableX = padding; tableY = cs.GetYByValue(cs.MinValue) - tableH - padding;
                    if (tableY < 0) tableY = padding; break;
                default: // BottomRight
                    tableX = cc.CanvasRight - cc.CanvasLeft - tableW - padding;
                    tableY = cs.GetYByValue(cs.MinValue) - tableH - padding;
                    if (tableY < 0) tableY = padding; break;
            }

            // Background
            rt.FillRectangle(new SharpDX.RectangleF(tableX, tableY, tableW, tableH), dxBrushTableBg);
            rt.DrawRectangle(new SharpDX.RectangleF(tableX, tableY, tableW, tableH), dxBrushTableBorder, 1f);

            // Header
            string[] headers = { "Session", "N", "P25", "P50 Med", "P75", "P90", "Mean/SD" };
            rt.FillRectangle(new SharpDX.RectangleF(tableX, tableY, tableW, headerH), dxBrushTableHeader);

            for (int c = 0; c < cols; c++)
            {
                float cx = tableX + c * cellW;
                using (var layout = new SharpDX.DirectWrite.TextLayout(
                    Core.Globals.DirectWriteFactory, headers[c], textFormatTable, cellW, headerH))
                {
                    layout.TextAlignment = SharpDX.DirectWrite.TextAlignment.Center;
                    rt.DrawTextLayout(new SharpDX.Vector2(cx, tableY + 2), layout, dxBrushTableHeaderText);
                }
            }

            // Session rows
            DrawTableRow(rt, tableX, tableY + headerH + 0 * cellH, cellW, cellH, "Asia",        asiaData,   ShowAsia);
            DrawTableRow(rt, tableX, tableY + headerH + 1 * cellH, cellW, cellH, "London",      londonData, ShowLondon);
            DrawTableRow(rt, tableX, tableY + headerH + 2 * cellH, cellW, cellH, "NY",          nyData,     ShowNY);
            DrawTableRow(rt, tableX, tableY + headerH + 3 * cellH, cellW, cellH, CustomLabel,   customData, ShowCustom);

            // Footer
            float footerY = tableY + headerH + 4 * cellH;
            var footBrush = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.96f, 0.96f, 0.96f, 1f));
            rt.FillRectangle(new SharpDX.RectangleF(tableX, footerY, tableW, cellH), footBrush);
            using (var layout = new SharpDX.DirectWrite.TextLayout(
                Core.Globals.DirectWriteFactory, "Lookback: " + LookbackSessions, textFormatTable, tableW, cellH))
            {
                layout.TextAlignment = SharpDX.DirectWrite.TextAlignment.Center;
                var footTxt = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.5f, 0.5f, 0.5f, 1f));
                rt.DrawTextLayout(new SharpDX.Vector2(tableX, footerY + 2), layout, footTxt);
                footTxt.Dispose();
            }
            footBrush.Dispose();
        }

        private void DrawTableRow(SharpDX.Direct2D1.RenderTarget rt, float x, float y, float cellW, float cellH,
                                   string name, SessionData data, bool active)
        {
            var bg = active ? dxBrushTableBg : dxBrushTableRowAlt;
            rt.FillRectangle(new SharpDX.RectangleF(x, y, cellW * 7, cellH), bg);

            int n = data.Ranges.Count;
            string p25s  = n >= 2 ? Percentile(data.Ranges.OrderBy(v => v).ToList(), 25).ToString("F1") : "-";
            string p50s  = n >= 2 ? Percentile(data.Ranges.OrderBy(v => v).ToList(), 50).ToString("F1") : "-";
            string p75s  = n >= 2 ? Percentile(data.Ranges.OrderBy(v => v).ToList(), 75).ToString("F1") : "-";
            string p90s  = n >= 2 ? Percentile(data.Ranges.OrderBy(v => v).ToList(), 90).ToString("F1") : "-";
            string avgSd = "-";
            if (n >= 2)
            {
                var sorted = data.Ranges.OrderBy(v => v).ToList();
                double avg = sorted.Average();
                double sd  = StdDev(sorted, avg);
                avgSd = avg.ToString("F1") + "/" + sd.ToString("F1");
            }

            string bullBear = data.BullCount + "b/" + data.BearCount + "B";
            string[] cells = { name + " " + bullBear, n.ToString(), p25s, p50s, p75s, p90s, avgSd };

            for (int c = 0; c < 7; c++)
            {
                float cx = x + c * cellW;
                rt.DrawLine(new SharpDX.Vector2(cx, y), new SharpDX.Vector2(cx, y + cellH), dxBrushTableBorder, 0.5f);
                using (var layout = new SharpDX.DirectWrite.TextLayout(
                    Core.Globals.DirectWriteFactory, cells[c], textFormatTable, cellW, cellH))
                {
                    layout.TextAlignment = SharpDX.DirectWrite.TextAlignment.Center;
                    rt.DrawTextLayout(new SharpDX.Vector2(cx, y + 2), layout, dxBrushTableText);
                }
            }
        }

        #endregion

        #region Resource Management

        private void CreateResources(SharpDX.Direct2D1.RenderTarget rt)
        {
            dxBrushTableBg         = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(1f, 1f, 1f, 0.95f));
            dxBrushTableHeader     = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.16f, 0.16f, 0.16f, 1f));
            dxBrushTableText       = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.24f, 0.24f, 0.24f, 1f));
            dxBrushTableHeaderText = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(1f, 1f, 1f, 1f));
            dxBrushTableBorder     = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.7f, 0.7f, 0.7f, 1f));
            dxBrushTableRowAlt     = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.92f, 0.92f, 0.92f, 1f));

            float fontSize = LabelSize == TextSize.Tiny ? 9f : LabelSize == TextSize.Small ? 10f : 11f;

            textFormatLabel = new SharpDX.DirectWrite.TextFormat(
                Core.Globals.DirectWriteFactory, "Consolas", fontSize)
            {
                WordWrapping = WordWrapping.NoWrap
            };

            textFormatTable = new SharpDX.DirectWrite.TextFormat(
                Core.Globals.DirectWriteFactory, "Consolas", 9f)
            {
                WordWrapping = WordWrapping.NoWrap
            };

            resourcesCreated = true;
        }

        private void DisposeResources()
        {
            if (dxBrushTableBg != null)         { dxBrushTableBg.Dispose();         dxBrushTableBg = null; }
            if (dxBrushTableHeader != null)      { dxBrushTableHeader.Dispose();     dxBrushTableHeader = null; }
            if (dxBrushTableText != null)        { dxBrushTableText.Dispose();       dxBrushTableText = null; }
            if (dxBrushTableHeaderText != null)  { dxBrushTableHeaderText.Dispose(); dxBrushTableHeaderText = null; }
            if (dxBrushTableBorder != null)      { dxBrushTableBorder.Dispose();     dxBrushTableBorder = null; }
            if (dxBrushTableRowAlt != null)      { dxBrushTableRowAlt.Dispose();     dxBrushTableRowAlt = null; }
            if (textFormatLabel != null)         { textFormatLabel.Dispose();        textFormatLabel = null; }
            if (textFormatTable != null)         { textFormatTable.Dispose();        textFormatTable = null; }

            resourcesCreated = false;
        }

        public override void OnRenderTargetChanged()
        {
            DisposeResources();
        }

        #endregion

        #region Helpers

        private bool IsInSession(int hhmm, int start, int end, bool crossesMidnight)
        {
            if (crossesMidnight)
                return hhmm >= start || hhmm < end;
            else
                return hhmm >= start && hhmm < end;
        }

        private void ParseCustomSession()
        {
            if (CustomStart.Length == 4 && CustomEnd.Length == 4)
            {
                int.TryParse(CustomStart.Substring(0, 2), out cusStartH);
                int.TryParse(CustomStart.Substring(2, 2), out cusStartM);
                int.TryParse(CustomEnd.Substring(0, 2),   out cusEndH);
                int.TryParse(CustomEnd.Substring(2, 2),   out cusEndM);
            }
        }

        /// <summary>
        /// Nearest-rank percentile matching Pine Script's array.percentile_nearest_rank
        /// </summary>
        private static double Percentile(List<double> sorted, int p)
        {
            if (sorted.Count == 0) return double.NaN;
            if (sorted.Count == 1) return sorted[0];

            double rank = (p / 100.0) * sorted.Count;
            int idx = (int)Math.Ceiling(rank) - 1;
            if (idx < 0) idx = 0;
            if (idx >= sorted.Count) idx = sorted.Count - 1;
            return sorted[idx];
        }

        private static double StdDev(List<double> values, double mean)
        {
            if (values.Count < 2) return 0;
            double sumSq = 0;
            foreach (var v in values)
                sumSq += (v - mean) * (v - mean);
            return Math.Sqrt(sumSq / values.Count);
        }

        #endregion

        #region Properties

        // ---- Global ----
        [NinjaScriptProperty]
        [Range(10, int.MaxValue)]
        [Display(Name = "Lookback Sessions", GroupName = "Global Settings", Order = 1,
                 Description = "Number of historical sessions for percentile calculation. 50+ recommended.")]
        public int LookbackSessions { get; set; }

        [Display(Name = "Label Size", GroupName = "Global Settings", Order = 2)]
        public TextSize LabelSize { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Stats Table", GroupName = "Global Settings", Order = 3)]
        public bool ShowTable { get; set; }

        [Display(Name = "Table Position", GroupName = "Global Settings", Order = 4)]
        public StatTablePosition TablePosition { get; set; }

        // ---- Sessions ----
        [NinjaScriptProperty]
        [Display(Name = "Show Asia (7pm-2am ET)", GroupName = "Sessions", Order = 1)]
        public bool ShowAsia { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show London (2am-8am ET)", GroupName = "Sessions", Order = 2)]
        public bool ShowLondon { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show NY (8am-4pm ET)", GroupName = "Sessions", Order = 3)]
        public bool ShowNY { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Custom Session", GroupName = "Sessions", Order = 4)]
        public bool ShowCustom { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Custom Start (HHMM ET)", GroupName = "Sessions", Order = 5)]
        public string CustomStart { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Custom End (HHMM ET)", GroupName = "Sessions", Order = 6)]
        public string CustomEnd { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Custom Label", GroupName = "Sessions", Order = 7)]
        public string CustomLabel { get; set; }

        // ---- Levels ----
        [NinjaScriptProperty]
        [Display(Name = "Median (P50)", GroupName = "Levels to Show", Order = 1)]
        public bool ShowMedian { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "IQR Band (P25/P75)", GroupName = "Levels to Show", Order = 2)]
        public bool ShowIQR { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "P10 / P90", GroupName = "Levels to Show", Order = 3)]
        public bool ShowP10P90 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "P95 (extreme sessions)", GroupName = "Levels to Show", Order = 4)]
        public bool ShowP95 { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Mean", GroupName = "Levels to Show", Order = 5)]
        public bool ShowMean { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Mean +/- 1 StDev", GroupName = "Levels to Show", Order = 6,
                 Description = "Less reliable for skewed data - use percentiles instead")]
        public bool ShowStDev { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "MAE / MFE (bull+bear sep.)", GroupName = "Levels to Show", Order = 7,
                 Description = "Max Adverse / Favorable Excursion from session open")]
        public bool ShowMAEMFE { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Separate Bull/Bear Levels", GroupName = "Levels to Show", Order = 8,
                 Description = "Show percentile levels split by session direction")]
        public bool ShowBullBear { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Fills", GroupName = "Levels to Show", Order = 9)]
        public bool ShowFills { get; set; }

        // ---- Style ----
        [XmlIgnore]
        [Display(Name = "Median Color", GroupName = "Style", Order = 1)]
        public System.Windows.Media.Brush MedianColor { get; set; }
        [Browsable(false)]
        public string MedianColorSerialize { get { return Serialize.BrushToString(MedianColor); } set { MedianColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "IQR Color", GroupName = "Style", Order = 2)]
        public System.Windows.Media.Brush IQRColor { get; set; }
        [Browsable(false)]
        public string IQRColorSerialize { get { return Serialize.BrushToString(IQRColor); } set { IQRColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "P10/P90 Color", GroupName = "Style", Order = 3)]
        public System.Windows.Media.Brush P10P90Color { get; set; }
        [Browsable(false)]
        public string P10P90ColorSerialize { get { return Serialize.BrushToString(P10P90Color); } set { P10P90Color = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "P95 Color", GroupName = "Style", Order = 4)]
        public System.Windows.Media.Brush P95Color { get; set; }
        [Browsable(false)]
        public string P95ColorSerialize { get { return Serialize.BrushToString(P95Color); } set { P95Color = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "Mean Color", GroupName = "Style", Order = 5)]
        public System.Windows.Media.Brush MeanColor { get; set; }
        [Browsable(false)]
        public string MeanColorSerialize { get { return Serialize.BrushToString(MeanColor); } set { MeanColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "StDev Color", GroupName = "Style", Order = 6)]
        public System.Windows.Media.Brush StDevColor { get; set; }
        [Browsable(false)]
        public string StDevColorSerialize { get { return Serialize.BrushToString(StDevColor); } set { StDevColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "MAE Color", GroupName = "Style", Order = 7)]
        public System.Windows.Media.Brush MAEColor { get; set; }
        [Browsable(false)]
        public string MAEColorSerialize { get { return Serialize.BrushToString(MAEColor); } set { MAEColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "MFE Color", GroupName = "Style", Order = 8)]
        public System.Windows.Media.Brush MFEColor { get; set; }
        [Browsable(false)]
        public string MFEColorSerialize { get { return Serialize.BrushToString(MFEColor); } set { MFEColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "IQR Fill Color", GroupName = "Style", Order = 9)]
        public System.Windows.Media.Brush IQRFillColor { get; set; }
        [Browsable(false)]
        public string IQRFillColorSerialize { get { return Serialize.BrushToString(IQRFillColor); } set { IQRFillColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "P90 Fill Color", GroupName = "Style", Order = 10)]
        public System.Windows.Media.Brush P90FillColor { get; set; }
        [Browsable(false)]
        public string P90FillColorSerialize { get { return Serialize.BrushToString(P90FillColor); } set { P90FillColor = Serialize.StringToBrush(value); } }

        #endregion
    }

    public enum TextSize
    {
        Tiny,
        Small,
        Normal
    }

    public enum StatTablePosition
    {
        TopLeft,
        TopRight,
        BottomLeft,
        BottomRight
    }
}
