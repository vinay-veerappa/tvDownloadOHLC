"""reasoner.py — the chart agent's verdict emitter (Phase 2 — corrected data).

A minimal reasoner that:
  1. Loads pre-computed ICT features from ict_data_loader
  2. Retrieves KB context via kb_context.fetch_kb_context()
  3. Assembles a prompt using the daily_bias_mtf v0.5 schema
  4. Calls the LLM (reusing trader_narrative's call_ollama pattern)
  5. Returns a structured YAML verdict

The LLM's built-in ICT knowledge does the interpretation — we feed it
ground-truth numbers + KB context + the schema, and it reasons through
the ICT framework. We do NOT reinvent ICT logic in Python.

Usage:
    python -m scripts.trader.chart_agent.reasoner --ticker ES1
    python -m scripts.trader.chart_agent.reasoner --ticker NQ1 --model gemma4:31b-cloud
    python -m scripts.trader.chart_agent.reasoner --ticker ES1 --save
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, date
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_REPO))

# Load .env file if it exists
_env_file = _REPO / ".env"
if _env_file.exists():
    with open(_env_file, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                if _k not in os.environ:
                    os.environ[_k] = _v

from scripts.trader import _path_setup  # noqa: F401 — side-effect sys.path
from scripts.trader.config_loader import get_llm_config
from scripts.trader.signals.ict_data_loader import (
    load_ict_context,
    compute_ict_daily_bias,
    load_ipda,
    load_kz_pivots,
    load_gaps,
    load_imbalances,
    load_orderblocks,
    load_liquidity,
    load_structure,
    load_imbalances_filtered,
    load_orderblocks_filtered,
    load_liquidity_filtered,
    compute_dealing_range,
)
from scripts.knowledge_bridge.kb_context import fetch_kb_context
from scripts.utils.fused_data_loader import load_fused_data
from scripts.trader.signals.session_ranges import compute_all_session_ranges

PROMPT_DIR = Path(__file__).parent / "prompts"
VERDICT_DIR = _REPO / "data" / "vision" / "verdicts"
VERDICT_DIR.mkdir(parents=True, exist_ok=True)

_llm_cfg = get_llm_config()
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_MODEL = _llm_cfg.get("default_trader_model") or _llm_cfg.get("default_model") or "gemma4:latest"
FALLBACK_MODEL = _llm_cfg.get("fallback_model") or "gemma4:31b-cloud"
LOCAL_FALLBACK_MODEL = _llm_cfg.get("local_fallback_model") or "gemma4:latest"

# DST-aware timezone
from zoneinfo import ZoneInfo
ET_TZ = ZoneInfo("America/New_York")


# ═══════════════════════════════════════════════════════════════════════
#  Feature assembly — ground-truth numbers from the data layer
# ═══════════════════════════════════════════════════════════════════════

def _get_current_price(ticker: str) -> float:
    """Get the latest price from live storage parquet."""
    try:
        df = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df is not None and not df.empty:
            return round(float(df["close"].iloc[-1]), 2)
    except Exception as e:
        log.warning("Could not load current price for %s: %s", ticker, e)
    return 0.0


def _fmt(val, decimals=2):
    """Format a float for display, returning 'N/A' if None/NaN."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    try:
        return f"{float(val):.{decimals}f}"
    except (ValueError, TypeError):
        return str(val)


def _session_block(name: str, r: dict) -> list[str]:
    """Format a session range dict into text lines."""
    if not r:
        return [f"  {name}: (no data)"]
    return [
        f"  {name}: H={_fmt(r.get('high'))} L={_fmt(r.get('low'))} Mid={_fmt(r.get('mid'))} Range={_fmt(r.get('range'))} O={_fmt(r.get('open'))} C={_fmt(r.get('close'))}",
    ]


