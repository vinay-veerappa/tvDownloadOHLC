"""Backtest validation loop — Phase 4 of the KB DESIGN.md roadmap.

Takes :class:`StrategyCandidate` objects from Phase 3 and runs them through
the existing backtest + prop firm simulation infrastructure:

    candidate → STRATEGY_FACTORY_REGISTRY → signals → VectorizedBacktester
              → trades_detailed → PropFirmSimulator → BacktestResult
              → write-back: candidate.status, candidate.epistemic_status,
                unit.metadata.linked_stat_ids

ADR compliance
--------------
- ADR-017: All detection functions are vectorized (candidates only reference
  vectorized functions).
- ADR-020: Candidates carry ``max_exit_time="16:00 ET"``; the backtester respects
  this via the session filter.
- ADR-021: Uses ONLY :class:`PropFirmSimulator` for prop firm viability.
- ADR-001: DataLoader produces ET-tz DataFrames; storage is UTC epoch.
- ADR-002: Performance metrics as price % (pnl_pct), not absolute points.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .strategy_candidates import StrategyCandidate, CandidateStatus


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class ProfileResult:
    """One prop firm profile's backtest result."""

    profile_name: str
    # Deterministic
    passed: bool
    blown: bool
    final_equity_delta: float
    max_drawdown_used: float
    win_rate: float
    profit_factor: float
    total_trades: int
    trading_days: int
    # Monte Carlo
    mc_pass_rate_pct: float
    mc_blow_rate_pct: float
    mc_grade: str
    avg_days_to_pass: Optional[float]
    p50_final_equity: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BacktestResult:
    """Complete backtest result for a single candidate.

    Attributes
    ----------
    candidate_id : str
        The :class:`StrategyCandidate` ID this result belongs to.
    strategy_key : str
        Strategy registry key used for execution.
    ticker : str
        Instrument tested.
    n_signals : int
        Total signals generated.
    n_trades : int
        Trades actually executed by the backtester.
    total_return_pct : float
        Cumulative return as price %.
    sharpe_ratio : float
    max_drawdown_pct : float
    win_rate_pct : float
    avg_mae_pct : float
    profiles : list[ProfileResult]
        Per-prop-firm-profile results.
    passed : bool
        Overall pass: primary profile MC pass_rate >= threshold.
    grade : str
        Primary profile MC grade (A/B/C/D/F).
    run_at : str
        ISO timestamp of this run.
    error : str, optional
        Error message if backtest failed (None on success).
    """

    candidate_id: str
    strategy_key: str
    ticker: str
    n_signals: int = 0
    n_trades: int = 0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    avg_mae_pct: float = 0.0
    profiles: List[ProfileResult] = field(default_factory=list)
    passed: bool = False
    grade: str = "F"
    run_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["profiles"] = [p.to_dict() for p in self.profiles]
        return d


# ── Backtest loop ─────────────────────────────────────────────────────────────

