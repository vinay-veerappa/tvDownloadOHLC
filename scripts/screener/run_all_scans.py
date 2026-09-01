"""
Master Daily Scanner Suite — Orchestrates Equity Momentum & Options Scanners
Runs:
1. Qullamaggie High Tight Flags (HFT)
2. Stockbee Episodic Pivots (EP)
3. Mark Minervini Trend Template
4. Qullamaggie Parabolic Shorts
5. Ben PatternProfits CSP & Bull Put Spread Engine (with multi-quarter trajectory review)

Outputs unified Terminal Leaderboards and an Interactive HTML Dashboard at reports/daily_scans/
"""

import sys
import os
import io
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from scripts.screener.cli import run_screener
from scripts.csp_ranking.scoring_engine import ScoredCandidate, rank_csp_candidates
from scripts.csp_ranking.trajectory_analyzer import run_autonomous_deep_review, CandidateDeepAnalysis
from scripts.csp_ranking.live_scanner import scan_live_market
from scripts.csp_ranking.finviz_client import FinvizClient
from scripts.csp_ranking.technicals import TechnicalAnalyzer
from scripts.utils.universe_manager import get_universe
from scripts.screener.options_income_scanners import scan_covered_calls, scan_pmcc_leaps, CoveredCallCandidate, PmccCandidate
from scripts.screener.ben_velocity_focus import scan_velocity_momentum, scan_institutional_leaders, VelocityLeader, InstitutionalLeader

REPORTS_DIR = Path("reports/daily_scans")


