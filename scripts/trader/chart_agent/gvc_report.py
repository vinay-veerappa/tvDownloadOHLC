"""gvc_report.py — render a GVC result JSON as a markdown verification report.

Produces a human-readable markdown file for eyeball-verification of the
Generate-Validate-Correct loop output.

Usage:
    python -m scripts.trader.chart_agent.gvc_report --ticker ES1
    python -m scripts.trader.chart_agent.gvc_report --file data/vision/gvc_results/ES1_2026-08-06_gvc.json
    python -m scripts.trader.chart_agent.gvc_report --ticker ES1 --ticker NQ1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent.parent.parent
GVC_DIR = _REPO / "data" / "vision" / "gvc_results"
REPORT_DIR = _REPO / "data" / "vision" / "gvc_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _strip_fences(text: str) -> str:
    """Strip ```yaml ... ``` fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first fence line
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _parse_verdict_fields(verdict_text: str) -> dict:
    """Lightweight extraction of key fields from the YAML verdict text.

    Not a full YAML parser — just pulls the fields we need for the summary
    table using regex. Avoids a PyYAML dependency for the report renderer.
    """
    text = _strip_fences(verdict_text)
    fields: dict = {}

    # bias:
    m = re.search(r"^bias:\s*(\w+)", text, re.MULTILINE)
    fields["bias"] = m.group(1) if m else "?"

    # readiness:
    m = re.search(r"^readiness:\s*(\w+)", text, re.MULTILINE)
    fields["readiness"] = m.group(1) if m else "?"

    # primary_pd_array:
    m = re.search(r"^primary_pd_array:\s*(\S+)", text, re.MULTILINE)
    fields["primary_pd_array"] = m.group(1) if m else "?"

    # primary_array_tf:
    m = re.search(r"^primary_array_tf:\s*(\S+)", text, re.MULTILINE)
    fields["primary_array_tf"] = m.group(1) if m else "?"

    # htf_story:
    m = re.search(r'^htf_story:\s*"(.+)"', text, re.MULTILINE)
    fields["htf_story"] = m.group(1) if m else "?"

    # readiness_reason:
    m = re.search(r'^readiness_reason:\s*"(.+)"', text, re.MULTILINE)
    fields["readiness_reason"] = m.group(1) if m else "?"

    # invalidation:
    m = re.search(r'^invalidation:\s*"(.+)"', text, re.MULTILINE)
    fields["invalidation"] = m.group(1) if m else "?"

    # alternate_scenario:
    m = re.search(r'^alternate_scenario:\s*"(.+)"', text, re.MULTILINE)
    fields["alternate_scenario"] = m.group(1) if m else "?"

    # price_delivery_narrative:
    m = re.search(r'^price_delivery_narrative:\s*"(.+)"', text, re.MULTILINE)
    fields["price_delivery_narrative"] = m.group(1) if m else "?"

    # premium_discount_position:
    m = re.search(r"^premium_discount_position:\s*(\w+)", text, re.MULTILINE)
    fields["pd_position"] = m.group(1) if m else "?"

    return fields


def _verdicts_equal(orig: str, corrected: str) -> bool:
    """Compare two verdicts ignoring fences/whitespace."""
    return _strip_fences(orig).strip() == _strip_fences(corrected).strip()


def _bias_mentioned_in_vision(bias: str, vision_text: str) -> str:
    """Check whether the verdict bias is supported/mentioned in a vision analysis."""
    bias_lower = bias.lower()
    if bias_lower in vision_text.lower():
        # crude: check if the analysis leans that way (title or summary)
        # Look for phrases like "bullish case", "bearish case" in headers
        if re.search(rf"#{1,6}\s.*{bias_lower}", vision_text, re.IGNORECASE):
            return "primary"
        return "mentioned"
    return "absent"


