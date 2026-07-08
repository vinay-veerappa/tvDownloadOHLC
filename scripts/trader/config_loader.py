"""Config loader for the Narrative Engine v2.

Loads `narrative_stats.yaml` once at startup and caches it.
All modules import from here: `from scripts.trader.config_loader import get_config`
"""
from __future__ import annotations

import logging
from pathlib import Path
from functools import lru_cache

import yaml

log = logging.getLogger(__name__)
_CONFIG_PATH = Path(__file__).parent / "config" / "narrative_stats.yaml"


@lru_cache(maxsize=1)
def get_config() -> dict:
    """Load and cache the narrative stats config. Fails fast if missing required keys."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {_CONFIG_PATH}")
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    _validate(cfg)
    log.debug("[config] Loaded v%s", cfg.get("version", "?"))
    return cfg


def _validate(cfg: dict) -> None:
    """Fail fast if required top-level keys are missing."""
    required = [
        "aln_patterns", "rth_breaks", "herman_pre_ny", "vix_regimes",
        "vvix_regimes", "day_types", "killzones", "confluence",
    ]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f"Config missing required keys: {missing}")


def get_section(key: str) -> dict:
    """Get a single config section."""
    return get_config().get(key, {})