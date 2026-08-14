# scripts/agent_loop/ — ARCHIVED

The source code in `_archive_predecessor/` is the **predecessor** of the
`agent-loop` package at [github.com/vinay-veerappa/agent-loop](https://github.com/vinay-veerappa/agent-loop).

It is retained for reference only. Do not run it. Three of its gates were
defective (see [AGENT_PATCH_LOOP.md](../../../docs/architecture/AGENT_PATCH_LOOP.md) section 4).

## Current architecture

The agent loop is now a standalone pip-installable package:

```
pip install git+https://github.com/vinay-veerappa/agent-loop.git@v0.1.0
```

Consumer profiles for this repo are in `scripts/agent_loop_config/`:

```powershell
# NT8 RiskGuard (C#)
python -m agent_loop --profile nt8-riskguard --profile-module scripts.agent_loop_config.nt8_riskguard --tickets scripts/agent_loop/tickets_p0.json --ticket T1

# Python
python -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --tickets tickets.json --ticket T1
```

## What's still here

The ticket JSON files (`tickets_p0.json`, `tickets_p0_51.json`, `tickets_p1_56.json`)
are kept because they define NT8 RiskGuard defects and are consumed by the
new package via `--tickets`.