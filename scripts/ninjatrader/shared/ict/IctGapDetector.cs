// =============================================================================
// IctGapDetector — the ONE copy of 3-bar gap + contiguous VI-merge semantics.
//
// Parity: fvg.py / ifvg.py / bpr.py inline identical detection (bull: l0>h2,
// bear: l2>h0; VI body-gaps merged with the Python 1e-4 tolerance). Every C#
// engine calls these — a semantic edit lands here and in the three Python
// kernels in the same commit.
//
// Pure static functions, no state.
// =============================================================================
namespace Vinay.Ict
{
    public static class IctGapDetector
    {
        public const double Eps = 1e-4; // Python 1e-4 tolerance in VI merges

        public struct GapZone { public double Top, Bottom; public int HasVi; }

        public static bool DetectBull(double o0, double h0, double l0, double c0,
                                      double o1, double h1, double l1, double c1,
                                      double o2, double h2, double l2, double c2,
                                      bool requireDirectional, bool includeVi,
                                      out GapZone zone)
        {
            zone = default(GapZone);
            if (!(l0 - h2 > 0.0)) return false;
            if (requireDirectional && !(c0 > o0)) return false;

            double top = l0, bot = h2;
            int hasVi = 0;

            if (includeVi)
            {
                double bodyTop2 = o2 > c2 ? o2 : c2;
                double bodyBot1 = o1 < c1 ? o1 : c1;
                if (bodyBot1 > bodyTop2 && h2 >= l1
                    && bodyTop2 <= top + Eps && bodyBot1 >= bot - Eps)
                {
                    if (bodyBot1 > top) top = bodyBot1;
                    if (bodyTop2 < bot) bot = bodyTop2;
                    hasVi = 1;
                }
                double bodyTop1 = o1 > c1 ? o1 : c1;
                double bodyBot0 = o0 < c0 ? o0 : c0;
                if (bodyBot0 > bodyTop1 && h1 >= l0
                    && bodyTop1 <= top + Eps && bodyBot0 >= bot - Eps)
                {
                    if (bodyBot0 > top) top = bodyBot0;
                    if (bodyTop1 < bot) bot = bodyTop1;
                    hasVi = 1;
                }
            }
            zone.Top = top; zone.Bottom = bot; zone.HasVi = hasVi;
            return true;
        }

        public static bool DetectBear(double o0, double h0, double l0, double c0,
                                      double o1, double h1, double l1, double c1,
                                      double o2, double h2, double l2, double c2,
                                      bool requireDirectional, bool includeVi,
                                      out GapZone zone)
        {
            zone = default(GapZone);
            if (!(l2 - h0 > 0.0)) return false;
            if (requireDirectional && !(c0 < o0)) return false;

            double top = l2, bot = h0;
            int hasVi = 0;

            if (includeVi)
            {
                double bodyBot2 = o2 < c2 ? o2 : c2;
                double bodyTop1 = o1 > c1 ? o1 : c1;
                if (bodyTop1 < bodyBot2 && l2 <= h1
                    && bodyBot2 >= bot - Eps && bodyTop1 <= top + Eps)
                {
                    if (bodyBot2 > top) top = bodyBot2;
                    if (bodyTop1 < bot) bot = bodyTop1;
                    hasVi = 1;
                }
                double bodyBot1 = o1 < c1 ? o1 : c1;
                double bodyTop0 = o0 > c0 ? o0 : c0;
                if (bodyTop0 < bodyBot1 && l1 <= h0
                    && bodyBot1 >= bot - Eps && bodyTop0 <= top + Eps)
                {
                    if (bodyBot1 > top) top = bodyBot1;
                    if (bodyTop0 < bot) bot = bodyTop0;
                    hasVi = 1;
                }
            }
            zone.Top = top; zone.Bottom = bot; zone.HasVi = hasVi;
            return true;
        }
    }
}