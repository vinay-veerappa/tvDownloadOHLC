"""Can a reader who has never seen this repo find the rules and act on them?

The question these answer is not "is the documentation good" but "does the path a
fresh agent actually walks lead to the right place, and does it contradict
itself on the way". Three real defects, all found 2026-09-05 by walking it:

  1. `CLAUDE.md` said **35 bespoke `run_*` scripts** in its summary and **32
     exist** forty lines later. Measured: 32, and only 6 are named `run_*` --
     section 4.1 already corrected the "35" claim and the summary never got it.
     A reader top-to-bottom hits the wrong number first.

  2. Section 2 is "Write the Python hunter" and never mentioned instrumenting
     it; section 3 is "Write or update the C# bot" and never mentioned the base
     class every bot must inherit. Both rules were filed under section 5,
     "Validate in NT8" -- so the step that needs the rule did not carry it. That
     is not a documentation nicety: it is why a fresh agent invents something
     new.

  3. Three citations still said the bot worklist was "B1-B6" after it reached
     B9, and sections 11.15 and 11.16 were the same ticket -- the exact
     redundancy the backlog had just been cleaned of.

WHY A TEST AND NOT A REVIEW. Every one of these is a claim that was true when
written. Numbers rot, sections move, and ranges grow -- so the rule "never quote
a count you did not just measure" only holds if something measures it.
"""

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
WORKFLOW = REPO / "docs" / "architecture" / "STRATEGY_WORKFLOW.md"
CLAUDE = REPO / "CLAUDE.md"
AGENTS = REPO / "AGENTS.md"
BACKLOG = REPO / "docs" / "architecture" / "BOT_FIX_BACKLOG.md"


def _text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def frozen_runner_count() -> int:
    from scripts.trading_framework.tests.frozen_runners import FROZEN
    return len(FROZEN)


# --------------------------------------------------------------------------- #
# A number in prose must match the thing that measures it
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("doc", [CLAUDE, AGENTS, WORKFLOW],
                         ids=lambda p: p.name)
def test_no_document_claims_a_runner_count_that_is_not_the_measured_one(doc):
    """`CLAUDE.md` carried 35 and 32 simultaneously. The population is in
    `frozen_runners.py`; a prose number that disagrees is stale by definition.

    Historical quotes are allowed when marked as such -- section 4.1 explains
    why the OLD "35 bespoke `run_*`" framing was wrong, and must keep saying so.
    """
    n = frozen_runner_count()
    body = _text(doc)
    # Strip anything explicitly flagged as the superseded claim.
    body = re.sub(r'(?i)(old|former|previous|was)\s+"?[^"\n]{0,40}35[^\n]*', "", body)
    wrong = sorted(set(re.findall(r"\b(\d{2})\s+bespoke", body))
                   | set(re.findall(r"\b(\d{2})\s+(?:engine-drivers|runners) (?:exist|already)",
                                    body)))
    bad = [w for w in wrong if int(w) != n]
    assert not bad, (
        "{} claims {} bespoke runner(s); frozen_runners.py has {}. Re-measure "
        "rather than editing the number to match.".format(doc.name, bad, n))


@pytest.mark.parametrize("doc", [CLAUDE, AGENTS], ids=lambda p: p.name)
def test_the_nth_runner_that_fails_is_one_past_the_measured_count(doc):
    """"a 33rd fails" is only true while 32 are frozen. This is the sentence
    that goes stale silently the moment one is added or retired."""
    n = frozen_runner_count()
    for m in re.finditer(r"a (\d+)(?:st|nd|rd|th) fails", _text(doc)):
        assert int(m.group(1)) == n + 1, (
            "{} says 'a {} fails' but {} runners are frozen, so it is the "
            "{}th that fails".format(doc.name, m.group(1), n, n + 1))


def test_the_bot_worklist_range_matches_the_tickets_that_exist():
    """Three citations said B1-B6 after the list reached B9."""
    ids = re.findall(r"^## (B\d+(?:\+B\d+)?)", _text(BACKLOG), re.M)
    assert ids, "no tickets found in BOT_FIX_BACKLOG.md -- the scan is vacuous"
    highest = max(int(n) for i in ids for n in re.findall(r"\d+", i))
    for doc in (CLAUDE, AGENTS, WORKFLOW):
        body = _text(doc)
        # Only RANGE citations ("the worklist, B1-B6"). A prose reference to
        # B1-B6 as the EVIDENCE for a claim is correct and must not be rewritten.
        for m in re.finditer(r"worklist[^\n]{0,40}?B1[–-]B(\d+)", body):
            assert int(m.group(1)) == highest, (
                "{} advertises the worklist as B1-B{} but it goes to B{}"
                .format(doc.name, m.group(1), highest))


# --------------------------------------------------------------------------- #
# The rule lives in the step that needs it
# --------------------------------------------------------------------------- #

