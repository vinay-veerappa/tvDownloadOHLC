#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
#endregion

//
// RiskManagerAddOn
// ────────────────────────────────────────────────────────────────────────────
// NinjaTrader 8 AddOn that monitors real account equity and order fills
// across ALL accounts except those in the ExcludedAccounts list.
//
// Install:  Copy to Documents\NinjaTrader 8\bin\Custom\AddOns\
//           Compile → Tools > NinjaScript Editor.
//           Enable:  Control Center > Tools > Options > AddOns > ✓ RiskManagerAddOn
//
// It auto-discovers every account NinjaTrader knows about and registers
// each non-excluded one with RiskGatekeeper.  From that point forward
// every RiskManagerBase-derived strategy on those accounts will have its
// entry gates enforced by the shared gatekeeper rather than isolated
// per-strategy state.
//

namespace NinjaTrader.NinjaScript.AddOns
{
    public class RiskManagerAddOn : AddOnBase
    {
        // ── Parameters ───────────────────────────────────────────────────────

        [Display(Name = "Excluded Accounts",
                 Description = "Comma-separated list of account names to exclude from monitoring " +
                               "(e.g. strategy-driven accounts with their own risk management). " +
                               "All other accounts are monitored automatically.",
                 Order = 1, GroupName = "Risk Manager AddOn")]
        public string ExcludedAccounts { get; set; } = "";

        [Display(Name = "Daily Max Loss ($)", Order = 2, GroupName = "Risk Manager AddOn")]
        public double DailyMaxLoss { get; set; } = 400;

        [Display(Name = "Trailing Drawdown ($)", Order = 3, GroupName = "Risk Manager AddOn")]
        public double TrailingDrawdown { get; set; } = 2000;

        [Display(Name = "Max Trades Per Day", Order = 4, GroupName = "Risk Manager AddOn")]
        public int MaxTradesPerDay { get; set; } = 6;

        [Display(Name = "Max Consecutive Losers (pause)", Order = 5, GroupName = "Risk Manager AddOn")]
        public int MaxConsecutiveLosers { get; set; } = 2;

        [Display(Name = "Pause Minutes After Consec Loss", Order = 6, GroupName = "Risk Manager AddOn")]
        public int PauseMinutes { get; set; } = 30;

        [Display(Name = "Hard Stop Consecutive Losers (done for day)", Order = 7, GroupName = "Risk Manager AddOn")]
        public int HardStopConsecutiveLosers { get; set; } = 3;

        // ── Internal ─────────────────────────────────────────────────────────

        // Accounts we are actively monitoring
        private readonly List<Account> _monitoredAccounts = new List<Account>();

        // Equity update throttle — only push to gatekeeper at most once per second per account
        private readonly Dictionary<string, DateTime> _lastEquityUpdate = new Dictionary<string, DateTime>(StringComparer.OrdinalIgnoreCase);

        // Track last-known position quantities to detect closing fills
        // Key = accountName, Value = last quantity seen (0 = flat)
        private readonly Dictionary<string, int> _lastQuantity = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        // Track last-known realized profit/loss to compute PnL deltas on fills
        private readonly Dictionary<string, double> _lastRealizedPnL = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);