def render_report(result: dict) -> str:
    """Render a GVC result dict as a markdown verification report."""
    ticker = result["ticker"]
    date = result["date"]
    model = result.get("model", "?")
    chart = result.get("chart", "?")
    timestamp = result.get("timestamp", "?")

    orig_verdict = result["original_verdict"]
    corrected_verdict = result["corrected_verdict"]
    blind = result.get("blind_vision", {})
    comparison = result.get("comparison", {})

    orig_fields = _parse_verdict_fields(orig_verdict)
    corr_fields = _parse_verdict_fields(corrected_verdict)
    verdicts_match = _verdicts_equal(orig_verdict, corrected_verdict)

    lines: list[str] = []
    a = lines.append

    a(f"# GVC Verification Report — {ticker} | {date}")
    a("")
    a(f"- **Model:** `{model}`")
    a(f"- **Chart:** `{chart}`")
    a(f"- **Timestamp:** {timestamp}")
    a(f"- **Verdict changed by correction:** {'NO — vision confirmed reasoner' if verdicts_match else 'YES — see corrected verdict below'}")
    a("")

    # ── Summary table ───────────────────────────────────────────────
    a("## Summary")
    a("")
    a("| Field | Original | Corrected |")
    a("|---|---|---|")
    a(f"| **Bias** | {orig_fields['bias']} | {corr_fields['bias']} |")
    a(f"| **Primary PD Array** | {orig_fields['primary_pd_array']} ({orig_fields['primary_array_tf']}) | {corr_fields['primary_pd_array']} ({corr_fields['primary_array_tf']}) |")
    a(f"| **P/D Position** | {orig_fields['pd_position']} | {corr_fields['pd_position']} |")
    a(f"| **Readiness** | {orig_fields['readiness']} | {corr_fields['readiness']} |")
    a("")

    # ── HTF story + narrative ────────────────────────────────────────
    a("## HTF Story (original)")
    a("")
    a(f"> {orig_fields['htf_story']}")
    a("")
    a("### Price Delivery Narrative (original)")
    a("")
    a(f"> {orig_fields['price_delivery_narrative']}")
    a("")

    # ── Key levels + invalidation ───────────────────────────────────
    a("## Invalidation & Alternate Scenario (original)")
    a("")
    a(f"- **Invalidation:** {orig_fields['invalidation']}")
    a(f"- **Alternate:** {orig_fields['alternate_scenario']}")
    a(f"- **Readiness reason:** {orig_fields['readiness_reason']}")
    a("")

    # ── Vision agreement matrix ─────────────────────────────────────
    a("## Vision Agreement Matrix")
    a("")
    verdict_bias = comparison.get("verdict_bias", orig_fields["bias"])
    a(f"Verdict bias: **{verdict_bias}**")
    a("")
    a("| Vision Analysis | Present in GVC | Verdict bias supported? |")
    a("|---|---|---|")
    for kind in ("bullish", "bearish", "neutral"):
        present = comparison.get(f"{kind}_analysis_present", False)
        present_str = "✓ present" if present else "✗ missing"
        vision_text = blind.get(kind, "")
        support = _bias_mentioned_in_vision(verdict_bias, vision_text) if vision_text else "—"
        a(f"| {kind.capitalize()} | {present_str} | {support} |")
    a("")

    # ── Correction assessment ──────────────────────────────────────
    a("## Correction Assessment")
    a("")
    if verdicts_match:
        a("✅ **No correction applied.** The 3 blind vision analyses agreed with the reasoner's original verdict. The corrected verdict is byte-identical to the original.")
    else:
        a("⚠️ **Correction applied.** Vision analyses surfaced observations that changed the verdict. Compare the original vs corrected YAML below.")
        if orig_fields["bias"] != corr_fields["bias"]:
            a(f"- **Bias flipped:** {orig_fields['bias']} → {corr_fields['bias']}")
        if orig_fields["readiness"] != corr_fields["readiness"]:
            a(f"- **Readiness changed:** {orig_fields['readiness']} → {corr_fields['readiness']}")
    a("")

    # ── Eyeball-verification checklist ──────────────────────────────
    a("## Eyeball-Verification Checklist")
    a("")
    a("Open the chart image and verify each claim against it:")
    a("")
    a(f"- [ ] Chart path: `{chart}`")
    a(f"- [ ] Bias ({orig_fields['bias']}) matches the visible price action direction")
    a(f"- [ ] Primary PD array ({orig_fields['primary_pd_array']}) is unmitigated and aligns with bias")
    a(f"- [ ] P/D position ({orig_fields['pd_position']}) is correct relative to the dealing range")
    a(f"- [ ] Invalidation level is visible and sensible: {orig_fields['invalidation']}")
    a(f"- [ ] HTF story is internally consistent: {orig_fields['htf_story']}")
    a("- [ ] Blind vision bullish case is plausible (see below)")
    a("- [ ] Blind vision bearish case is plausible (see below)")
    a("- [ ] Blind vision neutral observations are accurate (see below)")
    a("- [ ] Reasoner did not contradict itself across timeframes")
    a("")

    # ── Full blind vision analyses ─────────────────────────────────
    a("## Blind Vision Analyses (full text)")
    a("")
    a("These were generated INDEPENDENTLY from the verdict — Gemini read the chart with no knowledge of the reasoner's call.")
    a("")
    for kind in ("bullish", "bearish", "neutral"):
        text = blind.get(kind, "")
        a(f"<details><summary><b>{kind.capitalize()} analysis</b> ({len(text)} chars)</summary>")
        a("")
        a(text)
        a("")
        a("</details>")
        a("")

    # ── Full verdicts ──────────────────────────────────────────────
    a("## Original Verdict (YAML)")
    a("")
    a("```yaml")
    a(_strip_fences(orig_verdict))
    a("```")
    a("")
    if not verdicts_match:
        a("## Corrected Verdict (YAML)")
        a("")
        a("```yaml")
        a(_strip_fences(corrected_verdict))
        a("```")
        a("")
    else:
        a("## Corrected Verdict")
        a("")
        a("Identical to the original — vision confirmed the reasoner. No changes.")
        a("")

    a("---")
    a(f"*Generated by `scripts/trader/chart_agent/gvc_report.py` from `{result.get('_source_file', '?')}`*")
    a("")

    return "\n".join(lines)


