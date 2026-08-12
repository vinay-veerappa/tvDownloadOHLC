"""agent_loop_config package — registers profiles for tvDownloadOHLC.

The nt8-riskguard profile used to live here too. It moved with the addons
(2026-08-12 repo split) and is now `agent/nt8_riskguard.py` in
https://github.com/vinay-veerappa/nt8-riskguard, alongside the ticket files it
consumes. Run it from that repo:

    agent-loop --profile nt8-riskguard --profile-module agent.nt8_riskguard \
        --tickets agent/tickets_p0.json --ticket T1
"""
from .python_tvdownloadohlc import PYTHON_TVDOWNLOADOHLC
