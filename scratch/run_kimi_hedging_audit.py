"""
run_kimi_hedging_audit.py
=========================
Queries kimi-k2.7-code:cloud to perform a line-by-line audit of Gemma's 3 Trade Copier rules:
1. Prevent Hedging / Opposite-Side Market Order Skips.
2. Position Reconciler on Follower Fills.
3. Auto-close Follower Positions on Leader Flat.
"""
import sys
from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding='utf-8')

gemma_code = '''
public class TradeCopierEngine
{
    // Rule 1: Prevent Hedging Logic
    public void ProcessLeaderOrder(Order leaderOrder)
    {
        if (leaderOrder.OrderType != OrderType.Market) return;
        int followerPos = followerAccount.GetPosition(instrument);
        
        bool isOppositeDirection = (leaderOrder.OrderAction == OrderAction.Buy && followerPos < 0) ||
                                   (leaderOrder.OrderAction == OrderAction.Sell && followerPos > 0);

        if (isOppositeDirection) return; // Hedging blocked

        int executionQty = leaderOrder.Quantity;
        if (Math.Abs(followerPos) > 0 && leaderOrder.OrderAction != (followerPos > 0 ? OrderAction.Buy : OrderAction.Sell))
        {
            executionQty = Math.Min(executionQty, Math.Abs(followerPos));
        }

        SubmitFollowerOrder(leaderOrder.OrderAction, executionQty);
    }

    // Rule 2 & 3: Position Reconciler & Auto-Close on Leader Flat
    private void OnFollowerOrderFill(object sender, OrderFillEventArgs e)
    {
        if (e.Order.Instrument.FullName != instrument) return;

        int leaderPos = leaderAccount.GetPosition(instrument);
        if (leaderPos == 0)
        {
            FlattenFollowerAndCancelOrders();
            return;
        }

        int followerPos = followerAccount.GetPosition(instrument);
        if ((leaderPos > 0 && followerPos < 0) || (leaderPos < 0 && followerPos > 0))
        {
            EmergencyExitFollower();
        }
    }
}
'''

prompt = f"""You are a senior NinjaTrader 8 C# execution auditor.
Perform a line-by-line code review of Gemma's implementation of the 3 Trade Copier safety rules:

{gemma_code}

Evaluate:
1. Thread safety (NT8 Dispatcher marshalling).
2. Correct NT8 Cbi types (e.g. Account.Get(AccountItem.Position, instrument) vs GetPosition).
3. Edge cases in partial fills, short positions, and multi-contract scaling.
4. Provide the exact, production-ready C# code for TradeCopierEngine.cs.
"""

print("Querying kimi-k2.7-code:cloud for Hedging Audit...")
ans = query_ollama(prompt, model="kimi-k2.7-code:cloud")
print("\n--- KIMI HEDGING AUDIT RESPONSE ---")
print(ans)
