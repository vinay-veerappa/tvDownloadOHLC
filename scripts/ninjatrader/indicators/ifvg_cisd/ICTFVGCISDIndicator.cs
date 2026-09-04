#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
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
using Vinay.Ict;
#endregion

// =============================================================================
// ICTFVGCISDIndicator — COMPOSITE indicator over the ICT engines.
//
// ARCHITECTURE (docs/architecture/NT8_STRATEGY_OWNERSHIP.md + ICT_ENGINE_DESIGN):
//   Detection lives in shared/ict/ engines (parity ports of scripts/libs_py
//   trackers) — one Python tracker per engine, one parity unit each. This
//   indicator ONLY: feeds 5m bars, applies strategy gates (session/sweep/
//   HTF-EMA from the shared manifest), exposes Series for the bot, draws.
//
//   Replaces the pre-2026-09 indicator whose `Variant` parameter was dead
//   (all variants ran an identical close-cross reversal).
// =============================================================================
namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    public class ICTFVGCISDIndicator : Indicator
    {
        #region Custom Parameters
        [NinjaScriptProperty]
        [Display(Name = "Strategy Variant (0=Baseline, 1=V1, 2=V2)", Order = 0, GroupName = "1. Strategy Variant")]
        [Range(0, 2)]
        public int Variant { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Entry Mode (0=Market, 1=CISD Limit)", Order = 1, GroupName = "1. Strategy Variant")]
        [Range(0, 1)]
        public int EntryMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop Loss Type (0=BpsStat,1=Struct,2=StructCapped,3=SkipOOB)", Order = 2, GroupName = "1. Strategy Variant")]
        [Range(0, 3)]
        public int StopLossType { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use HTF Orderflow Filter", Order = 3, GroupName = "1. Strategy Variant")]
        public bool UseHtfFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Filter NY Lunch (11:30-13:30)", Order = 4, GroupName = "1. Strategy Variant")]
        public bool FilterLunch { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Require External Liquidity Sweep", Order = 5, GroupName = "1. Strategy Variant")]
        public bool RequireExternalSweep { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Queen Target (Bps)", Order = 6, GroupName = "2. Targets & Risk")]
        public double QueenTargetBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Runner Target (Bps)", Order = 7, GroupName = "2. Targets & Risk")]
        public double RunnerTargetBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop Loss (Bps, for BpsStat/StructCapped)", Order = 8, GroupName = "2. Targets & Risk")]
        public double StopLossBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min Risk Floor (Bps)", Order = 9, GroupName = "2. Targets & Risk")]
        public double MinRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Risk Ceiling (Bps)", Order = 10, GroupName = "2. Targets & Risk")]
        public double MaxRiskBps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable 50% Midline Reclaims", Order = 11, GroupName = "3. Midline Features")]
        public bool EnableMidlineReclaims { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Visual Elements", Order = 12, GroupName = "4. Visuals")]
        public bool ShowVisualElements { get; set; }

        [NinjaScriptProperty]
        [Range(10, 10000)]
        [Display(Name = "HTF EMA Period", Order = 13, GroupName = "1. Strategy Variant")]
        public int HtfEmaPeriod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Diag CSV Path (empty = off; enables parity runner)", Order = 14, GroupName = "5. Diagnostics")]
        public string DiagCsvPath { get; set; }
        #endregion

        #region Exported Series
        [Browsable(false)][XmlIgnore] public Series<int> SignalSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> StopLossSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> QueenTargetSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> RunnerTargetSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> CisdLevelSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> LimitPriceSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<double> ActiveMidlineSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> CisdStateSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> CisdEventSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> FvgEventSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> IfvgEventSeries { get; private set; }
        [Browsable(false)][XmlIgnore] public Series<int> BprEventSeries { get; private set; }
        #endregion

        // ── The engines (shared/ict/) ──
        private IctCisdEngine _cisd;
        private IctFvgEngine _fvg;
        private IctIfvgEngine _ifvg;
        private IctBprEngine _bpr;
        private IctCisdReversalSetup _setup;

        private EMA htfEma;
        private StreamWriter _diagCsv;

        // armed-level memory (previous bar end — the Python kernel's [i-1] arrays)
        private double _prevEndBull = double.NaN;
        private double _prevEndBear = double.NaN;

        // Session midline state (visual/confluence only)
        private double curAsiaH, curAsiaL, lastAsiaH, lastAsiaL, asiaMid;
        private double curLondonH, curLondonL, lastLondonH, lastLondonL, londonMid;
        private double curP12H, curP12L, lastP12H, lastP12L, p12Mid;
        private double curNyAmH, curNyAmL, lastNyAmH, lastNyAmL;
        private double prevDayH, prevDayL, prevDayMid;
        private DateTime curTradingDate;

        // HTF liquidity sweep pools
        private readonly List<double> bullFvgTops = new List<double>();
        private readonly List<double> bullFvgBots = new List<double>();
        private readonly List<double> bearFvgTops = new List<double>();
        private readonly List<double> bearFvgBots = new List<double>();

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "ICT CISD/FVG/iFVG/BPR composite (parity engines) with variant signals.";
                Name = "ICTFVGCISDIndicator";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;

                // Defaults from the SHARED MANIFEST (IfvgCisdConfig.cs — auto-generated
                // from configs/strategies/ifvg_cisd.yaml). Never hand-tune here.
                Variant = IfvgCisdConfig.Variant;
                EntryMode = IfvgCisdConfig.EntryMode;
                StopLossType = IfvgCisdConfig.StopLossTypeId;
                UseHtfFilter = IfvgCisdConfig.UseHtfFilter;
                HtfEmaPeriod = IfvgCisdConfig.HtfEmaPeriod;
                FilterLunch = IfvgCisdConfig.LunchFilterEnabled;
                RequireExternalSweep = IfvgCisdConfig.RequireExternalSweep;
                QueenTargetBps = IfvgCisdConfig.QueenTargetBps;
                RunnerTargetBps = IfvgCisdConfig.RunnerTargetBps;
                StopLossBps = IfvgCisdConfig.StopLossBps;
                MinRiskBps = IfvgCisdConfig.MinRiskBps;
                MaxRiskBps = IfvgCisdConfig.MaxRiskBps;
                EnableMidlineReclaims = IfvgCisdConfig.EnableMidlineReclaims;
                ShowVisualElements = true;
                DiagCsvPath = "";
            }
            else if (State == State.Configure)
            {
                AddPlot(new Stroke(Brushes.DodgerBlue, 2), PlotStyle.Line, "ActiveCISDLevel");
                AddPlot(new Stroke(Brushes.DarkOrange, DashStyleHelper.Dash, 1), PlotStyle.Line, "SessionMidline");
            }
            else if (State == State.DataLoaded)
            {
                htfEma = EMA(HtfEmaPeriod > 0 ? HtfEmaPeriod : 2400);
                SignalSeries = new Series<int>(this);
                StopLossSeries = new Series<double>(this);
                QueenTargetSeries = new Series<double>(this);
                RunnerTargetSeries = new Series<double>(this);
                CisdLevelSeries = new Series<double>(this);
                LimitPriceSeries = new Series<double>(this);
                ActiveMidlineSeries = new Series<double>(this);
                CisdStateSeries = new Series<int>(this);
                CisdEventSeries = new Series<int>(this);
                FvgEventSeries = new Series<int>(this);
                IfvgEventSeries = new Series<int>(this);
                BprEventSeries = new Series<int>(this);

                _cisd = new IctCisdEngine();
                _fvg = new IctFvgEngine
                {
                    IncludeVi = true,
                    RequireDirectional = IfvgCisdConfig.RequireDirectionalCandle,
                };
                _ifvg = new IctIfvgEngine
                {
                    IncludeVi = true,
                    RequireDirectional = IfvgCisdConfig.RequireDirectionalCandle,
                };
                _bpr = new IctBprEngine
                {
                    IncludeVi = true,
                    RequireDirectional = IfvgCisdConfig.RequireDirectionalCandle,
                };
                _setup = new IctCisdReversalSetup
                {
                    Variant = Variant,
                    TickSize = TickSize,
                    MinRiskBps = MinRiskBps,
                    MaxRiskBps = MaxRiskBps,
                    StopLossType = StopLossType,
                    StopLossBps = StopLossBps,
                    EntryMechanism = EntryMode,
                };

                if (!string.IsNullOrWhiteSpace(DiagCsvPath))
                {
                    try
                    {
                        _diagCsv = new StreamWriter(DiagCsvPath, false);
                        _diagCsv.WriteLine("BarCloseTime,Open,High,Low,Close,CisdEvent,CisdState,"
                            + "ActiveBullLevel,ActiveBearLevel,FvgEvent,FvgTop,FvgBottom,"
                            + "IfvgEvent,BprEvent,Signal,EntryPrice,StopPrice,RiskPts,Variant");
                    }
                    catch (Exception ex)
                    {
                        Print("[ICTFVGCISDIndicator] diag CSV open failed: " + ex.Message);
                        _diagCsv = null;
                    }
                }

                curAsiaH = curAsiaL = lastAsiaH = lastAsiaL = asiaMid = double.NaN;
                curLondonH = curLondonL = lastLondonH = lastLondonL = londonMid = double.NaN;
                curP12H = curP12L = lastP12H = lastP12L = p12Mid = double.NaN;
                curNyAmH = curNyAmL = lastNyAmH = lastNyAmL = double.NaN;
                prevDayH = prevDayL = prevDayMid = double.NaN;
                curTradingDate = DateTime.MinValue;
                _prevEndBull = double.NaN;
                _prevEndBear = double.NaN;
            }
            else if (State == State.Terminated)
            {
                if (_diagCsv != null)
                {
                    try { _diagCsv.Flush(); _diagCsv.Dispose(); } catch { }
                    _diagCsv = null;
                }
            }
        }

        private void UpdateSessionMidlines(double h0, double l0, DateTime barTime)
        {
            int hhmm = ToTime(barTime) / 100;

            if (barTime.Date != curTradingDate)
            {
                if (curTradingDate != DateTime.MinValue)
                {
                    prevDayH = High[1];
                    prevDayL = Low[1];
                    for (int k = 1; k <= Math.Min(400, CurrentBar); k++)
                    {
                        if (Time[k].Date == curTradingDate)
                        {
                            prevDayH = Math.Max(prevDayH, High[k]);
                            prevDayL = Math.Min(prevDayL, Low[k]);
                        }
                    }
                    prevDayMid = (prevDayH + prevDayL) / 2.0;
                }
                curTradingDate = barTime.Date;
            }

            if (hhmm == 1800)
            {
                curAsiaH = h0; curAsiaL = l0;
                curP12H = h0; curP12L = l0;
            }
            else if (hhmm > 1800 || hhmm < 200)
            {
                curAsiaH = double.IsNaN(curAsiaH) ? h0 : Math.Max(curAsiaH, h0);
                curAsiaL = double.IsNaN(curAsiaL) ? l0 : Math.Min(curAsiaL, l0);
                curP12H = double.IsNaN(curP12H) ? h0 : Math.Max(curP12H, h0);
                curP12L = double.IsNaN(curP12L) ? l0 : Math.Min(curP12L, l0);
            }
            else if (hhmm == 200)
            {
                lastAsiaH = curAsiaH; lastAsiaL = curAsiaL;
                if (!double.IsNaN(lastAsiaH) && !double.IsNaN(lastAsiaL)) asiaMid = (lastAsiaH + lastAsiaL) / 2.0;
                curLondonH = h0; curLondonL = l0;
                curP12H = double.IsNaN(curP12H) ? h0 : Math.Max(curP12H, h0);
                curP12L = double.IsNaN(curP12L) ? l0 : Math.Min(curP12L, l0);
            }
            else if (hhmm > 200 && hhmm < 600)
            {
                curLondonH = double.IsNaN(curLondonH) ? h0 : Math.Max(curLondonH, h0);
                curLondonL = double.IsNaN(curLondonL) ? l0 : Math.Min(curLondonL, l0);
                curP12H = double.IsNaN(curP12H) ? h0 : Math.Max(curP12H, h0);
                curP12L = double.IsNaN(curP12L) ? l0 : Math.Min(curP12L, l0);
            }
            else if (hhmm == 600)
            {
                lastP12H = curP12H; lastP12L = curP12L;
                if (!double.IsNaN(lastP12H) && !double.IsNaN(lastP12L)) p12Mid = (lastP12H + lastP12L) / 2.0;
                curLondonH = double.IsNaN(curLondonH) ? h0 : Math.Max(curLondonH, h0);
                curLondonL = double.IsNaN(curLondonL) ? l0 : Math.Min(curLondonL, l0);
            }
            else if (hhmm > 600 && hhmm < 800)
            {
                curLondonH = double.IsNaN(curLondonH) ? h0 : Math.Max(curLondonH, h0);
                curLondonL = double.IsNaN(curLondonL) ? l0 : Math.Min(curLondonL, l0);
            }
            else if (hhmm == 800)
            {
                lastLondonH = curLondonH; lastLondonL = curLondonL;
                if (!double.IsNaN(lastLondonH) && !double.IsNaN(lastLondonL)) londonMid = (lastLondonH + lastLondonL) / 2.0;
            }

            if (hhmm == 930) { curNyAmH = h0; curNyAmL = l0; }
            else if (hhmm > 930 && hhmm <= 1000)
            {
                curNyAmH = double.IsNaN(curNyAmH) ? h0 : Math.Max(curNyAmH, h0);
                curNyAmL = double.IsNaN(curNyAmL) ? l0 : Math.Min(curNyAmL, l0);
            }
            else if (hhmm > 1000) { lastNyAmH = curNyAmH; lastNyAmL = curNyAmL; }
        }

        #region Sweep helpers
        private bool CheckRejectionSweepBull(double level, int lookback)
        {
            if (double.IsNaN(level) || level <= 0) return false;
            int maxK = Math.Min(lookback, CurrentBar);
            for (int k = 0; k <= maxK; k++)
                if (Low[k] <= level && Close[k] > level) return true;
            return false;
        }

        private bool CheckRejectionSweepBear(double level, int lookback)
        {
            if (double.IsNaN(level) || level <= 0) return false;
            int maxK = Math.Min(lookback, CurrentBar);
            for (int k = 0; k <= maxK; k++)
                if (High[k] >= level && Close[k] < level) return true;
            return false;
        }

        private bool CheckFvgTapBull(int lookback)
        {
            if (bullFvgTops.Count == 0) return false;
            int maxK = Math.Min(lookback, CurrentBar);
            for (int k = 0; k <= maxK; k++)
                for (int f = 0; f < bullFvgTops.Count; f++)
                    if (Low[k] <= bullFvgTops[f] && Low[k] >= bullFvgBots[f]) return true;
            return false;
        }

        private bool CheckFvgTapBear(int lookback)
        {
            if (bearFvgTops.Count == 0) return false;
            int maxK = Math.Min(lookback, CurrentBar);
            for (int k = 0; k <= maxK; k++)
                for (int f = 0; f < bearFvgTops.Count; f++)
                    if (High[k] >= bearFvgBots[f] && High[k] <= bearFvgTops[f]) return true;
            return false;
        }
        #endregion

        protected override void OnBarUpdate()
        {
            double o0 = Open[0], h0 = High[0], l0 = Low[0], c0 = Close[0];
            int hhmm = ToTime(Time[0]) / 100;

            UpdateSessionMidlines(h0, l0, Time[0]);

            double activeMid = !double.IsNaN(londonMid) ? londonMid
                             : (!double.IsNaN(p12Mid) ? p12Mid : prevDayMid);
            ActiveMidlineSeries[0] = activeMid;
            Values[1][0] = activeMid;

            // sweep-filter FVG pools (rolling 50)
            bool isBullFvg = l0 > (CurrentBar >= 2 ? High[2] : h0);
            bool isBearFvg = h0 < (CurrentBar >= 2 ? Low[2] : l0);
            if (isBullFvg)
            {
                bullFvgTops.Add(l0); bullFvgBots.Add(CurrentBar >= 2 ? High[2] : h0);
                if (bullFvgTops.Count > 50) { bullFvgTops.RemoveAt(0); bullFvgBots.RemoveAt(0); }
            }
            if (isBearFvg)
            {
                bearFvgTops.Add(CurrentBar >= 2 ? Low[2] : l0); bearFvgBots.Add(h0);
                if (bearFvgTops.Count > 50) { bearFvgTops.RemoveAt(0); bearFvgBots.RemoveAt(0); }
            }

            // ── Feed the engines (all detection happens in shared/ict/) ─────
            double prevBull = _prevEndBull, prevBear = _prevEndBear;
            int ce = _cisd.OnBar(o0, h0, l0, c0);
            var fvgRes = _fvg.OnBar(o0, h0, l0, c0);
            var ifvgRes = _ifvg.OnBar(o0, h0, l0, c0);
            var bprRes = _bpr.OnBar(o0, h0, l0, c0);

            // armed levels at THIS bar's end (Python: arrays at [i])
            double endBull = _cisd.State == 1 ? _cisd.ActiveLevel : double.NaN;
            double endBear = _cisd.State == -1 ? _cisd.ActiveLevel : double.NaN;

            _setup.PushEngineEvents(ce, _cisd.State,
                fvgRes.Event,
                fvgRes.Event != 0 ? fvgRes.Top : double.NaN,
                fvgRes.Event != 0 ? fvgRes.Bottom : double.NaN,
                ifvgRes.Event, bprRes.Event,
                prevBull, prevBear, endBull, endBear, o0);
            var st = _setup.OnBar(o0, h0, l0, c0);

            _prevEndBull = endBull;
            _prevEndBear = endBear;

            CisdEventSeries[0] = ce;
            CisdStateSeries[0] = _cisd.State;
            FvgEventSeries[0] = fvgRes.Event;
            IfvgEventSeries[0] = ifvgRes.Event;
            BprEventSeries[0] = bprRes.Event;

            double activeLevel = _cisd.State == 1 ? endBull : (_cisd.State == -1 ? endBear : double.NaN);
            CisdLevelSeries[0] = activeLevel;
            Values[0][0] = activeLevel;

            // ── Strategy gates (manifest-driven) ─────────────────────────────
            bool inLunch = FilterLunch && (hhmm >= IfvgCisdConfig.LunchStartHHMM && hhmm <= IfvgCisdConfig.LunchEndHHMM);
            bool inWindow = hhmm >= IfvgCisdConfig.EarliestEntryHHMM && hhmm <= IfvgCisdConfig.LatestEntryHHMM;

            bool hasExtSweepBull = CheckRejectionSweepBull(prevDayL, 8)
                || CheckRejectionSweepBull(lastLondonL, 8)
                || CheckRejectionSweepBull(lastAsiaL, 8)
                || CheckRejectionSweepBull(lastNyAmL, 8)
                || CheckFvgTapBull(8);
            bool hasExtSweepBear = CheckRejectionSweepBear(prevDayH, 8)
                || CheckRejectionSweepBear(lastLondonH, 8)
                || CheckRejectionSweepBear(lastAsiaH, 8)
                || CheckRejectionSweepBear(lastNyAmH, 8)
                || CheckFvgTapBear(8);

            int signal = st.Signal;
            double stopLoss = st.StopPrice;
            double effectiveEntry = st.EntryPrice;
            double limitPrice = double.NaN;

            if (signal != 0)
            {
                if (!inWindow || inLunch) signal = 0;
                else if (UseHtfFilter && signal == 1 && c0 < htfEma[0]) signal = 0;
                else if (UseHtfFilter && signal == -1 && c0 > htfEma[0]) signal = 0;
                else if (RequireExternalSweep && signal == 1 && !hasExtSweepBull) signal = 0;
                else if (RequireExternalSweep && signal == -1 && !hasExtSweepBear) signal = 0;
                else if (EntryMode == 1
                         && !double.IsNaN(st.EntryPrice)
                         && ((signal == 1 && st.EntryPrice < c0) || (signal == -1 && st.EntryPrice > c0)))
                    limitPrice = st.EntryPrice;
            }

            // Baseline variant: regime + same-bar IFVG event (Python strict mode)
            if (Variant == 0 && st.Signal == 0 && ifvgRes.Event != 0 && _cisd.State != 0)
            {
                int bsig = (_cisd.State == 1 && ifvgRes.Event == 1) ? 1
                         : (_cisd.State == -1 && ifvgRes.Event == -1) ? -1 : 0;
                if (bsig != 0 && inWindow && !inLunch)
                {
                    if (UseHtfFilter && bsig == 1 && c0 < htfEma[0]) bsig = 0;
                    else if (UseHtfFilter && bsig == -1 && c0 > htfEma[0]) bsig = 0;
                }
                if (bsig != 0)
                {
                    signal = bsig;
                    effectiveEntry = c0;
                    double risk = c0 * Math.Max(StopLossBps, 0.5) / 10000.0;
                    stopLoss = bsig == 1 ? c0 - risk : c0 + risk;
                    limitPrice = double.NaN;
                }
            }

            double target1 = double.NaN, target2 = double.NaN;
            if (signal != 0)
            {
                double queenPts = effectiveEntry * QueenTargetBps / 10000.0;
                double runnerPts = effectiveEntry * RunnerTargetBps / 10000.0;
                target1 = signal == 1 ? effectiveEntry + queenPts : effectiveEntry - queenPts;
                target2 = signal == 1 ? effectiveEntry + runnerPts : effectiveEntry - runnerPts;
                if (signal == 1 && !double.IsNaN(activeMid) && activeMid > target2) target2 = activeMid;
                if (signal == -1 && !double.IsNaN(activeMid) && activeMid < target2) target2 = activeMid;

                if (ShowVisualElements)
                {
                    string tag = "CISD_" + (signal == 1 ? "Bull_" : "Bear_") + CurrentBar;
                    if (signal == 1)
                    {
                        Draw.ArrowUp(this, tag, false, 0, l0 - (6 * TickSize), Brushes.Gold);
                        Draw.Text(this, tag + "_txt", false,
                            string.Format("CISD LONG V{0}\nEntry: {1:F2} SL: {2:F2}", Variant, effectiveEntry, stopLoss),
                            0, l0 - (14 * TickSize), 0, Brushes.Gold, new SimpleFont("Arial", 9),
                            System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                        if (!double.IsNaN(activeLevel))
                            Draw.Line(this, tag + "_line", false, 6, activeLevel, 0, activeLevel, Brushes.Gold, DashStyleHelper.Solid, 2);
                    }
                    else
                    {
                        Draw.ArrowDown(this, tag, false, 0, h0 + (6 * TickSize), Brushes.Cyan);
                        Draw.Text(this, tag + "_txt", false,
                            string.Format("CISD SHORT V{0}\nEntry: {1:F2} SL: {2:F2}", Variant, effectiveEntry, stopLoss),
                            0, h0 + (14 * TickSize), 0, Brushes.Cyan, new SimpleFont("Arial", 9),
                            System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                        if (!double.IsNaN(activeLevel))
                            Draw.Line(this, tag + "_line", false, 6, activeLevel, 0, activeLevel, Brushes.Cyan, DashStyleHelper.Solid, 2);
                    }
                }
            }

            // 50% midline reclaim confluence (single-TF mode only)
            if (EnableMidlineReclaims && signal == 0 && !double.IsNaN(activeMid) && !inLunch && ce == 0)
            {
                double cPrev = CurrentBar >= 1 ? Close[1] : c0;
                if (l0 < activeMid && c0 > activeMid && o0 > activeMid && cPrev <= activeMid)
                {
                    double risk = c0 * StopLossBps / 10000.0;
                    signal = 1;
                    stopLoss = c0 - risk;
                    effectiveEntry = c0;
                    limitPrice = double.NaN;
                    target1 = c0 + (c0 * QueenTargetBps / 10000.0);
                    target2 = c0 + (c0 * RunnerTargetBps / 10000.0);
                    if (ShowVisualElements)
                    {
                        string tag = "MID_Reclaim_Bull_" + CurrentBar;
                        Draw.Dot(this, tag, false, 0, l0 - (4 * TickSize), Brushes.LightGreen);
                    }
                }
                else if (h0 > activeMid && c0 < activeMid && o0 < activeMid && cPrev >= activeMid)
                {
                    double risk = c0 * StopLossBps / 10000.0;
                    signal = -1;
                    stopLoss = c0 + risk;
                    effectiveEntry = c0;
                    limitPrice = double.NaN;
                    target1 = c0 - (c0 * QueenTargetBps / 10000.0);
                    target2 = c0 - (c0 * RunnerTargetBps / 10000.0);
                    if (ShowVisualElements)
                    {
                        string tag = "MID_Reclaim_Bear_" + CurrentBar;
                        Draw.Dot(this, tag, false, 0, h0 + (4 * TickSize), Brushes.OrangeRed);
                    }
                }
            }

            SignalSeries[0] = signal;
            StopLossSeries[0] = signal != 0 ? stopLoss : double.NaN;
            QueenTargetSeries[0] = signal != 0 ? target1 : double.NaN;
            RunnerTargetSeries[0] = signal != 0 ? target2 : double.NaN;
            LimitPriceSeries[0] = limitPrice;

            if (_diagCsv != null)
            {
                _diagCsv.WriteLine(string.Format(CultureInfo.InvariantCulture,
                    "{0:yyyy-MM-dd HH:mm:ss},{1:G},{2:G},{3:G},{4:G},{5},{6},{7:G},{8:G},{9},{10:G},{11:G},{12},{13},{14},{15:G},{16:G},{17:G},{18}",
                    Time[0], o0, h0, l0, c0,
                    ce, _cisd.State,
                    double.IsNaN(endBull) ? "" : endBull.ToString("G"),
                    double.IsNaN(endBear) ? "" : endBear.ToString("G"),
                    fvgRes.Event,
                    double.IsNaN(fvgRes.Top) || fvgRes.Event == 0 ? "" : fvgRes.Top.ToString("G"),
                    double.IsNaN(fvgRes.Bottom) || fvgRes.Event == 0 ? "" : fvgRes.Bottom.ToString("G"),
                    ifvgRes.Event, bprRes.Event, signal,
                    double.IsNaN(st.EntryPrice) ? "" : st.EntryPrice.ToString("G"),
                    double.IsNaN(st.StopPrice) ? "" : st.StopPrice.ToString("G"),
                    double.IsNaN(st.RiskPts) ? "" : st.RiskPts.ToString("G"),
                    Variant));
            }
        }
    }
}

#region NinjaScript Generated Code
namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private Vinay.ICTFVGCISDIndicator[] cacheICTFVGCISDIndicator;
        public Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(int variant, int entryMode, int stopLossType, bool useHtfFilter, bool filterLunch, bool requireExternalSweep, double queenTargetBps, double runnerTargetBps, double stopLossBps, double minRiskBps, double maxRiskBps, bool enableMidlineReclaims, bool showVisualElements)
        {
            return ICTFVGCISDIndicator(Input, variant, entryMode, stopLossType, useHtfFilter, filterLunch, requireExternalSweep, queenTargetBps, runnerTargetBps, stopLossBps, minRiskBps, maxRiskBps, enableMidlineReclaims, showVisualElements);
        }

        public Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(ISeries<double> input, int variant, int entryMode, int stopLossType, bool useHtfFilter, bool filterLunch, bool requireExternalSweep, double queenTargetBps, double runnerTargetBps, double stopLossBps, double minRiskBps, double maxRiskBps, bool enableMidlineReclaims, bool showVisualElements)
        {
            if (cacheICTFVGCISDIndicator != null)
                for (int idx = 0; idx < cacheICTFVGCISDIndicator.Length; idx++)
                    if (cacheICTFVGCISDIndicator[idx] != null && cacheICTFVGCISDIndicator[idx].Variant == variant && cacheICTFVGCISDIndicator[idx].EntryMode == entryMode && cacheICTFVGCISDIndicator[idx].StopLossType == stopLossType && cacheICTFVGCISDIndicator[idx].UseHtfFilter == useHtfFilter && cacheICTFVGCISDIndicator[idx].FilterLunch == filterLunch && cacheICTFVGCISDIndicator[idx].RequireExternalSweep == requireExternalSweep && cacheICTFVGCISDIndicator[idx].QueenTargetBps == queenTargetBps && cacheICTFVGCISDIndicator[idx].RunnerTargetBps == runnerTargetBps && cacheICTFVGCISDIndicator[idx].StopLossBps == stopLossBps && cacheICTFVGCISDIndicator[idx].MinRiskBps == minRiskBps && cacheICTFVGCISDIndicator[idx].MaxRiskBps == maxRiskBps && cacheICTFVGCISDIndicator[idx].EnableMidlineReclaims == enableMidlineReclaims && cacheICTFVGCISDIndicator[idx].ShowVisualElements == showVisualElements && cacheICTFVGCISDIndicator[idx].EqualsInput(input))
                        return cacheICTFVGCISDIndicator[idx];
            return CacheIndicator<Vinay.ICTFVGCISDIndicator>(new Vinay.ICTFVGCISDIndicator() { Variant = variant, EntryMode = entryMode, StopLossType = stopLossType, UseHtfFilter = useHtfFilter, FilterLunch = filterLunch, RequireExternalSweep = requireExternalSweep, QueenTargetBps = queenTargetBps, RunnerTargetBps = runnerTargetBps, StopLossBps = stopLossBps, MinRiskBps = minRiskBps, MaxRiskBps = maxRiskBps, EnableMidlineReclaims = enableMidlineReclaims, ShowVisualElements = showVisualElements }, input, ref cacheICTFVGCISDIndicator);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(int variant, int entryMode, int stopLossType, bool useHtfFilter, bool filterLunch, bool requireExternalSweep, double queenTargetBps, double runnerTargetBps, double stopLossBps, double minRiskBps, double maxRiskBps, bool enableMidlineReclaims, bool showVisualElements)
        {
            return indicator.ICTFVGCISDIndicator(Input, variant, entryMode, stopLossType, useHtfFilter, filterLunch, requireExternalSweep, queenTargetBps, runnerTargetBps, stopLossBps, minRiskBps, maxRiskBps, enableMidlineReclaims, showVisualElements);
        }

        public Indicators.Vinay.ICTFVGCISDIndicator ICTFVGCISDIndicator(ISeries<double> input, int variant, int entryMode, int stopLossType, bool useHtfFilter, bool filterLunch, bool requireExternalSweep, double queenTargetBps, double runnerTargetBps, double stopLossBps, double minRiskBps, double maxRiskBps, bool enableMidlineReclaims, bool showVisualElements)
        {
            return indicator.ICTFVGCISDIndicator(input, variant, entryMode, stopLossType, useHtfFilter, filterLunch, requireExternalSweep, queenTargetBps, runnerTargetBps, stopLossBps, minRiskBps, maxRiskBps, enableMidlineReclaims, showVisualElements);
        }
    }
}
#endregion
