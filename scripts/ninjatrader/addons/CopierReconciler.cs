using System;
using System.Collections.Generic;

// Cbi only -- Account, Order, Instrument, OrderState, OrderType, OrderAction,
// MarketPosition. Under TESTING these come from the stubs in RiskGuardAddOnTests.cs,
// which declare the same namespace, so this file needs no #if of its own.
using NinjaTrader.Cbi;

namespace NinjaTrader.NinjaScript.AddOns
{
    // ==================================================================
    // P3-30 / P3-31 -- the reconciler, part 1: the two pure functions.
    //
    // WHY THIS EXISTS AT ALL, since 48 defects were already closed without it:
    //
    // Almost every defect in this project is one shape -- the addon's model of
    // broker state diverged from the broker, and nothing re-derived it. The plan
    // said so on page one, and then each defect was closed by teaching the
    // event-driven fast path one more case. That series does not terminate,
    // because the event space belongs to NT8 and now to a third-party copier too.
    //
    // The concrete structural fact underneath the duplicate-leg family
    // (P0-49, P0-55, P1-56, P0-59): `SyncFollowerStopOnce` and
    // `SyncFollowerTargetOnce` decide what to do by reading ONE Order reference
    // per leg -- `bracket.WorkingStop` / `bracket.WorkingTarget`. Neither has
    // ever enumerated `followerAcc.Orders`. So a leg that exists at the broker
    // but is not the one we are holding a reference to is INVISIBLE, and
    // therefore PERMANENT. That is exactly what "2 working COPIER_TARGETs
    // against one lot" was on 2026-08-10: not a leg placed wrongly, a leg that
    // nothing was capable of noticing afterwards.
    //
    // So the model here is:
    //
    //   ComputeDesiredBracket  -- pure. What legs SHOULD exist, from broker
    //                             reads and the mirrored offsets. No accumulated
    //                             state, so every arithmetic defect (P0-6, P0-7,
    //                             the signed offset, the exit rounding, off-tick
    //                             prices) becomes a property test on one function.
    //
    //   Reconcile              -- pure diff of desired against the legs OWNED at
    //                             the broker. It cancels EXTRA owned legs, which
    //                             is the single rule that makes a duplicate leg
    //                             self-healing instead of permanent.
    //
    // Both are static and take values, not the engine, so they are testable
    // without a broker, a lock, or an event ordering.
    //
    // ------------------------------------------------------------------
    // The thing that took two attempts to get right: a leg has THREE states of
    // desire, not two.
    //
    // The obvious design is `HasStop: bool` -- and it is wrong, because
    // "no stop is desired" then means both "the position is gone, cancel
    // everything" AND "the leader cancelled its own stop so we do not know
    // where ours goes". Those need opposite handling: the second must LEAVE the
    // follower's working stop alone. Collapsing them would have reverted
    // P0-9 item (4) (TestBracket_LeaderCancellingItsStopLeavesTheFollowerProtected)
    // and taken the stop off an open position -- a naked follower, shipped as a
    // refactor. Hence LegIntent, and the Unspecified case that still de-duplicates
    // but never creates and never cancels the last survivor.
    // ==================================================================

    /// <summary>What we know about whether a protective leg should exist.</summary>
    internal enum LegIntent
    {
        /// <summary>We know the price and size this leg must have.</summary>
        Required,

        /// <summary>
        /// There is a position, but we do not know where this leg belongs -- no
        /// mirrored offset yet, or the leader retired its own leg. Keep one if one
        /// exists, drop duplicates, create nothing.
        /// </summary>
        Unspecified,

        /// <summary>
        /// This leg must not exist: the follower is flat, or is on the other side
        /// from the bracket. An orphan leg here is not a leftover -- it is a new
        /// position in the opposite direction the moment it fills (P0-50).
        /// </summary>
        Forbidden
    }

    /// <summary>One protective leg, as a value. No Order, no account, no broker.</summary>
    internal struct DesiredLeg
    {
        public LegIntent Intent;
        public OrderType Type;          // StopMarket for the stop, Limit for the target
        public OrderAction Action;      // Sell out of a long, BuyToCover out of a short
        public int Quantity;
        public double Price;            // tick-rounded; StopPrice for a stop, LimitPrice for a target
        public string Name;             // OwnedStopName / OwnedTargetName -- also the ownership mark
    }

