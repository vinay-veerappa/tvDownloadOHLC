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
            levels.Add(new LevelDef("PDH", LevelCategory.PriorDay, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "PDH"));
            levels.Add(new LevelDef("PDL", LevelCategory.PriorDay, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "PDL"));
            levels.Add(new LevelDef("PDC", LevelCategory.PriorDay, LevelRole.SweepTarget, LevelSource.PriorDayOHLC, "PriorClose"));
            levels.Add(new LevelDef("PDM", LevelCategory.PriorDay, LevelRole.ConfluenceFactor, LevelSource.Internal, "PriorDayMid"));  // (PDH+PDL)/2
            levels.Add(new LevelDef("Settlement", LevelCategory.PriorDay, LevelRole.ConfluenceFactor, LevelSource.Internal, "Settlement"));  // prior day settlement close

            // ── Prior Week (T1/T3) ──
            levels.Add(new LevelDef("PWH", LevelCategory.PriorWeek, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "PWH"));
            levels.Add(new LevelDef("PWL", LevelCategory.PriorWeek, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "PWL"));
            levels.Add(new LevelDef("PWM", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.Internal, "PriorWeekMid"));  // (PWH+PWL)/2
            levels.Add(new LevelDef("PWC", LevelCategory.PriorWeek, LevelRole.SweepTarget, LevelSource.Internal, "PriorWeekClose"));  // prev week close (settlement)
            levels.Add(new LevelDef("MH", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "MH"));
            levels.Add(new LevelDef("ML", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "ML"));
            levels.Add(new LevelDef("GH", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "GH"));
            levels.Add(new LevelDef("GL", LevelCategory.PriorWeek, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "GL"));

            // ── Prior Month (T3) ──
            levels.Add(new LevelDef("PMH", LevelCategory.PriorMonth, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "PMH"));
            levels.Add(new LevelDef("PML", LevelCategory.PriorMonth, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "PML"));            levels.Add(new LevelDef("PMM", LevelCategory.PriorMonth, LevelRole.ConfluenceFactor, LevelSource.Internal, "PriorMonthMid"));  // (PMH+PML)/2
            // ── Session Opens (T2 — NEW via SessionOpensEngine) ──
            levels.Add(new LevelDef("MidnightOpen", LevelCategory.SessionOpen, LevelRole.SweepTarget, LevelSource.SessionOpens, "MidnightOpen"));
            levels.Add(new LevelDef("LondonOpen", LevelCategory.SessionOpen, LevelRole.SweepTarget, LevelSource.SessionOpens, "LondonOpen"));
            levels.Add(new LevelDef("GlobexOpen", LevelCategory.SessionOpen, LevelRole.SweepTarget, LevelSource.SessionOpens, "GlobexOpen"));  // 18:00 ET overnight session open
            levels.Add(new LevelDef("RTHOpen", LevelCategory.SessionOpen, LevelRole.SweepTarget, LevelSource.SessionOpens, "RTHOpen"));  // 09:30 ET RTH session open
            levels.Add(new LevelDef("NYOpen", LevelCategory.SessionOpen, LevelRole.SweepTarget, LevelSource.CurrentDayOHL, "CurrentOpen"));
            levels.Add(new LevelDef("Open_04H", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_04H"));
            levels.Add(new LevelDef("Open_08H", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_08H"));
            levels.Add(new LevelDef("Open_12H", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_12H"));
            levels.Add(new LevelDef("Open_16H", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_16H"));
            levels.Add(new LevelDef("Open_20H", LevelCategory.SessionOpen, LevelRole.ConfluenceFactor, LevelSource.SessionOpens, "Open_20H"));

            // ── Session Ranges (T1 — from SessionRanges indicator) ──
            levels.Add(new LevelDef("AsiaHigh", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "Asia Range.High"));
            levels.Add(new LevelDef("AsiaLow", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "Asia Range.Low"));
            levels.Add(new LevelDef("AsiaMid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "Asia Range.Mid"));  // (AsiaH+AsiaL)/2
            levels.Add(new LevelDef("LondonHigh", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "London Range.High"));
            levels.Add(new LevelDef("LondonLow", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "London Range.Low"));
            levels.Add(new LevelDef("LondonMid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "London Range.Mid"));  // (LonH+LonL)/2
            levels.Add(new LevelDef("LondonOrMid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "London OR.Mid"));  // (LonOrH+LonOrL)/2
            levels.Add(new LevelDef("GlobexHigh", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "Globex Range.High"));
            levels.Add(new LevelDef("GlobexLow", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "Globex Range.Low"));
            levels.Add(new LevelDef("GlobexMid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "Globex Range.Mid"));  // (GlbH+GlbL)/2
            levels.Add(new LevelDef("IBHigh", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "IB.High"));
            levels.Add(new LevelDef("IBLow", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.SessionRanges, "IB.Low"));
            levels.Add(new LevelDef("IBMid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.SessionRanges, "IB.Mid"));

            // ── P12 (18:00-06:00 ET overnight range) — Profiler levels 8-10 ──
            levels.Add(new LevelDef("P12High", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.Internal, "P12High"));   // 18:00-06:00 ET H
            levels.Add(new LevelDef("P12Low", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.Internal, "P12Low"));    // 18:00-06:00 ET L
            levels.Add(new LevelDef("P12Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "P12Mid"));   // (P12H+P12L)/2

            // ── NY P12 (06:00-17:00 ET NY session range) + Prev ──
            levels.Add(new LevelDef("NYP12High", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.Internal, "NYP12High"));    // 06:00-17:00 ET H
            levels.Add(new LevelDef("NYP12Low", LevelCategory.SessionRange, LevelRole.SweepTarget, LevelSource.Internal, "NYP12Low"));     // 06:00-17:00 ET L
            levels.Add(new LevelDef("NYP12Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "NYP12Mid"));    // (NY_P12H+NY_P12L)/2
            levels.Add(new LevelDef("PrevNYP12High", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "PrevNYP12High"));
            levels.Add(new LevelDef("PrevNYP12Low", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "PrevNYP12Low"));
            levels.Add(new LevelDef("PrevNYP12Mid", LevelCategory.SessionRange, LevelRole.ConfluenceFactor, LevelSource.Internal, "PrevNYP12Mid"));

            // ── Intraday (T1/T3) ──
            levels.Add(new LevelDef("HOD", LevelCategory.Intraday, LevelRole.SweepTarget, LevelSource.CurrentDayOHL, "CurrentHigh"));
            levels.Add(new LevelDef("LOD", LevelCategory.Intraday, LevelRole.SweepTarget, LevelSource.CurrentDayOHL, "CurrentLow"));
            levels.Add(new LevelDef("NYH", LevelCategory.Intraday, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "NYH"));
            levels.Add(new LevelDef("NYL", LevelCategory.Intraday, LevelRole.SweepTarget, LevelSource.RedTailKeyLevels, "NYL"));

            // ── Volume Profile (T4) ──
            levels.Add(new LevelDef("CurrentPOC", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "CurrentPOCPlot"));
            levels.Add(new LevelDef("CurrentVAH", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "CurrentVAHPlot"));
            levels.Add(new LevelDef("CurrentVAL", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "CurrentVALPlot"));
            levels.Add(new LevelDef("PrevDayPOC", LevelCategory.VolumeProfile, LevelRole.SweepTarget, LevelSource.RedTailVolumeProfile, "PrevDayPOCPlot"));
            levels.Add(new LevelDef("PrevDayVAH", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "PrevDayVAHPlot"));
            levels.Add(new LevelDef("PrevDayVAL", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "PrevDayVALPlot"));
            levels.Add(new LevelDef("OvernightPOC", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightPOCPlot"));
            levels.Add(new LevelDef("OvernightVAH", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightVAHPlot"));
            levels.Add(new LevelDef("OvernightVAL", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightVALPlot"));
            levels.Add(new LevelDef("OvernightHigh", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightHighPlot"));
            levels.Add(new LevelDef("OvernightLow", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "OvernightLowPlot"));
            levels.Add(new LevelDef("NakedPOC", LevelCategory.VolumeProfile, LevelRole.SweepTarget, LevelSource.RedTailVolumeProfile, "GetWeeklyNakedPOCLevels", true));
            levels.Add(new LevelDef("NakedVAH", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "GetWeeklyNakedVAHLevels", true));
            levels.Add(new LevelDef("NakedVAL", LevelCategory.VolumeProfile, LevelRole.ConfluenceFactor, LevelSource.RedTailVolumeProfile, "GetWeeklyNakedVALLevels", true));

            // ── Structure (from RedTailMarketStructure) ──
            levels.Add(new LevelDef("StrongLevels", LevelCategory.Structure, LevelRole.SweepTarget, LevelSource.RedTailMarketStructure, "GetStrongLevels", true));
            levels.Add(new LevelDef("OBZones", LevelCategory.Structure, LevelRole.ConfluenceFactor, LevelSource.RedTailMarketStructure, "GetOBZones", true));

            // ── Pivots (T5 — off by default) ──
            levels.Add(new LevelDef("PP", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "Pp"));
            levels.Add(new LevelDef("R1", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "R1"));
            levels.Add(new LevelDef("R2", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "R2"));
            levels.Add(new LevelDef("R3", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "R3"));
            levels.Add(new LevelDef("S1", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "S1"));
            levels.Add(new LevelDef("S2", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "S2"));
            levels.Add(new LevelDef("S3", LevelCategory.Pivot, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, "S3"));

            // ── Fibs (T5 — off by default) ──
            for (int i = 1; i <= 10; i++)
                levels.Add(new LevelDef($"Fib{i}", LevelCategory.Fib, LevelRole.ConfluenceFactor, LevelSource.RedTailKeyLevels, $"FibLevel{i}"));

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