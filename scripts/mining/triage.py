"""Triage and scoring engine for harvested strategies.
Implements the 100-point rubric from docs/strategies/STRATEGY_MINING_SOP.md
and formats passing candidates into backlog-ready Markdown cards.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any, Tuple


class StrategyTriage:
    """Evaluates raw strategy candidates against repo admission criteria."""

    @classmethod
    def evaluate(cls, item: Dict[str, Any]) -> Tuple[float, Dict[str, float], bool]:
        """Score a harvested strategy out of 100 points."""
        source = item.get("source", "")
        text_corpus = ""
        if source == "youtube":
            text_corpus = (item.get("title", "") + " " + item.get("transcript", "")).lower()
        elif source == "tradingview":
            text_corpus = (item.get("title", "") + " " + item.get("source_code", "")).lower()
            if not text_corpus.strip():
                # Read script if path exists
                p = item.get("script_path")
                if p:
                    try:
                        text_corpus = (item.get("title", "") + " " + Path(p).read_text(encoding="utf-8")).lower()
                    except Exception:
                        pass
        elif source == "quantpedia":
            text_corpus = (item.get("title", "") + " " + item.get("rules", "") + " " + item.get("rationale", "")).lower()
        elif source == "github":
            text_corpus = (item.get("title", "") + " " + item.get("description", "") + " " + item.get("readme_excerpt", "")).lower()
        elif source in ["babypips", "reddit", "futures_io"]:
            text_corpus = (
                item.get("title", "")
                + " "
                + item.get("rules", "")
                + " "
                + item.get("content", "")
                + " "
                + item.get("futures_adaptation", "")
            ).lower()
            # If a downloaded archive or code file exists, inspect code
            fp = item.get("file_path")
            if fp and Path(fp).exists():
                try:
                    if fp.endswith(".zip"):
                        import zipfile
                        with zipfile.ZipFile(fp, "r") as z:
                            for fname in z.namelist():
                                if fname.endswith((".cs", ".txt")):
                                    text_corpus += " " + z.read(fname).decode("utf-8", errors="ignore").lower()
                    elif fp.endswith((".cs", ".txt")):
                        text_corpus += " " + Path(fp).read_text(encoding="utf-8", errors="ignore").lower()
                except Exception:
                    pass

        scores: Dict[str, float] = {}

        # G1: Rule Precision (30 pts)
        indicators = [
            "ema", "sma", "vwap", "rsi", "bollinger", "atr", "supertrend", "fvg", "order block", "macd",
            "thestrat", "the strat", "inside bar", "outside bar", "ftfc", "timeframe continuity", "broadening formation"
        ]
        triggers = [
            "crosses", "closes above", "closes below", "breakout", "rejection", "sweep", "crossover", "crossunder",
            "2-1-2", "3-1-2", "2-2", "failed 2", "reversal", "continuation"
        ]
        has_ind = any(i in text_corpus for i in indicators)
        has_trig = any(t in text_corpus for t in triggers)
        
        g1 = 0.0
        if has_ind:
            g1 += 15.0
        if has_trig:
            g1 += 15.0
        scores["G1_Rule_Precision"] = g1

        # G2: Risk Architecture (25 pts)
        has_sl = "stop loss" in text_corpus or "stoploss" in text_corpus or "sl_" in text_corpus or "stop_price" in text_corpus
        has_tp = "take profit" in text_corpus or "target" in text_corpus or "tp_" in text_corpus or "profit target" in text_corpus
        g2 = 0.0
        if has_sl:
            g2 += 15.0
        if has_tp:
            g2 += 10.0
        # If source is Quantpedia, rules are often portfolio rebalances where "cash" acts as risk off
        if source == "quantpedia" and ("cash" in text_corpus or "rebalance" in text_corpus):
            g2 = max(g2, 20.0)
        scores["G2_Risk_Architecture"] = g2

        # G3: Lookahead Immunity (20 pts)
        g3 = 20.0
        if item.get("lookahead_flag", False) or "lookahead_on" in text_corpus:
            g3 = 0.0
        scores["G3_Lookahead_Immunity"] = g3

        # G4: Friction Resilience (15 pts)
        # Higher points if timeframe is not sub-minute or if it explicitly accounts for slippage/commission
        g4 = 10.0
        if "commission" in text_corpus or "slippage" in text_corpus:
            g4 += 5.0
        scores["G4_Friction_Resilience"] = g4

        # G5: Regime Specificity (10 pts)
        has_session = any(s in text_corpus for s in ["session", "ny_am", "rth", "09:30", "london", "asia", "intraday", "daily", "timeframe"])
        g5 = 10.0 if has_session else 5.0
        scores["G5_Regime_Specificity"] = g5

        total_score = sum(scores.values())
        is_admitted = total_score >= 70.0 and (has_sl or source == "quantpedia") and g3 > 0

        return total_score, scores, is_admitted

    @classmethod
    def format_backlog_card(cls, item: Dict[str, Any], score: float) -> str:
        """Format strategy item as a Markdown card for the research backlog."""
        title = item.get("title", "Untitled Strategy")
        source = item.get("source", "").upper()
        url = item.get("url", "")
        archetype = item.get("archetype", "general")
        item_id = item.get("id", "item")

        return f"""### [{source}-{archetype.upper()}] {title}

* **Source**: [{source}]({url}) (ID: `{item_id}`)
* **Triage Score**: {score:.1f} / 100 (ADMITTED)
* **Archetype**: `{archetype}`
* **Hypothesis**: Mechanical rules harvested autonomously from {source}.
* **Independent Test Arms**:
  * `Arm 0 (Baseline)`: Raw setup trigger without secondary filters.
  * `Arm 1`: Baseline + Session Gate (09:30–11:30 ET).
  * `Arm 2`: Baseline + Kaufman Efficiency Ratio filter (KER > 0.40).
* **Mechanics Overview**:
  * *Context/Trigger*: {item.get('description', item.get('rules', 'See source for full code/transcript.'))[:300]}...
  * *Execution Standard*: 1 tick slippage, universal basis points (bps) stops & targets.
"""
