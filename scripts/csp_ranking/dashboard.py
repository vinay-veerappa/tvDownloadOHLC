import sys
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pathlib import Path
from scripts.csp_ranking.scoring_engine import ScoredCandidate
from scripts.csp_ranking.trajectory_analyzer import CandidateDeepAnalysis

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPORTS_DIR = Path("reports/csp_scanner")


def render_terminal_dashboard(
    all_candidates: List[ScoredCandidate],
    deep_analyses: List[CandidateDeepAnalysis],
    scan_source: str = "",
):
    """
    Renders Ben (@PatternProfits)'s exact 3-section institutional review in the terminal.
    """
    passed = deep_analyses
    excluded = [c for c in all_candidates if not c.is_passed_hard_filters]
    unique_tickers = len(set(c.contract.ticker for c in all_candidates))

    print("\n" + "=" * 105)
    print(f"  CASH-SECURED PUT RANKING                               Scan date: {date.today().strftime('%b %d, %Y')}")
    print(f"  Candidate Summary                                      Source: {scan_source}")
    print(f"                                                         Ranking: 1 contract / ticker")
    print("=" * 105)

    print(f"\n  [{len(all_candidates)}] CONTRACTS PARSED   |   [{unique_tickers}] UNIQUE TICKERS   |   [{len(excluded)}] EXCLUDED   |   [{len(passed)}] RANKED CANDIDATES\n")

    # Section 1: Multi-Quarter Trajectory Read
    print("  1. MULTI-QUARTER TRAJECTORY & RELATIVE STRENGTH READ")
    print("  " + "-" * 101)
    t_header = f"  {'Ticker':<7} {'RS Line Read':<28} {'Revenue Trend':<32} {'EPS Trend':<32}"
    print(t_header)
    print("  " + "-" * 101)
    for a in passed:
        rs_sub = (a.rs_line_read[:26] + "..") if len(a.rs_line_read) > 28 else a.rs_line_read
        rev_sub = (a.rev_trend_read[:30] + "..") if len(a.rev_trend_read) > 32 else a.rev_trend_read
        eps_sub = (a.eps_trend_read[:30] + "..") if len(a.eps_trend_read) > 32 else a.eps_trend_read
        print(f"  {a.ticker:<7} {rs_sub:<28} {rev_sub:<32} {eps_sub:<32}")
    print("  " + "-" * 101)

    # Section 2: Adjusted Ranking Leaderboard
    print("\n  2. ADJUSTED RANKING LEADERBOARD (BEN @PatternProfits METHODOLOGY)")
    print("  " + "-" * 101)
    header = f"  {'#':<4} {'TICKER':<8} {'STRIKE':<11} {'MARK':<9} {'EXP':<12} {'BASE':<7} {'RS':<5} {'REV':<5} {'EPS':<5} {'ADJ. SCORE':<12} {'ROR':<7}"
    print(header)
    print("  " + "-" * 101)

    for a in passed:
        rank_str = f"{a.rank:<4}"
        ticker_str = f"[{a.ticker}]"
        strike_str = f"{a.strike:.2f} P"
        mark_str = f"${a.mark:.2f}"
        exp_str = a.exp_str
        base_str = f"{a.base_score:.1f}"
        rs_str = f"{a.rs_adj:+d}"
        rev_str = f"{a.rev_adj:+d}"
        eps_str = f"{a.eps_adj:+d}"
        score_str = f"{a.final_adj_score:.1f}"
        ror_str = f"{a.trade_ror:.2f}%"

        badge = "🥇" if a.rank == 1 else ("🥈" if a.rank == 2 else ("🥉" if a.rank == 3 else "⭐️"))
        row = f"  {rank_str} {ticker_str:<8} {strike_str:<11} {mark_str:<9} {exp_str:<12} {base_str:<7} {rs_str:<5} {rev_str:<5} {eps_str:<5} {badge} {score_str:<8} {ror_str:<7}"
        print(row)
    print("  " + "-" * 101)

    # Section 3: Actionable Conviction Tiers
    print("\n  3. ACTIONABLE CONVICTION TIERS & TRADE RECOMMENDATIONS")
    print("  " + "-" * 101)
    t1 = [a for a in passed if a.tier == 1]
    t2 = [a for a in passed if a.tier == 2]
    t3 = [a for a in passed if a.tier == 3]

    if t1:
        print("  🟢 TIER 1: HIGH-CONVICTION GREEN LIGHTS (Top Institutional Trades)")
        for a in t1:
            print(f"     • {a.ticker} ${a.strike:.1f} Put ({a.exp_str}) — Mark: ${a.mark:.2f} | ROR: {a.trade_ror:.2f}% | Score: {a.final_adj_score:.1f}")
            print(f"       -> {a.tier_rationale}")

    if t2:
        print("  🟡 TIER 2: CAUTIOUS / SECONDARY GROWTH PLAYS")
        for a in t2:
            print(f"     • {a.ticker} ${a.strike:.1f} Put ({a.exp_str}) — Mark: ${a.mark:.2f} | ROR: {a.trade_ror:.2f}% | Score: {a.final_adj_score:.1f}")
            print(f"       -> {a.tier_rationale}")

    if t3:
        print("  🔴 TIER 3: DECELERATION TRAPS / DE-PRIORITIZE")
        for a in t3:
            print(f"     • {a.ticker} ${a.strike:.1f} Put ({a.exp_str}) — Base Score: {a.base_score:.1f} dropped to {a.final_adj_score:.1f}")
            print(f"       -> {a.rev_trend_read} | {a.eps_trend_read}")
    print("  " + "-" * 101)

    if excluded:
        print(f"\n  HARD-EXCLUDED CONTRACTS ({len(excluded)} Purged for Spread > 50% / Earnings / Low Vol)")
        print("  " + "-" * 101)
        for c in excluded[:8]:
            exp_str = c.contract.expiry_date.strftime("%b %d") if c.contract.expiry_date else "-"
            reasons = "; ".join(c.exclusion_reasons)
            print(f"  • {c.contract.ticker:<6} ${c.contract.strike:<6.1f} ({exp_str}) Mark: ${c.mark:.2f} | Vol: {c.contract.volume:<3} | ⚠️ {reasons}")
        if len(excluded) > 8:
            print(f"    ... and {len(excluded) - 8} more excluded contracts (view HTML dashboard).")
        print("  " + "-" * 101)
    print("\n")


