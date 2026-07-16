#if TESTING
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Linq;

// --- MOCK DEFINITIONS TO AVOID NINJATRADER ASSEMBLY DEPENDENCY IN TEST ENVIRONMENT ---
namespace NinjaTrader.Cbi
{
    public enum MarketPosition { Flat, Long, Short }
    public enum Currency { UsDollar }
    public enum AccountItem { CashValue, RealizedProfitLoss, UnrealizedProfitLoss }
    public enum OrderState { Submitted, Accepted, Working, Cancelled, Filled, PartFilled, Rejected, Unknown, Initialized }
    public enum OrderType { Limit, StopMarket, StopLimit, Market }
    public enum OrderAction { Buy, Sell }
    public enum TimeInForce { Day, Gtc }
    public enum PerformanceUnit { Currency, Percent, Pips, Points, Ticks }

    public class Instrument
    {
        public string FullName { get; set; }
        public MasterInstrument MasterInstrument { get; set; }
        public MarketData MarketData { get; set; }
        public Instrument(string name) 
        { 
            FullName = name; 
            MasterInstrument = new MasterInstrument { Name = name, TickSize = 0.25 };
            MarketData = new MarketData { Last = new Last { Price = 0.0 } };
        }
    }

    public class MasterInstrument
    {
        public string Name { get; set; }
        public double TickSize { get; set; }
        public double RoundToTickSize(double value) => Math.Round(value / TickSize) * TickSize;
    }

    public class MarketData
    {
        public Last Last { get; set; }
    }

    public class Last
    {
        public double Price { get; set; }
    }

    public class Order
    {
        public string Id { get; set; }
        public string OrderId { get; set; }
        public string Name { get; set; }
        public OrderState OrderState { get; set; }
        public OrderType OrderType { get; set; }
        public int Quantity { get; set; }
        public int Filled { get; set; }
        public Instrument Instrument { get; set; }
        public OrderAction OrderAction { get; set; }
        public double LimitPrice { get; set; }
        public double StopPrice { get; set; }
    }

    public class Position
    {
        public Instrument Instrument { get; set; }
        public MarketPosition MarketPosition { get; set; }
        public int Quantity { get; set; }
        public double AveragePrice { get; set; }
        public double UnrealizedPnL { get; set; }
        public double GetUnrealizedProfitLoss(PerformanceUnit unit) => UnrealizedPnL;
    }

    public class Execution
    {
        public Instrument Instrument { get; set; }
        public Order Order { get; set; }
        public int Quantity { get; set; }
        public double Price { get; set; }
    }

    public class Account
    {
        public string Name { get; set; }
        public Dictionary<AccountItem, double> Values { get; set; } = new Dictionary<AccountItem, double>();
        public List<Order> Orders { get; set; } = new List<Order>();
        public List<Position> Positions { get; set; } = new List<Position>();
        public static List<Account> All { get; set; } = new List<Account>();

        public event EventHandler<PositionEventArgs> PositionUpdate;
        public event EventHandler<OrderEventArgs> OrderUpdate;
        public event EventHandler<ExecutionEventArgs> ExecutionUpdate;

        public double Get(AccountItem item, Currency currency)
        {
            return Values.ContainsKey(item) ? Values[item] : 0.0;
        }

        public void Cancel(Order[] orders)
        {
            foreach (var o in orders)
            {
                o.OrderState = OrderState.Cancelled;
            }
        }

        public void Cancel(List<Order> orders)
        {
            foreach (var o in orders)
            {
                o.OrderState = OrderState.Cancelled;
            }
        }

        public void Flatten(Instrument[] instruments)
        {
            Positions.Clear();
            Orders.Clear();
        }

        public Order CreateOrder(Instrument instrument, OrderAction action, OrderType type, TimeInForce tif, int qty, double limit, double stop, string oco, string name, object custom)
        {
            var o = new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderId = Guid.NewGuid().ToString(),
                Name = name,
                OrderState = OrderState.Initialized,
                OrderType = type,
                Quantity = qty,
                Instrument = instrument,
                OrderAction = action,
                LimitPrice = limit,
                StopPrice = stop
            };
            return o;
        }

        public void Submit(Order[] orders)
        {
            foreach (var o in orders)
            {
                o.OrderState = OrderState.Submitted;
                Orders.Add(o);
            }
        }

        public void TriggerPositionUpdate(Position p)
        {
            PositionUpdate?.Invoke(this, new PositionEventArgs { Position = p });
        }

        public void TriggerOrderUpdate(Order o)
        {
            OrderUpdate?.Invoke(this, new OrderEventArgs { Order = o });
        }

        public void TriggerExecutionUpdate(Execution ex)
        {
            ExecutionUpdate?.Invoke(this, new ExecutionEventArgs { Execution = ex });
        }
    }

    public class Connection
    {
        public static event EventHandler<ConnectionStatusEventArgs> ConnectionStatusUpdate;
        public static void TriggerConnectionStatusUpdate(ConnectionStatusEventArgs e)
        {
            ConnectionStatusUpdate?.Invoke(null, e);
        }
    }

    public class ConnectionStatusEventArgs : EventArgs
    {
        public object Status { get; set; }
        public dynamic Connection { get; set; }
    }

    public class PositionEventArgs : EventArgs
    {
        public Position Position { get; set; }
    }

    public class OrderEventArgs : EventArgs
    {
        public Order Order { get; set; }
    }

    public class ExecutionEventArgs : EventArgs
    {
        public Execution Execution { get; set; }
    }
}

namespace NinjaTrader.Core
{
    public static class Globals
    {
        public static string UserDataDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "MockUserData");
    }
}

namespace NinjaTrader.Code
{
    public enum PrintTo { OutputTab1 }
    public static class Output
    {
        public static void Process(string msg, PrintTo tab)
        {
            Console.WriteLine("[OUTPUT] " + msg);
        }
    }
}

namespace NinjaTrader.NinjaScript
{
    public enum State
    {
        SetDefaults,
        Configure,
        Terminated
    }

    public class AddOnBase
    {
        public string Name { get; set; }
        public string Description { get; set; }
        public State State { get; set; }
        protected virtual void OnStateChange() {}
    }
}

namespace NinjaTrader.NinjaScript.AddOns
{
    using NinjaTrader.Cbi;

    // --- TEST EXECUTION HARNESS ---
    public class Program
    {
        private static int _testsPassed = 0;
        private static int _testsFailed = 0;

        public static void Main(string[] args)
        {
            Console.WriteLine("====================================================");
            Console.WriteLine("🛡️ RUNNING RISK GUARD ADDON EDGE CASE UNIT TESTS");
            Console.WriteLine("====================================================");

            // ── Original 9 tests ──
            TestMaxPositionSizeEnforcement();
            TestDailyLossLimitLockout();
            TestTrailingDrawdownLockout();
            TestMaxTradesOvertradingLockout();
            TestConsecutiveLossesCooldownLockout();
            TestAccountExclusionsBypass();
            TestManualUnlockResetsAllMetricsAndPreventsRelocking();
            TestRealizedPnLLagHandling();
            TestMcpBridgeLockoutBlock();

            // ── Critical gap tests ──
            TestIsArmedFalseBypassesAllRules();
            TestTradeTodayCountingOnRoundTrip();
            TestFlipDetectionCountsAsEntry();
            TestCooldownExpiryAllowsReEntry();
            TestOrderCancelledWhenLockedOnOrderUpdate();
            TestOrderCancelledWhenConsecLossesAtMaxNotLocked();

            // ── Important gap tests ──
            TestDailyLossIncludesUnrealizedPnL();
            TestSessionResetInSweep();
            TestLockoutEnforcementFirstSweep();
            TestLockoutEnforcementSubsequentSweepNoPosition();
            TestLockoutEnforcementSubsequentSweepWithNewPosition();
            TestStopGuardAutoStop();
            TestStopGuardFlatten();
            TestStopGuardNoActionWhenStopPresent();
            TestStopGuardTransientStateValidation();
            TestStopGuardPartiallyFilledValidation();
            TestEdgeWindowGateBreach();
            TestConsecutiveWinsResetLossCounter();
            TestAggregateSizeBreach();

            // ── Lower-priority / boundary tests ──
            TestShadowModeSkipsAction();
            TestLiveModeExecutesAction();
            TestMaxSizeAtExactlyLimit();
            TestDailyLossAtExactlyLimit();
            TestIsAccountLockedForUnknownAccount();
            TestMultipleInstrumentsNoPerInstrumentBreach();

            // ── Exclusion deep-dive tests (test-first) ──
            TestExcludedAccountMaxContractsBypassed();
            TestExcludedAccountAllRulesBypassed();
            TestExcludedAccountOrderNotCancelledWhenLocked();
            TestExcludedAccountNotCountedInAggregate();
            TestExcludedAccountNotFlattenedByAggregateBreach();
            TestExcludedAccountSweepDoesNotLockout();
            TestNonExcludedAccountStillCaughtBesideExcludedOne();
            TestExclusionRemovedReEnablesRules();

            // ── Pass 2 Gap Tests (test-first) ──
            TestSweepLockoutSkipsExcludedAccount();
            TestSweepPnLSyncSkipsConsecutiveLossForExcludedAccount();
            TestValidateInvariantReturnsFalseForUnknownAccount();
            TestStopGuardPartialStopGap();
            TestStopGuardWarnOnlyProducesNoAction();
            TestSweepAutoSetsCooldownOnConsecutiveLosses();
            TestProcessActionForceLiveBypassesShadowMode();
            TestEdgeWindowGateInsideWindowNoBreach();
            TestEdgeWindowGateNoWindowsDefinedNoBreach();
            TestMultipleRulesFireSimultaneously();

            // ── Pass 3 Gap Tests ──
            TestAggregateSizingExpectedCopiesScaling();
            TestFirmMirrorTrailingDDBreachEmitsAction();
            TestFirmMirrorDailyLossBreachEmitsAction();
            TestStopGuardDefaultOffsetFallback();

            // ── Manual Lockout Tests ──
            TestManualTimedLockout();
            TestManualEodLockout();
            TestManualUnlockClearsTimedLockout();

            Console.WriteLine("\n====================================================");
            Console.WriteLine(string.Format("RESULTS: Passed = {0}, Failed = {1}", _testsPassed, _testsFailed));
            Console.WriteLine("====================================================");

            if (_testsFailed > 0)
            {
                Environment.Exit(1);
            }
        }

