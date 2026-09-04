using System;
using System.IO;
using System.Text.RegularExpressions;

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// StratConfig — reads the CANONICAL scripts/strategies/the_strat/strat_config.json
    /// (deployed by sync_nt8_strategies.py to Strategies/Vinay/strat_config.json).
    /// Same file Python reads via scripts.libs_py.the_strat.config.load_strat_config().
    /// Fail-open: any missing file / parse error returns compiled defaults.
    /// No third-party JSON dependency — flat-key regex parse of a schema we own.
    /// </summary>
    public sealed class StratConfig
    {
        public string Version = "1.0.0";
        public double MinTargetPoints = 15.0;
        public double MaxRiskPoints = 15.0;
        public double MinRrRatio = 1.0;
        public double WickThreshold = 0.6;
        public int MinFtfcScore = 2;
        public bool UseFtfcFilter = true;
        public bool UseKillzones = true;
        public int EarliestEntry = 930;
        public int LatestEntry = 1530;
        public int FlattenBy = 1555;
        public int MaxTradesPerDay = 2;
        public int[] Killzones = new int[] { 945, 1130, 1400, 1530 };
        public bool FromFile = false;

        private static StratConfig _cached;
        private static readonly object _lock = new object();

        public static StratConfig Load()
        {
            lock (_lock)
            {
                if (_cached != null) return _cached;
                _cached = LoadOnce();
                return _cached;
            }
        }

        public static void ResetForTests() { lock (_lock) { _cached = null; } }

        private static StratConfig LoadOnce()
        {
            var cfg = new StratConfig();
            try
            {
                string dir = Path.GetDirectoryName(
                    System.Reflection.Assembly.GetExecutingAssembly().Location) ?? "";
                // Custom assembly loads from bin/Custom — walk to Strategies/Vinay.
                string[] candidates = new string[]
                {
                    Path.Combine(dir, "Strategies", "Vinay", "strat_config.json"),
                    Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                        "NinjaTrader 8", "bin", "Custom", "Strategies", "Vinay", "strat_config.json"),
                };
                string path = null;
                foreach (var c in candidates)
                    if (File.Exists(c)) { path = c; break; }
                if (path == null) return cfg; // fail-open with defaults

                string json = File.ReadAllText(path);
                cfg.MinTargetPoints = Num(json, "min_target_points", cfg.MinTargetPoints);
                cfg.MaxRiskPoints = Num(json, "max_risk_points", cfg.MaxRiskPoints);
                cfg.MinRrRatio = Num(json, "min_rr_ratio", cfg.MinRrRatio);
                cfg.WickThreshold = Num(json, "wick_threshold", cfg.WickThreshold);
                cfg.MinFtfcScore = (int)Num(json, "min_score", cfg.MinFtfcScore);
                cfg.UseFtfcFilter = Bool(json, "use_filter", cfg.UseFtfcFilter);
                cfg.UseKillzones = Bool(json, "use_killzones", cfg.UseKillzones);
                cfg.MaxTradesPerDay = (int)Num(json, "max_trades_per_day", cfg.MaxTradesPerDay);
                cfg.EarliestEntry = StratCore.ParseHhmm(Str(json, "earliest_entry", "09:30"), cfg.EarliestEntry);
                cfg.LatestEntry = StratCore.ParseHhmm(Str(json, "latest_entry", "15:30"), cfg.LatestEntry);
                cfg.FlattenBy = StratCore.ParseHhmm(Str(json, "flatten_by", "15:55"), cfg.FlattenBy);
                var kz = ParseKillzones(json);
                if (kz != null && kz.Length >= 2) cfg.Killzones = kz;
                var ver = Str(json, "\"version\"\\s*:\\s*\"([^\"]+)\"", null);
                if (!string.IsNullOrEmpty(ver)) cfg.Version = ver;
                cfg.FromFile = true;
            }
            catch { /* fail-open: compiled defaults */ }
            return cfg;
        }

        private static double Num(string json, string key, double fallback)
        {
            var m = Regex.Match(json, "\"" + key + "\"\\s*:\\s*(-?[0-9]+(?:\\.[0-9]+)?)");
            double v;
            return m.Success && double.TryParse(m.Groups[1].Value, out v) ? v : fallback;
        }

        private static bool Bool(string json, string key, bool fallback)
        {
            var m = Regex.Match(json, "\"" + key + "\"\\s*:\\s*(true|false)");
            return m.Success ? m.Groups[1].Value == "true" : fallback;
        }

        private static string Str(string json, string key, string fallback)
        {
            // key may be a plain name ("earliest_entry") or a prebuilt pattern (version).
            string pattern = key.StartsWith("\"")
                ? key
                : "\"" + key + "\"\\s*:\\s*\"([^\"]+)\"";
            var m = Regex.Match(json, pattern);
            return m.Success ? m.Groups[1].Value : fallback;
        }

        private static int[] ParseKillzones(string json)
        {
            // Grab every {"start": "HH:MM", "end": "HH:MM"} pair in order.
            var matches = Regex.Matches(json,
                "\\{\\s*\"name\"[^\\}]*\"start\"\\s*:\\s*\"([0-9:]+)\"[^\\}]*\"end\"\\s*:\\s*\"([0-9:]+)\"");
            if (matches.Count == 0)
                matches = Regex.Matches(json,
                    "\"start\"\\s*:\\s*\"([0-9:]+)\"[^\\}]*\"end\"\\s*:\\s*\"([0-9:]+)\"");
            if (matches.Count == 0) return null;
            var list = new System.Collections.Generic.List<int>();
            foreach (Match m in matches)
            {
                list.Add(StratCore.ParseHhmm(m.Groups[1].Value, -1));
                list.Add(StratCore.ParseHhmm(m.Groups[2].Value, -1));
            }
            return list.ToArray();
        }
    }
}
