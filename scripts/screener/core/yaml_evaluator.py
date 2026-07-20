"""
yaml_evaluator.py
=================
Declarative YAML strategy evaluator engine.
Loads strategy definitions from YAML files and evaluates vectorized Pandas expressions.
"""
import os
import hashlib
from typing import Dict, Any, List, Optional
import pandas as pd

try:
    import yaml
except ImportError:
    yaml = None


def get_file_config_hash(file_path: str) -> str:
    """Computes SHA256 config hash of the strategy YAML file for reproducibility."""
    if not os.path.exists(file_path):
        return "UNKNOWN_HASH"
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def load_yaml_strategy(file_path: str) -> Dict[str, Any]:
    """Loads a strategy YAML definition file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Strategy file not found: {file_path}")

    if yaml is not None:
        with open(file_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            content["config_hash"] = get_file_config_hash(file_path)
            return content

    # Minimal fallback parser if pyyaml is missing
    config = {
        "strategy_id": os.path.basename(file_path).replace(".yaml", ""),
        "version": "1.0.0",
        "rules": [],
        "config_hash": get_file_config_hash(file_path)
    }
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if "strategy_id:" in line:
                config["strategy_id"] = line.split(":")[-1].strip().strip('"\'')
            elif "expression:" in line:
                expr = line.split(":", 1)[-1].strip().strip('"\'')
                config["rules"].append({"name": "rule", "expression": expr})
    return config


def evaluate_strategy_file(file_path: str, feature_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Evaluates rules from a strategy YAML file against a feature matrix DataFrame.
    Returns DataFrame containing matched rows (latest session per ticker).
    """
    if feature_matrix is None or feature_matrix.empty:
        return pd.DataFrame()

    strategy = load_yaml_strategy(file_path)
    rules = strategy.get("rules", [])
    
    # Take the latest row for each ticker
    if "ticker" in feature_matrix.columns:
        latest = feature_matrix.groupby("ticker").last().reset_index()
    else:
        latest = feature_matrix.iloc[[-1]].copy()

    filtered = latest.copy()

    # Apply YAML rules vectorially
    for rule in rules:
        expr = rule.get("expression")
        rule_name = rule.get("name", "rule")
        if not expr:
            continue
        try:
            filtered = filtered.query(expr)
            if filtered.empty:
                break
        except Exception as e:
            import logging
            logging.getLogger("screener_yaml").error(
                f"Rule evaluation failed for '{rule_name}' ('{expr}'): {e}. Excluding unvalidated candidates."
            )
            filtered = filtered.iloc[0:0]
            break

    if not filtered.empty:
        filtered = filtered.copy()
        filtered["strategy_id"] = strategy.get("strategy_id", "custom")
        filtered["strategy_version"] = strategy.get("version", "1.0.0")
        filtered["config_hash"] = strategy.get("config_hash", "00000000")

    return filtered