    /// <summary>
    /// What the follower's protective legs should be, computed from broker reads
    /// alone. `Reason` exists so a reconcile that decides to do nothing can say why
    /// -- the old syncs returned silently from eight different guards.
    /// </summary>
    internal sealed class DesiredBracket
    {
        public bool HasPosition;
        public MarketPosition Side;
        public int Quantity;
        public DesiredLeg Stop;
        public DesiredLeg Target;
        public string Reason;
    }

    internal enum ReconcileVerb
    {
        /// <summary>Submit a new leg.</summary>
        Create,

        /// <summary>Move an existing leg in place -- no unprotected window.</summary>
        Modify,

        /// <summary>Cancel a leg that should not exist, or must be replaced.</summary>
        Cancel,

        /// <summary>
        /// This leg is wrong but must not be touched YET -- a change against it is already in
        /// flight. Do nothing to the broker; re-drive the sync once the order settles.
        ///
        /// Added after a live trade: NT8 silently drops a second Change() and REVERTS the order
        /// to its pre-change values, which left a 2-lot follower behind a 1-lot stop. See
        /// RiskGuardAddOn.AcceptsModification for the trace.
        /// </summary>
        Defer
    }

    /// <summary>
    /// One broker call the caller should make. A list of these is the entire output
    /// of the reconcile; nothing is executed here, so the decision is inspectable
    /// in a test without a broker.
    /// </summary>
    internal sealed class ReconcileAction
    {
        public ReconcileVerb Verb;
        public Order Subject;       // Modify/Cancel: the order acted on. Create: null.
        public DesiredLeg Leg;      // Create/Modify: what it should become.
        public string Reason;

        public override string ToString()
        {
            return Verb + " " + (Leg.Name ?? "?")
                + (Verb == ReconcileVerb.Create || Verb == ReconcileVerb.Modify
                    ? " " + Leg.Quantity + "@" + Leg.Price
                    : "")
                + " (" + Reason + ")";
        }
    }

    internal static class CopierBracketReconciler
    {
        /// <summary>
        /// The follower legs this copier owns. Ownership is EXACT-MATCH on the order
        /// name, deliberately.
        ///
        /// `ReevaluateLeaderStops` screens leader orders with `Name.Contains("COPIER")`,
        /// and P1-57 recorded why that is fragile: it held only because the other copier
        /// on this box happens to embed our name in its own, and a native `Stop1` goes
        /// straight through. Here the consequence of a false positive is worse than a
        /// missed one -- this function's output gets CANCELLED. An exact match can leave
        /// a stranger's leg alone (visible, and the position stays covered); a substring
        /// match can cancel a stranger's protective stop, or the user's manual one.
        /// </summary>
        internal const string OwnedStopName = "COPIER_STOP";
        internal const string OwnedTargetName = "COPIER_TARGET";

        /// <summary>Prices are compared after tick-rounding, so this only absorbs float noise.</summary>
        private const double PriceEpsilon = 1e-9;

        /// <summary>
        /// True if this order is one of ours, for this leg. See the note on
        /// <see cref="OwnedStopName"/> for why this is not a substring test.
        /// </summary>
        internal static bool IsOwnedLeg(Order o, string legName)
        {
            if (o == null || string.IsNullOrEmpty(legName)) return false;
            return string.Equals(o.Name, legName, StringComparison.OrdinalIgnoreCase);
        }

        // ------------------------------------------------------------------
        // 1. ComputeDesiredBracket -- pure
        // ------------------------------------------------------------------

