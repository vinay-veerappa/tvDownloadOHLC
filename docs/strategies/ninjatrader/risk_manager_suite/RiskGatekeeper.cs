#region Using declarations
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using NinjaTrader.Cbi;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
    // ══════════════════════════════════════════════════════════════════════
    // Per-account risk state snapshot
    // ══════════════════════════════════════════════════════════════════════

    [Serializable]
    public class AccountRiskState
    {
        // Session state — reset every day
        public DateTime TradingDate        { get; set; } = DateTime.MinValue;
        public double   SessionPnL         { get; set; } = 0;
        public int      TodayTradeCount    { get; set; } = 0;
        public int      ConsecutiveLosers  { get; set; } = 0;
        public bool     IsDoneForDay       { get; set; } = false;
        public bool     IsPaused           { get; set; } = false;
        public DateTime PauseUntil         { get; set; } = DateTime.MinValue;

        // Account state — persists across sessions
        public double   AccountEquity      { get; set; } = 0;
        public double   HighWaterMark      { get; set; } = 0;
        public bool     AccountBlown       { get; set; } = false;

        // Timestamp of last update (for staleness checks)
        public DateTime LastUpdated        { get; set; } = DateTime.MinValue;
    }

    // ══════════════════════════════════════════════════════════════════════
    // Risk parameters applied to each monitored account
    // (Populated by the AddOn from its UI settings)
    // ══════════════════════════════════════════════════════════════════════

    public class AccountRiskParameters
    {
        public double DailyMaxLoss              { get; set; } = 400;
        public double TrailingDrawdown          { get; set; } = 2000;
        public int    MaxTradesPerDay           { get; set; } = 6;
        public int    MaxConsecutiveLosers      { get; set; } = 2;
        public int    PauseMinutes              { get; set; } = 30;
        public int    HardStopConsecutiveLosers { get; set; } = 3;
    }

    // ══════════════════════════════════════════════════════════════════════
    // RiskGatekeeper — static shared risk registry
    // Thread-safe. All strategy instances and the AddOn call into this.
    // ══════════════════════════════════════════════════════════════════════

    public static class RiskGatekeeper
    {
        // ── Internal state ────────────────────────────────────────────────

        private static readonly object _lock = new object();

        // Per-account risk state (key = account name, case-insensitive)
        private static readonly Dictionary<string, AccountRiskState>      _states     = new Dictionary<string, AccountRiskState>(StringComparer.OrdinalIgnoreCase);
        private static readonly Dictionary<string, AccountRiskParameters> _parameters = new Dictionary<string, AccountRiskParameters>(StringComparer.OrdinalIgnoreCase);

        // Persist state files under NinjaTrader's documents folder
        private static readonly string _stateDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
            "NinjaTrader 8", "risk_gatekeeper");

        // ── Public API ────────────────────────────────────────────────────

        /// <summary>
        /// Register an account with its risk parameters.
        /// Called by the AddOn when it discovers a monitored account.
        /// If persisted state exists for today, it is loaded; otherwise starts fresh.
        /// </summary>
        public static void RegisterAccount(string accountName, AccountRiskParameters parameters)
        {
            lock (_lock)
            {
                _parameters[accountName] = parameters;

                if (!_states.ContainsKey(accountName))
                {
                    AccountRiskState loaded = LoadState(accountName);
                    _states[accountName] = loaded ?? new AccountRiskState();
                }
            }
        }

        /// <summary>
        /// Returns true if a new trade entry is permitted on this account.
        /// Strategies call this as part of their entry gate.
        /// Unregistered (excluded) accounts always return true — not monitored.
        /// </summary>
        public static bool CanTrade(string accountName)
        {
            lock (_lock)
            {
                if (!_states.ContainsKey(accountName) || !_parameters.ContainsKey(accountName))
                    return true; // Not monitored — let it through

                AccountRiskState      state = _states[accountName];
                AccountRiskParameters parms = _parameters[accountName];

                if (state.AccountBlown)
                    return false;

                if (state.IsDoneForDay)
                    return false;

                if (state.IsPaused)
                {
                    if (DateTime.Now < state.PauseUntil)
                        return false;

                    // Pause expired — clear it
                    state.IsPaused = false;
                    _states[accountName] = state;
                }

                if (state.TodayTradeCount >= parms.MaxTradesPerDay)
                    return false;

                return true;
            }
        }

        /// <summary>
        /// Returns true if the potential loss on the next trade would breach the daily max loss.
        /// potentialLoss should be a positive dollar amount (the max risk on the trade).
        /// </summary>
        public static bool WouldBreachDailyMaxLoss(string accountName, double potentialLoss)
        {
            lock (_lock)
            {
                if (!_states.ContainsKey(accountName) || !_parameters.ContainsKey(accountName))
                    return false;

                AccountRiskState      state = _states[accountName];
                AccountRiskParameters parms = _parameters[accountName];

                return (state.SessionPnL - potentialLoss) < -parms.DailyMaxLoss;
            }
        }

        /// <summary>
        /// Record a closed trade. Called by the AddOn's ExecutionUpdate handler
        /// when a closing fill is confirmed.
        /// </summary>
        public static void RecordTrade(string accountName, double pnl, DateTime tradeTime)
        {
            lock (_lock)
            {
                if (!_states.ContainsKey(accountName) || !_parameters.ContainsKey(accountName))
                    return;

                AccountRiskState      state = _states[accountName];
                AccountRiskParameters parms = _parameters[accountName];

                state.SessionPnL      += pnl;
                state.TodayTradeCount++;
                state.LastUpdated      = tradeTime;

                if (pnl < 0)
                {
                    state.ConsecutiveLosers++;

                    if (state.ConsecutiveLosers >= parms.HardStopConsecutiveLosers)
                    {
                        state.IsDoneForDay = true;
                        NinjaTrader.NinjaScript.NinjaScript.Log(
                            string.Format("[RiskGatekeeper] {0} DONE FOR DAY — {1} consecutive losers",
                                accountName, state.ConsecutiveLosers),
                            NinjaTrader.Cbi.LogLevel.Warning);
                    }
                    else if (state.ConsecutiveLosers >= parms.MaxConsecutiveLosers)
                    {
                        state.IsPaused   = true;
                        state.PauseUntil = tradeTime.AddMinutes(parms.PauseMinutes);
                        NinjaTrader.NinjaScript.NinjaScript.Log(
                            string.Format("[RiskGatekeeper] {0} PAUSED until {1} — {2} consecutive losers",
                                accountName, state.PauseUntil.ToShortTimeString(), state.ConsecutiveLosers),
                            NinjaTrader.Cbi.LogLevel.Warning);
                    }
                }
                else
                {
                    state.ConsecutiveLosers = 0;
                }

                _states[accountName] = state;
                SaveState(accountName, state);
            }
        }

        /// <summary>
        /// Update real account equity from the broker.
        /// Called by the AddOn's AccountItemUpdate handler (throttled — not every tick).
        /// Also evaluates the trailing drawdown rule.
        /// </summary>
        public static void UpdateEquity(string accountName, double equity, DateTime timestamp)
        {
            lock (_lock)
            {
                if (!_states.ContainsKey(accountName) || !_parameters.ContainsKey(accountName))
                    return;

                AccountRiskState      state = _states[accountName];
                AccountRiskParameters parms = _parameters[accountName];

                state.AccountEquity = equity;
                state.LastUpdated   = timestamp;

                // Ratchet HWM upward only
                if (equity > state.HighWaterMark)
                    state.HighWaterMark = equity;

                // Trailing drawdown check
                double drawdown = state.HighWaterMark - equity;
                if (!state.AccountBlown && drawdown >= parms.TrailingDrawdown)
                {
                    state.AccountBlown = true;
                    state.IsDoneForDay = true;
                    NinjaTrader.NinjaScript.NinjaScript.Log(
                        string.Format("[RiskGatekeeper] *** ACCOUNT BLOWN *** {0} | Drawdown {1:C} >= Limit {2:C} | Equity {3:C}",
                            accountName, drawdown, parms.TrailingDrawdown, equity),
                        NinjaTrader.Cbi.LogLevel.Warning);
                }

                _states[accountName] = state;
                // Don't save on every equity tick — saved on trade events instead
            }
        }

        /// <summary>
        /// Mark the account as done for the day because the daily max loss was breached
        /// by an open position. Called by RiskManagerBase when the intraday loss check fires.
        /// </summary>
        public static void MarkDailyMaxLossBreached(string accountName)
        {
            lock (_lock)
            {
                if (!_states.ContainsKey(accountName))
                    return;

                AccountRiskState state = _states[accountName];
                state.IsDoneForDay = true;
                _states[accountName] = state;
                SaveState(accountName, state);

                NinjaTrader.NinjaScript.NinjaScript.Log(
                    string.Format("[RiskGatekeeper] {0} DAILY MAX LOSS BREACHED — done for day", accountName),
                    NinjaTrader.Cbi.LogLevel.Warning);
            }
        }

        /// <summary>
        /// Reset session state for a new trading day.
        /// AccountBlown intentionally persists — it must be manually cleared.
        /// </summary>
        public static void ResetDay(string accountName, DateTime newDate)
        {
            lock (_lock)
            {
                if (!_states.ContainsKey(accountName))
                    return;

                AccountRiskState state = _states[accountName];

                // Preserve cross-session account state
                double savedEquity = state.AccountEquity;
                double savedHWM    = state.HighWaterMark;
                bool   savedBlown  = state.AccountBlown;

                state.TradingDate       = newDate;
                state.SessionPnL        = 0;
                state.TodayTradeCount   = 0;
                state.ConsecutiveLosers = 0;
                state.IsDoneForDay      = false;
                state.IsPaused          = false;
                state.PauseUntil        = DateTime.MinValue;
                state.LastUpdated       = DateTime.Now;
                state.AccountEquity     = savedEquity;
                state.HighWaterMark     = savedHWM;
                state.AccountBlown      = savedBlown;

                _states[accountName] = state;
                SaveState(accountName, state);

                NinjaTrader.NinjaScript.NinjaScript.Log(
                    string.Format("[RiskGatekeeper] {0} new session {1} | Equity: {2:C} | HWM: {3:C} | Blown: {4}",
                        accountName, newDate.ToShortDateString(), savedEquity, savedHWM, savedBlown),
                    NinjaTrader.Cbi.LogLevel.Information);
            }
        }

        /// <summary>
        /// Runtime recovery — seed today's session state from broker trade history.
        /// Called when persisted state is missing or stale (different day).
        /// currentEquity should come from Account.Get(AccountItem.CashValue, ...).
        /// todayTrades is a list of (pnl, time) tuples for today's completed trades.
        /// </summary>
        public static void RecoverFromHistory(string accountName, double currentEquity,
            IEnumerable<(double pnl, DateTime time)> todayTrades)
        {
            lock (_lock)
            {
                if (!_states.ContainsKey(accountName) || !_parameters.ContainsKey(accountName))
                    return;

                AccountRiskState      state = _states[accountName];
                AccountRiskParameters parms = _parameters[accountName];

                // Reset session counters
                state.TradingDate       = DateTime.Today;
                state.SessionPnL        = 0;
                state.TodayTradeCount   = 0;
                state.ConsecutiveLosers = 0;
                state.IsDoneForDay      = false;
                state.IsPaused          = false;
                state.PauseUntil        = DateTime.MinValue;

                // Seed equity from broker
                state.AccountEquity = currentEquity;
                if (state.HighWaterMark == 0)
                    state.HighWaterMark = currentEquity;

                // Replay today's trades to reconstruct counters
                foreach (var (pnl, time) in todayTrades.OrderBy(t => t.time))
                {
                    state.SessionPnL      += pnl;
                    state.TodayTradeCount++;

                    if (pnl < 0)
                    {
                        state.ConsecutiveLosers++;
                        if (state.ConsecutiveLosers >= parms.HardStopConsecutiveLosers)
                            state.IsDoneForDay = true;
                        else if (state.ConsecutiveLosers >= parms.MaxConsecutiveLosers)
                        {
                            state.IsPaused   = true;
                            state.PauseUntil = time.AddMinutes(parms.PauseMinutes);
                        }
                    }
                    else
                    {
                        state.ConsecutiveLosers = 0;
                        state.IsPaused          = false;
                    }
                }

                state.LastUpdated = DateTime.Now;
                _states[accountName] = state;
                SaveState(accountName, state);

                NinjaTrader.NinjaScript.NinjaScript.Log(
                    string.Format("[RiskGatekeeper] RECOVERED {0}: {1} trades, PnL={2:C}, ConsecL={3}, DoneForDay={4}, Equity={5:C}",
                        accountName, state.TodayTradeCount, state.SessionPnL,
                        state.ConsecutiveLosers, state.IsDoneForDay, state.AccountEquity),
                    NinjaTrader.Cbi.LogLevel.Information);
            }
        }

        /// <summary>
        /// Returns a snapshot of the current risk state for an account (for logging/UI).
        /// Returns null if the account is not registered.
        /// </summary>
        public static AccountRiskState GetState(string accountName)
        {
            lock (_lock)
            {
                return _states.TryGetValue(accountName, out AccountRiskState state) ? state : null;
            }
        }

        /// <summary>Returns all registered (monitored) account names.</summary>
        public static IEnumerable<string> RegisteredAccounts
        {
            get { lock (_lock) { return _states.Keys.ToList(); } }
        }

        // ── Persistence ───────────────────────────────────────────────────

        private static string GetStateFilePath(string accountName)
        {
            string safeName = string.Concat(accountName.Split(Path.GetInvalidFileNameChars()));
            return Path.Combine(_stateDir, safeName + "_risk_state.json");
        }

        private static void SaveState(string accountName, AccountRiskState state)
        {
            try
            {
                Directory.CreateDirectory(_stateDir);
                File.WriteAllText(GetStateFilePath(accountName), SerializeState(state), Encoding.UTF8);
            }
            catch (Exception ex)
            {
                NinjaTrader.NinjaScript.NinjaScript.Log(
                    string.Format("[RiskGatekeeper] SaveState failed for {0}: {1}", accountName, ex.Message),
                    NinjaTrader.Cbi.LogLevel.Warning);
            }
        }

        private static AccountRiskState LoadState(string accountName)
        {
            try
            {
                string path = GetStateFilePath(accountName);
                if (!File.Exists(path))
                    return null;

                AccountRiskState state = DeserializeState(File.ReadAllText(path, Encoding.UTF8));

                if (state != null && state.TradingDate.Date != DateTime.Today)
                {
                    NinjaTrader.NinjaScript.NinjaScript.Log(
                        string.Format("[RiskGatekeeper] Stale state for {0} (was {1}) — runtime recovery needed.",
                            accountName, state.TradingDate.ToShortDateString()),
                        NinjaTrader.Cbi.LogLevel.Information);
                    return null; // Caller will trigger RecoverFromHistory
                }

                return state;
            }
            catch (Exception ex)
            {
                NinjaTrader.NinjaScript.NinjaScript.Log(
                    string.Format("[RiskGatekeeper] LoadState failed for {0}: {1}", accountName, ex.Message),
                    NinjaTrader.Cbi.LogLevel.Warning);
                return null;
            }
        }

        // ── Minimal JSON serialisation (no external dependencies) ─────────

        private static string SerializeState(AccountRiskState s)
        {
            return string.Format(
                "{{\n" +
                "  \"TradingDate\": \"{0:O}\",\n" +
                "  \"SessionPnL\": {1},\n" +
                "  \"TodayTradeCount\": {2},\n" +
                "  \"ConsecutiveLosers\": {3},\n" +
                "  \"IsDoneForDay\": {4},\n" +
                "  \"IsPaused\": {5},\n" +
                "  \"PauseUntil\": \"{6:O}\",\n" +
                "  \"AccountEquity\": {7},\n" +
                "  \"HighWaterMark\": {8},\n" +
                "  \"AccountBlown\": {9},\n" +
                "  \"LastUpdated\": \"{10:O}\"\n" +
                "}}",
                s.TradingDate, s.SessionPnL, s.TodayTradeCount,
                s.ConsecutiveLosers,
                s.IsDoneForDay.ToString().ToLower(),
                s.IsPaused.ToString().ToLower(),
                s.PauseUntil, s.AccountEquity, s.HighWaterMark,
                s.AccountBlown.ToString().ToLower(),
                s.LastUpdated);
        }

        private static AccountRiskState DeserializeState(string json)
        {
            var state = new AccountRiskState();
            foreach (string line in json.Split('\n'))
            {
                string trimmed = line.Trim().TrimEnd(',');
                int colonIdx = trimmed.IndexOf(':');
                if (colonIdx < 0) continue;

                string key   = trimmed.Substring(0, colonIdx).Trim().Trim('"');
                string value = trimmed.Substring(colonIdx + 1).Trim().Trim('"');

                switch (key)
                {
                    case "TradingDate":       state.TradingDate       = ParseDate(value);   break;
                    case "SessionPnL":        state.SessionPnL        = ParseDouble(value); break;
                    case "TodayTradeCount":   state.TodayTradeCount   = ParseInt(value);    break;
                    case "ConsecutiveLosers": state.ConsecutiveLosers = ParseInt(value);    break;
                    case "IsDoneForDay":      state.IsDoneForDay      = ParseBool(value);   break;
                    case "IsPaused":          state.IsPaused          = ParseBool(value);   break;
                    case "PauseUntil":        state.PauseUntil        = ParseDate(value);   break;
                    case "AccountEquity":     state.AccountEquity     = ParseDouble(value); break;
                    case "HighWaterMark":     state.HighWaterMark     = ParseDouble(value); break;
                    case "AccountBlown":      state.AccountBlown      = ParseBool(value);   break;
                    case "LastUpdated":       state.LastUpdated       = ParseDate(value);   break;
                }
            }
            return state;
        }

        private static DateTime ParseDate(string s)   { DateTime r; return DateTime.TryParse(s, out r) ? r : DateTime.MinValue; }
        private static double   ParseDouble(string s) { double r;   return double.TryParse(s, System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out r) ? r : 0; }
        private static int      ParseInt(string s)    { int r;      return int.TryParse(s, out r) ? r : 0; }
        private static bool     ParseBool(string s)   { bool r;     return bool.TryParse(s, out r) && r; }
    }
}
