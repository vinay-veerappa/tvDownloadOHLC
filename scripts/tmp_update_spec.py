import re

filepath = r"c:\Users\vinay\tvDownloadOHLC\docs\trading_system\IMPLEMENTATION_SPEC.md"

with open(filepath, "r", encoding="utf-8") as f:
    text = f.read()

replacements = [
    (r"lib/data", r"scripts/libs/data"),
    (r"lib\.data", r"scripts.libs.data"),
    (r"lib/features", r"scripts/libs/features"),
    (r"lib\.features", r"scripts.libs.features"),
    (r"lib/regime", r"scripts/libs/regime"),
    (r"lib\.regime", r"scripts.libs.regime"),
    (r"lib/risk", r"scripts/libs/risk"),
    (r"lib\.risk", r"scripts.libs.risk"),
    (r"lib/reporting", r"scripts/trading_framework/reporting"),
    (r"lib\.reporting", r"scripts.trading_framework.reporting"),
    (r"lib/ml", r"scripts/trading_framework/ml"),
    (r"lib\.ml", r"scripts.trading_framework.ml"),
    (r"lib/backtest", r"scripts/trading_framework/core"),
    (r"lib\.backtest", r"scripts.trading_framework.core"),
    (r"lib/config_loader\.py", r"scripts/trading_framework/config/config_loader.py"),
    (r"lib\.config_loader", r"scripts.trading_framework.config.config_loader"),
    (r"strategies/", r"scripts/strategies/"),
    (r"from strategies", r"from scripts.strategies"),
    (r"File: `config/default\.yaml`", r"File: `scripts/trading_framework/config/sessions.yaml`"),
    (r"path: str = \"config/default\.yaml\"", r"path: str = \"scripts/trading_framework/config/sessions.yaml\"")
]

for old, new in replacements:
    text = re.sub(old, new, text)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(text)

print(f"Updated {filepath} with global replacements.")
