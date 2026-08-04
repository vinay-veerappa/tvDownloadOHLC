// ═══════════════════════════════════════════════════════════════════════════
// NtDrawingCore.cs — Core visual system for NT8 indicators (v5)
//
// Implements the canonical visual system (docs/indicators/DailyNYLevels/
// VISUAL_SYSTEM.md v5):
//   - Named color schemes (Midnight / Paper / Custom) with auto-detect
//   - Style resolver: token + scheme + display profile -> concrete values
//   - Display profile scaling (Tiny..Huge)
//   - Tag-based renderer (create/update/delete, no lifecycle states)
//   - Fixed-contrast badge label renderer (hybrid label model)
//
// This is the additive Core foundation. Indicators migrate onto it
// incrementally; existing indicators are untouched until they opt in.
//
// Design doc: docs/indicators/DailyNYLevels/VISUAL_SYSTEM.md
// ═══════════════════════════════════════════════════════════════════════════

using System;
using System.Collections.Generic;
using SharpDX;
using SharpDX.Direct2D1;
using SharpDX.DirectWrite;

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    // ════════════════════════════════════════════════════════════════════════
    // Color schemes
    // ════════════════════════════════════════════════════════════════════════

    public enum NtScheme
    {
        Midnight,   // dark-slate chrome (default for dark charts)
        Paper,      // light neutral chrome (default for light charts)
        Custom      // user-supplied overrides pass through unchanged
    }

    /// <summary>
    /// Named color scheme registry. Each scheme maps every palette token to a
    /// concrete color. Adding a theme = adding a named preset here.
    /// </summary>
    public static class NtPalette
    {
        // Core palette tokens (VISUAL_SYSTEM.md §2.1)
        public const string Bull = "bull";
        public const string Bear = "bear";
        public const string Neutral = "neutral";
        public const string Positive = "positive";
        public const string Negative = "negative";
        public const string Caution = "caution";
        public const string Confirm = "confirm";
        public const string Warning = "warning";
        public const string Median = "median";
        public const string Average = "average";
        public const string Stretch = "stretch";
        public const string Pivot = "pivot_color";
        public const string Invalidation = "invalidation";
        public const string MaxReversal = "max_reversal";

        // Session palette tokens (VISUAL_SYSTEM.md §2.3)
        public const string Asia = "asia";
        public const string London = "london";
        public const string Ny = "ny";
        public const string Ny2 = "ny2";
        public const string P12 = "p12";
        public const string PrevDay = "prev_day";
        public const string Settlement = "settlement";
        public const string Overnight = "overnight";

        // Semantic UI tokens (VISUAL_SYSTEM.md §2.2)
        public const string BgPrimary = "bg_primary";
        public const string BgSecondary = "bg_secondary";
        public const string BgBorder = "bg_border";
        public const string TextPrimary = "text_primary";
        public const string TextSecondary = "text_secondary";
        public const string TextDim = "text_dim";

        // Fixed badge background (theme-agnostic pill, VISUAL_SYSTEM.md §3.4)
        public static readonly Color BadgeBackground = new Color(0x1E, 0x22, 0x2D, 255);

        private static readonly Dictionary<string, Color> _midnight = new Dictionary<string, Color>
        {
            { Bull,        new Color(0x38, 0xBD, 0x8A, 255) },
            { Bear,        new Color(0xF8, 0x71, 0x71, 255) },
            { Neutral,     new Color(0x94, 0xA3, 0xB8, 255) },
            { Positive,    new Color(0x86, 0xEF, 0xAC, 255) },
            { Negative,    new Color(0xFC, 0xA5, 0xA5, 255) },
            { Caution,     new Color(0xFB, 0x92, 0x3C, 255) },
            { Confirm,     new Color(0x2D, 0xD4, 0xBF, 255) },
            { Warning,     new Color(0xF9, 0x73, 0x16, 255) },
            { Median,      new Color(0xFA, 0xCC, 0x15, 255) },
            { Average,     new Color(0x22, 0xD3, 0xEE, 255) },
            { Stretch,     new Color(0xFB, 0x92, 0x3C, 255) },
            { Pivot,       new Color(0x60, 0xA5, 0xFA, 255) },
            { Invalidation,new Color(0xF8, 0x71, 0x71, 255) },
            { MaxReversal, new Color(0xFC, 0xA5, 0xA5, 255) },
            { Asia,        new Color(0x3B, 0x82, 0xF6, 255) },
            { London,      new Color(0xEF, 0x44, 0x44, 255) },
            { Ny,          new Color(0x10, 0xB9, 0x81, 255) },
            { Ny2,         new Color(0x8B, 0x5C, 0xF6, 255) },
            { P12,         new Color(0xFA, 0xCC, 0x15, 255) },
            { PrevDay,     new Color(0x9C, 0xA3, 0xAF, 255) },
            { Settlement,  new Color(0xFB, 0x92, 0x3C, 255) },
            { Overnight,   new Color(0xF5, 0x9E, 0x0B, 255) },
            { BgPrimary,   new Color(0x0F, 0x17, 0x2A, 255) },
            { BgSecondary, new Color(0x1E, 0x29, 0x3B, 255) },
            { BgBorder,    new Color(0x33, 0x41, 0x55, 255) },
            { TextPrimary, new Color(0xF1, 0xF5, 0xF9, 255) },
            { TextSecondary,new Color(0xCB, 0xD5, 0xE1, 255) },
            { TextDim,     new Color(0x94, 0xA3, 0xB8, 255) }
        };

        private static readonly Dictionary<string, Color> _paper = new Dictionary<string, Color>
        {
            { Bull,        new Color(0x00, 0x80, 0x60, 255) },
            { Bear,        new Color(0xB3, 0x26, 0x1E, 255) },
            { Neutral,     new Color(0x6B, 0x72, 0x80, 255) },
            { Positive,    new Color(0x16, 0xA3, 0x4A, 255) },
            { Negative,    new Color(0xB9, 0x1C, 0x1C, 255) },
            { Caution,     new Color(0xC2, 0x41, 0x0C, 255) },
            { Confirm,     new Color(0x0D, 0x94, 0x88, 255) },
            { Warning,     new Color(0xC2, 0x41, 0x0C, 255) },
            { Median,      new Color(0xCA, 0x8A, 0x04, 255) },
            { Average,     new Color(0x08, 0x91, 0xB2, 255) },
            { Stretch,     new Color(0xC2, 0x41, 0x0C, 255) },
            { Pivot,       new Color(0x25, 0x63, 0xEB, 255) },
            { Invalidation,new Color(0xB3, 0x26, 0x1E, 255) },
            { MaxReversal, new Color(0xDC, 0x26, 0x26, 255) },
            { Asia,        new Color(0x1D, 0x4E, 0xD8, 255) },
            { London,      new Color(0xB9, 0x1C, 0x1C, 255) },
            { Ny,          new Color(0x04, 0x78, 0x57, 255) },
            { Ny2,         new Color(0x6D, 0x28, 0xD9, 255) },
            { P12,         new Color(0xCA, 0x8A, 0x04, 255) },
            { PrevDay,     new Color(0x6B, 0x72, 0x80, 255) },
            { Settlement,  new Color(0xC2, 0x41, 0x0C, 255) },
            { Overnight,   new Color(0xD9, 0x77, 0x06, 255) },
            { BgPrimary,   new Color(0xF8, 0xFA, 0xFC, 255) },
            { BgSecondary, new Color(0xFF, 0xFF, 0xFF, 255) },
            { BgBorder,    new Color(0x94, 0xA3, 0xB8, 255) },
            { TextPrimary, new Color(0x0F, 0x17, 0x2A, 255) },
            { TextSecondary,new Color(0x47, 0x55, 0x69, 255) },
            { TextDim,     new Color(0x78, 0x71, 0x6C, 255) }
        };

        /// <summary>Resolve a palette token to a concrete color under a scheme.</summary>
        public static Color Resolve(string token, NtScheme scheme)
        {
            var table = scheme == NtScheme.Paper ? _paper : _midnight;
            Color c;
            return table.TryGetValue(token, out c) ? c : _midnight[Neutral];
        }

        /// <summary>Auto-detect scheme from chart background luminance.</summary>
        public static NtScheme DetectScheme(System.Windows.Media.SolidColorBrush chartBackground)
        {
            if (chartBackground != null)
            {
                double lum = (0.299 * chartBackground.Color.R + 0.587 * chartBackground.Color.G + 0.114 * chartBackground.Color.B) / 255.0;
                return lum < 0.5 ? NtScheme.Midnight : NtScheme.Paper;
            }
            return NtScheme.Midnight;
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // Display profile
    // ════════════════════════════════════════════════════════════════════════

    public enum NtDisplayProfile
    {
        Tiny,
        Small,
        Normal,
        Large,
        Huge
    }

    /// <summary>
    /// Display profile scaling (VISUAL_SYSTEM.md §5). One chart-wide input
    /// scales label size, line width, and transparency uniformly.
    /// </summary>
    public static class NtDisplayProfileScale
    {
        public static float WidthMultiplier(NtDisplayProfile p)
        {
            switch (p)
            {
                case NtDisplayProfile.Tiny:   return 0.75f;
                case NtDisplayProfile.Small:  return 0.85f;
                case NtDisplayProfile.Normal: return 1.0f;
                case NtDisplayProfile.Large:  return 1.25f;
                case NtDisplayProfile.Huge:   return 1.5f;
                default: return 1.0f;
            }
        }

        public static int TransparencyDelta(NtDisplayProfile p)
        {
            switch (p)
            {
                case NtDisplayProfile.Tiny:   return 5;
                case NtDisplayProfile.Small:  return 5;
                case NtDisplayProfile.Normal: return 0;
                case NtDisplayProfile.Large:  return -5;
                case NtDisplayProfile.Huge:   return -10;
                default: return 0;
            }
        }

        /// <summary>Scale a base width (P/S/C) by the profile, min 1.</summary>
        public static float ScaledWidth(float baseWidth, NtDisplayProfile p)
        {
            return Math.Max(1f, baseWidth * WidthMultiplier(p));
        }

        /// <summary>Convert a Pine-style transparency (0-100) to SharpDX alpha (0-1).</summary>
        public static float AlphaFromTransparency(int transparency, NtDisplayProfile p)
        {
            int t = Math.Max(0, Math.Min(100, transparency + TransparencyDelta(p)));
            return (100 - t) / 100f;
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // Style resolver
    // ════════════════════════════════════════════════════════════════════════

    /// <summary>
    /// Resolves a palette token + scheme + profile to a concrete SharpDX
    /// Color4 (with alpha). Cached per render cycle by the caller.
    /// </summary>
    public static class NtStyleResolver
    {
        public static Color4 ResolveColor(string token, NtScheme scheme, int transparency, NtDisplayProfile profile)
        {
            Color c = NtPalette.Resolve(token, scheme);
            float alpha = NtDisplayProfileScale.AlphaFromTransparency(transparency, profile);
            return new Color4(c.R / 255f, c.G / 255f, c.B / 255f, alpha);
        }

        public static Color4 ResolveColor(string token, NtScheme scheme)
        {
            return ResolveColor(token, scheme, 0, NtDisplayProfile.Normal);
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // Tag-based renderer
    // ════════════════════════════════════════════════════════════════════════

    /// <summary>
    /// A semantic level record in the data model (VISUAL_SYSTEM.md §8). This is
    /// what the MCP data-model endpoint reads. `Key` matches the render tag's
    /// instance_key so a rendered object correlates to its semantic record.
    /// </summary>
    public class NtLevelRecord
    {
        public string Key { get; set; }            // e.g. "PDH_2026_08_03"
        public string Label { get; set; }          // canonical compact code, e.g. "PDH"
        public double Price { get; set; }
        public string Category { get; set; }        // e.g. "price_level"
        public string SchemeColor { get; set; }    // hex, e.g. "#38BD8A"
        public string State { get; set; }          // "active" | "historical"
        public DateTime Date { get; set; }
    }

    /// <summary>
    /// Tag-based create/update/delete renderer. No lifecycle state transitions.
    /// The indicator appends to a history list; the renderer draws the current
    /// slice and styles retained entries by age.
    /// </summary>
    public class NtTagRenderer
    {
        private readonly Dictionary<string, NtLevelRecord> _records = new Dictionary<string, NtLevelRecord>();

        /// <summary>Upsert a level record by key (create or update).</summary>
        public void Upsert(NtLevelRecord record)
        {
            _records[record.Key] = record;
        }

        /// <summary>Remove a level record by key.</summary>
        public void Remove(string key)
        {
            _records.Remove(key);
        }

        /// <summary>Clear all records (e.g. new session).</summary>
        public void Clear()
        {
            _records.Clear();
        }

        /// <summary>Snapshot of all current records (for MCP data-model read).</summary>
        public List<NtLevelRecord> Snapshot()
        {
            return new List<NtLevelRecord>(_records.Values);
        }

        /// <summary>Build a stable instance key from a level code + date.</summary>
        public static string InstanceKey(string levelCode, DateTime date)
        {
            return levelCode + "_" + date.ToString("yyyy_MM_dd");
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // Badge label renderer (hybrid label model)
    // ════════════════════════════════════════════════════════════════════════

    /// <summary>
    /// Renders a fixed-contrast badge label (theme-agnostic pill) on a SharpDX
    /// render target. Text color is the element's own color; the pill background
    /// is constant so labels stay readable on any chart.
    /// </summary>
    public static class NtBadge
    {
        public static void Draw(RenderTarget target, TextFormat format, string text, Color4 textColor,
            float x, float y, float paddingX = 4f, float paddingY = 2f)
        {
            using (var layout = new TextLayout(Core.Globals.DirectWriteFactory, text, format, float.MaxValue, float.MaxValue))
            {
                float w = (float)layout.Metrics.Width + paddingX * 2f;
                float h = (float)layout.Metrics.Height + paddingY * 2f;
                var rect = new RectangleF(x - paddingX, y - paddingY, w, h);

                using (var bg = new SolidColorBrush(target, new Color4(
                    NtPalette.BadgeBackground.R / 255f,
                    NtPalette.BadgeBackground.G / 255f,
                    NtPalette.BadgeBackground.B / 255f, 0.92f)))
                {
                    target.FillRectangle(rect, bg);
                }
                using (var textBrush = new SolidColorBrush(target, textColor))
                {
                    target.DrawTextLayout(new Vector2(x, y), layout, textBrush);
                }
            }
        }
    }
}
