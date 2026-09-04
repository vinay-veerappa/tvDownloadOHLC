// =============================================================================
// IctCisdReversalSetup — parity port of ifvg_cisd_strategy.py
//                                              ::_variant_signal_kernel.
//
// The SETUP layer: consumes the four engines' per-bar events and produces
// variant signals (V1: prior-leg BPR/IFVG evidence; V2: >=2 unmitigated
// opposing-run FVGs) with entry/stop brackets resolved per stop-loss type.
// Kept separate from the engines so any strategy can compose them differently.
//
// Engine events are pushed in via PushEngineEvents() BEFORE OnBar() each bar
// — mirrors the Python kernel receiving cisd/fvg/ifvg/bpr arrays computed on
// the same HTF frame.
// =============================================================================
using System;

namespace Vinay.Ict
{
    public sealed class IctCisdReversalSetup
    {
        public const int MaxLegFvg = 50;   // Python kernel max_fvg

        // ── Configuration (strategy layer sets from the manifest) ──
        public int Variant;                // 0=baseline 1=V1 2=V2
        public double TickSize = 0.25;
        public double MinRiskBps = 2.0;
        public double MaxRiskBps = 15.0;
        public int StopLossType;           // 0=bps_stat 1=structural 2=structural_capped_bps 3=skip_if_out_of_band
        public double StopLossBps = 5.0;
        public int EntryMechanism;          // 0=market 1=cisd_limit

        // ── Leg state machine ──
        private int _regime;
        private double _legOriginLow = double.NaN;
        private double _legOriginHigh = double.NaN;
        private double _legCisdLevel = double.NaN;
        private bool _legHasBpr;
        private bool _legHasIfvg;
        private bool _v2Triggered;
        private readonly double[] _legBullFvgBots = new double[MaxLegFvg];
        private int _legBullFvgCount;
        private readonly double[] _legBearFvgTops = new double[MaxLegFvg];
        private int _legBearFvgCount;

        // Per-bar engine events (pushed by the host before OnBar)
        private int _ce, _cs, _fe, _ie, _be;
        private double _feTop, _feBot;

        public struct SetupResult
        {
            public int Signal;             // +1 / -1 / 0
            public double EntryPrice;
            public double StopPrice;
            public double RiskPts;
        }

        /// <summary>
        /// Feed this bar's engine outputs (call BEFORE OnBar, same bar).
        ///
        /// Parity semantics (Python _variant_signal_kernel):
        ///   - crossed level (leg origin) = the OPPOSING regime's armed level as
        ///     of the END of the PREVIOUS bar (arrays indexed [i-1]);
        ///   - leg CISD level = the new regime's armed level at THIS bar's end
        ///     ([i]); falls back to the flip bar's OPEN when NaN.
        /// </summary>
        public void PushEngineEvents(int cisdEvent, int cisdState,
                                     int fvgEvent, double fvgTop, double fvgBottom,
                                     int ifvgEvent, int bprEvent,
                                     double prevEndBullLevel, double prevEndBearLevel,
                                     double newBullLevel, double newBearLevel,
                                     double flipBarOpen)
        {
            _ce = cisdEvent; _cs = cisdState; _fe = fvgEvent;
            _feTop = fvgTop; _feBot = fvgBottom;
            _ie = ifvgEvent; _be = bprEvent;

            // Snapshot prior leg flags BEFORE reset (V1/V2 read at the flip)
            bool priorLegHasBpr = _legHasBpr;
            bool priorLegHasIfvg = _legHasIfvg;
            int priorBullFvg = _legBullFvgCount;
            int priorBearFvg = _legBearFvgCount;

            if (cisdEvent == 1)
            {
                _regime = 1;
                _legOriginLow = double.IsNaN(prevEndBearLevel) ? double.NaN : prevEndBearLevel;
                _legOriginHigh = double.NaN;
                _legCisdLevel = double.IsNaN(newBullLevel) ? flipBarOpen : newBullLevel;
                _legHasBpr = false; _legHasIfvg = false; _v2Triggered = false;
                _legBullFvgCount = 0; _legBearFvgCount = 0;
            }
            else if (cisdEvent == -1)
            {
                _regime = -1;
                _legOriginLow = double.NaN;
                _legOriginHigh = double.IsNaN(prevEndBullLevel) ? double.NaN : prevEndBullLevel;
                _legCisdLevel = double.IsNaN(newBearLevel) ? flipBarOpen : newBearLevel;
                _legHasBpr = false; _legHasIfvg = false; _v2Triggered = false;
                _legBullFvgCount = 0; _legBearFvgCount = 0;
            }
            else
            {
                _regime = cisdState;
            }

            _priorLegHasBpr = priorLegHasBpr;
            _priorLegHasIfvg = priorLegHasIfvg;
            _priorBullFvg = priorBullFvg;
            _priorBearFvg = priorBearFvg;
        }

        private bool _priorLegHasBpr, _priorLegHasIfvg;
        private int _priorBullFvg, _priorBearFvg;