def assemble_features(ticker: str) -> str:
    """Assemble the pre-computed ICT features into a text block for the LLM.

    This is the GROUND TRUTH the LLM interprets. We load numbers from the
    data layer and let the LLM's ICT knowledge do the reasoning.

    Removed: IPDA, pre-computed 4-model bias, killzone pivots (per plan v2.0)
    Added: session ranges with mids, ONS/P12/submission, geometric filtering,
           dealing range (structural), HTF structure
    """
    current_price = _get_current_price(ticker)
    today = datetime.now(ET_TZ).date()

    ict = load_ict_context(ticker, current_price=current_price)
    bias_models = compute_ict_daily_bias(ticker, current_price)

    lines = [f"== ICT FEATURES for {ticker} (price={current_price}) =="]
    lines.append("")

    # ── HTF Levels (prior day/week/month) ──────────────────────────────
    lines.append("## HTF Levels (Prior Day/Week/Month)")
    if ict.get("pdh"): lines.append(f"  PDH (Prior Day High): {_fmt(ict['pdh'])}")
    if ict.get("pdl"): lines.append(f"  PDL (Prior Day Low): {_fmt(ict['pdl'])}")
    if ict.get("pdc"): lines.append(f"  PDC (Prior Day Close): {_fmt(ict['pdc'])}")
    if ict.get("pwh"): lines.append(f"  PWH (Prior Week High): {_fmt(ict['pwh'])}")
    if ict.get("pwl"): lines.append(f"  PWL (Prior Week Low): {_fmt(ict['pwl'])}")
    # Compute mids
    if ict.get("pdh") and ict.get("pdl"):
        pdm = (float(ict["pdh"]) + float(ict["pdl"])) / 2
        lines.append(f"  PDM (Prior Day Mid): {pdm:.2f}")
    if ict.get("pwh") and ict.get("pwl"):
        pwm = (float(ict["pwh"]) + float(ict["pwl"])) / 2
        lines.append(f"  PWM (Prior Week Mid): {pwm:.2f}")
    if ict.get("midnight_open"): lines.append(f"  Midnight Open: {_fmt(ict['midnight_open'])}")
    lines.append("")

    # ── Session Ranges (computed from 1m, DST-aware) ─────────────────
    lines.append("## Session Ranges (ICT killzones, computed from 1m)")
    try:
        df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_1m is not None and not df_1m.empty:
            if df_1m.index.tz is None:
                df_1m.index = pd.DatetimeIndex(df_1m.index).tz_localize("UTC").tz_convert(ET_TZ)
            else:
                df_1m.index = df_1m.index.tz_convert(ET_TZ)

            target = pd.Timestamp(today, tz=ET_TZ)
            ranges = compute_all_session_ranges(df_1m, target, ET_TZ)

            lines.extend(_session_block("ASIA", ranges.get("ASIA", {})))
            lines.extend(_session_block("LONDON", ranges.get("LONDON", {})))
            lines.extend(_session_block("ONS", ranges.get("ONS", {})))
            lines.extend(_session_block("P12", ranges.get("P12", {})))
            lines.extend(_session_block("NY_P12", ranges.get("NY_P12", {})))
            lines.extend(_session_block("NY_AM", ranges.get("NY_AM", {})))
            lines.extend(_session_block("NY_LUNCH", ranges.get("NY_LUNCH", {})))
            lines.extend(_session_block("NY_PM", ranges.get("NY_PM", {})))
            lines.extend(_session_block("SUBMISSION", ranges.get("SUBMISSION", {})))
            lines.extend(_session_block("RTH", ranges.get("RTH", {})))
    except Exception as e:
        log.debug("Session ranges computation failed: %s", e)
        lines.append("  (session ranges unavailable)")
    lines.append("")

    # ── Dealing Range (structural, NOT PDH-PDL) ───────────────────────
    lines.append("## Dealing Range (Structural Swing — TBP Definition)")
    try:
        df_1h = load_fused_data(ticker, timeframe="1h", require_historical=False)
        if df_1h is not None and not df_1h.empty:
            if df_1h.index.tz is None:
                df_1h.index = pd.DatetimeIndex(df_1h.index).tz_localize("UTC").tz_convert(ET_TZ)
            else:
                df_1h.index = df_1h.index.tz_convert(ET_TZ)
            dr = compute_dealing_range(df_1h, lookback=20)
            if dr.get("valid"):
                lines.append(f"  DR High: {dr['dr_high']:.2f}")
                lines.append(f"  DR Low: {dr['dr_low']:.2f}")
                lines.append(f"  DR Mid (50%): {dr['dr_mid']:.2f}")
                lines.append(f"  Both sides swept: YES")
            else:
                lines.append("  (dealing range not yet validated — both sides not swept)")
    except Exception as e:
        log.debug("Dealing range computation failed: %s", e)
        lines.append("  (dealing range unavailable)")
    lines.append("")

    # ── PD Arrays (geometrically filtered) ────────────────────────────
    lines.append("## PD Arrays (geometrically filtered — nearest 5 above/below)")
    try:
        # FVGs
        fvgs = load_imbalances_filtered(ticker, current_price, timeframe="5m",
                                        session_date=today, n_above=5, n_below=5)
        if not fvgs.empty:
            lines.append(f"  FVGs ({len(fvgs)} shown):")
            for _, row in fvgs.iterrows():
                top = row.get("fvg_top", row.get("top_price", "N/A"))
                bot = row.get("fvg_bottom", row.get("bottom_price", "N/A"))
                lines.append(f"    FVG top={_fmt(top)} bot={_fmt(bot)}")
    except Exception as e:
        log.debug("FVG load failed: %s", e)

    try:
        # Order Blocks
        obs = load_orderblocks_filtered(ticker, current_price, timeframe="5m",
                                        session_date=today, n_above=5, n_below=5)
        if not obs.empty:
            lines.append(f"  Order Blocks ({len(obs)} shown):")
            for _, row in obs.iterrows():
                top = row.get("ob_top", row.get("top_price", "N/A"))
                bot = row.get("ob_bottom", row.get("bottom_price", "N/A"))
                lines.append(f"    OB top={_fmt(top)} bot={_fmt(bot)}")
    except Exception as e:
        log.debug("OB load failed: %s", e)

    try:
        # Liquidity levels
        liq = load_liquidity_filtered(ticker, current_price, timeframe="5m",
                                      session_date=today, n_above=5, n_below=5)
        if not liq.empty:
            lines.append(f"  Liquidity Levels ({len(liq)} shown):")
            for _, row in liq.iterrows():
                level = row.get("liq_level", "N/A")
                kind = row.get("liq_kind", "")
                lines.append(f"    {kind} @ {_fmt(level)}")
    except Exception as e:
        log.debug("Liquidity load failed: %s", e)
    lines.append("")

    # ── Current State ─────────────────────────────────────────────────
    lines.append("## Current State")
    lines.append(f"  Current Price: {current_price}")
    if ict.get("dealing_range_pct"):
        lines.append(f"  Dealing Range %: {ict['dealing_range_pct']:.1f}%")
    if ict.get("premium_discount"):
        lines.append(f"  Premium/Discount: {ict['premium_discount']}")
    if ict.get("bsl_target"):
        lines.append(f"  BSL (Buy-Side Liquidity, above): {_fmt(ict['bsl_target'])}")
    if ict.get("ssl_target"):
        lines.append(f"  SSL (Sell-Side Liquidity, below): {_fmt(ict['ssl_target'])}")
    lines.append("")

    # ── Gaps ──────────────────────────────────────────────────────────
    try:
        gaps = load_gaps(ticker, auto_refresh=False)
        if not gaps.empty:
            today_gaps = gaps[gaps["trading_date"] == today] if "trading_date" in gaps.columns else gaps.tail(5)
            if today_gaps.empty:
                today_gaps = gaps.tail(5)
            if not today_gaps.empty:
                lines.append("## Gaps (recent)")
                for _, row in today_gaps.iterrows():
                    lines.append(f"  {row.get('gap_type', 'gap')} @ {row.get('price', 'N/A')} ({row.get('direction', '')})")
                lines.append("")
    except Exception as e:
        log.debug("Gaps load failed: %s", e)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  KB context retrieval
