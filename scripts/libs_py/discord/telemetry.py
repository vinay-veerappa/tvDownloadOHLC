# filepath: scripts/libs_py/discord/telemetry.py
"""Rate-limit and send-attempt telemetry for the Discord sub-package.

After Tier 2 added 429/5xx retry with capped exponential backoff,
operators had logs to read but **no aggregate counters** to answer
"are we getting throttled?" This module provides:

* :class:`RateLimitTelemetry` — a stateful object that hooks into
  the send functions and counts attempts, successes, failures,
  429s, 5xxs, network errors, and total backoff time. The
  counters can be snapshotted, reset, or dumped to a structured
  log via a pluggable ``sink``.

* :class:`RecordingTelemetry` — a test-friendly subclass that
  captures every event in a list, used by
  ``tests/test_discord_sender.py`` to assert event sequences
  without touching the network or the clock.

Design notes
------------
* **Zero overhead when unused** — every public send function
  accepts ``telemetry: Optional[RateLimitTelemetry] = None``. When
  ``None`` (the default) the hooks are skipped entirely, so
  short-lived scripts and tests pay nothing.

* **Pluggable sink** — the default sink writes structured
  ``log.info("telemetry.<event> key=value key=value")`` lines that
  any log aggregator (Datadog, Splunk, Loki) can parse. Operators
  can supply their own ``sink`` callable to forward events to
  Prometheus, a custom metrics endpoint, etc.

* **Thread-safe** — the counters are protected by a single
  ``threading.Lock`` so concurrent producers (e.g. multiple
  threads calling :func:`send_summary` simultaneously) do not
  race the counters.

Public surface
--------------
* :class:`RateLimitTelemetry`
* :class:`RecordingTelemetry`
* :func:`record_attempt`
* :func:`record_retry_scheduled`
* :func:`record_success`
* :func:`record_failure`
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

__all__ = (
    "RateLimitTelemetry",
    "RecordingTelemetry",
    "TelemetryEvent",
    "default_sink",
)


# ---------------------------------------------------------------------------
# Sink protocol
# ---------------------------------------------------------------------------
TelemetrySink = Callable[[str, dict[str, Any]], None]


def default_sink(event: str, payload: dict[str, Any]) -> None:
    """Default sink: emit structured ``log.info`` lines.

    Format: ``telemetry.<event> k1=v1 k2=v2 ...`` — easy to
    grep and easy to parse with a log aggregator.
    """
    parts = [f"{k}={v}" for k, v in payload.items()]
    log.info("telemetry.%s %s", event, " ".join(parts))


# ---------------------------------------------------------------------------
# Event record (used by RecordingTelemetry)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TelemetryEvent:
    """A single telemetry event captured by :class:`RecordingTelemetry`."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    monotonic: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# RateLimitTelemetry
