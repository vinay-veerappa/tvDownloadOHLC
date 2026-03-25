"""
Reporting Module
================
Generates Markdown reports for:
1. Standard Analysis (Grade, Edge Metrics)
2. Comparison Analysis (Delta between datasets)
3. Forensic Analysis (Contextual deep dive)
"""

from datetime import datetime
from .metrics import get_recommendations


# Standardized Metrics List for all reports
FULL_METRICS_LIST = [
    ('Trades', 'Trades', '{:.0f}'),
    ('Total P&L', 'Total P&L', '${:,.2f}'),
    ('Win Rate %', 'Win Rate %', '{:.2f}%'),
    ('Avg Contracts', 'Avg Contracts', '{:.1f}'),
    ('Risk ($)', 'Risk ($)', '${:.2f}'),
    ('EV ($)', 'Avg P&L (EV)', '${:.2f}'),
    ('Profit Factor', 'Profit Factor', '{:.2f}'),
    ('SQN', 'SQN', '{:.2f}'),
    ('Combined Edge', 'Combined Edge', '{:.1f}'),
    ('RoR %', 'RoR %', '{:.4f}%'),
    ('Max Drawdown', 'Max Drawdown', '${:,.0f}'),
    ('DRR', 'DRR', '{:.2f}'),
    ('Max Streak', 'Max Streak (Est)', '{:.1f}'),
    ('Grade', 'Grade', '**{}**'),
]

def generate_standard_report(datasets, all_stats):
    """
    Generates the 'Edge System' Report (Grade, EV, RoR).
    """
    lines = []
    lines.append("# Strategy Analysis Report")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    # 1. SCORECARD
    lines.append("## 🏆 Edge System Scorecard")
    lines.append("")
    names = [d['name'] for d in datasets]
    lines.append("| Metric | " + " | ".join(names) + " |")
    lines.append("|" + "|".join(["---"] * (len(names)+1)) + "|")
    
    for label, key, fmt in FULL_METRICS_LIST:
        row = [f"**{label}**"]
        for stats in all_stats:
            val = stats.get(key, 0)
            if isinstance(val, str): row.append(val)
            else: row.append(fmt.format(val))
        lines.append("| " + " | ".join(row) + " |")
        
    lines.append("")
    
    # 2. RECOMMENDATIONS
    lines.append("## 🛠️ Recommendations")
    for i, d in enumerate(datasets):
        name = d['name']
        stats = all_stats[i]
        recs = get_recommendations(stats)
        lines.append(f"### {name}")
        for r in recs:
            lines.append(f"- {r}")
        lines.append("")
        
    return "\n".join(lines)

def generate_comparison_report(base_dataset, compare_datasets, deltas):
    """
    Generate 'Impact Analysis' report (Cost vs Benefit) + Deep Risk Comparison.
    """
    lines = []
    lines.append("# Comparative Analysis Report")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    # --- 1. DEEP RISK SCORECARD ---
    lines.append("## 📊 Risk Profile Scorecard (Quality vs Quantity)")
    lines.append("Do the filters improve the *quality* of the strategy, even if profit drops?")
    lines.append("")
    
    # header
    all_sets = [base_dataset] + compare_datasets
    names = [d['name'] for d in all_sets]
    lines.append("| Metric | " + " | ".join(names) + " |")
    lines.append("|" + "|".join(["---"] * (len(names)+1)) + "|")
    
    # metrics to show (Standardized)
    for label, key, fmt in FULL_METRICS_LIST:
        row = [f"**{label}**"]
        for d in all_sets:
            # stats are in d['stats']
            val = d['stats'].get(key, 0)
            if isinstance(val, str): row.append(val)
            else: row.append(fmt.format(val))
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append(f"## Impact Analysis (vs Base: `{base_dataset['name']}`)")
    lines.append(f"- Trades: {len(base_dataset['df'])}")
    lines.append(f"- P&L: ${base_dataset['stats']['Total P&L']:,.2f}")
    lines.append("")
    
    for i, d in enumerate(compare_datasets):
        delta = deltas[i]
        name = d['name']
        lines.append(f"## vs `{name}`")
        lines.append(f"- **Trades**: {len(d['df'])} (Diff: {len(d['df']) - len(base_dataset['df'])})")
        lines.append(f"- **P&L**: ${d['stats']['Total P&L']:,.2f} (Delta: ${d['stats']['Total P&L'] - base_dataset['stats']['Total P&L']:,.2f})")
        lines.append("")
        lines.append("### Impact Analysis")
        lines.append(f"- **Missed Winners**: {delta['missed_wins_count']} (Cost: ${delta['missed_pnl']:,.2f})")
        lines.append(f"- **Avoided Losers**: {delta['avoided_loss_count']} (Saved: ${delta['avoided_loss_val']:,.2f})")
        lines.append(f"- **Net Efficiency**: ${delta['net_impact']:,.2f}")
        lines.append(f"*(Better to filter? {'YES ✅' if delta['net_impact'] > 0 else 'NO ❌'})*")
        lines.append("---")
        
    return "\n".join(lines)

def generate_forensic_report(dataset, forensic_stats_text):
    """
    Generate Forensic Deep Dive report.
    """
    lines = []
    lines.append(f"# Forensic Analysis: {dataset['name']}")
    lines.append("Enriching trade data with external context to find FAILURE PATTERNS.")
    lines.append("")
    lines.append("## 🔍 Correlation Findings")
    lines.append(forensic_stats_text)
    lines.append("")
    lines.append("## 💡 Conclusions")
    lines.append("If 'Trend Fighters' or 'Traps' > 20%, consider adding context filters (VWAP, Profiler).")
    lines.append("If 'Chop' > 20%, consider Min Range filter.")
    
    return "\n".join(lines)
