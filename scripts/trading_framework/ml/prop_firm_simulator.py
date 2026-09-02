"""
Prop Firm Simulator — Unified Implementation
==============================================
ADR-021: Unified Prop Firm Simulation Standard

This module is the single canonical source for prop firm evaluation
simulation across the entire trading framework. It consolidates logic
previously scattered across:
  - scripts/trading_framework/ml/prop_eval_mc.py      (deprecated)
  - scripts/orb_generic/strategy_validation/scripts/06_prop_sim.py
  - scripts/strategies/nine_thirty_breakout/utils/simulate_prop_pass.py

Architecture:
  1. PropFirmProfile   — immutable dataclass capturing one firm's rules
  2. FIRM_PROFILES     — dict of canonical presets (Apex, TopStep, FTMO)
  3. PropFirmSimulator — deterministic + Monte Carlo simulation engine
  4. PropSimReport     — structured results (passed to tearsheet / ADR-010)

Input Contract (ADR-020 compliance):
  Accepts the `trades_detailed` DataFrame emitted by VectorizedBacktester.run()
  which carries per-trade rows with at minimum: exit_time, pnl_pct columns.
  Dollar P&L is derived using account_size * pnl_pct / 100.

All exits are assumed to already comply with ADR-020 (16:00 ET hard exit).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. PropFirmProfile — Rule Specification
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PropFirmProfile:
    """
    Immutable specification of one prop firm's evaluation rules.

    All dollar amounts are in USD per 1 Micro contract equivalent
    (ADR-009: Micro-first sizing standard).

    Attributes
    ----------
    name : str
        Human-readable firm name (e.g. "Apex 50K").
    account_size : float
        Starting account / notional balance (USD).
    profit_target : float
        Gross profit required to pass evaluation (USD).
    max_trailing_drawdown : float
        Maximum trailing drawdown from equity peak (USD).
        Set `trailing` = False to treat as static (from-start) DD instead.
    trailing : bool
        If True, drawdown tracks from the running equity peak.
        If False, drawdown is measured from starting_equity (static DD).
    daily_loss_limit : float
        Maximum loss allowed in a single calendar day (USD).
        Trading is suspended for the rest of that day if breached.
    max_trades_per_day : int
        Hard cap on number of trades accepted per calendar day.
        Signals beyond this cap are discarded.
    consistency_rule_pct : float
        Maximum fraction (0–1) that any single day's profit may represent
        of the total account profit. Common rule: 0.30 (30%).
        Set to 1.0 to disable.
    eval_max_days : int
        Maximum calendar days allowed to reach profit_target.
        Evaluation fails if target is not reached within this window.
    """
    name: str
    account_size: float
    profit_target: float
    max_trailing_drawdown: float
    trailing: bool = True
    daily_loss_limit: float = 0.0       # 0 = disabled
    max_trades_per_day: int = 999        # 999 = disabled
    consistency_rule_pct: float = 1.0   # 1.0 = disabled
    eval_max_days: int = 60


# ─────────────────────────────────────────────────────────────────────────────
# 2. FIRM_PROFILES — Canonical Presets
# ─────────────────────────────────────────────────────────────────────────────

FIRM_PROFILES: Dict[str, PropFirmProfile] = {
    # ── Apex Trader Funding ───────────────────────────────────────────────────
    # Apex 50K: $3,000 profit target / $2,500 trailing DD / 30-day window
    "apex_50k": PropFirmProfile(
        name="Apex 50K",
        account_size=50_000.0,
        profit_target=3_000.0,
        max_trailing_drawdown=2_500.0,
        trailing=True,
        daily_loss_limit=0.0,           # Apex has no daily loss limit
        max_trades_per_day=999,
        consistency_rule_pct=1.0,       # No consistency rule on Apex eval
        eval_max_days=30,
    ),
    # Apex 100K: $6,000 profit target / $3,000 trailing DD
    "apex_100k": PropFirmProfile(
        name="Apex 100K",
        account_size=100_000.0,
        profit_target=6_000.0,
        max_trailing_drawdown=3_000.0,
        trailing=True,
        daily_loss_limit=0.0,
        max_trades_per_day=999,
        consistency_rule_pct=1.0,
        eval_max_days=30,
    ),
    # ── TopStep Trader ────────────────────────────────────────────────────────
    # TopStep 50K: $3,000 profit target / $2,000 trailing DD / $1,000 daily loss
    "topstep_50k": PropFirmProfile(
        name="TopStep 50K",
        account_size=50_000.0,
        profit_target=3_000.0,
        max_trailing_drawdown=2_000.0,
        trailing=True,
        daily_loss_limit=1_000.0,
        max_trades_per_day=999,
        consistency_rule_pct=1.0,
        eval_max_days=60,
    ),
    # TopStep 100K: $6,000 profit target / $3,000 trailing DD / $2,000 daily loss
    "topstep_100k": PropFirmProfile(
        name="TopStep 100K",
        account_size=100_000.0,
        profit_target=6_000.0,
        max_trailing_drawdown=3_000.0,
        trailing=True,
        daily_loss_limit=2_000.0,
        max_trades_per_day=999,
        consistency_rule_pct=1.0,
        eval_max_days=60,
    ),
    # ── FTMO ──────────────────────────────────────────────────────────────────
    # FTMO 50K: $5,000 profit target / $5,000 max loss (static) / $2,500 daily
    # + 30% single-day consistency rule
    "ftmo_50k": PropFirmProfile(
        name="FTMO 50K",
        account_size=50_000.0,
        profit_target=5_000.0,
        max_trailing_drawdown=5_000.0,
        trailing=False,                 # FTMO uses static (from-start) max loss
        daily_loss_limit=2_500.0,
        max_trades_per_day=999,
        consistency_rule_pct=0.30,      # No single day > 30% of total profit
        eval_max_days=30,
    ),
    # ── Take Profit Trader (TPT) ──────────────────────────────────────────────
    # TPT 50K: $3,000 profit target / $2,000 EOD trailing DD / $1,100 daily loss / 50% consistency
    "takeprofittrader_50k": PropFirmProfile(
        name="Take Profit Trader 50K",
        account_size=50_000.0,
        profit_target=3_000.0,
        max_trailing_drawdown=2_000.0,
        trailing=True,
        daily_loss_limit=1_100.0,
        max_trades_per_day=999,
        consistency_rule_pct=0.50,      # Max 50% single day profit
        eval_max_days=60,
    ),
    # ── Tradeify ──────────────────────────────────────────────────────────────
    # Tradeify 50K (Growth/Advanced): $3,000 target / $2,000 EOD trailing / $1,100 daily loss / 35% consistency
    "tradeify_50k": PropFirmProfile(
        name="Tradeify 50K",
        account_size=50_000.0,
        profit_target=3_000.0,
        max_trailing_drawdown=2_000.0,
        trailing=True,
        daily_loss_limit=1_100.0,
        max_trades_per_day=999,
        consistency_rule_pct=0.35,      # Max 35% single day profit
        eval_max_days=60,
    ),
    # ── Lucid Traders ─────────────────────────────────────────────────────────
    # Lucid 50K: $3,000 profit target / $2,000 EOD trailing / $1,000 daily loss / 35% consistency
    "lucid_50k": PropFirmProfile(
        name="Lucid 50K",
        account_size=50_000.0,
        profit_target=3_000.0,
        max_trailing_drawdown=2_000.0,
        trailing=True,
        daily_loss_limit=1_000.0,
        max_trades_per_day=999,
        consistency_rule_pct=0.35,      # Max 35% single day profit
        eval_max_days=60,
    ),
    # ── Minimal (internal testing) ────────────────────────────────────────────
    "generic_50k": PropFirmProfile(
        name="Generic 50K (no constraints)",
        account_size=50_000.0,
        profit_target=3_000.0,
        max_trailing_drawdown=2_000.0,
        trailing=True,
        daily_loss_limit=0.0,
        max_trades_per_day=999,
        consistency_rule_pct=1.0,
        eval_max_days=60,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# 3. PropSimReport — Structured Results
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DeterministicResult:
    """Outcome of a single deterministic pass through the trade history."""
    profile_name: str
    blown: bool
    passed: bool
    final_equity_delta: float       # USD gain/loss from account_size
    max_drawdown_used: float        # Worst drawdown seen (USD)
    trading_days: int
    total_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    avg_daily_pnl: float
    max_daily_pnl: float
    min_daily_pnl: float
    longest_losing_streak: int
    longest_winning_streak: int
    consistency_violation: bool     # True if any day exceeded consistency_rule_pct
    daily_loss_violations: int      # Days where daily_loss_limit was hit
    trades_skipped_daily_cap: int   # Trades discarded due to max_trades_per_day


@dataclass
class MonteCarloResult:
    """Monte Carlo permutation simulation results."""
    profile_name: str
    n_simulations: int
    pass_rate_pct: float
    blow_rate_pct: float
    timeout_rate_pct: float
    avg_days_to_pass: Optional[float]
    median_days_to_pass: Optional[float]
    p10_final_equity: float
    p50_final_equity: float
    p90_final_equity: float
    avg_max_drawdown: float
    # Composite pass / fail grade (ADR-010)
    grade: str = field(init=False)

    def __post_init__(self):
        self.grade = self._compute_grade()

    def _compute_grade(self) -> str:
        if self.pass_rate_pct >= 80:
            return "A"
        if self.pass_rate_pct >= 65:
            return "B"
        if self.pass_rate_pct >= 50:
            return "C"
        if self.pass_rate_pct >= 30:
            return "D"
        return "F"


# ─────────────────────────────────────────────────────────────────────────────
# 4. PropFirmSimulator — Main Engine
# ─────────────────────────────────────────────────────────────────────────────

class PropFirmSimulator:
    """
    Unified Prop Firm Viability Simulator (ADR-021).

    Usage
    -----
    >>> sim = PropFirmSimulator(account_size=50_000.0, point_value=2.0)
    >>> det = sim.run_deterministic(trades_detailed, profile=FIRM_PROFILES["apex_50k"])
    >>> mc  = sim.run_monte_carlo(trades_detailed, profile=FIRM_PROFILES["apex_50k"])
    >>> print(sim.format_report(det, mc))

    Parameters
    ----------
    account_size : float
        Account size in USD (overridden per-profile in simulation).
    point_value : float
        Dollar value per point for the instrument (ADR-009).
        MNQ = 2.0, MES = 5.0, NQ = 20.0, ES = 50.0.
    """

    def __init__(self, account_size: float = 50_000.0, point_value: float = 2.0):
        self.account_size = account_size
        self.point_value = point_value

    # ── Public API ────────────────────────────────────────────────────────────

    def run_all_profiles(
        self,
        trades_detailed: pd.DataFrame,
        n_simulations: int = 5_000,
        profiles: Optional[List[str]] = None,
    ) -> Dict[str, Tuple[DeterministicResult, MonteCarloResult]]:
        """
        Run deterministic + Monte Carlo for every (or selected) firm profile.

        Returns a dict keyed by profile key → (DeterministicResult, MonteCarloResult).
        """
        keys = profiles or list(FIRM_PROFILES.keys())
        results: Dict[str, Tuple[DeterministicResult, MonteCarloResult]] = {}
        for key in keys:
            profile = FIRM_PROFILES[key]
            det = self.run_deterministic(trades_detailed, profile)
            mc = self.run_monte_carlo(trades_detailed, profile, n_simulations)
            results[key] = (det, mc)
            logger.info(
                "[PropFirmSim] %s → Pass Rate: %.1f%% (Grade: %s) | Blown: %.1f%%",
                profile.name, mc.pass_rate_pct, mc.grade, mc.blow_rate_pct,
            )
        return results

    def run_deterministic(
        self,
        trades_detailed: pd.DataFrame,
        profile: PropFirmProfile,
    ) -> DeterministicResult:
        """
        Walk through the actual historical trade sequence applying all
        prop firm rule constraints. Returns a DeterministicResult.
        """
        dollar_pnls = self._to_dollar_pnl(trades_detailed, profile.account_size)
        if dollar_pnls.empty:
            return self._null_deterministic(profile.name)

        daily = self._aggregate_daily(trades_detailed, dollar_pnls, profile)
        return self._simulate_path(daily, profile)

    def run_monte_carlo(
        self,
        trades_detailed: pd.DataFrame,
        profile: PropFirmProfile,
        n_simulations: int = 5_000,
    ) -> MonteCarloResult:
        """
        Permutation-based Monte Carlo: shuffles the per-trade P&L sequence
        N times, re-aggregating to daily and re-running the prop firm logic
        each time. Returns pass rate, blow rate, and distribution stats.
        """
        dollar_pnls = self._to_dollar_pnl(trades_detailed, profile.account_size)
        if dollar_pnls.empty or len(dollar_pnls) < 2:
            return self._null_mc(profile.name, n_simulations)

        # Build trade-level dollar P&L array for resampling
        pnl_arr = dollar_pnls.values
        # Map exit dates for daily grouping
        exit_dates = self._extract_exit_dates(trades_detailed)

        passes = 0
        blowups = 0
        timeouts = 0
        days_to_pass_list: List[float] = []
        max_dd_list: List[float] = []
        final_equity_list: List[float] = []

        for _ in range(n_simulations):
            perm = np.random.permutation(pnl_arr)
            result = self._simulate_permuted_path(
                perm, exit_dates, profile
            )
            if result["passed"]:
                passes += 1
                if result["days_to_pass"] is not None:
                    days_to_pass_list.append(result["days_to_pass"])
            elif result["blown"]:
                blowups += 1
            else:
                timeouts += 1
            max_dd_list.append(result["max_drawdown"])
            final_equity_list.append(result["final_equity_delta"])

        eq_arr = np.array(final_equity_list)
        return MonteCarloResult(
            profile_name=profile.name,
            n_simulations=n_simulations,
            pass_rate_pct=passes / n_simulations * 100,
            blow_rate_pct=blowups / n_simulations * 100,
            timeout_rate_pct=timeouts / n_simulations * 100,
            avg_days_to_pass=float(np.mean(days_to_pass_list)) if days_to_pass_list else None,
            median_days_to_pass=float(np.median(days_to_pass_list)) if days_to_pass_list else None,
            p10_final_equity=float(np.percentile(eq_arr, 10)),
            p50_final_equity=float(np.percentile(eq_arr, 50)),
            p90_final_equity=float(np.percentile(eq_arr, 90)),
            avg_max_drawdown=float(np.mean(max_dd_list)),
        )

    # ── Formatting ────────────────────────────────────────────────────────────

    def format_report(
        self,
        det: DeterministicResult,
        mc: MonteCarloResult,
    ) -> str:
        """Render a markdown report block for the tearsheet."""
        status_emoji = "✅" if mc.pass_rate_pct >= 65 else "⚠️" if mc.pass_rate_pct >= 40 else "❌"
        blown_str = "🚨 YES" if det.blown else "No"
        consist_str = "🚨 VIOLATED" if det.consistency_violation else "OK"

        return f"""