# ---------------------------------------------------------------------------
class RateLimitTelemetry:
    """Aggregate counters for Discord send attempts and rate-limit hits.

    Construct one of these, pass it to every :func:`send_payload`
    (and friends) call you care about, and then either inspect
    :meth:`snapshot` at the end of a batch or call :meth:`summary`
    to dump a one-line status to the log via the sink.

    Example
    -------
    >>> tel = RateLimitTelemetry()
    >>> send_summary("hello", webhook_key="macro-alerts", telemetry=tel)
    1
    >>> tel.snapshot()["total_successes"]
    1
    >>> tel.summary()
    '... 1 send(s) ... 0 retry(s) ...'
    """

    def __init__(
        self,
        *,
        sink: Optional[TelemetrySink] = None,
        url_label: Optional[Callable[[str], str]] = None,
    ) -> None:
        """Create a fresh telemetry object.

        Parameters
        ----------
        sink:
            Callable ``(event_name, payload) -> None`` invoked
            for every event. Defaults to :func:`default_sink`,
            which writes a structured ``log.info`` line. Pass
            ``lambda *_: None`` for a fully silent object.
        url_label:
            Optional callable that maps a full webhook URL to a
            short label (e.g. the webhook key) for log
            readability. Default is the identity (raw URL).
        """
        self._sink: TelemetrySink = sink if sink is not None else default_sink
        self._url_label = url_label or (lambda u: u)
        self._lock = threading.Lock()
        self._start = time.monotonic()
        self.reset()

    # -----------------------------------------------------------------
    # State management
    # -----------------------------------------------------------------
    def reset(self) -> None:
        """Zero all counters and reset the start clock.

        Useful between unrelated test cases, or for callers that
        want a "per-report" reset before sending a batch.
        """
        with self._lock:
            self._start = time.monotonic()
            self.total_sends: int = 0
            self.total_successes: int = 0
            self.total_failures: int = 0
            self.total_retries: int = 0
            self.total_rate_limited: int = 0
            self.total_5xx: int = 0
            self.total_4xx: int = 0
            self.total_network_errors: int = 0
            self.total_backoff_seconds: float = 0.0
            self.attempts_to_success: list[int] = []
            self.attempts_to_failure: list[int] = []
            # Per-status tally (e.g. {200: 17, 429: 3, 500: 1}).
            self.status_counts: dict[int, int] = {}

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of the current counters as a plain dict.

        The ``attempts_to_success`` and ``attempts_to_failure``
        lists are copied so the caller can iterate without
        racing the producer.
        """
        with self._lock:
            return {
                "total_sends": self.total_sends,
                "total_successes": self.total_successes,
                "total_failures": self.total_failures,
                "total_retries": self.total_retries,
                "total_rate_limited": self.total_rate_limited,
                "total_5xx": self.total_5xx,
                "total_4xx": self.total_4xx,
                "total_network_errors": self.total_network_errors,
                "total_backoff_seconds": round(
                    self.total_backoff_seconds, 3
                ),
                "elapsed_seconds": round(
                    time.monotonic() - self._start, 3
                ),
                "attempts_to_success": list(self.attempts_to_success),
                "attempts_to_failure": list(self.attempts_to_failure),
                "status_counts": dict(self.status_counts),
                "avg_attempts_to_success": (
                    round(
                        sum(self.attempts_to_success)
                        / len(self.attempts_to_success),
                        3,
                    )
                    if self.attempts_to_success
                    else 0.0
                ),
            }

    def summary(self) -> str:
        """Return a one-line human-readable summary.

        Example
        -------
        >>> tel.summary()
        'sends=10 success=10 failure=0 retry=0 rate_limit=0 '
        '5xx=0 network=0 backoff=0.0s avg_attempts=1.0'
        """
        s = self.snapshot()
        return (
            f"sends={s['total_sends']} "
            f"success={s['total_successes']} "
            f"failure={s['total_failures']} "
            f"retry={s['total_retries']} "
            f"rate_limit={s['total_rate_limited']} "
            f"5xx={s['total_5xx']} "
            f"network={s['total_network_errors']} "
            f"backoff={s['total_backoff_seconds']}s "
            f"avg_attempts={s['avg_attempts_to_success']}"
        )

    # -----------------------------------------------------------------
    # Hooks called from the send functions
    # -----------------------------------------------------------------
    def on_attempt(
        self,
        url: str,
        status: Optional[int],
        attempt: int,
        retry_after: Optional[float] = None,
    ) -> None:
        """Record a single HTTP attempt (success or failure).

        Called once per ``_post_once`` invocation from inside
        :func:`send_payload` and :func:`_post_payload_with_retry`.
        The first attempt has ``attempt=1``.
        """
        label = self._url_label(url)
        with self._lock:
            self.total_sends += 1
            if status is not None:
                self.status_counts[status] = (
                    self.status_counts.get(status, 0) + 1
                )
            if status == 429:
                self.total_rate_limited += 1
            elif status is not None and 500 <= status < 600:
                self.total_5xx += 1
            elif status is not None and 400 <= status < 500:
                self.total_4xx += 1
        self._sink(
            "attempt",
            {
                "url": label,
                "status": status,
                "attempt": attempt,
                "retry_after": retry_after,
            },
        )

    def on_retry_scheduled(
        self,
        url: str,
        attempt: int,
        delay: float,
        reason: str,
    ) -> None:
        """Record a backoff sleep that is about to happen.

        ``reason`` is one of ``"429"``, ``"5xx"``, ``"4xx"``,
        ``"network"``.
        """
        label = self._url_label(url)
        with self._lock:
            self.total_retries += 1
            self.total_backoff_seconds += delay
        self._sink(
            "retry_scheduled",
            {
                "url": label,
                "attempt": attempt,
                "delay": round(delay, 3),
                "reason": reason,
            },
        )

    def on_success(self, url: str, attempts: int) -> None:
        """Record a successful send (after all retries, if any)."""
        label = self._url_label(url)
        with self._lock:
            self.total_successes += 1
            self.attempts_to_success.append(attempts)
        self._sink(
            "success",
            {"url": label, "attempts": attempts},
        )

    def on_failure(
        self,
        url: str,
        status: Optional[int],
        attempts: int,
        reason: str,
    ) -> None:
        """Record a failed send (exhausted retries, or non-retryable)."""
        label = self._url_label(url)
        with self._lock:
            self.total_failures += 1
            self.attempts_to_failure.append(attempts)
        self._sink(
            "failure",
            {
                "url": label,
                "status": status,
                "attempts": attempts,
                "reason": reason,
            },
        )


# ---------------------------------------------------------------------------
# RecordingTelemetry — test-friendly subclass
# ---------------------------------------------------------------------------
class RecordingTelemetry(RateLimitTelemetry):
    """A :class:`RateLimitTelemetry` that records every event in a list.

    Tests instantiate this, pass it as ``telemetry=`` to a send
    function, and then assert on :attr:`events` to verify the
    exact event sequence (attempts, retries, success/failure).
    The sink is overridden to a no-op by default; pass
    ``sink=...`` to capture log lines too.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("sink", lambda *_: None)
        super().__init__(**kwargs)
        self.events: list[TelemetryEvent] = []

    def _record(self, name: str, payload: dict[str, Any]) -> None:
        self.events.append(
            TelemetryEvent(name=name, payload=dict(payload))
        )

    def on_attempt(  # type: ignore[override]
        self,
        url: str,
        status: Optional[int],
        attempt: int,
        retry_after: Optional[float] = None,
    ) -> None:
        self._record(
            "attempt",
            {
                "url": url,
                "status": status,
                "attempt": attempt,
                "retry_after": retry_after,
            },
        )
        # Still increment the parent counters so snapshot() works.
        super().on_attempt(url, status, attempt, retry_after)

    def on_retry_scheduled(  # type: ignore[override]
        self,
        url: str,
        attempt: int,
        delay: float,
        reason: str,
    ) -> None:
        self._record(
            "retry_scheduled",
            {
                "url": url,
                "attempt": attempt,
                "delay": delay,
                "reason": reason,
            },
        )
        super().on_retry_scheduled(url, attempt, delay, reason)

    def on_success(self, url: str, attempts: int) -> None:  # type: ignore[override]
        self._record(
            "success", {"url": url, "attempts": attempts}
        )
        super().on_success(url, attempts)

    def on_failure(  # type: ignore[override]
        self,
        url: str,
        status: Optional[int],
        attempts: int,
        reason: str,
    ) -> None:
        self._record(
            "failure",
            {
                "url": url,
                "status": status,
                "attempts": attempts,
                "reason": reason,
            },
        )
        super().on_failure(url, status, attempts, reason)

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def event_names(self) -> list[str]:
        """Return just the event names in order — useful for assertions."""
        return [e.name for e in self.events]
