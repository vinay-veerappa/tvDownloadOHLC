"""
state_tracker.py
================
Persist pipeline state between runs so that regime changes, GEX sign flips,
and pin migrations can be detected and alerted on.

Public API
----------
load_previous_state(path)       → PipelineState | None
save_current_state(state, path) → None
detect_changes(previous, current) → list[StateChange]
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import OUTPUT_DIR

log = logging.getLogger(__name__)

STATE_FILE: Path = OUTPUT_DIR / "pipeline_state.json"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TickerSnapshot:
    """Key metrics for one ticker at one point in time."""
    ticker: str
    total_gex: float
    gex_regime: str              # "POSITIVE" or "NEGATIVE"
    regime_label: str            # "PINNED", "TRENDING", "COILED", "BATTLE_ZONE", "NEUTRAL"
    directional_bias: str        # "BEARISH", "BULLISH", "NEUTRAL"
    gamma_magnet: float | None = None
    pin_strike: float | None = None
    pin_odds: float = 0
    wall_separation: float | None = None
    call_wall: float | None = None
    put_wall: float | None = None
    zero_gamma: float | None = None
    net_vanna_exposure: float = 0
    call_centroid: float | None = None
    put_centroid: float | None = None
    max_pain: float | None = None
    atm_iv: float | None = None
    spot: float = 0


@dataclass
class PipelineState:
    """Full pipeline state for one run."""
    run_label: str
    timestamp: str                          # ISO format UTC
    tickers: dict[str, TickerSnapshot] = field(default_factory=dict)


@dataclass
class StateChange:
    """One detected change between runs."""
    ticker: str
    change_type: str   # "GEX_FLIP", "REGIME_CHANGE", "PIN_SHIFT", "MAGNET_SHIFT", "GEX_SWING"
    severity: str      # "HIGH", "MEDIUM", "LOW"
    message: str       # Human-readable description
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_previous_state(path: Path = STATE_FILE) -> PipelineState | None:
    """Load the previous run's state from disk, or None if not found."""
    if not path.exists():
        log.info("No previous state file at %s — first run.", path)
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        tickers = {}
        for key, snap_raw in raw.get("tickers", {}).items():
            tickers[key] = TickerSnapshot(**snap_raw)
        return PipelineState(
            run_label=raw["run_label"],
            timestamp=raw["timestamp"],
            tickers=tickers,
        )
    except Exception as exc:
        log.warning("Could not load previous state: %s", exc)
        return None


