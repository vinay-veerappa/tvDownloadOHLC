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

                KNOWN_STRATEGIES = [
                    "WHEEL", "ZERO_DTE_PCS", "LONG_DTE_CREDIT", 
                    "MEAN_REVERSION_EM", "WALL_BREAK", "INCOME_CC", "EARNINGS_STRANGLE"
                ]

                strategy_code = None
                for s in KNOWN_STRATEGIES:
                    if name.startswith(s + "_"):
                        strategy_code = s
                        break
                
                if not strategy_code:
                    continue
                
                remainder = name[len(strategy_code)+1:]
                parts = remainder.split("_")
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
                variant_name = "_".join(parts[:-1])
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
        Now upgraded to include cross-strategy rankings, P&L correlation matrix, and
        on-demand feature win-rate breakdown (C3 + C4).
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

        # 3. Fetch all closed trades for cross-strategy analysis
        all_closed_trades = await self.db.trade.find_many(
            where={"status": "CLOSED"},
            include={"snapshots": True}
        )
        
        trades_by_silo = {}
        for account in accounts:
            trades_by_silo[account.name] = [t for t in all_closed_trades if t.accountId == account.id]

        # 4. Build Markdown content
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

        # ─── 2.1 Cross-Strategy Correlation Matrix (C3) ───
        md.append("\n### 2.1 P&L Correlation Matrix (30-Day Outlook)\n")
        md.append("Measures the level of alignment or divergence between different strategy silos based on daily returns. Aim for low/negative correlations to maintain portfolio diversification:\n")
        
        silo_names = [s["name"] for s in silo_rows]
        if len(silo_names) >= 2:
            matrix = self._compute_correlation_matrix(silo_names, trades_by_silo)
            
            header = "| Strategy | " + " | ".join(silo_names) + " |"
            divider = "|:---| " + " | ".join([":---:" for _ in silo_names]) + " |"
            md.append(header)
            md.append(divider)
            
            for s1 in silo_names:
                row_str = f"| **{s1}** | "
                row_vals = []
                for s2 in silo_names:
                    val = matrix[s1][s2]
                    row_vals.append(f"{val:+.2f}")
                row_str += " | ".join(row_vals) + " |"
                md.append(row_str)
        else:
            md.append("*Insufficient active silos to calculate correlation matrix.*")

        # ─── 2.2 Feature Breakdown & Win-Rate Buckets (C4) ───
        md.append("\n### 2.2 Feature Importance & Regime Breakdown\n")
        md.append("Provides a dynamic granular breakdown of strategy performance based on market context and entry signals captured in trade metadata:\n")
        md.append("| Context Feature Bucket | Trades | Wins | Losses | Win Rate | Net P&L |")
        md.append("|:---|:---:|:---:|:---:|:---:|:---|")
        
        buckets = self._generate_feature_breakdown(all_closed_trades)
        for b_name, b_data in buckets.items():
            tot = b_data["total"]
            wins = b_data["wins"]
            losses = tot - wins
            wr = (wins / tot * 100.0) if tot > 0 else 0.0
            pnl_val = b_data["pnl"]
            md.append(f"| {b_name} | {tot} | {wins} | {losses} | {wr:.1f}% | {pnl_val:+,.2f} |")

        md.append("\n## 3. Near-Miss Filter Insights\n")
        md.append("The following filters prevented the most trade entries in the past 7 days. These values highlight how strategies are interacting with current volatility regimes:\n")
        md.append("| Failing Filter | Frequency | Actionable Suggestion |")
        md.append("|:---|:---|:---|")

        filter_suggestions = {
            "iv_rank_below_threshold": "Elevate DTE spreads or widen strikes to boost probability under low IV.",
            "earnings_not_in_range": "Systematic earnings window is quiet; no major announcements scheduled.",
            "blackout_window_active": "Calendar blocks successful; system avoided key macroeconomic volatility.",
            "gex_boundary_blocked": "Spot was too far from optimal GEX Walls to trigger wall break debit spreads.",
            "expected_move_not_reached": "Spot price remained within daily EM bounds. No mean reversion trades triggered.",
            "volume_below_threshold": "Breakout option volume was too low to ensure proper liquidity/slippage containment.",
            "dex_overextended_bullish": "Spot breached the Call Wall but exceeded today's 1SD Upper expected boundary.",
            "dex_overextended_bearish": "Spot breached the Put Wall but exceeded today's 1SD Lower expected boundary."
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

    def _compute_correlation_matrix(self, silo_names, trades_by_silo):
        """
        Computes Pearson correlation matrix based on daily P&L of each silo over the last 30 days.
        """
        import numpy as np
        # Get last 30 days
        now = datetime.now(pytz.utc)
        start_date = now - timedelta(days=30)
        
        # Build date list
        dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(31)]
        
        # Populate daily P&L series for each silo
        silo_pnl_series = {}
        for name in silo_names:
            series = {d: 0.0 for d in dates}
            for t in trades_by_silo.get(name, []):
                exit_date = t.exitDate or t.createdAt
                if exit_date:
                    date_str = exit_date.strftime("%Y-%m-%d")
                    if date_str in series:
                        series[date_str] += float(t.pnl or 0.0)
            silo_pnl_series[name] = [series[d] for d in dates]
            
        # Compute correlations
        matrix = {}
        for s1 in silo_names:
            matrix[s1] = {}
            for s2 in silo_names:
                v1 = silo_pnl_series[s1]
                v2 = silo_pnl_series[s2]
                if s1 == s2:
                    matrix[s1][s2] = 1.0
                elif np.std(v1) == 0 or np.std(v2) == 0:
                    matrix[s1][s2] = 0.0
                else:
                    corr = np.corrcoef(v1, v2)[0, 1]
                    matrix[s1][s2] = float(corr) if not np.isnan(corr) else 0.0
        return matrix

    def _generate_feature_breakdown(self, trades):
        """
        Groups trades by features stored in metadata (like vix, iv_rank, etc.)
        and computes win rate and trade count for each bucket.
        """
        buckets = {
            "VIX Low (<=15)": {"wins": 0, "total": 0, "pnl": 0.0},
            "VIX Moderate (15-20)": {"wins": 0, "total": 0, "pnl": 0.0},
            "VIX High (>20)": {"wins": 0, "total": 0, "pnl": 0.0},
            "IV Rank Low (<=30)": {"wins": 0, "total": 0, "pnl": 0.0},
            "IV Rank High (>30)": {"wins": 0, "total": 0, "pnl": 0.0},
            "Breakout (Bullish)": {"wins": 0, "total": 0, "pnl": 0.0},
            "Breakout (Bearish)": {"wins": 0, "total": 0, "pnl": 0.0},
        }

        for t in trades:
            meta = {}
            if t.metadata:
                if isinstance(t.metadata, str):
                    try:
                        meta = json.loads(t.metadata)
                    except Exception:
                        pass
                elif isinstance(t.metadata, dict):
                    meta = t.metadata
            
            pnl = float(t.pnl or 0.0)
            is_win = pnl > 0
            
            # VIX Buckets
            vix = meta.get("vix")
            if vix is not None:
                try:
                    vix_val = float(vix)
                    if vix_val <= 15:
                        buckets["VIX Low (<=15)"]["total"] += 1
                        buckets["VIX Low (<=15)"]["pnl"] += pnl
                        if is_win:
                            buckets["VIX Low (<=15)"]["wins"] += 1
                    elif vix_val <= 20:
                        buckets["VIX Moderate (15-20)"]["total"] += 1
                        buckets["VIX Moderate (15-20)"]["pnl"] += pnl
                        if is_win:
                            buckets["VIX Moderate (15-20)"]["wins"] += 1
                    else:
                        buckets["VIX High (>20)"]["total"] += 1
                        buckets["VIX High (>20)"]["pnl"] += pnl
                        if is_win:
                            buckets["VIX High (>20)"]["wins"] += 1
                except (ValueError, TypeError):
                    pass
            
            # IV Rank Buckets
            ivr = meta.get("iv_rank")
            if ivr is not None:
                try:
                    ivr_val = float(ivr)
                    if ivr_val <= 30:
                        buckets["IV Rank Low (<=30)"]["total"] += 1
                        buckets["IV Rank Low (<=30)"]["pnl"] += pnl
                        if is_win:
                            buckets["IV Rank Low (<=30)"]["wins"] += 1
                    else:
                        buckets["IV Rank High (>30)"]["total"] += 1
                        buckets["IV Rank High (>30)"]["pnl"] += pnl
                        if is_win:
                            buckets["IV Rank High (>30)"]["wins"] += 1
                except (ValueError, TypeError):
                    pass

            # Breakout Type Buckets
            is_bull = meta.get("is_bullish_breakout")
            is_bear = meta.get("is_bearish_breakout")
            if is_bull:
                buckets["Breakout (Bullish)"]["total"] += 1
                buckets["Breakout (Bullish)"]["pnl"] += pnl
                if is_win:
                    buckets["Breakout (Bullish)"]["wins"] += 1
            if is_bear:
                buckets["Breakout (Bearish)"]["total"] += 1
                buckets["Breakout (Bearish)"]["pnl"] += pnl
                if is_win:
                    buckets["Breakout (Bearish)"]["wins"] += 1

        return buckets

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
        
        dates = []
        equity = []
        current = initial_balance
        
        # Add initial point
        dates.append(sorted_trades[0].entryDate - timedelta(days=1))
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