def generate_html_dashboard(
    all_candidates: List[ScoredCandidate],
    deep_analyses: List[CandidateDeepAnalysis],
    scan_source: str = "",
) -> Path:
    """
    Generates a pixel-faithful dark-theme HTML dashboard matching Ben (@PatternProfits)'s UI,
    including the Multi-Quarter Trajectory Read, Adjusted Ranking, and Actionable Tiers.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    today_str = today.strftime("%b %d, %Y")
    file_date_str = today.strftime("%Y-%m-%d")
    html_path = REPORTS_DIR / f"csp_rankings_{file_date_str}.html"

    passed = deep_analyses
    excluded_all = [c for c in all_candidates if not c.is_passed_hard_filters]
    unique_tickers = len(set(c.contract.ticker for c in all_candidates))

    def fmt_adj(val: int) -> str:
        if val > 0:
            return f'<span class="adj-pos">+{val}</span>'
        elif val < 0:
            return f'<span class="adj-neg">{val}</span>'
        else:
            return f'<span class="adj-zero">0</span>'

    # Section 1: Trajectory Rows
    trajectory_rows = ""
    for a in passed:
        tv_link = f"https://www.tradingview.com/chart/?symbol={a.ticker}"
        trajectory_rows += f"""
        <tr>
            <td><a href="{tv_link}" target="_blank" class="ticker-badge">{a.ticker}</a></td>
            <td>{a.rs_line_read}</td>
            <td>{a.rev_trend_read}</td>
            <td>{a.eps_trend_read}</td>
            <td class="text-muted">{a.notes_read}</td>
        </tr>
        """

    # Section 2: Adjusted Ranking Rows
    adjusted_rows = ""
    for a in passed:
        rank_cls = "text-success fw-bold" if a.rank == 1 else "text-muted"
        score_bar_pct = min(100, max(5, int(a.final_adj_score)))
        score_bar = f"""
        <div class="score-container">
            <div class="score-bar-bg">
                <div class="score-bar-fill" style="width: {score_bar_pct}%;"></div>
            </div>
            <span class="score-val">{a.final_adj_score:.1f}</span>
        </div>
        """
        tv_link = f"https://www.tradingview.com/chart/?symbol={a.ticker}"

        adjusted_rows += f"""
        <tr>
            <td class="{rank_cls} text-center">{a.rank}</td>
            <td><a href="{tv_link}" target="_blank" class="ticker-badge">{a.ticker}</a></td>
            <td>
                <div class="strike-cell">
                    <span class="strike-val">{a.strike:.2f}</span>
                    <span class="strike-type">P</span>
                </div>
            </td>
            <td class="mark-val">${a.mark:.2f}</td>
            <td class="exp-cell">{a.exp_str}</td>
            <td class="base-val">{a.base_score:.1f}</td>
            <td class="text-center">{fmt_adj(a.rs_adj)}</td>
            <td class="text-center">{fmt_adj(a.rev_adj)}</td>
            <td class="text-center">{fmt_adj(a.eps_adj)}</td>
            <td>{score_bar}</td>
            <td class="ror-val">{a.trade_ror:.2f}%</td>
        </tr>
        """

    # Section 3: Action Cards
    t1_cards = ""
    for a in [x for x in passed if x.tier == 1]:
        t1_cards += f"""
        <div class="action-card card-tier1">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="tier-ticker">#{a.rank} {a.ticker} ${a.strike:.1f} PUT</span>
                <span class="badge bg-success">Yield: {a.trade_ror:.2f}% in 25d</span>
            </div>
            <div class="text-muted small mb-2">Mark: <strong>${a.mark:.2f}</strong> &bull; Exp: <strong>{a.exp_str}</strong> &bull; Score: <strong>{a.final_adj_score:.1f}</strong></div>
            <p class="mb-0 text-white-50 small">{a.tier_rationale} {a.rev_trend_read}.</p>
        </div>
        """

    t2_cards = ""
    for a in [x for x in passed if x.tier == 2]:
        t2_cards += f"""
        <div class="action-card card-tier2">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="tier-ticker">#{a.rank} {a.ticker} ${a.strike:.1f} PUT</span>
                <span class="badge bg-warning text-dark">Yield: {a.trade_ror:.2f}%</span>
            </div>
            <div class="text-muted small mb-2">Mark: <strong>${a.mark:.2f}</strong> &bull; Exp: <strong>{a.exp_str}</strong> &bull; Score: <strong>{a.final_adj_score:.1f}</strong></div>
            <p class="mb-0 text-white-50 small">{a.tier_rationale}</p>
        </div>
        """

    t3_cards = ""
    for a in [x for x in passed if x.tier == 3]:
        t3_cards += f"""
        <div class="action-card card-tier3">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="tier-ticker">#{a.rank} {a.ticker} ${a.strike:.1f} PUT</span>
                <span class="badge bg-danger">Deceleration Trap</span>
            </div>
            <div class="text-muted small mb-2">Base Score: <strong>{a.base_score:.1f}</strong> &rarr; Adjusted: <strong>{a.final_adj_score:.1f}</strong> (-{a.base_score-a.final_adj_score:.0f} pts)</div>
            <p class="mb-0 text-white-50 small">{a.eps_trend_read}. Caution on selling puts into decelerating quarters.</p>
        </div>
        """

    excluded_rows = ""
    for c in excluded_all:
        exp_str = c.contract.expiry_date.strftime("%b %d, %Y") if c.contract.expiry_date else "-"
        reasons = "; ".join(c.exclusion_reasons)
        tv_link = f"https://www.tradingview.com/chart/?symbol={c.contract.ticker}"
        excluded_rows += f"""
        <tr class="excluded-tr">
            <td><a href="{tv_link}" target="_blank" class="ticker-badge ticker-excluded">{c.contract.ticker}</a></td>
            <td><span class="strike-val">{c.contract.strike:.2f} P</span></td>
            <td>${c.mark:.2f}</td>
            <td>{exp_str}</td>
            <td>{c.contract.volume}</td>
            <td>{c.contract.spread_pct*100.0:.0f}%</td>
            <td class="text-warning">⚠️ {reasons}</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CASH-SECURED PUT RANKING — Candidate Summary</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f12;
            --card-bg: #11161b;
            --card-border: #1d252c;
            --text-primary: #e6edf3;
            --text-muted: #6e7681;
            --accent-green: #3fb950;
            --accent-red: #f85149;
            --accent-pill: #1f2933;
            --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 32px 40px;
            font-size: 14px;
        }}
        .header-sub {{
            font-family: var(--font-mono);
            color: var(--accent-green);
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        .header-title {{
            font-size: 32px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #ffffff;
            margin-bottom: 0;
        }}
        .meta-text {{
            font-family: var(--font-mono);
            font-size: 13px;
            color: var(--text-muted);
            line-height: 1.6;
        }}
        .meta-text strong {{
            color: #c9d1d9;
        }}
        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin: 28px 0;
        }}
        .kpi-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 20px 24px;
        }}
        .kpi-number {{
            font-size: 36px;
            font-weight: 700;
            color: #ffffff;
            line-height: 1;
            margin-bottom: 8px;
        }}
        .kpi-label {{
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .section-header {{
            font-family: var(--font-mono);
            font-size: 12px;
            font-weight: 700;
            color: var(--text-muted);
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-top: 36px;
            margin-bottom: 14px;
        }}
        .table-ben {{
            width: 100%;
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            border-collapse: separate;
            border-spacing: 0;
            overflow: hidden;
            margin-bottom: 30px;
        }}
        .table-ben th {{
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 16px 14px;
            border-bottom: 1px solid var(--card-border);
            background-color: rgba(255, 255, 255, 0.01);
        }}
        .table-ben td {{
            padding: 14px 14px;
            border-bottom: 1px solid #161d24;
            vertical-align: middle;
            font-size: 14px;
        }}
        .ticker-badge {{
            display: inline-block;
            background-color: var(--accent-pill);
            color: #ffffff;
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 13px;
            padding: 5px 12px;
            border-radius: 6px;
            text-decoration: none;
            border: 1px solid #2d3748;
            transition: all 0.15s ease;
        }}
        .ticker-badge:hover {{
            background-color: #2b3644;
            color: var(--accent-green);
            border-color: var(--accent-green);
        }}
        .ticker-excluded {{
            opacity: 0.7;
            background-color: #201415;
            border-color: #442224;
        }}
        .strike-cell {{
            display: flex;
            align-items: baseline;
            gap: 6px;
        }}
        .strike-val {{
            font-family: var(--font-mono);
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
        }}
        .strike-type {{
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 600;
        }}
        .mark-val {{
            font-family: var(--font-mono);
            font-size: 14px;
            font-weight: 600;
            color: #ffffff;
        }}
        .exp-cell {{
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--text-muted);
        }}
        .base-val {{
            font-family: var(--font-mono);
            color: var(--text-muted);
            font-size: 13px;
        }}
        .adj-pos {{
            color: var(--accent-green);
            font-family: var(--font-mono);
            font-weight: 700;
        }}
        .adj-neg {{
            color: var(--accent-red);
            font-family: var(--font-mono);
            font-weight: 700;
        }}
        .adj-zero {{
            color: var(--text-muted);
            font-family: var(--font-mono);
        }}
        .score-container {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .score-bar-bg {{
            width: 70px;
            height: 5px;
            background-color: #21262d;
            border-radius: 3px;
            overflow: hidden;
        }}
        .score-bar-fill {{
            height: 100%;
            background-color: var(--accent-green);
            border-radius: 3px;
        }}
        .score-val {{
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 14px;
            color: #ffffff;
            min-width: 35px;
        }}
        .ror-val {{
            font-family: var(--font-mono);
            font-weight: 600;
            color: #ffffff;
            font-size: 14px;
        }}
        .action-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 12px;
        }}
        .card-tier1 {{
            border-left: 4px solid var(--accent-green);
        }}
        .card-tier2 {{
            border-left: 4px solid #d29922;
        }}
        .card-tier3 {{
            border-left: 4px solid var(--accent-red);
        }}
        .tier-ticker {{
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 15px;
            color: #ffffff;
        }}
        .footnote-card {{
            background-color: transparent;
            border-top: 1px solid var(--card-border);
            padding-top: 24px;
            margin-top: 30px;
            font-family: var(--font-mono);
            font-size: 12px;
            color: #8b949e;
            line-height: 1.7;
        }}
        .footnote-card strong {{
            color: #c9d1d9;
        }}
        .excluded-tr td {{
            background-color: rgba(248, 81, 73, 0.03);
        }}
    </style>
