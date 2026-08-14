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

# Indicator source dirs — all subfolders sync to a single flat NT8 Indicators/
INDICATOR_SRC_DIRS = [
    ("vinay",        NT8_SRC / "indicators" / "vinay"),
    ("redtail",      NT8_SRC / "indicators" / "redtail"),
    ("third_party",  NT8_SRC / "indicators" / "third_party"),
]

NT8_HOME = Path(os.environ.get("USERPROFILE", "")) / "Documents" / "NinjaTrader 8" / "bin" / "Custom"
STRATEGIES_DST = NT8_HOME / "Strategies" / "Vinay"  # NT8 expects this folder name
INDICATORS_DST = NT8_HOME / "Indicators"


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

    # ── Indicator files: all subfolders -> NT8 Indicators/ ──
    # NT8 compiles all .cs in Indicators/ together. All indicator subfolders
    # (vinay/, redtail/, third_party/) sync to the same flat Indicators/ folder.
    all_indicator_src_names = set()
    if "indicators" in scopes:
        for label, src_dir in INDICATOR_SRC_DIRS:
            if not src_dir.exists():
                continue
            print(f"[Indicators/{label}/] {src_dir} -> {INDICATORS_DST}")
            r = sync_dir(src_dir, INDICATORS_DST, label, args.dry_run, args.verify)
            all_results.append(("Indicators/" + label, r))
            all_indicator_src_names.update(f.name for f in src_dir.glob("*.cs"))
            print()
            print()

    # ── Orphan detection (aggregate): files in NT8 but not in ANY source ──
    # Only meaningful for areas actually scanned this run; a scoped-out area has
    # an empty source set, which would report every deployed file as an orphan.
    strategy_orphans = []
    if "strategies" in scopes and STRATEGIES_DST.exists():
        dst_names = set(f.name for f in STRATEGIES_DST.glob("*.cs"))
        strategy_orphans = sorted(dst_names - all_strategy_src_names)

    indicator_orphans = []
    if "indicators" in scopes and INDICATORS_DST.exists():
        ind_dst_names = set(f.name for f in INDICATORS_DST.glob("*.cs"))
        indicator_orphans = sorted(ind_dst_names - all_indicator_src_names)

    # ── Summary ──
    print()
    print("=" * 70)
    total_synced = sum(len(r["copied"]) for _, r in all_results)
    total_copied = sum(len(r["missing_dst"]) for _, r in all_results)
    total_identical = sum(len(r["identical"]) for _, r in all_results)
    total_drift = total_synced + total_copied
    total_orphans = len(strategy_orphans) + len(indicator_orphans)

    if args.verify:
        if total_drift == 0:
            print(f"  ALL IN SYNC ({total_identical} files identical, {total_orphans} orphan(s) in NT8)")
        else:
            print(f"  DRIFT DETECTED: {total_drift} file(s) differ, {total_identical} identical, {total_orphans} orphan(s)")
            sys.exit(1)
    else:
        if args.dry_run:
            print(f"  DRY-RUN: {total_drift} file(s) would be synced, {total_identical} already identical")
        else:
            print(f"  DONE: {total_synced} synced, {total_copied} copied (new), {total_identical} already identical")

    if total_orphans > 0:
        print(f"  Orphan files in NT8 (not in repo source):")
        for name in strategy_orphans:
            print(f"    Strategies/Vinay/{name}")
        for name in indicator_orphans:
            print(f"    Indicators/{name}")

    print("=" * 70)


if __name__ == "__main__":
    main()