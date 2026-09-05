"""A report that cannot name its inputs is not evidence.

Section 7.3, rules 1 and 2. Both were 🔴 for the whole life of this framework
and `reports_attributed` was hardcoded to NOT EVALUATED -- a criterion that
returned the same string on every run, which means "validated" was unreachable
for every strategy however good it was.

RULE 1 -- A REPORT NAMES ITS INPUTS. Strategy, ticker, date range, parameter
hash, data hash, run id, price basis, and the commit it was produced at.

WHY THE HEADER IS DERIVED FROM THE RECORD AND NEVER PASSED ALONGSIDE IT. A
reporter handed a `ticker=` argument can be handed the wrong one, and then the
report is confidently mislabelled -- worse than unlabelled, because it looks
attributed. `render_provenance` takes the run-record document and nothing else,
so the header cannot disagree with the run it came from. Anything absent from
the record renders as `(not recorded)` rather than being invented.

RULE 2 -- A REPORT REFUSES TO EXIST WHEN IT HAS NOTHING TO SAY. The evidence
that motivated this rule is gone (the fixed-path outputs directory was deleted
when reports moved under the run id), and the rule stands anyway: a 2-byte file
containing `ok` was a strategy that emitted no signals producing something that
read as a report. `refuse_empty` gives the same shape the newer reporters
already use -- a named reason, never a blank section.

⚠️ A DIRTY TREE IS SURFACED, NOT BURIED. `code.dirty` was `True` on every run
measured while this was written. A report produced from uncommitted code cannot
be reproduced from its own commit hash, and that is exactly the kind of thing a
reader assumes is fine unless told. It is rendered as a warning line inside the
header, not a footnote.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any, Dict, Iterable, Optional

#: The string `_reports_attributed` searches for. A report without it fails the
#: criterion, so it must be stable and it must be unlikely to occur by accident.
PROVENANCE_MARKER = "<!-- provenance:v1 -->"

#: Below this, a report BODY is a stub rather than a report.
#:
#: MEASURED ON THE BODY, NOT THE FILE. The first version compared the whole file
#: against 200 bytes -- and the provenance header alone is ~600, so the check
#: could never fire: a green with no reachable red, inside the module written to
#: remove one. The stub test is what caught it.
#:
#: 40 is chosen against the two real cases. The motivating stub was 2 bytes
#: (`ok`); the smallest LEGITIMATE body is a named refusal, which `refuse_empty`
#: renders at roughly 65 characters. So the band is real rather than arbitrary,
#: and both ends are asserted.
MIN_BODY_CHARS = 40

#: The whole-file floor, used only by `audit_reports`, which sees files on disk
#: and cannot separate body from header. Any file carrying a real header clears
#: it, so it catches a TRUNCATED WRITE rather than a stub.
MIN_REPORT_BYTES = 200


class UnattributableReport(RuntimeError):
    """Raised rather than writing a report that cannot name its inputs."""


def _get(doc: Dict[str, Any], path: str, default: str = "(not recorded)") -> Any:
    cur: Any = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur if cur not in (None, "") else default


def _short(v: Any, n: int = 19) -> str:
    s = str(v)
    # A sha256 is 71 chars with its prefix and unreadable in a table; the first
    # 12 hex digits identify a corpus uniquely enough to compare two runs.
    m = re.match(r"^sha256:([0-9a-f]{12})", s)
    return "sha256:{}".format(m.group(1)) if m else (s if len(s) <= n else s[:n])


def render_provenance(doc: Dict[str, Any], *, title: str = "") -> str:
    """The header every report carries. ASCII only -- cp1252 consoles.

    Takes the run-record DOCUMENT. Not a ticker, not a strategy name, not a
    date range: those are the fields that go wrong when passed separately.
    """
    if not isinstance(doc, dict) or not doc:
        raise UnattributableReport(
            "no run record supplied, so this report cannot name its inputs. "
            "Pass RunRecord.doc; section 7.3 rule 1 refuses the alternative.")
    run_id = _get(doc, "runId", "")
    if not run_id or run_id == "(not recorded)":
        raise UnattributableReport(
            "the run record has no runId. A report that cannot be tied to a run "
            "is not evidence, and rendering it anyway is how an unattributed "
            "number gets quoted six months later.")

    L = [PROVENANCE_MARKER, ""]
    if title:
        L += ["# {}".format(title), ""]
    L += ["| Input | Value |", "|---|---|",
          "| Run id | `{}` |".format(run_id),
          "| Strategy | `{}` ({}) |".format(_get(doc, "strategy.key"),
                                            _get(doc, "strategy.name")),
          "| Ticker | {} |".format(_get(doc, "data.ticker")),
          "| Price basis | **{}** |".format(_get(doc, "data.adjustment")),
          "| Date range | {} -> {} |".format(_short(_get(doc, "data.firstBar")),
                                             _short(_get(doc, "data.lastBar"))),
          "| Bars | {} rows, {} columns |".format(_get(doc, "data.rows"),
                                                  _get(doc, "data.columns")),
          "| Data hash | `{}` |".format(_short(_get(doc, "data.contentHash"))),
          "| Params hash | `{}` |".format(_short(_get(doc, "strategy.paramsHash"))),
          "| Loader | `{}` |".format(_get(doc, "data.loader")),
          "| Commit | `{}` |".format(_short(_get(doc, "code.commit"), 12)),
          ]

    if _get(doc, "data.adjustment") in ("undeclared", "(not recorded)"):
        L += ["", "> **The price basis is not declared.** Every P&L figure below "
                  "is unattributable by construction, and the promotion "
                  "checklist FAILS `attributable` for this run."]
    if _get(doc, "code.dirty", False) is True:
        n = _get(doc, "code.dirtyFileCount", "?")
        L += ["", "> **Produced from a dirty working tree** ({} modified "
                  "file(s)). The commit above does NOT reproduce this report."
                  .format(n)]
    return "\n".join(L) + "\n"


def refuse_empty(has_content: bool, what: str, reason: str) -> Optional[str]:
    """Rule 2. Returns the refusal text, or None when there is content.

    Deliberately returns a NAMED REASON rather than an empty string: a section
    that vanishes is indistinguishable from a section that was never asked for,
    and the newer reporters already use this shape ("Not available: ...").
    """
    if has_content:
        return None
    return "### {}\n\n_Not available: {}_\n".format(what, reason)


def write_report(path, body: str, doc: Dict[str, Any], *,
                 title: str = "") -> pathlib.Path:
    """The only sanctioned way to write a report file.

    Prepends the provenance header, so a report cannot be written without one --
    the same reasoning as `GovernedStrategy` sealing `CheckForSignal`: make the
    wrong thing unrepresentable rather than forbidden.
    """
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    stripped = (body or "").strip()
    if len(stripped) < MIN_BODY_CHARS:
        raise UnattributableReport(
            "{} has a {}-character body -- a stub, not a report. Section 7.3 "
            "rule 2: a report refuses to exist when it has nothing to say, and "
            "it says so WITH A REASON. Call refuse_empty() to render the reason "
            "rather than writing an empty file.".format(p.name, len(stripped)))
    text = render_provenance(doc, title=title) + "\n" + stripped + "\n"
    p.write_text(text, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# The check `reports_attributed` runs
# --------------------------------------------------------------------------- #

#: Artifact keys that are REPORTS and must therefore be attributable. Data files
#: (`pythonTrades`, `decisionLog`) carry their provenance in the run record that
#: names them and in their own columns, and a CSV cannot hold a Markdown header.
REPORT_ARTIFACTS = ("tearsheet", "optimizationSummary", "mfeMaeSummary",
                    "riskProfile", "sessionBreakdown")


def audit_reports(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Every report artifact this run recorded: does it name its inputs?

    Returns a verdict dict. Deliberately reports `checked` as well as failures,
    because a pass over ZERO reports is not a pass -- it is the vacuous green
    this project has been bitten by repeatedly.
    """
    arts = (doc or {}).get("artifacts") or {}
    checked, missing_marker, absent, stubs = [], [], [], []
    for key in REPORT_ARTIFACTS:
        raw = arts.get(key)
        if not raw:
            continue
        p = pathlib.Path(raw)
        if not p.exists():
            absent.append(key)
            continue
        checked.append(key)
        text = p.read_text(encoding="utf-8", errors="replace")
        if PROVENANCE_MARKER not in text:
            missing_marker.append(key)
        if len(text.encode("utf-8", "replace")) < MIN_REPORT_BYTES:
            stubs.append(key)

    problems = []
    if missing_marker:
        problems.append("no provenance header: {}".format(", ".join(missing_marker)))
    if absent:
        problems.append("recorded but not on disk: {}".format(", ".join(absent)))
    if stubs:
        problems.append("under {} bytes, a stub not a report: {}"
                        .format(MIN_REPORT_BYTES, ", ".join(stubs)))
    return {
        "checked": checked,
        "problems": problems,
        # NOT `not problems`. Zero reports checked means the run produced none,
        # which is a different statement from "every report is attributable" and
        # must not be reported as a pass.
        "ok": bool(checked) and not problems,
        "reason": ("{} report(s) name their inputs: {}"
                   .format(len(checked), ", ".join(checked)) if checked and not problems
                   else "; ".join(problems) if problems
                   else "no report artifacts were recorded, so there is nothing "
                        "to attribute -- this is NOT a pass"),
    }
