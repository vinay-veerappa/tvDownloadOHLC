"""NotebookLM Synchronization Engine for Harvested Trading Strategies.

Aggregates harvested strategies, Pine scripts, and quantitative research from
`data/strategies/raw_mined/` into structured Markdown knowledge base dossiers,
mapped directly to dedicated Google NotebookLM notebooks.

Usage:
    python -m scripts.mining.sync_to_notebooklm --compile-dossiers
    python -m scripts.mining.sync_to_notebooklm --archetype gamma_exposure_gex
"""
from __future__ import annotations

import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.mining.config import DATA_DIR, NOTEBOOK_MAPPINGS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("NotebookLMSync")

SYNC_DIR = DATA_DIR / "synced"


def compile_archetype_dossier(archetype: str) -> Path:
    """Compile all mined items for a given archetype into a single structured Markdown dossier."""
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    nb_info = NOTEBOOK_MAPPINGS.get(archetype, {})
    title = nb_info.get("title", archetype.replace("_", " ").title())
    nb_id = nb_info.get("id", "UNASSIGNED")
    nb_url = nb_info.get("url", "")

    dossier_lines: List[str] = [
        f"# {title} — Master Knowledge Base",
        "",
        f"> **NotebookLM Knowledge Base**: [{title}]({nb_url}) (`{nb_id}`)",
        f"> **Archetype Key**: `{archetype}`",
        "> **Standard**: Universal Basis Points (bps) & Zero Lookahead",
        "",
        "---",
        "",
        "## 1. Domain Overview & Execution Edge",
        "",
    ]

    # Add domain-specific edge description
    if archetype == "gamma_exposure_gex":
        dossier_lines.extend([
            "Gamma Exposure (GEX) is a structural market microstructure discipline. Rather than relying on lagging price indicators, GEX models mandatory institutional dealer delta-hedging obligations.",
            "",
            "### Core Mechanical Edge Principles:",
            "1. **Positive Gamma Regime (Long Gamma)**: Dealers buy dips and sell rips to maintain delta neutrality. This acts as a volatility dampener, anchoring price to high-gamma strikes and favoring mean-reversion strategies.",
            "2. **Negative Gamma Regime (Short Gamma)**: Dealers sell dips and buy rips. This accelerates volatility, fueling directional liquidation cascades and favoring breakout/trend continuation strategies.",
            "3. **Zero Gamma Level (Volatility Trigger)**: The exact inflection price where net dealer gamma transitions between positive and negative.",
            "4. **Call Wall & Put Wall Pinning**: Strikes with peak open interest / gamma concentration act as major institutional resistance and support floors into OpEx.",
            "",
        ])
    elif archetype == "options_0dte_intraday":
        dossier_lines.extend([
            "0DTE (Zero-Days-to-Expiration) strategies exploit acute intraday time decay (Theta) and intraday dealer hedging on index products (SPX, NDX, QQQ, SPY).",
            "",
            "### Core Mechanical Edge Principles:",
            "1. **Expected Move (EM) Strike Pegging**: Strike selection anchored to the institutional 1-sigma / 0.5-sigma daily implied move rather than arbitrary point distances.",
            "2. **Noon Theta Acceleration**: The non-linear acceleration of gamma/theta decay between 11:30 AM and 14:00 PM EST.",
            "3. **Defined Stop-Loss Multipliers**: Pre-set risk floors (e.g. 2x to 3x credit received) to strictly control the negative convexity of short premium.",
            "4. **Delta-Neutral Scalping**: Rebalancing underlying futures/etfs against short options deltas around gamma inflection points.",
            "",
        ])
    elif archetype == "options_orderflow_sweeps":
        dossier_lines.extend([
            "Options Order Flow tracks aggressive institutional 'Smart Money' executions across options exchanges (CBOE, ISE, PHLX, BOX).",
            "",
            "### Core Mechanical Edge Principles:",
            "1. **Aggressive Ask-Side Sweeps**: Orders executed concurrently across multiple exchanges at the ask or above ask, indicating urgent institutional accumulation.",
            "2. **Golden Sweeps**: Out-of-the-money options sweeps with contract premiums exceeding $1,000,000 and expiration within 30-60 days.",
            "3. **Volume > Open Interest (Vol > OI)**: New opening positioning rather than closing/hedging existing inventory.",
            "4. **Dark Pool & Equity Block Confluence**: Large dark pool prints matching option sentiment within the same session window.",
            "",
        ])
    elif archetype == "options_volatility_events":
        dossier_lines.extend([
            "Volatility and Event trading strategies capitalize on Implied Volatility (IV) mispricing, post-earnings drift, and VIX term structure dynamics.",
            "",
            "### Core Mechanical Edge Principles:",
            "1. **Pre-Earnings IV Expansion**: Systematic long gamma/vega accumulation 14-21 days prior to earnings announcements, exiting before announcement.",
            "2. **Post-Earnings IV Crush**: Selling extreme IV rank (>90th percentile) prior to announcements, capturing rapid volatility collapse regardless of small moves.",
            "3. **Post-Earnings Announcement Drift (PEAD)**: Multi-week directional follow-through following significant Standardized Unexpected Earnings (SUE).",
            "4. **VIX Contango Roll Yield**: Harvesting the structural roll yield of VIX futures term structure during normal contango regimes.",
            "",
        ])
    elif archetype == "options_spreads_income":
        dossier_lines.extend([
            "Multi-leg spreads and systematic income strategies engineer asymmetric risk profiles and consistent portfolio yields across multi-week horizons.",
            "",
            "### Core Mechanical Edge Principles:",
            "1. **The Wheel Strategy**: Systematic cash-secured put selling at high delta/theta efficiency, transitioning to covered calls upon assignment.",
            "2. **Broken Wing Butterflies (BWB)**: Asymmetric butterflies with zero upside risk, designed to monetize range-bound equity drift.",
            "3. **45 DTE Tastytrade Management**: Selling 16-30 delta spreads at 45 DTE, taking profit mechanically at 50% max profit or 21 DTE.",
            "4. **Poor Man's Covered Call (PMCC)**: Deep ITM LEAPS long call substitution with short OTM call sales for high capital efficiency.",
            "",
        ])
    elif archetype == "range_chop_congestion":
        dossier_lines.extend([
            "Range and Congestion strategies identify periods of volatility compression, chop zones, and balance areas to execute mean-reversion at boundaries or trade high-conviction expansion breakouts.",
            "",
            "### Core Mechanical Edge Principles:",
            "1. **Chop Index & Kaufman Efficiency**: Quantifying chop regimes (KER < 0.30) to suppress trend-following systems and activate boundary fades.",
            "2. **Darvas & Consolidation Boxes**: Explicit high/low threshold boundaries establishing balance areas.",
            "3. **False Breakout Absorption**: Sweeps of range highs/lows that immediately fail to accept, reverting back to the range midpoint.",
            "",
        ])
    elif archetype == "stock_scanners_screeners":
        dossier_lines.extend([
            "Stock scanners and algorithmic screener engines dynamically filter thousands of equities into actionable, high-probability setups at market open and intraday.",
            "",
            "### Core Mechanical Edge Principles:",
            "1. **Relative Volume (RVOL) Surge**: Identifying stocks trading > 3x to 5x their 30-day average volume at the opening bell, confirming institutional participation.",
            "2. **Pre-Market Gappers & Catalysts**: Classifying gap size (> 4%), catalyst type (earnings, PR, biotech FDA, upgrades), and float rotation.",
            "3. **Episodic Pivots**: High-volume trend breaks initiated by fundamental earnings surprise or structural corporate change.",
            "4. **High Tight Flags**: 100%+ momentum runups consolidating in tight ranges (< 20-25% pullback) over 3-8 weeks.",
            "5. **High of Day (HOD) Momentum Sweeps**: Real-time scanners alerting on new intraday highs accompanied by volume acceleration and tape pressure.",
            "",
        ])
    elif archetype == "volatility_systems_vcp":
        dossier_lines.extend([
            "Volatility-based systems quantify volatility cycles (compression precedes expansion) to enter low-risk, high-asymmetry explosive breakouts.",
            "",
            "### Core Mechanical Edge Principles:",
            "1. **Volatility Contraction Pattern (VCP / Mark Minervini)**: Progressive contraction of price swings (e.g. 20% -> 10% -> 5% -> 2%) with dry volume before breakout.",
            "2. **Toby Crabel NR7 / NR4**: Identifying the Narrowest Range bar of the last 7 (or 4) bars, signaling imminent volatility expansion.",
            "3. **ATR Expansion Breakouts**: Stocks exploding out of tight bases with single-day range > 2x-3x 14-day Average True Range (ATR).",
            "4. **Volatility Squeeze Multi-Stock Scanners**: Systematic scanning across 1,000+ stocks where Bollinger Bands compress inside Keltner Channels.",
            "5. **Historical Volatility vs. Implied Volatility (HV/IV) Discrepancies**: Exploiting mispricings where HV collapses while IV remains elevated or vice versa.",
            "",
        ])

    dossier_lines.extend([
        "---",
        "",
        "## 2. Harvested Strategy Rulebooks & Implementations",
        "",
    ])

    # Scan all subdirectories in DATA_DIR for archetype-specific items
    found_items = 0
    for source_dir in DATA_DIR.iterdir():
        if not source_dir.is_dir() or source_dir.name == "synced":
            continue
        arch_dir = source_dir / archetype
        if not arch_dir.exists() or not arch_dir.is_dir():
            continue

        source_name = source_dir.name
        json_files = list(arch_dir.glob("*.json"))
        code_files = list(arch_dir.glob("*.pine")) + list(arch_dir.glob("*.py")) + list(arch_dir.glob("*.cs"))

        if json_files or code_files:
            dossier_lines.extend([
                f"### Channel: {source_name.upper()} Harvested Candidates",
                "",
            ])

        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8", errors="ignore"))
                title = data.get("title") or data.get("full_name") or data.get("id") or jf.stem
                url = data.get("url", "")
                desc = data.get("description", "")
                rules = data.get("rules", "")
                rationale = data.get("rationale", "")
                readme = data.get("readme_excerpt", "")

                found_items += 1
                dossier_lines.extend([
                    f"#### [{source_name.title()}] {title}",
                    f"* **URL**: {url}",
                ])
                if desc:
                    dossier_lines.append(f"* **Summary**: {desc}")
                if rules:
                    dossier_lines.extend([
                        "",
                        "**Mechanical Rules / Methodology**:",
                        f"> {rules}",
                        "",
                    ])
                if rationale:
                    dossier_lines.extend([
                        "",
                        "**Underlying Market Rationale / Edge**:",
                        f"> {rationale}",
                        "",
                    ])
                if readme:
                    dossier_lines.extend([
                        "",
                        "**Technical Specifications & Formulation**:",
                        "```text",
                        readme[:2500],
                        "```",
                        "",
                    ])
                dossier_lines.append("")
            except Exception as e:
                log.warning(f"Failed parsing {jf}: {e}")

        for cf in code_files:
            try:
                content = cf.read_text(encoding="utf-8", errors="ignore")
                lang = cf.suffix.replace(".", "")
                found_items += 1
                dossier_lines.extend([
                    f"#### Source Code: `{cf.name}`",
                    f"```{lang}",
                    content[:4000],
                    "```",
                    "",
                ])
            except Exception as e:
                log.warning(f"Failed reading code {cf}: {e}")

    if found_items == 0:
        dossier_lines.append(f"*No raw mined files found yet for `{archetype}`. Run `harvest_all.py --archetypes {archetype}` to harvest.*")

    out_file = SYNC_DIR / f"{archetype}_knowledge_base.md"
    out_file.write_text("\n".join(dossier_lines), encoding="utf-8")
    log.info(f"Compiled dossier for '{archetype}' -> {out_file} ({len(dossier_lines)} lines)")
    return out_file


def compile_all_dossiers() -> Dict[str, Path]:
    """Compile dossiers for all defined archetypes."""
    results: Dict[str, Path] = {}
    for arch in NOTEBOOK_MAPPINGS.keys():
        results[arch] = compile_archetype_dossier(arch)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile and sync strategy dossiers to NotebookLM.")
    parser.add_argument("--archetype", type=str, help="Specific archetype to compile")
    parser.add_argument("--compile-dossiers", action="store_true", help="Compile dossiers for all archetypes")
    args = parser.parse_args()

    if args.archetype:
        compile_archetype_dossier(args.archetype)
    else:
        compile_all_dossiers()