        /// <summary>
        /// What the follower's two legs should be. Takes the LIVE position and the
        /// bracket's mirrored offsets as values; performs no broker call and mutates
        /// nothing, so it can be property-tested.
        ///
        /// `tickSize` rather than an Instrument, for the same reason: rounding is
        /// arithmetic and does not need a broker object. Pass 0 to skip rounding,
        /// which is what <c>RoundLegToTick</c> does when the instrument cannot answer.
        /// </summary>
        /// <param name="bracketSide">The side the bracket was built for.</param>
        /// <param name="bracketQuantity">The size the bracket believes the follower holds.</param>
        /// <param name="liveSide">The side the broker reports RIGHT NOW.</param>
        /// <param name="liveQuantity">The size the broker reports RIGHT NOW.</param>
        /// <param name="followerEntryPrice">The follower's own average fill. NaN until it fills.</param>
        /// <param name="stopOffset">SIGNED points from the leader's entry to its stop. NaN if unknown.</param>
        /// <param name="targetOffset">SIGNED points from the leader's entry to its target. NaN if unknown.</param>
        /// <param name="roundToTick">
        /// The instrument's OWN rounding, injected rather than reimplemented. This is not
        /// fastidiousness: the desired price is compared against the price on the working
        /// order to decide whether to touch it, and NT8 silently re-rounds off-tick prices
        /// on some submit paths. If our arithmetic and NT8's rounder disagree by one tick,
        /// every comparison fails, and the leg is re-driven forever -- the failure the
        /// existing sync comment warns about from the other direction. Pass null for
        /// identity; <see cref="TickRounder"/> gives a pure one for tests.
        /// </param>
        internal static DesiredBracket ComputeDesiredBracket(
            MarketPosition bracketSide, int bracketQuantity,
            MarketPosition liveSide, int liveQuantity,
            double followerEntryPrice, double stopOffset, double targetOffset,
            Func<double, double> roundToTick)
        {
            var d = new DesiredBracket();

            // ---- Is there a position to protect at all? ----
            //
            // The live read wins over the bracket's snapshot every time. This is P0-50:
            // on 2026-08-07 three COPIER_STOPs were submitted against a FLAT Sim-ORB
            // after the trade had closed, because the decision was made from a stale
            // snapshot. Anything owned in this state is Forbidden, not merely unwanted.
            if (liveSide == MarketPosition.Flat || liveQuantity <= 0)
            {
                d.HasPosition = false;
                d.Reason = "follower is flat at the broker; no leg may exist";
            }
            else if (bracketSide == MarketPosition.Flat || bracketQuantity <= 0)
            {
                d.HasPosition = false;
                d.Reason = "the bracket holds no position; no leg may exist";
            }
            else if (liveSide != bracketSide)
            {
                d.HasPosition = false;
                d.Reason = "follower is " + liveSide + " but the bracket was built for "
                    + bracketSide + "; no leg may exist";
            }

            if (!d.HasPosition && d.Reason != null)
            {
                d.Side = MarketPosition.Flat;
                d.Quantity = 0;
                d.Stop = ForbiddenLeg(OwnedStopName, OrderType.StopMarket);
                d.Target = ForbiddenLeg(OwnedTargetName, OrderType.Limit);
                return d;
            }

            d.HasPosition = true;
            d.Side = liveSide;

            // Sized from the LIVE position, never from the bracket's snapshot alone. A
            // follower that scaled out between the decision and here would otherwise get
            // a leg larger than the position, which FLIPS it when the leg fires. The
            // bracket's figure still caps it, so a position grown by something that is
            // not us is not silently adopted.
            d.Quantity = Math.Min(bracketQuantity, liveQuantity);

            OrderAction exitAction = liveSide == MarketPosition.Long
                ? OrderAction.Sell
                : OrderAction.BuyToCover;

            d.Stop = ResolveLeg(OwnedStopName, OrderType.StopMarket, exitAction,
                d.Quantity, followerEntryPrice, stopOffset, roundToTick);
            d.Target = ResolveLeg(OwnedTargetName, OrderType.Limit, exitAction,
                d.Quantity, followerEntryPrice, targetOffset, roundToTick);

            d.Reason = "follower " + liveSide + " " + d.Quantity
                + "; stop " + d.Stop.Intent + ", target " + d.Target.Intent;
            return d;
        }

        private static DesiredLeg ForbiddenLeg(string name, OrderType type)
        {
            var leg = new DesiredLeg();
            leg.Intent = LegIntent.Forbidden;
            leg.Name = name;
            leg.Type = type;
            return leg;
        }

