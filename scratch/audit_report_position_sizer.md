## Executive Summary

**Component:** `position_sizer.py` + `ticker_registry.json`  
**Stated purpose:** Multi-Ticker Position Sizing Risk Engine  
**Actual state:** A *single-ticker, scalar, point-value-based sizer* with a partially correct core formula but major omissions in domain-rule enforcement, input validation, portfolio risk, performance, and error handling.

**Overall audit grade:** **C / Needs remediation before production.**  
The engine can convert “% of account × stop distance × point value” into a contract count for the six listed futures, but it silently ignores almost every domain field in the registry, re-reads a JSON file on every call, has a dangerous `max(1, …)` boundary bug, and has no concept of margin, cross-ticker exposure, or session filters.

---

## 1. Rule Fidelity & Domain Correctness

### What is correct
- The **monetary risk-to-contracts formula** is mathematically sound for futures quoted in whole points:

\[
\text{dollars\_at\_risk} = \text{account\_equity} \times \frac{\text{risk\_pct}}{100}
\]

\[
\text{risk\_per\_contract} = \text{stop\_distance\_points} \times \text{point\_value}
\]

\[
\text{raw\_contracts} = \frac{\text{dollars\_at\_risk}}{\text{risk\_per\_contract}}
\]

- `point_value` mappings in `ticker_registry.json` are consistent with CME tick values:
  - NQ: 4 ticks × $5 = **$20/point** ✔
  - ES: 4 ticks × $12.50 = **$50/point** ✔
  - CL: 100 ticks × $10 = **$1,000/point** ✔
  - GC: 10 ticks × $10 = **$100/point** ✔
  - YM/RTY values are internally consistent ✔

### What is missing or wrong relative to the registry / methodology
The registry encodes many rules, but the sizer consumes **only `point_value`**. Every other field is dead data:

| Registry field | Intended domain meaning | Used in sizer? | Risk |
|---|---|---|---|
| `momentum_threshold_points` | Minimum move required to validate a setup | ❌ | Sizer may size low-momentum, invalid signals |
| `rth_open_time` / `rth_close_time` | Allowed entry window | ❌ | Trades can be sized outside RTH / into close |
| `morning_pivot_exit_minute` | Time-based exit rule | ❌ | Holding-period risk not reflected in sizing |
| `weekly_settlement_hour` | No-new-position window before settlement | ❌ | Risk of settlement gaps ignored |
| Multi-ticker exposure | Correlation clusters (NQ/ES/YM/RTY) | ❌ | Account can pyramid equity-index risk |
| Daily/weekly loss limits | Circuit breakers | ❌ | No heat control |
| Margin / buying power | Futures are levered | ❌ | Can “size” contracts the account cannot afford |

**Verdict:** The engine is *not* a “Multi-Ticker Position Sizing **Risk Engine**”; it is a basic per-trade contract calculator. Without a written specification of “Matt Mickey & Austin’s master trading methodology,” full rule fidelity cannot be proven, but the **registry itself implies the methodology is broader than what is implemented**.

---

## 2. Edge Cases & Failure Modes

| # | Scenario | Current behavior | Severity |
|---|---|---|---|
| 1 | `raw_contracts < 1.0` (e.g., small account or wide stop) | Returns **0 contracts** and skips the trade without a clear flag | Medium — may drop valid setups |
| 2 | `max_contracts = 0` | `max(1, min(..., 0))` returns **1 contract**, violating the cap | **Critical** |
| 3 | `stop_distance_points <= 0` | Returns a **different-shaped dict** (`error`, `contract_count`, `dollars_at_risk` only) | High — breaks downstream consumers |
| 4 | `account_equity <= 0`, `risk_pct <= 0`, or `risk_pct > 100` | Accepted silently; produces nonsensical sizes | High |
| 5 | `NaN` / `inf` inputs | Passes through arithmetic; comparisons become unpredictable | High |
| 6 | Unknown ticker when registry file is missing | Falls back to NQ specs (`point_value=20`) | **Critical** for YM/RTY/CL/GC |
| 7 | Registry file missing or corrupt | Silently falls back to a 4-ticker default, logs a warning only | High |
| 8 | Registry key `point_value` missing for a ticker | Silently uses default `20.0` | High |
| 9 | Holiday / early-close sessions | Fixed `rth_close_time` used; no holiday calendar | Medium |
| 10 | Timezone/DST | Times are bare strings without timezone | Medium — RTH filters would be wrong across zones |
| 11 | Weekly settlement / rollover | No settlement-hour guard | High for physically-settled futures |
| 12 | Overnight gaps / stop slippage | Stop assumed filled exactly at distance in points | High — model risk |
| 13 | Margin | A `$4,500` account can size 20 NQ contracts (~$360k notional / ~$20k+ margin each) | **Critical** |
| 14 | Cross-ticker correlation | Can enter NQ + ES + YM + RTY simultaneously | High |

