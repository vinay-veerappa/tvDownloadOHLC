#!/usr/bin/env python3
"""
sync_nt8_strategies.py
=======================

Sync NinjaScript .cs files from the repo source-of-truth to the
NinjaTrader 8 live compilation folder.

Source (repo, git-tracked):
    scripts/ninjatrader/strategies/**/*.cs  ->  %USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/Strategies/Vinay/
    scripts/ninjatrader/indicators/**/*.cs  ->  %USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/Indicators/
    scripts/ninjatrader/shared/*.cs         ->  %USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/Strategies/Vinay/  (shared classes compile with strategies)

Destination (NT8 live, untracked):
    %USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/Strategies/Vinay/
    %USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/Indicators/

NOT the AddOns. The RiskGuard/TradeCopier/McpBridge addons left this repo in the
2026-08-12 split and deploy from their own repos:
    nt8-riskguard    ->  python tools/sync_nt8.py
    nt8-mcp-bridge   ->  python tools/deploy.py   (deploys the bridge AND its
                         vendored core; deploying either alone fails the whole
                         NT8 Custom assembly)
Running --only addons here now exits with an error rather than silently doing
nothing, because a deploy command that reports success while deploying nothing is
how a stale addon stays live.

Usage:
    python scripts/utils/sync_nt8_strategies.py          # sync all
    python scripts/utils/sync_nt8_strategies.py --verify  # show drift status only
    python scripts/utils/sync_nt8_strategies.py --dry-run # show what would be copied

This script is the SINGLE source-of-truth sync mechanism. Never manually copy
.cs files to the NT8 folder — always run this script after editing NinjaScript code.
"""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import os
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
NT8_SRC = REPO_ROOT / "scripts" / "ninjatrader"

# Strategy source dirs — all subfolders sync to a single flat NT8 Strategies/Vinay/
STRATEGIES_SRC_DIRS = [
    ("base",           NT8_SRC / "strategies" / "base"),
    ("ib_breakout",    NT8_SRC / "strategies" / "ib_breakout"),
    ("ema_pullback",   NT8_SRC / "strategies" / "ema_pullback"),
    ("failed_auction", NT8_SRC / "strategies" / "failed_auction"),
    ("vwap_reclaim",   NT8_SRC / "strategies" / "vwap_reclaim"),
]

# Shared source dir — classes used by both strategies and indicators
SHARED_SRC = NT8_SRC / "shared"

NT8_HOME = Path(os.environ.get("USERPROFILE", "")) / "Documents" / "NinjaTrader 8" / "bin" / "Custom"
STRATEGIES_DST = NT8_HOME / "Strategies" / "Vinay"  # NT8 expects this folder name
INDICATORS_ROOT = NT8_HOME / "Indicators"

# Indicator source dirs, each with its OWN destination subfolder.
#
# ⚠️ THIS USED TO BE A FLAT `Indicators/` FOR ALL OF THEM, AND IT WAS AN ARMED TRAP.
# Measured 2026-08-14: all 23 repo indicators are already deployed, byte-identical, at
# `Indicators/Vinay/` (9) and `Indicators/RedTail/` (14) — put there by hand, in the same
# per-vendor style as the other eleven subfolders NT8 already has (LuxAlgo2/, BTMM/, Gemify/…).
# The tool looked only at top-level `Indicators/*.cs`, found nothing, and reported all 23 as
# needing deployment. Running it WITHOUT --verify would have copied every one into
# `Indicators/`, next to the identical copy already in its subfolder.
#
# That is 23 duplicate class definitions. The measured consequence of exactly two such copies
# (RiskManagerBase.cs, earlier the same day) was one CS0101 followed by 496 x CS0229 — which
# fails the compile of the ENTIRE NT8 Custom assembly, so EVERY addon stops loading, RiskGuard
# included. NT8 then keeps serving the last good assembly, so nt_health reads healthy and the
# only symptom is a deploy that has no effect.
#
# So the destination is now per-source, matching where the files actually live. Strategies were
# always right (Strategies/Vinay/); only the indicator half was flat.
INDICATOR_SRC_DIRS = [
    ("vinay",        NT8_SRC / "indicators" / "vinay",       INDICATORS_ROOT / "Vinay"),
    ("redtail",      NT8_SRC / "indicators" / "redtail",     INDICATORS_ROOT / "RedTail"),
    ("third_party",  NT8_SRC / "indicators" / "third_party", INDICATORS_ROOT / "ThirdParty"),
]


