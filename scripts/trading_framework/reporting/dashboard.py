"""
Static Research Dashboard Generator
"""
import os
import re
from pathlib import Path

def generate_dashboard():
    """
    Scans outputs and generates a premium HTML index.
    """
    output_dir = Path("scripts/trading_framework/reporting/outputs")
    if not output_dir.exists():
        print("❌ No outputs found to generate dashboard.")
        return

    md_files = list(output_dir.glob("*.md"))
    results = []

    # Simple regex parser for our markdown grading table
    # | **Expected Value (EV)** | $120.00 | **A** |
    grade_pattern = re.compile(r"\| \s*\*\*([^*]+)\*\* \s*\| \s*([^|]+) \s*\| \s*\*\*([A-F])\*\* \s*\|")

    for md_file in md_files:
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            grades = grade_pattern.findall(content)
            
            # Extract ticker/strategy from filename
            # tearsheet_NQ1_box_reversion.md
            parts = md_file.stem.split("_")
            ticker = parts[1] if len(parts) > 1 else "Unknown"
            strategy = "_".join(parts[2:]) if len(parts) > 2 else "Unknown"
            
            results.append({
                "ticker": ticker,
                "strategy": strategy,
                "grades": {g[0].strip().split('(')[0].strip(): g[2] for g in grades},
                "filename": md_file.name
            })

    # Header and CSS
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Institutional Research Dashboard</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --text: #f8fafc;
            --accent: #38bdf8;
            --grade-a: #22c55e;
            --grade-b: #84cc16;
            --grade-c: #eab308;
            --grade-d: #f97316;
            --grade-f: #ef4444;
        }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); padding: 2rem; }}
        h1 {{ color: var(--accent); margin-bottom: 2rem; font-weight: 800; border-bottom: 2px solid var(--surface); padding-bottom: 1rem; }}
        .leaderboard {{ width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 12px; overflow: hidden; }}
        th, td {{ padding: 1.25rem; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #334155; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.1em; }}
        .grade {{ font-weight: 900; padding: 4px 8px; border-radius: 4px; display: inline-block; width: 24px; text-align: center; }}
        .grade-A {{ background: var(--grade-a); }}
        .grade-B {{ background: var(--grade-b); }}
        .grade-C {{ background: var(--grade-c); }}
        .grade-D {{ background: var(--grade-d); }}
        .grade-F {{ background: var(--grade-f); }}
        .row:hover {{ background: #2d3e50; transition: 0.2s; cursor: pointer; }}
        a {{ color: inherit; text-decoration: none; }}
    </style>
</head>
<body>
    <h1>🚀 Institutional Research Leaderboard</h1>
    <table class="leaderboard">
        <thead>
            <tr>
                <th>Ticker</th>
                <th>Strategy</th>
                <th>EV</th>
                <th>PF</th>
                <th>SQN</th>
                <th>DRR</th>
                <th>Edge</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
    """

    for r in results:
        g = r["grades"]
        html += f"""
            <tr class="row">
                <td>{r['ticker']}</td>
                <td>{r['strategy']}</td>
                <td><span class="grade grade-{g.get('Expected Value', 'F')}">{g.get('Expected Value', 'F')}</span></td>
                <td><span class="grade grade-{g.get('Profit Factor', 'F')}">{g.get('Profit Factor', 'F')}</span></td>
                <td><span class="grade grade-{g.get('System Quality', 'F')}">{g.get('System Quality', 'F')}</span></td>
                <td><span class="grade grade-{g.get('Drawdown Risk', 'F')}">{g.get('Drawdown Risk', 'F')}</span></td>
                <td><span class="grade grade-{g.get('Combined Edge', 'F')}">{g.get('Combined Edge', 'F')}</span></td>
                <td><a href="{r['filename']}">📄 View Tearsheet</a></td>
            </tr>
        """

    html += """
        </tbody>
    </table>
</body>
</html>
    """

    index_path = output_dir / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✨ Dashboard generated successfully: {index_path}")

if __name__ == "__main__":
    generate_dashboard()
