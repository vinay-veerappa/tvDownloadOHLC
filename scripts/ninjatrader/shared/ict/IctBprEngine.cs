// =============================================================================
// IctBprEngine — parity port of bpr.py::BPRTracker.
//
// Overlapping opposing FVGs: a new bull FVG overlapping any recent active
// bear FVG (or vice versa) fires a BPR event with the overlap zone.
// Pools are remove-oldest when full (max_active_gaps=50, no mitigation).
// =============================================================================
using System;

namespace Vinay.Ict
{
    public sealed class IctBprEngine
    {
        public const int MaxZones = 50;   // bpr.py compute default

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

        public bool IncludeVi = true;        // body-gap merging (bpr.py canonical)
        public bool RequireDirectional;

        public struct BprResult
        {
            public int Event;        // +1 / -1 / 0
            public double Top;       // overlap zone
            public double Bottom;
            public double Midpoint;
        }

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

        public BprResult OnBar(double o, double h, double l, double c)
        {
            int t = _t & 3;
            double o1 = _hO[(t + 3) & 3], h1 = _hH[(t + 3) & 3], l1 = _hL[(t + 3) & 3], c1 = _hC[(t + 3) & 3];
            double o2 = _hO[(t + 2) & 3], h2 = _hH[(t + 2) & 3], l2 = _hL[(t + 2) & 3], c2 = _hC[(t + 2) & 3];
            _hO[t] = o; _hH[t] = h; _hL[t] = l; _hC[t] = c;
            _t++;

            var res = new BprResult();
            if (_t < 3) return res;

            IctGapDetector.GapZone z;

            // 1. New bull FVG — check overlap against recent BEAR FVGs (newest first)
            if (IctGapDetector.DetectBull(o, h, l, c, o1, h1, l1, c1, o2, h2, l2, c2,
                                          RequireDirectional, IncludeVi, out z))
            {
                for (int k = _bearCount - 1; k >= 0; k--)
                {
                    double ovTop = z.Top < _bearTops[k] ? z.Top : _bearTops[k];
                    double ovBot = z.Bottom > _bearBots[k] ? z.Bottom : _bearBots[k];
                    if (ovTop - ovBot > 0.0)   // min_overlap_pts = 0.0 (python default)
                    {
                        res.Event = 1;
                        res.Top = ovTop; res.Bottom = ovBot;
                        res.Midpoint = (ovTop + ovBot) / 2.0;
                        break;
                    }
                }
                PoolPush(_bullTops, _bullBots, ref _bullCount, z.Top, z.Bottom);
            }

            // 2. New bear FVG — check overlap against recent BULL FVGs (newest first)
            if (IctGapDetector.DetectBear(o, h, l, c, o1, h1, l1, c1, o2, h2, l2, c2,
                                          RequireDirectional, IncludeVi, out z))
            {
                for (int k = _bullCount - 1; k >= 0; k--)
                {
                    double ovTop = z.Top < _bullTops[k] ? z.Top : _bullTops[k];
                    double ovBot = z.Bottom > _bullBots[k] ? z.Bottom : _bullBots[k];
                    if (ovTop - ovBot > 0.0)
                    {
                        res.Event = -1;
                        res.Top = ovTop; res.Bottom = ovBot;
                        res.Midpoint = (ovTop + ovBot) / 2.0;
                        break;
                    }
                }
                PoolPush(_bearTops, _bearBots, ref _bearCount, z.Top, z.Bottom);
            }
            return res;
        }
    }
}