"""Acceptance tests for the trade-set parity harness.

THE LOAD-BEARING TEST is `test_surplus_nt8_trades_cannot_hide`. The harness this
replaces matched each Python trade to the nearest NT8 trade within +/-60s and
then scored agreement over the matched pairs, so a surplus on either side had no
counterpart and never entered a denominator. On its own corpus that reported
**97.9% agreement** against a real trade-set recall of **47/73**. Any replacement
must make that arrangement impossible, and the test asserts the numbers a
tolerance join would have produced are NOT what comes back.

Everything else here exists because a parity metric is a detector, and a detector
that cannot go red is decoration: there are tests for a perfect match (must be
PASS), a total mismatch (must be FAIL), and an empty-vs-empty comparison (must be
neither -- an empty set trivially matches an empty set, so that is VACUOUS).
"""
import json

import numpy as np
import pandas as pd
import pytest

from scripts.parity.trade_set_parity import (
    ParityInputError,
    assign_bars,
    compare_matched,
    format_report,
    match_trade_sets,
    normalise_direction,
    normalise_trades,
    run_parity,
    summary,
    verdict,
)

ET = "America/New_York"


def _trades(rows, tz=ET):
    """rows: (entry_iso, direction, entry, exit_price, pnl, reason)."""
    return pd.DataFrame({
        "entry_time": [pd.Timestamp(r[0], tz=tz) for r in rows],
        "exit_time": [pd.Timestamp(r[0], tz=tz) + pd.Timedelta(minutes=5) for r in rows],
        "direction": [r[1] for r in rows],
        "entry_price": [r[2] for r in rows],
        "exit_price": [r[3] for r in rows],
        "pnl": [r[4] for r in rows],
        "exit_reason": [r[5] for r in rows],
    })


def _pair(py_rows, nt8_rows, **kw):
    kw.setdefault("bar_seconds", 60)
    kw.setdefault("min_recall", 0.95)
    kw.setdefault("min_precision", 0.95)
    return run_parity(_trades(py_rows), _trades(nt8_rows), **kw)


# ==========================================================================
# THE defect the old harness had
# ==========================================================================
def test_surplus_nt8_trades_cannot_hide():
    """Python finds 2 of NT8's 5 trades, and agrees perfectly on those 2.

    A tolerance join reports "100% agreement" here, because the 3 NT8 trades
    with no Python counterpart are never compared to anything. Recall must
    expose them.
    """
    py = [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "Profit Target"),
          ("2026-01-05 10:31", "long", 200.0, 205.0, 500.0, "Profit Target")]
    nt8 = py + [
        ("2026-01-05 11:31", "long", 300.0, 295.0, -500.0, "Stop Loss"),
        ("2026-01-05 12:31", "long", 310.0, 305.0, -500.0, "Stop Loss"),
        ("2026-01-05 13:31", "long", 320.0, 315.0, -500.0, "Stop Loss")]

    r = _pair(py, nt8)
    s = r["summary"]

    assert s["matched"] == 2
    assert s["nt8_only"] == 3
    assert s["python_only"] == 0
    assert s["recall"] == pytest.approx(2 / 5)
    assert s["precision"] == pytest.approx(1.0)
    assert s["jaccard"] == pytest.approx(2 / 5)

    # matched-pair agreement IS perfect -- and that is exactly the number the
    # old harness reported as the headline
    assert s["matched_entry_price_ok"] == pytest.approx(1.0)
    assert s["matched_pnl_sign_ok"] == pytest.approx(1.0)

    # ...and it must not be enough to pass
    assert r["verdict"]["verdict"] == "FAIL"
    assert any("missed 3 of NT8's 5" in x for x in r["verdict"]["reasons"])


