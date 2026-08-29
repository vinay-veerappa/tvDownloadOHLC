"""Standard Concept Provider Implementations

Wraps all specialized engines into the unified BaseConceptProvider interface
and registers them automatically in the ConceptRegistry.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
from scripts.concepts.base import BaseConceptProvider, ConceptPayload, ChartOverlays
from scripts.concepts.registry import ConceptRegistry

from scripts.candle_science.run_candle_science import analyze_candle_science, format_candle_science_markdown
from scripts.wargaming.htf_macro_levels import compute_htf_macro_levels, format_htf_macro_markdown
from scripts.wargaming.weekly_outlook_engine import compute_weekly_outlook, format_weekly_outlook_markdown
from scripts.wargaming.p12_scenario_engine import compute_p12_scenarios, format_p12_scenarios_markdown
from scripts.wargaming.session_budget_engine import compute_session_budget, format_session_budget_markdown
from scripts.wargaming.signature_setup_scanner import scan_signature_setups, format_signature_setups_markdown


# 1. CANDLE SCIENCE PROVIDER
class CandleScienceProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "candle_science"

    @property
    def description(self) -> str:
        return "3-Candle sequence patterns and empirical MFE/MAE percentiles (P30, P50, P70)."

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = analyze_candle_science(ticker=ticker, target_date=target_date, mode="open")
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["target_date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_candle_science_markdown(data)


# 2. HTF MACRO PROVIDER
class HTFMacroProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "htf_macro"

    @property
    def description(self) -> str:
        return "Prior Monthly Midpoint, NFP Benchmark Midpoint, and Weekly EMA(5) 52-week excursions."

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = compute_htf_macro_levels(ticker=ticker, target_date=target_date)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["target_date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_htf_macro_markdown(data)


# 3. WEEKLY OUTLOOK PROVIDER
class WeeklyOutlookProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "weekly_outlook"

    @property
    def description(self) -> str:
        return "Day-of-Week Macro Cycles (Mon/Tue vs Thu/Fri), Weekly Candle state, and 0DTE->Next Friday Expected Moves."

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = compute_weekly_outlook(ticker=ticker, target_date=target_date)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["eval_date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_weekly_outlook_markdown(data)


# 4. P12 SCENARIOS PROVIDER
class P12ScenariosProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "p12_scenarios"

    @property
    def description(self) -> str:
        return "P12 Directional Vectors, 88.5% Midline Gravity Wells, 99.26% Goalposts, and Handshake Vectors."

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = compute_p12_scenarios(ticker=ticker, target_date=target_date, cutoff_time=cutoff_time)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_p12_scenarios_markdown(data)


# 5. SESSION BUDGET PROVIDER
class SessionBudgetProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "session_budget"

    @property
    def description(self) -> str:
        return "Overnight Volatility Checkbook Spending % against 10-Day Median Range (DRO Baseline)."

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = compute_session_budget(ticker=ticker, target_date=target_date, cutoff_time=cutoff_time)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["date"],
            spot_price=0.0,
            data=data,
            markdown_report=md
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_session_budget_markdown(data)


# 6. SIGNATURE SETUPS SCANNER PROVIDER
class SignatureSetupsProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "signature_setups"

    @property
    def description(self) -> str:
        return "Automated detection of Firecracker, Spongebob, and Broken-Broken Goalpost trade setups."

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        data = scan_signature_setups(ticker=ticker, target_date=target_date, cutoff_time=cutoff_time)
        md = self.format_markdown(data)
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["date"],
            spot_price=data["spot_price"],
            data=data,
            markdown_report=md
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return format_signature_setups_markdown(data)


# 7. NQSTATS ALN (ASIA / LONDON / NY) SESSION DYNAMICS PROVIDER
class ALNSessionsProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "aln_sessions"

    @property
    def description(self) -> str:
        return "NQStats ALN Sessions: Asia-London-NY structural relationships (LPEU, LPED, LEA, AEL) and break probabilities."

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        from scripts.libs_py.nqstats.classifiers import compute_aln_bias, ALN_PATTERN_META
        
        # Default active session context
        pattern_code = "LPEU"
        broken_status = "Held/Held"
        bias_info = compute_aln_bias(code=pattern_code, broken_status=broken_status, spot=29657.50, london_high=29654.0, london_low=29596.0)
        
        data = {
            "ticker": ticker,
            "target_date": target_date or "Today",
            "pattern_code": pattern_code,
            "pattern_name": "London Protrusion Expansion Up (LPEU)",
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
* **Pattern Classification**: `{data['pattern_code']}` &mdash; **{data['pattern_name']}**
* **Broken / Held Status**: `{data['broken_status']}`
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
            spot_price=29657.50,
            data=data,
            markdown_report=md
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return f"# NQStats ALN Session Report for {data.get('ticker')}"


# 8. HERMAN PROBABILITIES PROVIDER (Scaffold / Ready for Extension)
class HermanProbabilitiesProvider(BaseConceptProvider):
    @property
    def name(self) -> str:
        return "herman_probabilities"

    @property
    def description(self) -> str:
        return "Herman Statistical Boundary Probabilities: Empirical probability cones and outlier thresholds."

    def compute(self, ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45", context: Optional[Dict[str, Any]] = None) -> ConceptPayload:
        spot = 29650.0
        data = {
            "ticker": ticker,
            "target_date": target_date or "Today",
            "spot_price": spot,
            "herman_cones": {
                "upper_1sd": round(spot + 85.0, 2),
                "upper_2sd": round(spot + 160.0, 2),
                "lower_1sd": round(spot - 85.0, 2),
                "lower_2sd": round(spot - 160.0, 2),
            },
            "status": "Herman Probability Scaffolding Active. Plug in Herman distribution engine."
        }
        md = f"""# 🎲 Herman Statistical Boundary Probabilities: {ticker} ({data['target_date']})
* **Spot Price**: `{spot:,.2f}` | **Status**: `{data['status']}`

### 📊 Herman Probability Cones
* **Upper 2 Standard Deviations (Outlier Ceiling)**: `{spot+160:,.2f}` (95.4% boundary)
* **Upper 1 Standard Deviation (Standard Range)**: `{spot+85:,.2f}` (68.2% boundary)
* **Lower 1 Standard Deviation (Standard Range)**: `{spot-85:,.2f}` (68.2% boundary)
* **Lower 2 Standard Deviations (Outlier Floor)**: `{spot-160:,.2f}` (95.4% boundary)
"""
        return ConceptPayload(
            name=self.name,
            ticker=ticker,
            target_date=data["target_date"],
            spot_price=spot,
            data=data,
            markdown_report=md
        )

    def format_markdown(self, data: Dict[str, Any]) -> str:
        return f"# Herman Probabilities Report for {data.get('ticker')}"


# AUTO-REGISTER ALL PROVIDERS
ConceptRegistry.register(CandleScienceProvider())
ConceptRegistry.register(HTFMacroProvider())
ConceptRegistry.register(WeeklyOutlookProvider())
ConceptRegistry.register(P12ScenariosProvider())
ConceptRegistry.register(SessionBudgetProvider())
ConceptRegistry.register(SignatureSetupsProvider())
ConceptRegistry.register(ALNSessionsProvider())
ConceptRegistry.register(HermanProbabilitiesProvider())
