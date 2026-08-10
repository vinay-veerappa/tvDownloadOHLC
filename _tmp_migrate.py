import io

# Each call site gets the predicate that matches the QUESTION it is asking.
#   ProvidesCoverage -> "will this order act on the market?"  (coverage, mirror-worthiness,
#                        modify-in-place eligibility)
#   OccupiesSlot     -> "is something already here?"          (do not duplicate, do I cancel it)
COPIER = [
 # OnFollowerOrderUpdate: nothing to react to while the leg still occupies its slot.
 # This is P0-59's trigger -- ChangeSubmitted used to fall through here and be re-submitted.
 ('            if (RiskGuardAddOn.IsPendingOrWorking(order.OrderState)) return;   // still live',
  '            if (RiskGuardAddOn.OccupiesSlot(order.OrderState)) return;   // still there; nothing lost'),
 # ReevaluateLeaderStops candidate filter: only mirror a leader leg that will actually act.
 ('                        && RiskGuardAddOn.IsPendingOrWorking(o.OrderState)\n                        && (string.IsNullOrEmpty(o.Name) || !o.Name.Contains("COPIER")))\n                    .ToList();',
  '                        && RiskGuardAddOn.ProvidesCoverage(o.OrderState)\n                        && (string.IsNullOrEmpty(o.Name) || !o.Name.Contains("COPIER")))\n                    .ToList();'),
 ('                if ((isStopLeg || isTargetLeg) && RiskGuardAddOn.IsPendingOrWorking(order.OrderState))',
  '                if ((isStopLeg || isTargetLeg) && RiskGuardAddOn.ProvidesCoverage(order.OrderState))'),
 ('            if (!RiskGuardAddOn.IsPendingOrWorking(order.OrderState)) return;',
  '            if (!RiskGuardAddOn.ProvidesCoverage(order.OrderState)) return;'),
 ('                if (ambiguousTarget != null && RiskGuardAddOn.IsPendingOrWorking(ambiguousTarget.OrderState))',
  '                if (ambiguousTarget != null && RiskGuardAddOn.OccupiesSlot(ambiguousTarget.OrderState))'),
 # CountLeaderTargetLegs
 ('                    && RiskGuardAddOn.IsPendingOrWorking(o.OrderState)\n                    && RiskGuardAddOn.IsProtectiveSide(o, leaderPos.MarketPosition)',
  '                    && RiskGuardAddOn.ProvidesCoverage(o.OrderState)\n                    && RiskGuardAddOn.IsProtectiveSide(o, leaderPos.MarketPosition)'),
 ('                    bool stillLive = RiskGuardAddOn.IsPendingOrWorking(bracket.WorkingStop.OrderState);',
  '                    bool stillLive = RiskGuardAddOn.OccupiesSlot(bracket.WorkingStop.OrderState);'),
 ('                    && RiskGuardAddOn.IsPendingOrWorking(toCancel.OrderState)\n                    && toCancel.OrderType == OrderType.StopMarket',
  '                    && RiskGuardAddOn.ProvidesCoverage(toCancel.OrderState)\n                    && toCancel.OrderType == OrderType.StopMarket'),
 ('                if (staleTarget != null && RiskGuardAddOn.IsPendingOrWorking(staleTarget.OrderState))',
  '                if (staleTarget != null && RiskGuardAddOn.OccupiesSlot(staleTarget.OrderState))'),
 ('                if (!RiskGuardAddOn.IsPendingOrWorking(leg.OrderState)) continue;',
  '                if (!RiskGuardAddOn.OccupiesSlot(leg.OrderState)) continue;'),
 ('                    bool stillLive = RiskGuardAddOn.IsPendingOrWorking(bracket.WorkingTarget.OrderState);',
  '                    bool stillLive = RiskGuardAddOn.OccupiesSlot(bracket.WorkingTarget.OrderState);'),
 ('                    && RiskGuardAddOn.IsPendingOrWorking(toCancel.OrderState)\n                    && toCancel.OrderType == OrderType.Limit',
  '                    && RiskGuardAddOn.ProvidesCoverage(toCancel.OrderState)\n                    && toCancel.OrderType == OrderType.Limit'),
 ('                if (bracket.WorkingStop != null && RiskGuardAddOn.IsPendingOrWorking(bracket.WorkingStop.OrderState))',
  '                if (bracket.WorkingStop != null && RiskGuardAddOn.OccupiesSlot(bracket.WorkingStop.OrderState))'),
 ('                if (bracket.WorkingTarget != null && RiskGuardAddOn.IsPendingOrWorking(bracket.WorkingTarget.OrderState))',
  '                if (bracket.WorkingTarget != null && RiskGuardAddOn.OccupiesSlot(bracket.WorkingTarget.OrderState))'),
]

p = 'scripts/ninjatrader/addons/TradeCopierEngine.cs'
s = io.open(p, encoding='utf-8').read()
for old, new in COPIER:
    assert old in s, 'COPIER NOT FOUND: ' + old[:80]
    s = s.replace(old, new)
assert 'IsPendingOrWorking' not in s, 'leftover in copier'
io.open(p, 'w', encoding='utf-8').write(s)

# Tests: every one of these asks "is this mirrored leg actually live on the market?"
p = 'scripts/ninjatrader/addons/RiskGuardAddOnTests.cs'
s = io.open(p, encoding='utf-8').read()
s = s.replace('RiskGuardAddOn.IsPendingOrWorking(o.OrderState)', 'RiskGuardAddOn.ProvidesCoverage(o.OrderState)')
s = s.replace('RiskGuardAddOn.IsPendingOrWorking(mirrored.OrderState)', 'RiskGuardAddOn.ProvidesCoverage(mirrored.OrderState)')

# The local helper was a SECOND definition of liveness that could drift from the real one --
# the same class of defect as the two predicates disagreeing. Delete it and call through.
old_helper = """        /// <summary>Mirrors RiskGuardAddOn.IsPendingOrWorking for assertions in this file.</summary>
        private static bool RiskGuardAddOn_IsLiveForTest(Order o)
        {
            return o.OrderState == OrderState.Submitted || o.OrderState == OrderState.Accepted
                || o.OrderState == OrderState.Initialized || o.OrderState == OrderState.Working
                || o.OrderState == OrderState.PartFilled;
        }"""
new_helper = """        /// <summary>
        /// Delegates to the production classification rather than restating it. It used to be a
        /// hand-copied duplicate of the old `IsPendingOrWorking` list -- a second definition of
        /// "alive" living in the grader, free to drift from the one being graded. That is the same
        /// shape of defect as P0-59 itself.
        /// </summary>
        private static bool RiskGuardAddOn_IsLiveForTest(Order o)
        {
            return RiskGuardAddOn.ProvidesCoverage(o.OrderState);
        }"""
assert old_helper in s, 'helper not found'
s = s.replace(old_helper, new_helper)
assert 'IsPendingOrWorking' not in s, 'leftover in tests'
io.open(p, 'w', encoding='utf-8').write(s)
print('migrated')