**Worst-case example:**  
`calculate_position_size(4500, 5, 100, "NQ1", max_contracts=0)`  
Expected: 0 contracts.  
Actual: 1 contract (`max(1, min(4, 0)) = 1`), violating the caller’s risk cap.

---

## 3. Code Quality, Vectorization & Performance

### Anti-patterns found
1. **I/O in the hot path**  
   `load_ticker_config()` opens and `json.load()`s the registry **on every call**. In a backtest or live tick loop this is a major bottleneck.

2. **No vectorized API**  
   The function is scalar only. A pandas/numpy batch sizing method is absent; callers will `df.apply(..., axis=1)`, which is slow for large histories.

3. **Brittle path resolution**  
   ```python
   REPO_ROOT = Path(__file__).parent.parent.parent
   REGISTRY_PATH = REPO_ROOT / "scripts" / "config" / "ticker_registry.json"
   ```
   Breaks if the file is moved, packaged, run from a different CWD, or deployed as a wheel/Frozen binary.

4. **Inconsistent return shape**  
   The `stop_distance_points <= 0` branch returns a different key set than the success branch. Typed callers will crash.

5. **Weak type safety / no validation**  
   - `dict[str, Any]` return type gives no guarantees.  
   - No `pydantic`/`dataclass` validation of inputs.  
   - No tests are visible.

6. **Silent fallbacks**  
   Unknown tickers and missing registry keys silently default to NQ values — a silent data-quality failure.

7. **Magic numbers**  
   Default `point_value=20.0`, `max_contracts=20`, and the hard-coded repo layout are not configurable.

### Performance note
Even ignoring the JSON reload, calling a pure-Python scalar function row-by-row across a multi-year, multi-ticker backtest can be 10–100× slower than a vectorized implementation.

---

## 4. Concrete Actionable Enhancements

Below is a hardened redesign. It addresses input validation, registry caching, the `max_contracts=0` bug, consistent return types, and a vectorized batch path. It also stubs where domain rules (margin, session windows, portfolio heat) should plug in.

### A. Hardened scalar sizer (recommended rewrite)

