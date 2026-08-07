"""Prove the Phase B backfill tests are falsifiable.

A test that has never been seen to fail is an assertion of faith. For each of
the six T1-T3 acceptance tests, revert *only* the production line(s) that test
exists to pin, re-run the suite, and require that the named test goes red.

The source file is restored from an in-memory copy after every case, including
on exception, so a crash cannot leave the tree patched.

Usage:  python -m scripts.agent_loop.verify_backfill_reverts
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADDON = REPO / "scripts" / "ninjatrader" / "addons" / "RiskGuardAddOn.cs"
TEST_CMD = [
    "dotnet", "run",
    "--project", str(REPO / "ninjatrader-addon" / "RiskGuardTests.csproj"),
    "--nologo", "-v", "q",
]

# (case name, test header substring, old, new)
CASES = [
    (
        "T2 auto-stop sized from live position",
        "T2: auto-stop is sized from the live position",
        "                int stopQuantity = (int)positionForQuantity.Quantity;",
        "                int stopQuantity = action.Quantity;",
    ),
    (
        "T2 ValidateInvariant admits a scaled-down position",
        "T2: a scaled-down position is still admitted",
        "                int liveQuantity = (int)position.Quantity;\n"
        "                if (liveQuantity <= 0)\n"
        "                    return false;",
        "                int liveQuantity = (int)position.Quantity;\n"
        "                if (liveQuantity <= 0)\n"
        "                    return false;\n"
        "                if (action.Quantity > liveQuantity)\n"
        "                    return false;",
    ),
    (
        "T2 rollback on submit failure",
        "T2: a failed auto-stop submit rolls the FSM back",
        '                    RollbackFsm($"Submit failed: {ex.Message}");',
        '                    // reverted: RollbackFsm($"Submit failed: {ex.Message}");',
    ),
    (
        "T1 cancelled stop clears the grace latch",
        "T1: a stop cancelled mid-position re-arms grace",
        "                                fsm.CoveredQuantity = 0;\n"
        "                                fsm.GraceEmitted = false;\n"
        "                                if (!fsm.GracePending)",
        "                                fsm.CoveredQuantity = 0;\n"
        "                                if (!fsm.GracePending)",
    ),
    (
        "T3 peak resets when the account is flat",
        "T3: a flat, profitable account emits no peak-giveback",
        "                    bool needsReset = stateModel.PeakOpenGain != 0.0\n"
        "                        || stateModel.PeakGivebackTriggered\n"
        "                        || !double.IsNaN(stateModel.PeakGivebackLastTriggerUnrealized);\n"
        "                    if (needsReset)\n"
        "                    {\n"
        "                        stateModel.PeakOpenGain = 0.0;\n"
        "                        stateModel.PeakGivebackTriggered = false;\n"
        "                        stateModel.PeakGivebackLastTriggerUnrealized = double.NaN;\n"
        "                        _stateDirty = true;\n"
        "                    }",
        "                    // reverted: flat no longer resets the peak",
    ),
    (
        "T3 flip resets the peak",
        "T3: a close+reverse flip does not carry",
        "                if (isFlip)\n"
        "                {\n"
        "                    PeakOpenGain = 0.0;\n"
        "                    PeakGivebackTriggered = false;\n"
        "                    PeakGivebackLastTriggerUnrealized = double.NaN;\n"
        "                }",
        "                // reverted: flip no longer resets the peak",
    ),
]


def failures_in(output: str, header: str):
    """Return the [FAIL] lines belonging to the test whose header matches."""
    blocks = re.split(r"\n(?=\[TEST\] )", output)
    for block in blocks:
        if header in block.split("\n", 1)[0]:
            return [l.strip() for l in block.splitlines() if "[FAIL]" in l]
    return None  # test never ran


def run_suite():
    p = subprocess.run(TEST_CMD, cwd=REPO, capture_output=True, text=True, timeout=1800)
    return p.stdout + p.stderr


def main():
    original = ADDON.read_text(encoding="utf-8")
    results = []
    try:
        for name, header, old, new in CASES:
            if original.count(old) != 1:
                results.append((name, "SKIP", f"anchor matched {original.count(old)}x, expected 1"))
                continue

            ADDON.write_text(original.replace(old, new), encoding="utf-8")
            out = run_suite()
            ADDON.write_text(original, encoding="utf-8")

            fails = failures_in(out, header)
            if fails is None:
                results.append((name, "ERROR", "test did not run (build failure?)"))
            elif fails:
                results.append((name, "FALSIFIABLE", fails[0][:100]))
            else:
                results.append((name, "NOT FALSIFIABLE", "test still passed with the fix reverted"))
    finally:
        ADDON.write_text(original, encoding="utf-8")

    print("\n" + "=" * 78)
    print("REVERT VERIFICATION")
    print("=" * 78)
    bad = 0
    for name, verdict, detail in results:
        mark = "ok  " if verdict == "FALSIFIABLE" else "BAD "
        if verdict != "FALSIFIABLE":
            bad += 1
        print(f"{mark} {verdict:<16} {name}\n        {detail}")
    print("=" * 78)
    print(f"{len(results) - bad}/{len(results)} tests proven to fail when their fix is reverted")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