        /// <summary>
        /// One leg's price and intent. The offset is SIGNED and must stay signed: a
        /// leader trailing its stop INTO PROFIT puts the stop above entry on a long, and
        /// an absolute distance would mirror that as a loss of the same size on the
        /// follower -- turning the leader's locked-in gain into open risk.
        /// </summary>
        private static DesiredLeg ResolveLeg(
            string name, OrderType type, OrderAction action,
            int quantity, double entryPrice, double offset, Func<double, double> roundToTick)
        {
            var leg = new DesiredLeg();
            leg.Name = name;
            leg.Type = type;
            leg.Action = action;
            leg.Quantity = quantity;

            // No anchor, or no mirrored offset -> we do not know where this leg goes.
            // Unspecified, NOT Forbidden: the position is open and a leg already at the
            // broker is protecting it. This is P0-9 item (4) -- the leader cancelling its
            // own stop leaves the follower's in place.
            if (double.IsNaN(entryPrice) || double.IsNaN(offset)
                || double.IsInfinity(entryPrice) || double.IsInfinity(offset))
            {
                leg.Intent = LegIntent.Unspecified;
                leg.Price = double.NaN;
                return leg;
            }

            double price = entryPrice + offset;
            if (roundToTick != null)
            {
                // A throwing rounder must not take the leg down with it -- the unrounded
                // price is what shipped before rounding existed, so it is the safe fallback.
                try { price = roundToTick(price); }
                catch { price = entryPrice + offset; }
            }

            // A non-positive price is not an instruction, it is a bug upstream. Refusing
            // to submit it is what the old syncs did; refusing to CANCEL over it is the
            // part that matters, hence Unspecified rather than Forbidden.
            if (price <= 0 || double.IsNaN(price))
            {
                leg.Intent = LegIntent.Unspecified;
                leg.Price = double.NaN;
                return leg;
            }

            leg.Intent = LegIntent.Required;
            leg.Price = price;
            return leg;
        }

        /// <summary>
        /// A pure tick rounder, for tests and for callers with no Instrument to hand.
        ///
        /// This is NOT the rounder the engine uses -- the engine passes the instrument's
        /// own <c>RoundToTickSize</c>, so that our idea of the desired price and NT8's
        /// idea of the submitted price cannot drift apart by a tick. See the
        /// <c>roundToTick</c> parameter note on <see cref="ComputeDesiredBracket"/>.
        ///
        /// Why rounding is needed at all: both legs are computed from the follower's
        /// AVERAGE fill, and an average across partial fills at different prices is
        /// routinely off-tick -- a live COPIER_TARGET sat Rejected at 29905.625 on MNQ,
        /// whose tick is 0.25.
        /// </summary>
        /// <remarks>
        /// The arithmetic deliberately matches <c>MasterInstrument.RoundToTickSize</c>'s shape --
        /// plain <c>Math.Round</c>, so midpoint behaviour agrees rather than differing on ties.
        /// A gratuitous one-tick disagreement between two rounders in the same codebase is
        /// how the "re-drives the leg forever" failure gets in.
        /// </remarks>
        internal static Func<double, double> TickRounder(double tickSize)
        {
            return delegate(double price)
            {
                if (tickSize <= 0 || double.IsNaN(tickSize) || double.IsInfinity(tickSize)) return price;
                if (double.IsNaN(price) || double.IsInfinity(price)) return price;
                return Math.Round(price / tickSize) * tickSize;
            };
        }

        // ------------------------------------------------------------------
        // 2. Reconcile -- pure diff
        // ------------------------------------------------------------------

        /// <summary>
        /// The diff: what to do so that the legs owned at the broker match
        /// <paramref name="desired"/>. Pure -- it reads order state and returns
        /// intentions, and executes nothing.
        ///
        /// The rule that earns this function its place is the LAST one applied per leg:
        /// every owned leg beyond the one we keep is cancelled. Nothing in the old
        /// event-driven syncs could do that, because they never enumerated the broker's
        /// orders, so a duplicate leg was permanent (P0-59, live 2026-08-10).
        /// </summary>
        /// <param name="desired">Output of <see cref="ComputeDesiredBracket"/>.</param>
        /// <param name="owned">
        /// Every order for THIS follower account and THIS instrument. Filtering to our
        /// own legs happens here, so a caller cannot accidentally widen it -- but the
        /// caller must not narrow it to the orders it already knows about, or the whole
        /// point is lost. Use <see cref="CollectCandidateOrders"/>.
        /// </param>
        /// <param name="stopSubmitInFlight">
        /// P3-31's half. True while a stop submit is between the decision and the
        /// broker's acknowledgement: the order is not yet in `owned`, so without this a
        /// second pass creates a second leg -- which is the duplicate family reproduced
        /// by the very thing meant to cure it. Suppresses Create only; a Cancel of a
        /// leg that must not exist is never suppressed.
        /// </param>
        /// <param name="targetSubmitInFlight">The same, for the target leg.</param>
        internal static List<ReconcileAction> Reconcile(
            DesiredBracket desired,
            IList<Order> owned,
            bool stopSubmitInFlight,
            bool targetSubmitInFlight)
        {
            var actions = new List<ReconcileAction>();
            if (desired == null) return actions;

            // The risk leg first, always. If a caller executes these in order, protection
            // is dealt with before upside -- the same asymmetry the two syncs already had.
            ReconcileLeg(actions, desired.Stop, owned, stopSubmitInFlight);
            ReconcileLeg(actions, desired.Target, owned, targetSubmitInFlight);
            return actions;
        }