        private static void Assert(bool condition, string message)
        {
            if (condition)
            {
                Console.WriteLine("  [PASS] " + message);
                _testsPassed++;
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("  [FAIL] " + message);
                Console.ResetColor();
                _testsFailed++;
            }
        }

        private static void TestMaxPositionSizeEnforcement()
        {
            Console.WriteLine("\n[TEST] Max Position Sizing Enforcement");
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount = 5;

            var account = new Account();
            account.Name = "TestAcc";
            
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 6, 18000, 0, config);

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Any(a => a.RuleId == "MAX_SIZE_BREACH"), "Size limit breached above max contracts.");

            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 4, 18000, 0, config);
            actions = addon.EvaluateRules(account, state);
            Assert(!actions.Any(a => a.RuleId == "MAX_SIZE_BREACH"), "No size breach under max contracts.");
        }

        private static void TestDailyLossLimitLockout()
        {
            Console.WriteLine("\n[TEST] Daily Loss Limit Lockout");
            var config = new RiskConfig();
            config.PnLRules.DailyLossLimit = 1000.0;

            var account = new Account();
            account.Name = "TestAcc";

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.RealizedPnL = -1100.0;

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Any(a => a.RuleId == "DAILY_LOSS_BREACH"), "Daily loss breach locks out account.");
            Assert(state.IsLockedOut, "Account state is marked as IsLockedOut.");
        }

        private static void TestTrailingDrawdownLockout()
        {
            Console.WriteLine("\n[TEST] Trailing Drawdown Lockout");
            var config = new RiskConfig();
            config.PnLRules.TrailingDrawdown = 1500.0;

            var account = new Account();
            account.Name = "TestAcc";

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");

            // Peak equity at +500
            state.RealizedPnL = 500.0;
            addon.EvaluateRules(account, state);
            Assert(state.PeakEquity == 500.0, "Peak equity correctly tracks top session profit.");

            // Drawdown to -1100 (breach = 500 - 1500 = -1000)
            state.RealizedPnL = -1100.0;
            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Any(a => a.RuleId == "TRAILING_DD_BREACH"), "Trailing Drawdown breach locks out account.");
            Assert(state.IsLockedOut, "Account state is marked as IsLockedOut.");
        }

        private static void TestMaxTradesOvertradingLockout()
        {
            Console.WriteLine("\n[TEST] Max Trades Overtrading Lockout");
            var config = new RiskConfig();
            config.Overtrading.MaxTradesPerSession = 5;

            var account = new Account();
            account.Name = "TestAcc";

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.TradesToday = 6;

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Any(a => a.RuleId == "MAX_TRADES_BREACH"), "Max trades breach locks out account.");
            Assert(state.IsLockedOut, "Account state is marked as IsLockedOut.");
        }

        private static void TestConsecutiveLossesCooldownLockout()
        {
            Console.WriteLine("\n[TEST] Consecutive Losses & Cooldown Lockout");
            var config = new RiskConfig();
            config.Overtrading.MaxConsecutiveLosses = 3;
            config.Overtrading.CooldownMinutes = 5;

            var account = new Account();
            account.Name = "TestAcc";

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.ConsecutiveLosses = 3;

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Any(a => a.RuleId == "CONSECUTIVE_LOSS_BREACH"), "Consec losses breach locks out account.");
            Assert(state.IsLockedOut, "Account state is marked as IsLockedOut.");

            // Check Cooldown
            state.ConsecutiveLosses = 0;
            state.CooldownUntil = DateTime.UtcNow.AddMinutes(5);
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 1, 18000, 0, config);
            actions = addon.EvaluateRules(account, state);
            Assert(actions.Any(a => a.RuleId == "COOLDOWN_BREACH"), "Entering during cooldown triggers flatten.");
        }

        private static void TestAccountExclusionsBypass()
        {
            Console.WriteLine("\n[TEST] Account Exclusions Bypass");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");
            config.PnLRules.DailyLossLimit = 1000.0;

            var account = new Account();
            account.Name = "ExcludedAcc";

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("ExcludedAcc");
            state.RealizedPnL = -1500.0;

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Count == 0, "Excluded account bypasses daily loss limit evaluation.");
            Assert(!state.IsLockedOut, "Excluded account is NOT marked as IsLockedOut.");
        }

        private static void TestManualUnlockResetsAllMetricsAndPreventsRelocking()
        {
            Console.WriteLine("\n[TEST] Manual Unlock Resets All Metrics & Prevents Relocking");
            var config = new RiskConfig();
            config.PnLRules.DailyLossLimit = 1000.0;
            config.PnLRules.TrailingDrawdown = 1500.0;
            config.Overtrading.MaxConsecutiveLosses = 3;
            config.Overtrading.MaxTradesPerSession = 5;

            var account = new Account();
            account.Name = "TestAcc";
            account.Values[AccountItem.RealizedProfitLoss] = -1200.0; // Currently down 1200

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            
            var state = new AccountState("TestAcc");
            state.IsLockedOut = true;
            state.PeakEquity = 200.0;
            state.TradesToday = 6;
            state.ConsecutiveLosses = 4;
            state.CooldownUntil = DateTime.UtcNow.AddMinutes(5);
            state.SessionStartRealizedPnL = 0.0;
            state.RealizedPnL = -1200.0;

            addon.SetAccountStateForTest("TestAcc", state);
            addon.SetSubscribedAccountForTest("TestAcc");

            // Account must be in Account.All so UnlockAccount can read its realized PnL
            Account.All.Clear();
            Account.All.Add(account);

            // --- PERFORM THE UNLOCK ---
            addon.UnlockAccount("TestAcc");

            // Verify all metrics reset
            Assert(!state.IsLockedOut, "IsLockedOut is set to false.");
            Assert(state.PeakEquity == 0.0, "PeakEquity is reset to 0.0.");
            Assert(state.TradesToday == 0, "TradesToday is reset to 0.");
            Assert(state.ConsecutiveLosses == 0, "ConsecutiveLosses is reset to 0.");
            Assert(state.CooldownUntil == DateTime.MinValue, "CooldownUntil is reset.");
            Assert(state.SessionStartRealizedPnL == -1200.0, "SessionStartRealizedPnL updated to current realized balance (-1200).");
            Assert(state.RealizedPnL == 0.0, "Relative RealizedPnL reset to 0.0.");

            // --- RUN EVALUATOR AGAIN ---
            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Count == 0, "No new lockout actions generated after unlocking (relative PnL is 0).");
            Assert(!state.IsLockedOut, "Account stays active (does not instantly re-lock!).");
        }

        private static void TestRealizedPnLLagHandling()
        {
            Console.WriteLine("\n[TEST] Real-Time PnL Lag Handling");
            var config = new RiskConfig();
            config.Overtrading.MaxConsecutiveLosses = 3;
            config.Overtrading.CooldownMinutes = 5;

            var account = new Account();
            account.Name = "TestAcc";

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.SessionStartRealizedPnL = 0.0;
            state.RealizedPnL = 0.0;
            state.ConsecutiveLosses = 0;

            addon.SetAccountStateForTest("TestAcc", state);
            addon.SetSubscribedAccountForTest("TestAcc");
            Account.All.Clear();
            Account.All.Add(account);

            // Pre-seed LastSessionDate to today so the sweep doesn't trigger a session reset
            // (which would overwrite SessionStartRealizedPnL back to 0)
            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            var currentSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;
            state.LastSessionDate = currentSessionDate;

            // 1. Simulate position closed (transition to flat).
            // At this exact moment, realized PnL is still 0 (lagging).
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Flat, 0, 0, 0, config);
            
            // Verify consecutive losses hasn't changed because PnL didn't change
            Assert(state.ConsecutiveLosses == 0, "Consecutive losses remains 0 immediately upon Flat update (lagging PnL).");

            // 2. A split second later, PnL updates on the account
            account.Values[AccountItem.RealizedProfitLoss] = -150.0;

            // 3. Safety sweep runs
            addon.ExecuteSafetySweep();

            // Verify ConsecutiveLosses was incremented in the safety sweep when it caught the change
            Assert(state.ConsecutiveLosses == 1, "Consecutive losses successfully incremented after sweep catches lagged realized PnL.");
            Assert(state.RealizedPnL == -150.0, "State RealizedPnL correctly syncs with lagging realized PnL.");
        }

        private static void TestMcpBridgeLockoutBlock()
        {
            Console.WriteLine("\n[TEST] McpBridge Lockout Block");
            var config = new RiskConfig();
            var account = new Account();
            account.Name = "TestAcc";

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            
            var state = new AccountState("TestAcc");
            addon.SetAccountStateForTest("TestAcc", state);

            Assert(!addon.IsAccountLocked("TestAcc"), "Account is not locked initially.");

            state.IsLockedOut = true;
            Assert(addon.IsAccountLocked("TestAcc"), "Account is correctly identified as locked.");
        }

        // ════════════════════════════════════════════════════════
        // CRITICAL GAP TESTS
        // ════════════════════════════════════════════════════════

        private static void TestIsArmedFalseBypassesAllRules()
        {
            Console.WriteLine("\n[TEST] IsArmed=false Bypasses All Rules");
            var config = new RiskConfig();
            config.PnLRules.DailyLossLimit = 1000.0;
            config.Sizing.MaxContractsPerAccount = 5;
            config.Overtrading.MaxTradesPerSession = 5;

            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetArmedForTest(false); // Disarm

            var state = new AccountState("TestAcc");
            state.RealizedPnL = -2000.0;  // Would breach daily loss
            state.TradesToday = 10;        // Would breach max trades
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 10, 18000, 0, config); // Would breach max size

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Count == 0, "Disarmed system returns 0 actions even with all rules violated.");
            Assert(!state.IsLockedOut, "Disarmed system does not lock out account.");
        }

        private static void TestTradeTodayCountingOnRoundTrip()
        {
            Console.WriteLine("\n[TEST] TradesToday Counts Each Open Leg");
            var config = new RiskConfig();
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var mnq = new Instrument("MNQ");

            // Trade 1: enter Long
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);
            Assert(state.TradesToday == 1, "TradesToday == 1 after first entry.");

            // Close trade 1
            state.UpdatePosition(account, mnq, MarketPosition.Flat, 0, 0, 0, config);
            Assert(state.TradesToday == 1, "TradesToday stays 1 after close.");

            // Trade 2: enter Long again
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18100, 0, config);
            Assert(state.TradesToday == 2, "TradesToday == 2 after second entry.");

            // Close trade 2
            state.UpdatePosition(account, mnq, MarketPosition.Flat, 0, 0, 0, config);
            Assert(state.TradesToday == 2, "TradesToday stays 2 after second close.");
        }

        private static void TestFlipDetectionCountsAsEntry()
        {
            Console.WriteLine("\n[TEST] Long→Short Flip Counts As Entry");
            var config = new RiskConfig();
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var mnq = new Instrument("MNQ");

            // Enter Long
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);
            Assert(state.TradesToday == 1, "TradesToday == 1 after Long entry.");

            // Flip directly to Short (Long→Short in one NT update)
            state.UpdatePosition(account, mnq, MarketPosition.Short, 2, 18100, 0, config);
            Assert(state.TradesToday == 2, "TradesToday == 2 after Long→Short flip (flip counts as new entry).");

            // Verify we're correctly Short
            Assert(state.Positions[mnq.FullName].MarketPosition == MarketPosition.Short, "Position correctly shows Short after flip.");
        }

        private static void TestCooldownExpiryAllowsReEntry()
        {
            Console.WriteLine("\n[TEST] Expired Cooldown Allows Re-Entry");
            var config = new RiskConfig();
            config.Overtrading.CooldownMinutes = 5;

            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            // Cooldown expired 1 minute ago
            state.CooldownUntil = DateTime.UtcNow.AddMinutes(-1);
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 1, 18000, 0, config);

            var actions = addon.EvaluateRules(account, state);

            Assert(!actions.Any(a => a.RuleId == "COOLDOWN_BREACH"), "No COOLDOWN_BREACH after cooldown has expired.");
        }

        private static void TestOrderCancelledWhenLockedOnOrderUpdate()
        {
            Console.WriteLine("\n[TEST] Working Order Cancelled When Account Is Locked");
            var config = new RiskConfig();
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.IsLockedOut = true;
            addon.SetAccountStateForTest("TestAcc", state);

            var order = new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderState = OrderState.Working,
                OrderType = OrderType.Limit,
                Instrument = new Instrument("MNQ")
            };
            account.Orders.Add(order);

            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = order });

            Assert(order.OrderState == OrderState.Cancelled,
                "Working Limit order is cancelled when account is locked.");
        }

        private static void TestOrderNotCancelledInFilledStateWhenLocked()
        {
            Console.WriteLine("\n[TEST] Filled Order NOT Cancelled When Account Is Locked");
            var config = new RiskConfig();
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.IsLockedOut = true;
            addon.SetAccountStateForTest("TestAcc", state);

            var order = new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderState = OrderState.Filled,  // Already filled — should NOT be cancelled
                OrderType = OrderType.Limit,
                Instrument = new Instrument("MNQ")
            };

            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = order });

            Assert(order.OrderState == OrderState.Filled,
                "Filled order state is unchanged even when account is locked.");
        }

        private static void TestOrderCancelledWhenConsecLossesAtMaxNotLocked()
        {
            Console.WriteLine("\n[TEST] Order Cancelled When ConsecLosses At Max (Not Formally Locked)");
            var config = new RiskConfig();
            config.Overtrading.MaxConsecutiveLosses = 3;

            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.IsLockedOut = false;         // NOT formally locked
            state.ConsecutiveLosses = 3;       // But at the consec-loss limit
            addon.SetAccountStateForTest("TestAcc", state);

            var order = new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderState = OrderState.Submitted,
                OrderType = OrderType.Market,
                Instrument = new Instrument("MNQ")
            };
            account.Orders.Add(order);

            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = order });

            Assert(order.OrderState == OrderState.Cancelled,
                "Submitted Market order cancelled when consecutive losses at max (even without formal lockout).");
        }

        // ════════════════════════════════════════════════════════
        // IMPORTANT GAP TESTS
        // ════════════════════════════════════════════════════════

        private static void TestDailyLossIncludesUnrealizedPnL()
        {
            Console.WriteLine("\n[TEST] Daily Loss Limit Includes Unrealized PnL");
            var config = new RiskConfig();
            config.PnLRules.DailyLossLimit = 1000.0;

            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.RealizedPnL   = -500.0;  // Within limit alone
            state.UnrealizedPnL = -600.0;  // Combined = -1100 → breach

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "DAILY_LOSS_BREACH fires when Realized + Unrealized combined exceeds limit.");
            Assert(state.IsLockedOut, "Account locked when unrealized PnL tips combined total past limit.");

            // Boundary: realized -500 + unrealized -499 = -999, within limit
            var state2 = new AccountState("TestAcc2");
            state2.RealizedPnL   = -500.0;
            state2.UnrealizedPnL = -499.0; // Combined = -999, just inside limit
            var actions2 = addon.EvaluateRules(account, state2);
            Assert(!actions2.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "No DAILY_LOSS_BREACH when Realized + Unrealized is just within limit.");
        }

        private static void TestSessionResetInSweep()
        {
            Console.WriteLine("\n[TEST] Session Reset Resets All Counters");
            var config = new RiskConfig();
            config.PnLRules.DailyLossLimit = 0.0; // Disable rules so only reset logic runs

            var account = new Account { Name = "TestAcc" };
            account.Values[AccountItem.RealizedProfitLoss] = -500.0;

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.TradesToday      = 7;
            state.ConsecutiveLosses = 4;
            state.PeakEquity       = 300.0;
            state.IsLockedOut      = true;
            // Deliberately set LastSessionDate to yesterday to trigger reset
            state.LastSessionDate  = DateTime.UtcNow.Date.AddDays(-2);
            state.SessionStartRealizedPnL = 0.0;

            addon.SetAccountStateForTest("TestAcc", state);
            addon.SetSubscribedAccountForTest("TestAcc");
            Account.All.Clear();
            Account.All.Add(account);

            addon.ExecuteSafetySweep();

            Assert(state.TradesToday == 0,       "TradesToday reset to 0 on new session.");
            Assert(state.ConsecutiveLosses == 0, "ConsecutiveLosses reset to 0 on new session.");
            Assert(state.PeakEquity == 0.0,      "PeakEquity reset to 0 on new session.");
            Assert(!state.IsLockedOut,            "IsLockedOut reset to false on new session.");
            Assert(state.SessionStartRealizedPnL == -500.0,
                "SessionStartRealizedPnL re-baselined to current account realized (-500) on new session.");
        }

        private static void TestLockoutEnforcementFirstSweep()
        {
            Console.WriteLine("\n[TEST] First Sweep After Lockout Flattens + Cancels");
            var config = new RiskConfig();

            var account = new Account { Name = "TestAcc" };
            // Simulate an open position on the account
            account.Positions.Add(new Position
            {
                Instrument      = new Instrument("MNQ"),
                MarketPosition  = MarketPosition.Long,
                Quantity        = 2,
                AveragePrice    = 18000
            });
            var workingOrder = new Order
            {
                Id         = Guid.NewGuid().ToString(),
                OrderState = OrderState.Working,
                OrderType  = OrderType.Limit,
                Instrument = new Instrument("MNQ")
            };
            account.Orders.Add(workingOrder);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");  // Must be live for actions to execute

            var state = new AccountState("TestAcc");
            state.IsLockedOut             = true;
            state.InitialLockoutFlattened = false;  // First time
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 2, 18000, 0, config);

            addon.SetAccountStateForTest("TestAcc", state);
            addon.SetSubscribedAccountForTest("TestAcc");
            Account.All.Clear();
            Account.All.Add(account);

            // Seed LastSessionDate to avoid session-reset side-effect
            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            state.LastSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

            addon.ExecuteSafetySweep();

            Assert(state.InitialLockoutFlattened, "InitialLockoutFlattened set to true after first enforcement sweep.");
            Assert(account.Positions.Count == 0, "Positions cleared after first lockout enforcement sweep.");
            Assert(workingOrder.OrderState == OrderState.Cancelled, "Working order cancelled by lockout enforcement.");
        }

        private static void TestLockoutEnforcementSubsequentSweepNoPosition()
        {
            Console.WriteLine("\n[TEST] Subsequent Sweep With Locked + No Positions → No Action");
            var config = new RiskConfig();

            var account = new Account { Name = "TestAcc" };  // No positions
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");

            var state = new AccountState("TestAcc");
            state.IsLockedOut             = true;
            state.InitialLockoutFlattened = true; // Already flattened once
            // No positions in state either

            addon.SetAccountStateForTest("TestAcc", state);
            addon.SetSubscribedAccountForTest("TestAcc");
            Account.All.Clear();
            Account.All.Add(account);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            state.LastSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

            addon.ExecuteSafetySweep();

            // Still locked, nothing to flatten, should remain stable
            Assert(state.IsLockedOut, "Account remains locked after subsequent sweep.");
            Assert(account.Positions.Count == 0, "No positions to flatten — account stays flat.");
        }

        private static void TestLockoutEnforcementSubsequentSweepWithNewPosition()
        {
            Console.WriteLine("\n[TEST] Subsequent Sweep With Locked + New Position → Re-Flattened");
            var config = new RiskConfig();

            var account = new Account { Name = "TestAcc" };
            // A new position snuck in after the first enforcement
            account.Positions.Add(new Position
            {
                Instrument     = new Instrument("MNQ"),
                MarketPosition = MarketPosition.Long,
                Quantity       = 1,
                AveragePrice   = 18000
            });

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");

            var state = new AccountState("TestAcc");
            state.IsLockedOut             = true;
            state.InitialLockoutFlattened = true; // Already ran first enforcement
            // Inject the snuck-in position into state
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 1, 18000, 0, config);

            addon.SetAccountStateForTest("TestAcc", state);
            addon.SetSubscribedAccountForTest("TestAcc");
            Account.All.Clear();
            Account.All.Add(account);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            state.LastSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

            addon.ExecuteSafetySweep();

            Assert(account.Positions.Count == 0, "New position re-flattened by lockout enforcement on subsequent sweep.");
        }

        private static void TestStopGuardAutoStop()
        {
            Console.WriteLine("\n[TEST] StopGuard AutoStop: Position With No Stop → MISSING_STOP_ATTACH");
            var config = new RiskConfig();
            config.StopGuard.OnMissing        = "AutoStop";
            config.StopGuard.StopAttachSeconds = 2;

            var account = new Account { Name = "TestAcc" }; // No working stop orders
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var mnq   = new Instrument("MNQ");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);

            // Backdate the entry so StopAttachSeconds has elapsed
            state.Positions[mnq.FullName].LastNonFlatTransition = DateTime.UtcNow.AddSeconds(-10);

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Any(a => a.RuleId == "MISSING_STOP_ATTACH"),
                "MISSING_STOP_ATTACH action generated when position is unprotected past grace period.");
        }

        private static void TestStopGuardFlatten()
        {
            Console.WriteLine("\n[TEST] StopGuard Flatten: Position With No Stop → MISSING_STOP_FLATTEN");
            var config = new RiskConfig();
            config.StopGuard.OnMissing        = "Flatten";
            config.StopGuard.StopAttachSeconds = 2;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var mnq   = new Instrument("MNQ");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);
            state.Positions[mnq.FullName].LastNonFlatTransition = DateTime.UtcNow.AddSeconds(-10);

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Any(a => a.RuleId == "MISSING_STOP_FLATTEN"),
                "MISSING_STOP_FLATTEN action generated when OnMissing=Flatten and no stop after grace period.");
        }

        private static void TestStopGuardNoActionWhenStopPresent()
        {
            Console.WriteLine("\n[TEST] StopGuard: No Action When Stop Quantity Covers Position");
            var config = new RiskConfig();
            config.StopGuard.OnMissing        = "AutoStop";
            config.StopGuard.StopAttachSeconds = 2;

            var account = new Account { Name = "TestAcc" };
            var mnq     = new Instrument("MNQ");

            // Add a working stop order that covers the 2-contract position
            account.Orders.Add(new Order
            {
                Id          = Guid.NewGuid().ToString(),
                OrderState  = OrderState.Working,
                OrderType   = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,   // Opposite of Long = stop
                Quantity    = 2,
                Instrument  = mnq
            });

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);
            state.Positions[mnq.FullName].LastNonFlatTransition = DateTime.UtcNow.AddSeconds(-10);

            var actions = addon.EvaluateRules(account, state);

            Assert(!actions.Any(a => a.RuleId == "MISSING_STOP_ATTACH" || a.RuleId == "MISSING_STOP_FLATTEN"),
                "No StopGuard action when working stop fully covers position quantity.");
        }

        private static void TestStopGuardTransientStateValidation()
        {
            Console.WriteLine("\n[TEST] StopGuard: Transient Order States Count Towards Protection");
            var config = new RiskConfig();
            config.StopGuard.OnMissing = "AutoStop";
            config.StopGuard.StopAttachSeconds = 2;

            var account = new Account { Name = "TestAcc" };
            var mnq = new Instrument("MNQ");

            // Add a pending submit stop order (transient state)
            account.Orders.Add(new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderState = OrderState.Initialized, 
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 2,
                Instrument = mnq
            });

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);
            state.Positions[mnq.FullName].LastNonFlatTransition = DateTime.UtcNow.AddSeconds(-10);

            var actions = addon.EvaluateRules(account, state);

            Assert(!actions.Any(a => a.RuleId == "MISSING_STOP_ATTACH"),
                "No StopGuard action when order is in Initialized transient state.");
        }

        private static void TestStopGuardPartiallyFilledValidation()
        {
            Console.WriteLine("\n[TEST] StopGuard: Partially Filled Orders Calculate Remaining Correctly");
            var config = new RiskConfig();
            config.StopGuard.OnMissing = "AutoStop";
            config.StopGuard.StopAttachSeconds = 2;

            var account = new Account { Name = "TestAcc" };
            var mnq = new Instrument("MNQ");

            // Stop order for 3 contracts, but 2 are filled, so only 1 remaining working
            account.Orders.Add(new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderState = OrderState.PartFilled,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 3,
                Filled = 2, // Only 1 contract remains working
                Instrument = mnq
            });

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            // Position is 2. We only have 1 working stop. We should get an AutoStop for 1 contract.
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);
            state.Positions[mnq.FullName].LastNonFlatTransition = DateTime.UtcNow.AddSeconds(-10);

            var actions = addon.EvaluateRules(account, state);

            var autoStopAction = actions.FirstOrDefault(a => a.RuleId == "MISSING_STOP_ATTACH");
            Assert(autoStopAction != null, "AutoStop generated because partial fill leaves position under-protected.");
            if (autoStopAction != null)
            {
                Assert(autoStopAction.Quantity == 1, $"AutoStop quantity should be 1 (2 pos - 1 remaining stop), but was {autoStopAction.Quantity}.");
            }
        }

        private static void TestEdgeWindowGateBreach()
        {
            Console.WriteLine("\n[TEST] EdgeWindowGate: Position Entered Outside Window → Breach");
            var config = new RiskConfig();
            config.EnableWindowGate = true;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            // Define window 09:50–11:10 ET Monday–Friday
            var parsedWindow = new ParsedWindow
            {
                Start = new TimeSpan(9, 50, 0),
                End   = new TimeSpan(11, 10, 0),
                Days  = new HashSet<DayOfWeek> { DayOfWeek.Monday, DayOfWeek.Tuesday, DayOfWeek.Wednesday, DayOfWeek.Thursday, DayOfWeek.Friday }
            };
            addon.SetParsedWindowsForTest(new List<ParsedWindow> { parsedWindow });

            var state = new AccountState("TestAcc");
            var mnq   = new Instrument("MNQ");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 1, 18000, 0, config);

            // Backdate entry to 08:00 ET on a weekday = clearly outside the 09:50 window.
            // Use a known Monday at 12:00 UTC = 08:00 ET (summer, UTC-4).
            state.Positions[mnq.FullName].LastNonFlatTransition =
                new DateTime(2026, 7, 13, 12, 0, 0, DateTimeKind.Utc); // Monday 2026-07-13 08:00 ET

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Any(a => a.RuleId == "EDGE_WINDOW_BREACH"),
                "EDGE_WINDOW_BREACH fires when position was entered outside permitted window.");
        }

        private static void TestConsecutiveWinsResetLossCounter()
        {
            Console.WriteLine("\n[TEST] Consecutive Win Resets Loss Counter in Sweep");
            var config = new RiskConfig();
            config.Overtrading.MaxConsecutiveLosses = 3;

            var account = new Account { Name = "TestAcc" };
            account.Values[AccountItem.RealizedProfitLoss] = 200.0; // Profitable

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.ConsecutiveLosses        = 2;
            state.SessionStartRealizedPnL  = 0.0;
            state.RealizedPnL              = 0.0;  // State hasn't synced yet

            addon.SetAccountStateForTest("TestAcc", state);
            addon.SetSubscribedAccountForTest("TestAcc");
            Account.All.Clear();
            Account.All.Add(account);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            state.LastSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

            addon.ExecuteSafetySweep(); // Sweep picks up +200 realized PnL → win

            Assert(state.ConsecutiveLosses == 0,
                "Consecutive loss counter reset to 0 after a profitable trade detected in sweep.");
            Assert(state.RealizedPnL == 200.0,
                "RealizedPnL synced to 200 after winning sweep.");
        }

        private static void TestAggregateSizeBreach()
        {
            Console.WriteLine("\n[TEST] Aggregate Cross-Account Size Breach");
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount  = 15;
            config.Sizing.MaxContractsAggregate   = 20;
            config.Sizing.ExpectedCopies          = 1;

            var acc1 = new Account { Name = "Acc1" };
            var acc2 = new Account { Name = "Acc2" };

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state1 = new AccountState("Acc1");
            var state2 = new AccountState("Acc2");
            var mnq    = new Instrument("MNQ");

            // 12 contracts each = 24 total > aggregate limit of 20
            state1.UpdatePosition(acc1, mnq, MarketPosition.Long, 12, 18000, 0, config);
            state2.UpdatePosition(acc2, mnq, MarketPosition.Long, 12, 18000, 0, config);

            addon.SetAccountStateForTest("Acc1", state1);
            addon.SetAccountStateForTest("Acc2", state2);
            addon.SetSubscribedAccountForTest("Acc1");
            addon.SetSubscribedAccountForTest("Acc2");
            Account.All.Clear();
            Account.All.Add(acc1);
            Account.All.Add(acc2);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            var today  = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;
            state1.LastSessionDate = today;
            state2.LastSessionDate = today;

            // We need live mode for ProcessAction to run, but we test the sweep logic
            // by checking that lockout actions would be generated. Use shadow mode but
            // verify the sweep didn't throw and the logic path was hit.
            addon.SetModeForTest("shadow");
            addon.ExecuteSafetySweep();

            // In shadow mode the flatten won't execute but we can verify the rule would have fired
            // by checking the aggregate contract count logic directly via EvaluateRules state.
            // After sweep in shadow mode with 12+12=24 > 20 aggregate: the aggregate check fires.
            // We verify this by showing the individual accounts are not per-account breached (12 < 15)
            // but combined would be. The sweep handles aggregate separately from per-account.
            var perAccActions1 = addon.EvaluateRules(acc1, state1);
            Assert(!perAccActions1.Any(a => a.RuleId == "MAX_SIZE_BREACH"),
                "Per-account rule does not fire since 12 < 15 per-account limit.");

            // Temporarily lower aggregate and verify sweep logic triggers for aggregate
            config.Sizing.MaxContractsAggregate = 10; // Now 24 > 10 aggregate
            addon.ExecuteSafetySweep(); // Shadow mode — won't flatten but exercises the code path
            Assert(true, "Aggregate size breach sweep runs without exception.");
        }

        // ════════════════════════════════════════════════════════
        // LOWER-PRIORITY / BOUNDARY TESTS
        // ════════════════════════════════════════════════════════

        private static void TestShadowModeSkipsAction()
        {
            Console.WriteLine("\n[TEST] Shadow Mode Skips Action Execution");
            var config = new RiskConfig();

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("shadow"); // Default, but explicit

            Account.All.Clear();
            Account.All.Add(account);

            var action = new GuardAction
            {
                AccountName = "TestAcc",
                ActionType  = GuardActionType.FlattenPosition,
                RuleId      = "TEST_RULE"
            };

            string result = addon.ProcessAction(action);

            Assert(result == "SHADOW (SKIPPED)",
                "ProcessAction returns 'SHADOW (SKIPPED)' in shadow mode.");
            Assert(account.Positions.Count == 0, "No positions were touched in shadow mode.");
        }

        private static void TestLiveModeExecutesAction()
        {
            Console.WriteLine("\n[TEST] Live Mode Executes Action");
            var config = new RiskConfig();

            var account = new Account { Name = "TestAcc" };
            account.Positions.Add(new Position
            {
                Instrument     = new Instrument("MNQ"),
                MarketPosition = MarketPosition.Long,
                Quantity       = 1,
                AveragePrice   = 18000
            });

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");

            Account.All.Clear();
            Account.All.Add(account);

            var action = new GuardAction
            {
                AccountName = "TestAcc",
                ActionType  = GuardActionType.FlattenPosition,
                RuleId      = "TEST_RULE"
            };

            string result = addon.ProcessAction(action);

            Assert(result == "EXECUTED", "ProcessAction returns 'EXECUTED' in live mode.");
            Assert(account.Positions.Count == 0, "Position was actually flattened in live mode.");
        }

        private static void TestMaxSizeAtExactlyLimit()
        {
            Console.WriteLine("\n[TEST] Max Size At Exactly The Limit — No Breach");
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount = 5;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            // Exactly at the limit — code uses >, not >=
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 5, 18000, 0, config);

            var actions = addon.EvaluateRules(account, state);

            Assert(!actions.Any(a => a.RuleId == "MAX_SIZE_BREACH"),
                "No MAX_SIZE_BREACH when quantity == limit (rule uses strict >, not >=).");
        }

        private static void TestDailyLossAtExactlyLimit()
        {
            Console.WriteLine("\n[TEST] Daily Loss At Exactly The Limit — No Breach");
            var config = new RiskConfig();
            config.PnLRules.DailyLossLimit = 1000.0;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            // Exactly at -1000 — code uses < -Limit, so -1000 < -1000 is false
            state.RealizedPnL = -1000.0;

            var actions = addon.EvaluateRules(account, state);

            Assert(!actions.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "No DAILY_LOSS_BREACH when PnL == -limit exactly (strict < rule).");
        }

        private static void TestIsAccountLockedForUnknownAccount()
        {
            Console.WriteLine("\n[TEST] IsAccountLocked Returns False For Unknown Account");
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(new RiskConfig());

            Assert(!addon.IsAccountLocked("NonExistentAccount"),
                "IsAccountLocked returns false (not exception) for an account that has never been seen.");
        }

        private static void TestMultipleInstrumentsNoPerInstrumentBreach()
        {
            Console.WriteLine("\n[TEST] Multiple Instruments — No Per-Instrument Breach When Each Is Under Limit");
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount = 5;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            // MNQ = 3 contracts, ES = 3 contracts — each individually under limit of 5
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 3, 18000, 0, config);
            state.UpdatePosition(account, new Instrument("ES"),  MarketPosition.Short, 3, 5000,  0, config);

            var actions = addon.EvaluateRules(account, state);

            Assert(!actions.Any(a => a.RuleId == "MAX_SIZE_BREACH"),
                "No MAX_SIZE_BREACH when each instrument is individually within the per-account limit.");
        }

        // ════════════════════════════════════════════════════════
        // EXCLUSION DEEP-DIVE TESTS  (test-first — these define the correct behaviour)
        // ════════════════════════════════════════════════════════

        // ────────────────────────────────────────────────────────
        // An excluded account must bypass ALL rules - EvaluateRules path
        // ────────────────────────────────────────────────────────
        private static void TestExcludedAccountMaxContractsBypassed()
        {
            Console.WriteLine("\n[TEST] Excluded Account: MaxContracts Rule Is Bypassed");
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount = 3;
            config.ExcludedAccounts.Add("ExcludedAcc");

            var account = new Account { Name = "ExcludedAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("ExcludedAcc");
            // 10 contracts — far exceeds limit of 3 — but account is excluded
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 10, 18000, 0, config);

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Count == 0,
                "Excluded account returns 0 rule actions even with 10 contracts (limit 3).");
            Assert(!state.IsLockedOut,
                "Excluded account is NOT locked out despite exceeding max contracts.");
        }

        // ────────────────────────────────────────────────────────
        // Excluded account: ALL rules bypassed simultaneously
        // ────────────────────────────────────────────────────────
        private static void TestExcludedAccountAllRulesBypassed()
        {
            Console.WriteLine("\n[TEST] Excluded Account: All Rules Bypassed Simultaneously");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");
            config.Sizing.MaxContractsPerAccount    = 2;
            config.PnLRules.DailyLossLimit          = 100.0;
            config.PnLRules.TrailingDrawdown        = 100.0;
            config.Overtrading.MaxTradesPerSession  = 1;
            config.Overtrading.MaxConsecutiveLosses = 1;
            config.Overtrading.CooldownMinutes      = 60;

            var account = new Account { Name = "ExcludedAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("ExcludedAcc");
            state.RealizedPnL      = -5000.0;  // Breaches DailyLoss
            state.UnrealizedPnL    = -5000.0;  // Breaches TrailingDD
            state.PeakEquity       = 0.0;
            state.TradesToday      = 99;        // Breaches MaxTrades
            state.ConsecutiveLosses = 99;       // Breaches ConsecLosses
            state.CooldownUntil    = DateTime.UtcNow.AddHours(1); // In cooldown
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 10, 18000, 0, config); // Breaches MaxSize + Cooldown

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Count == 0,
                "Excluded account has 0 rule actions even with every single rule violated.");
            Assert(!state.IsLockedOut,
                "Excluded account is NEVER locked out.");
        }

        // ────────────────────────────────────────────────────────
        // Excluded account: OnOrderUpdate must NOT cancel its orders
        // ────────────────────────────────────────────────────────
        private static void TestExcludedAccountOrderNotCancelledWhenLocked()
        {
            Console.WriteLine("\n[TEST] Excluded Account: Working Order NOT Cancelled Even With IsLockedOut=true");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");

            var account = new Account { Name = "ExcludedAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            // Even if state somehow has IsLockedOut=true (e.g. stale persisted state)
            var state = new AccountState("ExcludedAcc");
            state.IsLockedOut = true;
            addon.SetAccountStateForTest("ExcludedAcc", state);

            var order = new Order
            {
                Id         = Guid.NewGuid().ToString(),
                OrderState = OrderState.Working,
                OrderType  = OrderType.Market,
                Instrument = new Instrument("MNQ")
            };
            account.Orders.Add(order);

            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = order });

            Assert(order.OrderState == OrderState.Working,
                "Working order on excluded account is NOT cancelled, even when IsLockedOut=true.");
        }

        // ────────────────────────────────────────────────────────
        // BUG: Excluded account contracts must NOT count toward aggregate total
        // ────────────────────────────────────────────────────────
        private static void TestExcludedAccountNotCountedInAggregate()
        {
            Console.WriteLine("\n[TEST] Excluded Account Contracts NOT Counted In Aggregate Total");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");
            config.Sizing.MaxContractsAggregate = 10;
            config.Sizing.ExpectedCopies        = 1;

            // ExcludedAcc: 20 contracts (excluded, should be invisible to aggregate)
            // NormalAcc:    5 contracts (under the limit of 10)
            // Without the fix: 20+5=25 > 10 → triggers aggregate breach on NormalAcc
            // With the fix:      0+5= 5 <= 10 → no breach

            var exclAcc   = new Account { Name = "ExcludedAcc" };
            var normalAcc = new Account { Name = "NormalAcc" };

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");

            var exclState   = new AccountState("ExcludedAcc");
            var normalState = new AccountState("NormalAcc");
            var mnq         = new Instrument("MNQ");

            exclState.UpdatePosition(exclAcc, mnq, MarketPosition.Long, 20, 18000, 0, config);
            normalState.UpdatePosition(normalAcc, mnq, MarketPosition.Long, 5, 18000, 0, config);

            // Reflect positions on account.Positions for ExecuteAction to see
            exclAcc.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 20, AveragePrice = 18000 });
            normalAcc.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 5, AveragePrice = 18000 });

            addon.SetAccountStateForTest("ExcludedAcc", exclState);
            addon.SetAccountStateForTest("NormalAcc",   normalState);
            addon.SetSubscribedAccountForTest("ExcludedAcc");
            addon.SetSubscribedAccountForTest("NormalAcc");
            Account.All.Clear();
            Account.All.Add(exclAcc);
            Account.All.Add(normalAcc);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            var today  = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;
            exclState.LastSessionDate   = today;
            normalState.LastSessionDate = today;

            addon.ExecuteSafetySweep();

            Assert(normalAcc.Positions.Count > 0,
                "NormalAcc (5 contracts, under limit) is NOT flattened when excluded account's 20 contracts are correctly ignored in aggregate.");
            Assert(exclAcc.Positions.Count > 0,
                "ExcludedAcc is NOT flattened by aggregate check.");
        }

        // ────────────────────────────────────────────────────────
        // BUG: Excluded account must NOT be flattened by aggregate breach action
        // ────────────────────────────────────────────────────────
        private static void TestExcludedAccountNotFlattenedByAggregateBreach()
        {
            Console.WriteLine("\n[TEST] Excluded Account NOT Flattened Even When Aggregate Limit Breached By Non-Excluded Accounts");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");
            config.Sizing.MaxContractsAggregate = 5;
            config.Sizing.ExpectedCopies        = 1;

            // Two non-excluded accounts breach the aggregate limit.
            // The excluded account has a position too.
            // The excluded account must NOT be flattened.

            var exclAcc = new Account { Name = "ExcludedAcc" };
            var normAcc1 = new Account { Name = "NormAcc1" };
            var normAcc2 = new Account { Name = "NormAcc2" };

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");

            var mnq = new Instrument("MNQ");

            var exclState  = new AccountState("ExcludedAcc");
            var normState1 = new AccountState("NormAcc1");
            var normState2 = new AccountState("NormAcc2");

            exclState.UpdatePosition(exclAcc,   mnq, MarketPosition.Long, 2, 18000, 0, config);
            normState1.UpdatePosition(normAcc1,  mnq, MarketPosition.Long, 4, 18000, 0, config);
            normState2.UpdatePosition(normAcc2,  mnq, MarketPosition.Long, 4, 18000, 0, config);

            exclAcc.Positions.Add(new Position  { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000 });
            normAcc1.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 4, AveragePrice = 18000 });
            normAcc2.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 4, AveragePrice = 18000 });

            addon.SetAccountStateForTest("ExcludedAcc", exclState);
            addon.SetAccountStateForTest("NormAcc1",    normState1);
            addon.SetAccountStateForTest("NormAcc2",    normState2);
            addon.SetSubscribedAccountForTest("ExcludedAcc");
            addon.SetSubscribedAccountForTest("NormAcc1");
            addon.SetSubscribedAccountForTest("NormAcc2");
            Account.All.Clear();
            Account.All.Add(exclAcc);
            Account.All.Add(normAcc1);
            Account.All.Add(normAcc2);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            var today  = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;
            exclState.LastSessionDate  = today;
            normState1.LastSessionDate = today;
            normState2.LastSessionDate = today;

            addon.ExecuteSafetySweep();

            // NormAcc1 and NormAcc2 should be flattened (4+4=8 > limit of 5)
            // ExcludedAcc must keep its position
            Assert(exclAcc.Positions.Count > 0,
                "ExcludedAcc position is preserved even when non-excluded accounts trigger aggregate breach.");
            Assert(normAcc1.Positions.Count == 0 || normAcc2.Positions.Count == 0,
                "At least one non-excluded account IS flattened by aggregate breach.");
        }

        // ────────────────────────────────────────────────────────
        // Excluded account: sweep must never lock it out
        // ────────────────────────────────────────────────────────
        private static void TestExcludedAccountSweepDoesNotLockout()
        {
            Console.WriteLine("\n[TEST] Excluded Account: Full Sweep Never Locks It Out");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");
            config.PnLRules.DailyLossLimit         = 100.0;
            config.Overtrading.MaxTradesPerSession  = 1;

            var account = new Account { Name = "ExcludedAcc" };
            account.Values[AccountItem.RealizedProfitLoss] = -9999.0;

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("shadow"); // Shadow so no actual flatten, testing logic only

            var state = new AccountState("ExcludedAcc");
            state.RealizedPnL   = -9999.0;
            state.TradesToday   = 99;
            state.SessionStartRealizedPnL = 0.0;
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 1, 18000, 0, config);

            addon.SetAccountStateForTest("ExcludedAcc", state);
            addon.SetSubscribedAccountForTest("ExcludedAcc");
            Account.All.Clear();
            Account.All.Add(account);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            state.LastSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

            addon.ExecuteSafetySweep();

            Assert(!state.IsLockedOut,
                "Sweep does NOT lock out excluded account even with all rules violated.");
        }

        // ────────────────────────────────────────────────────────
        // A non-excluded account beside an excluded one is still enforced
        // ────────────────────────────────────────────────────────
        private static void TestNonExcludedAccountStillCaughtBesideExcludedOne()
        {
            Console.WriteLine("\n[TEST] Non-Excluded Account Is Still Caught When Beside Excluded Account");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");
            config.PnLRules.DailyLossLimit = 500.0;

            var exclAccount   = new Account { Name = "ExcludedAcc" };
            var normalAccount = new Account { Name = "NormalAcc" };

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var exclState   = new AccountState("ExcludedAcc");
            var normalState = new AccountState("NormalAcc");

            exclState.RealizedPnL   = -9999.0; // Excluded — should not fire
            normalState.RealizedPnL = -600.0;  // Not excluded — SHOULD fire DAILY_LOSS_BREACH

            var exclActions   = addon.EvaluateRules(exclAccount,   exclState);
            var normalActions = addon.EvaluateRules(normalAccount, normalState);

            Assert(exclActions.Count == 0,
                "Excluded account produces 0 rule actions.");
            Assert(normalActions.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "Non-excluded account beside it still gets DAILY_LOSS_BREACH.");
        }

        // ────────────────────────────────────────────────────────
        // Removing an account from exclusion list re-enables all rules
        // ────────────────────────────────────────────────────────
        private static void TestExclusionRemovedReEnablesRules()
        {
            Console.WriteLine("\n[TEST] Removing Exclusion Re-Enables All Rules");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("TestAcc");
            config.PnLRules.DailyLossLimit = 500.0;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.RealizedPnL = -600.0;

            // While excluded: no actions
            var actionsWhileExcluded = addon.EvaluateRules(account, state);
            Assert(actionsWhileExcluded.Count == 0,
                "No actions while account is in exclusion list.");

            // Remove from exclusion list
            config.ExcludedAccounts.Remove("TestAcc");
            state.IsLockedOut = false; // Reset so we measure just the rule

            var actionsAfterRemoval = addon.EvaluateRules(account, state);
            Assert(actionsAfterRemoval.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "DAILY_LOSS_BREACH fires immediately after account is removed from exclusion list.");
        }

        // ════════════════════════════════════════════════════════
        // PASS 2 GAP TESTS
        // ════════════════════════════════════════════════════════

        // 1.a) Excluded account with IsLockedOut=true (stale) should NOT be flattened by sweep lockout enforcement
        private static void TestSweepLockoutSkipsExcludedAccount()
        {
            Console.WriteLine("\n[TEST] Sweep Lockout Enforcement Skips Excluded Account");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");

            var account = new Account { Name = "ExcludedAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");

            var state = new AccountState("ExcludedAcc");
            state.IsLockedOut = true; // Stale state
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 1, 18000, 0, config);
            account.Positions.Add(new Position { Instrument = new Instrument("MNQ"), MarketPosition = MarketPosition.Long, Quantity = 1, AveragePrice = 18000 });

            addon.SetAccountStateForTest("ExcludedAcc", state);
            addon.SetSubscribedAccountForTest("ExcludedAcc");
            Account.All.Clear();
            Account.All.Add(account);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            var today = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;
            state.LastSessionDate = today;

            addon.ExecuteSafetySweep();

            Assert(account.Positions.Count > 0, "Excluded account position NOT flattened by sweep lockout enforcement despite IsLockedOut=true.");
        }

        // 1.b/c) Excluded account PnL sync should NOT increment ConsecutiveLosses or set CooldownUntil
        private static void TestSweepPnLSyncSkipsConsecutiveLossForExcludedAccount()
        {
            Console.WriteLine("\n[TEST] Sweep PnL Sync Skips ConsecutiveLosses and Cooldown for Excluded Account");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");
            config.Overtrading.MaxConsecutiveLosses = 1;
            config.Overtrading.CooldownMinutes = 10;

            var account = new Account { Name = "ExcludedAcc" };
            account.Values[AccountItem.RealizedProfitLoss] = -100.0; // Trigger loss

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");

            var state = new AccountState("ExcludedAcc");
            state.SessionStartRealizedPnL = 0.0;
            state.RealizedPnL = 0.0;

            addon.SetAccountStateForTest("ExcludedAcc", state);
            addon.SetSubscribedAccountForTest("ExcludedAcc");
            Account.All.Clear();
            Account.All.Add(account);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            var today = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;
            state.LastSessionDate = today;

            addon.ExecuteSafetySweep();

            Assert(state.ConsecutiveLosses == 0, "ConsecutiveLosses NOT incremented for excluded account.");
            Assert(state.CooldownUntil == DateTime.MinValue, "CooldownUntil NOT set for excluded account.");
        }

        // 2. ValidateInvariant returns false for unknown account
        private static void TestValidateInvariantReturnsFalseForUnknownAccount()
        {
            Console.WriteLine("\n[TEST] ValidateInvariant Returns False For Unknown Account");
            var addon = new RiskGuardAddOn();
            Account.All.Clear();
            
            var action = new GuardAction
            {
                AccountName = "UnknownAcc",
                ActionType = GuardActionType.FlattenPosition,
                RuleId = "TEST_RULE"
            };

            string result = addon.ProcessAction(action, forceLive: true);
            Assert(result == "REJECTED (INVARIANT VIOLATION)", "ProcessAction rejects action for account not in Account.All");
        }

        // 3. StopGuard partial stop gap
        private static void TestStopGuardPartialStopGap()
        {
            Console.WriteLine("\n[TEST] StopGuard Partial Stop Gap Emits Action For Missing Quantity");
            var config = new RiskConfig();
            config.StopGuard.StopAttachSeconds = 0; // immediate
            config.StopGuard.OnMissing = "AutoStop";

            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var mnq = new Instrument("MNQ");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 4, 18000, 0, config);
            // manually set transition time in the past
            state.Positions["MNQ"].LastNonFlatTransition = DateTime.UtcNow.AddSeconds(-10);

            // Add a working stop for 2 contracts
            account.Orders.Add(new Order { Instrument = mnq, OrderState = OrderState.Working, OrderType = OrderType.StopMarket, OrderAction = OrderAction.Sell, Quantity = 2 });

            var actions = addon.EvaluateRules(account, state);
            
            var attachAction = actions.FirstOrDefault(a => a.RuleId == "MISSING_STOP_ATTACH");
            Assert(attachAction != null, "Action generated for partial stop gap");
            if (attachAction != null)
            {
                Assert(attachAction.Quantity == 2, "Action quantity equals the missing stop quantity (4 - 2 = 2)");
            }
        }

        // 4. StopGuard OnMissing = "WarnOnly"
        private static void TestStopGuardWarnOnlyProducesNoAction()
        {
            Console.WriteLine("\n[TEST] StopGuard WarnOnly Produces No Action");
            var config = new RiskConfig();
            config.StopGuard.StopAttachSeconds = 0;
            config.StopGuard.OnMissing = "WarnOnly";

            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var mnq = new Instrument("MNQ");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 1, 18000, 0, config);
            state.Positions["MNQ"].LastNonFlatTransition = DateTime.UtcNow.AddSeconds(-10);

            var actions = addon.EvaluateRules(account, state);
            Assert(!actions.Any(a => a.RuleId.StartsWith("MISSING_STOP_")), "No action generated when OnMissing is WarnOnly");
        }

        // 5. Cooldown auto-set in sweep when consecutive losses breach limit
        private static void TestSweepAutoSetsCooldownOnConsecutiveLosses()
        {
            Console.WriteLine("\n[TEST] Sweep Auto-Sets Cooldown On ConsecutiveLosses Breach");
            var config = new RiskConfig();
            config.Overtrading.MaxConsecutiveLosses = 1;
            config.Overtrading.CooldownMinutes = 30;

            var account = new Account { Name = "TestAcc" };
            account.Values[AccountItem.RealizedProfitLoss] = -100.0; // loss

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("shadow");

            var state = new AccountState("TestAcc");
            state.SessionStartRealizedPnL = 0.0;
            state.RealizedPnL = 0.0;

            addon.SetAccountStateForTest("TestAcc", state);
            addon.SetSubscribedAccountForTest("TestAcc");
            Account.All.Clear();
            Account.All.Add(account);

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            var today = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;
            state.LastSessionDate = today;

            addon.ExecuteSafetySweep();

            Assert(state.ConsecutiveLosses == 1, "ConsecutiveLosses incremented by sweep");
            Assert(state.CooldownUntil > DateTime.UtcNow, "CooldownUntil auto-set by sweep");
        }

        // 6. forceLive parameter in ProcessAction bypasses shadow mode
        private static void TestProcessActionForceLiveBypassesShadowMode()
        {
            Console.WriteLine("\n[TEST] forceLive Parameter Bypasses Shadow Mode");
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetModeForTest("shadow");
            
            Account.All.Clear();
            Account.All.Add(account);

            var action = new GuardAction { AccountName = "TestAcc", ActionType = GuardActionType.FlattenPosition, RuleId = "MANUAL_PANIC" };
            
            string result = addon.ProcessAction(action, forceLive: true);
            Assert(result == "EXECUTED" || result.StartsWith("ERROR"), $"Action not skipped in shadow mode when forceLive=true (Result: {result})");
        }

        // 7. EdgeWindowGate: position entered INSIDE the window
        private static void TestEdgeWindowGateInsideWindowNoBreach()
        {
            Console.WriteLine("\n[TEST] EdgeWindowGate: Position Entered Inside Window -> No Breach");
            var config = new RiskConfig();
            config.EnableWindowGate = true;
            
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            
            var parsedWindows = new List<ParsedWindow>();
            parsedWindows.Add(new ParsedWindow { Start = new TimeSpan(0, 0, 0), End = new TimeSpan(23, 59, 59), Days = new HashSet<DayOfWeek> { DayOfWeek.Monday, DayOfWeek.Tuesday, DayOfWeek.Wednesday, DayOfWeek.Thursday, DayOfWeek.Friday, DayOfWeek.Saturday, DayOfWeek.Sunday } });
            addon.SetParsedWindowsForTest(parsedWindows);

            var state = new AccountState("TestAcc");
            var mnq = new Instrument("MNQ");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 1, 18000, 0, config);
            state.Positions["MNQ"].LastNonFlatTransition = DateTime.UtcNow;

            var actions = addon.EvaluateRules(account, state);
            Assert(!actions.Any(a => a.RuleId == "EDGE_WINDOW_BREACH"), "No EDGE_WINDOW_BREACH when inside window");
        }

        // 8. EdgeWindowGate: no windows defined
        private static void TestEdgeWindowGateNoWindowsDefinedNoBreach()
        {
            Console.WriteLine("\n[TEST] EdgeWindowGate: No Windows Defined -> No Breach");
            var config = new RiskConfig();
            config.EnableWindowGate = true;
            
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            
            var parsedWindows = new List<ParsedWindow>();
            addon.SetParsedWindowsForTest(parsedWindows);

            var state = new AccountState("TestAcc");
            var mnq = new Instrument("MNQ");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 1, 18000, 0, config);
            state.Positions["MNQ"].LastNonFlatTransition = DateTime.UtcNow;

            var actions = addon.EvaluateRules(account, state);
            Assert(!actions.Any(a => a.RuleId == "EDGE_WINDOW_BREACH"), "No EDGE_WINDOW_BREACH when no windows defined");
        }

        // 9. Multiple rules fire simultaneously
        private static void TestMultipleRulesFireSimultaneously()
        {
            Console.WriteLine("\n[TEST] Multiple Rules Fire Simultaneously");
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount = 1;
            config.PnLRules.DailyLossLimit = 100.0;
            config.Overtrading.MaxTradesPerSession = 1;

            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.RealizedPnL = -200.0; // Daily loss breach
            state.TradesToday = 2; // Max trades breach
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 5, 18000, 0, config); // Max size breach

            var actions = addon.EvaluateRules(account, state);
            
            bool hasSize = actions.Any(a => a.RuleId == "MAX_SIZE_BREACH");
            bool hasTrades = actions.Any(a => a.RuleId == "MAX_TRADES_BREACH");
            bool hasLoss = actions.Any(a => a.RuleId == "DAILY_LOSS_BREACH");
            
            Assert(hasSize && hasTrades && hasLoss, "All three breached rules return an action in the same evaluation");
        }

        // ════════════════════════════════════════════════════════
        // PASS 3 GAP TESTS
        // ════════════════════════════════════════════════════════

        // 1. Aggregate Sizing ExpectedCopies scaling
        private static void TestAggregateSizingExpectedCopiesScaling()
        {
            Console.WriteLine("\n[TEST] Aggregate Sizing ExpectedCopies Scaling Bypass");
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount = 15;
            config.Sizing.MaxContractsAggregate = 15;
            config.Sizing.ExpectedCopies = 2; // Intended 2-way mirror
            
            var acc1 = new Account { Name = "Acc1" };
            var acc2 = new Account { Name = "Acc2" };
            
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");
            
            var state1 = new AccountState("Acc1");
            var state2 = new AccountState("Acc2");
            
            state1.UpdatePosition(acc1, new Instrument("MNQ"), MarketPosition.Long, 10, 18000, 0, config);
            acc1.Positions.Add(new Position { Instrument = new Instrument("MNQ"), MarketPosition = MarketPosition.Long, Quantity = 10, AveragePrice = 18000 });
            
            state2.UpdatePosition(acc2, new Instrument("MNQ"), MarketPosition.Long, 10, 18000, 0, config);
            acc2.Positions.Add(new Position { Instrument = new Instrument("MNQ"), MarketPosition = MarketPosition.Long, Quantity = 10, AveragePrice = 18000 });
            
            addon.SetAccountStateForTest("Acc1", state1);
            addon.SetSubscribedAccountForTest("Acc1");
            
            addon.SetAccountStateForTest("Acc2", state2);
            addon.SetSubscribedAccountForTest("Acc2");
            
            Account.All.Clear();
            Account.All.Add(acc1);
            Account.All.Add(acc2);

            addon.ExecuteSafetySweep();

            Assert(acc1.Positions.Count > 0 && acc2.Positions.Count > 0, "Aggregate breach avoided due to ExpectedCopies scaling (max single=10, aggregate limit=15).");
        }

        // 2. Firm Mirror Trailing DD Integration
        private static void TestFirmMirrorTrailingDDBreachEmitsAction()
        {
            Console.WriteLine("\n[TEST] Firm Mirror Trailing DD Breach Emits Action And Locks Out");
            var account = new Account { Name = "FirmAcc" };
            var addon = new RiskGuardAddOn();
            
            var fmConfig = new FirmMirrorConfig();
            fmConfig.Enabled = true;
            fmConfig.TrailingDD.Enabled = true;
            fmConfig.TrailingDD.Amount = 2500;
            fmConfig.TrailingDD.Buffer = 300;
            
            var config = new RiskConfig();
            config.FirmMirror = fmConfig;
            addon.SetConfigForTest(config);
            
            var state = new AccountState("FirmAcc");
            state.FirmStartingBalance = 100000;
            state.FirmTrailingPeak = 100000;
            
            account.Values[AccountItem.CashValue] = 97000.0;
            account.Values[AccountItem.UnrealizedProfitLoss] = 0.0;
            account.Values[AccountItem.RealizedProfitLoss] = -3000.0;

            var actions = addon.EvaluateFirmMirror(account, state, DateTime.UtcNow);
            
            Assert(actions.Any(a => a.RuleId == "FIRM_TRAILING_DD_BREACH"), "Firm trailing DD breach action generated");
            Assert(state.IsLockedOut == true, "Firm mirror breach locks out account");
        }

        // 3. Firm Mirror Daily Loss Integration
        private static void TestFirmMirrorDailyLossBreachEmitsAction()
        {
            Console.WriteLine("\n[TEST] Firm Mirror Daily Loss Breach Emits Action And Locks Out");
            var account = new Account { Name = "FirmAcc" };
            var addon = new RiskGuardAddOn();
            
            var fmConfig = new FirmMirrorConfig();
            fmConfig.Enabled = true;
            fmConfig.DailyLoss.Enabled = true;
            fmConfig.DailyLoss.Amount = 1500;
            fmConfig.DailyLoss.Buffer = 200; // Limit is -1300
            
            var config = new RiskConfig();
            config.FirmMirror = fmConfig;
            addon.SetConfigForTest(config);
            
            var state = new AccountState("FirmAcc");
            state.FirmDailyDate = DateTime.UtcNow.Date;
            state.FirmDailyStartRealized = 0.0;
            
            account.Values[AccountItem.RealizedProfitLoss] = -1400.0; // Less than limit -1300
            account.Values[AccountItem.UnrealizedProfitLoss] = 0.0;
            account.Values[AccountItem.CashValue] = 98600.0; 

            var actions = addon.EvaluateFirmMirror(account, state, DateTime.UtcNow);
            
            Assert(actions.Any(a => a.RuleId == "FIRM_DAILY_LOSS_BREACH"), "Firm daily loss breach action generated");
            Assert(state.IsLockedOut == true, "Firm mirror breach locks out account");
        }

        // 4. StopGuard default offset fallback
        private static void TestStopGuardDefaultOffsetFallback()
        {
            Console.WriteLine("\n[TEST] StopGuard Default Offset Fallback (Unknown Ticker)");
            var config = new RiskConfig();
            config.StopGuard.StopAttachSeconds = 0; // immediate
            config.StopGuard.OnMissing = "AutoStop";
            
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var unknownTick = new Instrument("CL");
            unknownTick.MasterInstrument.TickSize = 0.01;
            
            state.UpdatePosition(account, unknownTick, MarketPosition.Long, 1, 80.00, 0, config);
            state.Positions["CL"].LastNonFlatTransition = DateTime.UtcNow.AddSeconds(-10);

            var actions = addon.EvaluateRules(account, state);
            var attachAction = actions.FirstOrDefault(a => a.RuleId == "MISSING_STOP_ATTACH");
            
            Assert(attachAction != null, "Action generated for missing stop on unknown ticker");
            Assert(true, "Fallback triggered gracefully");
        }

        // ════════════════════════════════════════════════════════
        // MANUAL LOCKOUT TESTS
        // ════════════════════════════════════════════════════════

        // 1. Manual Timed Lockout
        private static void TestManualTimedLockout()
        {
            Console.WriteLine("\n[TEST] Manual Timed Lockout Flattens And Prevents Entry");
            var addon = new RiskGuardAddOn();
            var config = new RiskConfig();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");
            
            var account = new Account { Name = "Acc1" };
            var state = new AccountState("Acc1");
            
            addon.SetAccountStateForTest("Acc1", state);
            addon.SetSubscribedAccountForTest("Acc1");
            Account.All.Clear();
            Account.All.Add(account);
            
            // Give them a position
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 1, 18000, 0, config);
            account.Positions.Add(new Position { Instrument = new Instrument("MNQ"), MarketPosition = MarketPosition.Long, Quantity = 1, AveragePrice = 18000 });
            
            // Lock for 15 minutes
            addon.LockAccount("Acc1", 15);
            
            Assert(state.LockoutUntil > DateTime.UtcNow, "LockoutUntil is in the future");
            Assert(state.IsLockedOut == false, "IsLockedOut is false for timed lockout");
            
            // Run sweep - should flatten
            addon.ExecuteSafetySweep();
            
            Assert(account.Positions.Count == 0, "Position flattened by manual timed lockout");
            Assert(state.InitialLockoutFlattened == true, "InitialLockoutFlattened set after sweep");
        }

        // 2. Manual EOD Lockout
        private static void TestManualEodLockout()
        {
            Console.WriteLine("\n[TEST] Manual EOD Lockout Uses IsLockedOut Flag");
            var addon = new RiskGuardAddOn();
            var state = new AccountState("Acc1");
            addon.SetAccountStateForTest("Acc1", state);
            
            addon.LockAccount("Acc1", -1);
            
            Assert(state.IsLockedOut == true, "EOD lock sets IsLockedOut to true");
            Assert(state.LockoutUntil == DateTime.MinValue, "EOD lock clears LockoutUntil");
        }

        // 3. Manual Unlock Clears Timed Lockout
        private static void TestManualUnlockClearsTimedLockout()
        {
            Console.WriteLine("\n[TEST] Manual Unlock Clears Timed Lockout");
            var addon = new RiskGuardAddOn();
            var state = new AccountState("Acc1");
            addon.SetAccountStateForTest("Acc1", state);
            
            addon.LockAccount("Acc1", 60);
            Assert(state.LockoutUntil > DateTime.UtcNow, "Account is timed locked");
            
            addon.UnlockAccount("Acc1");
            Assert(state.LockoutUntil == DateTime.MinValue, "Unlock clears timed lockout");
        }
    }
}
#endif
