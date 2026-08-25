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
using NinjaTrader.NinjaScript.Indicators;
using SharpDX;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    public class VWAPSMIHybrid : Indicator
    {
        #region Parameters
        [NinjaScriptProperty][Display(Name = "Log-space Scaling", Order = 1, GroupName = "VWAP Settings")]
        public bool LogSpaceScaling { get; set; }
        [NinjaScriptProperty][Display(Name = "VWAP Length", Order = 2, GroupName = "VWAP Settings")]
        public int VwapLength { get; set; }
        [NinjaScriptProperty][Display(Name = "2σ Multiplier", Order = 3, GroupName = "VWAP Settings")]
        public double Dev2Mult { get; set; }
        [NinjaScriptProperty][Display(Name = "3σ Multiplier", Order = 4, GroupName = "VWAP Settings")]
        public double Dev3Mult { get; set; }
        [NinjaScriptProperty][Display(Name = "VWAP Timeframe", Order = 5, GroupName = "VWAP Settings")]
        public int VwapTimeframe { get; set; }
        [NinjaScriptProperty][Display(Name = "VWAP Timeframe Type", Order = 6, GroupName = "VWAP Settings")]
        public BarsPeriodType VwapTimeframeType { get; set; }
        [NinjaScriptProperty][Display(Name = "SMI %K Length", Order = 1, GroupName = "SMI Core Settings")]
        public int KLength { get; set; }
        [NinjaScriptProperty][Display(Name = "SMI 1st Smoothing", Order = 2, GroupName = "SMI Core Settings")]
        public int KSmooth1 { get; set; }
        [NinjaScriptProperty][Display(Name = "SMI 2nd Smoothing", Order = 3, GroupName = "SMI Core Settings")]
        public int KSmooth2 { get; set; }
        [NinjaScriptProperty][Display(Name = "Signal EMA", Order = 1, GroupName = "SMI Signal System")]
        public int SignalLength { get; set; }
        [NinjaScriptProperty][Display(Name = "Filter EMA", Order = 2, GroupName = "SMI Signal System")]
        public int FilterLength { get; set; }
        [NinjaScriptProperty][Display(Name = "Overbought Level", Order = 3, GroupName = "SMI Signal System")]
        public double ObLevel { get; set; }
        [NinjaScriptProperty][Display(Name = "Oversold Level", Order = 4, GroupName = "SMI Signal System")]
        public double OsLevel { get; set; }
        [NinjaScriptProperty][Display(Name = "Cross Flexibility [1-10]", Order = 5, GroupName = "SMI Signal System")]
        public int CrossFlexibility { get; set; }
        [NinjaScriptProperty][Display(Name = "Enable MFI Confluence", Order = 1, GroupName = "MFI Confluence")]
        public bool UseMFI { get; set; }
        [NinjaScriptProperty][Display(Name = "MFI Length", Order = 2, GroupName = "MFI Confluence")]
        public int MfiLength { get; set; }
        [NinjaScriptProperty][Display(Name = "MFI-SMI %K Length", Order = 3, GroupName = "MFI Confluence")]
        public int MfiSmiK { get; set; }
        [NinjaScriptProperty][Display(Name = "MFI-SMI 1st Smooth", Order = 4, GroupName = "MFI Confluence")]
        public int MfiSmiSmooth1 { get; set; }
        [NinjaScriptProperty][Display(Name = "MFI-SMI 2nd Smooth", Order = 5, GroupName = "MFI Confluence")]
        public int MfiSmiSmooth2 { get; set; }
        [NinjaScriptProperty][Display(Name = "Min Signal Quality", Order = 1, GroupName = "Signal Filters")]
        public int MinSignalQuality { get; set; }
        [NinjaScriptProperty][Display(Name = "Volume Filter", Order = 2, GroupName = "Signal Filters")]
        public bool UseVolumeFilter { get; set; }
        [NinjaScriptProperty][Display(Name = "Volume Threshold", Order = 3, GroupName = "Signal Filters")]
        public double VolumeMultiplier { get; set; }
        [NinjaScriptProperty][Display(Name = "Market Type Filter", Order = 4, GroupName = "Signal Filters")]
        public bool UseMarketRegime { get; set; }
        [NinjaScriptProperty][Display(Name = "Enable Range Filter", Order = 1, GroupName = "Range Filter")]
        public bool UseRangeFilter { get; set; }
        [NinjaScriptProperty][Display(Name = "Range Mode", Order = 2, GroupName = "Range Filter")]
        public string RangeMethod { get; set; }
        [NinjaScriptProperty][Display(Name = "Band Width Lookback", Order = 3, GroupName = "Range Filter")]
        public int BandWidthLength { get; set; }
        [NinjaScriptProperty][Display(Name = "Tight Range Threshold", Order = 4, GroupName = "Range Filter")]
        public double TightRangeThreshold { get; set; }
        [NinjaScriptProperty][Display(Name = "Wide Range Threshold", Order = 5, GroupName = "Range Filter")]
        public double WideRangeThreshold { get; set; }
        [NinjaScriptProperty][Display(Name = "Color Bands by Range State", Order = 6, GroupName = "Range Filter")]
        public bool ShowRangeState { get; set; }
        [NinjaScriptProperty][Display(Name = "Session Statistics", Order = 1, GroupName = "Advanced Features")]
        public bool ShowSessionStats { get; set; }
        [NinjaScriptProperty][Display(Name = "Require SMI Divergence", Order = 2, GroupName = "Advanced Features")]
        public bool RequireDivergence { get; set; }
        [NinjaScriptProperty][Display(Name = "Show VWAP Line", Order = 1, GroupName = "Visual Settings")]
        public bool ShowVwapLine { get; set; }
        [NinjaScriptProperty][Display(Name = "Fill Band Areas", Order = 2, GroupName = "Visual Settings")]
        public bool FillBands { get; set; }
        [NinjaScriptProperty][Display(Name = "Show Trade Signals", Order = 3, GroupName = "Visual Settings")]
        public bool ShowSignals { get; set; }
        [NinjaScriptProperty][Display(Name = "Show ALL Band Touches", Order = 4, GroupName = "Visual Settings")]
        public bool ShowBandTouches { get; set; }
        [NinjaScriptProperty][Display(Name = "Show Win Rate Table", Order = 5, GroupName = "Visual Settings")]
        public bool ShowWinRate { get; set; }
        [NinjaScriptProperty][Display(Name = "Show SMI Info Panel", Order = 6, GroupName = "Visual Settings")]
        public bool ShowSmiPanel { get; set; }
        [NinjaScriptProperty][Display(Name = "Bullish Color", Order = 1, GroupName = "Colors")]
        public Brush BullishColor { get; set; }
        [NinjaScriptProperty][Display(Name = "Bearish Color", Order = 2, GroupName = "Colors")]
        public Brush BearishColor { get; set; }
        [NinjaScriptProperty][Display(Name = "Tight Range Color", Order = 3, GroupName = "Colors")]
        public Brush TightRangeColor { get; set; }
        [NinjaScriptProperty][Display(Name = "Wide/Choppy Color", Order = 4, GroupName = "Colors")]
        public Brush WideRangeColor { get; set; }
        [NinjaScriptProperty][Display(Name = "Enable Alerts", Order = 1, GroupName = "Alerts")]
        public bool EnableAlerts { get; set; }
        #endregion

        #region Exported Series
        [Browsable(false)][XmlIgnore] public Series<double> VwapSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> Upper2Series { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> Lower2Series { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> Upper3Series { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> Lower3Series { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> SmiSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> SmiSignalSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> SmiFilterSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> SignalSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> LongSignalSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> ShortSignalSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> StrongLongSignalSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> StrongShortSignalSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> MfiSmiSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> RelativeBandWidthSeries { get; private set; }
        #endregion

        // HTF-tied working series (BarsArray[1]) — only for EMA smoothing on HTF
        private Series<double> htfSrc, htfDist, htfRange, htfMfiDist, htfMfiRange, htfSmiSeries;
        private Series<double> htfBandWidth;
        private MFI htfMfiIndicator;
        private MFI priMfiIndicator; // for fallback on primary bars

        // Primary-tied working series for fallback (chart TF == VWAP TF)
        private Series<double> priDist, priRange, priMfiDist, priMfiRange, priSmiSeries, priBandWidth;

        // Scalar fields — set during BIP==1, forward-filled to BIP==0 (like request.security)
        private double _vwmean, _upper2Sigma, _lower2Sigma, _upper3Sigma, _lower3Sigma;
        private double _htfSmi, _htfSmiSignal, _htfSmiFilter, _htfMfiSmi;
        private bool _htfActive; // true once BIP=1 has computed (HTF path is working)

        // SMI states (from HTF, evaluated on chart TF)
        private bool bullishTrend, bearishTrend, filterRising, filterFalling;
        private bool signalAboveZero, signalBelowZero, inOverbought, inOversold;
        private bool wasOversold, wasOverbought, bullCross, bearCross;
        private bool zeroBullCross, zeroBearCross, bullCrossRecent, bearCrossRecent;
        private bool mfiSmiRising, mfiSmiFalling, mfiSmiAboveZero, mfiSmiBelowZero;
        private bool mfiConfirmsBull, mfiConfirmsBear;
        private bool bullishDivergence, bearishDivergence, bullishDivRecent, bearishDivRecent;
        private bool mfiSmiBullishDiv, mfiSmiBearishDiv, mfiSmiBullishDivRecent, mfiSmiBearishDivRecent;
        private bool dualBullishDiv, dualBearishDiv;
        private int bullSignalQuality, bearSignalQuality;
        private bool isTightRange, isWideRange, isNormalRange, rangeFilterPass;
        private double relativeBandWidth;
        private bool isAsian, isLondon, isNY, volumeQualified;
        private bool isTrending; private int trendDirection;
        private bool regimeLongOK, regimeShortOK;
        private bool upper2Touch, lower2Touch, upper3Touch, lower3Touch;
        private bool atUpperBands, atLowerBands, atUpper3, atLower3;
        private bool nearUpper2, nearLower2, nearUpper3, nearLower3;
        private bool smiConfirmLong, smiConfirmShort, divFilterLong, divFilterShort;
        private bool rawLongOpportunity, rawShortOpportunity, rawStrongLong, rawStrongShort;
        private bool longOpportunity, shortOpportunity, strongLongOpportunity, strongShortOpportunity;
        private bool regularLongOpportunity, regularShortOpportunity;
        private int barsSinceLastLong, barsSinceLastShort, barsSinceLastStrongLong, barsSinceLastStrongShort;
        private int totalOpportunities, successfulTrades, asianSignals, londonSignals, nySignals;
        private int asianWins, londonWins, nyWins;
        private double prevPriceHigh, prevPriceLow, prevSMIHigh, prevSMILow;
        private double prevMfiSmiHigh, prevMfiSmiLow;
        private int prevHighBar, prevLowBar, prevMfiSmiHighBar, prevMfiSmiLowBar;
        private double currPriceHigh, currPriceLow, currSMIHigh, currSMILow;
        private double currMfiSmiHigh, currMfiSmiLow;
        private int currHighBar, currLowBar, currMfiSmiHighBar, currMfiSmiLowBar;

        // Lightweight counters (no Series needed)
        private int bsOversold, bsOverbought, bsBullCross, bsBearCross;
        private int bsBullDiv, bsBearDiv, bsMfiBullDiv, bsMfiBearDiv;
        private int bsUpper2Touch, bsLower2Touch, bsUpper3Touch, bsLower3Touch;
        private bool[] longOppHist = new bool[6]; private bool[] shortOppHist = new bool[6];
        private int[] sessionHist = new int[6]; private int histIdx;

        // SharpDX brushes
        private SharpDX.Direct2D1.Brush upperFillBrush, lowerFillBrush;
        private bool brushesNeedUpdate;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "[Smith] VWAP + SMI Hybrid — VWAP bands + SMI oscillator computed on a higher timeframe; entries detected on the chart timeframe.";
                Name = "VWAPSMIHybrid";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true; DisplayInDataBox = true; DrawOnPricePanel = true;
                MaximumBarsLookBack = MaximumBarsLookBack.Infinite;

                LogSpaceScaling = true; VwapLength = 60; Dev2Mult = 2.0; Dev3Mult = 3.0;
                VwapTimeframe = 5; VwapTimeframeType = BarsPeriodType.Minute;
                KLength = 14; KSmooth1 = 3; KSmooth2 = 3;
                SignalLength = 8; FilterLength = 21; ObLevel = 40; OsLevel = -40; CrossFlexibility = 3;
                UseMFI = true; MfiLength = 14; MfiSmiK = 10; MfiSmiSmooth1 = 3; MfiSmiSmooth2 = 3;
                MinSignalQuality = 2; UseVolumeFilter = false; VolumeMultiplier = 1.2; UseMarketRegime = false;
                UseRangeFilter = true; RangeMethod = "Filter Choppy"; BandWidthLength = 20;
                TightRangeThreshold = 0.8; WideRangeThreshold = 1.3; ShowRangeState = true;
                ShowSessionStats = true; RequireDivergence = false;
                ShowVwapLine = true; FillBands = true; ShowSignals = true; ShowBandTouches = false;
                ShowWinRate = true; ShowSmiPanel = true;
                BullishColor = Brushes.LimeGreen; BearishColor = Brushes.Red;
                TightRangeColor = Brushes.DodgerBlue; WideRangeColor = Brushes.Orange;
                EnableAlerts = true;

                AddPlot(new Stroke(Brushes.Gray, 1), PlotStyle.Line, "VWAP");
                AddPlot(new Stroke(Brushes.Red, 1), PlotStyle.Line, "Upper2");
                AddPlot(new Stroke(Brushes.LimeGreen, 1), PlotStyle.Line, "Lower2");
                AddPlot(new Stroke(Brushes.Red, 1), PlotStyle.Line, "Upper3");
                AddPlot(new Stroke(Brushes.LimeGreen, 1), PlotStyle.Line, "Lower3");
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsArray[0].Instrument.FullName, VwapTimeframeType, VwapTimeframe);
            }
            else if (State == State.DataLoaded)
            {
                // Chart-TF exported series
                VwapSeries = new Series<double>(this);
                Upper2Series = new Series<double>(this);
                Lower2Series = new Series<double>(this);
                Upper3Series = new Series<double>(this);
                Lower3Series = new Series<double>(this);
                SignalSeries = new Series<int>(this);
                LongSignalSeries = new Series<int>(this);
                ShortSignalSeries = new Series<int>(this);
                StrongLongSignalSeries = new Series<int>(this);
                StrongShortSignalSeries = new Series<int>(this);
                RelativeBandWidthSeries = new Series<double>(this);

                // HTF-tied working series — only for EMA smoothing on the HTF
                htfSrc = new Series<double>(BarsArray[1], MaximumBarsLookBack.TwoHundredFiftySix);
                htfBandWidth = new Series<double>(BarsArray[1], MaximumBarsLookBack.TwoHundredFiftySix);
                htfDist = new Series<double>(BarsArray[1], MaximumBarsLookBack.TwoHundredFiftySix);
                htfRange = new Series<double>(BarsArray[1], MaximumBarsLookBack.TwoHundredFiftySix);
                htfMfiDist = new Series<double>(BarsArray[1], MaximumBarsLookBack.TwoHundredFiftySix);
                htfMfiRange = new Series<double>(BarsArray[1], MaximumBarsLookBack.TwoHundredFiftySix);
                htfSmiSeries = new Series<double>(BarsArray[1], MaximumBarsLookBack.TwoHundredFiftySix);

                // Primary-tied fallback series
                priDist = new Series<double>(this);
                priRange = new Series<double>(this);
                priMfiDist = new Series<double>(this);
                priMfiRange = new Series<double>(this);
                priSmiSeries = new Series<double>(this);
                priBandWidth = new Series<double>(this);

                // Exported SMI/MFI series point to chart-TF series (written from HTF values)
                SmiSeries = new Series<double>(this);
                SmiSignalSeries = new Series<double>(this);
                SmiFilterSeries = new Series<double>(this);
                MfiSmiSeries = new Series<double>(this);

                htfMfiIndicator = MFI(BarsArray[1], MfiLength);
                priMfiIndicator = MFI(MfiLength);

                barsSinceLastLong = barsSinceLastShort = 100;
                barsSinceLastStrongLong = barsSinceLastStrongShort = 100;
            }
        }

        // ══════════════════════════════════════════════════════════════════════════════════════════════════
        // HTF path: compute VWAP + SMI entirely on the higher timeframe (BarsInProgress == 1)
        // ══════════════════════════════════════════════════════════════════════════════════════════════════
        protected override void OnBarUpdate()
        {
            if (BarsInProgress == 1)
            {
                ComputeHtfVwapAndSmi();
                return;
            }
            if (BarsInProgress != 0)
                return;

            // Fallback: if BIP=1 hasn't ever computed (chart TF == VWAP TF, no separate
            // series created by NT8), compute VWAP + SMI directly on the primary bars
            // on EVERY bar. Once BIP=1 does fire (_htfActive becomes true), this stops
            // and the HTF scalar forward-fill takes over.
            if (!_htfActive && CurrentBar >= Math.Max(KLength, MfiLength))
                ComputeVwapAndSmiOnPrimary();

            // Write HTF scalar values to chart-TF exported series (forward-filled)
            SmiSeries[0] = _htfSmi;
            SmiSignalSeries[0] = _htfSmiSignal;
            SmiFilterSeries[0] = _htfSmiFilter;
            MfiSmiSeries[0] = _htfMfiSmi;
            RelativeBandWidthSeries[0] = relativeBandWidth;

            // Write band plots on EVERY chart bar (before signal guard)
            WriteBandPlots();

            // Signal logic guard
            if (CurrentBar < 50) return;

            // Chart-TF filters + signal detection
            RunChartTfSignalLogic();

            // Plots, signals, alerts
            WriteSignalsAndAlerts();
        }

        // Fallback: compute VWAP + SMI on the primary (chart TF) bars. Used when
        // chart TF == VWAP TF (no separate secondary series) or before the HTF catches up.
        private void ComputeVwapAndSmiOnPrimary()
        {
            double pClose = Close[0];
            double src = LogSpaceScaling ? Math.Log(pClose) : pClose;
            // Use the HTF src series if available, otherwise a primary-tied series
            // For the fallback, we compute directly on the primary bars
            int len = Math.Min(VwapLength, CurrentBar + 1);

            double dSum = 0, wSum = 0;
            for (int i = 0; i < len; i++) { dSum += Volume[i] * (LogSpaceScaling ? Math.Log(Close[i]) : Close[i]); wSum += Volume[i]; }
            double vwmean = wSum > 0 ? dSum / wSum : src;

            double devDSum = 0, devWSum = 0;
            for (int i = 0; i < len; i++) { devDSum += Volume[i] * Math.Abs((LogSpaceScaling ? Math.Log(Close[i]) : Close[i]) - vwmean); devWSum += Volume[i]; }
            double dev = devWSum > 0 ? devDSum / devWSum : 0;

            _vwmean = LogSpaceScaling ? Math.Exp(vwmean) : vwmean;
            _upper2Sigma = LogSpaceScaling ? Math.Exp(vwmean + dev * Dev2Mult) : vwmean + dev * Dev2Mult;
            _lower2Sigma = LogSpaceScaling ? Math.Exp(vwmean - dev * Dev2Mult) : vwmean - dev * Dev2Mult;
            _upper3Sigma = LogSpaceScaling ? Math.Exp(vwmean + dev * Dev3Mult) : vwmean + dev * Dev3Mult;
            _lower3Sigma = LogSpaceScaling ? Math.Exp(vwmean - dev * Dev3Mult) : vwmean - dev * Dev3Mult;

            // Band width / range
            double bw = (_upper2Sigma - _lower2Sigma) / _vwmean * 100.0;
            priBandWidth[0] = bw;
            int bwLen = Math.Min(BandWidthLength, CurrentBar + 1);
            double sumBW = 0; for (int i = 0; i < bwLen; i++) sumBW += priBandWidth[i];
            double avgBW = bwLen > 0 ? sumBW / bwLen : 0;
            relativeBandWidth = avgBW > 0 ? bw / avgBW : 1.0;
            isTightRange = relativeBandWidth < TightRangeThreshold;
            isWideRange = relativeBandWidth > WideRangeThreshold;

            // SMI on primary
            double hh = MAX(High, KLength)[0];
            double ll = MIN(Low, KLength)[0];
            double mid = (hh + ll) / 2.0;
            priDist[0] = Close[0] - mid;
            priRange[0] = hh - ll;
            double sDist = EMA(EMA(priDist, KSmooth1), KSmooth2)[0];
            double sRng = EMA(EMA(priRange, KSmooth1), KSmooth2)[0];
            double smi = sRng != 0 ? 100.0 * (sDist / (sRng / 2.0)) : 0.0;
            priSmiSeries[0] = smi;
            _htfSmi = smi;
            _htfSmiSignal = EMA(priSmiSeries, SignalLength)[0];
            _htfSmiFilter = EMA(priSmiSeries, FilterLength)[0];

            // MFI-SMI on primary
            double mfi = priMfiIndicator[0];
            double mfHh = double.MinValue, mfLl = double.MaxValue;
            int mfLen = Math.Min(MfiSmiK, CurrentBar + 1);
            for (int i = 0; i < mfLen; i++) { double m = priMfiIndicator[i]; if (m > mfHh) mfHh = m; if (m < mfLl) mfLl = m; }
            priMfiDist[0] = mfi - (mfHh + mfLl) / 2.0;
            priMfiRange[0] = mfHh - mfLl;
            double mfSd = EMA(EMA(priMfiDist, MfiSmiSmooth1), MfiSmiSmooth2)[0];
            double mfSr = EMA(EMA(priMfiRange, MfiSmiSmooth1), MfiSmiSmooth2)[0];
            _htfMfiSmi = mfSr != 0 ? 200.0 * (mfSd / mfSr) : 0.0;
        }

        private void ComputeHtfVwapAndSmi()
        {
            // Always write the source series so historical values are available
            // when the VWAP loop reads htfSrc[i] for past bars
            double htfClose = Close[0];
            double src = LogSpaceScaling ? Math.Log(htfClose) : htfClose;
            htfSrc[0] = src;

            if (CurrentBar < Math.Max(KLength, MfiLength)) return;
            int len = Math.Min(VwapLength, CurrentBar + 1);

            // smith_vwmean: volume-weighted mean over len HTF bars
            double dSum = 0, wSum = 0;
            for (int i = 0; i < len; i++) { dSum += Volume[i] * htfSrc[i]; wSum += Volume[i]; }
            double vwmean = wSum > 0 ? dSum / wSum : src;

            // smith_vwavdev: volume-weighted mean absolute deviation
            double devDSum = 0, devWSum = 0;
            for (int i = 0; i < len; i++) { devDSum += Volume[i] * Math.Abs(htfSrc[i] - vwmean); devWSum += Volume[i]; }
            double dev = devWSum > 0 ? devDSum / devWSum : 0;

            double u2 = vwmean + dev * Dev2Mult, l2 = vwmean - dev * Dev2Mult;
            double u3 = vwmean + dev * Dev3Mult, l3 = vwmean - dev * Dev3Mult;

            // Store as scalars (forward-filled to chart TF — like request.security)
            _vwmean = LogSpaceScaling ? Math.Exp(vwmean) : vwmean;
            _upper2Sigma = LogSpaceScaling ? Math.Exp(u2) : u2;
            _lower2Sigma = LogSpaceScaling ? Math.Exp(l2) : l2;
            _upper3Sigma = LogSpaceScaling ? Math.Exp(u3) : u3;
            _lower3Sigma = LogSpaceScaling ? Math.Exp(l3) : l3;
            _htfActive = true;

            // Band width / range detection (on HTF)
            double bw = (_upper2Sigma - _lower2Sigma) / _vwmean * 100.0;
            int bwLen = Math.Min(BandWidthLength, CurrentBar + 1);
            double sumBW = 0; for (int i = 0; i < bwLen; i++) sumBW += htfBandWidth[i];
            double avgBW = bwLen > 0 ? sumBW / bwLen : 0;
            relativeBandWidth = avgBW > 0 ? bw / avgBW : 1.0;
            isTightRange = relativeBandWidth < TightRangeThreshold;
            isWideRange = relativeBandWidth > WideRangeThreshold;

            // SMI on HTF
            double hh = MAX(High, KLength)[0];
            double ll = MIN(Low, KLength)[0];
            double mid = (hh + ll) / 2.0;
            htfDist[0] = Close[0] - mid;
            htfRange[0] = hh - ll;
            double sDist = EMA(EMA(htfDist, KSmooth1), KSmooth2)[0];
            double sRng = EMA(EMA(htfRange, KSmooth1), KSmooth2)[0];
            double smi = sRng != 0 ? 100.0 * (sDist / (sRng / 2.0)) : 0.0;
            htfSmiSeries[0] = smi;
            _htfSmi = smi;
            _htfSmiSignal = EMA(htfSmiSeries, SignalLength)[0];
            _htfSmiFilter = EMA(htfSmiSeries, FilterLength)[0];

            // MFI-SMI on HTF
            double mfi = htfMfiIndicator[0];
            double mfHh = double.MinValue, mfLl = double.MaxValue;
            int mfLen = Math.Min(MfiSmiK, CurrentBar + 1);
            for (int i = 0; i < mfLen; i++)
            {
                double m = htfMfiIndicator[i];
                if (m > mfHh) mfHh = m;
                if (m < mfLl) mfLl = m;
            }
            double mfMid = (mfHh + mfLl) / 2.0;
            htfMfiDist[0] = mfi - mfMid;
            htfMfiRange[0] = mfHh - mfLl;
            double mfSd = EMA(EMA(htfMfiDist, MfiSmiSmooth1), MfiSmiSmooth2)[0];
            double mfSr = EMA(EMA(htfMfiRange, MfiSmiSmooth1), MfiSmiSmooth2)[0];
            _htfMfiSmi = mfSr != 0 ? 200.0 * (mfSd / mfSr) : 0.0;
        }

        private void WriteBandPlots()
        {
            double vw = _vwmean > 0 ? _vwmean : double.NaN;
            double u2 = _vwmean > 0 ? _upper2Sigma : double.NaN;
            double l2 = _vwmean > 0 ? _lower2Sigma : double.NaN;
            double u3 = _vwmean > 0 ? _upper3Sigma : double.NaN;
            double l3 = _vwmean > 0 ? _lower3Sigma : double.NaN;

            Values[0][0] = ShowVwapLine ? vw : double.NaN;
            Values[1][0] = u2; Values[2][0] = l2; Values[3][0] = u3; Values[4][0] = l3;
            VwapSeries[0] = vw; Upper2Series[0] = u2; Lower2Series[0] = l2;
            Upper3Series[0] = u3; Lower3Series[0] = l3;

            Brush ubc = ShowRangeState ? (isTightRange ? TightRangeColor : (isWideRange ? WideRangeColor : BearishColor)) : BearishColor;
            Brush lbc = ShowRangeState ? (isTightRange ? TightRangeColor : (isWideRange ? WideRangeColor : BullishColor)) : BullishColor;
            Plots[1].Brush = ubc; Plots[2].Brush = lbc; Plots[3].Brush = ubc; Plots[4].Brush = lbc;
        }

        private void RunChartTfSignalLogic()
        {
            // SMI states (from HTF values, evaluated on chart TF)
            bullishTrend = _htfSmiSignal > _htfSmiFilter;
            bearishTrend = _htfSmiSignal < _htfSmiFilter;
            filterRising = _htfSmiFilter > SmiFilterSeries[1];
            filterFalling = _htfSmiFilter < SmiFilterSeries[1];
            signalAboveZero = _htfSmiSignal > 0; signalBelowZero = _htfSmiSignal < 0;
            inOverbought = _htfSmiSignal > ObLevel; inOversold = _htfSmiSignal < OsLevel;
            bsOversold = inOversold ? 0 : bsOversold + 1;
            bsOverbought = inOverbought ? 0 : bsOverbought + 1;
            wasOversold = bsOversold <= 5; wasOverbought = bsOverbought <= 5;

            bullCross = CrossAbove(SmiSignalSeries, SmiFilterSeries, 1);
            bearCross = CrossBelow(SmiSignalSeries, SmiFilterSeries, 1);
            zeroBullCross = CrossAbove(SmiSignalSeries, 0, 1);
            zeroBearCross = CrossBelow(SmiSignalSeries, 0, 1);
            bsBullCross = bullCross ? 0 : bsBullCross + 1;
            bsBearCross = bearCross ? 0 : bsBearCross + 1;
            bullCrossRecent = bsBullCross <= CrossFlexibility;
            bearCrossRecent = bsBearCross <= CrossFlexibility;

            // MFI-SMI confluence (from HTF)
            mfiSmiRising = _htfMfiSmi > MfiSmiSeries[1];
            mfiSmiFalling = _htfMfiSmi < MfiSmiSeries[1];
            mfiSmiAboveZero = _htfMfiSmi > 0; mfiSmiBelowZero = _htfMfiSmi < 0;
            mfiConfirmsBull = mfiSmiAboveZero || mfiSmiRising;
            mfiConfirmsBear = mfiSmiBelowZero || mfiSmiFalling;

            // Divergence (on HTF SMI values vs chart-TF price pivots)
            int divLookback = 5;
            int phBar = PivotHighBar(High, divLookback);
            int plBar = PivotLowBar(Low, divLookback);
            if (phBar >= 0) { prevPriceHigh = currPriceHigh; prevSMIHigh = currSMIHigh; prevHighBar = currHighBar; currPriceHigh = High[phBar]; currSMIHigh = _htfSmi; currHighBar = CurrentBar - phBar; }
            if (plBar >= 0) { prevPriceLow = currPriceLow; prevSMILow = currSMILow; prevLowBar = currLowBar; currPriceLow = Low[plBar]; currSMILow = _htfSmi; currLowBar = CurrentBar - plBar; }
            int barsFromPrevHigh = currHighBar - prevHighBar;
            int barsFromPrevLow = currLowBar - prevLowBar;
            bearishDivergence = phBar >= 0 && currPriceHigh > prevPriceHigh && currSMIHigh < prevSMIHigh && barsFromPrevHigh >= 10 && barsFromPrevHigh <= 50;
            bullishDivergence = plBar >= 0 && currPriceLow < prevPriceLow && currSMILow > prevSMILow && barsFromPrevLow >= 10 && barsFromPrevLow <= 50;
            bsBullDiv = bullishDivergence ? 0 : bsBullDiv + 1;
            bsBearDiv = bearishDivergence ? 0 : bsBearDiv + 1;
            bullishDivRecent = bsBullDiv <= 10; bearishDivRecent = bsBearDiv <= 10;

            int mfPhBar = PivotHighBar(SmiSeries, divLookback);
            int mfPlBar = PivotLowBar(SmiSeries, divLookback);
            if (mfPhBar >= 0) { prevMfiSmiHigh = currMfiSmiHigh; prevMfiSmiHighBar = currMfiSmiHighBar; currMfiSmiHigh = MfiSmiSeries[mfPhBar]; currMfiSmiHighBar = CurrentBar - mfPhBar; }
            if (mfPlBar >= 0) { prevMfiSmiLow = currMfiSmiLow; prevMfiSmiLowBar = currMfiSmiLowBar; currMfiSmiLow = MfiSmiSeries[mfPlBar]; currMfiSmiLowBar = CurrentBar - mfPlBar; }
            int mfBshp = currMfiSmiHighBar - prevMfiSmiHighBar;
            int mfBslp = currMfiSmiLowBar - prevMfiSmiLowBar;
            mfiSmiBearishDiv = mfPhBar >= 0 && currPriceHigh > prevPriceHigh && currMfiSmiHigh < prevMfiSmiHigh && mfBshp > 5 && mfBshp < 50;
            mfiSmiBullishDiv = mfPlBar >= 0 && currPriceLow < prevPriceLow && currMfiSmiLow > prevMfiSmiLow && mfBslp > 5 && mfBslp < 50;
            bsMfiBullDiv = mfiSmiBullishDiv ? 0 : bsMfiBullDiv + 1;
            bsMfiBearDiv = mfiSmiBearishDiv ? 0 : bsMfiBearDiv + 1;
            mfiSmiBullishDivRecent = bsMfiBullDiv <= 10; mfiSmiBearishDivRecent = bsMfiBearDiv <= 10;
            dualBullishDiv = bullishDivergence && mfiSmiBullishDivRecent;
            dualBearishDiv = bearishDivergence && mfiSmiBearishDivRecent;

            // Signal quality
            if (bullCross) { bullSignalQuality = 1; if (wasOversold) bullSignalQuality++; if (signalAboveZero || zeroBullCross) bullSignalQuality++; if (filterRising) bullSignalQuality++; if (UseMFI && mfiConfirmsBull) bullSignalQuality++; if (UseMFI && mfiSmiBullishDivRecent) bullSignalQuality++; if (UseMFI && dualBullishDiv) bullSignalQuality++; }
            else if (bullSignalQuality > 0 && bsBullCross > CrossFlexibility) bullSignalQuality = 0;
            if (bearCross) { bearSignalQuality = 1; if (wasOverbought) bearSignalQuality++; if (signalBelowZero || zeroBearCross) bearSignalQuality++; if (filterFalling) bearSignalQuality++; if (UseMFI && mfiConfirmsBear) bearSignalQuality++; if (UseMFI && mfiSmiBearishDivRecent) bearSignalQuality++; if (UseMFI && dualBearishDiv) bearSignalQuality++; }
            else if (bearSignalQuality > 0 && bsBearCross > CrossFlexibility) bearSignalQuality = 0;

            // Chart-TF filters
            int currentHour = Time[0].Hour;
            isAsian = currentHour >= 21 || currentHour < 8;
            isLondon = currentHour >= 8 && currentHour < 13;
            isNY = currentHour >= 13 && currentHour < 21;
            double avgVol = SMA(Volume, 20)[0];
            volumeQualified = UseVolumeFilter ? Volume[0] >= avgVol * VolumeMultiplier : true;
            double ema21 = EMA(Close, 21)[0], ema50 = EMA(Close, 50)[0], atr20 = ATR(20)[0];
            isTrending = Math.Abs(ema21 - ema50) > atr20 * 1.5;
            trendDirection = ema21 > ema50 ? 1 : -1;
            regimeLongOK = UseMarketRegime ? (!isTrending || (isTrending && trendDirection > 0)) : true;
            regimeShortOK = UseMarketRegime ? (!isTrending || (isTrending && trendDirection < 0)) : true;

            // Range filter
            if (UseRangeFilter) { if (RangeMethod == "Filter Choppy") rangeFilterPass = !isWideRange; else if (RangeMethod == "Range Only") rangeFilterPass = isTightRange; else if (RangeMethod == "Trend Only") rangeFilterPass = isWideRange; else rangeFilterPass = true; }
            else rangeFilterPass = true;

            // Band touches — chart-TF close crosses HTF bands
            if (_vwmean > 0) { upper2Touch = Close[0] >= _upper2Sigma && Close[1] < _upper2Sigma; lower2Touch = Close[0] <= _lower2Sigma && Close[1] > _lower2Sigma; upper3Touch = Close[0] >= _upper3Sigma && Close[1] < _upper3Sigma; lower3Touch = Close[0] <= _lower3Sigma && Close[1] > _lower3Sigma; }
            else { upper2Touch = lower2Touch = upper3Touch = lower3Touch = false; }
            bsUpper2Touch = upper2Touch ? 0 : bsUpper2Touch + 1; bsLower2Touch = lower2Touch ? 0 : bsLower2Touch + 1;
            bsUpper3Touch = upper3Touch ? 0 : bsUpper3Touch + 1; bsLower3Touch = lower3Touch ? 0 : bsLower3Touch + 1;
            atUpperBands = _vwmean > 0 && Close[0] >= _upper2Sigma; atLowerBands = _vwmean > 0 && Close[0] <= _lower2Sigma;
            atUpper3 = _vwmean > 0 && Close[0] >= _upper3Sigma; atLower3 = _vwmean > 0 && Close[0] <= _lower3Sigma;
            nearUpper2 = bsUpper2Touch <= CrossFlexibility || atUpperBands; nearLower2 = bsLower2Touch <= CrossFlexibility || atLowerBands;
            nearUpper3 = bsUpper3Touch <= CrossFlexibility || atUpper3; nearLower3 = bsLower3Touch <= CrossFlexibility || atLower3;

            smiConfirmLong = (bullCrossRecent && bullSignalQuality >= MinSignalQuality) || (bullishTrend && wasOversold) || (inOversold && filterRising);
            smiConfirmShort = (bearCrossRecent && bearSignalQuality >= MinSignalQuality) || (bearishTrend && wasOverbought) || (inOverbought && filterFalling);
            divFilterLong = RequireDivergence ? (bullishDivRecent || mfiSmiBullishDivRecent) : true;
            divFilterShort = RequireDivergence ? (bearishDivRecent || mfiSmiBearishDivRecent) : true;

            rawLongOpportunity = nearLower2 && smiConfirmLong && volumeQualified && regimeLongOK && divFilterLong && rangeFilterPass;
            rawShortOpportunity = nearUpper2 && smiConfirmShort && volumeQualified && regimeShortOK && divFilterShort && rangeFilterPass;
            rawStrongLong = nearLower3 && bullCrossRecent && bullSignalQuality >= 5 && volumeQualified && regimeLongOK && divFilterLong && rangeFilterPass;
            rawStrongShort = nearUpper3 && bearCrossRecent && bearSignalQuality >= 5 && volumeQualified && regimeShortOK && divFilterShort && rangeFilterPass;

            int cooldownBars = CrossFlexibility + 3;
            longOpportunity = rawLongOpportunity && barsSinceLastLong >= cooldownBars;
            shortOpportunity = rawShortOpportunity && barsSinceLastShort >= cooldownBars;
            strongLongOpportunity = rawStrongLong && barsSinceLastStrongLong >= cooldownBars && !longOpportunity;
            strongShortOpportunity = rawStrongShort && barsSinceLastStrongShort >= cooldownBars && !shortOpportunity;
            barsSinceLastLong = (longOpportunity || strongLongOpportunity) ? 0 : barsSinceLastLong + 1;
            barsSinceLastShort = (shortOpportunity || strongShortOpportunity) ? 0 : barsSinceLastShort + 1;
            barsSinceLastStrongLong = strongLongOpportunity ? 0 : barsSinceLastStrongLong + 1;
            barsSinceLastStrongShort = strongShortOpportunity ? 0 : barsSinceLastStrongShort + 1;
            regularLongOpportunity = longOpportunity && !strongLongOpportunity;
            regularShortOpportunity = shortOpportunity && !strongShortOpportunity;

            // Stats
            histIdx = (histIdx + 1) % 6;
            longOppHist[histIdx] = longOpportunity; shortOppHist[histIdx] = shortOpportunity;
            sessionHist[histIdx] = isAsian ? 1 : (isLondon ? 2 : (isNY ? 3 : 0));
            if (longOpportunity || shortOpportunity) { totalOpportunities++; if (ShowSessionStats) { if (isAsian) asianSignals++; else if (isLondon) londonSignals++; else if (isNY) nySignals++; } }
            int prevIdx = (histIdx + 1) % 6;
            if (longOppHist[prevIdx]) { if (MAX(Close, 5)[0] > _vwmean) { successfulTrades++; if (ShowSessionStats) { if (sessionHist[prevIdx] == 1) asianWins++; if (sessionHist[prevIdx] == 2) londonWins++; if (sessionHist[prevIdx] == 3) nyWins++; } } }
            if (shortOppHist[prevIdx]) { if (MIN(Close, 5)[0] < _vwmean) { successfulTrades++; if (ShowSessionStats) { if (sessionHist[prevIdx] == 1) asianWins++; if (sessionHist[prevIdx] == 2) londonWins++; if (sessionHist[prevIdx] == 3) nyWins++; } } }
        }

        private void WriteSignalsAndAlerts()
        {
            if (ShowBandTouches) { if (lower2Touch) Draw.Dot(this, "L2_" + CurrentBar, false, 0, Low[0] - (2 * TickSize), BullishColor); if (upper2Touch) Draw.Dot(this, "U2_" + CurrentBar, false, 0, High[0] + (2 * TickSize), BearishColor); if (lower3Touch) Draw.Diamond(this, "L3_" + CurrentBar, false, 0, Low[0] - (2 * TickSize), BullishColor); if (upper3Touch) Draw.Diamond(this, "U3_" + CurrentBar, false, 0, High[0] + (2 * TickSize), BearishColor); }
            if (ShowSignals && regularLongOpportunity) { string t = "LONG_" + CurrentBar; Draw.ArrowUp(this, t, false, 0, Low[0] - (4 * TickSize), BullishColor); Draw.Text(this, t + "_txt", false, "LONG", 0, Low[0] - (10 * TickSize), 0, BullishColor, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0); }
            if (ShowSignals && regularShortOpportunity) { string t = "SHORT_" + CurrentBar; Draw.ArrowDown(this, t, false, 0, High[0] + (4 * TickSize), BearishColor); Draw.Text(this, t + "_txt", false, "SHORT", 0, High[0] + (10 * TickSize), 0, BearishColor, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0); }
            if (ShowSignals && strongLongOpportunity) { string t = "SLONG_" + CurrentBar; Draw.Diamond(this, t, false, 0, Low[0] - (4 * TickSize), BullishColor); Draw.Text(this, t + "_txt", false, "STRONG LONG", 0, Low[0] - (12 * TickSize), 0, BullishColor, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0); }
            if (ShowSignals && strongShortOpportunity) { string t = "SSHORT_" + CurrentBar; Draw.Diamond(this, t, false, 0, High[0] + (4 * TickSize), BearishColor); Draw.Text(this, t + "_txt", false, "STRONG SHORT", 0, High[0] + (12 * TickSize), 0, BearishColor, new SimpleFont("Arial", 9), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0); }
            if (ShowSmiPanel && CurrentBar == BarsArray[0].Count - 1) Draw.Text(this, "SMI_PANEL", false, BuildSmiPanelText(), 0, High[0] + (20 * TickSize), 0, Brushes.White, new SimpleFont("Arial", 10), System.Windows.TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
            if (ShowWinRate && CurrentBar == BarsArray[0].Count - 1 && totalOpportunities > 0) { int wr = totalOpportunities > 5 ? (int)Math.Round(successfulTrades * 100.0 / totalOpportunities) : 0; int awr = asianSignals > 2 ? (int)Math.Round(asianWins * 100.0 / asianSignals) : 0; int lwr = londonSignals > 2 ? (int)Math.Round(londonWins * 100.0 / londonSignals) : 0; int nwr = nySignals > 2 ? (int)Math.Round(nyWins * 100.0 / nySignals) : 0; Draw.Text(this, "WIN_TABLE", false, BuildWinTableText(wr, awr, lwr, nwr), 0, Low[0] - (20 * TickSize), 0, Brushes.White, new SimpleFont("Arial", 10), System.Windows.TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0); }
            if (EnableAlerts) { if (regularLongOpportunity) Alert("Long", Priority.High, "LONG - VWAP band touch + SMI confirmation", "", 0, Brushes.Transparent, Brushes.Transparent); if (regularShortOpportunity) Alert("Short", Priority.High, "SHORT - VWAP band touch + SMI confirmation", "", 0, Brushes.Transparent, Brushes.Transparent); if (strongLongOpportunity) Alert("StrongLong", Priority.High, "STRONG LONG - 3σ touch + high quality SMI signal", "", 0, Brushes.Transparent, Brushes.Transparent); if (strongShortOpportunity) Alert("StrongShort", Priority.High, "STRONG SHORT - 3σ touch + high quality SMI signal", "", 0, Brushes.Transparent, Brushes.Transparent); if (dualBullishDiv || dualBearishDiv) Alert("DualDiv", Priority.Medium, "DUAL DIVERGENCE", "", 0, Brushes.Transparent, Brushes.Transparent); }
            SignalSeries[0] = regularLongOpportunity ? 1 : (regularShortOpportunity ? -1 : (strongLongOpportunity ? 2 : (strongShortOpportunity ? -2 : 0)));
            LongSignalSeries[0] = regularLongOpportunity ? 1 : 0; ShortSignalSeries[0] = regularShortOpportunity ? 1 : 0;
            StrongLongSignalSeries[0] = strongLongOpportunity ? 1 : 0; StrongShortSignalSeries[0] = strongShortOpportunity ? 1 : 0;
        }

        #region SharpDX Cloud Rendering
        private SharpDX.Direct2D1.Brush CreateFillBrush(SharpDX.Direct2D1.RenderTarget rt, Brush wm, byte a)
        { var s = wm as System.Windows.Media.SolidColorBrush; return s == null ? new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color((int)128, (int)128, (int)128, (int)a)) : new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color((int)s.Color.R, (int)s.Color.G, (int)s.Color.B, (int)a)); }
        public override void OnRenderTargetChanged() { if (upperFillBrush != null) upperFillBrush.Dispose(); if (lowerFillBrush != null) lowerFillBrush.Dispose(); upperFillBrush = lowerFillBrush = null; brushesNeedUpdate = true; }
        private void EnsureBrushes(SharpDX.Direct2D1.RenderTarget rt)
        { if (!brushesNeedUpdate && upperFillBrush != null && lowerFillBrush != null) return; if (upperFillBrush != null) upperFillBrush.Dispose(); if (lowerFillBrush != null) lowerFillBrush.Dispose(); Brush ubc = ShowRangeState ? (isTightRange ? TightRangeColor : (isWideRange ? WideRangeColor : BearishColor)) : BearishColor; Brush lbc = ShowRangeState ? (isTightRange ? TightRangeColor : (isWideRange ? WideRangeColor : BullishColor)) : BullishColor; upperFillBrush = CreateFillBrush(rt, ubc, 50); lowerFillBrush = CreateFillBrush(rt, lbc, 50); brushesNeedUpdate = false; }
        protected override void OnRender(ChartControl cc, ChartScale cs)
        { /* cloud disabled for debugging */ }
        private void RenderCloudBand(SharpDX.Direct2D1.RenderTarget rt, ChartControl cc, ChartScale cs, Series<double> topS, Series<double> botS, SharpDX.Direct2D1.Brush brush, int fi, int li)
        { if (rt == null || brush == null) return; var tp = new List<SharpDX.Vector2>(); var bp = new List<SharpDX.Vector2>(); for (int i = fi; i <= li; i++) { if (i < 0 || i >= Bars.Count) continue; double tv = topS.GetValueAt(i), bv = botS.GetValueAt(i); if (double.IsNaN(tv) || double.IsNaN(bv)) continue; float x = (float)cc.GetXByBarIndex(ChartBars, i); tp.Add(new SharpDX.Vector2(x, (float)cs.GetYByValue(tv))); bp.Add(new SharpDX.Vector2(x, (float)cs.GetYByValue(bv))); } if (tp.Count < 2) return; using (var g = new SharpDX.Direct2D1.PathGeometry(Core.Globals.D2DFactory)) using (var s = g.Open()) { s.SetFillMode(SharpDX.Direct2D1.FillMode.Winding); s.BeginFigure(tp[0], SharpDX.Direct2D1.FigureBegin.Filled); for (int i = 1; i < tp.Count; i++) s.AddLine(tp[i]); for (int i = bp.Count - 1; i >= 0; i--) s.AddLine(bp[i]); s.EndFigure(SharpDX.Direct2D1.FigureEnd.Closed); s.Close(); rt.FillGeometry(g, brush); } }
        #endregion

        #region Pivot helpers
        private int PivotHighBar(ISeries<double> src, int lb) { int rb = lb; if (CurrentBar < lb + rb) return -1; int pi = lb; double pv = src[pi]; for (int i = 0; i <= lb + rb; i++) { if (i == pi) continue; if (src[i] >= pv) return -1; } return pi; }
        private int PivotLowBar(ISeries<double> src, int lb) { int rb = lb; if (CurrentBar < lb + rb) return -1; int pi = lb; double pv = src[pi]; for (int i = 0; i <= lb + rb; i++) { if (i == pi) continue; if (src[i] <= pv) return -1; } return pi; }
        #endregion

        private string BuildSmiPanelText()
        { string t = bullishTrend ? "▲" : "▼"; string z = signalAboveZero ? "+" : "−"; string zo = inOverbought ? "OB" : (inOversold ? "OS" : "—"); string r = isTightRange ? "TIGHT" : (isWideRange ? "WIDE" : "NORMAL"); string txt = "SMI: " + t + " " + z + "\nZone: " + zo + "\nRange: " + r + " " + relativeBandWidth.ToString("0.##") + "x"; if (UseMFI) { string md = mfiSmiRising ? "▲" : (mfiSmiFalling ? "▼" : "—"); string mz = mfiSmiAboveZero ? "+" : "−"; string df = (dualBullishDiv || dualBearishDiv) ? " D²" : (mfiSmiBullishDivRecent ? " D+" : (mfiSmiBearishDivRecent ? " D−" : "")); txt += "\nVol: " + md + mz + df; } int qs = bullCrossRecent ? bullSignalQuality : (bearCrossRecent ? bearSignalQuality : 0); if (qs > 0) { string q = ""; for (int i = 1; i <= 7; i++) q += (i <= qs ? "●" : "○"); txt += "\nSig: " + (bullCrossRecent ? "▲" : "▼") + " " + q; } return txt; }

        private string BuildWinTableText(int wr, int awr, int lwr, int nwr)
        { string t = "VWAP+SMI Stats\nWin Rate: " + wr + "%\nSignals: " + successfulTrades + "/" + totalOpportunities; if (UseMarketRegime) t += "\nMarket: " + (isTrending ? (trendDirection > 0 ? "BULL" : "BEAR") : "RANGE"); if (ShowSessionStats) { string cs = isAsian ? "ASIAN" : (isLondon ? "LONDON" : "NEW YORK"); t += "\nCurrent: " + cs + "\nAsian: " + awr + "% (" + asianSignals + ")\nLondon: " + lwr + "% (" + londonSignals + ")\nNY: " + nwr + "% (" + nySignals + ")"; } return t; }
    }
}

