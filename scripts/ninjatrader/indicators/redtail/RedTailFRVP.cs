#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows;

using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Core;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    #region TypeConverters

    public class FRVPBOSConfirmationConverter : TypeConverter
    {
        public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
        public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return true; }
        public override StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
        { return new StandardValuesCollection(new[] { "Candle Close", "Wicks" }); }
    }

    public class FRVPVPAlignmentConverter : TypeConverter
    {
        public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
        public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return true; }
        public override StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
        { return new StandardValuesCollection(new[] { "Left", "Right" }); }
    }

    public class FRVPTriggerTypeConverter : TypeConverter
    {
        public override bool GetStandardValuesSupported(ITypeDescriptorContext context) { return true; }
        public override bool GetStandardValuesExclusive(ITypeDescriptorContext context) { return true; }
        public override StandardValuesCollection GetStandardValues(ITypeDescriptorContext context)
        { return new StandardValuesCollection(new[] { "CHoCH", "BOS (Confirmed Trend)" }); }
    }

    #endregion

    public enum FRVPVolumeType
    {
        Standard,
        Bullish,
        Bearish,
        Both
    }

    public enum FRVPRenderQuality
    {
        Manual,
        Adaptive
    }

    public class RedTailFRVPV2 : Indicator
    {
        #region Private Classes

        private class FRVPZone
        {
            public int StartBar;
            public int EndBar;
            public double StartPrice;
            public double EndPrice;
            public double HighPrice;
            public double LowPrice;
            public int Direction;       // 1=bull, -1=bear
            public bool IsActive;
            public int AvwapAnchorBar;
            public List<double> Volumes;
            public double MaxVolume;
            public int PocIndex, VaUpIndex, VaDownIndex;
            public double ProfileLowest, ProfileInterval;
            public List<KeyValuePair<int, double>> AvwapPoints;
            public List<ClusterLevelInfo> ClusterLevels;
            public List<bool> VolumePolarities;
            public bool Dirty;
        }

        private struct ClusterLevelInfo
        {
            public double POCPrice;
            public double POCVolume;
            public double ClusterHigh;
            public double ClusterLow;
            public double TotalVolume;
            public int BarCount;
        }

        private struct FibLevel { public double Ratio; public System.Windows.Media.Brush Color; }

        #endregion

        #region Private Variables

        // Market Structure (runs silently in background)
        private double _prevHigh, _prevLow;
        private int _prevHighIndex, _prevLowIndex;
        private bool _highActive, _lowActive;
        private int _prevBreakoutDir, _prevSwingType;

        // Leg origin tracking: remembers where each directional leg started
        // For bullish breakout: saves the swing high that was broken (top of the prior bullish leg)
        // For bearish breakout: saves the swing low that was broken (bottom of the prior bearish leg)
        private double _legOriginHigh;
        private int _legOriginHighIndex;
        private double _legOriginLow;
        private int _legOriginLowIndex;

        // Trend State: 0=none, 1=bull confirmed, -1=bear confirmed
        private int _trendState;
        // Pending CHoCH: 0=none, 1=bull choch pending BOS, -1=bear choch pending BOS
        private int _pendingChoch;

        // FRVP
        private FRVPZone _activeFrvp;
        private List<FRVPZone> _historicFrvps;
        private int _lastFrvpBarCount;
        private List<FibLevel> _cachedFibLevels;

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "RedTail FRVP V2 — Volume Profile triggered by Market Structure (CHoCH / BOS)";
                Name = "RedTail FRVP";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = false;
                DrawOnPricePanel = true;
                PaintPriceMarkers = false;
                IsSuspendedWhileInactive = true;
                ZOrder = int.MinValue;

                // Market Structure (internal engine)
                SwingLength = 20;
                BOSConfirmation = "Candle Close";

                // FRVP Trigger
                FRVPTrigger = "BOS (Confirmed Trend)";
                KeepPreviousFRVP = false;

                // Volume Profile
                FRVPRows = 250; FRVPProfileWidth = 30; FRVPVPAlignment = "Left";
                FRVPBarColor = System.Windows.Media.Brushes.Gray; FRVPBarOpacity = 40; FRVPBarThickness = 2;
                FRVPVolumeType = FRVPVolumeType.Standard;
                FRVPBullishBarColor = System.Windows.Media.Brushes.Green;
                FRVPBearishBarColor = System.Windows.Media.Brushes.Red;
                FRVPEnableGradientFill = false; FRVPGradientIntensity = 70;
                FRVPRenderQuality = FRVPRenderQuality.Adaptive;
                FRVPSmoothingPasses = 2; FRVPMinBarPixelHeight = 2.0f; FRVPMaxBarPixelHeight = 8.0f;
                FRVPBoundaryColor = System.Windows.Media.Brushes.White; FRVPBoundaryOpacity = 30; FRVPBoundaryWidth = 1;
                FRVPShowLabels = true; FRVPLabelFontSize = 10; FRVPShowPrice = true;

                // POC & Value Area
                FRVPDisplayPoC = true; FRVPPoCColor = System.Windows.Media.Brushes.Red; FRVPPoCWidth = 2;
                FRVPPoCStyle = DashStyleHelper.Solid; FRVPPoCOpacity = 100; FRVPExtendPoCVA = false;
                FRVPDisplayVA = true; FRVPValueAreaPct = 68;
                FRVPVABarColor = System.Windows.Media.Brushes.RoyalBlue; FRVPDisplayVALines = true;
                FRVPVALineColor = System.Windows.Media.Brushes.Gold; FRVPVALineWidth = 1;
                FRVPVALineStyle = DashStyleHelper.Dash; FRVPVALineOpacity = 80;

                // Fibonacci
                FRVPDisplayFibs = true; FRVPFibLineWidth = 1;
                FRVPFibStyle = DashStyleHelper.Dot; FRVPFibOpacity = 80;
                FRVPExtendFibs = false; FRVPFibLabelSize = 10; FRVPFibShowPrice = true;
                FibLevel1 = 0; FibLevel1Color = System.Windows.Media.Brushes.Gray;
                FibLevel2 = 23.6; FibLevel2Color = System.Windows.Media.Brushes.DodgerBlue;
                FibLevel3 = 38.2; FibLevel3Color = System.Windows.Media.Brushes.DodgerBlue;
                FibLevel4 = 50; FibLevel4Color = System.Windows.Media.Brushes.Gold;
                FibLevel5 = 61.8; FibLevel5Color = System.Windows.Media.Brushes.Red;
                FibLevel6 = 78.6; FibLevel6Color = System.Windows.Media.Brushes.OrangeRed;
                FibLevel7 = 100; FibLevel7Color = System.Windows.Media.Brushes.Gray;
                FibLevel8 = -1; FibLevel8Color = System.Windows.Media.Brushes.Cyan;
                FibLevel9 = -1; FibLevel9Color = System.Windows.Media.Brushes.Magenta;
                FibLevel10 = -1; FibLevel10Color = System.Windows.Media.Brushes.LimeGreen;

                // AVWAP
                FRVPDisplayAVWAP = true; FRVPAVWAPColor = System.Windows.Media.Brushes.DodgerBlue;
                FRVPAVWAPWidth = 2; FRVPAVWAPStyle = DashStyleHelper.Solid;
                FRVPAVWAPOpacity = 100; FRVPExtendAVWAP = true; FRVPShowAVWAPLabel = true;

                // Cluster Levels
                FRVPDisplayClusters = false; FRVPClusterCount = 5; FRVPClusterIterations = 50;
                FRVPClusterRowsPerLevel = 20; FRVPClusterLineWidth = 2;
                FRVPClusterLineStyle = DashStyleHelper.Dash; FRVPClusterOpacity = 80;
                FRVPExtendClusters = false; FRVPShowClusterLabels = true;
                FRVPCluster1Color = System.Windows.Media.Brushes.DodgerBlue;
                FRVPCluster2Color = System.Windows.Media.Brushes.Tomato;
                FRVPCluster3Color = System.Windows.Media.Brushes.LimeGreen;
                FRVPCluster4Color = System.Windows.Media.Brushes.Orange;
                FRVPCluster5Color = System.Windows.Media.Brushes.MediumPurple;

                // Alerts
                AlertOnCHoCH = false; AlertOnBOS = false;
                AlertSoundCHoCH = "Alert1.wav"; AlertSoundBOS = "Alert2.wav";
            }
            else if (State == State.DataLoaded)
            {
                _prevHigh = double.MinValue; _prevLow = double.MaxValue;
                _prevHighIndex = 0; _prevLowIndex = 0;
                _highActive = false; _lowActive = false;
                _prevBreakoutDir = 0; _prevSwingType = 0;
                _legOriginHigh = double.MinValue; _legOriginHighIndex = 0;
                _legOriginLow = double.MaxValue; _legOriginLowIndex = 0;
                _trendState = 0; _pendingChoch = 0;
                _activeFrvp = null; _historicFrvps = new List<FRVPZone>();
                _lastFrvpBarCount = -1; _cachedFibLevels = null;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < SwingLength * 2 + 1) return;
            ProcessMarketStructure();

            // Active FRVP only needs recalc when a new bar forms
            if (_activeFrvp != null && _activeFrvp.IsActive && CurrentBar != _lastFrvpBarCount)
            {
                _activeFrvp.Dirty = true;
                _lastFrvpBarCount = CurrentBar;
            }
        }

        #region OnRender — FRVP Drawing

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            base.OnRender(chartControl, chartScale);
            if (chartControl == null || chartScale == null) return;
            var rt = RenderTarget; if (rt == null) return;
            var cp = chartControl.ChartPanels[chartScale.PanelIndex]; if (cp == null) return;
            if (chartControl.BarsArray == null || chartControl.BarsArray.Count == 0) return;
            var chartBars = chartControl.BarsArray[0];

            if (KeepPreviousFRVP)
                foreach (var z in _historicFrvps) RenderFRVPZone(z, rt, chartControl, chartScale, cp, chartBars);

            if (_activeFrvp != null && _activeFrvp.IsActive)
                RenderFRVPZone(_activeFrvp, rt, chartControl, chartScale, cp, chartBars);
        }

        private void RenderFRVPZone(FRVPZone z, SharpDX.Direct2D1.RenderTarget rt, ChartControl cc, ChartScale cs, ChartPanel cp, ChartBars chartBars)
        {
            if (z == null || chartBars == null || chartBars.Bars == null) return;

            // Recalculate if dirty
            if (z.Dirty) CalcVolumeProfile(z, chartBars.Bars);

            if (z.Volumes == null || z.Volumes.Count == 0 || z.MaxVolume <= 0) return;

            // Get pixel coords
            float xLeft, xRight;
            bool pinnedToLeft = false;
            try
            {
                xLeft = cc.GetXByBarIndex(chartBars, z.StartBar);
                xRight = z.IsActive ? (float)cp.W : cc.GetXByBarIndex(chartBars, z.EndBar);
            }
            catch { return; }
            if (xRight < xLeft) { float t = xLeft; xLeft = xRight; xRight = t; }

            // Pin profile to left edge of panel when origin bar is scrolled off-screen
            if (xLeft < 0 && z.IsActive)
            {
                pinnedToLeft = true;
                xLeft = 0;
            }

            float rangeW = Math.Max(xRight - xLeft, 5f);
            float yTop = cs.GetYByValue(z.HighPrice);
            float yBot = cs.GetYByValue(z.LowPrice);
            float profilePx = rangeW * (FRVPProfileWidth / 100f);

            // 1. Boundary (outline only — fill removed to prevent chart interaction issues)
            float bOp = FRVPBoundaryOpacity / 100f;
            var bC4 = B2C4(FRVPBoundaryColor, bOp);
            using (var bBr = new SharpDX.Direct2D1.SolidColorBrush(rt, bC4))
            {
                if (FRVPBoundaryWidth > 0)
                {
                    // Border only
                    rt.DrawRectangle(new SharpDX.RectangleF(xLeft, yTop, rangeW, yBot - yTop), bBr, FRVPBoundaryWidth);
                }
            }

            // 2. Volume Profile bars (matched to drawing tool: adaptive, gradient, polarity)
            float barOp = FRVPBarOpacity / 100f;
            bool alignLeft = (FRVPVPAlignment == "Left");
            float pLeft = alignLeft ? xLeft : xRight - profilePx;
            float pRight = alignLeft ? xLeft + profilePx : xRight;

            // Adaptive rendering: smooth volumes and auto-size bars
            bool useAdaptive = FRVPRenderQuality == FRVPRenderQuality.Adaptive;
            double[] renderVolumes = useAdaptive && FRVPSmoothingPasses > 0
                ? GetSmoothedVolumes(z.Volumes, FRVPSmoothingPasses)
                : z.Volumes.ToArray();

            // Find max of (possibly smoothed) volumes for width scaling
            double renderMaxVol = 0;
            for (int i = 0; i < renderVolumes.Length; i++)
                if (renderVolumes[i] > renderMaxVol) renderMaxVol = renderVolumes[i];
            if (renderMaxVol <= 0) renderMaxVol = z.MaxVolume;

            // Calculate adaptive bar thickness
            float adaptiveThickness = useAdaptive
                ? CalcAdaptiveBarThickness(cs, z.ProfileLowest, z.ProfileLowest + z.ProfileInterval * (z.Volumes.Count - 1), z.Volumes.Count)
                : 0;

            for (int i = 0; i < renderVolumes.Length; i++)
            {
                double vol = renderVolumes[i]; if (vol <= 0) continue;
                double price = z.ProfileLowest + z.ProfileInterval * i;
                float y = cs.GetYByValue(price);
                float barW = (float)(vol / renderMaxVol * profilePx);
                bool isPoc = (i == z.PocIndex && FRVPDisplayPoC);
                bool isVA = (FRVPDisplayVA && i >= z.VaDownIndex && i <= z.VaUpIndex);

                // Determine source color based on volume type and polarity
                System.Windows.Media.Brush sourceColor;
                if (isPoc)
                    sourceColor = FRVPPoCColor;
                else if (isVA && FRVPVolumeType == FRVPVolumeType.Standard)
                    sourceColor = FRVPVABarColor;
                else if (FRVPVolumeType == FRVPVolumeType.Standard)
                    sourceColor = FRVPBarColor;
                else
                {
                    if (FRVPVolumeType == FRVPVolumeType.Bullish)
                        sourceColor = FRVPBullishBarColor;
                    else if (FRVPVolumeType == FRVPVolumeType.Bearish)
                        sourceColor = FRVPBearishBarColor;
                    else // Both - show dominant polarity
                        sourceColor = (z.VolumePolarities != null && i < z.VolumePolarities.Count && z.VolumePolarities[i]) ? FRVPBullishBarColor : FRVPBearishBarColor;
                }

                float sourceOpacity = isPoc ? (FRVPPoCOpacity / 100f) : barOp;
                float bL = alignLeft ? pLeft : pRight - barW;
                float bR = alignLeft ? pLeft + barW : pRight;

                // Apply gradient or solid fill
                SharpDX.Direct2D1.SolidColorBrush solidBarBr = null;
                SharpDX.Direct2D1.LinearGradientBrush gradientBrush = null;
                SharpDX.Direct2D1.Brush barBrush = null;

                if (FRVPEnableGradientFill)
                {
                    gradientBrush = CreateGradientBrush(rt, sourceColor, bL, bR, y, sourceOpacity);
                    if (gradientBrush != null) barBrush = gradientBrush;
                }

                if (barBrush == null)
                {
                    solidBarBr = new SharpDX.Direct2D1.SolidColorBrush(rt, B2C4(sourceColor, sourceOpacity));
                    barBrush = solidBarBr;
                }

                float effectiveThickness;
                float gapSize;
                if (useAdaptive)
                {
                    effectiveThickness = adaptiveThickness;
                    gapSize = Math.Max(0.5f, adaptiveThickness * 0.1f);
                }
                else
                {
                    gapSize = 1.0f;
                    effectiveThickness = Math.Max(1, FRVPBarThickness - gapSize);
                }

                float adjustedY = y + (gapSize / 2.0f);
                rt.DrawLine(new SharpDX.Vector2(bL, adjustedY), new SharpDX.Vector2(bR, adjustedY), barBrush, effectiveThickness);

                gradientBrush?.Dispose();
                solidBarBr?.Dispose();
            }

            // POC line
            if (FRVPDisplayPoC && z.PocIndex >= 0 && z.PocIndex < z.Volumes.Count)
            {
                double pocP = z.ProfileLowest + z.ProfileInterval * z.PocIndex;
                float pocY = cs.GetYByValue(pocP);
                float pocXEnd = FRVPExtendPoCVA ? (float)cp.W : pRight;
                using (var br = new SharpDX.Direct2D1.SolidColorBrush(rt, B2C4(FRVPPoCColor, FRVPPoCOpacity / 100f)))
                using (var ss = MakeSS(rt, FRVPPoCStyle))
                    rt.DrawLine(new SharpDX.Vector2(xLeft, pocY), new SharpDX.Vector2(pocXEnd, pocY), br, FRVPPoCWidth, ss);
            }

            // VA lines
            if (FRVPDisplayVA && FRVPDisplayVALines)
            {
                float vaOp = FRVPVALineOpacity / 100f;
                float vaXEnd = FRVPExtendPoCVA ? (float)cp.W : pRight;
                using (var br = new SharpDX.Direct2D1.SolidColorBrush(rt, B2C4(FRVPVALineColor, vaOp)))
                using (var ss = MakeSS(rt, FRVPVALineStyle))
                {
                    if (z.VaUpIndex >= 0 && z.VaUpIndex < z.Volumes.Count)
                    { float y = cs.GetYByValue(z.ProfileLowest + z.ProfileInterval * z.VaUpIndex); rt.DrawLine(new SharpDX.Vector2(xLeft, y), new SharpDX.Vector2(vaXEnd, y), br, FRVPVALineWidth, ss); }
                    if (z.VaDownIndex >= 0 && z.VaDownIndex < z.Volumes.Count)
                    { float y = cs.GetYByValue(z.ProfileLowest + z.ProfileInterval * z.VaDownIndex); rt.DrawLine(new SharpDX.Vector2(xLeft, y), new SharpDX.Vector2(vaXEnd, y), br, FRVPVALineWidth, ss); }
                }
            }

            // Labels
            if (FRVPShowLabels)
            {
                using (var bgBr = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.05f, 0.05f, 0.1f, 0.8f)))
                using (var fmt = new SharpDX.DirectWrite.TextFormat(Core.Globals.DirectWriteFactory, "Consolas", SharpDX.DirectWrite.FontWeight.Bold, SharpDX.DirectWrite.FontStyle.Normal, (float)FRVPLabelFontSize))
                {
                    if (FRVPDisplayPoC && z.PocIndex >= 0)
                    { double p = z.ProfileLowest + z.ProfileInterval * z.PocIndex; DL(rt, fmt, bgBr, B2C4(FRVPPoCColor, FRVPPoCOpacity / 100f), FRVPShowPrice ? "POC " + p.ToString("F2") : "POC", xLeft, cs.GetYByValue(p)); }
                    if (FRVPDisplayVA && FRVPDisplayVALines && z.VaUpIndex >= 0)
                    { double p = z.ProfileLowest + z.ProfileInterval * z.VaUpIndex; DL(rt, fmt, bgBr, B2C4(FRVPVALineColor, FRVPVALineOpacity / 100f), FRVPShowPrice ? "VAH " + p.ToString("F2") : "VAH", xLeft, cs.GetYByValue(p)); }
                    if (FRVPDisplayVA && FRVPDisplayVALines && z.VaDownIndex >= 0)
                    { double p = z.ProfileLowest + z.ProfileInterval * z.VaDownIndex; DL(rt, fmt, bgBr, B2C4(FRVPVALineColor, FRVPVALineOpacity / 100f), FRVPShowPrice ? "VAL " + p.ToString("F2") : "VAL", xLeft, cs.GetYByValue(p)); }
                }
            }

            // 3. Fibs
            if (FRVPDisplayFibs)
            {
                double fibRange = z.StartPrice - z.EndPrice;
                if (Math.Abs(fibRange) > double.Epsilon)
                {
                    float fOp = FRVPFibOpacity / 100f;
                    float fxEnd = FRVPExtendFibs ? (float)cp.W : xRight;
                    using (var bgBr = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.05f, 0.05f, 0.1f, 0.8f)))
                    using (var fmt = new SharpDX.DirectWrite.TextFormat(Core.Globals.DirectWriteFactory, "Consolas", SharpDX.DirectWrite.FontWeight.Bold, SharpDX.DirectWrite.FontStyle.Normal, (float)FRVPFibLabelSize))
                    {
                        if (_cachedFibLevels == null) _cachedFibLevels = GetFibLevels();
                        foreach (var lv in _cachedFibLevels)
                        {
                            double price = z.EndPrice + fibRange * lv.Ratio;
                            float y = cs.GetYByValue(price);
                            var lc = B2C4(lv.Color, fOp);
                            using (var br = new SharpDX.Direct2D1.SolidColorBrush(rt, lc))
                            using (var ss = MakeSS(rt, FRVPFibStyle))
                                rt.DrawLine(new SharpDX.Vector2(xLeft, y), new SharpDX.Vector2(fxEnd, y), br, FRVPFibLineWidth, ss);
                            try
                            {
                                string txt = FRVPFibShowPrice ? (lv.Ratio * 100).ToString("F1") + "% [" + price.ToString("F2") + "]" : (lv.Ratio * 100).ToString("F1") + "%";
                                using (var tl = new SharpDX.DirectWrite.TextLayout(Core.Globals.DirectWriteFactory, txt, fmt, 400, 20))
                                {
                                    float tw = tl.Metrics.Width, th = tl.Metrics.Height;
                                    float lx = fxEnd - tw - 8, ly = y - th - 2;
                                    rt.FillRoundedRectangle(new SharpDX.Direct2D1.RoundedRectangle { Rect = new SharpDX.RectangleF(lx - 2, ly, tw + 8, th + 4), RadiusX = 2, RadiusY = 2 }, bgBr);
                                    using (var tb = new SharpDX.Direct2D1.SolidColorBrush(rt, lc)) rt.DrawTextLayout(new SharpDX.Vector2(lx + 2, ly + 1), tl, tb);
                                }
                            }
                            catch { }
                        }
                    }
                }
            }

            // 4. AVWAP
            if (FRVPDisplayAVWAP && z.AvwapPoints != null && z.AvwapPoints.Count >= 2)
            {
                float aOp = FRVPAVWAPOpacity / 100f;
                var oldAA = rt.AntialiasMode; rt.AntialiasMode = SharpDX.Direct2D1.AntialiasMode.PerPrimitive;
                using (var br = new SharpDX.Direct2D1.SolidColorBrush(rt, B2C4(FRVPAVWAPColor, aOp)))
                using (var ss = MakeSS(rt, FRVPAVWAPStyle))
                {
                    var pts = new List<SharpDX.Vector2>();
                    double lastVal = 0;
                    foreach (var kvp in z.AvwapPoints)
                    {
                        try
                        {
                            float bx = cc.GetXByBarIndex(chartBars, kvp.Key);
                            float by = cs.GetYByValue(kvp.Value);
                            lastVal = kvp.Value;
                            if (!FRVPExtendAVWAP && bx > xRight) break;
                            pts.Add(new SharpDX.Vector2(bx, by));
                        }
                        catch { }
                    }
                    if (pts.Count >= 2)
                    {
                        using (var path = new SharpDX.Direct2D1.PathGeometry(rt.Factory))
                        {
                            using (var sink = path.Open())
                            {
                                sink.BeginFigure(pts[0], SharpDX.Direct2D1.FigureBegin.Hollow);
                                for (int p = 1; p < pts.Count; p++) sink.AddLine(pts[p]);
                                sink.EndFigure(SharpDX.Direct2D1.FigureEnd.Open); sink.Close();
                            }
                            rt.DrawGeometry(path, br, FRVPAVWAPWidth, ss);
                        }
                        if (FRVPShowAVWAPLabel && FRVPShowLabels)
                        {
                            try
                            {
                                var lp = pts[pts.Count - 1];
                                using (var bgBr = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.05f, 0.05f, 0.1f, 0.8f)))
                                using (var fmt = new SharpDX.DirectWrite.TextFormat(Core.Globals.DirectWriteFactory, "Consolas", SharpDX.DirectWrite.FontWeight.Bold, SharpDX.DirectWrite.FontStyle.Normal, (float)FRVPLabelFontSize))
                                    DL(rt, fmt, bgBr, B2C4(FRVPAVWAPColor, aOp), FRVPShowPrice ? "AVWAP " + lastVal.ToString("F2") : "AVWAP", lp.X - 60, lp.Y);
                            }
                            catch { }
                        }
                    }
                }
                rt.AntialiasMode = oldAA;
            }

            // 5. Cluster Levels
            if (FRVPDisplayClusters && z.ClusterLevels != null && z.ClusterLevels.Count > 0)
            {
                float clOp = FRVPClusterOpacity / 100f;
                float clXEnd = FRVPExtendClusters ? (float)cp.W : xRight;
                System.Windows.Media.Brush[] clColors = { FRVPCluster1Color, FRVPCluster2Color, FRVPCluster3Color, FRVPCluster4Color, FRVPCluster5Color };

                using (var bgBr = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color4(0.05f, 0.05f, 0.1f, 0.8f)))
                using (var fmt = new SharpDX.DirectWrite.TextFormat(Core.Globals.DirectWriteFactory, "Consolas", SharpDX.DirectWrite.FontWeight.Bold, SharpDX.DirectWrite.FontStyle.Normal, (float)FRVPLabelFontSize))
                {
                    for (int ci = 0; ci < z.ClusterLevels.Count; ci++)
                    {
                        var cl = z.ClusterLevels[ci];
                        var clBrush = clColors[ci % clColors.Length];
                        var clC4 = B2C4(clBrush, clOp);
                        float y = cs.GetYByValue(cl.POCPrice);

                        using (var lineBr = new SharpDX.Direct2D1.SolidColorBrush(rt, clC4))
                        using (var ss = MakeSS(rt, FRVPClusterLineStyle))
                            rt.DrawLine(new SharpDX.Vector2(xLeft, y), new SharpDX.Vector2(clXEnd, y), lineBr, FRVPClusterLineWidth, ss);

                        if (FRVPShowClusterLabels)
                        {
                            try
                            {
                                string lbl = FRVPShowPrice ? "C" + (ci + 1) + " POC " + cl.POCPrice.ToString("F2") : "C" + (ci + 1) + " POC";
                                DL(rt, fmt, bgBr, clC4, lbl, clXEnd - 120, y);
                            }
                            catch { }
                        }
                    }
                }
            }
        }

        #endregion

        #region FRVP Calculation

        private void CalcVolumeProfile(FRVPZone z, Bars bars)
        {
            z.Dirty = false;
            z.MaxVolume = 0; z.PocIndex = -1; z.VaUpIndex = -1; z.VaDownIndex = -1;

            if (z.Volumes == null || z.Volumes.Count != FRVPRows)
            {
                z.Volumes = new List<double>(FRVPRows);
                for (int i = 0; i < FRVPRows; i++) z.Volumes.Add(0);
            }
            else
                for (int i = 0; i < FRVPRows; i++) z.Volumes[i] = 0;

            if (z.VolumePolarities == null || z.VolumePolarities.Count != FRVPRows)
            {
                z.VolumePolarities = new List<bool>(FRVPRows);
                for (int i = 0; i < FRVPRows; i++) z.VolumePolarities.Add(true);
            }
            else
                for (int i = 0; i < FRVPRows; i++) z.VolumePolarities[i] = true;

            double[] bullishVolume = new double[FRVPRows];
            double[] bearishVolume = new double[FRVPRows];

            if (z.AvwapPoints == null) z.AvwapPoints = new List<KeyValuePair<int, double>>(256);
            else z.AvwapPoints.Clear();

            z.HighPrice = double.MinValue; z.LowPrice = double.MaxValue;

            int sb = z.StartBar, eb = z.IsActive ? bars.Count - 1 : z.EndBar;
            int sIdx = -1, eIdx = -1;

            for (int i = sb; i <= eb && i < bars.Count; i++)
            {
                if (sIdx == -1) sIdx = i; eIdx = i;
                z.HighPrice = Math.Max(z.HighPrice, bars.GetHigh(i));
                z.LowPrice = Math.Min(z.LowPrice, bars.GetLow(i));
            }
            if (sIdx == -1 || z.HighPrice <= z.LowPrice) return;

            if (z.IsActive)
            {
                if (z.Direction == 1) { z.StartPrice = z.LowPrice; z.EndPrice = z.HighPrice; }
                else                  { z.StartPrice = z.HighPrice; z.EndPrice = z.LowPrice; }
            }

            z.ProfileLowest = z.LowPrice;
            z.ProfileInterval = (z.HighPrice - z.LowPrice) / (FRVPRows - 1);
            if (z.ProfileInterval <= 0) return;

            for (int i = sIdx; i <= eIdx; i++)
            {
                double lo = bars.GetLow(i), hi = bars.GetHigh(i), vol = bars.GetVolume(i);
                double op = bars.GetOpen(i), cl = bars.GetClose(i);
                bool isBullish = cl >= op;
                int minI = Math.Max(0, Math.Min((int)Math.Floor((lo - z.ProfileLowest) / z.ProfileInterval), FRVPRows - 1));
                int maxI = Math.Max(0, Math.Min((int)Math.Ceiling((hi - z.ProfileLowest) / z.ProfileInterval), FRVPRows - 1));
                int touched = maxI - minI + 1;
                if (touched > 0)
                {
                    double vpl = vol / touched;
                    bool includeVol = FRVPVolumeType == FRVPVolumeType.Standard ||
                                     FRVPVolumeType == FRVPVolumeType.Both ||
                                     (FRVPVolumeType == FRVPVolumeType.Bullish && isBullish) ||
                                     (FRVPVolumeType == FRVPVolumeType.Bearish && !isBullish);
                    if (includeVol)
                    {
                        for (int j = minI; j <= maxI; j++)
                        {
                            z.Volumes[j] += vpl;
                            if (isBullish) bullishVolume[j] += vpl;
                            else bearishVolume[j] += vpl;
                        }
                    }
                }
            }

            // Set polarity for each row
            for (int i = 0; i < FRVPRows; i++)
                z.VolumePolarities[i] = bullishVolume[i] >= bearishVolume[i];

            z.PocIndex = 0;
            for (int i = 0; i < FRVPRows; i++) if (z.Volumes[i] > z.MaxVolume) { z.MaxVolume = z.Volumes[i]; z.PocIndex = i; }

            // Value Area
            z.VaUpIndex = z.PocIndex; z.VaDownIndex = z.PocIndex;
            double sumVol = 0; for (int i = 0; i < z.Volumes.Count; i++) sumVol += z.Volumes[i];
            double vaTarget = sumVol * FRVPValueAreaPct / 100.0;
            double vaSum = z.MaxVolume;
            while (vaSum < vaTarget)
            {
                double vUp = (z.VaUpIndex < FRVPRows - 1) ? z.Volumes[z.VaUpIndex + 1] : 0;
                double vDn = (z.VaDownIndex > 0) ? z.Volumes[z.VaDownIndex - 1] : 0;
                if (vUp == 0 && vDn == 0) break;
                if (vUp >= vDn) { vaSum += vUp; z.VaUpIndex++; } else { vaSum += vDn; z.VaDownIndex--; }
            }

            // AVWAP
            if (FRVPDisplayAVWAP)
            {
                int avwapStart = Math.Max(z.AvwapAnchorBar, sIdx);
                double cumVol = 0, cumTV = 0;
                for (int i = avwapStart; i < bars.Count; i++)
                {
                    double vol = bars.GetVolume(i);
                    double src = (bars.GetOpen(i) + bars.GetHigh(i) + bars.GetLow(i) + bars.GetClose(i)) / 4.0;
                    cumVol += vol; cumTV += src * vol;
                    if (cumVol > 0) z.AvwapPoints.Add(new KeyValuePair<int, double>(i, cumTV / cumVol));
                }
            }

            // Cluster Levels (K-Means)
            if (FRVPDisplayClusters)
                CalcClusterLevels(z, bars, sIdx, eIdx);
        }

        private void CalcClusterLevels(FRVPZone z, Bars bars, int sIdx, int eIdx)
        {
            if (z.ClusterLevels == null) z.ClusterLevels = new List<ClusterLevelInfo>();
            else z.ClusterLevels.Clear();

            var prices = new List<double>();
            var volList = new List<double>();
            var highList = new List<double>();
            var lowList = new List<double>();

            for (int i = sIdx; i <= eIdx; i++)
            {
                double h = bars.GetHigh(i), l = bars.GetLow(i), v = bars.GetVolume(i);
                prices.Add((h + l) / 2.0); volList.Add(v); highList.Add(h); lowList.Add(l);
            }

            int n = prices.Count;
            if (n < 2) return;

            int k = Math.Min(FRVPClusterCount, n);
            double minP = double.MaxValue, maxP = double.MinValue;
            for (int i = 0; i < n; i++) { if (prices[i] < minP) minP = prices[i]; if (prices[i] > maxP) maxP = prices[i]; }
            if (maxP <= minP) return;

            double[] cents = new double[k];
            double step = (maxP - minP) / (k + 1);
            for (int i = 0; i < k; i++) cents[i] = minP + (i + 1) * step;

            int[] assign = new int[n];
            for (int iter = 0; iter < FRVPClusterIterations; iter++)
            {
                for (int i = 0; i < n; i++)
                {
                    int bestK = 0; double minDist = double.MaxValue;
                    for (int j = 0; j < k; j++) { double dist = Math.Abs(prices[i] - cents[j]); if (dist < minDist) { minDist = dist; bestK = j; } }
                    assign[i] = bestK;
                }
                double[] sumPV = new double[k]; double[] sumV = new double[k];
                for (int i = 0; i < n; i++) { int c = assign[i]; sumPV[c] += prices[i] * volList[i]; sumV[c] += volList[i]; }
                for (int j = 0; j < k; j++) { if (sumV[j] > 0) cents[j] = sumPV[j] / sumV[j]; }
            }

            int rows = FRVPClusterRowsPerLevel;
            for (int cId = 0; cId < k; cId++)
            {
                double cMin = double.MaxValue, cMax = double.MinValue;
                double cTotalVol = 0; int cBarCount = 0;
                var cHighs = new List<double>(); var cLows = new List<double>(); var cVols = new List<double>();

                for (int i = 0; i < n; i++)
                {
                    if (assign[i] != cId) continue;
                    cHighs.Add(highList[i]); cLows.Add(lowList[i]); cVols.Add(volList[i]);
                    if (lowList[i] < cMin) cMin = lowList[i]; if (highList[i] > cMax) cMax = highList[i];
                    cTotalVol += volList[i]; cBarCount++;
                }
                if (cBarCount == 0 || cMax <= cMin) continue;

                double binSize = (cMax - cMin) / rows; if (binSize <= 0) continue;
                double[] binVols = new double[rows];
                for (int i = 0; i < cHighs.Count; i++)
                {
                    double bH = cHighs[i], bL = cLows[i], bV = cVols[i];
                    double wickRange = Math.Max(bH - bL, z.ProfileInterval > 0 ? z.ProfileInterval : 0.01);
                    for (int bIdx = 0; bIdx < rows; bIdx++)
                    {
                        double binBot = cMin + bIdx * binSize, binTop = binBot + binSize;
                        double intersectL = Math.Max(bL, binBot), intersectH = Math.Min(bH, binTop);
                        if (intersectH > intersectL) binVols[bIdx] += bV * (intersectH - intersectL) / wickRange;
                    }
                }

                double maxBinVol = 0; int pocIdx = 0;
                for (int bIdx = 0; bIdx < rows; bIdx++) { if (binVols[bIdx] > maxBinVol) { maxBinVol = binVols[bIdx]; pocIdx = bIdx; } }
                double pocPrice = cMin + pocIdx * binSize + binSize / 2.0;

                z.ClusterLevels.Add(new ClusterLevelInfo { POCPrice = pocPrice, POCVolume = maxBinVol, ClusterHigh = cMax, ClusterLow = cMin, TotalVolume = cTotalVol, BarCount = cBarCount });
            }
            z.ClusterLevels.Sort((a, b) => a.POCPrice.CompareTo(b.POCPrice));
        }

        private void CreateFRVPZone(int direction)
        {
            if (!KeepPreviousFRVP && _activeFrvp != null)
                _activeFrvp.IsActive = false;
            else if (KeepPreviousFRVP && _activeFrvp != null)
            {
                _activeFrvp.IsActive = false;
                _activeFrvp.EndBar = CurrentBar;
                _historicFrvps.Add(_activeFrvp);
            }

            int startB, avwapBar;
            double startP, endP;

            if (direction == 1)
            {
                // Bullish zone: need the absolute low of the entire bearish leg
                // Scan from the leg origin high (top of the move) down to _prevLowIndex
                // to find the true absolute bottom
                int scanFrom = _legOriginHighIndex;
                int scanTo = Math.Min(CurrentBar, _prevLowIndex + SwingLength);
                if (scanFrom > scanTo) { int tmp = scanFrom; scanFrom = tmp; scanTo = _prevLowIndex + SwingLength; scanFrom = Math.Max(0, _legOriginHighIndex); }

                double absLow = _prevLow;
                int absLowBar = _prevLowIndex;
                for (int i = scanFrom; i <= scanTo; i++)
                {
                    int barsAgo = CurrentBar - i;
                    if (barsAgo < 0 || barsAgo >= Count) continue;
                    double lo = Low[barsAgo];
                    if (lo < absLow)
                    {
                        absLow = lo;
                        absLowBar = i;
                    }
                }

                startB = absLowBar;
                avwapBar = absLowBar;
                startP = absLow;
                // Use the leg origin high as the top of the range
                endP = _legOriginHigh != double.MinValue ? _legOriginHigh : _prevHigh;
            }
            else
            {
                // Bearish zone: need the absolute high of the entire bullish leg
                int scanFrom = _legOriginLowIndex;
                int scanTo = Math.Min(CurrentBar, _prevHighIndex + SwingLength);
                if (scanFrom > scanTo) { scanFrom = Math.Max(0, _legOriginLowIndex); }

                double absHigh = _prevHigh;
                int absHighBar = _prevHighIndex;
                for (int i = scanFrom; i <= scanTo; i++)
                {
                    int barsAgo = CurrentBar - i;
                    if (barsAgo < 0 || barsAgo >= Count) continue;
                    double hi = High[barsAgo];
                    if (hi > absHigh)
                    {
                        absHigh = hi;
                        absHighBar = i;
                    }
                }

                startB = absHighBar;
                avwapBar = absHighBar;
                startP = absHigh;
                endP = _legOriginLow != double.MaxValue ? _legOriginLow : _prevLow;
            }

            _activeFrvp = new FRVPZone
            {
                StartBar = startB, EndBar = CurrentBar,
                StartPrice = startP, EndPrice = endP,
                Direction = direction, IsActive = true,
                AvwapAnchorBar = avwapBar, Dirty = true
            };
        }

        private List<FibLevel> GetFibLevels()
        {
            var list = new List<FibLevel>();
            double[] vals = { FibLevel1, FibLevel2, FibLevel3, FibLevel4, FibLevel5, FibLevel6, FibLevel7, FibLevel8, FibLevel9, FibLevel10 };
            System.Windows.Media.Brush[] cols = { FibLevel1Color, FibLevel2Color, FibLevel3Color, FibLevel4Color, FibLevel5Color, FibLevel6Color, FibLevel7Color, FibLevel8Color, FibLevel9Color, FibLevel10Color };
            for (int i = 0; i < 10; i++) if (vals[i] >= 0) list.Add(new FibLevel { Ratio = vals[i] / 100.0, Color = cols[i] ?? System.Windows.Media.Brushes.DodgerBlue });
            return list;
        }

        #endregion

        #region Market Structure (Silent — No Drawing)

        private void ProcessMarketStructure()
        {
            int len = SwingLength;
            double cH = High[len]; bool isPH = true;
            for (int i = 0; i <= len * 2; i++) { if (i == len) continue; if (High[i] > cH) { isPH = false; break; } }
            double cL = Low[len]; bool isPL = true;
            for (int i = 0; i <= len * 2; i++) { if (i == len) continue; if (Low[i] < cL) { isPL = false; break; } }

            int psb = _prevSwingType;
            if (isPH)
            {
                bool isHH = (cH >= _prevHigh); _prevSwingType = isHH ? 2 : 1;
                _prevHigh = cH; _prevHighIndex = CurrentBar - len; _highActive = true;
            }
            if (isPL)
            {
                bool isHL = (cL >= _prevLow); _prevSwingType = isHL ? -1 : -2;
                _prevLow = cL; _prevLowIndex = CurrentBar - len; _lowActive = true;
            }

            double hSrc = (BOSConfirmation == "Candle Close") ? Close[0] : High[0];
            double lSrc = (BOSConfirmation == "Candle Close") ? Close[0] : Low[0];

            // Bullish breakout
            if (hSrc > _prevHigh && _highActive && _prevHigh != double.MinValue)
            {
                _highActive = false;
                bool choch = (_prevBreakoutDir == -1);

                // When direction changes bear->bull, save the current low as the leg origin
                // This is the low that the bearish leg established before the reversal
                if (choch)
                {
                    _legOriginLow = _prevLow;
                    _legOriginLowIndex = _prevLowIndex;
                    _legOriginHigh = _prevHigh;
                    _legOriginHighIndex = _prevHighIndex;
                }

                if (choch && FRVPTrigger == "CHoCH") CreateFRVPZone(1);

                // Trend state tracking
                if (choch)
                    _pendingChoch = 1;
                else
                {
                    if (_pendingChoch == 1)
                    {
                        bool trendActuallyChanged = (_trendState != 1);
                        _trendState = 1;
                        _pendingChoch = 0;
                        if (trendActuallyChanged && FRVPTrigger == "BOS (Confirmed Trend)") CreateFRVPZone(1);
                    }
                    else if (_trendState == 1)
                        _pendingChoch = 0;
                }

                // Alerts
                if (State == State.Realtime)
                {
                    if (choch && AlertOnCHoCH) Alert("RTFRVP_CHoCH", Priority.High, "Bullish CHoCH at " + _prevHigh.ToString("F2"), NinjaTrader.Core.Globals.InstallDir + @"\sounds\" + AlertSoundCHoCH, 10, System.Windows.Media.Brushes.Transparent, System.Windows.Media.Brushes.Lime);
                    else if (!choch && AlertOnBOS) Alert("RTFRVP_BOS", Priority.Medium, "Bullish BOS at " + _prevHigh.ToString("F2"), NinjaTrader.Core.Globals.InstallDir + @"\sounds\" + AlertSoundBOS, 10, System.Windows.Media.Brushes.Transparent, System.Windows.Media.Brushes.DodgerBlue);
                }
                _prevBreakoutDir = 1;
            }

            // Bearish breakout
            if (lSrc < _prevLow && _lowActive && _prevLow != double.MaxValue)
            {
                _lowActive = false;
                bool choch = (_prevBreakoutDir == 1);

                // When direction changes bull->bear, save the current high as the leg origin
                if (choch)
                {
                    _legOriginHigh = _prevHigh;
                    _legOriginHighIndex = _prevHighIndex;
                    _legOriginLow = _prevLow;
                    _legOriginLowIndex = _prevLowIndex;
                }

                if (choch && FRVPTrigger == "CHoCH") CreateFRVPZone(-1);

                // Trend state tracking
                if (choch)
                    _pendingChoch = -1;
                else
                {
                    if (_pendingChoch == -1)
                    {
                        bool trendActuallyChanged = (_trendState != -1);
                        _trendState = -1;
                        _pendingChoch = 0;
                        if (trendActuallyChanged && FRVPTrigger == "BOS (Confirmed Trend)") CreateFRVPZone(-1);
                    }
                    else if (_trendState == -1)
                        _pendingChoch = 0;
                }

                // Alerts
                if (State == State.Realtime)
                {
                    if (choch && AlertOnCHoCH) Alert("RTFRVP_CHoCH", Priority.High, "Bearish CHoCH at " + _prevLow.ToString("F2"), NinjaTrader.Core.Globals.InstallDir + @"\sounds\" + AlertSoundCHoCH, 10, System.Windows.Media.Brushes.Transparent, System.Windows.Media.Brushes.OrangeRed);
                    else if (!choch && AlertOnBOS) Alert("RTFRVP_BOS", Priority.Medium, "Bearish BOS at " + _prevLow.ToString("F2"), NinjaTrader.Core.Globals.InstallDir + @"\sounds\" + AlertSoundBOS, 10, System.Windows.Media.Brushes.Transparent, System.Windows.Media.Brushes.DodgerBlue);
                }
                _prevBreakoutDir = -1;
            }
        }

        #endregion

        #region Helpers

        private double[] GetSmoothedVolumes(List<double> rawVolumes, int passes)
        {
            if (rawVolumes == null || rawVolumes.Count == 0) return new double[0];
            double[] current = rawVolumes.ToArray();
            double[] buffer = new double[current.Length];
            for (int pass = 0; pass < passes; pass++)
            {
                for (int i = 0; i < current.Length; i++)
                {
                    double sum = current[i] * 4.0; double weightSum = 4.0;
                    if (i - 1 >= 0) { sum += current[i - 1] * 2.0; weightSum += 2.0; }
                    if (i + 1 < current.Length) { sum += current[i + 1] * 2.0; weightSum += 2.0; }
                    if (i - 2 >= 0) { sum += current[i - 2] * 1.0; weightSum += 1.0; }
                    if (i + 2 < current.Length) { sum += current[i + 2] * 1.0; weightSum += 1.0; }
                    buffer[i] = sum / weightSum;
                }
                double[] temp = current; current = buffer; buffer = temp;
            }
            return current;
        }

        private float CalcAdaptiveBarThickness(ChartScale cs, double lowPrice, double highPrice, int rowCount)
        {
            float lowY = cs.GetYByValue(lowPrice);
            float highY = cs.GetYByValue(highPrice);
            float totalPixelHeight = Math.Abs(lowY - highY);
            float pixelsPerRow = totalPixelHeight / Math.Max(1, rowCount);
            float idealThickness = pixelsPerRow * 0.85f;
            return Math.Max(FRVPMinBarPixelHeight, Math.Min(idealThickness, FRVPMaxBarPixelHeight));
        }

        private SharpDX.Direct2D1.LinearGradientBrush CreateGradientBrush(SharpDX.Direct2D1.RenderTarget rt, System.Windows.Media.Brush baseColor, float startX, float endX, float y, float baseOpacity)
        {
            if (!FRVPEnableGradientFill || FRVPGradientIntensity <= 0) return null;
            try
            {
                System.Windows.Media.Color mediaColor;
                if (baseColor is System.Windows.Media.SolidColorBrush solidBrush) mediaColor = solidBrush.Color;
                else mediaColor = System.Windows.Media.Colors.Gray;
                float intensityFactor = FRVPGradientIntensity / 100.0f;
                float startOpacity = baseOpacity * (1.0f - intensityFactor);
                float endOpacity = baseOpacity;
                var gradientStops = new SharpDX.Direct2D1.GradientStop[2];
                gradientStops[0] = new SharpDX.Direct2D1.GradientStop { Position = 0.0f, Color = new SharpDX.Color4(mediaColor.R / 255f, mediaColor.G / 255f, mediaColor.B / 255f, startOpacity) };
                gradientStops[1] = new SharpDX.Direct2D1.GradientStop { Position = 1.0f, Color = new SharpDX.Color4(mediaColor.R / 255f, mediaColor.G / 255f, mediaColor.B / 255f, endOpacity) };
                var gsc = new SharpDX.Direct2D1.GradientStopCollection(rt, gradientStops);
                var gb = new SharpDX.Direct2D1.LinearGradientBrush(rt, new SharpDX.Direct2D1.LinearGradientBrushProperties { StartPoint = new SharpDX.Vector2(startX, y), EndPoint = new SharpDX.Vector2(endX, y) }, gsc);
                gsc.Dispose();
                return gb;
            }
            catch { return null; }
        }

        private SharpDX.Color4 B2C4(System.Windows.Media.Brush b, float op) { if (b is System.Windows.Media.SolidColorBrush s) { var c = s.Color; return new SharpDX.Color4(c.R / 255f, c.G / 255f, c.B / 255f, op); } return new SharpDX.Color4(1, 1, 1, op); }
        private SharpDX.Direct2D1.StrokeStyle MakeSS(SharpDX.Direct2D1.RenderTarget rt, DashStyleHelper ds)
        {
            float[] d; switch (ds) { case DashStyleHelper.Dash: d = new[] { 4f, 3f }; break; case DashStyleHelper.Dot: d = new[] { 0.5f, 2f }; break; case DashStyleHelper.DashDot: d = new[] { 4f, 2f, 0.5f, 2f }; break; default: return new SharpDX.Direct2D1.StrokeStyle(rt.Factory, new SharpDX.Direct2D1.StrokeStyleProperties { DashStyle = SharpDX.Direct2D1.DashStyle.Solid }); }
            return new SharpDX.Direct2D1.StrokeStyle(rt.Factory, new SharpDX.Direct2D1.StrokeStyleProperties { DashStyle = SharpDX.Direct2D1.DashStyle.Custom, DashCap = SharpDX.Direct2D1.CapStyle.Round, StartCap = SharpDX.Direct2D1.CapStyle.Round, EndCap = SharpDX.Direct2D1.CapStyle.Round }, d);
        }
        private void DL(SharpDX.Direct2D1.RenderTarget rt, SharpDX.DirectWrite.TextFormat fmt, SharpDX.Direct2D1.SolidColorBrush bg, SharpDX.Color4 tc, string txt, float x, float y)
        { try { using (var tl = new SharpDX.DirectWrite.TextLayout(Core.Globals.DirectWriteFactory, txt, fmt, 400, 20)) { float tw = tl.Metrics.Width, th = tl.Metrics.Height; rt.FillRoundedRectangle(new SharpDX.Direct2D1.RoundedRectangle { Rect = new SharpDX.RectangleF(x + 2, y - th - 2, tw + 8, th + 4), RadiusX = 2, RadiusY = 2 }, bg); using (var tb = new SharpDX.Direct2D1.SolidColorBrush(rt, tc)) rt.DrawTextLayout(new SharpDX.Vector2(x + 6, y - th - 1), tl, tb); } } catch { } }

        #endregion

        #region Properties

        // ══════════════════════════════════════════════════════════════
        // 1. MARKET STRUCTURE (Internal Engine)
        // ══════════════════════════════════════════════════════════════

        [NinjaScriptProperty][Range(3, 100)]
        [Display(Name = "Swing Length", Order = 1, GroupName = "01. Market Structure")]
        public int SwingLength { get; set; }

        [NinjaScriptProperty][TypeConverter(typeof(FRVPBOSConfirmationConverter))]
        [Display(Name = "BOS Confirmation", Order = 2, GroupName = "01. Market Structure")]
        public string BOSConfirmation { get; set; }

        // ══════════════════════════════════════════════════════════════
        // 2. FRVP TRIGGER
        // ══════════════════════════════════════════════════════════════

        [NinjaScriptProperty][TypeConverter(typeof(FRVPTriggerTypeConverter))]
        [Display(Name = "FRVP Trigger", Description = "Draw on CHoCH immediately, or wait for confirming BOS", Order = 1, GroupName = "02. FRVP Trigger")]
        public string FRVPTrigger { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Keep Previous FRVP", Order = 2, GroupName = "02. FRVP Trigger")]
        public bool KeepPreviousFRVP { get; set; }

        // ══════════════════════════════════════════════════════════════
        // 3. VOLUME PROFILE
        // ══════════════════════════════════════════════════════════════

        [NinjaScriptProperty][Range(50, 500)]
        [Display(Name = "Number of Rows", Order = 1, GroupName = "03. Volume Profile")]
        public int FRVPRows { get; set; }

        [NinjaScriptProperty][Range(5, 80)]
        [Display(Name = "Profile Width %", Order = 2, GroupName = "03. Volume Profile")]
        public int FRVPProfileWidth { get; set; }

        [NinjaScriptProperty][TypeConverter(typeof(FRVPVPAlignmentConverter))]
        [Display(Name = "VP Alignment", Order = 3, GroupName = "03. Volume Profile")]
        public string FRVPVPAlignment { get; set; }

        [XmlIgnore]
        [Display(Name = "Bar Color", Order = 4, GroupName = "03. Volume Profile")]
        public System.Windows.Media.Brush FRVPBarColor { get; set; }
        [Browsable(false)] public string FRVPBarColorS { get { return Serialize.BrushToString(FRVPBarColor); } set { FRVPBarColor = Serialize.StringToBrush(value); } }

        [Display(Name = "Bar Opacity %", Order = 5, GroupName = "03. Volume Profile")][Range(10, 100)]
        public int FRVPBarOpacity { get; set; }

        [Display(Name = "Bar Thickness", Order = 6, GroupName = "03. Volume Profile")][Range(1, 10)]
        public int FRVPBarThickness { get; set; }

        [Display(Name = "Volume Type", Description = "Standard, Bullish, Bearish, or Both (polarity coloring)", Order = 7, GroupName = "03. Volume Profile")]
        public FRVPVolumeType FRVPVolumeType { get; set; }

        [XmlIgnore]
        [Display(Name = "Bullish Bar Color", Order = 8, GroupName = "03. Volume Profile")]
        public System.Windows.Media.Brush FRVPBullishBarColor { get; set; }
        [Browsable(false)] public string FRVPBullishBarColorS { get { return Serialize.BrushToString(FRVPBullishBarColor); } set { FRVPBullishBarColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "Bearish Bar Color", Order = 9, GroupName = "03. Volume Profile")]
        public System.Windows.Media.Brush FRVPBearishBarColor { get; set; }
        [Browsable(false)] public string FRVPBearishBarColorS { get { return Serialize.BrushToString(FRVPBearishBarColor); } set { FRVPBearishBarColor = Serialize.StringToBrush(value); } }

        // ══════════════════════════════════════════════════════════════
        // 3b. GRADIENT FILL
        // ══════════════════════════════════════════════════════════════

        [Display(Name = "Enable Gradient Fill", Description = "Apply gradient effect to volume bars (fade from transparent to solid)", Order = 1, GroupName = "03b. Gradient Fill")]
        public bool FRVPEnableGradientFill { get; set; }

        [Display(Name = "Gradient Intensity", Description = "0=no fade (solid), 100=maximum fade effect", Order = 2, GroupName = "03b. Gradient Fill")][Range(0, 100)]
        public int FRVPGradientIntensity { get; set; }

        // ══════════════════════════════════════════════════════════════
        // 3c. ADAPTIVE RENDERING
        // ══════════════════════════════════════════════════════════════

        [Display(Name = "Render Quality", Description = "Manual = fixed bar thickness. Adaptive = auto-sizes bars and smooths profile shape.", Order = 1, GroupName = "03c. Adaptive Rendering")]
        public FRVPRenderQuality FRVPRenderQuality { get; set; }

        [Display(Name = "Smoothing Passes", Description = "Gaussian smoothing passes (0=raw, 2-3=recommended, 5=very smooth)", Order = 2, GroupName = "03c. Adaptive Rendering")][Range(0, 5)]
        public int FRVPSmoothingPasses { get; set; }

        [Display(Name = "Min Bar Pixel Height", Description = "Minimum bar height in pixels (prevents bars from disappearing)", Order = 3, GroupName = "03c. Adaptive Rendering")][Range(1.0f, 10.0f)]
        public float FRVPMinBarPixelHeight { get; set; }

        [Display(Name = "Max Bar Pixel Height", Description = "Maximum bar height in pixels (prevents bars from getting too thick)", Order = 4, GroupName = "03c. Adaptive Rendering")][Range(2.0f, 20.0f)]
        public float FRVPMaxBarPixelHeight { get; set; }

        [XmlIgnore]
        [Display(Name = "Boundary Color", Order = 7, GroupName = "03. Volume Profile")]
        public System.Windows.Media.Brush FRVPBoundaryColor { get; set; }
        [Browsable(false)] public string FRVPBoundaryColorS { get { return Serialize.BrushToString(FRVPBoundaryColor); } set { FRVPBoundaryColor = Serialize.StringToBrush(value); } }

        [Display(Name = "Boundary Opacity %", Order = 8, GroupName = "03. Volume Profile")][Range(0, 100)]
        public int FRVPBoundaryOpacity { get; set; }

        [Display(Name = "Boundary Width", Order = 9, GroupName = "03. Volume Profile")][Range(0, 5)]
        public int FRVPBoundaryWidth { get; set; }

        [Display(Name = "Show Labels (POC/VA)", Order = 10, GroupName = "03. Volume Profile")]
        public bool FRVPShowLabels { get; set; }

        [Display(Name = "Label Font Size", Order = 11, GroupName = "03. Volume Profile")][Range(8, 20)]
        public int FRVPLabelFontSize { get; set; }

        [Display(Name = "Show Price on Labels", Order = 12, GroupName = "03. Volume Profile")]
        public bool FRVPShowPrice { get; set; }

        // ══════════════════════════════════════════════════════════════
        // 4. POC & VALUE AREA
        // ══════════════════════════════════════════════════════════════

        [Display(Name = "Display POC", Order = 1, GroupName = "04. POC & Value Area")]
        public bool FRVPDisplayPoC { get; set; }

        [XmlIgnore]
        [Display(Name = "POC Color", Order = 2, GroupName = "04. POC & Value Area")]
        public System.Windows.Media.Brush FRVPPoCColor { get; set; }
        [Browsable(false)] public string FRVPPoCColorS { get { return Serialize.BrushToString(FRVPPoCColor); } set { FRVPPoCColor = Serialize.StringToBrush(value); } }

        [Display(Name = "POC Width", Order = 3, GroupName = "04. POC & Value Area")][Range(1, 5)]
        public int FRVPPoCWidth { get; set; }

        [Display(Name = "POC Style", Order = 4, GroupName = "04. POC & Value Area")]
        public DashStyleHelper FRVPPoCStyle { get; set; }

        [Display(Name = "POC Opacity %", Order = 5, GroupName = "04. POC & Value Area")][Range(10, 100)]
        public int FRVPPoCOpacity { get; set; }

        [Display(Name = "Display Value Area", Order = 6, GroupName = "04. POC & Value Area")]
        public bool FRVPDisplayVA { get; set; }

        [Display(Name = "Value Area %", Order = 7, GroupName = "04. POC & Value Area")][Range(50, 95)]
        public int FRVPValueAreaPct { get; set; }

        [XmlIgnore]
        [Display(Name = "VA Bar Color", Order = 8, GroupName = "04. POC & Value Area")]
        public System.Windows.Media.Brush FRVPVABarColor { get; set; }
        [Browsable(false)] public string FRVPVABarColorS { get { return Serialize.BrushToString(FRVPVABarColor); } set { FRVPVABarColor = Serialize.StringToBrush(value); } }

        [Display(Name = "Display VA Lines", Order = 9, GroupName = "04. POC & Value Area")]
        public bool FRVPDisplayVALines { get; set; }

        [XmlIgnore]
        [Display(Name = "VA Line Color", Order = 10, GroupName = "04. POC & Value Area")]
        public System.Windows.Media.Brush FRVPVALineColor { get; set; }
        [Browsable(false)] public string FRVPVALineColorS { get { return Serialize.BrushToString(FRVPVALineColor); } set { FRVPVALineColor = Serialize.StringToBrush(value); } }

        [Display(Name = "VA Line Width", Order = 11, GroupName = "04. POC & Value Area")][Range(1, 5)]
        public int FRVPVALineWidth { get; set; }

        [Display(Name = "VA Line Style", Order = 12, GroupName = "04. POC & Value Area")]
        public DashStyleHelper FRVPVALineStyle { get; set; }

        [Display(Name = "VA Line Opacity %", Order = 13, GroupName = "04. POC & Value Area")][Range(10, 100)]
        public int FRVPVALineOpacity { get; set; }

        [Display(Name = "Extend POC/VA Right", Description = "Extend POC and VA lines beyond the FRVP zone to chart edge", Order = 14, GroupName = "04. POC & Value Area")]
        public bool FRVPExtendPoCVA { get; set; }

        // ══════════════════════════════════════════════════════════════
        // 5. FIBONACCI
        // ══════════════════════════════════════════════════════════════

        [Display(Name = "Display Fibs", Order = 1, GroupName = "05. Fibonacci")]
        public bool FRVPDisplayFibs { get; set; }

        [Display(Name = "Fib Line Width", Order = 2, GroupName = "05. Fibonacci")][Range(1, 5)]
        public int FRVPFibLineWidth { get; set; }

        [Display(Name = "Fib Style", Order = 3, GroupName = "05. Fibonacci")]
        public DashStyleHelper FRVPFibStyle { get; set; }

        [Display(Name = "Fib Opacity %", Order = 4, GroupName = "05. Fibonacci")][Range(10, 100)]
        public int FRVPFibOpacity { get; set; }

        [Display(Name = "Extend Fibs Right", Order = 5, GroupName = "05. Fibonacci")]
        public bool FRVPExtendFibs { get; set; }

        [Display(Name = "Fib Label Size", Order = 6, GroupName = "05. Fibonacci")][Range(8, 20)]
        public int FRVPFibLabelSize { get; set; }

        [Display(Name = "Show Fib Price", Order = 7, GroupName = "05. Fibonacci")]
        public bool FRVPFibShowPrice { get; set; }

        // ══════════════════════════════════════════════════════════════
        // 6. FIB LEVELS
        // ══════════════════════════════════════════════════════════════

        [Display(Name = "Level 1 (%)", Description = "-1 to disable", Order = 1, GroupName = "06. Fib Levels")]
        public double FibLevel1 { get; set; }
        [XmlIgnore][Display(Name = "Level 1 Color", Order = 2, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel1Color { get; set; }
        [Browsable(false)] public string FL1CS { get { return Serialize.BrushToString(FibLevel1Color); } set { FibLevel1Color = Serialize.StringToBrush(value); } }

        [Display(Name = "Level 2 (%)", Order = 3, GroupName = "06. Fib Levels")]
        public double FibLevel2 { get; set; }
        [XmlIgnore][Display(Name = "Level 2 Color", Order = 4, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel2Color { get; set; }
        [Browsable(false)] public string FL2CS { get { return Serialize.BrushToString(FibLevel2Color); } set { FibLevel2Color = Serialize.StringToBrush(value); } }

        [Display(Name = "Level 3 (%)", Order = 5, GroupName = "06. Fib Levels")]
        public double FibLevel3 { get; set; }
        [XmlIgnore][Display(Name = "Level 3 Color", Order = 6, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel3Color { get; set; }
        [Browsable(false)] public string FL3CS { get { return Serialize.BrushToString(FibLevel3Color); } set { FibLevel3Color = Serialize.StringToBrush(value); } }

        [Display(Name = "Level 4 (%)", Order = 7, GroupName = "06. Fib Levels")]
        public double FibLevel4 { get; set; }
        [XmlIgnore][Display(Name = "Level 4 Color", Order = 8, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel4Color { get; set; }
        [Browsable(false)] public string FL4CS { get { return Serialize.BrushToString(FibLevel4Color); } set { FibLevel4Color = Serialize.StringToBrush(value); } }

        [Display(Name = "Level 5 (%)", Order = 9, GroupName = "06. Fib Levels")]
        public double FibLevel5 { get; set; }
        [XmlIgnore][Display(Name = "Level 5 Color", Order = 10, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel5Color { get; set; }
        [Browsable(false)] public string FL5CS { get { return Serialize.BrushToString(FibLevel5Color); } set { FibLevel5Color = Serialize.StringToBrush(value); } }

        [Display(Name = "Level 6 (%)", Order = 11, GroupName = "06. Fib Levels")]
        public double FibLevel6 { get; set; }
        [XmlIgnore][Display(Name = "Level 6 Color", Order = 12, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel6Color { get; set; }
        [Browsable(false)] public string FL6CS { get { return Serialize.BrushToString(FibLevel6Color); } set { FibLevel6Color = Serialize.StringToBrush(value); } }

        [Display(Name = "Level 7 (%)", Order = 13, GroupName = "06. Fib Levels")]
        public double FibLevel7 { get; set; }
        [XmlIgnore][Display(Name = "Level 7 Color", Order = 14, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel7Color { get; set; }
        [Browsable(false)] public string FL7CS { get { return Serialize.BrushToString(FibLevel7Color); } set { FibLevel7Color = Serialize.StringToBrush(value); } }

        [Display(Name = "Level 8 (%)", Order = 15, GroupName = "06. Fib Levels")]
        public double FibLevel8 { get; set; }
        [XmlIgnore][Display(Name = "Level 8 Color", Order = 16, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel8Color { get; set; }
        [Browsable(false)] public string FL8CS { get { return Serialize.BrushToString(FibLevel8Color); } set { FibLevel8Color = Serialize.StringToBrush(value); } }

        [Display(Name = "Level 9 (%)", Order = 17, GroupName = "06. Fib Levels")]
        public double FibLevel9 { get; set; }
        [XmlIgnore][Display(Name = "Level 9 Color", Order = 18, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel9Color { get; set; }
        [Browsable(false)] public string FL9CS { get { return Serialize.BrushToString(FibLevel9Color); } set { FibLevel9Color = Serialize.StringToBrush(value); } }

        [Display(Name = "Level 10 (%)", Order = 19, GroupName = "06. Fib Levels")]
        public double FibLevel10 { get; set; }
        [XmlIgnore][Display(Name = "Level 10 Color", Order = 20, GroupName = "06. Fib Levels")]
        public System.Windows.Media.Brush FibLevel10Color { get; set; }
        [Browsable(false)] public string FL10CS { get { return Serialize.BrushToString(FibLevel10Color); } set { FibLevel10Color = Serialize.StringToBrush(value); } }

        // ══════════════════════════════════════════════════════════════
        // 7. AVWAP
        // ══════════════════════════════════════════════════════════════

        [Display(Name = "Display AVWAP", Order = 1, GroupName = "07. AVWAP")]
        public bool FRVPDisplayAVWAP { get; set; }

        [XmlIgnore]
        [Display(Name = "AVWAP Color", Order = 2, GroupName = "07. AVWAP")]
        public System.Windows.Media.Brush FRVPAVWAPColor { get; set; }
        [Browsable(false)] public string FRVPAVWAPColorS { get { return Serialize.BrushToString(FRVPAVWAPColor); } set { FRVPAVWAPColor = Serialize.StringToBrush(value); } }

        [Display(Name = "AVWAP Width", Order = 3, GroupName = "07. AVWAP")][Range(1, 5)]
        public int FRVPAVWAPWidth { get; set; }

        [Display(Name = "AVWAP Style", Order = 4, GroupName = "07. AVWAP")]
        public DashStyleHelper FRVPAVWAPStyle { get; set; }

        [Display(Name = "AVWAP Opacity %", Order = 5, GroupName = "07. AVWAP")][Range(10, 100)]
        public int FRVPAVWAPOpacity { get; set; }

        [Display(Name = "Extend AVWAP Right", Order = 6, GroupName = "07. AVWAP")]
        public bool FRVPExtendAVWAP { get; set; }

        [Display(Name = "Show AVWAP Label", Order = 7, GroupName = "07. AVWAP")]
        public bool FRVPShowAVWAPLabel { get; set; }

        // ══════════════════════════════════════════════════════════════
        // 8. CLUSTER LEVELS
        // ══════════════════════════════════════════════════════════════

        [Display(Name = "Display Cluster Levels", Order = 1, GroupName = "08. Cluster Levels")]
        public bool FRVPDisplayClusters { get; set; }

        [Display(Name = "Number of Clusters", Description = "K-Means cluster count", Order = 2, GroupName = "08. Cluster Levels")][Range(2, 10)]
        public int FRVPClusterCount { get; set; }

        [Display(Name = "K-Means Iterations", Order = 3, GroupName = "08. Cluster Levels")][Range(5, 50)]
        public int FRVPClusterIterations { get; set; }

        [Display(Name = "Rows per Cluster", Description = "VP resolution per cluster for POC detection", Order = 4, GroupName = "08. Cluster Levels")][Range(5, 100)]
        public int FRVPClusterRowsPerLevel { get; set; }

        [Display(Name = "Line Width", Order = 5, GroupName = "08. Cluster Levels")][Range(1, 5)]
        public int FRVPClusterLineWidth { get; set; }

        [Display(Name = "Line Style", Order = 6, GroupName = "08. Cluster Levels")]
        public DashStyleHelper FRVPClusterLineStyle { get; set; }

        [Display(Name = "Opacity %", Order = 7, GroupName = "08. Cluster Levels")][Range(10, 100)]
        public int FRVPClusterOpacity { get; set; }

        [Display(Name = "Extend Right", Order = 8, GroupName = "08. Cluster Levels")]
        public bool FRVPExtendClusters { get; set; }

        [Display(Name = "Show Labels", Order = 9, GroupName = "08. Cluster Levels")]
        public bool FRVPShowClusterLabels { get; set; }

        // ══════════════════════════════════════════════════════════════
        // 9. CLUSTER COLORS
        // ══════════════════════════════════════════════════════════════

        [XmlIgnore][Display(Name = "Cluster 1 Color", Order = 1, GroupName = "09. Cluster Colors")]
        public System.Windows.Media.Brush FRVPCluster1Color { get; set; }
        [Browsable(false)] public string FRVPCluster1ColorS { get { return Serialize.BrushToString(FRVPCluster1Color); } set { FRVPCluster1Color = Serialize.StringToBrush(value); } }

        [XmlIgnore][Display(Name = "Cluster 2 Color", Order = 2, GroupName = "09. Cluster Colors")]
        public System.Windows.Media.Brush FRVPCluster2Color { get; set; }
        [Browsable(false)] public string FRVPCluster2ColorS { get { return Serialize.BrushToString(FRVPCluster2Color); } set { FRVPCluster2Color = Serialize.StringToBrush(value); } }

        [XmlIgnore][Display(Name = "Cluster 3 Color", Order = 3, GroupName = "09. Cluster Colors")]
        public System.Windows.Media.Brush FRVPCluster3Color { get; set; }
        [Browsable(false)] public string FRVPCluster3ColorS { get { return Serialize.BrushToString(FRVPCluster3Color); } set { FRVPCluster3Color = Serialize.StringToBrush(value); } }

        [XmlIgnore][Display(Name = "Cluster 4 Color", Order = 4, GroupName = "09. Cluster Colors")]
        public System.Windows.Media.Brush FRVPCluster4Color { get; set; }
        [Browsable(false)] public string FRVPCluster4ColorS { get { return Serialize.BrushToString(FRVPCluster4Color); } set { FRVPCluster4Color = Serialize.StringToBrush(value); } }

        [XmlIgnore][Display(Name = "Cluster 5 Color", Order = 5, GroupName = "09. Cluster Colors")]
        public System.Windows.Media.Brush FRVPCluster5Color { get; set; }
        [Browsable(false)] public string FRVPCluster5ColorS { get { return Serialize.BrushToString(FRVPCluster5Color); } set { FRVPCluster5Color = Serialize.StringToBrush(value); } }

        // ══════════════════════════════════════════════════════════════
        // 10. ALERTS
        // ══════════════════════════════════════════════════════════════

        [Display(Name = "Alert on BOS", Order = 1, GroupName = "10. Alerts")]
        public bool AlertOnBOS { get; set; }

        [Display(Name = "Alert on CHoCH", Order = 2, GroupName = "10. Alerts")]
        public bool AlertOnCHoCH { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "BOS Sound File", Description = "WAV file name in NinjaTrader sounds folder", Order = 3, GroupName = "10. Alerts")]
        public string AlertSoundBOS { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "CHoCH Sound File", Description = "WAV file name in NinjaTrader sounds folder", Order = 4, GroupName = "10. Alerts")]
        public string AlertSoundCHoCH { get; set; }

        #endregion
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private RedTailFRVPV2[] cacheRedTailFRVPV2;
		public RedTailFRVPV2 RedTailFRVPV2(int swingLength, string bOSConfirmation, string fRVPTrigger, bool keepPreviousFRVP, int fRVPRows, int fRVPProfileWidth, string fRVPVPAlignment, string alertSoundBOS, string alertSoundCHoCH)
		{
			return RedTailFRVPV2(Input, swingLength, bOSConfirmation, fRVPTrigger, keepPreviousFRVP, fRVPRows, fRVPProfileWidth, fRVPVPAlignment, alertSoundBOS, alertSoundCHoCH);
		}

		public RedTailFRVPV2 RedTailFRVPV2(ISeries<double> input, int swingLength, string bOSConfirmation, string fRVPTrigger, bool keepPreviousFRVP, int fRVPRows, int fRVPProfileWidth, string fRVPVPAlignment, string alertSoundBOS, string alertSoundCHoCH)
		{
			if (cacheRedTailFRVPV2 != null)
				for (int idx = 0; idx < cacheRedTailFRVPV2.Length; idx++)
					if (cacheRedTailFRVPV2[idx] != null && cacheRedTailFRVPV2[idx].SwingLength == swingLength && cacheRedTailFRVPV2[idx].BOSConfirmation == bOSConfirmation && cacheRedTailFRVPV2[idx].FRVPTrigger == fRVPTrigger && cacheRedTailFRVPV2[idx].KeepPreviousFRVP == keepPreviousFRVP && cacheRedTailFRVPV2[idx].FRVPRows == fRVPRows && cacheRedTailFRVPV2[idx].FRVPProfileWidth == fRVPProfileWidth && cacheRedTailFRVPV2[idx].FRVPVPAlignment == fRVPVPAlignment && cacheRedTailFRVPV2[idx].AlertSoundBOS == alertSoundBOS && cacheRedTailFRVPV2[idx].AlertSoundCHoCH == alertSoundCHoCH && cacheRedTailFRVPV2[idx].EqualsInput(input))
						return cacheRedTailFRVPV2[idx];
			return CacheIndicator<RedTailFRVPV2>(new RedTailFRVPV2(){ SwingLength = swingLength, BOSConfirmation = bOSConfirmation, FRVPTrigger = fRVPTrigger, KeepPreviousFRVP = keepPreviousFRVP, FRVPRows = fRVPRows, FRVPProfileWidth = fRVPProfileWidth, FRVPVPAlignment = fRVPVPAlignment, AlertSoundBOS = alertSoundBOS, AlertSoundCHoCH = alertSoundCHoCH }, input, ref cacheRedTailFRVPV2);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.RedTailFRVPV2 RedTailFRVPV2(int swingLength, string bOSConfirmation, string fRVPTrigger, bool keepPreviousFRVP, int fRVPRows, int fRVPProfileWidth, string fRVPVPAlignment, string alertSoundBOS, string alertSoundCHoCH)
		{
			return indicator.RedTailFRVPV2(Input, swingLength, bOSConfirmation, fRVPTrigger, keepPreviousFRVP, fRVPRows, fRVPProfileWidth, fRVPVPAlignment, alertSoundBOS, alertSoundCHoCH);
		}

		public Indicators.RedTailFRVPV2 RedTailFRVPV2(ISeries<double> input , int swingLength, string bOSConfirmation, string fRVPTrigger, bool keepPreviousFRVP, int fRVPRows, int fRVPProfileWidth, string fRVPVPAlignment, string alertSoundBOS, string alertSoundCHoCH)
		{
			return indicator.RedTailFRVPV2(input, swingLength, bOSConfirmation, fRVPTrigger, keepPreviousFRVP, fRVPRows, fRVPProfileWidth, fRVPVPAlignment, alertSoundBOS, alertSoundCHoCH);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.RedTailFRVPV2 RedTailFRVPV2(int swingLength, string bOSConfirmation, string fRVPTrigger, bool keepPreviousFRVP, int fRVPRows, int fRVPProfileWidth, string fRVPVPAlignment, string alertSoundBOS, string alertSoundCHoCH)
		{
			return indicator.RedTailFRVPV2(Input, swingLength, bOSConfirmation, fRVPTrigger, keepPreviousFRVP, fRVPRows, fRVPProfileWidth, fRVPVPAlignment, alertSoundBOS, alertSoundCHoCH);
		}

		public Indicators.RedTailFRVPV2 RedTailFRVPV2(ISeries<double> input , int swingLength, string bOSConfirmation, string fRVPTrigger, bool keepPreviousFRVP, int fRVPRows, int fRVPProfileWidth, string fRVPVPAlignment, string alertSoundBOS, string alertSoundCHoCH)
		{
			return indicator.RedTailFRVPV2(input, swingLength, bOSConfirmation, fRVPTrigger, keepPreviousFRVP, fRVPRows, fRVPProfileWidth, fRVPVPAlignment, alertSoundBOS, alertSoundCHoCH);
		}
	}
}

#endregion
