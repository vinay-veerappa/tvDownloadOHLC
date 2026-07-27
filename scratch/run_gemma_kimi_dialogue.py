"""
run_gemma_kimi_dialogue.py
==========================
Script to pass Gemma's code output to Kimi K2.7 Code Cloud for direct review.
"""
from scripts.utils.ollama_bridge import query_ollama

gemma_code = '''
using System;
using System.Collections.Generic;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Core;

namespace NinjaTrader.Custom.TradeCopier
{
    public class TradeCopierEngine
    {
        private readonly object _stateLock = new object();
        private EngineState _currentState = EngineState.Active;
        private readonly Queue<Action> _pendingActionQueue = new Queue<Action>();

        public enum EngineState { Active, Quarantined, Disabled }

        public void ExecuteOnMainThread(Action action)
        {
            if (action == null) return;
            Core.Globals.Dispatcher.InvokeAsync(() =>
            {
                try { action(); }
                catch (Exception ex) { Print($"TradeCopier Error executing action: {ex.Message}"); }
            });
        }

        public int CalculateScaledQuantity(int sourceQuantity, decimal scaleFactor)
        {
            if (sourceQuantity <= 0 || scaleFactor <= 0) return 0;
            decimal rawQuantity = (decimal)sourceQuantity * scaleFactor;
            decimal rounded = Math.Round(rawQuantity, 0, MidpointRounding.ToEven);
            return (int)rounded;
        }

        public void TransitionToState(EngineState newState)
        {
            lock (_stateLock)
            {
                _currentState = newState;
                if (_currentState == EngineState.Quarantined)
                {
                    int clearedCount = _pendingActionQueue.Count;
                    _pendingActionQueue.Clear();
                }
            }
        }

        public void ProcessSignal(int masterQty, decimal scaleFactor, Action tradeAction)
        {
            lock (_stateLock)
            {
                if (_currentState != EngineState.Active) return;
                int targetQty = CalculateScaledQuantity(masterQty, scaleFactor);
                if (targetQty == 0) return;
                ExecuteOnMainThread(tradeAction);
            }
        }
    }
}
'''

prompt = f"""Review the revised C# TradeCopierEngine implementation from Gemma 4 31B Cloud:

{gemma_code}

Evaluate if all 3 previous issues (NinjaTrader thread marshalling, contract scaling, and quarantine locking) are now fully resolved. Detail any remaining edge cases or confirm if it is production-ready."""

print("Querying kimi-k2.7-code:cloud...")
ans = query_ollama(prompt, model="kimi-k2.7-code:cloud")
print("\n--- KIMI CODE REVIEW RESPONSE ---")
import sys
sys.stdout.reconfigure(encoding='utf-8')
print(ans)
