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

def _find_dest_path(base_dir: Path, filename: str) -> Path:
    # Check if file exists in a subfolder first (e.g. Vinay, RedTail)
    existing = list(base_dir.rglob(filename))
    if existing:
        return existing[0]
    # Default to Vinay subfolder if it exists
    vinay_dir = base_dir / "Vinay"
    if vinay_dir.exists():
        return vinay_dir / filename
    return base_dir / filename

def deploy_strategy(strategy_name: str) -> bool:
    NT8_STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    
    matches = list(REPO_STRATEGIES_DIR.rglob(f"{strategy_name}.cs"))
    if not matches:
        matches = list(REPO_STRATEGIES_DIR.rglob(f"*{strategy_name}*.cs"))
        
    if not matches:
        print(f"❌ Strategy '{strategy_name}' not found in {REPO_STRATEGIES_DIR}")
        return False
        
    source_file = matches[0]
    dest_file = _find_dest_path(NT8_STRATEGIES_DIR, source_file.name)
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Also deploy base classes if they exist
    base_classes = list(REPO_STRATEGIES_DIR.rglob("RiskManagerBase.cs"))
    for base in base_classes:
        base_dest = _find_dest_path(NT8_STRATEGIES_DIR, base.name)
        shutil.copy2(base, base_dest)
        print(f"  Synced Base Class: {base.name} -> {base_dest}")
        
    shutil.copy2(source_file, dest_file)
    print(f"✅ Successfully Deployed: {source_file.name}")
    print(f"   Source : {source_file}")
    print(f"   Dest   : {dest_file}")
    print(f"   Size   : {dest_file.stat().st_size:,d} bytes")
    return True

def deploy_all():
    print("Deploying all repository strategies, indicators, and base classes to NT8...")
    NT8_STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    NT8_INDICATORS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Deploy Strategies
    strat_files = list(REPO_STRATEGIES_DIR.rglob("*.cs"))
    s_count = 0
    for f in strat_files:
        dest = _find_dest_path(NT8_STRATEGIES_DIR, f.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        s_count += 1
    print(f"✅ Deployed {s_count} strategy files to NT8")

    # Deploy Indicators
    ind_files = list(REPO_INDICATORS_DIR.rglob("*.cs"))
    i_count = 0
    for f in ind_files:
        dest = _find_dest_path(NT8_INDICATORS_DIR, f.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        i_count += 1
    print(f"✅ Deployed {i_count} indicator files to NT8")


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
