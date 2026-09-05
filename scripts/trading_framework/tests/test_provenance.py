"""Section 7.3: a report names its inputs, or it is not written.

WHAT THIS CLOSES. `reports_attributed` used to be a CONSTANT -- it set
NOT EVALUATED with a fixed string on every run, so `validated`, which is
`all(status == PASS)`, was unreachable for every strategy however good it was.
A criterion that cannot change its answer is exactly the shape section 0 exists
to forbid, and it sat inside the module written to enforce that.

So the tests below are weighted toward the FAILING direction. A green
`reports_attributed` is only worth something if a red is reachable, and there
are four distinct reds: no header, a recorded file that is not on disk, a stub,
and -- the one most likely to be missed -- zero reports checked.
"""

import json
import pathlib

import pytest

from scripts.trading_framework.reporting.provenance import (
    MIN_REPORT_BYTES, PROVENANCE_MARKER, REPORT_ARTIFACTS, UnattributableReport,
    audit_reports, refuse_empty, render_provenance, write_report,
)

REPO = pathlib.Path(__file__).resolve().parents[3]


def _doc(**over):
    d = {
        "runId": "RUN_20260905_000000_000_NQ1_TEST_abcdef01",
        "strategy": {"key": "test_strat", "name": "Test Strategy",
                     "paramsHash": "sha256:" + "a" * 64},
        "data": {"ticker": "NQ1", "adjustment": "unadjusted",
                 "firstBar": "2016-01-03 18:00:00-05:00",
                 "lastBar": "2026-03-31 23:59:00-04:00",
                 "rows": 3610528, "columns": 29,
                 "contentHash": "sha256:" + "b" * 64,
                 "loader": "DataLoader.load_enriched"},
        "code": {"commit": "c" * 40, "dirty": False},
        "artifacts": {},
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    return d


# --------------------------------------------------------------------------- #
# Rule 1 -- the header
# --------------------------------------------------------------------------- #

def test_the_header_names_every_input_the_rule_lists():
    """Strategy, ticker, date range, parameter hash, data hash, run id, basis."""
    h = render_provenance(_doc())
    for must in ("RUN_20260905", "test_strat", "NQ1", "unadjusted",
                 "2016-01-03", "2026-03-31", "sha256:aaaaaaaaaaaa",
                 "sha256:bbbbbbbbbbbb", "DataLoader.load_enriched"):
        assert must in h, must
    assert PROVENANCE_MARKER in h


def test_a_report_cannot_be_written_without_a_run_record():
    """The header is DERIVED from the record. A reporter handed a `ticker=`
    argument can be handed the wrong one, and then the report is confidently
    mislabelled -- worse than unlabelled, because it looks attributed."""
    with pytest.raises(UnattributableReport) as e:
        render_provenance({})
    assert "cannot name its inputs" in str(e.value)


def test_a_record_without_a_run_id_is_refused():
    with pytest.raises(UnattributableReport) as e:
        render_provenance(_doc(runId=""))
    assert "runId" in str(e.value)


def test_a_missing_field_is_marked_not_recorded_rather_than_invented():
    """An absent value and a wrong value are opposite failures. Only one of
    them is detectable by a reader."""
    d = _doc()
    del d["data"]["contentHash"]
    h = render_provenance(d)
    assert "(not recorded)" in h


def test_an_undeclared_price_basis_is_called_out_in_the_report_itself():
    """`--price-adjustment` defaults to `undeclared` by design, and every P&L
    figure in the report is then unattributable. Saying so in the checklist
    only helps someone who read the checklist."""
    h = render_provenance(_doc(data={"adjustment": "undeclared"}))
    assert "price basis is not declared" in h
    assert "unattributable" in h


def test_a_dirty_tree_is_surfaced_not_buried():
    """Measured: `code.dirty` was True on every run while this was written. A
    report produced from uncommitted code cannot be reproduced from the commit
    hash it prints, and a reader assumes it can unless told."""
    h = render_provenance(_doc(code={"dirty": True, "dirtyFileCount": 16}))
    assert "dirty working tree" in h
    assert "16 modified" in h
    assert "does NOT reproduce" in h


def test_a_clean_tree_gets_no_warning():
    """Negative control: a warning on every report is a warning nobody reads."""
    assert "dirty working tree" not in render_provenance(_doc())


def test_the_header_is_ascii():
    """cp1252 consoles cannot encode an em-dash. The TITLE may carry one because
    it is supplied by the caller and written to a UTF-8 file; the generated
    fields may not."""
    h = render_provenance(_doc())
    bad = sorted({c for c in h if ord(c) > 127})
    assert not bad, bad


def test_a_long_hash_is_shortened_but_still_identifies_the_corpus():
    h = render_provenance(_doc())
    assert "b" * 64 not in h, "the full 64-char hash is unreadable in a table"
    assert "sha256:bbbbbbbbbbbb" in h, "12 hex digits still identify the corpus"


# --------------------------------------------------------------------------- #
# Rule 2 -- refuse to exist when there is nothing to say
# --------------------------------------------------------------------------- #

def test_a_stub_is_refused_rather_than_written(tmp_path):
    """The motivating evidence: a 2-byte file containing `ok`, produced by a
    strategy that emitted no signals, which read as a report.

    ⚠️ THIS TEST FOUND THE CHECK IT GUARDS BEING VACUOUS. The first version of
    `write_report` compared the WHOLE FILE against 200 bytes, and the provenance
    header alone is ~600 -- so the refusal could never fire. It now measures the
    BODY.
    """
    with pytest.raises(UnattributableReport) as e:
        write_report(tmp_path / "r.md", "ok", _doc())
    assert "stub, not a report" in str(e.value)
    assert "refuse_empty" in str(e.value), (
        "the refusal must name the alternative, or the caller's next move is to "
        "pad the body until it passes")
    assert not (tmp_path / "r.md").exists(), "and it must not have been written"


def test_whitespace_is_not_content(tmp_path):
    """A body of newlines clears any byte threshold and says nothing."""
    with pytest.raises(UnattributableReport):
        write_report(tmp_path / "r.md", "\n\n   \n\t\n" * 20, _doc())


def test_the_smallest_LEGITIMATE_body_is_accepted(tmp_path):
    """THE OTHER END OF THE BAND. A named refusal is the smallest thing a report
    is allowed to say, so if the threshold rejected it the rule would forbid its
    own remedy. Both ends asserted, because a floor with only one side tested is
    a floor at an unknown height."""
    body = refuse_empty(False, "Where to cap trades",
                        "the trade frame carries no P&L column")
    assert body is not None
    p = write_report(tmp_path / "r.md", body, _doc())
    assert "Not available" in p.read_text(encoding="utf-8")


def test_a_real_report_is_written_with_its_header_prepended(tmp_path):
    body = ("## Body\n\nSomething to say, at the length a real report says it.\n"
            "\n| Metric | Value |\n|---|---|\n| EV | $6.98 |\n")
    p = write_report(tmp_path / "r.md", body, _doc(), title="T")
    text = p.read_text(encoding="utf-8")
    assert text.startswith(PROVENANCE_MARKER)
    assert "Something to say" in text
    assert "# T" in text


def test_refuse_empty_returns_a_named_reason_not_a_blank(tmp_path):
    """A section that vanishes is indistinguishable from one never asked for."""
    assert refuse_empty(True, "X", "why") is None
    out = refuse_empty(False, "Where to cap", "no trades")
    assert "Not available" in out and "no trades" in out


# --------------------------------------------------------------------------- #
# The audit -- and the four reachable reds
# --------------------------------------------------------------------------- #

def _run_dir(tmp_path, **files):
    arts = {}
    for key, body in files.items():
        p = tmp_path / "{}.md".format(key)
        p.write_text(body, encoding="utf-8")
        arts[key] = str(p)
    return _doc(artifacts=arts)


def test_a_run_whose_reports_carry_the_header_passes(tmp_path):
    body = PROVENANCE_MARKER + "\n" + "x" * (MIN_REPORT_BYTES + 50)
    v = audit_reports(_run_dir(tmp_path, tearsheet=body))
    assert v["ok"] is True
    assert v["checked"] == ["tearsheet"]


def test_red_1_a_report_without_the_header_fails(tmp_path):
    v = audit_reports(_run_dir(tmp_path, tearsheet="x" * (MIN_REPORT_BYTES + 50)))
    assert v["ok"] is False
    assert "no provenance header" in v["reason"]


def test_red_2_a_recorded_report_that_is_not_on_disk_fails(tmp_path):
    d = _doc(artifacts={"tearsheet": str(tmp_path / "gone.md")})
    v = audit_reports(d)
    assert v["ok"] is False
    assert "not on disk" in v["reason"]


def test_red_3_a_stub_on_disk_fails(tmp_path):
    v = audit_reports(_run_dir(tmp_path, tearsheet=PROVENANCE_MARKER))
    assert v["ok"] is False
    assert "stub not a report" in v["reason"]


def test_red_4_zero_reports_is_not_a_pass():
    """THE ONE MOST LIKELY TO BE MISSED. `not problems` over an empty set is
    True, and a run that produced no reports would then be reported as one
    whose every report is attributable -- a green with no reachable red, which
    is the defect this whole criterion replaced."""
    v = audit_reports(_doc(artifacts={}))
    assert v["ok"] is False
    assert "nothing to attribute" in v["reason"]
    assert "NOT a pass" in v["reason"]


def test_a_data_artifact_is_not_audited_as_a_report():
    """A CSV cannot carry a Markdown header, and `pythonTrades` /
    `decisionLog` are attributed by the record that names them and by their own
    columns. Auditing them would force a false red."""
    assert "pythonTrades" not in REPORT_ARTIFACTS
    assert "decisionLog" not in REPORT_ARTIFACTS
    v = audit_reports(_doc(artifacts={"pythonTrades": "/nope.csv"}))
    assert v["checked"] == []


# --------------------------------------------------------------------------- #
# The criterion is wired, and is no longer a constant
# --------------------------------------------------------------------------- #

def test_the_criterion_is_not_hardcoded_any_more():
    """It set NOT EVALUATED with a fixed string on every run for the whole life
    of the framework, which made `validated` unreachable."""
    src = (REPO / "scripts" / "trading_framework" / "workflow.py").read_text(
        encoding="utf-8")
    assert "_reports_attributed(ctx, doc)" in src
    assert "section 7.3 not built" not in src, (
        "the placeholder string is still present -- the criterion is still a "
        "constant somewhere")


def test_the_criterion_can_return_both_answers():
    """Drives the real function both ways. A criterion whose red is unreachable
    is what this replaced, so proving the red exists IS the test."""
    from scripts.trading_framework.workflow import Checklist, _reports_attributed

    class _Ctx:
        def __init__(self):
            self.check = Checklist()

    ok_body = PROVENANCE_MARKER + "\n" + "x" * (MIN_REPORT_BYTES + 50)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "t.md"
        p.write_text(ok_body, encoding="utf-8")

        c = _Ctx()
        _reports_attributed(c, _doc(artifacts={"tearsheet": str(p)}))
        assert c.check.items["reports_attributed"].status == "PASS"

        c = _Ctx()
        _reports_attributed(c, _doc(artifacts={}))
        assert c.check.items["reports_attributed"].status == "FAIL"


def test_the_live_run_directory_reports_are_attributed():
    """Against the newest real run, not a fixture. A unit test that passes while
    the pipeline writes unattributed files would be the wrong kind of green."""
    runs = sorted((REPO / "results" / "RESEARCH" / "_workflow").rglob("run_record.json"),
                  key=lambda p: p.stat().st_mtime)
    if not runs:
        pytest.skip("no run records on this machine")
    doc = json.loads(runs[-1].read_text(encoding="utf-8"))
    v = audit_reports(doc)
    assert v["ok"] is True, (
        "the most recent workflow run wrote reports that do not name their "
        "inputs: {}".format(v["reason"]))