def file_hash(path: Path) -> str:
    """MD5 of file content, normalised for drift comparison.

    Line endings are normalised to LF and a UTF-8 BOM is stripped before
    hashing. Files copied into the NT8 tree by other tools (or edited in NT8's
    own editor) come back CRLF while the repo keeps LF, and a raw byte hash
    then reports every single file as drifted.

    That is not hypothetical: it is exactly what happened on 2026-08-07, when a
    plain diff of the deployed addons showed 8216 changed lines on a 4108-line
    file. The files were byte-identical apart from carriage returns, but the
    false alarm was written into the deployment runbook as "the deployed
    sources have diverged" and cost real time to disprove. A drift check that
    cries wolf on every file teaches you to ignore it, which is worse than
    having no check at all.

    C# is insensitive to which one it gets, so a pure line-ending difference is
    not drift and must not trigger a redeploy.
    """
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.md5(data).hexdigest()


def sync_dir(src_dir: Path, dst_dir: Path, label: str, dry_run: bool = False, verify: bool = False) -> dict:
    """
    Sync all .cs files from src_dir to dst_dir.
    Multiple source subfolders may sync to the same dst_dir (e.g. all strategies
    go to Strategies/Vinay/). Orphan detection is handled by the caller, not here.
    Returns a dict with 'copied', 'identical', 'missing_dst' lists.
    """
    result = {"copied": [], "identical": [], "missing_dst": []}

    if not src_dir.exists():
        print(f"  [ERROR] Source dir does not exist: {src_dir}")
        return result

    dst_dir.mkdir(parents=True, exist_ok=True)

    src_files = sorted(src_dir.glob("*.cs"))

    for src_file in src_files:
        dst_file = dst_dir / src_file.name

        if not dst_file.exists():
            result["missing_dst"].append(src_file.name)
            if not verify:
                if not dry_run:
                    shutil.copy2(src_file, dst_file)
                    print(f"  [COPIED]  {src_file.name}  (new file)")
                else:
                    print(f"  [DRY-RUN] {src_file.name}  (would copy — new file)")
            else:
                # These were counted in the summary as "differ" and printed NOWHERE, so
                # --verify reported 23 files it never named and the only way to learn which
                # was to reimplement the comparison by hand. A count is not a report.
                print(f"  [MISSING] {src_file.name}  (in repo, NOT in NT8)")
            continue

        # Compare hashes
        if file_hash(src_file) == file_hash(dst_file):
            result["identical"].append(src_file.name)
            if verify:
                print(f"  [OK]      {src_file.name}")
        else:
            result["copied"].append(src_file.name)
            if not verify:
                if not dry_run:
                    shutil.copy2(src_file, dst_file)
                    print(f"  [SYNCED]  {src_file.name}  (content differed)")
                else:
                    print(f"  [DRY-RUN] {src_file.name}  (would sync — content differs)")
            else:
                print(f"  [DRIFT]   {src_file.name}  (source differs from NT8)")

    return result


