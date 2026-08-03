// ═══════════════════════════════════════════════════════════════════════════
// HitRateTrackerLib.cs — Reusable Hit-Rate Tracking Engine for NT8 Indicators
//
// Pure C#, NT8-free. Designed for reuse across LiquidityLevels, SessionRanges,
// and future Asia/London indicators. Each host indicator supplies:
//   - A HitWindow (the session time range to check for hits)
//   - A Func<DateTime, double> price provider per level (how to get the level
//     price for a given historical session date)
//
// Hit definition (direction-agnostic):
//   A bar's range intersects the level price: bar.High >= level && bar.Low <= level.
//   The FIRST such bar in the window is the "hit"; its time (minutes-of-day) is
//   recorded as HitTimeMin for future time-distribution analysis.
//
// Today's live session is tracked separately and NOT counted in historical
// hit_rate / streak stats. On day rollover it commits into history.
//
// Design doc: Phase 2 Statistics — Hit Rate Tracking (2026-08-03)
// ═══════════════════════════════════════════════════════════════════════════

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    // ════════════════════════════════════════════════════════════════════════
    // HitMode — how a "hit" is detected (extensible for future modes)
    // ════════════════════════════════════════════════════════════════════════
    public enum HitMode
    {
        Through,    // bar range intersects level (High >= level && Low <= level) — default
        Close,      // bar closes through level (future)
        Sweep       // full sweep detection wick+body (future)
    }

    // ════════════════════════════════════════════════════════════════════════
    // HitWindow — the time range within a session to check for hits
    // ════════════════════════════════════════════════════════════════════════
    public class HitWindow
    {
        public int StartMin { get; set; }    // ET minutes-of-day (e.g., 570 = 09:30)
        public int EndMin { get; set; }      // ET minutes-of-day (e.g., 960 = 16:00)
        public string Label { get; set; }   // "NY RTH", "Asia", "London"

        public bool CrossesMidnight => EndMin < StartMin;

        // Fence-post convention (per LIQUIDITY_LEVELS_INDICATOR_DESIGN.md §J.1):
        // NT8 close-timestamped bars: bar stamped 08:05 opens at 08:00.
        // Window start: barMins > StartMin (first bar whose OPEN is at/after start)
        // Window end (inclusive): barMins <= EndMin (last bar that closes within window)
        public bool InWindow(int barMins)
        {
            if (CrossesMidnight)
                return barMins > StartMin || barMins <= EndMin;
            return barMins > StartMin && barMins <= EndMin;
        }

        public string TimeRangeString
        {
            get
            {
                return $"{MinToTimeStr(StartMin)}-{MinToTimeStr(EndMin)}";
            }
        }

        public static string MinToTimeStr(int mins)
        {
            int h = mins / 60;
            int m = mins % 60;
            return $"{h:D2}:{m:D2}";
        }

        public static int TimeStrToMin(string s)
        {
            var parts = s.Split(':');
            if (parts.Length == 2 && int.TryParse(parts[0], out int h) && int.TryParse(parts[1], out int m))
                return h * 60 + m;
            return -1;
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // HitRateConfig — per-indicator configuration
    // ════════════════════════════════════════════════════════════════════════
    public class HitRateConfig
    {
        public int LookbackDays { get; set; } = 500;
        public int RecentN { get; set; } = 10;
        public int StreakMinHits { get; set; } = 1;
        public HitMode Mode { get; set; } = HitMode.Through;
    }

    // ════════════════════════════════════════════════════════════════════════
    // SessionBars — bars belonging to one session date, within the hit window
    // ════════════════════════════════════════════════════════════════════════
    public class SessionBars
    {
        public DateTime SessionDate;
        public List<BarData> WindowBars = new List<BarData>();
    }

    // ════════════════════════════════════════════════════════════════════════
    // BarData — lightweight bar snapshot (decoupled from NT8 Bar type)
    // ════════════════════════════════════════════════════════════════════════
    public class BarData
    {
        public DateTime TimeEt;
        public int BarMins;      // minutes-of-day (ET)
        public double High;
        public double Low;
        public double Open;
        public double Close;
        public int BarIndex;
    }

    // ════════════════════════════════════════════════════════════════════════
    // HitSample — committed per-day, per-level result
    // ════════════════════════════════════════════════════════════════════════
    public class HitSample
    {
        public DateTime SessionDate;
        public double LevelPrice;
        public bool Hit;
        public int HitTimeMin;    // minutes-of-day of FIRST hit, 0 if miss
    }

    // ════════════════════════════════════════════════════════════════════════
    // LevelHitStats — computed statistics for one level (drives tooltip + debug)
    // ════════════════════════════════════════════════════════════════════════
    public class LevelHitStats
    {
        public string LevelName;

        // Historical stats (committed past sessions only)
        public int DaysInHistory;
        public int TotalHits;
        public double HitRate;          // TotalHits / DaysInHistory * 100
        public int CurrentStreak;       // +N = consecutive hits, -N = consecutive misses
        public int MaxHitStreak;
        public int MaxMissStreak;

        // Today's live state (NOT counted in historical stats)
        public double TodayPrice;
        public bool TodayHit;
        public bool InWindow;

        // Config / debug fields
        public string TimeWindowLabel;
        public int NewDaysDetected;
        public int LocalIndex;
        public int LookbackDays;
        public int StreakMinHits;
        public int RecentN;

        // Recent history (most recent first; null = today/pending)
        public List<bool?> RecentHistory = new List<bool?>();
        public int RecentHitsCount;

        // Computed display strings
        public string RecentHistoryString
        {
            get
            {
                var sb = new StringBuilder();
                for (int i = 0; i < RecentHistory.Count; i++)
                {
                    if (i > 0) sb.Append(' ');
                    if (RecentHistory[i] == null)
                        sb.Append('/');
                    else if (RecentHistory[i] == true)
                        sb.Append('x');
                    else
                        sb.Append('-');
                }
                return sb.ToString();
            }
        }

        public string CurrentStreakDisplay
        {
            get
            {
                if (CurrentStreak > 0) return $"{CurrentStreak} hits";
                if (CurrentStreak < 0) return $"{CurrentStreak} misses";
                return "0";
            }
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // HitRateEngine — static, pure computation engine
    // ════════════════════════════════════════════════════════════════════════
    public static class HitRateEngine
    {
        // ── Build per-session-date window bars from raw bar data ────────────
        // One pass over all bars; groups by session date and filters to window.
        // sessionDateFromBarEt: maps a bar's ET time to its session date
        //   (e.g., 18:00 ET Monday → Tuesday's session; everything before 18:00
        //    belongs to the prior session date).
        public static List<SessionBars> BuildSessionBars(
            List<BarData> allBars,
            HitWindow window,
            Func<DateTime, DateTime> sessionDateFromBarEt)
        {
            var sessions = new List<SessionBars>();
            var byDate = new Dictionary<DateTime, SessionBars>();

            foreach (var bar in allBars)
            {
                DateTime sessDate = sessionDateFromBarEt(bar.TimeEt);
                if (!byDate.TryGetValue(sessDate, out var sb))
                {
                    sb = new SessionBars { SessionDate = sessDate };
                    byDate[sessDate] = sb;
                    sessions.Add(sb);
                }
                if (window.InWindow(bar.BarMins))
                    sb.WindowBars.Add(bar);
            }

            // Sort by session date
            sessions.Sort((a, b) => a.SessionDate.CompareTo(b.SessionDate));
            return sessions;
        }

        // ── Build hit history for one level across all sessions ──────────────
        // levelPriceProvider: given a session date, returns the level price
        //   that was active for that session (e.g., PDH = prior day's high).
        //   Returns 0 if level not available for that date (skip session).
        // Only historical sessions (where we have complete window data) are
        // included. The live/today session must be excluded by the caller.
        public static List<HitSample> BuildHistory(
            string levelName,
            Func<DateTime, double> levelPriceProvider,
            List<SessionBars> historicalSessions,
            HitRateConfig cfg)
        {
            var history = new List<HitSample>();

            foreach (var sess in historicalSessions)
            {
                // Skip sessions with no window bars (weekends/holidays/no data)
                if (sess.WindowBars.Count == 0) continue;

                double price = levelPriceProvider(sess.SessionDate);
                if (price <= 0) continue;

                bool hit = false;
                int hitMin = 0;

                // Find FIRST hit in the window
                foreach (var bar in sess.WindowBars)
                {
                    if (IsHit(bar, price, cfg.Mode))
                    {
                        hit = true;
                        hitMin = bar.BarMins;
                        break;
                    }
                }

                history.Add(new HitSample
                {
                    SessionDate = sess.SessionDate,
                    LevelPrice = price,
                    Hit = hit,
                    HitTimeMin = hit ? hitMin : 0
                });
            }

            // Trim to lookback (keep most recent N)
            if (history.Count > cfg.LookbackDays)
                history = history.Skip(history.Count - cfg.LookbackDays).ToList();

            return history;
        }

        // ── Hit test: bar range intersects level ─────────────────────────────
        public static bool IsHit(BarData bar, double levelPrice, HitMode mode)
        {
            switch (mode)
            {
                case HitMode.Through:
                    return bar.High >= levelPrice && bar.Low <= levelPrice;
                case HitMode.Close:
                    // Future: bar closes beyond the level
                    return false;
                case HitMode.Sweep:
                    // Future: full sweep detection (wick depth + close back through)
                    return false;
                default:
                    return bar.High >= levelPrice && bar.Low <= levelPrice;
            }
        }

        // ── Compute stats from committed history + today's live state ────────
        public static LevelHitStats ComputeStats(
            string levelName,
            List<HitSample> history,
            double todayPrice,
            bool todayHit,
            bool inWindow,
            int localIndex,
            int newDaysDetected,
            HitRateConfig cfg,
            HitWindow window)
        {
            int daysInHistory = history.Count;
            int totalHits = history.Count(h => h.Hit);
            double hitRate = daysInHistory > 0 ? (totalHits * 100.0 / daysInHistory) : 0.0;

            // Streaks: walk history from most recent backward
            int currentStreak = 0;
            int maxHitStreak = 0;
            int maxMissStreak = 0;

            if (history.Count > 0)
            {
                // Current streak: count from the last entry backward
                bool lastWasHit = history[history.Count - 1].Hit;
                for (int i = history.Count - 1; i >= 0; i--)
                {
                    if (history[i].Hit == lastWasHit)
                    {
                        currentStreak += lastWasHit ? 1 : -1;
                    }
                    else
                    {
                        break;
                    }
                }

                // Max streaks: single forward pass
                int hitRun = 0, missRun = 0;
                foreach (var s in history)
                {
                    if (s.Hit)
                    {
                        hitRun++;
                        missRun = 0;
                        if (hitRun > maxHitStreak) maxHitStreak = hitRun;
                    }
                    else
                    {
                        missRun++;
                        hitRun = 0;
                        if (missRun > maxMissStreak) maxMissStreak = missRun;
                    }
                }
            }

            // Recent history (most recent first, up to RecentN; null = today)
            var recent = new List<bool?>();
            int recentHits = 0;

            // Add today as '/' (null) at the front if in window
            int startIdx = inWindow ? -1 : 0;  // -1 signals today placeholder

            for (int i = 0; i < cfg.RecentN; i++)
            {
                int histIdx = history.Count - 1 - i;
                if (i == 0 && inWindow)
                {
                    recent.Add(null);  // today = '/'
                    continue;
                }
                if (histIdx >= 0)
                {
                    bool h = history[histIdx].Hit;
                    recent.Add(h);
                    if (h) recentHits++;
                }
            }

            return new LevelHitStats
            {
                LevelName = levelName,
                DaysInHistory = daysInHistory,
                TotalHits = totalHits,
                HitRate = Math.Round(hitRate, 1),
                CurrentStreak = currentStreak,
                MaxHitStreak = maxHitStreak,
                MaxMissStreak = maxMissStreak,
                TodayPrice = todayPrice,
                TodayHit = todayHit,
                InWindow = inWindow,
                TimeWindowLabel = window.TimeRangeString,
                NewDaysDetected = newDaysDetected,
                LocalIndex = localIndex,
                LookbackDays = cfg.LookbackDays,
                StreakMinHits = cfg.StreakMinHits,
                RecentN = cfg.RecentN,
                RecentHistory = recent,
                RecentHitsCount = recentHits
            };
        }

        // ── Live update within today's window (called per bar) ───────────────
        // Sets TodayHit=true if a hit is detected (first hit only).
        public static void AdvanceToday(
            LevelHitStats stats,
            DateTime barEt,
            double barHigh,
            double barLow,
            double levelPrice)
        {
            if (stats.TodayHit) return;  // first hit only
            if (levelPrice <= 0) return;

            if (barHigh >= levelPrice && barLow <= levelPrice)
            {
                stats.TodayHit = true;
            }
        }

        // ── Commit today's live result into history ──────────────────────────
        // Called on day rollover. Returns the sample to append.
        public static HitSample CommitToday(
            string levelName,
            DateTime sessionDate,
            double levelPrice,
            bool hit,
            int hitTimeMin)
        {
            return new HitSample
            {
                SessionDate = sessionDate,
                LevelPrice = levelPrice,
                Hit = hit,
                HitTimeMin = hit ? hitTimeMin : 0
            };
        }

        // ── Re-trim history to lookback and recompute stats ──────────────────
        // Convenience: re-trim an existing history list and recompute stats.
        public static List<HitSample> TrimHistory(List<HitSample> history, int lookbackDays)
        {
            if (history.Count <= lookbackDays) return history;
            return history.Skip(history.Count - lookbackDays).ToList();
        }
    }
}