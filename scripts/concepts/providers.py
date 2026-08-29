"""Standard Concept Provider Implementations

Wraps all specialized engines into the unified BaseConceptProvider interface.
Enforces strict production vs. scaffold segregation and real live data feeds.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Optional, List
import pandas as pd
import pytz

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.concepts.base import (
    BaseConceptProvider,
    ConceptPayload,
    ChartOverlays,
    STATUS_PRODUCTION,
    STATUS_SCAFFOLD,
)
from scripts.concepts.registry import ConceptRegistry
from scripts.utils.fused_data_loader import load_fused_data

from scripts.candle_science.run_candle_science import analyze_candle_science, format_candle_science_markdown
from scripts.wargaming.htf_macro_levels import compute_htf_macro_levels, format_htf_macro_markdown
from scripts.wargaming.weekly_outlook_engine import compute_weekly_outlook, format_weekly_outlook_markdown
from scripts.wargaming.p12_scenario_engine import compute_p12_scenarios, format_p12_scenarios_markdown
from scripts.wargaming.session_budget_engine import compute_session_budget, format_session_budget_markdown
from scripts.wargaming.signature_setup_scanner import scan_signature_setups, format_signature_setups_markdown

ET = pytz.timezone("America/New_York")


# 1. CANDLE SCIENCE PROVIDER (PRODUCTION)
class CandleScienceProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "candle_science"

    @property
    def description(self) -> str:
        return "3-Candle sequence patterns and empirical MFE/MAE percentiles (P30, P50, P70)."

    @property
    def status(self) -> str:
        return STATUS_PRODUCTION

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = analyze_candle_science(ticker=ticker, target_date=target_date, mode="open")
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["target_date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md,
            status=self.status,
            is_success=True,
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_candle_science_markdown(data)


# 2. HTF MACRO PROVIDER (PRODUCTION)
class HTFMacroProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "htf_macro"

    @property
    def description(self) -> str:
        return "Prior Monthly Midpoint, NFP Benchmark Midpoint, and Weekly EMA(5) 52-week excursions."

    @property
    def status(self) -> str:
        return STATUS_PRODUCTION

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = compute_htf_macro_levels(ticker=ticker, target_date=target_date)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["target_date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md,
            status=self.status,
            is_success=True,
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_htf_macro_markdown(data)


# 3. WEEKLY OUTLOOK PROVIDER (PRODUCTION)
class WeeklyOutlookProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "weekly_outlook"

    @property
    def description(self) -> str:
        return "Day-of-Week Macro Cycles (Mon/Tue vs Thu/Fri), Weekly Candle state, and 0DTE->Next Friday Expected Moves."

    @property
    def status(self) -> str:
        return STATUS_PRODUCTION

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = compute_weekly_outlook(ticker=ticker, target_date=target_date)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["eval_date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md,
            status=self.status,
            is_success=True,
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_weekly_outlook_markdown(data)


# 4. P12 SCENARIOS PROVIDER (PRODUCTION)
class P12ScenariosProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "p12_scenarios"

    @property
    def description(self) -> str:
        return "P12 Directional Vectors, 88.5% Midline Gravity Wells, 99.26% Goalposts, and Handshake Vectors."

    @property
    def status(self) -> str:
        return STATUS_PRODUCTION

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = compute_p12_scenarios(ticker=ticker, target_date=target_date, cutoff_time=cutoff_time)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md,
            status=self.status,
            is_success=True,
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_p12_scenarios_markdown(data)


# 5. SESSION BUDGET PROVIDER (PRODUCTION)
class SessionBudgetProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "session_budget"

    @property
    def description(self) -> str:
        return "Overnight Volatility Checkbook Spending % against 10-Day Median Range (DRO Baseline)."

    @property
    def status(self) -> str:
        return STATUS_PRODUCTION

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = compute_session_budget(ticker=ticker, target_date=target_date, cutoff_time=cutoff_time)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["date"],
            spot_price=0.0,
            data=data,
            markdown_report=md,
            status=self.status,
            is_success=True,
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_session_budget_markdown(data)


# 6. SIGNATURE SETUPS SCANNER PROVIDER (PRODUCTION)
class SignatureSetupsProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "signature_setups"

    @property
    def description(self) -> str:
        return "Automated detection of Firecracker, Spongebob, and Broken-Broken Goalpost trade setups."

    @property
    def status(self) -> str:
        return STATUS_PRODUCTION

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = scan_signature_setups(ticker=ticker, target_date=target_date, cutoff_time=cutoff_time)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md,
            status=self.status,
            is_success=True,
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_signature_setups_markdown(data)


# 7. NQSTATS ALN SESSION DYNAMICS PROVIDER (PRODUCTION - LIVE DATA FEEDED)
class ALNSessionsProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "aln_sessions"

    @property
    def description(self) -> str:
        return "NQStats ALN Sessions: Asia-London-NY structural relationships (LPEU, LPED, LEA, AEL) and break probabilities."

    @property
    def status(self) -> str:
        return STATUS_PRODUCTION

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        from scripts.libs_py.nqstats.classifiers import compute_aln_bias, ALN_PATTERN_META
        from scripts.libs_py.profiler.engine import SessionBoxEngine

        df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_1m.index.tz is None:
            df_1m.index = df_1m.index.tz_localize("US/Eastern")
        else:
            df_1m.index = df_1m.index.tz_convert("US/Eastern")

        t_dt = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else datetime.now(ET).date()
        c_h, c_m = map(int, cutoff_time.split(":"))
        cutoff_dt = pd.Timestamp(datetime.combine(t_dt, time(c_h, c_m)), tz="America/New_York")
        df_cutoff = df_1m[df_1m.index <= cutoff_dt]

        if df_cutoff.empty:
            raise ValueError(f"No market data available for {ticker} up to {cutoff_dt}")

        spot = float(df_cutoff["close"].iloc[-1])

        # 1. Exact Time Slices (ADR-004 Institutional Windows)
        asia_start = pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(18, 0)), tz="America/New_York")
        asia_end = pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(19, 30)), tz="America/New_York")
        lon_start = pd.Timestamp(datetime.combine(t_dt, time(2, 30)), tz="America/New_York")
        lon_end = pd.Timestamp(datetime.combine(t_dt, time(3, 30)), tz="America/New_York")

        asia_df = df_1m[(df_1m.index >= asia_start) & (df_1m.index < asia_end)]
        lon_df = df_1m[(df_1m.index >= lon_start) & (df_1m.index < lon_end)]

        if asia_df.empty:
            raise ValueError(f"Incomplete Asia session data ({asia_start} to {asia_end}) for {ticker}. Fail-closed: Zero synthetic fallback.")
        if lon_df.empty:
            raise ValueError(f"Incomplete London session data ({lon_start} to {lon_end}) for {ticker}. Fail-closed: Zero synthetic fallback.")

        asia_h = float(asia_df["high"].max())
        asia_l = float(asia_df["low"].min())
        lon_h = float(lon_df["high"].max())
        lon_l = float(lon_df["low"].min())

        # 2. Check broken status via SessionBoxEngine
        engine = SessionBoxEngine(df_cutoff, ticker=ticker).process()
        live_sessions = engine.get_live_sessions()
        asia_broken = bool(live_sessions.get("Asia", {}).get("broken", False))
        lon_broken = bool(live_sessions.get("London", {}).get("broken", False))

        # Classify ALN Pattern Code from Session Structure
        if lon_h > asia_h and lon_l >= asia_l:
            pattern_code = "LPEU"
        elif lon_l < asia_l and lon_h <= asia_h:
            pattern_code = "LPED"
        elif lon_h > asia_h and lon_l < asia_l:
            pattern_code = "LEA"
        else:
            pattern_code = "AEL"

        # Broken / Held Status
        if asia_broken and lon_broken:
            broken_status = "Broken/Broken"
        elif asia_broken and not lon_broken:
            broken_status = "Broken/Held"
        elif not asia_broken and lon_broken:
            broken_status = "Held/Broken"
        else:
            broken_status = "Held/Held"

        bias_info = compute_aln_bias(
            code=pattern_code,
            broken_status=broken_status,
            spot=spot,
            london_high=lon_h,
            london_low=lon_l
        )

        pattern_meta = ALN_PATTERN_META.get(pattern_code, {})
        full_name = pattern_meta.get("full_name", pattern_code)

        data = {
            "ticker": ticker,
            "target_date": t_dt.strftime("%Y-%m-%d"),
            "cutoff_time": cutoff_time,
            "spot_price": round(spot, 2),
            "asia_range": {"high": round(asia_h, 2), "low": round(asia_l, 2), "broken": asia_broken},
            "london_range": {"high": round(lon_h, 2), "low": round(lon_l, 2), "broken": lon_broken},
            "pattern_code": pattern_code,
            "pattern_name": full_name,
            "broken_status": broken_status,
            "bias": bias_info["bias"],
            "conviction": bias_info["conviction"],
            "reasoning": bias_info["reasoning"],
            "primary_target": bias_info["primary_target"],
            "primary_target_pct": bias_info["primary_target_pct"],
            "break_high_pct": bias_info["break_high_pct"],
            "break_low_pct": bias_info["break_low_pct"],
        }

        md = f"""# 🌐 NQStats ALN (Asia-London-NY) Session Report: {ticker} ({data['target_date']})
