"""Strat canonical config loader (Pillar 1).

Single source of truth: scripts/strategies/the_strat/strat_config.json.
The same file is read by NT8 bots via StratConfig.cs — keep the schema
flat, JSON-native (no YAML-isms), and backwards compatible.

Schema version: strat_config/v1. Unknown keys are ignored (forward-compat);
missing keys fall back to code defaults so old files keep loading.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    while p.name and p.name != "scripts":
        p = p.parent
    return p.parent if p.name == "scripts" else p


CANONICAL_CONFIG_PATH = (
    _repo_root() / "scripts" / "strategies" / "the_strat" / "strat_config.json"
)
# Legacy YAML kept as a fallback only (deprecated — do not extend).
LEGACY_CONFIG_PATH = (
    _repo_root() / "scripts" / "strategies" / "the_strat" / "config.yaml"
)


@dataclass
class InstrumentSpec:
    tick_size: float = 0.25
    point_value: float = 20.0
    commission: float = 2.05
    slippage_ticks: int = 1


@dataclass
class StratConfig:
    """Typed view over strat_config.json."""

    version: str = "1.0.0"
    signal_tf: str = "5min"
    ftfc_timeframes: list[str] = field(
        default_factory=lambda: ["5m", "15m", "1h", "D"]
    )
    htf_trend_tf: str = "60min"
    allowed_setups: list[str] = field(default_factory=list)
    use_ftfc_filter: bool = True
    min_ftfc_score: int = 2
    earliest_entry: str = "09:30"
    latest_entry: str = "15:30"
    flatten_by: str = "15:55"
    use_killzones: bool = True
    killzones: list[dict] = field(default_factory=list)
    min_target_points: float = 15.0
    max_risk_points: float = 15.0
    min_rr_ratio: float = 1.0
    max_holding_bars: int = 20
    wick_threshold: float = 0.6
    atr_period: int = 14
    atr_cap_mult: float = 1.5
    confirm_next_bar: bool = True
    stop_first: bool = True
    max_trades_per_day: int = 2
    instruments: dict[str, InstrumentSpec] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    def instrument(self, ticker: str) -> InstrumentSpec:
        """Resolve NQ1 -> NQ, MES1 -> MES, fall back to NQ spec."""
        base = ticker.upper().rstrip("1234567890!")
        if base in self.instruments:
            return self.instruments[base]
        if "NQ" in self.instruments:
            return self.instruments["NQ"]
        return InstrumentSpec()


def _from_dict(d: dict) -> StratConfig:
    tf = d.get("timeframes", {})
    setups = d.get("setups", {})
    ftfc = d.get("ftfc", {})
    sess = d.get("session", {})
    risk = d.get("risk", {})
    ex = d.get("execution", {})
    instruments = {
        k: InstrumentSpec(
            tick_size=float(v.get("tick_size", 0.25)),
            point_value=float(v.get("point_value", 20.0)),
            commission=float(v.get("commission", 2.05)),
            slippage_ticks=int(v.get("slippage_ticks", 1)),
        )
        for k, v in d.get("instruments", {}).items()
    }
    return StratConfig(
        version=str(d.get("version", "1.0.0")),
        signal_tf=str(tf.get("signal_tf", "5min")),
        ftfc_timeframes=list(tf.get("ftfc_timeframes", ["5m", "15m", "1h", "D"])),
        htf_trend_tf=str(tf.get("htf_trend_tf", "60min")),
        allowed_setups=list(setups.get("allowed", [])),
        use_ftfc_filter=bool(ftfc.get("use_filter", True)),
        min_ftfc_score=int(ftfc.get("min_score", 2)),
        earliest_entry=str(sess.get("earliest_entry", "09:30")),
        latest_entry=str(sess.get("latest_entry", "15:30")),
        flatten_by=str(sess.get("flatten_by", "15:55")),
        use_killzones=bool(sess.get("use_killzones", True)),
        killzones=list(sess.get("killzones", [])),
        min_target_points=float(risk.get("min_target_points", 15.0)),
        max_risk_points=float(risk.get("max_risk_points", 15.0)),
        min_rr_ratio=float(risk.get("min_rr_ratio", 1.0)),
        max_holding_bars=int(risk.get("max_holding_bars", 20)),
        wick_threshold=float(risk.get("wick_threshold", 0.6)),
        atr_period=int(risk.get("atr_period", 14)),
        atr_cap_mult=float(risk.get("atr_cap_mult", 1.5)),
        confirm_next_bar=bool(ex.get("confirm_next_bar", True)),
        stop_first=bool(ex.get("stop_first", True)),
        max_trades_per_day=int(ex.get("max_trades_per_day", 2)),
        instruments=instruments,
        raw=d,
    )


def load_strat_config(path: str | Path | None = None) -> StratConfig:
    """Load the canonical Strat config.

    Order: explicit path -> strat_config.json -> legacy config.yaml -> defaults.
    Never raises on missing file — returns defaults (fail-open for research,
    bots log the fallback via StratConfig.cs on the NT8 side).
    """
    if path is not None:
        p = Path(path)
        if p.exists():
            return _from_dict(json.loads(p.read_text(encoding="utf-8")))
        return StratConfig()
    if CANONICAL_CONFIG_PATH.exists():
        try:
            return _from_dict(
                json.loads(CANONICAL_CONFIG_PATH.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
            return StratConfig()
    if LEGACY_CONFIG_PATH.exists():  # deprecated fallback
        try:
            import yaml  # local import: PyYAML is optional

            return _from_dict(
                yaml.safe_load(LEGACY_CONFIG_PATH.read_text(encoding="utf-8")) or {}
            )
        except Exception:
            return StratConfig()
    return StratConfig()
