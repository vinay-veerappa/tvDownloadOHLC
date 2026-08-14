#!/usr/bin/env python
"""MaxDD & position-sizing analysis for the FVG-filtered IBRetestBot backtest.

Reads the NT8 Strategy Analyzer JSON (all 65 trades) and writes a JSON report.
Run:  .\.venv\Scripts\python.exe scratch\analyze_maxdd_sizing.py
"""
import json, math, os
from collections import Counter
from itertools import groupby
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_IN   = os.path.join(HERE, "nt8_ib_retest_fvg_sep26_full.json")
REPORT_OUT = os.path.join(HERE, "maxdd_sizing_report.json")

def load_trades(path):
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    # NT8 SA export: trades have instrument, marketPosition, quantity,
    # entryPrice, exitPrice, entryTime/date, exitTime/date, pnl/profit, commission, exitReason
    raw = data.get("trades", [])
    trades = []
    for t in raw:
        pnl = t.get("profitCurrency", t.get("pnl", t.get("profit", t.get("netProfit", 0.0))))
        trades.append({
            "entry_time":  t.get("entryTime", t.get("entryDate", t.get("date", ""))),
            "exit_time":   t.get("exitTime",   t.get("exitDate",   t.get("exit",  ""))),
            "side":        t.get("marketPosition", t.get("side", "")),
            "pnl":         float(pnl),
            "exit_reason": t.get("exitName", t.get("exitReason", t.get("reason", ""))),
        })
    # SA export is already chronological; keep order
    return trades, data.get("metrics", {})

def equity_curve(pnls):
    eq = [0.0]
    for p in pnls:
        eq.append(eq[-1] + p)
    return eq

def drawdown_series(eq):
    peak = eq[0]; dd = []
    for v in eq:
        peak = max(peak, v)
        dd.append(v - peak)
    return dd

def max_dd(dd):
    idx = min(range(len(dd)), key=lambda i: dd[i])
    return dd[idx], idx

def losing_streaks(pnls):
    streaks = []
    for win, grp in groupby(pnls, key=lambda p: p < 0):
        vals = list(grp)
        if win:  # losing group
            streaks.append(vals)
    return streaks

def worst_k_consec(pnls, k):
    best = None
    for i in range(len(pnls) - k + 1):
        s = sum(pnls[i:i+k])
        if best is None or s < best[0]:
            best = (s, i)
    return best

def main():
    trades, metrics = load_trades(JSON_IN)
    pnls = [t["pnl"] for t in trades]

    eq = equity_curve(pnls)
    dd = drawdown_series(eq)
    mdd, mdd_idx = max_dd(dd)
    # peak that preceded the trough (equity curve has len n+1; trades indexed 0..n-1)
    peak_idx = max(range(mdd_idx + 1), key=lambda i: eq[i])

    streaks = losing_streaks(pnls)
    len_dist = Counter(len(s) for s in streaks)
    bucketed = {"1": 0, "2": 0, "3": 0, "4": 0, "5+": 0}
    for L, c in len_dist.items():
        bucketed["5+" if L >= 5 else str(L)] += c
    longest = max(streaks, key=lambda s: (len(s), -sum(s))) if streaks else []

    w2 = worst_k_consec(pnls, 2)
    w3 = worst_k_consec(pnls, 3)

    n   = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    W   = wins / n if n else 0
    q   = 1 - W
    net = sum(pnls)

    # ---- position sizing ----
    target_dd = 5000.0
    scale = target_dd / abs(mdd) if mdd != 0 else 0.0      # linear fraction of backtest size
    scaled_net = net * scale
    scaled_dd  = mdd * scale

    risk_pct = 0.005
    acct = 50000.0
    risk_per_trade = acct * risk_pct            # $250
    consec_to_5k = math.floor(target_dd / risk_per_trade) if risk_per_trade > 0 else None

    prob_3_window = q ** 3
    # P(>= one 3-loss streak) over n trades, window approx
    prob_any_3 = 1 - (1 - prob_3_window) ** max(1, n - 2)

    # Kelly (assumed 1:2 R:R)
    R = 2.0
    kelly_2   = W - (1 - W) / R
    kelly_q2  = 0.25 * kelly_2
    # Kelly (actual avg win/loss ratio)
    avg_win  = mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0
    avg_loss = -mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 1
    b = avg_win / avg_loss if avg_loss else 0
    kelly_act  = W - (1 - W) / b if b else 0
    kelly_qact = 0.25 * kelly_act

    report = {
        "source": JSON_IN,
        "trade_count": n,
        "winners": wins, "losers": n - wins, "win_rate": round(W, 4),
        "net_pnl": round(net, 2),
        "equity_curve": {
            "final_equity": round(eq[-1], 2),
            "peak_equity": round(eq[peak_idx], 2),
            "peak_at_trade_index": peak_idx,
            "peak_entry_time": trades[min(peak_idx, len(trades)-1)]["entry_time"] if trades else None,
        },
        "max_drawdown": {
            "max_dd_usd": round(mdd, 2),
            "trough_at_trade_index": mdd_idx,
            "trough_entry_time": trades[min(mdd_idx, len(trades)-1)]["entry_time"] if trades else None,
            "span_trades": mdd_idx - peak_idx,
        },
        "losing_streaks": {
            "distribution": bucketed,
            "longest_by_count": len(longest),
            "longest_by_usd": round(sum(longest), 2),
            "worst_single_trade": round(min(pnls), 2) if pnls else 0,
            "worst_consec2_usd": round(w2[0], 2) if w2 else None,
            "worst_consec2_at_index": w2[1] if w2 else None,
            "worst_consec3_usd": round(w3[0], 2) if w3 else None,
            "worst_consec3_at_index": w3[1] if w3 else None,
        },
        "position_sizing": {
            "backtest_contracts": 1,
            "backtest_net": round(net, 2),
            "backtest_max_dd": round(mdd, 2),
            "target_max_dd": target_dd,
            "scale_fraction_of_backtest": round(scale, 4),
            "scaled_net_at_target_dd": round(scaled_net, 2),
            "scaled_max_dd_at_target_dd": round(scaled_dd, 2),
            "risk_per_trade_0.5pct_of_50k": risk_per_trade,
            "consec_losses_to_hit_5k_dd": consec_to_5k,
            "prob_3loss_single_window": round(prob_3_window, 4),
            "prob_at_least_one_3loss_streak_over_n": round(prob_any_3, 4),
            "kelly_R2": round(kelly_2, 4),
            "kelly_quarter_R2": round(kelly_q2, 4),
            "actual_avg_win": round(avg_win, 2),
            "actual_avg_loss": round(avg_loss, 2),
            "actual_win_loss_ratio": round(b, 4),
            "kelly_actual": round(kelly_act, 4),
            "kelly_quarter_actual": round(kelly_qact, 4),
        },
    }

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    print(f"\nReport written to {REPORT_OUT}")

if __name__ == "__main__":
    main()