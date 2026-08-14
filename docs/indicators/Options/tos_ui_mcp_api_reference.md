# TOS-UI-MCP — API & Scripts Reference

The full API, FastMCP server, and scripts reference for the ThinkorSwim
Automation Suite lives in the `tos-ui-mcp` submodule:

- **API reference**: [`tos-ui-mcp/API_AND_SCRIPTS_REFERENCE.md`](../../tos-ui-mcp/API_AND_SCRIPTS_REFERENCE.md)
- **JAB setup & handover**: [`tos-ui-mcp/TOS_JAB.md`](../../tos-ui-mcp/TOS_JAB.md)
- **Full specification**: [`tos-ui-mcp/SPECIFICATION.md`](../../tos-ui-mcp/SPECIFICATION.md)
- **Desktop isolation**: [`tos-ui-mcp/DESKTOP_ISOLATION.md`](../../tos-ui-mcp/DESKTOP_ISOLATION.md)
- **Hotkeys guide**: [`tos-ui-mcp/docs/TOS_DESKTOP_HOTKEYS_GUIDE.md`](../../tos-ui-mcp/docs/TOS_DESKTOP_HOTKEYS_GUIDE.md)

The `tos-ui-mcp` submodule provides dual-engine automation (Web via Playwright,
Desktop via JAB/RapidOCR) and a FastMCP server exposing `extract_expected_moves_from_tos_ui`
and `extract_expected_moves_from_tos_desktop`.

## Pipeline integration in this repo

The daily pipeline that consumes TOS expected moves lives in this repo:

- [`scripts/pipeline/extract_tos_expected_moves.py`](../../scripts/pipeline/extract_tos_expected_moves.py)
  — entry point; imports `tos_ui_mcp.desktop_extractor` and `tos_ui_mcp.extractor`
  from the submodule.
- [`scripts/market_data/extract_all_expiries_em.py`](../../scripts/market_data/extract_all_expiries_em.py)
  — multi-expiry EM + IV extraction with Schwab API failover and Prisma DB persistence.
- [`docs/architecture/TOS_EXPECTED_MOVE_PIPELINE_DESIGN.md`](../architecture/TOS_EXPECTED_MOVE_PIPELINE_DESIGN.md)
  — pipeline design doc.
- [`docs/indicators/Options/tos_expected_move_handoff.md`](tos_expected_move_handoff.md)
  — EM calibration formula (TOS's proprietary time-scaling model).