# ═══════════════════════════════════════════════════════════════════════

def retrieve_kb_context(features_text: str) -> str:
    """Retrieve KB context using the concept triggers in the features text.

    Reuses scripts.knowledge_bridge.kb_context.fetch_kb_context —
    the same function the narrative engine uses. Degrades gracefully
    (returns '') if the KB API is down.
    """
    try:
        ctx = fetch_kb_context(features_text, max_context_chars=6000, k_per_concept=3)
        if ctx:
            return f"# ICT Knowledge Base Context\n\n{ctx}"
        return "# ICT Knowledge Base Context\n\n(KB API unreachable or no context found — proceeding with LLM's built-in ICT knowledge.)"
    except Exception as e:
        log.warning("KB context retrieval failed: %s", e)
        return f"# ICT Knowledge Base Context\n\n(Error: {e}. Proceeding with LLM's built-in ICT knowledge.)"


# ═══════════════════════════════════════════════════════════════════════
#  LLM call — reuse trader_narrative's pattern
# ═══════════════════════════════════════════════════════════════════════

def call_llm(prompt: str, model: str, timeout: int = 300) -> str:
    """Call Ollama with fallback chain (same pattern as trader_narrative.call_ollama)."""
    import requests

    candidates = []
    seen = set()
    for m in [model, FALLBACK_MODEL, LOCAL_FALLBACK_MODEL]:
        if m and m not in seen:
            candidates.append(m)
            seen.add(m)

    for attempt_model in candidates:
        try:
            log.info("Calling LLM with model: %s ...", attempt_model)
            response = requests.post(
                OLLAMA_ENDPOINT,
                json={
                    "model": attempt_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_ctx": 262144,
                        "num_predict": 8192,
                    },
                },
                timeout=timeout,
            )
            if response.status_code == 200:
                result = response.json().get("response", "")
                if result:
                    log.info("LLM response received (%d chars)", len(result))
                    return result
            else:
                log.warning("Ollama returned HTTP %d", response.status_code)
        except Exception as e:
            log.warning("LLM call failed with %s: %s", attempt_model, e)

    raise RuntimeError("All LLM model attempts failed")