        // ── AddOn Lifecycle ───────────────────────────────────────────────────

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Monitors real account equity and fills across all non-excluded accounts " +
                              "and enforces shared risk limits via RiskGatekeeper.";
                Name        = "RiskManagerAddOn";
            }
            else if (State == State.Configure)
            {
                DiscoverAndRegisterAccounts();
            }
            else if (State == State.Terminated)
            {
                UnsubscribeAll();
            }
        }

        // ── Account Discovery ─────────────────────────────────────────────────

        private void DiscoverAndRegisterAccounts()
        {
            HashSet<string> excluded = ParseExcludeList(ExcludedAccounts);

            NinjaTrader.NinjaScript.NinjaScript.Log(
                string.Format("[RiskManagerAddOn] Scanning {0} account(s). Excluded: [{1}]",
                    Account.All.Count, string.Join(", ", excluded)),
                LogLevel.Information);

            foreach (Account account in Account.All)
            {
                if (excluded.Contains(account.Name))
                {
                    NinjaTrader.NinjaScript.NinjaScript.Log(
                        string.Format("[RiskManagerAddOn] SKIPPED (excluded): {0}", account.Name),
                        LogLevel.Information);
                    continue;
                }

                RegisterAndMonitor(account);
            }
        }

        private void RegisterAndMonitor(Account account)
        {
            // Build risk parameters from AddOn settings
            var parameters = new NinjaTrader.NinjaScript.Strategies.Vinay.AccountRiskParameters
            {
                DailyMaxLoss              = DailyMaxLoss,
                TrailingDrawdown          = TrailingDrawdown,
                MaxTradesPerDay           = MaxTradesPerDay,
                MaxConsecutiveLosers      = MaxConsecutiveLosers,
                PauseMinutes              = PauseMinutes,
                HardStopConsecutiveLosers = HardStopConsecutiveLosers,
            };

            // Register with gatekeeper (loads persisted state or starts fresh)
            NinjaTrader.NinjaScript.Strategies.Vinay.RiskGatekeeper.RegisterAccount(account.Name, parameters);

            // Seed / recover real equity from broker
            double currentEquity = account.Get(AccountItem.CashValue, Currency.UsDollar);
            double currentRealized = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
            _lastRealizedPnL[account.Name] = currentRealized;

            NinjaTrader.NinjaScript.Strategies.Vinay.RiskGatekeeper.UpdateEquity(
                account.Name, currentEquity, DateTime.Now);

            // Runtime recovery — reconstruct today's trade history if persisted state was stale
            var state = NinjaTrader.NinjaScript.Strategies.Vinay.RiskGatekeeper.GetState(account.Name);
            if (state != null && state.TradingDate.Date != DateTime.Today)
                RecoverFromBroker(account, currentEquity);

            // Subscribe to live events
            account.AccountItemUpdate  += OnAccountItemUpdate;
            account.ExecutionUpdate    += OnExecutionUpdate;

            _monitoredAccounts.Add(account);
            _lastEquityUpdate[account.Name]  = DateTime.MinValue;
            _lastQuantity[account.Name]      = 0;

            NinjaTrader.NinjaScript.NinjaScript.Log(
                string.Format("[RiskManagerAddOn] Monitoring: {0} | Equity: {1:C}",
                    account.Name, currentEquity),
                LogLevel.Information);
        }

        // ── Runtime Recovery ──────────────────────────────────────────────────

        /// <summary>
        /// Reconstruct today's session state by replaying today's trades from the broker.
        /// </summary>
        private void RecoverFromBroker(Account account, double currentEquity)
        {
            try
            {
                // Build a list of (pnl, time) for today's completed trades
                // NinjaTrader exposes completed trades via account.Executions; we group
                // entry+exit pairs by order name / strategy to compute per-trade PnL.
                // For simplicity we use the account's SystemPerformance when available.
                var todayTrades = new List<(double pnl, DateTime time)>();

                // Walk executions to find closing fills (MarketPosition.Flat = position closed)
                foreach (Execution exec in account.Executions)
                {
                    if (exec.Time.Date != DateTime.Today)
                        continue;

                    // Closing fills bring position to flat — use commission-adjusted PnL
                    // NinjaTrader Execution doesn't expose net PnL directly, so we approximate
                    // from quantity * price delta. A more accurate approach requires correlating
                    // with Trade objects (available via strategy SystemPerformance).
                    // Here we record the fill time; PnL = 0 means trade-count recovery is still
                    // accurate even if PnL value is approximate until the gatekeeper gets
                    // updated by live RecordTrade calls.
                    if (exec.MarketPosition == MarketPosition.Flat)
                        todayTrades.Add((0, exec.Time));
                }

                NinjaTrader.NinjaScript.Strategies.Vinay.RiskGatekeeper.RecoverFromHistory(
                    account.Name, currentEquity, todayTrades);
            }
            catch (Exception ex)
            {
                NinjaTrader.NinjaScript.NinjaScript.Log(
                    string.Format("[RiskManagerAddOn] RecoverFromBroker failed for {0}: {1}",
                        account.Name, ex.Message),
                    LogLevel.Warning);
            }
        }

        // ── Event Handlers ────────────────────────────────────────────────────

        /// <summary>
        /// Fires when account equity / margin / cash values change.
        /// Throttled to at most one push per second to avoid hammering the gatekeeper.
        /// </summary>
        private void OnAccountItemUpdate(object sender, AccountItemEventArgs e)
        {
            if (e.AccountItem != AccountItem.CashValue)
                return;

            string accountName = e.Account.Name;

            // Throttle: skip if we pushed equity less than 1 second ago
            if (_lastEquityUpdate.TryGetValue(accountName, out DateTime lastPush)
                && (DateTime.Now - lastPush).TotalSeconds < 1)
                return;

            _lastEquityUpdate[accountName] = DateTime.Now;

            NinjaTrader.NinjaScript.Strategies.Vinay.RiskGatekeeper.UpdateEquity(
                accountName, e.Value, DateTime.Now);
        }

        /// <summary>
        /// Fires on every order fill.  We detect closing fills by watching the
        /// position quantity drop to zero, then forward the trade to RiskGatekeeper.
        /// </summary>
        private void OnExecutionUpdate(object sender, ExecutionEventArgs e)
        {
            try
            {
                string accountName = e.Execution.Account.Name;

                // New session detection — reset gatekeeper state for the new day
                var state = NinjaTrader.NinjaScript.Strategies.Vinay.RiskGatekeeper.GetState(accountName);
                if (state != null && state.TradingDate.Date != e.Execution.Time.Date)
                {
                    NinjaTrader.NinjaScript.Strategies.Vinay.RiskGatekeeper.ResetDay(
                        accountName, e.Execution.Time.Date);
                }

                // Detect closing fills by position flipping to flat
                // e.Execution.MarketPosition reflects the position AFTER the fill
                if (e.Execution.MarketPosition != MarketPosition.Flat)
                {
                    // Position still open — track the current quantity for next comparison
                    _lastQuantity[accountName] = e.Execution.Quantity;
                    return;
                }

                // Position is now flat — this was a closing fill
                // Compute PnL: use the difference in Account's RealizedProfitLoss
                double pnl = 0;
                var account = e.Execution.Account;
                double currentRealized = account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                if (_lastRealizedPnL.TryGetValue(accountName, out double lastPnL))
                {
                    pnl = currentRealized - lastPnL;
                }
                _lastRealizedPnL[accountName] = currentRealized;

                _lastQuantity[accountName] = 0;

                // RecordTrade handles consecutive-loser logic, pause, done-for-day, persistence
                NinjaTrader.NinjaScript.Strategies.Vinay.RiskGatekeeper.RecordTrade(
                    accountName, pnl, e.Execution.Time);
            }
            catch (Exception ex)
            {
                NinjaTrader.NinjaScript.NinjaScript.Log(
                    string.Format("[RiskManagerAddOn] OnExecutionUpdate error: {0}", ex.Message),
                    LogLevel.Warning);
            }
        }

        // ── Teardown ──────────────────────────────────────────────────────────

        private void UnsubscribeAll()
        {
            foreach (Account account in _monitoredAccounts)
            {
                account.AccountItemUpdate -= OnAccountItemUpdate;
                account.ExecutionUpdate   -= OnExecutionUpdate;
            }
            _monitoredAccounts.Clear();
        }

        // ── Helpers ───────────────────────────────────────────────────────────

        private static HashSet<string> ParseExcludeList(string raw)
        {
            var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (string.IsNullOrWhiteSpace(raw))
                return result;

            foreach (string part in raw.Split(','))
            {
                string trimmed = part.Trim();
                if (!string.IsNullOrEmpty(trimmed))
                    result.Add(trimmed);
            }
            return result;
        }
    }
}
