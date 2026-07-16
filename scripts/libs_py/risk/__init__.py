"""
Scaffolded file for __init__.py
Pending implementation as per IMPLEMENTATION_SPEC.md
"""

# Placeholder re-exports for the narrative sub-package (added in v0.1.0,
# see scripts.libs_py.risk.narrative).  Importing from the parent
# `scripts.libs_py.risk` is supported so callers can do:
#
#     from scripts.libs_py.risk import validate_trade_plan
#
# without needing to know about the sub-package layout.
from .narrative import (
    validate_trade_plan,
    get_risk_config,
    reset_cache,
    RiskConfig,
    AccountPhase,
    InstrumentSpec,
    ValidatorRules,
)