def _find_gvc_json(ticker: str, date: str | None = None) -> Path | None:
    """Find the most recent GVC JSON for a ticker (optionally a specific date)."""
    if date:
        p = GVC_DIR / f"{ticker}_{date}_gvc.json"
        if p.exists():
            return p
    # fallback: most recent matching
    candidates = sorted(GVC_DIR.glob(f"{ticker}_*_gvc.json"), reverse=True)
    return candidates[0] if candidates else None


def main():
    ap = argparse.ArgumentParser(description="Render a GVC result as a markdown verification report")
    g_ticker = ap.add_argument("--ticker", action="append", help="Ticker symbol (can repeat)")
    ap.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: most recent)")
    ap.add_argument("--file", action="append", help="Direct path to a GVC JSON (can repeat)")
    ap.add_argument("--out-dir", default=str(REPORT_DIR), help="Output directory for markdown reports")
    args = ap.parse_args()

    files: list[Path] = []
    for f in args.file or []:
        p = Path(f)
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(1)
        files.append(p)

    for t in args.ticker or []:
        p = _find_gvc_json(t, args.date)
        if p is None:
            print(f"ERROR: no GVC JSON found for {t} (date={args.date})", file=sys.stderr)
            sys.exit(1)
        files.append(p)

    if not files:
        ap.error("Provide --ticker or --file")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            result = json.load(fh)
        result["_source_file"] = str(f)
        md = render_report(result)
        ticker = result["ticker"]
        date = result["date"]
        out_path = out_dir / f"{ticker}_{date}_verification.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"Wrote {out_path} ({len(md)} chars)")


if __name__ == "__main__":
    main()