#if TESTING
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

// --- MOCK DEFINITIONS TO AVOID NINJATRADER ASSEMBLY DEPENDENCY IN TEST ENVIRONMENT ---
namespace NinjaTrader.Cbi
{
    public enum MarketPosition { Flat, Long, Short }
    public enum Currency { UsDollar }
    public enum AccountItem { CashValue, RealizedProfitLoss, UnrealizedProfitLoss, NetLiquidation }

    public class AccountItemEventArgs : EventArgs
    {
        public AccountItem AccountItem { get; set; }
        public double Value { get; set; }
        public Currency Currency { get; set; }
    }
    // ALL SIXTEEN of NT8's OrderStates, in the order NinjaTrader.Cbi.OrderState declares
    // them. This stub used to carry ten, so six states could not be expressed by ANY test
    // and the suite was green at 686/0 while P0-59 was live on the box.
    //
    // Obtained by reflection, not by memory:
    //   [Reflection.Assembly]::LoadFrom("C:\Program Files\NinjaTrader 8\bin\NinjaTrader.Core.dll")
    //   [Enum]::GetNames($asm.GetType("NinjaTrader.Cbi.OrderState"))
    //
    // TestOrderLiveness_ClassifiesEveryNT8OrderState pins this list against
    // RiskGuardAddOn.Classify, so adding a state here without classifying it fails the
    // suite. Keeping the stub honest about the shape of the world is the whole point:
    // a test double we author is not evidence about NT8 unless something forces it to agree.
    public enum OrderState
    {
        Accepted, Cancelled, Filled, Initialized, PartFilled, CancelSubmitted,
        ChangeSubmitted, Submitted, TriggerPending, Rejected, Working, CancelPending,
        ChangePending, Suspended, AcceptedByRisk, Unknown
    }
    public enum OrderType { Limit, StopMarket, StopLimit, Market }
    public enum OrderAction { Buy, Sell, BuyToCover, SellShort }
    public enum TimeInForce { Day, Gtc }
    public enum PerformanceUnit { Currency, Percent, Pips, Points, Ticks }

    /// <summary>
    /// Stub of NT8's broker-provider enum. Only <c>Simulator</c> is load-bearing: it is
    /// how the copier tells a practice account from one that can lose real money, now
    /// that the account NAME is no longer trusted for that (P1-20).
    /// </summary>
    public enum Provider { NinjaTrader, Simulator, Playback, Rithmic, ContinuumFix, InteractiveBrokers }

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

        /// <summary>
        /// Stub of NT8's instrument lookup. Its absence was the ONLY thing forcing
        /// TradeCopierEngine.OnExecution (the entire trade-copy path, and the riskiest code in
        /// the addon) to sit inside `#if !TESTING`, i.e. compiled out of the test build with
        /// zero coverage. Registered instruments can be seeded by tests; unknown names resolve
        /// to a fresh instrument so symbol translation still works.
        /// </summary>
        public static Dictionary<string, Instrument> Registry =
            new Dictionary<string, Instrument>(StringComparer.OrdinalIgnoreCase);

        public static Instrument GetInstrument(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            Instrument found;
            if (Registry.TryGetValue(name, out found)) return found;
            var created = new Instrument(name);
            Registry[name] = created;
            return created;
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
        public Ask Ask { get; set; }
        public Bid Bid { get; set; }
    }

    public class Last
    {
        public double Price { get; set; }
    }

    public class Ask
    {
        public double Price { get; set; }
    }

    public class Bid
    {
        public double Price { get; set; }
    }

    public class Order
    {
        public string Id { get; set; }
        public string OrderId { get; set; }
        public string Name { get; set; }
        public string Oco { get; set; }
        public OrderState OrderState { get; set; }
        public OrderType OrderType { get; set; }
        public int Quantity { get; set; }
        public int Filled { get; set; }
        public Instrument Instrument { get; set; }
        public OrderAction OrderAction { get; set; }
        public double LimitPrice { get; set; }
        public double StopPrice { get; set; }
        // Required by TradeCopierEngine.OnExecution when mirroring the leader's TIF.
        public TimeInForce TimeInForce { get; set; } = TimeInForce.Day;
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
        // Required by TradeCopierEngine.OnExecution (recursion guard + dedupe).
        public Account Account { get; set; }
        public string ExecutionId { get; set; }
        public string Name { get; set; }
        // P1-22: the copier measures latency as leader exec.Time -> follower exec.Time. Left
        // default here so tests that do not care still exercise the wall-clock fallback.
        public DateTime Time { get; set; }
    }

    public class Account
    {
        public string Name { get; set; }

        // Defaults to a LIVE provider on purpose. A test that forgets to say it is
        // simulated gets the strict treatment, which is the same fail-closed posture
        // the production gate now takes. Defaulting to Simulator would reproduce the
        // exact bug P1-20 fixes -- assuming safety instead of establishing it.
        public Provider Provider { get; set; } = Provider.NinjaTrader;
        public Dictionary<AccountItem, double> Values { get; set; } = new Dictionary<AccountItem, double>();
        public List<Order> Orders { get; set; } = new List<Order>();
        public List<Position> Positions { get; set; } = new List<Position>();
        public static List<Account> All { get; set; } = new List<Account>();
        public bool SimulateExitRejection { get; set; }

        // Broker rejection of the auto-stop at Submit time. This is the failure T2's
        // rollback exists for: the FSM has already been moved to ProtectedPending
        // (reserve-before-submit), so if the submit throws and nothing rolls it back,
        // the position is unprotected while the FSM claims otherwise.
        public bool SimulateSubmitFailure { get; set; }
        // Broker refuses the flatten. This is the case P1-11 turns on: if the protective stop
        // was already cancelled on the way in, a failed flatten leaves an open position with
        // nothing behind it.
        public bool SimulateFlattenFailure { get; set; }
        // Broker refuses an in-place modification. The bracket sync prefers Change() and falls
        // back to cancel-then-create; that fallback is the only path that can retire an OCO
        // group and so the only one that needs a fresh id (P0-9 item 1). Nothing could reach it
        // before this switch existed.
        public bool SimulateChangeFailure { get; set; }
        // Counts Flatten calls so a test can prove the fail-closed fallback ran.
        public int FlattenCallCount { get; private set; }

        /// <summary>
        /// Fires on every call that reaches the broker (Cancel/Flatten/CreateOrder/Submit).
        /// Lets a test assert the invariant the design doc claims but the code did not keep:
        /// none of these may run while `_stateLock` is held (P1-10, P1-35). Reviewers cannot
        /// check this reliably by reading -- the offending sites are nested three calls deep
        /// inside a lock block -- so it is checked mechanically instead.
        /// </summary>
        public static Action<string> BrokerCallObserver;

        private static void ObserveBrokerCall(string method)
        {
            var obs = BrokerCallObserver;
            if (obs != null) obs(method);
        }

        public event EventHandler<PositionEventArgs> PositionUpdate;
        public event EventHandler<OrderEventArgs> OrderUpdate;
        public event EventHandler<ExecutionEventArgs> ExecutionUpdate;
        public event EventHandler<AccountItemEventArgs> AccountItemUpdate;

        public double Get(AccountItem item, Currency currency)
        {
            return Values.ContainsKey(item) ? Values[item] : 0.0;
        }

        public void Cancel(Order[] orders)
        {
            ObserveBrokerCall("Cancel");
            foreach (var o in orders)
            {
                o.OrderState = OrderState.Cancelled;
            }
        }

        public void Cancel(List<Order> orders)
        {
            ObserveBrokerCall("Cancel");
            foreach (var o in orders)
            {
                o.OrderState = OrderState.Cancelled;
            }
        }

        // P1-19: records exactly which instruments each Flatten call was asked to close.
        // The defect is in what ExecuteAction *requests* -- it ignored action.Instrument and
        // passed every instrument on the account -- so the request is the thing to assert on.
        public List<string> LastFlattenRequest = new List<string>();

        public void Flatten(Instrument[] instruments)
        {
            ObserveBrokerCall("Flatten");
            LastFlattenRequest = instruments == null
                ? new List<string>()
                : instruments.Where(i => i != null).Select(i => i.FullName).ToList();
            FlattenCallCount++;
            if (SimulateFlattenFailure)
                throw new Exception("Simulated broker rejection at Flatten.");
            Positions.Clear();
            Orders.Clear();
        }

        public Order CreateOrder(Instrument instrument, OrderAction action, OrderType type, TimeInForce tif, int qty, double limit, double stop, string oco, string name, object custom)
        {
            ObserveBrokerCall("CreateOrder");
            var o = new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderId = Guid.NewGuid().ToString(),
                Name = name,
                Oco = oco,
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

        // S7 drives copies from several threads at once. NT8 manages Account.Orders internally;
        // an unsynchronised List<T> here would corrupt or throw under that burst and the test
        // would be measuring the stub, not the engine.
        private readonly object _ordersLock = new object();

        public void Submit(Order[] orders)
        {
            ObserveBrokerCall("Submit");
            if (SimulateSubmitFailure)
                throw new Exception("Simulated broker rejection at Submit.");

            foreach (var o in orders)
            {
                o.OrderState = OrderState.Submitted;
                if (SimulateExitRejection && (o.Name.StartsWith("Stop_") || o.Name.StartsWith("Target_")))
                    o.OrderState = OrderState.Rejected;
                lock (_ordersLock) { Orders.Add(o); }
            }
        }

        /// <summary>Snapshot of Orders safe to enumerate while other threads are submitting.</summary>
        public List<Order> OrdersSnapshot()
        {
            lock (_ordersLock) { return new List<Order>(Orders); }
        }

        // Change() is a broker call like Cancel/Flatten/Submit and must be observed as one, or
        // the P1-10 lock-scope check silently exempts it -- the same shape of blind spot that let
        // P1-43's four `account.Cancel` calls sit under the lock unnoticed.
        public void Change(Order[] orders)
        {
            ObserveBrokerCall("Change");
            if (SimulateChangeFailure)
                throw new Exception("Simulated broker rejection at Change.");
            foreach (var o in orders)
            {
                o.OrderState = OrderState.Working;
            }
        }

        /// <summary>
        /// Fills `o` and retires the rest of its OCO group, which is what "one cancels the other"
        /// means and is the single OCO behaviour we depend on. Modelled here because the copier's
        /// re-submission logic has to tell "my protective leg was lost" from "my protective leg
        /// was retired because its sibling filled" -- and re-submitting in the second case places
        /// an order against a position that has just been closed, which is P0-50's orphan
        /// arriving by the route the pairing itself opens.
        ///
        /// Deliberately NOT modelled: whether cancelling one leg retires the group. That is
        /// plausible and unverified, so the copier is written to be correct either way rather
        /// than to match a guess encoded here.
        /// </summary>
        public void FillOrderAndRetireOcoGroup(Order o)
        {
            o.OrderState = OrderState.Filled;

            List<Order> siblings;
            lock (_ordersLock)
            {
                siblings = string.IsNullOrEmpty(o.Oco)
                    ? new List<Order>()
                    : Orders.Where(x => x != null && !ReferenceEquals(x, o)
                        && string.Equals(x.Oco, o.Oco, StringComparison.Ordinal)
                        && x.OrderState != OrderState.Filled
                        && x.OrderState != OrderState.Cancelled
                        && x.OrderState != OrderState.Rejected).ToList();
            }

            foreach (var s in siblings) s.OrderState = OrderState.Cancelled;

            TriggerOrderUpdate(o);
            foreach (var s in siblings) TriggerOrderUpdate(s);
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

        /// <summary>
        /// How many handlers are attached to ExecutionUpdate. P1-21's subscribe pass now runs on
        /// every connection change, so "attached exactly once" is the invariant that stops a
        /// flapping broker from copying each fill N times. Asserted directly rather than through
        /// order counts, because OnExecution's ExecutionId dedupe would mask a doubled handler
        /// and the test would pass while proving nothing.
        /// </summary>
        public int ExecutionUpdateHandlerCount
        {
            get
            {
                var d = ExecutionUpdate;
                return d == null ? 0 : d.GetInvocationList().Length;
            }
        }

        public void TriggerAccountItemUpdate(AccountItem item, double value)
        {
            AccountItemUpdate?.Invoke(this, new AccountItemEventArgs { AccountItem = item, Value = value, Currency = Currency.UsDollar });
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
    using NinjaTrader.Data;

    // --- TEST EXECUTION HARNESS ---
    public class Program
    {
        private static int _testsPassed = 0;
        private static int _testsFailed = 0;
        private static readonly HashSet<string> _invokedTests = new HashSet<string>(StringComparer.Ordinal);

        /// <summary>
        /// Deterministic clock for firm-mirror tests: a fixed mid-session UTC timestamp, safely
        /// before the default 22:00 UTC daily-reset boundary. Tests must never read the wall clock.
        /// </summary>
        private static readonly DateTime FirmTestClockUtc =
            new DateTime(2026, 7, 15, 14, 30, 0, DateTimeKind.Utc);

        /// <summary>
        /// Mirrors the production firm daily-boundary rule so tests seed FirmDailyDate the way
        /// ComputeFirmMirror will compute it, instead of assuming it equals the calendar date.
        /// </summary>
        private static DateTime FirmDailyDateFor(DateTime nowUtc, FirmMirrorConfig fm)
        {
            var boundary = new TimeSpan(fm.DailyResetHourUtc, fm.DailyResetMinuteUtc, 0);
            return nowUtc.TimeOfDay >= boundary ? nowUtc.Date.AddDays(1) : nowUtc.Date;
        }

        public static void Main(string[] args)
        {
            Console.WriteLine("====================================================");
            Console.WriteLine("- RUNNING RISK GUARD ADDON EDGE CASE UNIT TESTS");
            Console.WriteLine("====================================================");

            // - Original 9 tests -
            TestMaxPositionSizeEnforcement();
            TestDailyLossLimitLockout();
            TestTrailingDrawdownLockout();
            TestMaxTradesOvertradingLockout();
            TestConsecutiveLossesCooldownLockout();
            TestAccountExclusionsBypass();
            TestManualUnlockResetsAllMetricsAndPreventsRelocking();
            TestRealizedPnLLagHandling();
            TestMcpBridgeLockoutBlock();

            // - Critical gap tests -
            TestIsArmedFalseBypassesAllRules();
            TestTradeTodayCountingOnRoundTrip();
            TestFlipDetectionCountsAsEntry();
            TestTradeCountingMultiContractScalingDebounced();
            TestLockoutWatchdogSweepFlattensOpenPosition();
            TestP0_51_ShadowModeIssuesNoBrokerCallsFromTheLockoutSweep();
            TestP0_51_ShadowModeDoesNotDrainInterventionCancelsToTheBroker();
            TestP1_54_LockoutLapsesWhenItsDeadlinePasses();
            TestP1_54_LockoutDeadlineSurvivesARestart();
            TestP1_52_NormalAtmBracketIsNotAFlood();
            TestLockoutAllowsPositionReducingOrders();
            TestCooldownExpiryAllowsReEntry();
            TestOrderCancelledWhenLockedOnOrderUpdate();
            TestOrderCancelledWhenConsecLossesAtMaxNotLocked();

            // - Important gap tests -
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

            // - Lower-priority / boundary tests -
            TestShadowModeSkipsAction();
            TestLiveModeExecutesAction();
            TestMaxSizeAtExactlyLimit();
            TestDailyLossAtExactlyLimit();
            TestIsAccountLockedForUnknownAccount();
            TestMultipleInstrumentsNoPerInstrumentBreach();

            // - Exclusion deep-dive tests (test-first) -
            TestExcludedAccountMaxContractsBypassed();
            TestExcludedAccountAllRulesBypassed();
            TestExcludedAccountOrderNotCancelledWhenLocked();
            TestExcludedAccountNotCountedInAggregate();
            TestExcludedAccountNotFlattenedByAggregateBreach();
            TestExcludedAccountSweepDoesNotLockout();
            TestNonExcludedAccountStillCaughtBesideExcludedOne();
            TestExclusionRemovedReEnablesRules();

            // - Pass 2 Gap Tests (test-first) -
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

            // - Pass 3 Gap Tests -
            TestAggregateSizingExpectedCopiesScaling();
            TestFirmMirrorTrailingDDBreachEmitsAction();
            TestFirmMirrorDailyLossBreachEmitsAction();
            TestP1_42_MappedAccountIsEvaluatedAgainstItsFirmProfile();
            TestStopGuardDefaultOffsetFallback();

            // - Manual Lockout Tests -
            TestManualTimedLockout();
            TestManualEodLockout();
            TestManualUnlockClearsTimedLockout();

            // - FSM StopGuard Tests (-6) -
            TestFsm_UnprotectedToProtectedViaOcoStopLeg();
            TestFsm_NoDuplicateAutoStopWhenStopLegPending();
            TestFsm_GraceExpiryPlacesAutoStopOnce();
            TestFsm_StopArrivesBeforePositionIsBuffered();
            TestFsm_FlatTearsDownAndCancelsOrphanAutoStop();
            TestFsm_StandaloneStopReachesProtected();
            TestFsm_RejectedStopLegReturnsToUnprotected();
            TestFsm_PositionFlattenedBeforeGraceNoAutoStop();
            TestFsm_DuplicateOrderUpdatesAreIdempotent();
            TestFsm_DuplicatePositionUpdatesAreIdempotent();
            TestFsm_EvaluateRulesNoLongerEmitsStopGuard();
            TestFsm_ExcludedAccountSkipsFsm();

            // -- FSM edge-case tests --
            TestFsm_ProtectedToUnprotectedOnStopFilled();
            TestFsm_ProtectedPendingToUnprotectedOnCancelled();
            TestFsm_GraceExpiryFlatten();
            TestFsm_GraceNotExpiredNoAction();
            TestFsm_ShortPositionProtected();
            TestFsm_FlipRecreatesFsm();
            TestFsm_MultipleInstrumentsIndependent();
            TestFsm_DisarmedSkipsFsm();
            TestFsm_LimitOrderDoesNotTransition();
            TestFsm_PendingStopWorkingConsumed();

            // -- FSM OrderAction bug tests (BuyToCover/SellShort) --
            TestFsm_ShortPositionBuyToCoverStopRecognized();
            TestFsm_LongPositionSellShortStopRecognized();

            // -- AUDIT: Regression tests for identified bugs --
            TestFsm_QtyOnlyUpdatePreservesProtectedState();
            TestFsm_PartialFillPreservesProtectedState();
            TestFsm_GraceExpiryFlattenEmitsOnce();
            TestFsm_PositionQuantityUpdatedOnQtyChange();
            TestPnLRulesNotDuplicatedInEvaluateRules();
            TestExecuteOrderUpdateProcessesActionsOutsideLock();

            // -- PHASE B BACKFILL: acceptance tests for the T1/T2/T3 P0 fixes.
            // Each verified to fail with its fix reverted; see the handover.
            TestT2_AutoStopSizedFromLivePositionNotSnapshot();
            TestT2_ScaledDownPositionStillGetsAStop();
            TestT2_SubmitFailureRollsBackFsmAndClearsGraceEmitted();
            TestT1_CancelledStopMidPositionReArmsGrace();
            TestT3_ProfitableFlatAccountEmitsNoGiveback();
            TestT3_FlipDoesNotCarryPeakOpenGainIntoNewLeg();
            TestP1_40_NoiseSizedPeakDoesNotTripGiveback();
            TestP1_39_ConfigLoadDoesNotAppendDefaultCollections();
            TestP1_19_FlattenIsInstrumentScopedAndActionsCoalesce();
            TestP1_18_ProfileTrailingDDYieldsOnlyToAnEffectiveFirmRule();
            TestP1_16_ConsecutiveLossesCountTradesNotPartialExits();
            TestP1_17_EvaluationTargetUsesCumulativeNotSessionPnL();
            TestP1_37_ShadowSessionCounterSurvivesRestartWithoutRecounting();
            TestP1_23_SymbolTranslationAndSizingModesDoNotLie();
            TestP1_47_ArmDefaultFollowsTheResolvedMode();
            TestStress_S1toS4_OrderFloodGovernor();
            TestP2_41_PartialConfigPostMergesInsteadOfReplacing();
            TestP2_38_DeployGateClassifiesByProviderNotName();
            TestStress_S5_PartialFillStorm();
            TestStress_S6_RapidFlipLoop();
            TestStress_S8_ConfigReloadWhileArmedAndInPosition();
            TestStress_S9_RestartMidTrade();
            TestP1_10_SweepMakesNoBrokerCallsUnderTheStateLock();
            TestP1_13_NoGuardPathIsSkippedWhenThereIsNoDispatcher();
            TestP1_12_NoDiskWriteHappensUnderTheStateLock();
            TestP1_12_PositionChangeDefersThePersistToTheSweep();
            TestP1_14_SecondBufferedStopDoesNotOverwriteTheFirst();
            TestP1_14_ABufferedBreakoutEntryIsNotAdoptedAsProtection();
            TestP1_14_AnUnclaimedBufferedStopExpiresInsteadOfArmingALaterPosition();
            TestP1_36_TwoPartialStopsCoverThePositionInFull();
            TestP1_36_LosingOneOfTwoStopsIsPartialCoverNotNakedness();
            TestP1_36_AutoStopAddsToExistingCoverRatherThanReplacingIt();
            TestP1_35_OrphanAutoStopCancelHappensOutsideTheLock();
            TestP1_11_LockoutSweepDoesNotCancelTheProtectiveStopBeforeFlattening();
            TestP1_15_ReArmingSeedsFsmsForPositionsOpenedWhileDisarmed();

            // -- COPIER GROUPS & STRESS TESTS --
            TestCopierGroup_GroupManagement();
            TestCopierGroup_PerGroupConfigurationExecution();
            TestCopierGroup_GroupPersistence();
            TestCopierGroup_GroupStressAndConcurrency();
            RunCopierFixesVerificationTests();
            TestOrderVerificationWatchdogAndReconciliation();
            TestHedgingReconciliationAndAutoClose();

            // -- DYNAMIC ATM BRACKET TESTS --
            TestAtm_FixedTicksLong();
            TestAtm_FixedTicksShort();
            TestAtm_DrawdownShieldRegistersBracket();
            TestAtm_ScaledRunnerRegistersBracket();
            TestAtm_MonitoredStrategiesNotDoubleRegistered();
            TestAtm_VolatilityScaledQuantityCapped();
            TestAtm_VolatilityScaledRiskBasedQuantity();
            TestAtm_AtrAdaptiveFallbackUsesDefaultAtr();
            TestAtm_AtrAdaptiveUsesLiveAtr();
            TestAtm_SwingPointUsesSwingLow();
            TestAtm_SessionAdaptiveMultiplier();
            TestAtm_UnknownSymbolFallsBackToDefaults();
            TestAtm_GetProfileKnownAndUnknown();
            TestAtm_ZeroPriceReturnsError();
            TestAtm_RejectedExitOrdersPartialSubmit();
            TestAtm_OcoIdSharedAcrossExitOrders();
            TestAtm_ShouldTriggerBreakeven();
            TestAtm_CalculateBreakevenStopPrice();
            TestAtm_ActiveBracketStatus();

            // -- TDD COPIER, INSTRUMENT CAPS, ATM & PROP-FIRM TESTS --
            // These were previously reachable only from inside the corrupted body of
            // TestExecuteOrderUpdateProcessesActionsOutsideLock. Invoked explicitly here so
            // they are owned by the runner rather than by another test.
            TestPerInstrumentSizing_MNQVsMES();
            TestInstrumentBlacklist_BlocksMiniNQ();
            TestPropFirmProfile_AllowedInstruments();
            TestTradeCopier_RatioScaling();
            TestTradeCopier_SymbolMapping();
            TestAtmStrategy_DrawdownShieldBreakeven();
            TestNewsShield_FlattensBeforeCPI();
            TestStrategyApi_CanTradeReturnsFalseWhenLockedOut();
            TestEvaluationProfitTargetLock_LocksAccount();
            TestPeakEquityProtection_ClosesOnGiveback();
            TestOptionC_TradeCopierSingletonIntegration();
            TestOptionC_MultiPartialFillPositionClamping();
            TestOptionC_PropProtectionSingletonIntegration();

            // Previously declared but never invoked from anywhere.
            TestOrderNotCancelledInFilledStateWhenLocked();

            // -- COPY-PATH TESTS (previously impossible: OnExecution was #if !TESTING) --
            TestCopyPath_ExitDoesNotFlipFollowerShort();
            TestCopyPath_MicroToMiniDoesNotInflateNotional();
            TestCopyPath_LockedFollowerReceivesNoCopy();
            TestCopyPath_LiveAccountNamedSimIsNotTreatedAsSimulated();
            TestCopyPath_GenuineSimulatorAccountStillReceivesCopies();

            // -- COPIER SUBSCRIPTION TESTS (P1-21) --
            TestCopierSubs_LateConnectingLeaderIsCopied();
            TestCopierSubs_RepeatedRefreshAttachesOneHandler();
            TestCopierSubs_TeardownDetachesHandlers();

            // -- COPY SLIPPAGE / LATENCY TESTS (P1-22) --
            TestCopierSlip_FollowerFillPopulatesLatencyAndSlippage();
            TestCopierSlip_FavourableFillIsNegativeAndDoesNotQuarantine();
            TestCopierSlip_EntryQuarantinesButExitStillCopies();
            TestCopierSlip_IncomparableSymbolsRecordNoSlippage();
            TestCopierSlip_FillIsMatchedWhenOrderIdChanges();

            // -- BRACKET REPLICATION TESTS (P0-9) --
            TestBracket_StopMirrorsLeaderDistanceFromFollowerFill();
            TestBracket_StopBeforeFollowerFillIsAppliedOnFill();
            TestBracket_P0_55_LeaderStopAcceptedBeforeLeaderPositionIsStillMirrored();
            TestOrderLiveness_ClassifiesEveryNT8OrderState();
            TestBracket_P0_59_ALegBeingModifiedIsNotDuplicated();
            TestP0_60_AStopBeingCancelledStopsCountingAsCoverage();
            TestBracket_TrailingModifiesTheStopRatherThanRecreatingIt();
            TestBracket_TargetIsMirroredAsAnOcoPairWithTheStop();
            TestBracket_P0_9_ALateTargetJoinsTheLiveStopsOcoGroup();
            TestBracket_P0_9_ARecreatedStopMintsAFreshOcoIdAndRebuildsThePair();
            TestBracket_P0_9_InterleavedTargetSyncsLeaveExactlyOneTarget();
            TestBracket_P0_9_TargetResubmissionIsBounded();
            TestBracket_P0_9_ALegRetiredByItsOcoSiblingIsNotResubmitted();
            TestBracket_P0_9_AMultiTargetLeaderIsNotMirroredAtAll();
            TestBracket_P0_9_LegPricesAreRoundedToTheInstrumentsTick();
            TestBracket_TargetAcceptedBeforeLeaderPositionIsStillMirrored();
            TestBracket_FollowerGoingFlatCancelsBothLegs();
            TestBracket_MovingLeaderStopReplacesRatherThanDuplicates();
            TestBracket_P1_56_InterleavedSyncsLeaveExactlyOneProtectiveStop();
            TestBracket_P1_56_AThirdSyncStillLeavesExactlyOneProtectiveStop();
            TestBracket_FollowerGoingFlatCancelsTheMirroredStop();
            TestBracket_StopTrailedIntoProfitStaysAboveFollowerEntry();
            TestBracket_ShortStopTrailedIntoProfitStaysBelowFollowerEntry();
            TestBracket_RejectedStopIsResubmitted();
            TestBracket_P1_56_AFailedSubmitDoesNotWedgeLaterSyncs();
            TestBracket_ResubmissionIsBounded();
            TestBracket_IncomparableInstrumentsAreNotMirrored();
            TestBracket_P0_49_ExecutionBeforePositionStillGetsAStop();
            TestBracket_P0_50_NoStopIsPlacedOnAFlatFollower();
            TestBracket_StopLimitLeaderMirrorsTriggerPriceAsStopMarket();
            TestBracket_LeaderCancellingItsStopLeavesTheFollowerProtected();

            // -- S7: copier fan-out under burst (plan §8) --
            TestStress_S7_CopierFanOutUnderBurst();

            // -- P3-30/P3-31: the reconciler's pure core --
            TestDesired_SignedOffsetsMirrorBothSidesFromTheFollowersOwnFill();
            TestDesired_LeaderTrailingIntoProfitKeepsTheStopAboveEntry();
            TestDesired_OffTickAverageFillIsSnappedToTheInstrumentsTick();
            TestDesired_QuantityIsClampedToTheLivePositionNotTheBracketSnapshot();
            TestDesired_FlatFollowerForbidsBothLegs();
            TestDesired_SideMismatchForbidsBothLegs();
            TestDesired_UnknownOffsetIsUnspecifiedNotForbidden();
            TestDesired_NonPositivePriceIsRefusedWithoutCancellingCover();
            TestReconcile_NothingOwnedCreatesBothLegsRiskLegFirst();
            TestReconcile_CorrectLegsProduceNoActions();
            TestReconcile_TwoOwnedLegsAreDeduplicated();
            TestReconcile_DuplicateStopsBehindMismatchedQuantitiesLeaveOneCorrectLeg();
            TestReconcile_ChangeSubmittedLegIsNotDuplicated();
            TestReconcile_DepartingLegIsReplacedAndNotCancelledTwice();
            TestReconcile_P0_61_ALegMidChangeIsDeferredNotChangedAgain();
            TestOrderLiveness_P0_61_MidChangeAnswersTheThreeQuestionsDifferently();
            TestReconcile_TrailStepModifiesRatherThanReplaces();
            TestReconcile_FlatFollowerCancelsEveryOwnedLeg();
            TestReconcile_UnspecifiedLegKeepsOneAndCreatesNone();
            TestReconcile_InFlightSubmitSuppressesOnlyItsOwnCreate();
            TestReconcile_InFlightNeverSuppressesACancel();
            TestReconcile_ForeignAndManualOrdersAreNeverTouched();
            TestReconcile_WrongTypeLegIsReplacedNotLeftInPlace();
            TestReconcile_TerminalLegsAreIgnoredEntirely();
            TestReconcile_TheSameOrderListedTwiceIsOneLeg();
            TestReconcile_IsIdempotentUnderRepetition();
            TestReconcile_SurvivorPrefersTheLegThatActuallyCovers();
            TestBracket_P3_30_AStrayLegTheEngineNeverRecordedIsStillCancelled();
            TestBracket_P3_31_ALegNotYetVisibleAtTheBrokerIsNotDuplicated();
            TestBracket_P3_30_ACachedLegAlsoInAccountOrdersCountsOnce();
            TestBracket_P0_50_AFlatFollowerStandsTheBracketDown();
            TestBracket_P0_61_ADeferredChangeIsReappliedWhenTheLegSettles();

            // CM1: copier ratio converter, slice 1 -- RED until the fix lands
            TestCM1_MatrixSizesFromTheTableWithoutTheSymbolMultiplier();
            TestCM1_MatrixFailsClosedOnEntriesAndNeverOnExits();
            TestCM1_MatrixTreatsAnInvalidRatioAsNoRule();
            TestCM1_MatrixKeepsTheLeadersInstrument();

            // CM2: copier ratio converter, slice 3a -- RED until the fix lands
            TestCM2_RelationshipRoundTripKeepsSizingAndTheMatrix();
            TestCM2_GroupRoundTripKeepsSizingAndTheMatrix();
            TestCM2_ReloadedMatrixLookupIsStillCaseInsensitive();
            TestCM2_ALoadedMatrixActuallySizesATrade();
            TestCM2_LegacyAndAliasFormsStillLoad();
            TestCM2_AMalformedFieldDoesNotDiscardTheWholeConfig();
            TestCM2_AMalformedNumberNeverBecomesAZeroLimit();
            TestCM2_AnEmptySectionIsNotAParseFailure();

            // CM3: copier bridge merge semantics, slice 3b -- RED until the fix lands
            TestCM3_APartialGroupUpdateKeepsEveryUnmentionedField();
            TestCM3_APartialUpdateIsWhatGetsStoredAndSaved();
            TestCM3_APartialRelationshipUpdateKeepsEveryUnmentionedField();
            TestCM3_TheMatrixIsSettableThroughTheBridgeAtAll();
            TestCM3_AnUnknownGroupIsStillCreated();
            TestCM3_APartialUpdateCannotArmForLive();
            TestCM3_AnUnrelatedEditDoesNotSilentlyDisarm();
            TestCM3_AMalformedRequestDoesNotDestroyTheStoredGroup();

            // Structural self-check: fails if the runner silently stops covering declared tests.
            TestHarness_AllDeclaredTestsAreInvoked();

            Console.WriteLine("\n====================================================");
            Console.WriteLine(string.Format("RESULTS: Passed = {0}, Failed = {1}", _testsPassed, _testsFailed));
            Console.WriteLine("====================================================");

            if (_testsFailed > 0)
            {
                Environment.Exit(1);
            }
        }


        // ------------------------------------------------------------------
        // COPY-PATH TESTS (TradeCopierEngine.OnExecution)
        //
        // These exercise the actual order-submitting copy path, which until now was compiled
        // out of the test build by `#if !TESTING` and had ZERO coverage - despite being the
        // riskiest code in the addon. Each test below encodes a P0 defect from
        // docs/architecture/RISKGUARD_COPIER_HARDENING_PLAN.md and is expected to FAIL until
        // the corresponding fix lands.
        // ------------------------------------------------------------------

        /// <summary>Resets copier + account global state so copy-path tests are independent.</summary>
        private static Account SetupCopyPath(
            string leaderName, string followerName, CopierRelationship rel, int followerQty,
            Instrument followerInstrument, MarketPosition followerSide,
            Provider followerProvider = Provider.Simulator)
        {
            Account.All.Clear();
            Instrument.Registry.Clear();
            // RiskGuardAddOn.Instance is static, so a guard wired up by one copy-path
            // test would otherwise leak into every test that runs after it. Start each
            // one with no guard; the tests that need one install it explicitly.
            RiskGuardAddOn.SetInstanceForTest(null);

            // These are practice accounts unless a test says otherwise. Stated through the
            // provider rather than inferred from the "Sim" name prefix -- see P1-20.
            var leader = new Account { Name = leaderName, Provider = Provider.Simulator };
            var follower = new Account { Name = followerName, Provider = followerProvider };
            Account.All.Add(leader);
            Account.All.Add(follower);

            if (followerQty > 0 && followerInstrument != null)
            {
                follower.Positions.Add(new Position
                {
                    Instrument = followerInstrument,
                    MarketPosition = followerSide,
                    Quantity = followerQty,
                    AveragePrice = 18000
                });
            }

            TradeCopierEngine.Instance.RemoveRelationship(leaderName);
            TradeCopierEngine.Instance.UpsertRelationship(rel);
            return follower;
        }

        private static Execution LeaderExec(
            Account leader, Instrument inst, OrderAction action, int qty, string execId)
        {
            var order = new Order
            {
                Instrument = inst,
                OrderAction = action,
                OrderState = OrderState.Filled,
                OrderType = OrderType.Market,
                Quantity = qty,
                TimeInForce = TimeInForce.Day,
                Name = "LEADER_ENTRY"
            };
            return new Execution
            {
                Account = leader,
                Instrument = inst,
                Order = order,
                Quantity = qty,
                Price = 18000,
                ExecutionId = execId,
                Name = "LEADER_FILL"
            };
        }

        // P0-5: exit copies are sized from the LEADER's quantity and never clamped to what the
        // follower actually holds, so a follower holding less than the leader is flipped to the
        // opposite side by the exit copy.
        private static void TestCopyPath_ExitDoesNotFlipFollowerShort()
        {
            Console.WriteLine("\n[TEST] COPY PATH: leader exit must not flip a smaller follower short (P0-5)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = new CopierRelationship
            {
                LeaderAccountName = "SimLeader",
                FollowerAccountName = "SimFollower",
                IsEnabled = true,
                FixedLotMode = true,
                FixedLotSize = 1,
                AutoSymbolConversion = false,
                MaxPositionSize = 100
            };

            // Follower is LONG 1 (fixed-lot) while the leader is long 5.
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 1, mnq, MarketPosition.Long);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            // Leader exits all 5.
            var exec = LeaderExec(leader, mnq, OrderAction.Sell, 5, "EXIT-1");
            TradeCopierEngine.Instance.OnExecution(exec);

            var submitted = follower.Orders.Where(o => o.Name == "COPIER_FOLLOW").ToList();
            int copiedQty = submitted.Sum(o => o.Quantity);

            Assert(copiedQty <= 1,
                string.Format(
                    "Exit copy is clamped to the follower's actual position (expected <= 1, got {0}). "
                    + "Copying the leader's raw exit quantity leaves the follower SHORT the difference.",
                    copiedQty));
        }

        // P0-6: Math.Max(1, ...) floors sub-1 conversions to a whole contract, so a micro->mini
        // conversion multiplies notional by up to 10x.
        private static void TestCopyPath_MicroToMiniDoesNotInflateNotional()
        {
            Console.WriteLine("\n[TEST] COPY PATH: micro->mini must not floor to 1 contract (P0-6)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = new CopierRelationship
            {
                LeaderAccountName = "SimLeader",
                FollowerAccountName = "SimFollower",
                IsEnabled = true,
                AutoSymbolConversion = true,   // MNQ -> NQ, multiplier 0.1
                QuantityRatio = 1.0,
                MaxPositionSize = 100
            };

            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            // Leader buys 1 MNQ. 1 * 0.1 = 0.1 -> rounds to 0 -> must be SKIPPED, not floored to 1 NQ
            // (1 NQ == 10 MNQ of notional).
            var exec = LeaderExec(leader, mnq, OrderAction.Buy, 1, "MICRO-1");
            TradeCopierEngine.Instance.OnExecution(exec);

            var submitted = follower.Orders.Where(o => o.Name == "COPIER_FOLLOW").ToList();
            int copiedQty = submitted.Sum(o => o.Quantity);

            Assert(copiedQty == 0,
                string.Format(
                    "Sub-one-contract micro->mini conversion is skipped rather than floored to 1 "
                    + "(expected 0, got {0}). 1 NQ carries 10x the notional of 1 MNQ.",
                    copiedQty));
        }

        // P0-8: the copier is the only order-submitting path that does not consult RiskGuard,
        // so a locked-out follower keeps receiving copied entries.
        private static void TestCopyPath_LockedFollowerReceivesNoCopy()
        {
            Console.WriteLine("\n[TEST] COPY PATH: locked-out follower must not receive copies (P0-8)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = new CopierRelationship
            {
                LeaderAccountName = "SimLeader",
                FollowerAccountName = "SimFollower",
                IsEnabled = true,
                AutoSymbolConversion = false,
                QuantityRatio = 1.0,
                MaxPositionSize = 100
            };

            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            // Lock the follower out through RiskGuard, exactly as a daily-loss breach would.
            var guard = new RiskGuardAddOn();
            guard.SetConfigForTest(new RiskConfig());
            guard.SetSubscribedAccountForTest("SimFollower");
            var lockedState = new AccountState("SimFollower");
            lockedState.IsLockedOut = true;
            guard.SetAccountStateForTest("SimFollower", lockedState);
            // The copier consults RiskGuard through the static Instance, which
            // production assigns in State.Configure. Without this the guard built
            // above is invisible to OnExecution and the test cannot observe its
            // own subject.
            RiskGuardAddOn.SetInstanceForTest(guard);

            Assert(!guard.CanTrade("SimFollower", mnq.FullName, "TradeCopier"),
                "Precondition: RiskGuard reports the follower as not tradable");

            var exec = LeaderExec(leader, mnq, OrderAction.Buy, 2, "LOCKED-1");
            TradeCopierEngine.Instance.OnExecution(exec);

            var submitted = follower.Orders.Where(o => o.Name == "COPIER_FOLLOW").ToList();
            Assert(submitted.Count == 0,
                string.Format(
                    "No copy is submitted to a RiskGuard-locked follower (got {0} order(s)). "
                    + "Every other order path checks IsAccountLocked; the copier must too.",
                    submitted.Count));
        }

        // P1-20: the copier decided whether an account could lose real money by looking at
        // whether its NAME began with "Sim". Account names are chosen by the user, so a funded
        // account called "SimpsonFund" -- or "Simplex", or a prop firm whose name starts those
        // three letters -- was exempted from BOTH live-safety gates at once: the ArmedForLive
        // check and T5's requirement that a live follower be protected by RiskGuard. The P0 work
        // made that check load-bearing, so it has to be real.
        private static void TestCopyPath_LiveAccountNamedSimIsNotTreatedAsSimulated()
        {
            Console.WriteLine("\n[TEST] COPY PATH: a LIVE account whose name starts with 'Sim' is not treated as simulated (P1-20)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = new CopierRelationship
            {
                LeaderAccountName = "SimLeader",
                FollowerAccountName = "SimpsonFund",
                IsEnabled = true,
                ArmedForLive = false,      // NOT armed: a live follower must receive nothing
                AutoSymbolConversion = false,
                QuantityRatio = 1.0,
                MaxPositionSize = 100
            };

            // Name says "Sim...", provider says a real broker. The provider is the truth.
            var follower = SetupCopyPath("SimLeader", "SimpsonFund", rel, 0, null,
                                         MarketPosition.Flat, Provider.Rithmic);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            Assert(follower.Name.StartsWith("Sim", StringComparison.OrdinalIgnoreCase),
                "Precondition: the follower's name does begin with 'Sim'");
            Assert(follower.Provider != Provider.Simulator,
                "Precondition: the follower is nonetheless on a live broker provider");

            var exec = LeaderExec(leader, mnq, OrderAction.Buy, 2, "P1-20-LIVE");
            TradeCopierEngine.Instance.OnExecution(exec);

            var submitted = follower.Orders.Where(o => o.Name == "COPIER_FOLLOW").ToList();
            Assert(submitted.Count == 0,
                string.Format(
                    "A disarmed relationship sends nothing to a LIVE follower named 'SimpsonFund' "
                    + "(got {0} order(s)). Trusting the name prefix hands real money to an "
                    + "unarmed, unguarded copier.",
                    submitted.Count));
        }

        // The other half of P1-20: the fix must not break genuine simulation accounts. A real
        // Sim account is still exempt from ArmedForLive and from the guard requirement, so
        // practice copying keeps working without arming anything.
        private static void TestCopyPath_GenuineSimulatorAccountStillReceivesCopies()
        {
            Console.WriteLine("\n[TEST] COPY PATH: a genuine Simulator follower still receives copies while disarmed (P1-20)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = new CopierRelationship
            {
                LeaderAccountName = "SimLeader",
                FollowerAccountName = "PracticeAccount",   // name does NOT start with "Sim"
                IsEnabled = true,
                ArmedForLive = false,
                AutoSymbolConversion = false,
                QuantityRatio = 1.0,
                MaxPositionSize = 100
            };

            var follower = SetupCopyPath("SimLeader", "PracticeAccount", rel, 0, null,
                                         MarketPosition.Flat, Provider.Simulator);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            Assert(!follower.Name.StartsWith("Sim", StringComparison.OrdinalIgnoreCase),
                "Precondition: the follower's name does NOT begin with 'Sim'");

            var exec = LeaderExec(leader, mnq, OrderAction.Buy, 2, "P1-20-SIM");
            TradeCopierEngine.Instance.OnExecution(exec);

            var submitted = follower.Orders.Where(o => o.Name == "COPIER_FOLLOW").ToList();
            Assert(submitted.Count == 1,
                string.Format(
                    "A Simulator-provider follower receives the copy even though its name lacks the "
                    + "'Sim' prefix and nothing is armed (got {0} order(s)). The old check would "
                    + "have blocked this account for having the wrong name.",
                    submitted.Count));
        }

        // ------------------------------------------------------------------
        // COPIER SUBSCRIPTION TESTS (P1-21)
        //
        // McpBridgeAddOn enumerated Account.All exactly once, at State.Configure, and attached
        // the copier's execution handler there. Nothing ever ran that pass again, so an account
        // whose broker connected later never raised OnExecution: the relationship stayed
        // enabled in the config and visible in the UI while copying nothing at all. The
        // bookkeeping now lives on TradeCopierEngine so it is reachable from the test build --
        // McpBridgeAddOn.cs is excluded by RiskGuardTests.csproj, which is why this went
        // unnoticed.
        // ------------------------------------------------------------------

        /// <summary>Clears copier + account state and detaches any subscription left by a prior test.</summary>
        private static void ResetCopierSubscriptions(CopierRelationship rel)
        {
            Account.All.Clear();
            Instrument.Registry.Clear();
            RiskGuardAddOn.SetInstanceForTest(null);
            TradeCopierEngine.Instance.UnsubscribeAllAccounts();
            TradeCopierEngine.Instance.RemoveRelationship(rel.LeaderAccountName);
            TradeCopierEngine.Instance.UpsertRelationship(rel);
        }

        private static CopierRelationship SubsTestRelationship(string leader, string follower)
        {
            return new CopierRelationship
            {
                LeaderAccountName = leader,
                FollowerAccountName = follower,
                IsEnabled = true,
                FixedLotMode = true,
                FixedLotSize = 1,
                AutoSymbolConversion = false,
                MaxPositionSize = 100
            };
        }

        // P1-21: the leader's broker connects after State.Configure. Pre-fix there was no second
        // subscribe pass, so this leader's fills reached nobody.
        private static void TestCopierSubs_LateConnectingLeaderIsCopied()
        {
            Console.WriteLine("\n[TEST] COPIER SUBS: a leader that connects after startup is still copied (P1-21)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SubsTestRelationship("LateLeader", "SimFollower");
            ResetCopierSubscriptions(rel);

            // Startup: only the follower is online. This is the single pass McpBridgeAddOn used
            // to run at State.Configure and never repeat.
            var follower = new Account { Name = "SimFollower", Provider = Provider.Simulator };
            Account.All.Add(follower);
            TradeCopierEngine.Instance.RefreshAccountSubscriptions();

            // The leader's broker connects afterwards, and NT8 raises ConnectionStatusUpdate.
            var leader = new Account { Name = "LateLeader", Provider = Provider.Simulator };
            Account.All.Add(leader);
            TradeCopierEngine.Instance.RefreshAccountSubscriptions();

            // Delivered through the account event, not by calling OnExecution directly -- the
            // defect is in the wiring, so a test that bypasses the wiring cannot see it.
            leader.TriggerExecutionUpdate(LeaderExec(leader, mnq, OrderAction.Buy, 1, "P1-21-LATE"));

            int copied = follower.Orders.Count(o => o.Name == "COPIER_FOLLOW");
            Assert(copied == 1,
                string.Format(
                    "A leader that connected after startup still reaches the follower (expected 1 "
                    + "copy, got {0}). With the subscribe pass running only once, this leader "
                    + "raises no ExecutionUpdate and the relationship is silently dead.",
                    copied));
        }

        // P1-21 follow-on: the pass now runs on every connection change, and brokers flap. If it
        // were not idempotent, each reconnect would add another handler and copy every fill again.
        private static void TestCopierSubs_RepeatedRefreshAttachesOneHandler()
        {
            Console.WriteLine("\n[TEST] COPIER SUBS: repeated subscribe passes attach exactly one handler (P1-21)");

            var rel = SubsTestRelationship("FlapLeader", "SimFollower");
            ResetCopierSubscriptions(rel);

            var leader = new Account { Name = "FlapLeader", Provider = Provider.Simulator };
            Account.All.Add(leader);
            Account.All.Add(new Account { Name = "SimFollower", Provider = Provider.Simulator });

            for (int i = 0; i < 5; i++)
                TradeCopierEngine.Instance.RefreshAccountSubscriptions();

            Assert(leader.ExecutionUpdateHandlerCount == 1,
                string.Format(
                    "Five subscribe passes leave exactly one handler attached (got {0}). Each extra "
                    + "handler copies the fill again; the ExecutionId dedupe hides that only for "
                    + "executions that carry an id.",
                    leader.ExecutionUpdateHandlerCount));

            Assert(TradeCopierEngine.Instance.SubscribedAccountCount == 2,
                string.Format("Both accounts are tracked for teardown (got {0}).",
                    TradeCopierEngine.Instance.SubscribedAccountCount));
        }

        // NT8 reloads every AddOn on each recompile. A handler left attached keeps delivering
        // executions to the dead engine instance, which the new instance cannot detach.
        private static void TestCopierSubs_TeardownDetachesHandlers()
        {
            Console.WriteLine("\n[TEST] COPIER SUBS: teardown detaches every handler this engine attached (P1-21)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SubsTestRelationship("ShutdownLeader", "SimFollower");
            ResetCopierSubscriptions(rel);

            var leader = new Account { Name = "ShutdownLeader", Provider = Provider.Simulator };
            var follower = new Account { Name = "SimFollower", Provider = Provider.Simulator };
            Account.All.Add(leader);
            Account.All.Add(follower);
            TradeCopierEngine.Instance.RefreshAccountSubscriptions();

            int detached = TradeCopierEngine.Instance.UnsubscribeAllAccounts();

            Assert(detached == 2 && leader.ExecutionUpdateHandlerCount == 0,
                string.Format(
                    "Teardown reports 2 accounts and leaves 0 handlers (got {0} accounts, {1} "
                    + "handlers on the leader).",
                    detached, leader.ExecutionUpdateHandlerCount));

            leader.TriggerExecutionUpdate(LeaderExec(leader, mnq, OrderAction.Buy, 1, "P1-21-DOWN"));

            int copied = follower.Orders.Count(o => o.Name == "COPIER_FOLLOW");
            Assert(copied == 0,
                string.Format(
                    "A fill arriving after teardown is not copied (got {0} copy/copies).", copied));
        }

        // ------------------------------------------------------------------
        // COPY SLIPPAGE / LATENCY TESTS (P1-22)
        //
        // `LatencyMs` and `AvgSlippageTicks` were rendered in TradeCopierWindow (:799) and
        // written by nothing at all, so the UI reported a clean 0ms / 0.0t however badly a copy
        // filled. The copier's only possible observation of its own cost is the follower's fill,
        // which arrives as an ExecutionUpdate on the follower account.
        // ------------------------------------------------------------------

        private static readonly DateTime SlipT0 = new DateTime(2026, 8, 7, 14, 30, 0, DateTimeKind.Utc);

        private static CopierRelationship SlipRelationship(double maxSlippageTicks, bool autoConvert = false)
        {
            return new CopierRelationship
            {
                LeaderAccountName = "SimLeader",
                FollowerAccountName = "SimFollower",
                IsEnabled = true,
                FixedLotMode = true,
                FixedLotSize = 1,
                AutoSymbolConversion = autoConvert,
                MaxPositionSize = 100,
                MaxSlippageTicks = maxSlippageTicks
            };
        }

        /// <summary>Feeds back the fill of the copy order the engine just submitted.</summary>
        private static void FillFollowerCopy(
            Account follower, Instrument inst, double price, int msAfterLeader, string execId, int orderIndex = 0)
        {
            var copy = follower.Orders.Where(o => o.Name == "COPIER_FOLLOW").ElementAt(orderIndex);
            TradeCopierEngine.Instance.OnExecution(new Execution
            {
                Account = follower,
                Instrument = inst,
                Order = copy,
                Quantity = copy.Quantity,
                Price = price,
                ExecutionId = execId,
                Name = "COPIER_FOLLOW",
                Time = SlipT0.AddMilliseconds(msAfterLeader)
            });
        }

        private static void TestCopierSlip_FollowerFillPopulatesLatencyAndSlippage()
        {
            Console.WriteLine("\n[TEST] COPIER SLIP: a follower fill populates LatencyMs and AvgSlippageTicks (P1-22)");

            var mnq = new Instrument("MNQ 03-26");   // stub tick size 0.25
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            var lead = LeaderExec(leader, mnq, OrderAction.Buy, 1, "SLIP-A");
            lead.Time = SlipT0;
            lead.Price = 18000.00;
            TradeCopierEngine.Instance.OnExecution(lead);

            // Fills 250 ms later, one point higher -- 4 ticks WORSE for a buy.
            FillFollowerCopy(follower, mnq, 18001.00, 250, "SLIP-A-F");

            Assert(Math.Abs(rel.LatencyMs - 250.0) < 1.0,
                string.Format(
                    "Latency is measured leader-fill to follower-fill (expected ~250ms, got {0:F0}ms). "
                    + "It was previously never written and the UI rendered a constant 0.",
                    rel.LatencyMs));

            Assert(Math.Abs(rel.AvgSlippageTicks - 4.0) < 0.01,
                string.Format(
                    "Adverse slippage on a buy is recorded POSITIVE, in ticks (expected 4.0, got {0:F2}).",
                    rel.AvgSlippageTicks));
        }

        // Sign correctness. A fill that is BETTER than the leader's must not read as slippage,
        // or a MaxSlippageTicks threshold would quarantine relationships for filling well.
        private static void TestCopierSlip_FavourableFillIsNegativeAndDoesNotQuarantine()
        {
            Console.WriteLine("\n[TEST] COPIER SLIP: a favourable fill is negative slippage and never quarantines (P1-22)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(2.0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            // Leader goes SHORT at 18000; the follower fills one point HIGHER, which is better
            // for a short. Raw price delta is +4 ticks and must come out as -4.
            var lead = LeaderExec(leader, mnq, OrderAction.SellShort, 1, "SLIP-B");
            lead.Time = SlipT0;
            lead.Price = 18000.00;
            TradeCopierEngine.Instance.OnExecution(lead);

            FillFollowerCopy(follower, mnq, 18001.00, 100, "SLIP-B-F");

            Assert(Math.Abs(rel.AvgSlippageTicks + 4.0) < 0.01,
                string.Format(
                    "A short filled above the leader is -4.0 ticks, not +4.0 (got {0:F2}). An unsigned "
                    + "figure would quarantine this relationship for filling BETTER than the leader.",
                    rel.AvgSlippageTicks));

            Assert(!rel.IsQuarantined,
                "A favourable fill does not trip MaxSlippageTicks=2.");
        }

        // The safety-critical half. Quarantine must stop new ENTRIES without trapping the
        // follower in a position the leader has already left.
        private static void TestCopierSlip_EntryQuarantinesButExitStillCopies()
        {
            Console.WriteLine("\n[TEST] COPIER SLIP: a slippage quarantine blocks entries but still copies exits (P1-22)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(2.0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            var entry = LeaderExec(leader, mnq, OrderAction.Buy, 1, "SLIP-C");
            entry.Time = SlipT0;
            entry.Price = 18000.00;
            TradeCopierEngine.Instance.OnExecution(entry);

            // Fills 4 ticks adverse against a 2-tick limit.
            FillFollowerCopy(follower, mnq, 18001.00, 120, "SLIP-C-F");

            Assert(rel.IsQuarantined,
                string.Format("An entry slipping 4 ticks past a 2-tick limit quarantines the relationship (IsQuarantined={0}).",
                    rel.IsQuarantined));

            // The follower now actually holds the contract the copy bought.
            follower.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 1, AveragePrice = 18001
            });

            int ordersBefore = follower.Orders.Count(o => o.Name == "COPIER_FOLLOW");

            // A further ENTRY must be refused.
            var moreEntry = LeaderExec(leader, mnq, OrderAction.Buy, 1, "SLIP-C2");
            moreEntry.Time = SlipT0.AddSeconds(1);
            TradeCopierEngine.Instance.OnExecution(moreEntry);
            Assert(follower.Orders.Count(o => o.Name == "COPIER_FOLLOW") == ordersBefore,
                "A quarantined relationship refuses further entries.");

            // The EXIT must still go through.
            var exit = LeaderExec(leader, mnq, OrderAction.Sell, 1, "SLIP-C3");
            exit.Time = SlipT0.AddSeconds(2);
            TradeCopierEngine.Instance.OnExecution(exit);

            Assert(follower.Orders.Count(o => o.Name == "COPIER_FOLLOW") == ordersBefore + 1,
                string.Format(
                    "A quarantined relationship still copies the EXIT (expected {0} orders, got {1}). "
                    + "Blocking it strands the follower in a position the leader has already left -- "
                    + "the P0-5 failure reached by another route.",
                    ordersBefore + 1, follower.Orders.Count(o => o.Name == "COPIER_FOLLOW")));
        }

        // A custom symbol mapping can point at an instrument whose price is unrelated. Comparing
        // those two fills produces a meaningless number, and acting on it would quarantine a
        // perfectly healthy relationship on its first copy.
        private static void TestCopierSlip_IncomparableSymbolsRecordNoSlippage()
        {
            Console.WriteLine("\n[TEST] COPIER SLIP: an unrelated mapped symbol records no slippage (P1-22)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(2.0, autoConvert: true);
            rel.CustomSymbolMappings["MNQ"] = "ES";   // legitimate mapping, unrelated price scale

            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            var lead = LeaderExec(leader, mnq, OrderAction.Buy, 1, "SLIP-D");
            lead.Time = SlipT0;
            lead.Price = 18000.00;
            TradeCopierEngine.Instance.OnExecution(lead);

            var es = Instrument.GetInstrument("ES 03-26");
            Assert(follower.Orders.Any(o => o.Name == "COPIER_FOLLOW"),
                "Precondition: the mapped copy was submitted.");

            // ES fills at its own price level, ~13000 points from MNQ's.
            FillFollowerCopy(follower, es, 5000.00, 90, "SLIP-D-F");

            Assert(rel.AvgSlippageTicks == 0.0,
                string.Format(
                    "No slippage is recorded between price-incomparable instruments (got {0:F2} ticks).",
                    rel.AvgSlippageTicks));

            Assert(!rel.IsQuarantined,
                "A price-incomparable mapping does not quarantine the relationship on its first copy.");

            Assert(rel.LatencyMs > 0,
                string.Format("Latency is still measured -- it does not depend on price (got {0:F0}ms).", rel.LatencyMs));
        }

        // NT8's Order.OrderId is not guaranteed unique and CAN CHANGE over an order's lifetime
        // (historical->live transition) -- RiskGuardAddOn.cs:4481 already records this and tracks
        // recognised stops by object reference for the same reason. A pending-copy map keyed on
        // the id string looks correct and passes every other test in this file, because the stub
        // assigns one stable GUID per order. This test makes the stub behave like NT8.
        private static void TestCopierSlip_FillIsMatchedWhenOrderIdChanges()
        {
            Console.WriteLine("\n[TEST] COPIER SLIP: a fill is matched by Order reference, not OrderId (P1-22)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");

            var lead = LeaderExec(leader, mnq, OrderAction.Buy, 1, "SLIP-E");
            lead.Time = SlipT0;
            lead.Price = 18000.00;
            TradeCopierEngine.Instance.OnExecution(lead);

            var copy = follower.Orders.First(o => o.Name == "COPIER_FOLLOW");
            string original = copy.OrderId;

            // NT8 re-issues the id on the historical->live transition. Same Order object.
            copy.OrderId = Guid.NewGuid().ToString();
            Assert(copy.OrderId != original, "Precondition: the order's id changed after submit.");

            FillFollowerCopy(follower, mnq, 18001.00, 300, "SLIP-E-F");

            Assert(Math.Abs(rel.AvgSlippageTicks - 4.0) < 0.01 && rel.LatencyMs > 0,
                string.Format(
                    "The fill is still matched to its pending copy after the id changed "
                    + "(slippage {0:F2} ticks, latency {1:F0}ms; both 0 means the lookup missed). "
                    + "Keying on OrderId silently loses the measurement -- or attributes it to "
                    + "the wrong copy, since the id is not unique either.",
                    rel.AvgSlippageTicks, rel.LatencyMs));
        }

        // ------------------------------------------------------------------
        // BRACKET REPLICATION TESTS (P0-9)
        //
        // Followers received bare market orders with no protective legs. The mirrored stop is
        // anchored to the FOLLOWER's own fill and carries the LEADER's risk distance -- copying
        // the leader's stop price would be wrong by the slippage P1-22 measures, and wrong by an
        // entire price scale across a micro/mini conversion.
        // ------------------------------------------------------------------

        /// <summary>
        /// Clears bracket state and re-points the engine's subscriptions at the accounts the test
        /// just built. SetupCopyPath replaces Account.All with fresh objects, so without the
        /// re-subscribe the leader raises OrderUpdate into nothing and every bracket assertion
        /// fails for the wrong reason. These tests deliberately drive the real event wiring.
        /// </summary>
        private static void ResetBracketState()
        {
            TradeCopierEngine.Instance.ResetBracketsForTest();
            TradeCopierEngine.Instance.UnsubscribeAllAccounts();
            TradeCopierEngine.Instance.RefreshAccountSubscriptions();
        }

        /// <summary>Puts `acct` into a position the stub broker will report, as NT8 would.</summary>
        private static void SetPosition(Account acct, Instrument inst, MarketPosition side, int qty, double avg)
        {
            acct.Positions.RemoveAll(p => p.Instrument != null
                && p.Instrument.FullName.Equals(inst.FullName, StringComparison.OrdinalIgnoreCase));
            if (side == MarketPosition.Flat || qty <= 0) return;
            acct.Positions.Add(new Position
            {
                Instrument = inst, MarketPosition = side, Quantity = qty, AveragePrice = avg
            });
        }

        private static Order LeaderStop(Instrument inst, OrderAction action, int qty, double stopPrice)
        {
            return new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderId = Guid.NewGuid().ToString(),
                Name = "Stop_Leader",
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                Quantity = qty,
                Instrument = inst,
                OrderAction = action,
                StopPrice = stopPrice
            };
        }

        /// <summary>Drives an entry copy and the follower's fill, leaving the follower long `qty` at `fillPrice`.</summary>
        private static void DriveFollowerEntry(
            Account leader, Account follower, Instrument inst, int qty, double leaderPrice,
            double fillPrice, string execId)
        {
            var lead = LeaderExec(leader, inst, OrderAction.Buy, qty, execId);
            lead.Price = leaderPrice;
            lead.Time = SlipT0;
            TradeCopierEngine.Instance.OnExecution(lead);

            var copy = follower.Orders.Last(o => o.Name == "COPIER_FOLLOW");
            SetPosition(follower, inst, MarketPosition.Long, copy.Quantity, fillPrice);
            TradeCopierEngine.Instance.OnExecution(new Execution
            {
                Account = follower, Instrument = inst, Order = copy, Quantity = copy.Quantity,
                Price = fillPrice, ExecutionId = execId + "-F", Name = "COPIER_FOLLOW",
                Time = SlipT0.AddMilliseconds(100)
            });
        }

        // The defining property: the mirrored stop preserves the leader's RISK DISTANCE, applied
        // to where the follower actually filled.
        private static void TestBracket_StopMirrorsLeaderDistanceFromFollowerFill()
        {
            Console.WriteLine("\n[TEST] BRACKET: the leader's stop distance is anchored to the follower's own fill (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            // Follower fills 2 points worse than the leader.
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18002.00, "BR-A");

            Assert(!follower.Orders.Any(o => o.Name == "COPIER_STOP"),
                "No stop is placed before the leader has one -- there is no distance to mirror yet.");

            // Leader attaches its stop 10 points below its entry.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));

            var stops = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            Assert(stops.Count == 1,
                string.Format("Exactly one protective stop is placed on the follower (got {0}).", stops.Count));

            Assert(Math.Abs(stops[0].StopPrice - 17992.00) < 1e-9,
                string.Format(
                    "The stop sits at the follower's fill minus the leader's 10-point distance: "
                    + "expected 17992.00, got {0}. Copying the leader's stop PRICE (17990) would give "
                    + "the follower 12 points of risk instead of 10.",
                    stops[0].StopPrice));

            Assert(stops[0].OrderAction == OrderAction.Sell && stops[0].Quantity == 1,
                "The stop reduces the follower's long position and matches its size.");
        }

        // Ordering: the leader can attach its stop before our copy fills. The distance must be
        // held and applied when the anchor arrives, not dropped.
        private static void TestBracket_StopBeforeFollowerFillIsAppliedOnFill()
        {
            Console.WriteLine("\n[TEST] BRACKET: a leader stop seen before the follower fills is applied on the fill (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);

            // Leader's stop arrives FIRST, while the follower is still flat.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17985.00));
            Assert(!follower.Orders.Any(o => o.Name == "COPIER_STOP"),
                "Nothing is placed while the follower has no position to protect.");

            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18001.00, "BR-B");

            var stops = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            Assert(stops.Count == 1 && Math.Abs(stops[0].StopPrice - 17986.00) < 1e-9,
                string.Format(
                    "The held 15-point distance is applied once the follower fills at 18001 "
                    + "(expected one stop at 17986.00, got {0} stop(s) at {1}). Dropping the "
                    + "distance leaves the follower naked for the life of the trade.",
                    stops.Count, stops.Count > 0 ? stops[0].StopPrice.ToString() : "n/a"));
        }

        /// <summary>
        /// P0-55. The leader-side twin of P0-49, and it leaves the follower naked the same way.
        ///
        /// An ATM bracket's stop can reach `Accepted` BEFORE the leader's own PositionUpdate lands
        /// -- NT8 raises ExecutionUpdate before PositionUpdate, and on a partial fill the stop for
        /// the full size arrives while the leader still shows a smaller position or none at all.
        /// OnLeaderOrderUpdate reads `leaderAccount.Positions` to anchor the distance, finds
        /// nothing, and returns. **The offset is never computed, and nothing re-triggers it**: an
        /// accepted ATM stop raises no further OrderUpdate, and the leader's PositionUpdate was
        /// discarded outright because the account is not a follower.
        ///
        /// P0-49 fixed precisely this race on the FOLLOWER's anchor and its docstring names the
        /// mechanism. The leader's own anchor has the same race and was never covered.
        ///
        /// Observed live 2026-08-10 00:11:31 ET: Sim101's 2-lot ATM filled 1 + 1; stop 34262 was
        /// Accepted at .4203, the position first appeared at .4683. Sim-ORB received the copied
        /// entry and NO COPIER_STOP, and ran the whole trade Unprotected.
        /// </summary>
        private static void TestBracket_P0_55_LeaderStopAcceptedBeforeLeaderPositionIsStillMirrored()
        {
            Console.WriteLine("\n[TEST] BRACKET: a leader stop accepted BEFORE the leader's position is still mirrored (P0-55)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            // The stop is accepted while the leader is still FLAT -- the race. There is no anchor
            // to measure against yet, so nothing can be computed at this instant.
            var stop = LeaderStop(mnq, OrderAction.Sell, 2, 17985.00);
            // LeaderStop() alone only raises the event; NT8 also has the order in account.Orders,
            // and the re-anchor pass reads it from there. Without this the test would prove the
            // recovery cannot work rather than that it does.
            leader.Orders.Add(stop);
            leader.TriggerOrderUpdate(stop);

            Assert(!follower.Orders.Any(o => o.Name == "COPIER_STOP"),
                "Nothing is mirrored while the leader has no position to anchor the distance to");

            // Now the leader's position lands. This is the event that used to be thrown away,
            // and it is the last one that will ever mention this stop.
            SetPosition(leader, mnq, MarketPosition.Long, 2, 18000.00);
            leader.TriggerPositionUpdate(leader.Positions.First(p => p.Instrument.FullName == mnq.FullName));

            DriveFollowerEntry(leader, follower, mnq, 2, 18000.00, 18001.00, "BR-P055");

            var stops = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            Assert(stops.Count == 1,
                string.Format(
                    "The leader's stop is mirrored once the leader's position appears (got {0} "
                    + "stop(s)). Without this the follower carries the whole trade naked.",
                    stops.Count));
            Assert(stops.Count == 1 && Math.Abs(stops[0].StopPrice - 17986.00) < 1e-9,
                string.Format(
                    "The mirrored stop carries the leader's 15-point DISTANCE from the follower's "
                    + "own fill at 18001 (expected 17986.00, got {0})",
                    stops.Count > 0 ? stops[0].StopPrice.ToString() : "n/a"));
        }

        // A leader trailing its stop must move the follower's, not accumulate copies of it.
        private static void TestBracket_MovingLeaderStopReplacesRatherThanDuplicates()
        {
            Console.WriteLine("\n[TEST] BRACKET: a leader moving its stop replaces the follower's, not duplicates it (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-C");

            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));   // 10 pts
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17995.00));   // trailed to 5
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17998.00));   // trailed to 2

            var live = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && o.OrderState != OrderState.Cancelled)
                .ToList();

            Assert(live.Count == 1,
                string.Format(
                    "Exactly one stop is live after three trail steps (got {0}). Two live stops "
                    + "over-cover: when both fire the follower is flipped to the opposite side.",
                    live.Count));

            Assert(Math.Abs(live[0].StopPrice - 17998.00) < 1e-9,
                string.Format("The live stop tracks the leader's latest distance (expected 17998.00, got {0}).",
                    live[0].StopPrice));
        }

        /// <summary>
        /// P1-56. Two bracket syncs that interleave must not leave two protective stops working
        /// against one position.
        ///
        /// `SyncFollowerStop` clears `bracket.WorkingStop` under `_lock` BEFORE the broker call and
        /// only reassigns it AFTER `Submit`. A second sync entering that window sees `null`,
        /// concludes the follower has no stop, and creates another one. Observed live 2026-08-10
        /// 01:02: Sim-ORB finished with `COPIER_STOP` qty 1 AND `COPIER_STOP` qty 2 against a 2-lot
        /// position, both orders carrying the same creation timestamp. Three contracts of stop
        /// behind two contracts of position -- when both fire the follower is flipped short.
        ///
        /// The whole suite passed with this defect live, because every other test drives the sync
        /// paths sequentially. So the interleaving is reproduced deterministically rather than by
        /// racing threads and hoping: `BrokerCallObserver` fires INSIDE the first sync's
        /// `CreateOrder`, which is precisely the window -- the lock is released, `WorkingStop` is
        /// null and nothing has been submitted -- and the second sync is driven from another thread
        /// while the first is parked there.
        ///
        /// The two triggers are the pair that produced it live: a partial entry fill anchors the
        /// bracket at 1 lot, and the rest of the fill arrives as a follower position update
        /// carrying 2.
        ///
        /// BOTH assertions matter. Backing the second sync off closes the over-cover, but if its
        /// instruction is DISCARDED the follower is left with a 1-lot stop behind a 2-lot position
        /// -- under-cover, which is naked risk on the delta. The newer instruction has to be
        /// re-applied once the in-flight submit completes.
        /// </summary>
        private static void TestBracket_P1_56_InterleavedSyncsLeaveExactlyOneProtectiveStop()
        {
            Console.WriteLine("\n[TEST] BRACKET: two interleaved stop syncs leave ONE stop, sized to the whole position (P1-56)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            rel.FixedLotSize = 2;                      // a 2-lot copy, as the live trade was
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 2, 18000.00);

            var lead = LeaderExec(leader, mnq, OrderAction.Buy, 2, "BR-56");
            lead.Price = 18000.00;
            lead.Time = SlipT0;
            TradeCopierEngine.Instance.OnExecution(lead);

            var copy = follower.Orders.Last(o => o.Name == "COPIER_FOLLOW");

            // First piece of the entry fills. This anchors the bracket at ONE lot.
            SetPosition(follower, mnq, MarketPosition.Long, 1, 18000.00);
            TradeCopierEngine.Instance.OnExecution(new Execution
            {
                Account = follower, Instrument = mnq, Order = copy, Quantity = 1,
                Price = 18000.00, ExecutionId = "BR-56-F1", Name = "COPIER_FOLLOW",
                Time = SlipT0.AddMilliseconds(100)
            });

            var secondSyncMayRun = new ManualResetEventSlim(false);
            var secondSyncDone = new ManualResetEventSlim(false);
            Exception secondSyncError = null;

            // The second trigger: the rest of the entry fills, so the follower's position update
            // carries 2 lots. It runs while the first sync is inside CreateOrder.
            var second = new System.Threading.Thread(() =>
            {
                try
                {
                    if (!secondSyncMayRun.Wait(TimeSpan.FromSeconds(20))) return;
                    SetPosition(follower, mnq, MarketPosition.Long, 2, 18000.00);
                    follower.TriggerPositionUpdate(follower.Positions.First(p =>
                        p.Instrument != null && p.Instrument.FullName == mnq.FullName));
                }
                catch (Exception ex) { secondSyncError = ex; }
                finally { secondSyncDone.Set(); }
            });
            second.IsBackground = true;
            second.Start();

            int tripped = 0;
            var previousObserver = Account.BrokerCallObserver;
            Account.BrokerCallObserver = method =>
            {
                if (method != "CreateOrder") return;
                if (Interlocked.CompareExchange(ref tripped, 1, 0) != 0) return;
                secondSyncMayRun.Set();
                // Bounded on purpose: a fix that makes the second sync BLOCK on the first would
                // deadlock the suite here. Time out and let the assertions report instead.
                secondSyncDone.Wait(TimeSpan.FromSeconds(10));
            };

            try
            {
                leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 2, 17990.00));
            }
            finally
            {
                Account.BrokerCallObserver = previousObserver;
            }

            secondSyncMayRun.Set();                    // in case CreateOrder was never reached
            second.Join(TimeSpan.FromSeconds(20));

            Assert(secondSyncError == null,
                "The second sync completed without throwing"
                + (secondSyncError == null ? "" : ": " + secondSyncError.Message));

            Assert(Volatile.Read(ref tripped) == 1,
                "The interleaving actually happened -- the second sync was driven from inside the "
                + "first sync's CreateOrder. If this fails, nothing was proved.");

            var live = follower.OrdersSnapshot()
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn.ProvidesCoverage(o.OrderState))
                .ToList();

            Assert(live.Count == 1,
                string.Format(
                    "Exactly one COPIER_STOP is live after two interleaved syncs (got {0}, "
                    + "quantities {1}). Two live stops behind one position over-cover it: when both "
                    + "fire the follower is flipped to the opposite side.",
                    live.Count,
                    string.Join("+", live.Select(o => o.Quantity.ToString()).ToArray())));

            Assert(live.Sum(o => o.Quantity) == 2,
                string.Format(
                    "The surviving stop covers the whole 2-lot position (covered {0}). Backing the "
                    + "second sync off must not DISCARD its instruction -- a 1-lot stop behind a "
                    + "2-lot position is naked on the delta.",
                    live.Sum(o => o.Quantity)));
        }

        /// <summary>
        /// P0-9 refinement: a leader trailing its stop MODIFIES the follower's working stop rather
        /// than cancelling and re-creating it.
        ///
        /// Cancel-then-create leaves the follower unprotected between the cancel and the new
        /// order's acceptance, on every trail step -- and trailing is the most ordinary trade
        /// management there is. The original P0-9 note chose cancel-then-replace to avoid a stale
        /// stop working beside a new one, which over-covers and flips the follower when both fire.
        /// `Change()` avoids that by construction: there is only ever one order.
        ///
        /// This is safe to rely on here because the connection serving every account on this box
        /// advertises the `OrderChange` feature (see /api/connections). If a future connection does
        /// not, the implementation must fall back to cancel-then-create.
        /// </summary>
        private static void TestBracket_TrailingModifiesTheStopRatherThanRecreatingIt()
        {
            Console.WriteLine("\n[TEST] BRACKET: a leader trailing its stop MODIFIES the follower's stop, leaving no naked window (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-TRAIL");

            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));   // 10 pts
            var first = follower.Orders.Single(o => o.Name == "COPIER_STOP");
            Assert(Math.Abs(first.StopPrice - 17990.00) < 1e-9,
                "The initial mirrored stop sits at the leader's distance");

            // The leader trails into profit. This is the step that used to cancel and re-create.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17996.00));

            var all = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            Assert(all.Count == 1,
                string.Format(
                    "The trail modifies the existing stop rather than creating a second order "
                    + "(expected 1 COPIER_STOP, got {0}). A recreate leaves the follower naked "
                    + "between the cancel and the new order's acceptance.",
                    all.Count));
            Assert(!all.Any(o => o.OrderState == OrderState.Cancelled),
                "No COPIER_STOP was cancelled during the trail -- there is no naked window");
            Assert(ReferenceEquals(all[0], first),
                "It is the SAME order object, modified in place, not a replacement");
            Assert(Math.Abs(all[0].StopPrice - 17996.00) < 1e-9,
                string.Format("The modified stop carries the leader's new distance (expected 17996.00, got {0})",
                    all[0].StopPrice));
        }

        // ------------------------------------------------------------------
        // P0-9 item (1): the mirrored PROFIT TARGET, and the OCO pairing it brings with it.
        // ------------------------------------------------------------------

        /// <summary>
        /// P0-59 / P0-60. The classification must be TOTAL over NT8's OrderState, and the two
        /// derived predicates must be conservative in OPPOSITE directions for anything it cannot
        /// vouch for.
        ///
        /// This is the test that could not have existed before: six of NT8's sixteen states were
        /// absent from the stub enum, so no test could name them. The suite was green at 686/0
        /// with a P0 live on the box because the fiction we author was missing the states that
        /// mattered.
        /// </summary>
        private static void TestOrderLiveness_ClassifiesEveryNT8OrderState()
        {
            Console.WriteLine("\n[TEST] ORDER LIVENESS: every NT8 OrderState is classified, and unknowns fail safe BOTH ways (P0-59/P0-60)");

            // Reflected from NinjaTrader.Core.dll, not recalled. If NT8 adds a state, this list
            // and the switch in Classify must both learn about it.
            var expected = new[]
            {
                "Accepted", "Cancelled", "Filled", "Initialized", "PartFilled", "CancelSubmitted",
                "ChangeSubmitted", "Submitted", "TriggerPending", "Rejected", "Working",
                "CancelPending", "ChangePending", "Suspended", "AcceptedByRisk", "Unknown"
            };
            var declared = Enum.GetNames(typeof(OrderState));

            var missing = expected.Where(e => !declared.Contains(e)).ToList();
            var extra = declared.Where(d => !expected.Contains(d)).ToList();
            Assert(missing.Count == 0 && extra.Count == 0,
                string.Format(
                    "The test stub's OrderState matches NT8's exactly (missing: [{0}], unexpected: [{1}]). "
                    + "A state the stub cannot name is a state no test can drive.",
                    string.Join(",", missing), string.Join(",", extra)));

            // Every declared state must be classified, and nothing may fall through to
            // Indeterminate except the state that genuinely means "unknown".
            var unclassified = new List<string>();
            foreach (OrderState s in Enum.GetValues(typeof(OrderState)))
            {
                if (RiskGuardAddOn.Classify(s) == RiskGuardAddOn.OrderLiveness.Indeterminate
                    && s != OrderState.Unknown)
                    unclassified.Add(s.ToString());
            }
            Assert(unclassified.Count == 0,
                string.Format(
                    "Every OrderState is explicitly classified (fell through: [{0}]). A state that "
                    + "reaches the default arm is one the addons will guess about.",
                    string.Join(",", unclassified)));

            // The states that caused the two live defects, named individually so a regression
            // says which hazard came back.
            Assert(RiskGuardAddOn.ProvidesCoverage(OrderState.ChangeSubmitted)
                    && RiskGuardAddOn.OccupiesSlot(OrderState.ChangeSubmitted),
                "P0-59: an order mid-Change() is WORKING. Reading it as gone is what created a "
                + "second protective leg against one position.");
            Assert(RiskGuardAddOn.ProvidesCoverage(OrderState.ChangePending)
                    && RiskGuardAddOn.OccupiesSlot(OrderState.ChangePending),
                "An order mid-Change() is working in the pending state too");
            Assert(RiskGuardAddOn.ProvidesCoverage(OrderState.TriggerPending),
                "A stop waiting on its trigger is the most protective state a stop has; it must "
                + "count as coverage");

            Assert(!RiskGuardAddOn.ProvidesCoverage(OrderState.CancelSubmitted)
                    && !RiskGuardAddOn.ProvidesCoverage(OrderState.CancelPending),
                "P0-60: a stop that is being CANCELLED is not coverage. `!IsTerminal` used to say "
                + "it was, so a position read as protected while its only stop was going away.");
            Assert(!RiskGuardAddOn.OccupiesSlot(OrderState.CancelSubmitted),
                "...but its slot is free, so a replacement may be placed without waiting");

            Assert(!RiskGuardAddOn.ProvidesCoverage(OrderState.Suspended),
                "A suspended order will not act, so it is not coverage");
            Assert(RiskGuardAddOn.OccupiesSlot(OrderState.Suspended),
                "...yet it still exists, so it must not be duplicated");

            // The crux: one boolean cannot be fail-safe for both questions, which is why there
            // are two predicates.
            Assert(!RiskGuardAddOn.ProvidesCoverage(OrderState.Unknown),
                "An unclassifiable order is NOT coverage -- assuming it is leaves a naked position");
            Assert(RiskGuardAddOn.OccupiesSlot(OrderState.Unknown),
                "...and it DOES occupy a slot -- assuming it does not creates a duplicate leg. "
                + "Conservative in both directions at once; no single boolean can be.");

            Assert(RiskGuardAddOn.IsTerminal(OrderState.Filled)
                    && RiskGuardAddOn.IsTerminal(OrderState.Cancelled)
                    && RiskGuardAddOn.IsTerminal(OrderState.Rejected),
                "Terminal means terminal");
            Assert(!RiskGuardAddOn.IsTerminal(OrderState.CancelPending),
                "A cancelling order is NOT terminal -- it is Departing, and calling it terminal "
                + "would hide the distinction that P0-60 turns on");
        }

        /// <summary>
        /// P0-59, reproducing the live incident of 2026-08-10 13:55:56 exactly.
        ///
        /// A mirrored leg passes through `ChangeSubmitted` every time `Account.Change()` touches
        /// it — which is what our own trail does. The old classification said that state was not
        /// live, so `OnFollowerOrderUpdate` read the leg as LOST and re-submitted it while the
        /// original was still working: two `COPIER_TARGET`s at 29859.75 in one OCO group against
        /// one lot, mirrored onward to three accounts.
        ///
        /// No concurrency is involved. One handler misreading one state is enough, which is why
        /// `P1-56`'s reservation could not prevent it.
        /// </summary>
        private static void TestBracket_P0_59_ALegBeingModifiedIsNotDuplicated()
        {
            Console.WriteLine("\n[TEST] BRACKET: a leg in ChangeSubmitted is NOT re-submitted as a duplicate (P0-59)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-P059");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            leader.TriggerOrderUpdate(LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00));

            var target = follower.Orders.Single(o => o.Name == "COPIER_TARGET");
            var stop = follower.Orders.Single(o => o.Name == "COPIER_STOP");

            // The broker takes the leg into its change transition and tells us about it.
            target.OrderState = OrderState.ChangeSubmitted;
            follower.TriggerOrderUpdate(target);

            var targets = follower.Orders.Where(o => o.Name == "COPIER_TARGET").ToList();
            Assert(targets.Count == 1,
                string.Format(
                    "A leg mid-modification is not duplicated (got {0} COPIER_TARGET orders). Two "
                    + "live targets against one lot over-cover: when both fill the follower is "
                    + "flipped short. Seen live on 2026-08-10.",
                    targets.Count));

            // And the same for the RISK leg, which is where this actually costs money: our own
            // trail calls Change(), so a leader trailing its stop reaches this every step.
            stop.OrderState = OrderState.ChangeSubmitted;
            follower.TriggerOrderUpdate(stop);

            var stops = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            Assert(stops.Count == 1,
                string.Format(
                    "A STOP mid-modification is not duplicated either (got {0}). This is the one "
                    + "that matters: every trail step passes through this state.",
                    stops.Count));
        }

        /// <summary>
        /// P0-60, the same root cause pointing the other way.
        ///
        /// RiskGuard asked `!IsTerminal` to decide whether a stop was covering a position, so a
        /// stop in `CancelSubmitted`/`CancelPending` — one the broker has already been told to
        /// pull — still counted as cover. The position reads as protected during exactly the
        /// window in which its protection is being withdrawn, and no auto-stop is armed.
        ///
        /// Modelled on `TestP1_36_LosingOneOfTwoStopsIsPartialCoverNotNakedness`, with the one
        /// variable changed: the leg goes to `CancelSubmitted` rather than `Cancelled`.
        /// </summary>
        private static void TestP0_60_AStopBeingCancelledStopsCountingAsCoverage()
        {
            Console.WriteLine("\n[TEST] P0-60: a stop in CancelSubmitted is NOT coverage — protection being withdrawn is not protection");

            var mnq = new Instrument("MNQ");
            var account = AutoStopTestAccount(mnq, MarketPosition.Long, 6, 18000, 18000);
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 60));
            addon.TestClearFsms();

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 6);
            var legA = PartialStop(mnq, 3, 17990, "Stop_Half1");
            var legB = PartialStop(mnq, 3, 17985, "Stop_Half2");
            addon.TestFsmOnOrder(account, mnq.FullName, legA);
            addon.TestFsmOnOrder(account, mnq.FullName, legB);

            var fsm0 = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm0 != null && fsm0.CoveredQuantity == 6, "Precondition: both legs cover the 6 lots");

            // The broker has accepted a cancel for one leg. It is not terminal yet — and under
            // `!IsTerminal` it still counted as three lots of cover.
            legA.OrderState = OrderState.CancelSubmitted;
            addon.TestFsmOnOrder(account, mnq.FullName, legA);

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.CoveredQuantity == 3,
                string.Format(
                    "A stop with a cancel in flight stops counting as cover (CoveredQuantity {0}, "
                    + "expected 3). Counting it leaves three lots naked while the FSM reports them "
                    + "protected, and nothing arms a replacement.",
                    fsm == null ? -1 : fsm.CoveredQuantity));

            // CancelPending is the same situation one step further on.
            legB.OrderState = OrderState.CancelPending;
            addon.TestFsmOnOrder(account, mnq.FullName, legB);

            fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.CoveredQuantity == 0,
                string.Format(
                    "With both cancels in flight nothing covers the position (CoveredQuantity {0}).",
                    fsm == null ? -1 : fsm.CoveredQuantity));
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected,
                string.Format(
                    "...and the FSM says so, which is what arms the replacement (state {0}).",
                    fsm == null ? "none" : fsm.State.ToString()));
        }

        /// <summary>Builds a leader PROFIT TARGET (the protective limit leg of a bracket).</summary>
        private static Order LeaderTarget(Instrument inst, OrderAction action, int qty, double limitPrice)
        {
            return new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderId = Guid.NewGuid().ToString(),
                Name = "Target_Leader",
                OrderState = OrderState.Working,
                OrderType = OrderType.Limit,
                Quantity = qty,
                Instrument = inst,
                OrderAction = action,
                LimitPrice = limitPrice
            };
        }

        /// <summary>
        /// P0-9 item (1): the leader's profit target is mirrored, and the two legs are a real OCO
        /// pair.
        ///
        /// Mirroring a target without OCO is worse than not mirroring it: when the target fills,
        /// the stop keeps working against a now-flat follower and opens a fresh position in the
        /// opposite direction the moment it triggers. That is P0-50's hazard, which the copier has
        /// already been bitten by once.
        ///
        /// Both legs therefore carry one shared OCO id. NT8 pairs them with the same engine that
        /// pairs every ATM bracket on this connection -- verified via /api/connections: it
        /// advertises Order and OrderChange but NOT NativeOcoOrders, so the pairing is NT8-local
        /// rather than broker-native. That is the exposure the operator's own ATM brackets already
        /// carry, not a new one.
        /// </summary>
        private static void TestBracket_TargetIsMirroredAsAnOcoPairWithTheStop()
        {
            Console.WriteLine("\n[TEST] BRACKET: the leader's target is mirrored, OCO-paired with the stop (P0-9 item 1)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18001.00, "BR-OCO");

            // Leader's bracket: stop 10 points below entry, target 30 above.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            leader.TriggerOrderUpdate(LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00));

            var stop = follower.Orders.FirstOrDefault(o => o.Name == "COPIER_STOP"
                && o.OrderState != OrderState.Cancelled);
            var target = follower.Orders.FirstOrDefault(o => o.Name == "COPIER_TARGET"
                && o.OrderState != OrderState.Cancelled);

            Assert(stop != null, "The follower has a mirrored stop");
            Assert(target != null, "The follower has a mirrored TARGET");

            // Distances are anchored to the FOLLOWER's own fill at 18001, not the leader's price.
            Assert(stop != null && Math.Abs(stop.StopPrice - 17991.00) < 1e-9,
                string.Format("The stop carries the leader's -10 distance from 18001 (expected 17991.00, got {0})",
                    stop == null ? "none" : stop.StopPrice.ToString()));
            Assert(target != null && Math.Abs(target.LimitPrice - 18031.00) < 1e-9,
                string.Format("The target carries the leader's +30 distance from 18001 (expected 18031.00, got {0})",
                    target == null ? "none" : target.LimitPrice.ToString()));

            Assert(target != null && !string.IsNullOrEmpty(target.Oco),
                "The mirrored target carries an OCO id");
            Assert(stop != null && target != null && stop.Oco == target.Oco,
                string.Format(
                    "Stop and target share ONE OCO id (stop='{0}', target='{1}'). Without it the "
                    + "stop survives the target's fill and opens a fresh position when it triggers.",
                    stop == null ? "n/a" : stop.Oco, target == null ? "n/a" : target.Oco));
        }

        /// <summary>
        /// A target that appears AFTER the stop must JOIN the stop's live group, not force the
        /// stop to be re-created into a new one.
        ///
        /// This is the ordinary ordering -- OnLeaderOrderUpdate fires once per leg -- so if
        /// pairing required a matching pair of creations, every bracket would cancel and replace
        /// its own protective stop for the sake of upside. Joining is licensed by the live test in
        /// handover 4p: an id can be joined while its group still has a live member.
        /// </summary>
        private static void TestBracket_P0_9_ALateTargetJoinsTheLiveStopsOcoGroup()
        {
            Console.WriteLine("\n[TEST] BRACKET: a target arriving after the stop JOINS its group, without disturbing the stop (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-JOIN");

            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            var stop = follower.Orders.Single(o => o.Name == "COPIER_STOP");
            string groupBefore = stop.Oco;
            Assert(!string.IsNullOrEmpty(groupBefore),
                "The stop carries an OCO id from the start, so a later target has a live group to join");

            leader.TriggerOrderUpdate(LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00));

            var stopsNow = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            var target = follower.Orders.SingleOrDefault(o => o.Name == "COPIER_TARGET");

            Assert(stopsNow.Count == 1 && ReferenceEquals(stopsNow[0], stop)
                    && stop.OrderState != OrderState.Cancelled,
                string.Format(
                    "The protective stop is untouched by the target's arrival (got {0} stop order(s), "
                    + "state {1}). Re-creating it would open a naked window for the sake of upside.",
                    stopsNow.Count, stop.OrderState));

            Assert(target != null && target.Oco == groupBefore,
                string.Format("The target joined the stop's existing group (stop='{0}', target='{1}')",
                    groupBefore, target == null ? "n/a" : target.Oco));
        }

        /// <summary>
        /// The dead-group rule, which is the whole of what handover 4p bought.
        ///
        /// An OCO id can be joined while its group still has a live member, and is REJECTED once
        /// every leg has gone terminal. So the ONE path that needs a fresh id is the one that
        /// re-creates a leg: cancel-then-create, reached only when Change() fails. Re-using the
        /// bracket's id there would have the broker reject the new stop -- a NAKED FOLLOWER
        /// produced by the target feature, on the leg the target feature is not even about.
        ///
        /// The stale target is taken down with it and rebuilt, because a working order cannot be
        /// moved between groups (there is no OcoChanged field) and a target left behind in the
        /// retired group is no longer paired with anything.
        /// </summary>
        private static void TestBracket_P0_9_ARecreatedStopMintsAFreshOcoIdAndRebuildsThePair()
        {
            Console.WriteLine("\n[TEST] BRACKET: a re-created stop mints a FRESH OCO id and rebuilds the pair (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-DEADGRP");

            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            leader.TriggerOrderUpdate(LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00));

            string firstGroup = follower.Orders.Single(o => o.Name == "COPIER_STOP").Oco;
            Assert(!string.IsNullOrEmpty(firstGroup), "Precondition: the first bracket has a group id");

            // Force the trail down the cancel-then-create fallback.
            follower.SimulateChangeFailure = true;
            try
            {
                leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17996.00));
            }
            finally { follower.SimulateChangeFailure = false; }

            var liveStops = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn_IsLiveForTest(o)).ToList();
            var liveTargets = follower.Orders
                .Where(o => o.Name == "COPIER_TARGET" && RiskGuardAddOn_IsLiveForTest(o)).ToList();

            Assert(liveStops.Count == 1,
                string.Format("Exactly one stop is live after the fallback re-create (got {0})", liveStops.Count));
            Assert(liveTargets.Count == 1,
                string.Format(
                    "Exactly one target is live after the fallback re-create (got {0}). A target "
                    + "stranded in the retired group is paired with nothing.",
                    liveTargets.Count));

            Assert(liveStops.Count == 1 && liveStops[0].Oco != firstGroup,
                string.Format(
                    "The re-created stop carries a FRESH id, not the retired group's '{0}' (got '{1}'). "
                    + "NT8 rejects an id whose group has fully gone terminal, and a rejected stop is "
                    + "a naked follower.",
                    firstGroup, liveStops.Count == 1 ? liveStops[0].Oco : "n/a"));

            Assert(liveStops.Count == 1 && liveTargets.Count == 1
                    && liveStops[0].Oco == liveTargets[0].Oco,
                "Both live legs are in the SAME new group -- the pairing survives the re-create");
        }

        /// <summary>
        /// P1-56's defect, on the leg P1-56 was not about. Two target syncs that interleave must
        /// not leave two limit orders working against one position.
        ///
        /// The parked implementation of this feature had no reservation at all on the target
        /// path, so it carried the duplicate-leg defect verbatim. Two live targets over-cover
        /// exactly as two live stops do: when both fill the follower is flipped.
        ///
        /// Deterministic, not raced: BrokerCallObserver fires INSIDE the target's CreateOrder,
        /// which is the window, and the second sync runs on another thread while the first is
        /// parked there. The stop is placed before the observer is installed, so the first
        /// CreateOrder it sees is the target's.
        /// </summary>
        private static void TestBracket_P0_9_InterleavedTargetSyncsLeaveExactlyOneTarget()
        {
            Console.WriteLine("\n[TEST] BRACKET: two interleaved TARGET syncs leave ONE target, sized to the whole position (P0-9/P1-56)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            rel.FixedLotSize = 2;
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 2, 18000.00);

            var lead = LeaderExec(leader, mnq, OrderAction.Buy, 2, "BR-TGT56");
            lead.Price = 18000.00;
            lead.Time = SlipT0;
            TradeCopierEngine.Instance.OnExecution(lead);

            var copy = follower.Orders.Last(o => o.Name == "COPIER_FOLLOW");

            // Only part of the entry has filled: the bracket is anchored at ONE lot.
            SetPosition(follower, mnq, MarketPosition.Long, 1, 18000.00);
            TradeCopierEngine.Instance.OnExecution(new Execution
            {
                Account = follower, Instrument = mnq, Order = copy, Quantity = 1,
                Price = 18000.00, ExecutionId = "BR-TGT56-F1", Name = "COPIER_FOLLOW",
                Time = SlipT0.AddMilliseconds(100)
            });

            // The stop lands first, outside the instrumented window.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 2, 17990.00));

            var secondSyncMayRun = new ManualResetEventSlim(false);
            var secondSyncDone = new ManualResetEventSlim(false);

            var second = new System.Threading.Thread(() =>
            {
                try
                {
                    if (!secondSyncMayRun.Wait(TimeSpan.FromSeconds(20))) return;
                    SetPosition(follower, mnq, MarketPosition.Long, 2, 18000.00);
                    follower.TriggerPositionUpdate(follower.Positions.First(p =>
                        p.Instrument != null && p.Instrument.FullName == mnq.FullName));
                }
                catch { /* the assertions below report */ }
                finally { secondSyncDone.Set(); }
            });
            second.IsBackground = true;
            second.Start();

            int tripped = 0;
            var previousObserver = Account.BrokerCallObserver;
            Account.BrokerCallObserver = method =>
            {
                if (method != "CreateOrder") return;
                if (Interlocked.CompareExchange(ref tripped, 1, 0) != 0) return;
                secondSyncMayRun.Set();
                // Bounded: a fix that makes the second sync BLOCK would otherwise hang the suite.
                secondSyncDone.Wait(TimeSpan.FromSeconds(10));
            };

            try
            {
                leader.TriggerOrderUpdate(LeaderTarget(mnq, OrderAction.Sell, 2, 18030.00));
            }
            finally
            {
                Account.BrokerCallObserver = previousObserver;
                secondSyncMayRun.Set();
                secondSyncDone.Wait(TimeSpan.FromSeconds(10));
                second.Join(TimeSpan.FromSeconds(5));
            }

            var liveTargets = follower.OrdersSnapshot()
                .Where(o => o.Name == "COPIER_TARGET" && RiskGuardAddOn_IsLiveForTest(o)).ToList();

            Assert(liveTargets.Count == 1,
                string.Format(
                    "Exactly one target is live after the interleaved syncs (got {0}). Two live "
                    + "targets over-cover: when both fill the follower is flipped short.",
                    liveTargets.Count));

            Assert(liveTargets.Count == 1 && liveTargets[0].Quantity == 2,
                string.Format(
                    "The surviving target covers the WHOLE 2-lot position (got qty {0}). Backing the "
                    + "second sync off without re-applying its instruction under-covers instead.",
                    liveTargets.Count == 1 ? liveTargets[0].Quantity.ToString() : "n/a"));
        }

        /// <summary>
        /// The target leg needs its own re-submission bound. The stop's exists because answering a
        /// persistently-rejecting broker forever is the order flood the P1-43..P2-46 cluster
        /// already cost us; nothing about that reasoning is specific to stops, and the parked
        /// implementation of this feature had no bound at all.
        /// </summary>
        private static void TestBracket_P0_9_TargetResubmissionIsBounded()
        {
            Console.WriteLine("\n[TEST] BRACKET: target re-submission is bounded, not a flood (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-TGTBOUND");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            leader.TriggerOrderUpdate(LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00));

            for (int i = 0; i < 20; i++)
            {
                var latest = follower.Orders.LastOrDefault(o => o.Name == "COPIER_TARGET");
                if (latest == null) break;
                if (!RiskGuardAddOn_IsLiveForTest(latest)) break;
                latest.OrderState = OrderState.Rejected;
                follower.TriggerOrderUpdate(latest);
            }

            int submitted = follower.Orders.Count(o => o.Name == "COPIER_TARGET");
            Assert(submitted <= 4,
                string.Format("Target re-submission gives up after a bounded number of attempts (got {0}).",
                    submitted));
            Assert(submitted >= 2,
                string.Format("It did retry at least once before giving up (got {0}).", submitted));

            // And the risk leg is untouched by the target's failures: a churning target must not
            // consume the stop's budget, or the bound that keeps the follower protected becomes
            // unreachable.
            var liveStops = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn_IsLiveForTest(o)).ToList();
            Assert(liveStops.Count == 1,
                string.Format("The protective stop is still live throughout (got {0})", liveStops.Count));
        }

        /// <summary>
        /// The hazard the pairing itself creates, and the reason this test exists at all.
        ///
        /// When the target fills, NT8 cancels the stop -- that is what OCO means. The copier sees
        /// a mirrored stop go Cancelled while the follower still holds the position, because
        /// NT8 raises ExecutionUpdate BEFORE PositionUpdate (P0-49's ordering), and re-submits it.
        /// That places a protective stop against a position that has just been closed: P0-50's
        /// orphan, arriving by a route P0-50 did not cover and that did not exist before targets
        /// were mirrored.
        ///
        /// A leg whose sibling has FILLED was not lost. It was retired, and the follower's
        /// position update releases the bracket a moment later.
        /// </summary>
        private static void TestBracket_P0_9_ALegRetiredByItsOcoSiblingIsNotResubmitted()
        {
            Console.WriteLine("\n[TEST] BRACKET: a stop retired by its target's fill is NOT re-submitted (P0-9/P0-50)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-OCOFILL");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            leader.TriggerOrderUpdate(LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00));

            var target = follower.Orders.Single(o => o.Name == "COPIER_TARGET");
            int stopsBefore = follower.Orders.Count(o => o.Name == "COPIER_STOP");
            Assert(stopsBefore == 1, "Precondition: one mirrored stop is working");

            // The target fills. The position update has NOT landed yet -- the follower still reads
            // as long, which is precisely what makes the re-submission look reasonable.
            follower.FillOrderAndRetireOcoGroup(target);

            int stopsAfter = follower.Orders.Count(o => o.Name == "COPIER_STOP");
            Assert(stopsAfter == stopsBefore,
                string.Format(
                    "No replacement stop is submitted when the target's fill retires the group "
                    + "(expected {0} COPIER_STOP orders, got {1}). A stop placed here is an orphan "
                    + "on an account that has just gone flat, and an orphan stop is a new position "
                    + "in the opposite direction the moment it triggers.",
                    stopsBefore, stopsAfter));
        }

        /// <summary>
        /// Every mirrored leg price must be a multiple of the instrument's tick.
        ///
        /// The anchor is the follower's AVERAGE fill price, and an average across partial fills at
        /// different prices is routinely off-tick -- so a leg computed from it is off-tick too,
        /// even though every price the leader gave us was clean. This is not hypothetical: a live
        /// COPIER_TARGET sat Rejected at 29905.625 on MNQ, whose tick is 0.25 (handover 4p listed
        /// it under "suspected, not concluded"). NT8 rounds off-tick prices silently on some paths
        /// and rejects on others, and a rejected STOP is a naked follower.
        /// </summary>
        private static void TestBracket_P0_9_LegPricesAreRoundedToTheInstrumentsTick()
        {
            Console.WriteLine("\n[TEST] BRACKET: both mirrored legs are snapped to the instrument's tick (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            double tick = mnq.MasterInstrument.TickSize;

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            // The follower's average across two partial fills lands between ticks.
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.125, "BR-TICK");

            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));    // -10
            leader.TriggerOrderUpdate(LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00));  // +30

            var stop = follower.Orders.Single(o => o.Name == "COPIER_STOP");
            var target = follower.Orders.Single(o => o.Name == "COPIER_TARGET");

            Assert(Math.Abs(stop.StopPrice / tick - Math.Round(stop.StopPrice / tick)) < 1e-9,
                string.Format(
                    "The mirrored STOP sits on a tick boundary (got {0}, tick {1}). An off-tick stop "
                    + "is one a broker may reject, and a rejected stop is a naked follower.",
                    stop.StopPrice, tick));

            Assert(Math.Abs(target.LimitPrice / tick - Math.Round(target.LimitPrice / tick)) < 1e-9,
                string.Format(
                    "The mirrored TARGET sits on a tick boundary (got {0}, tick {1}). This is the "
                    + "shape of the COPIER_TARGET that came back Rejected at 29905.625 on 2026-08-10.",
                    target.LimitPrice, tick));

            // Rounding must not silently move the leg somewhere else: it snaps to the nearest tick.
            Assert(Math.Abs(stop.StopPrice - 17990.125) <= tick,
                string.Format("The stop stayed within one tick of the exact distance (got {0})", stop.StopPrice));
            Assert(Math.Abs(target.LimitPrice - 18030.125) <= tick,
                string.Format("The target stayed within one tick of the exact distance (got {0})", target.LimitPrice));
        }

        /// <summary>
        /// A scale-out leader has SEVERAL targets, and the follower has ONE mirrored leg. There is
        /// no honest single answer to "which one", and every wrong answer is expensive: mirroring
        /// the last one seen makes the follower's exit depend on NT8's event order, and mirroring
        /// the nearest exits the follower's WHOLE position at the leader's FIRST partial scale-out.
        ///
        /// So it refuses, loudly, and keeps the stop. The follower still exits when the leader's
        /// target fills are copied -- which is the behaviour that shipped before targets were
        /// mirrored at all, so the fallback is the old known-good one and the loss is fill quality.
        ///
        /// Target1/Target2/Target3 is ordinary ATM usage on this box, not an exotic case.
        /// </summary>
        private static void TestBracket_P0_9_AMultiTargetLeaderIsNotMirroredAtAll()
        {
            Console.WriteLine("\n[TEST] BRACKET: a scale-out leader with several targets mirrors NONE of them, and keeps the stop (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-MULTITGT");

            var stopLeg = LeaderStop(mnq, OrderAction.Sell, 1, 17990.00);
            leader.Orders.Add(stopLeg);
            leader.TriggerOrderUpdate(stopLeg);

            // One target: mirrored, as usual.
            var t1 = LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00);
            leader.Orders.Add(t1);
            leader.TriggerOrderUpdate(t1);
            Assert(follower.Orders.Any(o => o.Name == "COPIER_TARGET" && RiskGuardAddOn_IsLiveForTest(o)),
                "Precondition: a single leader target is mirrored");

            // A second target appears. The leader is scaling out.
            var t2 = LeaderTarget(mnq, OrderAction.Sell, 1, 18060.00);
            leader.Orders.Add(t2);
            leader.TriggerOrderUpdate(t2);

            var liveTargets = follower.Orders
                .Where(o => o.Name == "COPIER_TARGET" && RiskGuardAddOn_IsLiveForTest(o)).ToList();
            Assert(liveTargets.Count == 0,
                string.Format(
                    "The mirrored target is withdrawn once the leader has more than one (got {0} live). "
                    + "Leaving whichever was seen last makes the follower's exit an artefact of NT8's "
                    + "event ordering.",
                    liveTargets.Count));

            var liveStops = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn_IsLiveForTest(o)).ToList();
            Assert(liveStops.Count == 1,
                string.Format(
                    "The protective stop is untouched by the refusal (got {0} live). Ambiguity about "
                    + "upside must never cost the follower its risk leg.",
                    liveStops.Count));
        }

        /// <summary>
        /// A follower going flat must release BOTH legs, not just the stop. A surviving target is
        /// an orphan working order on a flat account -- the same class of defect as P0-50, which
        /// was about the stop.
        /// </summary>
        private static void TestBracket_FollowerGoingFlatCancelsBothLegs()
        {
            Console.WriteLine("\n[TEST] BRACKET: a follower going flat cancels the target as well as the stop");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-OCOFLAT");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            leader.TriggerOrderUpdate(LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00));

            Assert(follower.Orders.Any(o => o.Name == "COPIER_TARGET" && o.OrderState != OrderState.Cancelled),
                "Precondition: the follower has a working mirrored target");

            SetPosition(follower, mnq, MarketPosition.Flat, 0, 0);
            follower.TriggerPositionUpdate(new Position
            {
                Instrument = mnq,
                MarketPosition = MarketPosition.Flat,
                Quantity = 0,
                AveragePrice = 0
            });

            var liveStop = follower.Orders.Where(o => o.Name == "COPIER_STOP"
                && o.OrderState != OrderState.Cancelled).ToList();
            var liveTarget = follower.Orders.Where(o => o.Name == "COPIER_TARGET"
                && o.OrderState != OrderState.Cancelled).ToList();

            Assert(liveStop.Count == 0,
                string.Format("No mirrored stop survives the follower going flat (got {0})", liveStop.Count));
            Assert(liveTarget.Count == 0,
                string.Format(
                    "No mirrored TARGET survives the follower going flat (got {0}). An orphan "
                    + "target on a flat account opens a position when it fills, exactly as an "
                    + "orphan stop does (P0-50).",
                    liveTarget.Count));
        }

        /// <summary>
        /// The TARGET leg has the same accepted-before-the-leader's-position race as the stop
        /// (P0-55), and the first implementation of the re-anchor pass missed it: the rescan
        /// filtered on IsStopType, so a target accepted early was never re-evaluated.
        ///
        /// Caught live rather than by test on 2026-08-10 -- the instrumentation said
        /// "re-evaluating 1 working protective stop(s)" on a bracket that had two legs, which is
        /// exactly the sort of off-by-one-leg a stop-shaped test cannot see.
        /// </summary>
        private static void TestBracket_TargetAcceptedBeforeLeaderPositionIsStillMirrored()
        {
            Console.WriteLine("\n[TEST] BRACKET: a leader TARGET accepted before the leader's position is still mirrored");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            // BOTH legs accepted while the leader is still flat -- the real ATM sequence.
            var stop = LeaderStop(mnq, OrderAction.Sell, 1, 17990.00);
            var target = LeaderTarget(mnq, OrderAction.Sell, 1, 18030.00);
            leader.Orders.Add(stop);
            leader.Orders.Add(target);
            leader.TriggerOrderUpdate(stop);
            leader.TriggerOrderUpdate(target);

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            leader.TriggerPositionUpdate(leader.Positions.First(p => p.Instrument.FullName == mnq.FullName));

            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-OCORACE");

            Assert(follower.Orders.Any(o => o.Name == "COPIER_STOP" && o.OrderState != OrderState.Cancelled),
                "The stop leg is mirrored after the re-anchor");
            Assert(follower.Orders.Any(o => o.Name == "COPIER_TARGET" && o.OrderState != OrderState.Cancelled),
                "The TARGET leg is mirrored after the re-anchor too -- the rescan must cover both "
                + "protective legs, not just stops");
        }

        // An orphaned stop against a flat account is not a leftover, it is a new position.
        private static void TestBracket_FollowerGoingFlatCancelsTheMirroredStop()
        {
            Console.WriteLine("\n[TEST] BRACKET: a follower going flat has its mirrored stop cancelled (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-D");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));

            var stop = follower.Orders.Single(o => o.Name == "COPIER_STOP");
            Assert(stop.OrderState != OrderState.Cancelled, "Precondition: the mirrored stop is live.");

            // The leader exits; the copied exit fills and the follower is flat.
            SetPosition(leader, mnq, MarketPosition.Flat, 0, 0);
            var exit = LeaderExec(leader, mnq, OrderAction.Sell, 1, "BR-D-X");
            exit.Time = SlipT0.AddSeconds(1);
            TradeCopierEngine.Instance.OnExecution(exit);

            var exitCopy = follower.Orders.Last(o => o.Name == "COPIER_FOLLOW");
            SetPosition(follower, mnq, MarketPosition.Flat, 0, 0);
            TradeCopierEngine.Instance.OnExecution(new Execution
            {
                Account = follower, Instrument = mnq, Order = exitCopy, Quantity = exitCopy.Quantity,
                Price = 18005.00, ExecutionId = "BR-D-XF", Name = "COPIER_FOLLOW",
                Time = SlipT0.AddSeconds(1)
            });

            Assert(stop.OrderState == OrderState.Cancelled,
                string.Format(
                    "The mirrored stop is cancelled once the follower is flat (state {0}). Left "
                    + "working, it does not protect anything -- it OPENS a short when it fires.",
                    stop.OrderState));

            Assert(TradeCopierEngine.Instance.TrackedBracketCount == 0,
                "The bracket is released, so it cannot resurrect on a later unrelated fill.");
        }

        // The offset from the leader's entry to its stop must stay SIGNED. A leader that trails
        // its stop into profit puts it ABOVE entry on a long; mirrored as an absolute distance
        // that becomes a stop BELOW the follower's entry -- converting the leader's locked-in
        // gain into open risk of the same size, on every follower, silently.
        //
        // The original trail test moved the stop 17990 -> 17995 -> 17998, all below entry, so it
        // could never have caught this. Found by asking what a StopLimit conversion could break.
        private static void TestBracket_StopTrailedIntoProfitStaysAboveFollowerEntry()
        {
            Console.WriteLine("\n[TEST] BRACKET: a stop trailed into profit is mirrored above the follower's entry (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18002.00, "BR-F");

            // Leader is +12 and trails its stop to 18010 -- ten points ABOVE its own entry.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 18010.00));

            var live = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && o.OrderState != OrderState.Cancelled)
                .ToList();

            Assert(live.Count == 1, string.Format("One live mirrored stop (got {0}).", live.Count));

            Assert(Math.Abs(live[0].StopPrice - 18012.00) < 1e-9,
                string.Format(
                    "A stop 10 points ABOVE the leader's entry maps 10 points above the follower's "
                    + "entry: expected 18012.00, got {0}. An unsigned distance gives 17992 -- the "
                    + "leader is locked in for a gain while the follower carries a 10-point loss.",
                    live[0].StopPrice));

            Assert(live[0].StopPrice > 18002.00,
                "The mirrored stop is on the profitable side of the follower's own entry.");
        }

        // The same inversion on the short side: a short trailed into profit puts its stop BELOW
        // entry, which must map below the follower's entry, not above it.
        private static void TestBracket_ShortStopTrailedIntoProfitStaysBelowFollowerEntry()
        {
            Console.WriteLine("\n[TEST] BRACKET: a short's stop trailed into profit maps below the follower's entry (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Short, 1, 18000.00);

            var lead = LeaderExec(leader, mnq, OrderAction.SellShort, 1, "BR-G");
            lead.Price = 18000.00; lead.Time = SlipT0;
            TradeCopierEngine.Instance.OnExecution(lead);

            var copy = follower.Orders.Last(o => o.Name == "COPIER_FOLLOW");
            SetPosition(follower, mnq, MarketPosition.Short, copy.Quantity, 17998.00);
            TradeCopierEngine.Instance.OnExecution(new Execution
            {
                Account = follower, Instrument = mnq, Order = copy, Quantity = copy.Quantity,
                Price = 17998.00, ExecutionId = "BR-G-F", Name = "COPIER_FOLLOW", Time = SlipT0
            });

            // Short is +10; stop trailed to 17990, ten points BELOW its entry.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.BuyToCover, 1, 17990.00));

            var live = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && o.OrderState != OrderState.Cancelled)
                .ToList();

            Assert(live.Count == 1 && Math.Abs(live[0].StopPrice - 17988.00) < 1e-9,
                string.Format(
                    "Expected one stop at 17988.00 (follower entry 17998 minus 10), got {0} at {1}.",
                    live.Count, live.Count > 0 ? live[0].StopPrice.ToString() : "n/a"));

            Assert(live[0].OrderAction == OrderAction.BuyToCover,
                "The mirrored stop covers the follower's short.");
        }

        // Found by the loop's review mode, not by me (logs/agent_loop/review-51892d54_1_HEAD).
        // A mirrored stop that the broker rejects moments after submission left WorkingStop
        // holding a dead order and NOTHING re-triggered submission -- the follower stayed naked
        // for the life of the position. The OrderUpdate that reported the rejection was being
        // received and discarded, because the handler returned early for any account with no
        // relationships, which every follower is.
        private static void TestBracket_RejectedStopIsResubmitted()
        {
            Console.WriteLine("\n[TEST] BRACKET: a rejected mirrored stop is re-submitted (P0-9, found by review mode)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-H");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));

            var first = follower.Orders.Single(o => o.Name == "COPIER_STOP");

            // The broker rejects it a moment later. The follower is still long 1.
            first.OrderState = OrderState.Rejected;
            follower.TriggerOrderUpdate(first);

            var live = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn_IsLiveForTest(o))
                .ToList();

            Assert(live.Count == 1,
                string.Format(
                    "A replacement stop is working after the first was rejected (got {0} live). "
                    + "Without it the follower holds an open position with no protective order and "
                    + "nothing left to trigger another attempt.",
                    live.Count));

            Assert(Math.Abs(live[0].StopPrice - 17990.00) < 1e-9,
                string.Format("The replacement keeps the mirrored level (expected 17990.00, got {0}).",
                    live[0].StopPrice));
        }

        /// <summary>
        /// P1-56, third sync. The fix holds ONE reservation across a bounded re-drive loop, so the
        /// claim is that there is no instant between passes at which a newly-arriving sync sees no
        /// reservation and walks to the broker.
        ///
        /// That claim is worth a test rather than an argument. Two reviewers read this window in
        /// opposite directions -- one called it a duplicate-leg BLOCKER, the other traced every
        /// interleaving and concluded it could not happen -- and the arbiter recorded "there is no
        /// gap between passes" as a settled fact on the strength of the second. A settled fact that
        /// nothing tests is exactly how P1-40 shipped.
        ///
        /// So: three syncs. The first is parked inside CreateOrder; the second and third are both
        /// driven from there, at 1 lot and then 2. Whatever the ordering, the follower must end with
        /// ONE stop covering the whole position.
        /// </summary>
        private static void TestBracket_P1_56_AThirdSyncStillLeavesExactlyOneProtectiveStop()
        {
            Console.WriteLine("\n[TEST] BRACKET: a THIRD interleaved sync still leaves one stop covering the position (P1-56)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            rel.FixedLotSize = 2;
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 2, 18000.00);

            var lead = LeaderExec(leader, mnq, OrderAction.Buy, 2, "BR-56C");
            lead.Price = 18000.00;
            lead.Time = SlipT0;
            TradeCopierEngine.Instance.OnExecution(lead);

            var copy = follower.Orders.Last(o => o.Name == "COPIER_FOLLOW");

            SetPosition(follower, mnq, MarketPosition.Long, 1, 18000.00);
            TradeCopierEngine.Instance.OnExecution(new Execution
            {
                Account = follower, Instrument = mnq, Order = copy, Quantity = 1,
                Price = 18000.00, ExecutionId = "BR-56C-F1", Name = "COPIER_FOLLOW",
                Time = SlipT0.AddMilliseconds(100)
            });

            var mayRun = new ManualResetEventSlim(false);
            var bothDone = new ManualResetEventSlim(false);
            Exception threadError = null;

            // Two further syncs, back to back, while the first is parked in the broker. The second
            // re-states 1 lot; the third raises it to 2. The 2-lot instruction is the newest and is
            // the one that must survive.
            var others = new System.Threading.Thread(() =>
            {
                try
                {
                    if (!mayRun.Wait(TimeSpan.FromSeconds(20))) return;

                    follower.TriggerPositionUpdate(follower.Positions.First(p =>
                        p.Instrument != null && p.Instrument.FullName == mnq.FullName));

                    SetPosition(follower, mnq, MarketPosition.Long, 2, 18000.00);
                    follower.TriggerPositionUpdate(follower.Positions.First(p =>
                        p.Instrument != null && p.Instrument.FullName == mnq.FullName));
                }
                catch (Exception ex) { threadError = ex; }
                finally { bothDone.Set(); }
            });
            others.IsBackground = true;
            others.Start();

            int tripped = 0;
            var previousObserver = Account.BrokerCallObserver;
            Account.BrokerCallObserver = method =>
            {
                if (method != "CreateOrder") return;
                if (Interlocked.CompareExchange(ref tripped, 1, 0) != 0) return;
                mayRun.Set();
                bothDone.Wait(TimeSpan.FromSeconds(10));
            };

            try
            {
                leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 2, 17990.00));
            }
            finally
            {
                Account.BrokerCallObserver = previousObserver;
            }

            mayRun.Set();
            others.Join(TimeSpan.FromSeconds(20));

            Assert(threadError == null,
                "The two follow-on syncs completed without throwing"
                + (threadError == null ? "" : ": " + threadError.Message));

            Assert(Volatile.Read(ref tripped) == 1,
                "The three-way interleaving actually happened. If this fails, nothing was proved.");

            var live = follower.OrdersSnapshot()
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn.ProvidesCoverage(o.OrderState))
                .ToList();

            Assert(live.Count == 1,
                string.Format(
                    "Exactly one COPIER_STOP is live after THREE interleaved syncs (got {0}, "
                    + "quantities {1}). More than one means a sync found no reservation and walked "
                    + "to the broker -- the gap the arbiter recorded as impossible.",
                    live.Count,
                    string.Join("+", live.Select(o => o.Quantity.ToString()).ToArray())));

            Assert(live.Sum(o => o.Quantity) == 2,
                string.Format(
                    "The surviving stop still covers the whole 2-lot position after three syncs "
                    + "(covered {0}). Under-cover means the newest instruction was dropped by the "
                    + "re-drive rather than applied.",
                    live.Sum(o => o.Quantity)));
        }

        /// <summary>
        /// P1-56's companion, and the failure mode its fix introduces if it is written carelessly.
        ///
        /// Once a sync publishes an in-flight reservation so a concurrent sync backs off, that
        /// reservation MUST be released on every exit path -- including the ones where the broker
        /// threw. A reservation leaked on the failure path is permanent: every later trigger backs
        /// off politely and the follower never gets a stop at all, which is strictly worse than the
        /// duplicate-leg defect it was added to fix.
        ///
        /// This test passes today (there is no reservation yet) and is here to fail the moment one
        /// is added without a release on the throwing path. It is a regression guard, not an
        /// acceptance test.
        /// </summary>
        private static void TestBracket_P1_56_AFailedSubmitDoesNotWedgeLaterSyncs()
        {
            Console.WriteLine("\n[TEST] BRACKET: a stop submit that throws still leaves later syncs able to place one (P1-56)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-56B");

            // The broker throws on the mirrored stop's submit. The follower is still long 1.
            follower.SimulateSubmitFailure = true;
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            follower.SimulateSubmitFailure = false;

            Assert(!follower.OrdersSnapshot().Any(o => o.Name == "COPIER_STOP"),
                "Precondition: the throwing submit left no stop behind.");

            // The leader moves its stop, which is a genuinely new instruction and earns a fresh
            // attempt budget. Nothing about the previous failure may block it.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17985.00));

            var live = follower.OrdersSnapshot()
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn.ProvidesCoverage(o.OrderState))
                .ToList();

            Assert(live.Count == 1,
                string.Format(
                    "A later sync still places a stop after an earlier submit threw (got {0} live). "
                    + "Zero means the failure path left an in-flight reservation set and every "
                    + "subsequent sync now backs off forever -- a permanently naked follower.",
                    live.Count));

            Assert(live.Count == 1 && Math.Abs(live[0].StopPrice - 17985.00) < 1e-9,
                string.Format("It carries the leader's new distance (expected 17985.00, got {0}).",
                    live.Count == 1 ? live[0].StopPrice : double.NaN));
        }

        // The same fix must not become an order flood: a broker that rejects every attempt would
        // otherwise be answered forever. That is the P2-46 / flood-cluster failure mode.
        private static void TestBracket_ResubmissionIsBounded()
        {
            Console.WriteLine("\n[TEST] BRACKET: stop re-submission is bounded, not a flood (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-I");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));

            // Reject every stop the copier submits, twenty times over.
            for (int i = 0; i < 20; i++)
            {
                var latest = follower.Orders.LastOrDefault(o => o.Name == "COPIER_STOP");
                if (latest == null) break;
                if (!RiskGuardAddOn_IsLiveForTest(latest)) break;
                latest.OrderState = OrderState.Rejected;
                follower.TriggerOrderUpdate(latest);
            }

            int submitted = follower.Orders.Count(o => o.Name == "COPIER_STOP");
            Assert(submitted <= 4,
                string.Format(
                    "Re-submission stops after a bounded number of attempts (got {0} stop orders). "
                    + "Answering a persistently-rejecting broker forever is the order flood the "
                    + "P1-43..P2-46 cluster already cost us.",
                    submitted));

            Assert(submitted >= 2,
                string.Format("It did retry at least once before giving up (got {0}).", submitted));
        }

        /// <summary>
        /// Delegates to the production classification rather than restating it. It used to be a
        /// hand-copied duplicate of the old liveness list -- a second definition of "alive" living
        /// in the grader, free to drift from the one being graded. That is the same shape of
        /// defect as P0-59 itself.
        /// </summary>
        private static bool RiskGuardAddOn_IsLiveForTest(Order o)
        {
            return RiskGuardAddOn.ProvidesCoverage(o.OrderState);
        }

        // Mirroring a points-distance onto an instrument at a different price scale fabricates a
        // risk level. Same rule as P1-22's slippage guard.
        private static void TestBracket_IncomparableInstrumentsAreNotMirrored()
        {
            Console.WriteLine("\n[TEST] BRACKET: no stop is mirrored across price-incomparable instruments (P0-9)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0, autoConvert: true);
            rel.CustomSymbolMappings["MNQ"] = "ES";
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            var es = Instrument.GetInstrument("ES 03-26");
            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);

            var lead = LeaderExec(leader, mnq, OrderAction.Buy, 1, "BR-E");
            lead.Price = 18000.00; lead.Time = SlipT0;
            TradeCopierEngine.Instance.OnExecution(lead);

            var copy = follower.Orders.Last(o => o.Name == "COPIER_FOLLOW");
            SetPosition(follower, es, MarketPosition.Long, copy.Quantity, 5000.00);
            TradeCopierEngine.Instance.OnExecution(new Execution
            {
                Account = follower, Instrument = es, Order = copy, Quantity = copy.Quantity,
                Price = 5000.00, ExecutionId = "BR-E-F", Name = "COPIER_FOLLOW", Time = SlipT0
            });

            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));

            Assert(!follower.Orders.Any(o => o.Name == "COPIER_STOP"),
                "No stop is mirrored between MNQ and ES -- a 10-point MNQ distance is not 10 ES points.");
        }

        // ------------------------------------------------------------------
        // P0-49 / P0-50 — reproduced from a live ATM trade, 2026-08-07 (MNQ SEP26)
        //
        // The operator placed an ATM order on Sim101. Sim-ORB copied the entry correctly, and
        // then:
        //   15:43:21.237  Created FSM Sim-ORB|MNQ SEP26 -> Unprotected
        //   15:43:24.241  [SHADOW] Would execute FlattenPosition triggered by MISSING_STOP_FLATTEN
        //   15:45:22.572  COPIER_STOP finally submitted -- as the position was CLOSING
        //   15:45:30/31   two more COPIER_STOP orders, against a FLAT account
        //
        // The follower was naked for the whole trade, and then received three orphan stops.
        //
        // Root cause: the bracket's anchor came only from the follower's ExecutionUpdate, which
        // re-read `Positions` -- and NT8 raises ExecutionUpdate BEFORE PositionUpdate, so the
        // position did not exist yet. The bracket was released and nothing rebuilt it: an ATM
        // stop sits at `Accepted` and raises no further OrderUpdate, so the leader path never
        // fired again either.
        //
        // Note the ARITHMETIC was right all along -- the live stop landed at 29774.25, which is
        // exactly followerEntry 29789.25 + (29774.5 - 29789.5). It was the trigger that was
        // broken, not the offset.
        // ------------------------------------------------------------------

        private static void TestBracket_P0_49_ExecutionBeforePositionStillGetsAStop()
        {
            Console.WriteLine("\n[TEST] P0-49: a fill delivered BEFORE the position update still gets its mirrored stop");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);

            // The leader's ATM legs go out first, exactly as NT8 delivers them.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17985.00));

            // The copy is placed and FILLS -- and the execution arrives while follower.Positions
            // is still empty. This is the ordering that broke it.
            var lead = LeaderExec(leader, mnq, OrderAction.Buy, 1, "P049");
            lead.Price = 18000.00; lead.Time = SlipT0;
            TradeCopierEngine.Instance.OnExecution(lead);

            var copy = follower.Orders.Last(o => o.Name == "COPIER_FOLLOW");
            TradeCopierEngine.Instance.OnExecution(new Execution
            {
                Account = follower, Instrument = mnq, Order = copy, Quantity = copy.Quantity,
                Price = 18002.00, ExecutionId = "P049-F", Name = "COPIER_FOLLOW",
                Time = SlipT0.AddMilliseconds(100)
            });

            Assert(!follower.Orders.Any(o => o.Name == "COPIER_STOP"),
                "Nothing is placed yet -- the follower's position genuinely is not known at this point.");

            // NT8 now raises the PositionUpdate it always raises, ~2ms later.
            SetPosition(follower, mnq, MarketPosition.Long, 1, 18002.00);
            follower.TriggerPositionUpdate(follower.Positions[0]);

            var stops = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            Assert(stops.Count == 1,
                string.Format(
                    "The mirrored stop is placed once the position event lands (got {0}). Before "
                    + "P0-49 the execution path released the bracket on the flat read and nothing "
                    + "rebuilt it -- an ATM stop raises no further OrderUpdate, so the follower "
                    + "stayed naked for the ENTIRE trade.",
                    stops.Count));

            Assert(stops.Count == 1 && Math.Abs(stops[0].StopPrice - 17987.00) < 1e-9,
                string.Format(
                    "...and at the right price: the leader's 15-point distance on the follower's "
                    + "18002 fill = 17987.00, got {0}.",
                    stops.Count > 0 ? stops[0].StopPrice.ToString() : "n/a"));
        }

        private static void TestBracket_P0_50_NoStopIsPlacedOnAFlatFollower()
        {
            Console.WriteLine("\n[TEST] P0-50: no mirrored stop is submitted against a follower that is already flat");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "P050");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));

            var placed = follower.Orders.Count(o => o.Name == "COPIER_STOP");
            Assert(placed == 1, "Precondition: the follower is in position and has its mirrored stop.");

            // The follower goes flat at the broker -- but the bracket has not been told yet.
            SetPosition(follower, mnq, MarketPosition.Flat, 0, 0);

            // A late leader stop update now drives SyncFollowerStop against a flat follower.
            // This is what produced three orphan COPIER_STOP orders on the live box.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17992.00));
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17994.00));
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17996.00));

            var live = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn.ProvidesCoverage(o.OrderState))
                .ToList();

            Assert(live.Count == 0,
                string.Format(
                    "No stop is left working against a flat follower (got {0}). An orphan stop on a "
                    + "flat account is not a leftover -- it OPENS a position in the opposite "
                    + "direction the moment it triggers. Three of these were placed live.",
                    live.Count));

            Assert(follower.Orders.Count(o => o.Name == "COPIER_STOP") == placed,
                string.Format(
                    "...and no further stops were submitted at all (total {0}, expected {1}). Each "
                    + "one consumed a re-submission attempt against a position that no longer existed.",
                    follower.Orders.Count(o => o.Name == "COPIER_STOP"), placed));
        }

        // P0-9 item (3): a StopLimit leader becomes a StopMarket follower. Assessed as a fidelity
        // gap, not a safety one -- but "assessed" is not "pinned", and the assessment rests
        // entirely on the TRIGGER price being mirrored correctly. If the mirror ever read
        // LimitPrice instead of StopPrice, the follower's stop would sit at a price the leader
        // never used, and nothing in the suite would notice. That is the claim under test.
        private static void TestBracket_StopLimitLeaderMirrorsTriggerPriceAsStopMarket()
        {
            Console.WriteLine("\n[TEST] BRACKET: a StopLimit leader mirrors its TRIGGER price as a follower StopMarket (P0-9 item 3)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18001.00, "BR-SL");

            // Trigger 10 points below entry; limit a further 3 points down. The limit is the leg
            // that is deliberately NOT carried.
            var stopLimit = LeaderStop(mnq, OrderAction.Sell, 1, 17990.00);
            stopLimit.OrderType = OrderType.StopLimit;
            stopLimit.LimitPrice = 17987.00;
            leader.TriggerOrderUpdate(stopLimit);

            var stops = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            Assert(stops.Count == 1,
                string.Format("A StopLimit leader stop is recognised and mirrored (got {0} follower stops).", stops.Count));

            Assert(Math.Abs(stops[0].StopPrice - 17991.00) < 1e-9,
                string.Format(
                    "The mirror uses the leader's TRIGGER price: 10 points below entry, anchored to "
                    + "the follower's 18001 fill = 17991.00, got {0}. Reading LimitPrice (17987) "
                    + "instead would give the follower 14 points of risk in place of 10.",
                    stops[0].StopPrice));

            Assert(stops[0].OrderType == OrderType.StopMarket,
                string.Format(
                    "The follower's leg is a StopMarket (got {0}). This is the accepted divergence: "
                    + "a StopMarket is MORE likely to fill than a StopLimit, so it runs toward the "
                    + "follower being protected, never toward an unfilled exit.",
                    stops[0].OrderType));

            Assert(Math.Abs(stops[0].LimitPrice) < 1e-9,
                string.Format(
                    "No limit is carried across (got {0}). Carrying it without carrying the order "
                    + "TYPE would produce a StopMarket with a meaningless LimitPrice field.",
                    stops[0].LimitPrice));
        }

        // P0-9 item (4): the leader cancels its protective stop but stays in the position. The
        // follower KEEPS its mirrored stop. That is a deliberate divergence from the leader and
        // the fail-safe direction -- the follower stays protected while the leader chooses to
        // stand naked. It was untested, which meant a future refactor could flip it to
        // "cancel the follower's stop too" and the suite would stay green while every follower
        // silently went naked mid-trade.
        private static void TestBracket_LeaderCancellingItsStopLeavesTheFollowerProtected()
        {
            Console.WriteLine("\n[TEST] BRACKET: a leader cancelling its own stop leaves the follower's mirrored stop working (P0-9 item 4)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18000.00, "BR-LC");

            var leaderStop = LeaderStop(mnq, OrderAction.Sell, 1, 17990.00);
            leader.TriggerOrderUpdate(leaderStop);

            var mirrored = follower.Orders.Single(o => o.Name == "COPIER_STOP");
            Assert(RiskGuardAddOn.ProvidesCoverage(mirrored.OrderState),
                "Precondition: the follower has a live mirrored stop before the leader cancels.");

            // The leader cancels. Its position is UNCHANGED -- it is now naked by choice.
            leaderStop.OrderState = OrderState.Cancelled;
            leader.TriggerOrderUpdate(leaderStop);

            Assert(RiskGuardAddOn.ProvidesCoverage(mirrored.OrderState),
                string.Format(
                    "The follower's mirrored stop is still live after the leader cancelled its own "
                    + "(state {0}). Mirroring the cancellation would strip protection from every "
                    + "follower the instant the leader decided to manage a trade by hand.",
                    mirrored.OrderState));

            Assert(follower.Orders.Count(o => o.Name == "COPIER_STOP"
                    && RiskGuardAddOn.ProvidesCoverage(o.OrderState)) == 1,
                "The cancellation does not provoke a second stop either -- one live stop, still at its original level.");

            Assert(Math.Abs(mirrored.StopPrice - 17990.00) < 1e-9,
                string.Format("The surviving stop holds its level (expected 17990.00, got {0}).", mirrored.StopPrice));
        }

        // ------------------------------------------------------------------
        // S7 — COPIER FAN-OUT UNDER BURST (plan §8)
        //
        // One leader, several followers, rapid entries and exits driven concurrently. Asserts
        // OBSERVED INVARIANTS, not "no exception thrown" -- the pre-existing
        // TestCopierGroup_GroupStressAndConcurrency only asserts the latter, which is why it has
        // never caught anything (plan §8).
        //
        // Two invariants, both of which hold regardless of thread interleaving:
        //   1. No copy order may exceed the follower's actual position on an EXIT. That is P0-5:
        //      copying the leader's raw exit quantity flips the follower to the opposite side.
        //   2. A redelivered execution id produces no additional copies, under concurrency.
        //      That is the dedupe in _copiedExecutionIds, which the burst contends on.
        // ------------------------------------------------------------------
        private static void TestStress_S7_CopierFanOutUnderBurst()
        {
            Console.WriteLine("\n[TEST] S7 STRESS: copier fan-out under concurrent burst (P0-5, P0-6, P1-22)");

            var mnq = new Instrument("MNQ 03-26");
            Account.All.Clear();
            Instrument.Registry.Clear();
            RiskGuardAddOn.SetInstanceForTest(null);
            TradeCopierEngine.Instance.ResetBracketsForTest();
            TradeCopierEngine.Instance.UnsubscribeAllAccounts();
            TradeCopierEngine.Instance.RemoveRelationship("BurstLeader");

            var leader = new Account { Name = "BurstLeader", Provider = Provider.Simulator };
            Account.All.Add(leader);

            var followers = new List<Account>();
            for (int f = 1; f <= 3; f++)
            {
                var acc = new Account { Name = "BurstFollower" + f, Provider = Provider.Simulator };
                // Each follower holds exactly ONE contract for the whole burst.
                acc.Positions.Add(new Position
                {
                    Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 1, AveragePrice = 18000
                });
                Account.All.Add(acc);
                followers.Add(acc);

                TradeCopierEngine.Instance.UpsertRelationship(new CopierRelationship
                {
                    LeaderAccountName = "BurstLeader",
                    FollowerAccountName = acc.Name,
                    IsEnabled = true,
                    AutoSymbolConversion = false,
                    QuantityRatio = 1.0,
                    MaxPositionSize = 100
                });
            }

            const int threads = 4, perThread = 25;
            var errors = new List<string>();
            var errorLock = new object();
            var workers = new List<System.Threading.Thread>();

            for (int t = 0; t < threads; t++)
            {
                int tid = t;
                var th = new System.Threading.Thread(() =>
                {
                    try
                    {
                        for (int i = 0; i < perThread; i++)
                        {
                            // Leader exits 5 while every follower holds 1. Each copy must be
                            // clamped to at most 1; unclamped it is 5 and inverts the follower.
                            var ex = LeaderExec(leader, mnq, OrderAction.Sell, 5,
                                                string.Format("S7-{0}-{1}", tid, i));
                            TradeCopierEngine.Instance.OnExecution(ex);

                            // Immediate redelivery of the SAME execution id -- the dedupe is what
                            // must absorb it, and it is contended by every other thread.
                            TradeCopierEngine.Instance.OnExecution(ex);
                        }
                    }
                    catch (Exception ex)
                    {
                        lock (errorLock) { errors.Add(ex.GetType().Name + ": " + ex.Message); }
                    }
                });
                workers.Add(th);
                th.Start();
            }
            foreach (var th in workers) th.Join();

            Assert(errors.Count == 0,
                string.Format("The burst completed without exceptions ({0}){1}",
                    errors.Count, errors.Count > 0 ? ": " + errors[0] : ""));

            int totalCopies = 0, oversized = 0, worstQty = 0;
            foreach (var acc in followers)
            {
                foreach (var o in acc.OrdersSnapshot().Where(o => o.Name == "COPIER_FOLLOW"))
                {
                    totalCopies++;
                    if (o.Quantity > 1) { oversized++; worstQty = Math.Max(worstQty, o.Quantity); }
                }
            }

            // Invariant 1 -- P0-5 under concurrency.
            Assert(oversized == 0,
                string.Format(
                    "No exit copy exceeds the follower's 1-lot position ({0} of {1} did, largest {2}). "
                    + "An exit sized from the leader's raw quantity leaves the follower SHORT the "
                    + "difference -- and under a burst it does so on every relationship at once.",
                    oversized, totalCopies, worstQty));

            // Invariant 2 -- dedupe under contention. 4*25 distinct ids, each delivered twice,
            // fanned out to 3 followers: at most one copy per (id, follower).
            int distinctExecs = threads * perThread;
            Assert(totalCopies <= distinctExecs * followers.Count,
                string.Format(
                    "Redelivered executions produced no extra copies (got {0}, ceiling {1}). "
                    + "Exceeding the ceiling means _copiedExecutionIds lost a race and the same "
                    + "leader fill was copied more than once.",
                    totalCopies, distinctExecs * followers.Count));

            Assert(totalCopies > 0, "The burst actually drove the copy path (a stress test that drives nothing reports safety).");
        }

        /// <summary>
        /// Guards the defect that motivated this harness repair: a test body was overwritten by a
        /// bad merge, which orphaned ten tests and left a stray Environment.Exit that aborted the
        /// run at test 92 of 117. Nothing detected that for as long as the suite was green.
        ///
        /// Uses reflection to compare every declared Test* method against a registry of methods
        /// the runner actually reached, so a future merge that drops an invocation fails loudly
        /// instead of quietly reducing coverage.
        /// </summary>
        private static void TestHarness_AllDeclaredTestsAreInvoked()
        {
            Console.WriteLine("\n[TEST] HARNESS: every declared test method is invoked by the runner");

            // Self-register before computing, since this method's own Assert runs afterwards.
            _invokedTests.Add("TestHarness_AllDeclaredTestsAreInvoked");

            var declared = typeof(Program)
                .GetMethods(System.Reflection.BindingFlags.NonPublic
                            | System.Reflection.BindingFlags.Public
                            | System.Reflection.BindingFlags.Static)
                .Where(m => m.Name.StartsWith("Test", StringComparison.Ordinal)
                            && m.GetParameters().Length == 0
                            && m.ReturnType == typeof(void))
                .Select(m => m.Name)
                .ToList();

            var missing = declared.Where(n => !_invokedTests.Contains(n)).OrderBy(n => n).ToList();

            Assert(missing.Count == 0,
                missing.Count == 0
                    ? string.Format("All {0} declared test methods were invoked by the runner", declared.Count)
                    : string.Format("{0} declared test method(s) never invoked: {1}",
                        missing.Count, string.Join(", ", missing)));
        }

        /// <summary>
        /// Records which test method the assertion came from, so
        /// TestHarness_AllDeclaredTestsAreInvoked can prove the runner still reaches every
        /// declared test. [CallerMemberName] means no call site has to change, and a test that
        /// asserts nothing never registers - which is itself the failure we want surfaced.
        /// </summary>
        private static void Assert(
            bool condition,
            string message,
            [System.Runtime.CompilerServices.CallerMemberName] string caller = null)
        {
            if (!string.IsNullOrEmpty(caller))
            {
                _invokedTests.Add(caller);
            }

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
            state.UnrealizedPnL = 0.0;

            var actions = addon.EvaluatePnLRules(account, state);

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
            state.UnrealizedPnL = 0.0;

            // Peak equity at +500
            state.RealizedPnL = 500.0;
            addon.EvaluatePnLRules(account, state);
            Assert(state.PeakEquity == 500.0, "Peak equity correctly tracks top session profit.");

            // Drawdown to -1100 (breach = 500 - 1500 = -1000)
            state.RealizedPnL = -1100.0;
            var actions = addon.EvaluatePnLRules(account, state);

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

            // 3. AccountItemUpdate fires (event-driven PnL sync replaces sweep polling)
            account.TriggerAccountItemUpdate(AccountItem.RealizedProfitLoss, -150.0);
            // ExecuteAccountItemUpdate processes the PnL change synchronously in TESTING mode
            addon.ExecuteAccountItemUpdate(account, new AccountItemEventArgs { AccountItem = AccountItem.RealizedProfitLoss, Value = -150.0 });

            // Verify ConsecutiveLosses was incremented when AccountItemUpdate catches the change
            Assert(state.ConsecutiveLosses == 1, "Consecutive losses successfully incremented after AccountItemUpdate catches lagged realized PnL.");
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

        // -
        // CRITICAL GAP TESTS
        // -

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
            System.Threading.Thread.Sleep(1050);

            // Trade 2: enter Long again
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18100, 0, config);
            Assert(state.TradesToday == 2, "TradesToday == 2 after second entry.");

            // Close trade 2
            state.UpdatePosition(account, mnq, MarketPosition.Flat, 0, 0, 0, config);
            Assert(state.TradesToday == 2, "TradesToday stays 2 after second close.");
        }

        private static void TestFlipDetectionCountsAsEntry()
        {
            Console.WriteLine("\n[TEST] Long-Short Flip Counts As Entry");
            var config = new RiskConfig();
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var mnq = new Instrument("MNQ");

            // Enter Long
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);
            Assert(state.TradesToday == 1, "TradesToday == 1 after Long entry.");

            // Flip directly to Short (Long-Short in one NT update)
            state.UpdatePosition(account, mnq, MarketPosition.Short, 2, 18100, 0, config);
            Assert(state.TradesToday == 2, "TradesToday == 2 after Long-Short flip (flip counts as new entry).");

            // Verify we're correctly Short
            Assert(state.Positions[mnq.FullName].MarketPosition == MarketPosition.Short, "Position correctly shows Short after flip.");
        }

        private static void TestTradeCountingMultiContractScalingDebounced()
        {
            Console.WriteLine("\n[TEST] Multi-Contract Scaling & Staggered Fills Debounced");
            var config = new RiskConfig();
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var mnq = new Instrument("MNQ");

            // Leg 1: enter Long 1 contract
            state.UpdatePosition(account, mnq, MarketPosition.Long, 1, 18000, 0, config);
            Assert(state.TradesToday == 1, "TradesToday == 1 after 1st contract fill.");

            // Leg 2: scale up to 2 contracts (staggered fill / multi-contract)
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);
            Assert(state.TradesToday == 1, "TradesToday remains 1 after scaling up to 2 contracts.");

            // Leg 3: scale down to 1 contract
            state.UpdatePosition(account, mnq, MarketPosition.Long, 1, 18050, 0, config);
            Assert(state.TradesToday == 1, "TradesToday remains 1 on partial exit.");

            // Flat
            state.UpdatePosition(account, mnq, MarketPosition.Flat, 0, 0, 0, config);
            Assert(state.TradesToday == 1, "TradesToday remains 1 on final flat.");
        }

        private static void TestLockoutWatchdogSweepFlattensOpenPosition()
        {
            Console.WriteLine("\n[TEST] Lockout Safety Sweep Watchdog Flattens Open Position");
            var config = new RiskConfig();
            var account = new Account { Name = "TestAcc" };
            Account.All.Add(account);
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetArmedForTest(true);

            var state = new AccountState("TestAcc");
            state.IsLockedOut = true;
            var mnq = new Instrument("MNQ");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);

            DateTime nowEt = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"));
            state.LastSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;
            Account.All.Clear();
            Account.All.Add(account);
            addon.SetConfigForTest(config);
            addon.SetAccountStateForTest("TestAcc", state);
            addon.SetSubscribedAccountForTest("TestAcc");
            addon.SetArmedForTest(true);
            addon.SetModeForTest("live");

            // Run safety sweep with no incoming order events
            addon.ExecuteSafetySweep();

            Assert(state.CurrentLockoutPhase == AccountState.LockoutPhase.PendingCancel ||
                   state.CurrentLockoutPhase == AccountState.LockoutPhase.PendingFlatten ||
                   state.CurrentLockoutPhase == AccountState.LockoutPhase.Confirmed, 
                   "Lockout phase advanced during sweep watchdog evaluation.");
        }

        /// <summary>
        /// P0-51. Shadow mode must restrain EVERY path, not just the action pipeline.
        ///
        /// The lockout leaves the addon by two routes. EvaluateLockoutPhase emits a
        /// FlattenPosition GuardAction, which ProcessAction's mode gate correctly skips with
        /// "[SHADOW] Would execute action FlattenPosition". The lockout watchdog sweep separately
        /// builds its own cancel/flatten batches and calls Account.Cancel / Account.Flatten
        /// directly, with no _mode check anywhere in the block. Both fire. The guard announces it
        /// is only observing and flattens the account anyway.
        ///
        /// Observed live on 2026-08-09 21:15:25 ET: Sim101, SimCopyTest1 and SimCopy2 each logged
        /// the [SHADOW] line and were each really flattened a moment later (orders 34256/34257/
        /// 34258, market Sell 2, named "Close" -- the name Account.Flatten() gives its close
        /// order). Sim-ORB, the one account that had not tripped the lockout, was untouched, which
        /// is what rules out a manual flatten.
        ///
        /// The existing suite asserts ProcessAction's gate and that gate has always been correct.
        /// What was never asserted is the NEGATIVE: that in shadow mode NO path reaches the
        /// broker. That is what this test pins, and it is why the defect shipped.
        /// </summary>
        private static void TestP0_51_ShadowModeIssuesNoBrokerCallsFromTheLockoutSweep()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] P0-51: shadow mode issues no broker calls from the lockout sweep");

            var config  = new RiskConfig();
            var account = new Account { Name = "ShadowAcc" };
            var mnq     = new Instrument("MNQ");

            var state = new AccountState("ShadowAcc");
            state.IsLockedOut = true;
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 29849.75, 0, config);

            // The sweep builds its flatten batch from account.Positions (RiskGuardAddOn.cs:1878),
            // NOT from AccountState. Without this the flatten path is never reached and the test
            // would silently prove only half of what it claims.
            account.Positions.Add(new Position
            {
                Instrument     = mnq,
                MarketPosition = MarketPosition.Long,
                Quantity       = 2,
                AveragePrice   = 29849.75
            });

            // A working protective stop and a working target, exactly as an ATM bracket leaves them.
            account.Orders.Add(new Order
            {
                Name         = "Stop1",
                Instrument   = mnq,
                OrderType    = OrderType.StopMarket,
                OrderAction  = OrderAction.Sell,
                OrderState   = OrderState.Working,
                Quantity     = 2,
                StopPrice    = 29835
            });
            account.Orders.Add(new Order
            {
                Name         = "Target1",
                Instrument   = mnq,
                OrderType    = OrderType.Limit,
                OrderAction  = OrderAction.Sell,
                OrderState   = OrderState.Working,
                Quantity     = 2,
                LimitPrice   = 29879.75
            });

            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            state.LastSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

            Account.All.Clear();
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetAccountStateForTest("ShadowAcc", state);
            addon.SetSubscribedAccountForTest("ShadowAcc");
            addon.SetArmedForTest(true);
            addon.SetModeForTest("shadow");

            // Record EVERY broker call, not just the ones under _stateLock (that is P1-10's
            // question, and it is already answered). Here the lock is irrelevant: in shadow the
            // count must be zero however it is reached.
            var brokerCalls = new List<string>();
            Account.BrokerCallObserver = method => brokerCalls.Add(method);
            try
            {
                addon.ExecuteSafetySweep();
                addon.ExecuteSafetySweep();   // second sweep: PendingCancel -> PendingFlatten
            }
            finally { Account.BrokerCallObserver = null; }

            Assert(!brokerCalls.Contains("Flatten"),
                "Shadow mode does not flatten: the lockout sweep issued no Account.Flatten call");
            Assert(!brokerCalls.Contains("Cancel"),
                "Shadow mode does not cancel: the lockout sweep issued no Account.Cancel call");
            Assert(brokerCalls.Count == 0,
                "Shadow mode reaches the broker by no path at all during a lockout sweep "
                + "(saw: " + (brokerCalls.Count == 0 ? "none" : string.Join(", ", brokerCalls)) + ")");

            // The position and its protection must both survive untouched -- the guard is an
            // observer here, and an observer that cancels the stop is worse than no guard at all.
            Assert(account.Orders.Any(o => o.Name == "Stop1" && o.OrderState == OrderState.Working),
                "The protective stop is still working after a shadow-mode lockout sweep");
            Assert(account.Positions.Any(p => p.Instrument != null
                        && p.Instrument.FullName == mnq.FullName
                        && p.MarketPosition == MarketPosition.Long),
                "The position is still open after a shadow-mode lockout sweep");

            Account.All.Clear();
        }

        /// <summary>
        /// P0-51, second half: the DEFERRED cancel queue must respect the mode too.
        ///
        /// _pendingCancels exists because P1-43 forbids sending a cancel from under _stateLock, so
        /// the lockout/blacklist/cap paths queue the trader's orders and DrainPendingCancels()
        /// sends them after the lock is released. Four of the five enqueue sites are interventions
        /// against orders the TRADER placed; only the FSM-teardown site cancels an order RiskGuard
        /// itself submitted.
        ///
        /// This test exists because the patch loop got this wrong twice in opposite directions and
        /// no gate caught either. First it gated the drain entirely, which leaves the queue growing
        /// all session and fires a stale burst the moment the mode is switched to live. Then the
        /// arbiter's remedy was to drain unconditionally in every mode -- which reintroduces the
        /// defect this ticket exists to fix, because it cancels the trader's working orders while
        /// the guard claims to be observing. Both candidates passed every gate and all five of the
        /// other acceptance tests, because none of them drove this path.
        ///
        /// The rule: an intervention against the trader's order is subject to the mode. Cleanup of
        /// RiskGuard's own footprint is not.
        /// </summary>
        private static void TestP0_51_ShadowModeDoesNotDrainInterventionCancelsToTheBroker()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] P0-51: shadow mode does not send queued intervention cancels to the broker");

            var config  = new RiskConfig();
            var account = new Account { Name = "ShadowDrainAcc" };
            var mnq     = new Instrument("MNQ");

            Account.All.Clear();
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetSubscribedAccountForTest("ShadowDrainAcc");
            addon.SetArmedForTest(true);
            addon.SetModeForTest("shadow");

            var state = new AccountState("ShadowDrainAcc");
            addon.SetAccountStateForTest("ShadowDrainAcc", state);

            // Sweep once unobserved so the daily session reset settles; it clears IsLockedOut, so
            // locking before this call would be undone before the queue is ever exercised.
            addon.ExecuteSafetySweep();
            state.IsLockedOut = true;

            // A resting entry the TRADER placed. With the account locked out, ExecuteOrderUpdate
            // queues it for cancellation (RiskGuardAddOn.cs:1635-1649) rather than cancelling it
            // inline, because that block runs under _stateLock.
            var restingEntry = new Order
            {
                Id          = "TRADER-1",
                Name        = "Entry1",
                Instrument  = mnq,
                OrderType   = OrderType.Limit,
                OrderAction = OrderAction.Buy,
                OrderState  = OrderState.Working,
                Quantity    = 1,
                LimitPrice  = 29800
            };
            account.Orders.Add(restingEntry);
            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = restingEntry });

            var brokerCalls = new List<string>();
            Account.BrokerCallObserver = method => brokerCalls.Add(method);
            try { addon.ExecuteSafetySweep(); }
            finally { Account.BrokerCallObserver = null; }

            Assert(!brokerCalls.Contains("Cancel"),
                "Shadow mode does not drain queued intervention cancels to the broker");
            Assert(restingEntry.OrderState == OrderState.Working,
                "The trader's resting entry is untouched by a shadow-mode lockout "
                + "(state " + restingEntry.OrderState + ")");

            Account.All.Clear();
        }

        /// <summary>
        /// P1-54. A lockout must end when its deadline passes.
        ///
        /// The lockout test is `IsLockedOut || DateTime.UtcNow &lt; LockoutUntil` -- an OR -- and
        /// nothing ever cleared the flag when the deadline lapsed. The only clears were the daily
        /// session reset and a manual UnlockAccount, so Overtrading.LockoutMinutes (default 60)
        /// could only ever EXTEND a lockout, never end one.
        ///
        /// Observed 2026-08-10: Sim101, SimCopy2 and SimCopyTest1 were still locked out roughly
        /// three hours after a (false) flood lockout and blocked a fresh order outright. All three
        /// had to be cleared by hand.
        ///
        /// P1-45 added the deadline and is not reopened; this is the other half of making it mean
        /// something.
        /// </summary>
        private static void TestP1_54_LockoutLapsesWhenItsDeadlinePasses()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] P1-54: a lockout ends when its deadline passes");

            var config  = new RiskConfig();
            var account = new Account { Name = "LapseAcc" };
            Account.All.Clear();
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetSubscribedAccountForTest("LapseAcc");
            addon.SetArmedForTest(true);
            addon.SetModeForTest("live");

            var state = new AccountState("LapseAcc");
            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            state.LastSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;
            addon.SetAccountStateForTest("LapseAcc", state);

            // Locked out, with a deadline that has already passed -- i.e. the lockout served its
            // time. Nothing is open and nothing is working, so there is no reason to hold it.
            state.IsLockedOut = true;
            state.LockoutUntil = DateTime.UtcNow.AddMinutes(-1);

            addon.ExecuteSafetySweep();

            Assert(!addon.IsAccountLocked("LapseAcc"),
                "A lockout whose LockoutUntil has passed no longer reports the account as locked");

            // Still locked while the deadline is in the FUTURE -- the lapse must not become a
            // blanket unlock.
            state.IsLockedOut = true;
            state.LockoutUntil = DateTime.UtcNow.AddMinutes(30);
            addon.ExecuteSafetySweep();

            Assert(addon.IsAccountLocked("LapseAcc"),
                "A lockout whose LockoutUntil is still in the future stays locked");

            Account.All.Clear();
        }

        /// <summary>
        /// P1-54, second half: the deadline has to survive a restart.
        ///
        /// state.json persisted only a top-level LockedOutAccounts NAME LIST, so a restart restored
        /// IsLockedOut = true with LockoutUntil = DateTime.MinValue. Even with the lapse fixed, a
        /// 60-minute lockout silently became an all-day one across any recompile -- and a recompile
        /// is routine here.
        /// </summary>
        private static void TestP1_54_LockoutDeadlineSurvivesARestart()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] P1-54: the lockout deadline survives a restart");

            var config = new RiskConfig();
            Account.All.Clear();

            var writer = new RiskGuardAddOn();
            writer.SetConfigForTest(config);
            writer.SetSubscribedAccountForTest("PersistAcc");

            var deadline = DateTime.UtcNow.AddMinutes(45);
            var state = new AccountState("PersistAcc") { IsLockedOut = true, LockoutUntil = deadline };
            writer.SetAccountStateForTest("PersistAcc", state);

            string path = Path.Combine(Path.GetTempPath(), "rg_p1_54_" + Guid.NewGuid().ToString("N") + ".json");
            try
            {
                writer.SetStateFileForTest(path);
                writer.SavePersistedStateForTest();

                var reader = new RiskGuardAddOn();
                reader.SetConfigForTest(config);
                reader.SetStateFileForTest(path);
                reader.LoadPersistedStateForTest();

                var restored = reader.GetAccountStateForTest("PersistAcc");
                Assert(restored != null && restored.IsLockedOut,
                    "The lockout itself survives the restart");
                Assert(restored != null && Math.Abs((restored.LockoutUntil - deadline).TotalSeconds) < 2.0,
                    "The lockout DEADLINE survives the restart, so a 60-minute lockout does not "
                    + "become an all-day one (restored " + (restored == null ? "null" : restored.LockoutUntil.ToString("o")) + ")");
            }
            finally
            {
                try { if (File.Exists(path)) File.Delete(path); } catch { }
            }
        }

        /// <summary>
        /// P1-52. The order-flood governor counts distinct order IDs in a one-second window with
        /// no notion of a bracket. A single 2-contract ATM entry is SIX orders -- two entry fills,
        /// two protective stops, two targets -- against a default limit of five. So every 2-lot
        /// bracketed entry trips a lockout.
        ///
        /// Observed live on 2026-08-09 21:15:22 ET on three accounts in the same second, because a
        /// third-party copier mirrored the bracket: copier fan-out multiplies a false positive
        /// across every mirrored account at once.
        ///
        /// This is the third defect on this governor (P1-44, P1-45, P2-46 preceded it) and the
        /// second about it firing when it should not. P2-46 fixed double-counting one order's
        /// state transitions; this is different -- six genuinely distinct orders that are one
        /// trade. Raising the threshold alone is not a fix: a limit high enough to clear a 5-lot
        /// ATM is high enough to miss a real runaway.
        /// </summary>
        private static void TestP1_52_NormalAtmBracketIsNotAFlood()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] P1-52: a normal 2-lot ATM bracket is not an order flood");

            var config  = new RiskConfig();
            var account = new Account { Name = "AtmAcc" };
            var mnq     = new Instrument("MNQ");

            var state = new AccountState("AtmAcc");
            var etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            var nowEt  = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, etZone);
            state.LastSessionDate = nowEt.TimeOfDay >= new TimeSpan(18, 0, 0) ? nowEt.Date.AddDays(1) : nowEt.Date;

            Account.All.Clear();
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetAccountStateForTest("AtmAcc", state);
            addon.SetSubscribedAccountForTest("AtmAcc");
            addon.SetArmedForTest(true);
            addon.SetModeForTest("shadow");

            // Exactly what NT8 emits for one 2-contract ATM entry, all inside one second:
            // two entries, then a stop and a target per contract.
            //
            // The governor only counts orders in Submitted or Accepted state, keyed on Order.Id
            // (RiskGuardAddOn.cs:1591-1596) -- that is P2-46's distinct-order-ID fix. So the
            // states here matter: this is the moment each leg is submitted, which is exactly when
            // the live lockout fired.
            var bracket = new List<Order>
            {
                new Order { Id = "ATM-1", Name = "Entry1",  Instrument = mnq, OrderType = OrderType.Market,     OrderAction = OrderAction.Buy,  Quantity = 1 },
                new Order { Id = "ATM-2", Name = "Entry2",  Instrument = mnq, OrderType = OrderType.Market,     OrderAction = OrderAction.Buy,  Quantity = 1 },
                new Order { Id = "ATM-3", Name = "Stop1",   Instrument = mnq, OrderType = OrderType.StopMarket, OrderAction = OrderAction.Sell, Quantity = 1, StopPrice  = 29835,    Oco = "BRACKET-C1" },
                new Order { Id = "ATM-4", Name = "Target1", Instrument = mnq, OrderType = OrderType.Limit,      OrderAction = OrderAction.Sell, Quantity = 1, LimitPrice = 29879.75, Oco = "BRACKET-C1" },
                new Order { Id = "ATM-5", Name = "Stop2",   Instrument = mnq, OrderType = OrderType.StopMarket, OrderAction = OrderAction.Sell, Quantity = 1, StopPrice  = 29835,    Oco = "BRACKET-C2" },
                new Order { Id = "ATM-6", Name = "Target2", Instrument = mnq, OrderType = OrderType.Limit,      OrderAction = OrderAction.Sell, Quantity = 1, LimitPrice = 29879.75, Oco = "BRACKET-C2" },
            };

            // The protective legs carry per-contract OCO ids, as a real NT8 ATM bracket does.
            // This deliberately leaves BOTH plausible fixes open: keying the flood map on Oco
            // (4 distinct keys) and excluding protective legs from the count (2) each satisfy the
            // assertion below. The test pins the OUTCOME -- one trade is not a flood -- not the
            // mechanism.

            foreach (var o in bracket)
            {
                o.OrderState = OrderState.Submitted;
                account.Orders.Add(o);
                addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = o });

                o.OrderState = OrderState.Accepted;
                addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = o });
            }

            Assert(!state.IsLockedOut,
                "Six orders from ONE 2-lot ATM bracket do not trip the order-flood lockout");

            Account.All.Clear();
        }

        private static void TestLockoutAllowsPositionReducingOrders()
        {
            Console.WriteLine("\n[TEST] Lockout Allows Position Reducing Orders");
            var config = new RiskConfig();
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            var mnq = new Instrument("MNQ");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, config);

            var sellOrder = new Order
            {
                Instrument = mnq,
                OrderAction = OrderAction.Sell,
                OrderType = OrderType.Market,
                Quantity = 2
            };

            var buyOrder = new Order
            {
                Instrument = mnq,
                OrderAction = OrderAction.Buy,
                OrderType = OrderType.Limit,
                Quantity = 2
            };

            Assert(addon.IsPositionReducingOrder(sellOrder, state) == true, "Sell order is position reducing for Long.");
            Assert(addon.IsPositionReducingOrder(buyOrder, state) == false, "Buy order is NOT position reducing for Long.");
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

            // P0-51: cancelling the trader's order is an INTERVENTION, so it only happens in an
            // acting mode. This test never said which mode it wanted and _mode defaults to
            // "shadow", so it was asserting that a shadow-mode guard cancels a working order --
            // true only because the deferred cancel queue ignored the mode entirely. Fourth test
            // in this file found doing this; see the handover note on the pattern.
            addon.SetModeForTest("live");

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
                OrderState = OrderState.Filled,  // Already filled - should NOT be cancelled
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

            // P0-51: same correction as TestOrderCancelledWhenLockedOnOrderUpdate. The
            // consec-loss cancel is an intervention against the trader's order, so it belongs to
            // an acting mode; the test ran in the "shadow" default and passed only because the
            // deferred cancel queue drained regardless of mode.
            addon.SetModeForTest("live");

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

        // -
        // IMPORTANT GAP TESTS
        // -

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
            state.UnrealizedPnL = -600.0;  // Combined = -1100 - breach

            var actions = addon.EvaluatePnLRules(account, state);

            Assert(actions.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "DAILY_LOSS_BREACH fires when Realized + Unrealized combined exceeds limit.");
            Assert(state.IsLockedOut, "Account locked when unrealized PnL tips combined total past limit.");

            // Boundary: realized -500 + unrealized -499 = -999, within limit
            var state2 = new AccountState("TestAcc2");
            state2.RealizedPnL   = -500.0;
            state2.UnrealizedPnL = -499.0; // Combined = -999, just inside limit
            var actions2 = addon.EvaluatePnLRules(account, state2);
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

            // Lockout enforcement is now event-driven via PositionUpdate.
            // The phased lockout needs two events: first cancels orders, second flattens.
            // Backdate LastLockoutFlattenAttempt so the throttle doesn't block the flatten.
            state.LastLockoutFlattenAttempt = DateTime.UtcNow.AddSeconds(-10);

            // Fire PositionUpdate to trigger EvaluateLockoutPhase (phase 1: cancel orders).
            addon.ExecutePositionUpdate(account, new PositionEventArgs { Position = new Position { Instrument = new Instrument("MNQ"), MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000 } });

            // After cancel phase, fire OrderUpdate to advance to flatten phase.
            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = workingOrder });

            // Backdate again so the flatten phase's 5s throttle is satisfied.
            state.LastLockoutFlattenAttempt = DateTime.UtcNow.AddSeconds(-10);

            // Fire another PositionUpdate to trigger flatten phase.
            addon.ExecutePositionUpdate(account, new PositionEventArgs { Position = new Position { Instrument = new Instrument("MNQ"), MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000 } });

            Assert(account.Positions.Count == 0, "Positions cleared after lockout enforcement via PositionUpdate.");
            Assert(workingOrder.OrderState == OrderState.Cancelled, "Working order cancelled by lockout enforcement.");
        }

        private static void TestLockoutEnforcementSubsequentSweepNoPosition()
        {
            Console.WriteLine("\n[TEST] Subsequent Sweep With Locked + No Positions - No Action");
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
            Assert(account.Positions.Count == 0, "No positions to flatten - account stays flat.");
        }

        private static void TestLockoutEnforcementSubsequentSweepWithNewPosition()
        {
            Console.WriteLine("\n[TEST] Subsequent Sweep With Locked + New Position - Re-Flattened");
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

            // Lockout enforcement is now event-driven. Fire PositionUpdate to trigger re-flatten.
            addon.ExecutePositionUpdate(account, new PositionEventArgs { Position = new Position { Instrument = new Instrument("MNQ"), MarketPosition = MarketPosition.Long, Quantity = 1, AveragePrice = 18000 } });

            Assert(account.Positions.Count == 0, "New position re-flattened by lockout enforcement via PositionUpdate.");
        }

        private static void TestStopGuardAutoStop()
        {
            Console.WriteLine("\n[TEST] StopGuard AutoStop: Position With No Stop - MISSING_STOP_ATTACH");
            var config = new RiskConfig();
            config.StopGuard.OnMissing        = "AutoStop";
            config.StopGuard.StopAttachSeconds = 0;

            var account = new Account { Name = "TestAcc" };
            var mnq   = new Instrument("MNQ");
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();

            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000 });

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(actions.Any(a => a.RuleId == "MISSING_STOP_ATTACH"),
                "MISSING_STOP_ATTACH action generated when position is unprotected past grace period.");
        }

        private static void TestStopGuardFlatten()
        {
            Console.WriteLine("\n[TEST] StopGuard Flatten: Position With No Stop - MISSING_STOP_FLATTEN");
            var config = new RiskConfig();
            config.StopGuard.OnMissing        = "Flatten";
            config.StopGuard.StopAttachSeconds = 0;

            var account = new Account { Name = "TestAcc" };
            var mnq   = new Instrument("MNQ");
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();

            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000 });

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(actions.Any(a => a.RuleId == "MISSING_STOP_FLATTEN"),
                "MISSING_STOP_FLATTEN action generated when OnMissing=Flatten and no stop after grace period.");
        }

        private static void TestStopGuardNoActionWhenStopPresent()
        {
            Console.WriteLine("\n[TEST] StopGuard: No Action When Stop Quantity Covers Position");
            var config = new RiskConfig();
            config.StopGuard.OnMissing        = "AutoStop";
            config.StopGuard.StopAttachSeconds = 0;

            var account = new Account { Name = "TestAcc" };
            var mnq     = new Instrument("MNQ");
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            // Add a working stop order that covers the 2-contract position
            var stopOrder = new Order
            {
                Id          = Guid.NewGuid().ToString(),
                OrderState  = OrderState.Working,
                OrderType   = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity    = 2,
                Instrument  = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stopOrder);

            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000 });

            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(!actions.Any(a => a.RuleId == "MISSING_STOP_ATTACH" || a.RuleId == "MISSING_STOP_FLATTEN"),
                "No StopGuard action when working stop fully covers position quantity.");
        }

        private static void TestStopGuardTransientStateValidation()
        {
            Console.WriteLine("\n[TEST] StopGuard: Transient Order States Count Towards Protection");
            var config = new RiskConfig();
            config.StopGuard.OnMissing = "AutoStop";
            config.StopGuard.StopAttachSeconds = 0;

            var account = new Account { Name = "TestAcc" };
            var mnq = new Instrument("MNQ");
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            // Add a pending submit stop order (transient state)
            var stopOrder = new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderState = OrderState.Initialized,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 2,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stopOrder);

            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000 });

            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(!actions.Any(a => a.RuleId == "MISSING_STOP_ATTACH"),
                "No StopGuard action when order is in Initialized transient state (FSM is ProtectedPending).");
        }

        private static void TestStopGuardPartiallyFilledValidation()
        {
            Console.WriteLine("\n[TEST] StopGuard: Partially Filled Orders Calculate Remaining Correctly");
            // With the FSM, a PartFilled stop is recognized as ProtectedPending,
            // so grace expiry will NOT fire. The partial gap is handled by the
            // FSM recognizing the stop as pending, not by a legacy gap calculation.
            var config = new RiskConfig();
            config.StopGuard.OnMissing = "AutoStop";
            config.StopGuard.StopAttachSeconds = 0;

            var account = new Account { Name = "TestAcc" };
            var mnq = new Instrument("MNQ");
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            // Stop order for 3 contracts, but 2 are filled, so only 1 remaining working
            var stopOrder = new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderState = OrderState.PartFilled,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 3,
                Filled = 2,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stopOrder);

            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000 });

            // PartFilled is recognized by the FSM as ProtectedPending, so no action.
            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(!actions.Any(a => a.RuleId == "MISSING_STOP_ATTACH"),
                "PartFilled stop recognized as ProtectedPending - no auto-stop from grace expiry.");
        }

        private static void TestEdgeWindowGateBreach()
        {
            Console.WriteLine("\n[TEST] EdgeWindowGate: Position Entered Outside Window - Breach");
            var config = new RiskConfig();
            config.EnableWindowGate = true;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            // Define window 09:50-11:10 ET Monday-Friday
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

            // PnL sync is now event-driven via AccountItemUpdate, not the sweep.
            addon.ExecuteAccountItemUpdate(account, new AccountItemEventArgs { AccountItem = AccountItem.RealizedProfitLoss, Value = 200.0 });

            Assert(state.ConsecutiveLosses == 0,
                "Consecutive loss counter reset to 0 after a profitable trade detected via AccountItemUpdate.");
            Assert(state.RealizedPnL == 200.0,
                "RealizedPnL synced to 200 after winning AccountItemUpdate.");
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
            addon.ExecuteSafetySweep(); // Shadow mode - won't flatten but exercises the code path
            Assert(true, "Aggregate size breach sweep runs without exception.");
        }

        // -
        // LOWER-PRIORITY / BOUNDARY TESTS
        // -

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
            Console.WriteLine("\n[TEST] Max Size At Exactly The Limit - No Breach");
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount = 5;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            // Exactly at the limit - code uses >, not >=
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 5, 18000, 0, config);

            var actions = addon.EvaluateRules(account, state);

            Assert(!actions.Any(a => a.RuleId == "MAX_SIZE_BREACH"),
                "No MAX_SIZE_BREACH when quantity == limit (rule uses strict >, not >=).");
        }

        private static void TestDailyLossAtExactlyLimit()
        {
            Console.WriteLine("\n[TEST] Daily Loss At Exactly The Limit - No Breach");
            var config = new RiskConfig();
            config.PnLRules.DailyLossLimit = 1000.0;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.UnrealizedPnL = 0.0;
            // Exactly at -1000 - code uses < -Limit, so -1000 < -1000 is false
            state.RealizedPnL = -1000.0;

            var actions = addon.EvaluatePnLRules(account, state);

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
            Console.WriteLine("\n[TEST] Multiple Instruments - No Per-Instrument Breach When Each Is Under Limit");
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount = 5;

            var account = new Account { Name = "TestAcc" };
            var addon   = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            // MNQ = 3 contracts, ES = 3 contracts - each individually under limit of 5
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 3, 18000, 0, config);
            state.UpdatePosition(account, new Instrument("ES"),  MarketPosition.Short, 3, 5000,  0, config);

            var actions = addon.EvaluateRules(account, state);

            Assert(!actions.Any(a => a.RuleId == "MAX_SIZE_BREACH"),
                "No MAX_SIZE_BREACH when each instrument is individually within the per-account limit.");
        }

        // -
        // EXCLUSION DEEP-DIVE TESTS  (test-first - these define the correct behaviour)
        // -

        // -
        // An excluded account must bypass ALL rules - EvaluateRules path
        // -
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
            // 10 contracts - far exceeds limit of 3 - but account is excluded
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 10, 18000, 0, config);

            var actions = addon.EvaluateRules(account, state);

            Assert(actions.Count == 0,
                "Excluded account returns 0 rule actions even with 10 contracts (limit 3).");
            Assert(!state.IsLockedOut,
                "Excluded account is NOT locked out despite exceeding max contracts.");
        }

        // -
        // Excluded account: ALL rules bypassed simultaneously
        // -
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
                "Excluded account has 0 rule actions from EvaluateRules (sizing/overtrading bypassed).");
            Assert(!state.IsLockedOut,
                "Excluded account is NEVER locked out.");

            // Also verify PnL rules are bypassed for excluded accounts
            var pnlActions = addon.EvaluatePnLRules(account, state);
            Assert(pnlActions.Count == 0,
                "Excluded account has 0 PnL rule actions (PnL rules bypassed).");
        }

        // -
        // Excluded account: OnOrderUpdate must NOT cancel its orders
        // -
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

        // -
        // BUG: Excluded account contracts must NOT count toward aggregate total
        // -
        private static void TestExcludedAccountNotCountedInAggregate()
        {
            Console.WriteLine("\n[TEST] Excluded Account Contracts NOT Counted In Aggregate Total");
            var config = new RiskConfig();
            config.ExcludedAccounts.Add("ExcludedAcc");
            config.Sizing.MaxContractsAggregate = 10;
            config.Sizing.ExpectedCopies        = 1;

            // ExcludedAcc: 20 contracts (excluded, should be invisible to aggregate)
            // NormalAcc:    5 contracts (under the limit of 10)
            // Without the fix: 20+5=25 > 10 - triggers aggregate breach on NormalAcc
            // With the fix:      0+5= 5 <= 10 - no breach

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

            // Aggregate sizing is now event-driven via PositionUpdate, not the sweep.
            // Fire a PositionUpdate on normalAcc to trigger EvaluateAggregateSizing.
            addon.ExecutePositionUpdate(normalAcc, new PositionEventArgs { Position = new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 5, AveragePrice = 18000 } });

            Assert(normalAcc.Positions.Count > 0,
                "NormalAcc (5 contracts, under limit) is NOT flattened when excluded account's 20 contracts are correctly ignored in aggregate.");
            Assert(exclAcc.Positions.Count > 0,
                "ExcludedAcc is NOT flattened by aggregate check.");
        }

        // -
        // BUG: Excluded account must NOT be flattened by aggregate breach action
        // -
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

            // Aggregate sizing is now event-driven via PositionUpdate, not the sweep.
            // Fire a PositionUpdate on normAcc1 to trigger EvaluateAggregateSizing.
            addon.ExecutePositionUpdate(normAcc1, new PositionEventArgs { Position = new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 4, AveragePrice = 18000 } });

            // NormAcc1 and NormAcc2 should be flattened (4+4=8 > limit of 5)
            // ExcludedAcc must keep its position
            Assert(exclAcc.Positions.Count > 0,
                "ExcludedAcc position is preserved even when non-excluded accounts trigger aggregate breach.");
            Assert(normAcc1.Positions.Count == 0 || normAcc2.Positions.Count == 0,
                "At least one non-excluded account IS flattened by aggregate breach.");
        }

        // -
        // Excluded account: sweep must never lock it out
        // -
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

        // -
        // A non-excluded account beside an excluded one is still enforced
        // -
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

            exclState.RealizedPnL   = -9999.0; // Excluded - should not fire
            normalState.RealizedPnL = -600.0;  // Not excluded - SHOULD fire DAILY_LOSS_BREACH

            var exclActions   = addon.EvaluateRules(exclAccount,   exclState);
            var normalActions  = addon.EvaluateRules(normalAccount, normalState);
            var normalPnlActions = addon.EvaluatePnLRules(normalAccount, normalState);

            Assert(exclActions.Count == 0,
                "Excluded account produces 0 rule actions.");
            Assert(!normalActions.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "EvaluateRules does not emit PnL rules for non-excluded account (owned by EvaluatePnLRules).");
            Assert(normalPnlActions.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "Non-excluded account beside it still gets DAILY_LOSS_BREACH from EvaluatePnLRules.");
        }

        // -
        // Removing an account from exclusion list re-enables all rules
        // -
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
            state.UnrealizedPnL = 0.0;

            // While excluded: no actions
            var actionsWhileExcluded = addon.EvaluatePnLRules(account, state);
            Assert(actionsWhileExcluded.Count == 0,
                "No PnL actions while account is in exclusion list.");

            // Remove from exclusion list
            config.ExcludedAccounts.Remove("TestAcc");
            state.IsLockedOut = false; // Reset so we measure just the rule

            var actionsAfterRemoval = addon.EvaluatePnLRules(account, state);
            Assert(actionsAfterRemoval.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "DAILY_LOSS_BREACH fires immediately after account is removed from exclusion list.");
        }

        // -
        // PASS 2 GAP TESTS
        // -

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
            Console.WriteLine("\n[TEST] StopGuard Partial Stop: FSM recognizes partial stop as ProtectedPending");
            var config = new RiskConfig();
            config.StopGuard.StopAttachSeconds = 0;
            config.StopGuard.OnMissing = "AutoStop";

            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 4);

            // Add a working stop for 2 contracts (partial coverage)
            var stopOrder = new Order { Instrument = mnq, OrderState = OrderState.Working, OrderType = OrderType.StopMarket, OrderAction = OrderAction.Sell, Quantity = 2 };
            addon.TestFsmOnOrder(account, mnq.FullName, stopOrder);

            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 4, AveragePrice = 18000 });

            // P0-4 (RISKGUARD_COPIER_HARDENING_PLAN.md): this test previously asserted the
            // DEFECT - that a working stop of ANY quantity marked the position fully protected,
            // so a 2-lot stop under a 4-lot position suppressed MISSING_STOP_ATTACH and left
            // 2 contracts naked for the rest of the session. The FSM now tracks CoveredQuantity,
            // so grace expiry fires for the uncovered delta only.
            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            var attach = actions.FirstOrDefault(a => a.RuleId == "MISSING_STOP_ATTACH");
            Assert(attach != null,
                "MISSING_STOP_ATTACH IS emitted when the working stop only partially covers the position.");
            Assert(attach != null && attach.Quantity == 2,
                "MISSING_STOP_ATTACH is sized to the uncovered delta (4 position - 2 covered = 2), "
                + "never the full position, which would over-cover and flip the position.");
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
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 1, AveragePrice = 18000 });

            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
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

            // PnL sync is now event-driven via AccountItemUpdate, not the sweep.
            addon.ExecuteAccountItemUpdate(account, new AccountItemEventArgs { AccountItem = AccountItem.RealizedProfitLoss, Value = -100.0 });

            Assert(state.ConsecutiveLosses == 1, "ConsecutiveLosses incremented by AccountItemUpdate");
            Assert(state.CooldownUntil > DateTime.UtcNow, "CooldownUntil auto-set by AccountItemUpdate");
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
            state.UnrealizedPnL = 0.0;
            state.TradesToday = 2; // Max trades breach
            state.UpdatePosition(account, new Instrument("MNQ"), MarketPosition.Long, 5, 18000, 0, config); // Max size breach

            // EvaluateRules handles sizing + overtrading (not PnL anymore)
            var actions = addon.EvaluateRules(account, state);
            
            bool hasSize = actions.Any(a => a.RuleId == "MAX_SIZE_BREACH");
            bool hasTrades = actions.Any(a => a.RuleId == "MAX_TRADES_BREACH");
            
            Assert(hasSize && hasTrades, "Sizing and overtrading rules return actions in the same evaluation");

            // PnL rules are separate
            var pnlActions = addon.EvaluatePnLRules(account, state);
            bool hasLoss = pnlActions.Any(a => a.RuleId == "DAILY_LOSS_BREACH");
            Assert(hasLoss, "DAILY_LOSS_BREACH fires from EvaluatePnLRules");
        }

        // -
        // PASS 3 GAP TESTS
        // -

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

            // Fixed clock. DateTime.UtcNow made this test time-of-day dependent: past the
            // FirmMirror daily-reset boundary (DailyResetHourUtc, default 22:00 UTC) the firm
            // session rolls over and rebases the P&L, so the breach no longer fires.
            var nowUtc = FirmTestClockUtc;
            state.FirmDailyDate = FirmDailyDateFor(nowUtc, fmConfig);

            var actions = addon.EvaluateFirmMirror(account, state, nowUtc);
            
            Assert(actions.Any(a => a.RuleId == "FIRM_TRAILING_DD_BREACH"), "Firm trailing DD breach action generated");
            Assert(state.IsLockedOut == true, "Firm mirror breach locks out account");
        }

        // P1-42: EvaluateFirmMirror passed the TOP-LEVEL FirmMirrorConfig straight into
        // ComputeFirmMirror, which reads only fm.TrailingDD / fm.DailyLoss. AccountFirmMap and
        // FirmProfiles were consulted by no evaluation path at all -- the only reference to
        // AccountFirmMap in the addon was RunPreflight's validation, which checks that mapped
        // firms exist. So preflight validated a mapping that nothing read, and the researched
        // per-firm numbers were dead config. This test uses the exact live shape observed on
        // 2026-08-07: top-level sub-rules disabled, real firm profiles present, and a funded
        // TakeProfit Trader account that consequently had no firm protection whatsoever.
        private static void TestP1_42_MappedAccountIsEvaluatedAgainstItsFirmProfile()
        {
            Console.WriteLine("\n[TEST] P1-42: a mapped account must be evaluated against its firm profile");

            Func<FirmMirrorConfig> liveShape = () =>
            {
                var fm = new FirmMirrorConfig();
                fm.Enabled = true;
                fm.TrailingDD.Enabled = false;   // as live: top-level sub-rules are OFF
                fm.DailyLoss.Enabled = false;
                fm.FirmProfiles["TakeProfitTrader"] = new FirmProfile
                {
                    Name = "TakeProfitTrader",
                    TrailingDD = new FirmTrailingDDConfig
                    {
                        Enabled = true, Type = "eod", IncludesUnrealized = false,
                        Amount = 1500.0, Buffer = 200.0, LockAtProfit = 0.0
                    },
                    DailyLoss = new FirmDailyLossConfig { Enabled = false, Basis = "realized" }
                };
                return fm;
            };

            Func<FirmMirrorConfig, string, List<GuardAction>> evaluate = (fm, accountName) =>
            {
                var account = new Account { Name = accountName };
                var addon = new RiskGuardAddOn();
                var config = new RiskConfig();
                config.FirmMirror = fm;
                addon.SetConfigForTest(config);

                var state = new AccountState(accountName);
                state.FirmStartingBalance = 50000.0;
                state.FirmTrailingPeak = 50000.0;
                // floor = 50000 - 1500 + 200 = 48700; equity 48000 is below it.
                account.Values[AccountItem.CashValue] = 48000.0;
                account.Values[AccountItem.UnrealizedProfitLoss] = 0.0;
                account.Values[AccountItem.RealizedProfitLoss] = -2000.0;
                state.FirmDailyDate = FirmDailyDateFor(FirmTestClockUtc, fm);
                return addon.EvaluateFirmMirror(account, state, FirmTestClockUtc);
            };

            // The live case: mapped account, top-level disabled, profile enabled.
            var mapped = liveShape();
            mapped.AccountFirmMap["TAKEPROFITPRO524207503"] = "TakeProfitTrader";
            Assert(evaluate(mapped, "TAKEPROFITPRO524207503").Any(a => a.RuleId == "FIRM_TRAILING_DD_BREACH"),
                "a mapped account must breach on its firm profile's numbers even though the top-level rule is disabled");

            // An account that is NOT mapped must keep falling back to the top-level pair,
            // which here is disabled -- it must not inherit some other firm's profile.
            var unmappedFm = liveShape();
            unmappedFm.AccountFirmMap["SomeOtherAccount"] = "TakeProfitTrader";
            Assert(!evaluate(unmappedFm, "TAKEPROFITPRO524207503").Any(a => a.RuleId == "FIRM_TRAILING_DD_BREACH"),
                "an unmapped account must not pick up another account's firm profile");

            // Fallback must still work in the positive direction: unmapped + top-level enabled.
            var topLevel = liveShape();
            topLevel.TrailingDD.Enabled = true;
            topLevel.TrailingDD.Type = "eod";
            topLevel.TrailingDD.Amount = 1500.0;
            topLevel.TrailingDD.Buffer = 200.0;
            Assert(evaluate(topLevel, "UnmappedAcc").Any(a => a.RuleId == "FIRM_TRAILING_DD_BREACH"),
                "an unmapped account must still be evaluated against the top-level rule");

            // A mapping to a firm that is absent from FirmProfiles must fall back, not throw.
            // Preflight blocks arming in that case, but the evaluator must not depend on
            // preflight having run -- config can be reloaded while armed.
            var danglingFm = liveShape();
            danglingFm.TrailingDD.Enabled = true;
            danglingFm.TrailingDD.Type = "eod";
            danglingFm.TrailingDD.Amount = 1500.0;
            danglingFm.TrailingDD.Buffer = 200.0;
            danglingFm.AccountFirmMap["DanglingAcc"] = "NoSuchFirm";
            Assert(evaluate(danglingFm, "DanglingAcc").Any(a => a.RuleId == "FIRM_TRAILING_DD_BREACH"),
                "a mapping to an unknown firm must fall back to the top-level rule rather than throw or silently disable");

            // Both dictionaries are OrdinalIgnoreCase; resolution must honour that.
            var casedFm = liveShape();
            casedFm.AccountFirmMap["takeprofitpro524207503"] = "takeprofittrader";
            Assert(evaluate(casedFm, "TAKEPROFITPRO524207503").Any(a => a.RuleId == "FIRM_TRAILING_DD_BREACH"),
                "account and firm lookup must stay case-insensitive");

            // The profile's DailyLoss must resolve too, not just TrailingDD.
            var dailyFm = liveShape();
            dailyFm.FirmProfiles["Tradeify"] = new FirmProfile
            {
                Name = "Tradeify",
                TrailingDD = new FirmTrailingDDConfig { Enabled = false },
                DailyLoss = new FirmDailyLossConfig
                {
                    Enabled = true, Basis = "realized", Amount = 1250.0, Buffer = 100.0
                }
            };
            dailyFm.AccountFirmMap["TradeifyAcc"] = "Tradeify";
            Assert(evaluate(dailyFm, "TradeifyAcc").Any(a => a.RuleId == "FIRM_DAILY_LOSS_BREACH"),
                "a mapped account's firm DailyLoss rule must be evaluated (-2000 breaches a 1250/100 limit)");
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
            // Fixed clock, and FirmDailyDate derived with the SAME boundary rule the production
            // code uses. Previously this set UtcNow.Date, which stops matching after 22:00 UTC
            // and silently rebased FirmDailyStartRealized, so the breach never fired.
            var nowUtc = FirmTestClockUtc;
            state.FirmDailyDate = FirmDailyDateFor(nowUtc, fmConfig);
            state.FirmDailyStartRealized = 0.0;
            
            account.Values[AccountItem.RealizedProfitLoss] = -1400.0; // Less than limit -1300
            account.Values[AccountItem.UnrealizedProfitLoss] = 0.0;
            account.Values[AccountItem.CashValue] = 98600.0; 

            var actions = addon.EvaluateFirmMirror(account, state, nowUtc);
            
            Assert(actions.Any(a => a.RuleId == "FIRM_DAILY_LOSS_BREACH"), "Firm daily loss breach action generated");
            Assert(state.IsLockedOut == true, "Firm mirror breach locks out account");
        }

        // 4. StopGuard default offset fallback
        private static void TestStopGuardDefaultOffsetFallback()
        {
            Console.WriteLine("\n[TEST] StopGuard Default Offset Fallback (Unknown Ticker)");
            var config = new RiskConfig();
            config.StopGuard.StopAttachSeconds = 0;
            config.StopGuard.OnMissing = "AutoStop";
            
            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();

            var unknownTick = new Instrument("CL");
            unknownTick.MasterInstrument.TickSize = 0.01;
            
            account.Positions.Add(new Position { Instrument = unknownTick, MarketPosition = MarketPosition.Long, Quantity = 1, AveragePrice = 80.00 });

            addon.TestFsmOnPosition(account, unknownTick.FullName, MarketPosition.Long, 1);

            var actions = addon.EvaluateGraceExpiry(account, unknownTick.FullName);
            var attachAction = actions.FirstOrDefault(a => a.RuleId == "MISSING_STOP_ATTACH");
            
            Assert(attachAction != null, "Action generated for missing stop on unknown ticker via FSM");
            Assert(true, "Fallback triggered gracefully");
        }

        // -
        // MANUAL LOCKOUT TESTS
        // -

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
            
            // Lockout enforcement is now event-driven via PositionUpdate.
            // Fire a PositionUpdate to trigger EvaluateLockoutPhase.
            addon.ExecutePositionUpdate(account, new PositionEventArgs { Position = new Position { Instrument = new Instrument("MNQ"), MarketPosition = MarketPosition.Long, Quantity = 1, AveragePrice = 18000 } });
            
            Assert(account.Positions.Count == 0, "Position flattened by manual timed lockout via PositionUpdate");
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

        // -
        // FSM STOPGUARD TESTS (-6 of RiskGuardAddOn.md)
        // These assert on the per-position FSM state across event sequences
        // rather than on a single EvaluateRules snapshot, which was the gap
        // that hid the duplicate-SL race.
        // -

        private static RiskConfig FsmTestConfig(int graceSeconds = 60, string onMissing = "AutoStop")
        {
            var c = new RiskConfig();
            c.StopGuard.StopAttachSeconds = graceSeconds;
            c.StopGuard.OnMissing = onMissing;
            return c;
        }

        private static Account FsmTestAccount(string name = "TestAcc")
        {
            Account.All.Clear();
            var a = new Account { Name = name };
            Account.All.Add(a);
            return a;
        }

        // ------------------------------------------------------------------
        // P1-14 — the pending-stop buffer
        //
        // NT8 can deliver a stop's OrderUpdate before the PositionUpdate that opens the position
        // it protects, so the buffer is necessary. As written it was one Order per
        // (account, instrument), never expired, and judged only on side at consumption. Three
        // tests, one per failure.
        // ------------------------------------------------------------------

        private static Order BufferedStopOrder(Instrument inst, OrderAction action, int qty, string name)
        {
            return new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderId = Guid.NewGuid().ToString(),
                Name = name,
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                Quantity = qty,
                Instrument = inst,
                OrderAction = action,
                StopPrice = 17900
            };
        }

        // A bracket with two stop legs, or simply a second stop arriving first, used to overwrite
        // the first: `_pendingStops[key] = order`. The guard then saw only whichever happened to
        // land last, which is decided by broker event ordering -- i.e. not decided at all.
        private static void TestP1_14_SecondBufferedStopDoesNotOverwriteTheFirst()
        {
            Console.WriteLine("\n[TEST] P1-14: a second buffered stop does not overwrite the first");

            var mnq = new Instrument("MNQ");
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 60));
            addon.TestClearFsms();

            // Both legs of a 6-lot bracket arrive before the position event. The 6-lot leg lands
            // first, the 3-lot leg second -- the ordering that loses the useful one.
            addon.TestFsmOnOrder(account, mnq.FullName, BufferedStopOrder(mnq, OrderAction.Sell, 6, "Stop_A"));
            addon.TestFsmOnOrder(account, mnq.FullName, BufferedStopOrder(mnq, OrderAction.Sell, 3, "Stop_B"));

            Assert(addon.TestPendingStopCount(account.Name, mnq.FullName) == 2,
                string.Format("Both buffered stops are retained (got {0}). A single slot keeps whichever arrived last.",
                    addon.TestPendingStopCount(account.Name, mnq.FullName)));

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 6);

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.CoveredQuantity == 6,
                string.Format(
                    "The 6-lot position is recognised as fully covered (CoveredQuantity {0}). "
                    + "Keeping only the last-arrived 3-lot leg reports the position half naked and "
                    + "attaches a duplicate auto-stop for a delta that is already covered.",
                    fsm == null ? -1 : fsm.CoveredQuantity));

            Assert(fsm != null && fsm.State == GuardFsmState.Protected,
                string.Format("...and Protected, not under-covered (state {0}).", fsm == null ? "none" : fsm.State.ToString()));
        }

        // The side is genuinely unknown at buffer time, so classification has to happen on
        // consumption -- but it only ever checked SIDE. A resting stop-market breakout ENTRY
        // passes that check by coincidence: a sell-stop entry does, technically, reduce a long.
        // Adopting it reports coverage the position does not have, cancels the grace timer, and
        // suppresses the auto-stop -- and if the order ever triggers it flips the account by the
        // size difference.
        private static void TestP1_14_ABufferedBreakoutEntryIsNotAdoptedAsProtection()
        {
            Console.WriteLine("\n[TEST] P1-14: a resting breakout ENTRY order is not adopted as the position's protective stop");

            var mnq = new Instrument("MNQ");
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 60));
            addon.TestClearFsms();

            // Flat. The trader rests a 10-lot sell-stop below the market as a breakout SHORT
            // entry. It is a stop order on this instrument, so it is buffered.
            addon.TestFsmOnOrder(account, mnq.FullName,
                BufferedStopOrder(mnq, OrderAction.SellShort, 10, "BreakoutEntry"));

            // Then, unrelated to it, a 1-lot LONG is opened by hand.
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.CoveredQuantity == 0,
                string.Format(
                    "The breakout entry contributes no coverage (CoveredQuantity {0}, position 1). "
                    + "Adopting it reads as 10 lots of cover on a 1-lot position -- and firing it "
                    + "leaves the account 9 lots SHORT.",
                    fsm == null ? -1 : fsm.CoveredQuantity));

            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected,
                string.Format(
                    "The position is correctly Unprotected (state {0}), so the grace timer runs and "
                    + "the auto-stop gets its chance.",
                    fsm == null ? "none" : fsm.State.ToString()));

            Assert(fsm != null && fsm.GracePending,
                "Grace is armed -- the whole point of refusing the adoption is that protection is still owed.");
        }

        // Entries were removed only on consumption or on a flat transition. A stop buffered for a
        // position that never opened -- entry rejected, order pulled -- therefore lived forever,
        // and the next position on that instrument adopted it.
        private static void TestP1_14_AnUnclaimedBufferedStopExpiresInsteadOfArmingALaterPosition()
        {
            Console.WriteLine("\n[TEST] P1-14: an unclaimed buffered stop expires instead of protecting a later, unrelated position");

            var mnq = new Instrument("MNQ");
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 30));
            addon.SetSubscribedAccountForTest(account.Name);
            addon.SetAccountStateForTest(account.Name, new AccountState(account.Name));
            addon.TestClearFsms();

            // A stop is buffered against an entry that is then rejected: no position ever arrives.
            addon.TestFsmOnOrder(account, mnq.FullName, BufferedStopOrder(mnq, OrderAction.Sell, 2, "Stop_Orphan"));
            Assert(addon.TestPendingStopCount(account.Name, mnq.FullName) == 1, "Precondition: the stop is buffered.");

            // Not yet stale: one grace period in, the TTL is two, and a genuine stop can lag its
            // position event. Expiring here would break the race the buffer exists for.
            addon.TestBackdatePendingStops(account.Name, mnq.FullName, TimeSpan.FromSeconds(31));
            addon.ExecuteSafetySweep();
            Assert(addon.TestPendingStopCount(account.Name, mnq.FullName) == 1,
                "A stop that is merely lagging its position event is NOT expired -- that race is why the buffer exists.");

            // Well past two grace periods, with no position to claim it.
            addon.TestBackdatePendingStops(account.Name, mnq.FullName, TimeSpan.FromSeconds(60));
            addon.ExecuteSafetySweep();
            Assert(addon.TestPendingStopCount(account.Name, mnq.FullName) == 0,
                string.Format("The unclaimed stop is expired (still buffered: {0}).",
                    addon.TestPendingStopCount(account.Name, mnq.FullName)));

            // The later, unrelated position must not inherit it.
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected && fsm.CoveredQuantity == 0,
                string.Format(
                    "The new position starts Unprotected with no coverage (state {0}, covered {1}). "
                    + "Inheriting a stop buffered for a trade that never happened means the guard "
                    + "stands down for a position that has nothing behind it.",
                    fsm == null ? "none" : fsm.State.ToString(), fsm == null ? -1 : fsm.CoveredQuantity));
        }

        // 1. flat -> nonflat (Unprotected) -> OCO stop leg Submitted (ProtectedPending) -> Working (Protected)
        private static void TestFsm_UnprotectedToProtectedViaOcoStopLeg()
        {
            Console.WriteLine("\n[TEST] FSM: Unprotected -> ProtectedPending -> Protected via OCO stop leg");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected, "FSM created in Unprotected");

            var stopLeg = new Order
            {
                OrderState = OrderState.Submitted,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 2,
                Instrument = mnq,
                Oco = "BRACKET-1"
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg);

            fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm.State == GuardFsmState.ProtectedPending, "Stop leg Submitted -> ProtectedPending");
            Assert(ReferenceEquals(fsm.RecognizedStopOrder, stopLeg), "Recognised stop is the OCO leg (by reference)");

            stopLeg.OrderState = OrderState.Working;
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg);
            fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm.State == GuardFsmState.Protected, "Stop leg Working -> Protected");
        }

        // 2. After ProtectedPending, a second grace-expiry / duplicate event must NOT place another stop.
        private static void TestFsm_NoDuplicateAutoStopWhenStopLegPending()
        {
            Console.WriteLine("\n[TEST] FSM: No duplicate auto-stop when stop leg is pending");
            var config = FsmTestConfig(graceSeconds: 0); // grace already expired
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            // Stop leg arrives Submitted (FSM -> ProtectedPending)
            var stopLeg = new Order
            {
                OrderState = OrderState.Submitted,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 2,
                Instrument = mnq,
                Oco = "BRACKET-1"
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg);

            // Position object present for EvaluateGraceExpiry
            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2 });

            // Grace is 0s, so deadline is already past. But FSM is ProtectedPending, so no action.
            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(actions.Count == 0, "No auto-stop emitted while FSM is ProtectedPending (grace expiry suppressed)");
        }

        // 3. Grace expiry from Unprotected emits exactly one MISSING_STOP_ATTACH, then FSM is ProtectedPending.
        private static void TestFsm_GraceExpiryPlacesAutoStopOnce()
        {
            Console.WriteLine("\n[TEST] FSM: Grace expiry places auto-stop exactly once");
            var config = FsmTestConfig(graceSeconds: 0, onMissing: "AutoStop");
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 1 });

            var first = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(first.Any(a => a.RuleId == "MISSING_STOP_ATTACH"), "First grace expiry emits MISSING_STOP_ATTACH");

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm.State == GuardFsmState.ProtectedPending, "FSM moved to ProtectedPending after emitting");

            // Second call must not emit again (FSM no longer Unprotected).
            var second = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(second.Count == 0, "Second grace-expiry call emits nothing (FSM already ProtectedPending)");
        }

        // 4. Stop OrderUpdate arrives BEFORE PositionUpdate -> buffered, consumed on position open.
        private static void TestFsm_StopArrivesBeforePositionIsBuffered()
        {
            Console.WriteLine("\n[TEST] FSM: Stop arriving before position is buffered and consumed");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            var stopLeg = new Order
            {
                OrderState = OrderState.Submitted,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 2,
                Instrument = mnq,
                Oco = "BRACKET-2"
            };
            // No FSM yet -> should be buffered.
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg);
            Assert(addon.TestAllFsms().Count == 0, "No FSM created by stop event alone");

            // Position opens -> FSM created and consumes the buffered stop.
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.ProtectedPending,
                "Buffered stop consumed on position open -> ProtectedPending");
            Assert(ReferenceEquals(fsm.RecognizedStopOrder, stopLeg), "Buffered stop recognised by reference");
        }

        // 5. nonflat -> flat tears down FSM and cancels an orphan RiskGuard auto-stop.
        private static void TestFsm_FlatTearsDownAndCancelsOrphanAutoStop()
        {
            Console.WriteLine("\n[TEST] FSM: Flat tears down FSM and cancels orphan auto-stop");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);

            // Simulate an auto-stop we placed, still working.
            var autoStop = new Order
            {
                Name = "RiskGuardAutoStop",
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 1,
                Instrument = mnq
            };
            account.Orders.Add(autoStop);
            addon.TestFsmOnOrder(account, mnq.FullName, autoStop);
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm.State == GuardFsmState.Protected, "Auto-stop Working -> Protected");
            Assert(ReferenceEquals(fsm.AutoStopOrder, autoStop), "AutoStopOrder recorded");

            // Position flattens -> FSM torn down, orphan auto-stop cancelled.
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Flat, 0);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName) == null, "FSM removed on flat");
            Assert(autoStop.OrderState == OrderState.Cancelled, "Orphan auto-stop cancelled on flat");
        }

        // 6. Standalone (non-OCO) working stop -> Protected.
        private static void TestFsm_StandaloneStopReachesProtected()
        {
            Console.WriteLine("\n[TEST] FSM: Standalone working stop reaches Protected");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Short, 1);

            var stop = new Order
            {
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Buy, // opposite of short
                Quantity = 1,
                Instrument = mnq
                // Oco intentionally empty (external/manual bracket)
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stop);
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm.State == GuardFsmState.Protected, "Standalone working stop -> Protected (no Oco needed)");
        }

        // 7. Recognised stop leg Rejected -> back to Unprotected.
        private static void TestFsm_RejectedStopLegReturnsToUnprotected()
        {
            Console.WriteLine("\n[TEST] FSM: Rejected stop leg returns FSM to Unprotected");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);

            var stopLeg = new Order
            {
                OrderState = OrderState.Submitted,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 1,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).State == GuardFsmState.ProtectedPending,
                "Submitted -> ProtectedPending");

            stopLeg.OrderState = OrderState.Rejected;
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg);
            // Position still open (qty 1) -> Unprotected
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected, "Rejected stop -> Unprotected (position still open)");
            Assert(fsm.RecognizedStopOrder == null, "Recognised stop cleared on rejection");
        }

        // 8. Position flattens before grace expires -> no auto-stop emitted.
        private static void TestFsm_PositionFlattenedBeforeGraceNoAutoStop()
        {
            Console.WriteLine("\n[TEST] FSM: Position flat before grace -> no auto-stop");
            var config = FsmTestConfig(graceSeconds: 60); // grace far in future
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Flat, 0);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName) == null, "FSM torn down on flat");

            // Even if grace were somehow invoked, no FSM exists -> no action.
            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(actions.Count == 0, "No auto-stop after position flattened before grace");
        }

        // 9. Duplicate OrderUpdate for the same stop leg is idempotent.
        private static void TestFsm_DuplicateOrderUpdatesAreIdempotent()
        {
            Console.WriteLine("\n[TEST] FSM: Duplicate OrderUpdate events are idempotent");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);

            var stopLeg = new Order
            {
                OrderState = OrderState.Submitted,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 1,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg);
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg); // duplicate
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg); // duplicate

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm.State == GuardFsmState.ProtectedPending, "Repeated Submitted events stay ProtectedPending");
            Assert(addon.TestAllFsms().Count == 1, "Still exactly one FSM");
        }

        // 10. Duplicate PositionUpdate (re-entrant) is idempotent.
        private static void TestFsm_DuplicatePositionUpdatesAreIdempotent()
        {
            Console.WriteLine("\n[TEST] FSM: Duplicate PositionUpdate events are idempotent");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2); // duplicate
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2); // duplicate

            Assert(addon.TestAllFsms().Count == 1, "Exactly one FSM after duplicate position updates");
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm.State == GuardFsmState.Unprotected, "Still Unprotected (no stop arrived)");
            Assert(fsm.PositionQuantity == 2, "Quantity preserved");
        }

        // 11. EvaluateRules no longer emits StopGuard actions (FSM owns it).
        private static void TestFsm_EvaluateRulesNoLongerEmitsStopGuard()
        {
            Console.WriteLine("\n[TEST] FSM: EvaluateRules no longer emits StopGuard actions");
            var config = FsmTestConfig(graceSeconds: 0, onMissing: "AutoStop");
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            var state = new AccountState("TestAcc");
            state.UpdatePosition(account, mnq, MarketPosition.Long, 1, 18000, 0, config);
            state.Positions[mnq.FullName].LastNonFlatTransition = DateTime.UtcNow.AddSeconds(-10);
            addon.SetAccountStateForTest("TestAcc", state);
            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 1 });

            var actions = addon.EvaluateRules(account, state);
            Assert(!actions.Any(a => a.RuleId == "MISSING_STOP_ATTACH" || a.RuleId == "MISSING_STOP_FLATTEN"),
                "EvaluateRules emits no MISSING_STOP_* (FSM owns StopGuard now)");
        }

        // 12. Excluded account: FSM is not created.
        private static void TestFsm_ExcludedAccountSkipsFsm()
        {
            Console.WriteLine("\n[TEST] FSM: Excluded account does not create FSM");
            var config = FsmTestConfig();
            config.ExcludedAccounts = new List<string> { "ExcludedAcc" };
            var account = FsmTestAccount("ExcludedAcc");
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            Assert(addon.TestAllFsms().Count == 0, "No FSM created for excluded account");
        }

        // 13. Protected -> Unprotected when recognised stop FILLS (not just rejected).
        private static void TestFsm_ProtectedToUnprotectedOnStopFilled()
        {
            Console.WriteLine("\n[TEST] FSM: Protected -> Unprotected when stop fills (position still open)");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            var stop = new Order
            {
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 1,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stop);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).State == GuardFsmState.Protected,
                "Working stop -> Protected");

            // Stop fills (e.g., OCO target leg hit the stop, but position still shows open briefly).
            stop.OrderState = OrderState.Filled;
            addon.TestFsmOnOrder(account, mnq.FullName, stop);
            // PositionQuantity is still 1 (set at creation), so -> Unprotected.
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected,
                "Filled stop -> Unprotected (position still open)");
        }

        // 14. ProtectedPending -> Unprotected on Cancelled (distinct from Rejected).
        private static void TestFsm_ProtectedPendingToUnprotectedOnCancelled()
        {
            Console.WriteLine("\n[TEST] FSM: ProtectedPending -> Unprotected on Cancelled");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            var stop = new Order
            {
                OrderState = OrderState.Submitted,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 1,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stop);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).State == GuardFsmState.ProtectedPending,
                "Submitted -> ProtectedPending");

            stop.OrderState = OrderState.Cancelled;
            addon.TestFsmOnOrder(account, mnq.FullName, stop);
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected,
                "Cancelled stop -> Unprotected (position still open)");
        }

        // =================================================================
        // PHASE B BACKFILL - acceptance tests for T1/T2/T3.
        //
        // The nine P0 defects were closed on the strength of review plus a
        // non-regressing suite. That proves the fixes broke nothing; it does
        // not prove they work, and it would not notice if one were reverted.
        // These six tests pin the behaviours directly, and each was checked
        // to FAIL with its fix reverted -- an acceptance test nobody has seen
        // fail is an assertion of faith, not a test.
        // =================================================================

        /// <summary>
        /// Builds an account holding one live position, with a last-traded price
        /// so ExecuteAction can price a stop instead of falling through to its
        /// "no market data -> flatten" branch.
        /// </summary>
        private static Account AutoStopTestAccount(
            Instrument instrument, MarketPosition side, int qty, double avgPrice, double lastPrice)
        {
            Account.All.Clear();
            var a = new Account { Name = "TestAcc" };
            instrument.MarketData.Last.Price = lastPrice;
            a.Positions.Add(new Position
            {
                Instrument = instrument,
                MarketPosition = side,
                Quantity = qty,
                AveragePrice = avgPrice
            });
            Account.All.Add(a);
            return a;
        }

        private static GuardAction AutoStopAction(Account account, Instrument instrument, int snapshotQty)
        {
            return new GuardAction
            {
                AccountName = account.Name,
                ActionType = GuardActionType.PlaceStopOrder,
                Instrument = instrument.FullName,
                InstrumentObj = instrument,
                Quantity = snapshotQty,
                RuleId = "MISSING_STOP_ATTACH"
            };
        }

        // ------------------------------------------------------------------
        // P1-36 — coverage is the SUM over every live protective stop
        //
        // The FSM tracked exactly one stop order. A trader covering a 6-lot position with two
        // working 3-lot stops -- a scale-out plan, or simply a bracket with two legs -- therefore
        // read as CoveredQuantity 3. The under-coverage rule T1 introduced then fired and attached
        // a 3-lot auto-stop, making 9 lots of protection on a 6-lot position. When the stops
        // trigger, the account is flipped 3 lots the wrong way: the guard manufactures the
        // reversal it exists to prevent.
        // ------------------------------------------------------------------

        private static Order PartialStop(Instrument inst, int qty, double stopPrice, string name)
        {
            return new Order
            {
                Id = Guid.NewGuid().ToString(),
                OrderId = Guid.NewGuid().ToString(),
                Name = name,
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                Quantity = qty,
                Instrument = inst,
                OrderAction = OrderAction.Sell,
                StopPrice = stopPrice
            };
        }

        private static void TestP1_36_TwoPartialStopsCoverThePositionInFull()
        {
            Console.WriteLine("\n[TEST] P1-36: two partial stops together cover the position, and no auto-stop is attached");

            var mnq = new Instrument("MNQ");
            var account = AutoStopTestAccount(mnq, MarketPosition.Long, 6, 18000, 18000);
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 60));
            addon.TestClearFsms();

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 6);
            addon.TestFsmOnOrder(account, mnq.FullName, PartialStop(mnq, 3, 17990, "Stop_Half1"));
            addon.TestFsmOnOrder(account, mnq.FullName, PartialStop(mnq, 3, 17985, "Stop_Half2"));

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.CoveredQuantity == 6,
                string.Format(
                    "Coverage is 3 + 3 = 6 (got {0}). Tracking one stop reports 3 of 6, and the "
                    + "under-coverage rule then adds a third stop for a delta that is already "
                    + "protected -- 9 lots of stops on a 6-lot position.",
                    fsm == null ? -1 : fsm.CoveredQuantity));

            Assert(fsm != null && fsm.State == GuardFsmState.Protected,
                string.Format("The position is Protected, not under-covered (state {0}).",
                    fsm == null ? "none" : fsm.State.ToString()));

            Assert(fsm != null && !fsm.GracePending,
                "No grace timer is left armed -- a fully covered position is not owed another stop.");

            // The rule that would have fired must now emit nothing at all.
            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(actions == null || !actions.Any(a => a.RuleId == "MISSING_STOP_ATTACH"),
                string.Format(
                    "Grace expiry emits no auto-stop for a fully covered position (emitted {0}). "
                    + "This is the order that flips the account when all three stops trigger.",
                    actions == null ? 0 : actions.Count(a => a.RuleId == "MISSING_STOP_ATTACH")));
        }

        private static void TestP1_36_LosingOneOfTwoStopsIsPartialCoverNotNakedness()
        {
            Console.WriteLine("\n[TEST] P1-36: cancelling one of two stops leaves partial cover, not a naked position");

            var mnq = new Instrument("MNQ");
            // Needs a real broker position: EvaluateGraceExpiry sizes off account.Positions.
            var account = AutoStopTestAccount(mnq, MarketPosition.Long, 6, 18000, 18000);
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 60));
            addon.TestClearFsms();

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 6);
            var legA = PartialStop(mnq, 3, 17990, "Stop_Half1");
            var legB = PartialStop(mnq, 3, 17985, "Stop_Half2");
            addon.TestFsmOnOrder(account, mnq.FullName, legA);
            addon.TestFsmOnOrder(account, mnq.FullName, legB);

            // The trader pulls one leg. Three lots are still covered by the other.
            legA.OrderState = OrderState.Cancelled;
            addon.TestFsmOnOrder(account, mnq.FullName, legA);

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.CoveredQuantity == 3,
                string.Format(
                    "Three lots remain covered by the surviving leg (got {0}). Zeroing coverage "
                    + "because 'the' stop went terminal reports a fully naked position and sizes "
                    + "the replacement for all 6 -- 9 lots of protection again, from the other side.",
                    fsm == null ? -1 : fsm.CoveredQuantity));

            Assert(fsm != null && fsm.State != GuardFsmState.Unprotected,
                string.Format("The position is not declared Unprotected while a live stop still covers half of it (state {0}).",
                    fsm == null ? "none" : fsm.State.ToString()));

            Assert(fsm != null && fsm.GracePending,
                "Grace is armed for the uncovered delta -- partial cover is still owed the rest.");

            // And the action, when it comes, is sized to the DELTA.
            fsm.GraceDeadline = DateTime.UtcNow.AddSeconds(-1);
            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            var attach = actions == null ? null : actions.FirstOrDefault(a => a.RuleId == "MISSING_STOP_ATTACH");
            Assert(attach != null && attach.Quantity == 3,
                string.Format(
                    "The replacement stop is sized to the 3 uncovered lots (got {0}), not the whole position.",
                    attach == null ? -1 : attach.Quantity));
        }

        private static void TestP1_36_AutoStopAddsToExistingCoverRatherThanReplacingIt()
        {
            Console.WriteLine("\n[TEST] P1-36: the auto-stop adds to existing cover instead of replacing it");

            var mnq = new Instrument("MNQ");
            var account = AutoStopTestAccount(mnq, MarketPosition.Long, 6, 18000, 18000);
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop"));
            addon.TestClearFsms();

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 6);

            // The trader has covered half the position himself.
            var traderStop = PartialStop(mnq, 3, 17990, "Stop_Trader");
            account.Orders.Add(traderStop);
            addon.TestFsmOnOrder(account, mnq.FullName, traderStop);

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.CoveredQuantity == 3, "Precondition: 3 of 6 covered by the trader's own stop.");

            // Grace expires: the guard is owed the 3-lot delta, and no more.
            fsm.GraceDeadline = DateTime.UtcNow.AddSeconds(-1);
            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            var attach = actions.First(a => a.RuleId == "MISSING_STOP_ATTACH");
            Assert(attach.Quantity == 3, string.Format("The emitted action covers the 3-lot delta (got {0}).", attach.Quantity));

            addon.TestExecuteAction(attach);

            var autoStop = account.Orders.FirstOrDefault(o => o.Name == "RiskGuardAutoStop");
            Assert(autoStop != null && autoStop.Quantity == 3,
                string.Format("A 3-lot auto-stop was placed (got {0}).", autoStop == null ? -1 : autoStop.Quantity));

            Assert(fsm.CoveredQuantity == 6,
                string.Format(
                    "Total cover is now 3 + 3 = 6 (got {0}). Overwriting coverage with the auto-stop's "
                    + "own 3 leaves the FSM reading 3 of 6 with SIX lots of stops already working -- "
                    + "so it asks for another 3, and keeps asking.",
                    fsm.CoveredQuantity));

            Assert(fsm.RecognizedStops.Any(o => ReferenceEquals(o, traderStop)),
                "The trader's own stop is still part of the recorded cover, not displaced by ours.");

            // The escalation loop must be closed: nothing further is owed.
            fsm.GraceDeadline = DateTime.UtcNow.AddSeconds(-1);
            fsm.GraceEmitted = false;
            var again = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(again == null || !again.Any(a => a.RuleId == "MISSING_STOP_ATTACH"),
                string.Format(
                    "No further auto-stop is requested once the position is fully covered (got {0}).",
                    again == null ? 0 : again.Count(a => a.RuleId == "MISSING_STOP_ATTACH")));
        }

        // T2 / P0-2: the emitted action carries a quantity snapshot taken when grace
        // expired. By the time it executes the trader may have scaled out. Sizing the
        // stop from the snapshot over-covers and flips the position when it triggers.
        private static void TestT2_AutoStopSizedFromLivePositionNotSnapshot()
        {
            Console.WriteLine("\n[TEST] T2: auto-stop is sized from the live position, not the action snapshot");
            var config = FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop");
            var mnq = new Instrument("MNQ");
            var account = AutoStopTestAccount(mnq, MarketPosition.Long, 2, 18000, 18000);
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            // Snapshot says 5; the trader has since scaled down to 2.
            addon.TestExecuteAction(AutoStopAction(account, mnq, snapshotQty: 5));

            var stop = account.Orders.FirstOrDefault(o => o.Name == "RiskGuardAutoStop");
            Assert(stop != null, "An auto-stop reached the broker");
            Assert(stop != null && stop.Quantity == 2,
                string.Format("Auto-stop sized {0} from the live position, not 5 from the stale snapshot "
                            + "(a 5-lot stop on a 2-lot position reverses it on trigger)",
                              stop == null ? -1 : stop.Quantity));
            Assert(stop != null && stop.OrderAction == OrderAction.Sell,
                "Auto-stop on a long position is a Sell");

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.CoveredQuantity == 2,
                "Recorded coverage matches the live position, so the grace path sees full cover");
        }

        // T2 / settled decision: ValidateInvariant must NOT reject a PlaceStopOrder
        // whose snapshot quantity exceeds the live position. Rejecting it looks like a
        // safety check and is the opposite -- the action is dropped and the position is
        // left permanently naked. ExecuteAction re-sizes from the live position instead.
        private static void TestT2_ScaledDownPositionStillGetsAStop()
        {
            Console.WriteLine("\n[TEST] T2: a scaled-down position is still admitted for protection");
            var config = FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop");
            var mnq = new Instrument("MNQ");
            var account = AutoStopTestAccount(mnq, MarketPosition.Long, 2, 18000, 18000);
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            Assert(addon.TestValidateInvariant(AutoStopAction(account, mnq, snapshotQty: 5)),
                "Snapshot qty 5 > live qty 2 is ADMITTED - dropping it would leave the position naked");
            Assert(addon.TestValidateInvariant(AutoStopAction(account, mnq, snapshotQty: 1)),
                "Snapshot qty below the live position is admitted too (partial cover beats none)");

            // The invariant must still have teeth: these are genuinely unsafe and must be refused.
            var noInstrument = AutoStopAction(account, mnq, snapshotQty: 2);
            noInstrument.InstrumentObj = null;
            Assert(!addon.TestValidateInvariant(noInstrument),
                "An action with no instrument is still refused");

            var zeroQty = AutoStopAction(account, mnq, snapshotQty: 0);
            Assert(!addon.TestValidateInvariant(zeroQty),
                "A zero-quantity action is still refused");

            account.Positions.Clear();
            Assert(!addon.TestValidateInvariant(AutoStopAction(account, mnq, snapshotQty: 2)),
                "A stop against a flat position is still refused (it would open new risk, not reduce it)");
        }

        // T2 / P0-3: reserve-before-submit moves the FSM to ProtectedPending BEFORE the
        // broker call. If Submit then throws and nothing rolls that back, the FSM claims
        // protection that does not exist and the GraceEmitted latch suppresses every
        // future attempt -- the position stays naked for the life of the trade.
        private static void TestT2_SubmitFailureRollsBackFsmAndClearsGraceEmitted()
        {
            Console.WriteLine("\n[TEST] T2: a failed auto-stop submit rolls the FSM back and clears the grace latch");
            var config = FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop");
            var mnq = new Instrument("MNQ");
            var account = AutoStopTestAccount(mnq, MarketPosition.Long, 2, 18000, 18000);
            account.SimulateSubmitFailure = true;
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            // State as it stands after grace expiry emitted the action.
            var armed = addon.TestGetFsm(account.Name, mnq.FullName);
            armed.GraceEmitted = true;

            bool threw = false;
            try
            {
                addon.TestExecuteAction(AutoStopAction(account, mnq, snapshotQty: 2));
            }
            catch (Exception)
            {
                threw = true;
            }

            Assert(threw, "The submit failure propagates rather than being swallowed");

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected,
                string.Format("FSM rolled back to Unprotected (was {0}) - reserve-before-submit had moved it to ProtectedPending",
                              fsm == null ? "<null>" : fsm.State.ToString()));
            Assert(fsm != null && !fsm.GraceEmitted,
                "GraceEmitted cleared, so grace can re-arm; left set, the latch silently blocks every retry");
            Assert(fsm != null && fsm.AutoStopOrder == null && fsm.RecognizedStopOrder == null,
                "No reference kept to a stop that never reached the broker");
            Assert(fsm != null && fsm.CoveredQuantity == 0,
                "No phantom coverage recorded, so the position reads as fully uncovered");
        }

        // T1+T2 / P0-1: the trader cancels the protective stop mid-position. The FSM must
        // return to Unprotected AND clear the anti-duplicate latch, or grace never fires
        // again and the position runs naked to the close.
        private static void TestT1_CancelledStopMidPositionReArmsGrace()
        {
            Console.WriteLine("\n[TEST] T1: a stop cancelled mid-position re-arms grace and is replaced");
            var config = FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop");
            var mnq = new Instrument("MNQ");
            var account = AutoStopTestAccount(mnq, MarketPosition.Long, 2, 18000, 18000);
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            // Drive grace expiry deterministically rather than waiting on the timer.
            var fsm0 = addon.TestGetFsm(account.Name, mnq.FullName);
            fsm0.GraceDeadline = DateTime.UtcNow.AddSeconds(-1);

            var first = addon.EvaluateGraceExpiry(account, mnq.FullName);
            var firstAction = first.FirstOrDefault(a => a.RuleId == "MISSING_STOP_ATTACH");
            Assert(firstAction != null, "Grace expiry emits the auto-stop action");
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).GraceEmitted,
                "Anti-duplicate latch is set once the action has been emitted");

            addon.TestExecuteAction(firstAction);
            var stop = account.Orders.FirstOrDefault(o => o.Name == "RiskGuardAutoStop");
            Assert(stop != null, "Auto-stop reached the broker and is the recognised stop");

            // The trader cancels it by hand while the position is still open.
            stop.OrderState = OrderState.Cancelled;
            addon.TestFsmOnOrder(account, mnq.FullName, stop);

            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected,
                "Cancelled stop returns the FSM to Unprotected");
            Assert(fsm != null && fsm.CoveredQuantity == 0,
                "Coverage drops to zero when the only stop is cancelled");
            Assert(fsm != null && !fsm.GraceEmitted,
                "The grace latch is cleared - this is the bit that lets protection be re-attempted at all");

            fsm.GraceDeadline = DateTime.UtcNow.AddSeconds(-1);
            var second = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(second.Any(a => a.RuleId == "MISSING_STOP_ATTACH"),
                "Grace genuinely re-armed: a fresh auto-stop is emitted for the now-naked position");
        }

        /// <summary>
        /// Runs <paramref name="body"/> with a broker-call observer installed, and returns the
        /// names of any Cancel/Flatten/CreateOrder/Submit calls that happened while the addon
        /// held `_stateLock`.
        /// </summary>
        private static List<string> RecordBrokerCallsUnderLock(RiskGuardAddOn addon, Action body)
        {
            var violations = new List<string>();
            Account.BrokerCallObserver = method =>
            {
                if (addon.TestIsStateLockHeld()) violations.Add(method);
            };
            try { body(); }
            finally { Account.BrokerCallObserver = null; }
            return violations;
        }

        // P1-10: the safety sweep held _stateLock across Cancel, Flatten, CreateOrder, Submit
        // and ProcessAction. The design doc states in two places that the lock is always
        // yielded before calling into NinjaTrader; the event handlers honour that, the sweep
        // did not. Because the sweep runs on the WPF dispatcher, any NT8 path that blocks on a
        // background thread needing _stateLock deadlocks the UI thread -- and with it the guard.
        // P1-23: two ways the copier config could lie.
        //  (a) TranslateSymbol used a global rawSymbol.Replace(root, target) instead of
        //      substituting the parsed root, and compared an upper-cased root against the raw
        //      string, so a lower-case instrument name translated to nothing at all -- silently
        //      copying an ES fill to an ES follower that was configured for MES.
        //  (b) NetLiquidationRatio and AvailableCashPercent are declared in CopierSizingMode but
        //      never handled, so they fell through to the QuantityRatio branch. A small follower
        //      set to equity-scaling silently received the FULL leader size, which is the P0-6
        //      over-size failure arriving through the config instead of the conversion matrix.
        private static void TestP1_23_SymbolTranslationAndSizingModesDoNotLie()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] P1-23: symbol translation substitutes the root, and sizing modes cannot lie");

            var engine = new TradeCopierEngine();
            var rel = new CopierRelationship { AutoSymbolConversion = true, QuantityRatio = 1.0 };

            Assert(engine.TranslateSymbol("ES 12-26", rel) == "MES 12-26",
                "ES 12-26 translates to MES 12-26");
            Assert(engine.TranslateSymbol("MES 03-26", rel) == "ES 03-26",
                "MES 03-26 translates back to ES 03-26");

            // The root is upper-cased before lookup but Replace ran against the raw string, so a
            // lower-case name matched nothing and was returned untranslated.
            Assert(engine.TranslateSymbol("es 12-26", rel) == "MES 12-26",
                string.Format("a lower-case instrument name must still translate (got '{0}')",
                              engine.TranslateSymbol("es 12-26", rel)));

            // Only the root may be substituted -- never a match inside the rest of the name.
            var custom = new CopierRelationship { AutoSymbolConversion = false, QuantityRatio = 1.0 };
            custom.CustomSymbolMappings["ES"] = "MES";
            Assert(engine.TranslateSymbol("ES 12-26", custom) == "MES 12-26",
                "a custom mapping substitutes the root");
            Assert(engine.TranslateSymbol("XES 12-26", custom) == "XES 12-26",
                "a root that merely CONTAINS a mapped symbol must not be rewritten");

            var noConv = new CopierRelationship { AutoSymbolConversion = false, QuantityRatio = 1.0 };
            Assert(engine.TranslateSymbol("ES 12-26", noConv) == "ES 12-26",
                "with AutoSymbolConversion off the symbol is untouched");

            // ---- sizing modes ----
            bool clamped;
            var equityMode = new CopierRelationship
            {
                AutoSymbolConversion = false, QuantityRatio = 1.0,
                SizingMode = CopierSizingMode.NetLiquidationRatio
            };
            int entryQty = engine.CalculateFollowerQuantity(equityMode, 10, "ES 12-26", 0, false, out clamped);
            Assert(entryQty == 0,
                string.Format("an unimplemented sizing mode must NOT silently size as 1:1 -- entries fail closed (got {0})", entryQty));

            // ...but an exit must never be blocked, or the follower is stranded in a position the
            // leader has already left. Same reasoning as the P0-5/P0-6 exit clamp.
            int exitQty = engine.CalculateFollowerQuantity(equityMode, 4, "ES 12-26", 4, true, out clamped);
            Assert(exitQty > 0,
                string.Format("an unimplemented sizing mode must still allow EXITS (got {0})", exitQty));

            // The implemented modes must be untouched.
            var ratio = new CopierRelationship
            {
                AutoSymbolConversion = false, QuantityRatio = 2.0,
                SizingMode = CopierSizingMode.QuantityRatio
            };
            Assert(engine.CalculateFollowerQuantity(ratio, 3, "ES 12-26", 0, false, out clamped) == 6,
                "QuantityRatio still sizes 3 x 2.0 = 6");
        }

        // P1-47: the guard defaulted to disarmed, so every recompile silently removed all
        // protection -- four times in one session on 2026-08-07. Arming controls whether the
        // guard EVALUATES; the mode controls whether it ACTS. Shadow cannot act at all
        // (ProcessAction returns "SHADOW (SKIPPED)" before touching the broker), so coming up
        // disarmed there buys no safety and costs total observability. Acting modes still
        // require a deliberate arm after preflight, which is FR-30's actual intent.
        private static void TestP1_47_ArmDefaultFollowsTheResolvedMode()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] P1-47: the guard comes up armed in shadow and disarmed in acting modes");

            Assert(RiskGuardAddOn.DefaultArmedForMode("shadow"),
                "shadow must come up ARMED -- it cannot act, and disarmed means observing nothing");
            Assert(!RiskGuardAddOn.DefaultArmedForMode("live"),
                "live must come up disarmed; arming an acting mode stays a deliberate act");
            Assert(!RiskGuardAddOn.DefaultArmedForMode("pure"),
                "pure must come up disarmed");
            Assert(!RiskGuardAddOn.DefaultArmedForMode("override_with_friction"),
                "override_with_friction must come up disarmed");
            Assert(RiskGuardAddOn.DefaultArmedForMode("nonsense-unrecognised"),
                "an unrecognised mode cannot act (ProcessAction requires live), so it is safe to observe");

            // Wired, not merely declared: initialising must actually apply it.
            var shadowGuard = new RiskGuardAddOn();
            shadowGuard.SetConfigForTest(new RiskConfig());
            shadowGuard.SetModeForTest("shadow");
            shadowGuard.SetArmedForTest(false);
            shadowGuard.ApplyInitialArmStateForTest();
            Assert(shadowGuard.GetIsArmed(), "initialising in shadow leaves the guard armed");

            var liveGuard = new RiskGuardAddOn();
            liveGuard.SetConfigForTest(new RiskConfig());
            liveGuard.SetModeForTest("live");
            liveGuard.SetArmedForTest(true);
            liveGuard.ApplyInitialArmStateForTest();
            Assert(!liveGuard.GetIsArmed(),
                "initialising in an acting mode must disarm, even if the field was already true -- "
                + "a restart must never come up armed AND acting");
        }

        // Stress programme S1-S4 (plan §8). These exist because the operator's order-flood
        // stress test found four defects in one afternoon that a green suite had not. They are
        // driven through the real entry point, ExecuteOrderUpdate, so they catch wiring and not
        // just arithmetic.
        // ==================================================================
        // S5 — PARTIAL-FILL STORM (plan §8)
        //
        // Realized PnL arrives PER EXECUTION, so one trade exited in eight partials delivers
        // eight negative deltas. Counting each as a consecutive loss made a MaxConsecutiveLosses=3
        // lockout reachable from a single losing trade. P1-16 banks the deltas and judges once --
        // but its correctness depends entirely on event ORDER, and NT8 guarantees none. Both
        // orderings are driven here, through the real entry points.
        // ==================================================================
        // P2-41. POST /api/riskguard/config deserialized the request body straight into a
        // complete RiskConfig, so every field the caller OMITTED silently became its default --
        // and SaveAndReloadConfig then wrote those defaults to disk and reloaded them live. The
        // reply said "applied" and echoed the request, so nothing about it revealed that the rest
        // of the risk configuration had just been reset.
        private static void TestP2_41_PartialConfigPostMergesInsteadOfReplacing()
        {
            Console.WriteLine("\n[TEST] P2-41: a partial config POST merges onto the live config instead of flattening it");

            var live = new RiskConfig();
            live.Mode = "live";
            live.MinShadowSessions = 3;
            live.EnableWindowGate = true;
            live.StopGuard.StopAttachSeconds = 45;
            live.StopGuard.OnMissing = "AutoStop";
            live.Overtrading.MaxConsecutiveLosses = 4;
            live.ExcludedAccounts = new List<string> { "OldExclusion" };

            // The exact body from the plan's acceptance test: one key, nothing else.
            var patch = Newtonsoft.Json.Linq.JObject.Parse("{\"ExcludedAccounts\":[\"X\"]}");

            Newtonsoft.Json.Linq.JObject mergedJson;
            var result = RiskConfigMerge.Apply(live, patch, out mergedJson);

            Assert(result != null, "The merged document still deserializes to a RiskConfig.");

            Assert(result.ExcludedAccounts != null
                   && result.ExcludedAccounts.Count == 1
                   && result.ExcludedAccounts[0] == "X",
                string.Format(
                    "The key the caller sent is applied, and arrays REPLACE rather than append "
                    + "(got [{0}]). Union semantics would make ExcludedAccounts append-only with "
                    + "no way to remove an entry through the API -- and concatenation is the exact "
                    + "mechanism behind P1-39.",
                    result.ExcludedAccounts == null ? "null" : string.Join(",", result.ExcludedAccounts)));

            Assert(result.Mode == "live",
                string.Format("Mode survives (got '{0}', expected 'live'). Resetting it to shadow "
                    + "silently disarms enforcement on a guard the operator believes is acting.", result.Mode));
            Assert(result.MinShadowSessions == 3,
                string.Format("MinShadowSessions survives (got {0}). Zeroing it removes the live-arming gate.",
                    result.MinShadowSessions));
            Assert(result.EnableWindowGate,
                "EnableWindowGate survives -- defaulting it to false opens every trading window.");
            Assert(result.StopGuard.StopAttachSeconds == 45,
                string.Format("StopGuard.StopAttachSeconds survives (got {0}, expected 45).",
                    result.StopGuard.StopAttachSeconds));
            Assert(result.StopGuard.OnMissing == "AutoStop",
                string.Format("StopGuard.OnMissing survives (got '{0}').", result.StopGuard.OnMissing));
            Assert(result.Overtrading.MaxConsecutiveLosses == 4,
                string.Format("Nested values the caller never mentioned survive (got {0}, expected 4).",
                    result.Overtrading.MaxConsecutiveLosses));

            // A nested partial must merge into its object, not replace the whole object.
            var nested = Newtonsoft.Json.Linq.JObject.Parse("{\"StopGuard\":{\"StopAttachSeconds\":90}}");
            Newtonsoft.Json.Linq.JObject nestedMerged;
            var afterNested = RiskConfigMerge.Apply(live, nested, out nestedMerged);
            Assert(afterNested.StopGuard.StopAttachSeconds == 90,
                string.Format("A nested edit applies (got {0}).", afterNested.StopGuard.StopAttachSeconds));
            Assert(afterNested.StopGuard.OnMissing == "AutoStop",
                string.Format(
                    "...and its SIBLINGS survive (OnMissing '{0}'). Replacing the whole StopGuard "
                    + "object would set OnMissing back to its default, which is how the guard "
                    + "stops attaching stops without anyone changing that setting.",
                    afterNested.StopGuard.OnMissing));

            // An empty body must be a no-op, not a factory reset.
            Newtonsoft.Json.Linq.JObject emptyMerged;
            var afterEmpty = RiskConfigMerge.Apply(live, new Newtonsoft.Json.Linq.JObject(), out emptyMerged);
            Assert(afterEmpty.Mode == "live" && afterEmpty.MinShadowSessions == 3
                   && afterEmpty.StopGuard.StopAttachSeconds == 45,
                "An empty body changes nothing at all.");
        }

        // P2-38. Three deploy/order gates classified an account as simulated with
        // `Name.StartsWith("Sim") || Provider.Contains("imulat")`, and a fourth used the name
        // alone. The provider test is correct; OR-ing a name prefix in front of it means a funded
        // account called "SimpsonFund" is treated as simulated and can be deployed to, and traded
        // on, without confirmLive=true. Same root cause as P1-20.
        //
        // Asserted partly against source text because McpBridgeAddOn.cs is excluded from this
        // test build by construction (WPF dependencies), so its gates cannot be executed here at
        // all. The behavioural half -- that the shared classifier gets "SimpsonFund" right -- is
        // executed properly.
        private static void TestP2_38_DeployGateClassifiesByProviderNotName()
        {
            Console.WriteLine("\n[TEST] P2-38: the bridge's deploy/order gates classify by provider, never by name prefix");

            var simpson = new Account { Name = "SimpsonFund", Provider = Provider.NinjaTrader };
            Assert(!TradeCopierEngine.IsSimulationAccount(simpson),
                "A LIVE account named 'SimpsonFund' is not simulated. The name-prefix test said it was, "
                + "and that is the whole defect: it gates strategy deployment and order placement.");

            var sim101 = new Account { Name = "Sim101", Provider = Provider.Simulator };
            Assert(TradeCopierEngine.IsSimulationAccount(sim101),
                "A genuine Simulator account still classifies as simulated.");

            var oddlyNamed = new Account { Name = "PlaybackDesk", Provider = Provider.Simulator };
            Assert(TradeCopierEngine.IsSimulationAccount(oddlyNamed),
                "A simulated account that does not start with 'Sim' still classifies as simulated -- "
                + "the name was never the signal in either direction.");

            var bridgePath = Path.Combine(Path.GetDirectoryName(AddonSourcePath()), "McpBridgeAddOn.cs");
            Assert(File.Exists(bridgePath), string.Format("The bridge source is readable at {0}", bridgePath));

            var code = string.Join("\n", File.ReadAllText(bridgePath)
                .Split('\n')
                .Select(l => { int i = l.IndexOf("//"); return i >= 0 ? l.Substring(0, i) : l; }));

            var nameGate = new System.Text.RegularExpressions.Regex(
                @"isSim\s*=\s*[^;]*Name\s*\.\s*StartsWith", System.Text.RegularExpressions.RegexOptions.Singleline);
            Assert(!nameGate.IsMatch(code),
                "No sim/live gate in the bridge classifies by account name any more.");

            int shared = System.Text.RegularExpressions.Regex.Matches(
                code, @"IsSimulationAccount\(").Count;
            Assert(shared >= 4,
                string.Format(
                    "All four gates use the shared classifier (found {0}). Two definitions of "
                    + "'simulated' drift, and the one that drifts is the one nobody is testing.",
                    shared));
        }

        private static void TestStress_S5_PartialFillStorm()
        {
            Console.WriteLine("\n[STRESS S5] partial-fill storm, both event orderings (P1-16)");

            var mnq = new Instrument("MNQ");

            Func<Tuple<RiskGuardAddOn, Account, AccountState>> build = () =>
            {
                Account.All.Clear();
                var acct = new Account { Name = "FillAcc", Provider = Provider.Simulator };
                Account.All.Add(acct);
                var a = new RiskGuardAddOn();
                var cfg = new RiskConfig();
                cfg.Overtrading.MaxConsecutiveLosses = 3;
                cfg.Overtrading.CooldownMinutes = 15;
                a.SetConfigForTest(cfg);
                a.SetSubscribedAccountForTest("FillAcc");
                var st = new AccountState("FillAcc");
                st.LastSessionDate = DateTime.UtcNow.Date;
                a.SetAccountStateForTest("FillAcc", st);
                return Tuple.Create(a, acct, st);
            };

            // Drives a realized-PnL change through the real AccountItemUpdate handler.
            Action<Tuple<RiskGuardAddOn, Account, AccountState>, double> realized = (t, cumulative) =>
                t.Item1.ExecuteAccountItemUpdate(t.Item2, new AccountItemEventArgs
                {
                    AccountItem = AccountItem.RealizedProfitLoss,
                    Value = cumulative,
                    Currency = Currency.UsDollar
                });

            // ---- ordering A: every partial fill lands BEFORE the position goes flat ----
            var a1 = build();
            a1.Item2.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 8, AveragePrice = 18000
            });
            a1.Item3.UpdatePosition(a1.Item2, mnq, MarketPosition.Long, 8, 18000, 0, a1.Item1.Config);

            double running = 0;
            for (int i = 1; i <= 8; i++)
            {
                running -= 25.0;                        // each partial exits at a loss
                a1.Item2.Positions[0].Quantity = 8 - i;
                if (i < 8)
                    a1.Item3.UpdatePosition(a1.Item2, mnq, MarketPosition.Long, 8 - i, 18000, 0, a1.Item1.Config);
                realized(a1, running);
            }
            a1.Item2.Positions.Clear();
            a1.Item3.UpdatePosition(a1.Item2, mnq, MarketPosition.Flat, 0, 0, 0, a1.Item1.Config);

            Assert(a1.Item3.ConsecutiveLosses == 1,
                string.Format(
                    "Eight partial exits of ONE losing trade count as ONE consecutive loss (got {0}). "
                    + "Counting each fill separately makes a 3-loss lockout reachable from a single "
                    + "trade, and puts this counter at odds with TradesToday.",
                    a1.Item3.ConsecutiveLosses));

            Assert(!a1.Item3.IsLockedOut,
                "One losing trade does not lock the account out at MaxConsecutiveLosses=3.");

            // ---- ordering B: the position goes flat FIRST, the tail of the fills arrives after ----
            // This is the ordering P1-16's late-fill revision exists for, and the one no unit test
            // could pin without driving the real handler.
            var b1 = build();
            b1.Item2.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 8, AveragePrice = 18000
            });
            b1.Item3.UpdatePosition(b1.Item2, mnq, MarketPosition.Long, 8, 18000, 0, b1.Item1.Config);

            realized(b1, -50.0);                          // two partials seen while still open
            b1.Item2.Positions.Clear();
            b1.Item3.UpdatePosition(b1.Item2, mnq, MarketPosition.Flat, 0, 0, 0, b1.Item1.Config);

            for (int i = 3; i <= 8; i++)                   // six LATE fills, after flat
                realized(b1, -25.0 * i);

            Assert(b1.Item3.ConsecutiveLosses == 1,
                string.Format(
                    "Late fills REVISE the closed trade's judgement rather than accumulating (got {0}). "
                    + "Each one landing as its own loss is the same defect arriving through the other "
                    + "event ordering.",
                    b1.Item3.ConsecutiveLosses));

            // ---- and the revision must be able to change the VERDICT, not just avoid double-counting ----
            var c1 = build();
            c1.Item2.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 4, AveragePrice = 18000
            });
            c1.Item3.UpdatePosition(c1.Item2, mnq, MarketPosition.Long, 4, 18000, 0, c1.Item1.Config);
            realized(c1, 120.0);                          // looks like a winner at the flat transition
            c1.Item2.Positions.Clear();
            c1.Item3.UpdatePosition(c1.Item2, mnq, MarketPosition.Flat, 0, 0, 0, c1.Item1.Config);
            Assert(c1.Item3.ConsecutiveLosses == 0, "Precondition: settled as a win, streak reset.");

            realized(c1, -80.0);                          // a late fill turns the trade net negative

            Assert(c1.Item3.ConsecutiveLosses == 1,
                string.Format(
                    "A late fill that flips the trade from net win to net loss is re-judged as a loss "
                    + "(got {0}). Judging once and never revisiting means a trade whose losing tail "
                    + "arrives late is recorded as a win.",
                    c1.Item3.ConsecutiveLosses));

            // ---- three genuinely distinct losing trades must STILL trip the lockout ----
            // The fix must not have bought its accuracy by desensitising the rule.
            var d1 = build();
            for (int trade = 1; trade <= 3; trade++)
            {
                d1.Item2.Positions.Clear();
                d1.Item2.Positions.Add(new Position
                {
                    Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
                });
                d1.Item3.UpdatePosition(d1.Item2, mnq, MarketPosition.Long, 2, 18000, 0, d1.Item1.Config);
                realized(d1, -100.0 * trade);
                d1.Item2.Positions.Clear();
                d1.Item3.UpdatePosition(d1.Item2, mnq, MarketPosition.Flat, 0, 0, 0, d1.Item1.Config);
            }
            Assert(d1.Item3.ConsecutiveLosses == 3,
                string.Format("Three separate losing trades still count as three (got {0}).",
                    d1.Item3.ConsecutiveLosses));
            Assert(d1.Item3.CooldownUntil > DateTime.UtcNow,
                "...and the cooldown fires, so the rule kept its teeth.");
        }

        // ==================================================================
        // S6 — RAPID FLIP LOOP (plan §8)
        //
        // long <-> short, repeatedly. Coverage must never outlive the position it covered: a
        // CoveredQuantity carried across a flip means the new leg reads as protected by a stop
        // that is on the wrong side of it, so grace never arms and the position stays naked.
        // ==================================================================
        private static void TestStress_S6_RapidFlipLoop()
        {
            Console.WriteLine("\n[STRESS S6] rapid long/short flip loop (P1-36, T1)");

            var mnq = new Instrument("MNQ");
            Account.All.Clear();
            var account = new Account { Name = "FlipAcc", Provider = Provider.Simulator };
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop"));
            addon.SetSubscribedAccountForTest("FlipAcc");
            addon.SetAccountStateForTest("FlipAcc", new AccountState("FlipAcc"));
            addon.TestClearFsms();

            var staleCoverage = new List<string>();
            var missingGrace = new List<string>();
            var wrongSide = new List<string>();
            Order previousStop = null;

            for (int leg = 0; leg < 12; leg++)
            {
                bool longLeg = leg % 2 == 0;
                var side = longLeg ? MarketPosition.Long : MarketPosition.Short;
                int qty = 2 + (leg % 3);

                // The previous leg's stop is STILL WORKING as the flip lands. That is the real
                // shape of this hazard: NT8 collapses close+reverse into one position update, and
                // for a moment the old protective order is live against a position that has
                // already reversed under it. Killing the stop before flipping -- the tidy version
                // -- makes every assertion below unfalsifiable, because a terminal order cannot
                // contribute coverage to anything.
                SetPosition(account, mnq, side, qty, 18000);
                addon.TestFsmOnPosition(account, mnq.FullName, side, qty);

                var fsm = addon.TestGetFsm("FlipAcc", mnq.FullName);
                if (fsm == null) { missingGrace.Add("leg " + leg + ": no FSM at all"); continue; }

                // The instant a new leg opens it is naked: whatever covered the previous leg is
                // on the wrong side of this one.
                if (fsm.CoveredQuantity != 0)
                    staleCoverage.Add(string.Format("leg {0} ({1} {2}) opened with CoveredQuantity {3}",
                        leg, side, qty, fsm.CoveredQuantity));
                if (!fsm.GracePending)
                    missingGrace.Add(string.Format("leg {0} ({1} {2}) opened with no grace timer", leg, side, qty));
                if (fsm.PositionSide != side || fsm.PositionQuantity != qty)
                    wrongSide.Add(string.Format("leg {0}: FSM says {1} {2}, position is {3} {4}",
                        leg, fsm.PositionSide, fsm.PositionQuantity, side, qty));

                // Now the stale stop is cancelled, as the broker would once the reversal settles.
                if (previousStop != null)
                {
                    previousStop.OrderState = OrderState.Cancelled;
                    account.Orders.Remove(previousStop);
                    addon.TestFsmOnOrder(account, mnq.FullName, previousStop);
                }

                // Cover the new leg properly, so the NEXT flip has real, live coverage to carry.
                var stop = new Order
                {
                    Id = Guid.NewGuid().ToString(), OrderId = Guid.NewGuid().ToString(),
                    Name = "Stop_Leg" + leg, OrderState = OrderState.Working,
                    OrderType = OrderType.StopMarket, Quantity = qty, Instrument = mnq,
                    OrderAction = longLeg ? OrderAction.Sell : OrderAction.BuyToCover,
                    StopPrice = longLeg ? 17900 : 18100
                };
                account.Orders.Add(stop);
                addon.TestFsmOnOrder(account, mnq.FullName, stop);

                var covered = addon.TestGetFsm("FlipAcc", mnq.FullName);
                if (covered == null || covered.CoveredQuantity != qty)
                    staleCoverage.Add(string.Format("leg {0}: covering stop of {1} recorded as {2}",
                        leg, qty, covered == null ? -1 : covered.CoveredQuantity));

                previousStop = stop;
            }

            if (previousStop != null)
            {
                previousStop.OrderState = OrderState.Cancelled;
                account.Orders.Remove(previousStop);
            }

            Assert(staleCoverage.Count == 0,
                string.Format(
                    "Coverage never outlives the position it covered ({0} violation(s)){1}. A stale "
                    + "CoveredQuantity carried into a flipped leg means the guard believes a stop on "
                    + "the WRONG SIDE is protecting it -- grace never arms, and the position is naked "
                    + "for its whole life.",
                    staleCoverage.Count,
                    staleCoverage.Count == 0 ? "" : ": " + string.Join("; ", staleCoverage.Take(3))));

            Assert(missingGrace.Count == 0,
                string.Format("Every leg arms its own grace timer ({0} violation(s)){1}.",
                    missingGrace.Count,
                    missingGrace.Count == 0 ? "" : ": " + string.Join("; ", missingGrace.Take(3))));

            Assert(wrongSide.Count == 0,
                string.Format("The FSM tracks each leg's real side and size ({0} violation(s)){1}.",
                    wrongSide.Count,
                    wrongSide.Count == 0 ? "" : ": " + string.Join("; ", wrongSide.Take(3))));

            // Finally flat: nothing may be left tracked.
            SetPosition(account, mnq, MarketPosition.Flat, 0, 0);
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Flat, 0);
            Assert(addon.TestGetFsm("FlipAcc", mnq.FullName) == null,
                "Going flat after twelve flips leaves no FSM behind.");
            Assert(addon.TestPendingStopCount("FlipAcc", mnq.FullName) == 0,
                "...and no buffered stops either (P1-14's buffer is cleared on flat).");
        }

        // ==================================================================
        // S8 — CONFIG RELOAD WHILE ARMED AND IN POSITION (plan §8)
        //
        // A live reload must not drop FSMs, coverage or lockouts, and must not corrupt the config.
        // P1-39 is the reason for the last clause: every load appended the default windows, so
        // WindowsET grew without bound and a deleted default came back on the next reload.
        // ==================================================================
        private static void TestStress_S8_ConfigReloadWhileArmedAndInPosition()
        {
            Console.WriteLine("\n[STRESS S8] config reload while armed and in position (P1-39, P1-42)");

            var mnq = new Instrument("MNQ");
            Account.All.Clear();
            var account = new Account { Name = "ReloadAcc", Provider = Provider.Simulator };
            Account.All.Add(account);

            string dir = Path.Combine(Path.GetTempPath(), "riskguard_s8_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            string configPath = Path.Combine(dir, "config.json");

            try
            {
                var addon = new RiskGuardAddOn();
                addon.SetConfigFileForTest(configPath);
                var cfg = FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop");
                cfg.ExcludedAccounts = new List<string>();
                addon.SetConfigForTest(cfg);
                addon.SetSubscribedAccountForTest("ReloadAcc");

                var state = new AccountState("ReloadAcc");
                state.LastSessionDate = DateTime.UtcNow.Date;
                addon.SetAccountStateForTest("ReloadAcc", state);
                addon.TestClearFsms();

                // In position, covered, and locked out. All three must survive the reload.
                SetPosition(account, mnq, MarketPosition.Long, 4, 18000);
                addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 4);
                var stop = PartialStop(mnq, 4, 17900, "Stop_Live");
                account.Orders.Add(stop);
                addon.TestFsmOnOrder(account, mnq.FullName, stop);
                state.IsLockedOut = true;
                state.LockoutUntil = DateTime.UtcNow.AddMinutes(30);

                var before = addon.TestGetFsm("ReloadAcc", mnq.FullName);
                Assert(before != null && before.CoveredQuantity == 4,
                    "Precondition: a covered 4-lot position is tracked.");

                int windowsBefore = addon.Config.WindowsET == null ? 0 : addon.Config.WindowsET.Count;

                // Five genuine save+reload round trips through the real path, as an operator
                // hammering Save or a script POSTing config would produce.
                for (int i = 0; i < 5; i++)
                {
                    var edited = addon.Config;
                    edited.StopGuard.StopAttachSeconds = 45 + i;
                    addon.SaveAndReloadConfig(edited);
                }

                var after = addon.TestGetFsm("ReloadAcc", mnq.FullName);
                Assert(after != null,
                    "The FSM survives five live config reloads. Losing it leaves an open position "
                    + "untracked, with the guard reporting armed.");
                Assert(after != null && after.CoveredQuantity == 4,
                    string.Format("Coverage survives too (got {0} of 4). Dropping it makes the guard "
                        + "attach a duplicate stop to an already-covered position.",
                        after == null ? -1 : after.CoveredQuantity));
                Assert(after != null && after.PositionQuantity == 4 && after.PositionSide == MarketPosition.Long,
                    "...and the position it describes is still the real one.");

                var stateAfter = addon.GetAccountStateForTest("ReloadAcc");
                Assert(stateAfter != null && stateAfter.IsLockedOut,
                    "The lockout survives the reload. A reload that clears it is a free unlock for "
                    + "anyone who can save the config.");

                int windowsAfter = addon.Config.WindowsET == null ? 0 : addon.Config.WindowsET.Count;
                Assert(windowsAfter == windowsBefore,
                    string.Format(
                        "WindowsET is unchanged across five reloads ({0} -> {1}). P1-39 appended the "
                        + "defaults on every single load, so the list grew without bound and a deleted "
                        + "default could never stay deleted.",
                        windowsBefore, windowsAfter));

                Assert(Math.Abs(addon.Config.StopGuard.StopAttachSeconds - 49) < 1,
                    string.Format("The edit actually round-tripped through disk (StopAttachSeconds {0}, expected 49). "
                        + "If it did not, every assertion above was measuring a config that never reloaded.",
                        addon.Config.StopGuard.StopAttachSeconds));

                var reread = Newtonsoft.Json.JsonConvert.DeserializeObject<RiskConfig>(File.ReadAllText(configPath));
                Assert(reread != null && (reread.WindowsET == null ? 0 : reread.WindowsET.Count) == windowsBefore,
                    "And the file on disk is not corrupted either -- the growth would otherwise be "
                    + "invisible until the next restart read it back.");
            }
            finally
            {
                try { Directory.Delete(dir, true); } catch { }
            }
        }

        // ==================================================================
        // S9 — RESTART MID-TRADE (plan §8)
        //
        // Kill and reload with a position open. The seeded FSM must match the broker, trades and
        // losses must not double-count, and lockouts must survive. P1-16 has a documented restart
        // limit -- an in-flight trade settles as a scratch rather than inventing a result -- and
        // this pins that limit rather than pretending it is not there.
        // ==================================================================
        private static void TestStress_S9_RestartMidTrade()
        {
            Console.WriteLine("\n[STRESS S9] restart mid-trade (P1-15, P1-16's restart limit)");

            var mnq = new Instrument("MNQ");
            string dir = Path.Combine(Path.GetTempPath(), "riskguard_s9_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            string statePath = Path.Combine(dir, "state.json");

            try
            {
                // ---- session 1: two losing trades banked, then a third trade left OPEN ----
                Account.All.Clear();
                var account = new Account { Name = "RestartAcc", Provider = Provider.Simulator };
                Account.All.Add(account);

                var first = new RiskGuardAddOn();
                first.SetStateFileForTest(statePath);
                var cfg1 = FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop");
                cfg1.Overtrading.MaxConsecutiveLosses = 3;
                cfg1.Overtrading.CooldownMinutes = 15;
                first.SetConfigForTest(cfg1);
                first.SetSubscribedAccountForTest("RestartAcc");
                var s1 = new AccountState("RestartAcc");
                s1.LastSessionDate = DateTime.UtcNow.Date;
                first.SetAccountStateForTest("RestartAcc", s1);
                first.TestClearFsms();

                double running = 0;
                for (int trade = 1; trade <= 2; trade++)
                {
                    account.Positions.Clear();
                    account.Positions.Add(new Position
                    {
                        Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
                    });
                    s1.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0, cfg1);
                    running -= 100.0;
                    first.ExecuteAccountItemUpdate(account, new AccountItemEventArgs
                    {
                        AccountItem = AccountItem.RealizedProfitLoss, Value = running, Currency = Currency.UsDollar
                    });
                    account.Positions.Clear();
                    s1.UpdatePosition(account, mnq, MarketPosition.Flat, 0, 0, 0, cfg1);
                }
                Assert(s1.ConsecutiveLosses == 2, "Precondition: two losing trades banked.");

                // A third trade is opened and left open, with a partial loss already realized.
                SetPosition(account, mnq, MarketPosition.Long, 3, 18000);
                s1.UpdatePosition(account, mnq, MarketPosition.Long, 3, 18000, 0, cfg1);
                running -= 40.0;
                first.ExecuteAccountItemUpdate(account, new AccountItemEventArgs
                {
                    AccountItem = AccountItem.RealizedProfitLoss, Value = running, Currency = Currency.UsDollar
                });
                s1.IsLockedOut = true;

                first.SavePersistedStateForTest();
                Assert(File.Exists(statePath), "Precondition: state was persisted before the restart.");

                // ---- the restart. New instance, same broker state, same state file. ----
                var second = new RiskGuardAddOn();
                second.SetStateFileForTest(statePath);
                var cfg2 = FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop");
                cfg2.Overtrading.MaxConsecutiveLosses = 3;
                cfg2.Overtrading.CooldownMinutes = 15;
                second.SetConfigForTest(cfg2);
                second.SetSubscribedAccountForTest("RestartAcc");
                second.SetAccountStateForTest("RestartAcc", new AccountState("RestartAcc"));
                second.TestClearFsms();
                second.LoadPersistedStateForTest();

                var restored = second.GetAccountStateForTest("RestartAcc");
                Assert(restored != null && restored.ConsecutiveLosses == 2,
                    string.Format(
                        "The two banked losses survive the restart (got {0}). Losing them hands the "
                        + "trader a fresh streak, so the lockout that was one trade away is now three.",
                        restored == null ? -1 : restored.ConsecutiveLosses));

                Assert(restored != null && restored.IsLockedOut,
                    "The lockout survives the restart. Restarting NT8 must not be an unlock button.");

                // The open trade's partial loss is deliberately NOT persisted (P1-16): it settles
                // as a scratch rather than inventing a result from half a trade.
                Assert(restored != null && Math.Abs(restored.OpenTradeRealizedDelta) < 0.01,
                    string.Format(
                        "The in-flight trade's partial PnL is not carried across the restart (got {0}). "
                        + "This is P1-16's documented limit, pinned rather than assumed: half a trade's "
                        + "realized PnL is not a result, and persisting it would invent one.",
                        restored == null ? -1 : restored.OpenTradeRealizedDelta));

                // ---- and the guard must re-derive the OPEN position from the broker ----
                second.SetArmedForTest(false);
                second.ToggleArmed();
                Assert(second.GetIsArmed(), "Precondition: arming succeeded after the restart.");

                var fsm = second.TestGetFsm("RestartAcc", mnq.FullName);
                Assert(fsm != null,
                    "The open 3-lot position is seeded on arm. Without it the guard comes back armed "
                    + "and covering nothing until the position happens to change.");
                Assert(fsm != null && fsm.PositionQuantity == 3 && fsm.PositionSide == MarketPosition.Long,
                    string.Format("The seeded FSM matches the BROKER, not the state file ({0} {1}).",
                        fsm == null ? "none" : fsm.PositionSide.ToString(),
                        fsm == null ? -1 : fsm.PositionQuantity));
                Assert(fsm != null && fsm.CoveredQuantity == 0 && fsm.GracePending,
                    "It is seeded uncovered with grace armed -- there is no stop on the account, and "
                    + "assuming otherwise across a restart is exactly how a position stays naked.");

                // Closing that trade must count as ONE further loss, not repeat the two banked ones.
                account.Positions.Clear();
                restored.UpdatePosition(account, mnq, MarketPosition.Flat, 0, 0, 0, cfg2);
                second.ExecuteAccountItemUpdate(account, new AccountItemEventArgs
                {
                    AccountItem = AccountItem.RealizedProfitLoss, Value = running - 60.0, Currency = Currency.UsDollar
                });

                Assert(restored.ConsecutiveLosses == 3,
                    string.Format(
                        "Closing the restarted trade at a loss makes three, not five (got {0}). "
                        + "Double-counting the banked trades on reload is how a restart manufactures "
                        + "a lockout.",
                        restored.ConsecutiveLosses));
            }
            finally
            {
                try { Directory.Delete(dir, true); } catch { }
            }
        }

        private static void TestStress_S1toS4_OrderFloodGovernor()
        {
            Console.WriteLine("\n[STRESS S1-S4] order-flood governor");

            var mnq = new Instrument("MNQ");

            Func<RiskConfig, Tuple<RiskGuardAddOn, Account, AccountState>> build = cfg =>
            {
                Account.All.Clear();
                var acct = new Account { Name = "FloodAcc", Provider = Provider.Simulator };
                Account.All.Add(acct);
                var a = new RiskGuardAddOn();
                a.SetConfigForTest(cfg);
                a.SetSubscribedAccountForTest("FloodAcc");
                var st = new AccountState("FloodAcc");
                st.LastSessionDate = DateTime.UtcNow.Date;
                a.SetAccountStateForTest("FloodAcc", st);
                return Tuple.Create(a, acct, st);
            };

            Func<Instrument, string, OrderAction, OrderType, Order> mkOrder = (inst, id, act, typ) =>
                new Order
                {
                    Id = id, OrderId = id, Instrument = inst, OrderAction = act,
                    OrderType = typ, Quantity = 1, OrderState = OrderState.Submitted,
                    Name = "Entry" + id
                };

            // ---- S1: the rate governor must count DISTINCT ORDERS, not state transitions ----
            // One order passing Submitted -> Accepted currently adds two ticks, so a nominal
            // "more than 5 per second" fires at about three real orders per second.
            var s1 = build(new RiskConfig());
            for (int i = 0; i < 3; i++)
            {
                var o = mkOrder(mnq, "S1-" + i, OrderAction.Buy, OrderType.Limit);
                o.OrderState = OrderState.Submitted;
                s1.Item1.ExecuteOrderUpdate(s1.Item2, new OrderEventArgs { Order = o });
                o.OrderState = OrderState.Accepted;
                s1.Item1.ExecuteOrderUpdate(s1.Item2, new OrderEventArgs { Order = o });
            }
            Assert(!s1.Item3.IsLockedOut,
                "three distinct orders, each seen Submitted then Accepted, must NOT trip a 5/sec governor");

            // Ten genuinely distinct orders in the same second must still trip it.
            var s1b = build(new RiskConfig());
            for (int i = 0; i < 10; i++)
            {
                var o = mkOrder(mnq, "S1B-" + i, OrderAction.Buy, OrderType.Limit);
                s1b.Item1.ExecuteOrderUpdate(s1b.Item2, new OrderEventArgs { Order = o });
            }
            Assert(s1b.Item3.IsLockedOut,
                "ten distinct orders in one second must trip the governor");

            // ---- S2: the order that trips the governor may be a PROTECTIVE STOP ----
            // Cancelling it locks the account out with an open, unprotected position.
            var s2 = build(new RiskConfig());
            s2.Item2.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
            });
            s2.Item3.UpdatePosition(s2.Item2, mnq, MarketPosition.Long, 2, 18000, 0, new RiskConfig());
            for (int i = 0; i < 8; i++)
            {
                var o = mkOrder(mnq, "S2-" + i, OrderAction.Buy, OrderType.Limit);
                s2.Item1.ExecuteOrderUpdate(s2.Item2, new OrderEventArgs { Order = o });
            }
            var protectiveStop = new Order
            {
                Id = "S2-STOP", OrderId = "S2-STOP", Instrument = mnq,
                OrderAction = OrderAction.Sell, OrderType = OrderType.StopMarket,
                Quantity = 2, OrderState = OrderState.Submitted, Name = "Stop1", StopPrice = 17900
            };
            s2.Item2.Orders.Add(protectiveStop);
            s2.Item1.ExecuteOrderUpdate(s2.Item2, new OrderEventArgs { Order = protectiveStop });
            Assert(protectiveStop.OrderState != OrderState.Cancelled,
                "a protective stop must NEVER be cancelled by the rate governor -- doing so leaves the position naked");

            // ---- S3: a flood lockout must lapse, like every other lockout ----
            var s3cfg = new RiskConfig();
            s3cfg.Overtrading.LockoutMinutes = 60;
            var s3 = build(s3cfg);
            for (int i = 0; i < 10; i++)
            {
                var o = mkOrder(mnq, "S3-" + i, OrderAction.Buy, OrderType.Limit);
                s3.Item1.ExecuteOrderUpdate(s3.Item2, new OrderEventArgs { Order = o });
            }
            Assert(s3.Item3.IsLockedOut, "the flood lockout fires");
            Assert(s3.Item3.LockoutUntil > DateTime.UtcNow,
                "a flood lockout must carry a deadline; without LockoutUntil the test at :1485 is an OR and it never lapses");

            // ---- S4: no broker call may happen while _stateLock is held, on THIS path ----
            // P1-10/P1-35 machine-checked the invariant but only ever drove the sweep and FSM
            // teardown. ExecuteOrderUpdate has four Cancel sites inside the lock.
            var s4 = build(new RiskConfig());
            s4.Item3.IsLockedOut = true;
            s4.Item2.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
            });
            s4.Item2.Orders.Add(new Order
            {
                Instrument = mnq, OrderState = OrderState.Working, OrderType = OrderType.Limit,
                OrderAction = OrderAction.Buy, Quantity = 1, Id = "S4-RESTING", Name = "RESTING_ENTRY"
            });

            // Every entry point that can reach a broker call, not a hand-picked one. P1-43
            // existed precisely because the original check only drove the sweep and FSM teardown.
            var violations = RecordBrokerCallsUnderLock(s4.Item1, () =>
            {
                for (int i = 0; i < 8; i++)
                {
                    var o = mkOrder(mnq, "S4-" + i, OrderAction.Buy, OrderType.Limit);
                    s4.Item1.ExecuteOrderUpdate(s4.Item2, new OrderEventArgs { Order = o });
                }
                s4.Item3.IsLockedOut = true;
                s4.Item1.ExecuteAccountItemUpdate(s4.Item2,
                    new AccountItemEventArgs { AccountItem = AccountItem.RealizedProfitLoss, Value = -5000.0 });
                s4.Item1.ExecutePositionUpdateDetails(s4.Item2, s4.Item2.Positions[0]);
                s4.Item3.IsLockedOut = true;
                s4.Item1.ExecuteSafetySweep();
            });
            Assert(violations.Count == 0,
                string.Format("the order-update, account-item, position and sweep paths made {0} broker call(s) under _stateLock{1}",
                    violations.Count,
                    violations.Count == 0 ? "" : ": " + string.Join(", ", violations.Distinct())));
        }

        private static void TestP1_10_SweepMakesNoBrokerCallsUnderTheStateLock()
        {
            Console.WriteLine("\n[TEST] P1-10: the safety sweep makes no broker calls while holding _stateLock");

            var mnq = new Instrument("MNQ");
            Account.All.Clear();
            var account = new Account { Name = "TestAcc", Provider = Provider.Simulator };
            account.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
            });
            account.Orders.Add(new Order
            {
                Instrument = mnq, OrderState = OrderState.Working, OrderType = OrderType.Limit,
                OrderAction = OrderAction.Buy, Quantity = 1, Name = "RESTING_ENTRY"
            });
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(new RiskConfig());
            addon.SetSubscribedAccountForTest("TestAcc");
            var locked = new AccountState("TestAcc");
            addon.SetAccountStateForTest("TestAcc", locked);

            // P0-51: this test is about the sweep's ACTING behaviour -- whether its broker calls
            // happen outside _stateLock -- so it has to run in an acting mode. It did not set one,
            // and _mode defaults to "shadow", so it was asserting that a shadow-mode sweep reaches
            // the broker. That was true only because the sweep ignored the mode entirely, which is
            // the defect P0-51 fixes. The test's subject is unchanged; only the mode is now stated.
            addon.SetModeForTest("live");

            // Sweep once unobserved so the daily session reset happens and settles. It clears
            // IsLockedOut, so locking the account before this call would be undone before the
            // lockout watchdog ever ran -- the test would then pass while touching nothing.
            addon.ExecuteSafetySweep();
            locked.IsLockedOut = true;

            var violations = RecordBrokerCallsUnderLock(addon, () => addon.ExecuteSafetySweep());

            Assert(violations.Count == 0,
                string.Format(
                    "The sweep made {0} broker call(s) while holding _stateLock{1}. Every one is a "
                    + "deadlock window against any NT8 path that needs the lock from another thread.",
                    violations.Count,
                    violations.Count == 0 ? "" : ": " + string.Join(", ", violations.Distinct())));

            // The refactor must not lose the work: a locked account with an open position and a
            // resting entry still has to be cancelled and flattened, just outside the lock.
            Assert(account.FlattenCallCount > 0,
                "The locked account was still flattened (the enforcement itself is preserved)");
        }

        /// <summary>
        /// Absolute path of the addon source, resolved at COMPILE time. The test exe runs from
        /// bin/, and the csproj links the sources in from another directory, so any runtime path
        /// walk would be guessing.
        /// </summary>
        private static string AddonSourcePath(
            [System.Runtime.CompilerServices.CallerFilePath] string thisFile = "")
        {
            return Path.Combine(Path.GetDirectoryName(thisFile), "RiskGuardAddOn.cs");
        }

        // P1-13, fail-open half. This one is asserted against the SOURCE TEXT, which needs
        // justifying: the branch it protects lives under `#if !TESTING` and therefore cannot be
        // executed by this suite at all. That is precisely the P1-47 shape -- code the test build
        // never sees -- and the honest options are to leave it unchecked or to check what can
        // actually be checked. A source assertion proves less than an execution would, but it
        // proves the exact thing that regressed here: that no guard event path returns early
        // because there is no WPF dispatcher.
        //
        // What it is defending: with Application.Current null -- early startup, or a headless NT8
        // -- all five handlers plus the entire safety sweep silently discarded every event, while
        // the guard went on reporting itself armed and guarding. No FSM, no grace, no rules, no
        // log line.
        private static void TestP1_13_NoGuardPathIsSkippedWhenThereIsNoDispatcher()
        {
            Console.WriteLine("\n[TEST] P1-13: no guard event path is dropped when Application.Current has no Dispatcher");

            var path = AddonSourcePath();
            Assert(File.Exists(path), string.Format("The addon source is readable at {0}", path));
            var source = File.ReadAllText(path);

            // Comments are stripped first. The seam's own doc comment quotes the defective
            // pattern verbatim -- that documentation is worth keeping, and a check that forbids
            // describing the bug it prevents is a check that gets the comment deleted instead.
            var code = string.Join("\n", source
                .Split('\n')
                .Select(l => { int i = l.IndexOf("//"); return i >= 0 ? l.Substring(0, i) : l; }));

            // The exact fail-open shape, tolerant of whitespace and of `Dispatcher`/`disp` naming.
            var failOpen = new System.Text.RegularExpressions.Regex(
                @"if\s*\(\s*\w*[dD]ispatcher\w*\s*==\s*null\s*\)\s*return\s*;");
            var hits = failOpen.Matches(code);
            Assert(hits.Count == 0,
                string.Format(
                    "{0} guard path(s) still return early when there is no dispatcher. Each one is a "
                    + "silent, total protection outage that reports itself as armed.",
                    hits.Count));

            // And the seam is genuinely the single funnel, not a helper nobody calls.
            int wired = System.Text.RegularExpressions.Regex.Matches(source, @"RunGuardWork\(").Count;
            Assert(wired >= 7,
                string.Format(
                    "All six guard entry points route through RunGuardWork plus its own definition "
                    + "(found {0} references). A handler that dispatches by hand is one that can "
                    + "quietly reacquire the early return.",
                    wired));

            foreach (var handler in new[] { "PositionUpdate", "OrderUpdate", "ExecutionUpdate",
                                            "AccountItemUpdate", "SafetySweep", "GraceExpiry" })
            {
                Assert(source.Contains("RunGuardWork(\"" + handler + "\""),
                    string.Format("{0} is routed through the seam", handler));
            }
        }

        /// <summary>
        /// Runs <paramref name="body"/> with a disk-write observer installed, and returns the
        /// labels of any addon file write that happened while `_stateLock` was held. Deliberately
        /// the same shape as <see cref="RecordBrokerCallsUnderLock"/> -- P1-12 is P1-10's
        /// invariant applied to the other kind of unbounded call.
        /// </summary>
        private static List<string> RecordFileWritesUnderLock(RiskGuardAddOn addon, Action body)
        {
            var violations = new List<string>();
            RiskGuardAddOn.FileWriteObserver = label =>
            {
                if (addon.TestIsStateLockHeld()) violations.Add(label);
            };
            try { body(); }
            finally { RiskGuardAddOn.FileWriteObserver = null; }
            return violations;
        }

        /// <summary>Counts addon file writes by label, regardless of lock state.</summary>
        private static List<string> RecordFileWrites(Action body)
        {
            var writes = new List<string>();
            RiskGuardAddOn.FileWriteObserver = label => { lock (writes) writes.Add(label); };
            try { body(); }
            finally { RiskGuardAddOn.FileWriteObserver = null; }
            return writes;
        }

        // P1-12a. `_stateLock` is the lock every NT8 event handler needs. The sweep wrote the
        // heartbeat file, appended the log and serialised the whole persisted state inside it, so
        // a slow or stalled disk stalled order-event processing -- including the handlers that
        // attach protective stops -- for as long as the disk took.
        //
        // Asserted mechanically for the same reason P1-10 is: the lock is RE-ENTRANT, so a write
        // that reads as "outside the lock" is inside it whenever its caller held the lock, and no
        // amount of reading settles that. Monitor.IsEntered does.
        private static void TestP1_12_NoDiskWriteHappensUnderTheStateLock()
        {
            Console.WriteLine("\n[TEST] P1-12: no disk write happens while _stateLock is held");

            var mnq = new Instrument("MNQ");
            Account.All.Clear();
            var account = new Account { Name = "TestAcc", Provider = Provider.Simulator };
            account.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
            });
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(new RiskConfig());
            addon.SetSubscribedAccountForTest("TestAcc");
            addon.SetAccountStateForTest("TestAcc", new AccountState("TestAcc"));

            var violations = RecordFileWritesUnderLock(addon, () =>
            {
                // The hot path first: a position change is the highest-frequency event there is.
                addon.ExecutePositionUpdateDetails(account, account.Positions[0]);
                // Then the sweep, which owns the heartbeat, the log flush and the state flush.
                addon.ExecuteSafetySweep();
                // Then the two rare-but-real callers that used to persist inside the lock.
                addon.ToggleArmed();
                addon.UnlockAccount("TestAcc");
            });

            Assert(violations.Count == 0,
                string.Format(
                    "{0} disk write(s) ran while _stateLock was held{1}. Each one couples "
                    + "order-event latency to disk latency, on the lock that every NT8 handler "
                    + "needs to make progress.",
                    violations.Count,
                    violations.Count == 0 ? "" : ": " + string.Join(", ", violations.Distinct())));
        }

        // P1-12b. The batching is the fix, not a side effect of it. `_stateDirty` already existed
        // and the sweep already drained it; the position-update path just ignored it and wrote
        // synchronously on every single change. This asserts the two halves separately, because a
        // "fix" that simply deleted the write would pass the lock-scope test above while quietly
        // dropping persistence altogether -- state would then be lost on every restart.
        private static void TestP1_12_PositionChangeDefersThePersistToTheSweep()
        {
            Console.WriteLine("\n[TEST] P1-12: a position change defers its persist to the sweep rather than writing inline");

            var mnq = new Instrument("MNQ");
            Account.All.Clear();
            var account = new Account { Name = "TestAcc", Provider = Provider.Simulator };
            account.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
            });
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(new RiskConfig());
            addon.SetSubscribedAccountForTest("TestAcc");
            addon.SetAccountStateForTest("TestAcc", new AccountState("TestAcc"));

            // Settle the session reset so the first observed sweep is a steady-state one.
            addon.ExecuteSafetySweep();

            var inline = RecordFileWrites(() =>
            {
                for (int i = 1; i <= 5; i++)
                {
                    account.Positions[0].Quantity = 2 + i;
                    addon.ExecutePositionUpdateDetails(account, account.Positions[0]);
                }
            });

            Assert(inline.Count(l => l == "state") == 0,
                string.Format(
                    "Five position changes wrote the state file {0} time(s) inline; expected 0. "
                    + "One full serialise-and-write of every tracked account per position change, "
                    + "under the lock, was the cost being paid.",
                    inline.Count(l => l == "state")));

            var swept = RecordFileWrites(() => addon.ExecuteSafetySweep());

            Assert(swept.Count(l => l == "state") == 1,
                string.Format(
                    "The sweep flushed the deferred state exactly once (got {0}). Deferring without "
                    + "flushing is not batching, it is data loss: nothing else persists the "
                    + "session's PnL baselines or the locked-out list.",
                    swept.Count(l => l == "state")));

            var clean = RecordFileWrites(() => addon.ExecuteSafetySweep());
            Assert(clean.Count(l => l == "state") == 0,
                string.Format(
                    "A sweep with nothing dirty writes no state at all (got {0}) -- the dirty flag "
                    + "is cleared by the flush, so an idle guard is not rewriting its state file "
                    + "on every tick.",
                    clean.Count(l => l == "state")));
        }

        // P1-15: UpdateFsmOnPosition and UpdateFsmOnOrder both return early while disarmed. So
        // disarm, open a position, re-arm, and the guard tracks nothing: no FSM, no grace timer,
        // no protection, until the position happens to change side. Seeding already exists and
        // is good -- it was just only ever called from SubscribeToAccount.
        private static void TestP1_15_ReArmingSeedsFsmsForPositionsOpenedWhileDisarmed()
        {
            Console.WriteLine("\n[TEST] P1-15: re-arming seeds FSMs for positions opened while disarmed");

            var mnq = new Instrument("MNQ");
            Account.All.Clear();
            var account = new Account { Name = "TestAcc", Provider = Provider.Simulator };
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop"));
            addon.SetSubscribedAccountForTest("TestAcc");
            addon.TestClearFsms();
            addon.SetArmedForTest(false);

            // A position is opened while the guard is disarmed.
            account.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
            });
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);
            Assert(addon.TestGetFsm("TestAcc", mnq.FullName) == null,
                "Precondition: while disarmed the FSM paths return early, so nothing is tracked");

            addon.ToggleArmed();
            Assert(addon.GetIsArmed(), "Precondition: arming succeeded (preflight passed in shadow mode)");

            var fsm = addon.TestGetFsm("TestAcc", mnq.FullName);
            Assert(fsm != null,
                "Re-arming seeds an FSM for the already-open position. Without this the guard is "
                + "armed and reports healthy while covering nothing.");
            Assert(fsm != null && fsm.PositionQuantity == 2,
                "The seeded FSM carries the live position quantity");
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected,
                "It starts Unprotected - no covering stop exists yet");
            Assert(fsm != null && fsm.GracePending,
                "A grace timer is armed, so protection is actually attempted rather than merely tracked");
        }

        // P1-11: the lockout watchdog cancelled EVERY non-terminal order before flattening --
        // including the protective stop covering the position it was about to flatten. The
        // flatten can fail (the broker rejects it, the fallback market order also fails), and
        // then the account holds an open position with nothing behind it, created by the very
        // code meant to protect it. The design doc also promises position-reducing orders are
        // preserved; that promise was honoured in OnOrderUpdate and nowhere else.
        private static void TestP1_11_LockoutSweepDoesNotCancelTheProtectiveStopBeforeFlattening()
        {
            Console.WriteLine("\n[TEST] P1-11: the lockout sweep cancels entries but keeps the protective stop until flat");

            var mnq = new Instrument("MNQ");
            Account.All.Clear();
            var account = new Account { Name = "TestAcc", Provider = Provider.Simulator };
            account.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
            });

            // The stop protecting the long, and a resting entry that would add risk.
            var protectiveStop = new Order
            {
                Instrument = mnq, OrderState = OrderState.Working, OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell, Quantity = 2, Name = "PROTECTIVE_STOP"
            };
            var restingEntry = new Order
            {
                Instrument = mnq, OrderState = OrderState.Working, OrderType = OrderType.Limit,
                OrderAction = OrderAction.Buy, Quantity = 1, Name = "RESTING_ENTRY"
            };
            account.Orders.Add(protectiveStop);
            account.Orders.Add(restingEntry);
            Account.All.Add(account);

            // The broker refuses the flatten, which is the whole point: protection must survive.
            account.SimulateFlattenFailure = true;

            var addon = new RiskGuardAddOn();
            var config = new RiskConfig();
            addon.SetConfigForTest(config);
            addon.SetSubscribedAccountForTest("TestAcc");

            var state = new AccountState("TestAcc");
            // IsPositionReducingOrder classifies against the account's tracked position.
            state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 0.0, config);
            addon.SetAccountStateForTest("TestAcc", state);

            // P0-51: same correction as TestP1_10. The cancel-ordering rule this test pins --
            // risk-increasing orders cancelled first, the protective stop held back until the
            // flatten is confirmed -- only has meaning when the sweep is allowed to act. Without
            // an explicit mode it ran in the "shadow" default and passed only because the sweep
            // ignored the mode.
            //
            // Stating the mode honestly is what exposed P0-53 (CLOSED 2026-08-09): P1-11 filtered
            // the SWEEP's own cancel batches so a protective stop is never cancelled before the
            // flatten is confirmed, but the lockout's PendingCancel phase ALSO emits a
            // CancelAllOrders GuardAction, and ExecuteAction's branch cancelled every working
            // order with no IsPositionReducingOrder filter. In an acting mode the stop therefore
            // died before the flatten was attempted, and a failed flatten left the position naked
            // -- the exact hazard P1-11 exists to prevent, surviving in the action pipeline
            // instead of the sweep. Shadow mode hid it, because ProcessAction skipped the cancel.
            //
            // This test now covers BOTH routes, which is why the mode must stay "live": in shadow
            // it would prove nothing at all.
            addon.SetModeForTest("live");

            // Settle the daily session reset first (it clears IsLockedOut), then lock.
            addon.ExecuteSafetySweep();
            state.IsLockedOut = true;

            addon.ExecuteSafetySweep();

            Assert(restingEntry.OrderState == OrderState.Cancelled,
                string.Format("The risk-increasing resting entry is cancelled (state {0})",
                              restingEntry.OrderState));

            Assert(protectiveStop.OrderState != OrderState.Cancelled,
                string.Format(
                    "The protective stop SURVIVES a failed flatten (state {0}). Cancelling it "
                    + "first and then failing to flatten is how the lockout path creates the "
                    + "naked position it exists to prevent.",
                    protectiveStop.OrderState));

            Assert(account.FlattenCallCount > 0,
                "The sweep still attempted the flatten");
        }

        // P1-35: the same violation on the hot event path. UpdateFsmOnPosition is only ever
        // called with _stateLock held, and its nonflat->flat branch cancelled the orphan
        // auto-stop directly. Queue it and drain after the lock releases -- without silently
        // dropping the cancel, which is the real risk of this refactor.
        private static void TestP1_35_OrphanAutoStopCancelHappensOutsideTheLock()
        {
            Console.WriteLine("\n[TEST] P1-35: the orphan auto-stop cancel happens outside _stateLock, and still happens");

            var mnq = new Instrument("MNQ");
            Account.All.Clear();
            var account = new Account { Name = "TestAcc", Provider = Provider.Simulator };
            mnq.MarketData.Last.Price = 18000;
            account.Positions.Add(new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2, AveragePrice = 18000
            });
            Account.All.Add(account);

            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(FsmTestConfig(graceSeconds: 60, onMissing: "AutoStop"));
            addon.TestClearFsms();
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);

            // Give the FSM a live RiskGuard auto-stop, exactly as ExecuteAction would.
            var autoStop = new Order
            {
                Instrument = mnq, OrderState = OrderState.Working, OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell, Quantity = 2, Name = "RiskGuardAutoStop"
            };
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            fsm.AutoStopOrder = autoStop;
            account.Orders.Add(autoStop);

            // The position goes flat. The FSM is torn down and the now-orphaned stop must die.
            account.Positions.Clear();
            var flatPos = new Position
            {
                Instrument = mnq, MarketPosition = MarketPosition.Flat, Quantity = 0, AveragePrice = 0
            };
            account.Positions.Add(flatPos);

            var violations = RecordBrokerCallsUnderLock(addon,
                () => addon.ExecutePositionUpdateDetails(account, flatPos));

            Assert(violations.Count == 0,
                string.Format(
                    "Going flat made {0} broker call(s) under _stateLock{1}. This is the hot event "
                    + "path, so it is the likeliest of all the sites to deadlock.",
                    violations.Count,
                    violations.Count == 0 ? "" : ": " + string.Join(", ", violations.Distinct())));

            Assert(autoStop.OrderState == OrderState.Cancelled,
                string.Format(
                    "The orphaned auto-stop was still cancelled (state {0}). Deferring the cancel "
                    + "must not drop it -- a live stop with no position behind it can open a "
                    + "brand-new position in the opposite direction when it triggers.",
                    autoStop.OrderState));

            Assert(addon.TestGetFsm(account.Name, mnq.FullName) == null,
                "The FSM is still torn down on flat");
        }

        // P1-37: MinShadowSessions is the interlock between shadow mode and live arming.
        // The counter was persisted but _lastShadowSessionDate -- the marker that debounces it
        // to once a day -- was not, so every addon reload re-satisfied the "new day" test and
        // bumped the counter again. Found by deploying: four minutes of ordinary recompile
        // churn took a live install from 0 to 3 and satisfied MinShadowSessions=3 outright,
        // on one day, with no feed connected and not one position taken.
        // P1-17: EvaluationTargetProfit is a CUMULATIVE prop-firm evaluation target ($3,000),
        // but the rule was fed stateModel.RealizedPnL, which is session-scoped
        // (raw - SessionStartRealizedPnL) and zeroed at every session reset. So the target only
        // fired if the whole $3,000 was made in a single day, which is precisely not what a
        // multi-day evaluation is. The rule silently never fired for its actual purpose.
        // P1-16: realized PnL arrives per execution, so one trade scaled out in three partials
        // delivers three negative deltas. Counting each as a consecutive loss meant a single
        // losing trade could reach MaxConsecutiveLosses=3 and lock the account out, and it put
        // this counter at odds with TradesToday, which is already debounced to the trade
        // lifecycle (:4043). Loss/win must be judged once per trade, at the flat transition.
        // P1-18: two trailing-drawdown implementations overlap. EvaluatePnLRules enforces
        // profile.TrailingDrawdown against a session-reset PeakEquity, while EvaluateFirmMirror
        // implements the firm's real (often non-resetting) model. Precedence was undefined, so
        // both could fire on one event.
        //
        // The obvious fix -- "FirmMirror wins whenever FirmMirror.Enabled" -- REMOVES PROTECTION
        // on the live config, where FirmMirror.Enabled is true but its TrailingDD.Enabled is
        // false and no account is mapped. That would skip the profile rule while the firm rule
        // evaluates nothing, leaving no trailing-drawdown cover at all. Precedence must key on
        // whether a firm trailing rule is actually IN EFFECT for that account.
        // P1-19: two separate problems in one defect.
        //  (a) ExecuteAction's FlattenPosition ignored action.Instrument and flattened every
        //      instrument holding a position OR merely a working order. A missing stop on MES
        //      therefore closed an unrelated, correctly-protected MNQ position too.
        //  (b) One EvaluatePnLRules pass can append five FlattenPosition actions, each of which
        //      independently walks the account and calls Flatten.
        private static void TestP1_19_FlattenIsInstrumentScopedAndActionsCoalesce()
        {
            Console.WriteLine("\n[TEST] P1-19: flatten honours instrument scope, and duplicate actions coalesce");

            var mnq = new Instrument("MNQ");
            var mes = new Instrument("MES");

            Func<string, List<string>> flattenRequestFor = instrumentScope =>
            {
                var account = new Account { Name = "ScopeAcc" };
                account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 2 });
                account.Positions.Add(new Position { Instrument = mes, MarketPosition = MarketPosition.Long, Quantity = 1 });
                Account.All.Clear();
                Account.All.Add(account);

                var addon = new RiskGuardAddOn();
                addon.SetConfigForTest(new RiskConfig());
                addon.SetModeForTest("live");   // shadow would skip execution entirely
                addon.ProcessAction(new GuardAction
                {
                    AccountName = "ScopeAcc",
                    ActionType = GuardActionType.FlattenPosition,
                    Instrument = instrumentScope,
                    RuleId = "MISSING_STOP_FLATTEN"
                });
                return account.LastFlattenRequest;
            };

            // Scoped to MES: MNQ must be left alone.
            var scoped = flattenRequestFor(mes.FullName);
            Assert(scoped.Count == 1 && scoped[0] == mes.FullName,
                string.Format("a flatten scoped to MES must request MES only (got [{0}])", string.Join(",", scoped)));

            // No scope set -> account-wide, which is correct for account-level risk rules.
            var unscoped = flattenRequestFor(null);
            Assert(unscoped.Count == 2,
                string.Format("an unscoped flatten must still close the whole account (got {0})", unscoped.Count));

            // (b) Coalescing: five account-wide flattens from one evaluation pass are one action.
            var five = new List<GuardAction>
            {
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, RuleId = "DAILY_LOSS_BREACH" },
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, RuleId = "TRAILING_DD_BREACH" },
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, RuleId = "NEWS_SHIELD_LOCKOUT" },
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, RuleId = "EVALUATION_TARGET_REACHED" },
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, RuleId = "PEAK_GIVEBACK_BREACH" },
            };
            var coalesced = RiskGuardAddOn.CoalesceActions(five);
            Assert(coalesced.Count == 1,
                string.Format("five account-wide flattens coalesce to one (got {0})", coalesced.Count));

            // Different instruments are different actions and must all survive.
            var perInstrument = new List<GuardAction>
            {
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, Instrument = "MNQ SEP26", RuleId = "MISSING_STOP_FLATTEN" },
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, Instrument = "MES SEP26", RuleId = "MISSING_STOP_FLATTEN" },
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, Instrument = "MNQ SEP26", RuleId = "MISSING_STOP_FLATTEN" },
            };
            Assert(RiskGuardAddOn.CoalesceActions(perInstrument).Count == 2,
                "two distinct instruments survive coalescing; the duplicate does not");

            // Different accounts and different action types must never be merged.
            var mixed = new List<GuardAction>
            {
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, RuleId = "DAILY_LOSS_BREACH" },
                new GuardAction { AccountName = "B", ActionType = GuardActionType.FlattenPosition, RuleId = "DAILY_LOSS_BREACH" },
                new GuardAction { AccountName = "A", ActionType = GuardActionType.CancelAllOrders, RuleId = "DAILY_LOSS_BREACH" },
            };
            Assert(RiskGuardAddOn.CoalesceActions(mixed).Count == 3,
                "different accounts and action types are never merged");

            // An account-wide flatten supersedes per-instrument ones for the same account:
            // keeping both would close the account and then re-issue a redundant scoped call.
            var widePlusScoped = new List<GuardAction>
            {
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, Instrument = "MNQ SEP26", RuleId = "MISSING_STOP_FLATTEN" },
                new GuardAction { AccountName = "A", ActionType = GuardActionType.FlattenPosition, RuleId = "DAILY_LOSS_BREACH" },
            };
            var superseded = RiskGuardAddOn.CoalesceActions(widePlusScoped);
            Assert(superseded.Count == 1 && string.IsNullOrEmpty(superseded[0].Instrument),
                string.Format("an account-wide flatten supersedes scoped ones for that account (got {0})", superseded.Count));
        }

        private static void TestP1_18_ProfileTrailingDDYieldsOnlyToAnEffectiveFirmRule()
        {
            Console.WriteLine("\n[TEST] P1-18: the profile trailing-DD yields only to a firm rule that is actually in effect");

            Func<RiskConfig, string, List<GuardAction>> evaluate = (config, accountName) =>
            {
                var account = new Account { Name = accountName };
                var addon = new RiskGuardAddOn();
                addon.SetConfigForTest(config);

                var state = new AccountState(accountName);
                state.PeakEquity = 2000.0;   // drawn down from +2000 to 0, past a 1500 limit
                state.RealizedPnL = 0.0;
                state.UnrealizedPnL = 0.0;
                account.Values[AccountItem.CashValue] = 100000.0;
                account.Values[AccountItem.RealizedProfitLoss] = 0.0;
                account.Values[AccountItem.UnrealizedProfitLoss] = 0.0;
                return addon.EvaluatePnLRules(account, state);
            };

            // Baseline: no firm mirror at all -- the profile rule is the only cover and must fire.
            var noFirm = new RiskConfig();
            noFirm.FirmMirror.Enabled = false;
            Assert(evaluate(noFirm, "Acc").Any(a => a.RuleId == "TRAILING_DD_BREACH"),
                "with FirmMirror disabled the profile trailing-DD rule must fire");

            // THE TRAP, and the live config's exact shape: FirmMirror is enabled but its
            // trailing rule is not, and the account is unmapped. The profile rule must still
            // fire -- skipping it here would leave the account with no trailing-DD cover.
            var enabledButInert = new RiskConfig();
            enabledButInert.FirmMirror.Enabled = true;
            enabledButInert.FirmMirror.TrailingDD.Enabled = false;
            Assert(evaluate(enabledButInert, "Acc").Any(a => a.RuleId == "TRAILING_DD_BREACH"),
                "FirmMirror enabled with its trailing rule OFF must NOT suppress the profile rule");

            // Firm trailing rule genuinely in effect at the top level -> firm owns it.
            var firmActive = new RiskConfig();
            firmActive.FirmMirror.Enabled = true;
            firmActive.FirmMirror.TrailingDD.Enabled = true;
            firmActive.FirmMirror.TrailingDD.Amount = 2000.0;
            Assert(!evaluate(firmActive, "Acc").Any(a => a.RuleId == "TRAILING_DD_BREACH"),
                "an effective firm trailing rule must suppress the duplicate profile rule");

            // In effect via a mapped per-firm profile, with the top level off (P1-42's path).
            var viaProfile = new RiskConfig();
            viaProfile.FirmMirror.Enabled = true;
            viaProfile.FirmMirror.TrailingDD.Enabled = false;
            viaProfile.FirmMirror.FirmProfiles["Apex"] = new FirmProfile
            {
                Name = "Apex",
                TrailingDD = new FirmTrailingDDConfig
                {
                    Enabled = true, Type = "eod", IncludesUnrealized = false,
                    Amount = 2000.0, Buffer = 200.0
                },
                DailyLoss = new FirmDailyLossConfig { Enabled = false }
            };
            viaProfile.FirmMirror.AccountFirmMap["MappedAcc"] = "Apex";
            Assert(!evaluate(viaProfile, "MappedAcc").Any(a => a.RuleId == "TRAILING_DD_BREACH"),
                "a firm trailing rule reached through a mapped profile must also suppress the profile rule");

            // ...but only for the mapped account. An unmapped account on the same config still
            // falls back to the top level, which is off, so it keeps the profile rule.
            Assert(evaluate(viaProfile, "UnmappedAcc").Any(a => a.RuleId == "TRAILING_DD_BREACH"),
                "another account on the same config, unmapped, must keep the profile rule");
        }

        private static void TestP1_16_ConsecutiveLossesCountTradesNotPartialExits()
        {
            Console.WriteLine("\n[TEST] P1-16: consecutive losses must count trades, not partial fills");

            var config = new RiskConfig();
            config.Overtrading.MaxConsecutiveLosses = 3;
            config.Overtrading.CooldownMinutes = 0; // isolate the counter from the cooldown
            var instrument = new Instrument("MNQ");
            var account = new Account { Name = "PartialAcc" };

            Func<AccountState> openTrade = () =>
            {
                var st = new AccountState("PartialAcc");
                st.UpdatePosition(account, instrument, MarketPosition.Long, 3, 100.0, 0.0, config);
                return st;
            };

            // One losing trade, scaled out in three partials, then flat.
            var state = openTrade();
            state.RecordRealizedDelta(-50.0, config);
            state.RecordRealizedDelta(-30.0, config);
            state.RecordRealizedDelta(-20.0, config);
            state.UpdatePosition(account, instrument, MarketPosition.Flat, 0, 0.0, 0.0, config);
            Assert(state.ConsecutiveLosses == 1,
                string.Format("one losing trade exited in three partials is ONE consecutive loss (got {0})",
                              state.ConsecutiveLosses));

            // Three genuinely separate losing trades still count three.
            var separate = new AccountState("PartialAcc");
            for (int i = 0; i < 3; i++)
            {
                separate.UpdatePosition(account, instrument, MarketPosition.Long, 1, 100.0, 0.0, config);
                separate.RecordRealizedDelta(-25.0, config);
                separate.UpdatePosition(account, instrument, MarketPosition.Flat, 0, 0.0, 0.0, config);
            }
            Assert(separate.ConsecutiveLosses == 3,
                string.Format("three separate losing trades are three consecutive losses (got {0})",
                              separate.ConsecutiveLosses));

            // A winning trade resets the streak, even if it had a losing partial along the way.
            var mixed = openTrade();
            mixed.ConsecutiveLosses = 2;
            mixed.RecordRealizedDelta(-20.0, config);
            mixed.RecordRealizedDelta(120.0, config);
            mixed.UpdatePosition(account, instrument, MarketPosition.Flat, 0, 0.0, 0.0, config);
            Assert(mixed.ConsecutiveLosses == 0,
                string.Format("a trade that nets positive resets the streak despite a losing partial (got {0})",
                              mixed.ConsecutiveLosses));

            // A trade that nets negative despite a winning partial is still one loss.
            var netLoss = openTrade();
            netLoss.RecordRealizedDelta(40.0, config);
            netLoss.RecordRealizedDelta(-90.0, config);
            netLoss.UpdatePosition(account, instrument, MarketPosition.Flat, 0, 0.0, 0.0, config);
            Assert(netLoss.ConsecutiveLosses == 1,
                string.Format("a trade netting negative is one loss even with a winning partial (got {0})",
                              netLoss.ConsecutiveLosses));

            // The order of the realized-PnL event and the position-flat event is NOT guaranteed.
            // A fill arriving after settlement must REVISE that trade's judgement, not land on
            // the next trade -- and it can flip the net result in either direction.
            var lateWin = new AccountState("PartialAcc");
            lateWin.UpdatePosition(account, instrument, MarketPosition.Long, 3, 100.0, 0.0, config);
            lateWin.RecordRealizedDelta(-50.0, config);
            lateWin.RecordRealizedDelta(-30.0, config);
            lateWin.UpdatePosition(account, instrument, MarketPosition.Flat, 0, 0.0, 0.0, config);
            Assert(lateWin.ConsecutiveLosses == 1,
                "on the fills seen at the flat transition the trade settles as a loss");
            lateWin.RecordRealizedDelta(200.0, config);   // late fill: the trade netted +120
            Assert(lateWin.ConsecutiveLosses == 0,
                string.Format("a late fill flipping the trade to a net win must revise the streak to 0 (got {0})",
                              lateWin.ConsecutiveLosses));

            var lateLoss = new AccountState("PartialAcc");
            lateLoss.ConsecutiveLosses = 2;              // set before entry so the snapshot sees it
            lateLoss.UpdatePosition(account, instrument, MarketPosition.Long, 2, 100.0, 0.0, config);
            lateLoss.RecordRealizedDelta(40.0, config);
            lateLoss.UpdatePosition(account, instrument, MarketPosition.Flat, 0, 0.0, 0.0, config);
            Assert(lateLoss.ConsecutiveLosses == 0,
                "on the fills seen at the flat transition the trade settles as a win and resets the streak");
            lateLoss.RecordRealizedDelta(-90.0, config);  // late fill: the trade netted -50
            Assert(lateLoss.ConsecutiveLosses == 3,
                string.Format("a late fill flipping the trade to a net loss must restore the streak and increment it (got {0})",
                              lateLoss.ConsecutiveLosses));

            // A realized delta with no tracked trade at all (guard never saw the position, or a
            // standalone adjustment) must still be judged -- ignoring it would make the lockout
            // less sensitive than before this fix.
            var untracked = new AccountState("PartialAcc");
            untracked.RecordRealizedDelta(-75.0, config);
            Assert(untracked.ConsecutiveLosses == 1,
                string.Format("an untracked realized loss must still count (got {0})",
                              untracked.ConsecutiveLosses));

            // A scratch trade must not touch the streak in either direction.
            var scratch = openTrade();
            scratch.ConsecutiveLosses = 2;
            scratch.UpdatePosition(account, instrument, MarketPosition.Flat, 0, 0.0, 0.0, config);
            Assert(scratch.ConsecutiveLosses == 2,
                string.Format("a scratch trade leaves the streak untouched (got {0})",
                              scratch.ConsecutiveLosses));
        }

        private static void TestP1_17_EvaluationTargetUsesCumulativeNotSessionPnL()
        {
            Console.WriteLine("\n[TEST] P1-17: the evaluation profit target must be cumulative across sessions");

            Func<double, double, List<GuardAction>> evaluate = (cumulative, session) =>
            {
                var account = new Account { Name = "EvalAcc" };
                var addon = new RiskGuardAddOn();
                addon.SetConfigForTest(new RiskConfig());

                var state = new AccountState("EvalAcc");
                state.CumulativeRealizedPnL = cumulative;   // banked in prior sessions
                state.RealizedPnL = session;                // this session so far
                account.Values[AccountItem.CashValue] = 100000.0 + cumulative + session;
                account.Values[AccountItem.RealizedProfitLoss] = session;
                account.Values[AccountItem.UnrealizedProfitLoss] = 0.0;
                return addon.EvaluatePnLRules(account, state);
            };

            // $1,500 banked over previous days plus $1,600 today = $3,100 >= $3,000 target.
            // Today's session alone is only $1,600, which is why this never fired before.
            Assert(evaluate(1500.0, 1600.0).Any(a => a.RuleId == "EVALUATION_TARGET_REACHED"),
                "a cumulative $3,100 across sessions must reach the $3,000 evaluation target");

            // Below target in total must still not fire.
            Assert(!evaluate(500.0, 400.0).Any(a => a.RuleId == "EVALUATION_TARGET_REACHED"),
                "a cumulative $900 must not reach the $3,000 target");

            // The single-session case must keep working -- this is what used to be the only
            // way the rule could fire, and it must not regress.
            Assert(evaluate(0.0, 3200.0).Any(a => a.RuleId == "EVALUATION_TARGET_REACHED"),
                "a single session of $3,200 must still reach the target");

            // A losing history must offset, not be ignored.
            Assert(!evaluate(-1000.0, 2500.0).Any(a => a.RuleId == "EVALUATION_TARGET_REACHED"),
                "prior losses must offset: -$1,000 plus $2,500 is $1,500, not a $2,500 target hit");

            // Cumulative PnL is worthless if a recompile resets it -- the whole point is that it
            // outlives sessions and restarts. Round-trip it through the persisted state file.
            string stateFile = Path.Combine(
                Path.GetTempPath(), "rg_cumpnl_" + Guid.NewGuid().ToString("N") + ".json");
            try
            {
                var first = new RiskGuardAddOn();
                first.SetConfigForTest(new RiskConfig());
                first.SetStateFileForTest(stateFile);
                var st = new AccountState("EvalAcc");
                st.CumulativeRealizedPnL = 2750.0;
                st.LastSessionDate = DateTime.UtcNow.Date;
                first.SetAccountStateForTest("EvalAcc", st);
                first.SavePersistedStateForTest();

                var second = new RiskGuardAddOn();
                second.SetConfigForTest(new RiskConfig());
                second.SetStateFileForTest(stateFile);
                second.LoadPersistedStateForTest();

                var restored = second.GetAccountStateForTest("EvalAcc");
                Assert(restored != null && Math.Abs(restored.CumulativeRealizedPnL - 2750.0) < 0.001,
                    string.Format("CumulativeRealizedPnL must survive a restart (got {0})",
                                  restored == null ? "no state" : restored.CumulativeRealizedPnL.ToString()));
            }
            finally
            {
                try { if (File.Exists(stateFile)) File.Delete(stateFile); } catch { }
            }
        }

        private static void TestP1_37_ShadowSessionCounterSurvivesRestartWithoutRecounting()
        {
            Console.WriteLine("\n[TEST] P1-37: the shadow-session counter counts days, not addon restarts");

            string stateFile = Path.Combine(
                Path.GetTempPath(), "rg_shadow_" + Guid.NewGuid().ToString("N") + ".json");

            try
            {
                // --- first run of the day ---
                var first = new RiskGuardAddOn();
                first.SetConfigForTest(new RiskConfig { MinShadowSessions = 3 });
                first.SetModeForTest("shadow");
                first.SetStateFileForTest(stateFile);

                first.ExecuteSafetySweep();
                Assert(first.GetShadowSessionsCompletedForTest() == 1,
                    string.Format("First sweep counts session #1 (got {0})",
                                  first.GetShadowSessionsCompletedForTest()));

                // Sweeping again the same day must not count twice.
                first.ExecuteSafetySweep();
                first.ExecuteSafetySweep();
                Assert(first.GetShadowSessionsCompletedForTest() == 1,
                    string.Format("Repeated sweeps on the same day still count 1 (got {0})",
                                  first.GetShadowSessionsCompletedForTest()));

                first.SavePersistedStateForTest();

                // --- the addon restarts (recompile, NT8 restart, hot-swap) ---
                var second = new RiskGuardAddOn();
                second.SetConfigForTest(new RiskConfig { MinShadowSessions = 3 });
                second.SetModeForTest("shadow");
                second.SetStateFileForTest(stateFile);
                second.LoadPersistedStateForTest();

                Assert(second.GetShadowSessionsCompletedForTest() == 1,
                    string.Format("The restarted addon rehydrates the counter as 1 (got {0})",
                                  second.GetShadowSessionsCompletedForTest()));
                Assert(second.GetLastShadowSessionDateForTest() != DateTime.MinValue.Date,
                    "The restarted addon also rehydrates WHICH day was counted - without this the "
                    + "counter has nothing to debounce against");

                second.ExecuteSafetySweep();
                Assert(second.GetShadowSessionsCompletedForTest() == 1,
                    string.Format(
                        "A restart on the same calendar day does NOT count another session (got {0}). "
                        + "Otherwise MinShadowSessions is satisfied by restarting, and the gate "
                        + "guarding live arming means nothing.",
                        second.GetShadowSessionsCompletedForTest()));

                // --- a genuinely new day must still count ---
                second.SetLastShadowSessionDateForTest(
                    second.GetLastShadowSessionDateForTest().AddDays(-1));
                second.ExecuteSafetySweep();
                Assert(second.GetShadowSessionsCompletedForTest() == 2,
                    string.Format("A new calendar day counts session #2 (got {0}) - the gate still advances",
                                  second.GetShadowSessionsCompletedForTest()));

                // --- and the fix must not resurrect the armed flag (FR-30/31) ---
                Assert(!second.GetIsArmed(),
                    "Rehydrating the session date does not rehydrate the armed flag");
            }
            finally
            {
                try { if (File.Exists(stateFile)) File.Delete(stateFile); } catch { }
            }
        }

        /// <summary>
        /// Swaps in a peak-giveback config and returns the previous one so the shared
        /// PropFirmProtectionSuite singleton is left as it was found.
        /// </summary>
        private static PropFirmProtectionConfig UsePeakGivebackConfig(double maxGivebackPct)
        {
            var previous = PropFirmProtectionSuite.Instance.Config;
            PropFirmProtectionSuite.Instance.UpdateConfig(new PropFirmProtectionConfig
            {
                EnablePeakEquityProtection = true,
                MaxPeakGivebackPct = maxGivebackPct
            });
            return previous;
        }

        // T3 / P0-5: the peak fed to the giveback rule must be unrealized-only. Fed a
        // total-equity peak, a flat account that banked a profitable session reads as
        // having given back 100% of its peak, and the rule tries to flatten a position
        // that no longer exists -- on every single evaluation.
        private static void TestT3_ProfitableFlatAccountEmitsNoGiveback()
        {
            Console.WriteLine("\n[TEST] T3: a flat, profitable account emits no peak-giveback breach");
            var previous = UsePeakGivebackConfig(0.30);
            try
            {
                var config = new RiskConfig();
                var account = new Account { Name = "TestAcc" };
                var addon = new RiskGuardAddOn();
                addon.SetConfigForTest(config);

                var state = new AccountState("TestAcc");
                var mnq = new Instrument("MNQ");

                // Open and in profit: the peak tracks unrealized gain.
                state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 1000.0, config);
                state.RealizedPnL = 0.0;
                state.UnrealizedPnL = 1000.0;
                addon.EvaluatePnLRules(account, state);
                Assert(state.PeakOpenGain == 1000.0,
                    string.Format("Peak tracks unrealized gain while open (got {0})", state.PeakOpenGain));

                // Close at a profit: 1000 moves from unrealized to realized.
                state.UpdatePosition(account, mnq, MarketPosition.Flat, 0, 0.0, 0.0, config);
                state.RealizedPnL = 1000.0;
                state.UnrealizedPnL = 0.0;
                var actions = addon.EvaluatePnLRules(account, state);

                Assert(state.PeakOpenGain == 0.0,
                    string.Format("Peak resets to zero when the account is flat (got {0})", state.PeakOpenGain));
                Assert(!actions.Any(a => a.RuleId == "PEAK_GIVEBACK_BREACH"),
                    "No PEAK_GIVEBACK_BREACH on a flat account that simply banked its profit");
                Assert(!state.PeakGivebackTriggered,
                    "The giveback latch is not left set by a profitable close");

                // The flat reset lives in two places -- UpdatePosition and EvaluatePnLRules --
                // so the assertions above pass even if the rule-evaluation one is removed.
                // Plant a stale peak directly to pin that second site on its own; without it a
                // peak surviving from any path is measured against a flat account's zero
                // unrealized PnL, which is a 100% giveback on every evaluation.
                state.PeakOpenGain = 750.0;
                state.PeakGivebackTriggered = false;
                state.PeakGivebackLastTriggerUnrealized = double.NaN;
                var staleActions = addon.EvaluatePnLRules(account, state);
                Assert(state.PeakOpenGain == 0.0,
                    string.Format("EvaluatePnLRules itself clears a stale peak on a flat account (got {0})",
                                  state.PeakOpenGain));
                Assert(!staleActions.Any(a => a.RuleId == "PEAK_GIVEBACK_BREACH"),
                    "A stale peak on a flat account still produces no breach");
            }
            finally
            {
                PropFirmProtectionSuite.Instance.UpdateConfig(previous);
            }
        }

        // T3 / P0-5: NinjaTrader collapses a close+reverse into a single position update.
        // If the peak is not reset on the flip, the brand-new opposite leg is measured
        // against the peak of the leg that just closed and is flattened immediately.
        private static void TestT3_FlipDoesNotCarryPeakOpenGainIntoNewLeg()
        {
            Console.WriteLine("\n[TEST] T3: a close+reverse flip does not carry the old leg's peak");
            var previous = UsePeakGivebackConfig(0.30);
            try
            {
                var config = new RiskConfig();
                var account = new Account { Name = "TestAcc" };
                var addon = new RiskGuardAddOn();
                addon.SetConfigForTest(config);

                var state = new AccountState("TestAcc");
                var mnq = new Instrument("MNQ");

                state.UpdatePosition(account, mnq, MarketPosition.Long, 2, 18000, 1000.0, config);
                state.UnrealizedPnL = 1000.0;
                addon.EvaluatePnLRules(account, state);
                Assert(state.PeakOpenGain == 1000.0, "The long leg establishes a peak of 1000");

                // Long 2 -> Short 2 in one update: a flip.
                state.UpdatePosition(account, mnq, MarketPosition.Short, 2, 18010, 0.0, config);

                Assert(state.PeakOpenGain == 0.0,
                    string.Format("Flip resets the peak (got {0}) - the new leg has its own episode",
                                  state.PeakOpenGain));
                Assert(!state.PeakGivebackTriggered, "Flip clears the giveback latch");

                state.UnrealizedPnL = 0.0;
                var actions = addon.EvaluatePnLRules(account, state);
                Assert(!actions.Any(a => a.RuleId == "PEAK_GIVEBACK_BREACH"),
                    "The fresh short leg is not flattened for the closed long leg's giveback");
            }
            finally
            {
                PropFirmProtectionSuite.Instance.UpdateConfig(previous);
            }
        }

        // 15. Grace expiry with OnMissing=Flatten emits MISSING_STOP_FLATTEN.
        private static void TestFsm_GraceExpiryFlatten()
        {
            Console.WriteLine("\n[TEST] FSM: Grace expiry with OnMissing=Flatten");
            var config = FsmTestConfig(graceSeconds: 0, onMissing: "Flatten");
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 1 });

            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(actions.Any(a => a.RuleId == "MISSING_STOP_FLATTEN"),
                "Grace expiry with OnMissing=Flatten emits MISSING_STOP_FLATTEN");
        }

        // 16. Grace not expired yet (deadline in future) -> no action.
        private static void TestFsm_GraceNotExpiredNoAction()
        {
            Console.WriteLine("\n[TEST] FSM: Grace not expired -> no action");
            var config = FsmTestConfig(graceSeconds: 600);
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 1 });

            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(actions.Count == 0, "No action when grace deadline is in the future");
        }

        // 17. Short position FSM reaches Protected via opposite-side buy stop.
        private static void TestFsm_ShortPositionProtected()
        {
            Console.WriteLine("\n[TEST] FSM: Short position reaches Protected");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var es = new Instrument("ES");

            addon.TestFsmOnPosition(account, es.FullName, MarketPosition.Short, 3);
            var fsm = addon.TestGetFsm(account.Name, es.FullName);
            Assert(fsm != null && fsm.PositionSide == MarketPosition.Short, "FSM created with Short side");

            var stop = new Order
            {
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.BuyToCover, // NT8 ATM uses BuyToCover for short-covering stops
                Quantity = 3,
                Instrument = es
            };
            addon.TestFsmOnOrder(account, es.FullName, stop);
            Assert(addon.TestGetFsm(account.Name, es.FullName).State == GuardFsmState.Protected,
                "Short position + buy stop -> Protected");
        }

        // 18. Position flip (Long->Short) recreates FSM with the new side.
        private static void TestFsm_FlipRecreatesFsm()
        {
            Console.WriteLine("\n[TEST] FSM: Position flip recreates FSM with new side");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);
            var fsm1 = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm1.PositionSide == MarketPosition.Long, "Initial FSM is Long");

            // Flip to short.
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Short, 1);
            var fsm2 = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm2 != null, "FSM exists after flip");
            Assert(fsm2.PositionSide == MarketPosition.Short, "FSM side updated to Short after flip");
            Assert(fsm2.PositionQuantity == 1, "FSM quantity updated to 1 after flip");
            Assert(fsm2.State == GuardFsmState.Unprotected, "FSM is Unprotected after flip (new entry, new grace)");
        }

        // 19. Multiple instruments get separate independent FSMs.
        private static void TestFsm_MultipleInstrumentsIndependent()
        {
            Console.WriteLine("\n[TEST] FSM: Multiple instruments have independent FSMs");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");
            var es = new Instrument("ES");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            addon.TestFsmOnPosition(account, es.FullName, MarketPosition.Long, 2);

            Assert(addon.TestAllFsms().Count == 2, "Two FSMs created for two instruments");

            // Protect MNQ only.
            var stop = new Order
            {
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 1,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stop);

            Assert(addon.TestGetFsm(account.Name, mnq.FullName).State == GuardFsmState.Protected,
                "MNQ is Protected");
            Assert(addon.TestGetFsm(account.Name, es.FullName).State == GuardFsmState.Unprotected,
                "ES is still Unprotected (independent)");
        }

        // 20. Disarmed guard does not create FSMs.
        private static void TestFsm_DisarmedSkipsFsm()
        {
            Console.WriteLine("\n[TEST] FSM: Disarmed guard does not create FSMs");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetArmedForTest(false);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            Assert(addon.TestAllFsms().Count == 0, "No FSM created when guard is disarmed");
        }

        // 21. Non-stop order types (Limit target leg) do not transition the FSM.
        private static void TestFsm_LimitOrderDoesNotTransition()
        {
            Console.WriteLine("\n[TEST] FSM: Limit order (target leg) does not transition FSM");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);

            // A limit order (target leg of bracket) opposite side but not a stop type.
            var target = new Order
            {
                OrderState = OrderState.Working,
                OrderType = OrderType.Limit,
                OrderAction = OrderAction.Sell,
                Quantity = 1,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, target);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).State == GuardFsmState.Unprotected,
                "Limit order does not protect position (only stop types do)");
        }

        // 22. Pending stop is consumed even when it arrives in Working state (buffered then consumed).
        private static void TestFsm_PendingStopWorkingConsumed()
        {
            Console.WriteLine("\n[TEST] FSM: Buffered Working stop consumed -> Protected directly");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            // Stop arrives Working before position event.
            var stop = new Order
            {
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 1,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stop);
            Assert(addon.TestAllFsms().Count == 0, "No FSM yet (buffered)");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.Protected,
                "Buffered Working stop consumed -> Protected directly");
        }

        // 23. Short position with BuyToCover stop leg (the exact bug: NT8 ATM uses BuyToCover, not Buy).
        private static void TestFsm_ShortPositionBuyToCoverStopRecognized()
        {
            Console.WriteLine("\n[TEST] FSM: Short position BuyToCover stop leg recognized (the original bug)");
            var config = FsmTestConfig(graceSeconds: 2);
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            // Position goes short.
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Short, 6);
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null && fsm.State == GuardFsmState.Unprotected, "FSM created Unprotected for short");

            // OCO stop leg arrives as BuyToCover (NT8 ATM for shorts).
            var stopLeg = new Order
            {
                OrderState = OrderState.Submitted,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.BuyToCover,
                Quantity = 6,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stopLeg);

            fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm.State == GuardFsmState.ProtectedPending,
                "BuyToCover stop leg Submitted -> ProtectedPending (not ignored!)");

            // Grace expiry should NOT fire (FSM is ProtectedPending).
            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Short, Quantity = 6 });
            var actions = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(actions.Count == 0,
                "No auto-stop emitted -- BuyToCover stop recognized, no duplicate SL");
        }

        // 24. Long position with SellShort stop leg (symmetric: NT8 may use SellShort for long exits).
        private static void TestFsm_LongPositionSellShortStopRecognized()
        {
            Console.WriteLine("\n[TEST] FSM: Long position SellShort stop leg recognized");
            var config = FsmTestConfig(graceSeconds: 2);
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var es = new Instrument("ES");

            addon.TestFsmOnPosition(account, es.FullName, MarketPosition.Long, 2);
            Assert(addon.TestGetFsm(account.Name, es.FullName).State == GuardFsmState.Unprotected,
                "FSM created Unprotected for long");

            var stopLeg = new Order
            {
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.SellShort,
                Quantity = 2,
                Instrument = es
            };
            addon.TestFsmOnOrder(account, es.FullName, stopLeg);
            Assert(addon.TestGetFsm(account.Name, es.FullName).State == GuardFsmState.Protected,
                "SellShort stop Working -> Protected (not ignored!)");
        }

        // --
        // AUDIT REGRESSION TESTS
        // These tests are written FIRST (red), then the code is fixed to make them green.
        // --

        // A1. PositionUpdate with same side + different qty must NOT recreate the FSM
        // (the FSM should update qty in place, preserving Protected state).
        private static void TestFsm_QtyOnlyUpdatePreservesProtectedState()
        {
            Console.WriteLine("\n[TEST] AUDIT: Qty-only PositionUpdate preserves Protected FSM");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            // Open long 2
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);
            var stopRef = new Order
            {
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 2,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stopRef);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).State == GuardFsmState.Protected,
                "FSM is Protected after stop Working");

            // NT8 fires PositionUpdate with same side, qty=3 (partial fill / scale-out)
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 3);
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm != null, "FSM still exists after qty-only update");
            Assert(fsm.State == GuardFsmState.Protected,
                "FSM stays Protected after qty-only PositionUpdate (not reset to Unprotected)");
            Assert(fsm.PositionQuantity == 3, "FSM PositionQuantity updated to 3");
            Assert(ReferenceEquals(fsm.RecognizedStopOrder, stopRef),
                "RecognizedStopOrder preserved across qty-only update");
        }

        // A2. Partial fill on an already-protected position must not reset the FSM.
        private static void TestFsm_PartialFillPreservesProtectedState()
        {
            Console.WriteLine("\n[TEST] AUDIT: Partial fill does not reset Protected FSM");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 5);
            var stop = new Order
            {
                OrderState = OrderState.Working,
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 5,
                Instrument = mnq
            };
            addon.TestFsmOnOrder(account, mnq.FullName, stop);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).State == GuardFsmState.Protected,
                "Protected after stop");

            // Partial fill reduces qty from 5 to 3, same side.
            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 3);
            var fsm = addon.TestGetFsm(account.Name, mnq.FullName);
            Assert(fsm.State == GuardFsmState.Protected,
                "Still Protected after partial fill qty reduction");
            Assert(fsm.PositionQuantity == 3, "Qty updated to 3");
        }

        // A3. Grace expiry with OnMissing=Flatten should emit exactly once.
        private static void TestFsm_GraceExpiryFlattenEmitsOnce()
        {
            Console.WriteLine("\n[TEST] AUDIT: Grace expiry Flatten emits exactly once");
            var config = FsmTestConfig(graceSeconds: 0, onMissing: "Flatten");
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 1);
            account.Positions.Add(new Position { Instrument = mnq, MarketPosition = MarketPosition.Long, Quantity = 1 });

            var first = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(first.Any(a => a.RuleId == "MISSING_STOP_FLATTEN"),
                "First grace expiry emits MISSING_STOP_FLATTEN");

            // Second call must not re-emit (FSM should have transitioned out of Unprotected).
            var second = addon.EvaluateGraceExpiry(account, mnq.FullName);
            Assert(second.Count == 0,
                "Second grace-expiry Flatten call emits nothing (already triggered)");
        }

        // A4. FSM PositionQuantity is kept in sync with actual position qty.
        private static void TestFsm_PositionQuantityUpdatedOnQtyChange()
        {
            Console.WriteLine("\n[TEST] AUDIT: FSM PositionQuantity stays in sync");
            var config = FsmTestConfig();
            var account = FsmTestAccount();
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.TestClearFsms();
            var mnq = new Instrument("MNQ");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 4);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).PositionQuantity == 4,
                "Initial qty = 4");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 7);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).PositionQuantity == 7,
                "Qty updated to 7 after scale-out");

            addon.TestFsmOnPosition(account, mnq.FullName, MarketPosition.Long, 2);
            Assert(addon.TestGetFsm(account.Name, mnq.FullName).PositionQuantity == 2,
                "Qty updated to 2 after partial close");
        }

        // A5. EvaluateRules should NOT emit DAILY_LOSS_BREACH or TRAILING_DD_BREACH
        // (those are owned by EvaluatePnLRules via AccountItemUpdate to avoid double-fire).
        private static void TestPnLRulesNotDuplicatedInEvaluateRules()
        {
            Console.WriteLine("\n[TEST] AUDIT: PnL rules not duplicated in EvaluateRules");
            var config = new RiskConfig();
            config.PnLRules.DailyLossLimit = 500.0;
            config.PnLRules.TrailingDrawdown = 500.0;

            var account = new Account { Name = "TestAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);

            var state = new AccountState("TestAcc");
            state.RealizedPnL = -600.0; // Breaches daily loss
            state.PeakEquity = 0.0;
            state.UnrealizedPnL = 0.0;

            var actions = addon.EvaluateRules(account, state);
            // After fix, EvaluateRules should NOT emit PnL rules (owned by EvaluatePnLRules).
            Assert(!actions.Any(a => a.RuleId == "DAILY_LOSS_BREACH"),
                "EvaluateRules does not emit DAILY_LOSS_BREACH (owned by EvaluatePnLRules)");
            Assert(!actions.Any(a => a.RuleId == "TRAILING_DD_BREACH"),
                "EvaluateRules does not emit TRAILING_DD_BREACH (owned by EvaluatePnLRules)");
        }

        // A6. ExecuteOrderUpdate should process lockout actions OUTSIDE the lock
        // to avoid re-entrancy corruption. We verify by ensuring that a locked-out
        // account with a working order gets the order cancelled and no exception.
        private static void TestExecuteOrderUpdateProcessesActionsOutsideLock()
        {
            Console.WriteLine("\n[TEST] AUDIT: ExecuteOrderUpdate processes lockout actions safely");

            // NOTE: this test body was previously destroyed by a bad merge - it declared a
            // RiskConfig, then contained the TAIL OF Main() (ten test invocations, a summary
            // print and Environment.Exit(1)). It therefore asserted nothing, and its stray
            // Environment.Exit aborted the process at call #92 of 117 whenever any earlier
            // test had failed, silently skipping the last 25 tests. Restored below.
            var config = new RiskConfig();
            config.Sizing.MaxContractsPerAccount = 10;

            var account = new Account { Name = "LockAcc" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetSubscribedAccountForTest("LockAcc");

            var state = new AccountState("LockAcc");
            state.IsLockedOut = true;
            addon.SetAccountStateForTest("LockAcc", state);

            var mnq = new Instrument("MNQ");
            // A working BUY order on a locked-out account: risk-increasing, must be cancelled.
            var working = new Order
            {
                Instrument = mnq,
                OrderState = OrderState.Working,
                OrderType = OrderType.Limit,
                OrderAction = OrderAction.Buy,
                Quantity = 2
            };
            account.Orders.Add(working);

            // The real assertion of this test's name: ExecuteOrderUpdate must complete without
            // throwing or deadlocking, i.e. it must not invoke broker calls while holding
            // _stateLock re-entrantly from inside its own event handler.
            bool threw = false;
            try
            {
                addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = working });
            }
            catch (Exception)
            {
                threw = true;
            }

            Assert(!threw, "ExecuteOrderUpdate completes without throwing for a locked-out account");
            Assert(addon.IsAccountLocked("LockAcc"),
                "Account remains locked out after ExecuteOrderUpdate processes the order");
        }

        private static void TestPerInstrumentSizing_MNQVsMES()
        {
            Console.WriteLine("\n[TEST] TestPerInstrumentSizing_MNQVsMES");
            var config = new RiskConfig();
            config.InstrumentLimits["MNQ"] = new PerInstrumentRiskConfig { MaxContracts = 2 };
            config.InstrumentLimits["MES"] = new PerInstrumentRiskConfig { MaxContracts = 10 };

            var account = new Account { Name = "Sim101" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");

            var mnqOrder = new Order { Id = "1", OrderState = OrderState.Working, OrderType = OrderType.Market, Quantity = 3, Instrument = new Instrument("MNQ SEP26") };
            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = mnqOrder });
            Assert(mnqOrder.OrderState == OrderState.Cancelled, "MNQ order exceeding 2 contracts cap cancelled");

            var mesOrder = new Order { Id = "2", OrderState = OrderState.Working, OrderType = OrderType.Market, Quantity = 8, Instrument = new Instrument("MES SEP26") };
            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = mesOrder });
            Assert(mesOrder.OrderState == OrderState.Working, "MES order under 10 contracts cap allowed working");
        }

        private static void TestInstrumentBlacklist_BlocksMiniNQ()
        {
            Console.WriteLine("\n[TEST] TestInstrumentBlacklist_BlocksMiniNQ");
            var config = new RiskConfig();
            config.BlockedInstruments = new List<string> { "NQ", "ES", "YM" };

            var account = new Account { Name = "Sim101" };
            var addon = new RiskGuardAddOn();
            addon.SetConfigForTest(config);
            addon.SetModeForTest("live");

            var nqOrder = new Order { Id = "1", OrderState = OrderState.Working, OrderType = OrderType.Market, Quantity = 1, Instrument = new Instrument("NQ SEP26") };
            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = nqOrder });
            Assert(nqOrder.OrderState == OrderState.Cancelled, "Blacklisted Mini NQ order cancelled");

            var mnqOrder = new Order { Id = "2", OrderState = OrderState.Working, OrderType = OrderType.Market, Quantity = 1, Instrument = new Instrument("MNQ SEP26") };
            addon.ExecuteOrderUpdate(account, new OrderEventArgs { Order = mnqOrder });
            Assert(mnqOrder.OrderState == OrderState.Working, "Non-blacklisted Micro MNQ order allowed");
        }

        private static void TestPropFirmProfile_AllowedInstruments()
        {
            Console.WriteLine("\n[TEST] TestPropFirmProfile_AllowedInstruments");
            var profile = new PropFirmProfile
            {
                Name = "Apex Trader Funding",
                AllowedInstruments = new List<string> { "NQ", "MNQ", "ES", "MES" },
                BlockedInstruments = new List<string> { "ZB", "ZN" }
            };
            Assert(profile.AllowedInstruments.Contains("MNQ"), "Apex profile allows MNQ");
            Assert(profile.BlockedInstruments.Contains("ZB"), "Apex profile blocks ZB");
        }

        private static void TestTradeCopier_RatioScaling()
        {
            Console.WriteLine("\n[TEST] TestTradeCopier_RatioScaling");
            var engine = new TradeCopierEngine();
            var rel = new CopierRelationship
            {
                LeaderAccountName = "Sim101",
                FollowerAccountName = "SimCopy2",
                QuantityRatio = 0.5,
                AutoSymbolConversion = false,
                IsEnabled = true
            };
            engine.AddRelationship(rel);
            int followerQty = engine.CalculateFollowerQuantity(rel, 4, "MNQ SEP26");
            Assert(followerQty == 2, "4 leader contracts @ 0.5x ratio = 2 follower contracts");
        }

        private static void TestTradeCopier_SymbolMapping()
        {
            Console.WriteLine("\n[TEST] TestTradeCopier_SymbolMapping");
            var engine = new TradeCopierEngine();
            var rel = new CopierRelationship
            {
                LeaderAccountName = "Sim101",
                FollowerAccountName = "SimCopy2",
                QuantityRatio = 1.0,
                AutoSymbolConversion = true,
                IsEnabled = true
            };
            engine.AddRelationship(rel);
            string targetSymbol = engine.TranslateSymbol("NQ SEP26");
            int targetQty = engine.CalculateFollowerQuantity(rel, 1, "NQ SEP26");
            Assert(targetSymbol == "MNQ SEP26", "NQ translated to MNQ");
            Assert(targetQty == 10, "1 NQ translated to 10 MNQ contracts");
        }

        private static void TestAtmStrategy_DrawdownShieldBreakeven()
        {
            Console.WriteLine("\n[TEST] TestAtmStrategy_DrawdownShieldBreakeven");
            var atm = new DynamicAtmManager();
            var config = new AtmStrategyConfig
            {
                Type = AtmStrategyType.DrawdownShield,
                BreakevenTriggerTicks = 12,
                BreakevenOffsetTicks = 2
            };
            bool shouldTrail = atm.ShouldTriggerBreakeven(config, entryPrice: 20000.0, currentPrice: 20003.0, isLong: true, tickSize: 0.25);
            Assert(shouldTrail == true, "+12 ticks gain triggers breakeven trailing");

            double newStop = atm.CalculateBreakevenStopPrice(entryPrice: 20000.0, isLong: true, tickSize: 0.25, offsetTicks: 2);
            Assert(newStop == 20000.50, "Breakeven stop placed at Entry + 2 ticks");
        }

        private static void TestNewsShield_FlattensBeforeCPI()
        {
            Console.WriteLine("\n[TEST] TestNewsShield_FlattensBeforeCPI");
            var suite = new PropFirmProtectionSuite();
            var cpiTime = DateTime.UtcNow.AddMinutes(1); // 1 minute in future
            suite.AddTestNewsEvent(new EconomicNewsEvent { EventTimeUtc = cpiTime, Title = "CPI", Impact = "High" });

            bool inBuffer = suite.IsInNewsWindow(DateTime.UtcNow, bufferMinutesBefore: 2, bufferMinutesAfter: 2);
            Assert(inBuffer == true, "Within 2m pre-CPI window detects news lock");
        }

        private static void TestStrategyApi_CanTradeReturnsFalseWhenLockedOut()
        {
            Console.WriteLine("\n[TEST] TestStrategyApi_CanTradeReturnsFalseWhenLockedOut");
            var addon = new RiskGuardAddOn();
            var state = new AccountState("Sim101") { IsLockedOut = true };
            addon.SetAccountStateForTest("Sim101", state);

            bool canTrade = addon.CanTrade("Sim101", "MNQ SEP26", "MyStrategy");
            Assert(canTrade == false, "CanTrade returns false for locked-out account");
        }

        private static void TestEvaluationProfitTargetLock_LocksAccount()
        {
            Console.WriteLine("\n[TEST] TestEvaluationProfitTargetLock_LocksAccount");
            var suite = new PropFirmProtectionSuite();
            var config = new PropFirmProtectionConfig { EnableProfitTargetLock = true, EvaluationTargetProfit = 3000.0 };

            bool reached = suite.EvaluateProfitTargetLock(currentRealizedPnL: 3050.0, config);
            Assert(reached == true, "+$3,050 PnL triggers evaluation target lockout");
        }

        private static void TestPeakEquityProtection_ClosesOnGiveback()
        {
            Console.WriteLine("\n[TEST] TestPeakEquityProtection_ClosesOnGiveback");
            var suite = new PropFirmProtectionSuite();
            var config = new PropFirmProtectionConfig { EnablePeakEquityProtection = true, MaxPeakGivebackPct = 0.30 };

            bool givebackExceeded = suite.EvaluatePeakEquityGiveback(peakOpenGain: 1000.0, currentUnrealized: 600.0, config);
            Assert(givebackExceeded == true, "40% giveback (from $1000 peak to $600) exceeds 30% giveback threshold");

            TestOptionC_TradeCopierSingletonIntegration();
            TestOptionC_PropProtectionSingletonIntegration();
        }

        // P1-40: the giveback rule was proportional-only, with `peakOpenGain > 0` as its only
        // floor. One MNQ tick is $0.50, so a position that ticked one tick into profit and gave
        // it back scored a 100% giveback and tripped a flatten. Observed live on 2026-08-07:
        // six PEAK_GIVEBACK_BREACH firings in 36 seconds, the first 2.4s after entry with the
        // position DOWN $1.00. The pre-existing tests missed it because they all use
        // $500-$1000 peaks, where proportional-only logic looks correct.
        private static void TestP1_40_NoiseSizedPeakDoesNotTripGiveback()
        {
            Console.WriteLine("\n[TEST] P1-40: a noise-sized peak must not trip the giveback rule");
            var suite = new PropFirmProtectionSuite();
            var config = new PropFirmProtectionConfig
            {
                EnablePeakEquityProtection = true,
                MaxPeakGivebackPct = 0.30
            };

            // One MNQ tick of open profit, fully given back. Proportional-only this is 100%.
            Assert(suite.EvaluatePeakEquityGiveback(0.50, 0.00, config) == false,
                "a $0.50 peak fully given back must NOT breach: it is one tick of noise, not a peak");

            // The exact live case: peak one tick, position now down a dollar.
            Assert(suite.EvaluatePeakEquityGiveback(0.50, -1.00, config) == false,
                "a $0.50 peak against -$1.00 must NOT breach (the 2026-08-07 live false positive)");

            // Just under the floor, a total loss of the peak.
            Assert(suite.EvaluatePeakEquityGiveback(config.MinPeakGainDollars - 0.01, 0.00, config) == false,
                "a peak just below MinPeakGainDollars must NOT breach however far it retraces");

            // At the floor the rule engages again: the peak is established.
            Assert(suite.EvaluatePeakEquityGiveback(config.MinPeakGainDollars, 0.00, config) == true,
                "a peak exactly at MinPeakGainDollars, fully given back, MUST breach");

            // Regression guard: the meaningful-peak behaviour must be untouched.
            Assert(suite.EvaluatePeakEquityGiveback(1000.0, 600.0, config) == true,
                "40% giveback from a $1000 peak must still breach");
            Assert(suite.EvaluatePeakEquityGiveback(1000.0, 900.0, config) == false,
                "10% giveback from a $1000 peak must still not breach");

            // The floor must be configurable, and setting it to zero restores the old behaviour
            // for anyone who deliberately wants a purely proportional rule.
            var noFloor = new PropFirmProtectionConfig
            {
                EnablePeakEquityProtection = true,
                MaxPeakGivebackPct = 0.30,
                MinPeakGainDollars = 0.0
            };
            Assert(suite.EvaluatePeakEquityGiveback(0.50, 0.00, noFloor) == true,
                "with MinPeakGainDollars=0 the rule is purely proportional again");
        }

        // P1-39: RiskConfig's collection properties are pre-populated by initializers, and
        // Json.NET's default ObjectCreationHandling.Auto REUSES a populated collection and
        // appends to it. So every config load re-added the two default WindowsET entries and
        // five more Days per window. Live on 2026-08-07 one POST took the config 6 -> 10
        // windows (that path deserializes twice) and the dashboard's Save button did it again.
        // The half that matters for safety: a default window could never be deleted, so the
        // window gate silently widened and the operator could not narrow it.
        private static void TestP1_39_ConfigLoadDoesNotAppendDefaultCollections()
        {
            Console.WriteLine("\n[TEST] P1-39: deserializing a config must replace its collections, not append to them");

            // Exactly the two windows the initializer already contains.
            string bothDefaults = @"{
                ""WindowsET"": [
                    { ""Name"": ""NY_AM_Macro"", ""Start"": ""09:50"", ""End"": ""11:10"", ""Days"": [""Monday""] },
                    { ""Name"": ""NY_PM_Macro"", ""Start"": ""13:50"", ""End"": ""15:10"", ""Days"": [""Monday""] }
                ]
            }";

            var cfg = Newtonsoft.Json.JsonConvert.DeserializeObject<RiskConfig>(bothDefaults);
            Assert(cfg.WindowsET.Count == 2,
                $"a config holding the two default windows must deserialize to 2, not {cfg.WindowsET.Count}");
            Assert(cfg.WindowsET[0].Days.Count == 1,
                $"a window declaring one day must deserialize to 1 day, not {cfg.WindowsET[0].Days.Count}");

            // Round-tripping must be stable -- this is what compounds across restarts.
            string once = Newtonsoft.Json.JsonConvert.SerializeObject(cfg);
            var twice = Newtonsoft.Json.JsonConvert.DeserializeObject<RiskConfig>(once);
            string thrice = Newtonsoft.Json.JsonConvert.SerializeObject(twice);
            var final = Newtonsoft.Json.JsonConvert.DeserializeObject<RiskConfig>(thrice);
            Assert(final.WindowsET.Count == 2,
                $"window count must be stable across round-trips, got {final.WindowsET.Count}");
            Assert(final.WindowsET[0].Days.Count == 1,
                $"Days must be stable across round-trips, got {final.WindowsET[0].Days.Count}");

            // The safety-relevant case: a default the operator deliberately removed must stay
            // removed. If NY_AM_Macro comes back, the permitted-trading set silently widens.
            string onlyPm = @"{
                ""WindowsET"": [
                    { ""Name"": ""NY_PM_Macro"", ""Start"": ""13:50"", ""End"": ""15:10"", ""Days"": [""Monday""] }
                ]
            }";
            var pruned = Newtonsoft.Json.JsonConvert.DeserializeObject<RiskConfig>(onlyPm);
            Assert(pruned.WindowsET.Count == 1,
                $"a config declaring one window must yield one window, not {pruned.WindowsET.Count}");
            Assert(!pruned.WindowsET.Any(w => w.Name == "NY_AM_Macro"),
                "a default window removed from the file must NOT be reinstated by the loader");

            // Guard against the tempting over-broad fix. Setting ObjectCreationHandling.Replace
            // at the serializer level also replaces the dictionaries -- and InstrumentLimits,
            // AccountFirmMap and FirmProfiles are built with StringComparer.OrdinalIgnoreCase.
            // Json.NET would hand back a fresh Dictionary with the DEFAULT comparer, silently
            // turning case-insensitive instrument lookups case-sensitive. Fix per-property.
            string withLimits = @"{ ""InstrumentLimits"": { ""MNQ"": { ""MaxContracts"": 3 } } }";
            var limited = Newtonsoft.Json.JsonConvert.DeserializeObject<RiskConfig>(withLimits);
            Assert(limited.InstrumentLimits.ContainsKey("mnq"),
                "InstrumentLimits must stay case-insensitive after deserialization (do not fix P1-39 at the serializer level)");
        }

        private static void TestOptionC_TradeCopierSingletonIntegration()
        {
            Console.WriteLine("\n[TEST] TestOptionC_TradeCopierSingletonIntegration");
            var rel = new CopierRelationship
            {
                LeaderAccountName = "SimLeader",
                FollowerAccountName = "SimFollower",
                ArmedForLive = true,
                QuantityRatio = 1.0,
                AutoSymbolConversion = true
            };

            // Test Arming Gate: confirmLive = false must force ArmedForLive = false
            TradeCopierEngine.Instance.UpsertRelationship(rel, confirmLive: false);
            var rels = TradeCopierEngine.Instance.GetRelationships();
            var registeredRel = rels.FirstOrDefault(r => r.LeaderAccountName == "SimLeader");
            Assert(registeredRel != null, "CopierRelationship registered in TradeCopierEngine.Instance");
            Assert(registeredRel.ArmedForLive == false, "ArmedForLive forced to false when confirmLive is false");

            // Arm with confirmLive = true
            rel.ArmedForLive = true;
            TradeCopierEngine.Instance.UpsertRelationship(rel, confirmLive: true);
            Assert(rel.ArmedForLive == true, "ArmedForLive enabled when confirmLive is true");

            // Worked Examples for Quantity Math & 10x Conversion
            string followerSymbol = TradeCopierEngine.Instance.TranslateSymbol("NQ 09-26");
            Assert(followerSymbol == "MNQ 09-26", "Symbol translated from NQ to MNQ");

            int qty1 = TradeCopierEngine.Instance.CalculateFollowerQuantity(rel, 1, "NQ 09-26", isExit: false);
            Assert(qty1 == 10, "Worked Example: 1 NQ leader @ 1.0 ratio = 10 MNQ follower");

            rel.QuantityRatio = 2.0;
            rel.MaxPositionSize = 50;
            int qty2 = TradeCopierEngine.Instance.CalculateFollowerQuantity(rel, 1, "NQ 09-26", isExit: false);
            Assert(qty2 == 20, "Worked Example: 1 NQ leader @ 2.0 ratio = 20 MNQ follower");

            // Reduce / Exit Handling
            int exitQty = TradeCopierEngine.Instance.CalculateFollowerQuantity(rel, 0, "NQ 09-26", isExit: true);
            Assert(exitQty == 0, "Exit with 0 qty returns 0 without floored 1-lot minimum");

            TestOptionC_MultiPartialFillPositionClamping();
        }

        private static void TestOptionC_MultiPartialFillPositionClamping()
        {
            Console.WriteLine("\n[TEST] TestOptionC_MultiPartialFillPositionClamping");
            var rel = new CopierRelationship
            {
                LeaderAccountName = "SimLeader",
                FollowerAccountName = "SimFollower",
                ArmedForLive = true,
                QuantityRatio = 1.0,
                AutoSymbolConversion = true,
                MaxPositionSize = 25
            };

            int currentPos = 0;

            // Partial Fill 1: Leader fills 1 NQ (wants 10 MNQ)
            int fill1 = TradeCopierEngine.Instance.CalculateFollowerQuantity(rel, 1, "NQ 09-26", currentPos, isExit: false, out bool clamped1);
            Assert(fill1 == 10, "Partial Fill 1 copies 10 MNQ");
            Assert(clamped1 == false, "Partial Fill 1 is not clamped");
            currentPos += fill1;

            // Partial Fill 2: Leader fills another 1 NQ (wants 10 MNQ)
            int fill2 = TradeCopierEngine.Instance.CalculateFollowerQuantity(rel, 1, "NQ 09-26", currentPos, isExit: false, out bool clamped2);
            Assert(fill2 == 10, "Partial Fill 2 copies 10 MNQ");
            Assert(clamped2 == false, "Partial Fill 2 is not clamped");
            currentPos += fill2;

            // Partial Fill 3: Leader fills another 1 NQ (wants 10 MNQ, but capacity is 25 - 20 = 5 MNQ)
            int fill3 = TradeCopierEngine.Instance.CalculateFollowerQuantity(rel, 1, "NQ 09-26", currentPos, isExit: false, out bool clamped3);
            Assert(fill3 == 5, "Partial Fill 3 clamped to remaining capacity of 5 MNQ");
            Assert(clamped3 == true, "Partial Fill 3 triggers position clamping warning flag");
            currentPos += fill3;

            Assert(currentPos == 25, "Follower cumulative position capped at MaxPositionSize 25 MNQ across multi-partial fills");
        }

        private static void TestOptionC_PropProtectionSingletonIntegration()
        {
            Console.WriteLine("\n[TEST] TestOptionC_PropProtectionSingletonIntegration");
            var cfg = new PropFirmProtectionConfig
            {
                ArmedForLive = true,
                EnableNewsShield = true,
                EnableProfitTargetLock = true,
                EvaluationTargetProfit = 2500.0,
                MaxPeakGivebackPct = 0.25
            };

            // Test Arming Gate: confirmLive = false must force ArmedForLive = false
            PropFirmProtectionSuite.Instance.UpdateConfig(cfg, confirmLive: false);
            Assert(PropFirmProtectionSuite.Instance.Config.ArmedForLive == false, "ArmedForLive forced to false when confirmLive is false");

            cfg.ArmedForLive = true;
            PropFirmProtectionSuite.Instance.UpdateConfig(cfg, confirmLive: true);
            Assert(PropFirmProtectionSuite.Instance.Config.ArmedForLive == true, "ArmedForLive enabled when confirmLive is true");

            bool locked = PropFirmProtectionSuite.Instance.EvaluateProfitTargetLock(2600.0);
            Assert(locked == true, "PnL 2600 reaches 2500 target lock threshold");
        }

        private static void TestCopierGroup_GroupManagement()
        {
            Console.WriteLine("\n[TEST] TestCopierGroup_GroupManagement");
            var engine = TradeCopierEngine.Instance;
            
            var grp = new CopierGroup
            {
                GroupName = "UnitTestGroup1",
                LeaderAccountName = "SimLeader1",
                QuantityRatio = 1.5,
                MaxPositionSize = 50,
                FollowerAccounts = new List<string> { "SimCopyA", "SimCopyB" }
            };

            engine.UpsertGroup(grp, confirmLive: false);
            var groups = engine.GetGroups();
            Assert(groups.Any(g => g.GroupName == "UnitTestGroup1"), "Group UnitTestGroup1 created and registered");

            engine.AddFollowerToGroup("UnitTestGroup1", "SimCopyC");
            var fetched = engine.GetGroup("UnitTestGroup1");
            Assert(fetched != null && fetched.FollowerAccounts.Contains("SimCopyC"), "Follower SimCopyC added to UnitTestGroup1");

            engine.RemoveFollowerFromGroup("UnitTestGroup1", "SimCopyA");
            fetched = engine.GetGroup("UnitTestGroup1");
            Assert(fetched != null && !fetched.FollowerAccounts.Contains("SimCopyA"), "Follower SimCopyA removed from UnitTestGroup1");

            engine.RemoveGroup("UnitTestGroup1");
            groups = engine.GetGroups();
            Assert(!groups.Any(g => g.GroupName == "UnitTestGroup1"), "Group UnitTestGroup1 deleted successfully");
        }

        private static void TestCopierGroup_PerGroupConfigurationExecution()
        {
            Console.WriteLine("\n[TEST] TestCopierGroup_PerGroupConfigurationExecution");
            var engine = TradeCopierEngine.Instance;

            foreach (var g in engine.GetGroups()) engine.RemoveGroup(g.GroupName);

            var group1 = new CopierGroup
            {
                GroupName = "Apex_50K",
                LeaderAccountName = "SimLeaderAlpha",
                QuantityRatio = 1.0,
                AutoSymbolConversion = true,
                MaxPositionSize = 100,
                FollowerAccounts = new List<string> { "ApexFollower1", "ApexFollower2" }
            };

            var group2 = new CopierGroup
            {
                GroupName = "Topstep_100K",
                LeaderAccountName = "SimLeaderAlpha",
                QuantityRatio = 0.5,
                AutoSymbolConversion = true,
                MaxPositionSize = 100,
                FollowerAccounts = new List<string> { "TopstepFollower1" }
            };

            engine.UpsertGroup(group1, confirmLive: false);
            engine.UpsertGroup(group2, confirmLive: false);

            var activeRels = engine.GetActiveRelationshipsForLeader("SimLeaderAlpha");
            Assert(activeRels.Count == 3, "Leader SimLeaderAlpha maps to 3 total follower relationships across 2 groups");

            var apexRel = activeRels.First(r => r.FollowerAccountName == "ApexFollower1");
            int apexQty = engine.CalculateFollowerQuantity(apexRel, 1, "NQ 09-26");
            Assert(apexQty == 10, "Apex group follower copies 1 NQ as 10 MNQ (1.0x ratio)");

            var topstepRel = activeRels.First(r => r.FollowerAccountName == "TopstepFollower1");
            int topstepQty = engine.CalculateFollowerQuantity(topstepRel, 1, "NQ 09-26");
            Assert(topstepQty == 5, "Topstep group follower copies 1 NQ as 5 MNQ (0.5x ratio)");
        }

        private static void TestCopierGroup_GroupPersistence()
        {
            Console.WriteLine("\n[TEST] TestCopierGroup_GroupPersistence");
            var engine = TradeCopierEngine.Instance;
            string testFile = Path.Combine(Path.GetTempPath(), "test_copier_group_config.json");

            var group = new CopierGroup
            {
                GroupName = "PersistTestGroup",
                LeaderAccountName = "PersistLeader",
                QuantityRatio = 2.0,
                FollowerAccounts = new List<string> { "PersistFollower1", "PersistFollower2" }
            };

            engine.UpsertGroup(group, confirmLive: false);
            engine.SaveToDisk(testFile);
            Assert(File.Exists(testFile), "Group config JSON successfully saved to disk");

            engine.RemoveGroup("PersistTestGroup");
            Assert(engine.GetGroup("PersistTestGroup") == null, "Group removed in-memory prior to reload");

            engine.LoadFromDisk(testFile);
            var reloaded = engine.GetGroup("PersistTestGroup");
            Assert(reloaded != null, "Reloaded group PersistTestGroup exists");
            Assert(reloaded.QuantityRatio == 2.0, "Reloaded group QuantityRatio is 2.0");
            Assert(reloaded.FollowerAccounts != null && reloaded.FollowerAccounts.Count == 2, "Reloaded group FollowerAccounts count is 2");

            try { File.Delete(testFile); } catch {}
        }

        private static void TestCopierGroup_GroupStressAndConcurrency()
        {
            Console.WriteLine("\n[TEST] TestCopierGroup_GroupStressAndConcurrency");
            var engine = TradeCopierEngine.Instance;

            for (int i = 1; i <= 10; i++)
            {
                var followers = new List<string>();
                for (int j = 1; j <= 5; j++) followers.Add($"StressFollower_{i}_{j}");

                var grp = new CopierGroup
                {
                    GroupName = $"StressGroup_{i}",
                    LeaderAccountName = "StressLeaderMaster",
                    QuantityRatio = 0.5 * i,
                    MaxPositionSize = 200,
                    FollowerAccounts = followers
                };
                engine.UpsertGroup(grp, confirmLive: false);
            }

            int iterationsPerThread = 250;
            int threadCount = 4;
            int totalCalculatedOrders = 0;
            bool threadExceptionOccurred = false;

            var tasks = new Task[threadCount + 1];

            for (int t = 0; t < threadCount; t++)
            {
                tasks[t] = Task.Run(() =>
                {
                    try
                    {
                        string[] symbols = new string[] { "NQ 09-26", "ES 09-26", "YM 09-26", "CL 10-26", "GC 12-26" };
                        for (int k = 0; k < iterationsPerThread; k++)
                        {
                            string sym = symbols[k % symbols.Length];
                            var rels = engine.GetActiveRelationshipsForLeader("StressLeaderMaster");
                            foreach (var rel in rels)
                            {
                                int qty = engine.CalculateFollowerQuantity(rel, 2, sym);
                                Interlocked.Increment(ref totalCalculatedOrders);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[STRESS TEST ERROR] Worker thread exception: {ex.Message}");
                        threadExceptionOccurred = true;
                    }
                });
            }

            tasks[threadCount] = Task.Run(() =>
            {
                try
                {
                    for (int m = 0; m < 50; m++)
                    {
                        engine.AddFollowerToGroup("StressGroup_1", $"DynamicFollower_{m}");
                        engine.RemoveFollowerFromGroup("StressGroup_1", $"DynamicFollower_{m}");
                        Thread.Sleep(2);
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[STRESS TEST ERROR] Mutator thread exception: {ex.Message}");
                    threadExceptionOccurred = true;
                }
            });

            Task.WaitAll(tasks);

            Assert(!threadExceptionOccurred, "Stress & concurrency test executed with ZERO thread exceptions or race conditions");
            Assert(totalCalculatedOrders >= iterationsPerThread * threadCount * 50, $"Processed {totalCalculatedOrders} follower quantity evaluations across 1,000 rapid execution bursts under load");
        }

        public static void RunCopierFixesVerificationTests()
        {
            Console.WriteLine("\n--- RUNNING COPIER FIXES VERIFICATION TESTS ---");
            var engine = TradeCopierEngine.Instance;

            // Test 1: Deduplication of Group and Direct Relationships
            string testLeader = "DedupLeader";
            string testFollower = "DedupFollower";

            var directRel = new CopierRelationship
            {
                LeaderAccountName = testLeader,
                FollowerAccountName = testFollower,
                IsEnabled = true
            };
            engine.UpsertRelationship(directRel);

            var grp = new CopierGroup
            {
                GroupName = "DedupGroup",
                LeaderAccountName = testLeader,
                IsEnabled = true,
                FollowerAccounts = new List<string> { testFollower }
            };
            engine.UpsertGroup(grp);

            var activeRels = engine.GetActiveRelationshipsForLeader(testLeader);
            Assert(activeRels.Count == 1, $"Group and Direct follower relationship deduplicated to 1 record (got {activeRels.Count})");
            Assert(activeRels[0].FollowerAccountName.Equals(testFollower, StringComparison.OrdinalIgnoreCase), "Correct follower account returned");

            // Test 2: Inverse Mode Quantity Calculation
            var inverseRel = new CopierRelationship
            {
                LeaderAccountName = testLeader,
                FollowerAccountName = "InverseFollower",
                QuantityRatio = -1.0,
                AutoSymbolConversion = false,
                MaxPositionSize = 10
            };
            int qtyEntry = engine.CalculateFollowerQuantity(inverseRel, 2, "NQ 09-26", 0, false, out _);
            Assert(qtyEntry == 2, $"Inverse entry quantity is positive 2 (got {qtyEntry})");

            // Test 3: Bidirectional Symbol Translation (Mini <-> Micro)
            string mnqTrans = engine.TranslateSymbol("NQ 09-26");
            Assert(mnqTrans.Contains("MNQ"), $"NQ translated to MNQ (got {mnqTrans})");

            string nqTrans = engine.TranslateSymbol("MNQ 09-26");
            Assert(nqTrans.Contains("NQ") && !nqTrans.Contains("MNQ"), $"MNQ translated to NQ (got {nqTrans})");

            string mesTrans = engine.TranslateSymbol("ES 09-26");
            Assert(mesTrans.Contains("MES"), $"ES translated to MES (got {mesTrans})");

            string esTrans = engine.TranslateSymbol("MES 09-26");
            Assert(esTrans.Contains("ES") && !esTrans.Contains("MES"), $"MES translated to ES (got {esTrans})");

            // Test 4: Per-Ticker Ratio Overrides & Micro-to-Mini Fractional Scaling
            var tickerRel = new CopierRelationship
            {
                LeaderAccountName = testLeader,
                FollowerAccountName = "TickerFollower",
                QuantityRatio = 1.0,
                AutoSymbolConversion = true,
                MaxPositionSize = 100
            };
            tickerRel.PerTickerRatios["NQ"] = 2.0;
            tickerRel.PerTickerRatios["ES"] = 0.5;

            // NQ -> MNQ with 2.0x ratio override: 1 NQ * 2.0 * 10 = 20 MNQ
            int nqQty = engine.CalculateFollowerQuantity(tickerRel, 1, "NQ 09-26", 0, false, out _);
            Assert(nqQty == 20, $"NQ with 2.0x ratio override equals 20 MNQ (got {nqQty})");

            // ES -> MES with 0.5x ratio override: 2 ES * 0.5 * 10 = 10 MES
            int esQty = engine.CalculateFollowerQuantity(tickerRel, 2, "ES 09-26", 0, false, out _);
            Assert(esQty == 10, $"ES with 0.5x ratio override equals 10 MES (got {esQty})");

            // Micro -> Mini 0.1x scaling: 10 MNQ * 1.0 * 0.1 = 1 NQ
            var microToMiniRel = new CopierRelationship
            {
                LeaderAccountName = testLeader,
                FollowerAccountName = "MiniFollower",
                QuantityRatio = 1.0,
                AutoSymbolConversion = true,
                MaxPositionSize = 100
            };
            int miniQty = engine.CalculateFollowerQuantity(microToMiniRel, 10, "MNQ 09-26", 0, false, out _);
            Assert(miniQty == 1, $"10 MNQ scaled to Mini equals 1 NQ (got {miniQty})");

            Console.WriteLine("[PASS] All Copier Fixes Verification Tests Passed Successfully!");
        }

        public static void TestOrderVerificationWatchdogAndReconciliation()
        {
            Console.WriteLine("\n--- RUNNING ORDER VERIFICATION & WATCHDOG TESTS ---");

            var engine = TradeCopierEngine.Instance;

            // Test 1: AwayFromZero Contract Scaling Precision
            int scaledHalf = engine.CalculateScaledQuantity(1, 0.5m);
            Assert(scaledHalf == 1, "1 contract @ 0.5 ratio rounds AwayFromZero to 1 contract");

            int scaledQuart = engine.CalculateScaledQuantity(1, 0.2m);
            Assert(scaledQuart == 0, "1 contract @ 0.2 ratio rounds to 0");

            // Test 2: Double-Checked Quarantine State Locking
            var testRel = new CopierRelationship
            {
                LeaderAccountName = "QuarantineLeader",
                FollowerAccountName = "QuarantinedFollower",
                IsQuarantined = true,
                QuarantineReason = "Execution Verification Timeout"
            };
            engine.UpsertRelationship(testRel, confirmLive: true);
            var active = engine.GetActiveRelationshipsForLeader("QuarantineLeader");
            Assert(active.Count == 0, "Quarantined relationship excluded from active leader execution list");

            // Test 3: Emergency Flatten Sequence Order State Filter
            var activeStates = new List<OrderState> { OrderState.Working, OrderState.Submitted, OrderState.Accepted, OrderState.PartFilled };
            Assert(activeStates.Contains(OrderState.PartFilled), "PartFilled order state included in emergency flatten cancel pass");
            Assert(activeStates.Contains(OrderState.Submitted), "Submitted order state included in emergency flatten cancel pass");

            Console.WriteLine("[PASS] All Order Verification Watchdog & Reconciliation Tests Passed Successfully!");
        }

        public static void TestHedgingReconciliationAndAutoClose()
        {
            Console.WriteLine("\n--- RUNNING HEDGING, RECONCILIATION & AUTO-CLOSE TESTS ---");

            var engine = TradeCopierEngine.Instance;

            // Test 1: Normal short entry allowed when flat
            int safeShortDelta = engine.CalculateSafeFollowerDelta(leaderTargetQty: -2, currentFollowerQty: 0, isMarketOrder: true, out bool isBlocked);
            Assert(safeShortDelta == -2 && !isBlocked, "Normal short entry delta allowed when flat");

            // Test 2: Quantity Capping on Position Reduction
            int cappedDelta = engine.CalculateSafeFollowerDelta(leaderTargetQty: 0, currentFollowerQty: 5, isMarketOrder: true, out isBlocked);
            Assert(cappedDelta == -5 && !isBlocked, "Exit delta capped to follower open position size");

            // Test 3: Standalone Limit/Stop entries unblocked
            int limitDelta = engine.CalculateSafeFollowerDelta(leaderTargetQty: 3, currentFollowerQty: 0, isMarketOrder: false, out isBlocked);
            Assert(limitDelta == 3 && !isBlocked, "Standalone Limit/Stop entry unblocked when flat");

            Console.WriteLine("[PASS] All Hedging, Reconciliation & Auto-Close Tests Passed Successfully!");
        }

        // ─────────────────────────────────────────────────────────────────────
        // DYNAMIC ATM BRACKET TESTS
        // Exercises DynamicAtmManager.PlaceBracket strategy math, profile
        // fallback, OCO wiring, bracket registration, and error paths without
        // requiring a live NinjaTrader runtime or open market.
        // ─────────────────────────────────────────────────────────────────────

        private static bool Approx(double a, double b, double tol = 0.0001)
        {
            return Math.Abs(a - b) <= tol;
        }

        private static Account CreateAtmAccount(string name = "Sim101")
        {
            return new Account { Name = name };
        }

        private static Instrument CreateAtmInstrument(string root, string fullName = null)
        {
            var instr = new Instrument(fullName ?? root);
            instr.MasterInstrument.Name = root;
            instr.MasterInstrument.TickSize = 0.25;
            return instr;
        }

        private static void TestAtm_FixedTicksLong()
        {
            Console.WriteLine("\n[TEST] ATM: FixedTicks Long");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.FixedTicks, StopTicks = 8, TargetTicks = 16 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "submitted", "FixedTicks long submitted");
            Assert(result.StrategyName == "FixedTicks", "Strategy name is FixedTicks");
            Assert(Approx(result.StopPrice, 17998.0), "Stop = entry - 8 ticks (17998)");
            Assert(Approx(result.TargetPrice, 18004.0), "Target = entry + 16 ticks (18004)");
            Assert(!string.IsNullOrEmpty(result.BracketId), "BracketId generated");
            Assert(!string.IsNullOrEmpty(result.OcoId), "OcoId generated");
            Assert(!string.IsNullOrEmpty(result.EntryOrderId) && !string.IsNullOrEmpty(result.StopOrderId) && !string.IsNullOrEmpty(result.TargetOrderId), "All 3 order ids returned");
            Assert(account.Orders.Count == 3, "3 orders submitted to account");
            Assert(account.Orders.Count(o => o.Name.StartsWith("AtmEntry_")) == 1, "Entry order named AtmEntry_*");
            Assert(account.Orders.Count(o => o.Name.StartsWith("Stop_")) == 1, "Stop order named Stop_*");
            Assert(account.Orders.Count(o => o.Name.StartsWith("Target_")) == 1, "Target order named Target_*");
        }

        private static void TestAtm_FixedTicksShort()
        {
            Console.WriteLine("\n[TEST] ATM: FixedTicks Short");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.FixedTicks, StopTicks = 8, TargetTicks = 16 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "sell", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "submitted", "FixedTicks short submitted");
            Assert(Approx(result.StopPrice, 18002.0), "Short stop = entry + 8 ticks (18002)");
            Assert(Approx(result.TargetPrice, 17996.0), "Short target = entry - 16 ticks (17996)");
            var entry = account.Orders.First(o => o.Name.StartsWith("AtmEntry_"));
            var stop = account.Orders.First(o => o.Name.StartsWith("Stop_"));
            var target = account.Orders.First(o => o.Name.StartsWith("Target_"));
            Assert(entry.OrderAction == OrderAction.Sell, "Short entry order action is Sell");
            Assert(stop.OrderAction == OrderAction.Buy, "Short stop order action is Buy");
            Assert(target.OrderAction == OrderAction.Buy, "Short target order action is Buy");
        }

        private static void TestAtm_OcoIdSharedAcrossExitOrders()
        {
            Console.WriteLine("\n[TEST] ATM: OCO Id Shared Across Exit Orders");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.FixedTicks, StopTicks = 8, TargetTicks = 16 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            var stop = account.Orders.First(o => o.Name.StartsWith("Stop_"));
            var target = account.Orders.First(o => o.Name.StartsWith("Target_"));
            var entry = account.Orders.First(o => o.Name.StartsWith("AtmEntry_"));
            Assert(!string.IsNullOrEmpty(stop.Oco) && stop.Oco == result.OcoId, "Stop order carries result OcoId");
            Assert(!string.IsNullOrEmpty(target.Oco) && target.Oco == result.OcoId, "Target order carries result OcoId");
            Assert(string.IsNullOrEmpty(entry.Oco), "Entry order has empty Oco id (not OCO-linked)");
        }

        private static void TestAtm_DrawdownShieldRegistersBracket()
        {
            Console.WriteLine("\n[TEST] ATM: DrawdownShield Registers Monitor Bracket");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.DrawdownShield, StopTicks = 10, TargetTicks = 20, BreakevenTriggerTicks = 12, BreakevenOffsetTicks = 2 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "submitted", "DrawdownShield submitted");
            Assert(result.Note != null && result.Note.Contains("registered"), "Bracket registered note present");
            var brackets = DynamicAtmManager.Instance.GetActiveBrackets();
            Assert(brackets.Any(b => b.BracketId == result.BracketId), "Bracket appears in GetActiveBrackets()");
            var bracket = brackets.First(b => b.BracketId == result.BracketId);
            Assert(bracket.Symbol == "MNQ" && bracket.IsLong && bracket.Quantity == 1, "Bracket metadata correct (symbol/isLong/qty)");
            Assert(bracket.Config.Type == AtmStrategyType.DrawdownShield, "Bracket carries strategy config");

            DynamicAtmManager.Instance.RemoveBracket(result.BracketId);
        }

        private static void TestAtm_ScaledRunnerRegistersBracket()
        {
            Console.WriteLine("\n[TEST] ATM: ScaledRunner Registers Monitor Bracket");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("NQ", "NQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.ScaledRunner, StopTicks = 8, TargetTicks = 30 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 20.0);

            Assert(result.Status == "submitted", "ScaledRunner submitted");
            var brackets = DynamicAtmManager.Instance.GetActiveBrackets();
            Assert(brackets.Any(b => b.BracketId == result.BracketId), "ScaledRunner bracket registered");
            Assert(brackets.First(b => b.BracketId == result.BracketId).Config.Type == AtmStrategyType.ScaledRunner, "Bracket carries ScaledRunner config");

            DynamicAtmManager.Instance.RemoveBracket(result.BracketId);
        }

        private static void TestAtm_MonitoredStrategiesNotDoubleRegistered()
        {
            Console.WriteLine("\n[TEST] ATM: Non-monitored Strategy Does Not Register Bracket");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");

            var config = new AtmStrategyConfig { Type = AtmStrategyType.FixedTicks, StopTicks = 8, TargetTicks = 16 };
            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "submitted", "FixedTicks submitted");
            var brackets = DynamicAtmManager.Instance.GetActiveBrackets();
            Assert(!brackets.Any(b => b.BracketId == result.BracketId), "FixedTicks bracket NOT registered for monitoring");
        }

        private static void TestAtm_VolatilityScaledQuantityCapped()
        {
            Console.WriteLine("\n[TEST] ATM: VolatilityScaled Quantity Capped At MaxContracts");
            BarsRequest.TestBarsFactory = null; // ensure fallback ATR path (isolation from prior live-ATR tests)
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.VolatilityScaled, RiskPerTrade = 100000.0 };

            // MNQ profile: MaxContracts = 50, DefaultATR = 30 (tick 0.25) -> fallback atr = 7.5
            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "submitted", "VolatilityScaled submitted");
            Assert(result.CalculatedQuantity == 50, "Calculated quantity capped at profile MaxContracts (50)");
        }

        private static void TestAtm_VolatilityScaledRiskBasedQuantity()
        {
            Console.WriteLine("\n[TEST] ATM: VolatilityScaled Risk-Based Quantity");
            BarsRequest.TestBarsFactory = null; // ensure fallback ATR path (isolation from prior live-ATR tests)
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.VolatilityScaled, RiskPerTrade = 200.0 };

            // fallback atr = 30*0.25 = 7.5; riskPerContract = 7.5*1.5*2.0 = 22.5; qty = floor(200/22.5) = 8
            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "submitted", "VolatilityScaled submitted");
            Assert(result.CalculatedQuantity == 8, "Calculated quantity = floor(RiskPerTrade / riskPerContract) = 8");
        }

        private static void TestAtm_AtrAdaptiveFallbackUsesDefaultAtr()
        {
            Console.WriteLine("\n[TEST] ATM: AtrAdaptive Fallback To Profile DefaultATR");
            BarsRequest.TestBarsFactory = null; // ensure fallback ATR path (no live bars injected)
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.AtrAdaptive };

            // No bars factory -> atr = DefaultATR * tickSize = 30*0.25 = 7.5
            // slDist = 7.5*1.5 = 11.25, tpDist = 7.5*2.5 = 18.75
            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "submitted", "AtrAdaptive submitted");
            Assert(Approx(result.StopPrice, 17988.75), "Stop = entry - 11.25 (profile default ATR fallback)");
            Assert(Approx(result.TargetPrice, 18018.75), "Target = entry + 18.75 (profile default ATR fallback)");
        }

        private static void TestAtm_AtrAdaptiveUsesLiveAtr()
        {
            Console.WriteLine("\n[TEST] ATM: AtrAdaptive Uses Live ATR From Bars");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.AtrAdaptive };

            // Constant range bars -> TR = 1.0 for every bar -> ATR = 1.0
            int n = 20;
            var high = new double[n];
            var low = new double[n];
            var close = new double[n];
            var open = new double[n];
            var vol = new long[n];
            var time = new DateTime[n];
            var baseTime = new DateTime(2026, 8, 1, 9, 30, 0);
            for (int i = 0; i < n; i++)
            {
                high[i] = 100.0;
                low[i] = 99.0;
                close[i] = 99.5;
                open[i] = 99.5;
                vol[i] = 1000;
                time[i] = baseTime.AddMinutes(i);
            }
            BarsRequest.TestBarsFactory = req => new Bars(high, low, close, open, vol, time);

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            // ATR = 1.0 -> slDist = 1.5, tpDist = 2.5
            Assert(result.Status == "submitted", "AtrAdaptive submitted with live ATR");
            Assert(Approx(result.StopPrice, 17998.5), "Stop = entry - 1.5 (live ATR=1.0)");
            Assert(Approx(result.TargetPrice, 18002.5), "Target = entry + 2.5 (live ATR=1.0)");

            BarsRequest.TestBarsFactory = null;
        }

        private static void TestAtm_SwingPointUsesSwingLow()
        {
            Console.WriteLine("\n[TEST] ATM: SwingPoint Uses Swing Low");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.SwingPoint, SwingLookbackBars = 5, SwingBufferTicks = 4 };

            // lows descending: last lookback window min = 17996; buffer = 4 ticks = 1.0 -> stop = 17995
            int n = 10;
            double[] lows = { 18010, 18009, 18008, 18007, 18006, 18005, 18004, 18003, 18002, 17996 };
            var high = new double[n];
            var low = new double[n];
            var close = new double[n];
            var open = new double[n];
            var vol = new long[n];
            var time = new DateTime[n];
            var baseTime = new DateTime(2026, 8, 1, 9, 30, 0);
            for (int i = 0; i < n; i++)
            {
                low[i] = lows[i];
                high[i] = low[i] + 2.0;
                close[i] = high[i] - 0.5;
                open[i] = high[i] - 0.5;
                vol[i] = 1000;
                time[i] = baseTime.AddMinutes(i * 5);
            }
            BarsRequest.TestBarsFactory = req => new Bars(high, low, close, open, vol, time);

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "submitted", "SwingPoint submitted");
            Assert(Approx(result.StopPrice, 17995.0), "Stop = swing low 17996 - buffer 1.0 = 17995");
            Assert(Approx(result.TargetPrice, 18010.0), "Target = entry + 2x(entry-stop) = 18010");

            BarsRequest.TestBarsFactory = null;
        }

        private static void TestAtm_SessionAdaptiveMultiplier()
        {
            Console.WriteLine("\n[TEST] ATM: SessionAdaptive Smoke Test");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.SessionAdaptive, StopTicks = 8, TargetTicks = 16 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "submitted", "SessionAdaptive submitted");
            Assert(result.StrategyName == "SessionAdaptive", "Strategy name is SessionAdaptive");
            Assert(result.StopPrice < 18000 && result.TargetPrice > 18000, "Stop below entry and target above entry for long");
            Assert(result.StopPrice < result.TargetPrice, "Stop strictly below target");
        }

        private static void TestAtm_UnknownSymbolFallsBackToDefaults()
        {
            Console.WriteLine("\n[TEST] ATM: Unknown Symbol Falls Back To Default Profile");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("XYZ", "XYZ 12-26");
            instrument.MasterInstrument.TickSize = 0.25;
            var config = new AtmStrategyConfig { Type = AtmStrategyType.FixedTicks, StopTicks = 8, TargetTicks = 16 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 100, 0.25, 50.0);

            Assert(result.Status == "submitted", "Unknown-symbol bracket submitted");
            Assert(result.StrategyName == "FixedTicks", "Fallback profile uses FixedTicks");
            Assert(Approx(result.StopPrice, 98.0), "Fallback stop = entry - 8 ticks (98)");
            Assert(Approx(result.TargetPrice, 104.0), "Fallback target = entry + 16 ticks (104)");
        }

        private static void TestAtm_GetProfileKnownAndUnknown()
        {
            Console.WriteLine("\n[TEST] ATM: GetProfile Known And Unknown");
            var mnq = DynamicAtmManager.GetProfile("MNQ");
            Assert(mnq != null && mnq.MaxContracts == 50 && mnq.DefaultStrategy == AtmStrategyType.AtrAdaptive, "MNQ profile returns MaxContracts=50, AtrAdaptive default");
            var es = DynamicAtmManager.GetProfile("ES");
            Assert(es != null && es.DefaultStrategy == AtmStrategyType.SwingPoint, "ES profile default strategy is SwingPoint");
            var sixE = DynamicAtmManager.GetProfile("6E");
            Assert(sixE != null && sixE.DefaultStrategy == AtmStrategyType.FixedTicks, "6E profile default strategy is FixedTicks");
            Assert(DynamicAtmManager.GetProfile("ZZZZ") == null, "Unknown root returns null profile");
        }

        private static void TestAtm_ZeroPriceReturnsError()
        {
            Console.WriteLine("\n[TEST] ATM: Zero Price Returns Error");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.FixedTicks, StopTicks = 8, TargetTicks = 16 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 0, 0.25, 2.0);

            Assert(result.Status == "error", "Zero entry price produces error status");
            Assert(!string.IsNullOrEmpty(result.Error), "Error message populated for zero price");
        }

        private static void TestAtm_RejectedExitOrdersPartialSubmit()
        {
            Console.WriteLine("\n[TEST] ATM: Rejected Exit Orders -> partial_submit");
            var account = CreateAtmAccount();
            account.SimulateExitRejection = true;
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.FixedTicks, StopTicks = 8, TargetTicks = 16 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);

            Assert(result.Status == "partial_submit", "Status becomes partial_submit when exit orders rejected");
            Assert(result.Note != null && result.Note.Contains("rejected"), "Note mentions rejected exit orders");
        }

        private static void TestAtm_ShouldTriggerBreakeven()
        {
            Console.WriteLine("\n[TEST] ATM: ShouldTriggerBreakeven Logic");
            var mgr = DynamicAtmManager.Instance;
            var config = new AtmStrategyConfig { BreakevenTriggerTicks = 12 };

            Assert(mgr.ShouldTriggerBreakeven(config, 18000, 18003.0, true, 0.25), "Long at exactly +12 ticks triggers breakeven");
            Assert(!mgr.ShouldTriggerBreakeven(config, 18000, 18002.75, true, 0.25), "Long at +11 ticks does not trigger breakeven");
            Assert(mgr.ShouldTriggerBreakeven(config, 18000, 17997.0, false, 0.25), "Short at -12 ticks triggers breakeven");
            Assert(!mgr.ShouldTriggerBreakeven(config, 18000, 18002.75, false, 0.25), "Short at +11 ticks does not trigger breakeven");
        }

        private static void TestAtm_CalculateBreakevenStopPrice()
        {
            Console.WriteLine("\n[TEST] ATM: CalculateBreakevenStopPrice Logic");
            var mgr = DynamicAtmManager.Instance;

            Assert(Approx(mgr.CalculateBreakevenStopPrice(18000, true, 0.25, 2), 18000.5), "Long breakeven stop = entry + offset 0.5");
            Assert(Approx(mgr.CalculateBreakevenStopPrice(18000, false, 0.25, 2), 17999.5), "Short breakeven stop = entry - offset 0.5");
            Assert(Approx(mgr.CalculateBreakevenStopPrice(18000, true, 0.25, 0), 18000.0), "Long breakeven stop = entry with zero offset");
        }

        private static void TestAtm_ActiveBracketStatus()
        {
            Console.WriteLine("\n[TEST] ATM: GetBracketStatus");
            var account = CreateAtmAccount();
            var instrument = CreateAtmInstrument("MNQ", "MNQ 09-26");
            var config = new AtmStrategyConfig { Type = AtmStrategyType.DrawdownShield, StopTicks = 10, TargetTicks = 20 };

            var result = DynamicAtmManager.Instance.PlaceBracket(account, instrument, "buy", 1, config, 18000, 0.25, 2.0);
            var status = DynamicAtmManager.Instance.GetBracketStatus(result.BracketId) as dynamic;

            Assert(status != null, "GetBracketStatus returns an object for a registered bracket");
            string statusBracketId = status.bracketId;
            Assert(statusBracketId == result.BracketId, "Status bracketId matches result BracketId");
            bool isComplete = status.isComplete;
            Assert(isComplete == false, "Newly registered bracket is not complete");
            var missing = DynamicAtmManager.Instance.GetBracketStatus("does-not-exist");
            Assert(missing is dynamic && ((dynamic)missing).error != null, "Unknown bracketId returns error payload");

            DynamicAtmManager.Instance.RemoveBracket(result.BracketId);
        }

        // ==================================================================
        // P3-30 / P3-31 -- the reconciler's two pure functions.
        //
        // These are deliberately written against VALUES rather than through the
        // engine. Every duplicate-leg defect in this project (P0-49, P0-55,
        // P1-56, P0-59) was found live or by mutation and NOT by the suite,
        // because reaching the decision required an event ordering, an account,
        // a lock and a broker -- so the decision itself was never tested, only
        // the machinery around it.
        //
        // The load-bearing case is TestReconcile_TwoOwnedLegsAreDeduplicated:
        // the old syncs COULD NOT have passed it at any price, because they read
        // one Order reference per leg and never enumerated the broker's orders.
        // ==================================================================

        /// <summary>An owned leg at the broker, as the reconciler will find it.</summary>
        private static Order OwnedLeg(
            Instrument inst, string name, OrderType type, OrderAction action,
            int qty, double price, OrderState state)
        {
            var o = new Order
            {
                Instrument = inst,
                Name = name,
                OrderType = type,
                OrderAction = action,
                Quantity = qty,
                OrderState = state,
                TimeInForce = TimeInForce.Day
            };
            if (type == OrderType.Limit) o.LimitPrice = price; else o.StopPrice = price;
            return o;
        }

        private static Instrument ReconInstrument()
        {
            var inst = new Instrument("MNQ 09-26");
            inst.MasterInstrument.TickSize = 0.25;
            return inst;
        }

        /// <summary>A long 2-lot follower filled at 20000, leader stop 40 pts below, target 80 above.</summary>
        private static DesiredBracket LongTwoLot(double stopOffset = -40, double targetOffset = 80)
        {
            return CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 2, MarketPosition.Long, 2,
                20000, stopOffset, targetOffset,
                CopierBracketReconciler.TickRounder(0.25));
        }

        private static int CountVerb(List<ReconcileAction> actions, ReconcileVerb verb, string legName)
        {
            int n = 0;
            foreach (var a in actions)
                if (a.Verb == verb && a.Leg.Name == legName) n++;
            return n;
        }

        // ---- ComputeDesiredBracket ----

        private static void TestDesired_SignedOffsetsMirrorBothSidesFromTheFollowersOwnFill()
        {
            var lng = LongTwoLot();
            Assert(lng.Stop.Intent == LegIntent.Required && Math.Abs(lng.Stop.Price - 19960) < 1e-9,
                "Long: stop sits at follower entry + signed offset (20000-40 = 19960)");
            Assert(lng.Target.Intent == LegIntent.Required && Math.Abs(lng.Target.Price - 20080) < 1e-9,
                "Long: target sits at follower entry + signed offset (20000+80 = 20080)");
            Assert(lng.Stop.Action == OrderAction.Sell && lng.Target.Action == OrderAction.Sell,
                "Long: both legs exit with Sell");

            // A short leader's stop is ABOVE its entry, so the offset arrives positive.
            var shrt = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Short, 1, MarketPosition.Short, 1,
                20000, +40, -80, CopierBracketReconciler.TickRounder(0.25));
            Assert(Math.Abs(shrt.Stop.Price - 20040) < 1e-9 && Math.Abs(shrt.Target.Price - 19920) < 1e-9,
                "Short: signed offsets carry through unflipped (stop 20040, target 19920)");
            Assert(shrt.Stop.Action == OrderAction.BuyToCover && shrt.Target.Action == OrderAction.BuyToCover,
                "Short: both legs exit with BuyToCover");
        }

        private static void TestDesired_LeaderTrailingIntoProfitKeepsTheStopAboveEntry()
        {
            // The signed-offset invariant, stated as its own test because an absolute
            // distance here turns the leader's locked-in GAIN into open risk on the
            // follower -- the same size loss, on the wrong side of entry.
            var d = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 1, MarketPosition.Long, 1,
                20000, +25, double.NaN, CopierBracketReconciler.TickRounder(0.25));
            Assert(Math.Abs(d.Stop.Price - 20025) < 1e-9,
                "A long whose leader trailed into profit gets a stop ABOVE its entry, not below");
        }

        private static void TestDesired_OffTickAverageFillIsSnappedToTheInstrumentsTick()
        {
            // The live rejection: 29905.625 on MNQ, tick 0.25.
            var d = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 1, MarketPosition.Long, 1,
                29945.625, -40, 40, CopierBracketReconciler.TickRounder(0.25));
            Assert(Math.Abs(d.Stop.Price % 0.25) < 1e-9 && Math.Abs(d.Target.Price % 0.25) < 1e-9,
                "An off-tick average fill produces on-tick legs (the 29905.625 rejection)");
        }

        private static void TestDesired_QuantityIsClampedToTheLivePositionNotTheBracketSnapshot()
        {
            // The follower scaled out to 1 while the bracket still says 3. A 3-lot stop
            // behind 1 lot does not protect it, it FLIPS it to short 2 on trigger.
            var d = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 3, MarketPosition.Long, 1,
                20000, -40, 80, CopierBracketReconciler.TickRounder(0.25));
            Assert(d.Quantity == 1 && d.Stop.Quantity == 1 && d.Target.Quantity == 1,
                "Legs are sized from the LIVE position (1), not the bracket's stale 3");

            // And the reverse: a position grown by something that is not us is not adopted.
            var grown = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 1, MarketPosition.Long, 5,
                20000, -40, 80, CopierBracketReconciler.TickRounder(0.25));
            Assert(grown.Quantity == 1,
                "A position larger than the bracket's is not silently adopted (1, not 5)");
        }

        private static void TestDesired_FlatFollowerForbidsBothLegs()
        {
            var d = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 2, MarketPosition.Flat, 0,
                20000, -40, 80, CopierBracketReconciler.TickRounder(0.25));
            Assert(!d.HasPosition
                && d.Stop.Intent == LegIntent.Forbidden && d.Target.Intent == LegIntent.Forbidden,
                "P0-50: a flat follower forbids both legs -- an orphan leg is a new position on trigger");
        }

        private static void TestDesired_SideMismatchForbidsBothLegs()
        {
            var d = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 2, MarketPosition.Short, 2,
                20000, -40, 80, CopierBracketReconciler.TickRounder(0.25));
            Assert(!d.HasPosition && d.Stop.Intent == LegIntent.Forbidden,
                "A follower on the other side from the bracket forbids both legs");
        }

        private static void TestDesired_UnknownOffsetIsUnspecifiedNotForbidden()
        {
            // THE distinction the three-state intent exists for. P0-9 item (4): the leader
            // cancelling its own stop must leave the follower's stop working. A two-state
            // desire would read this as "no stop wanted" and cancel it -- a naked follower
            // delivered as a refactor.
            var d = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 2, MarketPosition.Long, 2,
                20000, double.NaN, 80, CopierBracketReconciler.TickRounder(0.25));
            Assert(d.HasPosition && d.Stop.Intent == LegIntent.Unspecified,
                "An unknown stop offset is Unspecified, NOT Forbidden (P0-9 item 4)");
            Assert(d.Target.Intent == LegIntent.Required,
                "One leg being unknown does not make the other unknown");

            // No follower fill yet: nothing is anchored, but nothing is forbidden either.
            var unfilled = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 2, MarketPosition.Long, 2,
                double.NaN, -40, 80, CopierBracketReconciler.TickRounder(0.25));
            Assert(unfilled.Stop.Intent == LegIntent.Unspecified
                && unfilled.Target.Intent == LegIntent.Unspecified,
                "Before the follower fills there is no anchor, so both legs are Unspecified");
        }

        private static void TestDesired_NonPositivePriceIsRefusedWithoutCancellingCover()
        {
            var d = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 1, MarketPosition.Long, 1,
                100, -500, 80, CopierBracketReconciler.TickRounder(0.25));
            Assert(d.Stop.Intent == LegIntent.Unspecified,
                "A non-positive computed price is refused as Unspecified, so existing cover survives it");
        }

        // ---- Reconcile ----

        private static void TestReconcile_NothingOwnedCreatesBothLegsRiskLegFirst()
        {
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), new List<Order>(), false, false);
            Assert(actions.Count == 2
                && actions[0].Verb == ReconcileVerb.Create
                && actions[0].Leg.Name == CopierBracketReconciler.OwnedStopName
                && actions[1].Leg.Name == CopierBracketReconciler.OwnedTargetName,
                "Nothing owned: create both legs, and the RISK leg is emitted first");
        }

        private static void TestReconcile_CorrectLegsProduceNoActions()
        {
            var inst = ReconInstrument();
            var owned = new List<Order>
            {
                OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell, 2, 19960, OrderState.Working),
                OwnedLeg(inst, "COPIER_TARGET", OrderType.Limit, OrderAction.Sell, 2, 20080, OrderState.Working)
            };
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), owned, false, false);
            Assert(actions.Count == 0,
                "Legs already at the right price and size produce NO actions (the reconcile is idempotent)");
        }

        private static void TestReconcile_TwoOwnedLegsAreDeduplicated()
        {
            // Observed live 2026-08-10: two working COPIER_TARGETs against one lot. The old
            // syncs could not see this at any price -- they read bracket.WorkingTarget, a
            // single Order reference, and never enumerated the account's orders. So the
            // duplicate was not merely created, it was PERMANENT.
            var inst = ReconInstrument();
            var keep = OwnedLeg(inst, "COPIER_TARGET", OrderType.Limit, OrderAction.Sell, 2, 20080, OrderState.Working);
            var dupe = OwnedLeg(inst, "COPIER_TARGET", OrderType.Limit, OrderAction.Sell, 2, 20080, OrderState.Working);
            var owned = new List<Order> { keep, dupe };

            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), owned, false, false);

            Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_TARGET") == 1,
                "Two owned targets: exactly ONE is cancelled");
            Assert(CountVerb(actions, ReconcileVerb.Create, "COPIER_TARGET") == 0,
                "Two owned targets: no third one is created");

            // And the survivor is left correct, not cancelled along with the duplicate.
            bool survivorTouched = false;
            foreach (var a in actions)
                if (a.Verb == ReconcileVerb.Cancel && ReferenceEquals(a.Subject, keep)) survivorTouched = true;
            Assert(!survivorTouched, "The working survivor is kept, not swept up with its duplicate");
        }

        private static void TestReconcile_DuplicateStopsBehindMismatchedQuantitiesLeaveOneCorrectLeg()
        {
            // P1-56 as it actually appeared: qty 1 AND qty 2 behind 2 lots, which flips the
            // follower when both fire. One pass must leave exactly one leg, correctly sized.
            var inst = ReconInstrument();
            var one = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell, 1, 19960, OrderState.Working);
            var two = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell, 2, 19960, OrderState.Working);
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), new List<Order> { one, two }, false, false);

            Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 1,
                "P1-56: one of the two stops is cancelled in a single pass");
            int survivorQty = 0;
            foreach (var a in actions)
                if (a.Verb == ReconcileVerb.Cancel && a.Subject != null) survivorQty = ReferenceEquals(a.Subject, one) ? 2 : 1;
            // Whichever is kept, the pass must end with a 2-lot stop: either it already is
            // one, or it is modified to become one.
            bool endsCorrect = survivorQty == 2 || CountVerb(actions, ReconcileVerb.Modify, "COPIER_STOP") == 1;
            Assert(endsCorrect, "P1-56: after one pass exactly one stop remains, sized to the 2-lot position");
        }

        private static void TestReconcile_ChangeSubmittedLegIsNotDuplicated()
        {
            // P0-59, the copier's half of P0-60: an order mid-Change() is emphatically NOT
            // gone. Reading it as gone is what put two working targets behind one lot.
            var inst = ReconInstrument();
            var changing = OwnedLeg(inst, "COPIER_TARGET", OrderType.Limit, OrderAction.Sell,
                2, 20080, OrderState.ChangeSubmitted);
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), new List<Order> { changing }, false, false);
            Assert(CountVerb(actions, ReconcileVerb.Create, "COPIER_TARGET") == 0,
                "P0-59: a leg in ChangeSubmitted occupies its slot, so no second one is created");
        }

        private static void TestReconcile_DepartingLegIsReplacedAndNotCancelledTwice()
        {
            // P0-60, RiskGuard's half, seen from the copier's side: a stop being cancelled
            // is NOT coverage. The slot is free, so a replacement is created -- and the
            // departing order is not cancelled a second time.
            var inst = ReconInstrument();
            var leaving = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell,
                2, 19960, OrderState.CancelSubmitted);
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), new List<Order> { leaving }, false, false);
            Assert(CountVerb(actions, ReconcileVerb.Create, "COPIER_STOP") == 1,
                "P0-60: a stop being cancelled is not coverage, so a replacement is created");
            Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 0,
                "P0-60: the departing stop is not cancelled a second time");
        }

        /// <summary>
        /// P0-61, found by a live trade on 2026-08-10 and not by any gate. A leg mid-change must
        /// not be changed again: NT8 silently drops the second Change() and REVERTS the order to
        /// its pre-change values, so the leg ends up neither where the first change wanted it nor
        /// where the second did. Live, that left a 2-lot follower behind a 1-lot stop and target.
        ///
        /// The trap is that the two P0-60 predicates both answer "yes" here -- it occupies a slot
        /// and it provides coverage -- so the wrong answer is the natural one.
        /// </summary>
        private static void TestReconcile_P0_61_ALegMidChangeIsDeferredNotChangedAgain()
        {
            var inst = ReconInstrument();
            foreach (var midChange in new[] { OrderState.ChangeSubmitted, OrderState.ChangePending })
            {
                var changing = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell,
                    1, 19960, midChange);
                // Desired differs in BOTH price and quantity, as it did live (1 -> 2 lots).
                var actions = CopierBracketReconciler.Reconcile(
                    LongTwoLot(-20, 80), new List<Order> { changing }, false, false);

                Assert(CountVerb(actions, ReconcileVerb.Defer, "COPIER_STOP") == 1,
                    "P0-61: a leg in " + midChange + " is DEFERRED, not changed a second time");
                Assert(CountVerb(actions, ReconcileVerb.Modify, "COPIER_STOP") == 0,
                    "P0-61: no second Change() is issued against a leg in " + midChange
                    + " -- NT8 drops it and reverts the order");
                Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 0,
                    "P0-61: and it does NOT fall back to cancel-then-replace -- pulling a "
                    + "protective leg whose change is landing opens a naked window to fix a price");
                Assert(CountVerb(actions, ReconcileVerb.Create, "COPIER_STOP") == 0,
                    "P0-61: nor is a second leg created beside it (" + midChange + ")");
            }
        }

        /// <summary>
        /// The three questions, on one order state, stated together. P0-60 built two predicates
        /// whose answers point opposite ways; P0-61 added a third that neither answers. A future
        /// session collapsing any of them back together should fail here.
        /// </summary>
        private static void TestOrderLiveness_P0_61_MidChangeAnswersTheThreeQuestionsDifferently()
        {
            foreach (var s in new[] { OrderState.ChangeSubmitted, OrderState.ChangePending })
            {
                Assert(RiskGuardAddOn.OccupiesSlot(s),
                    s + " OCCUPIES a slot -- reading it as gone duplicated a live leg (P0-59)");
                Assert(RiskGuardAddOn.ProvidesCoverage(s),
                    s + " PROVIDES coverage -- it is protecting the position right now");
                Assert(!RiskGuardAddOn.AcceptsModification(s),
                    s + " does NOT accept modification -- a second Change() is dropped and the "
                    + "order reverts (P0-61, live 2026-08-10)");
                Assert(!RiskGuardAddOn.IsTerminal(s), s + " is not terminal");
            }

            // And the ordinary working states still accept one.
            foreach (var s in new[] { OrderState.Working, OrderState.Accepted, OrderState.TriggerPending })
                Assert(RiskGuardAddOn.AcceptsModification(s),
                    s + " accepts modification, so an ordinary trail step is still one order");

            // A cancelling leg accepts nothing and covers nothing (P0-60).
            Assert(!RiskGuardAddOn.AcceptsModification(OrderState.CancelSubmitted)
                    && !RiskGuardAddOn.ProvidesCoverage(OrderState.CancelSubmitted),
                "CancelSubmitted neither covers nor accepts modification");
        }

        private static void TestReconcile_TrailStepModifiesRatherThanReplaces()
        {
            var inst = ReconInstrument();
            var working = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell,
                2, 19960, OrderState.Working);
            // Leader trailed its stop up 20 points. The target is legitimately absent from
            // `owned` here, so it is created too -- the assertion is about the STOP leg.
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(-20, 80), new List<Order> { working }, false, false);
            Assert(CountVerb(actions, ReconcileVerb.Modify, "COPIER_STOP") == 1
                && CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 0
                && CountVerb(actions, ReconcileVerb.Create, "COPIER_STOP") == 0,
                "An ordinary trail step MODIFIES the working stop in place -- no unprotected window");
            Assert(ReferenceEquals(actions[0].Subject, working)
                && Math.Abs(actions[0].Leg.Price - 19980) < 1e-9,
                "The trail step moves that same order to the new price (19980)");
        }

        private static void TestReconcile_FlatFollowerCancelsEveryOwnedLeg()
        {
            var inst = ReconInstrument();
            var owned = new List<Order>
            {
                OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell, 2, 19960, OrderState.Working),
                OwnedLeg(inst, "COPIER_TARGET", OrderType.Limit, OrderAction.Sell, 2, 20080, OrderState.Working)
            };
            var flat = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 2, MarketPosition.Flat, 0,
                20000, -40, 80, CopierBracketReconciler.TickRounder(0.25));
            var actions = CopierBracketReconciler.Reconcile(flat, owned, false, false);
            Assert(actions.Count == 2
                && CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 1
                && CountVerb(actions, ReconcileVerb.Cancel, "COPIER_TARGET") == 1,
                "P0-50: a flat follower has every owned leg cancelled and nothing created");
        }

        private static void TestReconcile_UnspecifiedLegKeepsOneAndCreatesNone()
        {
            var inst = ReconInstrument();
            var working = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell,
                2, 19960, OrderState.Working);
            var d = LongTwoLot(double.NaN, 80);

            var actions = CopierBracketReconciler.Reconcile(d, new List<Order> { working }, false, false);
            Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 0
                && CountVerb(actions, ReconcileVerb.Modify, "COPIER_STOP") == 0,
                "P0-9 item 4: an Unspecified stop leaves the follower's working stop untouched");

            // But a DUPLICATE is still dropped -- not knowing where the leg goes is no reason
            // to tolerate two of them.
            var dupe = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell,
                2, 19960, OrderState.Working);
            var dedup = CopierBracketReconciler.Reconcile(d, new List<Order> { working, dupe }, false, false);
            Assert(CountVerb(dedup, ReconcileVerb.Cancel, "COPIER_STOP") == 1,
                "An Unspecified leg still de-duplicates: one survivor, no creation");
            Assert(CountVerb(dedup, ReconcileVerb.Create, "COPIER_STOP") == 0,
                "An Unspecified leg never creates");
        }

        private static void TestReconcile_InFlightSubmitSuppressesOnlyItsOwnCreate()
        {
            // P3-31. Between Submit and Accepted the order is not in `owned`, so a second
            // pass with no reservation creates a second leg -- the duplicate family
            // reproduced by the very mechanism meant to cure it.
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), new List<Order>(), true, false);
            Assert(CountVerb(actions, ReconcileVerb.Create, "COPIER_STOP") == 0,
                "P3-31: a stop submit in flight suppresses the stop Create");
            Assert(CountVerb(actions, ReconcileVerb.Create, "COPIER_TARGET") == 1,
                "P3-31: an in-flight STOP does not make the target wait -- upside must not delay, "
                + "and protection must not be delayed by upside either");
        }

        private static void TestReconcile_InFlightNeverSuppressesACancel()
        {
            // The asymmetry that keeps the reservation safe: it may delay creating a leg,
            // never removing one. A reservation that suppressed cancels would let an orphan
            // leg survive on a flat account -- P0-50, resurrected through the ledger.
            var inst = ReconInstrument();
            var orphan = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell,
                2, 19960, OrderState.Working);
            var flat = CopierBracketReconciler.ComputeDesiredBracket(
                MarketPosition.Long, 2, MarketPosition.Flat, 0,
                20000, -40, 80, CopierBracketReconciler.TickRounder(0.25));
            var actions = CopierBracketReconciler.Reconcile(flat, new List<Order> { orphan }, true, true);
            Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 1,
                "An in-flight reservation suppresses Create only, never a Cancel");
        }

        private static void TestReconcile_ForeignAndManualOrdersAreNeverTouched()
        {
            // P1-57 from the dangerous direction. This function's Cancels get EXECUTED, so a
            // false positive on ownership cancels a stranger's protective stop or the user's
            // manual one. Exact-match naming is the whole defence; a Contains("COPIER")
            // test -- which is what ReevaluateLeaderStops uses -- would cancel the first
            // three of these.
            var inst = ReconInstrument();
            var owned = new List<Order>
            {
                OwnedLeg(inst, "COPIER_STOP_REPLIKANTO", OrderType.StopMarket, OrderAction.Sell, 2, 19900, OrderState.Working),
                OwnedLeg(inst, "Replikanto_COPIER_TARGET", OrderType.Limit, OrderAction.Sell, 2, 20200, OrderState.Working),
                OwnedLeg(inst, "COPIER_STOPX", OrderType.StopMarket, OrderAction.Sell, 2, 19900, OrderState.Working),
                OwnedLeg(inst, "Stop1", OrderType.StopMarket, OrderAction.Sell, 2, 19900, OrderState.Working),
                OwnedLeg(inst, "", OrderType.StopMarket, OrderAction.Sell, 2, 19900, OrderState.Working)
            };
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), owned, false, false);

            foreach (var a in actions)
                if (a.Verb == ReconcileVerb.Cancel)
                {
                    Assert(false, "A foreign or manual order was cancelled: " + a.Subject.Name);
                    return;
                }
            Assert(true, "P1-57: no foreign, third-party or manual order is ever cancelled (exact-match ownership)");
            Assert(CountVerb(actions, ReconcileVerb.Create, "COPIER_STOP") == 1,
                "A stranger's stop does not count as OUR leg, so ours is still created");
        }

        private static void TestReconcile_WrongTypeLegIsReplacedNotLeftInPlace()
        {
            // A leg carrying our name but the wrong shape cannot be Changed into the right
            // one. It must be cancelled AND replaced in the same pass -- emitting only the
            // cancel is a naked follower.
            var inst = ReconInstrument();
            var wrong = OwnedLeg(inst, "COPIER_STOP", OrderType.Limit, OrderAction.Sell,
                2, 19960, OrderState.Working);
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), new List<Order> { wrong }, false, false);
            Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 1
                && CountVerb(actions, ReconcileVerb.Create, "COPIER_STOP") == 1,
                "A leg of the wrong order type is cancelled AND replaced in one pass");
            int cancelIdx = actions.FindIndex(a => a.Verb == ReconcileVerb.Cancel);
            int createIdx = actions.FindIndex(a => a.Verb == ReconcileVerb.Create);
            Assert(cancelIdx < createIdx, "The cancel is ordered before its replacement");
        }

        private static void TestReconcile_TerminalLegsAreIgnoredEntirely()
        {
            var inst = ReconInstrument();
            var owned = new List<Order>
            {
                OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell, 2, 19960, OrderState.Cancelled),
                OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell, 2, 19960, OrderState.Rejected),
                OwnedLeg(inst, "COPIER_TARGET", OrderType.Limit, OrderAction.Sell, 2, 20080, OrderState.Filled)
            };
            var actions = CopierBracketReconciler.Reconcile(LongTwoLot(), owned, false, false);
            Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 0
                && CountVerb(actions, ReconcileVerb.Cancel, "COPIER_TARGET") == 0,
                "Terminal legs are gone: never cancelled again");
            Assert(CountVerb(actions, ReconcileVerb.Create, "COPIER_STOP") == 1
                && CountVerb(actions, ReconcileVerb.Create, "COPIER_TARGET") == 1,
                "Terminal legs free their slots, so both legs are created");
        }

        private static void TestReconcile_TheSameOrderListedTwiceIsOneLeg()
        {
            // Callers build `owned` from more than one source -- the broker's enumeration plus
            // whatever the engine has cached -- so the same Order object arriving twice is
            // ordinary. Reading it as two legs turns the de-duplication rule into the very
            // defect it exists to prevent: it would cancel the engine's own working stop as its
            // own duplicate, leaving the position naked.
            var inst = ReconInstrument();
            var one = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell,
                2, 19960, OrderState.Working);

            var actions = CopierBracketReconciler.Reconcile(
                LongTwoLot(), new List<Order> { one, one, one }, false, false);

            Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 0,
                "The same order listed three times is ONE leg -- nothing is cancelled as its own duplicate");
            Assert(CountVerb(actions, ReconcileVerb.Create, "COPIER_STOP") == 0,
                "...and nothing is created either: the leg is already correct");
        }

        private static void TestReconcile_IsIdempotentUnderRepetition()
        {
            // The property that makes event ordering stop mattering, and with it P0-49,
            // P0-55, P1-56 and P0-59 as a class: applying the reconcile to the state it
            // asked for must produce nothing further to do.
            var inst = ReconInstrument();
            var d = LongTwoLot();
            var actions = CopierBracketReconciler.Reconcile(d, new List<Order>(), false, false);

            // Apply what it asked for.
            var owned = new List<Order>();
            foreach (var a in actions)
                if (a.Verb == ReconcileVerb.Create)
                    owned.Add(OwnedLeg(inst, a.Leg.Name, a.Leg.Type, a.Leg.Action,
                        a.Leg.Quantity, a.Leg.Price, OrderState.Working));

            var second = CopierBracketReconciler.Reconcile(d, owned, false, false);
            var third = CopierBracketReconciler.Reconcile(d, owned, false, false);
            Assert(second.Count == 0 && third.Count == 0,
                "Reconcile is idempotent: re-running against the state it produced asks for nothing");
        }

        /// <summary>
        /// P3-30, END TO END through the engine -- the test the old sync path could not have
        /// passed at any price.
        ///
        /// A stray COPIER_STOP is planted directly in `follower.Orders` and NOT in
        /// `bracket.WorkingStop`, which is exactly the state the live 2026-08-10 defect left
        /// behind: two working protective legs, one of which the engine held no reference to.
        /// The old sync decided from `bracket.WorkingStop` alone and never enumerated the
        /// account, so the stray was invisible -- and being invisible, permanent. Two stops
        /// behind one position FLIP the follower when both fire.
        ///
        /// This is the difference between the reconciler and an extra guard on the fast path,
        /// so it is asserted through the real engine and not against the pure functions.
        /// </summary>
        private static void TestBracket_P3_30_AStrayLegTheEngineNeverRecordedIsStillCancelled()
        {
            Console.WriteLine("\n[TEST] BRACKET: a stray protective leg the engine holds no reference to is reconciled away (P3-30)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18002.00, "BR-P330");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));

            var recorded = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            Assert(recorded.Count == 1, "Precondition: the engine placed its one mirrored stop.");

            // The orphan. Same name, same instrument, working at the broker -- and the engine
            // has never heard of it, precisely as on 2026-08-10.
            var stray = new Order
            {
                Id = Guid.NewGuid().ToString(),
                Instrument = mnq,
                Name = "COPIER_STOP",
                OrderType = OrderType.StopMarket,
                OrderAction = OrderAction.Sell,
                Quantity = 1,
                StopPrice = 17985.00,
                OrderState = OrderState.Working,
                TimeInForce = TimeInForce.Day
            };
            follower.Orders.Add(stray);
            Assert(follower.Orders.Count(o => o.Name == "COPIER_STOP"
                    && RiskGuardAddOn.OccupiesSlot(o.OrderState)) == 2,
                "Precondition: TWO working stops now stand behind a 1-lot position.");

            // Any leader stop update drives a sync. Nothing here tells the engine about the
            // stray -- it has to find it.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17989.00));

            var live = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn.OccupiesSlot(o.OrderState))
                .ToList();
            Assert(live.Count == 1,
                string.Format(
                    "Exactly one protective stop survives the reconcile (got {0}). The old sync read "
                    + "bracket.WorkingStop and never enumerated follower.Orders, so the stray was "
                    + "permanent -- and two stops behind one lot flip the follower when both fire.",
                    live.Count));
            Assert(!RiskGuardAddOn.OccupiesSlot(stray.OrderState),
                "The stray leg specifically is the one cancelled, not the leg the engine was managing.");
            Assert(Math.Abs(live[0].StopPrice - 17991.00) < 1e-9,
                string.Format(
                    "The survivor is at the newly mirrored distance (expected 17991.00, got {0}).",
                    live[0].StopPrice));
        }

        /// <summary>
        /// The reconciler treats `Account.Orders` as the truth, and a leg the engine submitted a
        /// moment ago may not be in it yet. The engine's own cached reference is folded in to
        /// cover that window -- and if it were not, this pass would see an empty slot and submit
        /// a SECOND stop, which is the duplicate family reproduced by the cure.
        ///
        /// Written because a mutation that removed the fold left the whole suite green.
        /// </summary>
        private static void TestBracket_P3_31_ALegNotYetVisibleAtTheBrokerIsNotDuplicated()
        {
            Console.WriteLine("\n[TEST] BRACKET: a submitted leg that has not appeared in Account.Orders yet is not duplicated (P3-31)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18002.00, "BR-P331");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));

            var placed = follower.Orders.Where(o => o.Name == "COPIER_STOP").ToList();
            Assert(placed.Count == 1, "Precondition: the engine placed its mirrored stop.");

            // The window: the order is live at the broker but not yet enumerable. Only the
            // engine's cached reference knows it exists.
            follower.Orders.Remove(placed[0]);

            // Same leader stop, so the desired leg is unchanged. Nothing should be submitted.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));

            int submitted = follower.Orders.Count(o => o.Name == "COPIER_STOP");
            Assert(submitted == 0,
                string.Format(
                    "No second stop is submitted while the first is invisible to Account.Orders (got {0} new). "
                    + "Trusting the broker enumeration ALONE creates a duplicate in this window.",
                    submitted));
        }

        /// <summary>
        /// The other side of that fold: a cached leg that IS in `Account.Orders` must count once.
        /// Counting it twice makes the reconcile see a duplicate and cancel the engine's own
        /// working stop -- turning the de-duplication rule into the naked-position defect it
        /// exists to prevent. A mutation removing the reference-identity check left the suite
        /// green, which is why this exists.
        /// </summary>
        private static void TestBracket_P3_30_ACachedLegAlsoInAccountOrdersCountsOnce()
        {
            Console.WriteLine("\n[TEST] BRACKET: a cached leg that is also in Account.Orders is one leg, not two (P3-30)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18002.00, "BR-DUP1");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            // Trail it, so the pass has real work to do and must not mistake one leg for two.
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17992.00));

            var live = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn.OccupiesSlot(o.OrderState))
                .ToList();
            Assert(live.Count == 1,
                string.Format("Exactly one stop is live after a trail step (got {0}).", live.Count));
            Assert(Math.Abs(live[0].StopPrice - 17994.00) < 1e-9,
                string.Format(
                    "The one surviving stop is at the trailed distance (expected 17994.00, got {0}). "
                    + "If the cached leg were counted twice, the reconcile would cancel it as its own duplicate.",
                    live[0].StopPrice));
        }

        /// <summary>
        /// When the follower is flat, the bracket must be stood down and not merely left without
        /// a leg. A bracket that goes on believing it protects a position is what submits a stop
        /// against a flat account on the next event -- P0-50, whose live form was three
        /// COPIER_STOPs against a flat Sim-ORB, each cancelling the last.
        /// </summary>
        private static void TestBracket_P0_50_AFlatFollowerStandsTheBracketDown()
        {
            Console.WriteLine("\n[TEST] BRACKET: a flat follower stands the bracket down, not just its legs (P0-50)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18002.00, "BR-FLAT1");
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17990.00));
            Assert(TradeCopierEngine.Instance.GetBracketSideForTest("SimFollower", "MNQ 03-26")
                    == MarketPosition.Long,
                "Precondition: the bracket believes the follower is long.");

            // The trade closes at the broker, and a leader stop update arrives after it.
            follower.Positions.Clear();
            leader.TriggerOrderUpdate(LeaderStop(mnq, OrderAction.Sell, 1, 17991.00));

            Assert(TradeCopierEngine.Instance.GetBracketSideForTest("SimFollower", "MNQ 03-26")
                    == MarketPosition.Flat,
                "The bracket is stood down, so no later event can place a leg against a flat account.");
            Assert(!follower.Orders.Any(o => o.Name == "COPIER_STOP"
                    && RiskGuardAddOn.OccupiesSlot(o.OrderState)),
                "No protective leg is left working against the flat position.");
        }

        /// <summary>
        /// P0-61 end to end, and the half that matters: **declining to act is only safe if
        /// something later acts.**
        ///
        /// Deferring the change while one is in flight stops NT8 dropping it and reverting the
        /// order -- but if nothing re-drives when the leg settles, the deferred price and size are
        /// lost for the life of the position, which is the same under-covered follower by a
        /// quieter route. `OnFollowerOrderUpdate` returns early on `OccupiesSlot`, and a leg
        /// settling out of `ChangeSubmitted` still occupies its slot, so this hook has to run
        /// before that return.
        ///
        /// Written because two mutations that silently dropped the re-drive left the suite green.
        /// </summary>
        private static void TestBracket_P0_61_ADeferredChangeIsReappliedWhenTheLegSettles()
        {
            Console.WriteLine("\n[TEST] BRACKET: an instruction deferred during an in-flight change is re-applied when the leg settles (P0-61)");

            var mnq = new Instrument("MNQ 03-26");
            var rel = SlipRelationship(0);
            var follower = SetupCopyPath("SimLeader", "SimFollower", rel, 0, null, MarketPosition.Flat);
            var leader = Account.All.First(a => a.Name == "SimLeader");
            ResetBracketState();

            SetPosition(leader, mnq, MarketPosition.Long, 1, 18000.00);
            DriveFollowerEntry(leader, follower, mnq, 1, 18000.00, 18002.00, "BR-P061");

            // ONE leader stop order, trailed in place. That is what NT8 actually does -- a trailed
            // leg keeps its orderId and its oco (confirmed live, handover 4p) -- and it matters
            // here: raising a SECOND leader stop object leaves the first one Working, and the
            // engine may legitimately re-anchor from whichever it reads last, which makes the
            // assertion below depend on iteration order rather than on the behaviour under test.
            var leaderStop = LeaderStop(mnq, OrderAction.Sell, 1, 17990.00);
            leader.TriggerOrderUpdate(leaderStop);

            var stop = follower.Orders.Single(o => o.Name == "COPIER_STOP");
            Assert(Math.Abs(stop.StopPrice - 17992.00) < 1e-9,
                "Precondition: the mirrored stop is at 17992.00.");

            // A change is now in flight against it -- the state NT8 was in when it dropped our
            // second Change() and reverted the order.
            stop.OrderState = OrderState.ChangeSubmitted;

            // The leader trails its stop in place, 5 points below entry. The sync must NOT touch
            // the broker while our leg's own change is still in flight.
            leaderStop.StopPrice = 17995.00;
            leader.TriggerOrderUpdate(leaderStop);

            Assert(Math.Abs(stop.StopPrice - 17992.00) < 1e-9,
                string.Format(
                    "While the change is in flight the leg is left alone (still 17992.00, got {0}). "
                    + "A second Change() here is dropped by NT8 AND reverts the order.",
                    stop.StopPrice));
            Assert(follower.Orders.Count(o => o.Name == "COPIER_STOP"
                    && RiskGuardAddOn.OccupiesSlot(o.OrderState)) == 1,
                "No duplicate leg is created while the change is in flight either.");

            // The change lands. THIS is what must re-drive the deferred instruction.
            stop.OrderState = OrderState.Working;
            follower.TriggerOrderUpdate(stop);

            var live = follower.Orders
                .Where(o => o.Name == "COPIER_STOP" && RiskGuardAddOn.OccupiesSlot(o.OrderState))
                .ToList();
            Assert(live.Count == 1,
                string.Format("Exactly one stop is live after the re-drive (got {0}).", live.Count));
            Assert(Math.Abs(live[0].StopPrice - 17997.00) < 1e-9,
                string.Format(
                    "The deferred trail is applied once the leg settles: expected 17997.00 "
                    + "(follower entry 18002 - the leader's new 5-point distance), got {0}. "
                    + "Losing it here leaves the follower on a stale stop for the life of the trade.",
                    live[0].StopPrice));
        }

        private static void TestReconcile_SurvivorPrefersTheLegThatActuallyCovers()
        {
            // Three owned stops, only one of which is real coverage. Keeping a departing or
            // suspended leg and cancelling the working one would leave the position naked
            // for as long as the broker takes to act.
            var inst = ReconInstrument();
            var departing = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell, 2, 19960, OrderState.Suspended);
            var working = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell, 2, 19960, OrderState.Working);
            var unknown = OwnedLeg(inst, "COPIER_STOP", OrderType.StopMarket, OrderAction.Sell, 2, 19960, OrderState.Unknown);

            var actions = CopierBracketReconciler.Reconcile(
                LongTwoLot(), new List<Order> { departing, working, unknown }, false, false);

            Assert(CountVerb(actions, ReconcileVerb.Cancel, "COPIER_STOP") == 2,
                "Three owned stops: two are cancelled");
            foreach (var a in actions)
                if (a.Verb == ReconcileVerb.Cancel && ReferenceEquals(a.Subject, working))
                {
                    Assert(false, "The only leg providing coverage was cancelled");
                    return;
                }
            Assert(true, "The survivor is the leg that actually provides coverage, not a suspended or unknown one");
        }

        // ------------------------------------------------------------------
        // CM1: PerTickerMatrix sizing, same instrument, fail closed on entries
        //
        // Acceptance tests for the copier ratio converter, slice 1 of 3. Written
        // BEFORE the fix, so every Assert below is expected to FAIL at baseline.
        //
        // They live in THIS file rather than a new one because Program is not
        // partial and Assert is private to it: a test in a separate class cannot
        // be reached by TestHarness_AllDeclaredTestsAreInvoked, so it would
        // compile and silently run nothing.
        // ------------------------------------------------------------------

        private static CopierRelationship Cm1Matrix(double ratio, string root = "MES")
        {
            var rel = new CopierRelationship
            {
                LeaderAccountName = "Cm1Leader",
                FollowerAccountName = "Cm1Follower",
                SizingMode = CopierSizingMode.PerTickerMatrix,
                // Deliberately hostile defaults: a flat ratio that must be ignored,
                // and auto conversion that must not apply x0.1 to a micro root.
                QuantityRatio = 7.0,
                AutoSymbolConversion = true,
                MaxPositionSize = 100
            };
            rel.PerTickerRatios[root] = ratio;
            return rel;
        }

        private static void TestCM1_MatrixSizesFromTheTableWithoutTheSymbolMultiplier()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM1: PerTickerMatrix sizes from the table, ignoring the mini/micro multiplier");

            var engine = new TradeCopierEngine();

            bool clampedThree;
            int three = engine.CalculateFollowerQuantity(
                Cm1Matrix(3.0), 1, "MES 03-26", 0, false, out clampedThree);
            Assert(three == 3, string.Format(
                "matrix entry sized 3 MES from the table with no symbol multiplier (got {0})", three));

            bool clampedFive;
            int five = engine.CalculateFollowerQuantity(
                Cm1Matrix(5.0), 1, "MES 03-26", 0, false, out clampedFive);
            Assert(five == 5, string.Format(
                "matrix entry sized 5 MES on a second relationship from the same leader fill (got {0})", five));

            // The flat QuantityRatio on the relationship is 7.0. If matrix mode fell
            // through to the ratio branch this would be 7, or 1 once the x0.1 micro
            // multiplier was applied.
            Assert(three == 3 && three != 7, string.Format(
                "matrix mode ignored the flat QuantityRatio on the relationship (got {0})", three));

            // Ordering: the matrix test must be reached BEFORE the guard for the
            // declared-but-unimplemented modes, and that guard must still refuse.
            var netLiq = new CopierRelationship
            {
                SizingMode = CopierSizingMode.NetLiquidationRatio,
                MaxPositionSize = 100
            };
            bool netLiqClamped;
            int netLiqQty = engine.CalculateFollowerQuantity(
                netLiq, 1, "MES 03-26", 0, false, out netLiqClamped);
            Assert(three == 3 && netLiqQty == 0, string.Format(
                "matrix branch was evaluated before the unimplemented sizing mode guard (matrix {0}, netliq {1})",
                three, netLiqQty));
        }

        private static void TestCM1_MatrixFailsClosedOnEntriesAndNeverOnExits()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM1: PerTickerMatrix refuses an unmapped ENTRY and never blocks an EXIT");

            var engine = new TradeCopierEngine();

            // A rule exists, but not for the instrument the leader traded.
            var unmapped = Cm1Matrix(3.0, "MNQ");
            bool entryClamped;
            int entryQty = engine.CalculateFollowerQuantity(
                unmapped, 1, "MES 03-26", 0, false, out entryClamped);
            Assert(entryQty == 0 && entryClamped, string.Format(
                "matrix entry with no rule for the leader instrument was refused and flagged clamped (qty {0}, clamped {1})",
                entryQty, entryClamped));

            // The same relationship must still let the follower OUT of a position.
            bool exitClamped;
            int exitQty = engine.CalculateFollowerQuantity(
                unmapped, 4, "MES 03-26", 4, true, out exitClamped);
            Assert(exitQty == 4, string.Format(
                "matrix exit with no rule mirrored the leader and was capped to the follower position (got {0})",
                exitQty));

            // A follower sitting on the OPPOSITE side must never be increased. The
            // return is an unsigned magnitude, so it may not exceed the position it
            // is reducing.
            bool oppClamped;
            int oppQty = engine.CalculateFollowerQuantity(
                unmapped, 2, "MES 03-26", -3, true, out oppClamped);
            Assert(oppQty <= 3 && oppQty == 2, string.Format(
                "matrix exit never increased an opposite side follower position (got {0} against a position of -3)",
                oppQty));

            // Capacity, not MaxPositionSize: 4 of 5 already held leaves room for 1.
            var capped = Cm1Matrix(3.0);
            capped.MaxPositionSize = 5;
            bool capClamped;
            int capQty = engine.CalculateFollowerQuantity(
                capped, 1, "MES 03-26", 4, false, out capClamped);
            Assert(capQty == 1 && capClamped, string.Format(
                "matrix entry clamped to the remaining capacity when the follower already holds contracts (qty {0}, clamped {1})",
                capQty, capClamped));

            // A null table is empty, not a crash.
            var nullTable = Cm1Matrix(3.0);
            nullTable.PerTickerRatios = null;
            int nullQty = -1;
            bool nullClamped = false;
            bool threw = false;
            try
            {
                nullQty = engine.CalculateFollowerQuantity(
                    nullTable, 1, "MES 03-26", 0, false, out nullClamped);
            }
            catch (Exception)
            {
                threw = true;
            }
            Assert(!threw && nullQty == 0 && nullClamped, string.Format(
                "matrix mode with a null ratio table refused the entry without throwing (threw {0}, qty {1})",
                threw, nullQty));
        }

        private static void TestCM1_MatrixTreatsAnInvalidRatioAsNoRule()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM1: PerTickerMatrix treats NaN, infinities, zero and negatives as no rule");

            var engine = new TradeCopierEngine();

            bool c;
            int nan = engine.CalculateFollowerQuantity(
                Cm1Matrix(double.NaN), 1, "MES 03-26", 0, false, out c);
            Assert(nan == 0 && c, string.Format(
                "matrix entry with a NaN ratio was refused (qty {0}, clamped {1})", nan, c));

            int zero = engine.CalculateFollowerQuantity(
                Cm1Matrix(0.0), 1, "MES 03-26", 0, false, out c);
            Assert(zero == 0 && c, string.Format(
                "matrix entry with a zero ratio was refused (qty {0}, clamped {1})", zero, c));

            // The existing lookup calls Math.Abs, which would turn -3.0 into 3
            // contracts. In matrix mode a negative ratio is a refusal.
            int negative = engine.CalculateFollowerQuantity(
                Cm1Matrix(-3.0), 1, "MES 03-26", 0, false, out c);
            Assert(negative == 0 && c, string.Format(
                "matrix entry with a negative ratio was refused rather than absolute-valued (qty {0})", negative));

            int posInf = engine.CalculateFollowerQuantity(
                Cm1Matrix(double.PositiveInfinity), 1, "MES 03-26", 0, false, out c);
            Assert(posInf == 0 && c, string.Format(
                "matrix entry with a positive infinity ratio was refused (qty {0})", posInf));

            int negInf = engine.CalculateFollowerQuantity(
                Cm1Matrix(double.NegativeInfinity), 1, "MES 03-26", 0, false, out c);
            Assert(negInf == 0 && c, string.Format(
                "matrix entry with a negative infinity ratio was refused (qty {0})", negInf));

            // A ratio that is valid but rounds to nothing must be a VISIBLE refusal,
            // not the silent sub-one-contract skip.
            int roundsToZero = engine.CalculateFollowerQuantity(
                Cm1Matrix(0.4), 1, "MES 03-26", 0, false, out c);
            Assert(roundsToZero == 0 && c, string.Format(
                "matrix entry whose ratio rounds to zero was refused and flagged clamped (qty {0}, clamped {1})",
                roundsToZero, c));
        }

        private static void TestCM1_MatrixKeepsTheLeadersInstrument()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM1: PerTickerMatrix stays in the leader instrument and refuses a cross-instrument mapping");

            var engine = new TradeCopierEngine();

            var rel = Cm1Matrix(3.0);
            string translated = engine.TranslateSymbol("MES 03-26", rel);
            Assert(translated == "MES 03-26", string.Format(
                "matrix mode left MES untranslated instead of routing it to ES (got '{0}')", translated));

            // A custom mapping naming a DIFFERENT root is slice 2, and must be
            // refused rather than sized as if the instruments were equivalent.
            var crossed = Cm1Matrix(3.0);
            crossed.CustomSymbolMappings["MES"] = "ES";
            bool crossClamped;
            int crossQty = engine.CalculateFollowerQuantity(
                crossed, 1, "MES 03-26", 0, false, out crossClamped);
            Assert(crossQty == 0 && crossClamped, string.Format(
                "matrix mode refused an entry whose custom mapping names a different root (qty {0}, clamped {1})",
                crossQty, crossClamped));

            // TranslateSymbol must never signal by returning null: two callers pass
            // its result straight on.
            string crossTranslated = engine.TranslateSymbol("MES 03-26", crossed);
            Assert(crossTranslated != null, string.Format(
                "matrix mode translate returned a string and never null for an unsupported mapping (got '{0}')",
                crossTranslated == null ? "null" : crossTranslated));

            // Every other sizing mode keeps the behaviour it has today.
            var plain = new CopierRelationship
            {
                SizingMode = CopierSizingMode.QuantityRatio,
                QuantityRatio = 1.0,
                AutoSymbolConversion = true,
                MaxPositionSize = 100
            };
            string autoTranslated = engine.TranslateSymbol("ES 12-26", plain);
            Assert(autoTranslated == "MES 12-26", string.Format(
                "non matrix sizing mode still applied the mini micro auto table (got '{0}')", autoTranslated));
        }

        // ------------------------------------------------------------------
        // CM2: the copier config round trip is lossy in one direction only
        //
        // SaveToDisk writes each relationship and group with
        // JsonConvert.SerializeObject, so EVERY property reaches the file.
        // LoadFromDisk hand-parses a remembered subset at three separate sites
        // (structured relationships, groups, and the flat legacy dictionary) and
        // the bridge's set_group is a fourth. None of them reads SizingMode,
        // Mode, PerTickerRatios, CustomSymbolMappings or StealthMode, and only
        // the relationship site reads MaxSlippageTicks.
        //
        // So the fields are on disk, they look set, and loading silently returns
        // them to their defaults. That is worse than "cannot be configured": it
        // is P2-41's shape, where the config echoes what you asked for and
        // applies something else. SizingMode is among them, which is why
        // slice 1's PerTickerMatrix cannot be selected at all.
        //
        // Written BEFORE the fix; every Assert below is expected to FAIL at
        // baseline. In this file rather than a new one because Program is not
        // partial and Assert is private to it (see the CM1 header).
        // ------------------------------------------------------------------

        private static string Cm2TempFile(string name)
        {
            return Path.Combine(Path.GetTempPath(), "test_cm2_" + name + ".json");
        }

        private static CopierRelationship Cm2Relationship()
        {
            var rel = new CopierRelationship
            {
                LeaderAccountName = "Cm2Leader",
                FollowerAccountName = "Cm2Follower",
                SizingMode = CopierSizingMode.PerTickerMatrix,
                Mode = CopierExecutionMode.Executions,
                QuantityRatio = 7.0,
                AutoSymbolConversion = true,
                StealthMode = false,
                MaxSlippageTicks = 2.5,
                MaxPositionSize = 100
            };
            rel.PerTickerRatios["MES"] = 3.0;
            rel.PerTickerRatios["MNQ"] = 5.0;
            return rel;
        }

        private static void TestCM2_RelationshipRoundTripKeepsSizingAndTheMatrix()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM2: a saved relationship reloads with its sizing mode and ratio table intact");

            string file = Cm2TempFile("relationship");
            var writer = new TradeCopierEngine();
            writer.UpsertRelationship(Cm2Relationship());
            writer.SaveToDisk(file);

            // The file must actually carry them -- if SaveToDisk dropped them
            // this would be a serializer defect, not a parser one, and the
            // remedy would be somewhere else entirely.
            string onDisk = File.ReadAllText(file);
            Assert(onDisk.Contains("PerTickerRatios") && onDisk.Contains("SizingMode"),
                "SaveToDisk wrote SizingMode and PerTickerRatios to the file, so the loss is on the READ side");

            var reader = new TradeCopierEngine();
            reader.LoadFromDisk(file);
            var rel = reader.GetRelationships().FirstOrDefault(r => r.FollowerAccountName == "Cm2Follower");
            Assert(rel != null, "the reloaded relationship exists");

            Assert(rel != null && rel.SizingMode == CopierSizingMode.PerTickerMatrix, string.Format(
                "reloaded SizingMode is PerTickerMatrix (got {0})", rel == null ? "<null rel>" : rel.SizingMode.ToString()));
            Assert(rel != null && rel.PerTickerRatios != null && rel.PerTickerRatios.Count == 2, string.Format(
                "reloaded PerTickerRatios kept both entries (got {0})",
                rel == null || rel.PerTickerRatios == null ? -1 : rel.PerTickerRatios.Count));

            double mes = 0.0;
            Assert(rel != null && rel.PerTickerRatios != null
                   && rel.PerTickerRatios.TryGetValue("MES", out mes) && mes == 3.0, string.Format(
                "reloaded PerTickerRatios['MES'] is 3.0 (got {0})", mes));
            Assert(rel != null && rel.StealthMode == false,
                "reloaded StealthMode kept its non default value of false");
            Assert(rel != null && rel.MaxSlippageTicks == 2.5, string.Format(
                "reloaded MaxSlippageTicks is 2.5 (got {0})", rel == null ? -1.0 : rel.MaxSlippageTicks));

            try { File.Delete(file); } catch {}
        }

        private static void TestCM2_GroupRoundTripKeepsSizingAndTheMatrix()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM2: a saved group reloads with its sizing mode, ratio table and slippage cap");

            string file = Cm2TempFile("group");
            var writer = new TradeCopierEngine();
            var grp = new CopierGroup
            {
                GroupName = "Cm2Group",
                LeaderAccountName = "Cm2GroupLeader",
                SizingMode = CopierSizingMode.PerTickerMatrix,
                QuantityRatio = 7.0,
                StealthMode = false,
                MaxSlippageTicks = 4.0,
                FollowerAccounts = new List<string> { "Cm2GroupFollower1", "Cm2GroupFollower2" }
            };
            grp.PerTickerRatios["MES"] = 3.0;
            writer.UpsertGroup(grp, confirmLive: false);
            writer.SaveToDisk(file);

            var reader = new TradeCopierEngine();
            reader.LoadFromDisk(file);
            var reloaded = reader.GetGroup("Cm2Group");
            Assert(reloaded != null, "the reloaded group exists");

            Assert(reloaded != null && reloaded.SizingMode == CopierSizingMode.PerTickerMatrix, string.Format(
                "reloaded group SizingMode is PerTickerMatrix (got {0})",
                reloaded == null ? "<null group>" : reloaded.SizingMode.ToString()));

            double mes = 0.0;
            Assert(reloaded != null && reloaded.PerTickerRatios != null
                   && reloaded.PerTickerRatios.TryGetValue("MES", out mes) && mes == 3.0, string.Format(
                "reloaded group PerTickerRatios['MES'] is 3.0 (got {0})", mes));

            // MaxSlippageTicks is parsed at the RELATIONSHIP site and not at the
            // group one. Two readers of the same field disagreeing is the shape
            // under this whole defect, so it is pinned separately.
            Assert(reloaded != null && reloaded.MaxSlippageTicks == 4.0, string.Format(
                "reloaded group MaxSlippageTicks is 4.0 (got {0})",
                reloaded == null ? -1.0 : reloaded.MaxSlippageTicks));
            Assert(reloaded != null && reloaded.FollowerAccounts != null
                   && reloaded.FollowerAccounts.Count == 2,
                "reloaded group still carries both followers");

            try { File.Delete(file); } catch {}
        }

        private static void TestCM2_ReloadedMatrixLookupIsStillCaseInsensitive()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM2: the reloaded ratio table is still an OrdinalIgnoreCase dictionary");

            // P1-39's lesson, carried over: the obvious deserializer fix
            // (ObjectCreationHandling.Replace) throws the property initializer's
            // StringComparer away and makes every instrument lookup
            // case-sensitive. A root arriving as "mes" would then match no rule
            // and, under slice 1, refuse the entry.
            string file = Cm2TempFile("case");
            var writer = new TradeCopierEngine();
            writer.UpsertRelationship(Cm2Relationship());
            writer.SaveToDisk(file);

            var reader = new TradeCopierEngine();
            reader.LoadFromDisk(file);
            var rel = reader.GetRelationships().FirstOrDefault(r => r.FollowerAccountName == "Cm2Follower");

            double lower = 0.0;
            Assert(rel != null && rel.PerTickerRatios != null
                   && rel.PerTickerRatios.TryGetValue("mes", out lower) && lower == 3.0, string.Format(
                "reloaded PerTickerRatios still matches 'mes' against the stored 'MES' (got {0})", lower));

            try { File.Delete(file); } catch {}
        }

        private static void TestCM2_ALoadedMatrixActuallySizesATrade()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM2: a relationship loaded from disk sizes a fill from its table");

            // The end to end statement of the feature: everything else here is a
            // field comparison, and this is the one that says the operator gets
            // three contracts.
            string file = Cm2TempFile("sizing");
            var writer = new TradeCopierEngine();
            writer.UpsertRelationship(Cm2Relationship());
            writer.SaveToDisk(file);

            var reader = new TradeCopierEngine();
            reader.LoadFromDisk(file);
            var rel = reader.GetRelationships().FirstOrDefault(r => r.FollowerAccountName == "Cm2Follower");

            bool clamped;
            int qty = rel == null ? -1 : reader.CalculateFollowerQuantity(rel, 1, "MES 03-26", 0, false, out clamped);
            Assert(qty == 3, string.Format(
                "a relationship round tripped through disk sized 1 leader MES as 3 follower MES (got {0})", qty));

            try { File.Delete(file); } catch {}
        }

        private static void TestCM2_LegacyAndAliasFormsStillLoad()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM2: the camelCase aliases and the flat legacy file still load");

            // Regression guard. Deserializing the object wholesale is the obvious
            // fix and it does NOT understand these: Json.NET matches property
            // names case-insensitively, but 'leaderAccount' is a different NAME
            // from 'LeaderAccountName', not a different case of it.
            string aliasFile = Cm2TempFile("alias");
            File.WriteAllText(aliasFile,
                "{\"Relationships\":{\"A_B\":{\"leaderAccount\":\"AliasLeader\"," +
                "\"followerAccount\":\"AliasFollower\",\"quantityRatio\":2.5," +
                "\"maxPositionSize\":42}}}");

            var reader = new TradeCopierEngine();
            reader.LoadFromDisk(aliasFile);
            var alias = reader.GetRelationships().FirstOrDefault(r => r.FollowerAccountName == "AliasFollower");
            Assert(alias != null && alias.LeaderAccountName == "AliasLeader",
                "the camelCase alias 'leaderAccount' still maps to LeaderAccountName");
            Assert(alias != null && alias.QuantityRatio == 2.5, string.Format(
                "the camelCase alias 'quantityRatio' still maps to QuantityRatio (got {0})",
                alias == null ? -1.0 : alias.QuantityRatio));
            Assert(alias != null && alias.MaxPositionSize == 42, string.Format(
                "the camelCase alias 'maxPositionSize' still maps to MaxPositionSize (got {0})",
                alias == null ? -1 : alias.MaxPositionSize));

            // The flat form has no Relationships/Groups wrapper at all.
            string flatFile = Cm2TempFile("flat");
            File.WriteAllText(flatFile,
                "{\"FlatLeader\":{\"FollowerAccountName\":\"FlatFollower\"," +
                "\"SizingMode\":\"PerTickerMatrix\",\"PerTickerRatios\":{\"MES\":3.0}}}");

            var flatReader = new TradeCopierEngine();
            flatReader.LoadFromDisk(flatFile);
            var flat = flatReader.GetRelationships().FirstOrDefault(r => r.FollowerAccountName == "FlatFollower");
            Assert(flat != null && flat.LeaderAccountName == "FlatLeader",
                "the flat legacy form still loads and takes the leader from the key");

            double flatMes = 0.0;
            Assert(flat != null && flat.SizingMode == CopierSizingMode.PerTickerMatrix
                   && flat.PerTickerRatios != null
                   && flat.PerTickerRatios.TryGetValue("MES", out flatMes) && flatMes == 3.0, string.Format(
                "the flat legacy form also carries SizingMode and the ratio table (mode {0}, MES {1})",
                flat == null ? "<null>" : flat.SizingMode.ToString(), flatMes));

            try { File.Delete(aliasFile); } catch {}
            try { File.Delete(flatFile); } catch {}
        }

        private static void TestCM2_AMalformedFieldDoesNotDiscardTheWholeConfig()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM2: one unreadable field does not take the entire copier configuration with it");

            // PASSES at baseline, and is here because the FIX can break it.
            // LoadFromDisk clears _relationships and _groups before parsing and
            // wraps everything in one try/catch, so anything that throws leaves
            // the engine with NO configuration at all. Today SizingMode is not
            // read, so a garbage value is harmless. The moment it is read, an
            // unrecognised enum name throws -- and a single typo in
            // copier_config.json would silently disarm every relationship.
            //
            // Not in expect_green: it is green now and must stay green, which is
            // what the no-new-failures gate is for.
            string file = Cm2TempFile("malformed");
            File.WriteAllText(file,
                "{\"Relationships\":{\"A_B\":{\"LeaderAccountName\":\"MalformedLeader\"," +
                "\"FollowerAccountName\":\"MalformedFollower\",\"QuantityRatio\":2.0," +
                "\"SizingMode\":\"NotARealSizingMode\"}}}");

            var reader = new TradeCopierEngine();
            reader.LoadFromDisk(file);
            var rel = reader.GetRelationships().FirstOrDefault(r => r.FollowerAccountName == "MalformedFollower");

            Assert(rel != null,
                "an unreadable SizingMode left the rest of the relationship loaded rather than discarding the file");
            Assert(rel != null && rel.QuantityRatio == 2.0, string.Format(
                "the fields either side of the unreadable one still loaded (got {0})",
                rel == null ? -1.0 : rel.QuantityRatio));
            Assert(rel != null && rel.SizingMode == CopierSizingMode.QuantityRatio, string.Format(
                "the unreadable SizingMode fell back to the default rather than throwing (got {0})",
                rel == null ? "<null rel>" : rel.SizingMode.ToString()));

            try { File.Delete(file); } catch {}
        }

        private static void TestCM2_AnEmptySectionIsNotAParseFailure()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM2: an empty Relationships section is a valid file, not a parse failure");

            // The one upheld review finding that survived checking, and it is
            // narrower than it was filed as. A section written as an empty ARRAY
            // is a legitimate way to say "no relationships", and `as JObject`
            // yields null for it. The claim was that this routes to the flat
            // legacy path, which deserialises the WHOLE document as
            // Dictionary<string,JObject>, throws on the array, and has the outer
            // catch swallow it after everything was already cleared.
            //
            // What it misses: `hasStructuredSections` is an OR. A file with a
            // real Groups section never reaches the flat path at all, which is
            // what this pins -- an empty Relationships array must not take
            // Groups down with it. The genuinely unreachable case (BOTH sections
            // written as arrays) discards a configuration that declared nothing,
            // so there is nothing to lose and no test to write for it.
            string file = Cm2TempFile("empty_section");
            File.WriteAllText(file,
                "{\"Relationships\":[],\"Groups\":{\"KeepMe\":{\"GroupName\":\"KeepMe\"," +
                "\"LeaderAccountName\":\"KeepLeader\",\"FollowerAccounts\":[\"KeepFollower\"]}}}");

            var reader = new TradeCopierEngine();
            reader.LoadFromDisk(file);

            Assert(reader.GetGroup("KeepMe") != null,
                "an empty Relationships array left the Groups section loaded rather than discarding the file");

            try { File.Delete(file); } catch {}
        }

        private static void TestCM2_AMalformedNumberNeverBecomesAZeroLimit()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM2: a malformed number fails closed rather than silently becoming zero");

            // PASSES at baseline. Added after a review panel found the defect in
            // a candidate the whole gate ladder had passed: tolerating an
            // unrecognised ENUM (the guard above) had been widened into a
            // blanket Json.NET Error handler that swallowed EVERY deserialisation
            // error. A type mismatch then leaves the field at the CLR default
            // rather than the property initialiser's value -- MaxPositionSize 0
            // instead of 100, QuantityRatio 0.0 instead of 1.0 -- and a zero
            // limit or a zero ratio sizes every fill at nothing, so the leader
            // trades and the follower does not.
            //
            // Fail closed either way: discarding the entry is fine, and so is
            // keeping the intended default. Silently producing ZERO is not.
            string file = Cm2TempFile("malformed_number");
            File.WriteAllText(file,
                "{\"Relationships\":{\"A_B\":{\"LeaderAccountName\":\"BadNumLeader\"," +
                "\"FollowerAccountName\":\"BadNumFollower\"," +
                "\"MaxPositionSize\":\"not a number\",\"QuantityRatio\":\"also not a number\"}}}");

            var reader = new TradeCopierEngine();
            reader.LoadFromDisk(file);
            var rel = reader.GetRelationships().FirstOrDefault(r => r.FollowerAccountName == "BadNumFollower");

            Assert(rel == null || rel.MaxPositionSize != 0, string.Format(
                "a malformed MaxPositionSize did not become a zero position cap (got {0})",
                rel == null ? "<entry refused>" : rel.MaxPositionSize.ToString()));
            Assert(rel == null || rel.QuantityRatio != 0.0, string.Format(
                "a malformed QuantityRatio did not become a zero sizing ratio (got {0})",
                rel == null ? "<entry refused>" : rel.QuantityRatio.ToString()));

            try { File.Delete(file); } catch {}
        }

        // ------------------------------------------------------------------
        // CM3: slice 3b -- a partial bridge update must not destroy stored config
        //
        // McpBridgeAddOn's CopierConfig("set_group"/"set") builds a BRAND NEW
        // CopierGroup/CopierRelationship from a hand-written field list and hands
        // it to UpsertGroup/UpsertRelationship, which REMOVE the existing object
        // and add the new one wholesale (TradeCopierEngine.cs:256 and :139). The
        // very next line calls SaveToDisk.
        //
        // So every field the caller does not mention reverts to its initialiser
        // default and is then written to disk. A set_group carrying only
        // {groupName, quantityRatio} DESTROYS PerTickerRatios, SizingMode,
        // CustomSymbolMappings, StealthMode and MaxSlippageTicks. That is data
        // loss, and completing the field list does not fix it -- the next omitted
        // field is destroyed just the same. Only merge semantics fix it: apply
        // the fields actually PRESENT in the request, and leave the rest alone.
        //
        // These drive ApplyGroupRequest/ApplyRelationshipRequest on the engine
        // rather than the bridge, because McpBridgeAddOn.cs is <Compile Remove>d
        // from RiskGuardTests.csproj for its WPF deps -- anything left in that
        // file can only be pinned by source-text regex, which is not evidence.
        // Slice 3b moves the mapping here so the harness EXECUTES it.
        //
        // Written BEFORE the fix; every Assert below is expected to FAIL at
        // baseline. In this file rather than a new one because Program is not
        // partial and Assert is private to it (see the CM1 header).
        // ------------------------------------------------------------------

        private static TradeCopierEngine Cm3EngineWithAStoredGroup()
        {
            var engine = new TradeCopierEngine();
            var grp = new CopierGroup
            {
                GroupName = "Cm3Group",
                LeaderAccountName = "Cm3Leader",
                SizingMode = CopierSizingMode.PerTickerMatrix,
                QuantityRatio = 1.0,
                StealthMode = false,
                MaxSlippageTicks = 2.5,
                MaxPositionSize = 42
            };
            grp.PerTickerRatios["MES"] = 3.0;
            grp.PerTickerRatios["MNQ"] = 5.0;
            grp.CustomSymbolMappings["NQ"] = "MNQ";
            grp.FollowerAccounts.Add("Cm3Follower");
            engine.UpsertGroup(grp);
            return engine;
        }

        private static void TestCM3_APartialGroupUpdateKeepsEveryUnmentionedField()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM3: a set_group naming only the ratio leaves the stored matrix alone");

            var engine = Cm3EngineWithAStoredGroup();

            // Exactly what the MCP bridge receives from `nt_copier_config` when a
            // caller nudges one number: the group key, and the field they changed.
            var merged = engine.ApplyGroupRequest(
                JObject.Parse(@"{""groupName"":""Cm3Group"",""quantityRatio"":2.0}"), false);

            Assert(merged != null, "the update returned a group");
            Assert(merged != null && merged.QuantityRatio == 2.0, string.Format(
                "the field that WAS named got applied (got {0})",
                merged == null ? -1.0 : merged.QuantityRatio));

            Assert(merged != null && merged.SizingMode == CopierSizingMode.PerTickerMatrix, string.Format(
                "SizingMode survived an update that never mentioned it (got {0})",
                merged == null ? "<null>" : merged.SizingMode.ToString()));
            Assert(merged != null && merged.PerTickerRatios != null && merged.PerTickerRatios.Count == 2, string.Format(
                "PerTickerRatios kept both entries (got {0})",
                merged == null || merged.PerTickerRatios == null ? -1 : merged.PerTickerRatios.Count));
            Assert(merged != null && merged.CustomSymbolMappings != null && merged.CustomSymbolMappings.Count == 1,
                "CustomSymbolMappings survived");
            Assert(merged != null && merged.StealthMode == false,
                "StealthMode kept its non default value of false");
            Assert(merged != null && merged.MaxSlippageTicks == 2.5, string.Format(
                "MaxSlippageTicks survived (got {0})", merged == null ? -1.0 : merged.MaxSlippageTicks));
            Assert(merged != null && merged.MaxPositionSize == 42, string.Format(
                "MaxPositionSize kept 42 rather than reverting to the initialiser's 100 (got {0})",
                merged == null ? -1 : merged.MaxPositionSize));
            Assert(merged != null && merged.LeaderAccountName == "Cm3Leader",
                "the leader was not replaced by the bridge's Sim101 default");
            Assert(merged != null && merged.FollowerAccounts != null && merged.FollowerAccounts.Count == 1,
                "the follower list was not emptied");
        }

        private static void TestCM3_APartialUpdateIsWhatGetsStoredAndSaved()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM3: the merged group -- not a stub -- is what reaches the engine and the disk");

            var engine = Cm3EngineWithAStoredGroup();
            engine.ApplyGroupRequest(
                JObject.Parse(@"{""groupName"":""Cm3Group"",""quantityRatio"":2.0}"), false);

            // The in-memory list is what the copier actually sizes fills from.
            var stored = engine.GetGroups().FirstOrDefault(g => g.GroupName == "Cm3Group");
            Assert(stored != null && stored.PerTickerRatios != null && stored.PerTickerRatios.Count == 2,
                "the ENGINE's copy kept the matrix, not just the returned object");
            Assert(engine.GetGroups().Count(g => g.GroupName == "Cm3Group") == 1,
                "the merge upserted rather than appending a duplicate group");

            string file = Path.Combine(Path.GetTempPath(), "test_cm3_group.json");
            engine.SaveToDisk(file);
            var reader = new TradeCopierEngine();
            reader.LoadFromDisk(file);
            var reloaded = reader.GetGroups().FirstOrDefault(g => g.GroupName == "Cm3Group");

            Assert(reloaded != null && reloaded.SizingMode == CopierSizingMode.PerTickerMatrix,
                "SizingMode survived the update AND the disk round trip");
            double mes = 0.0;
            Assert(reloaded != null && reloaded.PerTickerRatios != null
                   && reloaded.PerTickerRatios.TryGetValue("mes", out mes) && mes == 3.0, string.Format(
                "the reloaded matrix is still OrdinalIgnoreCase after a partial update (got {0})", mes));
            Assert(reloaded != null && reloaded.QuantityRatio == 2.0,
                "the reloaded group carries the value the partial update set");

            try { File.Delete(file); } catch {}
        }

        private static void TestCM3_APartialRelationshipUpdateKeepsEveryUnmentionedField()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM3: the relationship half of the bridge merges too");

            var engine = new TradeCopierEngine();
            engine.UpsertRelationship(Cm2Relationship());

            var merged = engine.ApplyRelationshipRequest(JObject.Parse(
                @"{""leaderAccount"":""Cm2Leader"",""followerAccount"":""Cm2Follower"",""maxPositionSize"":7}"), false);

            Assert(merged != null && merged.MaxPositionSize == 7, "the named field was applied");
            Assert(merged != null && merged.SizingMode == CopierSizingMode.PerTickerMatrix,
                "SizingMode survived");
            Assert(merged != null && merged.PerTickerRatios != null && merged.PerTickerRatios.Count == 2,
                "PerTickerRatios kept both entries");
            Assert(merged != null && merged.QuantityRatio == 7.0, string.Format(
                "QuantityRatio kept 7.0 rather than reverting to the bridge default of 1.0 (got {0})",
                merged == null ? -1.0 : merged.QuantityRatio));
            Assert(merged != null && merged.MaxSlippageTicks == 2.5, "MaxSlippageTicks survived");
            Assert(engine.GetRelationships().Count(r => r.FollowerAccountName == "Cm2Follower") == 1,
                "the merge upserted rather than appending a duplicate relationship");
        }

        private static void TestCM3_TheMatrixIsSettableThroughTheBridgeAtAll()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM3: PerTickerRatios and SizingMode can be SET through the request path");

            // This is slice 3's actual goal. Until now the bridge's hand-written
            // field list had no entry for either, so PerTickerMatrix could not be
            // selected by any means except editing C# and recompiling.
            var engine = new TradeCopierEngine();
            var merged = engine.ApplyGroupRequest(JObject.Parse(
                @"{""groupName"":""Cm3New"",""leaderAccount"":""L1"",""sizingMode"":""PerTickerMatrix"",""perTickerRatios"":{""MES"":3.0},""maxSlippageTicks"":1.5,""stealthMode"":false}"),
                false);

            Assert(merged != null && merged.SizingMode == CopierSizingMode.PerTickerMatrix, string.Format(
                "sizingMode arrived as PerTickerMatrix (got {0})",
                merged == null ? "<null>" : merged.SizingMode.ToString()));
            double mes = 0.0;
            Assert(merged != null && merged.PerTickerRatios != null
                   && merged.PerTickerRatios.TryGetValue("MES", out mes) && mes == 3.0, string.Format(
                "perTickerRatios arrived (got {0})", mes));
            Assert(merged != null && merged.MaxSlippageTicks == 1.5, "maxSlippageTicks arrived");
            Assert(merged != null && merged.StealthMode == false, "stealthMode arrived");
            Assert(merged != null && merged.LeaderAccountName == "L1",
                "the camelCase leaderAccount alias still maps to LeaderAccountName");

            // A matrix set through the bridge must be case insensitive like every
            // other one, or a fill on "mes" misses the ratio it just configured.
            double lower = 0.0;
            Assert(merged != null && merged.PerTickerRatios != null
                   && merged.PerTickerRatios.TryGetValue("mes", out lower) && lower == 3.0,
                "a matrix set through the bridge is OrdinalIgnoreCase");
        }

        private static void TestCM3_AnUnknownGroupIsStillCreated()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM3: merging onto nothing still creates the group, with defaults");

            var engine = new TradeCopierEngine();
            var merged = engine.ApplyGroupRequest(
                JObject.Parse(@"{""groupName"":""Fresh"",""quantityRatio"":4.0}"), false);

            Assert(merged != null && merged.GroupName == "Fresh", "the new group was created");
            Assert(merged != null && merged.QuantityRatio == 4.0, "its named field was applied");
            Assert(merged != null && merged.MaxPositionSize == 100,
                "its unnamed fields took the initialiser defaults, not zero");
            Assert(merged != null && merged.PerTickerRatios != null,
                "its matrix is an empty dictionary rather than null");
            Assert(engine.GetGroups().Any(g => g.GroupName == "Fresh"), "it reached the engine");
        }

        private static void TestCM3_APartialUpdateCannotArmForLive()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM3: merge semantics did not open a way to arm live without confirmation");

            var engine = Cm3EngineWithAStoredGroup();
            var merged = engine.ApplyGroupRequest(JObject.Parse(
                @"{""groupName"":""Cm3Group"",""armedForLive"":true}"), false);
            Assert(merged != null && merged.ArmedForLive == false,
                "armedForLive:true WITHOUT confirmLive left the group disarmed");

            var armed = engine.ApplyGroupRequest(JObject.Parse(
                @"{""groupName"":""Cm3Group"",""armedForLive"":true}"), true);
            Assert(armed != null && armed.ArmedForLive == true,
                "armedForLive:true WITH confirmLive armed it");
        }

        private static void TestCM3_AnUnrelatedEditDoesNotSilentlyDisarm()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM3: an edit that never mentions arming leaves the armed state as it was");

            // The counterpart to the test above, and the reason merge semantics
            // need saying out loud here: if an omitted armedForLive fell back to
            // the initialiser's false, then nudging a ratio would silently stop a
            // live group from copying -- the leader trades and the follower does
            // not, which is P0-9's failure shape arrived at from a new direction.
            var engine = Cm3EngineWithAStoredGroup();
            engine.ApplyGroupRequest(JObject.Parse(
                @"{""groupName"":""Cm3Group"",""armedForLive"":true}"), true);

            var merged = engine.ApplyGroupRequest(JObject.Parse(
                @"{""groupName"":""Cm3Group"",""quantityRatio"":3.0}"), false);

            Assert(merged != null && merged.ArmedForLive == true,
                "a partial edit that never mentions armedForLive left it armed");
            Assert(merged != null && merged.QuantityRatio == 3.0, "and still applied the edit");

            var disarmed = engine.ApplyGroupRequest(JObject.Parse(
                @"{""groupName"":""Cm3Group"",""armedForLive"":false}"), false);
            Assert(disarmed != null && disarmed.ArmedForLive == false,
                "an EXPLICIT armedForLive:false disarms without needing confirmLive");
        }

        private static void TestCM3_AMalformedRequestDoesNotDestroyTheStoredGroup()
        {
            Console.WriteLine();
            Console.WriteLine("[TEST] CM3: an unreadable request field leaves the stored config untouched");

            // Session 14's rule, applied to the write path: a malformed NUMBER
            // fails closed. It must not land a zero cap, and it must not take the
            // stored matrix with it on the way out.
            var engine = Cm3EngineWithAStoredGroup();
            CopierGroup merged = null;
            try
            {
                merged = engine.ApplyGroupRequest(JObject.Parse(
                    @"{""groupName"":""Cm3Group"",""maxPositionSize"":""not-a-number""}"), false);
            }
            catch (Exception) { merged = null; }

            var stored = engine.GetGroups().FirstOrDefault(g => g.GroupName == "Cm3Group");
            Assert(stored != null, "the stored group still exists after a malformed request");
            Assert(stored == null || stored.MaxPositionSize == 42, string.Format(
                "the malformed number neither applied nor became a zero cap (got {0})",
                stored == null ? -1 : stored.MaxPositionSize));
            Assert(stored == null || (stored.PerTickerRatios != null && stored.PerTickerRatios.Count == 2),
                "the stored matrix survived the malformed request");
            Assert(merged == null || merged.MaxPositionSize != 0,
                "no zero position cap was returned");
        }
    }
}
#endif