class BacktestLoop:
    """Runs :class:`StrategyCandidate` objects through the full backtest pipeline.

    Parameters
    ----------
    config_path : str
        Path to ``sessions.yaml`` config.
    ticker : str
        Instrument to test (e.g., "NQ1", "ES1").
    profiles : list[str], optional
        Prop firm profile keys to run (default: from config).
    n_simulations : int
        Monte Carlo iterations (default 5000).
    pass_threshold_pct : float
        MC pass rate threshold for overall pass (default 65.0).
    auto_status_update : bool
        If True, update candidate.status/epistemic_status after backtest.
    """

    def __init__(
        self,
        config_path: str = "scripts/trading_framework/config/sessions.yaml",
        ticker: str = "NQ1",
        profiles: Optional[List[str]] = None,
        n_simulations: int = 5000,
        pass_threshold_pct: float = 65.0,
        auto_status_update: bool = True,
    ):
        self.config_path = config_path
        self.ticker = ticker
        self.n_simulations = n_simulations
        self.pass_threshold_pct = pass_threshold_pct
        self.auto_status_update = auto_status_update

        # Lazy-loaded (only when a backtest actually runs)
        self._config = None
        self._df = None
        self._strategy_registry = None
        self._pf_sim = None
        self._profiles = profiles  # override list

    # ── Lazy initialization ──────────────────────────────────────────────────

    def _ensure_loaded(self):
        """Load config, data, and simulator on first use."""
        if self._config is not None:
            return

        # Add project root to sys.path
        root = Path(__file__).resolve().parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from scripts.trading_framework.config.config_loader import load_config
        from scripts.libs_py.data.loader import DataLoader
        from scripts.trading_framework.ml.prop_firm_simulator import (
            PropFirmSimulator,
            FIRM_PROFILES,
        )

        self._config = load_config(self.config_path)
        loader = DataLoader(self._config)
        self._df = loader.load_enriched(self.ticker)

        point_value = (
            self._config.execution.point_value.get(self.ticker, 2.0)
            if hasattr(self._config, "execution")
            else 2.0
        )
        account_size = (
            self._config.account_risk.starting_equity
            if hasattr(self._config, "account_risk")
            else 50_000.0
        )

        self._pf_sim = PropFirmSimulator(
            account_size=account_size,
            point_value=point_value,
        )

        # Resolve profiles
        if self._profiles is None:
            if hasattr(self._config, "prop_firm") and self._config.prop_firm:
                self._profiles = list(self._config.prop_firm.run_profiles)
            else:
                self._profiles = ["apex_50k", "topstep_50k"]

        self._firm_profiles_mod = FIRM_PROFILES

    # ── Single candidate ────────────────────────────────────────────────────

    def run_candidate(
        self,
        candidate: StrategyCandidate,
        params: Optional[Dict[str, Any]] = None,
    ) -> BacktestResult:
        """Run a single candidate through the full backtest pipeline.

        Parameters
        ----------
        candidate : StrategyCandidate
            The candidate to backtest.
        params : dict, optional
            Override strategy parameters (default: candidate metadata).

        Returns
        -------
        BacktestResult
        """
        self._ensure_loaded()

        result = BacktestResult(
            candidate_id=candidate.candidate_id,
            strategy_key=candidate.strategy_key or "",
            ticker=self.ticker,
            run_at=datetime.now(timezone.utc).isoformat(),
        )

        if not candidate.strategy_key:
            result.error = "No strategy_key set on candidate — cannot resolve strategy"
            if self.auto_status_update:
                candidate.status = CandidateStatus.REJECTED
                candidate.epistemic_status = "contradicted"
            return result

        try:
            from scripts.trading_framework.strategies.registry import get_strategy
            from scripts.trading_framework.core.backtest_engine import VectorizedBacktester

            # 1. Get strategy + generate signals
            strategy = get_strategy(candidate.strategy_key, self.ticker)
            signals = strategy.generate_signals(self._df, params or {})

            result.n_signals = len(signals) if hasattr(signals, "__len__") else 0

            if result.n_signals == 0:
                result.error = "Strategy generated 0 signals"
                if self.auto_status_update:
                    candidate.status = CandidateStatus.REJECTED
                    candidate.epistemic_status = "contradicted"
                return result

            # 2. Backtest
            engine = VectorizedBacktester()
            bt_result = engine.run(signals, self._df, {
                "leverage": 1.0,
                "ticker": self.ticker,
                "force_exit_time": "16:00",
            })

            trades_detailed = bt_result.get("trades_detailed")
            result.n_trades = int(bt_result.get("num_trades", 0))
            result.total_return_pct = float(bt_result.get("total_return_%", 0.0))
            result.sharpe_ratio = float(bt_result.get("sharpe_ratio", 0.0))
            result.max_drawdown_pct = float(bt_result.get("max_drawdown_%", 0.0))
            result.win_rate_pct = float(bt_result.get("win_rate_%", 0.0))
            result.avg_mae_pct = float(bt_result.get("avg_mae_%", 0.0))

            if trades_detailed is None or len(trades_detailed) == 0:
                result.error = "Backtester produced 0 trades"
                if self.auto_status_update:
                    candidate.status = CandidateStatus.REJECTED
                return result

            # 3. Prop firm simulation
            from scripts.trading_framework.ml.prop_firm_simulator import FIRM_PROFILES

            primary_passed = False
            primary_grade = "F"

            for profile_key in self._profiles:
                profile = FIRM_PROFILES.get(profile_key)
                if profile is None:
                    continue

                det = self._pf_sim.run_deterministic(trades_detailed, profile)
                mc = self._pf_sim.run_monte_carlo(
                    trades_detailed, profile,
                    n_simulations=self.n_simulations,
                )

                pr = ProfileResult(
                    profile_name=profile.name,
                    passed=det.passed,
                    blown=det.blown,
                    final_equity_delta=det.final_equity_delta,
                    max_drawdown_used=det.max_drawdown_used,
                    win_rate=det.win_rate,
                    profit_factor=det.profit_factor,
                    total_trades=det.total_trades,
                    trading_days=det.trading_days,
                    mc_pass_rate_pct=mc.pass_rate_pct,
                    mc_blow_rate_pct=mc.blow_rate_pct,
                    mc_grade=mc.grade,
                    avg_days_to_pass=mc.avg_days_to_pass,
                    p50_final_equity=mc.p50_final_equity,
                )
                result.profiles.append(pr)

                # Primary profile = first in list
                if profile_key == self._profiles[0]:
                    primary_passed = mc.pass_rate_pct >= self.pass_threshold_pct
                    primary_grade = mc.grade

            result.passed = primary_passed
            result.grade = primary_grade

            # 4. Update candidate status
            if self.auto_status_update:
                if result.passed:
                    candidate.status = CandidateStatus.VALIDATED
                    candidate.epistemic_status = "validated"
                    candidate.backtest_result_id = result.candidate_id
                else:
                    candidate.status = CandidateStatus.REJECTED
                    candidate.epistemic_status = "contradicted"
                    candidate.backtest_result_id = result.candidate_id

        except Exception as exc:
            result.error = str(exc)
            if self.auto_status_update:
                candidate.status = CandidateStatus.REJECTED
                candidate.epistemic_status = "contradicted"

        return result

    # ── Batch ───────────────────────────────────────────────────────────────

    def run_batch(
        self,
        candidates: Sequence[StrategyCandidate],
        params: Optional[Dict[str, Any]] = None,
    ) -> List[BacktestResult]:
        """Run multiple candidates through the backtest pipeline.

        Only candidates with a ``strategy_key`` are backtested. Others are
        skipped with an error result.
        """
        self._ensure_loaded()
        results: List[BacktestResult] = []
        for cand in candidates:
            r = self.run_candidate(cand, params=params)
            results.append(r)
        return results