</head>
<body>
    <div class="container-fluid max-w-6xl">
        <!-- Header -->
        <div class="d-flex justify-content-between align-items-start">
            <div>
                <div class="header-sub">CASH-SECURED PUT RANKING</div>
                <h1 class="header-title">Candidate Summary</h1>
            </div>
            <div class="meta-text text-end">
                <div>Scan date: <strong>{today_str}</strong></div>
                <div>Source: <strong>{Path(scan_source).name if scan_source else "TOS Export"}</strong></div>
                <div>Ranking: <strong>1 contract / ticker</strong></div>
            </div>
        </div>

        <!-- 4 Top KPI Cards -->
        <div class="kpi-row">
            <div class="kpi-card">
                <div class="kpi-number">{len(all_candidates)}</div>
                <div class="kpi-label">Contracts Parsed</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-number">{unique_tickers}</div>
                <div class="kpi-label">Unique Tickers</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-number" style="color: #f0883e;">{len(excluded_all)}</div>
                <div class="kpi-label">Excluded — Spread / Earnings / Vol</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-number" style="color: var(--accent-green);">{len(passed)}</div>
                <div class="kpi-label">Ranked Candidates</div>
            </div>
        </div>

        <!-- Section 1: Multi-Quarter Trajectory Read -->
        <div class="section-header">1. Multi-Quarter Trajectory &amp; Relative Strength Read</div>
        <table class="table-ben">
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>RS Line</th>
                    <th>Revenue Trend (Sequential)</th>
                    <th>EPS Trend (Sequential)</th>
                    <th>Notes &amp; Flags</th>
                </tr>
            </thead>
            <tbody>
                {trajectory_rows}
            </tbody>
        </table>

        <!-- Section 2: Final Adjusted Rankings -->
        <div class="section-header">2. Adjusted Rankings (Ben @PatternProfits Methodology)</div>
        <table class="table-ben">
            <thead>
                <tr>
                    <th style="width: 40px;" class="text-center">#</th>
                    <th>TICKER</th>
                    <th>STRIKE</th>
                    <th>MARK</th>
                    <th>EXP</th>
                    <th>BASE</th>
                    <th class="text-center">RS</th>
                    <th class="text-center">REV</th>
                    <th class="text-center">EPS</th>
                    <th>ADJ. SCORE</th>
                    <th>ROR</th>
                </tr>
            </thead>
            <tbody>
                {adjusted_rows}
            </tbody>
        </table>

        <!-- Section 3: Actionable Conviction Tiers -->
        <div class="section-header">3. Actionable Conviction Tiers &amp; Execution Cards</div>
        <div class="row g-3">
            <div class="col-md-4">
                <h6 class="text-success fw-bold mb-2">🟢 Tier 1: Green Lights</h6>
                {t1_cards if t1_cards else '<div class="text-muted small">None meeting Tier 1 criteria.</div>'}
            </div>
            <div class="col-md-4">
                <h6 class="text-warning fw-bold mb-2">🟡 Tier 2: Secondary Plays</h6>
                {t2_cards if t2_cards else '<div class="text-muted small">None in Tier 2.</div>'}
            </div>
            <div class="col-md-4">
                <h6 class="text-danger fw-bold mb-2">🔴 Tier 3: Avoid / Decelerating</h6>
                {t3_cards if t3_cards else '<div class="text-muted small">None in Tier 3.</div>'}
            </div>
        </div>

        <!-- Hard-Excluded Table -->
        {f'''
        <div class="section-header mt-5">
            <span style="color: var(--accent-red);">Hard Exclusions (Before Scoring) — {len(excluded_all)} Contracts</span>
        </div>
        <table class="table-ben">
            <thead>
                <tr>
                    <th>TICKER</th>
                    <th>STRIKE</th>
                    <th>MARK</th>
                    <th>EXP</th>
                    <th>VOLUME</th>
                    <th>SPREAD %</th>
                    <th>EXCLUSION REASON</th>
                </tr>
            </thead>
            <tbody>
                {excluded_rows}
            </tbody>
        </table>
        ''' if excluded_all else ''}

        <!-- Exact Footnote / Methodology Card -->
        <div class="footnote-card">
            <div>Base score = ROR (25) + spread tightness (20) + liquidity (15) + technical cushion (15) + fundamentals (15) + |delta| (10), max 100.</div>
            <div>Hard exclusions (before scoring): earnings before expiration, volume &lt; 10, bid/ask spread &gt; 50% of mid.</div>
            <div>Adjustment (via RS Line + EPS &amp; Sales table): RS Line above its MA &rarr; +5, below &rarr; -5. Revenue trend (last 3-4 qtrs): growing &rarr; +5, mixed &rarr; 0, declining &rarr; -8. EPS trend: accelerating/stable &rarr; +5, choppy/no clear direction &rarr; 0, decelerating &rarr; -8.</div>
        </div>
    </div>
</body>
</html>
"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return html_path
