"""Mutation battery for slice 3b. Each mutation must turn the suite RED.

A surviving mutant is a test that only looks like coverage.
"""
import os, subprocess, sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

ENGINE = os.path.join(REPO, 'scripts', 'ninjatrader', 'addons', 'TradeCopierEngine.cs')

MUTANTS = [
    ("merge -> rebuild (group)",
     "                grp = existing != null\n                    ? CloneConfig(existing)\n                    : new CopierGroup { GroupName = groupName, LeaderAccountName = \"Sim101\" };",
     "                grp = new CopierGroup { GroupName = groupName, LeaderAccountName = \"Sim101\" };"),

    ("merge -> rebuild (relationship)",
     "                rel = existing != null\n                    ? CloneConfig(existing)\n                    : new CopierRelationship();",
     "                rel = new CopierRelationship();"),

    ("clone removed: malformed request mutates stored group",
     "                    ? CloneConfig(existing)\n                    : new CopierGroup { GroupName = groupName, LeaderAccountName = \"Sim101\" };",
     "                    ? existing\n                    : new CopierGroup { GroupName = groupName, LeaderAccountName = \"Sim101\" };"),

    ("group matrix comparer not re-applied",
     "            grp.PerTickerRatios = EnsureOrdinalIgnoreCase(grp.PerTickerRatios);\n            grp.CustomSymbolMappings = EnsureOrdinalIgnoreCase(grp.CustomSymbolMappings);",
     ""),

    ("explicit null no longer stripped (a null wipes stored config)",
     "                if (prop.Value == null || prop.Value.Type == JTokenType.Null)\n                    normalized.Remove(prop.Name);",
     "                if (false)\n                    normalized.Remove(prop.Name);"),

    ("relationship matrix comparer not re-applied",
     "            rel.PerTickerRatios = EnsureOrdinalIgnoreCase(rel.PerTickerRatios);\n            rel.CustomSymbolMappings = EnsureOrdinalIgnoreCase(rel.CustomSymbolMappings);\n\n            ApplyArmingGate",
     "\n            ApplyArmingGate"),

    ("arming gate ignores whether arming was requested (silently disarms)",
     "            if (armed && armingWasRequested && !confirmLive)",
     "            if (armed && !confirmLive)"),

    ("arming gate dropped entirely (arms without confirmLive)",
     "            if (armed && armingWasRequested && !confirmLive)\n                set(false);",
     "            if (false)\n                set(false);"),

    ("Upsert re-applies its own gate, undoing the preserved armed state",
     "            ApplyArmingGate(grp.ArmedForLive, armingWasRequested, confirmLive, v => grp.ArmedForLive = v);\n            UpsertGroup(grp, true);",
     "            ApplyArmingGate(grp.ArmedForLive, armingWasRequested, confirmLive, v => grp.ArmedForLive = v);\n            UpsertGroup(grp, confirmLive);"),

    ("`followers` spelling dropped",
     "            if (normalized[\"FollowerAccounts\"] == null && req[\"followers\"] is JArray followers)\n                normalized[\"FollowerAccounts\"] = followers;",
     ""),

    ("unknown-enum stripping dropped (a bad sizingMode should not wipe the config)",
     "            return RemoveUnknownEnums(normalized, targetType);",
     "            return normalized;"),
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
        print(f'  [SKIP] {name}: anchor matched {original.count(old)} times')
        survivors.append(name + ' (ANCHOR)')
        continue
    open(ENGINE, 'w', encoding='utf-8', newline='').write(original.replace(old, new))
    res = run()
    killed = 'Failed = 0' not in res
    print(f'  [{"KILLED" if killed else "SURVIVED"}] {name}: {res}')
    if not killed:
        survivors.append(name)

open(ENGINE, 'w', encoding='utf-8', newline='').write(original)
print('\nrestored original;', run())
print('\nSURVIVORS:', survivors if survivors else 'none')