# ── JSON export ──────────────────────────────────────────────────────────────

def export_backtest_results(
    results: Sequence[BacktestResult],
    output_path: str | Path,
    indent: int = 2,
) -> Path:
    """Export backtest results to JSON.

    Parameters
    ----------
    results : list[BacktestResult]
    output_path : str | Path
    indent : int

    Returns
    -------
    Path
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": "0.1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "result_count": len(results),
        "results": [r.to_dict() for r in results],
    }
    path.write_text(json.dumps(data, indent=indent, default=str), encoding="utf-8")
    return path


def load_backtest_results(input_path: str | Path) -> List[BacktestResult]:
    """Load backtest results from JSON.

    Parameters
    ----------
    input_path : str | Path

    Returns
    -------
    list[BacktestResult]
    """
    path = Path(input_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    results_data = data.get("results", data if isinstance(data, list) else [])
    out: List[BacktestResult] = []
    for r_data in results_data:
        profiles_data = r_data.pop("profiles", [])
        profiles = [ProfileResult(**p) for p in profiles_data]
        out.append(BacktestResult(profiles=profiles, **r_data))
    return out


# ── Write-back to candidates ────────────────────────────────────────────────

def apply_backtest_results(
    candidates: Sequence[StrategyCandidate],
    results: Sequence[BacktestResult],
) -> Dict[str, CandidateStatus]:
    """Apply backtest results to candidates (status + epistemic_status).

    Returns mapping ``{candidate_id: new_status}``.
    """
    result_map: Dict[str, BacktestResult] = {r.candidate_id: r for r in results}
    updates: Dict[str, CandidateStatus] = {}
    for cand in candidates:
        r = result_map.get(cand.candidate_id)
        if r is None:
            continue
        if r.error:
            cand.status = CandidateStatus.REJECTED
            cand.epistemic_status = "contradicted"
        elif r.passed:
            cand.status = CandidateStatus.VALIDATED
            cand.epistemic_status = "validated"
        else:
            cand.status = CandidateStatus.REJECTED
            cand.epistemic_status = "contradicted"
        cand.backtest_result_id = r.candidate_id
        updates[cand.candidate_id] = cand.status
    return updates


# ── Summary ──────────────────────────────────────────────────────────────────

def summarize_results(results: Sequence[BacktestResult]) -> Dict[str, Any]:
    """Compute summary statistics for a set of backtest results."""
    if not results:
        return {"total": 0}
    passed = sum(1 for r in results if r.passed)
    errors = sum(1 for r in results if r.error)
    grades: Dict[str, int] = {}
    for r in results:
        grades[r.grade] = grades.get(r.grade, 0) + 1
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed - errors,
        "errors": errors,
        "pass_rate_pct": round(passed / len(results) * 100, 1) if results else 0,
        "grades": grades,
        "avg_signals": round(sum(r.n_signals for r in results) / len(results), 1),
        "avg_trades": round(sum(r.n_trades for r in results) / len(results), 1),
        "avg_sharpe": round(sum(r.sharpe_ratio for r in results) / len(results), 3),
    }


# ── Convenience function ─────────────────────────────────────────────────────

def run_candidate_backtest(
    candidate: StrategyCandidate,
    ticker: str = "NQ1",
    config_path: str = "scripts/trading_framework/config/sessions.yaml",
    profiles: Optional[List[str]] = None,
    n_simulations: int = 5000,
    pass_threshold_pct: float = 65.0,
    params: Optional[Dict[str, Any]] = None,
) -> BacktestResult:
    """One-shot backtest for a single candidate.

    Parameters
    ----------
    candidate : StrategyCandidate
    ticker : str
    config_path : str
    profiles : list[str], optional
    n_simulations : int
    pass_threshold_pct : float
    params : dict, optional

    Returns
    -------
    BacktestResult
    """
    loop = BacktestLoop(
        config_path=config_path,
        ticker=ticker,
        profiles=profiles,
        n_simulations=n_simulations,
        pass_threshold_pct=pass_threshold_pct,
    )
    return loop.run_candidate(candidate, params=params)