```python
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TickerSpec:
    tick_size: float
    tick_value: float
    point_value: float
    rth_open_time: str | None = None
    rth_close_time: str | None = None
    weekly_settlement_hour: int | None = None
    momentum_threshold_points: float | None = None
    morning_pivot_exit_minute: int | None = None

    @classmethod
    def from_dict(cls, cfg: dict[str, Any]) -> "TickerSpec":
        required = ("tick_size", "tick_value", "point_value")
        missing = [k for k in required if k not in cfg]
        if missing:
            raise ValueError(f"Ticker config missing required keys: {missing}")
        return cls(
            tick_size=float(cfg["tick_size"]),
            tick_value=float(cfg["tick_value"]),
            point_value=float(cfg["point_value"]),
            rth_open_time=cfg.get("rth_open_time"),
            rth_close_time=cfg.get("rth_close_time"),
            weekly_settlement_hour=cfg.get("weekly_settlement_hour"),
            momentum_threshold_points=cfg.get("momentum_threshold_points"),
            morning_pivot_exit_minute=cfg.get("morning_pivot_exit_minute"),
        )


@dataclass(frozen=True)
class SizingResult:
    ticker: str
    account_equity: float
    risk_pct: float
    stop_distance_points: float
    dollars_at_risk: float
    point_value: float
    risk_per_contract: float
    raw_contracts: float
    contract_count: int
    actual_risk: float
    capped_by_max: bool
    skipped: bool
    messages: tuple[str, ...]


# ---------------------------------------------------------------------------
# Registry loading (once, cached)
# ---------------------------------------------------------------------------

DEFAULT_REGISTRY: dict[str, TickerSpec] = {
    "NQ1": TickerSpec(0.25, 5.0, 20.0),
    "ES1": TickerSpec(0.25, 12.5, 50.0),
    "CL1": TickerSpec(0.01, 10.0, 1000.0),
    "GC1": TickerSpec(0.10, 10.0, 100.0),
    "YM1": TickerSpec(1.0, 5.0, 5.0),
    "RTY1": TickerSpec(0.10, 5.0, 50.0),
}


def _default_registry_path() -> Path:
    # Prefer an env override; fall back to a relative path only as a default.
    env_path = __import__("os").getenv("TICKER_REGISTRY_PATH")
    if env_path:
        return Path(env_path)
    return Path(__file__).parent / "ticker_registry.json"


@lru_cache(maxsize=4)
def load_registry(path: Path | None = None) -> dict[str, TickerSpec]:
    path = path or _default_registry_path()
    if not path.exists():
        log.error("Ticker registry not found at %s; using built-in defaults", path)
        return DEFAULT_REGISTRY.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        log.error("Failed to parse ticker registry at %s: %s", path, e)
        return DEFAULT_REGISTRY.copy()

    specs: dict[str, TickerSpec] = {}
    for ticker, cfg in raw.items():
        try:
            specs[ticker] = TickerSpec.from_dict(cfg)
        except Exception as e:
            log.error("Skipping invalid ticker config %s: %s", ticker, e)
    if not specs:
        log.error("Registry produced no valid specs; using defaults")
        return DEFAULT_REGISTRY.copy()
    return specs


def get_spec(ticker: str, registry_path: Path | None = None) -> TickerSpec:
    specs = load_registry(registry_path)
    if ticker not in specs:
        # Fail loudly rather than silently defaulting to NQ.
        raise KeyError(f"Ticker {ticker!r} not found in registry")
    return specs[ticker]


# ---------------------------------------------------------------------------
# Core scalar sizer
# ---------------------------------------------------------------------------

def calculate_position_size(
    account_equity: float,
    risk_pct: float,
    stop_distance_points: float,
    ticker: str,
    max_contracts: int = 20,
) -> SizingResult:
    """Hardened contract sizing for a single futures trade."""

    # ---- input validation -------------------------------------------------
    if not (math.isfinite(account_equity) and account_equity > 0):
        raise ValueError(f"account_equity must be finite and positive, got {account_equity}")
    if not (math.isfinite(risk_pct) and 0 < risk_pct <= 100):
        raise ValueError(f"risk_pct must be in (0, 100], got {risk_pct}")
    if not (math.isfinite(stop_distance_points) and stop_distance_points > 0):
        raise ValueError(f"stop_distance_points must be finite and positive, got {stop_distance_points}")
    if not isinstance(max_contracts, int) or max_contracts < 0:
        raise ValueError(f"max_contracts must be a non-negative int, got {max_contracts}")

    spec = get_spec(ticker)

    # ---- sizing -----------------------------------------------------------
    dollars_at_risk = account_equity * (risk_pct / 100.0)
    risk_per_contract = stop_distance_points * spec.point_value
    raw_contracts = dollars_at_risk / risk_per_contract if risk_per_contract > 0 else 0.0

    messages: list[str] = []
    capped_by_max = False
    skipped = False

    if raw_contracts < 1.0:
        contract_count = 0
        skipped = True
        messages.append(
            f"raw size {raw_contracts:.4f} < 1 contract; skipping to avoid oversizing"
        )
    else:
        contract_count = min(int(raw_contracts), max_contracts)
        if contract_count == max_contracts and raw_contracts > max_contracts:
            capped_by_max = True
            messages.append(
                f"raw size {raw_contracts:.4f} capped at max_contracts={max_contracts}"
            )

    actual_risk = contract_count * risk_per_contract

    return SizingResult(
        ticker=ticker,
        account_equity=round(account_equity, 2),
        risk_pct=risk_pct,
        stop_distance_points=round(stop_distance_points, 2),
        dollars_at_risk=round(dollars_at_risk, 2),
        point_value=spec.point_value,
        risk_per_contract=round(risk_per_contract, 2),
        raw_contracts=round(raw_contracts, 4),
        contract_count=contract_count,
        actual_risk=round(actual_risk, 2),
        capped_by_max=capped_by_max,
        skipped=skipped,
        messages=tuple(messages),
    )
```

Key fixes in this rewrite:
- `max_contracts=0` now correctly yields **0 contracts**.
- Unknown tickers raise `KeyError` instead of inheriting NQ specs.
- Registry is loaded once and cached via `lru_cache`.
- Inputs are validated for finiteness, positivity, and type.
- Returns a single, frozen, well-typed result object in all cases.
- Exposes `raw_contracts`, `capped_by_max`, and `skipped` for audit trails.

