// =============================================================================
// IctFvgEngine — parity port of fvg.py::FVGTracker.
//
// 3-bar FVG with contiguous VI merges, rolling active-gap pool with
// mitigation (bull filled when low <= bottom; bear when high >= top).
// Pool semantics differ per engine IN PYTHON (FVG mitigates; IFVG/BPR pools
// are remove-oldest only) — deliberately preserved.
// =============================================================================
using System;

namespace Vinay.Ict
{
    public sealed class IctFvgEngine
    {
        public const int MaxActive = 100;   // fvg.py kernel default

        private readonly double[] _tops = new double[MaxActive];
        private readonly double[] _bots = new double[MaxActive];
        private readonly int[] _types = new int[MaxActive];
        private int _active;

        private readonly double[] _hO = new double[4];
        private readonly double[] _hH = new double[4];
        private readonly double[] _hL = new double[4];
        private readonly double[] _hC = new double[4];
        private int _t;

        public bool IncludeVi = true;
        public bool RequireDirectional;

        public struct FvgResult
        {
            public int Event;        // +1 bull / -1 bear / 0
            public double Top;
            public double Bottom;
            public double Ce;
            public bool HasVi;
        }

        public int ActiveCount { get { return _active; } }

        public FvgResult OnBar(double o, double h, double l, double c)
        {
            int t = _t & 3;
            double o1 = _hO[(t + 3) & 3], h1 = _hH[(t + 3) & 3], l1 = _hL[(t + 3) & 3], c1 = _hC[(t + 3) & 3];
            double o2 = _hO[(t + 2) & 3], h2 = _hH[(t + 2) & 3], l2 = _hL[(t + 2) & 3], c2 = _hC[(t + 2) & 3];
            _hO[t] = o; _hH[t] = h; _hL[t] = l; _hC[t] = c;
            _t++;

            var res = new FvgResult();
            if (_t < 3) return res;   // Python loop starts at t=2

            IctGapDetector.GapZone z;
            if (IctGapDetector.DetectBull(o, h, l, c, o1, h1, l1, c1, o2, h2, l2, c2,
                                          RequireDirectional, IncludeVi, out z))
            {
                res.Event = 1; res.Top = z.Top; res.Bottom = z.Bottom;
                res.Ce = (z.Top + z.Bottom) / 2.0; res.HasVi = z.HasVi == 1;
                if (_active < MaxActive)
                {
                    _types[_active] = 1; _tops[_active] = z.Top; _bots[_active] = z.Bottom;
                    _active++;
                }
            }
            else if (IctGapDetector.DetectBear(o, h, l, c, o1, h1, l1, c1, o2, h2, l2, c2,
                                               RequireDirectional, IncludeVi, out z))
            {
                res.Event = -1; res.Top = z.Top; res.Bottom = z.Bottom;
                res.Ce = (z.Top + z.Bottom) / 2.0; res.HasVi = z.HasVi == 1;
                if (_active < MaxActive)
                {
                    _types[_active] = -1; _tops[_active] = z.Top; _bots[_active] = z.Bottom;
                    _active++;
                }
            }

            // Mitigation
            int k = 0;
            while (k < _active)
            {
                bool mitigated = (_types[k] == 1 && l <= _bots[k])
                              || (_types[k] == -1 && h >= _tops[k]);
                if (mitigated)
                {
                    for (int m = k; m < _active - 1; m++)
                    {
                        _types[m] = _types[m + 1];
                        _tops[m] = _tops[m + 1];
                        _bots[m] = _bots[m + 1];
                    }
                    _active--;
                }
                else k++;
            }
            return res;
        }
    }
}