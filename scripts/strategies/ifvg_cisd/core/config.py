"""
IFVG/CISD shared config loader — single source of truth for both platforms.

The manifest at configs/strategies/ifvg_cisd.yaml is canonical. This module
loads it once and exposes typed accessors. The C# side is regenerated from
the same file by scripts/utils/gen_ifvg_cisd_config.py; never hand-tune a
default in either platform without editing the manifest first.

Parity contract: docs/strategies/ifvg_cisd/PARITY_WORKFLOW.md
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

MANIFEST_PATH = Path(_root_dir) / "configs" / "strategies" / "ifvg_cisd.yaml"

_VALID_STOP_TYPES = {"bps_stat", "structural", "structural_capped_bps", "skip_if_out_of_band"}
_VALID_VARIANTS = {"baseline", "variant1", "variant2"}
_VALID_MECHANISMS = {"market", "cisd_limit"}


@dataclass(frozen=True)
class IfvgCisdConfig:
    """Frozen view of the manifest. All times are ET wall-clock HHMM ints."""

    # session
    earliest_entry_hhmm: int
    latest_entry_hhmm: int
    flatten_by_hhmm: int
    lunch_filter_enabled: bool
    lunch_start_hhmm: int
    lunch_end_hhmm: int

    # risk
    min_risk_bps: float
    max_risk_bps: float
    stop_loss_type: str
    stop_loss_bps: float
    queen_target_bps: float
    runner_target_bps: float

    # structure
    htf_resample: str
    variant: str
    entry_mechanism: str
    require_directional_candle: bool
    include_vi: bool
    strict_ifvg_only: bool
    atr_risk_mult: float
    cisd_scan_max_bars: int

    # gates
    max_trades_per_day: int
    use_htf_filter: bool
    htf_ema_period: int
    require_external_sweep: bool
    enable_midline_reclaims: bool
    enable_confirmed_reentry: bool
    reentry_window_bars: int

    # sim
    eod_flatten_hhmm: int
    commission_per_contract: float
    slippage_ticks: int

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "IfvgCisdConfig":
        sess = d["session"]
        risk = d["risk"]
        struct = d["structure"]
        gates = d["gates"]
        sim = d["sim"]

        cfg = IfvgCisdConfig(
            earliest_entry_hhmm=int(sess["earliest_entry_hhmm"]),
            latest_entry_hhmm=int(sess["latest_entry_hhmm"]),
            flatten_by_hhmm=int(sess["flatten_by_hhmm"]),
            lunch_filter_enabled=bool(sess["lunch_filter_enabled"]),
            lunch_start_hhmm=int(sess["lunch_start_hhmm"]),
            lunch_end_hhmm=int(sess["lunch_end_hhmm"]),
            min_risk_bps=float(risk["min_risk_bps"]),
            max_risk_bps=float(risk["max_risk_bps"]),
            stop_loss_type=str(risk["stop_loss_type"]),
            stop_loss_bps=float(risk["stop_loss_bps"]),
            queen_target_bps=float(risk["queen_target_bps"]),
            runner_target_bps=float(risk["runner_target_bps"]),
            htf_resample=str(struct["htf_resample"]),
            variant=str(struct["variant"]),
            entry_mechanism=str(struct["entry_mechanism"]),
            require_directional_candle=bool(struct["require_directional_candle"]),
            include_vi=bool(struct["include_vi"]),
            strict_ifvg_only=bool(struct["strict_ifvg_only"]),
            atr_risk_mult=float(struct["atr_risk_mult"]),
            cisd_scan_max_bars=int(struct["cisd_scan_max_bars"]),
            max_trades_per_day=int(gates["max_trades_per_day"]),
            use_htf_filter=bool(gates["use_htf_filter"]),
            htf_ema_period=int(gates["htf_ema_period"]),
            require_external_sweep=bool(gates["require_external_sweep"]),
            enable_midline_reclaims=bool(gates["enable_midline_reclaims"]),
            enable_confirmed_reentry=bool(gates["enable_confirmed_reentry"]),
            reentry_window_bars=int(gates["reentry_window_bars"]),
            eod_flatten_hhmm=int(sim["eod_flatten_hhmm"]),
            commission_per_contract=float(sim["commission_per_contract"]),
            slippage_ticks=int(sim["slippage_ticks"]),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.stop_loss_type not in _VALID_STOP_TYPES:
            raise ValueError(
                f"stop_loss_type '{self.stop_loss_type}' not in {sorted(_VALID_STOP_TYPES)}"
            )
        if self.variant not in _VALID_VARIANTS:
            raise ValueError(f"variant '{self.variant}' not in {sorted(_VALID_VARIANTS)}")
        if self.entry_mechanism not in _VALID_MECHANISMS:
            raise ValueError(
                f"entry_mechanism '{self.entry_mechanism}' not in {sorted(_VALID_MECHANISMS)}"
            )
        if not (0 <= self.lunch_start_hhmm < 2400 and 0 <= self.lunch_end_hhmm < 2400):
            raise ValueError("lunch window HHMM values must be in [0, 2400)")
        if self.earliest_entry_hhmm >= self.latest_entry_hhmm:
            raise ValueError("earliest_entry_hhmm must be < latest_entry_hhmm")
        if self.stop_loss_bps <= 0:
            raise ValueError("stop_loss_bps must be > 0")
        if self.min_risk_bps > self.max_risk_bps:
            raise ValueError("min_risk_bps must be <= max_risk_bps")


_CACHE: Dict[str, IfvgCisdConfig] = {}


def load_config(path: Path = MANIFEST_PATH) -> IfvgCisdConfig:
    """Load (and memoize) the shared manifest. Raises on invalid values."""
    key = str(path)
    if key in _CACHE:
        return _CACHE[key]
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    cfg = IfvgCisdConfig.from_dict(raw)
    _CACHE[key] = cfg
    return cfg


def manifest_for_export() -> Dict[str, Any]:
    """Raw manifest dict, for the C# generator and parity tooling."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)