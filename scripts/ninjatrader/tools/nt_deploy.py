#!/usr/bin/env python3
"""
NinjaTrader 8 Strategy Deployment CLI

Copies C# strategies and indicators from repository to NinjaTrader 8 Custom directories.

Usage:
    python -m scripts.ninjatrader.tools.nt_deploy Bandits8020Bot
    python -m scripts.ninjatrader.tools.nt_deploy --all
"""

import sys
import shutil
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

NT8_CUSTOM_DIR = Path(r"C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom")
NT8_STRATEGIES_DIR = NT8_CUSTOM_DIR / "Strategies"
NT8_INDICATORS_DIR = NT8_CUSTOM_DIR / "Indicators"

REPO_ROOT = Path(__file__).resolve().parents[3]
REPO_STRATEGIES_DIR = REPO_ROOT / "scripts" / "ninjatrader" / "strategies"
REPO_INDICATORS_DIR = REPO_ROOT / "scripts" / "ninjatrader" / "indicators"

def deploy_strategy(strategy_name: str) -> bool:
    NT8_STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Search in repository strategies
    matches = list(REPO_STRATEGIES_DIR.rglob(f"{strategy_name}.cs"))
    if not matches:
        matches = list(REPO_STRATEGIES_DIR.rglob(f"*{strategy_name}*.cs"))
        
    if not matches:
        print(f"❌ Strategy '{strategy_name}' not found in {REPO_STRATEGIES_DIR}")
        return False
        
    source_file = matches[0]
    dest_file = NT8_STRATEGIES_DIR / source_file.name
    
    # Also deploy base classes if they exist
    base_classes = list(REPO_STRATEGIES_DIR.rglob("RiskManagerBase.cs"))
    for base in base_classes:
        base_dest = NT8_STRATEGIES_DIR / base.name
        shutil.copy2(base, base_dest)
        print(f"  Synced Base Class: {base.name} -> {base_dest}")
        
    shutil.copy2(source_file, dest_file)
    print(f"✅ Successfully Deployed: {source_file.name}")
    print(f"   Source : {source_file}")
    print(f"   Dest   : {dest_file}")
    print(f"   Size   : {dest_file.stat().st_size:,d} bytes")
    return True

def deploy_all():
    print("Deploying all repository strategies and base classes to NT8...")
    cs_files = list(REPO_STRATEGIES_DIR.rglob("*.cs"))
    count = 0
    for f in cs_files:
        dest = NT8_STRATEGIES_DIR / f.name
        shutil.copy2(f, dest)
        count += 1
    print(f"✅ Deployed {count} strategy files to {NT8_STRATEGIES_DIR}")

def main():
    parser = argparse.ArgumentParser(description="Deploy NinjaScript strategies to NinjaTrader 8 Custom folder")
    parser.add_argument("strategy", nargs="?", default="Bandits8020Bot", help="Name of strategy (e.g. Bandits8020Bot)")
    parser.add_argument("--all", action="store_true", help="Deploy all strategies")
    args = parser.parse_args()

    if args.all:
        deploy_all()
    else:
        deploy_strategy(args.strategy)

if __name__ == "__main__":
    main()
