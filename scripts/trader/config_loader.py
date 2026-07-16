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


def get_llm_config() -> dict:
    """Return the LLM defaults section from `narrative_stats.yaml`.

    Single source of truth for which Ollama model the narrative
    chains use. Both `daily_narrative.py` and `trader_narrative.py`
    read their `DEFAULT_MODEL` and `FALLBACK_MODEL` from here
    (audit §2.6). The two chains previously had drifted to
    different defaults (`deepseek-v4-pro:cloud` vs `gemma4:latest`),
    producing inconsistent voice and JSON adherence.

    Expected shape (see `narrative_stats.yaml::llm`):
        llm:
          default_model: "gemma4:latest"
          default_trader_model: "gemma4:latest"
          fallback_model: "gemma4:31b-cloud"
          local_fallback_model: "gemma4:latest"

    Returns an empty dict if the `llm` section is missing. Callers
    are expected to fall back to hardcoded defaults in that case
    (see `daily_narrative.DEFAULT_MODEL` and friends). We do NOT
    raise on missing-section here because the config loader is
    used at module-import time and a missing key should not take
    down the whole narrative chain — the fallbacks exist for
    exactly that reason.
    """
    return get_section("llm")