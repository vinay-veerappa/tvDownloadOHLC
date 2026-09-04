// =============================================================================
// IctCisdEngine — parity port of cisd.py::CISDTracker.
//
// tncylyv extreme-open + continuous re-anchor model (the DEFAULT engine in
// cisd.py; production parity target — NOT the `canonical=True` strict sweep
// kernel, which is a separate Python code path and a separate engine if ever
// ported). One continuous level per regime; fires on close cross.
//
// Pure state machine: no NinjaScript, no drawing, primitives in/out.
// Ring buffer keeps 512 bars of O/C for the 500-bar extreme-open scans.
// =============================================================================
using System;

namespace Vinay.Ict
{
    public sealed class IctCisdEngine
    {
        public const int HistorySize = 512;      // >= CrystalBallMaxScan + margin
        public const int MaxScan = 500;          // cisd.py _consult_crystal_ball cap

        private readonly double[] _hO = new double[HistorySize];
        private readonly double[] _hC = new double[HistorySize];
        private int _t;

        private int _vibes;                       // +1 bull / -1 bear / 0 uninit
        private double _bagholderEntry = double.NaN;
        private double _painThreshold = double.NaN;

        /// <summary>Running regime as of the last processed bar: +1 / -1 / 0.</summary>
        public int State { get { return _vibes; } }

        /// <summary>Armed level of the current regime (extreme open). NaN when unset.</summary>
        public double ActiveLevel
        {
            get { return _vibes == 0 ? double.NaN : _bagholderEntry; }
        }

        public int BarsProcessed { get { return _t; } }

        private double HO(int t) { return _hO[t & (HistorySize - 1)]; }
        private double HC(int t) { return _hC[t & (HistorySize - 1)]; }

        private int CandleAt(int t)
        {
            double c = HC(t), o = HO(t);
            return c > o ? 1 : (c < o ? -1 : 0);
        }

        // cisd.py::_consult_crystal_ball — extreme open of the same-direction
        // delivery run ending at t. Never NaN (falls back to open[t]).
        private double ConsultCrystalBall(int bias, int t)
        {
            double extreme = HO(t);
            int att = CandleAt(t);
            if (att == 0 || att != bias)
                return extreme;

            int maxI = Math.Min(MaxScan, t);
            for (int i = 1; i <= maxI; i++)
            {
                int a = CandleAt(t - i);
                if (a == 0) continue;
                if (a != bias) break;
                if (bias == 1)
                {
                    if (HO(t - i) < extreme) extreme = HO(t - i);
                }
                else
                {
                    if (HO(t - i) > extreme) extreme = HO(t - i);
                }
            }
            return extreme;
        }

        // cisd.py::_archaeologist_jones — skip bar t, first matching candle
        // backward, extend through the run. May return NaN.
        private double ArchaeologistJones(int bias, int t)
        {
            bool artifactFound = false;
            double extreme = double.NaN;
            int maxJ = Math.Min(MaxScan, t);
            for (int j = 1; j <= maxJ; j++)
            {
                int a = CandleAt(t - j);
                if (a == 0) continue;
                bool correctEra = a == bias;
                if (!artifactFound)
                {
                    if (correctEra)
                    {
                        artifactFound = true;
                        extreme = HO(t - j);
                    }
                }
                else
                {
                    if (!correctEra) break;
                    if (bias == 1)
                    {
                        if (HO(t - j) < extreme) extreme = HO(t - j);
                    }
                    else
                    {
                        if (HO(t - j) > extreme) extreme = HO(t - j);
                    }
                }
            }
            return extreme;
        }

        /// <summary>
        /// Process one completed bar. Returns the CISD event: +1 bull flip,
        /// -1 bear flip, 0 none. State/ActiveLevel reflect the bar's end.
        /// </summary>
        public int OnBar(double o, double h, double l, double c)
        {
            int t = _t;
            _hO[t & (HistorySize - 1)] = o;
            _hC[t & (HistorySize - 1)] = c;
            _t++;

            int personality = c > o ? 1 : (c < o ? -1 : 0);

            // --- Init (cisd.py: vibes == 0 and t > 10) ---
            if (_vibes == 0 && t > 10)
            {
                int firstImpression = personality;
                if (firstImpression == 0)
                {
                    int maxK = Math.Min(50, t);
                    for (int k = 1; k <= maxK; k++)
                    {
                        firstImpression = CandleAt(t - k);
                        if (firstImpression != 0) break;
                    }
                }
                if (firstImpression != 0)
                {
                    _vibes = firstImpression;
                    _bagholderEntry = ConsultCrystalBall(firstImpression, t);
                    _painThreshold = firstImpression == 1 ? h : l;
                }
            }

            // --- Re-anchor on new extreme ---
            if (_vibes == 1 && h > _painThreshold && !double.IsNaN(_painThreshold))
            {
                _painThreshold = h;
                double ep = personality == 1
                    ? ConsultCrystalBall(1, t)
                    : ArchaeologistJones(1, t);
                if (!double.IsNaN(ep)) _bagholderEntry = ep;
            }
            else if (_vibes == -1 && l < _painThreshold && !double.IsNaN(_painThreshold))
            {
                _painThreshold = l;
                double ep = personality == -1
                    ? ConsultCrystalBall(-1, t)
                    : ArchaeologistJones(-1, t);
                if (!double.IsNaN(ep)) _bagholderEntry = ep;
            }

            // --- Flip detection (close cross of the extreme open) ---
            bool shortsSqueezed = _vibes == -1 && !double.IsNaN(_bagholderEntry) && c > _bagholderEntry;
            bool longsRekt = _vibes == 1 && !double.IsNaN(_bagholderEntry) && c < _bagholderEntry;

            int ev = 0;
            if (shortsSqueezed)
            {
                ev = 1;
                _vibes = 1;
                _bagholderEntry = ConsultCrystalBall(1, t);
                _painThreshold = h;
            }
            else if (longsRekt)
            {
                ev = -1;
                _vibes = -1;
                _bagholderEntry = ConsultCrystalBall(-1, t);
                _painThreshold = l;
            }
            return ev;
        }
    }
}