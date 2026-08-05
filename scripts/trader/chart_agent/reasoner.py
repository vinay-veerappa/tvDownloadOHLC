"""reasoner.py — the chart agent's verdict emitter (Phase 0a).

A minimal reasoner that:
  1. Loads pre-computed ICT features from ict_data_loader
  2. Retrieves KB context via kb_context.fetch_kb_context()
  3. Assembles a prompt using the daily_bias_mtf v0.4 schema
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
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_REPO))

from scripts.trader import _path_setup  # noqa: F401 — side-effect sys.path
from scripts.trader.config_loader import get_llm_config
from scripts.trader.signals.ict_data_loader import (
    load_ict_context,
    compute_ict_daily_bias,
    load_ipda,
    load_kz_pivots,
    load_gaps,
    load_imbalances,
)
from scripts.knowledge_bridge.kb_context import fetch_kb_context

PROMPT_DIR = Path(__file__).parent / "prompts"
VERDICT_DIR = _REPO / "data" / "vision" / "verdicts"
VERDICT_DIR.mkdir(parents=True, exist_ok=True)

_llm_cfg = get_llm_config()
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_MODEL = _llm_cfg.get("default_trader_model") or _llm_cfg.get("default_model") or "gemma4:latest"
FALLBACK_MODEL = _llm_cfg.get("fallback_model") or "gemma4:31b-cloud"
LOCAL_FALLBACK_MODEL = _llm_cfg.get("local_fallback_model") or "gemma4:latest"


# ═══════════════════════════════════════════════════════════════════════
#  Feature assembly — ground-truth numbers from the data layer
# ═══════════════════════════════════════════════════════════════════════

def _get_current_price(ticker: str) -> float:
    """Get the latest price from live storage parquet."""
    try:
        from scripts.utils.fused_data_loader import load_fused_data
        df = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df is not None and not df.empty:
            return round(float(df["close"].iloc[-1]), 2)
    except Exception as e:
        log.warning("Could not load current price for %s: %s", ticker, e)
    return 0.0


def assemble_features(ticker: str) -> str:
    """Assemble the pre-computed ICT features into a text block for the LLM.

    This is the GROUND TRUTH the LLM interprets. We do NOT compute ICT logic
    here — we load numbers and let the LLM's ICT knowledge do the reasoning.
    """
    current_price = _get_current_price(ticker)
    ict = load_ict_context(ticker, current_price=current_price)
    bias_models = compute_ict_daily_bias(ticker, current_price)

    lines = [f"== ICT FEATURES for {ticker} (price={current_price}) =="]
    lines.append("")

    # Core levels
    lines.append("## Dealing Range Levels")
    if ict.get("pdh"): lines.append(f"  PDH: {ict['pdh']}")
    if ict.get("pdl"): lines.append(f"  PDL: {ict['pdl']}")
    if ict.get("pdc"): lines.append(f"  PDC: {ict['pdc']}")
    if ict.get("midnight_open"): lines.append(f"  Midnight Open: {ict['midnight_open']}")
    if ict.get("pwh"): lines.append(f"  PWH: {ict['pwh']}")
    if ict.get("pwl"): lines.append(f"  PWL: {ict['pwl']}")
    if ict.get("dealing_range_pct"): lines.append(f"  Dealing Range %: {ict['dealing_range_pct']:.1f}%")
    if ict.get("premium_discount"): lines.append(f"  Premium/Discount: {ict['premium_discount']}")
    if ict.get("weekly_range_pct"): lines.append(f"  Weekly Range %: {ict['weekly_range_pct']}")
    lines.append("")

    # Liquidity targets
    lines.append("## Liquidity Targets")
    if ict.get("bsl_target"): lines.append(f"  BSL (buy-side, above): {ict['bsl_target']}")
    if ict.get("ssl_target"): lines.append(f"  SSL (sell-side, below): {ict['ssl_target']}")
    lines.append("")

    # Daily bias models (the repo's existing 4-model computation)
    lines.append("## Pre-computed Daily Bias Models (4-model combination)")
    if bias_models:
        lines.append(f"  Overall bias: {bias_models.get('bias', 'N/A')}")
        lines.append(f"  Confidence: {bias_models.get('confidence', 'N/A')}")
        for m in bias_models.get("models", []):
            lines.append(f"  - {m['model']}: {m['signal']} — {m['detail']}")
        if bias_models.get("summary"):
            lines.append(f"  Summary: {bias_models['summary']}")
    lines.append("")

    # IPDA (inter-day position)
    try:
        ipda = load_ipda(ticker, auto_refresh=False)
        if not ipda.empty:
            today = datetime.now().date()
            ipda["trading_date"] = pd.to_datetime(ipda["trading_date"]).dt.date
            today_row = ipda[ipda["trading_date"] == today]
            if today_row.empty:
                today_row = ipda.tail(1)
            if not today_row.empty:
                row = today_row.iloc[0]
                lines.append("## IPDA (Interbank Price Delivery Algorithm)")
                ipda20 = row.get("ipda20_pct")
                ipda60 = row.get("ipda60_pct")
                if pd.notna(ipda20): lines.append(f"  IPDA-20 position: {ipda20:.1f}%")
                if pd.notna(ipda60): lines.append(f"  IPDA-60 position: {ipda60:.1f}%")
                lines.append("")
    except Exception as e:
        log.debug("IPDA load failed: %s", e)

    # Killzone pivots
    try:
        kz = load_kz_pivots(ticker, auto_refresh=False)
        if not kz.empty:
            today = datetime.now().date()
            kz["trading_date"] = pd.to_datetime(kz["trading_date"]).dt.date
            today_kz = kz[kz["trading_date"] == today]
            if today_kz.empty:
                today_kz = kz.tail(1)
            if not today_kz.empty:
                lines.append("## Killzone Pivots")
                row = today_kz.iloc[0]
                for col in row.index:
                    if col != "trading_date" and pd.notna(row[col]):
                        lines.append(f"  {col}: {row[col]}")
                lines.append("")
    except Exception as e:
        log.debug("KZ pivots load failed: %s", e)

    # Gaps
    try:
        gaps = load_gaps(ticker, auto_refresh=False)
        if not gaps.empty:
            today = datetime.now().date()
            gaps["trading_date"] = pd.to_datetime(gaps["trading_date"]).dt.date
            today_gaps = gaps[gaps["trading_date"] == today]
            if today_gaps.empty:
                today_gaps = gaps.tail(5)
            if not today_gaps.empty:
                lines.append("## Gaps (recent)")
                for _, row in today_gaps.iterrows():
                    lines.append(f"  {row.get('gap_type', 'gap')} @ {row.get('price', 'N/A')} ({row.get('direction', '')})")
                lines.append("")
    except Exception as e:
        log.debug("Gaps load failed: %s", e)

    # Imbalances (FVGs)
    try:
        imb = load_imbalances(ticker, auto_refresh=False)
        if not imb.empty:
            today = datetime.now().date()
            if "trading_date" in imb.columns:
                imb["trading_date"] = pd.to_datetime(imb["trading_date"]).dt.date
                today_imb = imb[imb["trading_date"] == today]
                if today_imb.empty:
                    today_imb = imb.tail(10)
            else:
                today_imb = imb.tail(10)
            if not today_imb.empty:
                lines.append("## Imbalances / FVGs (recent)")
                for _, row in today_imb.iterrows():
                    lines.append(f"  {row.get('imbalance_type', 'FVG')} top={row.get('top_price', 'N/A')} bot={row.get('bottom_price', 'N/A')}")
                lines.append("")
    except Exception as e:
        log.debug("Imbalances load failed: %s", e)

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