# ═══════════════════════════════════════════════════════════════════════
#  Verdict emission
# ═══════════════════════════════════════════════════════════════════════

def emit_verdict(ticker: str, model: str | None = None, save: bool = False) -> str:
    """Generate a daily_bias_mtf verdict for the given ticker.

    Args:
        ticker: e.g. "ES1", "NQ1"
        model: LLM model to use (defaults to config)
        save: if True, saves the verdict to data/vision/verdicts/

    Returns:
        the verdict YAML string
    """
    use_model = model or DEFAULT_MODEL

    log.info("=== Emitting daily_bias_mtf verdict for %s ===", ticker)

    features = assemble_features(ticker)
    log.info("Features assembled (%d chars)", len(features))

    kb_context = retrieve_kb_context(features)
    log.info("KB context retrieved (%d chars)", len(kb_context))

    prompt_path = PROMPT_DIR / "daily_bias_reasoner.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")
    prompt = prompt_template.replace("{FEATURES_BLOCK}", features).replace("{KB_CONTEXT_BLOCK}", kb_context)

    verdict = call_llm(prompt, use_model)

    if save:
        date_str = datetime.now().strftime("%Y-%m-%d")
        save_path = VERDICT_DIR / f"{ticker}_{date_str}_daily_bias_mtf.yaml"
        save_path.write_text(verdict, encoding="utf-8")
        log.info("Verdict saved to %s", save_path)

    return verdict


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Emit a daily_bias_mtf verdict for a ticker")
    ap.add_argument("--ticker", default="ES1", help="Ticker symbol (ES1, NQ1)")
    ap.add_argument("--model", default=None, help="LLM model (defaults to config)")
    ap.add_argument("--save", action="store_true", help="Save verdict to data/vision/verdicts/")
    args = ap.parse_args()

    verdict = emit_verdict(args.ticker, model=args.model, save=args.save)
    print("\n" + "=" * 60)
    print(verdict.encode("utf-8", errors="replace").decode("utf-8"))


if __name__ == "__main__":
    main()