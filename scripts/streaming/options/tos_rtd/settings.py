"""
RTD COM settings — GUIDs, ProgID, and timing constants.

Ported from: 2187Nick/tos-streamlit-dashboard (futures branch)
Source: config/config.yaml + src/core/settings.py

These are the TOS RTD COM server identifiers. They are fixed by the
ThinkorSwim application and should never change.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RTDSettings:
    """Immutable RTD COM server configuration."""

    # COM ProgID for TOS RTD server
    progid: str = "Tos.RTD"

    # Type library GUID
    typelib_guid: str = "{BA792DC8-807E-43E3-B484-47465D82C4D1}"

    # IRtdServer interface GUID
    server_guid: str = "{EC0E6191-DB51-11D3-8F3E-00C04F3651B8}"

    # IRTDUpdateEvent callback interface GUID
    update_event_guid: str = "{A43788C1-D91B-11D3-8F39-00C04F3651B8}"

    # Heartbeat intervals (milliseconds)
    initial_heartbeat: int = 200   # Used during first connection
    default_heartbeat: int = 500  # Steady-state heartbeat

    # Worker poll intervals (seconds)
    fast_poll_interval: float = 0.05  # Before first data arrives
    normal_poll_interval: float = 1.0  # After first data arrives

    # Init retry
    max_init_retries: int = 3
    init_retry_delays: tuple = (0.5, 1.0, 2.0)


# Singleton — use this everywhere
SETTINGS = RTDSettings()