* **Analysis Cutoff**: `{cutoff_time} ET` | **Current Spot**: `{spot:,.2f}`
* **Pattern Classification**: `{data['pattern_code']}` &mdash; **{data['pattern_name']}**
* **Broken / Held Status**: `{data['broken_status']}` (Asia Broken: {asia_broken} | Lon Broken: {lon_broken})
* **Directional Bias**: **{data['bias']}** (Conviction: `{data['conviction']}`)

---

### 📊 NQStats Historical Break Probabilities
* **NY Breaks London High**: `{data['break_high_pct']:.1f}%`
* **NY Breaks London Low**: `{data['break_low_pct']:.1f}%`
* **Primary Target**: `{data['primary_target']}` (`{data['primary_target_pct']:.1f}%` Hit Rate)

### 🧭 Tactical Synthesis
* **{data['reasoning']}**
"""
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["target_date"],
            spot_price=spot,
            data=data,
            markdown_report=md,
            status=self.status,
            is_success=True,
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return f"# NQStats ALN Session Report for {data.get('ticker')}"


# 8. HERMAN PROBABILITIES PROVIDER (EXPLICIT SCAFFOLD - NOT PRODUCTION)
class HermanProbabilitiesProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "herman_probabilities"

    @property
    def description(self) -> str:
        return "Herman Statistical Boundary Probabilities (Cones & Outlier Thresholds)."

    @property
    def status(self) -> str:
        return STATUS_SCAFFOLD

    @property
    def version(self) -> str:
        return "0.1.0-scaffold"

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        # Explicitly marked scaffold warning
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=target_date or "Today",
            spot_price=0.0,
            data={"status": "scaffold_pending_engine", "note": "Herman mathematical engine pending implementation."},
            markdown_report="""# ⚠️ Herman Statistical Probabilities [SCAFFOLD]
> **Status**: Mathematical calculation engine is pending implementation. Excluded from production synthesis.
""",
            status=self.status,
            is_success=True,
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return f"# Herman Probabilities Report (Scaffold)"


# REGISTER ALL PROVIDERS
ConceptRegistry.register(CandleScienceProvider())
ConceptRegistry.register(HTFMacroProvider())
ConceptRegistry.register(WeeklyOutlookProvider())
ConceptRegistry.register(P12ScenariosProvider())
ConceptRegistry.register(SessionBudgetProvider())
ConceptRegistry.register(SignatureSetupsProvider())
ConceptRegistry.register(ALNSessionsProvider())
ConceptRegistry.register(HermanProbabilitiesProvider())
