"""Tests for the F-6 RiskGuard alert relay.

⚠️ THE HAPPY PATH IS THE LEAST INTERESTING THING HERE. A relay that delivers a message is
easy; what makes this component trustworthy is that it cannot fail SILENTLY, because the
whole architecture (guard decides, separate process delivers) buys safety in the NT8
process at the cost of a new way to go quiet. So most of these assert on the quiet
failures: a cursor past a truncated file, a torn line, a dead destination, a poisoned
alert wedging the queue, and a heartbeat that could never report anything bad.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.riskguard.alert_relay import (
    NOT_IMPLEMENTED_CHANNELS,
    deliver,
    format_alert,
    format_heartbeat,
    read_cursor,
    read_new_alerts,
    resolve_channel,
    run,
    write_cursor,
)


def _write_outbox(path: Path, alerts: list[dict]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for a in alerts:
            f.write(json.dumps(a) + "\n")


def _alert(event="DAILY_LOSS_BREACH", title=None, body="account: Sim101"):
    # The title DERIVES from the event unless overridden -- an earlier version pinned a
    # constant title, so a test asserting the event name appeared in the delivered text was
    # asserting on a string the renderer never produced.
    return {"timestamp_utc": "2026-08-15T20:00:00Z", "account": "Sim101",
            "eventType": event, "severity": "critical",
            "title": title if title is not None else f"🚨 {event}", "body": body}


class TestReadNewAlerts:
    def test_reads_only_what_is_new(self, tmp_path: Path) -> None:
        outbox = tmp_path / "alerts_outbox.jsonl"
        cursor = tmp_path / "cursor.json"
        _write_outbox(outbox, [_alert(), _alert("ORPHAN_STOP")])

        alerts, offset = read_new_alerts(outbox, cursor)
        assert len(alerts) == 2
        write_cursor(cursor, offset)

        # NEGATIVE CONTROL: a second read with nothing appended returns nothing. Without
        # this, "reads only what is new" passes for a relay that re-sends the whole file
        # every poll -- which would spam the channel on a timer.
        again, _ = read_new_alerts(outbox, cursor)
        assert again == []

        _write_outbox(outbox, [_alert("NAKED_POSITION")])
        third, _ = read_new_alerts(outbox, cursor)
        assert len(third) == 1
        assert third[0]["eventType"] == "NAKED_POSITION"

    def test_a_truncated_outbox_resets_the_cursor(self, tmp_path: Path) -> None:
        """⚠️ THE SILENT-SKIP CASE, and the reason this branch exists.

        The outbox is append-only in normal operation, but it can be rotated or deleted.
        A cursor left pointing past the end of a now-shorter file would make the relay
        skip every future alert while reporting itself perfectly healthy -- indefinitely.
        """
        outbox = tmp_path / "alerts_outbox.jsonl"
        cursor = tmp_path / "cursor.json"
        _write_outbox(outbox, [_alert() for _ in range(5)])
        _, offset = read_new_alerts(outbox, cursor)
        write_cursor(cursor, offset)

        outbox.write_text("", encoding="utf-8")          # rotated
        _write_outbox(outbox, [_alert("AFTER_ROTATION")])

        alerts, _ = read_new_alerts(outbox, cursor)
        assert len(alerts) == 1
        assert alerts[0]["eventType"] == "AFTER_ROTATION"

    def test_a_torn_final_line_is_re_read_not_skipped(self, tmp_path: Path) -> None:
        """Reading mid-append must not half-deliver and then skip the line."""
        outbox = tmp_path / "alerts_outbox.jsonl"
        cursor = tmp_path / "cursor.json"
        _write_outbox(outbox, [_alert("COMPLETE")])
        with open(outbox, "a", encoding="utf-8") as f:
            f.write('{"eventType": "TOR')       # torn, no newline

        alerts, offset = read_new_alerts(outbox, cursor)
        assert [a["eventType"] for a in alerts] == ["COMPLETE"]
        write_cursor(cursor, offset)

        # Now the writer finishes the line.
        with open(outbox, "a", encoding="utf-8") as f:
            f.write('N", "title": "t", "body": "b"}\n')

        rest, _ = read_new_alerts(outbox, cursor)
        assert [a["eventType"] for a in rest] == ["TORN"]

    def test_a_utf8_bom_on_the_first_line_does_not_lose_that_alert(self, tmp_path: Path) -> None:
        """⚠️ MEASURED LIVE, and it cost the first alert of the first outbox.

        The guard wrote the file with .NET's ``Encoding.UTF8``, which emits ``EF BB BF``
        when it CREATES a file. ``json.loads`` refuses a line with a BOM prefix, so the
        first record of every new outbox was dropped -- and the first record is, by
        construction, the one announcing that something began going wrong.

        The producer now writes ``UTF8Encoding(false)``. This stays regardless: files
        written by the old build exist on disk, and a consumer that only works against a
        corrected producer would silently drop their first line forever.
        """
        outbox = tmp_path / "alerts_outbox.jsonl"
        with open(outbox, "wb") as f:
            f.write(b"\xef\xbb\xbf" + json.dumps(_alert("FIRST")).encode("utf-8") + b"\n")
            f.write(json.dumps(_alert("SECOND")).encode("utf-8") + b"\n")

        alerts, _ = read_new_alerts(outbox, tmp_path / "c.json")
        assert [a["eventType"] for a in alerts] == ["FIRST", "SECOND"]

    def test_a_missing_outbox_is_not_an_error(self, tmp_path: Path) -> None:
        alerts, offset = read_new_alerts(tmp_path / "nope.jsonl", tmp_path / "c.json")
        assert alerts == [] and offset == 0

    def test_an_unreadable_cursor_starts_from_zero(self, tmp_path: Path) -> None:
        cursor = tmp_path / "cursor.json"
        cursor.write_text("not json", encoding="utf-8")
        assert read_cursor(cursor) == 0


class TestDelivery:
    def test_counts_only_confirmed_deliveries(self) -> None:
        """⚠️ P1-105 by another name: report the OUTCOME, not the call."""
        results = iter([True, False, True])
        sent = deliver(["a", "b", "c"], webhook_url="u",
                       sender=lambda url, msg: next(results))
        assert sent == 2, "a sender that returned False must not be counted as delivered"

    def test_a_raising_sender_does_not_kill_the_relay(self) -> None:
        def boom(url, msg):
            raise RuntimeError("network down")

        assert deliver(["a", "b"], webhook_url="u", sender=boom) == 0

    def test_a_failed_send_does_not_wedge_the_queue(self, tmp_path: Path, monkeypatch) -> None:
        """⚠️ ONE POISONED ALERT MUST NOT BECOME TOTAL SILENCE.

        The cursor advances even when a POST fails. Holding it back to retry would convert
        a single lost message into a permanently stuck relay -- trading one missed alert
        for every future one.
        """
        outbox = tmp_path / "alerts_outbox.jsonl"
        _write_outbox(outbox, [_alert("FAILS")])
        sent: list[str] = []

        run(guard_dir=tmp_path, webhook_key="k", once=True, webhook_url="u",
            sender=lambda url, msg: (sent.append(msg), False)[1])

        _write_outbox(outbox, [_alert("SUCCEEDS")])
        run(guard_dir=tmp_path, webhook_key="k", once=True, webhook_url="u",
            sender=lambda url, msg: (sent.append(msg), True)[1])

        joined = " ".join(sent)
        assert "SUCCEEDS" in joined, "the alert after a failed one must still be delivered"


class TestHeartbeat:
    def test_reports_the_guard_as_stale_when_it_is(self, tmp_path: Path) -> None:
        """⚠️ A GREEN THAT CAN NEVER BE RED IS NOT A MEASUREMENT.

        `nt_health`'s `feedConnected` was `Account.All.Count > 0`, so it was true on every
        box forever. This asserts the heartbeat reaches the bad state on real input.
        """
        hb = tmp_path / "heartbeat.txt"
        hb.write_text("2026-08-15T10:00:00Z", encoding="utf-8")
        import os
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()
        os.utime(hb, (old, old))

        msg = format_heartbeat(tmp_path, delivered=0)
        assert "STALE" in msg

    def test_reports_the_guard_as_alive_when_fresh(self, tmp_path: Path) -> None:
        """The negative control -- otherwise 'reports STALE' passes for a constant."""
        (tmp_path / "heartbeat.txt").write_text("now", encoding="utf-8")
        msg = format_heartbeat(tmp_path, delivered=3)
        assert "STALE" not in msg and "alive" in msg
        assert "3 alert(s) delivered" in msg

    def test_a_missing_heartbeat_file_is_reported_not_hidden(self, tmp_path: Path) -> None:
        assert "UNKNOWN" in format_heartbeat(tmp_path, delivered=0)


class TestTransportRefusals:
    def test_telegram_is_refused_by_name(self) -> None:
        """Advertising a transport that does nothing is P1-72, which regressed twice."""
        with pytest.raises(NotImplementedError) as exc:
            resolve_channel("telegram")
        assert "NOT_IMPLEMENTED" in str(exc.value)

    def test_an_unknown_transport_names_the_real_ones(self) -> None:
        with pytest.raises(ValueError) as exc:
            resolve_channel("carrier-pigeon")
        assert "discord" in str(exc.value)
        assert "telegram" in str(exc.value), "the refusal lists what exists but is unimplemented"

    def test_discord_is_accepted(self) -> None:
        resolve_channel("discord")   # must not raise


class TestRefusalToStart:
    def test_no_webhook_url_refuses_rather_than_running_silently(self, tmp_path: Path, monkeypatch) -> None:
        """⚠️ A relay with no destination is indistinguishable from a working one."""
        monkeypatch.setattr(
            "scripts.libs_py.discord.load_webhook_url", lambda *a, **k: None
        )
        with pytest.raises(SystemExit) as exc:
            run(guard_dir=tmp_path, webhook_key="nope", once=True)
        assert "Refusing to start" in str(exc.value)


class TestFormatting:
    def test_the_relay_adds_no_policy_of_its_own(self) -> None:
        """The guard already decided. A second opinion here is a second reader."""
        a = _alert(title="⚠ [WOULD] DAILY_LOSS_BREACH", body="account: Sim101\nmode: shadow")
        out = format_alert(a)
        assert "[WOULD]" in out, "the guard's honesty marker survives to the phone"
        assert "Sim101" in out

    def test_a_malformed_alert_still_renders(self) -> None:
        assert format_alert({}) != ""
