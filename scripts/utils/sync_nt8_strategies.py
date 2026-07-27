#!/usr/bin/env python3
"""
sync_nt8_strategies.py
=======================

Sync strategy and addon .cs files from the repo source-of-truth to the
NinjaTrader 8 live compilation folder.

Source (repo, git-tracked):
    ninjatrader-addon/Strategies/Vinay/*.cs  ->  %USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/Strategies/Vinay/
    ninjatrader-addon/*.cs (addon root)      ->  %USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/AddOns/

Destination (NT8 live, untracked):
    %USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/Strategies/Vinay/
    %USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/AddOns/

Usage:
    python scripts/utils/sync_nt8_strategies.py          # sync all
    python scripts/utils/sync_nt8_strategies.py --verify  # show drift status only
    python scripts/utils/sync_nt8_strategies.py --dry-run # show what would be copied

This script is the SINGLE source-of-truth sync mechanism. Never manually copy
.cs files to the NT8 folder — always run this script after editing strategy code.
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
NT8_SRC = REPO_ROOT / "scripts" / "strategies" / "nt8"
STRATEGIES_SRC_DIRS = [
    ("base",          NT8_SRC / "base"),
    ("ib_breakout",   NT8_SRC / "ib_breakout"),
    ("ema_pullback",  NT8_SRC / "ema_pullback"),
    ("failed_auction",NT8_SRC / "failed_auction"),
    ("vwap_reclaim",  NT8_SRC / "vwap_reclaim"),
]
ADDONS_SRC = NT8_SRC / "addons"

NT8_HOME = Path(os.environ.get("USERPROFILE", "")) / "Documents" / "NinjaTrader 8" / "bin" / "Custom"
STRATEGIES_DST = NT8_HOME / "Strategies" / "Vinay"  # NT8 expects this folder name
ADDONS_DST = NT8_HOME / "AddOns"


def file_hash(path: Path) -> str:
    """MD5 hash of file content for drift comparison."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


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


def sync_addon_files(dry_run: bool, verify: bool) -> dict:
    """
    Sync addon .cs files (copy trading + riskguard) from scripts/strategies/nt8/addons/
    to NT8 AddOns/ folder. This is for the RiskGuard, TradeCopier, McpBridge, etc.
    that are NT8 AddOns (not strategies).
    """
    result = {"copied": [], "identical": [], "missing_dst": [], "missing_src": [], "extra_dst": []}

    if not ADDONS_DST.exists():
        print(f"  [ERROR] NT8 AddOns dir does not exist: {ADDONS_DST}")
        return result

    if not ADDONS_SRC.exists():
        print(f"  [ERROR] Source addons dir does not exist: {ADDONS_SRC}")
        return result

    src_files = sorted(ADDONS_SRC.glob("*.cs"))
    dst_files = set(f.name for f in ADDONS_DST.glob("*.cs"))
    src_names = set(f.name for f in src_files)

    for name in sorted(dst_files - src_names):
        result["extra_dst"].append(name)

    for src_file in src_files:
        dst_file = ADDONS_DST / src_file.name

        if not dst_file.exists():
            result["missing_dst"].append(src_file.name)
            if not verify:
                if not dry_run:
                    shutil.copy2(src_file, dst_file)
                    print(f"  [COPIED]  {src_file.name}  (new file in AddOns/)")
                else:
                    print(f"  [DRY-RUN] {src_file.name}  (would copy to AddOns/)")
            continue

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
                    print(f"  [DRY-RUN] {src_file.name}  (would sync)")
            else:
                print(f"  [DRIFT]   {src_file.name}  (source differs from NT8)")

    return result


def main():
    parser = argparse.ArgumentParser(description="Sync repo strategy .cs files to NT8 live folder.")
    parser.add_argument("--verify", action="store_true", help="Show drift status without copying.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without copying.")
    args = parser.parse_args()

    print("=" * 70)
    print("NT8 Strategy Sync — repo source -> NT8 live compilation folder")
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
    for label, src_dir in STRATEGIES_SRC_DIRS:
        print(f"[Strategies/{label}/] {src_dir} -> {STRATEGIES_DST}")
        r = sync_dir(src_dir, STRATEGIES_DST, label, args.dry_run, args.verify)
        all_results.append(("Strategies/" + label, r))
        all_strategy_src_names.update(f.name for f in src_dir.glob("*.cs"))
        print()

    # ── AddOns: copy trading + riskguard -> NT8 AddOns/ ──
    print(f"[AddOns/] {ADDONS_SRC} -> {ADDONS_DST}")
    addon_result = sync_addon_files(args.dry_run, args.verify)
    all_results.append(("AddOns", addon_result))

    # ── Orphan detection (aggregate): files in NT8 but not in ANY source ──
    strategy_orphans = []
    if STRATEGIES_DST.exists():
        dst_names = set(f.name for f in STRATEGIES_DST.glob("*.cs"))
        strategy_orphans = sorted(dst_names - all_strategy_src_names)

    addon_orphans = addon_result.get("extra_dst", [])

    # ── Summary ──
    print()
    print("=" * 70)
    total_synced = sum(len(r["copied"]) for _, r in all_results)
    total_copied = sum(len(r["missing_dst"]) for _, r in all_results)
    total_identical = sum(len(r["identical"]) for _, r in all_results)
    total_drift = total_synced + total_copied
    total_orphans = len(strategy_orphans) + len(addon_orphans)

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
        for name in addon_orphans:
            print(f"    AddOns/{name}")

    print("=" * 70)


if __name__ == "__main__":
    main()