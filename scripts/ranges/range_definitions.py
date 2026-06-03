"""
Range Definitions and Standard Presets

Every range type is an instance of RangeDefinition.
Adding a new range requires only a config entry — no code changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RangeDefinition:
    """Atomic descriptor for any time-based range."""

    name: str                              # e.g. "OR_5", "IB_60", "ASIA"
    display_name: str                      # e.g. "5-Min Opening Range"
    start_time: str                        # "HH:MM" ET
    end_time: str                          # "HH:MM" ET
    timezone: str                          = "America/New_York"
    session: str                           = "RTH"    # RTH | ETH | FULL
    formation_field: str                   = "hl"     # "hl" = high/low of all bars
    require_complete: bool                 = True     # skip day if <80% bar count
    extension_levels: List[float]          = field(
        default_factory=lambda: [0.5, 1.0, 1.5, 2.0, 3.0])
    observe_until: Optional[str]           = None     # "16:00" or None → end of session


RANGE_PRESETS: dict[str, RangeDefinition] = {
    # ── Opening Ranges ────────────────────────────────────────────────────────
    "OR_5":  RangeDefinition("OR_5",  "5-Min Opening Range",  "09:30", "09:35"),
    "OR_15": RangeDefinition("OR_15", "15-Min Opening Range", "09:30", "09:45"),
    "OR_30": RangeDefinition("OR_30", "30-Min Opening Range", "09:30", "10:00"),

    # ── Initial Balance ───────────────────────────────────────────────────────
    "IB_30": RangeDefinition("IB_30", "30-Min Initial Balance", "09:30", "10:00"),
    "IB_60": RangeDefinition("IB_60", "60-Min Initial Balance", "09:30", "10:30"),
    "IB_90": RangeDefinition("IB_90", "90-Min Initial Balance", "09:30", "11:00"),
    "GLOBEX_IB_60": RangeDefinition("GLOBEX_IB_60", "60-Min Initial Balance", "18:00", "19:00"),
    "TOKYO_IB_60": RangeDefinition("TOKYO_IB_60", "60-Min Initial Balance", "19:00", "20:00"),



    # ── Session Ranges ────────────────────────────────────────────────────────
    "ASIA": RangeDefinition(
        "ASIA", "Asia Range", "20:00", "02:00", session="ETH",
        observe_until="16:00",
    ),
    "LONDON": RangeDefinition(
        "LONDON", "London Range", "03:00", "04:30", session="ETH",
        observe_until="16:00",
    ),
    "LUNCH": RangeDefinition("LUNCH", "Lunch Range",   "12:00", "13:30"),
    "NY_AM": RangeDefinition("NY_AM", "NY AM Range",   "09:30", "12:00"),
    "NY_PM": RangeDefinition("NY_PM", "NY PM Range",   "13:30", "16:00"),

    # ── Overnight ─────────────────────────────────────────────────────────────
    "OVERNIGHT": RangeDefinition(
        "OVERNIGHT", "Overnight Range", "18:00", "09:30", session="ETH",
        observe_until="16:00",
    ),
    "PRIOR_DAY": RangeDefinition(
        "PRIOR_DAY", "Prior Day RTH", "09:30", "16:00",
        observe_until="16:00",
    ),

    # ── ICT-Specific ──────────────────────────────────────────────────────────
    "SILVER_BULLET_AM": RangeDefinition(
        "SILVER_BULLET_AM", "AM Silver Bullet", "10:00", "11:00"),
    "SILVER_BULLET_PM": RangeDefinition(
        "SILVER_BULLET_PM", "PM Silver Bullet", "14:00", "15:00"),
    "POWER_HOUR": RangeDefinition(
        "POWER_HOUR", "Power Hour", "15:00", "16:00"),
}
