# ThinkorSwim Automation Suite (TOS-UI-MCP) - API, FastMCP & Scripts Reference Manual

**Version**: 2.5.0  
**Target Platform**: ThinkorSwim Web (`trade.thinkorswim.com`) & ThinkorSwim Desktop (`thinkorswim.exe`)  
**Repositories**:
- `tos-ui-mcp` (Standalone Engine & FastMCP Server): [https://github.com/vinay-veerappa/tos-ui-mcp](https://github.com/vinay-veerappa/tos-ui-mcp)
- `tvDownloadOHLC` (Main Workspace & Data Pipeline): [https://github.com/vinay-veerappa/tvDownloadOHLC](https://github.com/vinay-veerappa/tvDownloadOHLC)

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [FastMCP Server Tools (`mcp_server.py`)](#2-fastmcp-server-tools-mcp_serverpy)
3. [Python API Client (`TOSWebClient`)](#3-python-api-client-toswebclient)
4. [Standalone Production Extractor Modules](#4-standalone-production-extractor-modules)
5. [Pipeline Integration Scripts](#5-pipeline-integration-scripts)
6. [Symbol Normalizer & Asset Awareness (`symbol_utils.py`)](#6-symbol-normalizer--asset-awareness-symbol_utilspy)
7. [Persistent UI Registry & Coordinate Engine (`ui_registry.py`)](#7-persistent-ui-registry--coordinate-engine-ui_registrypy)
8. [Diagnostic & Verification Scripts](#8-diagnostic--verification-scripts)

---

## 1. Architecture Overview

`tos-ui-mcp` provides a dual-engine architecture supporting both **ThinkorSwim Web** and **ThinkorSwim Desktop**:

```
+---------------------------------------------------------------------------------------------------+
|                                       AI Agents & Python Pipelines                                |
|           (FastMCP Server / Direct Python Imports / Automated Daily Pipeline Scripts)              |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
+--------------------------------------------------+ +----------------------------------------------+
|     Engine 1: ThinkorSwim Web App (Playwright)   | |  Engine 2: ThinkorSwim Desktop (RapidOCR)    |
| - Runs 100% Headless in Background               | | - State-Driven OCR Launcher Engine           |
| - Auto Multi-Path Iframe Authentication          | | - Auto Launcher Update Detection & Login    |
| - DOM Accordion Expected Move Extractor          | | - RapidOCR Neural Vision (<100ms)           |
| - Concurrency Lock & SQLite Audit/Idempotency    | | - DPI-Aware Screen Click Coordinate Mapping |
+--------------------------------------------------+ +----------------------------------------------+
```

---

## 2. FastMCP Server Tools (`mcp_server.py`)

Run FastMCP Server:
```powershell
.\.venv\Scripts\python.exe -m tos-ui-mcp.tos_ui_mcp.mcp_server
```

### Tool 1: `extract_expected_moves_from_tos_ui`
* **Description**: Launches ThinkorSwim Web App (`trade.thinkorswim.com`) in Playwright, logs in automatically, expands option chain accordions, and extracts exact platform Expected Move values (`± XX.XX`).
* **Parameters**:
  - `tickers` (*list[str]*): List of ticker symbols (e.g. `["SPX", "NQ", "AAPL"]`).
  - `headless` (*bool*, default `True`): Run browser in headless background mode.
  - `output_file` (*str*, default `"output/tos_ui_expected_moves.json"`): Path to save output JSON.
* **Return Value**: Summary string with status and output path.

### Tool 2: `extract_expected_moves_from_tos_desktop`
* **Description**: Automates ThinkorSwim Desktop Application (`thinkorswim.exe`), auto-launches and logs in via State-Driven OCR, navigates tickers, and runs RapidOCR neural vision on option chains to extract exact platform Expected Move values (`± XX.XX`).
* **Parameters**:
  - `tickers` (*list[str]*): List of ticker symbols (e.g. `["SPX", "NQ", "MNQ", "AAPL"]`).
  - `output_file` (*str*, default `"output/tos_desktop_expected_moves.json"`): Path to save output JSON.
* **Return Value**: Summary string with status and output path.

---

## 3. Python API Client (`TOSWebClient`)

Located in `tos_ui_mcp/client.py`:

```python
from tos_ui_mcp import TOSWebClient
import asyncio

async def main():
    async with TOSWebClient() as client:
        # 1. Fetch Expected Moves
        em_data = await client.extract_expected_moves(tickers=["SPX", "NQ"])
        print("SPX EM:", em_data["tickers"]["SPX"]["expirations"][0]["expected_move"])

        # 2. Place Equity Order (Dry-Run / Paper Trading Mode)
        order_res = await client.place_equity_order(
            symbol="AAPL",
            qty=10,
            action="BUY",
            order_type="LIMIT",
            limit_price=220.00,
            dry_run=True,
            idempotency_key="order-001"
        )
        print("Order Echo-Back:", order_res["mode"], order_res["status"])

asyncio.run(main())
```

---

## 4. Standalone Production Extractor Modules

### 1. `tos_ui_mcp/desktop_extractor.py` (ThinkorSwim Desktop)
Automates `thinkorswim.exe` with zero mouse clicks for symbol navigation and RapidOCR for data extraction.

#### CLI Command:
```powershell
.\.venv\Scripts\python.exe -m tos-ui-mcp.tos_ui_mcp.desktop_extractor --tickers SPX NQ MNQ AAPL NVDA
```

#### Python Function:
```python
from tos_ui_mcp.desktop_extractor import extract_desktop_expected_moves

data = extract_desktop_expected_moves(
    tickers=["SPX", "NQ", "MNQ", "AAPL"],
    save_json=True,
    output_file=Path("output/tos_desktop_expected_moves.json")
)
```

#### Output JSON Schema:
```json
{
  "extracted_at": "2026-07-25T12:14:02.123456",
  "source": "thinkorswim_desktop_ui",
  "window_title": "Paper@thinkorswim [build 1992]",
  "tickers": {
    "SPX": {
      "symbol": "SPX",
      "account_mode": "Paper Trading",
      "last_price": 5700.50,
      "series_count": 22,
      "expirations": [
        {
          "expiry": "27 JUL 26",
          "dte": 2,
          "iv_pct": 12.72,
          "expected_move": 57.038,
          "raw_ocr": ">27 JUL 26 (2) 100 (Weeklys) 12.72% (±57.038)"
        }
      ]
    }
  }
}
```

### 2. `tos_ui_mcp/extractor.py` (ThinkorSwim Web App)
Automates `trade.thinkorswim.com` via Playwright.

#### Python Async Function:
```python
from tos_ui_mcp.extractor import extract_tos_ui_expected_moves
import asyncio

data = asyncio.run(
    extract_tos_ui_expected_moves(
        tickers=["SPX", "NQ"],
        headless=True,
        save_json=True
    )
)
```

---

## 5. Pipeline Integration Scripts

Located in `scripts/pipeline/extract_tos_expected_moves.py` in `tvDownloadOHLC`:

### CLI Execution:
```powershell
# Desktop App Pipeline
.\.venv\Scripts\python.exe -m scripts.pipeline.extract_tos_expected_moves --source desktop --tickers SPX NQ MNQ AAPL NVDA

# Web App Background Pipeline
.\.venv\Scripts\python.exe -m scripts.pipeline.extract_tos_expected_moves --source web --tickers SPX NQ AAPL NVDA
```

### Output Paths Generated:
- Timestamped: `data/expected_moves/tos_expected_moves_YYYY-MM-DD.json`
- Latest Pointer: `data/expected_moves/latest_tos_expected_moves.json`

---

## 6. Symbol Normalizer & Asset Awareness (`symbol_utils.py`)

Located in `tos_ui_mcp/symbol_utils.py`:

```python
from tos_ui_mcp.symbol_utils import normalize_tos_symbol, sanitize_filename_symbol

# Futures Slash Normalization
print(normalize_tos_symbol("NQ"))    # ➜ Returns "/NQ"
print(normalize_tos_symbol("MNQ"))   # ➜ Returns "/MNQ"
print(normalize_tos_symbol("ES"))    # ➜ Returns "/ES"
print(normalize_tos_symbol("SPX"))   # ➜ Returns "SPX"

# Windows Filename Sanitization
print(sanitize_filename_symbol("/NQ")) # ➜ Returns "_NQ"
```

### Covered Futures Contracts:
`NQ`, `ES`, `CL`, `GC`, `ZB`, `ZN`, `RTY`, `YM`, `MES`, `MNQ`, `MYM`, `M2K`, `MCL`, `MGC`, `MBTC`, `MET`, `SI`, `HG`, `NG`, `6E`, `6J`, `6B`, `6A`, `6C`, `6S`, `6M`, `VX`.

---

## 7. Persistent UI Registry & Coordinate Engine (`ui_registry.py`)

Located in `tos_ui_mcp/ui_registry.py`:

### SQLite Database (`tos_ui_registry.db`)
Manages UI field definitions, visual anchor patterns, and target offset rules:

```python
from tos_ui_mcp.ui_registry import UIElementsDB, resolve_ocr_box_click_coords

db = UIElementsDB()

# Register new field dynamically
db.register_field(
    field_id="desktop.trade.active_trader_buy_mkt",
    platform="desktop",
    tab="Trade",
    element_name="Buy Market Button",
    element_type="button",
    anchor_text_regex=r"\bbuy\s*mkt\b",
    x_pct=0.88,
    y_pct=0.15,
    description="Active Trader Buy Market order submission button"
)

# Compute DPI-aware screen click position with element_type offsets
target_x, target_y = resolve_ocr_box_click_coords(
    hwnd=hwnd,
    box=ocr_box,
    img_size=img.size,
    element_type="input_label_above" # Adds +25px dy_offset to hit input field BELOW text label
)
```

---

## 8. Diagnostic & Verification Scripts

All diagnostic and test scripts are organized under `debug/` and `tests/`:

| Script Path | Purpose | Execution Command |
| :--- | :--- | :--- |
| `debug/verify_win32_coords.py` | Win32 Window Rect, Client Area, and DPI Scale Ratio Diagnostic | `.\.venv\Scripts\python.exe tos-ui-mcp\debug\verify_win32_coords.py` |
| `debug/debug_trade_tab_ocr.py` | Trade Tab OCR Text Bounding Box Visual Inspection | `.\.venv\Scripts\python.exe tos-ui-mcp\debug\debug_trade_tab_ocr.py` |
| `debug/debug_password_screen.py` | Password Screen Layout OCR Inspection | `.\.venv\Scripts\python.exe tos-ui-mcp\debug\debug_password_screen.py` |
| `debug/debug_find_windows.py` | List All Active Top-Level Windows & Handles | `.\.venv\Scripts\python.exe tos-ui-mcp\debug\debug_find_windows.py` |
| `tests/test_mcp_call.py` | Direct FastMCP Tool Call Simulator | `.\.venv\Scripts\python.exe tos-ui-mcp\tests\test_mcp_call.py` |
| `tests/test_desktop_login_click.py` | Standalone Precision Desktop Login Click Test | `.\.venv\Scripts\python.exe tos-ui-mcp\tests\test_desktop_login_click.py` |
