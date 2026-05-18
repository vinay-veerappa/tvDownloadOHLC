import logging
import os
import json
import yaml
from datetime import datetime, timedelta
import pytz
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logger = logging.getLogger(__name__)

class AnalyticsService:
    """
    Analytics & Performance Rollup Engine.
    Executes Daily EOD metric updates, assigns grades (A+ through F),
    renders beautiful dark-mode equity curves, and generates comprehensive
    Weekly Rundown markdown reports saved to DB and local files.
    """
    def __init__(self, prisma, config_path: str):
        self.db = prisma
        self.config_path = config_path
        self.config = {}
        
        # Load config
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Create assets & rundowns directories inside workspace
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.assets_dir = os.path.join(self.base_dir, "assets")
        self.rundowns_dir = os.path.join(self.base_dir, "rundowns")
        
        os.makedirs(self.assets_dir, exist_ok=True)
        os.makedirs(self.rundowns_dir, exist_ok=True)

    async def run_daily_rollup(self, now: datetime):
        """
        Daily EOD rollup. Calculates performance metrics for each active 
        ResearchStrategy combination, generates/updates their ResearchRun rows,
        and saves equity curves.
        """
        logger.info(f"Analytics: Starting Daily EOD Rollup at {now}")
        
        # Fetch all silos (Accounts)
        accounts = await self.db.account.find_many()
        
        for account in accounts:
            try:
                # Name format is {StrategyCode}_{VariantName}_{Ticker}
                # e.g., ZERO_DTE_PCS_16D_SPY
                name = account.name
                
                # Retrieve the ResearchStrategy matching this name
                research_strat = await self.db.researchstrategy.find_unique(where={"name": name})
                if not research_strat:
                    continue

                # Parse the parts
                parts = name.split("_")
                if len(parts) < 3:
                    continue
                
                strategy_code = parts[0]
                ticker = parts[-1]

                # Fetch all trades for this account
                trades = await self.db.trade.find_many(
                    where={"accountId": account.id},
                    include={"snapshots": True}
                )

                closed_trades = [t for t in trades if t.status == "CLOSED"]
                total_trades = len(closed_trades)
                
                # Compute basic metrics
                wins = [t for t in closed_trades if (t.pnl or 0) > 0]
                losses = [t for t in closed_trades if (t.pnl or 0) <= 0]
                win_rate = (len(wins) / total_trades) if total_trades > 0 else 0.0

                total_pnl = sum(t.pnl or 0.0 for t in closed_trades)
                avg_pnl = (total_pnl / total_trades) if total_trades > 0 else 0.0

                gross_profit = sum(t.pnl or 0.0 for t in wins)
                gross_loss = abs(sum(t.pnl or 0.0 for t in losses))
                profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

                # Expectancy
                expectancy = (win_rate * avg_pnl) - ((1.0 - win_rate) * (gross_loss / len(losses) if len(losses) > 0 else 0.0))

                # Sharpe ratio (using daily trade returns)
                sharpe = 0.0
                if len(closed_trades) >= 3:
                    import numpy as np
                    pnls = [t.pnl or 0.0 for t in closed_trades]
                    std_dev = np.std(pnls)
                    if std_dev > 0:
                        sharpe = float(np.mean(pnls) / std_dev * np.sqrt(252)) # annualized approximation

                # Drawdown calculation
                max_dd = 0.0
                running_balance = account.initialBalance
                peak = running_balance
                for t in sorted(closed_trades, key=lambda x: x.exitDate or x.createdAt):
                    running_balance += t.pnl or 0.0
                    if running_balance > peak:
                        peak = running_balance
                    dd = peak - running_balance
                    if dd > max_dd:
                        max_dd = dd

                # Assign Grade based on Win Rate & Profit Factor
                grade = self._assign_grade(win_rate, profit_factor, total_trades)

                metrics = {
                    "initial_balance": account.initialBalance,
                    "current_balance": account.currentBalance,
                    "total_trades": total_trades,
                    "win_rate": float(win_rate),
                    "profit_factor": float(profit_factor),
                    "max_drawdown": float(max_dd),
                    "total_pnl": float(total_pnl),
                    "average_trade_pnl": float(avg_pnl),
                    "expectancy": float(expectancy),
                    "sharpe_ratio": float(sharpe),
                    "open_trades_count": len(trades) - total_trades
                }

                # Config params lookup
                # Find matching variant parameters in config yaml
                strat_config = self.config.get("strategies", {}).get(strategy_code, {})
                variant_name = "_".join(parts[1:-1])
                variant_params = strat_config.get("variants", {}).get(variant_name, {})

                # Generate Equity Curve
                equity_curve_path = await self._generate_equity_curve(account.name, account.initialBalance, closed_trades)

                # Write ResearchRun row
                run_id = f"RUN_{name}_{now.strftime('%Y%m%d')}"
                
                # Check if exists to update, else create
                existing_run = await self.db.researchrun.find_unique(where={"runId": run_id})
                if existing_run:
                    await self.db.researchrun.update(
                        where={"id": existing_run.id},
                        data={
                            "metricsJson": json.dumps(metrics),
                            "equityCurvePath": equity_curve_path,
                            "grade": grade,
                            "updatedAt": now
                        }
                    )
                else:
                    await self.db.researchrun.create(
                        data={
                            "runId": run_id,
                            "ticker": ticker,
                            "environment": "Paper",
                            "strategyId": research_strat.id,
                            "metricsJson": json.dumps(metrics),
                            "configJson": json.dumps(variant_params),
                            "equityCurvePath": equity_curve_path,
                            "grade": grade,
                            "createdAt": now,
                            "updatedAt": now
                        }
                    )

                logger.info(f"Analytics: Updated ResearchRun '{run_id}' with Grade {grade}")

            except Exception as e:
                logger.error(f"Analytics: Error processing daily rollup for silo '{account.name}': {e}", exc_info=True)

    async def run_weekly_rollup(self, now: datetime):
        """
        Weekly rollup. Generates a comprehensive summary markdown rundown report 
        collating all silo metrics and near-miss statistics. Saves to DB and a local physical file.
        """
        logger.info(f"Analytics: Generating Weekly Rundown Report...")
        
        # 1. Fetch all silos (Accounts) & ResearchRuns
        accounts = await self.db.account.find_many()
        runs = await self.db.researchrun.find_many(include={"strategy": True})

        # Match only the latest run for each active strategy
        latest_runs = {}
        for r in sorted(runs, key=lambda x: x.updatedAt, reverse=True):
            name = r.strategy.name
            if name not in latest_runs:
                latest_runs[name] = r

        # 2. Get Near-Miss stats in the last 7 days
        start_date = now - timedelta(days=7)
        near_misses = await self.db.signalnearmiss.find_many(
            where={"evaluatedAt": {"gte": start_date}}
        )

        near_miss_counts = {}
        for nm in near_misses:
            key = nm.failingFilter
            near_miss_counts[key] = near_miss_counts.get(key, 0) + 1

        # 3. Build Markdown content
        date_str = now.strftime("%Y-%m-%d")
        md = []
        md.append(f"# Weekly Strategy Engine Rundown — {date_str}\n")
        md.append("## 1. Executive Summary\n")
        
        total_silos = len(accounts)
        overall_pnl = sum(a.currentBalance - a.initialBalance for a in accounts)
        overall_pct = (overall_pnl / sum(a.initialBalance for a in accounts)) * 100.0 if sum(a.initialBalance for a in accounts) > 0 else 0.0

        md.append(f"- **Total Strategy Silos:** {total_silos}")
        md.append(f"- **Weekly Aggregate P&L:** ${overall_pnl:,.2f} ({overall_pct:+.2f}%)")
        md.append(f"- **System Mode:** Paper Execution (Continuous Scheduler)\n")

        md.append("## 2. Silo Rankings & Performance\n")
        md.append("| Silo Account | Initial Bal | Current Bal | Net P&L | Win Rate | Trades | Grade |")
        md.append("|:---|:---|:---|:---|:---|:---|:---|")

        # Sort silos by performance (absolute profit)
        silo_rows = []
        for account in accounts:
            name = account.name
            run = latest_runs.get(name)
            metrics = json.loads(run.metricsJson) if run and run.metricsJson else {}
            
            pnl = account.currentBalance - account.initialBalance
            win_rate = metrics.get("win_rate", 0.0) * 100.0
            trades = metrics.get("total_trades", 0)
            grade = run.grade if run else "N/A"

            silo_rows.append({
                "name": name,
                "initial": account.initialBalance,
                "current": account.currentBalance,
                "pnl": pnl,
                "win_rate": win_rate,
                "trades": trades,
                "grade": grade
            })

        silo_rows.sort(key=lambda x: x["pnl"], reverse=True)

        for s in silo_rows:
            md.append(f"| {s['name']} | ${s['initial']:,.2f} | ${s['current']:,.2f} | {s['pnl']:+,.2f} | {s['win_rate']:.1f}% | {s['trades']} | **{s['grade']}** |")

        md.append("\n## 3. Near-Miss Filter Insights\n")
        md.append("The following filters prevented the most trade entries in the past 7 days. These values highlight how strategies are interacting with current volatility regimes:\n")
        md.append("| Failing Filter | Frequency | Actionable Suggestion |")
        md.append("|:---|:---|:---|")

        filter_suggestions = {
            "iv_rank_below_threshold": "Elevate DTE spreads or widen strikes to boost probability under low IV.",
            "earnings_not_in_range": "Systematic earnings window is quiet; no major announcements scheduled.",
            "blackout_window_active": "Calendar blocks successful; system avoided key macroeconomic volatility.",
            "gex_boundary_blocked": "Spot was too far from optimal GEX Walls to trigger wall break debit spreads.",
            "expected_move_not_reached": "Spot price remained within daily EM bounds. No mean reversion trades triggered."
        }

        if near_miss_counts:
            sorted_filters = sorted(near_miss_counts.items(), key=lambda x: x[1], reverse=True)
            for filt, count in sorted_filters:
                suggestion = filter_suggestions.get(filt, "Refine parameters based on daily regimes.")
                md.append(f"| `{filt}` | {count} times | {suggestion} |")
        else:
            md.append("| *No near-miss data recorded this week.* | - | - |")

        md.append("\n## 4. Operational Recommendations\n")
        md.append("1. **Income Covered Calls:** Ensure Google and Tesla long holdings are calibrated for Covered Call write Deltas on Monday open.")
        md.append("2. **IV Rank Proxies:** Low volatility environment continues. Spreads on SPY/SPX have lower margins; consider scaling down size temporarily.")
        md.append("3. **Staleness Limits:** Check that GEX calculator is refreshed every 60 seconds to ensure index strategies scan without blocks.")
        
        markdown_text = "\n".join(md)

        # 4. Save to Database Rundown table
        # Since 'Rundown' has a unique 'date' field (which is a DateTime),
        # we will use the current date at midnight as the unique key.
        midnight = datetime(now.year, now.month, now.day, 0, 0, 0, 0)
        try:
            existing_rundown = await self.db.rundown.find_unique(where={"date": midnight})
            if existing_rundown:
                await self.db.rundown.update(
                    where={"id": existing_rundown.id},
                    data={"content": markdown_text}
                )
            else:
                await self.db.rundown.create(
                    data={
                        "date": midnight,
                        "content": markdown_text,
                        "mood": "Systematic",
                        "score": 100
                    }
                )
        except Exception as db_err:
            logger.error(f"Analytics: Failed to write weekly rundown to database: {db_err}")

        # 5. Save to local physical file
        filename = f"weekly_rundown_{date_str}.md"
        filepath = os.path.join(self.rundowns_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        logger.info(f"Analytics: Weekly Rundown saved to database and {filepath}")

    def _assign_grade(self, win_rate: float, profit_factor: float, total_trades: int) -> str:
        """Assigns a visual grade based on trading metrics."""
        if total_trades == 0:
            return "N/A"
        
        if win_rate >= 0.80 and profit_factor >= 2.0:
            return "A+"
        elif win_rate >= 0.70 and profit_factor >= 1.5:
            return "A"
        elif win_rate >= 0.60 and profit_factor >= 1.2:
            return "B"
        elif win_rate >= 0.50 and profit_factor >= 1.0:
            return "C"
        elif win_rate >= 0.40:
            return "D"
        else:
            return "F"

    async def _generate_equity_curve(self, silo_name: str, initial_balance: float, closed_trades: list) -> str:
        """Generates a premium dark-mode equity curve image using matplotlib."""
        if not closed_trades:
            # Generate static image with just the initial balance line
            fig, ax = plt.subplots(figsize=(8, 4), facecolor="#121212")
            ax.set_facecolor("#1e1e1e")
            ax.plot([0, 10], [initial_balance, initial_balance], color="#2962FF", linewidth=2.5)
            ax.set_title(f"Equity Curve - {silo_name}", color="white", fontsize=12, pad=15)
            ax.spines['bottom'].set_color('#333333')
            ax.spines['left'].set_color('#333333')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.tick_params(colors='white')
            ax.grid(True, color='#2c2c2c', linestyle='--')
            
            filepath = os.path.join(self.assets_dir, f"{silo_name}_equity.png")
            plt.savefig(filepath, facecolor="#121212", bbox_inches='tight', dpi=100)
            plt.close()
            return filepath

        # Calculate chronological equity curve
        sorted_trades = sorted(closed_trades, key=lambda x: x.exitDate or x.createdAt)
        
        dates = [t.entryDate for t in sorted_trades]
        equity = []
        current = initial_balance
        
        # Add initial point
        dates.insert(0, sorted_trades[0].entryDate - timedelta(days=1))
        equity.append(initial_balance)
        
        for t in sorted_trades:
            current += t.pnl or 0.0
            dates.append(t.exitDate or t.createdAt)
            equity.append(current)

        # Matplotlib plot
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5), facecolor="#121212")
        ax.set_facecolor("#1e1e1e")
        
        # Plot styling
        line_color = "#00C853" if current >= initial_balance else "#D50000"
        ax.plot(dates, equity, color=line_color, linewidth=2.5, marker='o', markersize=4, label="Silo Equity")
        ax.fill_between(dates, equity, initial_balance, color=line_color, alpha=0.15)
        
        # Reference baseline
        ax.axhline(y=initial_balance, color="#555555", linestyle="--", linewidth=1.2, label="Starting Capital")

        # Labels & Ticks
        ax.set_title(f"Equity Curve - {silo_name}", color="white", fontsize=14, fontweight="bold", pad=20)
        ax.spines['bottom'].set_color('#333333')
        ax.spines['left'].set_color('#333333')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(colors='white', labelsize=9)
        ax.grid(True, color='#2c2c2c', linestyle='--', alpha=0.7)
        ax.legend(facecolor="#1e1e1e", edgecolor="#333333", loc="upper left")

        # Date formatting
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        fig.autofmt_xdate()

        filepath = os.path.join(self.assets_dir, f"{silo_name}_equity.png")
        plt.savefig(filepath, facecolor="#121212", bbox_inches='tight', dpi=120)
        plt.close()
        return filepath