def test_summary_exposes_no_single_headline_agreement_figure():
    """A consumer able to quote one number will quote the flattering one."""
    r = _pair([("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")],
              [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")])
    for banned in ("agreement_pct", "agreement", "accuracy", "match_pct"):
        assert banned not in r["summary"], banned
    assert {"recall", "precision", "jaccard"} <= set(r["summary"])


def test_surplus_python_trades_are_penalised_too():
    """Invented trades are as disqualifying as missed ones, in the other index."""
    nt8 = [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")]
    py = nt8 + [("2026-01-05 10:31", "short", 200.0, 195.0, 500.0, "PT"),
                ("2026-01-05 11:31", "short", 210.0, 205.0, 500.0, "PT")]
    r = _pair(py, nt8)
    s = r["summary"]
    assert s["recall"] == pytest.approx(1.0)
    assert s["precision"] == pytest.approx(1 / 3)
    assert s["python_only"] == 2
    assert r["verdict"]["verdict"] == "FAIL"
    assert any("took 2 trades NT8 did not" in x for x in r["verdict"]["reasons"])


# ==========================================================================
# The verdict must reach every state
# ==========================================================================
def test_identical_trade_sets_pass():
    rows = [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT"),
            ("2026-01-06 09:45", "short", 200.0, 195.0, 500.0, "PT")]
    r = _pair(rows, rows)
    assert r["verdict"]["verdict"] == "PASS"
    assert r["verdict"]["reasons"] == []
    assert r["summary"]["jaccard"] == pytest.approx(1.0)


def test_disjoint_trade_sets_fail():
    py = [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")]
    nt8 = [("2026-03-05 14:00", "short", 300.0, 295.0, 500.0, "PT")]
    r = _pair(py, nt8)
    assert r["summary"]["matched"] == 0
    assert r["summary"]["jaccard"] == pytest.approx(0.0)
    assert r["verdict"]["verdict"] == "FAIL"


def test_two_empty_sets_are_vacuous_not_a_pass():
    """An empty set matches an empty set. That proves nothing.

    Same family as a gate whose `All` over an empty sequence returns true --
    the state has to be nameable so it cannot be banked as evidence.
    """
    empty = pd.DataFrame(columns=["entry_time", "direction", "entry_price",
                                  "exit_price", "pnl", "exit_reason"])
    r = run_parity(empty, empty, bar_seconds=60, min_recall=0.95,
                   min_precision=0.95)
    assert r["verdict"]["verdict"] == "VACUOUS"
    assert "UNTESTED, not proven" in r["verdict"]["reasons"][0]


def test_python_silent_while_nt8_trades_is_a_failure_not_vacuous():
    empty = pd.DataFrame(columns=["entry_time", "direction", "entry_price",
                                  "exit_price", "pnl", "exit_reason"])
    nt8 = _trades([("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")])
    r = run_parity(empty, nt8, bar_seconds=60, min_recall=0.95, min_precision=0.95)
    assert r["verdict"]["verdict"] == "FAIL"
    assert any("Python produced no trades" in x for x in r["verdict"]["reasons"])


def test_thresholds_are_required_and_recorded():
    """No default thresholds: a default becomes the standard by accident."""
    with pytest.raises(TypeError):
        verdict({"nt8_trades": 1, "python_trades": 1, "recall": 1.0,
                 "precision": 1.0, "matched_pnl_sign_ok": 1.0,
                 "nt8_only": 0, "python_only": 0})
    r = _pair([("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")],
              [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")],
              min_recall=0.8, min_precision=0.7)
    assert r["verdict"]["thresholds"]["min_recall"] == 0.8
    assert r["verdict"]["thresholds"]["min_precision"] == 0.7


def test_a_matched_pnl_sign_flip_fails_even_at_perfect_recall():
    """Same trades, opposite outcomes. Recall and precision are both 1.0."""
    py = [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "Profit Target")]
    nt8 = [("2026-01-05 09:31", "long", 100.0, 95.0, -500.0, "Stop Loss")]
    r = _pair(py, nt8)
    s = r["summary"]
    assert s["recall"] == pytest.approx(1.0)
    assert s["precision"] == pytest.approx(1.0)
    assert s["matched_pnl_sign_ok"] == pytest.approx(0.0)
    assert r["verdict"]["verdict"] == "FAIL"
    assert any("win/loss SIGN" in x for x in r["verdict"]["reasons"])


# ==========================================================================
# The join key
# ==========================================================================
def test_same_bar_different_direction_does_not_match():
    py = [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")]
    nt8 = [("2026-01-05 09:31", "short", 100.0, 95.0, 500.0, "PT")]
    r = _pair(py, nt8)
    assert r["summary"]["matched"] == 0


def test_entries_within_one_bar_match_despite_differing_seconds():
    """Both engines place the trade in the 09:31 bar; the seconds differ."""
    py = [("2026-01-05 09:31:00", "long", 100.0, 105.0, 500.0, "PT")]
    nt8 = [("2026-01-05 09:31:47", "long", 100.0, 105.0, 500.0, "PT")]
    r = _pair(py, nt8, bar_seconds=60)
    assert r["summary"]["matched"] == 1


def test_adjacent_bars_do_not_match():
    """A tolerance join with +/-60s would pair these. A bar join must not."""
    py = [("2026-01-05 09:31:59", "long", 100.0, 105.0, 500.0, "PT")]
    nt8 = [("2026-01-05 09:32:01", "long", 100.0, 105.0, 500.0, "PT")]
    r = _pair(py, nt8, bar_seconds=60)
    assert r["summary"]["matched"] == 0
    assert r["summary"]["python_only"] == 1
    assert r["summary"]["nt8_only"] == 1


def test_bars_are_floored_not_rounded():
    """09:31:59 belongs to the 09:31 bar; rounding would move it to 09:32 and
    manufacture a mismatch against an engine that floors."""
    t = _trades([("2026-01-05 09:31:59", "long", 100.0, 105.0, 500.0, "PT")])
    n = normalise_trades(t, label="x")
    b = assign_bars(n, 60)
    assert b["entry_bar"].iloc[0] == pd.Timestamp("2026-01-05 09:31", tz=ET).tz_convert("UTC")


def test_multiple_occurrences_in_one_bar_zip_and_surplus_remains():
    """NT8 re-entry inside a single bar is real; the extra must stay unmatched."""
    py = [("2026-01-05 09:31:10", "long", 100.0, 105.0, 500.0, "PT")]
    nt8 = [("2026-01-05 09:31:10", "long", 100.0, 105.0, 500.0, "PT"),
           ("2026-01-05 09:31:40", "long", 101.0, 106.0, 500.0, "PT")]
    r = _pair(py, nt8, bar_seconds=300)
    assert r["summary"]["matched"] == 1
    assert r["summary"]["nt8_only"] == 1
    assert r["summary"]["recall"] == pytest.approx(0.5)


def test_bar_seconds_must_be_declared_and_positive():
    t = normalise_trades(_trades([("2026-01-05 09:31", "long", 1.0, 1.0, 0.0, "x")]),
                         label="x")
    with pytest.raises(ParityInputError, match="bar_seconds must be positive"):
        assign_bars(t, 0)


def test_bar_length_changes_the_answer_so_it_cannot_be_guessed():
    """The same two trades match at 5m and not at 1m. This is why the harness
    demands `bar_seconds` instead of inferring it."""
    py = [("2026-01-05 09:31:00", "long", 100.0, 105.0, 500.0, "PT")]
    nt8 = [("2026-01-05 09:33:00", "long", 100.0, 105.0, 500.0, "PT")]
    assert _pair(py, nt8, bar_seconds=60)["summary"]["matched"] == 0
    assert _pair(py, nt8, bar_seconds=300)["summary"]["matched"] == 1


# ==========================================================================
# Input normalisation: refuse rather than guess
# ==========================================================================
def test_naive_timestamps_are_refused_without_an_explicit_zone():
    """NT8 SA exports ET-naive. Reading them as UTC shifts every trade 4-5h."""
    df = pd.DataFrame({"entry_time": ["2026-01-05 09:31:00"], "direction": ["long"],
                       "entry_price": [100.0], "exit_price": [105.0],
                       "pnl": [500.0], "exit_reason": ["PT"]})
    with pytest.raises(ParityInputError, match="TIMEZONE-NAIVE"):
        normalise_trades(df, label="nt8")
    ok = normalise_trades(df, label="nt8", assume_tz=ET)
    assert ok["entry_time"].iloc[0] == pd.Timestamp("2026-01-05 09:31", tz=ET)


def test_the_utc_misreading_would_have_destroyed_the_match():
    """Pins WHY naive input is refused rather than defaulted."""
    naive = pd.DataFrame({"entry_time": ["2026-01-05 09:31:00"], "direction": ["long"],
                          "entry_price": [100.0], "exit_price": [105.0],
                          "pnl": [500.0], "exit_reason": ["PT"]})
    right = normalise_trades(naive, label="nt8", assume_tz=ET)
    wrong = normalise_trades(naive, label="nt8", assume_tz="UTC")
    delta = abs((right["entry_time"].iloc[0] - wrong["entry_time"].iloc[0]).total_seconds())
    assert delta >= 4 * 3600


def test_pascal_and_camel_case_nt8_exports_are_understood():
    df = pd.DataFrame({"EntryTime": [pd.Timestamp("2026-01-05 09:31", tz=ET)],
                       "ExitTime": [pd.Timestamp("2026-01-05 09:36", tz=ET)],
                       "MarketPosition": ["Long"], "EntryPrice": [100.0],
                       "ExitPrice": [105.0], "ProfitCurrency": [500.0],
                       "ExitName": ["Profit target"]})
    n = normalise_trades(df, label="nt8")
    assert n["direction"].iloc[0] == "long"
    assert n["pnl"].iloc[0] == 500.0


def test_missing_join_key_columns_are_refused_by_name():
    df = pd.DataFrame({"entry_price": [100.0], "pnl": [1.0]})
    with pytest.raises(ParityInputError, match="JOIN KEY"):
        normalise_trades(df, label="python")


def test_direction_spellings_and_the_ones_that_are_refused():
    assert list(normalise_direction(["Long", "BUY", "1", "short", "Sell", "-1"])) == \
        ["long", "long", "long", "short", "short", "short"]
    with pytest.raises(ParityInputError, match="unreadable direction"):
        normalise_direction(["flat"])
    with pytest.raises(ParityInputError, match="unreadable direction"):
        normalise_direction([None])


def test_unparseable_timestamps_are_refused():
    df = pd.DataFrame({"entry_time": ["not a date"], "direction": ["long"],
                       "entry_price": [1.0], "exit_price": [1.0], "pnl": [0.0],
                       "exit_reason": ["x"]})
    with pytest.raises(ParityInputError, match="could not be parsed"):
        normalise_trades(df, label="nt8", assume_tz=ET)


# ==========================================================================
# Reporting
# ==========================================================================
def test_report_names_recall_before_matched_agreement():
    """Ordering is load-bearing: the matched-pair figure is the one that misleads
    when read first."""
    py = [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")]
    nt8 = py + [("2026-01-05 10:31", "long", 200.0, 195.0, -500.0, "SL")]
    txt = format_report(_pair(py, nt8))
    assert txt.index("recall") < txt.index("matched_entry_price_ok")
    assert "meaningless without recall" in txt


def test_report_lists_the_worst_matched_disagreements():
    py = [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "Profit Target")]
    nt8 = [("2026-01-05 09:31", "long", 100.0, 95.0, -500.0, "Stop Loss")]
    txt = format_report(_pair(py, nt8))
    assert "worst matched disagreements" in txt
    assert "Stop Loss" in txt


def test_price_tolerance_is_applied_and_reported():
    py = [("2026-01-05 09:31", "long", 100.00, 105.0, 500.0, "PT")]
    nt8 = [("2026-01-05 09:31", "long", 100.20, 105.0, 500.0, "PT")]
    loose = _pair(py, nt8, price_tol=0.25)
    tight = _pair(py, nt8, price_tol=0.10)
    assert loose["summary"]["matched_entry_price_ok"] == pytest.approx(1.0)
    assert tight["summary"]["matched_entry_price_ok"] == pytest.approx(0.0)
    assert loose["tolerances"]["price_tol"] == 0.25


def test_summary_is_json_serialisable_for_a_run_record():
    r = _pair([("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")],
              [("2026-01-05 09:31", "long", 100.0, 105.0, 500.0, "PT")])
    blob = json.dumps({"summary": r["summary"], "verdict": r["verdict"]},
                      default=str)
    assert json.loads(blob)["verdict"]["verdict"] == "PASS"


# ==========================================================================
# Against a REAL NT8 payload, not an invented schema
# ==========================================================================
FIXTURE = ("scripts/parity/fixtures/"
           "nt8_trades_BollingerCrossOver_ES_15m_2026-07-01_2026-07-10.csv")


def _real_nt8():
    return pd.read_csv(FIXTURE)


def test_real_nt8_export_normalises_without_alias_guessing():
    """The alias table was written BEFORE this capture; this is what confirms it.

    Captured from a live Strategy Analyzer run: 47 trades, NT8's own field names
    (marketPosition / entryPrice / profitCurrency / exitName) and its own
    ET-naive timestamps.
    """
    n = normalise_trades(_real_nt8(), label="nt8", assume_tz=ET)
    assert len(n) == 47
    assert set(n["direction"]) == {"long", "short"}
    assert n["entry_time"].dt.tz is not None
    assert n["entry_price"].notna().all()
    assert n["pnl"].notna().all()
    # NT8's reported net, reproduced from the per-trade records
    assert n["pnl"].sum() == pytest.approx(-4375.0, abs=0.01)
    assert (n["pnl"] > 0).sum() == 27
    assert (n["pnl"] < 0).sum() == 20


def test_real_nt8_export_is_refused_without_a_declared_zone():
    """These timestamps really are naive; the refusal is not hypothetical."""
    with pytest.raises(ParityInputError, match="TIMEZONE-NAIVE"):
        normalise_trades(_real_nt8(), label="nt8")


def test_a_trade_set_is_in_perfect_parity_with_itself():
    """Control at real scale: 47 real trades against themselves must PASS.

    If the join key were too strict -- say it included exit price or a raw
    timestamp -- this would fail, and a harness that cannot recognise identity
    can never certify parity.
    """
    real = _real_nt8()
    r = run_parity(real, real, bar_seconds=900, min_recall=1.0,
                   min_precision=1.0, assume_tz_python=ET, assume_tz_nt8=ET)
    s = r["summary"]
    assert s["matched"] == 47
    assert s["python_only"] == 0 and s["nt8_only"] == 0
    assert s["recall"] == pytest.approx(1.0)
    assert s["jaccard"] == pytest.approx(1.0)
    assert r["verdict"]["verdict"] == "PASS"


def test_the_old_harnesses_failure_reproduced_at_full_scale():
    """47 of 73 recall with perfect matched agreement -- the reported shape.

    The IB harness reported 97.9% agreement on a corpus where Python had found
    47 of NT8's 73 trades. Reconstructed here at that magnitude: keep 47 real
    NT8 trades as the Python side, add 26 more as NT8-only. Matched agreement is
    perfect and the verdict must still be FAIL.
    """
    real = normalise_trades(_real_nt8(), label="nt8", assume_tz=ET)
    py_side = real.iloc[:47].copy()
    # 26 extra NT8 trades in bars the Python side does not occupy
    extra = real.iloc[:26].copy()
    extra["entry_time"] = extra["entry_time"] + pd.Timedelta(days=400)
    extra["exit_time"] = extra["exit_time"] + pd.Timedelta(days=400)
    nt8_side = pd.concat([real, extra], ignore_index=True)

    m = match_trade_sets(py_side, nt8_side, 900)
    s = summary(m, compare_matched(m))
    v = verdict(s, min_recall=0.95, min_precision=0.95)

    assert s["python_trades"] == 47
    assert s["nt8_trades"] == 73
    assert s["matched"] == 47
    assert s["nt8_only"] == 26
    assert s["recall"] == pytest.approx(47 / 73, abs=1e-6)
    # the flattering figure the old harness reported
    assert s["matched_entry_price_ok"] == pytest.approx(1.0)
    assert s["matched_pnl_sign_ok"] == pytest.approx(1.0)
    # and the verdict that must follow anyway
    assert v["verdict"] == "FAIL"
    assert any("missed 26 of NT8's 73" in x for x in v["reasons"])


def test_a_back_adjustment_price_shift_is_caught_on_matched_pairs():
    """Prices offset by a roll adjustment, same trades, same bars.

    This is the shape `GlobalMergePolicy = MergeBackAdjusted` produces against
    unadjusted Python data. Recall and precision stay perfect -- the TRADE SET is
    identical -- and the matched-pair price comparison is what has to catch it.
    """
    real = normalise_trades(_real_nt8(), label="nt8", assume_tz=ET)
    shifted = real.copy()
    shifted["entry_price"] = shifted["entry_price"] - 292.0
    shifted["exit_price"] = shifted["exit_price"] - 292.0

    m = match_trade_sets(shifted, real, 900)
    s = summary(m, compare_matched(m, price_tol=0.25))
    assert s["recall"] == pytest.approx(1.0)
    assert s["precision"] == pytest.approx(1.0)
    assert s["matched_entry_price_ok"] == pytest.approx(0.0)
    assert s["max_abs_entry_delta"] == pytest.approx(292.0)
    # P&L is unaffected by a constant shift, so the sign check passes -- which is
    # why price agreement is reported separately and not folded into one score.
    assert s["matched_pnl_sign_ok"] == pytest.approx(1.0)


# ==========================================================================
# GEOMETRY, not absolute price
#
# A strategy decides DISTANCES: where the stop sits relative to entry, how far
# the target is, how far price travelled before the exit. A constant price
# offset -- which is exactly what a back-adjusted continuous series is against
# an unadjusted one -- changes every absolute level and none of those distances.
# Failing such a run would report a bookkeeping difference as a logic defect.
# ==========================================================================
def test_a_constant_offset_passes_and_is_reported_as_a_note():
    """The whole trade set shifted by one roll adjustment. Same trades."""
    real = normalise_trades(_real_nt8(), label="nt8", assume_tz=ET)
    shifted = real.copy()
    shifted["entry_price"] = shifted["entry_price"] - 292.0
    shifted["exit_price"] = shifted["exit_price"] - 292.0

    m = match_trade_sets(shifted, real, 900)
    s = summary(m, compare_matched(m, price_tol=0.25))
    v = verdict(s, min_recall=1.0, min_precision=1.0)

    assert s["matched_geometry_ok"] == pytest.approx(1.0)
    assert s["max_abs_points_delta"] == pytest.approx(0.0)
    assert v["verdict"] == "PASS", v["reasons"]
    assert s["constant_price_offset"] == pytest.approx(-292.0)
    assert s["price_offset_spread"] == pytest.approx(0.0)
    assert any("adjustment-basis difference" in n for n in v["notes"])
    # the absolute-price diagnostic still records what happened
    assert s["matched_entry_price_ok"] == pytest.approx(0.0)


def test_a_real_geometry_divergence_still_fails():
    """Control: the offset tolerance must not swallow an actual difference.

    Same entries, but every exit 5 points further away -- the distance travelled
    genuinely differs, which no adjustment basis can explain.
    """
    real = normalise_trades(_real_nt8(), label="nt8", assume_tz=ET)
    moved = real.copy()
    sgn = np.where(moved["direction"] == "long", 1.0, -1.0)
    moved["exit_price"] = moved["exit_price"] + 5.0 * sgn

    m = match_trade_sets(moved, real, 900)
    s = summary(m, compare_matched(m, price_tol=0.25))
    v = verdict(s, min_recall=1.0, min_precision=1.0)

    assert s["recall"] == pytest.approx(1.0)
    assert s["matched_geometry_ok"] == pytest.approx(0.0)
    assert s["max_abs_points_delta"] == pytest.approx(5.0)
    assert v["verdict"] == "FAIL"
    assert any("agree on GEOMETRY" in r for r in v["reasons"])


def test_offset_plus_divergence_is_not_excused_by_the_offset():
    """A constant offset AND a real difference. The offset must not launder it."""
    real = normalise_trades(_real_nt8(), label="nt8", assume_tz=ET)
    both = real.copy()
    both["entry_price"] = both["entry_price"] - 292.0
    sgn = np.where(both["direction"] == "long", 1.0, -1.0)
    both["exit_price"] = both["exit_price"] - 292.0 + 5.0 * sgn

    m = match_trade_sets(both, real, 900)
    s = summary(m, compare_matched(m, price_tol=0.25))
    v = verdict(s, min_recall=1.0, min_precision=1.0)

    assert s["matched_geometry_ok"] == pytest.approx(0.0)
    assert v["verdict"] == "FAIL"


def test_scattered_price_differences_are_not_called_a_constant_offset():
    """Only a ZERO-spread difference is an adjustment basis. Noise is not."""
    real = normalise_trades(_real_nt8(), label="nt8", assume_tz=ET)
    noisy = real.copy()
    rng = np.random.default_rng(1)
    noisy["entry_price"] = noisy["entry_price"] + rng.normal(0, 3.0, len(noisy))

    m = match_trade_sets(noisy, real, 900)
    s = summary(m, compare_matched(m, price_tol=0.25))

    assert s["constant_price_offset"] is None
    assert s["price_offset_spread"] > 1.0


def test_geometry_is_direction_aware():
    """A short that made 10 points and a long that made 10 points both travelled
    +10 in strategy terms. Signing by direction is what makes the comparison
    mean the same thing on both sides."""
    py = [("2026-01-05 09:31", "short", 100.0, 90.0, 500.0, "PT")]
    nt8 = [("2026-01-05 09:31", "short", 100.0, 90.0, 500.0, "PT")]
    r = _pair(py, nt8)
    row = r["matched_detail"].iloc[0]
    assert row["py_points"] == pytest.approx(10.0)
    assert row["nt8_points"] == pytest.approx(10.0)
    assert row["geometry_ok"]


def test_report_puts_geometry_above_absolute_price():
    """Ordering is load-bearing: absolute price is the number that misleads under
    a constant offset, so it must not be read first."""
    real = _real_nt8()
    shifted = real.copy()
    shifted["entryPrice"] = shifted["entryPrice"] - 292.0
    shifted["exitPrice"] = shifted["exitPrice"] - 292.0
    txt = format_report(run_parity(shifted, real, bar_seconds=900, min_recall=1.0,
                                   min_precision=1.0, assume_tz_python=ET,
                                   assume_tz_nt8=ET))
    assert txt.index("GEOMETRY") < txt.index("ABSOLUTE PRICE")
    assert "THIS is judged" in txt
    assert "not behaviour" in txt
    assert "VERDICT: PASS" in txt
