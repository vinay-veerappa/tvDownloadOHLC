"""
run_final_kimi_audit.py
=======================
Submits the exact code snippet of EmergencyFlatten in McpBridgeAddOn.cs to kimi-k2.7-code:cloud
for final NinjaTrader 8 code review and signoff.
"""
import sys
from scripts.utils.ollama_bridge import query_ollama

sys.stdout.reconfigure(encoding='utf-8')

code_to_review = '''
private object EmergencyFlatten(string body)
{
    var req = string.IsNullOrWhiteSpace(body) ? new JObject() : JObject.Parse(body);
    var accountFilter = req.Str("account");
    int lockoutMinutes = req["lockoutMinutes"] != null ? (int)req["lockoutMinutes"] : 60;
    var key = req.Str("idempotencyKey");

    int cancelled = 0, flattened = 0;
    System.Windows.Application.Current.Dispatcher.Invoke(() =>
    {
        foreach (Account acc in Account.All)
        {
            if (!string.IsNullOrEmpty(accountFilter) && !acc.Name.Equals(accountFilter, StringComparison.OrdinalIgnoreCase)) continue;

            // 1. Terminate automated strategies on the account to prevent bracket re-submission
            try
            {
                foreach (NinjaTrader.NinjaScript.StrategyBase str in acc.Strategies)
                {
                    try { str.SetState(State.Terminated); } catch {}
                }
            }
            catch {}

            // 2. Cancel all working orders BEFORE flattening
            foreach (Order ord in acc.Orders)
            {
                if (ord.OrderState == OrderState.Working || ord.OrderState == OrderState.Submitted || ord.OrderState == OrderState.Accepted)
                {
                    try { acc.Cancel(new[] { ord }); cancelled++; } catch {}
                }
            }

            // 3. Close open positions
            try { acc.Flatten(acc.Positions.Select(p => p.Instrument).ToList()); flattened++; } catch {}

            // 4. Second cancel pass to clean up any residual bracket orders
            foreach (Order ord in acc.Orders)
            {
                if (ord.OrderState == OrderState.Working || ord.OrderState == OrderState.Submitted || ord.OrderState == OrderState.Accepted)
                {
                    try { acc.Cancel(new[] { ord }); } catch {}
                }
            }
        }
    });

    Log($"[EMERGENCY FLATTEN AUDIT-NT8-001] ActionKey={key} Cancelled={cancelled} Flattened={flattened} Lockout={lockoutMinutes}m", LogLevel.Warning);
    return new { success = true, actionId = key ?? Guid.NewGuid().ToString(), cancelledOrders = cancelled, flattenedAccounts = flattened, lockoutMinutes };
}
'''

prompt = f"""You are a senior NinjaTrader 8 C# auditor. Perform a final line-by-line audit of the updated EmergencyFlatten method in McpBridgeAddOn.cs:

{code_to_review}

Verify:
1. Is thread marshalling properly handled via System.Windows.Application.Current.Dispatcher.Invoke?
2. Does terminating strategies before cancelling orders prevent race conditions?
3. Is order cancellation sequence correct (Cancel -> Flatten -> Second Cancel)?
4. Is it fully production-ready for NinjaTrader 8?
"""

print("Querying kimi-k2.7-code:cloud for final code signoff...")
ans = query_ollama(prompt, model="kimi-k2.7-code:cloud")
print("\n--- KIMI FINAL AUDIT VERDICT ---")
print(ans)
