"""Cross-Asset Commander's Directive (Section 0) — HTF composite routing.

Scores all core futures (NQ1, ES1, RTY1, YM1, GC1, CL1) on Mickey's HTF EMA
system + regime gate and produces a day directive:

- ASSET FOCUS ranking: which asset carries the statistical edge today
- DAY POSTURE: TREND / ROTATION / CHOP-WARNING, from complex-wide structure
- TRIGGERS: the if-then handoffs that change the day

Philosophy: never predicts day types (R1/R2/DNP/DWP are EOD labels); the
directive describes statistical state and posture only.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

CORE_TICKERS = ["NQ1", "ES1", "RTY1", "YM1", "GC1", "CL1"]
INDEX_TICKERS = {"NQ1", "ES1", "RTY1", "YM1"}
COMMODITY_TICKERS = {"GC1", "CL1"}

ANOMALY_EXTENSION_PCT = 2.0  # |dist from weekly EMA| beyond which extension is flagged


def _score_asset(d: dict[str, Any]) -> dict[str, Any]:
    """Per-asset statistical score + directive from the HTF EMA result."""
    regime = d.get("regime", {})
    edge = d.get("weekly_edge", {})
    spent = d.get("spent_targets", []) or []
    unspent = d.get("unspent_primary_targets", []) or []
    lockin = d.get("weekly_lockin", {})
    dist = float(d.get("dist_pct", 0.0))

    regime_name = regime.get("regime", "unknown")
    pullback = regime.get("pullback_state", "unknown")
    edge_state = edge.get("state", "unknown")
    n_spent = len(spent)
    n_unspent_primary = len(unspent)
    extension = abs(dist)

    # --- Score: how tradeable is this asset on HTF stats today? ---
    score = 0
    reasons: list[str] = []

    if regime_name == "bull_trend":
        score += 3
        reasons.append("70/30 bull regime (above NFP close + prev-month mid)")
    else:
        reasons.append("50/50 regime — no HTF directional edge")

    if pullback == "quarterly_pullback_watch":
        reasons.append("below both NFP close and prev-month mid (quarterly pullback state)")

    if edge_state == "active_targets":
        score += 3
        nxt = unspent[0]
        side = "up" if dist >= 0 else "down"
        reasons.append(
            f"live primary target {nxt['level_pct']}% ({'above' if side == 'up' else 'below'}"
            f" EMA @ {nxt['up_price'] if side == 'up' else nxt['down_price']:,.2f})"
        )
    elif edge_state == "no_edge_5050":
        score -= 2
        reasons.append(edge.get("reason", "all primary targets spent") + " — 50/50 coin flip")

    if n_spent > 0:
        reasons.append(f"{n_spent} level(s) already spent this week")

    if extension >= ANOMALY_EXTENSION_PCT:
        score -= 1
        reasons.append(f"extended {dist:+.2f}% from weekly EMA (anomaly-zone edge)")

    direction = "long" if dist >= 0 else "short"
    if edge_state == "no_edge_5050":
        directive = "FADE-WATCH (no fresh HTF positions; reversal-counter setups only)"
    elif score >= 5:
        directive = f"PRIMARY FOCUS — HTF-aligned {direction} continuation"
    elif score >= 3:
        directive = f"SECONDARY — tradeable, prefer {direction} side"
    else:
        directive = "STAND DOWN — no HTF edge; session models only"

    return {
        "ticker": d.get("ticker"),
        "dist_pct": dist,
        "weekly_ema5": d.get("weekly_ema5"),
        "regime": regime_name,
        "pullback_state": pullback,
        "edge_state": edge_state,
        "n_spent": n_spent,
        "n_unspent_primary": n_unspent_primary,
        "extension": round(extension, 2),
        "locked_extreme": lockin.get("locked_extreme"),
        "score": score,
        "directive": directive,
        "reasons": reasons,
        "next_target": edge.get("next_target_pct"),
        "next_target_up_price": edge.get("next_target_up_price"),
        "next_target_down_price": edge.get("next_target_down_price"),
    }


def _day_posture(scores: list[dict[str, Any]]) -> tuple[str, str]:
    """Complex-wide posture from cross-asset structure."""
    idx = [s for s in scores if s["ticker"] in INDEX_TICKERS]
    cmd = [s for s in scores if s["ticker"] in COMMODITY_TICKERS]

    idx_bull = sum(1 for s in idx if s["regime"] == "bull_trend")
    cmd_bull = sum(1 for s in cmd if s["regime"] == "bull_trend")

    aligned_idx = len({s["regime"] for s in idx}) == 1
    divergence = (idx_bull / max(len(idx), 1) < 0.5) and (cmd_bull / max(len(cmd), 1) >= 0.5)

    if divergence:
        return (
            "ROTATION — equities de-rating while commodities hold the 70/30 bull regime",
            "Risk appetite is intact outside equities: favors single-asset focus over "
            "complex-wide plays. Do not read the equity pullback as broad risk-off.",
        )
    if aligned_idx and idx_bull >= 3:
        return (
            "TREND — index complex aligned in 70/30 regime",
            "Trade index continuations; use EMA ladder targets as runners.",
        )
    if aligned_idx and idx_bull == 0:
        any_targets = any(s["edge_state"] == "active_targets" for s in idx)
        if any_targets:
            return (
                "TREND-DOWN — index complex aligned 50/50 with live downside targets",
                "Quarterly-pullback continuation posture; respect target shelves, "
                "fade only on four-step reversal confirmation.",
            )
        return (
            "CHOP WARNING — index complex in 50/50 with targets exhausted",
            "Reversions only; no breakout chasing. Broken-Broken/Goalpost session "
            "structure confirms two-way tape.",
        )
    return (
        "MIXED — no complex-wide alignment",
        "Asset-by-asset focus; let the focus asset's regime lead.",
    )


def build_cross_asset_directive(focus_ticker: str = "NQ1",
                                target_date: str | None = None) -> dict[str, Any]:
    """Compute the Section 0 directive across all core tickers."""
    from scripts.wargaming.htf_ema_analysis import compute_htf_ema_analysis

    scores = []
    for t in CORE_TICKERS:
        try:
            d = compute_htf_ema_analysis(ticker=t, target_date=target_date)
            scores.append(_score_asset(d))
        except Exception as e:
            log.warning("[cross_asset] failed for %s: %s", t, e)
            scores.append({
                "ticker": t, "score": -99, "directive": "DATA ERROR",
                "reasons": [str(e)], "dist_pct": 0.0, "regime": "unknown",
                "pullback_state": "unknown", "edge_state": "unknown",
                "n_spent": 0, "n_unspent_primary": 0, "extension": 0.0,
                "locked_extreme": None, "next_target": None,
                "next_target_up_price": None, "next_target_down_price": None,
                "weekly_ema5": None,
            })

    scores.sort(key=lambda s: s["score"], reverse=True)
    posture, posture_note = _day_posture(scores)
    focus = next((s for s in scores if s["ticker"] == focus_ticker), None)
    top = scores[0] if scores else None

    return {
        "focus_ticker": focus_ticker,
        "scores": scores,
        "posture": posture,
        "posture_note": posture_note,
        "recommended_focus": top["ticker"] if top else None,
        "recommended_directive": top["directive"] if top else None,
        "focus_in_scope": focus.get("directive") if focus else None,
        "focus_score": focus["score"] if focus else None,
    }


def format_cross_asset_markdown(cad: dict[str, Any]) -> str:
    """Render Section 0: Commander's Brief."""
    lines = [
        "## 🎯 0. COMMANDER'S BRIEF (Cross-Asset HTF Composite)",
        f"* **Day Posture**: **{cad['posture']}**  ",
        f"* **Rationale**: {cad['posture_note']}  ",
        "",
        f"**Cross-Asset Ranking** (statistical state, not prediction):",
        "",
        "| Rank | Ticker | Dist from EMA | Regime | Edge State | Directive |",
        "|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(cad["scores"], 1):
        dist_s = f"{s['dist_pct']:+.2f}%" if s["weekly_ema5"] else "n/a"
        if s["edge_state"] == "active_targets" and s["next_target_up_price"] and s["next_target_down_price"]:
            edge_s = (f"ACTIVE ({s['next_target']}% → "
                      f"{s['next_target_up_price']:,.2f} / {s['next_target_down_price']:,.2f})")
        elif s["edge_state"] == "no_edge_5050":
            edge_s = "SPENT (50/50)"
        else:
            edge_s = str(s["edge_state"])
        lines.append(
            f"| {i} | **{s['ticker']}** | {dist_s} | {s['regime']}/{s['pullback_state']} "
            f"| {edge_s} | {s['directive']} |"
        )
    lines.append("")
    focus = cad["focus_in_scope"]
    if focus:
        lines.append(
            f"**Focus ticker ({cad['focus_ticker']}) directive**: {focus} "
            f"(score {cad['focus_score']}). "
            f"Complex-wide recommended focus: **{cad['recommended_focus']}** — "
            f"{cad['recommended_directive']}."
        )
    else:
        lines.append(
            f"Complex-wide recommended focus: **{cad['recommended_focus']}** — "
            f"{cad['recommended_directive']}."
        )
    lines.append("")
    lines.append(
        "*Triggers that change the day*: (1) reclaim of Sunday open + NFP range "
        "flips weekly lock-in back to undetermined; (2) any target exhaustion "
        "re-ranks the focus asset; (3) 09:45/10:00 news candles gate all "
        "executions. Day types (R1/R2/DWP/DNP) remain EOD diagnostics only."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)