def main():
    parser = argparse.ArgumentParser(description="Sync repo strategy .cs files to NT8 live folder.")
    parser.add_argument("--verify", action="store_true", help="Show drift status without copying.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without copying.")
    parser.add_argument(
        "--only",
        choices=["strategies", "indicators", "addons"],
        action="append",
        help="Limit the sync to one area (repeatable). Without it, everything syncs. "
             "Deploying the addons should not also push unrelated indicators into a "
             "live NT8 that is mid-session, so scope deliberate deployments.",
    )
    args = parser.parse_args()

    if args.only and "addons" in args.only:
        print("[ERROR] The addons no longer live in this repo (2026-08-12 split).")
        print("        Deploy them from their own repos:")
        print("          nt8-riskguard:   python tools/sync_nt8.py")
        print("          nt8-mcp-bridge:  python tools/deploy.py")
        sys.exit(2)

    scopes = set(args.only) if args.only else {"strategies", "indicators"}

    print("=" * 70)
    print("NT8 NinjaScript Sync — repo source -> NT8 live compilation folder")
    print("=" * 70)
    print(f"  Source:   {NT8_SRC}")
    print(f"  NT8 dest: {NT8_HOME}")
    print()

    if not NT8_HOME.exists():
        print(f"[ERROR] NT8 Custom folder not found: {NT8_HOME}")
        print("        Is NinjaTrader 8 installed on this machine?")
        sys.exit(1)

    mode = "VERIFY" if args.verify else "DRY-RUN" if args.dry_run else "SYNC"
    print(f"Mode: {mode}")
    print()

    all_results = []

    # ── Strategy files: all subfolders -> NT8 Strategies/Vinay/ ──
    # NT8 compiles all .cs in Strategies/Vinay/ together, so base classes,
    # IB strategies, and individual bots all land in the same flat folder.
    all_strategy_src_names = set()
    if "strategies" in scopes:
        for label, src_dir in STRATEGIES_SRC_DIRS:
            print(f"[Strategies/{label}/] {src_dir} -> {STRATEGIES_DST}")
            r = sync_dir(src_dir, STRATEGIES_DST, label, args.dry_run, args.verify)
            all_results.append(("Strategies/" + label, r))
            all_strategy_src_names.update(f.name for f in src_dir.glob("*.cs"))
            print()

        # ── Shared files: shared classes -> NT8 Strategies/Vinay/ (compiled with strategies) ──
        if SHARED_SRC.exists():
            print(f"[Shared/] {SHARED_SRC} -> {STRATEGIES_DST}")
            r = sync_dir(SHARED_SRC, STRATEGIES_DST, "shared", args.dry_run, args.verify)
            all_results.append(("Shared", r))
            all_strategy_src_names.update(f.name for f in SHARED_SRC.glob("*.cs"))
            print()

    # ── Indicator files: each source subfolder -> its OWN NT8 Indicators/<Name>/ ──
    # NT8 compiles every .cs under Indicators/ recursively, so the subfolder is organisation,
    # not scoping — which is exactly why a second copy in a DIFFERENT folder still collides.
    # See INDICATOR_SRC_DIRS for what a flat destination did here.
    all_indicator_src_names = set()
    indicator_dsts = []
    if "indicators" in scopes:
        for label, src_dir, dst_dir in INDICATOR_SRC_DIRS:
            if not src_dir.exists():
                continue
            print(f"[Indicators/{label}/] {src_dir} -> {dst_dir}")
            r = sync_dir(src_dir, dst_dir, label, args.dry_run, args.verify)
            all_results.append(("Indicators/" + label, r))
            all_indicator_src_names.update(f.name for f in src_dir.glob("*.cs"))
            indicator_dsts.append(dst_dir)
            print()

    # ── Orphan detection (aggregate): files in NT8 but not in ANY source ──
    # Only meaningful for areas actually scanned this run; a scoped-out area has
    # an empty source set, which would report every deployed file as an orphan.
    # ⚠️ Compared CASE-INSENSITIVELY. Windows resolves `EMAPullbackBot.cs` and
    # `EMAPullBackBot.cs` to the SAME file, so an exact-name set difference reported the
    # deployed copy as an orphan on the line after reporting it [OK] — one file, two verdicts.
    def lower(names):
        return {n.lower() for n in names}

    strategy_orphans = []
    if "strategies" in scopes and STRATEGIES_DST.exists():
        src_lower = lower(all_strategy_src_names)
        strategy_orphans = sorted(f.name for f in STRATEGIES_DST.glob("*.cs")
                                  if f.name.lower() not in src_lower)

    # Only the folders this tool OWNS. The other eleven subfolders under Indicators/ are
    # vendor packs (LuxAlgo2/, BTMM/, Gemify/…) and the 210 files at top level are NT8's own
    # samples plus hand-installed third-party indicators — none of it is repo-owned, so
    # calling it "orphaned" would be noise that trains you to ignore the list.
    indicator_orphans = []
    if "indicators" in scopes:
        src_lower = lower(all_indicator_src_names)
        for dst_dir in indicator_dsts:
            if not dst_dir.exists():
                continue
            indicator_orphans.extend(
                f"{dst_dir.name}/{f.name}" for f in sorted(dst_dir.glob("*.cs"))
                if f.name.lower() not in src_lower)

    # ── Summary ──
    print()
    print("=" * 70)
    total_synced = sum(len(r["copied"]) for _, r in all_results)
    total_copied = sum(len(r["missing_dst"]) for _, r in all_results)
    total_identical = sum(len(r["identical"]) for _, r in all_results)
    total_drift = total_synced + total_copied
    total_orphans = len(strategy_orphans) + len(indicator_orphans)

    # ⚠️ The summary used to say "N file(s) differ" for a total that is `synced + missing_dst`.
    # In --verify nothing syncs, so every one of them was actually MISSING FROM NT8 — a
    # different fact with a different fix, described by a word that means neither.
    verify_exit = 0
    if args.verify:
        if total_drift == 0:
            print(f"  ALL IN SYNC ({total_identical} files identical, {total_orphans} orphan(s) in NT8)")
        else:
            print(f"  DRIFT DETECTED: {total_copied} missing from NT8, {total_synced} content-differs, "
                  f"{total_identical} identical, {total_orphans} orphan(s)")
            # ⚠️ sys.exit(1) USED TO BE HERE, above the orphan block below — so the list was
            # unreachable whenever there was drift, and 23 permanently-missing files guaranteed
            # drift on every run. The tool announced "212 orphan(s)" and exited before naming
            # one, for as long as it has existed. Exit AFTER the report, never before it.
            verify_exit = 1
    else:
        if args.dry_run:
            print(f"  DRY-RUN: {total_drift} file(s) would be synced, {total_identical} already identical")
        else:
            print(f"  DONE: {total_synced} synced, {total_copied} copied (new), {total_identical} already identical")

    if total_orphans > 0:
        print(f"  Orphan files in NT8 (in a folder this tool owns, but not in repo source):")
        for name in strategy_orphans:
            print(f"    Strategies/Vinay/{name}")
        for name in indicator_orphans:
            print(f"    Indicators/{name}")

    print("=" * 70)
    if verify_exit:
        sys.exit(verify_exit)


if __name__ == "__main__":
    main()