// === DIAG PATCH START ===
// Per-bar gate diagnostics for ORB_AllDay_MultiTP.cs OnBarUpdate.
// Purpose: emit ground-truth gate decisions to the SA log file so the
//          Python<->NT8 parity harness can localize the discrepancy root cause.
//
// VERIFIED FIXES (per scratch/parity_loop_result.json reviewer feedback):
//   - Use Log(..., LogLevel.Information) not Print() (Print -> SA UI only, NOT log file).
//   - Use Time[0] (bar historical time), NOT DateTime.Now (wall-clock, wrong in SA backtest).
//   - Do NOT call EnterLong()/EnterShort()/ExitLong()/ExitShort() in diagnostics
//     -- those SUBMIT orders, they do not query signals. Track a private bool instead.
//   - Bypass gatekeeper for SA accounts named "Sim101"/"Playback*"/"backtest"
//     (Account.Name.Contains("backtest") is unreliable -- SA accounts are "Sim101").
//   - Gate-by-gate logging cadence (per repo nt8_zero_trade_debugging.md):
//       out-of-window -> every 100th bar; in-window -> every 10th bar;
//       decision bar (signal fired) -> every bar.
//
// Splice this block at the TOP of OnBarUpdate() in ORB_AllDay_MultiTP.cs.
// Requires a bool property `VerboseDiag` (default true) and that the strategy
// already exposes: orHigh, orLow, orRangeComplete, predictedDir,
// RequireDirectionBias, gatekeeperBlocked. Adapt field names to your class.

// --- private signal flag, set BEFORE this block by your existing entry logic ---
// private bool _signalFiredThisBar = false;  // set true on the bar where you call EnterLong/Short

// inside OnBarUpdate(), after BarsRequiredToTrade check:
bool diagVerbose = VerboseDiag
    && (State == State.Historical || State == State.Realtime)
    && (Account.Name.IndexOf("Sim", StringComparison.OrdinalIgnoreCase) >= 0
        || Account.Name.IndexOf("Playback", StringComparison.OrdinalIgnoreCase) >= 0
        || Account.Name.IndexOf("backtest", StringComparison.OrdinalIgnoreCase) >= 0);

if (diagVerbose)
{
    try
    {
        // Bar historical time, NOT DateTime.Now (reviewer fix).
        int barHour   = Time[0].Hour;
        int barMinute = Time[0].Minute;
        bool inWindow = barHour == 9 && barMinute >= 30
                     || (barHour > 9 && barHour < 16);

        bool shouldLog = inWindow ? (CurrentBar % 10 == 0) : (CurrentBar % 100 == 0);
        // Decision-bar: log every bar where an entry/exit signal actually fired.
        // Track via your own flag; do NOT invoke order methods here.
        if (_signalFiredThisBar) shouldLog = true;

        if (shouldLog)
        {
            // gatekeeper bypass for SA backtest accounts (verified Bug 2 fix)
            string gkStatus = diagVerbose ? "BYPASS" : (gatekeeperBlocked ? "BLK" : "OK");

            Log(string.Format(
                "[DIAG] Bar={0} ET={1:HH:mm} Close={2} | Win={3} | "
                "ORH={4} ORL={5} RangeComp={6} | Dir={7} BiasReq={8} BiasBlk={9} | "
                "GT_H={10} LT_L={11} | GK={12} | Sig={13}",
                CurrentBar,
                Time[0],
                Close[0],
                inWindow,
                orHigh,
                orLow,
                orRangeComplete,
                predictedDir,
                RequireDirectionBias,
                (RequireDirectionBias && predictedDir == 0),
                (Close[0] > orHigh),
                (Close[0] < orLow),
                gkStatus,
                _signalFiredThisBar),
                LogLevel.Information);
        }
    }
    catch (Exception ex)
    {
        // Never let diagnostics crash the strategy.
        Log("[DIAG_ERR] " + ex.Message, LogLevel.Error);
    }
}

// Reset the per-bar signal flag at the END of OnBarUpdate:
// _signalFiredThisBar = false;
// === DIAG PATCH END ===