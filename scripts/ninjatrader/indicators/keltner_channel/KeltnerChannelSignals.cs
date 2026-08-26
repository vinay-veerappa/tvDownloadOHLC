#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public enum MovingAverageVariant
    {
        SMA,
        EMA,
        WMA,
        DEMA,
        TEMA,
        TRIMA,
        KAMA,
        MAMA,
        T3
    }

    /// <summary>
    /// Keltner Channel Signals Indicator (Multi-Timeframe Enabled)
    /// Converted faithfully from TradingView Pine Script (APEX) with complete MTF support.
    /// Features multi-variant Moving Averages (SMA, EMA, WMA, DEMA, TEMA, TRIMA, KAMA, MAMA, T3),
    /// dual-band Keltner Channels (Min/Max ATR multipliers), %B Bollinger/Keltner reversal signals,
    /// dynamic support/resistance tracking, and optional WaveTrend background momentum filters.
    /// </summary>
    public class KeltnerChannelSignals : Indicator
    {
        #region Parameters

        // ── 0. Multi-Timeframe (MTF) Settings ──
        [NinjaScriptProperty]
        [Display(Name = "Use Higher Timeframe (MTF)", GroupName = "0. Multi-Timeframe (MTF)", Order = 1, Description = "Enable multi-timeframe calculation on a secondary data series")]
        public bool UseHtf { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "HTF Period Type", GroupName = "0. Multi-Timeframe (MTF)", Order = 2, Description = "Bar period type for HTF (Minute, Day, etc.)")]
        public BarsPeriodType HtfPeriodType { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "HTF Period Value", GroupName = "0. Multi-Timeframe (MTF)", Order = 3, Description = "Value for the HTF period (e.g. 15 for 15-minute, 60 for 60-minute, 1 for 1-Day)")]
        public int HtfPeriodValue { get; set; }

        // ── 1. MA Base Settings ──
        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "MA Length", GroupName = "1. MA Base Settings", Order = 1, Description = "Period for the base centerline moving average")]
        public int MovingAverageLength { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "MA Type", GroupName = "1. MA Base Settings", Order = 2, Description = "Type of moving average algorithm")]
        public MovingAverageVariant MaType { get; set; }

        // ── 2. Keltner Channel Settings ──
        [NinjaScriptProperty]
        [Range(0.0, double.MaxValue)]
        [Display(Name = "ATR Multiplier Min", GroupName = "2. Keltner Channels", Order = 1, Description = "Multiplier for inner channel bounds")]
        public double AtrMultiplierMin { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, double.MaxValue)]
        [Display(Name = "ATR Multiplier Max", GroupName = "2. Keltner Channels", Order = 2, Description = "Multiplier for outer channel bounds")]
        public double AtrMultiplierMax { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "ATR Smoothing MA", GroupName = "2. Keltner Channels", Order = 3, Description = "Smoothing type for True Range")]
        public MovingAverageVariant AtrSmoothingMaType { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "ATR Smoothing Length", GroupName = "2. Keltner Channels", Order = 4, Description = "Period for True Range smoothing")]
        public int AtrLength { get; set; }

        // ── 3. Reversal Signals (%B from KC Mid + StDev) ──
        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Keltner Deviation Length", GroupName = "3. Reversal Signals (%B)", Order = 1, Description = "Lookback for Standard Deviation")]
        public int KeltnerDeviationLength { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Keltner Deviation Multiplier", GroupName = "3. Reversal Signals (%B)", Order = 2, Description = "Multiplier for Standard Deviation")]
        public double KeltnerDeviationMultiplier { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Overbought Threshold", GroupName = "3. Reversal Signals (%B)", Order = 3, Description = "Overbought %B threshold level")]
        public double OverboughtThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Oversold Threshold", GroupName = "3. Reversal Signals (%B)", Order = 4, Description = "Oversold %B threshold level")]
        public double OversoldThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Signal Arrows", GroupName = "3. Reversal Signals (%B)", Order = 5, Description = "Display Buy/Sell triangle arrows on the chart")]
        public bool ShowArrows { get; set; }

        // ── 4. WaveTrend Momentum Filter ──
        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Channel Length", GroupName = "4. WaveTrend Filter", Order = 1, Description = "WaveTrend channel period")]
        public int WaveTrendChannelLength { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "MA Length", GroupName = "4. WaveTrend Filter", Order = 2, Description = "WaveTrend moving average period")]
        public int WaveTrendMALength { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Smoothing Length", GroupName = "4. WaveTrend Filter", Order = 3, Description = "WaveTrend signal smoothing period")]
        public int WaveTrendSmoothLength { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Overbought Level", GroupName = "4. WaveTrend Filter", Order = 4, Description = "WaveTrend overbought threshold")]
        public double WaveTrendOverbought { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Oversold Level", GroupName = "4. WaveTrend Filter", Order = 5, Description = "WaveTrend oversold threshold")]
        public double WaveTrendOversold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Highlight WT Cross", GroupName = "4. WaveTrend Filter", Order = 6, Description = "Highlight chart background on WaveTrend cross")]
        public bool ShowWtCrossBackground { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Highlight WT Overbought", GroupName = "4. WaveTrend Filter", Order = 7, Description = "Highlight chart background when WaveTrend is overbought")]
        public bool ShowWtOverboughtBackground { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Highlight WT Oversold", GroupName = "4. WaveTrend Filter", Order = 8, Description = "Highlight chart background when WaveTrend is oversold")]
        public bool ShowWtOversoldBackground { get; set; }

        #endregion

        #region Public Output Series

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> KcBase => Values[0];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> KcTopMin => Values[1];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> KcTopMax => Values[2];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> KcBottomMin => Values[3];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> KcBottomMax => Values[4];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> Resistance => Values[5];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> Support => Values[6];

        [Browsable(false)]
        [XmlIgnore]
        public Series<int> SignalSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> BbrSeries { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> WaveTrend1 { get; private set; }

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> WaveTrend2 { get; private set; }

        #endregion

        #region Private State & Indicators

        // Primary (Chart TF) Series & Indicators
        private Series<double> trueRangeSeries;
        private VariantMAManager midMAManager;
        private VariantMAManager rangeMAManager;
        private StdDev stdDevIndicator;

        private Series<double> hlc3Series;
        private EMA wtEma1;
        private Series<double> wtDiffSeries;
        private EMA wtEma2;
        private Series<double> wtCiSeries;
        private EMA wtWaveTrend1Indicator;
        private SMA wtWaveTrend2Indicator;

        private double persistentResLevel;
        private double persistentSupLevel;

        // HTF (Secondary TF) Series & Indicators
        private Series<double> htfTrueRangeSeries;
        private Series<double> htfBbrSeries;
        private Series<double> htfWaveTrend1;
        private Series<double> htfWaveTrend2;
        private VariantMAManager htfMidMAManager;
        private VariantMAManager htfRangeMAManager;
        private StdDev htfStdDev;

        private Series<double> htfHlc3Series;
        private EMA htfWtEma1;
        private Series<double> htfWtDiffSeries;
        private EMA htfWtEma2;
        private Series<double> htfWtCiSeries;
        private EMA htfWtWaveTrend1Ind;
        private SMA htfWtWaveTrend2Ind;

        // Cached HTF state for primary forward-projection
        private double _htfKcMid;
        private double _htfKcTopMin;
        private double _htfKcTopMax;
        private double _htfKcBotMin;
        private double _htfKcBotMax;
        private double _htfResLevel;
        private double _htfSupLevel;
        private double _htfBbr;
        private double _htfWt1;
        private double _htfWt2;
        private bool _htfBuySignal;
        private bool _htfSellSignal;
        private bool _htfBuyHandled;
        private bool _htfSellHandled;

        private Brush wtCrossBrush;
        private Brush wtOverboughtBrush;
        private Brush wtOversoldBrush;

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                 = "Keltner Channel signals indicator with multi-variant MAs, %B reversal levels, WaveTrend momentum, and full Multi-Timeframe (MTF) capability.";
                Name                        = "KeltnerChannelSignals";
                Calculate                   = Calculate.OnBarClose;
                IsOverlay                   = true;
                DisplayInDataBox            = true;
                DrawOnPricePanel            = true;
                IsSuspendedWhileInactive    = true;

                // MTF Defaults
                UseHtf                      = false;
                HtfPeriodType               = BarsPeriodType.Minute;
                HtfPeriodValue              = 15;

                // MA Defaults
                MovingAverageLength         = 34;
                MaType                      = MovingAverageVariant.EMA;

                AtrMultiplierMin            = 1.5;
                AtrMultiplierMax            = 3.5;
                AtrSmoothingMaType          = MovingAverageVariant.EMA;
                AtrLength                   = 88;

                KeltnerDeviationLength      = 34;
                KeltnerDeviationMultiplier  = 2.0;
                OverboughtThreshold         = 1.0;
                OversoldThreshold           = 0.0;
                ShowArrows                  = true;

                WaveTrendChannelLength      = 10;
                WaveTrendMALength           = 3;
                WaveTrendSmoothLength       = 3;
                WaveTrendOverbought         = 90.0;
                WaveTrendOversold           = -90.0;
                ShowWtCrossBackground       = false;
                ShowWtOverboughtBackground  = false;
                ShowWtOversoldBackground    = false;

                // 7 Main Plots
                AddPlot(new Stroke(Brushes.Orange, 1), PlotStyle.Line, "KC Base");
                AddPlot(new Stroke(Brushes.Red, 1), PlotStyle.Line, "KC Top Min");
                AddPlot(new Stroke(Brushes.Crimson, 1), PlotStyle.Line, "KC Top Max");
                AddPlot(new Stroke(Brushes.LimeGreen, 1), PlotStyle.Line, "KC Bottom Min");
                AddPlot(new Stroke(Brushes.SeaGreen, 1), PlotStyle.Line, "KC Bottom Max");
                AddPlot(new Stroke(Brushes.Red, 2), PlotStyle.Dot, "Resistance Level");
                AddPlot(new Stroke(Brushes.LimeGreen, 2), PlotStyle.Dot, "Support Level");
            }
            else if (State == State.Configure)
            {
                if (UseHtf)
                {
                    AddDataSeries(BarsArray[0].Instrument.FullName, HtfPeriodType, HtfPeriodValue);
                }
            }
            else if (State == State.DataLoaded)
            {
                // Primary Chart-TF exported series
                trueRangeSeries     = new Series<double>(this);
                SignalSeries        = new Series<int>(this);
                BbrSeries           = new Series<double>(this);
                WaveTrend1          = new Series<double>(this);
                WaveTrend2          = new Series<double>(this);

                // Primary MA and WaveTrend calculations
                midMAManager        = new VariantMAManager(this, Close, MaType, MovingAverageLength, BarsArray[0]);
                rangeMAManager      = new VariantMAManager(this, trueRangeSeries, AtrSmoothingMaType, AtrLength, BarsArray[0]);
                stdDevIndicator     = StdDev(Close, KeltnerDeviationLength);

                hlc3Series          = new Series<double>(this);
                wtEma1              = EMA(hlc3Series, WaveTrendChannelLength);
                wtDiffSeries        = new Series<double>(this);
                wtEma2              = EMA(wtDiffSeries, WaveTrendChannelLength);
                wtCiSeries          = new Series<double>(this);
                wtWaveTrend1Indicator = EMA(wtCiSeries, WaveTrendMALength);
                wtWaveTrend2Indicator = SMA(WaveTrend1, WaveTrendSmoothLength);

                persistentResLevel  = double.NaN;
                persistentSupLevel  = double.NaN;

                // Initialize HTF secondary series if enabled
                if (UseHtf && BarsArray.Length > 1)
                {
                    htfTrueRangeSeries  = new Series<double>(BarsArray[1]);
                    htfBbrSeries        = new Series<double>(BarsArray[1]);
                    htfWaveTrend1       = new Series<double>(BarsArray[1]);
                    htfWaveTrend2       = new Series<double>(BarsArray[1]);

                    htfMidMAManager     = new VariantMAManager(this, Closes[1], MaType, MovingAverageLength, BarsArray[1]);
                    htfRangeMAManager   = new VariantMAManager(this, htfTrueRangeSeries, AtrSmoothingMaType, AtrLength, BarsArray[1]);
                    htfStdDev           = StdDev(Closes[1], KeltnerDeviationLength);

                    htfHlc3Series       = new Series<double>(BarsArray[1]);
                    htfWtEma1           = EMA(htfHlc3Series, WaveTrendChannelLength);
                    htfWtDiffSeries     = new Series<double>(BarsArray[1]);
                    htfWtEma2           = EMA(htfWtDiffSeries, WaveTrendChannelLength);
                    htfWtCiSeries       = new Series<double>(BarsArray[1]);
                    htfWtWaveTrend1Ind  = EMA(htfWtCiSeries, WaveTrendMALength);
                    htfWtWaveTrend2Ind  = SMA(htfWaveTrend1, WaveTrendSmoothLength);
                }

                // Translucent brushes for background highlights
                wtCrossBrush        = new SolidColorBrush(Color.FromArgb(60, 255, 165, 0));
                wtCrossBrush.Freeze();
                wtOverboughtBrush   = new SolidColorBrush(Color.FromArgb(40, 255, 0, 0));
                wtOverboughtBrush.Freeze();
                wtOversoldBrush     = new SolidColorBrush(Color.FromArgb(40, 0, 255, 0));
                wtOversoldBrush.Freeze();
            }
        }

        protected override void OnBarUpdate()
        {
            // ── Multi-Timeframe Routing ──
            if (UseHtf && BarsArray.Length > 1)
            {
                if (BarsInProgress == 1)
                {
                    ProcessHtfBar();
                    return;
                }
                else if (BarsInProgress == 0)
                {
                    ProcessPrimaryChartBarHtfProjected();
                    return;
                }
                return;
            }

            // Single Timeframe Mode
            if (BarsInProgress == 0)
            {
                ProcessSingleTimeframeBar();
            }
        }

        #region HTF Processing (BarsInProgress == 1)

        private void ProcessHtfBar()
        {
            int cb = CurrentBars[1];

            // 1. HTF True Range
            if (cb == 0)
            {
                htfTrueRangeSeries[0] = Highs[1][0] - Lows[1][0];
            }
            else
            {
                double highLowDiff   = Highs[1][0] - Lows[1][0];
                double highCloseDiff = Math.Abs(Highs[1][0] - Closes[1][1]);
                double lowCloseDiff  = Math.Abs(Lows[1][0] - Closes[1][1]);
                htfTrueRangeSeries[0] = Math.Max(highLowDiff, Math.Max(highCloseDiff, lowCloseDiff));
            }

            // 2. HTF Moving Average Channels
            double kcMid   = htfMidMAManager.Update();
            double kcRange = htfRangeMAManager.Update();

            _htfKcMid    = kcMid;
            _htfKcTopMin = kcMid + (kcRange * AtrMultiplierMin);
            _htfKcTopMax = kcMid + (kcRange * AtrMultiplierMax);
            _htfKcBotMin = kcMid - (kcRange * AtrMultiplierMin);
            _htfKcBotMax = kcMid - (kcRange * AtrMultiplierMax);

            // 3. HTF %B & Support / Resistance
            int reqBars = Math.Max(MovingAverageLength, Math.Max(AtrLength, KeltnerDeviationLength));
            if (cb >= reqBars)
            {
                double stdevVal = htfStdDev[0];
                double dev      = KeltnerDeviationMultiplier * stdevVal;
                double upper    = kcMid + dev;
                double lower    = kcMid - dev;
                double bbr      = (Math.Abs(upper - lower) > double.Epsilon) ? (Closes[1][0] - lower) / (upper - lower) : 0.5;
                htfBbrSeries[0] = bbr;

                double prevBbr = (cb >= 1) ? htfBbrSeries[1] : bbr;
                bool isOverboughtExit = (prevBbr > OverboughtThreshold) && (bbr < OverboughtThreshold);
                bool isOversoldExit   = (prevBbr < OversoldThreshold) && (bbr > OversoldThreshold);

                if (isOverboughtExit && cb >= 1)
                {
                    _htfResLevel = Highs[1][1];
                }

                if (isOversoldExit && cb >= 1)
                {
                    _htfSupLevel = Lows[1][1];
                }

                _htfBbr        = bbr;
                _htfBuySignal  = isOversoldExit;
                _htfSellSignal = isOverboughtExit;
            }
            else
            {
                _htfResLevel   = Highs[1][0];
                _htfSupLevel   = Lows[1][0];
                _htfBbr        = 0.5;
                _htfBuySignal  = false;
                _htfSellSignal = false;
            }

            // 4. HTF WaveTrend
            htfHlc3Series[0] = (Highs[1][0] + Lows[1][0] + Closes[1][0]) / 3.0;
            double wtMa1     = htfWtEma1[0];
            htfWtDiffSeries[0] = Math.Abs(htfHlc3Series[0] - wtMa1);
            double wtMa2     = htfWtEma2[0];
            htfWtCiSeries[0] = (wtMa2 != 0.0) ? (htfHlc3Series[0] - wtMa1) / (0.015 * wtMa2) : 0.0;

            htfWaveTrend1[0] = htfWtWaveTrend1Ind[0];
            htfWaveTrend2[0] = htfWtWaveTrend2Ind[0];
            _htfWt1          = htfWaveTrend1[0];
            _htfWt2          = htfWaveTrend2[0];
        }

        #endregion

        #region Primary Chart Processing with HTF Projection (BarsInProgress == 0)

        private void ProcessPrimaryChartBarHtfProjected()
        {
            // Forward-fill HTF values to primary chart plots & series
            KcBase[0]      = _htfKcMid;
            KcTopMin[0]    = _htfKcTopMin;
            KcTopMax[0]    = _htfKcTopMax;
            KcBottomMin[0] = _htfKcBotMin;
            KcBottomMax[0] = _htfKcBotMax;

            Resistance[0]  = _htfResLevel;
            Support[0]     = _htfSupLevel;
            BbrSeries[0]   = _htfBbr;
            WaveTrend1[0]  = _htfWt1;
            WaveTrend2[0]  = _htfWt2;

            // Signal trigger routing on HTF change
            if (_htfBuySignal && !_htfBuyHandled)
            {
                SignalSeries[0] = 1;
                _htfBuyHandled  = true;
                if (ShowArrows)
                {
                    Draw.TriangleUp(this, "Buy_" + CurrentBar, false, 0, Low[0] - (2 * TickSize), Brushes.LimeGreen);
                }
            }
            else if (_htfSellSignal && !_htfSellHandled)
            {
                SignalSeries[0] = -1;
                _htfSellHandled = true;
                if (ShowArrows)
                {
                    Draw.TriangleDown(this, "Sell_" + CurrentBar, false, 0, High[0] + (2 * TickSize), Brushes.Red);
                }
            }
            else
            {
                SignalSeries[0] = 0;
            }

            if (!_htfBuySignal) _htfBuyHandled = false;
            if (!_htfSellSignal) _htfSellHandled = false;

            // WaveTrend Background Highlighting
            if (ShowWtCrossBackground && CurrentBar >= 1 && CrossAbove(WaveTrend1, WaveTrend2, 1))
            {
                BackBrush = wtCrossBrush;
            }
            else if (ShowWtOverboughtBackground && WaveTrend2[0] > WaveTrendOverbought)
            {
                BackBrush = wtOverboughtBrush;
            }
            else if (ShowWtOversoldBackground && WaveTrend2[0] < WaveTrendOversold)
            {
                BackBrush = wtOversoldBrush;
            }
        }

        #endregion

        #region Single Timeframe Bar Processing

        private void ProcessSingleTimeframeBar()
        {
            // ── 1. Calculate True Range ──
            if (CurrentBar == 0)
            {
                trueRangeSeries[0] = High[0] - Low[0];
            }
            else
            {
                double highLowDiff   = High[0] - Low[0];
                double highCloseDiff = Math.Abs(High[0] - Close[1]);
                double lowCloseDiff  = Math.Abs(Low[0] - Close[1]);
                trueRangeSeries[0]   = Math.Max(highLowDiff, Math.Max(highCloseDiff, lowCloseDiff));
            }

            // ── 2. Update Moving Average Bands ──
            double kcMid   = midMAManager.Update();
            double kcRange = rangeMAManager.Update();

            double kcTopMinVal = kcMid + (kcRange * AtrMultiplierMin);
            double kcTopMaxVal = kcMid + (kcRange * AtrMultiplierMax);
            double kcBotMinVal = kcMid - (kcRange * AtrMultiplierMin);
            double kcBotMaxVal = kcMid - (kcRange * AtrMultiplierMax);

            KcBase[0]      = kcMid;
            KcTopMin[0]    = kcTopMinVal;
            KcTopMax[0]    = kcTopMaxVal;
            KcBottomMin[0] = kcBotMinVal;
            KcBottomMax[0] = kcBotMaxVal;

            // ── 3. Reversal Signals (%B from KC Mid + StDev) ──
            int requiredBars = Math.Max(MovingAverageLength, Math.Max(AtrLength, KeltnerDeviationLength));
            if (CurrentBar < requiredBars)
            {
                SignalSeries[0]    = 0;
                BbrSeries[0]       = 0.5;
                Resistance[0]      = High[0];
                Support[0]         = Low[0];
                persistentResLevel = High[0];
                persistentSupLevel = Low[0];
                return;
            }

            double stdevVal = stdDevIndicator[0];
            double dev      = KeltnerDeviationMultiplier * stdevVal;
            double upper    = kcMid + dev;
            double lower    = kcMid - dev;
            double bbr      = (Math.Abs(upper - lower) > double.Epsilon) ? (Close[0] - lower) / (upper - lower) : 0.5;
            BbrSeries[0]    = bbr;

            double prevBbr = (CurrentBar >= 1) ? BbrSeries[1] : bbr;
            bool isOverboughtExit = (prevBbr > OverboughtThreshold) && (bbr < OverboughtThreshold);
            bool isOversoldExit   = (prevBbr < OversoldThreshold) && (bbr > OversoldThreshold);

            if (isOverboughtExit && CurrentBar >= 1)
            {
                persistentResLevel = High[1];
            }

            if (isOversoldExit && CurrentBar >= 1)
            {
                persistentSupLevel = Low[1];
            }

            Resistance[0] = persistentResLevel;
            Support[0]    = persistentSupLevel;

            // Signal Generation
            bool sellSignal = isOverboughtExit;
            bool buySignal  = isOversoldExit;

            if (buySignal)
            {
                SignalSeries[0] = 1;
                if (ShowArrows)
                {
                    Draw.TriangleUp(this, "Buy_" + CurrentBar, false, 0, Low[0] - (2 * TickSize), Brushes.LimeGreen);
                }
            }
            else if (sellSignal)
            {
                SignalSeries[0] = -1;
                if (ShowArrows)
                {
                    Draw.TriangleDown(this, "Sell_" + CurrentBar, false, 0, High[0] + (2 * TickSize), Brushes.Red);
                }
            }
            else
            {
                SignalSeries[0] = 0;
            }

            // ── 4. WaveTrend Momentum Filter ──
            hlc3Series[0] = (High[0] + Low[0] + Close[0]) / 3.0;
            double wtMa1  = wtEma1[0];
            wtDiffSeries[0] = Math.Abs(hlc3Series[0] - wtMa1);
            double wtMa2  = wtEma2[0];
            wtCiSeries[0] = (wtMa2 != 0.0) ? (hlc3Series[0] - wtMa1) / (0.015 * wtMa2) : 0.0;

            WaveTrend1[0] = wtWaveTrend1Indicator[0];
            WaveTrend2[0] = wtWaveTrend2Indicator[0];

            // Optional Background Highlighting
            if (ShowWtCrossBackground && CurrentBar >= 1 && CrossAbove(WaveTrend1, WaveTrend2, 1))
            {
                BackBrush = wtCrossBrush;
            }
            else if (ShowWtOverboughtBackground && WaveTrend2[0] > WaveTrendOverbought)
            {
                BackBrush = wtOverboughtBrush;
            }
            else if (ShowWtOversoldBackground && WaveTrend2[0] < WaveTrendOversold)
            {
                BackBrush = wtOversoldBrush;
            }
        }

        #endregion

        #region Nested Helper Classes for Moving Average Algorithms

        public class VariantMAManager
        {
            private readonly Indicator indicator;
            private readonly ISeries<double> source;
            private readonly MovingAverageVariant variant;
            private readonly int length;
            private readonly Bars bars;

            private SMA sma;
            private EMA ema;
            private WMA wma;
            private DEMA dema;
            private TEMA tema;

            // TRIMA components
            private SMA trima1;
            private Series<double> trimaSeries;
            private SMA trima2;

            // T3 cascaded EMAs
            private EMA t3E1, t3E2, t3E3, t3E4, t3E5, t3E6;

            // KAMA & MAMA custom state engines
            private KamaCalculator kama;
            private MamaCalculator mama;

            public VariantMAManager(Indicator ind, ISeries<double> src, MovingAverageVariant maType, int len, Bars seriesBars = null)
            {
                indicator = ind;
                source    = src;
                variant   = maType;
                length    = Math.Max(1, len);
                bars      = seriesBars;

                switch (variant)
                {
                    case MovingAverageVariant.SMA:
                        sma = ind.SMA(source, length);
                        break;
                    case MovingAverageVariant.EMA:
                        ema = ind.EMA(source, length);
                        break;
                    case MovingAverageVariant.WMA:
                        wma = ind.WMA(source, length);
                        break;
                    case MovingAverageVariant.DEMA:
                        dema = ind.DEMA(source, length);
                        break;
                    case MovingAverageVariant.TEMA:
                        tema = ind.TEMA(source, length);
                        break;
                    case MovingAverageVariant.TRIMA:
                        int len1 = (int)Math.Ceiling(length / 2.0);
                        int len2 = (int)Math.Floor(length / 2.0) + 1;
                        trima1 = ind.SMA(source, len1);
                        trimaSeries = (bars != null) ? new Series<double>(bars) : new Series<double>(ind);
                        trima2 = ind.SMA(trimaSeries, len2);
                        break;
                    case MovingAverageVariant.KAMA:
                        kama = new KamaCalculator(ind, source, length, bars);
                        break;
                    case MovingAverageVariant.MAMA:
                        mama = new MamaCalculator(ind, source, bars);
                        break;
                    case MovingAverageVariant.T3:
                        t3E1 = ind.EMA(source, length);
                        t3E2 = ind.EMA(t3E1, length);
                        t3E3 = ind.EMA(t3E2, length);
                        t3E4 = ind.EMA(t3E3, length);
                        t3E5 = ind.EMA(t3E4, length);
                        t3E6 = ind.EMA(t3E5, length);
                        break;
                }
            }

            public double Update()
            {
                switch (variant)
                {
                    case MovingAverageVariant.SMA:
                        return sma[0];
                    case MovingAverageVariant.EMA:
                        return ema[0];
                    case MovingAverageVariant.WMA:
                        return wma[0];
                    case MovingAverageVariant.DEMA:
                        return dema[0];
                    case MovingAverageVariant.TEMA:
                        return tema[0];
                    case MovingAverageVariant.TRIMA:
                        trimaSeries[0] = trima1[0];
                        return trima2[0];
                    case MovingAverageVariant.KAMA:
                        return kama.Update();
                    case MovingAverageVariant.MAMA:
                        return mama.Update();
                    case MovingAverageVariant.T3:
                        const double b = 0.7;
                        const double c1 = -b * b * b;
                        const double c2 = 3.0 * b * b + 3.0 * b * b * b;
                        const double c3 = -6.0 * b * b - 3.0 * b - 3.0 * b * b * b;
                        const double c4 = 1.0 + 3.0 * b + b * b * b + 3.0 * b * b;
                        return c1 * t3E6[0] + c2 * t3E5[0] + c3 * t3E4[0] + c4 * t3E3[0];
                    default:
                        return sma[0];
                }
            }
        }

        public class KamaCalculator
        {
            private readonly Indicator indicator;
            private readonly ISeries<double> src;
            private readonly int len;
            private readonly Bars bars;
            private readonly Series<double> kamaSeries;
            private readonly Series<double> xvNoise;

            public KamaCalculator(Indicator ind, ISeries<double> source, int period, Bars seriesBars = null)
            {
                indicator  = ind;
                src        = source;
                len        = Math.Max(1, period);
                bars       = seriesBars;
                kamaSeries = (bars != null) ? new Series<double>(bars) : new Series<double>(ind);
                xvNoise    = (bars != null) ? new Series<double>(bars) : new Series<double>(ind);
            }

            public double Update()
            {
                int cb = (bars != null) ? bars.CurrentBar : indicator.CurrentBar;
                if (cb == 0)
                {
                    xvNoise[0]    = 0.0;
                    kamaSeries[0] = src[0];
                    return kamaSeries[0];
                }

                xvNoise[0] = Math.Abs(src[0] - src[1]);

                if (cb < len)
                {
                    kamaSeries[0] = src[0];
                    return kamaSeries[0];
                }

                double nsignal = Math.Abs(src[0] - src[len]);
                double nnoise = 0.0;
                for (int i = 0; i < len; i++)
                {
                    nnoise += xvNoise[i];
                }

                double nefratio = (nnoise != 0.0) ? nsignal / nnoise : 0.0;
                double nsmooth  = Math.Pow(nefratio * (0.666 - 0.0645) + 0.0645, 2);
                double prevAMA  = kamaSeries[1];
                kamaSeries[0]   = prevAMA + nsmooth * (src[0] - prevAMA);
                return kamaSeries[0];
            }
        }

        public class MamaCalculator
        {
            private readonly Indicator ind;
            private readonly ISeries<double> src;
            private readonly Bars bars;
            private readonly Series<double> sp;
            private readonly Series<double> dt;
            private readonly Series<double> q1;
            private readonly Series<double> i1;
            private readonly Series<double> jI;
            private readonly Series<double> jq;
            private readonly Series<double> i2;
            private readonly Series<double> q2;
            private readonly Series<double> re;
            private readonly Series<double> im;
            private readonly Series<double> p;
            private readonly Series<double> spp;
            private readonly Series<double> phase;
            private readonly Series<double> mama;

            public MamaCalculator(Indicator indicator, ISeries<double> source, Bars seriesBars = null)
            {
                ind   = indicator;
                src   = source;
                bars  = seriesBars;
                sp    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                dt    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                q1    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                i1    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                jI    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                jq    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                i2    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                q2    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                re    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                im    = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                p     = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                spp   = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                phase = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
                mama  = (bars != null) ? new Series<double>(bars) : new Series<double>(indicator);
            }

            public double Update()
            {
                int cb = (bars != null) ? bars.CurrentBar : ind.CurrentBar;
                if (cb == 0)
                {
                    sp[0] = src[0];
                    dt[0] = 0; q1[0] = 0; i1[0] = 0; jI[0] = 0; jq[0] = 0;
                    i2[0] = 0; q2[0] = 0; re[0] = 0; im[0] = 0;
                    p[0]  = 0; spp[0] = 0; phase[0] = 0;
                    mama[0] = src[0];
                    return mama[0];
                }

                const double fl = 0.5;
                const double sl = 0.05;
                const double pi = Math.PI;

                double s0 = src[0];
                double s1 = cb >= 1 ? src[1] : s0;
                double s2 = cb >= 2 ? src[2] : s1;
                double s3 = cb >= 3 ? src[3] : s2;

                sp[0] = (4.0 * s0 + 3.0 * s1 + 2.0 * s2 + s3) / 10.0;

                double sp2    = cb >= 2 ? sp[2] : sp[0];
                double sp4    = cb >= 4 ? sp[4] : sp2;
                double sp6    = cb >= 6 ? sp[6] : sp4;
                double p1Prev = cb >= 1 ? p[1] : 0.0;

                dt[0] = (0.0962 * sp[0] + 0.5769 * sp2 - 0.5769 * sp4 - 0.0962 * sp6) * (0.075 * p1Prev + 0.54);

                double dt2 = cb >= 2 ? dt[2] : dt[0];
                double dt4 = cb >= 4 ? dt[4] : dt2;
                double dt6 = cb >= 6 ? dt[6] : dt4;

                q1[0] = (0.0962 * dt[0] + 0.5769 * dt2 - 0.5769 * dt4 - 0.0962 * dt6) * (0.075 * p1Prev + 0.54);
                i1[0] = cb >= 3 ? dt[3] : dt[0];

                double i12 = cb >= 2 ? i1[2] : i1[0];
                double i14 = cb >= 4 ? i1[4] : i12;
                double i16 = cb >= 6 ? i1[6] : i14;

                jI[0] = (0.0962 * i1[0] + 0.5769 * i12 - 0.5769 * i14 - 0.0962 * i16) * (0.075 * p1Prev + 0.54);

                double q12 = cb >= 2 ? q1[2] : q1[0];
                double q14 = cb >= 4 ? q1[4] : q12;
                double q16 = cb >= 6 ? q1[6] : q14;

                jq[0] = (0.0962 * q1[0] + 0.5769 * q12 - 0.5769 * q14 - 0.0962 * q16) * (0.075 * p1Prev + 0.54);

                double i2_ = i1[0] - jq[0];
                double q2_ = q1[0] + jI[0];

                double prevI2 = cb >= 1 ? i2[1] : 0.0;
                double prevQ2 = cb >= 1 ? q2[1] : 0.0;

                i2[0] = 0.2 * i2_ + 0.8 * prevI2;
                q2[0] = 0.2 * q2_ + 0.8 * prevQ2;

                double re_ = i2[0] * prevI2 + q2[0] * prevQ2;
                double im_ = i2[0] * prevQ2 - q2[0] * prevI2;

                double prevRe = cb >= 1 ? re[1] : 0.0;
                double prevIm = cb >= 1 ? im[1] : 0.0;

                re[0] = 0.2 * re_ + 0.8 * prevRe;
                im[0] = 0.2 * im_ + 0.8 * prevIm;

                double p1Val = (im[0] != 0.0 && re[0] != 0.0) ? (2.0 * pi / Math.Atan(im[0] / re[0])) : p1Prev;
                double p2Val = (p1Val > 1.5 * p1Prev) ? 1.5 * p1Prev : (p1Val < 0.67 * p1Prev ? 0.67 * p1Prev : p1Val);
                double p3Val = p2Val < 6.0 ? 6.0 : (p2Val > 50.0 ? 50.0 : p2Val);

                p[0] = 0.2 * p3Val + 0.8 * p1Prev;
                double prevSpp = cb >= 1 ? spp[1] : 0.0;
                spp[0] = 0.33 * p[0] + 0.67 * prevSpp;

                double denominator = (i1[0] != 0.0) ? i1[0] : 0.0001;
                phase[0] = (180.0 / pi) * Math.Atan(q1[0] / denominator);

                double prevPhase = cb >= 1 ? phase[1] : phase[0];
                double dphase_   = prevPhase - phase[0];
                double dphase    = dphase_ < 1.0 ? 1.0 : dphase_;

                double alpha_ = fl / dphase;
                double alpha  = alpha_ < sl ? sl : (alpha_ > fl ? fl : alpha_);

                double prevMama = cb >= 1 ? mama[1] : src[0];
                mama[0] = alpha * src[0] + (1.0 - alpha) * prevMama;

                return mama[0];
            }
        }

        #endregion
    }
}

#region NinjaScript Generated Code
namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private KeltnerChannelSignals[] cacheKeltnerChannelSignals;

        public KeltnerChannelSignals KeltnerChannelSignals()
        {
            return KeltnerChannelSignals(Input, false, BarsPeriodType.Minute, 15, 34, MovingAverageVariant.EMA, 1.5, 3.5, MovingAverageVariant.EMA, 88, 34, 2.0, 1.0, 0.0, true, 10, 3, 3, 90.0, -90.0, false, false, false);
        }

        public KeltnerChannelSignals KeltnerChannelSignals(int movingAverageLength, MovingAverageVariant maType, double atrMultiplierMin, double atrMultiplierMax)
        {
            return KeltnerChannelSignals(Input, false, BarsPeriodType.Minute, 15, movingAverageLength, maType, atrMultiplierMin, atrMultiplierMax, MovingAverageVariant.EMA, 88, 34, 2.0, 1.0, 0.0, true, 10, 3, 3, 90.0, -90.0, false, false, false);
        }

        public KeltnerChannelSignals KeltnerChannelSignals(bool useHtf, BarsPeriodType htfPeriodType, int htfPeriodValue)
        {
            return KeltnerChannelSignals(Input, useHtf, htfPeriodType, htfPeriodValue, 34, MovingAverageVariant.EMA, 1.5, 3.5, MovingAverageVariant.EMA, 88, 34, 2.0, 1.0, 0.0, true, 10, 3, 3, 90.0, -90.0, false, false, false);
        }

        public KeltnerChannelSignals KeltnerChannelSignals(bool useHtf, BarsPeriodType htfPeriodType, int htfPeriodValue, int movingAverageLength, MovingAverageVariant maType, double atrMultiplierMin, double atrMultiplierMax, MovingAverageVariant atrSmoothingMaType, int atrLength, int keltnerDeviationLength, double keltnerDeviationMultiplier, double overboughtThreshold, double oversoldThreshold, bool showArrows, int waveTrendChannelLength, int waveTrendMALength, int waveTrendSmoothLength, double waveTrendOverbought, double waveTrendOversold, bool showWtCrossBackground, bool showWtOverboughtBackground, bool showWtOversoldBackground)
        {
            return KeltnerChannelSignals(Input, useHtf, htfPeriodType, htfPeriodValue, movingAverageLength, maType, atrMultiplierMin, atrMultiplierMax, atrSmoothingMaType, atrLength, keltnerDeviationLength, keltnerDeviationMultiplier, overboughtThreshold, oversoldThreshold, showArrows, waveTrendChannelLength, waveTrendMALength, waveTrendSmoothLength, waveTrendOverbought, waveTrendOversold, showWtCrossBackground, showWtOverboughtBackground, showWtOversoldBackground);
        }

        public KeltnerChannelSignals KeltnerChannelSignals(ISeries<double> input, bool useHtf, BarsPeriodType htfPeriodType, int htfPeriodValue, int movingAverageLength, MovingAverageVariant maType, double atrMultiplierMin, double atrMultiplierMax, MovingAverageVariant atrSmoothingMaType, int atrLength, int keltnerDeviationLength, double keltnerDeviationMultiplier, double overboughtThreshold, double oversoldThreshold, bool showArrows, int waveTrendChannelLength, int waveTrendMALength, int waveTrendSmoothLength, double waveTrendOverbought, double waveTrendOversold, bool showWtCrossBackground, bool showWtOverboughtBackground, bool showWtOversoldBackground)
        {
            if (cacheKeltnerChannelSignals != null)
                for (int idx = 0; idx < cacheKeltnerChannelSignals.Length; idx++)
                    if (cacheKeltnerChannelSignals[idx] != null && cacheKeltnerChannelSignals[idx].UseHtf == useHtf && cacheKeltnerChannelSignals[idx].HtfPeriodType == htfPeriodType && cacheKeltnerChannelSignals[idx].HtfPeriodValue == htfPeriodValue && cacheKeltnerChannelSignals[idx].MovingAverageLength == movingAverageLength && cacheKeltnerChannelSignals[idx].MaType == maType && Math.Abs(cacheKeltnerChannelSignals[idx].AtrMultiplierMin - atrMultiplierMin) < double.Epsilon && Math.Abs(cacheKeltnerChannelSignals[idx].AtrMultiplierMax - atrMultiplierMax) < double.Epsilon && cacheKeltnerChannelSignals[idx].AtrSmoothingMaType == atrSmoothingMaType && cacheKeltnerChannelSignals[idx].AtrLength == atrLength && cacheKeltnerChannelSignals[idx].KeltnerDeviationLength == keltnerDeviationLength && Math.Abs(cacheKeltnerChannelSignals[idx].KeltnerDeviationMultiplier - keltnerDeviationMultiplier) < double.Epsilon && Math.Abs(cacheKeltnerChannelSignals[idx].OverboughtThreshold - overboughtThreshold) < double.Epsilon && Math.Abs(cacheKeltnerChannelSignals[idx].OversoldThreshold - oversoldThreshold) < double.Epsilon && cacheKeltnerChannelSignals[idx].ShowArrows == showArrows && cacheKeltnerChannelSignals[idx].WaveTrendChannelLength == waveTrendChannelLength && cacheKeltnerChannelSignals[idx].WaveTrendMALength == waveTrendMALength && cacheKeltnerChannelSignals[idx].WaveTrendSmoothLength == waveTrendSmoothLength && Math.Abs(cacheKeltnerChannelSignals[idx].WaveTrendOverbought - waveTrendOverbought) < double.Epsilon && Math.Abs(cacheKeltnerChannelSignals[idx].WaveTrendOversold - waveTrendOversold) < double.Epsilon && cacheKeltnerChannelSignals[idx].ShowWtCrossBackground == showWtCrossBackground && cacheKeltnerChannelSignals[idx].ShowWtOverboughtBackground == showWtOverboughtBackground && cacheKeltnerChannelSignals[idx].ShowWtOversoldBackground == showWtOversoldBackground && cacheKeltnerChannelSignals[idx].EqualsInput(input))
                        return cacheKeltnerChannelSignals[idx];
            return new KeltnerChannelSignals
            {
                UseHtf                     = useHtf,
                HtfPeriodType              = htfPeriodType,
                HtfPeriodValue             = htfPeriodValue,
                MovingAverageLength        = movingAverageLength,
                MaType                     = maType,
                AtrMultiplierMin           = atrMultiplierMin,
                AtrMultiplierMax           = atrMultiplierMax,
                AtrSmoothingMaType         = atrSmoothingMaType,
                AtrLength                  = atrLength,
                KeltnerDeviationLength     = keltnerDeviationLength,
                KeltnerDeviationMultiplier = keltnerDeviationMultiplier,
                OverboughtThreshold        = overboughtThreshold,
                OversoldThreshold          = oversoldThreshold,
                ShowArrows                 = showArrows,
                WaveTrendChannelLength     = waveTrendChannelLength,
                WaveTrendMALength          = waveTrendMALength,
                WaveTrendSmoothLength      = waveTrendSmoothLength,
                WaveTrendOverbought        = waveTrendOverbought,
                WaveTrendOversold          = waveTrendOversold,
                ShowWtCrossBackground      = showWtCrossBackground,
                ShowWtOverboughtBackground = showWtOverboughtBackground,
                ShowWtOversoldBackground   = showWtOversoldBackground
            };
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.KeltnerChannelSignals KeltnerChannelSignals()
        {
            return indicator.KeltnerChannelSignals(Input, false, BarsPeriodType.Minute, 15, 34, Indicators.MovingAverageVariant.EMA, 1.5, 3.5, Indicators.MovingAverageVariant.EMA, 88, 34, 2.0, 1.0, 0.0, true, 10, 3, 3, 90.0, -90.0, false, false, false);
        }

        public Indicators.KeltnerChannelSignals KeltnerChannelSignals(bool useHtf, BarsPeriodType htfPeriodType, int htfPeriodValue, int movingAverageLength, Indicators.MovingAverageVariant maType, double atrMultiplierMin, double atrMultiplierMax, Indicators.MovingAverageVariant atrSmoothingMaType, int atrLength, int keltnerDeviationLength, double keltnerDeviationMultiplier, double overboughtThreshold, double oversoldThreshold, bool showArrows, int waveTrendChannelLength, int waveTrendMALength, int waveTrendSmoothLength, double waveTrendOverbought, double waveTrendOversold, bool showWtCrossBackground, bool showWtOverboughtBackground, bool showWtOversoldBackground)
        {
            return indicator.KeltnerChannelSignals(Input, useHtf, htfPeriodType, htfPeriodValue, movingAverageLength, maType, atrMultiplierMin, atrMultiplierMax, atrSmoothingMaType, atrLength, keltnerDeviationLength, keltnerDeviationMultiplier, overboughtThreshold, oversoldThreshold, showArrows, waveTrendChannelLength, waveTrendMALength, waveTrendSmoothLength, waveTrendOverbought, waveTrendOversold, showWtCrossBackground, showWtOverboughtBackground, showWtOversoldBackground);
        }

        public Indicators.KeltnerChannelSignals KeltnerChannelSignals(ISeries<double> input, bool useHtf, BarsPeriodType htfPeriodType, int htfPeriodValue, int movingAverageLength, Indicators.MovingAverageVariant maType, double atrMultiplierMin, double atrMultiplierMax, Indicators.MovingAverageVariant atrSmoothingMaType, int atrLength, int keltnerDeviationLength, double keltnerDeviationMultiplier, double overboughtThreshold, double oversoldThreshold, bool showArrows, int waveTrendChannelLength, int waveTrendMALength, int waveTrendSmoothLength, double waveTrendOverbought, double waveTrendOversold, bool showWtCrossBackground, bool showWtOverboughtBackground, bool showWtOversoldBackground)
        {
            return indicator.KeltnerChannelSignals(input, useHtf, htfPeriodType, htfPeriodValue, movingAverageLength, maType, atrMultiplierMin, atrMultiplierMax, atrSmoothingMaType, atrLength, keltnerDeviationLength, keltnerDeviationMultiplier, overboughtThreshold, oversoldThreshold, showArrows, waveTrendChannelLength, waveTrendMALength, waveTrendSmoothLength, waveTrendOverbought, waveTrendOversold, showWtCrossBackground, showWtOverboughtBackground, showWtOversoldBackground);
        }
    }
}
#endregion