def _section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i:text.index(end, i)]


def test_the_step_that_writes_the_hunter_says_to_instrument_it():
    """Section 2 is where someone writing a hunter reads. The rule was in
    section 5 and therefore unreachable from the step that needs it."""
    body = _section(_text(WORKFLOW), "## 2. Step 1", "## 3. Step 2")
    assert "GateRecorder" in body, (
        "section 2 must name GateRecorder -- a reader writing a hunter does not "
        "reach section 5 first")
    assert "last_decisions" in body


def test_the_step_that_writes_the_bot_says_which_base_class():
    """Same defect, other side. `GovernedStrategy` was documented under
    "Step 4 -- Validate in NT8", three sections after the step that needs it."""
    body = _section(_text(WORKFLOW), "## 3. Step 2", "## 4. Step 3")
    assert "GovernedStrategy" in body
    assert "OnEvaluate" in body, (
        "section 3 must show the method a bot implements, or a reader knows the "
        "class name and not the contract")
    assert "sealed" in body, (
        "and it must say CheckForSignal is SEALED -- that is the reason the "
        "design holds, not a detail")


def test_the_step_that_writes_the_bot_says_how_it_is_tested():
    """The user's question, made mechanical: does a new agent know how a bot is
    VERIFIED? Nothing here compiles NinjaScript, so the honest answer is layered
    and must be stated rather than left to be discovered."""
    body = _section(_text(WORKFLOW), "## 3. Step 2", "## 4. Step 3")
    assert "How a bot is tested" in body
    for must in ("nt_compile", "roster", "parity"):
        assert must in body, (
            "the testing section must name {!r} as part of the evidence chain"
            .format(must))
    assert "not a compile" in body or "NOT a compile" in body, (
        "a parse check reads as a compile check unless it says it is not")


# --------------------------------------------------------------------------- #
# Both agent files agree, since they are meant to be one rule set
# --------------------------------------------------------------------------- #

def test_both_agent_files_name_the_same_base_class_and_section():
    """CLAUDE.md and AGENTS.md are the same rules for different agents. A rule
    in one and not the other is a rule that applies to some agents."""
    c, a = _text(CLAUDE), _text(AGENTS)
    for token in ("GovernedStrategy", "OnEvaluate", "uninstrumented.py"):
        assert token in c, "CLAUDE.md is missing {!r}".format(token)
        assert token in a, "AGENTS.md is missing {!r}".format(token)
    sec_c = set(re.findall(r"§(\d+\.\d+)", c))
    sec_a = set(re.findall(r"§(\d+\.\d+)", a))
    # Both must cite the governance sections. `or True` was in the first draft
    # of this line, which made it a green with no reachable red.
    for s in ("3.4", "5.5"):
        assert s in sec_c, "CLAUDE.md must cite section {}".format(s)
    assert "3.4" in sec_a, "AGENTS.md must cite the base-class section"


def _workflow_citing_regions():
    """Only the text where a bare `§N.N` MEANS a STRATEGY_WORKFLOW section.

    My first version scanned every `docs/architecture/*.md` and flagged
    `AGENT_LOOP_V2_PLAN.md §9.1` and `CLAUDE.md §5.84` -- which refer to those
    documents' OWN sections and to the riskguard handover. A gate that fires on
    correct input trains you to switch it off, so the region is stated instead
    of assumed. In CLAUDE.md the strategy rules end at `## Global Rules`; every
    workflow citation is above it and every foreign one below.
    """
    claude = _text(CLAUDE)
    return [
        ("CLAUDE.md (strategy block)", claude[:claude.index("## Global Rules")]),
        ("AGENTS.md", _text(AGENTS)),
        ("BOT_FIX_BACKLOG.md", _text(BACKLOG)),
        ("STRATEGY_WORKFLOW.md (self-refs)", _text(WORKFLOW)),
    ]


def test_every_section_cited_as_a_workflow_section_exists():
    """A moved section leaves every pointer to it wrong. §5.7 became §3.4 and
    fourteen references had to move with it -- this is what would have caught
    the ones I missed."""
    body = _text(WORKFLOW)
    headings = set(re.findall(r"^#{2,4} (\d+(?:\.\d+)?)[ .]", body, re.M))
    assert len(headings) > 20, "heading scan is vacuous: {}".format(sorted(headings))
    dangling = {}
    for name, region in _workflow_citing_regions():
        for s in set(re.findall(r"§(\d+\.\d+)", region)) | set(
                re.findall(r"section (\d+\.\d+)", region)):
            if s not in headings:
                dangling.setdefault(name, []).append(s)
    assert not dangling, (
        "these references point at STRATEGY_WORKFLOW.md sections that do not "
        "exist: {}. A renumbered section takes every pointer with it."
        .format({k: sorted(v) for k, v in dangling.items()}))
