// ═══════════════════════════════════════════════════════════════════════════
// LiquidityLevelsModels.cs — LevelDef, LevelState, SweepEvent + enums
//
// Data structures for the unified LiquidityLevels indicator.
// Aggregates 52+ liquidity levels from RedTail + built-ins + SessionOpens.
//
// Design doc: docs/architecture/LIQUIDITY_LEVELS_INDICATOR_DESIGN.md
// ═══════════════════════════════════════════════════════════════════════════

using System;
using System.Collections.Generic;

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    // ════════════════════════════════════════════════════════════════════════
    // Enums
    // ════════════════════════════════════════════════════════════════════════

    public enum LevelCategory
    {
        PriorDay,       // PDH, PDL, PDC
        PriorWeek,      // PWH, PWL, MH, ML, GH, GL
        PriorMonth,     // PMH, PML
        SessionOpen,    // Midnight, 4H, London, NY opens
        SessionRange,   // Asia/London/Globex/IB H/L
        Intraday,       // HOD, LOD, NYH, NYL
        VolumeProfile,  // POC, VAH, VAL, naked levels
        Structure,      // EQH/EQL, strong levels, OB zones
        Pivot,          // PP, R1-R3, S1-S3, midlines
        Fib             // Fib1-10
    }

    public enum LevelRole
    {
        SweepTarget,        // price is drawn to this level (resting liquidity)
        ConfluenceFactor,   // used for target/stop placement, not swept
        Both                // can be both
    }

    public enum LevelSource
    {
        RedTailKeyLevels,
        RedTailVolumeProfile,
        RedTailMarketStructure,
        PriorDayOHLC,       // built-in @PriorDayOHLC
        CurrentDayOHL,      // built-in @CurrentDayOHL
        SessionOpens,       // NEW — SessionOpensEngine
        SessionRanges,      // sibling indicator
        Internal            // computed internally
    }

    public enum SweepMode
    {
        Wick,       // wick beyond level + close back through (default)
        BodyClose,  // close through level, no wick requirement
        Both        // detect both modes
    }

    public enum LabelPlacement
    {
        RightMargin, // Draw labels on right margin (default, cleanest)
        Origin,      // Draw labels at ray origin bar
        Both         // Draw labels at both origin and right margin
    }

    public enum VoiceGenderSelection
    {
        Female,
        Male
    }

    // ════════════════════════════════════════════════════════════════════════
    // LevelDef — immutable catalog entry (one per level type)
    // ════════════════════════════════════════════════════════════════════════
    public class LevelDef
    {
        public string Name { get; set; }               // Short key e.g. "PDH", "PMH"
        public string FullName { get; set; }           // Full form e.g. "Prior Day High", "Prev Month High"
        public LevelCategory Category { get; set; }
        public LevelRole Role { get; set; }
        public LevelSource Source { get; set; }
        public string Accessor { get; set; }            // property/method name on source indicator
        public bool IsArray { get; set; }               // true for lists (naked POCs, strong levels, OB zones)

        public LevelDef(string name, string fullName, LevelCategory cat, LevelRole role, LevelSource src,
            string accessor = null, bool isArray = false)
        {
            Name = name;
            FullName = fullName ?? name;
            Category = cat;
            Role = role;
            Source = src;
            Accessor = accessor;
            IsArray = isArray;
        }

        public LevelDef(string name, LevelCategory cat, LevelRole role, LevelSource src,
            string accessor = null, bool isArray = false)
            : this(name, name, cat, role, src, accessor, isArray)
        {
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // LevelState — mutable per-bar state for one level
    // ════════════════════════════════════════════════════════════════════════
    public class LevelState
    {
        public LevelDef Def { get; set; }
        public double Price { get; set; }               // current level price (0 if not available)
        public DateTime SetTime { get; set; }            // when the level was established
        public int SetBarIndex { get; set; }             // bar index when set
        public bool IsActive { get; set; }               // within valid window
        public bool Swept { get; set; }                  // has been swept
        public DateTime? SweptTime { get; set; }         // when swept
        public int TouchCount { get; set; }              // number of times price touched
        public List<string> StacksWith { get; set; }     // names of levels within stacking tolerance

        public LevelState(LevelDef def)
        {
            Def = def;
            StacksWith = new List<string>();
        }

        public void Reset()
        {
            Price = 0;
            SetTime = DateTime.MinValue;
            SetBarIndex = 0;
            IsActive = false;
            Swept = false;
            SweptTime = null;
            TouchCount = 0;
            StacksWith.Clear();
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // SweepEvent — emitted when a sweep is detected
    // ════════════════════════════════════════════════════════════════════════
    public class SweepEvent
    {
        public string LevelName { get; set; }            // "PDH", "EQH", "MidnightOpen"
        public double LevelPrice { get; set; }
        public DateTime SweepTime { get; set; }           // bar time of sweep
        public bool IsBullSweep { get; set; }             // true = swept lows (SSL taken), false = swept highs (BSL taken)
        public double SweepDepth { get; set; }            // price excursion beyond level (in ticks)
        public double WickPct { get; set; }               // wick as % of bar range
        public double ClosePrice { get; set; }            // close of sweep bar
        public int BarIndex { get; set; }
        public SweepMode Mode { get; set; }               // how the sweep was detected
        public bool IsStackSweep { get; set; }            // true if level was stacked with others
    }

    // ════════════════════════════════════════════════════════════════════════
    // SessionOpenDef — configuration for one session open
    // ════════════════════════════════════════════════════════════════════════
    public class SessionOpenDef
    {
        public string Name { get; set; }                 // "MidnightOpen", "LondonOpen"
        public int HourET { get; set; }                   // hour in ET (0-23)
        public int MinuteET { get; set; }                 // minute in ET
        public bool IsDSTAware { get; set; }              // true for London open (shifts with DST)
        public int DstHourET { get; set; }                // alternate hour during DST
        public bool IsEnabled { get; set; }

        public int CurrentHourET(DateTime dateEt)
        {
            if (!IsDSTAware) return HourET;
            bool isDst = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time").IsDaylightSavingTime(dateEt);
            return isDst ? DstHourET : HourET;
        }

        public int MinutesOfDay(DateTime dateEt)
        {
            return CurrentHourET(dateEt) * 60 + MinuteET;
        }
    }
}