def run_all_scanners(
    open_browser: bool = False,
    limit: int = 50,
) -> Path:
    """
    Runs all equity momentum and options scanners, producing a unified daily report.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    today_str = today.strftime("%b %d, %Y")
    file_date_str = today.strftime("%Y-%m-%d")
    html_path = REPORTS_DIR / f"daily_scans_{file_date_str}.html"

    print("\n" + "=" * 90)
    print(f"  MASTER DAILY SCANNER SUITE — {today_str.upper()}")
    print("  Running Qullamaggie, Minervini, Stockbee & Ben CSP/Spread Engines...")
    print("=" * 90)

    # 1. Run Equity Momentum Scanners
    screener_results: Dict[str, pd.DataFrame] = {}
    strategies = [
        ("qullamaggie_hft", "Qullamaggie High Tight Flags (HFT)"),
        ("stockbee_ep", "Stockbee Episodic Pivots (EP)"),
        ("minervini_trend", "Mark Minervini Trend Template"),
        ("parabolic_short", "Qullamaggie Parabolic Shorts"),
    ]

    for strat_id, strat_name in strategies:
        print(f"\n🔍 Scanning: {strat_name}...")
        try:
            df = run_screener(strategy_id=strat_id, limit=limit, log_duckdb=True)
            screener_results[strat_id] = df
            print(f"   -> Found {len(df)} qualifying setups.")
        except Exception as e:
            print(f"   ⚠️ Error running {strat_id}: {e}")
            screener_results[strat_id] = pd.DataFrame()

    # 2. Run Ben CSP & Spread Engine
    print(f"\n🧠 Scanning: Ben PatternProfits CSP & Put Credit Spreads...")
    try:
        raw_contracts = scan_live_market()
        finviz_client = FinvizClient()
        tech_analyzer = TechnicalAnalyzer()

        unique_tickers = sorted(list(set(c.ticker for c in raw_contracts)))
        profiles = {t: finviz_client.get_ticker_profile(t) for t in unique_tickers}
        technicals = {t: tech_analyzer.analyze_ticker(t, fallback_price=profiles[t].price if profiles[t] else 0.0) for t in unique_tickers}

        scored_all = [
            ScoredCandidate(
                contract=c,
                profile=profiles.get(c.ticker),
                technicals=technicals.get(c.ticker),
                scan_date=today,
            )
            for c in raw_contracts
        ]

        ranked = rank_csp_candidates(scored_all, one_contract_per_ticker=True)
        passed = [c for c in ranked if c.is_passed_hard_filters]
        deep_csp_analyses = run_autonomous_deep_review(passed)
        print(f"   -> Found {len(deep_csp_analyses)} ranked CSP & Spread candidates.")
    except Exception as e:
        print(f"   ⚠️ Error running CSP engine: {e}")
        deep_csp_analyses = []

    # 3. Run Covered Call & PMCC / LEAPS Scanners
    print(f"\n📈 Scanning: Covered Calls & Poor Man's Covered Calls (LEAPS)...")
    try:
        cc_candidates = scan_covered_calls()
        pmcc_candidates = scan_pmcc_leaps()
    except Exception as e:
        print(f"   ⚠️ Error running Covered Call / PMCC scanner: {e}")
        cc_candidates, pmcc_candidates = [], []

    # 4. Run Ben Velocity & Institutional Leaders Scanners
    print(f"\n🏛️ Scanning: Ben Bennett Focus List (Institutional Leaders) & Velocity...")
    try:
        institutional_leaders = scan_institutional_leaders()
        velocity_leaders = scan_velocity_momentum()
    except Exception as e:
        print(f"   ⚠️ Error running Ben Velocity/Focus List scanner: {e}")
        institutional_leaders, velocity_leaders = [], []

    # 5. Render Terminal Summary
    print("\n" + "=" * 90)
    print(f"  DAILY SCANNER SUMMARY LEADERBOARD ({today_str})")
    print("=" * 90)

    # Focus List Highlights
    if institutional_leaders:
        print(f"\n  🏛️ TOP INSTITUTIONAL LEADERS (EPS 40 / Rev 30 / RS 30):")
        for l in institutional_leaders[:5]:
            print(f"     • {l.ticker:<6} ${l.price:<7.2f} EPS YoY: {l.eps_yoy:>+6.1f}% | Rev YoY: {l.rev_yoy:>+6.1f}% | RS: {l.rs_rating:<3} | Score: {l.score:.1f}")

    # Velocity Highlights
    if velocity_leaders:
        print(f"\n  ⚡ TOP VELOCITY LEADERS (Float Churn < 20d):")
        for v in velocity_leaders[:5]:
            print(f"     • {v.ticker:<6} ${v.price:<7.2f} Chg: {v.chg_pct:>+5.2f}% | Rel Vol: {v.rel_vol_pct:.0f}% | Turn: {v.days_to_turn:.1f}d | RS: {v.rs_rating}")

    # Momentum Highlights
    print(f"\n  🚀 EQUITY MOMENTUM BREAKOUTS:")
    for strat_id, strat_name in strategies:
        df = screener_results.get(strat_id, pd.DataFrame())
        if not df.empty and "ticker" in df.columns:
            top_tickers = df["ticker"].head(8).tolist()
            print(f"     • {strat_name:<40}: {', '.join(top_tickers)}")
        else:
            print(f"     • {strat_name:<40}: (No active breakouts today)")

    # Options Highlights: CSP & Spreads
    t1_csps = [a for a in deep_csp_analyses if a.tier == 1]
    if t1_csps:
        print(f"\n  🟢 TOP TIER-1 CASH-SECURED PUTS & SPREADS:")
        for a in t1_csps:
            print(f"     • #{a.rank} {a.ticker:<6} ${a.strike:<5.1f} Put ({a.exp_str}) Mark: ${a.mark:.2f} | ROR: {a.trade_ror:.2f}% | Score: {a.final_adj_score:.1f}")

    # Options Highlights: Covered Calls
    if cc_candidates:
        print(f"\n  🎯 TOP COVERED CALL INCOME SETUPS (30 DTE):")
        for c in cc_candidates[:5]:
            print(f"     • {c.ticker:<6} ${c.spot:<7.2f} Stk: ${c.strike:<5.1f}C ({c.expiry_date.strftime('%b %d')}) Mark: ${c.mid:.2f} | Mo. Yield: {c.static_yield_pct:.2f}% | If Called: {c.if_called_yield_pct:.2f}%")

    # Options Highlights: LEAPS / PMCC
    if pmcc_candidates:
        print(f"\n  🚀 TOP POOR MAN'S COVERED CALLS (LEAPS):")
        for p in pmcc_candidates[:5]:
            l_str = f"{p.long_expiry.strftime('%b %y')} ${p.long_strike:.0f}C"
            s_str = f"{p.short_expiry.strftime('%b %d')} ${p.short_strike:.0f}C"
            print(f"     • {p.ticker:<6} ${p.spot:<7.2f} Long: {l_str:<12} Short: {s_str:<12} Cost: ${p.net_debit:.2f} | Monthly ROC: {p.roc_pct:.2f}%")

    # 6. Generate Unified HTML Dashboard
    generate_unified_html_report(
        html_path=html_path,
        today_str=today_str,
        screener_results=screener_results,
        deep_csp_analyses=deep_csp_analyses,
        cc_candidates=cc_candidates,
        pmcc_candidates=pmcc_candidates,
        institutional_leaders=institutional_leaders,
        velocity_leaders=velocity_leaders,
    )

    print(f"\n🌐 Unified Daily Scanner Dashboard saved to: {html_path.resolve()}\n")

    if open_browser:
        try:
            import webbrowser
            webbrowser.open(html_path.resolve().as_uri())
        except Exception:
            pass

    return html_path


def generate_unified_html_report(
    html_path: Path,
    today_str: str,
    screener_results: Dict[str, pd.DataFrame],
    deep_csp_analyses: List[CandidateDeepAnalysis],
    cc_candidates: List[CoveredCallCandidate],
    pmcc_candidates: List[PmccCandidate],
    institutional_leaders: Optional[List[InstitutionalLeader]] = None,
    velocity_leaders: Optional[List[VelocityLeader]] = None,
):
    """Generates a responsive dark-mode HTML report combining all scanners."""
    institutional_leaders = institutional_leaders or []
    velocity_leaders = velocity_leaders or []

    # Build Institutional Leaders Rows
    inst_rows = ""
    for i, l in enumerate(institutional_leaders, 1):
        tv_link = f"https://www.tradingview.com/chart/?symbol={l.ticker}"
        inst_rows += f"""
        <tr>
            <td class="text-center">{i}</td>
            <td><a href="{tv_link}" target="_blank" class="ticker-badge">{l.ticker}</a></td>
            <td>${l.price:.2f}</td>
            <td class="text-success fw-bold">+{l.eps_yoy:.1f}%</td>
            <td class="text-info fw-bold">+{l.rev_yoy:.1f}%</td>
            <td><span class="badge bg-secondary">{l.rs_rating}</span></td>
            <td><strong class="text-warning">{l.score:.1f}</strong></td>
            <td class="text-muted small">{l.industry}</td>
        </tr>
        """
    if not inst_rows:
        inst_rows = "<tr><td colspan='8' class='text-muted text-center py-3'>No institutional leaders passed hard floors today.</td></tr>"

    # Build Velocity Rows
    vel_rows = ""
    for i, v in enumerate(velocity_leaders, 1):
        tv_link = f"https://www.tradingview.com/chart/?symbol={v.ticker}"
        turn_badge = f"<span class='badge bg-danger'>🔥 {v.days_to_turn:.1f}d</span>" if v.is_fast_turn else f"{v.days_to_turn:.1f}d"
        sq_badge = "<span class='badge bg-warning text-dark'>🍋 Squeeze</span>" if v.is_short_squeeze else ""
        vel_rows += f"""
        <tr>
            <td class="text-center">{i}</td>
            <td><a href="{tv_link}" target="_blank" class="ticker-badge">{v.ticker}</a></td>
            <td>${v.price:.2f}</td>
            <td class="{'text-success' if v.chg_pct>=0 else 'text-danger'} fw-bold">{v.chg_pct:>+5.2f}%</td>
            <td><span class="badge bg-secondary">{v.rs_rating}</span></td>
            <td class="text-white fw-bold">{v.rel_vol_pct:.0f}%</td>
            <td>{v.float_m:.1f}M</td>
            <td>{turn_badge}</td>
            <td>{v.short_float_pct:.1f}% {sq_badge}</td>
        </tr>
        """
    if not vel_rows:
        vel_rows = "<tr><td colspan='9' class='text-muted text-center py-3'>No momentum velocity setups triggered today.</td></tr>"
    # Build Equity Tables
    equity_sections = ""
    strategy_titles = {
        "qullamaggie_hft": "Kristjan Qullamaggie — High Tight Flags (HFT)",
        "stockbee_ep": "Stockbee (Pradeep Bonde) — Episodic Pivots (EP)",
        "minervini_trend": "Mark Minervini — Stage 2 Trend Template",
        "parabolic_short": "Kristjan Qullamaggie — Parabolic Shorts",
    }

    for strat_id, title in strategy_titles.items():
        df = screener_results.get(strat_id, pd.DataFrame())
        if df.empty:
            rows = "<tr><td colspan='5' class='text-muted text-center py-3'>No setups triggered today.</td></tr>"
        else:
            rows = ""
            for _, r in df.head(15).iterrows():
                tick = r.get("ticker", "-")
                close_p = r.get("close", 0.0)
                vol = r.get("volume", 0)
                rs = r.get("rs_spy", "-")
                tv_link = f"https://www.tradingview.com/chart/?symbol={tick}"
                rows += f"""
                <tr>
                    <td><a href="{tv_link}" target="_blank" class="ticker-badge">{tick}</a></td>
                    <td class="text-white fw-bold">${close_p:.2f}</td>
                    <td>{vol:,.0f}</td>
                    <td>{rs}</td>
                    <td class="text-success small">{r.get("notes", "Passed Criteria")}</td>
                </tr>
                """

        equity_sections += f"""
        <div class="card bg-dark border-secondary mb-4">
            <div class="card-header bg-dark text-success fw-bold border-secondary">
                🚀 {title} ({len(df)} Setups)
            </div>
            <div class="table-responsive">
                <table class="table table-dark table-hover table-striped mb-0">
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th>Price</th>
                            <th>Volume</th>
                            <th>RS Score</th>
                            <th>Setup Details</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </div>
        """

    # Build CSP Rows
    csp_rows = ""
    for a in deep_csp_analyses:
        badge = "🟢 Tier 1" if a.tier == 1 else ("🟡 Tier 2" if a.tier == 2 else "🔴 Tier 3")
        tv_link = f"https://www.tradingview.com/chart/?symbol={a.ticker}"
        csp_rows += f"""
        <tr>
            <td class="text-center">{a.rank}</td>
            <td><a href="{tv_link}" target="_blank" class="ticker-badge">{a.ticker}</a></td>
            <td><strong>${a.strike:.2f} P</strong></td>
            <td>${a.mark:.2f}</td>
            <td>{a.exp_str}</td>
            <td><span class="badge {'bg-success' if a.tier==1 else 'bg-warning text-dark' if a.tier==2 else 'bg-danger'}">{badge}</span></td>
            <td><strong>{a.final_adj_score:.1f}</strong></td>
            <td class="text-success fw-bold">{a.trade_ror:.2f}%</td>
            <td class="text-muted small">{a.tier_rationale}</td>
        </tr>
        """

    # Build Covered Call Rows
    cc_rows = ""
    for i, c in enumerate(cc_candidates, 1):
        tv_link = f"https://www.tradingview.com/chart/?symbol={c.ticker}"
        cc_rows += f"""
        <tr>
            <td class="text-center">{i}</td>
            <td><a href="{tv_link}" target="_blank" class="ticker-badge">{c.ticker}</a></td>
            <td>${c.spot:.2f}</td>
            <td><strong>${c.strike:.1f} C</strong></td>
            <td>${c.mid:.2f}</td>
            <td>{c.expiry_date.strftime('%b %d')} ({c.dte}d)</td>
            <td class="text-success fw-bold">{c.static_yield_pct:.2f}%</td>
            <td class="text-info fw-bold">{c.if_called_yield_pct:.2f}%</td>
            <td class="text-muted small">+{c.ann_yield_pct:.1f}% Ann.</td>
        </tr>
        """

    # Build PMCC / LEAPS Rows
    pmcc_rows = ""
    for i, p in enumerate(pmcc_candidates, 1):
        tv_link = f"https://www.tradingview.com/chart/?symbol={p.ticker}"
        l_str = f"{p.long_expiry.strftime('%b %y')} ${p.long_strike:.0f}C (Δ{p.long_delta:.2f})"
        s_str = f"{p.short_expiry.strftime('%b %d')} ${p.short_strike:.0f}C (Δ{p.short_delta:.2f})"
        pmcc_rows += f"""
        <tr>
            <td class="text-center">{i}</td>
            <td><a href="{tv_link}" target="_blank" class="ticker-badge">{p.ticker}</a></td>
            <td>${p.spot:.2f}</td>
            <td><code>{l_str}</code></td>
            <td><code>{s_str}</code></td>
            <td><strong>${p.net_debit:.2f}</strong></td>
            <td>${p.short_credit:.2f}</td>
            <td class="text-success fw-bold">+{p.roc_pct:.2f}%</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Master Daily Scanner Suite — {today_str}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #0b0f12; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 24px; }}
        .header-title {{ font-size: 28px; font-weight: 800; color: #fff; margin-bottom: 2px; }}
        .ticker-badge {{ background: #1f2933; color: #fff; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-weight: bold; text-decoration: none; border: 1px solid #2d3748; }}
        .ticker-badge:hover {{ color: #3fb950; border-color: #3fb950; }}
        .card {{ background-color: #11161b !important; border: 1px solid #1d252c !important; }}
    </style>
</head>
<body>
    <div class="container-fluid max-w-7xl">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h1 class="header-title">Master Daily Scanner Suite</h1>
                <div class="text-muted small">Equity Momentum &amp; Options Income Leaderboards</div>
            </div>
            <div class="text-end text-muted small">
                <div>Scan Date: <strong>{today_str}</strong></div>
                <div>Status: <span class="badge bg-success">Automated Scan Completed</span></div>
            </div>
        </div>

        <!-- 1. CSP & Spreads Section -->
        <div class="card bg-dark border-secondary mb-4">
            <div class="card-header bg-dark text-success fw-bold border-secondary d-flex justify-content-between">
                <span>💰 Ben PatternProfits — Cash-Secured Puts &amp; Bull Put Spreads ({len(deep_csp_analyses)} Ranked)</span>
                <span class="badge bg-success">{len([x for x in deep_csp_analyses if x.tier==1])} Tier-1 Green Lights</span>
            </div>
            <div class="table-responsive">
                <table class="table table-dark table-hover table-striped mb-0">
                    <thead>
                        <tr>
                            <th class="text-center">#</th>
                            <th>Ticker</th>
                            <th>Strike</th>
                            <th>Mark</th>
                            <th>Exp</th>
                            <th>Tier</th>
                            <th>Adj. Score</th>
                            <th>ROR %</th>
                            <th>Deep Analysis &amp; Trajectory Read</th>
                        </tr>
                    </thead>
                    <tbody>{csp_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- 2. Covered Calls Section -->
        <div class="card bg-dark border-secondary mb-4">
            <div class="card-header bg-dark text-info fw-bold border-secondary d-flex justify-content-between">
                <span>🎯 Monthly Covered Call Income Engine ({len(cc_candidates)} Found)</span>
                <span class="badge bg-info text-dark">High Yield + Upside Buffer</span>
            </div>
            <div class="table-responsive">
                <table class="table table-dark table-hover table-striped mb-0">
                    <thead>
                        <tr>
                            <th class="text-center">#</th>
                            <th>Ticker</th>
                            <th>Stock Price</th>
                            <th>Call Strike</th>
                            <th>Option Mark</th>
                            <th>Expiration</th>
                            <th>Monthly Yield</th>
                            <th>If-Called Total Return</th>
                            <th>Annualized Yield</th>
                        </tr>
                    </thead>
                    <tbody>{cc_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- 3. Poor Man's Covered Calls (LEAPS) Section -->
        <div class="card bg-dark border-secondary mb-4">
            <div class="card-header bg-dark text-warning fw-bold border-secondary d-flex justify-content-between">
                <span>🚀 Poor Man's Covered Calls / LEAPS ({len(pmcc_candidates)} Setups)</span>
                <span class="badge bg-warning text-dark">Deep ITM 0.80Δ + Front Month Rent</span>
            </div>
            <div class="table-responsive">
                <table class="table table-dark table-hover table-striped mb-0">
                    <thead>
                        <tr>
                            <th class="text-center">#</th>
                            <th>Ticker</th>
                            <th>Stock Price</th>
                            <th>Long LEAPS Leg (0.80Δ)</th>
                            <th>Short Front Leg (0.30Δ)</th>
                            <th>Net Debit Cost</th>
                            <th>Short Premium</th>
                            <th>Monthly Return on Capital</th>
                        </tr>
                    </thead>
                    <tbody>{pmcc_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- 4. Ben Bennett Focus List: Institutional Leaders Section -->
        <div class="card bg-dark border-secondary mb-4">
            <div class="card-header bg-dark text-warning fw-bold border-secondary d-flex justify-content-between">
                <span>🏛️ Ben Bennett Focus List — Institutional Leaders ({len(institutional_leaders)} Qualifiers)</span>
                <span class="badge bg-warning text-dark">Floors: EPS ≥25% • Rev ≥25% • RS ≥80 (Score: EPS 40 / Rev 30 / RS 30)</span>
            </div>
            <div class="table-responsive">
                <table class="table table-dark table-hover table-striped mb-0">
                    <thead>
                        <tr>
                            <th class="text-center">#</th>
                            <th>Ticker</th>
                            <th>Stock Price</th>
                            <th>EPS YoY %</th>
                            <th>Rev YoY %</th>
                            <th>RS Rating</th>
                            <th>Composite Score</th>
                            <th>Industry / Group</th>
                        </tr>
                    </thead>
                    <tbody>{inst_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- 5. Ben Bennett Velocity Scan: Momentum Leaders Section -->
        <div class="card bg-dark border-secondary mb-4">
            <div class="card-header bg-dark text-danger fw-bold border-secondary d-flex justify-content-between">
                <span>⚡ Ben Bennett Velocity Scan — Momentum Leaders ({len(velocity_leaders)} Qualifiers)</span>
                <span class="badge bg-danger">Float ≤ 100M • Rel Vol ≥ 130% • Days to Turn &lt; 20d</span>
            </div>
            <div class="table-responsive">
                <table class="table table-dark table-hover table-striped mb-0">
                    <thead>
                        <tr>
                            <th class="text-center">#</th>
                            <th>Ticker</th>
                            <th>Stock Price</th>
                            <th>Chg %</th>
                            <th>RS Rating</th>
                            <th>Rel Vol</th>
                            <th>Float</th>
                            <th>Days to Turn</th>
                            <th>Short Float &amp; Squeeze</th>
                        </tr>
                    </thead>
                    <tbody>{vel_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- Equity Momentum Sections -->
        <h4 class="text-white mt-5 mb-3">📈 Equity Momentum Breakouts &amp; Setups</h4>
        {equity_sections}
    </div>
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    run_all_scanners(open_browser=False)