### B. Vectorized batch sizer

For backtests or signal DataFrames, add a vectorized path:

```python
import numpy as np
import pandas as pd


def size_batch(
    df: pd.DataFrame,
    registry_path: Path | None = None,
    max_contracts: int = 20,
) -> pd.DataFrame:
    """
    Vectorized sizing for a DataFrame with columns:
    ['account_equity', 'risk_pct', 'stop_distance_points', 'ticker'].
    """
    required = {"account_equity", "risk_pct", "stop_distance_points", "ticker"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")

    specs = load_registry(registry_path)
    point_map = {t: s.point_value for t, s in specs.items()}

    out = df.copy()
    out["point_value"] = out["ticker"].map(point_map)
    if out["point_value"].isna().any():
        bad = out.loc[out["point_value"].isna(), "ticker"].unique()
        raise ValueError(f"Unknown tickers in batch: {list(bad)}")

    out["dollars_at_risk"] = out["account_equity"] * out["risk_pct"] / 100.0
    out["risk_per_contract"] = out["stop_distance_points"] * out["point_value"]
    raw = out["dollars_at_risk"] / out["risk_per_contract"]
    out["raw_contracts"] = raw

    floor_raw = np.floor(raw).astype(int)
    out["contract_count"] = np.where(
        raw >= 1.0,
        np.minimum(floor_raw, max_contracts),
        0,
    )
    out["capped_by_max"] = (raw >= 1.0) & (floor_raw > max_contracts)
    out["skipped"] = raw < 1.0
    out["actual_risk"] = out["contract_count"] * out["risk_per_contract"]

    return out
```

### C. Domain-rule guards you should add next

These belong in the trading orchestrator, but the sizer should expose the hooks:

```python
from dataclasses import dataclass


@dataclass
class PortfolioHeatGuard:
    """Enforce total open risk across all positions <= max_heat_pct of equity."""
    account_equity: float
    max_heat_pct: float
    _open_risk: float = 0.0

    def limit(self) -> float:
        return self.account_equity * self.max_heat_pct / 100.0

    def can_add(self, additional_risk: float) -> bool:
        return self._open_risk + additional_risk <= self.limit() + 1e-9

    def add(self, risk: float) -> None:
        if not self.can_add(risk):
            raise RuntimeError("Portfolio heat limit exceeded")
        self._open_risk += risk

    def release(self, risk: float) -> None:
        self._open_risk = max(0.0, self._open_risk - risk)


@dataclass
class MarginGuard:
    """Prevent sizing beyond available buying power."""
    buying_power: float
    margin_per_contract: float  # could come from broker / exchange specs

    def max_contracts(self) -> int:
        if self.margin_per_contract <= 0:
            return 0
        return int(self.buying_power // self.margin_per_contract)
```

### D. Critical rule changes to discuss with the methodology owners

1. **Sub-1-contract behavior** — decide whether `raw_contracts < 1` should:
   - Skip the trade (current behavior), or
   - Take 1 contract and flag that risk exceeds the planned %.

2. **Rounding mode** — the current code floors (`int`). If stops are in ticks, consider aligning `stop_distance_points` to the nearest tick increment:

   ```python
   aligned_stop = round(stop_distance_points / tick_size) * tick_size
   ```

3. **Time-of-day filters** — integrate `rth_open_time`, `rth_close_time`, `morning_pivot_exit_minute`, and `weekly_settlement_hour` into an entry eligibility check *before* sizing.

4. **Correlation clusters** — NQ, ES, YM, RTY are highly correlated. A true multi-ticker risk engine should treat them as one risk bucket and cap cluster exposure.

5. **Margin / buying power** — add per-ticker initial margin requirements and reject any size where `contracts × margin > available_buying_power`.

---

## Recommended next steps

1. Replace `position_sizer.py` with the hardened scalar + vectorized versions above.
2. Add unit tests covering:
   - `max_contracts=0`
   - unknown ticker
   - `raw_contracts < 1`
   - registry load failure
   - NaN/negative inputs
   - vectorized batch with mixed tickers
3. Extend `TickerSpec` to include margin requirements (or fetch from broker API).
4. Implement `PortfolioHeatGuard` and `MarginGuard` in the execution layer.
5. Document the exact discretionary rules (momentum threshold, settlement window, pivot exit) so the engine can enforce them rather than ignore them.