        private static void ReconcileLeg(
            List<ReconcileAction> actions, DesiredLeg leg, IList<Order> owned, bool submitInFlight)
        {
            // Legs we own, for this leg kind, that the broker still holds.
            //
            // `OccupiesSlot` is the right predicate for "is something already here":
            // a Departing order (CancelSubmitted/CancelPending) does NOT occupy a slot,
            // so its replacement is created -- and it is not in this list, so it is not
            // cancelled a second time. A Terminal one is gone. An Indeterminate one
            // occupies a slot and provides no coverage, conservative both ways at once.
            // Getting this predicate wrong in either direction is P0-60.
            List<Order> slots = null;
            if (owned != null)
            {
                for (int i = 0; i < owned.Count; i++)
                {
                    var o = owned[i];
                    if (!IsOwnedLeg(o, leg.Name)) continue;
                    if (!RiskGuardAddOn.OccupiesSlot(o.OrderState)) continue;
                    if (slots == null) slots = new List<Order>();
                    // One ORDER is one leg, however many times the caller listed it. Callers
                    // build `owned` from more than one source -- the broker's enumeration plus
                    // whatever the engine has cached -- so the same object arriving twice is
                    // ordinary, and reading it as two legs would turn the de-duplication rule
                    // into the naked-position defect: it would cancel the engine's own working
                    // stop as its own duplicate.
                    //
                    // Honest note on what this line does and does not do: the BEHAVIOURAL
                    // protection is `ReferenceEquals(slots[i], keeper)` in the cancel loop
                    // below, which already skips the same object however often it appears --
                    // mutating this line away leaves the suite green, and that was checked
                    // rather than assumed. It is kept because it makes `slotCount` truthful,
                    // and that number goes into the operator-facing log line.
                    if (ContainsReference(slots, o)) continue;
                    slots.Add(o);
                }
            }
            int slotCount = slots == null ? 0 : slots.Count;

            if (leg.Intent == LegIntent.Forbidden)
            {
                for (int i = 0; i < slotCount; i++)
                    actions.Add(Act(ReconcileVerb.Cancel, slots[i], leg,
                        "this leg must not exist against the live position"));
                return;
            }

            if (slotCount == 0)
            {
                if (leg.Intent != LegIntent.Required) return;   // nothing owned, nothing known
                if (submitInFlight) return;                     // P3-31: one is already on its way
                actions.Add(Act(ReconcileVerb.Create, null, leg, "no leg is present"));
                return;
            }

            // Keep the one that actually protects the position, so a cancel-in-progress or
            // suspended duplicate is what gets dropped rather than the working leg.
            Order keeper = slots[0];
            for (int i = 0; i < slotCount; i++)
            {
                if (RiskGuardAddOn.ProvidesCoverage(slots[i].OrderState)) { keeper = slots[i]; break; }
            }

            // THE RULE. Every other owned leg goes, whatever we decide about the keeper.
            // Emitted before the keeper's own action so that executing in order never
            // leaves the position momentarily over-covered.
            for (int i = 0; i < slotCount; i++)
            {
                if (ReferenceEquals(slots[i], keeper)) continue;
                actions.Add(Act(ReconcileVerb.Cancel, slots[i], leg,
                    "duplicate " + leg.Name + "; " + slotCount + " were owned where 1 belongs"));
            }

            // We do not know what this leg should be, so the survivor stands as it is.
            if (leg.Intent != LegIntent.Required) return;

            // SHAPE BEFORE PRICE. Checking price first and returning "already correct" was
            // the first version of this function, and a test caught it: a leg carrying our
            // name with OrderType.Limit at the stop's price compares equal on price and
            // quantity, so it was accepted as the stop -- while a limit sitting below the
            // market is not a stop at all, it fills at once. The order of these two checks
            // is the difference between a protective stop and an instant exit.
            bool rightShape = keeper.OrderType == leg.Type && keeper.OrderAction == leg.Action;

            if (rightShape)
            {
                bool samePrice = Math.Abs(LegPriceOf(keeper) - leg.Price) < PriceEpsilon;
                bool sameQty = keeper.Quantity == leg.Quantity;
                if (samePrice && sameQty) return;               // already correct
            }

            // A change is already in flight against this leg. Issuing a second one is not a
            // no-op: NT8 drops it AND reverts the order to its pre-change values, so the leg
            // ends up neither where the first change wanted it nor where the second did. Live
            // on 2026-08-10 that left a 2-lot follower behind a 1-lot stop and target.
            //
            // Deliberately does NOT fall through to cancel-then-replace. Cancelling a
            // protective leg whose change is about to land is strictly worse than waiting a
            // beat -- it opens a naked window to fix a price.
            if (rightShape && !RiskGuardAddOn.AcceptsModification(keeper.OrderState)
                && RiskGuardAddOn.ProvidesCoverage(keeper.OrderState))
            {
                actions.Add(Act(ReconcileVerb.Defer, keeper, leg,
                    "a change is already in flight (" + keeper.OrderState
                    + "); a second one would be dropped and revert the leg. Re-drive when it settles."));
                return;
            }

            // Modify in place where the broker can: one order, so no unprotected window
            // on an ordinary trail step, and OCO group membership survives (confirmed
            // live 2026-08-10 -- a trailed leg kept both its orderId and its oco).
            if (rightShape && RiskGuardAddOn.AcceptsModification(keeper.OrderState))
            {
                actions.Add(Act(ReconcileVerb.Modify, keeper, leg,
                    "leg is " + keeper.Quantity + "@" + LegPriceOf(keeper)
                    + ", should be " + leg.Quantity + "@" + leg.Price));
                return;
            }

            // Cannot be modified -- wrong type, wrong side, or not in a state the broker
            // will change. Replace it. Both actions are emitted so the caller cannot
            // cancel and then forget to create, which is a naked follower.
            actions.Add(Act(ReconcileVerb.Cancel, keeper, leg,
                "leg cannot be modified in place (" + keeper.OrderType + " "
                + keeper.OrderAction + " " + keeper.OrderState + "); replacing it"));
            if (!submitInFlight)
                actions.Add(Act(ReconcileVerb.Create, null, leg, "replacement for the cancelled leg"));
        }

