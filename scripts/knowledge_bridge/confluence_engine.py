"""Confluence engine — Phase 5 of the KB DESIGN.md roadmap.

At runtime (intraday or premarket), derives confluences across domains from
live market data + KB knowledge. Per DESIGN §5.2:

1. **Live data input:** GEX levels, session timing, price structure, ICT features
2. **KB query:** Search for setups/concepts matching current conditions
3. **Candidate matching:** Which strategy candidates' trigger conditions are met?
4. **Confluence detection:** Cross-domain alignment:
   - ICT setup (CSD after BSL sweep) + GEX (negative gamma at price level) = confluence
   - Market structure (break/retest) + Volume profile (POC rejection) = confluence
5. **Output:** Trade plan with cited KB sources, confidence score, and risk params

Two modes
---------
- **Script mode** (default): Python checks signal providers against live data,
  matches candidates, and scores confluence deterministically.
- **LLM mode:** LLM reads KB units + live data, reasons about confluences, and
  generates a narrative trade plan with citations (via the narrative engine).

ADR compliance
--------------
- ADR-017: Signal scoring is vectorized NumPy where possible; no O(N) loops
  in the scoring path.
- ADR-001: All times are ET; storage is UTC epoch.
- ADR-002: Risk metrics are price %, not absolute points.
- ADR-020: Default max_exit_time = "16:00 ET".
- ADR-021: Trade plans are designed for ``PropFirmSimulator`` evaluation.

Design
------
The engine is modular: signal providers are pluggable callables that return
:class:`ConfluenceSignal` lists. The engine aggregates, weights, matches
against :class:`StrategyCandidate` triggers, queries the KB for grounded
citations, and emits a :class:`ConfluenceResult`.

    from scripts.knowledge_bridge.confluence_engine import (
        ConfluenceEngine, ConfluenceResult, ConfluenceSignal,
    )
    engine = ConfluenceEngine()
    result = engine.run(ticker="ES1")
    print(result.summary())
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

from .kb_context import (
    DEFAULT_KB_API_URL,
    CONCEPT_TRIGGERS,
    check_kb_api,
    detect_concepts,
    fetch_kb_context,
)

log = logging.getLogger(__name__)

# ── Domain weights (tunable) ─────────────────────────────────────────────────
# Higher weight = stronger vote. Cross-domain agreement multiplies via the
# geometric mean so a single strong domain cannot dominate when others are
# silent or contradictory.
DEFAULT_DOMAIN_WEIGHTS: Dict[str, float] = {
    "ict": 1.0,        # ICT structure (CSD, FVG, MSS, sweeps)
    "gex": 0.8,        # Options gamma positioning
    "structure": 0.7,  # Market structure (break/retest, range position)
    "session": 0.6,    # Session timing (killzones, macros, Silver Bullet)
    "bias": 0.9,       # Herman/ALN/FTFC directional bias
    "volume": 0.5,     # Volume profile / POC (planned — low weight until wired)
}

# Direction alignment bonus: when ≥3 domains agree on direction, boost.
DIRECTION_AGREEMENT_BONUS = 0.15
DIRECTION_AGREEMENT_THRESHOLD = 3


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class ConfluenceSignal:
    """One signal from one domain contributing to the confluence score.

    Attributes
    ----------
    domain : str
        Which domain produced this: "ict", "gex", "structure", "session",
        "bias", "volume".
    direction : str
        "long", "short", or "neutral".
    strength : float
        0.0–1.0. How strong this signal is within its domain.
    source : str
        Human-readable identifier of the provider (e.g. "herman_pre_ny_sweep").
    citation : str
        KB unit ID or live-data reference for audit.
    notes : str
        Free-text explanation.
    """

    domain: str
    direction: str
    strength: float
    source: str
    citation: str = ""
    notes: str = ""

    @property
    def signed_strength(self) -> float:
        """Strength with sign: + for long, − for short, 0 for neutral."""
        if self.direction == "long":
            return self.strength
        if self.direction == "short":
            return -self.strength
        return 0.0


@dataclass
class TradePlan:
    """Structured trade plan output from the confluence engine.

    All price levels are absolute (futures scale). Risk is expressed as
    price % per ADR-002.
    """

    direction: str  # "long", "short", "neutral"
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    risk_pct: Optional[float] = None  # (entry - stop) / entry * 100
    reward_pct: Optional[float] = None  # (target - entry) / entry * 100
    rr_ratio: Optional[float] = None
    max_exit_time: str = "16:00 ET"
    session_filter: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "risk_pct": self.risk_pct,
            "reward_pct": self.reward_pct,
            "rr_ratio": self.rr_ratio,
            "max_exit_time": self.max_exit_time,
            "session_filter": self.session_filter,
            "notes": self.notes,
        }


@dataclass
class ConfluenceResult:
    """Final output of a confluence engine run."""

    timestamp: str
    ticker: str
    direction: str  # consensus: "long", "short", "neutral"
    confidence: float  # 0–1 weighted
    signals: List[ConfluenceSignal] = field(default_factory=list)
    matched_candidate_ids: List[str] = field(default_factory=list)
    kb_citations: List[Dict[str, Any]] = field(default_factory=list)
    trade_plan: Optional[TradePlan] = None
    reasoning: str = ""

    def summary(self) -> str:
        """One-line summary suitable for logs/UI."""
        parts = [
            f"[{self.timestamp}] {self.ticker}",
            f"direction={self.direction}",
            f"confidence={self.confidence:.0%}",
            f"signals={len(self.signals)}",
            f"candidates={len(self.matched_candidate_ids)}",
            f"kb_units={len(self.kb_citations)}",
        ]
        if self.trade_plan:
            tp = self.trade_plan
            parts.append(
                f"plan={tp.direction}"
                f" entry={tp.entry}"
                f" stop={tp.stop}"
                f" target={tp.target}"
                f" RR={tp.rr_ratio}"
            )
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "ticker": self.ticker,
            "direction": self.direction,
            "confidence": self.confidence,
            "signals": [
                {
                    "domain": s.domain,
                    "direction": s.direction,
                    "strength": s.strength,
                    "source": s.source,
                    "citation": s.citation,
                    "notes": s.notes,
                }
                for s in self.signals
            ],
            "matched_candidate_ids": self.matched_candidate_ids,
            "kb_citations": self.kb_citations,
            "trade_plan": self.trade_plan.to_dict() if self.trade_plan else None,
            "reasoning": self.reasoning,
        }


# ── Signal provider protocol ────────────────────────────────────────────────
# A signal provider is a callable: (ctx: LiveContext) -> List[ConfluenceSignal]
# Providers are registered in the engine and called in sequence.

SignalProvider = Callable[["LiveContext"], List[ConfluenceSignal]]


@dataclass
class LiveContext:
    """Bag of live market data passed to signal providers.

    Populated lazily — providers read only the keys they need. This keeps
    the engine decoupled from any specific data loader.
    """

    ticker: str
    target_date: Optional[date] = None
    now_et: Optional[datetime] = None
    spot: Optional[float] = None
    nq_spot: Optional[float] = None
    es_spot: Optional[float] = None
    gex: Dict[str, Any] = field(default_factory=dict)
    session_ranges: Dict[str, Any] = field(default_factory=dict)
    herman_sweep: Dict[str, Any] = field(default_factory=dict)
    ict_features: Dict[str, Any] = field(default_factory=dict)
    overnight: Dict[str, Any] = field(default_factory=dict)
    classification: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


# ── Built-in signal providers ───────────────────────────────────────────────

def _gex_signal_provider(ctx: LiveContext) -> List[ConfluenceSignal]:
    """GEX gamma positioning signal.

    Negative gamma + spot below flip → bearish.
    Positive gamma + spot above flip → bullish.
    """
    gex = ctx.gex
    if not gex:
        return []

    spot = ctx.spot or ctx.nq_spot or ctx.es_spot
    if not spot:
        return []

    regime = gex.get("regime", "unknown")
    flip = gex.get("flip")
    call_wall = gex.get("call_wall")
    put_wall = gex.get("put_wall")

    signals: List[ConfluenceSignal] = []
    notes_parts = [f"regime={regime}"]

    if flip and call_wall and put_wall:
        if spot < flip:
            direction = "short"
            notes_parts.append(f"spot {spot:.2f} below flip {flip:.2f} → rips sold")
        elif spot > flip:
            direction = "long"
            notes_parts.append(f"spot {spot:.2f} above flip {flip:.2f} → dips bought")
        else:
            direction = "neutral"
            notes_parts.append("spot at flip — unstable")
        strength = 0.6 if regime == "negative" else 0.4
    else:
        direction = "neutral"
        strength = 0.3

    # Distance to walls adds context
    if call_wall and put_wall:
        notes_parts.append(f"call_wall={call_wall:.2f} put_wall={put_wall:.2f}")

    signals.append(ConfluenceSignal(
        domain="gex",
        direction=direction,
        strength=strength,
        source="gex_positioning",
        citation="live_macro_levels.json",
        notes=" | ".join(notes_parts),
    ))
    return signals


def _herman_sweep_signal_provider(ctx: LiveContext) -> List[ConfluenceSignal]:
    """Herman Pre-NY sweep — the DOMINANT bias signal (86.4% / 77.9%)."""
    sweep = ctx.herman_sweep
    if not sweep:
        return []

    bias = sweep.get("bias", "").lower()
    probability = sweep.get("probability", 0.0)
    dominant = sweep.get("dominant", False)
    label = sweep.get("label", "?")

    if "bull" in bias:
        direction = "long"
    elif "bear" in bias:
        direction = "short"
    else:
        direction = "neutral"

    strength = min(probability / 100.0, 1.0)
    if dominant:
        strength = max(strength, 0.85)

    return [ConfluenceSignal(
        domain="bias",
        direction=direction,
        strength=strength,
        source="herman_pre_ny_sweep",
        citation="herman_stats",
        notes=f"{label} | bias={bias} | prob={probability:.1f}% | dominant={dominant}",
    )]


def _session_signal_provider(ctx: LiveContext) -> List[ConfluenceSignal]:
    """Session timing signal — killzones, Silver Bullet windows, macros.

    Signals are neutral on direction (they're timing gates, not directional),
    but contribute a "session active" signal that boosts confluence when an
    ICT setup window is open.
    """
    now = ctx.now_et
    if not now:
        return []

    hour = now.hour
    minute = now.minute
    t = hour + minute / 60.0  # ET hour fraction

    signals: List[ConfluenceSignal] = []

    # Silver Bullet windows (ICT): 10:00-11:00, 13:30-14:30, (15:00-16:00 London)
    sb_windows = [(10.0, 11.0), (13.5, 14.5)]
    for start, end in sb_windows:
        if start <= t < end:
            signals.append(ConfluenceSignal(
                domain="session",
                direction="neutral",
                strength=0.5,
                source="silver_bullet_window",
                citation="ict_killzones",
                notes=f"Silver Bullet window active ({start:.0f}:00–{end:.0f}:00 ET)",
            ))
            break

    # Killzones: London 02:00-05:00, NY AM 09:30-12:00, NY PM 13:30-16:00
    kz_windows = [("london", 2.0, 5.0), ("ny_am", 9.5, 12.0), ("ny_pm", 13.5, 16.0)]
    for name, start, end in kz_windows:
        if start <= t < end:
            signals.append(ConfluenceSignal(
                domain="session",
                direction="neutral",
                strength=0.4,
                source=f"killzone_{name}",
                citation="ict_killzones",
                notes=f"{name} killzone active ({start:.1f}–{end:.1f} ET)",
            ))
            break

    # Macros: 9:12, 10:10, 11:15, 13:20, 15:15 (approximate)
    macro_minutes = {9 * 60 + 12, 10 * 60 + 10, 11 * 60 + 15, 13 * 60 + 20, 15 * 60 + 15}
    current_minute = hour * 60 + minute
    for mm in macro_minutes:
        if abs(current_minute - mm) <= 2:
            signals.append(ConfluenceSignal(
                domain="session",
                direction="neutral",
                strength=0.6,
                source="macro_window",
                citation="ict_macros",
                notes=f"Macro window near {mm // 60:02d}:{mm % 60:02d} ET",
            ))
            break

    return signals


def _ict_features_signal_provider(ctx: LiveContext) -> List[ConfluenceSignal]:
    """ICT features signal — FVG, order blocks, MSS/BOS, IPDA levels from precomputed pipeline.

    Reads the ``ict_features`` dict in the context, which should contain
    the output of ``scripts.context.compute_ict_features`` for the current
    ticker/session.
    """
    feats = ctx.ict_features
    if not feats:
        return []

    spot = ctx.spot or ctx.nq_spot or ctx.es_spot
    signals: List[ConfluenceSignal] = []

    # FVG confluence: if spot is near an unfilled FVG, signal direction based
    # on gap type (bullish FVG below = long magnet, bearish FVG above = short magnet)
    fvgs = feats.get("fvgs", [])
    for fvg in fvgs[:3]:  # top 3 nearest
        fvg_dir = fvg.get("type", "").lower()
        fvg_high = fvg.get("high")
        fvg_low = fvg.get("low")
        if not (fvg_high and fvg_low and spot):
            continue
        # Near = within 0.3% of spot
        near = abs(spot - (fvg_high + fvg_low) / 2) / spot < 0.003
        if not near:
            continue
        direction = "long" if "bull" in fvg_dir else "short" if "bear" in fvg_dir else "neutral"
        signals.append(ConfluenceSignal(
            domain="ict",
            direction=direction,
            strength=0.55,
            source="fvg_proximity",
            citation=f"ict_features:{fvg.get('id', '?')}",
            notes=f"FVG {fvg_dir} [{fvg_low:.2f}–{fvg_high:.2f}] near spot {spot:.2f}",
        ))

    # MSS/BOS: if a recent structure shift is detected
    mss = feats.get("mss", {})
    if mss:
        mss_dir = mss.get("direction", "").lower()
        direction = "long" if "bull" in mss_dir else "short" if "bear" in mss_dir else "neutral"
        signals.append(ConfluenceSignal(
            domain="ict",
            direction=direction,
            strength=0.6,
            source="mss_break",
            citation=f"ict_features:mss",
            notes=f"MSS {mss_dir} at {mss.get('price', '?')}",
        ))

    # IPDA levels: 20/40/60 — if spot is testing one, signal
    ipda = feats.get("ipda_levels", {})
    for level_name in ("ipda_20", "ipda_40", "ipda_60"):
        lvl = ipda.get(level_name)
        if lvl and spot:
            near = abs(spot - lvl) / spot < 0.002
            if near:
                signals.append(ConfluenceSignal(
                    domain="ict",
                    direction="neutral",  # IPDA is a magnet, direction depends on side
                    strength=0.5,
                    source="ipda_level_test",
                    citation=f"ict_features:{level_name}",
                    notes=f"{level_name}={lvl:.2f} tested by spot {spot:.2f}",
                ))

    return signals


def _structure_signal_provider(ctx: LiveContext) -> List[ConfluenceSignal]:
    """Market structure signal — range position, breakout vs inside.

    Uses ``session_ranges`` from the context. If price is at the high of a
    tight range → short (resistance). At the low → long (support). Breakout
    → direction of break.
    """
    ranges = ctx.session_ranges
    if not ranges:
        return []

    spot = ctx.spot or ctx.nq_spot or ctx.es_spot
    if not spot:
        return []

    # Prefer the tightest active range
    for key in ("MICRO_15", "MICRO_5", "SHORT_60", "SESSION", "RTH"):
        r = ranges.get(key)
        if not r:
            continue
        high = r.get("high")
        low = r.get("low")
        if not (high and low):
            continue
        width_pct = r.get("width_pct", 0)
        pos_pct = r.get("position_pct", 50)
        is_inside = r.get("is_inside", True)
        breakout = r.get("breakout")

        if breakout:
            direction = "long" if breakout == "up" else "short"
            return [ConfluenceSignal(
                domain="structure",
                direction=direction,
                strength=0.65,
                source=f"range_breakout_{key}",
                citation=f"range_detection:{key}",
                notes=f"{key} breakout {breakout} | width={width_pct:.2f}%",
            )]

        if not is_inside:
            return []

        # Inside range: position-based
        if pos_pct >= 90:
            direction = "short"
            strength = 0.5
            note = f"{key} at top ({pos_pct:.0f}%) — resistance"
        elif pos_pct <= 10:
            direction = "long"
            strength = 0.5
            note = f"{key} at bottom ({pos_pct:.0f}%) — support"
        else:
            direction = "neutral"
            strength = 0.3
            note = f"{key} mid-range ({pos_pct:.0f}%)"

        return [ConfluenceSignal(
            domain="structure",
            direction=direction,
            strength=strength,
            source=f"range_position_{key}",
            citation=f"range_detection:{key}",
            notes=note,
        )]

    return []


def _classification_signal_provider(ctx: LiveContext) -> List[ConfluenceSignal]:
    """Daily classification bias signal — R1/R2/DWP/DNP probabilities."""
    cls = ctx.classification
    if not cls:
        return []

    # Overnight key → directional bias
    overnight_key = cls.get("overnight_key", "")
    # R2 = reversal (often counter-trend), R1 = trend continuation
    most_likely = cls.get("most_likely_outcome", "")
    probabilities = cls.get("overnight_probabilities", {})

    if not probabilities:
        return []

    # Map outcomes to directional bias
    # R1 = trend day (follow overnight direction), R2 = reversal
    r1_prob = probabilities.get("R1", 0)
    r2_prob = probabilities.get("R2", 0)

    overnight_dir = ctx.overnight.get("change_pct", 0)
    if overnight_dir > 0 and r1_prob > r2_prob:
        direction = "long"
        strength = r1_prob / 100.0
        note = f"R1={r1_prob:.0f}% (trend follow) | overnight +{overnight_dir:.2f}%"
    elif overnight_dir < 0 and r1_prob > r2_prob:
        direction = "short"
        strength = r1_prob / 100.0
        note = f"R1={r1_prob:.0f}% (trend follow) | overnight {overnight_dir:.2f}%"
    elif r2_prob > r1_prob:
        # Reversal: fade overnight direction
        direction = "short" if overnight_dir > 0 else "long" if overnight_dir < 0 else "neutral"
        strength = r2_prob / 100.0 * 0.7  # reversal is less reliable
        note = f"R2={r2_prob:.0f}% (reversal) | overnight {overnight_dir:+.2f}%"
    else:
        direction = "neutral"
        strength = 0.3
        note = f"R1={r1_prob:.0f}% R2={r2_prob:.0f}% — unclear"

    return [ConfluenceSignal(
        domain="bias",
        direction=direction,
        strength=strength,
        source="daily_classification",
        citation="daily_classification_bias",
        notes=note,
    )]


# ── Confluence engine ────────────────────────────────────────────────────────

DEFAULT_PROVIDERS: List[SignalProvider] = [
    _gex_signal_provider,
    _herman_sweep_signal_provider,
    _session_signal_provider,
    _ict_features_signal_provider,
    _structure_signal_provider,
    _classification_signal_provider,
]


class ConfluenceEngine:
    """Runtime cross-domain confluence detector.

    Parameters
    ----------
    kb_api_url : str
        KB API base URL for grounded citations.
    providers : list[SignalProvider], optional
        Custom signal providers. Defaults to :data:`DEFAULT_PROVIDERS`.
    domain_weights : dict[str, float], optional
        Per-domain weight overrides. Merged with :data:`DEFAULT_DOMAIN_WEIGHTS`.
    max_exit_time : str
        ADR-020 default max exit time.
    """

    def __init__(
        self,
        kb_api_url: str = DEFAULT_KB_API_URL,
        providers: Optional[List[SignalProvider]] = None,
        domain_weights: Optional[Dict[str, float]] = None,
        max_exit_time: str = "16:00 ET",
    ):
        self.kb_api_url = kb_api_url
        self.providers = providers if providers is not None else list(DEFAULT_PROVIDERS)
        self.domain_weights = {**DEFAULT_DOMAIN_WEIGHTS, **(domain_weights or {})}
        self.max_exit_time = max_exit_time

    # ── Live context population ─────────────────────────────────────────────

    def build_context(
        self,
        ticker: str,
        target_date: Optional[date] = None,
        now_et: Optional[datetime] = None,
    ) -> LiveContext:
        """Populate a :class:`LiveContext` from live data sources.

        This is a thin orchestrator that calls into existing briefing_core /
        signal modules. Each section is wrapped in try/except so a single
        failing provider doesn't kill the whole engine.
        """
        import pytz

        et = pytz.timezone("America/New_York")
        resolved_now_et = now_et or datetime.now(et)
        resolved_target_date = target_date or resolved_now_et.date()
        today_et = datetime.now(et).date()
        historical_mode = resolved_target_date != today_et

        ctx = LiveContext(ticker=ticker, target_date=resolved_target_date, now_et=resolved_now_et)
        ctx.extra["historical_mode"] = historical_mode

        # Spot price + overnight
        try:
            from scripts.trader.briefing_core import build_overnight_context, get_dataloader
            loader = get_dataloader(lookback_days=5)
            on_ctx = build_overnight_context(loader, ticker, resolved_target_date)
            ctx.overnight = on_ctx
            ctx.spot = on_ctx.get("close")
            if ticker.startswith("NQ"):
                ctx.nq_spot = ctx.spot
            elif ticker.startswith("ES"):
                ctx.es_spot = ctx.spot
        except Exception as e:
            log.debug("[confluence] overnight context failed: %s", e)

        # GEX
        if historical_mode:
            # Historical replay has no dated GEX snapshots yet. Skip gracefully
            # so the remaining providers can still produce a plan.
            ctx.extra["gex_skipped"] = "historical_mode"
        else:
            try:
                from scripts.trader.briefing_core import load_macro_levels, _extract_gex_levels
                unified = load_macro_levels(session="live")
                ticker_key = "NQ" if ticker.startswith("NQ") else "ES" if ticker.startswith("ES") else ticker
                proxy = unified.get(ticker_key) or unified.get("QQQ" if ticker_key == "NQ" else "SPY") or {}
                gex = _extract_gex_levels(proxy, ticker_key)
                ctx.gex = gex
            except Exception as e:
                log.debug("[confluence] GEX failed: %s", e)

        # Herman Pre-NY sweep
        try:
            from scripts.libs_py.nqstats.classifiers import compute_herman_pre_ny_sweep
            from scripts.trader.signals.session_ranges import compute_all_session_ranges
            from scripts.utils.fused_data_loader import load_fused_data
            ET = et
            df = load_fused_data(ticker, timeframe="1m", require_historical=False)
            if df is not None and not df.empty:
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC").tz_convert(ET)
                elif df.index.tz != ET:
                    df.index = df.index.tz_convert(ET)
                sr = compute_all_session_ranges(df, resolved_target_date, ET)
                pre_ny = sr.get("PRE_NY", {})
                london = sr.get("LONDON", {})
                ctx.session_ranges = sr
                if pre_ny and london:
                    ctx.herman_sweep = compute_herman_pre_ny_sweep(
                        pre_ny, london.get("high"), london.get("low")
                    )
        except Exception as e:
            log.debug("[confluence] Herman sweep failed: %s", e)

        # ICT features (precomputed)
        try:
            import json
            from pathlib import Path
            feats_dir = Path("data/derived")
            dated_name = f"{ticker}_ict_features_{resolved_target_date.isoformat()}.json"
            latest_name = f"{ticker}_ict_features_latest.json"
            feats_path = feats_dir / (dated_name if historical_mode else latest_name)
            if feats_path.exists():
                ctx.ict_features = json.loads(feats_path.read_text(encoding="utf-8"))
            elif historical_mode:
                # Best-effort fallback for historical runs without dated features.
                ctx.extra["ict_features_skipped"] = f"missing:{dated_name}"
            elif (feats_dir / latest_name).exists():
                ctx.ict_features = json.loads((feats_dir / latest_name).read_text(encoding="utf-8"))
        except Exception as e:
            log.debug("[confluence] ICT features failed: %s", e)

        # Classification
        try:
            import scripts.analysis.analyze_daily_classification_bias as class_module
            import sys
            from datetime import timedelta
            orig_argv = sys.argv
            yesterday = resolved_target_date - timedelta(days=1)
            sys.argv = ["analyze_daily_classification_bias.py", "--ticker", ticker, "--date", yesterday.isoformat()]
            _, class_data = class_module.main()
            sys.argv = orig_argv
            ctx.classification = class_data
        except Exception as e:
            log.debug("[confluence] classification failed: %s", e)

        return ctx

    # ── Core run ─────────────────────────────────────────────────────────────

    def run(
        self,
        ticker: str = "ES1",
        target_date: Optional[date] = None,
        now_et: Optional[datetime] = None,
        candidates: Optional[Sequence[Any]] = None,
    ) -> ConfluenceResult:
        """Run the confluence engine for one ticker.

        Parameters
        ----------
        ticker : str
            Ticker symbol (e.g. "ES1", "NQ1").
        target_date : date, optional
            Target date for data resolution. Defaults to today.
        now_et : datetime, optional
            Current ET timestamp for session timing. Defaults to now.
        candidates : list[StrategyCandidate], optional
            Pre-loaded candidates to match against. If omitted, candidate
            matching is skipped (signals-only mode).
        """
        if now_et is None:
            import pytz
            now_et = datetime.now(pytz.timezone("America/New_York"))
        if target_date is None:
            target_date = now_et.date()

        ctx = self.build_context(ticker, target_date, now_et)

        # Gather signals from all providers
        all_signals: List[ConfluenceSignal] = []
        for provider in self.providers:
            try:
                sigs = provider(ctx)
                all_signals.extend(sigs)
            except Exception as e:
                log.warning("[confluence] provider %s failed: %s", provider.__name__, e)

        # Score confluence
        direction, confidence, reasoning = self._score_confluence(all_signals)

        # Match candidates
        matched_ids: List[str] = []
        if candidates:
            matched_ids = self._match_candidates(all_signals, candidates)

        # Query KB for grounded citations
        kb_citations = self._query_kb_citations(all_signals, ctx)

        # Build trade plan
        trade_plan = self._build_trade_plan(direction, confidence, ctx, all_signals)

        return ConfluenceResult(
            timestamp=now_et.isoformat(),
            ticker=ticker,
            direction=direction,
            confidence=confidence,
            signals=all_signals,
            matched_candidate_ids=matched_ids,
            kb_citations=kb_citations,
            trade_plan=trade_plan,
            reasoning=reasoning,
        )

    # ── Scoring ──────────────────────────────────────────────────────────────

    def _score_confluence(
        self, signals: List[ConfluenceSignal]
    ) -> tuple[str, float, str]:
        """Compute consensus direction, confidence (0–1), and reasoning text.

        Uses a weighted signed-strength aggregate:
        - Each signal contributes ``weight * signed_strength``.
        - The aggregate is normalized to [−1, +1] by total weight.
        - Confidence = |aggregate| + direction-agreement bonus.
        """
        if not signals:
            return "neutral", 0.0, "No signals available."

        # Aggregate signed strength per domain
        domain_scores: Dict[str, float] = {}  # domain → weighted signed sum
        domain_weights_used: Dict[str, float] = {}
        for sig in signals:
            w = self.domain_weights.get(sig.domain, 0.5)
            s = sig.signed_strength * w
            domain_scores[sig.domain] = domain_scores.get(sig.domain, 0.0) + s
            domain_weights_used[sig.domain] = domain_weights_used.get(sig.domain, 0.0) + w

        # Net aggregate (normalized by total weight)
        total_weight = sum(domain_weights_used.values()) or 1.0
        net = sum(domain_scores.values()) / total_weight  # [-1, +1]

        # Consensus direction
        if net > 0.15:
            direction = "long"
        elif net < -0.15:
            direction = "short"
        else:
            direction = "neutral"

        # Direction agreement: count domains that agree with consensus
        agreeing = 0
        for domain, score in domain_scores.items():
            if direction == "long" and score > 0:
                agreeing += 1
            elif direction == "short" and score < 0:
                agreeing += 1
            elif direction == "neutral":
                agreeing += 1  # neutral counts as non-conflicting

        agreement_bonus = DIRECTION_AGREEMENT_BONUS if agreeing >= DIRECTION_AGREEMENT_THRESHOLD else 0.0
        confidence = min(abs(net) + agreement_bonus, 1.0)

        # Reasoning
        parts = [f"net={net:+.2f}", f"agreeing_domains={agreeing}/{len(domain_scores)}"]
        for domain, score in sorted(domain_scores.items(), key=lambda kv: -abs(kv[1])):
            parts.append(f"{domain}={score:+.2f}")
        reasoning = " | ".join(parts)

        return direction, confidence, reasoning

    # ── Candidate matching ──────────────────────────────────────────────────

    def _match_candidates(
        self,
        signals: List[ConfluenceSignal],
        candidates: Sequence[Any],
    ) -> List[str]:
        """Match signals against candidates' trigger concepts.

        A candidate "matches" if its consensus direction agrees with the
        candidate's ``direction`` (or is "both") AND at least one of its
        detection-step concepts is cited by a signal source.
        """
        # Collect signal sources for matching
        signal_sources = {s.source.lower() for s in signals}
        signal_direction = next(
            (s.direction for s in signals if s.direction != "neutral"),
            "neutral",
        )

        matched: List[str] = []
        for cand in candidates:
            # Direction agreement
            cand_dir = getattr(cand, "direction", "both")
            if cand_dir != "both" and cand_dir != signal_direction and signal_direction != "neutral":
                continue

            # Concept overlap: check if any detection step concept appears in signals
            steps = getattr(cand, "detection_steps", [])
            cand_concepts = {s.concept.lower() for s in steps}
            # Check signal notes and sources for concept mentions
            signal_text = " ".join(s.notes + " " + s.source for s in signals).lower()
            overlap = sum(1 for c in cand_concepts if c and c in signal_text)
            if overlap == 0:
                continue

            matched.append(getattr(cand, "candidate_id", "?"))

        return matched

    # ── KB citations ─────────────────────────────────────────────────────────

    def _query_kb_citations(
        self,
        signals: List[ConfluenceSignal],
        ctx: LiveContext,
    ) -> List[Dict[str, Any]]:
        """Query the KB for grounded citations matching detected signals.

        Builds a pseudo-cheat-sheet from signal notes and uses
        :func:`fetch_kb_context` to retrieve matching KB units.
        """
        if not check_kb_api(self.kb_api_url):
            return []

        # Build a text blob from signals for concept detection
        text_blob = "\n".join(
            f"{s.source}: {s.notes}" for s in signals if s.notes
        )
        if not text_blob:
            return []

        # Fetch KB context
        kb_text = fetch_kb_context(text_blob, kb_api_url=self.kb_api_url, max_context_chars=1500)
        if not kb_text:
            return []

        # Parse the KB context block back into unit dicts (best-effort)
        # The format is: [ktype] source_file (conf=X)\n  Concepts: ...\n  Summary: ...\n  Anchor: ...
        units: List[Dict[str, Any]] = []
        current: Dict[str, Any] = {}
        for line in kb_text.split("\n"):
            if line.startswith("[") and "]" in line:
                if current:
                    units.append(current)
                ktype = line[1:line.index("]")].strip()
                rest = line[line.index("]") + 1:].strip()
                # rest = "source_file (conf=X)"
                source_file = rest
                conf = 0.0
                if "(conf=" in rest:
                    source_file = rest[:rest.rindex("(conf=")].strip()
                    conf_str = rest[rest.rindex("(conf=") + 6:rest.rindex(")")]
                    try:
                        conf = float(conf_str)
                    except ValueError:
                        pass
                current = {"knowledge_type": ktype, "source_file": source_file, "confidence": conf}
            elif line.startswith("  Concepts:"):
                current["concepts"] = line[len("  Concepts:"):].strip()
            elif line.startswith("  Summary:"):
                current["summary"] = line[len("  Summary:"):].strip()
            elif line.startswith("  Anchor:"):
                current["verbatim_anchor"] = line[len("  Anchor:"):].strip()
        if current:
            units.append(current)

        return units

    # ── Trade plan builder ───────────────────────────────────────────────────

    def _build_trade_plan(
        self,
        direction: str,
        confidence: float,
        ctx: LiveContext,
        signals: List[ConfluenceSignal],
    ) -> Optional[TradePlan]:
        """Build a structured trade plan from the confluence result.

        Uses GEX walls + session ranges for entry/stop/target when available.
        Returns ``None`` if direction is neutral or insufficient data.
        """
        if direction == "neutral" or confidence < 0.2:
            return None

        spot = ctx.spot or ctx.nq_spot or ctx.es_spot
        if not spot:
            return None

        gex = ctx.gex
        ranges = ctx.session_ranges

        # Determine entry/stop/target from available levels
        if direction == "long":
            entry = spot
            # Stop below nearest support (put wall or range low)
            stop = gex.get("put_wall") if gex else None
            if not stop:
                # Use tightest range low
                for key in ("MICRO_15", "MICRO_5", "SESSION", "RTH"):
                    r = ranges.get(key, {}) if ranges else {}
                    if r.get("low"):
                        stop = r["low"]
                        break
            if stop and stop >= entry:
                stop = None  # invalid
            # Target at call wall or range high
            target = gex.get("call_wall") if gex else None
            if not target:
                for key in ("MICRO_15", "MICRO_5", "SESSION", "RTH"):
                    r = ranges.get(key, {}) if ranges else {}
                    if r.get("high"):
                        target = r["high"]
                        break
            if target and target <= entry:
                target = None
        else:  # short
            entry = spot
            stop = gex.get("call_wall") if gex else None
            if not stop:
                for key in ("MICRO_15", "MICRO_5", "SESSION", "RTH"):
                    r = ranges.get(key, {}) if ranges else {}
                    if r.get("high"):
                        stop = r["high"]
                        break
            if stop and stop <= entry:
                stop = None
            target = gex.get("put_wall") if gex else None
            if not target:
                for key in ("MICRO_15", "MICRO_5", "SESSION", "RTH"):
                    r = ranges.get(key, {}) if ranges else {}
                    if r.get("low"):
                        target = r["low"]
                        break
            if target and target >= entry:
                target = None

        # Compute risk/reward in price % (ADR-002)
        risk_pct = None
        reward_pct = None
        rr_ratio = None
        if entry and stop:
            risk_pct = abs((entry - stop) / entry * 100)
        if entry and target:
            reward_pct = abs((target - entry) / entry * 100)
        if risk_pct and reward_pct and risk_pct > 0:
            rr_ratio = round(reward_pct / risk_pct, 2)

        # Session filter from signals
        session_filter = None
        for s in signals:
            if s.domain == "session" and "killzone" in s.source:
                session_filter = s.source.replace("killzone_", "")
                break
            if s.domain == "session" and "silver_bullet" in s.source:
                session_filter = "silver_bullet"
                break

        notes_parts = [f"confidence={confidence:.0%}", f"signals={len(signals)}"]
        if not stop:
            notes_parts.append("no valid stop level — manual stop required")
        if not target:
            notes_parts.append("no valid target level — manual target required")

        return TradePlan(
            direction=direction,
            entry=round(entry, 2) if entry else None,
            stop=round(stop, 2) if stop else None,
            target=round(target, 2) if target else None,
            risk_pct=round(risk_pct, 3) if risk_pct else None,
            reward_pct=round(reward_pct, 3) if reward_pct else None,
            rr_ratio=rr_ratio,
            max_exit_time=self.max_exit_time,
            session_filter=session_filter,
            notes=" | ".join(notes_parts),
        )


# ── CLI entry point ──────────────────────────────────────────────────────────

def main():
    """CLI: ``python -m scripts.knowledge_bridge.confluence_engine --ticker ES1``"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Confluence engine — runtime cross-domain confluence detection.")
    parser.add_argument("--ticker", default="ES1", help="Ticker (default ES1).")
    parser.add_argument("--kb-url", default=DEFAULT_KB_API_URL, help="KB API URL.")
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    parser.add_argument("--candidates", default=None, help="Path to candidates JSON file for matching.")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (historical replay mode).")
    parser.add_argument("--time", default=None, help="ET time HH:MM (defaults to 09:30 in --date mode).")
    args = parser.parse_args()

    engine = ConfluenceEngine(kb_api_url=args.kb_url)

    candidates = None
    if args.candidates:
        from pathlib import Path
        from .candidate_export import load_candidates_json
        candidates = load_candidates_json(Path(args.candidates))

    run_target_date: Optional[date] = None
    run_now_et: Optional[datetime] = None
    if args.date:
        import pytz

        run_target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        hhmm = args.time or "09:30"
        hh, mm = [int(x) for x in hhmm.split(":", 1)]
        run_now_et = pytz.timezone("America/New_York").localize(
            datetime.combine(run_target_date, datetime.min.time()).replace(hour=hh, minute=mm)
        )

    result = engine.run(
        ticker=args.ticker,
        target_date=run_target_date,
        now_et=run_now_et,
        candidates=candidates,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print()
        print("=" * 70)
        print("CONFLUENCE ENGINE RESULT")
        print("=" * 70)
        print(result.summary())
        print()
        print("-- SIGNALS --")
        for s in result.signals:
            print(f"  [{s.domain:10s}] {s.direction:7s} str={s.strength:.2f} | {s.source}: {s.notes}")
        print()
        if result.kb_citations:
            print(f"-- KB CITATIONS ({len(result.kb_citations)} units) --")
            for u in result.kb_citations:
                print(f"  [{u.get('knowledge_type', '?')}] {u.get('source_file', '?')} (conf={u.get('confidence', 0):.2f})")
                print(f"    {u.get('summary', '')[:120]}")
            print()
        if result.trade_plan:
            tp = result.trade_plan
            print("-- TRADE PLAN --")
            print(f"  Direction: {tp.direction}")
            print(f"  Entry:     {tp.entry}")
            print(f"  Stop:      {tp.stop}  (risk {tp.risk_pct}%)")
            print(f"  Target:    {tp.target}  (reward {tp.reward_pct}%)")
            print(f"  RR Ratio:  {tp.rr_ratio}")
            print(f"  Max Exit:  {tp.max_exit_time}")
            print(f"  Session:   {tp.session_filter or 'any'}")
            print(f"  Notes:     {tp.notes}")
        else:
            print("-- TRADE PLAN: None (neutral or low confidence) --")
        print()
        print(f"Reasoning: {result.reasoning}")
        print("=" * 70)


if __name__ == "__main__":
    main()


__all__ = [
    "ConfluenceEngine",
    "ConfluenceResult",
    "ConfluenceSignal",
    "TradePlan",
    "LiveContext",
    "SignalProvider",
    "DEFAULT_PROVIDERS",
    "DEFAULT_DOMAIN_WEIGHTS",
]