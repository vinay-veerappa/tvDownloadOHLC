import os

scaffold_structure = {
    "scripts/libs/risk": [
        "__init__.py",
        "trade_policies.py",
        "session_manager.py",
        "account_manager.py",
        "risk_config.py"
    ],
    "scripts/libs/features": [
        "vwap.py",
        "initial_balance.py",
        "bollinger.py",
        "keltner.py",
        "ema.py",
        "internals.py",
        "chop.py",
        "auction.py",
        "acceptance_rejection.py",
        "atr.py"
    ],
    "scripts/trading_framework/core": [
        "mfe_mae.py",
        "execution.py",
        "portfolio_sim.py"
    ],
    "scripts/trading_framework/ml": [
        "prop_eval_mc.py",
        "leakage_guard.py"
    ],
    "scripts/trading_framework/reporting": [
        "tearsheet.py",
        "conditional_tables.py",
        "mfe_mae_report.py",
        "chop_filter_report.py",
        "export.py"
    ],
    "scripts/strategies": [
        "base.py"
    ],
    "scripts/strategies/vwap_reclaim": ["__init__.py"],
    "scripts/strategies/ib_breakout": ["__init__.py"],
    "scripts/strategies/ema_pullback": ["__init__.py"],
    "scripts/strategies/failed_auction": ["__init__.py"],
}

for folder, files in scaffold_structure.items():
    os.makedirs(folder, exist_ok=True)
    for file in files:
        file_path = os.path.join(folder, file)
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                content = f'"""\nScaffolded file for {file}\nPending implementation as per IMPLEMENTATION_SPEC.md\n"""\n'
                f.write(content)

print("Scaffolding complete.")