        /// <summary>
        /// Complete the bar: track in-leg FVGs, mitigate, evaluate the variant
        /// signal. Call after PushEngineEvents.
        /// </summary>
        public SetupResult OnBar(double o, double h, double l, double c)
        {
            if (_regime != 0)
            {
                if (_fe == 1 && _legBullFvgCount < MaxLegFvg)
                    _legBullFvgBots[_legBullFvgCount++] = _feBot;
                else if (_fe == -1 && _legBearFvgCount < MaxLegFvg)
                    _legBearFvgTops[_legBearFvgCount++] = _feTop;
                if (_ie == 1 && _regime == 1) _legHasIfvg = true;
                if (_ie == -1 && _regime == -1) _legHasIfvg = true;
                if (_be != 0) _legHasBpr = true;

                int k = 0;
                while (k < _legBullFvgCount)
                {
                    if (l <= _legBullFvgBots[k])
                    {
                        for (int m = k; m < _legBullFvgCount - 1; m++)
                            _legBullFvgBots[m] = _legBullFvgBots[m + 1];
                        _legBullFvgCount--;
                    }
                    else k++;
                }
                k = 0;
                while (k < _legBearFvgCount)
                {
                    if (h >= _legBearFvgTops[k])
                    {
                        for (int m = k; m < _legBearFvgCount - 1; m++)
                            _legBearFvgTops[m] = _legBearFvgTops[m + 1];
                        _legBearFvgCount--;
                    }
                    else k++;
                }
            }

            double priceRef = c;
            double minRisk = priceRef * MinRiskBps / 10000.0;
            double maxRisk = priceRef * MaxRiskBps / 10000.0;

            var res = new SetupResult();
            int signal = 0;
            double ep = double.NaN, rs = double.NaN, risk = 0.0;

            if (Variant == 1)
            {
                if (_ce == 1 && (_priorLegHasBpr || _priorLegHasIfvg))
                {
                    if (ResolveLongBracket(c, l, out ep, out rs, out risk) && risk >= minRisk && risk <= maxRisk)
                        signal = 1;
                }
                else if (_ce == -1 && (_priorLegHasBpr || _priorLegHasIfvg))
                {
                    if (ResolveShortBracket(c, h, out ep, out rs, out risk) && risk >= minRisk && risk <= maxRisk)
                        signal = -1;
                }
            }
            else if (Variant == 2)
            {
                if (_ce == 1 && !_v2Triggered && _priorBearFvg >= 2)
                {
                    if (ResolveLongBracket(c, l, out ep, out rs, out risk) && risk >= minRisk && risk <= maxRisk)
                    {
                        signal = 1;
                        _v2Triggered = true;
                    }
                }
                else if (_ce == -1 && !_v2Triggered && _priorBullFvg >= 2)
                {
                    if (ResolveShortBracket(c, h, out ep, out rs, out risk) && risk >= minRisk && risk <= maxRisk)
                    {
                        signal = -1;
                        _v2Triggered = true;
                    }
                }
            }

            res.Signal = signal;
            res.EntryPrice = signal != 0 ? ep : double.NaN;
            res.StopPrice = signal != 0 ? rs : double.NaN;
            res.RiskPts = signal != 0 ? risk : double.NaN;
            return res;
        }

        // ── Bracket resolvers (_resolve_long/_short_bracket in Python) ──
        private bool ResolveLongBracket(double c, double l, out double ep, out double rs, out double risk)
        {
            ep = c;
            if (EntryMechanism == 1 && !double.IsNaN(_legCisdLevel) && _legCisdLevel < c)
                ep = _legCisdLevel;

            if (StopLossType == 0)
            {
                rs = ep - (ep * StopLossBps / 10000.0);
                risk = ep - rs;
                return true;
            }
            if (double.IsNaN(_legOriginLow))
            {
                rs = ep - (ep * StopLossBps / 10000.0);
                risk = ep - rs;
                return true;
            }
            double structStop = _legOriginLow - 2.0 * TickSize;
            if (structStop >= ep)
            {
                if (StopLossType == 2)
                {
                    rs = ep - (ep * StopLossBps / 10000.0);
                    risk = ep - rs;
                    return true;
                }
                rs = structStop; risk = 0.0;
                return false;
            }
            risk = ep - structStop;
            if (StopLossType == 2)
            {
                double maxRisk = ep * StopLossBps / 10000.0;
                if (risk > maxRisk)
                {
                    rs = ep - maxRisk;
                    risk = maxRisk;
                    return true;
                }
            }
            rs = structStop;
            return true;
        }

        private bool ResolveShortBracket(double c, double h, out double ep, out double rs, out double risk)
        {
            ep = c;
            if (EntryMechanism == 1 && !double.IsNaN(_legCisdLevel) && _legCisdLevel > c)
                ep = _legCisdLevel;

            if (StopLossType == 0)
            {
                rs = ep + (ep * StopLossBps / 10000.0);
                risk = rs - ep;
                return true;
            }
            if (double.IsNaN(_legOriginHigh))
            {
                rs = ep + (ep * StopLossBps / 10000.0);
                risk = rs - ep;
                return true;
            }
            double structStop = _legOriginHigh + 2.0 * TickSize;
            if (structStop <= ep)
            {
                if (StopLossType == 2)
                {
                    rs = ep + (ep * StopLossBps / 10000.0);
                    risk = rs - ep;
                    return true;
                }
                rs = structStop; risk = 0.0;
                return false;
            }
            risk = structStop - ep;
            if (StopLossType == 2)
            {
                double maxRisk = ep * StopLossBps / 10000.0;
                if (risk > maxRisk)
                {
                    rs = ep + maxRisk;
                    risk = maxRisk;
                    return true;
                }
            }
            rs = structStop;
            return true;
        }
    }
}