#region NinjaScript Generated Code
namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private Vinay.VWAPSMIHybrid[] cacheVWAPSMIHybrid;
        public Vinay.VWAPSMIHybrid VWAPSMIHybrid(bool logSpaceScaling, int vwapLength, double dev2Mult, double dev3Mult, int vwapTimeframe, BarsPeriodType vwapTimeframeType, int kLength, int kSmooth1, int kSmooth2, int signalLength, int filterLength, double obLevel, double osLevel, int crossFlexibility, bool useMFI, int mfiLength, int mfiSmiK, int mfiSmiSmooth1, int mfiSmiSmooth2, int minSignalQuality, bool useVolumeFilter, double volumeMultiplier, bool useMarketRegime, bool useRangeFilter, string rangeMethod, int bandWidthLength, double tightRangeThreshold, double wideRangeThreshold, bool showRangeState, bool showSessionStats, bool requireDivergence, bool showVwapLine, bool fillBands, bool showSignals, bool showBandTouches, bool showWinRate, bool showSmiPanel, Brush bullishColor, Brush bearishColor, Brush tightRangeColor, Brush wideRangeColor, bool enableAlerts)
        { return VWAPSMIHybrid(Input, logSpaceScaling, vwapLength, dev2Mult, dev3Mult, vwapTimeframe, vwapTimeframeType, kLength, kSmooth1, kSmooth2, signalLength, filterLength, obLevel, osLevel, crossFlexibility, useMFI, mfiLength, mfiSmiK, mfiSmiSmooth1, mfiSmiSmooth2, minSignalQuality, useVolumeFilter, volumeMultiplier, useMarketRegime, useRangeFilter, rangeMethod, bandWidthLength, tightRangeThreshold, wideRangeThreshold, showRangeState, showSessionStats, requireDivergence, showVwapLine, fillBands, showSignals, showBandTouches, showWinRate, showSmiPanel, bullishColor, bearishColor, tightRangeColor, wideRangeColor, enableAlerts); }
        public Vinay.VWAPSMIHybrid VWAPSMIHybrid(ISeries<double> input, bool logSpaceScaling, int vwapLength, double dev2Mult, double dev3Mult, int vwapTimeframe, BarsPeriodType vwapTimeframeType, int kLength, int kSmooth1, int kSmooth2, int signalLength, int filterLength, double obLevel, double osLevel, int crossFlexibility, bool useMFI, int mfiLength, int mfiSmiK, int mfiSmiSmooth1, int mfiSmiSmooth2, int minSignalQuality, bool useVolumeFilter, double volumeMultiplier, bool useMarketRegime, bool useRangeFilter, string rangeMethod, int bandWidthLength, double tightRangeThreshold, double wideRangeThreshold, bool showRangeState, bool showSessionStats, bool requireDivergence, bool showVwapLine, bool fillBands, bool showSignals, bool showBandTouches, bool showWinRate, bool showSmiPanel, Brush bullishColor, Brush bearishColor, Brush tightRangeColor, Brush wideRangeColor, bool enableAlerts)
        {
            if (cacheVWAPSMIHybrid != null) for (int idx = 0; idx < cacheVWAPSMIHybrid.Length; idx++) if (cacheVWAPSMIHybrid[idx] != null && cacheVWAPSMIHybrid[idx].LogSpaceScaling == logSpaceScaling && cacheVWAPSMIHybrid[idx].VwapLength == vwapLength && cacheVWAPSMIHybrid[idx].Dev2Mult == dev2Mult && cacheVWAPSMIHybrid[idx].Dev3Mult == dev3Mult && cacheVWAPSMIHybrid[idx].VwapTimeframe == vwapTimeframe && cacheVWAPSMIHybrid[idx].VwapTimeframeType == vwapTimeframeType && cacheVWAPSMIHybrid[idx].KLength == kLength && cacheVWAPSMIHybrid[idx].KSmooth1 == kSmooth1 && cacheVWAPSMIHybrid[idx].KSmooth2 == kSmooth2 && cacheVWAPSMIHybrid[idx].SignalLength == signalLength && cacheVWAPSMIHybrid[idx].FilterLength == filterLength && cacheVWAPSMIHybrid[idx].ObLevel == obLevel && cacheVWAPSMIHybrid[idx].OsLevel == osLevel && cacheVWAPSMIHybrid[idx].CrossFlexibility == crossFlexibility && cacheVWAPSMIHybrid[idx].UseMFI == useMFI && cacheVWAPSMIHybrid[idx].MfiLength == mfiLength && cacheVWAPSMIHybrid[idx].MfiSmiK == mfiSmiK && cacheVWAPSMIHybrid[idx].MfiSmiSmooth1 == mfiSmiSmooth1 && cacheVWAPSMIHybrid[idx].MfiSmiSmooth2 == mfiSmiSmooth2 && cacheVWAPSMIHybrid[idx].MinSignalQuality == minSignalQuality && cacheVWAPSMIHybrid[idx].UseVolumeFilter == useVolumeFilter && cacheVWAPSMIHybrid[idx].VolumeMultiplier == volumeMultiplier && cacheVWAPSMIHybrid[idx].UseMarketRegime == useMarketRegime && cacheVWAPSMIHybrid[idx].UseRangeFilter == useRangeFilter && cacheVWAPSMIHybrid[idx].RangeMethod == rangeMethod && cacheVWAPSMIHybrid[idx].BandWidthLength == bandWidthLength && cacheVWAPSMIHybrid[idx].TightRangeThreshold == tightRangeThreshold && cacheVWAPSMIHybrid[idx].WideRangeThreshold == wideRangeThreshold && cacheVWAPSMIHybrid[idx].ShowRangeState == showRangeState && cacheVWAPSMIHybrid[idx].ShowSessionStats == showSessionStats && cacheVWAPSMIHybrid[idx].RequireDivergence == requireDivergence && cacheVWAPSMIHybrid[idx].ShowVwapLine == showVwapLine && cacheVWAPSMIHybrid[idx].FillBands == fillBands && cacheVWAPSMIHybrid[idx].ShowSignals == showSignals && cacheVWAPSMIHybrid[idx].ShowBandTouches == showBandTouches && cacheVWAPSMIHybrid[idx].ShowWinRate == showWinRate && cacheVWAPSMIHybrid[idx].ShowSmiPanel == showSmiPanel && cacheVWAPSMIHybrid[idx].BullishColor == bullishColor && cacheVWAPSMIHybrid[idx].BearishColor == bearishColor && cacheVWAPSMIHybrid[idx].TightRangeColor == tightRangeColor && cacheVWAPSMIHybrid[idx].WideRangeColor == wideRangeColor && cacheVWAPSMIHybrid[idx].EnableAlerts == enableAlerts && cacheVWAPSMIHybrid[idx].EqualsInput(input)) return cacheVWAPSMIHybrid[idx];
            return CacheIndicator<Vinay.VWAPSMIHybrid>(new Vinay.VWAPSMIHybrid() { LogSpaceScaling = logSpaceScaling, VwapLength = vwapLength, Dev2Mult = dev2Mult, Dev3Mult = dev3Mult, VwapTimeframe = vwapTimeframe, VwapTimeframeType = vwapTimeframeType, KLength = kLength, KSmooth1 = kSmooth1, KSmooth2 = kSmooth2, SignalLength = signalLength, FilterLength = filterLength, ObLevel = obLevel, OsLevel = osLevel, CrossFlexibility = crossFlexibility, UseMFI = useMFI, MfiLength = mfiLength, MfiSmiK = mfiSmiK, MfiSmiSmooth1 = mfiSmiSmooth1, MfiSmiSmooth2 = mfiSmiSmooth2, MinSignalQuality = minSignalQuality, UseVolumeFilter = useVolumeFilter, VolumeMultiplier = volumeMultiplier, UseMarketRegime = useMarketRegime, UseRangeFilter = useRangeFilter, RangeMethod = rangeMethod, BandWidthLength = bandWidthLength, TightRangeThreshold = tightRangeThreshold, WideRangeThreshold = wideRangeThreshold, ShowRangeState = showRangeState, ShowSessionStats = showSessionStats, RequireDivergence = requireDivergence, ShowVwapLine = showVwapLine, FillBands = fillBands, ShowSignals = showSignals, ShowBandTouches = showBandTouches, ShowWinRate = showWinRate, ShowSmiPanel = showSmiPanel, BullishColor = bullishColor, BearishColor = bearishColor, TightRangeColor = tightRangeColor, WideRangeColor = wideRangeColor, EnableAlerts = enableAlerts }, input, ref cacheVWAPSMIHybrid);
        }
    }
}
namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.Vinay.VWAPSMIHybrid VWAPSMIHybrid(bool logSpaceScaling, int vwapLength, double dev2Mult, double dev3Mult, int vwapTimeframe, BarsPeriodType vwapTimeframeType, int kLength, int kSmooth1, int kSmooth2, int signalLength, int filterLength, double obLevel, double osLevel, int crossFlexibility, bool useMFI, int mfiLength, int mfiSmiK, int mfiSmiSmooth1, int mfiSmiSmooth2, int minSignalQuality, bool useVolumeFilter, double volumeMultiplier, bool useMarketRegime, bool useRangeFilter, string rangeMethod, int bandWidthLength, double tightRangeThreshold, double wideRangeThreshold, bool showRangeState, bool showSessionStats, bool requireDivergence, bool showVwapLine, bool fillBands, bool showSignals, bool showBandTouches, bool showWinRate, bool showSmiPanel, Brush bullishColor, Brush bearishColor, Brush tightRangeColor, Brush wideRangeColor, bool enableAlerts)
        { return indicator.VWAPSMIHybrid(Input, logSpaceScaling, vwapLength, dev2Mult, dev3Mult, vwapTimeframe, vwapTimeframeType, kLength, kSmooth1, kSmooth2, signalLength, filterLength, obLevel, osLevel, crossFlexibility, useMFI, mfiLength, mfiSmiK, mfiSmiSmooth1, mfiSmiSmooth2, minSignalQuality, useVolumeFilter, volumeMultiplier, useMarketRegime, useRangeFilter, rangeMethod, bandWidthLength, tightRangeThreshold, wideRangeThreshold, showRangeState, showSessionStats, requireDivergence, showVwapLine, fillBands, showSignals, showBandTouches, showWinRate, showSmiPanel, bullishColor, bearishColor, tightRangeColor, wideRangeColor, enableAlerts); }
        public Indicators.Vinay.VWAPSMIHybrid VWAPSMIHybrid(ISeries<double> input, bool logSpaceScaling, int vwapLength, double dev2Mult, double dev3Mult, int vwapTimeframe, BarsPeriodType vwapTimeframeType, int kLength, int kSmooth1, int kSmooth2, int signalLength, int filterLength, double obLevel, double osLevel, int crossFlexibility, bool useMFI, int mfiLength, int mfiSmiK, int mfiSmiSmooth1, int mfiSmiSmooth2, int minSignalQuality, bool useVolumeFilter, double volumeMultiplier, bool useMarketRegime, bool useRangeFilter, string rangeMethod, int bandWidthLength, double tightRangeThreshold, double wideRangeThreshold, bool showRangeState, bool showSessionStats, bool requireDivergence, bool showVwapLine, bool fillBands, bool showSignals, bool showBandTouches, bool showWinRate, bool showSmiPanel, Brush bullishColor, Brush bearishColor, Brush tightRangeColor, Brush wideRangeColor, bool enableAlerts)
        { return indicator.VWAPSMIHybrid(input, logSpaceScaling, vwapLength, dev2Mult, dev3Mult, vwapTimeframe, vwapTimeframeType, kLength, kSmooth1, kSmooth2, signalLength, filterLength, obLevel, osLevel, crossFlexibility, useMFI, mfiLength, mfiSmiK, mfiSmiSmooth1, mfiSmiSmooth2, minSignalQuality, useVolumeFilter, volumeMultiplier, useMarketRegime, useRangeFilter, rangeMethod, bandWidthLength, tightRangeThreshold, wideRangeThreshold, showRangeState, showSessionStats, requireDivergence, showVwapLine, fillBands, showSignals, showBandTouches, showWinRate, showSmiPanel, bullishColor, bearishColor, tightRangeColor, wideRangeColor, enableAlerts); }
    }
}
#endregion