// GENERATED FILE -- DO NOT EDIT.
//
// Source : scripts/trading_framework/config/trading_defaults.json
// Tool   : scripts/utils/generate_trading_defaults.py
// Spec   : docs/architecture/STRATEGY_WORKFLOW.md section 1.3
//
// Edit the JSON and re-run the tool. A hand edit here is reverted by the
// next generation and fails test_bot_defaults.py in the meantime.
//
// WHY COMPILED CONSTANTS AND NOT A RUNTIME JSON READ: StratConfig.cs reads
// its JSON at runtime and is deliberately FAIL-OPEN. That is correct for
// tunables and wrong for these -- a bot that silently falls back to its own
// flatten time is the defect this file exists to remove.

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    /// <summary>
    /// The frozen defaults every strategy inherits. Only the trade setup varies.
    /// </summary>
    public static class TradingDefaults
    {
        public const string SourceHash = "992f9c07befaa2e9";
        public const string FrozenOn   = "2026-09-05";

        // ---- Instrument (ADR-009: micros are the traded class) ----------
        public const string DefaultInstrument = "MNQ";
        public const double PointValueES = 50.0;   // tick 0.25 = $12.5
        public const double PointValueMES = 5.0;   // tick 0.25 = $1.25
        public const double PointValueMNQ = 2.0;   // tick 0.25 = $0.5
        public const double PointValueNQ = 20.0;   // tick 0.25 = $5.0

        /// <summary>Point value for a data ticker OR a contract symbol.
        /// NQ1 names a PRICE SERIES; MNQ names the CONTRACT you trade.
        /// Throws rather than guessing -- a silent default here valued one
        /// run's point at $20 in P&amp;L and $2 in the prop simulation.</summary>
        public static double PointValueFor(string ticker)
        {
            switch ((ticker ?? "").Trim().ToUpperInvariant())
            {
                case "ES":
                    return PointValueES;
                case "ES1":
                case "ES1!":
                case "MES":
                case "MES1!":
                    return PointValueMES;
                case "MNQ":
                case "MNQ1!":
                case "NQ1":
                case "NQ1!":
                    return PointValueMNQ;
                case "NQ":
                    return PointValueNQ;
                default:
                    throw new System.ArgumentException(
                        "unknown instrument '" + ticker + "'. Add it to trading_defaults.json; do not pass a point value at the call site.");
            }
        }

        // ---- Risk ------------------------------------------------------
        public const int    MaxContractsPerTrade   = 1;
        public const int    MaxConcurrentPositions = 1;
        public const int    MaxTradesPerDay        = 3;
        public const int    LastEntry              = 1430;   // 14:30 ET
        public const int    FlattenBy              = 1545;   // 15:45 ET
        public const int    RthHardExit            = 1600;   // 16:00 ET, ADR-020
        public const double RiskPerTradeFraction   = 0.00267;

        // ---- Execution -------------------------------------------------
        public const int    SlippageTicks   = 1;
        public const double CommissionRT    = 0.62;
        public const int    DefaultContracts = 1;

        // ---- NT8 Strategy Analyzer (asserted, never written) -----------
        public const string GlobalMergePolicy = "MergeNonBackAdjusted";
        public const bool   IncludeCommission = true;

        // ---- Sessions, ET. A PARTITION: contiguous, non-overlapping, and
        //      covering the day exactly once (asserted on the Python side).
        public const int GLOBEXStart = 1800;   // 18:00
        public const int ASIAStart = 2000;   // 20:00
        public const int LONDONStart = 200;   // 02:00
        public const int NYPREStart = 800;   // 08:00
        public const int NYAMStart = 930;   // 09:30
        public const int NYLUNCHStart = 1100;   // 11:00
        public const int NYPMStart = 1330;   // 13:30
        public const int CLOSEDStart = 1600;   // 16:00

        /// <summary>Frozen session name for a HHMM time-of-day.</summary>
        public static string SessionFor(int hhmm)
        {
            if (hhmm >= 1800 && hhmm < 2000) return "GLOBEX";
            if (hhmm >= 2000 || hhmm < 200) return "ASIA";
            if (hhmm >= 200 && hhmm < 800) return "LONDON";
            if (hhmm >= 800 && hhmm < 930) return "NY_PRE";
            if (hhmm >= 930 && hhmm < 1100) return "NY_AM";
            if (hhmm >= 1100 && hhmm < 1330) return "NY_LUNCH";
            if (hhmm >= 1330 && hhmm < 1600) return "NY_PM";
            if (hhmm >= 1600 && hhmm < 1800) return "CLOSED";
            throw new System.ArgumentException("no session for " + hhmm);
        }
    }
}
