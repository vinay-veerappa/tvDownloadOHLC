import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import schwab


INDEX_SYMBOL_ALIASES = {
    "SPX": "$SPX",
    "NDX": "$NDX",
    "RUT": "$RUT",
    "VIX": "$VIX",
}



def normalize_option_chain_symbol(symbol: str) -> str:
    return INDEX_SYMBOL_ALIASES.get(symbol.upper(), symbol)


def find_expiration_key(option_map: dict[str, Any], target_date: date) -> str | None:
    target = target_date.strftime("%Y-%m-%d")
    for exp_key in option_map.keys():
        if exp_key.startswith(target):
            return exp_key
    return None


def first_contracts_for_expiration(option_map: dict[str, Any], expiration_key: str) -> list[dict[str, Any]]:
    if expiration_key not in option_map:
        return []
    return [contracts[0] for contracts in option_map[expiration_key].values() if contracts]


def get_option_mark(option_data: dict[str, Any]) -> float:
    mark = option_data.get("mark")
    if mark is not None:
        return float(mark)
    return float(option_data.get("bid", 0) + option_data.get("ask", 0)) / 2.0


def get_option_iv(option_data: dict[str, Any]) -> float:
    vol = option_data.get("volatility")
    if vol is None:
        return 0.0
    return float(vol)


def get_greeks(option_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "delta": option_data.get("delta"),
        "gamma": option_data.get("gamma"),
        "theta": option_data.get("theta"),
        "vega": option_data.get("vega"),
        "rho": option_data.get("rho"),
        "volatility": option_data.get("volatility"),
    }
