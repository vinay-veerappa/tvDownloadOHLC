"""
reporter.py — Report formatting for validation results.

Produces markdown tables and JSON reports from ValidationResult lists.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import ValidationResult, ComparisonStatus


def format_validation_result(result: ValidationResult) -> str:
    """Format a single validation result as a markdown block."""
    lines = []
    lines.append(f"### Filter: `{result.filter_key}`")
    lines.append(f"**Feature:** {result.feature} | **Target:** {result.target_session} | "
                 f"**Ticker:** {result.ticker}")
    lines.append(f"**Local Days:** {result.local_count} | "
                 f"**WebUI Days:** {result.webui_count or 'N/A'}")
    lines.append("")

    if result.error:
        lines.append(f"**❌ ERROR:** {result.error}")
        return "\n".join(lines)

    # Summary table
    lines.append("| Field | Status |")
    lines.append("|-------|--------|")
    for field, status in result.summary.items():
        lines.append(f"| {field} | {status.value} |")

    # Detailed diffs
    mismatches = [fc for fc in result.field_comparisons if fc.status == ComparisonStatus.MISMATCH]
    if mismatches:
        lines.append("")
        lines.append(f"**Discrepancies ({len(mismatches)}):**")
        for fc in mismatches[:30]:
            lines.append(f"  - `{fc.field_path}`: local={fc.local_value} webui={fc.webui_value}")
            if fc.message:
                lines[-1] += f" ({fc.message})"
        if len(mismatches) > 30:
            lines.append(f"  - ... and {len(mismatches) - 30} more")

    return "\n".join(lines)


def format_side_by_side(result: ValidationResult) -> str:
    """
    Format a single validation result as a comprehensive side-by-side comparison,
    organized by outcome. Shows EVERY field with local vs lookup values.
    """
    lines = []
    lines.append(f"# Side-by-Side Comparison")
    lines.append(f"")
    lines.append(f"**Filter:** `{result.filter_key}`")
    lines.append(f"**Target:** {result.target_session} | **Ticker:** {result.ticker}")
    lines.append(f"**Days:** {result.local_count} (local) = {result.webui_count or 'N/A'} (lookup)")
    lines.append(f"**Overall:** {result.overall_status.value} ({result.matched_fields}/{result.total_fields} fields match)")
    lines.append("")

    if result.error:
        lines.append(f"**❌ ERROR:** {result.error}")
        return "\n".join(lines)

    # Group field comparisons by category
    categories: Dict[str, List] = {}
    for fc in result.field_comparisons:
        parts = fc.field_path.split(".")
        cat = parts[0]
        categories.setdefault(cat, []).append(fc)

    # ── Section 1: Overall Stats ──
    lines.append("---")
    lines.append("## Section 1: Overall Statistics")
    lines.append("")

    # Count
    count_fcs = [fc for fc in result.field_comparisons if fc.field_path == "count"]
    if count_fcs:
        fc = count_fcs[0]
        lines.append(f"**Count:** local={fc.local_value} | lookup={fc.webui_value} | {fc.status.value}")
        lines.append("")

    # Distribution
    dist_fcs = [fc for fc in result.field_comparisons if fc.field_path.startswith("distribution.")]
    if dist_fcs:
        lines.append("### Outcome Distribution (probabilities)")
        lines.append("| Outcome | Local | Lookup | Status |")
        lines.append("|---------|-------|--------|--------|")
        for fc in sorted(dist_fcs, key=lambda x: x.field_path):
            outcome = fc.field_path.split(".")[-1]
            lv = str(fc.local_value) if fc.local_value is not None else "None"
            wv = str(fc.webui_value) if fc.webui_value is not None else "None"
            lines.append(f"| {outcome} | {lv} | {wv} | {fc.status.value} |")
        lines.append("")

    # ── Section 2: Per-Outcome Breakdown ──
    lines.append("---")
    lines.append("## Section 2: Per-Outcome Breakdown")
    lines.append("")

    # Identify outcomes from field paths
    outcomes = set()
    for fc in result.field_comparisons:
        parts = fc.field_path.split(".")
        if len(parts) >= 3:
            outcomes.add(parts[1])

    for outcome in sorted(outcomes):
        lines.append(f"### Outcome: {outcome}")
        lines.append("")

        # Count
        count_fc = next((fc for fc in result.field_comparisons if fc.field_path == f"distribution.{outcome}"), None)
        if count_fc:
            lines.append(f"**Count:** local={count_fc.local_value} | lookup={count_fc.webui_value} | {count_fc.status.value}")
            lines.append("")

        # Price stats
        ps_fcs = [fc for fc in result.field_comparisons if fc.field_path.startswith(f"price_stats.{outcome}.")]
        if ps_fcs:
            lines.append("#### Price Stats (Mode / Median)")
            lines.append("| Field | Local | Lookup | Status |")
            lines.append("|-------|-------|--------|--------|")
            for fc in sorted(ps_fcs, key=lambda x: x.field_path):
                field = fc.field_path.split(".")[-1]
                lv = str(fc.local_value) if fc.local_value is not None else "None"
                wv = str(fc.webui_value) if fc.webui_value is not None else "None"
                lines.append(f"| {field} | {lv} | {wv} | {fc.status.value} |")
            lines.append("")

        # Timing
        t_fcs = [fc for fc in result.field_comparisons if fc.field_path.startswith(f"timing.{outcome}.")]
        if t_fcs:
            lines.append("#### HOD/LOD Timing")
            lines.append("| Field | Local | Lookup | Status |")
            lines.append("|-------|-------|--------|--------|")
            for fc in sorted(t_fcs, key=lambda x: x.field_path):
                field = fc.field_path.split(".")[-1]
                lv = str(fc.local_value) if fc.local_value is not None else "None"
                wv = str(fc.webui_value) if fc.webui_value is not None else "None"
                lines.append(f"| {field} | {lv} | {wv} | {fc.status.value} |")
            lines.append("")

        # Broken rate
        br_fc = next((fc for fc in result.field_comparisons if fc.field_path == f"broken_rate.{outcome}"), None)
        if br_fc:
            lv = str(br_fc.local_value) if br_fc.local_value is not None else "None"
            wv = str(br_fc.webui_value) if br_fc.webui_value is not None else "None"
            lines.append(f"**Broken Rate:** local={lv}% | lookup={wv}% | {br_fc.status.value}")
            lines.append("")

        # Level hit rates
        lh_fcs = [fc for fc in result.field_comparisons if fc.field_path.startswith(f"level_hit_rate.")]
        if lh_fcs:
            lines.append("#### Level Hit Rates")
            lines.append("| Level | Local (%) | Lookup (%) | Status |")
            lines.append("|-------|-----------|------------|--------|")
            for fc in sorted(lh_fcs, key=lambda x: x.field_path):
                level = fc.field_path.split(".")[-1]
                lv = str(fc.local_value) if fc.local_value is not None else "None"
                wv = str(fc.webui_value) if fc.webui_value is not None else "None"
                lines.append(f"| {level} | {lv} | {wv} | {fc.status.value} |")
            lines.append("")

    return "\n".join(lines)


def format_summary_table(results: List[ValidationResult]) -> str:
    """Format all results as a summary table."""
    lines = []
    lines.append("## Validation Summary")
    lines.append("")
    lines.append(f"**Feature:** {results[0].feature if results else 'N/A'} | "
                 f"**Ticker:** {results[0].ticker if results else 'N/A'}")
    lines.append("")

    # Determine all summary fields
    all_fields = set()
    for r in results:
        all_fields.update(r.summary.keys())
    all_fields.discard("overall")
    sorted_fields = sorted(all_fields)

    header = "| Filter | Target | Days | " + " | ".join(f"{f}" for f in sorted_fields) + " | Overall |"
    sep = "|--------|--------|------|" + "|".join("--------" for _ in sorted_fields) + "|---------|"
    lines.append(header)
    lines.append(sep)

    for r in results:
        row = [
            f"`{r.filter_key}`",
            r.target_session,
            str(r.local_count),
        ]
        for f in sorted_fields:
            status = r.summary.get(f, ComparisonStatus.SKIPPED)
            row.append(status.value)
        row.append(r.overall_status.value)
        lines.append("| " + " | ".join(row) + " |")

    total = len(results)
    passed = sum(1 for r in results if r.overall_status == ComparisonStatus.MATCH)
    lines.append("")
    if passed == total:
        lines.append(f"**{passed}/{total} filter combinations passed** ✅")
    else:
        lines.append(f"**{passed}/{total} filter combinations passed** ⚠️")

    return "\n".join(lines)


class MarkdownReporter:
    """Generates a full markdown validation report."""

    def __init__(self, title: str = "WebUI Validation Report"):
        self.title = title

    def generate(self, results: List[ValidationResult]) -> str:
        """Generate a complete markdown report."""
        lines = [f"# {self.title}", ""]

        # Summary
        lines.append(format_summary_table(results))
        lines.append("")

        # Detailed results
        lines.append("---")
        lines.append("## Detailed Results")
        lines.append("")
        for r in results:
            lines.append(format_validation_result(r))
            lines.append("")

        return "\n".join(lines)


class JsonReporter:
    """Generates a JSON validation report."""

    @staticmethod
    def generate(results: List[ValidationResult]) -> str:
        """Generate a JSON report."""
        data = {
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.overall_status == ComparisonStatus.MATCH),
                "failed": sum(1 for r in results if r.overall_status == ComparisonStatus.MISMATCH),
                "errors": sum(1 for r in results if r.overall_status == ComparisonStatus.ERROR),
            },
            "results": [
                {
                    "feature": r.feature,
                    "filter_key": r.filter_key,
                    "target_session": r.target_session,
                    "ticker": r.ticker,
                    "local_count": r.local_count,
                    "webui_count": r.webui_count,
                    "overall_status": r.overall_status.value,
                    "matched_fields": r.matched_fields,
                    "mismatched_fields": r.mismatched_fields,
                    "total_fields": r.total_fields,
                    "error": r.error,
                    "field_comparisons": [
                        {
                            "field_path": fc.field_path,
                            "status": fc.status.value,
                            "local_value": str(fc.local_value),
                            "webui_value": str(fc.webui_value),
                            "diff": fc.diff,
                            "message": fc.message,
                        }
                        for fc in r.field_comparisons
                    ],
                }
                for r in results
            ],
        }
        return json.dumps(data, indent=2)
