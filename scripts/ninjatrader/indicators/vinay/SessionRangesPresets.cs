// ═══════════════════════════════════════════════════════════════════════════
// SessionRangesPresets.cs — Preset catalog + ResolvePreset()
//
// Mirrors PineScript RangeSessionLib.f_resolve_preset() and the
// DailyNYLevels PRD §3 preset catalog.
// ═══════════════════════════════════════════════════════════════════════════

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    // ════════════════════════════════════════════════════════════════════════
    // SessionPreset — enum of available preset groups
    // ════════════════════════════════════════════════════════════════════════
    public enum SessionPreset
    {
        [Description("IB Only (09:30-10:00)")] IBO,
        [Description("ICT Core (Asia+London+IB+Globex)")] ICTCore,
        [Description("DailyNYLevels Preset A (Overnight)")] DNYL_A,
        [Description("DailyNYLevels Preset B (Pre-Market)")] DNYL_B,
        [Description("DailyNYLevels Preset C (Intraday)")] DNYL_C,
        [Description("Herman Full (Asia+London+NY Fractal)")] HermanFull,
        [Description("Magic Hours (7 strategies)")] MagicHours,
        [Description("All Ranges")] All,
        [Description("Custom (user-defined)")] Custom
    }

    // ════════════════════════════════════════════════════════════════════════
    // PresetCatalog — builds List<RangeSpec> from a preset enum
    // ════════════════════════════════════════════════════════════════════════
    public static class PresetCatalog
    {
        // ═══ Helper: HHMM string → minutes-of-day ═══
        public static int ParseHHMM(string hhmm)
        {
            if (string.IsNullOrEmpty(hhmm) || hhmm.Length < 3) return 0;
            int h = int.Parse(hhmm.Substring(0, hhmm.Length - 2));
            int m = int.Parse(hhmm.Substring(hhmm.Length - 2));
            return h * 60 + m;
        }

        // ═══ Helper: create a RangeSpec with defaults ═══
        private static RangeSpec Make(string name, string group, string start, string end,
            string cutoff, string days = "23456", bool isTransfer = false, double evPct = 0.0)
        {
            return new RangeSpec
            {
                Name = name,
                PresetGroup = group,
                OrStartMin = ParseHHMM(start),
                OrEndMin = ParseHHMM(end),
                CutoffMin = ParseHHMM(cutoff),
                Days = days,
                IsTransfer = isTransfer,
                EvTargetPct = evPct,
                IsEnabled = true,
                FillOpacity = 85,       // 85% transparent = light fill
                ShowLabel = true,
                LineWidth = 1,
            };
        }

        // ═══ Resolve a preset → List<RangeSpec> ═══
        public static List<RangeSpec> ResolvePreset(SessionPreset preset)
        {
            switch (preset)
            {
                case SessionPreset.IBO:
                    return new List<RangeSpec>
                    {
                        Make("IB", "IB Only", "0930", "1000", "1600", "23456"),
                    };

                case SessionPreset.ICTCore:
                    return new List<RangeSpec>
                    {
                        Make("Asia Range",    "ICT Core", "0000", "0200", "0500", "23456"),
                        Make("London OR",     "ICT Core", "0200", "0300", "0500", "23456"),
                        Make("London Range",  "ICT Core", "0200", "0500", "0930", "23456"),
                        Make("Globex Range",  "ICT Core", "1800", "0830", "0930", "12345"),  // crosses midnight
                        Make("IB",            "ICT Core", "0930", "1000", "1600", "23456"),
                        Make("NY Opening Range", "ICT Core", "0930", "0935", "1200", "23456"),
                    };

                case SessionPreset.DNYL_A:
                    return new List<RangeSpec>
                    {
                        Make("1800 Break",    "Overnight", "1800", "1815", "0300", "12345"),
                        Make("0300 Break",    "Overnight", "0300", "0305", "0830", "23456"),
                        Make("0300 Transfer", "Overnight", "0300", "0305", "0830", "23456", isTransfer: true),
                    };

                case SessionPreset.DNYL_B:
                    return new List<RangeSpec>
                    {
                        Make("Magic Hour",    "Pre-Market", "0300", "0700", "0830", "23456"),
                        Make("Market Open",   "Pre-Market", "0930", "0935", "1200", "23456"),
                        Make("Q1 Break",      "Pre-Market", "0600", "0830", "1200", "23456"),
                    };

                case SessionPreset.DNYL_C:
                    return new List<RangeSpec>
                    {
                        Make("1100 BO",       "Intraday", "1100", "1115", "1230", "23456"),
                        Make("Lunch Break",   "Intraday", "0830", "1200", "1600", "23456"),
                        Make("1400 Break",    "Intraday", "1400", "1415", "1600", "23456"),
                    };

                case SessionPreset.HermanFull:
                    return new List<RangeSpec>
                    {
                        Make("Asia Range",    "Herman", "0000", "0200", "0500", "23456"),
                        Make("Pre-London",    "Herman", "0000", "0200", "0300", "23456"),
                        Make("London OR",     "Herman", "0200", "0300", "0500", "23456"),
                        Make("London Range",  "Herman", "0200", "0500", "0930", "23456"),
                        Make("IB",            "Herman", "0930", "1000", "1600", "23456"),
                        Make("NY AM",         "Herman", "0700", "1000", "1300", "23456"),
                        Make("NY PM",         "Herman", "1300", "1600", "1600", "23456"),
                    };

                case SessionPreset.MagicHours:
                    return new List<RangeSpec>
                    {
                        Make("00:00 Magic",   "Magic Hours", "0000", "0100", "0830", "23456"),
                        Make("01:00 Magic",   "Magic Hours", "0100", "0200", "0830", "23456"),
                        Make("02:00 Magic",   "Magic Hours", "0200", "0300", "0830", "23456"),
                        Make("06:00 Magic",   "Magic Hours", "0600", "0700", "1200", "23456"),
                        Make("07:00 Magic",   "Magic Hours", "0700", "0800", "1200", "23456"),
                        Make("08:00 Magic",   "Magic Hours", "0800", "0900", "1200", "23456"),
                        Make("23:00 Magic",   "Magic Hours", "2300", "0000", "0830", "12345"),  // crosses midnight
                    };

                case SessionPreset.All:
                {
                    var all = new List<RangeSpec>();
                    all.AddRange(ResolvePreset(SessionPreset.ICTCore));
                    all.AddRange(ResolvePreset(SessionPreset.DNYL_A));
                    all.AddRange(ResolvePreset(SessionPreset.DNYL_B));
                    all.AddRange(ResolvePreset(SessionPreset.DNYL_C));
                    // Deduplicate by name
                    var seen = new HashSet<string>();
                    all.RemoveAll(s => !seen.Add(s.Name));
                    return all;
                }

                case SessionPreset.Custom:
                    return new List<RangeSpec>();  // populated by indicator from user input

                default:
                    return new List<RangeSpec>();
            }
        }

        // ═══ Parse custom range definitions from inline string ═══
        // Format: "RangeName:StartHHMM-EndHHMM-CutoffHHMM;RangeName2:..."
        // Example: "MyRange:1400-1600-1800;Asia:0000-0200-0500"
        public static List<RangeSpec> ParseCustomRanges(string customDefs)
        {
            var result = new List<RangeSpec>();
            if (string.IsNullOrWhiteSpace(customDefs)) return result;

            string[] entries = customDefs.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (string entry in entries)
            {
                string[] parts = entry.Split(new[] { ':' }, 2);
                if (parts.Length < 2) continue;
                string name = parts[0].Trim();
                string[] times = parts[1].Split(new[] { '-' }, StringSplitOptions.RemoveEmptyEntries);
                if (times.Length < 3) continue;

                result.Add(Make(name, "Custom", times[0].Trim(), times[1].Trim(), times[2].Trim()));
            }
            return result;
        }
    }
}