// ═══════════════════════════════════════════════════════════════════════════
// LiquidityLevelsCatalog.cs — Static catalog of all 52+ liquidity level definitions
//
// Design doc: docs/architecture/LIQUIDITY_LEVELS_INDICATOR_DESIGN.md §C
// ═══════════════════════════════════════════════════════════════════════════

using System.Collections.Generic;

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    public static class LiquidityLevelsCatalog
    {
        // ═══ Get all level definitions ═══
        public static List<LevelDef> GetAllLevels()
        {
            var levels = new List<LevelDef>();

            // ── Prior Day (T1 sweep targets) ──
            levels.Add(new LevelDef("PDH", "Prior Day High", LevelCategory.PriorDay, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "PDH"));
            levels.Add(new LevelDef("PDL", "Prior Day Low", LevelCategory.PriorDay, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "PDL"));
            levels.Add(new LevelDef("PDC", "Prior Day Close", LevelCategory.PriorDay, LevelRole.SweepTarget, LevelSource.PriorDayOHLC, "PriorClose"));
            levels.Add(new LevelDef("PDM", "Prior Day Mid", LevelCategory.PriorDay, LevelRole.ConfluenceFactor, LevelSource.Internal, "PriorDayMid"));  // (PDH+PDL)/2
            levels.Add(new LevelDef("Settlement", "Settlement", LevelCategory.PriorDay, LevelRole.ConfluenceFactor, LevelSource.Internal, "Settlement"));  // prior day settlement close

            // ── Prior Week (T1/T3) ──
            levels.Add(new LevelDef("PWH", "Prior Week High", LevelCategory.PriorWeek, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "PWH"));
            levels.Add(new LevelDef("PWL", "Prior Week Low", LevelCategory.PriorWeek, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "PWL"));
            levels.Add(new LevelDef("PWM", "Prior Week Mid", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.Internal, "PriorWeekMid"));  // (PWH+PWL)/2
            levels.Add(new LevelDef("PWC", "Prior Week Close", LevelCategory.PriorWeek, LevelRole.SweepTarget, LevelSource.Internal, "PriorWeekClose"));  // prev week close (settlement)
            levels.Add(new LevelDef("MH", "Monday High", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "MH"));
            levels.Add(new LevelDef("ML", "Monday Low", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "ML"));
            levels.Add(new LevelDef("GH", "Globex High", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "GH"));
            levels.Add(new LevelDef("GL", "Globex Low", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "GL"));

            // ── Prior Month (T3) ──
            levels.Add(new LevelDef("PMH", "Prev Month High", LevelCategory.PriorMonth, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "PMH"));
            levels.Add(new LevelDef("PML", "Prev Month Low", LevelCategory.PriorMonth, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "PML"));
            levels.Add(new LevelDef("PMM", "Prev Month Mid", LevelCategory.PriorMonth, LevelRole.ConfluenceFactor, LevelSource.Internal, "PriorMonthMid"));  // (PMH+PML)/2

            // ── Session Opens (T2 — NEW via SessionOpensEngine) ──
            levels.Add(new LevelDef("MidnightOpen", "Midnight Open", LevelCategory.SessionOpen, LevelRole.SweepTarget, LevelSource.SessionOpens, "MidnightOpen"));
            levels.Add(new LevelDef("LondonOpen", "London Open", LevelCategory.SessionOpen, LevelRole.SweepTarget, LevelSource.SessionOpens, "LondonOpen"));
            levels.Add(new LevelDef("GlobexOpen", "Globex Open", LevelCategory.SessionOpen, LevelRole.SweepTarget, LevelSource.SessionOpens, "GlobexOpen"));  // 18:00 ET overnight session open
            levels.Add(new LevelDef("RTHOpen", "RTH / NY Open (09:30 ET)", LevelCategory.SessionOpen, LevelRole.SweepTarget, LevelSource.SessionOpens, "RTHOpen"));  // 09:30 ET RTH open
            levels.Add(new LevelDef("Open_04H", "Open 04:00", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_04H"));
            levels.Add(new LevelDef("Open_08H", "Open 08:00", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_08H"));
            levels.Add(new LevelDef("Open_12H", "Open 12:00", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_12H"));
            levels.Add(new LevelDef("Open_16H", "Open 16:00", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_16H"));
            levels.Add(new LevelDef("Open_20H", "Open 20:00", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_20H"));

            // ── Session Ranges (T1 — from SessionRanges indicator) ──
            levels.Add(new LevelDef("AsiaH", "Asia Range High", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "Asia Range.High"));
            levels.Add(new LevelDef("AsiaL", "Asia Range Low", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "Asia Range.Low"));
            levels.Add(new LevelDef("AsiaMid", "Asia Range Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "Asia Range.Mid"));  // (AsiaH+AsiaL)/2
            levels.Add(new LevelDef("LonH", "London Range High", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "London Range.High"));
            levels.Add(new LevelDef("LonL", "London Range Low", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "London Range.Low"));
            levels.Add(new LevelDef("LonMid", "London Range Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "London Range.Mid"));  // (LonH+LonL)/2
            levels.Add(new LevelDef("LonOrMid", "London OR Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "London OR.Mid"));  // (LonOrH+LonOrL)/2
            levels.Add(new LevelDef("GlbH", "Globex Range High", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "Globex Range.High"));
            levels.Add(new LevelDef("GlbL", "Globex Range Low", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "Globex Range.Low"));
            levels.Add(new LevelDef("GlbMid", "Globex Range Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "Globex Range.Mid"));  // (GlbH+GlbL)/2
            levels.Add(new LevelDef("IBH", "Initial Balance High", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "IB.High"));
            levels.Add(new LevelDef("IBL", "Initial Balance Low", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "IB.Low"));
            levels.Add(new LevelDef("IBMid", "Initial Balance Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "IB.Mid"));

            // ── P12 (18:00-06:00 ET overnight range) — Profiler levels 8-10 ──
            levels.Add(new LevelDef("P12High", "Overnight P12 High", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.Internal, "P12High"));   // 18:00-06:00 ET H
            levels.Add(new LevelDef("P12Low", "Overnight P12 Low", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.Internal, "P12Low"));    // 18:00-06:00 ET L
            levels.Add(new LevelDef("P12Mid", "Overnight P12 Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "P12Mid"));   // (P12H+P12L)/2

            // ── NY P12 (06:00-17:00 ET NY session range) + Prev ──
            levels.Add(new LevelDef("NYP12High", "NY P12 High", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.Internal, "NYP12High"));    // 06:00-17:00 ET H
            levels.Add(new LevelDef("NYP12Low", "NY P12 Low", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.Internal, "NYP12Low"));     // 06:00-17:00 ET L
            levels.Add(new LevelDef("NYP12Mid", "NY P12 Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "NYP12Mid"));    // (NY_P12H+NY_P12L)/2
            levels.Add(new LevelDef("PrevNYP12High", "Prev NY P12 High", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "PrevNYP12High"));
            levels.Add(new LevelDef("PrevNYP12Low", "Prev NY P12 Low", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "PrevNYP12Low"));
            levels.Add(new LevelDef("PrevNYP12Mid", "Prev NY P12 Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "PrevNYP12Mid"));

            // ── Intraday (T1/T3) ──
            levels.Add(new LevelDef("HOD", "High of Day", LevelCategory.Intraday, LevelRole.SweepTarget, LevelSource.CurrentDayOHL, "CurrentHigh"));
            levels.Add(new LevelDef("LOD", "Low of Day", LevelCategory.Intraday, LevelRole.SweepTarget, LevelSource.CurrentDayOHL, "CurrentLow"));
            levels.Add(new LevelDef("NYH", "NY Session High", LevelCategory.Intraday, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "NYH"));
            levels.Add(new LevelDef("NYL", "NY Session Low", LevelCategory.Intraday, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "NYL"));

            // ── Volume Profile (T4) ──
            levels.Add(new LevelDef("CurrentPOC", "Current Session POC", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "CurrentPOCPlot"));
            levels.Add(new LevelDef("CurrentVAH", "Current Session VAH", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "CurrentVAHPlot"));
            levels.Add(new LevelDef("CurrentVAL", "Current Session VAL", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "CurrentVALPlot"));
            levels.Add(new LevelDef("PrevDayPOC", "Prev Day POC", LevelCategory.VolumeProfile, LevelRole.SweepTarget, LevelSource.RedTailVolumeProfile, "PrevDayPOCPlot"));
            levels.Add(new LevelDef("PrevDayVAH", "Prev Day VAH", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "PrevDayVAHPlot"));
            levels.Add(new LevelDef("PrevDayVAL", "Prev Day VAL", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "PrevDayVALPlot"));
            levels.Add(new LevelDef("OvernightPOC", "Overnight POC", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightPOCPlot"));
            levels.Add(new LevelDef("OvernightVAH", "Overnight VAH", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightVAHPlot"));
            levels.Add(new LevelDef("OvernightVAL", "Overnight VAL", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightVALPlot"));
            levels.Add(new LevelDef("OvernightHigh", "Overnight High", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightHighPlot"));
            levels.Add(new LevelDef("OvernightLow", "Overnight Low", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightLowPlot"));
            levels.Add(new LevelDef("NakedPOC", "Naked POC", LevelCategory.VolumeProfile, LevelRole.SweepTarget, LevelSource.RedTailVolumeProfile, "GetWeeklyNakedPOCLevels", true));
            levels.Add(new LevelDef("NakedVAH", "Naked VAH", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "GetWeeklyNakedVAHLevels", true));
            levels.Add(new LevelDef("NakedVAL", "Naked VAL", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "GetWeeklyNakedVALLevels", true));

            // ── Structure (from RedTailMarketStructure) ──
            levels.Add(new LevelDef("StrongLevels", "Strong Level", LevelCategory.Structure, LevelRole.SweepTarget, LevelSource.RedTailMarketStructure, "GetStrongLevels", true));
            levels.Add(new LevelDef("OBZones", "Order Block Zone", LevelCategory.Structure, LevelRole.ConfluenceFactor, LevelSource.RedTailMarketStructure, "GetOBZones", true));

            // ── Pivots (T5 — off by default) ──
            levels.Add(new LevelDef("PP", "Pivot Point", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "Pp"));
            levels.Add(new LevelDef("R1", "Resistance 1", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "R1"));
            levels.Add(new LevelDef("R2", "Resistance 2", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "R2"));
            levels.Add(new LevelDef("R3", "Resistance 3", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "R3"));
            levels.Add(new LevelDef("S1", "Support 1", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "S1"));
            levels.Add(new LevelDef("S2", "Support 2", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "S2"));
            levels.Add(new LevelDef("S3", "Support 3", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "S3"));

            // ── Fibs (T5 — off by default) ──
            levels.Add(new LevelDef("Fib 23.6%", "Fibonacci 23.6%", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel1"));
            levels.Add(new LevelDef("Fib 38.2%", "Fibonacci 38.2%", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel2"));
            levels.Add(new LevelDef("Fib 50.0%", "Fibonacci 50.0% (Mid)", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel3"));
            levels.Add(new LevelDef("Fib 61.8%", "Fibonacci 61.8%", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel4"));
            levels.Add(new LevelDef("Fib 78.6%", "Fibonacci 78.6%", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel5"));
            levels.Add(new LevelDef("Fib 100%", "Fibonacci 100% (PDH)", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel6"));
            levels.Add(new LevelDef("Fib 127.2%", "Fibonacci 127.2% (Ext)", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel7"));
            levels.Add(new LevelDef("Fib 161.8%", "Fibonacci 161.8% (Ext)", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel8"));
            levels.Add(new LevelDef("Fib -27.2%", "Fibonacci -27.2% (Ext)", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel9"));
            levels.Add(new LevelDef("Fib -61.8%", "Fibonacci -61.8% (Ext)", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "FibLevel10"));

            return levels;
        }

        // ═══ Get only sweep targets (T1 + T2) ═══
        public static List<LevelDef> GetSweepTargets()
        {
            var all = GetAllLevels();
            var targets = new List<LevelDef>();
            foreach (var def in all)
            {
                if (def.Role == LevelRole.SweepTarget || def.Role == LevelRole.Both)
                    targets.Add(def);
            }
            return targets;
        }

        // ═══ Get session open definitions ═══
        public static List<SessionOpenDef> GetSessionOpens(bool include4H = true)
        {
            var opens = new List<SessionOpenDef>();

            opens.Add(new SessionOpenDef
            {
                Name = "MidnightOpen",
                HourET = 0, MinuteET = 0,
                IsDSTAware = false, DstHourET = 0,
                IsEnabled = true
            });

            if (include4H)
            {
                opens.Add(new SessionOpenDef { Name = "Open_04H", HourET = 4, MinuteET = 0, IsEnabled = true });
                opens.Add(new SessionOpenDef { Name = "Open_08H", HourET = 8, MinuteET = 0, IsEnabled = true });
                opens.Add(new SessionOpenDef { Name = "Open_12H", HourET = 12, MinuteET = 0, IsEnabled = true });
                opens.Add(new SessionOpenDef { Name = "Open_16H", HourET = 16, MinuteET = 0, IsEnabled = true });
                opens.Add(new SessionOpenDef { Name = "Open_20H", HourET = 20, MinuteET = 0, IsEnabled = true });
            }

            // London open: 02:00 EST / 03:00 EDT (DST-aware)
            opens.Add(new SessionOpenDef
            {
                Name = "LondonOpen",
                HourET = 2, MinuteET = 0,
                IsDSTAware = true, DstHourET = 3,
                IsEnabled = true
            });

            // Globex open: 18:00 ET (overnight session start)
            opens.Add(new SessionOpenDef
            {
                Name = "GlobexOpen",
                HourET = 18, MinuteET = 0,
                IsDSTAware = false, DstHourET = 18,
                IsEnabled = true
            });

            // RTH open: 09:30 ET (regular trading hours start = IB open)
            opens.Add(new SessionOpenDef
            {
                Name = "RTHOpen",
                HourET = 9, MinuteET = 30,
                IsDSTAware = false, DstHourET = 9,
                IsEnabled = true
            });

            return opens;
        }
    }
}