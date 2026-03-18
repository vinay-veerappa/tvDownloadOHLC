
### FR-5 Output files

| ID | Requirement |
|---|---|
| FR-5.1 | Overwrite `data/daily_levels.json` each run |
| FR-5.2 | Overwrite `data/daily_levels.txt` each run |
| FR-5.3 | JSON entries must include `{ level, type, asset, regime, cash_ticker, basis_spread }` |
| FR-5.4 | TXT must include copy-ready string block, interpretation/pre-open plan block, and detailed summary block |
| FR-5.5 | Copy-ready ordering must match operational template (Upper EM → Lower EM 10-level set) |

### FR-6 Notifications and scheduling

| ID | Requirement |
|---|---|
| FR-6.1 | Support on-demand execution and scheduler mode (`--schedule`) |
| FR-6.2 | Scheduler must run at configured weekday ET times |
| FR-6.3 | Discord updates must be optional and controllable via config and CLI (`--discord`, `--no-discord`) |
| FR-6.4 | Discord failure must not block file output |

---

## 5) Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Reliability | Per-ticker failure must not stop the full run |
| NFR-2 | Observability | Log all run stages and fallbacks to `data/dealer_levels.log` |
| NFR-3 | Robustness | Handle weekend/off-hours sparse data without producing structurally empty output when fallback data exists |
| NFR-4 | Security | Never log API keys/secrets |
| NFR-5 | Extensibility | New index family should be primarily configurable in `config.py` mappings |

---

## 6) Constraints

- Schwab rate limits apply.
- TradingView Pine has no direct file I/O; manual paste/input flow is required.
- Weekday-only scheduling is implemented; exchange holiday filtering is out of scope.
