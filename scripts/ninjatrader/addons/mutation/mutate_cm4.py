"""Mutation battery for slice 2 (cross-instrument matrix rules).

Each mutation must turn the suite RED. A surviving mutant is a test that only
looks like coverage. Run after any edit to TranslateSymbol,
ResolveFollowerInstrument, ArePricesComparable, or the PerTickerMatrix branch
of CalculateFollowerQuantity.
"""
import os
import subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
ENGINE = os.path.join(REPO, 'scripts', 'ninjatrader', 'addons', 'TradeCopierEngine.cs')

MUTANTS = [
    # --- slice 2's core: the refusal must be gone from BOTH halves together ---
    ("TranslateSymbol re-refuses a cross-instrument mapping in matrix mode",
     "                return customTarget.ToUpper() + remainder;",
     "                if (rel.SizingMode == CopierSizingMode.PerTickerMatrix\n"
     "                    && customTarget.ToUpper() != root) return root + remainder;\n"
     "                return customTarget.ToUpper() + remainder;"),

    ("an explicit mapping is gated on AutoSymbolConversion",
     "            if (rel != null && rel.CustomSymbolMappings != null\n"
     "                && rel.CustomSymbolMappings.TryGetValue(root, out var customTarget)",
     "            if (rel != null && rel.AutoSymbolConversion && rel.CustomSymbolMappings != null\n"
     "                && rel.CustomSymbolMappings.TryGetValue(root, out var customTarget)"),

    ("ResolveFollowerInstrument short-circuits on AutoSymbolConversion again",
     "            string translated = TranslateSymbol(leaderInstrument.FullName, rel);",
     "            if (!rel.AutoSymbolConversion) return leaderInstrument;\n"
     "            string translated = TranslateSymbol(leaderInstrument.FullName, rel);"),

    # --- the ratio is keyed by the LEADER root; guessing rebuilds defect 2 ---
    ("the ratio falls back to the MAPPED root when the leader root has no rule",
     "                if (!hasRatio)\n                {\n                    // No usable ratio",
     "                if (!hasRatio && rel.CustomSymbolMappings != null\n"
     "                    && rel.CustomSymbolMappings.TryGetValue(symbol, out var fb)\n"
     "                    && rel.PerTickerRatios != null\n"
     "                    && rel.PerTickerRatios.TryGetValue(fb.ToUpper(), out ratio)\n"
     "                    && ratio > 0.0) { hasRatio = true; }\n"
     "                if (!hasRatio)\n                {\n                    // No usable ratio"),

    # --- slice 1's validation must still apply on the shared path ---
    ("a negative ratio is taken as an absolute value",
     "                    if (!double.IsNaN(ratio) && !double.IsInfinity(ratio) && ratio > 0.0)\n"
     "                    {\n                        hasRatio = true;\n                    }",
     "                    if (!double.IsNaN(ratio) && !double.IsInfinity(ratio) && ratio != 0.0)\n"
     "                    {\n                        ratio = Math.Abs(ratio); hasRatio = true;\n                    }"),

    ("a ratio rounding to zero is silently skipped instead of refused",
     "                    if (rawCopyQty < 1 && !isExit)",
     "                    if (false)"),

    ("a missing rule copies unscaled instead of failing closed on entry",
     "                        isClamped = true;\n                        return 0;\n                    }\n"
     "                    // Exit with no rule: mirror leaderQty",
     "                        isClamped = true;\n                    }\n"
     "                    // Exit with no rule: mirror leaderQty"),

    # --- P1-22 must survive ---
    ("MNQ and MES are declared price comparable",
     '                case "MNQ": return b == "NQ";',
     '                case "MNQ": return b == "NQ" || b == "MES";'),

    ("every pair is declared comparable",
     "            if (string.IsNullOrEmpty(leaderRoot) || string.IsNullOrEmpty(followerRoot)) return false;",
     "            if (string.IsNullOrEmpty(leaderRoot) || string.IsNullOrEmpty(followerRoot)) return false;\n"
     "            return true;"),

    # --- matrix mode must still never auto-convert ---
    ("matrix mode consults the mini/micro auto table",
     "            if (rel == null || (rel.AutoSymbolConversion && rel.SizingMode != CopierSizingMode.PerTickerMatrix))",
     "            if (rel == null || rel.AutoSymbolConversion)"),
]


def run():
    b = subprocess.run(['dotnet', 'build', 'RiskGuardTests.csproj', '-v', 'q', '--nologo'],
                       cwd=os.path.join(REPO, 'ninjatrader-addon'), capture_output=True, text=True)
    if 'Build succeeded' not in b.stdout:
        return 'BUILD FAILED'
    r = subprocess.run(['dotnet', 'run', '--project', 'RiskGuardTests.csproj', '--no-build'],
                       cwd=os.path.join(REPO, 'ninjatrader-addon'), capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith('RESULTS:'):
            return line.strip()
    return 'NO RESULT LINE'


original = open(ENGINE, encoding='utf-8').read()
print('=== baseline ===')
print(' ', run())

survivors = []
for name, old, new in MUTANTS:
    if original.count(old) != 1:
        print('  [SKIP] %s: anchor matched %d times' % (name, original.count(old)))
        survivors.append(name + ' (ANCHOR)')
        continue
    open(ENGINE, 'w', encoding='utf-8', newline='').write(original.replace(old, new))
    res = run()
    killed = 'Failed = 0' not in res
    print('  [%s] %s: %s' % ('KILLED' if killed else 'SURVIVED', name, res))
    if not killed:
        survivors.append(name)

open(ENGINE, 'w', encoding='utf-8', newline='').write(original)
print('\nrestored original;', run())
print('\nSURVIVORS:', survivors if survivors else 'none')
