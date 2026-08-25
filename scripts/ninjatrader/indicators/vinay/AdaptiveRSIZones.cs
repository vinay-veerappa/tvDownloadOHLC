#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
using SharpDX;
using MediaColor = System.Windows.Media.Color;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    public enum AdaptiveRsiPlotType
    {
        Line,
        Bar,
        Candle,
        HeikinAshi
    }

    public enum AdaptiveRsiSourceInput
    {
        Close,
        HLC2,
        HLC3,
        OHLC4
    }

    public enum AdaptiveRsiMaType
    {
        None,
        SMA,
        SMA_BollingerBands,
        EMA,
        SMMA,
        WMA,
        VWMA
    }

    /// <summary>
    /// Adaptive RSI zones indicator for NinjaTrader 8.
    /// Ported from the TradingView Pine Script "RSI adaptive zones [AdaptiveRSI]".
    /// Original work © AdaptiveRSI, licensed under CC BY-NC-SA 4.0.
    /// </summary>
    public class AdaptiveRSIZones : Indicator
    {
        #region Parameters

        [NinjaScriptProperty]
        [Range(2, 100)]
        [Display(Name = "Length", Order = 1, GroupName = "1. RSI Settings")]
        public int Length { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Plot RSI As", Order = 2, GroupName = "1. RSI Settings")]
        public AdaptiveRsiPlotType RsiPlotType { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "RSI Color", Order = 3, GroupName = "1. RSI Settings")]
        public Brush RsiColorBrush { get; set; }

        [Browsable(false)]
        public string RsiColorBrushSerializable
        {
            get { return Serialize.BrushToString(RsiColorBrush); }
            set { RsiColorBrush = Serialize.StringToBrush(value); }
        }

        [NinjaScriptProperty]
        [Display(Name = "Show Support / Resistance Zones", Order = 1, GroupName = "2. Visibility and Colors")]
        public bool ShowSupRes { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "Support/Resistance Color", Order = 2, GroupName = "2. Visibility and Colors")]
        public Brush SupResColorBrush { get; set; }

        [Browsable(false)]
        public string SupResColorBrushSerializable
        {
            get { return Serialize.BrushToString(SupResColorBrush); }
            set { SupResColorBrush = Serialize.StringToBrush(value); }
        }

        [NinjaScriptProperty]
        [Display(Name = "Show Overbought / Oversold Zones", Order = 3, GroupName = "2. Visibility and Colors")]
        public bool ShowOO { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "Overbought Color", Order = 4, GroupName = "2. Visibility and Colors")]
        public Brush OverboughtColorBrush { get; set; }

        [Browsable(false)]
        public string OverboughtColorBrushSerializable
        {
            get { return Serialize.BrushToString(OverboughtColorBrush); }
            set { OverboughtColorBrush = Serialize.StringToBrush(value); }
        }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "Oversold Color", Order = 5, GroupName = "2. Visibility and Colors")]
        public Brush OversoldColorBrush { get; set; }

        [Browsable(false)]
        public string OversoldColorBrushSerializable
        {
            get { return Serialize.BrushToString(OversoldColorBrush); }
            set { OversoldColorBrush = Serialize.StringToBrush(value); }
        }

        [NinjaScriptProperty]
        [Display(Name = "OB/OS Candle Coloring", Order = 6, GroupName = "2. Visibility and Colors")]
        public bool OOColoring { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "OB Intense Color", Order = 7, GroupName = "2. Visibility and Colors")]
        public Brush ObIntenseColorBrush { get; set; }

        [Browsable(false)]
        public string ObIntenseColorBrushSerializable
        {
            get { return Serialize.BrushToString(ObIntenseColorBrush); }
            set { ObIntenseColorBrush = Serialize.StringToBrush(value); }
        }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "OS Intense Color", Order = 8, GroupName = "2. Visibility and Colors")]
        public Brush OsIntenseColorBrush { get; set; }

        [Browsable(false)]
        public string OsIntenseColorBrushSerializable
        {
            get { return Serialize.BrushToString(OsIntenseColorBrush); }
            set { OsIntenseColorBrush = Serialize.StringToBrush(value); }
        }

        [NinjaScriptProperty]
        [Display(Name = "Show Zone Values on Scale", Order = 9, GroupName = "2. Visibility and Colors")]
        public bool ShowZoneValues { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "RSI Input", Order = 1, GroupName = "3. RSI Smoothing")]
        public AdaptiveRsiSourceInput SmoothingSource { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "MA Type", Order = 2, GroupName = "3. RSI Smoothing")]
        public AdaptiveRsiMaType MaType { get; set; }

        [NinjaScriptProperty]
        [Range(1, 200)]
        [Display(Name = "MA Length", Order = 3, GroupName = "3. RSI Smoothing")]
        public int MaLength { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "MA Color", Order = 4, GroupName = "3. RSI Smoothing")]
        public Brush MaColorBrush { get; set; }

        [Browsable(false)]
        public string MaColorBrushSerializable
        {
            get { return Serialize.BrushToString(MaColorBrush); }
            set { MaColorBrush = Serialize.StringToBrush(value); }
        }

        [NinjaScriptProperty]
        [Range(0, 10)]
        [Display(Name = "BB StdDev Multiplier", Order = 5, GroupName = "3. RSI Smoothing")]
        public double BbMultiplier { get; set; }

        [NinjaScriptProperty]
        [XmlIgnore]
        [Display(Name = "BB Color", Order = 6, GroupName = "3. RSI Smoothing")]
        public Brush BbColorBrush { get; set; }

        [Browsable(false)]
        public string BbColorBrushSerializable
        {
            get { return Serialize.BrushToString(BbColorBrush); }
            set { BbColorBrush = Serialize.StringToBrush(value); }
        }

        [NinjaScriptProperty]
        [Display(Name = "Show MA/BB Values on Scale", Order = 7, GroupName = "3. RSI Smoothing")]
        public bool ShowMaValues { get; set; }

        #endregion

        #region Exported Series
        // These public Series<double> values and threshold doubles are available
        // to NinjaScript strategies via:
        //   var rsi = AdaptiveRSIZones();
        //   double val = rsi.RsiClose[0];
        //   bool ob   = rsi.RsiClose[0] > rsi.OverboughtThreshold;

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> RsiClose { get; private set; }

        /// <summary>Alias for RsiClose; the close-based adaptive RSI value.</summary>
        [Browsable(false)]
        [XmlIgnore]
        public Series<double> RsiValue { get { return RsiClose; } }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> RsiOpen { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> RsiHigh { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> RsiLow { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> HaRsiClose { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> HaRsiOpen { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> HaRsiHigh { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> HaRsiLow { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> LogitMa { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> BbUpper { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> BbLower { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public double OverboughtThreshold { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public double OversoldThreshold { get; private set; }

        #endregion

        #region Internal Series

        private Series<double> middle;
        private Series<double> ccVol;
        private Series<double> logitRsiClose;
        private Series<double> logitRsiOpen;
        private Series<double> logitRsiHigh;
        private Series<double> logitRsiLow;
        private Series<double> logitHaOpen;
        private Series<double> logitHaClose;
        private Series<double> logitSource;
        private Series<double> rawMa;
        private Series<double> rawStdDev;

        private Series<double> zoneR1;
        private Series<double> zoneR2;
        private Series<double> zoneS1;
        private Series<double> zoneS2;
        private Series<double> zoneObTop;
        private Series<double> zoneObBot;
        private Series<double> zoneOsTop;
        private Series<double> zoneOsBot;

        private string lastRenderError;

        private const double HalfRange = 50.0;
        private const double Eps = 1e-10;

        private static Brush FreezeBrush(MediaColor color)
        {
            var brush = new System.Windows.Media.SolidColorBrush(color);
            if (brush.CanFreeze)
                brush.Freeze();
            return brush;
        }

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Adaptive RSI zones with logit-based smoothing, support/resistance bands, and overbought/oversold shading. Ported from AdaptiveRSI (CC BY-NC-SA 4.0).";
                Name = "AdaptiveRSIZones";
                Calculate = Calculate.OnBarClose;
                IsOverlay = false;
                DrawOnPricePanel = false;
                DisplayInDataBox = true;
                IsSuspendedWhileInactive = true;
                ScaleJustification = ScaleJustification.Right;

                Length = 14;
                BarsRequiredToPlot = 14;
                RsiPlotType = AdaptiveRsiPlotType.Candle;
                RsiColorBrush = Brushes.DodgerBlue;

                ShowSupRes = true;
                SupResColorBrush = Brushes.Gray;
                ShowOO = true;
                OverboughtColorBrush = FreezeBrush(MediaColor.FromRgb(0x33, 0xA6, 0x45));
                OversoldColorBrush = FreezeBrush(MediaColor.FromRgb(0xD9, 0x23, 0x23));
                OOColoring = true;
                ObIntenseColorBrush = FreezeBrush(MediaColor.FromRgb(0xF2, 0x27, 0x38));
                OsIntenseColorBrush = FreezeBrush(MediaColor.FromRgb(0x33, 0xE6, 0x43));
                ShowZoneValues = false;

                SmoothingSource = AdaptiveRsiSourceInput.Close;
                MaType = AdaptiveRsiMaType.VWMA;
                MaLength = 21;
                MaColorBrush = FreezeBrush(MediaColor.FromRgb(0xF2, 0xBD, 0x1D));
                BbMultiplier = 2.0;
                BbColorBrush = FreezeBrush(MediaColor.FromRgb(0xF2, 0x74, 0x05));
                ShowMaValues = true;

                AddPlot(new Stroke(RsiColorBrush, 2), PlotStyle.Line, "RsiLine");
                AddPlot(new Stroke(RsiColorBrush, 1), PlotStyle.Line, "AutoScaleLow");
                AddPlot(new Stroke(MaColorBrush, 2), PlotStyle.Line, "LogitMa");
                AddPlot(new Stroke(BbColorBrush, 1), PlotStyle.Line, "BbUpper");
                AddPlot(new Stroke(BbColorBrush, 1), PlotStyle.Line, "BbLower");
                AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dash, 1), PlotStyle.Line, "Middle50");

                AddPlot(new Stroke(SupResColorBrush, 1), PlotStyle.Line, "ResistanceTop");
                AddPlot(new Stroke(SupResColorBrush, 1), PlotStyle.Line, "ResistanceBot");
                AddPlot(new Stroke(SupResColorBrush, 1), PlotStyle.Line, "SupportTop");
                AddPlot(new Stroke(SupResColorBrush, 1), PlotStyle.Line, "SupportBot");

                AddPlot(new Stroke(OverboughtColorBrush, 1), PlotStyle.Line, "OverboughtTop");
                AddPlot(new Stroke(OverboughtColorBrush, 1), PlotStyle.Line, "OverboughtBot");
                AddPlot(new Stroke(OversoldColorBrush, 1), PlotStyle.Line, "OversoldTop");
                AddPlot(new Stroke(OversoldColorBrush, 1), PlotStyle.Line, "OversoldBot");

            }
            else if (State == State.DataLoaded)
            {
                middle = new Series<double>(this, MaximumBarsLookBack.Infinite);
                ccVol = new Series<double>(this, MaximumBarsLookBack.Infinite);

                RsiClose = new Series<double>(this, MaximumBarsLookBack.Infinite);
                RsiOpen = new Series<double>(this, MaximumBarsLookBack.Infinite);
                RsiHigh = new Series<double>(this, MaximumBarsLookBack.Infinite);
                RsiLow = new Series<double>(this, MaximumBarsLookBack.Infinite);

                logitRsiClose = new Series<double>(this, MaximumBarsLookBack.Infinite);
                logitRsiOpen = new Series<double>(this, MaximumBarsLookBack.Infinite);
                logitRsiHigh = new Series<double>(this, MaximumBarsLookBack.Infinite);
                logitRsiLow = new Series<double>(this, MaximumBarsLookBack.Infinite);

                logitHaOpen = new Series<double>(this, MaximumBarsLookBack.Infinite);
                logitHaClose = new Series<double>(this, MaximumBarsLookBack.Infinite);
                HaRsiClose = new Series<double>(this, MaximumBarsLookBack.Infinite);
                HaRsiOpen = new Series<double>(this, MaximumBarsLookBack.Infinite);
                HaRsiHigh = new Series<double>(this, MaximumBarsLookBack.Infinite);
                HaRsiLow = new Series<double>(this, MaximumBarsLookBack.Infinite);

                logitSource = new Series<double>(this, MaximumBarsLookBack.Infinite);
                rawMa = new Series<double>(this, MaximumBarsLookBack.Infinite);
                rawStdDev = new Series<double>(this, MaximumBarsLookBack.Infinite);
                LogitMa = new Series<double>(this, MaximumBarsLookBack.Infinite);
                BbUpper = new Series<double>(this, MaximumBarsLookBack.Infinite);
                BbLower = new Series<double>(this, MaximumBarsLookBack.Infinite);

                zoneR1 = new Series<double>(this, MaximumBarsLookBack.Infinite);
                zoneR2 = new Series<double>(this, MaximumBarsLookBack.Infinite);
                zoneS1 = new Series<double>(this, MaximumBarsLookBack.Infinite);
                zoneS2 = new Series<double>(this, MaximumBarsLookBack.Infinite);
                zoneObTop = new Series<double>(this, MaximumBarsLookBack.Infinite);
                zoneObBot = new Series<double>(this, MaximumBarsLookBack.Infinite);
                zoneOsTop = new Series<double>(this, MaximumBarsLookBack.Infinite);
                zoneOsBot = new Series<double>(this, MaximumBarsLookBack.Infinite);
            }
            else if (State == State.Terminated)
            {
                // No unmanaged resources to dispose
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar == 0)
            {
                middle[0] = Close[0];
                ccVol[0] = 0.0;
            }
            else
            {
                double sf = 1.0 / Length;
                middle[0] = (1.0 - sf) * middle[1] + sf * Close[0];
                ccVol[0] = (1.0 - sf) * ccVol[1] + sf * Math.Abs(Close[0] - Close[1]);
            }

            double middleO, middleH, middleL;
            double ccVolO, ccVolH, ccVolL;

            if (CurrentBar == 0)
            {
                // No prior bar available; neutralize the O/H/L RSI components so we do not
                // access an invalid series index and the Wilder warmup stays stable.
                middleO  = Open[0];
                middleH  = High[0];
                middleL  = Low[0];
                ccVolO   = 0.0;
                ccVolH   = 0.0;
                ccVolL   = 0.0;
            }
            else
            {
                double sfLocal = 1.0 / Length;
                middleO = (1.0 - sfLocal) * middle[1] + sfLocal * Open[0];
                middleH = (1.0 - sfLocal) * middle[1] + sfLocal * High[0];
                middleL = (1.0 - sfLocal) * middle[1] + sfLocal * Low[0];

                ccVolO  = (1.0 - sfLocal) * ccVol[1] + sfLocal * Math.Abs(Open[0]  - Close[1]);
                ccVolH  = (1.0 - sfLocal) * ccVol[1] + sfLocal * Math.Abs(High[0]  - Close[1]);
                ccVolL  = (1.0 - sfLocal) * ccVol[1] + sfLocal * Math.Abs(Low[0]   - Close[1]);
            }

            double denC = Math.Max(ccVol[0], Eps) * (Length - 1.0);
            double denO = Math.Max(ccVolO, Eps) * (Length - 1.0);
            double denH = Math.Max(ccVolH, Eps) * (Length - 1.0);
            double denL = Math.Max(ccVolL, Eps) * (Length - 1.0);

            double myRsi = HalfRange + HalfRange * ((Close[0] - middle[0]) / denC);
            double rsiO = HalfRange + HalfRange * ((Open[0] - middleO) / denO);
            double rsiH = HalfRange + HalfRange * ((High[0] - middleH) / denH);
            double rsiL = HalfRange + HalfRange * ((Low[0] - middleL) / denL);

            RsiClose[0] = myRsi;
            RsiOpen[0] = rsiO;
            RsiHigh[0] = rsiH;
            RsiLow[0] = rsiL;

            logitRsiClose[0] = Logit(myRsi);
            logitRsiOpen[0] = Logit(rsiO);
            logitRsiHigh[0] = Logit(rsiH);
            logitRsiLow[0] = Logit(rsiL);

            double logitHaC = (logitRsiOpen[0] + logitRsiHigh[0] + logitRsiLow[0] + logitRsiClose[0]) / 4.0;
            logitHaClose[0] = logitHaC;

            double logitHaO;
            if (CurrentBar == 0 || double.IsNaN(logitHaOpen[1]))
                logitHaO = (logitRsiOpen[0] + logitRsiClose[0]) / 2.0;
            else
                logitHaO = (logitHaOpen[1] + logitHaClose[1]) / 2.0;
            logitHaOpen[0] = logitHaO;

            double logitHaH = Math.Max(logitRsiHigh[0], Math.Max(logitHaOpen[0], logitHaC));
            double logitHaL = Math.Min(logitRsiLow[0], Math.Min(logitHaOpen[0], logitHaC));

            HaRsiClose[0] = Logistic(logitHaC);
            HaRsiOpen[0] = Logistic(logitHaOpen[0]);
            HaRsiHigh[0] = Logistic(logitHaH);
            HaRsiLow[0] = Logistic(logitHaL);

            double src;
            switch (SmoothingSource)
            {
                case AdaptiveRsiSourceInput.Close:
                    src = logitRsiClose[0];
                    break;
                case AdaptiveRsiSourceInput.HLC2:
                    src = (logitRsiHigh[0] + logitRsiLow[0]) / 2.0;
                    break;
                case AdaptiveRsiSourceInput.HLC3:
                    src = (logitRsiHigh[0] + logitRsiLow[0] + logitRsiClose[0]) / 3.0;
                    break;
                case AdaptiveRsiSourceInput.OHLC4:
                    src = (logitRsiHigh[0] + logitRsiLow[0] + logitRsiClose[0] + logitRsiClose[0]) / 4.0;
                    break;
                default:
                    src = logitRsiClose[0];
                    break;
            }
            logitSource[0] = src;

            bool enableMa = MaType != AdaptiveRsiMaType.None;
            bool isBB = MaType == AdaptiveRsiMaType.SMA_BollingerBands;

            double ma = double.NaN;
            if (enableMa)
            {
                ma = ComputeMa(logitSource, MaLength, MaType);
                rawMa[0] = ma;
            }
            else
            {
                rawMa[0] = double.NaN;
            }

            if (isBB)
            {
                rawStdDev[0] = ComputeStdDev(logitSource, rawMa, MaLength);
            }
            else
            {
                rawStdDev[0] = double.NaN;
            }

            LogitMa[0] = enableMa ? Logistic(ma) : double.NaN;
            BbUpper[0] = isBB ? Logistic(ma + BbMultiplier * rawStdDev[0]) : double.NaN;
            BbLower[0] = isBB ? Logistic(ma - BbMultiplier * rawStdDev[0]) : double.NaN;

            // Zone thresholds
            double bodyThreshold = Math.Sqrt((5.0 - Math.Sqrt(17.0)) / 2.0);
            double tailThreshold = Math.Sqrt((5.0 + Math.Sqrt(17.0)) / 2.0);
            double breakoutThreshold = 1.0;
            double reversalThreshold = Math.Sqrt(3.0);
            double invSqrtLenm1 = 1.0 / Math.Pow(Length - 1.0, 0.5);

            double zIns = RsiDistance(bodyThreshold, invSqrtLenm1);
            double zOut = RsiDistance(breakoutThreshold, invSqrtLenm1);
            double ooIns = RsiDistance(reversalThreshold, invSqrtLenm1);
            double ooOut = RsiDistance(tailThreshold, invSqrtLenm1);

            zoneR1[0] = 50.0 + zOut;
            zoneR2[0] = 50.0 + zIns;
            zoneS1[0] = 50.0 - zIns;
            zoneS2[0] = 50.0 - zOut;
            zoneObTop[0] = 50.0 + ooOut;
            zoneObBot[0] = 50.0 + ooIns;
            zoneOsTop[0] = 50.0 - ooIns;
            zoneOsBot[0] = 50.0 - ooOut;

            OverboughtThreshold = 50.0 + ooIns;
            OversoldThreshold = 50.0 - ooIns;

            bool isObLine = myRsi > OverboughtThreshold;
            bool isOsLine = myRsi < OversoldThreshold;
            bool isObOhlc = CurrentBar >= Length && rsiH > 50.0 + ooIns;
            bool isOsOhlc = CurrentBar >= Length && rsiL < 50.0 - ooIns;

            // Main plots - keep hidden until enough bars are available so the
            // Wilder-style warmup does not blow up the panel scale.
            bool ready = CurrentBar >= Length;

            Values[5][0] = 50.0;


            Values[2][0] = ready && MaType != AdaptiveRsiMaType.None ? LogitMa[0] : double.NaN;
            Values[3][0] = ready && MaType == AdaptiveRsiMaType.SMA_BollingerBands ? BbUpper[0] : double.NaN;
            Values[4][0] = ready && MaType == AdaptiveRsiMaType.SMA_BollingerBands ? BbLower[0] : double.NaN;

            // Zone boundary plots
            Values[6][0] = ready && ShowZoneValues ? zoneR1[0] : double.NaN;
            Values[7][0] = ready && ShowZoneValues ? zoneR2[0] : double.NaN;
            Values[8][0] = ready && ShowZoneValues ? zoneS1[0] : double.NaN;
            Values[9][0] = ready && ShowZoneValues ? zoneS2[0] : double.NaN;
            Values[10][0] = ready && ShowZoneValues ? zoneObTop[0] : double.NaN;
            Values[11][0] = ready && ShowZoneValues ? zoneObBot[0] : double.NaN;
            Values[12][0] = ready && ShowZoneValues ? zoneOsTop[0] : double.NaN;
            Values[13][0] = ready && ShowZoneValues ? zoneOsBot[0] : double.NaN;

            // Feed the visible RSI line plot so it also anchors the panel scale.
            if (ready && RsiPlotType == AdaptiveRsiPlotType.Line)
            {
                Values[0][0] = myRsi;
            }
            else
            {
                Values[0].Reset(0);
            }

            // Keep a live low anchor so the scale does not collapse when zones are hidden.
            Values[1][0] = ready ? RsiLow[0] : double.NaN;

            if (!string.IsNullOrEmpty(lastRenderError))
                Draw.TextFixed(this, "ARZErr", $"Render: {lastRenderError}", TextPosition.TopLeft);
        }


        #region Math Helpers

        private static double Logit(double x)
        {
            double clamped = Math.Min(Math.Max(x, Eps), 100.0 - Eps);
            return Math.Log(clamped / (100.0 - clamped));
        }

        private static double Logistic(double x)
        {
            double e = Math.Exp(x);
            return 100.0 * e / (1.0 + e);
        }

        private static double Tanh(double x)
        {
            double e = Math.Exp(2.0 * x);
            return (e - 1.0) / (e + 1.0);
        }

        private static double RsiDistance(double z, double invSqrtLenm1)
        {
            return HalfRange * Tanh(z * invSqrtLenm1);
        }

        private double ComputeMa(Series<double> source, int length, AdaptiveRsiMaType type)
        {
            if (CurrentBar < length - 1)
                return source[0];

            switch (type)
            {
                case AdaptiveRsiMaType.SMA:
                case AdaptiveRsiMaType.SMA_BollingerBands:
                    {
                        double sum = 0.0;
                        for (int i = 0; i < length; i++)
                            sum += source[i];
                        return sum / length;
                    }
                case AdaptiveRsiMaType.EMA:
                    {
                        double alpha = 2.0 / (length + 1.0);
                        if (CurrentBar == length - 1)
                            return source[0];
                        return alpha * source[0] + (1.0 - alpha) * rawMa[1];
                    }
                case AdaptiveRsiMaType.SMMA:
                    {
                        double alpha = 1.0 / length;
                        if (CurrentBar == 0)
                            return source[0];
                        return alpha * source[0] + (1.0 - alpha) * rawMa[1];
                    }
                case AdaptiveRsiMaType.WMA:
                    {
                        double weightedSum = 0.0;
                        double weightSum = 0.0;
                        for (int i = 0; i < length; i++)
                        {
                            int weight = length - i;
                            weightedSum += source[i] * weight;
                            weightSum += weight;
                        }
                        return weightSum > 0 ? weightedSum / weightSum : source[0];
                    }
                case AdaptiveRsiMaType.VWMA:
                    {
                        double weightedSum = 0.0;
                        double volumeSum = 0.0;
                        for (int i = 0; i < length; i++)
                        {
                            double vol = Volume[i];
                            weightedSum += source[i] * vol;
                            volumeSum += vol;
                        }
                        return volumeSum > 0 ? weightedSum / volumeSum : source[0];
                    }
                default:
                    return source[0];
            }
        }

        private double ComputeStdDev(Series<double> source, Series<double> maSeries, int length)
        {
            if (CurrentBar < length - 1)
                return 0.0;

            double ma = maSeries[0];
            double sumSq = 0.0;
            for (int i = 0; i < length; i++)
            {
                double diff = source[i] - ma;
                sumSq += diff * diff;
            }
            return Math.Sqrt(sumSq / length);
        }

        #endregion

        #region Rendering

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            if (ChartBars == null || ChartBars.ToIndex < ChartBars.FromIndex || CurrentBar < Length)
                return;

            // Zone fills
            DrawZoneFills(chartControl, chartScale);

            // Custom candles / bars / heikin-ashi
            if (RsiPlotType != AdaptiveRsiPlotType.Line)
                DrawRsiCandles(chartControl, chartScale);
        }

        private void DrawZoneFills(ChartControl chartControl, ChartScale chartScale)
        {
            float x1 = chartControl.GetXByBarIndex(ChartBars, ChartBars.FromIndex);
            float x2 = chartControl.GetXByBarIndex(ChartBars, ChartBars.ToIndex)
                       + (float)chartControl.Properties.BarDistance;

            if (x2 <= x1) return;

            float width = x2 - x1;

            if (ShowOO)
            {
                FillRect(chartControl, chartScale, x1, width, zoneObTop[0], zoneObBot[0], OverboughtColorBrush, 90);
                FillRect(chartControl, chartScale, x1, width, zoneOsTop[0], zoneOsBot[0], OversoldColorBrush, 90);
            }

            if (ShowSupRes)
            {
                FillRect(chartControl, chartScale, x1, width, zoneR1[0], zoneR2[0], SupResColorBrush, 85);
                FillRect(chartControl, chartScale, x1, width, zoneS1[0], zoneS2[0], SupResColorBrush, 85);
            }
        }

        private void FillRect(ChartControl chartControl, ChartScale chartScale, float x, float width,
                              double priceTop, double priceBot, Brush brush, int opacityPercent)
        {
            if (double.IsNaN(priceTop) || double.IsNaN(priceBot) || brush == null)
                return;

            float yTop = chartScale.GetYByValue(priceTop);
            float yBot = chartScale.GetYByValue(priceBot);
            if (yBot <= yTop) return;

            var scb = brush as SolidColorBrush;
            if (scb == null) return;

            byte alpha = (byte)(255 * (100 - Math.Max(0, Math.Min(100, opacityPercent))) / 100.0);
            var color = new Color4(scb.Color.R / 255f, scb.Color.G / 255f, scb.Color.B / 255f, alpha / 255f);

            var rect = new RectangleF(x, yTop, width, yBot - yTop);
            var fillBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, color);
            RenderTarget.FillRectangle(rect, fillBrush);
            fillBrush.Dispose();
        }

        private void DrawRsiCandles(ChartControl chartControl, ChartScale chartScale)
        {
            bool isHA = RsiPlotType == AdaptiveRsiPlotType.HeikinAshi;
            bool isBar = RsiPlotType == AdaptiveRsiPlotType.Bar;

            float barDistance = (float)chartControl.Properties.BarDistance;
            float bodyWidth = Math.Max(1f, barDistance - 2f);

            int fromIdx = Math.Max(ChartBars.FromIndex, 0);
            int lastIdx = Math.Min(ChartBars.ToIndex, ChartBars.Bars.Count - 1);
            if (lastIdx < fromIdx)
                return;

            for (int i = fromIdx; i <= lastIdx; i++)
            {
                double o, h, l, c;
                if (isHA)
                {
                    o = HaRsiOpen.GetValueAt(i);
                    h = HaRsiHigh.GetValueAt(i);
                    l = HaRsiLow.GetValueAt(i);
                    c = HaRsiClose.GetValueAt(i);
                }
                else
                {
                    o = RsiOpen.GetValueAt(i);
                    h = RsiHigh.GetValueAt(i);
                    l = RsiLow.GetValueAt(i);
                    c = RsiClose.GetValueAt(i);
                }

                if (double.IsNaN(o) || double.IsNaN(h) || double.IsNaN(l) || double.IsNaN(c))
                    continue;

                float x = chartControl.GetXByBarIndex(ChartBars, i);
                float yO = chartScale.GetYByValue(o);
                float yH = chartScale.GetYByValue(h);
                float yL = chartScale.GetYByValue(l);
                float yC = chartScale.GetYByValue(c);

                bool isUp = c >= o;
                Brush bodyBrush = ChooseCandleBrush(isUp, i);

                var scb = bodyBrush as SolidColorBrush;
                if (scb == null) continue;

                var color = new Color4(scb.Color.R / 255f, scb.Color.G / 255f, scb.Color.B / 255f, 1f);
                using (var brush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, color))
                {
                    // Wick
                    RenderTarget.DrawLine(new Vector2(x, yH), new Vector2(x, yL), brush, 1f);

                    if (isBar)
                    {
                        float halfW = bodyWidth / 2f;
                        RenderTarget.DrawLine(new Vector2(x - halfW, yO), new Vector2(x, yO), brush, 1f);
                        RenderTarget.DrawLine(new Vector2(x, yC), new Vector2(x + halfW, yC), brush, 1f);
                    }
                    else
                    {
                        float top = Math.Min(yO, yC);
                        float bot = Math.Max(yO, yC);
                        float bodyH = Math.Max(1f, bot - top);
                        var bodyRect = new RectangleF(x - bodyWidth / 2f, top, bodyWidth, bodyH);
                        RenderTarget.FillRectangle(bodyRect, brush);
                        RenderTarget.DrawRectangle(bodyRect, brush, 1f);
                    }
                }
            }
        }

        private Brush ChooseCandleBrush(bool isUp, int chartBarIndex)
        {
            double h = RsiHigh.GetValueAt(chartBarIndex);
            double l = RsiLow.GetValueAt(chartBarIndex);

            bool isOb = chartBarIndex >= Length && h > OverboughtThreshold;
            bool isOs = chartBarIndex >= Length && l < OversoldThreshold;

            if (!OOColoring)
                return isUp ? RsiColorBrush : RsiColorBrush;
            if (isOb)
                return ObIntenseColorBrush;
            if (isOs)
                return OsIntenseColorBrush;
            return isUp ? RsiColorBrush : RsiColorBrush;
        }

        #endregion
    }
}

#region NinjaScript Generated Code
namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private Vinay.AdaptiveRSIZones[] cacheAdaptiveRSIZones;

        public Vinay.AdaptiveRSIZones AdaptiveRSIZones()
        {
            return AdaptiveRSIZones(Input);
        }

        public Vinay.AdaptiveRSIZones AdaptiveRSIZones(ISeries<double> input)
        {
            if (cacheAdaptiveRSIZones != null)
                for (int idx = 0; idx < cacheAdaptiveRSIZones.Length; idx++)
                    if (cacheAdaptiveRSIZones[idx] != null
                        && cacheAdaptiveRSIZones[idx].EqualsInput(input)
                        && cacheAdaptiveRSIZones[idx].Length == 14
                        && cacheAdaptiveRSIZones[idx].RsiPlotType == Vinay.AdaptiveRsiPlotType.Line)
                        return cacheAdaptiveRSIZones[idx];

            return CacheIndicator<Vinay.AdaptiveRSIZones>(new Vinay.AdaptiveRSIZones() { Length = 14, RsiPlotType = Vinay.AdaptiveRsiPlotType.Line }, input, ref cacheAdaptiveRSIZones);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.Vinay.AdaptiveRSIZones AdaptiveRSIZones()
        {
            return indicator.AdaptiveRSIZones(Input);
        }

        public Indicators.Vinay.AdaptiveRSIZones AdaptiveRSIZones(ISeries<double> input)
        {
            return indicator.AdaptiveRSIZones(input);
        }
    }
}
#endregion
