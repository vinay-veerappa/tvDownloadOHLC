import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def calculate_caution_score(
    vix_ctx: Dict[str, Any],
    nq_ctx: Dict[str, Any],
    es_ctx: Dict[str, Any],
    econ_releases: List[Dict[str, Any]],
    earnings_events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Calculate the Caution Score (0-100) and Risk Posture based on multi-factor risks."""
    score = 0
    reasons = []

    # 1. Volatility Signals (VIX/VVIX)
    vix_close = vix_ctx.get("vix_close") or vix_ctx.get("close")
    if vix_close is not None:
        if vix_close > 30:
            score += 30
            reasons.append(f"VIX is in crisis (>30): {vix_close:.2f}")
        elif vix_close > 20:
            score += 15
            reasons.append(f"VIX is elevated (>20): {vix_close:.2f}")
            
    vvix_close = vix_ctx.get("vvix_close")
    if vvix_close is not None and vvix_close > 110:
        score += 10
        reasons.append(f"VVIX is elevated (>110): {vvix_close:.2f}")
        
    div_read = vix_ctx.get("divergence_read")
    if div_read in ("panic", "smart_money_divergence"):
        score += 15
        reasons.append(f"VIX/VVIX divergence detected: {div_read}")

    # 2. Overnight price moves (NQ/ES)
    if nq_ctx:
        nq_chg = abs(nq_ctx.get("change_pct", 0.0))
        if nq_chg > 1.5:
            score += 15
            reasons.append(f"Large NQ overnight move (>1.5%): {nq_chg:.2f}%")
            
    if es_ctx:
        es_chg = abs(es_ctx.get("change_pct", 0.0))
        if es_chg > 1.0:
            score += 15
            reasons.append(f"Large ES overnight move (>1.0%): {es_chg:.2f}%")

    # 3. Calendar conflicts
    conflict_count = sum(1 for e in econ_releases if e.get("macro_window_conflict"))
    if conflict_count > 0:
        score += 20
        reasons.append(f"Scheduled US econ releases land within macro windows ({conflict_count} conflict(s))")

    # 4. Index-critical earnings gaps beyond EM
    critical_beyond_em = [
        e for e in earnings_events 
        if e.get("index_critical") and e.get("beyond_em")
    ]
    for e in critical_beyond_em:
        score += 15
        move_pct = e.get("premkt_move_pct", 0.0) * 100
        reasons.append(f"Index-critical earnings gap beyond EM: {e['ticker']} ({move_pct:+.2f}%)")

    # Cap at 100
    final_score = min(score, 100)

    # Determine Risk Posture
    if final_score >= 70:
        posture = "EXTREME CAUTION"
    elif final_score >= 45:
        posture = "DEFENSIVE"
    elif final_score >= 20:
        posture = "HEDGED"
    else:
        posture = "RISK-ON"

    return {
        "score": final_score,
        "posture": posture,
        "reasons": reasons
    }