def save_current_state(state: PipelineState, path: Path = STATE_FILE) -> None:
    """Write current state to disk for the next run to compare against."""
    doc = {
        "run_label": state.run_label,
        "timestamp": state.timestamp,
        "tickers": {key: asdict(snap) for key, snap in state.tickers.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    log.info("Pipeline state saved → %s", path)


def build_current_state(
    run_label: str,
    translated_levels: list,
    cash_levels_by_ticker: dict,
) -> PipelineState:
    """
    Build a PipelineState from the current run's outputs.

    Accepts both TranslatedLevels and DealerLevels objects.
    """
    state = PipelineState(
        run_label=run_label,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Translated futures levels (primary)
    for tl in translated_levels:
        ticker = tl.futures_symbol if hasattr(tl, 'futures_symbol') else tl.ticker
        spot = tl.futures_price if hasattr(tl, 'futures_price') else tl.spot
        state.tickers[ticker] = TickerSnapshot(
            ticker=ticker,
            total_gex=tl.total_gex,
            gex_regime=tl.gex_regime,
            regime_label=tl.regime_label,
            directional_bias=tl.directional_bias,
            gamma_magnet=tl.gamma_magnet,
            pin_strike=tl.pin_strike,
            pin_odds=tl.pin_odds,
            wall_separation=tl.wall_separation,
            call_wall=tl.call_wall,
            put_wall=tl.put_wall,
            zero_gamma=tl.zero_gamma,
            net_vanna_exposure=tl.net_vanna_exposure,
            call_centroid=getattr(tl, 'call_volume_centroid', None),
            put_centroid=getattr(tl, 'put_volume_centroid', None),
            max_pain=getattr(tl, 'max_pain', None),
            atm_iv=getattr(tl, 'atm_iv', None),
            spot=spot,
        )

    # Cash-space levels (secondary — stored for completeness)
    for ticker, levels in cash_levels_by_ticker.items():
        if ticker not in state.tickers:
            state.tickers[ticker] = TickerSnapshot(
                ticker=ticker,
                total_gex=levels.total_gex,
                gex_regime=levels.gex_regime,
                regime_label=levels.regime_label,
                directional_bias=levels.directional_bias,
                gamma_magnet=levels.gamma_magnet,
                pin_strike=levels.pin_strike,
                pin_odds=levels.pin_odds,
                wall_separation=levels.wall_separation,
                call_wall=levels.call_wall,
                put_wall=levels.put_wall,
                zero_gamma=levels.zero_gamma,
                net_vanna_exposure=levels.net_vanna_exposure,
                call_centroid=getattr(levels, 'call_volume_centroid', None),
                put_centroid=getattr(levels, 'put_volume_centroid', None),
                max_pain=getattr(levels, 'max_pain', None),
                atm_iv=getattr(levels, 'atm_iv', None),
                spot=levels.spot,
            )

    return state


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def detect_changes(
    previous: PipelineState | None,
    current: PipelineState,
) -> list[StateChange]:
    """
    Compare two pipeline states and return a list of actionable changes.

    Only compares tickers present in both states.
    """
    if previous is None:
        return []

    changes: list[StateChange] = []

    for ticker, curr in current.tickers.items():
        prev = previous.tickers.get(ticker)
        if prev is None:
            continue

        # 1. GEX sign flip — HIGH severity
        if prev.gex_regime != curr.gex_regime:
            changes.append(StateChange(
                ticker=ticker,
                change_type="GEX_FLIP",
                severity="HIGH",
                message=(
                    f"⚠️ GEX FLIPPED {prev.gex_regime} → {curr.gex_regime} for {ticker}. "
                    f"GEX went from {prev.total_gex:,.0f} to {curr.total_gex:,.0f}. "
                    f"{'Stop mean reverting — trend-follow now.' if curr.gex_regime == 'NEGATIVE' else 'Shift to mean-revert mode — fade moves to the walls.'}"
                ),
                details={
                    "prev_gex": prev.total_gex,
                    "curr_gex": curr.total_gex,
                    "prev_regime": prev.gex_regime,
                    "curr_regime": curr.gex_regime,
                },
            ))

        # 2. Regime label change — HIGH severity
        if prev.regime_label != curr.regime_label:
            changes.append(StateChange(
                ticker=ticker,
                change_type="REGIME_CHANGE",
                severity="HIGH",
                message=(
                    f"⚠️ REGIME CHANGE for {ticker}: {prev.regime_label} → {curr.regime_label}. "
                    f"Adjust your trading approach — the character of the day has shifted."
                ),
                details={
                    "prev_regime": prev.regime_label,
                    "curr_regime": curr.regime_label,
                },
            ))

        # 3. Large GEX swing (>30% change) without sign flip — MEDIUM severity
        if prev.total_gex != 0:
            gex_pct_change = abs(curr.total_gex - prev.total_gex) / abs(prev.total_gex)
            if gex_pct_change > 0.30 and prev.gex_regime == curr.gex_regime:
                direction = "strengthened" if abs(curr.total_gex) > abs(prev.total_gex) else "weakened"
                changes.append(StateChange(
                    ticker=ticker,
                    change_type="GEX_SWING",
                    severity="MEDIUM",
                    message=(
                        f"📊 GEX {direction} by {gex_pct_change:.0%} for {ticker} "
                        f"({prev.total_gex:,.0f} → {curr.total_gex:,.0f}). "
                        f"Regime is still {curr.gex_regime} but conviction {'increased' if direction == 'strengthened' else 'decreased'}."
                    ),
                    details={
                        "prev_gex": prev.total_gex,
                        "curr_gex": curr.total_gex,
                        "pct_change": round(gex_pct_change, 4),
                    },
                ))

        # 4. Pin strike migration — MEDIUM severity
        if (prev.pin_strike is not None and curr.pin_strike is not None
                and prev.pin_strike != curr.pin_strike):
            shift = curr.pin_strike - prev.pin_strike
            if curr.spot > 0 and abs(shift) / curr.spot > 0.002:  # >0.2% move
                changes.append(StateChange(
                    ticker=ticker,
                    change_type="PIN_SHIFT",
                    severity="MEDIUM",
                    message=(
                        f"📌 Pin strike shifted {shift:+.2f} for {ticker} "
                        f"({prev.pin_strike:.2f} → {curr.pin_strike:.2f}). "
                        f"Gravity has moved — update your targets."
                    ),
                    details={
                        "prev_pin": prev.pin_strike,
                        "curr_pin": curr.pin_strike,
                        "shift": round(shift, 2),
                    },
                ))

        # 5. Gamma magnet migration — LOW severity
        if (prev.gamma_magnet is not None and curr.gamma_magnet is not None
                and prev.gamma_magnet != curr.gamma_magnet):
            shift = curr.gamma_magnet - prev.gamma_magnet
            if curr.spot > 0 and abs(shift) / curr.spot > 0.001:  # >0.1% move
                changes.append(StateChange(
                    ticker=ticker,
                    change_type="MAGNET_SHIFT",
                    severity="LOW",
                    message=(
                        f"🧲 Gamma magnet drifted {shift:+.2f} for {ticker} "
                        f"({prev.gamma_magnet:.2f} → {curr.gamma_magnet:.2f})."
                    ),
                    details={
                        "prev_magnet": prev.gamma_magnet,
                        "curr_magnet": curr.gamma_magnet,
                        "shift": round(shift, 2),
                    },
                ))

    return changes


def format_change_alert(changes: list[StateChange], run_label: str) -> str | None:
    """Format a list of state changes into a single Discord-ready alert string."""
    if not changes:
        return None

    high = [c for c in changes if c.severity == "HIGH"]
    medium = [c for c in changes if c.severity == "MEDIUM"]
    low = [c for c in changes if c.severity == "LOW"]

    parts: list[str] = [f"**⚡ Regime Monitor — {run_label}**\n"]

    if high:
        parts.append("🔴 **HIGH PRIORITY**")
        for c in high:
            parts.append(c.message)
        parts.append("")

    if medium:
        parts.append("🟡 **MONITOR**")
        for c in medium:
            parts.append(c.message)
        parts.append("")

    if low:
        parts.append("ℹ️ **INFO**")
        for c in low:
            parts.append(c.message)

    return "\n".join(parts).strip()