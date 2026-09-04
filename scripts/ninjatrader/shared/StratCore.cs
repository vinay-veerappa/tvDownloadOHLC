using System;

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// StratCore — PURE Strat math, zero NT8 dependencies (no Series, no Draw).
    /// This is the C# mirror of scripts/libs_py/the_strat/:
    ///   taxonomy.py (ClassifyBar/WickType) + targets.py (MeasuredTargets) +
    ///   session.py (EntryAllowed) + signals.py FTFC scoring.
    /// Rule changes go here AND in Python together — never in only one side.
    /// Consumers: TheStratClassifier (signals), TheStratFTFCHud (FTFC),
    /// Strat212ContinuationBot / Strat22RevStratBot (gates via StratConfig).
    /// </summary>
    public static class StratCore
    {
        // Strat bar types — must match Python StratType codes.
        public const int Inside = 1;
        public const int TwoUp = 21;
        public const int TwoDown = 22;
        public const int Outside = 3;
        public const int Unknown = 0;

        public static int ClassifyBar(double currHigh, double currLow, double prevHigh, double prevLow)
        {
            bool higher = currHigh > prevHigh;
            bool lower = currLow < prevLow;
            if (!higher && !lower) return Inside;
            if (higher && !lower) return TwoUp;
            if (lower && !higher) return TwoDown;
            return Outside;
        }

        /// <returns>1 = Hammer, -1 = Shooter, 0 = None.</returns>
        public static int WickType(double open, double close, double high, double low, double threshold, double tickSize)
        {
            double range = high - low;
            if (range <= tickSize) return 0;
            double bodyTop = Math.Max(open, close);
            double bodyBottom = Math.Min(open, close);
            double upperRatio = (high - bodyTop) / range;
            double lowerRatio = (bodyBottom - low) / range;
            if (lowerRatio >= threshold && close >= (low + 0.5 * range)) return 1;
            if (upperRatio >= threshold && close <= (low + 0.5 * range)) return -1;
            return 0;
        }

        public struct MeasuredResult
        {
            public double Target1;
            public double Target2;
            public double RiskPoints;
            public double RewardPoints;
            public double RrRatio;
            public bool StopCapped;
        }

        /// <summary>
        /// Canonical measured-move targets — mirror of targets.measured_targets().
        /// direction: +1 LONG, -1 SHORT.
        /// </summary>
        public static MeasuredResult MeasuredTargets(
            int direction, double entry, double structuralStop,
            double insideHigh, double insideLow, double priorLegPoints,
            double minTargetPoints, double maxRiskPoints, double tickSize)
        {
            double insideRange = Math.Max(insideHigh - insideLow, tickSize);
            double leg = Math.Max(priorLegPoints, 0.0);
            double dist = Math.Max(insideRange, Math.Max(0.5 * leg, minTargetPoints));

            double structRisk = Math.Abs(entry - structuralStop);
            if (structRisk < tickSize) structRisk = tickSize;
            bool capped = structRisk > maxRiskPoints;
            double risk = Math.Min(structRisk, maxRiskPoints);
            if (risk < tickSize) risk = tickSize;

            double t1 = direction == 1 ? entry + dist : entry - dist;
            double t2 = direction == 1 ? entry + 2.0 * dist : entry - 2.0 * dist;
            return new MeasuredResult
            {
                Target1 = t1,
                Target2 = t2,
                RiskPoints = risk,
                RewardPoints = dist,
                RrRatio = risk > 0 ? dist / risk : 0.0,
                StopCapped = capped
            };
        }

        /// <summary>
        /// FTFC score: +1 per TF where price &gt; open, -1 where below. Flat counts 0.
        /// Mirror of signals.py per-bar scoring (price vs TF opens ffilled).
        /// </summary>
        public static int FtfcScore(double price, double[] tfOpens)
        {
            int score = 0;
            if (tfOpens == null) return 0;
            foreach (double op in tfOpens)
            {
                if (op <= 0 || double.IsNaN(op)) continue;
                if (price > op) score++;
                else if (price < op) score--;
            }
            return score;
        }

        /// <summary>
        /// Session entry gate — mirror of session.entry_allowed().
        /// Times are NT8 Time[0] wall-clock (exchange tz); killzones flat pairs.
        /// </summary>
        public static bool EntryAllowed(
            DateTime barTime, int earliestHhmm, int latestHhmm, int flattenHhmm,
            int[] killzones /* flat {s1,e1,s2,e2...} as HHMM */, bool useKillzones)
        {
            int t = barTime.Hour * 100 + barTime.Minute;
            if (t < earliestHhmm || t > latestHhmm || t >= flattenHhmm) return false;
            if (useKillzones && killzones != null && killzones.Length >= 2)
            {
                for (int k = 0; k + 1 < killzones.Length; k += 2)
                    if (t >= killzones[k] && t <= killzones[k + 1]) return true;
                return false;
            }
            return true;
        }

        public static int ParseHhmm(string s, int fallback)
        {
            try
            {
                var parts = s.Split(':');
                return int.Parse(parts[0]) * 100 + int.Parse(parts[1]);
            }
            catch { return fallback; }
        }
    }

    /// <summary>
    /// Tracks per-timeframe candle opens for the FTFC gate — C# mirror of the
    /// opens signals.py ffill()s onto the signal index.
    /// Daily open is anchored at the 18:00 ET Globex session open (NOT midnight),
    /// matching _session_opens_daily() in Python. Intraday buckets (1H/15m/5m)
    /// are wall-clock aligned, matching both TheStratFTFCHud and resample(origin=start_day).
    /// Convention (same as RiskManagerBase): Time[0] is exchange-local, desk runs NT8 on ET.
    /// One instance per bot; call Update() on every bar before reading the opens.
    /// </summary>
    public sealed class StratSessionTracker
    {
        public double DayOpen { get; private set; }
        public double H1Open { get; private set; }
        public double M15Open { get; private set; }
        public double M5Open { get; private set; }

        private DateTime sessionDate = DateTime.MinValue;
        private int hour = -1;
        private int m15Bucket = -1;
        private int hour15 = -1;
        private int m5Bucket = -1;
        private int hour5 = -1;

        public void Update(DateTime barTime, double barOpen)
        {
            // Globex session date: bars before 18:00 belong to the session that
            // opened 18:00 the prior day (mirror of Python _session_opens_daily).
            DateTime sess = barTime.Hour < 18 ? barTime.Date.AddDays(-1) : barTime.Date;
            if (sess != sessionDate || DayOpen <= 0)
            {
                sessionDate = sess;
                DayOpen = barOpen;
            }
            if (barTime.Hour != hour || H1Open <= 0)
            {
                hour = barTime.Hour;
                H1Open = barOpen;
            }
            // Hour guard: 10:00 and 11:00 share bucket 0 but are different candles
            // (same guard as TheStratFTFCHud).
            int b15 = barTime.Minute / 15;
            if (b15 != m15Bucket || barTime.Hour != hour15 || M15Open <= 0)
            {
                m15Bucket = b15;
                hour15 = barTime.Hour;
                M15Open = barOpen;
            }
            int b5 = barTime.Minute / 5;
            if (b5 != m5Bucket || barTime.Hour != hour5 || M5Open <= 0)
            {
                m5Bucket = b5;
                hour5 = barTime.Hour;
                M5Open = barOpen;
            }
        }

        public int FtfcScore(double price)
        {
            return StratCore.FtfcScore(price, new double[] { DayOpen, H1Open, M15Open, M5Open });
        }
    }
}
