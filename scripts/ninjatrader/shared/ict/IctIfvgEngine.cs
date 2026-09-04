// =============================================================================
// IctIfvgEngine — parity port of ifvg.py::IFVGTracker.
//
// Two inversion pools: bull FVGs await bear inversion (checked against their
// BOTTOM), bear FVGs await bull inversion (checked against their TOP).
// Pools are remove-oldest when full (Python max_active_zones=50, NO
// mitigation removal here — that is FVG-engine semantics, deliberately not
// shared). Zones removed only on inversion.
// =============================================================================
using System;

namespace Vinay.Ict
{
    public sealed class IctIfvgEngine
    {
        public const int MaxZones = 50;   // ifvg.py compute default

        private readonly double[] _bullTops = new double[MaxZones];
        private readonly double[] _bullBots = new double[MaxZones];
        private int _bullCount;
        private readonly double[] _bearTops = new double[MaxZones];
        private readonly double[] _bearBots = new double[MaxZones];
        private int _bearCount;

        private readonly double[] _hO = new double[4];
        private readonly double[] _hH = new double[4];
        private readonly double[] _hL = new double[4];
        private readonly double[] _hC = new double[4];
        private int _t;
        private double _prevClose = double.NaN;

        public bool IncludeVi = true;
        public bool RequireDirectional;

        public struct IfvgResult
        {
            public int Event;        // +1 bull inversion / -1 bear inversion / 0
            public double Top;
            public double Bottom;
            public double Ce;
        }

        public int BullPoolCount { get { return _bullCount; } }
        public int BearPoolCount { get { return _bearCount; } }

        private void PoolPush(double[] tops, double[] bots, ref int count, double top, double bot)
        {
            if (count >= MaxZones)
            {
                for (int m = 0; m < MaxZones - 1; m++)
                {
                    tops[m] = tops[m + 1];
                    bots[m] = bots[m + 1];
                }
                count = MaxZones - 1;
            }
            tops[count] = top; bots[count] = bot;
            count++;
        }

        public IfvgResult OnBar(double o, double h, double l, double c)
        {
            int t = _t & 3;
            double o1 = _hO[(t + 3) & 3], h1 = _hH[(t + 3) & 3], l1 = _hL[(t + 3) & 3], c1 = _hC[(t + 3) & 3];
            double o2 = _hO[(t + 2) & 3], h2 = _hH[(t + 2) & 3], l2 = _hL[(t + 2) & 3], c2 = _hC[(t + 2) & 3];
            _hO[t] = o; _hH[t] = h; _hL[t] = l; _hC[t] = c;
            int prevT = _t;
            _t++;
            double prevCloseBeforeThisBar = _prevClose;
            _prevClose = c;

            var res = new IfvgResult();
            if (prevT < 2) return res;   // Python loop starts at t=2

            IctGapDetector.GapZone z;
            if (IctGapDetector.DetectBull(o, h, l, c, o1, h1, l1, c1, o2, h2, l2, c2,
                                          RequireDirectional, IncludeVi, out z))
                PoolPush(_bullTops, _bullBots, ref _bullCount, z.Top, z.Bottom);
            if (IctGapDetector.DetectBear(o, h, l, c, o1, h1, l1, c1, o2, h2, l2, c2,
                                          RequireDirectional, IncludeVi, out z))
                PoolPush(_bearTops, _bearBots, ref _bearCount, z.Top, z.Bottom);

            // c1 in the Python kernel is close[t-1] — the close BEFORE this bar.
            double prevC = double.IsNaN(prevCloseBeforeThisBar) ? c1 : prevCloseBeforeThisBar;

            // Bullish inversion: close crosses ABOVE a bear zone top (prev close <= top)
            for (int k = _bearCount - 1; k >= 0; k--)
            {
                if (c > _bearTops[k] && prevC <= _bearTops[k])
                {
                    res.Event = 1;
                    res.Top = _bearTops[k]; res.Bottom = _bearBots[k];
                    res.Ce = (res.Top + res.Bottom) / 2.0;
                    for (int m = k; m < _bearCount - 1; m++)
                    {
                        _bearTops[m] = _bearTops[m + 1];
                        _bearBots[m] = _bearBots[m + 1];
                    }
                    _bearCount--;
                    return res;
                }
            }
            // Bearish inversion: close crosses BELOW a bull zone bottom
            for (int k = _bullCount - 1; k >= 0; k--)
            {
                if (c < _bullBots[k] && prevC >= _bullBots[k])
                {
                    res.Event = -1;
                    res.Top = _bullTops[k]; res.Bottom = _bullBots[k];
                    res.Ce = (res.Top + res.Bottom) / 2.0;
                    for (int m = k; m < _bullCount - 1; m++)
                    {
                        _bullTops[m] = _bullTops[m + 1];
                        _bullBots[m] = _bullBots[m + 1];
                    }
                    _bullCount--;
                    return res;
                }
            }
            return res;
        }
    }
}