        /// <summary>
        /// Reference identity, not <c>Order.OrderId</c>. NT8 does not guarantee the id is unique
        /// and it can change over an order's lifetime across the historical->live transition
        /// (RiskGuardAddOn.cs:4481 carries the same warning). Keying on it here would mis-identify
        /// a leg -- and no test would catch it, because the stub hands out a stable GUID per order.
        /// </summary>
        private static bool ContainsReference(List<Order> orders, Order o)
        {
            for (int i = 0; i < orders.Count; i++)
                if (ReferenceEquals(orders[i], o)) return true;
            return false;
        }

        /// <summary>The price that matters for this order's type.</summary>
        internal static double LegPriceOf(Order o)
        {
            if (o == null) return double.NaN;
            return o.OrderType == OrderType.Limit ? o.LimitPrice : o.StopPrice;
        }

        private static ReconcileAction Act(ReconcileVerb verb, Order subject, DesiredLeg leg, string reason)
        {
            var a = new ReconcileAction();
            a.Verb = verb;
            a.Subject = subject;
            a.Leg = leg;
            a.Reason = reason;
            return a;
        }

        // ------------------------------------------------------------------
        // 3. The one impure helper: reading the broker
        // ------------------------------------------------------------------

        /// <summary>
        /// Every order on this account for this instrument. Deliberately UNFILTERED by
        /// our own bookkeeping -- the reconcile is only worth anything if it can see legs
        /// we are not holding a reference to, which is the entire class of defect it
        /// exists for. Ownership filtering happens inside <see cref="Reconcile"/>.
        ///
        /// Fails closed on a throw: an empty list means "nothing owned", and the worst a
        /// caller does with that is create a leg it believes is missing. Returning a
        /// PARTIAL list would be worse -- it reads as "the duplicate is gone".
        /// </summary>
        internal static List<Order> CollectCandidateOrders(Account account, Instrument instrument)
        {
            var result = new List<Order>();
            if (account == null || instrument == null) return result;
            try
            {
                foreach (var o in account.Orders)
                {
                    if (o == null || o.Instrument == null) continue;
                    if (!o.Instrument.FullName.Equals(instrument.FullName, StringComparison.OrdinalIgnoreCase))
                        continue;
                    result.Add(o);
                }
            }
            catch
            {
                // A collection mutated while enumerating leaves whatever was gathered. See
                // above for why a partial answer is not returned.
                result.Clear();
            }
            return result;
        }
    }
}
