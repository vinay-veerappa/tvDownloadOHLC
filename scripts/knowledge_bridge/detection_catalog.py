"""Detection function catalog — maps KB prose concept names to executable
vectorized detection functions in ``ict_engine``.

This is the *prose → function* registry that Phase 3 of the KB DESIGN.md
roadmap requires. Each entry maps one or more KB transcript terms to a
detection function with its module path, signature, and metadata.

ADR compliance
--------------
- ADR-017 (Zero-Loop): All cataloged functions are vectorized NumPy/Pandas.
  Functions marked ``loop_safe=True`` use bounded event loops (not O(N) main
  path) and are safe under the Zero-Loop constraint.
- ADR-001 (Timezone): Functions accept UTC-naive inputs and use ET session
  windows internally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class DetectionEntry:
    """Single entry in the detection catalog.

    Attributes
    ----------
    concept : str
        Canonical ICT concept name (e.g., "Fair Value Gap").
    aliases : tuple[str, ...]
        Alternative names found in KB transcripts.
    category : str
        Concept group: "price_action", "structure", "liquidity",
        "sessions", "gaps", "htf", "retracements", "correlation",
        "cycles", "bias", "projections".
    module : str
        Dotted import path to the module containing the function.
    function_name : str
        Name of the detection function.
    input_kind : str
        Expected input: "ohlc", "ohlc_swings", "ohlc_fvg_df", "dual_ohlc",
        "ohlc_anchor", "ohlc_daily_intraday".
    output_kind : str
        Return type: "dataframe", "series", "scalar_df".
    vectorized : bool
        True if fully vectorized (ADR-017 compliant).
    loop_safe : bool
        True if uses bounded event loop (safe under ADR-017).
    description : str
        Human-readable description of what the function detects.
    params : tuple[str, ...]
        Optional parameters the function accepts.
    """

    concept: str
    aliases: Tuple[str, ...]
    category: str
    module: str
    function_name: str
    input_kind: str
    output_kind: str
    vectorized: bool
    loop_safe: bool
    description: str
    params: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def qualified_name(self) -> str:
        """``module.function_name`` string."""
        return f"{self.module}.{self.function_name}"

    def resolve(self) -> Callable[..., Any]:
        """Import and return the actual callable."""
        import importlib

        mod = importlib.import_module(self.module)
        fn = getattr(mod, self.function_name)
        if fn is None:
            raise AttributeError(
                f"{self.function_name} not found in {self.module}"
            )
        return fn


# ── Catalog entries ─────────────────────────────────────────────────────────
# Module path prefix for ict_engine
_E = "scripts.libs_py.ict_engine.core"


DETECTION_CATALOG: List[DetectionEntry] = [
    # ── Price Action ────────────────────────────────────────────────────────
    DetectionEntry(
        concept="Fair Value Gap",
        aliases=("FVG", "imbalance", "3-bar imbalance"),
        category="price_action",
        module=f"{_E}.pa",
        function_name="detect_fvg",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="3-bar FVG: bull (high[i-2] < low[i]), bear (low[i-2] > high[i]). "
                    "Optional consecutive merge and candle-direction filter.",
        params=("join_consecutive", "require_candle_direction", "resample_rule"),
    ),
    DetectionEntry(
        concept="Volume Imbalance",
        aliases=("VI", "body gap"),
        category="price_action",
        module=f"{_E}.pa",
        function_name="detect_volume_imbalance",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Gap between bodies of consecutive candles (close[i-1] vs open[i]).",
        params=("resample_rule",),
    ),
    DetectionEntry(
        concept="Inversion FVG",
        aliases=("IFVG",),
        category="price_action",
        module=f"{_E}.pa",
        function_name="detect_inversion_fvg",
        input_kind="ohlc_fvg_df",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Bullish FVG closed below → bearish inversion; bearish FVG closed above → bullish inversion.",
        params=(),
    ),
    DetectionEntry(
        concept="Balanced Price Range",
        aliases=("BPR",),
        category="price_action",
        module=f"{_E}.pa",
        function_name="detect_bpr",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Overlap zone where bullish and bearish FVGs intersect.",
        params=(),
    ),
    DetectionEntry(
        concept="Liquidity Void",
        aliases=("displacement candle",),
        category="price_action",
        module=f"{_E}.pa",
        function_name="detect_liquidity_void",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Large displacement candle (range > 2.5× 20-bar average).",
        params=(),
    ),
    DetectionEntry(
        concept="First FVG (hourly)",
        aliases=("first presented FVG",),
        category="price_action",
        module=f"{_E}.pa",
        function_name="detect_first_fvg_per_hour",
        input_kind="ohlc_fvg_df",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="First FVG after each H:00 open.",
        params=(),
    ),
    DetectionEntry(
        concept="First FVG after time",
        aliases=("first FVG after open",),
        category="price_action",
        module=f"{_E}.pa",
        function_name="detect_first_fvg_after_time",
        input_kind="ohlc_fvg_df",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Single first FVG after a specific target time (e.g., 09:30 NY open).",
        params=("time_str",),
    ),
    DetectionEntry(
        concept="FVG Mitigation",
        aliases=("FVG fill", "mitigation tracking"),
        category="price_action",
        module=f"{_E}.pa",
        function_name="check_fvg_mitigation",
        input_kind="ohlc_fvg_df",
        output_kind="series",
        vectorized=False,
        loop_safe=True,
        description="Tracks when price first touches each FVG level. Bounded loop over FVG events.",
        params=(),
    ),

    # ── Structure ───────────────────────────────────────────────────────────
    DetectionEntry(
        concept="Swing High/Low",
        aliases=("fractal", "pivot", "swing point"),
        category="structure",
        module=f"{_E}.structure",
        function_name="detect_swings",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Center-bar fractal: high == rolling_max(2N+1) → SH; low == rolling_min → SL.",
        params=("swing_length",),
    ),
    DetectionEntry(
        concept="Break of Structure",
        aliases=("BOS", "MSS", "Market Structure Shift"),
        category="structure",
        module=f"{_E}.structure",
        function_name="detect_structure_breaks",
        input_kind="ohlc_swings",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Close breaks tracked swing high (bullish) or swing low (bearish). "
                    "BOS=continuation, MSS=reversal.",
        params=(),
    ),
    DetectionEntry(
        concept="CISD (proxy)",
        aliases=("Change in State of Delivery",),
        category="structure",
        module=f"{_E}.structure",
        function_name="detect_cisd",
        input_kind="ohlc_swings",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Sweep-open proxy: after liquidity sweep, CISD fires when close exceeds "
                    "the sweep bar's open.",
        params=(),
    ),
    DetectionEntry(
        concept="CISD (authoritative)",
        aliases=("CISD authoritative",),
        category="structure",
        module=f"{_E}.structure",
        function_name="detect_cisd_authoritative",
        input_kind="ohlc_swings",
        output_kind="dataframe",
        vectorized=False,
        loop_safe=True,
        description="Authoritative ICT CISD: consecutive same-close-direction delivery series; "
                    "reference = open of FIRST candle in the run. ~14% false positive rate.",
        params=("displacement_ratio",),
    ),

    # ── Liquidity ───────────────────────────────────────────────────────────
    DetectionEntry(
        concept="Liquidity Pools",
        aliases=("BSL", "SSL", "EQH", "EQL", "buy side liquidity", "sell side liquidity"),
        category="liquidity",
        module=f"{_E}.pa",
        function_name="detect_liquidity",
        input_kind="ohlc_swings",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="BSL=swing highs, SSL=swing lows. EQH/EQL=equal highs/lows within tolerance.",
        params=("threshold",),
    ),
    DetectionEntry(
        concept="Order Block",
        aliases=("OB",),
        category="liquidity",
        module=f"{_E}.pa",
        function_name="detect_orderblock",
        input_kind="ohlc_swings",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Last down candle before bullish structure break (bull OB); "
                    "last up candle before bearish break (bear OB).",
        params=(),
    ),
    DetectionEntry(
        concept="Breaker Block",
        aliases=("breaker",),
        category="liquidity",
        module=f"{_E}.pa",
        function_name="detect_breaker",
        input_kind="ohlc_swings",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Failed OB that swept liquidity before being broken. "
                    "Bullish breaker = bearish OB broken above.",
        params=(),
    ),

    # ── Sessions / Killzones / Macros / Silver Bullets ──────────────────────
    DetectionEntry(
        concept="Killzone",
        aliases=("asian", "london_open", "ny_open", "london_close", "KZ"),
        category="sessions",
        module=f"{_E}.sessions",
        function_name="get_session_data",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Marks bars within killzone window; computes per-day session H/L. "
                    "Pass session_name: asian, london_open, ny_open, london_close.",
        params=("session_name", "timezone"),
    ),
    DetectionEntry(
        concept="ICT Macro",
        aliases=("macro", "macro window"),
        category="sessions",
        module=f"{_E}.sessions",
        function_name="get_macro_data",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Marks bars within ICT macro window; per-day macro H/L. "
                    "8 macros: london_macro_1/2, ny_am, ny_morning, ny_mid_morning, "
                    "ny_lunch_1/2, ny_last_hour.",
        params=("macro_name", "timezone"),
    ),
    DetectionEntry(
        concept="Silver Bullet",
        aliases=("SB", "silver bullet window"),
        category="sessions",
        module=f"{_E}.sessions",
        function_name="get_silver_bullet_data",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Silver Bullet window: london_sb (03:00-04:00), ny_am_sb (10:00-11:00), "
                    "ny_pm_sb (14:00-15:00). Running H/L.",
        params=("bullet_name", "timezone"),
    ),

    # ── Gaps ────────────────────────────────────────────────────────────────
    DetectionEntry(
        concept="Opening Gaps",
        aliases=("NWOG", "NDOG", "New Week Opening Gap", "New Day Opening Gap"),
        category="gaps",
        module=f"{_E}.gaps",
        function_name="detect_opening_gaps",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="NWOG if prev=Friday; NDOG if prev=Mon-Thu. Anchors on 18:00 ET session open.",
        params=("timezone",),
    ),
    DetectionEntry(
        concept="RTH Gap",
        aliases=("regular trading hours gap",),
        category="gaps",
        module=f"{_E}.gaps",
        function_name="detect_rth_gaps",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Today's 09:30 open vs previous day's 16:15 close.",
        params=("ticker", "timezone"),
    ),
    DetectionEntry(
        concept="Consequent Encroachment",
        aliases=("CE", "50% of gap"),
        category="gaps",
        module=f"{_E}.gaps",
        function_name="get_gap_consequent_encroachment",
        input_kind="ohlc",
        output_kind="series",
        vectorized=True,
        loop_safe=False,
        description="50% midpoint of detected gaps.",
        params=(),
    ),
    DetectionEntry(
        concept="Gap Fill",
        aliases=("gap fill tracking",),
        category="gaps",
        module=f"{_E}.gaps",
        function_name="detect_gap_fills",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=False,
        loop_safe=True,
        description="Tracks when price trades back into NWOG/NDOG/RTH gap zone. Bounded loop.",
        params=(),
    ),

    # ── HTF Levels & IPDA ───────────────────────────────────────────────────
    DetectionEntry(
        concept="HTF Levels",
        aliases=("PDH", "PDL", "PWH", "PWL", "PMH", "PML", "previous day high"),
        category="htf",
        module=f"{_E}.htf",
        function_name="detect_htf_levels",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Previous Day/Week/Month High/Low/Mid — forward-filled onto intraday index.",
        params=(),
    ),
    DetectionEntry(
        concept="IPDA Ranges",
        aliases=("IPDA", "20/40/60 range", "interbank price delivery"),
        category="htf",
        module=f"{_E}.htf",
        function_name="detect_ipda_ranges",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="IPDA 20/40/60 rolling dealing ranges. Excludes current daily candle. "
                    "Position pct = (close−low)/(high−low)×100.",
        params=(),
    ),

    # ── Retracements / Dealing Range ────────────────────────────────────────
    DetectionEntry(
        concept="Fibonacci Retracement",
        aliases=("OTE", "optimal trade entry", "retracement"),
        category="retracements",
        module=f"{_E}.retracements",
        function_name="calculate_retracements",
        input_kind="ohlc_swings",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Tracks impulse leg from last swing; computes retracement % (0.5, 0.618, 0.705, 0.786).",
        params=(),
    ),
    DetectionEntry(
        concept="Dealing Range",
        aliases=("premium", "discount", "equilibrium"),
        category="retracements",
        module=f"{_E}.retracements",
        function_name="detect_dealing_range",
        input_kind="ohlc_swings",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Price below 50% = discount (look for buys); above = premium (look for sells).",
        params=(),
    ),

    # ── Correlation ─────────────────────────────────────────────────────────
    DetectionEntry(
        concept="SMT Divergence",
        aliases=("SMT", "cross-asset divergence"),
        category="correlation",
        module=f"{_E}.correlation",
        function_name="detect_smt",
        input_kind="dual_ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Bullish SMT: A makes higher low while B makes lower low. "
                    "Bearish: A makes lower high while B makes higher high. "
                    "Primarily NQ vs ES vs YM.",
        params=(),
    ),

    # ── Cycles ──────────────────────────────────────────────────────────────
    DetectionEntry(
        concept="TTrades Fractal",
        aliases=("C1", "C2", "C3", "C4", "fractal cycle"),
        category="cycles",
        module=f"{_E}.cycles",
        function_name="detect_ttrade_fractal",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="C2 reversal (wick through prior extreme + reclaim) + C3 confirmation (directional close).",
        params=(),
    ),
    DetectionEntry(
        concept="Power of 3",
        aliases=("PO3", "AMD", "accumulation manipulation distribution"),
        category="cycles",
        module=f"{_E}.cycles",
        function_name="detect_po3",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=False,
        loop_safe=False,
        description="Power of 3 phases. NOTE: Currently a stub — returns empty phases.",
        params=("session_mask",),
    ),
    DetectionEntry(
        concept="Quarterly Theory",
        aliases=("90-min cycle", "quarterly cycle"),
        category="cycles",
        module=f"{_E}.cycles",
        function_name="quarterly_cycles",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=False,
        loop_safe=False,
        description="90-min quarterly cycles. NOTE: Currently a stub.",
        params=(),
    ),

    # ── Bias Models ─────────────────────────────────────────────────────────
    DetectionEntry(
        concept="MMXM Simple Bias",
        aliases=("200 EMA bias", "MMXM"),
        category="bias",
        module=f"{_E}.bias",
        function_name="detect_bias_mmxm_simple",
        input_kind="ohlc",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Price > 200 EMA (1H) = bullish; < = bearish.",
        params=(),
    ),
    DetectionEntry(
        concept="TTrades Mechanical Bias",
        aliases=("PDH PDL bias",),
        category="bias",
        module=f"{_E}.bias",
        function_name="detect_bias_ttrades_mechanical",
        input_kind="ohlc_daily_intraday",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Close above PDH=bull, below PDL=bear. Sweep+reclaim=potential reversal.",
        params=(),
    ),
    DetectionEntry(
        concept="Midnight Open Filter",
        aliases=("MOP", "midnight open"),
        category="bias",
        module=f"{_E}.bias",
        function_name="apply_midnight_open_filter",
        input_kind="ohlc",
        output_kind="series",
        vectorized=True,
        loop_safe=False,
        description="Bullish: buy below midnight open (discount); Bearish: sell above (premium).",
        params=(),
    ),

    # ── Projections ─────────────────────────────────────────────────────────
    DetectionEntry(
        concept="SD Projections",
        aliases=("standard deviation projection", "SD targets"),
        category="projections",
        module=f"{_E}.projections",
        function_name="sd_projections",
        input_kind="ohlc_anchor",
        output_kind="dataframe",
        vectorized=True,
        loop_safe=False,
        description="Projects SD levels (−2, −2.5, −4) from manipulation leg delta. Used for exit targets.",
        params=(),
    ),
]


# ── Lookup indices (built once) ─────────────────────────────────────────────

_CATALOG_BY_CONCEPT: Dict[str, DetectionEntry] = {}
_CATALOG_BY_ALIAS: Dict[str, DetectionEntry] = {}

for _entry in DETECTION_CATALOG:
    _CATALOG_BY_CONCEPT[_entry.concept.lower()] = _entry
    for _alias in _entry.aliases:
        _CATALOG_BY_ALIAS[_alias.lower()] = _entry


def resolve_detection(term: str) -> Optional[DetectionEntry]:
    """Resolve a KB prose term to a :class:`DetectionEntry`.

    Tries exact concept match first, then alias match (case-insensitive).
    Returns ``None`` if no match found.
    """
    key = term.lower().strip()
    if key in _CATALOG_BY_CONCEPT:
        return _CATALOG_BY_CONCEPT[key]
    return _CATALOG_BY_ALIAS.get(key)


def list_concepts() -> List[str]:
    """Return all canonical concept names."""
    return [e.concept for e in DETECTION_CATALOG]


def concepts_by_category() -> Dict[str, List[str]]:
    """Group concept names by category."""
    result: Dict[str, List[str]] = {}
    for entry in DETECTION_CATALOG:
        result.setdefault(entry.category, []).append(entry.concept)
    return result


def search_concepts(query: str) -> List[DetectionEntry]:
    """Fuzzy search concepts and aliases for a query string."""
    q = query.lower().strip()
    hits: List[DetectionEntry] = []
    for entry in DETECTION_CATALOG:
        if q in entry.concept.lower():
            hits.append(entry)
            continue
        if any(q in a.lower() for a in entry.aliases):
            hits.append(entry)
    return hits