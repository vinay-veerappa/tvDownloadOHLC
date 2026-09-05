import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List

class OptimizationReporter:
    """
    Generates premium HTML research summaries for optimization runs.
    Includes Institutional Grading, Risk of Ruin, and EV metrics.
    """
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_report(self, 
                        run_id: str, 
                        ticker: str, 
                        strategy_name: str, 
                        best_params: Dict[str, Any], 
                        risk_metrics: Dict[str, Any],
                        trials_df: pd.DataFrame) -> str:
        """
        Generates the optimization_summary.html file.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # --- HTML Template ---
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Summary: {run_id}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --success: #22c55e;
            --warning: #eab308;
            --danger: #ef4444;
            --grade-a: #22c55e;
            --grade-b: #84cc16;
            --grade-c: #eab308;
            --grade-d: #f97316;
            --grade-f: #ef4444;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Inter', sans-serif; 
            background: var(--bg); 
            color: var(--text); 
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        /* Header */
        header {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 3rem;
            border-bottom: 1px solid var(--surface);
            padding-bottom: 2rem;
        }}
        h1 {{ font-size: 2.5rem; font-weight: 800; color: var(--accent); }}
        .meta {{ text-align: right; color: var(--text-muted); font-size: 0.9rem; }}

        /* Risk Profile Grid */
        .grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); 
            gap: 1.5rem; 
            margin-bottom: 3rem; 
        }}
        .card {{ 
            background: var(--surface); 
            padding: 1.5rem; 
            border-radius: 16px; 
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            border: 1px solid rgba(255,255,255,0.05);
        }}
        .card-label {{ color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
        .card-value {{ font-size: 1.5rem; font-weight: 700; display: flex; align-items: center; justify-content: space-between; }}
        
        .grade {{ 
            font-weight: 900; 
            padding: 4px 12px; 
            border-radius: 6px; 
            font-size: 1rem;
            min-width: 40px;
            text-align: center;
        }}
        .grade-A {{ background: var(--grade-a); color: #fff; }}
        .grade-B {{ background: var(--grade-b); color: #fff; }}
        .grade-C {{ background: var(--grade-c); color: #fff; }}
        .grade-D {{ background: var(--grade-d); color: #fff; }}
        .grade-F {{ background: var(--grade-f); color: #fff; }}
        
        /* Sections */
        section {{ margin-bottom: 3rem; }}
        h2 {{ font-size: 1.5rem; margin-bottom: 1.5rem; color: var(--text); border-left: 4px solid var(--accent); padding-left: 1rem; }}

        /* Tables */
        .table-wrapper {{ overflow-x: auto; background: var(--surface); border-radius: 16px; border: 1px solid rgba(255,255,255,0.05); }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 1rem 1.5rem; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        th {{ background: rgba(255,255,255,0.03); color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: rgba(255,255,255,0.02); }}

        /* Best Params List */
        .params-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }}
        .param-item {{ background: rgba(56, 189, 248, 0.1); padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid rgba(56, 189, 248, 0.2); }}
        .param-key {{ font-size: 0.75rem; color: var(--accent); font-weight: 600; text-transform: uppercase; }}
        .param-value {{ font-size: 1rem; font-weight: 700; }}

        .badge {{ padding: 4px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
        .badge-success {{ background: rgba(34, 197, 94, 0.2); color: var(--success); }}
        .badge-warning {{ background: rgba(234, 179, 8, 0.2); color: var(--warning); }}

    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>{ticker} Optimization Summary</h1>
                <p style="color: var(--text-muted)">{strategy_name} | {run_id}</p>
            </div>
            <div class="meta">
                <p>Generated: {timestamp}</p>
                <p>Strategy Version: 3.0.0 (Institutional)</p>
            </div>
        </header>

        <section>
            <h2>🏆 Best Parameter Set</h2>
            <div class="params-grid">
                {"".join([f'<div class="param-item"><div class="param-key">{k}</div><div class="param-value">{v}</div></div>' for k, v in best_params.items()])}
            </div>
        </section>

        <section>
            <h2>🛡️ Institutional Risk Profile (OOS)</h2>
            <div class="grid">
                <div class="card">
                    <div class="card-label">Expected Value (EV)</div>
                    <div class="card-value">
                        ${risk_metrics.get('ev_dollars', 0):.2f}
                        <span class="grade grade-{risk_metrics.get('ev_grade', 'F')}">{risk_metrics.get('ev_grade', 'F')}</span>
                    </div>
                </div>
                <div class="card">
                    <div class="card-label">Profit Factor</div>
                    <div class="card-value">
                        {risk_metrics.get('profit_factor', 0):.2f}
                        <span class="grade grade-{risk_metrics.get('pf_grade', 'F')}">{risk_metrics.get('pf_grade', 'F')}</span>
                    </div>
                </div>
                <div class="card">
                    <div class="card-label">System Quality (SQN)</div>
                    <div class="card-value">
                        {risk_metrics.get('sqn', 0):.2f}
                        <span class="grade grade-{risk_metrics.get('sqn_grade', 'F')}">{risk_metrics.get('sqn_grade', 'F')}</span>
                    </div>
                </div>
                <div class="card">
                    <div class="card-label">Combined Edge</div>
                    <div class="card-value">
                        {risk_metrics.get('combined_edge', 0):.2f}
                        <span class="grade grade-{risk_metrics.get('ce_grade', 'F')}">{risk_metrics.get('ce_grade', 'F')}</span>
                    </div>
                </div>
                <div class="card">
                    <div class="card-label">Risk of Ruin</div>
                    <div class="card-value">
                        {risk_metrics.get('ror', 1.0) * 100:.2f}%
                        <span class="badge { 'badge-success' if risk_metrics.get('ror', 1.0) < 0.01 else 'badge-warning' }">
                            {risk_metrics.get('ror_grade', 'Dangerous')}
                        </span>
                    </div>
                </div>
                <div class="card">
                    <div class="card-label">Drawdown Risk (DRR)</div>
                    <div class="card-value">
                        {risk_metrics.get('drr', 0):.2f}
                        <span class="grade grade-{risk_metrics.get('drr_grade', 'F')}">{risk_metrics.get('drr_grade', 'F')}</span>
                    </div>
                </div>
            </div>
        </section>

        <section>
            <h2>📊 Optimization Trials (Top 20)</h2>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Trial</th>
                            <th>Value (Sharpe)</th>
                            <th>Status</th>
                            {"".join([f'<th>{col}</th>' for col in trials_df.columns if col.startswith('params_')])}
                        </tr>
                    </thead>
                    <tbody>
                        {self._generate_trials_rows(trials_df)}
                    </tbody>
                </table>
            </div>
        </section>
    </div>
</body>
</html>
        """
        
        output_path = os.path.join(self.output_dir, "optimization_summary.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        return output_path

    def _generate_trials_rows(self, df: pd.DataFrame) -> str:
        # Sort by value decending, take top 20
        df_sorted = df.sort_values(by="value", ascending=False).head(20)
        rows = []
        for _, row in df_sorted.iterrows():
            param_cols = [f'<td>{row[col]}</td>' for col in df.columns if col.startswith('params_')]
            rows.append(f"""
                <tr>
                    <td>{row['number']}</td>
                    <td style="font-weight: 700; color: var(--accent)">{row['value']:.4f}</td>
                    <td><span class="badge badge-success">{row['state']}</span></td>
                    {"".join(param_cols)}
                </tr>
            """)
        return "".join(rows)