### Prop Firm Simulation — {det.profile_name} {status_emoji}

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | {"✅ PASSED" if det.passed else "💀 BLOWN" if det.blown else "⏱ TIMED OUT"} |
| **Account Blown** | {blown_str} |
| **Final P&L** | ${det.final_equity_delta:+,.2f} |
| **Max DD Used** | ${det.max_drawdown_used:,.2f} |
| **Trading Days** | {det.trading_days} |
| **Total Trades** | {det.total_trades} |
| **Win Rate** | {det.win_rate:.1f}% |
| **Avg Win / Loss** | ${det.avg_win:.2f} / ${det.avg_loss:.2f} |
| **Profit Factor** | {det.profit_factor:.2f} |
| **Avg Daily P&L** | ${det.avg_daily_pnl:+,.2f} |
| **Best / Worst Day** | ${det.max_daily_pnl:+,.2f} / ${det.min_daily_pnl:+,.2f} |
| **Longest Loss Streak** | {det.longest_losing_streak} trades |
| **Consistency Rule** | {consist_str} |
| **Daily Loss Violations** | {det.daily_loss_violations} days |
| **Trades Skipped (Daily Cap)** | {det.trades_skipped_daily_cap} |

#### Monte Carlo ({mc.n_simulations:,} Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **{mc.pass_rate_pct:.1f}%** (Grade: **{mc.grade}**) |
| **Blow-Up Rate** | {mc.blow_rate_pct:.1f}% |
| **Timeout Rate** | {mc.timeout_rate_pct:.1f}% |
| **Avg Days to Pass** | {f"{mc.avg_days_to_pass:.1f}" if mc.avg_days_to_pass else "N/A"} |
| **Median Days to Pass** | {f"{mc.median_days_to_pass:.1f}" if mc.median_days_to_pass else "N/A"} |
| **P10 / P50 / P90 Equity** | ${mc.p10_final_equity:+,.2f} / ${mc.p50_final_equity:+,.2f} / ${mc.p90_final_equity:+,.2f} |
| **Avg Max Drawdown** | ${mc.avg_max_drawdown:,.2f} |
"""

    def format_multi_report(
        self,
        all_results: Dict[str, Tuple[DeterministicResult, MonteCarloResult]],
    ) -> str:
        """Render a combined summary table across all firm profiles."""
        rows = []
        for key, (det, mc) in all_results.items():
            grade_badge = {"A": "[A]", "B": "[B]", "C": "[C]", "D": "[D]", "F": "[F]"}.get(mc.grade, mc.grade)
            rows.append(
                f"| {det.profile_name} | {mc.pass_rate_pct:.1f}% | {grade_badge} | "
                f"{mc.blow_rate_pct:.1f}% | ${det.max_drawdown_used:,.0f} | "
                f"{'YES' if det.blown else 'No'} | "
                f"{f'{mc.avg_days_to_pass:.0f}d' if mc.avg_days_to_pass else 'N/A'} |"
            )

        header = (
            "### Prop Firm Viability Summary\n\n"
            "| Firm | MC Pass Rate | Grade | Blow Rate | Max DD Used | Hist Blown | Avg Days |\n"
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n"
        )
        return header + "\n".join(rows)

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _to_dollar_pnl(self, trades: pd.DataFrame, account_size: float) -> pd.Series:
        """
        Convert `pnl_pct` column (% of entry price) to dollar P&L.
        Uses account_size as the denominator base consistent with ADR-002.
        """
        if trades is None or trades.empty or "pnl_pct" not in trades.columns:
            return pd.Series(dtype=float)
        pnl_pct = pd.to_numeric(trades["pnl_pct"], errors="coerce").fillna(0.0)
        return pnl_pct / 100.0 * account_size

    def _extract_exit_dates(self, trades: pd.DataFrame) -> pd.Series:
        """Return a Series of date strings aligned to the trades index."""
        if "exit_time" in trades.columns:
            return pd.to_datetime(trades["exit_time"], errors="coerce").dt.normalize()
        return pd.Series(pd.NaT, index=trades.index)

    def _aggregate_daily(
        self,
        trades: pd.DataFrame,
        dollar_pnls: pd.Series,
        profile: PropFirmProfile,
    ) -> pd.DataFrame:
        """
        Aggregate per-trade dollar P&L to daily summaries, applying
        daily trade cap and daily loss limit rules.
        Returns a DataFrame with columns: [date, pnl, n_trades, skipped, dd_violation].
        """
        exit_dates = self._extract_exit_dates(trades)

        records = []
        trades_today = 0
        daily_pnl = 0.0
        current_date = None
        skipped_today = 0
        dd_violation = False

        for idx in range(len(dollar_pnls)):
            date = exit_dates.iloc[idx]
            pnl = dollar_pnls.iloc[idx]

            if date != current_date:
                if current_date is not None:
                    records.append({
                        "date": current_date,
                        "pnl": daily_pnl,
                        "n_trades": trades_today,
                        "skipped": skipped_today,
                        "dd_violation": dd_violation,
                    })
                current_date = date
                daily_pnl = 0.0
                trades_today = 0
                skipped_today = 0
                dd_violation = False

            # Apply daily trade cap
            if trades_today >= profile.max_trades_per_day:
                skipped_today += 1
                continue

            # Apply daily loss limit (suspend rest of day if already hit)
            if profile.daily_loss_limit > 0 and daily_pnl <= -profile.daily_loss_limit:
                dd_violation = True
                skipped_today += 1
                continue

            daily_pnl += pnl
            trades_today += 1

        if current_date is not None:
            records.append({
                "date": current_date,
                "pnl": daily_pnl,
                "n_trades": trades_today,
                "skipped": skipped_today,
                "dd_violation": dd_violation,
            })

        return pd.DataFrame(records)

    def _simulate_path(
        self, daily: pd.DataFrame, profile: PropFirmProfile
    ) -> DeterministicResult:
        """Walk the daily P&L sequence through the prop firm rulebook."""
        if daily.empty:
            return self._null_deterministic(profile.name)

        equity = 0.0
        peak_equity = 0.0
        max_dd_used = 0.0
        blown = False
        passed = False
        consistency_violation = False
        total_equity_profit = 0.0   # running total profit (for consistency rule)

        for _, row in daily.iterrows():
            day_pnl = row["pnl"]

            # Trailing vs static drawdown
            if profile.trailing:
                dd = peak_equity - equity
            else:
                dd = max(0.0, -equity)

            if dd >= profile.max_trailing_drawdown:
                blown = True
                break

            equity += day_pnl
            peak_equity = max(peak_equity, equity)

            current_dd = (peak_equity - equity) if profile.trailing else max(0.0, -equity)
            max_dd_used = max(max_dd_used, current_dd)

            # Consistency rule check (only on profitable days, after equity is positive)
            if profile.consistency_rule_pct < 1.0 and equity > 0 and day_pnl > 0:
                if day_pnl / equity > profile.consistency_rule_pct:
                    consistency_violation = True

            # Check profit target
            if equity >= profile.profit_target:
                passed = True
                break

        # Aggregate stats from the accepted daily series
        pnls = daily["pnl"].values
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        n_trades = int(daily["n_trades"].sum())
        skipped = int(daily["skipped"].sum())
        dd_violations = int(daily["dd_violation"].sum())

        pf = (wins.sum() / abs(losses.sum())) if len(losses) > 0 and losses.sum() != 0 else float("inf")

        return DeterministicResult(
            profile_name=profile.name,
            blown=blown,
            passed=passed,
            final_equity_delta=equity,
            max_drawdown_used=max_dd_used,
            trading_days=len(daily),
            total_trades=n_trades,
            win_rate=float(np.mean(pnls > 0)) * 100 if len(pnls) > 0 else 0.0,
            avg_win=float(wins.mean()) if len(wins) > 0 else 0.0,
            avg_loss=float(abs(losses.mean())) if len(losses) > 0 else 0.0,
            profit_factor=pf,
            avg_daily_pnl=float(pnls.mean()) if len(pnls) > 0 else 0.0,
            max_daily_pnl=float(pnls.max()) if len(pnls) > 0 else 0.0,
            min_daily_pnl=float(pnls.min()) if len(pnls) > 0 else 0.0,
            longest_losing_streak=_max_consecutive(pnls, negative=True),
            longest_winning_streak=_max_consecutive(pnls, negative=False),
            consistency_violation=consistency_violation,
            daily_loss_violations=dd_violations,
            trades_skipped_daily_cap=skipped,
        )

    def _simulate_permuted_path(
        self,
        permuted_pnl: np.ndarray,
        exit_dates: pd.Series,
        profile: PropFirmProfile,
    ) -> dict:
        """
        Simulate one Monte Carlo path using a permuted trade P&L sequence.
        Re-aggregates trades to days using the original date structure,
        then applies prop firm constraints.
        """
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        blown = False
        passed = False
        days_to_pass = None

        # Group trades by day using original date sequence
        # (day-count structure preserved, only order within day shuffled)
        if not exit_dates.empty and exit_dates.notna().any():
            unique_dates = exit_dates.dropna().unique()
            # Assign permuted P&Ls to days proportionally
            trades_per_day = len(permuted_pnl) / max(len(unique_dates), 1)
            day_idx = 0
            pos = 0
            for d in unique_dates:
                day_count = max(1, round(trades_per_day))
                day_pnl = float(np.sum(permuted_pnl[pos:pos + day_count]))
                pos = min(pos + day_count, len(permuted_pnl))

                # Drawdown check BEFORE adding today's P&L
                dd = (peak - equity) if profile.trailing else max(0.0, -equity)
                if dd >= profile.max_trailing_drawdown:
                    blown = True
                    break

                equity += day_pnl
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) if profile.trailing else max(0.0, -equity))
                day_idx += 1

                if equity >= profile.profit_target:
                    passed = True
                    days_to_pass = day_idx
                    break

                if day_idx >= profile.eval_max_days:
                    break
        else:
            # Fallback: treat each trade as one "day"
            for i, pnl in enumerate(permuted_pnl):
                dd = (peak - equity) if profile.trailing else max(0.0, -equity)
                if dd >= profile.max_trailing_drawdown:
                    blown = True
                    break
                equity += pnl
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) if profile.trailing else max(0.0, -equity))
                if equity >= profile.profit_target:
                    passed = True
                    days_to_pass = i + 1
                    break

        return {
            "passed": passed and not blown,
            "blown": blown,
            "days_to_pass": days_to_pass,
            "max_drawdown": max_dd,
            "final_equity_delta": equity,
        }

    def _null_deterministic(self, profile_name: str) -> DeterministicResult:
        return DeterministicResult(
            profile_name=profile_name,
            blown=False, passed=False, final_equity_delta=0.0,
            max_drawdown_used=0.0, trading_days=0, total_trades=0,
            win_rate=0.0, avg_win=0.0, avg_loss=0.0, profit_factor=0.0,
            avg_daily_pnl=0.0, max_daily_pnl=0.0, min_daily_pnl=0.0,
            longest_losing_streak=0, longest_winning_streak=0,
            consistency_violation=False, daily_loss_violations=0,
            trades_skipped_daily_cap=0,
        )

    def _null_mc(self, profile_name: str, n_sims: int) -> MonteCarloResult:
        return MonteCarloResult(
            profile_name=profile_name,
            n_simulations=n_sims, pass_rate_pct=0.0, blow_rate_pct=0.0,
            timeout_rate_pct=100.0, avg_days_to_pass=None,
            median_days_to_pass=None, p10_final_equity=0.0,
            p50_final_equity=0.0, p90_final_equity=0.0, avg_max_drawdown=0.0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────────────────

def _max_consecutive(arr: np.ndarray, negative: bool = True) -> int:
    """Count the longest run of negative (or positive) values."""
    mask = (arr < 0) if negative else (arr > 0)
    max_streak = current = 0
    for m in mask:
        if m:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak
