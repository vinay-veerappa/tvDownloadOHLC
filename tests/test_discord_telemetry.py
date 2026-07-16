# filepath: tests/test_discord_telemetry.py
"""Tests for the Tier-3 additions to ``scripts.libs_py.discord``.

Tier 3 adds two capabilities to the Discord sub-package:

1. **Thread routing** — every public ``send_*`` function accepts
   ``thread_id`` and ``thread_name`` keyword arguments, which
   are injected into the JSON payload before POST.

2. **Rate-limit telemetry** — a new :class:`RateLimitTelemetry`
   class records per-attempt and per-retry events. A
   :class:`RecordingTelemetry` subclass captures events in a
   list for test assertions.

This file covers:
  - ``RateLimitTelemetry`` snapshot / summary / reset
  - ``RecordingTelemetry`` event capture
  - Telemetry wiring into ``send_payload`` (success, retry,
    failure, network error, embed fallback)
  - Telemetry wiring into ``send_embeds`` (per-batch)
  - Telemetry wiring into ``send_with_files`` (per-chunk)
  - Telemetry wiring into ``send_message``
  - Telemetry wiring into ``send_summary`` (per-chunk)
  - ``thread_id`` / ``thread_name`` injection across all
    5 send functions
  - Public API surface includes the Tier-3 symbols
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from scripts.libs_py import discord as discord_lib
from scripts.libs_py.discord import (
    RateLimitTelemetry,
    RecordingTelemetry,
    send_embeds,
    send_message,
    send_payload,
    send_summary,
    send_with_files,
)


# ---------------------------------------------------------------------------
# Helpers (Tier-3 specific)
# ---------------------------------------------------------------------------
class _RecordingSink:
    """Captures every (event, payload) tuple passed to the sink."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, event: str, payload: dict[str, Any]) -> None:
        self.calls.append((event, payload))


class _FakeResp:
    """A minimal Response-like object for testing."""

    def __init__(self, status: int, text: str = "", headers: dict | None = None) -> None:
        self.status_code = status
        self.text = text
        self.headers = headers or {}


class _Poster:
    """Records every POST and returns scripted responses in order.

    Each entry is either an int (status code) or a tuple
    ``(status, headers_dict)`` so we can test Retry-After
    header handling.
    """

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        url: str,
        *,
        json: Any = None,
        data: Any = None,
        files: Any = None,
        timeout: float = 10,
    ) -> _FakeResp:
        self.calls.append(
            {"url": url, "json": json, "data": data, "files": files, "timeout": timeout}
        )
        if not self.script:
            return _FakeResp(200)
        nxt = self.script.pop(0)
        if isinstance(nxt, tuple):
            status, headers = nxt
        else:
            status, headers = nxt, {}
        return _FakeResp(status, headers=headers)


def _write_webhooks(mapping: dict[str, str]) -> Path:
    """Write a temp webhooks file and return its path."""
    fd, name = tempfile.mkstemp(suffix=".json")
    import os
    os.close(fd)
    p = Path(name)
    p.write_text(json.dumps(mapping), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# RateLimitTelemetry unit tests
# ---------------------------------------------------------------------------
class TestRateLimitTelemetryUnit:
    def test_initial_state_is_zero(self) -> None:
        tel = RateLimitTelemetry()
        snap = tel.snapshot()
        assert snap["total_sends"] == 0
        assert snap["total_successes"] == 0
        assert snap["total_failures"] == 0
        assert snap["total_retries"] == 0
        assert snap["total_rate_limited"] == 0
        assert snap["total_5xx"] == 0
        assert snap["total_4xx"] == 0
        assert snap["total_network_errors"] == 0
        assert snap["total_backoff_seconds"] == 0.0
        assert snap["attempts_to_success"] == []
        assert snap["attempts_to_failure"] == []
        assert snap["status_counts"] == {}

    def test_reset_clears_state(self) -> None:
        tel = RateLimitTelemetry()
        tel.on_attempt("u", 200, 1)
        tel.on_success("u", 1)
        tel.reset()
        snap = tel.snapshot()
        assert snap["total_sends"] == 0
        assert snap["total_successes"] == 0

    def test_on_attempt_counts_429(self) -> None:
        tel = RateLimitTelemetry()
        tel.on_attempt("u", 429, 1)
        tel.on_attempt("u", 429, 2)
        assert tel.total_sends == 2
        assert tel.total_rate_limited == 2
        assert tel.status_counts[429] == 2

    def test_on_attempt_counts_5xx(self) -> None:
        tel = RateLimitTelemetry()
        tel.on_attempt("u", 500, 1)
        tel.on_attempt("u", 502, 1)
        tel.on_attempt("u", 503, 1)
        tel.on_attempt("u", 504, 1)
        assert tel.total_5xx == 4
        assert tel.status_counts[500] == 1
        assert tel.status_counts[504] == 1

    def test_on_attempt_counts_4xx_non_429(self) -> None:
        tel = RateLimitTelemetry()
        tel.on_attempt("u", 400, 1)
        tel.on_attempt("u", 401, 1)
        # 400 and 401 are 4xx, but not 429
        assert tel.total_4xx == 2
        assert tel.total_rate_limited == 0

    def test_on_attempt_with_none_status(self) -> None:
        tel = RateLimitTelemetry()
        tel.on_attempt("u", None, 1)
        assert tel.total_sends == 1
        assert tel.status_counts == {}

    def test_on_retry_scheduled_increments(self) -> None:
        tel = RateLimitTelemetry()
        tel.on_retry_scheduled("u", 1, 1.0, "429")
        tel.on_retry_scheduled("u", 2, 3.0, "5xx")
        tel.on_retry_scheduled("u", 3, 1.5, "network")
        assert tel.total_retries == 3
        assert tel.total_backoff_seconds == pytest.approx(5.5)

    def test_on_success_appends_attempts(self) -> None:
        tel = RateLimitTelemetry()
        tel.on_success("u", 1)
        tel.on_success("u", 3)
        assert tel.total_successes == 2
        assert tel.attempts_to_success == [1, 3]
        assert tel.snapshot()["avg_attempts_to_success"] == pytest.approx(2.0)

    def test_on_failure_appends_attempts(self) -> None:
        tel = RateLimitTelemetry()
        tel.on_failure("u", 500, 4, "500")
        tel.on_failure("u", None, 2, "network")
        assert tel.total_failures == 2
        assert tel.attempts_to_failure == [4, 2]

    def test_summary_is_one_line(self) -> None:
        tel = RateLimitTelemetry()
        tel.on_attempt("u", 200, 1)
        tel.on_success("u", 1)
        s = tel.summary()
        assert "sends=1" in s
        assert "success=1" in s
        assert "failure=0" in s
        assert "retry=0" in s

    def test_custom_sink_called(self) -> None:
        sink = _RecordingSink()
        tel = RateLimitTelemetry(sink=sink)
        tel.on_attempt("u", 200, 1)
        tel.on_success("u", 1)
        assert len(sink.calls) == 2
        assert sink.calls[0][0] == "attempt"
        assert sink.calls[1][0] == "success"

    def test_silent_sink_lambda(self) -> None:
        # Operators can pass a no-op to suppress log output.
        tel = RateLimitTelemetry(sink=lambda *_: None)
        tel.on_attempt("u", 200, 1)
        # No exception, counters still work.
        assert tel.total_sends == 1

    def test_url_label_applied(self) -> None:
        sink = _RecordingSink()
        tel = RateLimitTelemetry(
            sink=sink, url_label=lambda u: u.split("/")[-1]
        )
        tel.on_attempt("https://example.invalid/hook/abc", 200, 1)
        assert sink.calls[0][1]["url"] == "abc"

    def test_thread_safe_concurrent_increments(self) -> None:
        """Concurrent producers must not race the counters."""
        import threading

        tel = RateLimitTelemetry()
        def hammer() -> None:
            for _ in range(100):
                tel.on_attempt("u", 200, 1)
                tel.on_success("u", 1)
        threads = [threading.Thread(target=hammer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert tel.total_sends == 800
        assert tel.total_successes == 800
        assert len(tel.attempts_to_success) == 800


# ---------------------------------------------------------------------------
# RecordingTelemetry unit tests
# ---------------------------------------------------------------------------
class TestRecordingTelemetry:
    def test_records_events(self) -> None:
        tel = RecordingTelemetry()
        tel.on_attempt("u", 200, 1)
        tel.on_success("u", 1)
        assert [e.name for e in tel.events] == ["attempt", "success"]

    def test_event_payload_captured(self) -> None:
        tel = RecordingTelemetry()
        tel.on_retry_scheduled("u", 1, 2.5, "429")
        assert len(tel.events) == 1
        e = tel.events[0]
        assert e.name == "retry_scheduled"
        assert e.payload["delay"] == 2.5
        assert e.payload["reason"] == "429"

    def test_event_names_helper(self) -> None:
        tel = RecordingTelemetry()
        tel.on_attempt("u", 200, 1)
        tel.on_retry_scheduled("u", 1, 1.0, "5xx")
        tel.on_attempt("u", 200, 2)
        tel.on_success("u", 2)
        assert tel.event_names() == [
            "attempt", "retry_scheduled", "attempt", "success"
        ]

    def test_counters_also_incremented(self) -> None:
        # The recording subclass still maintains the parent's counters.
        tel = RecordingTelemetry()
        tel.on_attempt("u", 429, 1)
        tel.on_retry_scheduled("u", 1, 1.0, "429")
        tel.on_attempt("u", 200, 2)
        tel.on_success("u", 2)
        assert tel.total_sends == 2
        assert tel.total_rate_limited == 1
        assert tel.total_retries == 1
        assert tel.total_successes == 1


# ---------------------------------------------------------------------------
# send_payload telemetry wiring
# ---------------------------------------------------------------------------
class TestSendPayloadTelemetry:
    def test_success_records_attempt_and_success(self) -> None:
        tel = RecordingTelemetry()
        poster = _Poster([200])
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=0,
            telemetry=tel,
        )
        assert ok is True
        assert tel.event_names() == ["attempt", "success"]
        assert tel.total_successes == 1
        assert tel.attempts_to_success == [1]

    def test_retry_429_records_two_attempts_and_one_retry(self) -> None:
        tel = RecordingTelemetry()
        poster = _Poster([(429, {"Retry-After": "0.0"}), 200])
        sleep_calls: list[float] = []
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=3,
            sleep_fn=sleep_calls.append,
            telemetry=tel,
        )
        assert ok is True
        names = tel.event_names()
        # attempt, retry_scheduled, attempt, success
        assert names == [
            "attempt", "retry_scheduled", "attempt", "success"
        ]
        assert tel.total_retries == 1
        assert tel.total_rate_limited == 1
        assert tel.attempts_to_success == [2]

    def test_retry_5xx_records_retry(self) -> None:
        tel = RecordingTelemetry()
        poster = _Poster([500, 200])
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=3,
            sleep_fn=lambda _: None,
            telemetry=tel,
        )
        assert ok is True
        assert tel.total_retries == 1
        assert tel.total_5xx == 1
        assert "retry_scheduled" in tel.event_names()

    def test_exhausted_retries_records_failure(self) -> None:
        tel = RecordingTelemetry()
        poster = _Poster([500, 500, 500, 500])  # 1 + 3 retries
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=3,
            sleep_fn=lambda _: None,
            telemetry=tel,
        )
        assert ok is False
        assert tel.total_failures == 1
        assert tel.attempts_to_failure == [4]
        assert "failure" in tel.event_names()

    def test_non_retryable_records_failure(self) -> None:
        tel = RecordingTelemetry()
        poster = _Poster([400])
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=3,
            sleep_fn=lambda _: None,
            telemetry=tel,
        )
        assert ok is False
        assert tel.total_failures == 1
        assert tel.total_4xx == 1

    def test_network_error_records_attempt_with_none_status(self) -> None:
        tel = RecordingTelemetry()

        def raising_poster(*args: Any, **kwargs: Any) -> None:
            raise ConnectionError("boom")

        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=raising_poster,
            max_retries=0,
            telemetry=tel,
        )
        assert ok is False
        assert tel.total_failures == 1
        assert tel.attempts_to_failure == [1]

    def test_no_telemetry_is_zero_overhead(self) -> None:
        # When telemetry=None, no event hooks fire — but the
        # call still succeeds.
        poster = _Poster([200])
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=0,
            telemetry=None,
        )
        assert ok is True
        assert poster.calls[0]["url"] == "https://example.invalid/hook"

    def test_embed_fallback_emits_telemetry_per_fallback_post(self) -> None:
        # 400 on the embed payload triggers the per-embed fallback.
        # The first 400 returns False (embed), then 200s for each
        # fallback content. We expect: attempt(400), failure, then
        # for each embed: attempt(200), success.
        tel = RecordingTelemetry()
        poster = _Poster([400, 200, 200])
        ok = send_payload(
            "https://example.invalid/hook",
            {
                "embeds": [
                    {"title": "A", "description": "first"},
                    {"title": "B", "description": "second"},
                ]
            },
            poster=poster,
            max_retries=0,
            telemetry=tel,
        )
        assert ok is True
        # 1 attempt + 1 failure (the 400) + 2 fallback attempts
        # + 2 successes.
        assert tel.event_names() == [
            "attempt", "failure",
            "attempt", "success",
            "attempt", "success",
        ]
        assert tel.total_successes == 2
        assert tel.total_failures == 1


# ---------------------------------------------------------------------------
# send_payload thread_id / thread_name injection
# ---------------------------------------------------------------------------
class TestSendPayloadThreadId:
    def test_thread_id_injected_into_payload(self) -> None:
        poster = _Poster([200])
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            thread_id="123456789",
        )
        assert ok is True
        assert poster.calls[0]["json"]["thread_id"] == "123456789"

    def test_thread_name_injected_into_payload(self) -> None:
        poster = _Poster([200])
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            thread_name="EOD-2026-07-14",
        )
        assert ok is True
        assert poster.calls[0]["json"]["thread_name"] == "EOD-2026-07-14"

    def test_thread_id_coerced_to_string(self) -> None:
        poster = _Poster([200])
        send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            thread_id=987654321,  # int, not str
        )
        assert poster.calls[0]["json"]["thread_id"] == "987654321"

    def test_no_thread_id_means_no_field(self) -> None:
        poster = _Poster([200])
        send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
        )
        assert "thread_id" not in poster.calls[0]["json"]
        assert "thread_name" not in poster.calls[0]["json"]


# ---------------------------------------------------------------------------
# send_embeds telemetry + thread_id
# ---------------------------------------------------------------------------
class TestSendEmbedsTelemetry:
    def test_per_batch_attempt_and_success(self) -> None:
        tel = RecordingTelemetry()
        # 3 embeds, max_embeds=2 → 2 batches
        embeds = [
            {"title": "A", "description": "1"},
            {"title": "B", "description": "2"},
            {"title": "C", "description": "3"},
        ]
        poster = _Poster([200, 200])
        sent = send_embeds(
            "https://example.invalid/hook",
            embeds,
            poster=poster,
            max_embeds=2,
            telemetry=tel,
        )
        assert sent == 2
        # Each batch produces: attempt, success.
        assert tel.event_names() == [
            "attempt", "success",
            "attempt", "success",
        ]
        assert tel.total_successes == 2

    def test_thread_id_propagated_to_each_batch(self) -> None:
        embeds = [{"title": "A"}, {"title": "B"}]
        poster = _Poster([200, 200])
        send_embeds(
            "https://example.invalid/hook",
            embeds,
            poster=poster,
            max_embeds=1,
            thread_id="111",
        )
        assert poster.calls[0]["json"]["thread_id"] == "111"
        assert poster.calls[1]["json"]["thread_id"] == "111"


# ---------------------------------------------------------------------------
# send_with_files telemetry + thread_id
# ---------------------------------------------------------------------------
class TestSendWithFilesTelemetry:
    def test_single_chunk_records_attempt_and_success(self) -> None:
        tel = RecordingTelemetry()
        poster = _Poster([200])
        ok = send_with_files(
            "https://example.invalid/hook",
            "hello world",
            [],
            poster=poster,
            max_retries=0,
            telemetry=tel,
        )
        assert ok is True
        assert tel.event_names() == ["attempt", "success"]

    def test_thread_id_propagated(self) -> None:
        poster = _Poster([200])
        send_with_files(
            "https://example.invalid/hook",
            "hello",
            [],
            poster=poster,
            thread_id="222",
        )
        assert poster.calls[0]["json"]["thread_id"] == "222"

    def test_thread_name_propagated(self) -> None:
        poster = _Poster([200])
        send_with_files(
            "https://example.invalid/hook",
            "hello",
            [],
            poster=poster,
            thread_name="EOD-Thread",
        )
        assert poster.calls[0]["json"]["thread_name"] == "EOD-Thread"


# ---------------------------------------------------------------------------
# send_message telemetry + thread_id
# ---------------------------------------------------------------------------
class TestSendMessageTelemetry:
    def test_records_attempt_and_success(self) -> None:
        tel = RecordingTelemetry()
        poster = _Poster([200])
        ok = send_message(
            "https://example.invalid/hook",
            message="hello",
            poster=poster,
            telemetry=tel,
        )
        assert ok is True
        assert tel.event_names() == ["attempt", "success"]

    def test_thread_id_propagated(self) -> None:
        poster = _Poster([200])
        send_message(
            "https://example.invalid/hook",
            message="hello",
            poster=poster,
            thread_id="333",
        )
        assert poster.calls[0]["json"]["thread_id"] == "333"


# ---------------------------------------------------------------------------
# send_summary telemetry + thread_id
# ---------------------------------------------------------------------------
class _FakePoster2:
    """Used by TestSendSummaryTelemetry — same shape as the
    existing _FakePoster but with a public ``calls`` list of
    ``(url, payload, timeout)`` tuples (matching ``requests.post``
    signature) so we can inspect the per-chunk JSON payload."""

    def __init__(self, *, fail_indices: set[int] | None = None) -> None:
        self.calls: list[tuple[str, dict, int]] = []
        self.fail_indices = fail_indices or set()
        self._counter = 0

    def __call__(self, url: str, json: dict, timeout: int) -> None:
        idx = self._counter
        self._counter += 1
        if idx in self.fail_indices:
            raise RuntimeError(f"simulated failure for chunk {idx}")
        self.calls.append((url, json, timeout))


class TestSendSummaryTelemetry:
    def test_per_chunk_attempt_and_success(self) -> None:
        tel = RecordingTelemetry()
        # 3 chunks
        webhooks = _write_webhooks({"macro-alerts": "https://example.invalid/hook"})
        summary = "".join(f"\n## S{i}\n" + ("x" * 1500) for i in range(3))
        delivered = send_summary(
            summary,
            webhook_key="macro-alerts",
            webhooks_path=webhooks,
            max_chars=1900,
            poster=_FakePoster2(),
            telemetry=tel,
        )
        assert delivered == 3
        # 3 chunks × (attempt, success) = 6 events.
        assert tel.event_names() == [
            "attempt", "success",
            "attempt", "success",
            "attempt", "success",
        ]
        assert tel.total_successes == 3
        assert tel.attempts_to_success == [1, 2, 3]

    def test_per_chunk_failure_recorded(self) -> None:
        # When one chunk POST raises, send_summary records a failure.
        tel = RecordingTelemetry()
        webhooks = _write_webhooks({"macro-alerts": "https://example.invalid/hook"})
        poster = _FakePoster2(fail_indices={0, 2})  # 1st and 3rd chunk fail
        summary = "".join(f"\n## S{i}\n" + ("x" * 1500) for i in range(3))
        delivered = send_summary(
            summary,
            webhook_key="macro-alerts",
            webhooks_path=webhooks,
            max_chars=1900,
            poster=poster,
            telemetry=tel,
        )
        assert delivered == 1
        # attempt(fail), failure, attempt(success), success,
        # attempt(fail), failure.
        names = tel.event_names()
        assert names == [
            "attempt", "failure",
            "attempt", "success",
            "attempt", "failure",
        ]
        assert tel.total_successes == 1
        assert tel.total_failures == 2

    def test_thread_id_propagated_to_each_chunk(self) -> None:
        webhooks = _write_webhooks({"macro-alerts": "https://example.invalid/hook"})
        poster = _FakePoster2()
        summary = "".join(f"\n## S{i}\n" + ("x" * 1500) for i in range(2))
        send_summary(
            summary,
            webhook_key="macro-alerts",
            webhooks_path=webhooks,
            max_chars=1900,
            poster=poster,
            thread_id="444",
        )
        assert poster.calls[0][1]["thread_id"] == "444"
        assert poster.calls[1][1]["thread_id"] == "444"

    def test_thread_name_propagated_to_each_chunk(self) -> None:
        webhooks = _write_webhooks({"macro-alerts": "https://example.invalid/hook"})
        poster = _FakePoster2()
        send_summary(
            "## S1\n" + ("x" * 1500) + "\n## S2\n" + ("x" * 1500),
            webhook_key="macro-alerts",
            webhooks_path=webhooks,
            max_chars=1900,
            poster=poster,
            thread_name="EOD-2026-07-14",
        )
        assert poster.calls[0][1]["thread_name"] == "EOD-2026-07-14"


# ---------------------------------------------------------------------------
# Public API surface — Tier 3
# ---------------------------------------------------------------------------
def test_public_api_surface_is_stable_tier3() -> None:
    """Guard against accidental rename of the Tier-3 entry points."""
    expected = {
        # Tier-3 telemetry
        "RateLimitTelemetry",
        "RecordingTelemetry",
        "TelemetryEvent",
        "default_sink",
    }
    exported = set(discord_lib.__all__)
    assert expected.issubset(exported), (
        f"Missing Tier-3 public symbols: {expected - exported}"
    )


# ---------------------------------------------------------------------------
# Telemetry + thread_id combined
# ---------------------------------------------------------------------------
def test_thread_id_and_telemetry_work_together() -> None:
    """A send call that uses both thread_id and telemetry emits
    the thread_id in the payload AND records telemetry events."""
    tel = RecordingTelemetry()
    poster = _Poster([200])
    ok = send_payload(
        "https://example.invalid/hook",
        {"content": "hi"},
        poster=poster,
        thread_id="555",
        telemetry=tel,
    )
    assert ok is True
    assert poster.calls[0]["json"]["thread_id"] == "555"
    assert tel.event_names() == ["attempt", "success"]
    assert tel.total_successes == 1
