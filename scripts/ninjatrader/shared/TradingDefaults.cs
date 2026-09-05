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
        public const string SourceHash = "92c5427858251e03";
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
        // NoLimit is -1, not 0 and not int.MaxValue: 0 would read as 'no
        // trades allowed' if a caller compared with >=, and MaxValue hides
        // in arithmetic. A cap is an OUTPUT of reporting/trade_ordinal.py,
        // not a frozen input, and an entry may happen at ANY time -- only
        // the 16:00 exit is fixed. See trading_defaults.json risk._doc.
        public const int    NoLimit = -1;
        public const int    MaxContractsPerTrade   = 1;
        public const int    MaxConcurrentPositions = 1;
        public const int    MaxTradesPerDay        = NoLimit;   // analysis-derived; no frozen cap
        public const int    MaxTradesPerSession    = NoLimit;   // analysis-derived; no frozen cap
        public const int    LastEntry              = NoLimit;   // an entry may happen at ANY time
        public const int    FlattenBy              = 1545;   // 15:45 ET, overridable
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

        // ---- governance gate names (section 3.4) --------------------------
        // GovernedStrategy records its own refusals under these, so a bot
        // blocked by a FRAMEWORK rule lands in the roster instead of
        // vanishing -- the C# half of the funnel gap in section 11 item 13.
        public const string GateHardExit = "adr020_hard_exit";
        public const string GateFlattenBy = "flatten_by";
        public const string GateMaxPerDay = "max_trades_per_day";
        public const string GateMaxPerSession = "max_trades_per_session";
        public const string GateLastEntry = "last_entry_et";
        public const string GateConcurrent = "max_concurrent_positions";

        /// <summary>Every governance gate name, so a test can assert the
        /// set rather than each member -- a new one added to the JSON and
        /// never recorded would otherwise pass every existing check.</summary>
        public static readonly string[] GovernanceGates = new string[] {
            GateHardExit, GateFlattenBy, GateMaxPerDay, GateMaxPerSession, GateLastEntry, GateConcurrent };
    }
}
